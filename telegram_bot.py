import os
import asyncio
import contextvars
from datetime import date, datetime, timedelta
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from database import get_bot_db_connection as get_db_connection, salvar_presenca_supabase
from alerts_manager import AlertsManager

# Estado global da conversação do bot por chat_id
chat_states = {}

# Caches e Contextos para permissões dinâmicas no menu do Telegram
current_user_id = contextvars.ContextVar('current_user_id', default=None)
USER_PERMISSIONS_CACHE = {}

TIPOS_DISPENSA = [
    'Total (todas as atividades)',
    'Para Esforço Físico',
    'Para Atividades Externas',
    'Para Armamento',
    'Parcial — Especificar abaixo',
]

TIPOS_LICENCA = [
    'Licença Para Tratamento de Saúde (LTS)',
    'Licença Especial',
    'Licença Nojo',
    'Licença Gala',
    'Afastamento Autorizado',
]

# Instância única do bot
bot = None
polling_task = None

def get_unauthorized_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row(types.KeyboardButton("📝 Solicitar Acesso"))
    return markup

def get_main_menu_keyboard():
    uid = current_user_id.get()
    allowed_features = USER_PERMISSIONS_CACHE.get(uid)
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    
    if allowed_features is None:
        # Se não carregou permissões ou não autorizado, mostra apenas Configurações e Cancelar
        markup.row(types.KeyboardButton("⚙️ Configurações"), types.KeyboardButton("❌ Cancelar"))
        return markup

    # Linha 1: Anotação e Resumo Diário
    row = []
    if 'menu_gestao_acoes' in allowed_features:
        row.append(types.KeyboardButton("📋 Anotação"))
    if 'menu_siscomca_dashboard' in allowed_features:
        row.append(types.KeyboardButton("📊 Resumo Diário"))
    if row:
        markup.row(*row)
        
    # Linha 2: Presença e Saúde
    row = []
    if 'menu_presenca' in allowed_features:
        row.append(types.KeyboardButton("📞 Presença"))
    if 'menu_saude' in allowed_features:
        row.append(types.KeyboardButton("🏥 Saúde"))
    if row:
        markup.row(*row)
        
    # Linha 3: Quadro de Avisos e Pernoite
    row = []
    if 'menu_avisos' in allowed_features:
        row.append(types.KeyboardButton("📢 Quadro de Avisos"))
    if 'menu_pernoite' in allowed_features:
        row.append(types.KeyboardButton("🛌 Lançar Pernoite"))
    if row:
        markup.row(*row)
        
    # Linha 4: Consulta de Aluno
    row = []
    if 'menu_alunos' in allowed_features:
        row.append(types.KeyboardButton("🔍 Consulta de Aluno"))
    if row:
        markup.row(*row)
        
    # Linha 5: Configurações, Ajuda e Cancelar
    markup.row(types.KeyboardButton("⚙️ Configurações"), types.KeyboardButton("ℹ️ Ajuda"), types.KeyboardButton("❌ Cancelar"))
    return markup

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Cancelar"))
    return markup

def get_settings_keyboard(is_authorized=True):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    if is_authorized:
        markup.row(types.KeyboardButton("📅 Ano Letivo"), types.KeyboardButton("🔔 Notificações"))
        markup.row(types.KeyboardButton("⬅️ Voltar"))
    else:
        markup.row(types.KeyboardButton("📝 Solicitar Acesso"), types.KeyboardButton("⬅️ Voltar"))
    return markup

def get_notifications_toggle_keyboard(user_prefs):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    
    st_silence = "🔴 SIM" if user_prefs.get("silence_all", False) else "🟢 NÃO"
    st_aviso = "🟢 ATIVADO" if user_prefs.get("notify_aviso", True) else "🔴 MUTADO"
    st_saude = "🟢 ATIVADO" if user_prefs.get("notify_saude", True) else "🔴 MUTADO"
    st_escala = "🟢 ATIVADO" if user_prefs.get("notify_escala", True) else "🔴 MUTADO"
    st_new_user = "🟢 ATIVADO" if user_prefs.get("notify_new_user", True) else "🔴 MUTADO"
    st_anotacao = "🟢 ATIVADO" if user_prefs.get("notify_anotacao", True) else "🔴 MUTADO"
    
    markup.row(types.KeyboardButton(f"📢 Letreiro/Avisos: {st_aviso}"), types.KeyboardButton(f"🏥 Saúde: {st_saude}"))
    markup.row(types.KeyboardButton(f"👮 Escalas: {st_escala}"), types.KeyboardButton(f"📋 Anotações: {st_anotacao}"))
    markup.row(types.KeyboardButton(f"👥 Novos Acessos: {st_new_user}"), types.KeyboardButton(f"🔇 Silenciar Tudo: {st_silence}"))
    markup.row(types.KeyboardButton("⬅️ Voltar"))
    return markup

def get_aviso_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row(types.KeyboardButton("📢 Novo Aviso"), types.KeyboardButton("📋 Listar Existentes"))
    markup.row(types.KeyboardButton("✏️ Editar Aviso"), types.KeyboardButton("❌ Remover/Excluir"))
    markup.row(types.KeyboardButton("🔒 Enviar Aviso Privado"), types.KeyboardButton("❌ Cancelar"))
    return markup

def get_duration_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row(types.KeyboardButton("1"), types.KeyboardButton("2"), types.KeyboardButton("3"))
    markup.row(types.KeyboardButton("5"), types.KeyboardButton("7"), types.KeyboardButton("10"))
    markup.row(types.KeyboardButton("15"), types.KeyboardButton("30"), types.KeyboardButton("❌ Cancelar"))
    return markup


def get_bot_token() -> str:
    """Busca o token do Telegram na tabela Config do banco ou no .env como fallback."""
    token = ""
    try:
        conn = get_db_connection()
        if conn:
            res = conn.table('Config').select('*').eq('chave', 'telegram_bot_token').execute()
            if res.data and res.data[0].get('valor'):
                token = res.data[0]['valor'].strip()
    except Exception as e:
        print(f"[Bot] Erro ao ler token do banco de dados: {e}")
    
    if not token:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
    return token

async def get_allowed_features_for_user(profile) -> set:
    allowed_features = set()
    if not profile:
        return allowed_features
    user_role = str(profile.get('role', 'compel')).strip().lower()
    
    defaults = {
        'menu_siscomca_dashboard': ['admin', 'supervisor', 'operador', 'comcia', 'compel', 'aluno', 'ajosca'],
        'menu_escalas': ['admin', 'supervisor', 'operador', 'comcia', 'ajosca'],
        'menu_alunos': ['admin', 'supervisor', 'operador'],
        'menu_gestao_acoes': ['admin', 'supervisor', 'operador', 'comcia'],
        'menu_presenca': ['admin', 'supervisor', 'operador', 'comcia', 'ajosca', 'compel'],
        'menu_saude': ['admin', 'supervisor', 'operador', 'comcia', 'ajosca'],
        'menu_pernoite': ['admin', 'supervisor', 'operador', 'comcia', 'ajosca'],
        'menu_avisos': ['admin', 'supervisor', 'comcia']
    }
    
    conn = get_db_connection()
    if conn:
        try:
            res = conn.table('Permissoes').select('*').execute()
            if res.data:
                for row in res.data:
                    fk = row.get('feature_key')
                    allowed = row.get('allowed_roles')
                    if fk and allowed:
                        defaults[fk] = [r.strip().lower() for r in allowed.split(',') if r.strip()]
        except Exception as e:
            print(f"[Bot] Erro ao ler Permissoes do banco: {e}")
            
    for fk, roles in defaults.items():
        if user_role in roles:
            allowed_features.add(fk)
    return allowed_features

async def check_authorized_user(from_user_id: int):
    """Verifica se o telegram_id está associado a um usuário autorizado no banco."""
    current_user_id.set(from_user_id)
    conn = get_db_connection()
    if not conn:
        return None
    try:
        res = conn.table('Users').select('*').eq('telegram_id', str(from_user_id)).execute()
        if res.data:
            # Ordena os perfis para colocar os que não são 'aluno' primeiro
            sorted_profiles = sorted(res.data, key=lambda u: 1 if u.get('role') == 'aluno' else 0)
            profile = sorted_profiles[0]
            allowed = await get_allowed_features_for_user(profile)
            USER_PERMISSIONS_CACHE[from_user_id] = allowed
            return profile
    except Exception as e:
        print(f"[Bot] Erro ao validar telegram_id {from_user_id}: {e}")
    return None

def clear_state(chat_id):
    if chat_id in chat_states:
        del chat_states[chat_id]

def get_user_active_year(profile):
    if not profile or 'id' not in profile:
        return '2026'
    from notifications_manager import get_user_preferences
    try:
        user_prefs = get_user_preferences(profile['id'])
        return user_prefs.get('ano_letivo_ativo', '2026')
    except Exception:
        return '2026'

async def prompt_pelotao_selection(bot_instance, message, state):
    conn = get_db_connection()
    pelotoes = []
    if conn:
        try:
            active_year = get_user_active_year(state.get('user'))
            res = conn.table('Alunos').select('pelotao').eq('ano_letivo', active_year).execute()
            if res.data:
                pelotoes = sorted(list(set([r['pelotao'] for r in res.data if r.get('pelotao')])))
        except Exception as e:
            print(f"[Bot] Erro ao carregar pelotões: {e}")
            
    if not pelotoes:
        pelotoes = ['1º Pelotão', '2º Pelotão', '3º Pelotão']
        
    state['step'] = 'choose_pelotao'
    state['data']['pelotoes'] = pelotoes
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    # Adiciona pelotões em linhas de 2
    for i in range(0, len(pelotoes), 2):
        row = [types.KeyboardButton(p) for p in pelotoes[i:i+2]]
        markup.row(*row)
    markup.row(types.KeyboardButton("🔍 Digitar / Lote"), types.KeyboardButton("❌ Cancelar"))
    
    action_map = {
        'anotacao': 'Anotação',
        'saude': 'Saúde',
        'pernoite': 'Pernoite',
        'presenca': 'Presença'
    }
    action_label = action_map.get(state['action'], 'Lançamento')
    await bot_instance.reply_to(
        message, 
        f"📋 {action_label}: Selecione o Pelotão do aluno (ou escolha digitar/lote):", 
        reply_markup=markup
    )

async def handle_pelotao_selection(bot_instance, message, state):
    chat_id = message.chat.id
    text = message.text.strip()
    conn = get_db_connection()
    if not conn:
        await bot_instance.reply_to(message, "❌ Sem conexão com o banco de dados.", reply_markup=get_main_menu_keyboard())
        clear_state(chat_id)
        return
        
    try:
        active_year = get_user_active_year(state.get('user'))
        res = conn.table('Alunos').select('*').eq('pelotao', text).eq('ano_letivo', active_year).execute()
        alunos_pelotao = res.data if res.data else []
    except Exception as e:
        await bot_instance.reply_to(message, f"❌ Erro ao ler alunos do pelotão: {e}", reply_markup=get_main_menu_keyboard())
        clear_state(chat_id)
        return
        
    if not alunos_pelotao:
        await bot_instance.reply_to(
            message, 
            f"❌ Nenhum aluno cadastrado no pelotão '{text}'.\n"
            "Escolha outro pelotão ou digite para buscar:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    state['step'] = 'choose_student_button'
    state['data']['alunos_pelotao'] = alunos_pelotao
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    # Ordena os alunos por ordem alfabética do nome de guerra
    alunos_pelotao_sorted = sorted(alunos_pelotao, key=lambda x: str(x.get('nome_guerra', '')).upper())
    for i in range(0, len(alunos_pelotao_sorted), 2):
        row = [types.KeyboardButton(f"MIKE {a['numero_interno']} - {a['nome_guerra']}") for a in alunos_pelotao_sorted[i:i+2]]
        markup.row(*row)
    markup.row(types.KeyboardButton("⬅️ Voltar"), types.KeyboardButton("❌ Cancelar"))
    await bot_instance.reply_to(message, f"📋 Alunos do {text}: Selecione o militar desejado abaixo:", reply_markup=markup)

async def handle_student_button_selection(bot_instance, message, state):
    chat_id = message.chat.id
    text = message.text.strip()
    
    alunos = state['data'].get('alunos_pelotao', [])
    selected = None
    if "MIKE " in text:
        try:
            num_int = text.split("MIKE ")[1].split(" -")[0].strip()
            selected = next((a for a in alunos if str(a.get('numero_interno')) == num_int), None)
        except Exception:
            pass
            
    if not selected:
        await bot_instance.reply_to(message, "⚠️ Militar não encontrado na lista. Por favor, clique em um dos botões abaixo:")
        return
        
    if state['action'] == 'anotacao':
        await prompt_action_type(bot_instance, message, state, selected)
    elif state['action'] == 'saude':
        await prompt_health_status(bot_instance, message, state, selected)
    elif state['action'] == 'pernoite':
        await prompt_pernoite_confirm(bot_instance, message, state, selected)

async def check_and_prompt_ano_letivo(bot_instance, message, profile):
    chat_id = message.chat.id
    from notifications_manager import get_user_preferences
    user_prefs = get_user_preferences(profile['id'])
    
    if not user_prefs.get('ano_letivo_ativo'):
        chat_states[chat_id] = {
            'action': 'select_initial_ano_letivo',
            'step': 'choose_year',
            'user': profile,
            'data': {}
        }
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.row(types.KeyboardButton("2025"), types.KeyboardButton("2026"))
        await bot_instance.send_message(
            chat_id,
            "📅 **Configuração Inicial: Ano Letivo**\n\n"
            "Antes de prosseguir, por favor escolha o **Ano Letivo Ativo** padrão para suas consultas e lançamentos de alunos:\n\n"
            "*(Você poderá alterar esta opção nas Configurações a qualquer momento)*",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return True
    return False

def setup_handlers(bot_instance):
    """Configura os ouvintes de mensagem no bot."""
    
    @bot_instance.message_handler(commands=['start', 'help', 'menu'])
    async def send_welcome(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        
        if not profile:
            welcome_text = (
                "⚓ **Comando Tático SisCOMCA** ⚓\n\n"
                "Olá! Você está acessando o assistente oficial do SisCOMCA por Telegram.\n\n"
                "⚠️ **Acesso Restrito / Não Autorizado**\n"
                f"Seu Telegram ID (`{message.from_user.id}`) não está vinculado a nenhum operador ativo no sistema.\n\n"
                "Para realizar qualquer tarefa, é necessário **solicitar acesso** para aprovação do Administrador.\n"
                "Clique no botão abaixo para preencher sua solicitação."
            )
            await bot_instance.reply_to(message, welcome_text, reply_markup=get_unauthorized_keyboard(), parse_mode='Markdown')
            return

        if await check_and_prompt_ano_letivo(bot_instance, message, profile):
            return

        welcome_text = (
            "⚓ **Comando Tático SisCOMCA** ⚓\n\n"
            f"Olá, {profile['nome']}! Eu sou o assistente oficial do SisCOMCA para lançamento de avisos, ocorrências, presença e saúde por Telegram.\n\n"
            "Use os botões do teclado abaixo para realizar as tarefas permitidas para o seu perfil."
        )
        
        await bot_instance.reply_to(message, welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')

    @bot_instance.message_handler(commands=['presenca', 'chamada'])
    async def register_presenca_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_presenca' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para acessar o menu de Presença.")
            return
            
        chat_states[chat_id] = {
            'action': 'presenca',
            'step': 'choose_initial_presenca_option',
            'user': profile,
            'data': {}
        }
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.row(types.KeyboardButton("📋 Realizar Chamada"), types.KeyboardButton("❌ Listar Faltosos (Ausentes)"))
        markup.row(types.KeyboardButton("❌ Cancelar"))
        
        await bot_instance.reply_to(message, "📞 Controle de Presença: Selecione uma opção abaixo:", reply_markup=markup)

    async def register_settings_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        
        chat_states[chat_id] = {
            'action': 'settings',
            'step': 'choose_option',
            'user': profile,
            'data': {}
        }
        
        is_authorized = profile is not None
        ano_letivo = "Não Definido"
        if is_authorized:
            from notifications_manager import get_user_preferences
            user_prefs = get_user_preferences(profile['id'])
            ano_letivo = user_prefs.get('ano_letivo_ativo', '2026')
            
        await bot_instance.reply_to(
            message,
            "⚙️ **CONFIGURAÇÕES DO SISTEMA**\n\n"
            f"📅 **Ano Letivo Ativo:** `{ano_letivo}`\n\n"
            "Escolha uma das opções de configuração abaixo:",
            reply_markup=get_settings_keyboard(is_authorized),
            parse_mode='Markdown'
        )

    @bot_instance.message_handler(commands=['settings', 'configuracoes', 'config'])
    async def register_settings_handler(message):
        await register_settings_command(message)

    @bot_instance.message_handler(commands=['atrasado', 'atraso'])
    async def register_atrasado_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_presenca' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para registrar atrasos (Presença).")
            return
            
        conn = get_db_connection()
        absent_students = []
        if conn:
            try:
                data_hoje = date.today().strftime('%Y-%m-%d')
                res_ausentes = conn.table('presenca_ausencia').select('*').eq('data', data_hoje).eq('presente', False).execute()
                absents = res_ausentes.data if res_ausentes.data else []
                if absents:
                    active_year = get_user_active_year(profile)
                    res_alunos = conn.table('Alunos').select('*').eq('ano_letivo', active_year).execute()
                    alunos = res_alunos.data if res_alunos.data else []
                    for ab in absents:
                        num = str(ab.get('numero_interno', '')).lower()
                        for al in alunos:
                            if str(al.get('numero_interno', '')).lower() == num:
                                absent_students.append(al)
                                break
            except Exception as e:
                print(f"[Bot] Erro ao carregar ausentes para atraso: {e}", flush=True)

        if absent_students:
            chat_states[chat_id] = {
                'action': 'atrasado',
                'step': 'choose_absent_student',
                'user': profile,
                'data': {'absent_students_list': absent_students}
            }
            
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for idx, al in enumerate(absent_students):
                markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
            markup.add(types.KeyboardButton(f"{len(absent_students) + 1} — 🔍 Buscar outro aluno"))
            markup.add(types.KeyboardButton("❌ Cancelar"))
            
            prompt = "🕒 Lançamento de Atrasado: Selecione o aluno que chegou atrasado na lista abaixo (ou escolha buscar outro):"
            await bot_instance.reply_to(message, prompt, reply_markup=markup)
        else:
            chat_states[chat_id] = {
                'action': 'atrasado',
                'step': 'search_student',
                'user': profile,
                'data': {}
            }
            await bot_instance.reply_to(
                message, 
                "🕒 Lançamento de Atrasado: Não há ausentes registrados hoje. Digite o nome de guerra ou número interno do aluno:",
                reply_markup=get_cancel_keyboard()
            )

    @bot_instance.message_handler(commands=['enfermaria', 'saude'])
    async def register_saude_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_saude' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para acessar a Enfermaria/Saúde.")
            return
            
        chat_states[chat_id] = {
            'action': 'saude',
            'step': 'choose_initial_option',
            'user': profile,
            'data': {}
        }
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.row(types.KeyboardButton("🆕 Novo Lançamento"), types.KeyboardButton("🏥 Listar Baixados"))
        markup.add(types.KeyboardButton("❌ Cancelar"))
        
        await bot_instance.reply_to(message, "🏥 Gestão de Saúde / Enfermaria: Selecione uma opção abaixo:", reply_markup=markup)

    @bot_instance.message_handler(commands=['cancelar'])
    async def cancel_action(message):
        chat_id = message.chat.id
        current_user_id.set(message.from_user.id)
        if message.from_user.id not in USER_PERMISSIONS_CACHE:
            await check_authorized_user(message.from_user.id)
        clear_state(chat_id)
        await bot_instance.reply_to(message, "❌ Operação cancelada com sucesso.", reply_markup=get_main_menu_keyboard())

    @bot_instance.message_handler(commands=['vincular'])
    async def link_user(message):
        await bot_instance.reply_to(
            message,
            "⚠️ O comando `/vincular` foi desativado por questões de segurança.\n"
            "Por favor, solicite acesso usando o botão correspondente e um Administrador associará seu Telegram ID ao seu perfil.",
            reply_markup=get_unauthorized_keyboard(),
            parse_mode='Markdown'
        )

    @bot_instance.message_handler(commands=['aviso'])
    async def register_aviso(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_avisos' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para acessar a gestão de Avisos.")
            return
            
        chat_states[chat_id] = {
            'action': 'aviso',
            'step': 'select_option',
            'user': profile
        }
        await bot_instance.reply_to(
            message, 
            "📢 **MENU AVISOS (TV & OPERADORES)**\n\n"
            "Escolha o que deseja fazer com os avisos no painel/TV ou para os operadores:", 
            reply_markup=get_aviso_menu_keyboard(), 
            parse_mode='Markdown'
        )

    @bot_instance.message_handler(commands=['anotacao'])
    async def register_anotacao(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_gestao_acoes' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para acessar o menu de Anotações.")
            return
            
        chat_states[chat_id] = {
            'action': 'anotacao',
            'step': 'choose_pelotao',
            'user': profile,
            'data': {}
        }
        await prompt_pelotao_selection(bot_instance, message, chat_states[chat_id])

    @bot_instance.message_handler(commands=['pernoite'])
    async def register_pernoite_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_pernoite' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para lançar Pernoite.")
            return
            
        chat_states[chat_id] = {
            'action': 'pernoite',
            'step': 'choose_pelotao',
            'user': profile,
            'data': {}
        }
        await prompt_pelotao_selection(bot_instance, message, chat_states[chat_id])

    @bot_instance.message_handler(commands=['resumo', 'parada'])
    async def register_resumo_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_siscomca_dashboard' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para visualizar o Resumo Diário.")
            return
            
        conn = get_db_connection()
        if not conn:
            await bot_instance.reply_to(message, "❌ Sem conexão com o banco de dados.")
            return

        await bot_instance.send_chat_action(chat_id, 'typing')
        
        try:
            hoje_str = datetime.now().strftime('%Y-%m-%d')
            hoje_br = datetime.now().strftime('%d/%m/%Y')
            
            active_year = get_user_active_year(profile)
            res_al = conn.table('Alunos').select('id, numero_interno, nome_guerra, pelotao').eq('ano_letivo', active_year).execute()
            alunos = res_al.data if res_al.data else []
            total_alunos = len(alunos)
            
            res_pr = conn.table('presenca_ausencia').select('*').eq('data', hoje_str).execute()
            presencas = res_pr.data if res_pr.data else []
            
            pres_map = {p['numero_interno']: p for p in presencas}
            
            presentes = []
            ausentes = []
            pendentes = []
            
            for al in alunos:
                ni = al['numero_interno']
                p_rec = pres_map.get(ni)
                if p_rec:
                    if p_rec.get('presente'):
                        presentes.append(al)
                    else:
                        ausentes.append((al, p_rec.get('motivo_ausencia') or 'Sem motivo'))
                else:
                    pendentes.append(al)
            
            total_pres = len(presentes)
            total_aus = len(ausentes)
            total_pend = len(pendentes)
            
            res_pn = conn.table('pernoite').select('*').eq('data', hoje_str).eq('presente', True).execute()
            pernoites = res_pn.data if res_pn.data else []
            total_pernoite = len(pernoites)
            
            res_enf = conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
            enfermaria_records = res_enf.data if res_enf.data else []
            
            baixados = []
            hospitalizados = []
            dispensados = []
            licenciados = []
            
            for row in enfermaria_records:
                cat = row.get('categoria') or 'enfermaria'
                status = row.get('status') or 'Ativo'
                data_ini = row.get('data_ini')
                data_fim = row.get('data_fim')
                
                esta_valido = True
                if data_ini and data_fim:
                    try:
                        esta_valido = (str(data_ini) <= hoje_str <= str(data_fim))
                    except Exception:
                        pass
                if not esta_valido:
                    continue
                    
                item = {
                    'ni': row.get('numero_interno', ''),
                    'nome': row.get('nome_guerra', '').upper(),
                    'motivo': row.get('motivo', 'Sem motivo')
                }
                
                if cat == 'licenca' or status == 'Licença' or status == 'Licenciado':
                    licenciados.append(item)
                elif status == 'Hospital' or status == 'Hospitalizado':
                    hospitalizados.append(item)
                elif cat == 'dispensa' or status == 'Dispensado':
                    dispensados.append(item)
                else:
                    baixados.append(item)
            
            added_nis = {x['ni'] for x in licenciados + baixados + hospitalizados + dispensados}
            for al, motivo in ausentes:
                if any(k in motivo.lower() for k in ['licen', 'licença', 'licenca', 'licena']):
                    ni = al['numero_interno']
                    if ni not in added_nis:
                        licenciados.append({
                            'ni': ni,
                            'nome': al['nome_guerra'].upper(),
                            'motivo': motivo
                        })
                        added_nis.add(ni)
            
            # 👮 Pessoal de Serviço de Hoje
            escala_text = ""
            try:
                res_es = conn.table('escala_diaria').select('*').eq('data', hoje_str).execute()
                escala_records = res_es.data if res_es.data else []
                if escala_records:
                    escala_text = "\n👮 **PESSOAL DE SERVIÇO DE HOJE:**\n"
                    for esc in escala_records:
                        cargo = esc.get('cargo', '').upper()
                        nome = esc.get('nome', '').upper()
                        if nome and nome != 'NÃO ESCALADO':
                            escala_text += f"• *{cargo}*: {nome}\n"
                else:
                    escala_text = "\n👮 **PESSOAL DE SERVIÇO DE HOJE:**\n• _(Nenhuma escala cadastrada para hoje)_\n"
            except Exception as e_esc:
                print(f"[BOT RESUMO ESCALA ERROR] {e_esc}")

            def format_list(items, show_motivo=False):
                if not items:
                    return " _(Nenhum)_"
                if show_motivo:
                    return "\n  ↳ _" + ", ".join([f"{x['ni']}—{x['nome']} ({x['motivo']})" for x in items]) + "_"
                return "\n  ↳ _" + ", ".join([f"{x['ni']}—{x['nome']}" for x in items]) + "_"
                
            ausentes_list = [{'ni': a[0]['numero_interno'], 'nome': a[0]['nome_guerra']} for a in ausentes]
            ausentes_str = format_list(ausentes_list)
            
            pernoite_names = []
            for pn in pernoites:
                aid = str(pn.get('aluno_id'))
                al_match = next((a for a in alunos if str(a['id']) == aid), None)
                if al_match:
                    pernoite_names.append({'ni': al_match['numero_interno'], 'nome': al_match['nome_guerra']})
            
            pernoite_nis = [f"{x['ni']}" for x in pernoite_names] if pernoite_names else []
            pernoite_str = "\n  ↳ _" + ", ".join(pernoite_nis) + "_" if pernoite_nis else " _(Nenhum)_"
            
            resumo_text = (
                f"📊 **RESUMO DIÁRIO — {hoje_br}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 **EFETIVO GERAL:**\n"
                f"• 📈 Total de Alunos: `{total_alunos}`\n"
                f"• ✅ Presentes: `{total_pres}`\n"
                f"• ❌ Ausentes: `{total_aus}`{ausentes_str}\n"
                f"• ⏳ Pendentes de Chamada: `{total_pend}`\n"
                f"{escala_text}\n"
                f"🛌 **PERNOITE (A BORDO):**\n"
                f"• 🛌 Autorizados: `{total_pernoite}`{pernoite_str}\n\n"
                f"🏥 **SITUAÇÃO DE SAÚDE / LICENÇAS:**\n"
                f"• 🏥 Internado/Observação: `{len(baixados)}`{format_list(baixados)}\n"
                f"• 🚑 Hospitalizado: `{len(hospitalizados)}`{format_list(hospitalizados)}\n"
                f"• 📝 Dispensas Ativas: `{len(dispensados)}`{format_list(dispensados, show_motivo=True)}\n"
                f"• ✈️ Licenças Ativas: `{len(licenciados)}`{format_list(licenciados, show_motivo=True)}"
            )
            
            await bot_instance.reply_to(message, resumo_text, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
        except Exception as e:
            await bot_instance.reply_to(message, f"❌ Erro ao gerar resumo: {e}")

    @bot_instance.message_handler(commands=['escala', 'servico'])
    async def register_escala_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_escalas' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para acessar a Escala de Serviço.")
            return
            
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.row(types.KeyboardButton("📅 Hoje"), types.KeyboardButton("📅 Amanhã"))
        markup.add(types.KeyboardButton("❌ Cancelar"))
        
        chat_states[chat_id] = {
            'action': 'escala',
            'step': 'choose_date',
            'user': profile,
            'data': {}
        }
        await bot_instance.reply_to(message, "📅 Escala de Serviço: Selecione o dia desejado:", reply_markup=markup)

    @bot_instance.message_handler(commands=['consulta', 'aluno'])
    async def register_consulta_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        profile = await check_authorized_user(message.from_user.id)
        if not profile:
            await bot_instance.reply_to(
                message, 
                f"⚠️ Acesso não autorizado!\nPor favor, utilize o botão abaixo para solicitar o acesso aos Administradores do sistema (Seu Telegram ID: {message.from_user.id}).",
                reply_markup=get_unauthorized_keyboard()
            )
            return
            
        allowed = USER_PERMISSIONS_CACHE.get(message.from_user.id, set())
        if 'menu_alunos' not in allowed:
            await bot_instance.reply_to(message, "⚠️ Seu perfil de usuário não tem permissão correlata no app para fazer Consulta de Aluno.")
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            term = args[1].strip()
            await perform_consulta_search(bot_instance, message, profile, term)
        else:
            chat_states[chat_id] = {
                'action': 'consulta',
                'step': 'search_student',
                'user': profile,
                'data': {}
            }
            await bot_instance.reply_to(message, "🔍 Consulta de Aluno: Digite o nome de guerra ou número interno do aluno:", reply_markup=get_cancel_keyboard())

    @bot_instance.message_handler(commands=['ajuda', 'help'])
    async def register_ajuda_command(message):
        chat_id = message.chat.id
        clear_state(chat_id)
        
        help_text = (
            "ℹ️ **MANUAL DE AJUDA — SisCOMCA BOT**\n\n"
            "Este assistente permite gerenciar o efetivo de alunos diretamente do Telegram. Veja abaixo os menus e funções disponíveis:\n\n"
            "📋 **Anotação**: Lança ocorrências disciplinares ou elogios para os alunos. Permite selecionar o aluno e o tipo de ação (positiva, neutra ou negativa).\n\n"
            "📊 **Resumo Diário**: Exibe um sumário geral do efetivo de hoje, incluindo contagem de presentes, baixados na enfermaria, internados no hospital e licenciados.\n\n"
            "📞 **Presença**: Permite realizar a chamada diária de um pelotão específico (marcando todos presentes ou definindo ausentes com justificativa) e listar os faltosos do dia.\n\n"
            "🏥 **Saúde**: Lança alterações de saúde dos alunos (Enfermaria, Hospital, Dispensa Médica, NAS), definindo o status de saúde e datas de dispensa correspondentes.\n\n"
            "📢 **Quadro de Avisos**: Adiciona, edita, remove ou exibe avisos na TV e no painel do letreiro digital.\n\n"
            "🛌 **Lançar Pernoite**: Registra autorizações de pernoite para alunos hoje. Permite digitar múltiplos números internos separados por vírgula para inserção em massa.\n\n"
            "🔍 **Consulta de Aluno**: Busca a ficha cadastral de um aluno, histórico recente de pontuações, ocorrências e pendências administrativas. Você pode digitar o nome ou o **número interno** do aluno diretamente.\n\n"
            "📅 **Ano Letivo**: Todo o aplicativo e as consultas referem-se ao ano letivo selecionado nas suas configurações. Inicialmente, ao iniciar o bot, você define o ano letivo padrão (ex: 2026), e este pode ser alterado a qualquer momento em Configurações.\n\n"
            "⚙️ **Configurações**: Permite alterar o ano letivo ativo do bot, solicitar acesso de novos operadores, gerenciar toggles de notificações específicas ou vincular sua conta web."
        )
        await bot_instance.reply_to(message, help_text, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')

    @bot_instance.message_handler(func=lambda msg: True)
    async def handle_normal_message(message):
        chat_id = message.chat.id
        text = message.text.strip() if message.text else ""
        
        # Define o ID do usuário corrente no contexto da requisição
        current_user_id.set(message.from_user.id)
        
        # Garante que as permissões estejam no cache para renderizar o teclado corretamente
        if message.from_user.id not in USER_PERMISSIONS_CACHE:
            await check_authorized_user(message.from_user.id)
            
        # Cancelamento global/Voltar ao menu: trata "cancelar", "voltar", "menu principal", etc.
        clean_text = text.lower()
        cancel_terms = ["cancelar", "menu principal", "voltar pro menu", "voltar para o menu", "voltar ao menu"]
        is_cancel = any(term in clean_text for term in cancel_terms) or clean_text in ["voltar", "⬅️ voltar"]
        
        if is_cancel:
            clear_state(chat_id)
            await bot_instance.reply_to(message, "🏠 Retornando ao Menu Principal.", reply_markup=get_main_menu_keyboard())
            return
            
        state = chat_states.get(chat_id)
        if not state:
            profile = await check_authorized_user(message.from_user.id)
            clean_text = text.lower()
            
            if not profile:
                if "solicitar acesso" in clean_text:
                    # Inicializa o estado de configurações e direciona para solicitação
                    chat_states[chat_id] = {
                        'action': 'settings',
                        'step': 'request_access_name',
                        'user': None,
                        'data': {}
                    }
                    await bot_instance.reply_to(message, "📝 **Solicitação de Acesso**\n\nPor favor, digite seu **Nome Completo**:", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
                    return
                elif "configuracao" in clean_text or "configuração" in clean_text or "configurações" in clean_text or "configuracoes" in clean_text or "settings" in clean_text:
                    await register_settings_command(message)
                    return
                
                welcome_text = (
                    "⚓ **Comando Tático SisCOMCA** ⚓\n\n"
                    "⚠️ **Acesso Restrito / Não Autorizado**\n"
                    f"Seu Telegram ID (`{message.from_user.id}`) não está vinculado a nenhum operador ativo no sistema.\n\n"
                    "Para realizar qualquer tarefa, é necessário **solicitar acesso** para aprovação do Administrador.\n"
                    "Clique no botão abaixo para preencher sua solicitação."
                )
                await bot_instance.reply_to(message, welcome_text, reply_markup=get_unauthorized_keyboard(), parse_mode='Markdown')
                return

            if await check_and_prompt_ano_letivo(bot_instance, message, profile):
                return

            if "resumo" in clean_text or "parada" in clean_text:
                await register_resumo_command(message)
                return
            elif "escala" in clean_text or "serviço" in clean_text or "servico" in clean_text:
                await register_escala_command(message)
                return
            elif "consulta" in clean_text or "aluno" in clean_text:
                await register_consulta_command(message)
                return
            elif "anotação" in clean_text or "anotacao" in clean_text or "ocorrência" in clean_text or "ocorrencia" in clean_text:
                await register_anotacao(message)
                return
            elif "presenca" in clean_text or "chamada" in clean_text or "presença" in clean_text:
                await register_presenca_command(message)
                return
            elif "atrasado" in clean_text or "atraso" in clean_text:
                await register_atrasado_command(message)
                return
            elif "enfermaria" in clean_text or "saúde" in clean_text or "saude" in clean_text:
                await register_saude_command(message)
                return
            elif "aviso" in clean_text:
                await register_aviso(message)
                return
            elif "pernoite" in clean_text:
                await register_pernoite_command(message)
                return
            elif "configuração" in clean_text or "configuracao" in clean_text or "configurações" in clean_text or "configuracoes" in clean_text or "settings" in clean_text:
                await register_settings_command(message)
                return
            elif "ajuda" in clean_text or "help" in clean_text or "ℹ️ ajuda" in clean_text:
                await register_ajuda_command(message)
                return
            elif "cancelar" in clean_text:
                await cancel_action(message)
                return

            welcome_text = (
                "⚠️ Comando ou opção não reconhecida.\n\n"
                "Para iniciar uma conversa ou operação, use os botões abaixo ou um dos comandos:\n"
                "🔹 `/resumo` (ou `/parada`) : Exibe o resumo do efetivo e saúde de hoje.\n"
                "🔹 `/escala` (ou `/servico`) : Consulta, adiciona e altera a escala.\n"
                "🔹 `/consulta` (ou `/aluno`) : Exibe a ficha e ocorrências de um aluno.\n"
                "🔹 `/anotacao` : Inicia o lançamento de comportamento de alunos.\n"
                "🔹 `/enfermaria` (ou `/saude`) : Inicia o lançamento de registros de saúde.\n"
                "🔹 `/pernoite` : Lança autorização de pernoite para hoje.\n"
                "🔹 `/aviso` : Adiciona um aviso no letreiro da TV.\n"
                "🔹 `/menu` : Exibe o menu principal do SisCOMCA.\n"
                "🔹 `/cancelar` : Aborta qualquer operação em andamento."
            )
            
            await bot_instance.reply_to(message, welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
            return
            
        action = state['action']
        step = state['step']
        text = message.text.strip()
        
        conn = get_db_connection()
        if not conn:
            await bot_instance.reply_to(message, "❌ Sem conexão com o banco de dados. Operação abortada.")
            clear_state(chat_id)
            return

        # ── CONFIGURAÇÃO DE ANO LETIVO INICIAL ─────────────────────────
        if action == 'select_initial_ano_letivo':
            if step == 'choose_year':
                ano_escolhido = text.strip()
                if ano_escolhido not in ['2025', '2026']:
                    await bot_instance.reply_to(message, "⚠️ Escolha inválida. Por favor, clique em um dos botões: 2025 ou 2026")
                    return
                
                from notifications_manager import get_user_preferences, save_user_preferences
                profile = state['user']
                user_prefs = get_user_preferences(profile['id'])
                user_prefs['ano_letivo_ativo'] = ano_escolhido
                save_user_preferences(profile['id'], user_prefs)
                
                await bot_instance.reply_to(
                    message,
                    f"✅ **Ano Letivo configurado com sucesso!**\n\n"
                    f"Seu ano letivo ativo agora é **{ano_escolhido}**.\n"
                    f"Você pode iniciar suas atividades usando o menu principal.",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
                clear_state(chat_id)
                return

        # ── PROCESSAMENTO DO AVISO ────────────────────────────────────
        if action == 'aviso':
            if text.lower() in ['cancelar', '❌ cancelar']:
                await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                clear_state(chat_id)
                return

            autor = state['user'].get('nome', 'TELEGRAM').upper()

            if step == 'select_option':
                clean_opt = text.lower()
                if "novo" in clean_opt or "adicionar" in clean_opt:
                    state['step'] = 'get_text'
                    await bot_instance.reply_to(message, "📢 Digite o texto do aviso que deseja exibir/enviar:", reply_markup=get_cancel_keyboard())
                    return
                elif "listar" in clean_opt or "existente" in clean_opt:
                    try:
                        today_str = date.today().strftime('%Y-%m-%d')
                        res = conn.table('Ordens_Diarias').select('*').eq('data', today_str).execute()
                        active_list = res.data if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler avisos: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    if not active_list:
                        await bot_instance.reply_to(message, "📋 **Avisos de Hoje na TV**:\nNenhum aviso cadastrado para hoje no letreiro da TV.", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    resp = "📋 **AVISOS ATIVOS HOJE NA TV:**\n\n"
                    for i, o in enumerate(active_list):
                        resp += f"🔹 *{i+1}* - \"{o['texto']}\" (Autor: {o.get('autor_id', 'TELEGRAM')})\n\n"
                    
                    await bot_instance.reply_to(message, resp, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
                    clear_state(chat_id)
                    return
                elif "editar" in clean_opt:
                    try:
                        today_str = date.today().strftime('%Y-%m-%d')
                        res = conn.table('Ordens_Diarias').select('*').eq('data', today_str).execute()
                        active_list = res.data if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler avisos: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    if not active_list:
                        await bot_instance.reply_to(message, "⚠️ Nenhum aviso ativo cadastrado para hoje.", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    state['active_avisos'] = active_list
                    state['step'] = 'select_edit_index'
                    
                    response_text = "✏️ **Selecione o aviso que deseja editar:**\n\n"
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for i, o in enumerate(active_list):
                        idx = i + 1
                        response_text += f"*{idx}* - \"{o['texto']}\" (Autor: {o.get('autor_id', 'TELEGRAM')})\n\n"
                        markup.add(types.KeyboardButton(str(idx)))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, response_text + "Digite ou clique no número correspondente:", reply_markup=markup, parse_mode='Markdown')
                    return
                elif "remover" in clean_opt or "excluir" in clean_opt:
                    try:
                        today_str = date.today().strftime('%Y-%m-%d')
                        res = conn.table('Ordens_Diarias').select('*').eq('data', today_str).execute()
                        active_list = res.data if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler avisos: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    if not active_list:
                        await bot_instance.reply_to(message, "⚠️ Nenhum aviso cadastrado para hoje.", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    state['active_avisos'] = active_list
                    state['step'] = 'select_remove_index'
                    
                    response_text = "❌ **Selecione o aviso que deseja remover do letreiro da TV:**\n\n"
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for i, o in enumerate(active_list):
                        idx = i + 1
                        response_text += f"*{idx}* - \"{o['texto']}\" (Autor: {o.get('autor_id', 'TELEGRAM')})\n\n"
                        markup.add(types.KeyboardButton(str(idx)))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, response_text + "Digite ou clique no número correspondente:", reply_markup=markup, parse_mode='Markdown')
                    return
                elif "privado" in clean_opt:
                    try:
                        res = conn.table('Users').select('*').execute()
                        recipients = [u for u in res.data if u.get('telegram_id') and str(u.get('telegram_id')).strip()] if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler operadores cadastrados: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    if not recipients:
                        await bot_instance.reply_to(message, "⚠️ Nenhum outro operador possui Telegram ID associado no SisCOMCA.", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    state['recipients'] = recipients
                    state['step'] = 'select_recipient_index'
                    
                    response_text = "🔒 **Selecione o operador que receberá o aviso privado:**\n\n"
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for i, u in enumerate(recipients):
                        idx = i + 1
                        response_text += f"*{idx}* - {u.get('nome', 'Sem Nome').upper()} ({u.get('email', 'Sem Email')})\n"
                        markup.add(types.KeyboardButton(str(idx)))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, response_text + "\nDigite ou clique no número correspondente:", reply_markup=markup, parse_mode='Markdown')
                    return
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Selecione uma das opções abaixo:", reply_markup=get_aviso_menu_keyboard())
                    return

            elif step == 'get_text':
                state['aviso_text'] = text
                state['step'] = 'select_target'
                
                # Pergunta destinatário
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                markup.row(types.KeyboardButton("📺 Letreiro da TV (Todos)"), types.KeyboardButton("🔒 Operador Específico (Privado)"))
                markup.add(types.KeyboardButton("❌ Cancelar"))
                
                await bot_instance.reply_to(
                    message, 
                    "📺 **DESTINATÁRIO DO AVISO**\n\n"
                    "Onde deseja publicar este aviso?\n"
                    "🔹 **Letreiro da TV (Todos)**: Fica rodando na TV da parada.\n"
                    "🔹 **Operador Específico (Privado)**: Notificação particular para o Telegram de um operador específico.", 
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
                return

            elif step == 'select_target':
                clean_target = text.lower()
                aviso_text = state.get('aviso_text', '')
                
                if "tv" in clean_target or "todos" in clean_target or "letreiro" in clean_target:
                    # Salva no letreiro da TV
                    try:
                        conn.table('Ordens_Diarias').insert({
                            'data': date.today().strftime('%Y-%m-%d'),
                            'texto': aviso_text,
                            'autor_id': autor,
                            'status': 'Ativo'
                        }).execute()
                        
                        # Transmite à TV
                        AlertsManager.trigger_alert(
                            "Novo Aviso",
                            f"Aviso publicado por {autor}: {aviso_text}",
                            "info"
                        )
                        
                        try:
                            from notifications_manager import notify_telegram
                            alert_txt = (
                                f"📢 **NOVO AVISO CRÍTICO PUBLICADO**\n"
                                f"👤 Autor: {autor}\n\n"
                                f"\"{aviso_text}\""
                            )
                            notify_telegram(alert_txt, "aviso")
                        except Exception as e_notif:
                            print(f"[BOT AVISO NOTIFY ERROR] {e_notif}")
                        
                        await bot_instance.reply_to(message, "✅ Aviso gravado com sucesso e transmitido para a TV!", reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao gravar aviso na TV: {e}", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                        
                elif "operador" in clean_target or "privado" in clean_target or "especifico" in clean_target:
                    # Selecionar Operador
                    try:
                        res = conn.table('Users').select('*').execute()
                        recipients = [u for u in res.data if u.get('telegram_id') and str(u.get('telegram_id')).strip()] if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler operadores cadastrados: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    if not recipients:
                        await bot_instance.reply_to(message, "⚠️ Nenhum outro operador possui Telegram ID associado no SisCOMCA para receber avisos privados.", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    
                    state['recipients'] = recipients
                    state['step'] = 'select_recipient_index'
                    
                    response_text = "🔒 **Selecione o operador que receberá o aviso privado:**\n\n"
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for i, u in enumerate(recipients):
                        idx = i + 1
                        response_text += f"*{idx}* - {u.get('nome', 'Sem Nome').upper()} ({u.get('email', 'Sem Email')})\n"
                        markup.add(types.KeyboardButton(str(idx)))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, response_text + "\nDigite ou clique no número correspondente:", reply_markup=markup, parse_mode='Markdown')
                    return
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Selecione Letreiro da TV ou Operador Específico:")
                    return

            elif step == 'select_edit_index':
                try:
                    idx = int(text) - 1
                    active_list = state.get('active_avisos', [])
                    if idx < 0 or idx >= len(active_list):
                        raise ValueError()
                    selected = active_list[idx]
                except (ValueError, TypeError):
                    await bot_instance.reply_to(message, "⚠️ Número inválido. Digite um número válido da lista ou clique em Cancelar:")
                    return
                
                state['selected_aviso'] = selected
                state['step'] = 'get_edit_text'
                await bot_instance.reply_to(message, f"✏️ Aviso selecionado:\n\"{selected['texto']}\"\n\nDigite o novo texto para este aviso:", reply_markup=get_cancel_keyboard())
                return

            elif step == 'get_edit_text':
                selected = state.get('selected_aviso')
                if not selected:
                    await bot_instance.reply_to(message, "❌ Erro ao recuperar aviso selecionado. Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                try:
                    conn.table('Ordens_Diarias').update({
                        'texto': text,
                        'autor_id': autor
                    }).eq('id', selected['id']).execute()
                    
                    # Transmite à TV
                    AlertsManager.trigger_alert(
                        "Aviso Atualizado",
                        f"Aviso atualizado por {autor}: {text}",
                        "info"
                    )
                    
                    try:
                        from notifications_manager import notify_telegram
                        alert_txt = (
                            f"✏️ **AVISO ATUALIZADO NA TV**\n"
                            f"👤 Autor: {autor}\n\n"
                            f"Novo Texto: \"{text}\""
                        )
                        notify_telegram(alert_txt, "aviso")
                    except Exception as e_notif:
                        print(f"[BOT AVISO EDIT NOTIFY ERROR] {e_notif}")
                    
                    await bot_instance.reply_to(message, "✅ Aviso atualizado com sucesso e transmitido para a TV!", reply_markup=get_main_menu_keyboard())
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao atualizar aviso: {e}", reply_markup=get_main_menu_keyboard())
                clear_state(chat_id)
                return

            elif step == 'select_remove_index':
                try:
                    idx = int(text) - 1
                    active_list = state.get('active_avisos', [])
                    if idx < 0 or idx >= len(active_list):
                        raise ValueError()
                    selected = active_list[idx]
                except (ValueError, TypeError):
                    await bot_instance.reply_to(message, "⚠️ Número inválido. Digite um número válido da lista ou clique em Cancelar:")
                    return
                
                try:
                    conn.table('Ordens_Diarias').delete().eq('id', selected['id']).execute()
                    
                    # Transmite à TV
                    AlertsManager.trigger_alert(
                        "Aviso Removido",
                        f"Aviso publicado por {selected.get('autor_id', 'OPERADOR')} foi removido por {autor}.",
                        "warning"
                    )
                    
                    try:
                        from notifications_manager import notify_telegram
                        alert_txt = (
                            f"❌ **AVISO REMOVIDO DO LETREIRO**\n"
                            f"👤 Removido por: {autor}\n\n"
                            f"Texto antigo: \"{selected['texto']}\""
                        )
                        notify_telegram(alert_txt, "aviso")
                    except Exception as e_notif:
                        print(f"[BOT AVISO REMOVE NOTIFY ERROR] {e_notif}")
                    
                    await bot_instance.reply_to(message, "✅ Aviso removido com sucesso!", reply_markup=get_main_menu_keyboard())
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao remover aviso: {e}", reply_markup=get_main_menu_keyboard())
                clear_state(chat_id)
                return

            elif step == 'select_recipient_index':
                try:
                    idx = int(text) - 1
                    recipients = state.get('recipients', [])
                    if idx < 0 or idx >= len(recipients):
                        raise ValueError()
                    selected = recipients[idx]
                except (ValueError, TypeError):
                    await bot_instance.reply_to(message, "⚠️ Número inválido. Digite um número válido da lista ou clique em Cancelar:")
                    return
                
                state['selected_recipient'] = selected
                state['step'] = 'get_private_text'
                await bot_instance.reply_to(message, f"🔒 Enviar Aviso Privado para {selected.get('nome', 'OPERADOR').upper()}:\nDigite o texto do aviso que deseja enviar em privado:", reply_markup=get_cancel_keyboard())
                return

            elif step == 'get_private_text':
                selected = state.get('selected_recipient')
                if not selected or not selected.get('telegram_id'):
                    await bot_instance.reply_to(message, "❌ Erro ao recuperar operador selecionado ou o ID é inválido. Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                try:
                    recipient_tg = int(selected['telegram_id'])
                    alert_txt = (
                        f"🔒 **AVISO PRIVADO RECEBIDO**\n"
                        f"👤 Remetente: {autor}\n"
                        f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                        f"\"{text}\""
                    )
                    await bot_instance.send_message(recipient_tg, alert_txt, parse_mode='Markdown')
                    await bot_instance.reply_to(message, f"✅ Aviso privado enviado com sucesso para {selected.get('nome', 'OPERADOR').upper()}!", reply_markup=get_main_menu_keyboard())
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao enviar aviso privado: {e}", reply_markup=get_main_menu_keyboard())
                clear_state(chat_id)
                return

        # ── PROCESSAMENTO DA ANOTAÇÃO ─────────────────────────────────
        elif action == 'anotacao':
            if step == 'choose_pelotao':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                if "digitar" in text.lower() or "lote" in text.lower() or "buscar" in text.lower():
                    state['step'] = 'search_student'
                    await bot_instance.reply_to(message, "🔍 Digite o nome de guerra ou número interno do aluno:", reply_markup=get_cancel_keyboard())
                    return
                await handle_pelotao_selection(bot_instance, message, state)
                return
                
            elif step == 'choose_student_button':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                if "voltar" in text.lower() or "⬅️" in text:
                    await prompt_pelotao_selection(bot_instance, message, state)
                    return
                await handle_student_button_selection(bot_instance, message, state)
                return

            # Passo 1: Busca de Alunos
            elif step == 'search_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    active_year = get_user_active_year(state.get('user'))
                    res = conn.table('Alunos').select('*').eq('ano_letivo', active_year).execute()
                    alunos = res.data if res.data else []
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}")
                    clear_state(chat_id)
                    return
                
                matches = []
                query = text.lower()
                for al in alunos:
                    num = str(al.get('numero_interno', '')).lower()
                    nome = str(al.get('nome_guerra', '')).lower()
                    if query in num or query in nome or num.endswith("-" + query) or num.endswith(query):
                        matches.append(al)
                
                if not matches:
                    await bot_instance.reply_to(message, f"⚠️ Nenhum aluno encontrado com '{text}'. Digite novamente ou selecione Cancelar:", reply_markup=get_cancel_keyboard())
                    return
                
                # Ordena os resultados da busca por ordem alfabética do nome de guerra
                matches = sorted(matches, key=lambda x: str(x.get('nome_guerra', '')).upper())
                
                if len(matches) > 1:
                    state['step'] = 'choose_student'
                    state['data']['matches'] = matches[:10] # Limita a 10 opções
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, al in enumerate(state['data']['matches']):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
 
                    prompt = "🔍 Múltiplos alunos encontrados. Selecione o correspondente abaixo:\n\n"
                    for idx, al in enumerate(state['data']['matches']):
                        prompt += f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']} ({al['pelotao']})\n"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup)
                else:
                    await prompt_action_type(bot_instance, message, state, matches[0])
            
            # Passo 2: Seleção de Aluno em Lista
            elif step == 'choose_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                matches = state['data'].get('matches', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(matches):
                        selected = matches[choice - 1]
                        await prompt_action_type(bot_instance, message, state, selected)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número entre 1 e {len(matches)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")
 
            # Passo 3: Escolha do Tipo de Ocorrência
            elif step == 'choose_action_type':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                tipos = state['data'].get('tipos', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(tipos):
                        selected_type = tipos[choice - 1]
                        state['step'] = 'get_description'
                        state['data']['tipo'] = selected_type
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("⏭️ Pular"), types.KeyboardButton("❌ Cancelar"))
                        
                        await bot_instance.reply_to(
                            message, 
                            f"📝 Tipo selecionado: {selected_type['nome']}\n\n"
                            "Digite a descrição/justificativa para esta ocorrência (ou escolha Pular):",
                            reply_markup=markup
                        )
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número entre 1 e {len(tipos)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente ao tipo de ação:")
 
            # Passo 4: Justificativa/Descrição
            elif step == 'get_description':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                desc = "" if text in ("/pular", "⏭️ Pular", "⏭️ pular", "pular") else text
                state['step'] = 'confirm_submit'
                state['data']['description'] = desc
                
                student = state['data']['student']
                tipo = state['data']['tipo']
                pts = float(tipo.get('pontuacao', 0.0) or 0.0)
                
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))

                confirm_prompt = (
                    "⚠️ Confirmar Lançamento?\n\n"
                    f"👤 Aluno: {student['nome_guerra']} ({student['numero_interno']})\n"
                    f"🛡️ Tipo: {tipo['nome']} ({pts:+.1f} pts)\n"
                    f"📝 Justificativa: {desc or 'Nenhuma'}\n\n"
                    "Selecione uma das opções abaixo:"
                )
                await bot_instance.reply_to(message, confirm_prompt, reply_markup=markup)

            # Passo 5: Confirmação Final
            elif step == 'confirm_submit':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — confirmar']:
                    try:
                        student = state['data']['student']
                        tipo = state['data']['tipo']
                        desc = state['data']['description']
                        usuario = state['user'].get('nome', 'TELEGRAM').upper()
                        
                        conn.table('Acoes').insert({
                            'aluno_id': str(student['id']),
                            'tipo_acao_id': str(tipo['id']),
                            'tipo': tipo['nome'],
                            'descricao': desc,
                            'data': date.today().strftime('%Y-%m-%d'),
                            'usuario': usuario,
                            'status': 'Pendente'
                        }).execute()
                        
                        aluno_lbl = f"{student.get('numero_interno', '')} — {str(student.get('nome_guerra', '')).upper()} ({str(student.get('pelotao', '')).upper()})"
                        pts = float(tipo.get('pontuacao', 0.0) or 0.0)
                        
                        # Determina se é relacionado a saúde para ser laranja (warning)
                        is_saude = False
                        lbl_upper = tipo['nome'].upper()
                        for h in ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]:
                            if h in lbl_upper:
                                is_saude = True
                                
                        alert_type = "success" if pts > 0 else "alert" if pts < 0 else "info"
                        if is_saude:
                            alert_type = "warning"
                            
                        AlertsManager.trigger_alert(
                            "Registro de Ocorrência",
                            f"{aluno_lbl} recebeu {tipo['nome'].upper()} por {usuario}!",
                            alert_type
                        )
                        
                        await bot_instance.reply_to(message, "✅ Ocorrência registrada em status PENDENTE e transmitida para a TV!", reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao salvar ocorrência: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                elif ans in ['n', 'não', 'nao', 'no', 'n — cancelar', 'cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Lançamento abortado.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Responda apenas com S (Sim) ou N (Não):")

        elif action == 'presenca':
            # Passo Inicial: Escolha entre Realizar Chamada ou Listar Faltosos
            if step == 'choose_initial_presenca_option':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                if "realizar chamada" in text.lower():
                    pelotoes = []
                    if conn:
                        try:
                            active_year = get_user_active_year(state.get('user'))
                            res = conn.table('Alunos').select('pelotao').eq('ano_letivo', active_year).execute()
                            if res.data:
                                pelotoes = sorted(list(set([r['pelotao'] for r in res.data if r.get('pelotao')])))
                        except Exception as e:
                            print(f"Erro ao carregar pelotões: {e}")
                    if not pelotoes:
                        pelotoes = ['1º Pelotão', '2º Pelotão', '3º Pelotão']
                    state['data']['pelotoes'] = pelotoes
                    state['step'] = 'choose_pelotao'
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, pel in enumerate(pelotoes):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {pel}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    prompt = "📋 Chamada Diária: Selecione a Turma (Pelotão) abaixo:\n\n"
                    for idx, pel in enumerate(pelotoes):
                        prompt += f"{idx + 1} — {pel}\n"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup, parse_mode='Markdown')
                
                elif "listar faltosos" in text.lower():
                    try:
                        data_hoje = date.today().strftime('%Y-%m-%d')
                        res_ausentes = conn.table('presenca_ausencia').select('*').eq('data', data_hoje).eq('presente', False).execute()
                        absents = res_ausentes.data if res_ausentes.data else []
                        
                        absent_students = []
                        if absents:
                            active_year = get_user_active_year(state.get('user'))
                            res_alunos = conn.table('Alunos').select('*').eq('ano_letivo', active_year).execute()
                            alunos = res_alunos.data if res_alunos.data else []
                            for ab in absents:
                                num = str(ab.get('numero_interno', '')).lower()
                                for al in alunos:
                                    if str(al.get('numero_interno', '')).lower() == num:
                                        absent_students.append(al)
                                        break
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler faltosos: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                        
                    if not absent_students:
                        await bot_instance.reply_to(message, "🟢 Nenhum aluno está marcado como AUSENTE hoje!", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                        
                    state['step'] = 'choose_faltoso_student'
                    state['data']['faltosos_list'] = absent_students
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, al in enumerate(absent_students):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    prompt = "❌ **LISTA DE FALTOSOS DE HOJE**\n\nSelecione o aluno para gerenciar a ausência:"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup, parse_mode='Markdown')
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Selecione uma das opções do teclado:")

            elif step == 'choose_faltoso_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                faltosos = state['data']['faltosos_list']
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(faltosos):
                        selected = faltosos[choice - 1]
                        state['data']['selected_student'] = selected
                        state['step'] = 'choose_faltoso_action'
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("✅ Dar Presença (Apenas)"), types.KeyboardButton("🕒 Lançar Atraso (Presença + Ocorrência)"))
                        markup.row(types.KeyboardButton("⬅️ Voltar"), types.KeyboardButton("❌ Cancelar"))
                        
                        prompt = (
                            f"👤 **Aluno**: {selected['nome_guerra']} ({selected['numero_interno']})\n"
                            f"📋 **Turma**: {selected['pelotao']}\n\n"
                            "Selecione uma ação rápida para este militar:"
                        )
                        await bot_instance.reply_to(message, prompt, reply_markup=markup, parse_mode='Markdown')
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(faltosos)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Selecione um militar clicando nos botões ou envie Cancelar:")

            elif step == 'choose_faltoso_action':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                elif "voltar" in text.lower() or "⬅️" in text.lower():
                    # Volta para a lista de faltosos
                    state['step'] = 'choose_initial_presenca_option'
                    message.text = "❌ Listar Faltosos (Ausentes)"
                    await handle_normal_message(message)
                    return
                    
                selected = state['data']['selected_student']
                if "dar presença" in text.lower() or "dar presenca" in text.lower():
                    try:
                        salvar_presenca_supabase(
                            numero_interno=selected['numero_interno'],
                            nome_guerra=selected['nome_guerra'],
                            turma=selected['pelotao'],
                            presente=True
                        )
                        await bot_instance.reply_to(message, f"✅ Presença gravada com sucesso para {selected['nome_guerra']} ({selected['numero_interno']})!", reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao salvar presença: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                elif "atraso" in text.lower():
                    # Direciona para a confirmação de atraso reutilizando prompt_atrasado_confirm
                    state['action'] = 'atrasado'
                    await prompt_atrasado_confirm(bot_instance, message, state, conn, selected)
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Selecione uma das opções do teclado:")

            # Passo 1: Escolha do Pelotão
            elif step == 'choose_pelotao':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                pelotoes = state['data']['pelotoes']
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(pelotoes):
                        pelotao = pelotoes[choice - 1]
                        state['data']['pelotao'] = pelotao
                        state['step'] = 'choose_presenca_mode'
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.add(types.KeyboardButton("1 — Marcar TODOS como PRESENTES"))
                        markup.add(types.KeyboardButton("2 — Marcar todos como PRESENTES, EXCETO ausentes"))
                        markup.add(types.KeyboardButton("❌ Cancelar"))

                        prompt = (
                            f"Turma Selecionada: {pelotao}\n\n"
                            "Selecione o tipo de lançamento de presença abaixo:"
                        )
                        await bot_instance.reply_to(message, prompt, reply_markup=markup)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(pelotoes)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 2: Escolha do Modo de Presença
            elif step == 'choose_presenca_mode':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    pelotao = state['data']['pelotao']
                    if choice == 1:
                        state['data']['mode'] = 'todos_presentes'
                        state['step'] = 'confirm_presenca_submit'
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))

                        confirm_prompt = (
                            f"⚠️ Confirmar Lançamento de Presença Coletiva?\n\n"
                            f"📋 Turma: {pelotao}\n"
                            f"📊 Lançamento: TODOS PRESENTES\n\n"
                            "Selecione uma das opções abaixo:"
                        )
                        await bot_instance.reply_to(message, confirm_prompt, reply_markup=markup)
                    elif choice == 2:
                        state['data']['mode'] = 'ausentes_excecao'
                        state['step'] = 'get_absent_numbers'
                        await bot_instance.reply_to(
                            message,
                            "🚫 Digite o Número Interno dos ausentes separados por vírgula (ex: 101, 105, 210):\n"
                            "Ou envie `/cancelar` para abortar:",
                            reply_markup=get_cancel_keyboard()
                        )
                    else:
                        await bot_instance.reply_to(message, "⚠️ Opção inválida. Escolha '1' ou '2':")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")
            # Passo 3: Obter Números dos Ausentes
            elif step == 'get_absent_numbers':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                pelotao = state['data']['pelotao']
                
                try:
                    res = conn.table('Alunos').select('*').eq('pelotao', pelotao).execute()
                    alunos_pelotao = res.data if res.data else []
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao ler alunos do pelotão: {e}", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                if not alunos_pelotao:
                    await bot_instance.reply_to(message, f"❌ Nenhum aluno cadastrado no pelotão {pelotao}. Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return

                raw_inputs = [x.strip() for x in text.split(',')]
                absent_students = []
                not_found = []
                
                for ri in raw_inputs:
                    if not ri:
                        continue
                    found = False
                    for al in alunos_pelotao:
                        num_str = str(al.get('numero_interno', '')).strip().lower()
                        term = ri.strip().lower()
                        if term == num_str or num_str.endswith("-" + term) or num_str.endswith(term):
                            absent_students.append(al)
                            found = True
                            break
                    if not found:
                        not_found.append(ri)
                
                if not absent_students:
                    await bot_instance.reply_to(
                        message, 
                        "⚠️ Nenhum aluno do pelotão correspondente foi encontrado com os termos inseridos.\n"
                        "Insira os números internos válidos novamente ou selecione Cancelar:",
                        reply_markup=get_cancel_keyboard()
                    )
                    return

                state['data']['absent_students'] = absent_students
                state['step'] = 'choose_absent_reason'
                
                warning_lbl = ""
                if not_found:
                    warning_lbl = f"⚠️ Não encontrados: {', '.join(not_found)}\n\n"

                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                markup.add(types.KeyboardButton("1 — Falta Injustificada"))
                markup.add(types.KeyboardButton("2 — Doença"))
                markup.add(types.KeyboardButton("3 — Licença"))
                markup.add(types.KeyboardButton("4 — Pernoite"))
                markup.add(types.KeyboardButton("5 — Saída Autorizada"))
                markup.add(types.KeyboardButton("6 — Outro"))
                markup.add(types.KeyboardButton("❌ Cancelar"))

                prompt = (
                    f"{warning_lbl}"
                    f"🚫 Ausentes Detectados:\n"
                    f"{', '.join([a['nome_guerra'] for a in absent_students])}\n\n"
                    "Selecione o motivo padrão de ausência abaixo:"
                )
                await bot_instance.reply_to(message, prompt, reply_markup=markup)

            # Passo 4: Escolha do Motivo da Ausência
            elif step == 'choose_absent_reason':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                reasons_map = {
                    1: 'Falta Injustificada',
                    2: 'Doença',
                    3: 'Licença',
                    4: 'Pernoite',
                    5: 'Saída Autorizada',
                    6: 'Outro'
                }
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if choice in reasons_map:
                        reason = reasons_map[choice]
                        state['data']['absent_reason'] = reason
                        state['step'] = 'confirm_presenca_submit'
                        
                        pelotao = state['data']['pelotao']
                        absent_students = state['data']['absent_students']
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))

                        confirm_prompt = (
                            f"⚠️ Confirmar Lançamento de Presença Coletiva?\n\n"
                            f"📋 Turma: {pelotao}\n"
                            f"📊 Lançamento: PRESENTES COM EXCEÇÕES\n"
                            f"🚫 Ausentes ({reason}):\n"
                            + '\n'.join([f"• {a['numero_interno']} — {a['nome_guerra']}" for a in absent_students])
                            + "\n\nSelecione uma das opções abaixo:"
                        )
                        await bot_instance.reply_to(message, confirm_prompt, reply_markup=markup)
                    else:
                        await bot_instance.reply_to(message, "⚠️ Opção inválida. Digite um número de 1 a 6:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente ao motivo:")

            # Passo 5: Confirmação e Inserção no Supabase
            elif step == 'confirm_presenca_submit':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — confirmar']:
                    try:
                        pelotao = state['data']['pelotao']
                        mode = state['data']['mode']
                        
                        res = conn.table('Alunos').select('*').eq('pelotao', pelotao).execute()
                        alunos_pelotao = res.data if res.data else []
                        
                        if mode == 'todos_presentes':
                            for al in alunos_pelotao:
                                salvar_presenca_supabase(
                                    numero_interno=al['numero_interno'],
                                    nome_guerra=al['nome_guerra'],
                                    turma=pelotao,
                                    presente=True
                                )
                            msg_sucesso = f"✅ Presença de todos os alunos da turma {pelotao} gravada com sucesso!"
                            msg_alerta = f"Chamada do pelotão {pelotao} realizada (Todos Presentes)!"
                        else:
                            absent_students = state['data']['absent_students']
                            reason = state['data']['absent_reason']
                            absent_ids = [a['id'] for a in absent_students]
                            
                            for al in alunos_pelotao:
                                is_present = al['id'] not in absent_ids
                                motivo = reason if not is_present else None
                                salvar_presenca_supabase(
                                    numero_interno=al['numero_interno'],
                                    nome_guerra=al['nome_guerra'],
                                    turma=pelotao,
                                    presente=is_present,
                                    motivo_ausencia=motivo
                                )
                            msg_sucesso = f"✅ Chamada da turma {pelotao} gravada com sucesso!"
                            msg_alerta = f"Chamada do pelotão {pelotao} realizada (Ausentes: {', '.join([a['nome_guerra'] for a in absent_students])})!"
                        
                        AlertsManager.trigger_alert("Chamada Diária", msg_alerta, "info")
                        await bot_instance.reply_to(message, msg_sucesso, reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao gravar chamada: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)

        elif action == 'atrasado':
            # Passo 1: Seleção de Aluno Ausente da Lista (ou Buscar outro)
            if step == 'choose_absent_student':
                absent_students = state['data']['absent_students_list']
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(absent_students):
                        selected = absent_students[choice - 1]
                        await prompt_atrasado_confirm(bot_instance, message, state, conn, selected)
                    elif choice == len(absent_students) + 1:
                        state['step'] = 'search_student'
                        await bot_instance.reply_to(message, "🔍 Digite o Nome de Guerra ou Número Interno do aluno:", reply_markup=get_cancel_keyboard())
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(absent_students) + 1}:")
                except ValueError:
                    # Se não for número, assume busca direta
                    if text.lower() in ['cancelar', '❌ cancelar']:
                        await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    state['step'] = 'search_student'
                    try:
                        res = conn.table('Alunos').select('*').execute()
                        alunos = res.data if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                        return
                    matches = []
                    query = text.lower()
                    for al in alunos:
                        num = str(al.get('numero_interno', '')).lower()
                        nome = str(al.get('nome_guerra', '')).lower()
                        if query in num or query in nome:
                            matches.append(al)
                    if not matches:
                        await bot_instance.reply_to(message, f"⚠️ Nenhum aluno encontrado com '{text}'. Digite novamente ou selecione Cancelar:", reply_markup=get_cancel_keyboard())
                        return
                    if len(matches) > 1:
                        state['step'] = 'choose_student'
                        state['data']['matches'] = matches[:10]
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        for idx, al in enumerate(state['data']['matches']):
                            markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
                        markup.add(types.KeyboardButton("❌ Cancelar"))
                        
                        prompt = "🔍 Múltiplos alunos encontrados. Selecione o correspondente abaixo:\n\n"
                        for idx, al in enumerate(state['data']['matches']):
                            prompt += f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']} ({al['pelotao']})\n"
                        await bot_instance.reply_to(message, prompt, reply_markup=markup)
                    else:
                        await prompt_atrasado_confirm(bot_instance, message, state, conn, matches[0])

            # Passo 2: Busca de Alunos
            elif step == 'search_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    res = conn.table('Alunos').select('*').execute()
                    alunos = res.data if res.data else []
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                matches = []
                query = text.lower()
                for al in alunos:
                    num = str(al.get('numero_interno', '')).lower()
                    nome = str(al.get('nome_guerra', '')).lower()
                    if query in num or query in nome:
                        matches.append(al)
                
                if not matches:
                    await bot_instance.reply_to(message, f"⚠️ Nenhum aluno encontrado com '{text}'. Digite novamente ou selecione Cancelar:", reply_markup=get_cancel_keyboard())
                    return
                
                if len(matches) > 1:
                    state['step'] = 'choose_student'
                    state['data']['matches'] = matches[:10]
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, al in enumerate(state['data']['matches']):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    prompt = "🔍 Múltiplos alunos encontrados. Selecione o correspondente abaixo:\n\n"
                    for idx, al in enumerate(state['data']['matches']):
                        prompt += f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']} ({al['pelotao']})\n"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup)
                else:
                    await prompt_atrasado_confirm(bot_instance, message, state, conn, matches[0])

            # Passo 3: Escolha do Aluno na lista de homônimos
            elif step == 'choose_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                matches = state['data'].get('matches', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(matches):
                        selected = matches[choice - 1]
                        await prompt_atrasado_confirm(bot_instance, message, state, conn, selected)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número entre 1 e {len(matches)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 4: Confirmação Final do Atraso
            elif step == 'confirm_atraso_submit':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — confirmar']:
                    try:
                        student = state['data']['student']
                        tipo_atraso = state['data']['tipo_atraso']
                        usuario = state['user'].get('nome', 'TELEGRAM').upper()
                        
                        # 1. Altera a presença de hoje para PRESENTE
                        hoje_str = date.today().strftime('%Y-%m-%d')
                        salvar_presenca_supabase(
                            numero_interno=student['numero_interno'],
                            nome_guerra=student['nome_guerra'],
                            turma=student['pelotao'],
                            presente=True,
                            motivo_ausencia=None
                        )
                        
                        # 2. Lança ocorrência de atraso
                        conn.table('Acoes').insert({
                            'aluno_id': str(student['id']),
                            'tipo_acao_id': str(tipo_atraso['id']),
                            'tipo': tipo_atraso['nome'],
                            'descricao': 'Atraso registrado via Telegram',
                            'data': hoje_str,
                            'usuario': usuario,
                            'status': 'Pendente'
                        }).execute()
                        
                        # Alerta na TV
                        aluno_lbl = f"{student.get('numero_interno', '')} — {str(student.get('nome_guerra', '')).upper()} ({str(student.get('pelotao', '')).upper()})"
                        AlertsManager.trigger_alert(
                            "Atraso Registrado",
                            f"{aluno_lbl} chegou atrasado e presença foi atualizada por {usuario}!",
                            "info"
                        )
                        await bot_instance.reply_to(
                            message, 
                            f"✅ Atraso Lançado com Sucesso!\n"
                            f"• Presença de {student['nome_guerra']} alterada para PRESENTE.\n"
                            f"• Ocorrência de ATRASO gravada em status PENDENTE.",
                            reply_markup=get_main_menu_keyboard()
                        )
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao salvar lançamento: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                elif ans in ['n', 'não', 'nao', 'no', 'n — cancelar', 'cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Lançamento abortado.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Responda apenas com S (Sim) ou N (Não):")
        elif action == 'saude':
            # Passo 0: Escolha da Opção Inicial (Novo Lançamento / Listar Baixados)
            if step == 'choose_initial_option':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                if "novo" in text.lower() or "lançamento" in text.lower() or "lancamento" in text.lower() or "🆕" in text:
                    await prompt_pelotao_selection(bot_instance, message, state)
                    return
                elif "baixados" in text.lower() or "listar" in text.lower() or "🏥" in text:
                    await bot_instance.send_chat_action(chat_id, 'typing')
                    try:
                        hoje_str = datetime.now().strftime('%Y-%m-%d')
                        res_enf = conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
                        active_records = res_enf.data if res_enf.data else []
                        
                        valid_records = []
                        for row in active_records:
                            data_ini = row.get('data_ini')
                            data_fim = row.get('data_fim')
                            esta_valido = True
                            if data_ini and data_fim:
                                try:
                                    esta_valido = (str(data_ini) <= hoje_str <= str(data_fim))
                                except Exception:
                                    pass
                            if esta_valido:
                                valid_records.append(row)
                                
                        if not valid_records:
                            await bot_instance.reply_to(message, "🟢 Não há alunos baixados ou com dispensas/licenças ativas no momento.", reply_markup=get_main_menu_keyboard())
                            clear_state(chat_id)
                            return
                            
                        state['step'] = 'choose_baixado'
                        state['data']['active_cases'] = valid_records[:10]
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        for idx, row in enumerate(state['data']['active_cases']):
                            markup.add(types.KeyboardButton(f"{idx + 1} — {row['numero_interno']} : {row['nome_guerra']} ({row['status']})"))
                        markup.add(types.KeyboardButton("❌ Cancelar"))
                        
                        prompt = "🏥 Militares Ativos na Enfermaria/Saúde:\nSelecione um para ver detalhes ou dar alta:\n\n"
                        for idx, row in enumerate(state['data']['active_cases']):
                            prompt += f"{idx + 1} — {row['numero_interno']} : {row['nome_guerra']} ({row['status']})\n"
                        await bot_instance.reply_to(message, prompt, reply_markup=markup)
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao listar baixados: {e}", reply_markup=get_main_menu_keyboard())
                        clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Escolha uma das opções: '🆕 Novo Lançamento' ou '🏥 Listar Baixados':")
            
            elif step == 'choose_pelotao':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                if "digitar" in text.lower() or "lote" in text.lower() or "buscar" in text.lower():
                    state['step'] = 'search_student'
                    await bot_instance.reply_to(message, "🔍 Digite o Nome de Guerra ou Número Interno do aluno para registrar saúde:", reply_markup=get_cancel_keyboard())
                    return
                await handle_pelotao_selection(bot_instance, message, state)
                return
                
            elif step == 'choose_student_button':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                if "voltar" in text.lower() or "⬅️" in text:
                    await prompt_pelotao_selection(bot_instance, message, state)
                    return
                await handle_student_button_selection(bot_instance, message, state)
                return
            
            # Passo 1: Busca de Alunos
            elif step == 'search_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    res = conn.table('Alunos').select('*').execute()
                    alunos = res.data if res.data else []
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                matches = []
                query = text.lower()
                for al in alunos:
                    num = str(al.get('numero_interno', '')).lower()
                    nome = str(al.get('nome_guerra', '')).lower()
                    if query in num or query in nome:
                        matches.append(al)
                
                if not matches:
                    await bot_instance.reply_to(message, f"⚠️ Nenhum aluno encontrado com '{text}'. Digite novamente ou selecione Cancelar:", reply_markup=get_cancel_keyboard())
                    return
                
                # Ordena os resultados da busca por ordem alfabética do nome de guerra
                matches = sorted(matches, key=lambda x: str(x.get('nome_guerra', '')).upper())
                
                if len(matches) > 1:
                    state['step'] = 'choose_student'
                    state['data']['matches'] = matches[:10] # Limita a 10 opções
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, al in enumerate(state['data']['matches']):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))

                    prompt = "🔍 Múltiplos alunos encontrados. Selecione o correspondente abaixo:\n\n"
                    for idx, al in enumerate(state['data']['matches']):
                        prompt += f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']} ({al['pelotao']})\n"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup)
                else:
                    await prompt_health_status(bot_instance, message, state, matches[0])
            
            # Passo 2: Seleção de Aluno em Lista
            elif step == 'choose_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                matches = state['data'].get('matches', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(matches):
                        selected = matches[choice - 1]
                        await prompt_health_status(bot_instance, message, state, selected)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número entre 1 e {len(matches)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 3: Escolha do Status de Saúde
            elif step == 'choose_health_status':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                status_map = {
                    1: ('Internado', 'enfermaria'),
                    2: ('Em Observação', 'enfermaria'),
                    3: ('Hospital', 'enfermaria'),
                    4: ('Dispensado', 'dispensa'),
                    5: ('Licença', 'licenca'),
                    6: ('Alta', 'alta')
                }
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if choice in status_map:
                        status, category = status_map[choice]
                        state['data']['status'] = status
                        state['data']['categoria'] = category
                        
                        if status == 'Dispensado':
                            state['step'] = 'choose_dispensa_type'
                            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                            for idx, val in enumerate(TIPOS_DISPENSA):
                                markup.add(types.KeyboardButton(f"{idx + 1} — {val}"))
                            markup.add(types.KeyboardButton("❌ Cancelar"))
                            prompt = "📋 Selecione o Tipo de Dispensa:"
                            await bot_instance.reply_to(message, prompt, reply_markup=markup)
                        elif status == 'Licença':
                            state['step'] = 'choose_licenca_type'
                            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                            for idx, val in enumerate(TIPOS_LICENCA):
                                markup.add(types.KeyboardButton(f"{idx + 1} — {val}"))
                            markup.add(types.KeyboardButton("❌ Cancelar"))
                            prompt = "✈️ Selecione o Tipo de Licença:"
                            await bot_instance.reply_to(message, prompt, reply_markup=markup)
                        else:
                            state['data']['detalhe'] = ''
                            state['step'] = 'get_health_motive'
                            await bot_instance.reply_to(message, "🩺 Digite o Motivo/Diagnóstico (ex: Cefaleia, Entorse, Cirurgia):", reply_markup=get_cancel_keyboard())
                    else:
                        await bot_instance.reply_to(message, "⚠️ Opção inválida. Digite um número de 1 a 6:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 4a: Tipo de Dispensa
            elif step == 'choose_dispensa_type':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(TIPOS_DISPENSA):
                        state['data']['detalhe'] = TIPOS_DISPENSA[choice - 1]
                        state['step'] = 'get_health_motive'
                        await bot_instance.reply_to(message, "🩺 Digite o Motivo/Diagnóstico (ex: Cefaleia, Entorse, Cirurgia):", reply_markup=get_cancel_keyboard())
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(TIPOS_DISPENSA)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 4b: Tipo de Licença
            elif step == 'choose_licenca_type':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(TIPOS_LICENCA):
                        state['data']['detalhe'] = TIPOS_LICENCA[choice - 1]
                        state['step'] = 'get_health_motive'
                        await bot_instance.reply_to(message, "🩺 Digite o Motivo/Diagnóstico (ex: Cefaleia, Entorse, Cirurgia):", reply_markup=get_cancel_keyboard())
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(TIPOS_LICENCA)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 5: Motivo/Diagnóstico
            elif step == 'get_health_motive':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                state['data']['motivo'] = text
                status = state['data']['status']
                
                if status in ('Dispensado', 'Licença'):
                    state['step'] = 'get_health_duration'
                    await bot_instance.reply_to(message, "🕒 Selecione ou digite a duração em dias (ex: 5):", reply_markup=get_duration_keyboard())
                else:
                    state['step'] = 'get_health_obs'
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("⏭️ Pular"), types.KeyboardButton("❌ Cancelar"))
                    await bot_instance.reply_to(message, "📝 Digite alguma observação adicional (ou escolha Pular/Cancelar):", reply_markup=markup)

            # Passo 6: Duração em dias
            elif step == 'get_health_duration':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                try:
                    dias = int(text)
                    if dias > 0:
                        state['data']['dias'] = dias
                        state['step'] = 'get_health_obs'
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("⏭️ Pular"), types.KeyboardButton("❌ Cancelar"))
                        await bot_instance.reply_to(message, "📝 Digite alguma observação adicional (ou escolha Pular/Cancelar):", reply_markup=markup)
                    else:
                        await bot_instance.reply_to(message, "⚠️ A duração em dias deve ser um número maior que 0:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas um número inteiro para a quantidade de dias:")

            # Passo 7: Observação adicional e Confirmação
            elif step == 'get_health_obs':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                obs = "" if text in ("/pular", "⏭️ Pular", "⏭️ pular", "pular") else text
                state['data']['observacao'] = obs
                
                student = state['data']['student']
                status = state['data']['status']
                detalhe = state['data'].get('detalhe', '')
                motivo = state['data']['motivo']
                dias = state['data'].get('dias', None)
                
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))

                confirm_prompt = (
                    "⚠️ Confirmar Lançamento de Saúde?\n\n"
                    f"👤 Aluno: {student['nome_guerra']} ({student['numero_interno']})\n"
                    f"🩺 Situação: {status}\n"
                )
                if detalhe:
                    confirm_prompt += f"📋 Tipo/Detalhe: {detalhe}\n"
                confirm_prompt += f"🔬 Motivo: {motivo}\n"
                if dias:
                    confirm_prompt += f"🕒 Prazo: {dias} dia(s)\n"
                if obs:
                    confirm_prompt += f"📝 Observação: {obs}\n"
                    
                confirm_prompt += "\nSelecione uma das opções abaixo:"
                state['step'] = 'confirm_health_submit'
                await bot_instance.reply_to(message, confirm_prompt, reply_markup=markup)

            # Passo 8: Confirmação e inserção
            elif step == 'confirm_health_submit':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — confirmar']:
                    try:
                        student = state['data']['student']
                        status = state['data']['status']
                        category = state['data']['categoria']
                        detalhe = state['data'].get('detalhe', '')
                        motivo = state['data']['motivo']
                        dias = state['data'].get('dias', None)
                        obs = state['data']['observacao']
                        usuario = state['user'].get('nome', 'TELEGRAM').upper()
                        
                        data_ini = date.today().strftime('%Y-%m-%d') if status in ('Dispensado', 'Licença') else None
                        data_fim = (date.today() + timedelta(days=dias)).strftime('%Y-%m-%d') if (status in ('Dispensado', 'Licença') and dias) else None
                        
                        conn.table('enfermaria').insert({
                            'numero_interno': str(student['numero_interno']),
                            'nome_guerra': student['nome_guerra'],
                            'turma': student.get('pelotao', ''),
                            'status': status,
                            'categoria': category,
                            'motivo': motivo,
                            'observacao': obs,
                            'detalhe': detalhe,
                            'data_ini': data_ini,
                            'data_fim': data_fim,
                            'data': date.today().strftime('%Y-%m-%d'),
                            'hora': datetime.now().strftime('%H:%M')
                        }).execute()
                        
                        # Alerta em tempo real na TV
                        health_title = "Alta Médica" if status == "Alta" else "Aviso de Saúde"
                        AlertsManager.trigger_alert(
                            health_title,
                            f"{student['numero_interno']} — {student['nome_guerra'].upper()} ({student.get('pelotao', '').upper()}) classificado como {status.upper()} by {usuario}!",
                            "success" if status == "Alta" else "warning"
                        )
                        
                        if status == 'Hospital' or status == 'Hospitalizado':
                            try:
                                from notifications_manager import notify_telegram
                                alert_txt = (
                                    f"🏥 **ALERTA: INTERNAÇÃO HOSPITALAR**\n\n"
                                    f"👤 Aluno: {student['nome_guerra'].upper()} ({student['numero_interno']})\n"
                                    f"🩺 Status: HOSPITALIZADO\n"
                                    f"🔬 Motivo: {motivo}\n"
                                    f"👮 Registrado por: {usuario}"
                                )
                                notify_telegram(alert_txt, "saude")
                            except Exception as e_notif:
                                print(f"[BOT SAUDE NOTIFY ERROR] {e_notif}")
                        
                        await bot_instance.reply_to(message, f"✅ Registro de saúde para {student['nome_guerra']} gravado com sucesso!", reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao gravar registro de saúde: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                elif ans in ['n', 'não', 'nao', 'no', 'n — cancelar', 'cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Lançamento abortado.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Responda apenas com S (Sim) ou N (Não):")

            # Passo 9: Seleção de Baixado para dar Alta
            elif step == 'choose_baixado':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                active_cases = state['data'].get('active_cases', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(active_cases):
                        selected = active_cases[choice - 1]
                        state['data']['selected_case'] = selected
                        state['step'] = 'confirm_alta'
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("🟢 Dar Alta"), types.KeyboardButton("❌ Cancelar"))
                        
                        detalhe_str = f"\n📋 Detalhe: {selected['detalhe']}" if selected.get('detalhe') else ""
                        periodo_str = f"\n🕒 Período: {selected['data_ini']} a {selected['data_fim']}" if selected.get('data_ini') else ""
                        
                        prompt = (
                            f"⚠️ Detalhes do Registro de Saúde:\n\n"
                            f"👤 Aluno: {selected['nome_guerra']} ({selected['numero_interno']})\n"
                            f"🩺 Situação: {selected['status']}\n"
                            f"🔬 Motivo: {selected['motivo'] or 'Sem motivo informado'}"
                            f"{detalhe_str}"
                            f"{periodo_str}\n\n"
                            f"Deseja dar ALTA para este militar?"
                        )
                        await bot_instance.reply_to(message, prompt, reply_markup=markup)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(active_cases)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")

            # Passo 10: Confirmação de Alta
            elif step == 'confirm_alta':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', '🟢 dar alta', 'dar alta', 's — dar alta']:
                    try:
                        selected = state['data']['selected_case']
                        usuario = state['user'].get('nome', 'TELEGRAM').upper()
                        
                        conn.table('enfermaria').update({
                            'status': 'Alta',
                            'categoria': 'alta',
                            'atualizado_em': datetime.now().isoformat()
                        }).eq('id', selected['id']).execute()
                        
                        # Alerta em tempo real na TV
                        AlertsManager.trigger_alert(
                            "Alta Médica",
                            f"{selected['numero_interno']} — {selected['nome_guerra'].upper()} ({selected.get('turma', '').upper()}) obteve alta médica por {usuario}!",
                            "success"
                        )
                        
                        await bot_instance.reply_to(message, f"✅ Alta para {selected['nome_guerra']} registrada com sucesso!", reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao registrar alta: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                elif ans in ['n', 'não', 'nao', 'no', 'cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Escolha uma das opções: '🟢 Dar Alta' ou '❌ Cancelar':")

        # ── PROCESSAMENTO DO LANÇAMENTO DE ESCALA ─────────────────────
        elif action == 'escala':
            # Passo 1: Escolha do Dia (Hoje/Amanhã)
            if step == 'choose_date':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                target_date = None
                date_lbl = ""
                
                if "hoje" in text.lower():
                    target_date = date.today()
                    date_lbl = "Hoje"
                elif "amanhã" in text.lower() or "amanha" in text.lower():
                    target_date = date.today() + timedelta(days=1)
                    date_lbl = "Amanhã"
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Escolha '📅 Hoje' ou '📅 Amanhã':")
                    return
                
                date_str = target_date.strftime('%Y-%m-%d')
                date_br = target_date.strftime('%d/%m/%Y')
                
                state['data']['date_str'] = date_str
                state['data']['date_lbl'] = date_lbl
                state['data']['date_br'] = date_br
                
                await bot_instance.send_chat_action(chat_id, 'typing')
                
                try:
                    res_es = conn.table('escala_diaria').select('*').eq('data', date_str).execute()
                    escala_records = res_es.data if res_es.data else []
                    
                    from database import get_cargos_escala
                    cargos_config = get_cargos_escala()
                    
                    escala_map = {row['cargo'].upper(): row for row in escala_records}
                    
                    roster_lines = []
                    for cargo in cargos_config:
                        cargo_upper = cargo.upper()
                        rec = escala_map.get(cargo_upper)
                        if rec:
                            nome_escalado = rec['nome'].upper()
                            obs = f" ({rec['observacao']})" if rec.get('observacao') else ""
                            roster_lines.append(f"• {cargo}: `{nome_escalado}`{obs}")
                        else:
                            roster_lines.append(f"• {cargo}: `NÃO ESCALADO`")
                    
                    if not escala_records:
                        roster_text = f"👮 ESCALA DE SERVIÇO ({date_lbl} — {date_br}) 👮\n\n⚠️ Nenhuma escala cadastrada para esta data."
                    else:
                        roster_text = (
                            f"👮 ESCALA DE SERVIÇO ({date_lbl} — {date_br}) 👮\n\n"
                            + "\n".join(roster_lines)
                        )
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("✏️ Adicionar / Alterar Escala"), types.KeyboardButton("❌ Sair"))
                    
                    await bot_instance.reply_to(message, roster_text, reply_markup=markup, parse_mode='Markdown')
                    state['step'] = 'choose_action'
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao consultar escala: {e}", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
            
            # Passo 2: Escolha de Ação (Alterar ou Sair)
            elif step == 'choose_action':
                if text.lower() in ['sair', '❌ sair', 'cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "👋 Fim da consulta de escala.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                if "alterar" in text.lower() or "✏️" in text:
                    from database import get_cargos_escala
                    cargos_config = get_cargos_escala()
                    
                    state['step'] = 'choose_cargo'
                    state['data']['cargos_list'] = cargos_config
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for c in cargos_config:
                        markup.add(types.KeyboardButton(c))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, "✏️ Selecione o Cargo que deseja alterar/adicionar na escala:", reply_markup=markup)
                else:
                    await bot_instance.reply_to(message, "⚠️ Escolha uma das opções: '✏️ Adicionar / Alterar Escala' ou '❌ Sair':")
            
            # Passo 3: Escolha do Cargo
            elif step == 'choose_cargo':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Alteração de escala cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                cargos_list = state['data'].get('cargos_list', [])
                cargo_match = next((c for c in cargos_list if c.upper() == text.upper()), None)
                if not cargo_match:
                    await bot_instance.reply_to(message, "⚠️ Cargo inválido. Selecione uma das opções do teclado:")
                    return
                
                state['data']['cargo'] = cargo_match
                state['step'] = 'get_name'
                await bot_instance.reply_to(message, f"👤 Digite o Nome (completo ou de guerra) da pessoa a ser escalada para {cargo_match}:", reply_markup=get_cancel_keyboard())
            
            # Passo 4: Digitar Nome e buscar correspondências
            elif step == 'get_name':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Alteração de escala cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                query = text.strip()
                await bot_instance.send_chat_action(chat_id, 'typing')
                
                try:
                    res_us = conn.table('Users').select('*').execute()
                    users = res_us.data if res_us.data else []
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao ler usuários: {e}", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                matches = [u for u in users if query.lower() in str(u.get('nome', '')).lower() or query.lower() in str(u.get('username', '')).lower()]
                
                if not matches:
                    state['step'] = 'confirm_external'
                    state['data']['nome_escalado'] = query
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))
                    
                    prompt = (
                        f"⚠️ Operador não cadastrado.\n"
                        f"Deseja escalar '{query}' mesmo assim?"
                    )
                    await bot_instance.reply_to(message, prompt, reply_markup=markup)
                elif len(matches) > 1:
                    state['step'] = 'choose_user'
                    state['data']['user_matches'] = matches[:10]
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, u in enumerate(state['data']['user_matches']):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {u['nome']}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    prompt = "🔍 Múltiplas correspondências encontradas. Selecione a correta abaixo:\n\n"
                    for idx, u in enumerate(state['data']['user_matches']):
                        prompt += f"{idx + 1} — {u['nome']} ({u.get('username', '')})\n"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup)
                else:
                    state['data']['nome_escalado'] = matches[0]['nome']
                    state['step'] = 'get_obs'
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("Sem observação"), types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, f"📝 Selecionado: {matches[0]['nome']}\n\nDigite uma observação (ou clique em 'Sem observação'):", reply_markup=markup)
            
            # Passo 5a: Escolher Usuário em Homônimos
            elif step == 'choose_user':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Alteração de escala cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                matches = state['data'].get('user_matches', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(matches):
                        selected = matches[choice - 1]
                        state['data']['nome_escalado'] = selected['nome']
                        state['step'] = 'get_obs'
                        
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                        markup.row(types.KeyboardButton("Sem observação"), types.KeyboardButton("❌ Cancelar"))
                        
                        await bot_instance.reply_to(message, f"Selecionei: {selected['nome']}\n\nDigite uma observação (ou clique em 'Sem observação'):", reply_markup=markup)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(matches)}:")
                except ValueError:
                    # Treat as new name search
                    state['step'] = 'get_name'
                    # Re-run search
                    await handle_normal_message(message)
            
            # Passo 5b: Confirmar Escalar Nome Externo
            elif step == 'confirm_external':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — confirmar']:
                    state['step'] = 'get_obs'
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("Sem observação"), types.KeyboardButton("❌ Cancelar"))
                    
                    await bot_instance.reply_to(message, "Digite uma observação para a escala (ou clique em 'Sem observação'):", reply_markup=markup)
                else:
                    await bot_instance.reply_to(message, "❌ Alteração de escala cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
            
            # Passo 6: Obter Observação
            elif step == 'get_obs':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Alteração de escala cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                
                obs = "" if text.lower() in ["sem observação", "sem observacao", "/pular"] else text
                state['data']['observacao'] = obs
                state['step'] = 'confirm_escala_submit'
                
                date_lbl = state['data']['date_lbl']
                date_br = state['data']['date_br']
                cargo = state['data']['cargo']
                nome_escalado = state['data']['nome_escalado']
                
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                markup.row(types.KeyboardButton("S — Salvar Escala"), types.KeyboardButton("N — Cancelar"))
                
                prompt = (
                    f"⚠️ Confirmar Gravação de Escala de Serviço?\n\n"
                    f"📅 Data: {date_lbl} ({date_br})\n"
                    f"👮 Cargo: {cargo}\n"
                    f"👤 Escalado: {nome_escalado.upper()}\n"
                    f"📝 Observação: {obs or 'Nenhuma'}\n\n"
                    f"Selecione uma opção:"
                )
                await bot_instance.reply_to(message, prompt, reply_markup=markup)
            
            # Passo 7: Confirmação e Gravação da Escala
            elif step == 'confirm_escala_submit':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — salvar alteração', 's — salvar escala']:
                    try:
                        date_str = state['data']['date_str']
                        date_lbl = state['data']['date_lbl']
                        date_br = state['data']['date_br']
                        cargo = state['data']['cargo']
                        nome_escalado = state['data']['nome_escalado']
                        obs = state['data']['observacao']
                        
                        salvar_escala_diaria_data(conn, date_str, cargo, nome_escalado, obs)
                        
                        # Dispara alerta sonoro e popup na TV
                        AlertsManager.trigger_alert(
                            "Escala de Serviço",
                            f"Escala de {date_lbl} salva: {cargo} definido como {nome_escalado.upper()}!",
                            "info"
                        )
                        
                        await bot_instance.reply_to(message, f"✅ Escala de {cargo} salva para {nome_escalado} com sucesso!", reply_markup=get_main_menu_keyboard())
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao salvar escala: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "❌ Alteração de escala abortada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
        
        # ── PROCESSAMENTO DO PERNOITE ─────────────────────────────────
        elif action == 'pernoite':
            if step == 'choose_pelotao':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                if "digitar" in text.lower() or "lote" in text.lower() or "buscar" in text.lower():
                    state['step'] = 'search_student'
                    await bot_instance.reply_to(message, "🔍 Digite o nome de guerra, número interno ou números em lote (separados por vírgula):", reply_markup=get_cancel_keyboard())
                    return
                await handle_pelotao_selection(bot_instance, message, state)
                return
                
            elif step == 'choose_student_button':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                if "voltar" in text.lower() or "⬅️" in text:
                    await prompt_pelotao_selection(bot_instance, message, state)
                    return
                await handle_student_button_selection(bot_instance, message, state)
                return

            elif step == 'search_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return

                # Obter o ano letivo do usuário (para filtrar)
                try:
                    from notifications_manager import get_user_preferences
                    user_prefs = get_user_preferences(state['user']['id'])
                    active_year = user_prefs.get('ano_letivo_ativo', '2026')
                except Exception:
                    active_year = '2026'

                # Verificar se é lançamento em massa (com vírgulas)
                if "," in text:
                    parts = [p.strip() for p in text.split(',') if p.strip()]
                    invalid_parts = []
                    found_alunos = []
                    
                    try:
                        res = conn.table('Alunos').select('*').eq('ano_letivo', active_year).execute()
                        alunos = res.data if res.data else []
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}")
                        clear_state(chat_id)
                        return
                    
                    for part in parts:
                        match = None
                        for al in alunos:
                            if str(al.get('numero_interno', '')).strip() == part:
                                match = al
                                break
                        if match:
                            found_alunos.append(match)
                        else:
                            invalid_parts.append(part)
                    
                    if invalid_parts:
                        await bot_instance.reply_to(
                            message,
                            f"⚠️ Os seguintes números internos não foram encontrados no ano letivo {active_year}:\n"
                            f"❌ `{', '.join(invalid_parts)}`\n\n"
                            "Por favor, verifique os números e digite novamente ou cancele:",
                            reply_markup=get_cancel_keyboard(),
                            parse_mode='Markdown'
                        )
                        return
                    
                    state['step'] = 'confirm_mass_pernoite'
                    state['data']['mass_students'] = found_alunos
                    
                    student_list_str = "\n".join([f"• NI {al['numero_interno']}: {al['nome_guerra']} ({al['pelotao']})" for al in found_alunos])
                    prompt = (
                        f"🛌 **Confirmar Autorização de Pernoite em Massa?**\n\n"
                        f"Os seguintes alunos serão autorizados:\n{student_list_str}\n\n"
                        f"Clique em um dos botões abaixo para confirmar:"
                    )
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("🟢 CONFIRMAR LANÇAMENTO"), types.KeyboardButton("❌ Cancelar"))
                    await bot_instance.reply_to(message, prompt, reply_markup=markup, parse_mode='Markdown')
                    return

                try:
                    res = conn.table('Alunos').select('*').eq('ano_letivo', active_year).execute()
                    alunos = res.data if res.data else []
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}")
                    clear_state(chat_id)
                    return
                
                matches = []
                query = text.lower()
                for al in alunos:
                    num = str(al.get('numero_interno', '')).lower()
                    nome = str(al.get('nome_guerra', '')).lower()
                    if query in num or query in nome or num.endswith("-" + query) or num.endswith(query):
                        matches.append(al)
                
                if not matches:
                    await bot_instance.reply_to(message, f"⚠️ Nenhum aluno encontrado com '{text}' no ano letivo {active_year}. Digite novamente ou selecione Cancelar:", reply_markup=get_cancel_keyboard())
                    return
                
                # Ordena os resultados da busca por ordem alfabética do nome de guerra
                matches = sorted(matches, key=lambda x: str(x.get('nome_guerra', '')).upper())
                
                if len(matches) > 1:
                    state['step'] = 'choose_student'
                    state['data']['matches'] = matches[:10]
                    
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for idx, al in enumerate(state['data']['matches']):
                        markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
                    markup.add(types.KeyboardButton("❌ Cancelar"))
                    
                    prompt = "🔍 Múltiplos alunos encontrados. Selecione o correspondente abaixo:\n\n"
                    for idx, al in enumerate(state['data']['matches']):
                        prompt += f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']} ({al['pelotao']})\n"
                    await bot_instance.reply_to(message, prompt, reply_markup=markup)
                else:
                    await prompt_pernoite_confirm(bot_instance, message, state, matches[0])
            
            elif step == 'choose_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                matches = state['data'].get('matches', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(matches):
                        selected = matches[choice - 1]
                        await prompt_pernoite_confirm(bot_instance, message, state, selected)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número entre 1 e {len(matches)}:")
                except ValueError:
                    await bot_instance.reply_to(message, "⚠️ Digite apenas o número correspondente à sua escolha:")
            
            elif step == 'confirm_pernoite_submit':
                ans = text.strip().lower()
                if ans in ['s', 'sim', 'y', 'yes', 's — confirmar']:
                    try:
                        student = state['data']['student']
                        usuario = state['user'].get('nome', 'TELEGRAM').upper()
                        hoje_str = date.today().strftime('%Y-%m-%d')
                        
                        conn.table('pernoite').upsert({
                            'aluno_id': int(student['id']),
                            'data': hoje_str,
                            'presente': True
                        }, on_conflict='aluno_id,data').execute()
                        
                        aluno_lbl = f"{student.get('numero_interno', '')} — {str(student.get('nome_guerra', '')).upper()} ({str(student.get('pelotao', '')).upper()})"
                        AlertsManager.trigger_alert(
                            "Pernoite Autorizado",
                            f"Pernoite de {aluno_lbl} autorizado por {usuario}!",
                            "success"
                        )
                        
                        await bot_instance.reply_to(
                            message,
                            f"✅ Pernoite Autorizado com Sucesso!\n"
                            f"• Militar: {student['nome_guerra']} ({student['numero_interno']})\n"
                            f"• Status: Autorizado para Hoje ({date.today().strftime('%d/%m')}).",
                            reply_markup=get_main_menu_keyboard()
                        )
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao salvar pernoite: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                elif ans in ['n', 'não', 'nao', 'no', 'n — cancelar', 'cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Lançamento de pernoite abortado.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Responda apenas com S (Sim) ou N (Não):")

            elif step == 'confirm_mass_pernoite':
                ans = text.strip().lower()
                if "confirmar" in ans or ans == 's' or ans == 'sim' or ans == '🟢 confirmar lançamento':
                    try:
                        mass_students = state['data'].get('mass_students', [])
                        usuario = state['user'].get('nome', 'TELEGRAM').upper()
                        hoje_str = date.today().strftime('%Y-%m-%d')
                        
                        success_count = 0
                        for student in mass_students:
                            conn.table('pernoite').upsert({
                                'aluno_id': int(student['id']),
                                'data': hoje_str,
                                'presente': True
                            }, on_conflict='aluno_id,data').execute()
                            
                            aluno_lbl = f"{student.get('numero_interno', '')} — {str(student.get('nome_guerra', '')).upper()} ({str(student.get('pelotao', '')).upper()})"
                            AlertsManager.trigger_alert(
                                "Pernoite Autorizado",
                                f"Pernoite de {aluno_lbl} autorizado por {usuario}!",
                                "success"
                            )
                            success_count += 1
                        
                        await bot_instance.reply_to(
                            message,
                            f"✅ **Lançamento em Massa Concluído!**\n\n"
                            f"• Total de pernoites autorizados: `{success_count}` militar(es).\n"
                            f"• Data: {date.today().strftime('%d/%m')}.",
                            reply_markup=get_main_menu_keyboard(),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        await bot_instance.reply_to(message, f"❌ Erro ao salvar pernoites em massa: {e}", reply_markup=get_main_menu_keyboard())
                    finally:
                        clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "❌ Lançamento de pernoite em massa abortado.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
        
        # ── PROCESSAMENTO DA CONSULTA DE ALUNO ────────────────────────
        elif action == 'consulta':
            if step == 'search_student':
                await perform_consulta_search(bot_instance, message, state['user'], text)
            elif step == 'choose_student':
                if text.lower() in ['cancelar', '❌ cancelar']:
                    await bot_instance.reply_to(message, "❌ Consulta cancelada.", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                    return
                matches = state['data'].get('matches', [])
                try:
                    clean_text = text.split('—')[0].strip()
                    choice = int(clean_text)
                    if 1 <= choice <= len(matches):
                        selected = matches[choice - 1]
                        await display_student_dossier(bot_instance, message, conn, selected)
                    else:
                        await bot_instance.reply_to(message, f"⚠️ Opção inválida. Digite um número de 1 a {len(matches)}:")
                except ValueError:
                    # Treat as new name search
                    await perform_consulta_search(bot_instance, message, state['user'], text)

        # ── PROCESSAMENTO DE CONFIGURAÇÕES DO BOT ───────────────────────
        elif action == 'settings':
            if text.lower() in ['cancelar', '❌ cancelar']:
                if state['user'] is not None:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_main_menu_keyboard())
                else:
                    await bot_instance.reply_to(message, "❌ Operação cancelada.", reply_markup=get_unauthorized_keyboard())
                clear_state(chat_id)
                return
            elif text.lower() in ['voltar', '⬅️ voltar']:
                if step == 'choose_option':
                    if state['user'] is not None:
                        await bot_instance.reply_to(message, "Voltando ao menu principal...", reply_markup=get_main_menu_keyboard())
                    else:
                        await bot_instance.reply_to(message, "Voltando...", reply_markup=get_unauthorized_keyboard())
                    clear_state(chat_id)
                    return
                else:
                    state['step'] = 'choose_option'
                    await bot_instance.reply_to(message, "Configurações:", reply_markup=get_settings_keyboard(state['user'] is not None))
                    return

            if step == 'choose_option':
                clean_opt = text.lower()
                if "solicitar acesso" in clean_opt:
                    profile = state['user']
                    if profile:
                        await bot_instance.reply_to(message, f"⚠️ Você já está cadastrado e autorizado como {profile['nome']}!", reply_markup=get_settings_keyboard(True))
                        return
                    state['step'] = 'request_access_name'
                    await bot_instance.reply_to(message, "📝 **Solicitação de Acesso**\n\nPor favor, digite seu **Nome Completo**:", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
                elif "notificações" in clean_opt or "notificacoes" in clean_opt:
                    profile = state['user']
                    if not profile:
                        await bot_instance.reply_to(message, "⚠️ Você precisa solicitar acesso e ter uma conta autorizada antes de configurar notificações.", reply_markup=get_settings_keyboard(False))
                        return
                    from notifications_manager import get_user_preferences
                    user_prefs = get_user_preferences(profile['id'])
                    status = "🔴 SILENCIADAS (Não está recebendo avisos da TV ou sistema)" if user_prefs.get("silence_all", False) else "🟢 ATIVADAS (Você receberá avisos da TV, saúde e escalas no chat)"
                    
                    state['step'] = 'toggle_notifications'
                    prompt = (
                        f"🔔 **Suas Configurações de Notificação:**\n\n"
                        f"Status atual: {status}\n\n"
                        f"Escolha uma opção abaixo para ativar ou silenciar todas as notificações:"
                    )
                    await bot_instance.reply_to(message, prompt, reply_markup=get_notifications_toggle_keyboard(user_prefs), parse_mode='Markdown')
                elif "ano letivo" in clean_opt:
                    profile = state['user']
                    if not profile:
                        await bot_instance.reply_to(message, "⚠️ Acesso restrito. Solicite acesso primeiro.", reply_markup=get_settings_keyboard(False))
                        return
                    
                    state['step'] = 'change_year'
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    markup.row(types.KeyboardButton("2025"), types.KeyboardButton("2026"))
                    markup.row(types.KeyboardButton("⬅️ Voltar"))
                    
                    await bot_instance.reply_to(
                        message,
                        "📅 **Alterar Ano Letivo Ativo**\n\n"
                        "Escolha o ano letivo que deseja usar para suas operações no bot:",
                        reply_markup=markup,
                        parse_mode='Markdown'
                    )
                elif "vincular conta" in clean_opt:
                    await bot_instance.reply_to(
                        message,
                        "⚠️ A vinculação manual está desativada por questões de segurança.\n"
                        "Por favor, use a opção 'Solicitar Acesso' e os administradores farão a vinculação.",
                        reply_markup=get_settings_keyboard(state['user'] is not None)
                    )
                elif "voltar" in clean_opt or "⬅️ voltar" in clean_opt:
                    await bot_instance.reply_to(message, "Voltando ao menu principal...", reply_markup=get_main_menu_keyboard())
                    clear_state(chat_id)
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Selecione uma das opções do teclado:")

            elif step == 'request_access_name':
                state['data']['reg_nome'] = text
                state['step'] = 'request_access_guerra'
                await bot_instance.reply_to(message, "👮 Digite seu **Nome de Guerra** (ex: Sgt Silva):", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')

            elif step == 'request_access_guerra':
                state['data']['reg_guerra'] = text
                state['step'] = 'request_access_email'
                await bot_instance.reply_to(message, "📧 Digite seu **E-mail de Serviço**:", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')

            elif step == 'request_access_email':
                state['data']['reg_email'] = text
                try:
                    from notifications_manager import notify_telegram
                    alert_txt = (
                        f"🔔 **SOLICITAÇÃO DE NOVO ACESSO (TELEGRAM)**\n\n"
                        f"👤 Nome: {state['data']['reg_nome'].upper()}\n"
                        f"👮 Nome de Guerra: {state['data']['reg_guerra'].upper()}\n"
                        f"📧 E-mail: {state['data']['reg_email']}\n"
                        f"⚡ Telegram ID: `{message.from_user.id}`\n\n"
                        f"Aprovação recomendada via painel Web vinculando o Telegram ID correspondente."
                    )
                    notify_telegram(alert_txt, "new_user", role_required="admin")
                    await bot_instance.reply_to(message, "✅ **Solicitação de Acesso Enviada!**\n\nOs administradores foram notificados. Aguarde a criação e vinculação do seu acesso.", reply_markup=get_main_menu_keyboard())
                except Exception as ex:
                    await bot_instance.reply_to(message, f"❌ Erro ao enviar solicitação: {ex}", reply_markup=get_main_menu_keyboard())
                finally:
                    clear_state(chat_id)

            elif step == 'toggle_notifications':
                profile = state['user']
                if not profile:
                    await bot_instance.reply_to(message, "⚠️ Você precisa solicitar acesso e ter uma conta autorizada antes de configurar notificações.", reply_markup=get_settings_keyboard(False))
                    state['step'] = 'choose_option'
                    return
                
                from notifications_manager import get_user_preferences, save_user_preferences
                user_prefs = get_user_preferences(profile['id'])
                
                clean_text = text.lower()
                if "letreiro/avisos" in clean_text:
                    user_prefs['notify_aviso'] = not user_prefs.get('notify_aviso', True)
                    save_user_preferences(profile['id'], user_prefs)
                    status = "🟢 ATIVADO" if user_prefs['notify_aviso'] else "🔴 MUTADO"
                    await bot_instance.reply_to(message, f"📢 Notificações de Letreiro/Avisos alteradas para: {status}", reply_markup=get_notifications_toggle_keyboard(user_prefs))
                elif "saúde" in clean_text or "saude" in clean_text:
                    user_prefs['notify_saude'] = not user_prefs.get('notify_saude', True)
                    save_user_preferences(profile['id'], user_prefs)
                    status = "🟢 ATIVADO" if user_prefs['notify_saude'] else "🔴 MUTADO"
                    await bot_instance.reply_to(message, f"🏥 Notificações de Saúde alteradas para: {status}", reply_markup=get_notifications_toggle_keyboard(user_prefs))
                elif "escalas" in clean_text:
                    user_prefs['notify_escala'] = not user_prefs.get('notify_escala', True)
                    save_user_preferences(profile['id'], user_prefs)
                    status = "🟢 ATIVADO" if user_prefs['notify_escala'] else "🔴 MUTADO"
                    await bot_instance.reply_to(message, f"👮 Notificações de Escalas alteradas para: {status}", reply_markup=get_notifications_toggle_keyboard(user_prefs))
                elif "novos acessos" in clean_text:
                    user_prefs['notify_new_user'] = not user_prefs.get('notify_new_user', True)
                    save_user_preferences(profile['id'], user_prefs)
                    status = "🟢 ATIVADO" if user_prefs['notify_new_user'] else "🔴 MUTADO"
                    await bot_instance.reply_to(message, f"👥 Notificações de Novos Acessos alteradas para: {status}", reply_markup=get_notifications_toggle_keyboard(user_prefs))
                elif "anotações" in clean_text or "anotacoes" in clean_text or "anotação" in clean_text:
                    user_prefs['notify_anotacao'] = not user_prefs.get('notify_anotacao', True)
                    save_user_preferences(profile['id'], user_prefs)
                    status = "🟢 ATIVADO" if user_prefs['notify_anotacao'] else "🔴 MUTADO"
                    await bot_instance.reply_to(message, f"📋 Notificações de Anotações alteradas para: {status}", reply_markup=get_notifications_toggle_keyboard(user_prefs))
                elif "silenciar tudo" in clean_text:
                    user_prefs['silence_all'] = not user_prefs.get('silence_all', False)
                    save_user_preferences(profile['id'], user_prefs)
                    status = "🔴 SILENCIADAS" if user_prefs['silence_all'] else "🟢 ATIVADAS"
                    await bot_instance.reply_to(message, f"🔇 Status de Silêncio Geral alterado para: {status}", reply_markup=get_notifications_toggle_keyboard(user_prefs))
                elif "voltar" in clean_text or "⬅️ voltar" in clean_text:
                    state['step'] = 'choose_option'
                    await bot_instance.reply_to(message, "Configurações:", reply_markup=get_settings_keyboard(profile is not None))
                else:
                    await bot_instance.reply_to(message, "⚠️ Opção inválida. Selecione uma das opções do teclado:", reply_markup=get_notifications_toggle_keyboard(user_prefs))

            elif step == 'change_year':
                clean_opt = text.lower()
                if "voltar" in clean_opt or "⬅️ voltar" in clean_opt:
                    state['step'] = 'choose_option'
                    await bot_instance.reply_to(message, "Configurações:", reply_markup=get_settings_keyboard(state['user'] is not None))
                    return
                
                if text.strip() not in ['2025', '2026']:
                    await bot_instance.reply_to(message, "⚠️ Escolha inválida. Escolha 2025 ou 2026:")
                    return
                
                from notifications_manager import get_user_preferences, save_user_preferences
                profile = state['user']
                user_prefs = get_user_preferences(profile['id'])
                user_prefs['ano_letivo_ativo'] = text.strip()
                save_user_preferences(profile['id'], user_prefs)
                
                await bot_instance.reply_to(
                    message,
                    f"✅ **Ano Letivo alterado com sucesso!**\n\nSeu ano letivo ativo agora é **{text.strip()}**.",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
                clear_state(chat_id)
                return

            elif step == 'link_account_email':
                username = text.split('@')[0] if '@' in text else text
                try:
                    res = conn.table('Users').select('*').eq('username', username).execute()
                    if not res.data:
                        await bot_instance.reply_to(message, f"❌ Nenhum operador encontrado com o username/email '{username}'. Digite novamente ou cancele:", reply_markup=get_cancel_keyboard())
                        return
                    user_profile = res.data[0]
                    conn.table('Users').update({'telegram_id': str(message.from_user.id)}).eq('id', user_profile['id']).execute()
                    await bot_instance.reply_to(message, f"✅ Vinculação Concluída com sucesso para o operador {user_profile['nome']}!", reply_markup=get_main_menu_keyboard())
                except Exception as e:
                    await bot_instance.reply_to(message, f"❌ Erro ao vincular conta: {e}", reply_markup=get_main_menu_keyboard())
                finally:
                    clear_state(chat_id)

async def prompt_pernoite_confirm(bot_instance, message, state, student):
    state['step'] = 'confirm_pernoite_submit'
    state['data']['student'] = student
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))
    
    confirm_prompt = (
        "🛌 Confirmar Autorização de Pernoite?\n\n"
        f"👤 Aluno: {student['nome_guerra']} ({student['numero_interno']})\n"
        f"📋 Pelotão: {student['pelotao']}\n"
        f"📅 Data: Hoje ({date.today().strftime('%d/%m/%Y')})\n\n"
        "Selecione uma das opções abaixo:"
    )
    await bot_instance.reply_to(message, confirm_prompt, reply_markup=markup)

async def prompt_health_status(bot_instance, message, state, student):
    """Apresenta as opções de status de saúde para seleção."""
    state['step'] = 'choose_health_status'
    state['data']['student'] = student
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("1 — 🏥 Internado (Enfermaria)"))
    markup.add(types.KeyboardButton("2 — 👁️ Em Observação (Enfermaria)"))
    markup.add(types.KeyboardButton("3 — 🚑 Hospital (Hospitalizado)"))
    markup.add(types.KeyboardButton("4 — 📝 Dispensado (Dispensa Médica)"))
    markup.add(types.KeyboardButton("5 — ✈️ Licença (Afastado da Unidade)"))
    markup.add(types.KeyboardButton("6 — 🟢 Alta (Retorno ao Serviço/Atividades)"))
    markup.add(types.KeyboardButton("❌ Cancelar"))

    prompt = (
        f"👤 Aluno Selecionado: **{student['nome_guerra']}** ({student['numero_interno']})\n\n"
        "Selecione o **Status de Saúde** abaixo:"
    )
    await bot_instance.reply_to(message, prompt, reply_markup=markup, parse_mode='Markdown')

async def prompt_atrasado_confirm(bot_instance, message, state, conn, student):
    """Busca o tipo de ocorrência de atraso e pede confirmação para retirar falta e aplicar atraso."""
    try:
        res = conn.table('Tipos_Acao').select('*').execute()
        tipos = res.data if res.data else []
        tipo_atraso = next((t for t in tipos if t['id'] == 9 or 'atraso' in t['nome'].lower()), None)
    except Exception as e:
        await bot_instance.reply_to(message, f"❌ Erro ao buscar tipo de ação Atraso: {e}")
        clear_state(message.chat.id)
        return

    if not tipo_atraso:
        await bot_instance.reply_to(message, "❌ Tipo de ocorrência 'ATRASO' não encontrado no banco de dados. Operação cancelada.")
        clear_state(message.chat.id)
        return

    state['step'] = 'confirm_atraso_submit'
    state['data']['student'] = student
    state['data']['tipo_atraso'] = tipo_atraso

    presenca_status = "Ausente ou Sem Registro"
    try:
        data_hoje = date.today().strftime('%Y-%m-%d')
        res_p = conn.table('presenca_ausencia').select('*').eq('numero_interno', student['numero_interno']).eq('data', data_hoje).execute()
        if res_p.data:
            pres = res_p.data[0]
            presenca_status = "PRESENTE" if pres.get('presente') else f"AUSENTE ({pres.get('motivo_ausencia') or 'Sem motivo'})"
    except Exception:
        pass

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row(types.KeyboardButton("S — Confirmar"), types.KeyboardButton("N — Cancelar"))

    prompt = (
        "⚠️ **Confirmar Lançamento de Atrasado?**\n\n"
        f"👤 **Aluno**: {student['nome_guerra']} ({student['numero_interno']})\n"
        f"📊 **Presença Hoje**: {presenca_status}\n\n"
        f"🔄 **Ações a Executar**:\n"
        f"1. Alterar presença do dia de hoje para **PRESENTE**.\n"
        f"2. Registrar ocorrência de **{tipo_atraso['nome']}** ({float(tipo_atraso.get('pontuacao', 0.0) or 0.0):+.1f} pts) em status PENDENTE.\n\n"
        "Selecione uma das opções abaixo:"
    )
    await bot_instance.reply_to(message, prompt, reply_markup=markup)

async def prompt_action_type(bot_instance, message, state, student):
    """Busca os tipos de ações cadastrados e exibe as opções para o operador, agrupadas por categoria, com botões."""
    conn = get_db_connection()
    if not conn:
        await bot_instance.reply_to(message, "❌ Sem conexão com o banco. Operação abortada.", reply_markup=get_main_menu_keyboard())
        clear_state(message.chat.id)
        return

    try:
        res = conn.table('Tipos_Acao').select('*').execute()
        raw_tipos = res.data if res.data else []
    except Exception as e:
        await bot_instance.reply_to(message, f"❌ Erro ao ler tipos de ações: {e}", reply_markup=get_main_menu_keyboard())
        clear_state(message.chat.id)
        return

    if not raw_tipos:
        await bot_instance.reply_to(message, "❌ Nenhum Tipo de Ocorrência cadastrado no banco. Operação abortada.", reply_markup=get_main_menu_keyboard())
        clear_state(message.chat.id)
        return

    # Agrupa e ordena alfabeticamente dentro de cada categoria
    positivas = sorted([t for t in raw_tipos if float(t.get('pontuacao', 0.0) or 0.0) > 0], key=lambda t: t.get('nome', '').lower())
    neutras = sorted([t for t in raw_tipos if float(t.get('pontuacao', 0.0) or 0.0) == 0], key=lambda t: t.get('nome', '').lower())
    negativas = sorted([t for t in raw_tipos if float(t.get('pontuacao', 0.0) or 0.0) < 0], key=lambda t: t.get('nome', '').lower())

    tipos = positivas + neutras + negativas

    state['step'] = 'choose_action_type'
    state['data']['student'] = student
    state['data']['tipos'] = tipos

    prompt = (
        f"👤 Aluno Selecionado: {student['nome_guerra']} ({student['numero_interno']})\n\n"
        "Selecione o Tipo de Ocorrência usando os botões abaixo:\n\n"
    )
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    idx = 0
    if positivas:
        prompt += "➕ POSITIVAS:\n"
        for tp in positivas:
            pts = float(tp.get('pontuacao', 0.0) or 0.0)
            prompt += f"{idx + 1} — {tp['nome']} ({pts:+.1f} pts)\n"
            markup.add(types.KeyboardButton(f"{idx + 1} — {tp['nome']}"))
            idx += 1
        prompt += "\n"
        
    if neutras:
        prompt += "⚪ NEUTRAS:\n"
        for tp in neutras:
            prompt += f"{idx + 1} — {tp['nome']} (0.0 pts)\n"
            markup.add(types.KeyboardButton(f"{idx + 1} — {tp['nome']}"))
            idx += 1
        prompt += "\n"
        
    if negativas:
        prompt += "➖ NEGATIVAS:\n"
        for tp in negativas:
            pts = float(tp.get('pontuacao', 0.0) or 0.0)
            prompt += f"{idx + 1} — {tp['nome']} ({pts:+.1f} pts)\n"
            markup.add(types.KeyboardButton(f"{idx + 1} — {tp['nome']}"))
            idx += 1

    markup.add(types.KeyboardButton("❌ Cancelar"))
    await bot_instance.reply_to(message, prompt, reply_markup=markup)

def salvar_escala_diaria_data(conn, data_str, cargo, nome, observacao=''):
    """Salva registro de escala de serviço para uma data específica"""
    registro = {
        'data': data_str,
        'cargo': cargo,
        'nome': nome,
        'observacao': observacao or '',
        'criado_em': datetime.now().isoformat(),
    }
    try:
        resp = conn.table('escala_diaria').select('id').eq('data', data_str).eq('cargo', cargo).execute()
        if resp.data:
            conn.table('escala_diaria').update(registro).eq('id', resp.data[0]['id']).execute()
        else:
            conn.table('escala_diaria').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[Bot] Erro ao salvar escala: {e}", flush=True)
        return False

async def perform_consulta_search(bot_instance, message, profile, term):
    chat_id = message.chat.id
    conn = get_db_connection()
    if not conn:
        await bot_instance.reply_to(message, "❌ Sem conexão com o banco de dados.")
        clear_state(chat_id)
        return
        
    try:
        from notifications_manager import get_user_preferences
        user_prefs = get_user_preferences(profile['id'])
        active_year = user_prefs.get('ano_letivo_ativo', '2026')
        res = conn.table('Alunos').select('*').eq('ano_letivo', active_year).execute()
        alunos = res.data if res.data else []
    except Exception as e:
        await bot_instance.reply_to(message, f"❌ Erro ao ler alunos: {e}")
        clear_state(chat_id)
        return
        
    matches = []
    query = term.strip().lower()
    for al in alunos:
        num = str(al.get('numero_interno', '')).lower()
        nome = str(al.get('nome_guerra', '')).lower()
        if query in num or query in nome or num.endswith("-" + query) or num.endswith(query):
            matches.append(al)
            
    if not matches:
        await bot_instance.reply_to(message, f"⚠️ Nenhum aluno encontrado com '{term}'. Consulta abortada.", reply_markup=get_main_menu_keyboard())
        clear_state(chat_id)
        return
        
    # Ordena os resultados da busca por ordem alfabética do nome de guerra
    matches = sorted(matches, key=lambda x: str(x.get('nome_guerra', '')).upper())
        
    if len(matches) > 1:
        chat_states[chat_id] = {
            'action': 'consulta',
            'step': 'choose_student',
            'user': profile,
            'data': {'matches': matches[:10]}
        }
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for idx, al in enumerate(chat_states[chat_id]['data']['matches']):
            markup.add(types.KeyboardButton(f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']}"))
        markup.add(types.KeyboardButton("❌ Cancelar"))
        
        prompt = "🔍 Múltiplos alunos encontrados. Selecione o correspondente abaixo:\n\n"
        for idx, al in enumerate(chat_states[chat_id]['data']['matches']):
            prompt += f"{idx + 1} — {al['numero_interno']} : {al['nome_guerra']} ({al['pelotao']})\n"
        await bot_instance.reply_to(message, prompt, reply_markup=markup)
    else:
        await display_student_dossier(bot_instance, message, conn, matches[0])

async def display_student_dossier(bot_instance, message, conn, student):
    chat_id = message.chat.id
    await bot_instance.send_chat_action(chat_id, 'typing')
    
    try:
        hoje_str = date.today().strftime('%Y-%m-%d')
        
        # 1. Presence Today
        pres_lbl = "⏳ SEM REGISTRO (Pendente)"
        try:
            res_p = conn.table('presenca_ausencia').select('*').eq('numero_interno', student['numero_interno']).eq('data', hoje_str).execute()
            if res_p.data:
                pres = res_p.data[0]
                if pres.get('presente'):
                    pres_lbl = "✅ PRESENTE"
                else:
                    motivo = pres.get('motivo_ausencia') or 'Sem motivo informado'
                    pres_lbl = f"❌ AUSENTE ({motivo})"
        except Exception:
            pass
            
        # 2. Health Status
        health_lbl = "🟢 Sem restrições ativas"
        try:
            res_h = conn.table('enfermaria').select('*').eq('numero_interno', student['numero_interno']).neq('status', 'Alta').execute()
            if res_h.data:
                for row in res_h.data:
                    data_ini = row.get('data_ini')
                    data_fim = row.get('data_fim')
                    esta_valido = True
                    if data_ini and data_fim:
                        try:
                            esta_valido = (str(data_ini) <= hoje_str <= str(data_fim))
                        except Exception:
                            pass
                    if esta_valido:
                        status = row.get('status')
                        motivo = row.get('motivo') or 'Sem motivo'
                        detalhe = row.get('detalhe')
                        detalhe_str = f" - {detalhe}" if detalhe else ""
                        periodo_str = f" [de {data_ini} a {data_fim}]" if data_ini and data_fim else ""
                        health_lbl = f"⚠️ SITUAÇÃO: {status} ({motivo}{detalhe_str}){periodo_str}"
                        break
        except Exception:
            pass
            
        # 3. Contacts
        tel_aluno = student.get('telefone_contato') or 'Não informado'
        emerg_nome = student.get('contato_emergencia_nome') or 'Não informado'
        emerg_num = student.get('contato_emergencia_numero') or 'Não informado'
        
        # 4. Last 5 Occurrences (Acoes)
        res_ac = conn.table('Acoes').select('*').eq('aluno_id', str(student['id'])).execute()
        acoes_list = res_ac.data if res_ac.data else []
        
        res_ta = conn.table('Tipos_Acao').select('*').execute()
        tipos_map = {str(t['id']): t for t in res_ta.data} if res_ta.data else {}
        
        acoes_sorted = sorted(acoes_list, key=lambda x: x.get('data', ''), reverse=True)[:5]
        ocurrences_lines = []
        for ac in acoes_sorted:
            tipo_id = str(ac.get('tipo_acao_id', ''))
            tipo_info = tipos_map.get(tipo_id)
            pts = float(tipo_info.get('pontuacao', 0.0) or 0.0) if tipo_info else 0.0
            data_part = ac.get('data', '').split()[0]
            try:
                dt_obj = datetime.strptime(data_part, '%Y-%m-%d')
                dt_lbl = dt_obj.strftime('%d/%m')
            except Exception:
                dt_lbl = data_part
                
            status_lbl = " [Pend.]" if ac.get('status') == 'Pendente' else ""
            desc = ac.get('descricao')
            desc_lbl = f" — {desc}" if desc else ""
            ocurrences_lines.append(f"• `{dt_lbl}`: {ac.get('tipo') or 'Ação'} ({pts:+.1f} pts){status_lbl}{desc_lbl}")
            
        ocurrences_str = "\n".join(ocurrences_lines) if ocurrences_lines else "• Nenhuma ocorrência registrada."
        
        dossier = (
            f"👤 DOSSIÊ DO ALUNO 👤\n\n"
            f"• Nome Completo: {student.get('nome_completo') or student.get('nome_guerra')}\n"
            f"• Nome de Guerra: {student.get('nome_guerra')}\n"
            f"• Número Interno: `{student.get('numero_interno')}`\n"
            f"• Pelotão (Turma): {student.get('pelotao')}\n"
            f"• Situação Cadastral: {student.get('status') or 'Ativo'}\n\n"
            f"📊 Presença Hoje: {pres_lbl}\n"
            f"🩺 Situação de Saúde: {health_lbl}\n\n"
            f"📞 Contatos de Emergência:\n"
            f"• Telefone do Aluno: `{tel_aluno}`\n"
            f"• Contato de Emergência: {emerg_nome} (`{emerg_num}`)\n\n"
            f"📋 Últimas 5 Ocorrências:\n"
            f"{ocurrences_str}"
        )
        
        await bot_instance.reply_to(message, dossier, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
    except Exception as e:
        await bot_instance.reply_to(message, f"❌ Erro ao gerar dossiê: {e}", reply_markup=get_main_menu_keyboard())
    finally:
        clear_state(chat_id)

async def init_bot():
    """Tarefa assíncrona inicializada no startup do NiceGUI para rodar o Telegram bot."""
    global bot, polling_task
    
    # Se DISABLE_TELEGRAM_BOT estiver ativo, pula a inicialização do bot
    if os.getenv("DISABLE_TELEGRAM_BOT") == "True":
        print("[TELEGRAM BOT] Desabilitado via variável de ambiente DISABLE_TELEGRAM_BOT=True.", flush=True)
        return
        
    # Se já existir uma instância ou tarefa rodando, garante o encerramento limpo antes de iniciar outra
    if polling_task or bot:
        print("[TELEGRAM BOT] Detectada instância ativa anterior. Parando-a primeiro...", flush=True)
        await stop_bot()
        
    token = get_bot_token()
    
    if not token:
        print("[TELEGRAM BOT] Erro: TELEGRAM_TOKEN não configurado no banco e nem no .env. Bot desabilitado.", flush=True)
        return
        
    try:
        print("[TELEGRAM BOT] Conectando ao Telegram...", flush=True)
        
        # DIAGNOSTICO DE REDE
        try:
            import socket
            print("[TELEGRAM DIAGNOSTIC] Iniciando teste de conexao...", flush=True)
            for host in ["api.telegram.org", "telegram-proxy.pixdiostudio.workers.dev", "hjlvxxmeefjgymwerqmk.supabase.co"]:
                try:
                    ips = socket.getaddrinfo(host, 443)
                    print(f"[TELEGRAM DIAGNOSTIC] Resolvido {host} para: {[ip[4][0] for ip in ips]}", flush=True)
                except Exception as e_dns:
                    print(f"[TELEGRAM DIAGNOSTIC] Erro de DNS para {host}: {e_dns}", flush=True)
                    
                try:
                    s = socket.create_connection((host, 443), timeout=5)
                    print(f"[TELEGRAM DIAGNOSTIC] Conexao TCP com {host}:443 realizada com SUCESSO!", flush=True)
                    s.close()
                except Exception as e_tcp:
                    print(f"[TELEGRAM DIAGNOSTIC] Erro de conexao TCP com {host}:443 -> {e_tcp}", flush=True)
                    
            # Teste de requisicao aiohttp assincrona com dump de erro
            import aiohttp
            print("[TELEGRAM DIAGNOSTIC] Testando requisicao HTTP assincrona com aiohttp...", flush=True)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://telegram-proxy.pixdiostudio.workers.dev/", timeout=5) as resp:
                        body = await resp.text()
                        print(f"[TELEGRAM DIAGNOSTIC] aiohttp com sucesso! Status: {resp.status}, Body length: {len(body)}", flush=True)
            except Exception as e_aio:
                import traceback
                print(f"[TELEGRAM DIAGNOSTIC] Erro detalhado no aiohttp: {e_aio}", flush=True)
                traceback.print_exc()
        except Exception as e_diag:
            print(f"[TELEGRAM DIAGNOSTIC] Falha ao executar diagnostico: {e_diag}", flush=True)
            
        import telebot
        from telebot import asyncio_helper
        
        custom_api_url = os.getenv("TELEGRAM_API_URL")
        if custom_api_url:
            print(f"[TELEGRAM BOT] Usando URL de API personalizada: {custom_api_url}", flush=True)
            telebot.apihelper.API_URL = custom_api_url
            asyncio_helper.API_URL = custom_api_url
            
        custom_proxy = os.getenv("TELEGRAM_PROXY")
        if custom_proxy:
            print(f"[TELEGRAM BOT] Usando proxy de conexao: {custom_proxy}", flush=True)
            telebot.apihelper.proxy = {'https': custom_proxy, 'http': custom_proxy}
            asyncio_helper.proxy = {'https': custom_proxy, 'http': custom_proxy}

        bot = AsyncTeleBot(token)
        setup_handlers(bot)
        
        # Configura a lista oficial de comandos no menu do Telegram
        try:
            print("[TELEGRAM BOT] Configurando lista de comandos no menu do Telegram...", flush=True)
            await bot.set_my_commands([
                types.BotCommand("menu", "Exibe o menu de comandos e teclado"),
                types.BotCommand("resumo", "Exibe o resumo diário do efetivo"),
                types.BotCommand("escala", "Consulta/altera escala de serviço"),
                types.BotCommand("consulta", "Dossiê completo de contatos de um aluno"),
                types.BotCommand("anotacao", "Lança comportamento/ocorrência"),
                types.BotCommand("presenca", "Realiza chamada coletiva da turma"),
                types.BotCommand("atrasado", "Registra atraso e retira falta do dia"),
                types.BotCommand("enfermaria", "Lança saúde/baixas de alunos"),
                types.BotCommand("pernoite", "Lança autorização de pernoite"),
                types.BotCommand("aviso", "Adiciona aviso corrido letreiro na TV"),
                types.BotCommand("vincular", "Associa Telegram ID ao usuário Web"),
                types.BotCommand("cancelar", "Cancela a operação atual")
            ])
            print("[TELEGRAM BOT] Lista de comandos configurada com sucesso!", flush=True)
        except Exception as cmd_err:
            print(f"[TELEGRAM BOT] Aviso ao configurar lista de comandos: {cmd_err}", flush=True)

        # Limpa qualquer webhook pendente e atualizações acumuladas para evitar erros de 409 Conflict no polling
        try:
            print("[TELEGRAM BOT] Limpando webhooks e atualizações pendentes...", flush=True)
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception as wh_err:
            print(f"[TELEGRAM BOT] Aviso ao deletar webhook: {wh_err}", flush=True)
            
        # Inicia polling infinito em segundo plano
        polling_task = asyncio.create_task(bot.polling(non_stop=True))
        print("[TELEGRAM BOT] Bot de Telegram ativo em segundo plano e escutando!", flush=True)
    except Exception as e:
        print(f"[TELEGRAM BOT] Erro crítico ao iniciar o Bot: {e}", flush=True)

async def stop_bot():
    """Para o bot de Telegram cancelando a tarefa de polling e fechando a sessão."""
    global bot, polling_task
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        polling_task = None
    if bot:
        try:
            await bot.close_session()
        except Exception as e:
            print(f"[TELEGRAM BOT] Erro ao fechar sessão: {e}", flush=True)
        bot = None
    print("[TELEGRAM BOT] Bot parado com sucesso.", flush=True)

async def restart_bot():
    """Para e reinicia o bot do Telegram com as novas configurações."""
    print("[TELEGRAM BOT] Reiniciando bot...", flush=True)
    await stop_bot()
    await init_bot()
