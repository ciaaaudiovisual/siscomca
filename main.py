import os
import socket

# Monkeypatch socket.getaddrinfo para forçar IPv4 e evitar timeouts de IPv6 no Hugging Face
original_getaddrinfo = socket.getaddrinfo
def forced_ipv4_getaddrinfo(*args, **kwargs):
    responses = original_getaddrinfo(*args, **kwargs)
    filtered = [r for r in responses if r[0] == socket.AF_INET]
    return filtered if filtered else responses
socket.getaddrinfo = forced_ipv4_getaddrinfo

from nicegui import ui, app
from dotenv import load_dotenv


# Mapeia a pasta local de assets para servir arquivos estáticos no navegador
assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
os.makedirs(assets_dir, exist_ok=True)
app.add_static_files('/assets', assets_dir)

import theme
import admin
import notifications
import theme_toggle
import alunos_cadastro
import alunos_presenca
import alunos_saude
import alunos_fila
import alunos_escalas
import alunos_pernoite
import alunos_rancho
import alunos_transporte
import gestao_acoes
import pagamentos
import turmas
import importacao_documentos
import geracao_documentos
import revisao_geral
import relatorio_geral
import conselho_avaliacao
import programacao
import relatorios
import assistente_ia
import config
import admin_panel
import telegram_bot
import siscomca_dashboard
import siscomca_tv
from database import authenticate_user, get_user_by_id
from services import data_service

# Carrega o .env a partir do diretório absoluto do arquivo
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

app.native.window_args['resizable'] = True
app.native.window_args['title'] = 'SisCOMCA'

PUBLIC_ROUTES = {'/login'}

siscomca_menu_categories = [
    {
        'category': 'PAINEL GERAL',
        'items': [
            {'name': 'Dashboard Alunos', 'icon': 'analytics', 'path': '/siscomca_dashboard'},
            {'name': 'Fila de Espera', 'icon': 'format_list_numbered', 'path': '/fila'},
        ]
    },
    {
        'category': 'CONTROLE DIÁRIO',
        'items': [
            {'name': 'Chamada Diária', 'icon': 'fact_check', 'path': '/presenca'},
            {'name': 'Enfermaria (Saúde)', 'icon': 'local_hospital', 'path': '/saude', 'roles': ['admin', 'supervisor', 'operador', 'comcia', 'ajosca']},
        ]
    },
    {
        'category': 'CADASTROS E EFETIVO',
        'items': [
            {'name': 'Alunos (Cadastro)', 'icon': 'person_search', 'path': '/alunos', 'roles': ['admin', 'supervisor', 'operador']},
            {'name': 'Gestão de Efetivo', 'icon': 'manage_accounts', 'path': '/admin', 'roles': ['admin', 'supervisor']},
        ]
    },
    {
        'category': 'APOIO LOGÍSTICO',
        'items': [
            {'name': 'Controle de Pernoite', 'icon': 'bed', 'path': '/pernoite', 'roles': ['admin', 'supervisor', 'operador', 'comcia', 'ajosca']},
            {'name': 'Prévia de Rancho', 'icon': 'restaurant', 'path': '/rancho'},
            {'name': 'Auxílio Transporte', 'icon': 'directions_bus', 'path': '/transporte'},
        ]
    },
    {
        'category': 'HISTÓRICO E DISCIPLINAR',
        'items': [
            {'name': 'Gestão de Ações', 'icon': 'gavel', 'path': '/gestao_acoes', 'roles': ['admin', 'supervisor', 'operador', 'comcia']},
            {'name': 'Revisão de Ocorrências', 'icon': 'rate_review', 'path': '/revisao_geral', 'roles': ['admin', 'supervisor', 'comcia']},
            {'name': 'Conselho de Avaliação', 'icon': 'gavel', 'path': '/conselho_avaliacao', 'roles': ['admin', 'supervisor', 'comcia']},
        ]
    },
    {
        'category': 'ENSINO E RELATÓRIOS',
        'items': [
            {'name': 'Programação de Instrução', 'icon': 'schedule', 'path': '/programacao', 'roles': ['admin', 'supervisor', 'comcia']},
            {'name': 'Relatórios de Ensino', 'icon': 'analytics', 'path': '/relatorios', 'roles': ['admin', 'supervisor', 'comcia']},
            {'name': 'Relatório Geral', 'icon': 'assessment', 'path': '/relatorio_geral', 'roles': ['admin', 'supervisor', 'comcia']},
        ]
    },
    {
        'category': 'FERRAMENTAS E ARQUIVOS',
        'items': [
            {'name': 'Assistente de IA', 'icon': 'psychology', 'path': '/assistente_ia'},
            {'name': 'Geração de Documentos', 'icon': 'summarize', 'path': '/geracao_documentos', 'roles': ['admin', 'supervisor', 'comcia']},
            {'name': 'Importação de Dados', 'icon': 'upload_file', 'path': '/importacao_documentos', 'roles': ['admin']},
            {'name': 'Controle Financeiro', 'icon': 'payments', 'path': '/pagamentos', 'roles': ['admin']},
        ]
    },
    {
        'category': 'ADMINISTRAÇÃO',
        'items': [
            {'name': 'Configurações', 'icon': 'settings', 'path': '/config', 'roles': ['admin', 'supervisor']},
            {'name': 'Usuários e Permissões', 'icon': 'admin_panel_settings', 'path': '/admin_panel', 'roles': ['admin']},
        ]
    }
]


def is_authenticated() -> bool:
    authenticated = app.storage.user.get('authenticated', False)
    if authenticated:
        login_time = app.storage.user.get('login_time')
        duration = app.storage.user.get('session_duration')
        if login_time and duration and duration > 0:
            import time
            if time.time() - login_time > duration:
                app.storage.user.clear()
                return False
    return authenticated


def get_current_user() -> dict:
    return app.storage.user.get('user_data', {})


def check_auth():
    if not is_authenticated():
        ui.navigate.to('/login')


def build_layout(page_func):
    def wrapper():
        if not is_authenticated():
            ui.navigate.to('/login')
            return
            
        role_user = str(app.storage.user.get('user_data', {}).get('role', '')).strip().lower()
        if role_user in ('tv', 'tv_comcia') and app.storage.user.get('current_path') != '/siscomca_tv':
            ui.navigate.to('/siscomca_tv')
            return
            
        if app.storage.user.get('tv_lock_active', False) and app.storage.user.get('current_path') != '/siscomca_tv':
            ui.navigate.to('/siscomca_tv')
            return
            
        theme.apply_global_styles()
        
        # Se for sessão temporária, atualiza o timestamp de atividade para renovar as 2h
        duration = app.storage.user.get('session_duration')
        if duration and duration > 0:
            import time
            app.storage.user['login_time'] = time.time()
            
        user_cached = get_current_user()
        user = user_cached
        if user_cached and 'id' in user_cached:
            import pandas as pd
            users_df = data_service.get_core_data().get('users', pd.DataFrame())
            if not users_df.empty:
                user_row = users_df[users_df['id'].astype(str) == str(user_cached['id'])]
                if not user_row.empty:
                    p_row = user_row.iloc[0]
                    user = {
                        'id': p_row.get('id'),
                        'username': p_row.get('username'),
                        'nome_guerra': p_row.get('nome', p_row.get('username')),
                        'role': p_row.get('role', 'compel'),
                        'email': user_cached.get('email', '')
                    }
        
        user_name = user.get('nome_guerra') if user else 'Operador'
        role = str(user.get('role', 'compel')).strip().lower() if user else 'compel'
        role_map = {
            'admin': 'Administrador',
            'supervisor': 'Supervisor',
            'comcia': 'Comissão CIA',
            'compel': 'Companhia Alunos',
            'aluno': 'Aluno',
            'ajosca': 'Ajosca'
        }
        user_posto = user.get('posto') or role_map.get(role, 'Operador')
        
        system_title = str(data_service.get_config_value('cabecalho_tv_title', 'SISTEMA C2') or 'SISTEMA C2').upper()
        ui.run_javascript(f"document.title = '{system_title}'")
        
        with ui.header().classes('no-shadow').style(f'background: {theme.colors["bg_panel"]}; border-bottom: {theme.colors["border"]}'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white dense')
                    ui.icon('shield', color='primary').classes('text-2xl drop-shadow-[0_0_8px_rgba(0,229,255,0.4)]')
                    with ui.column().classes('gap-0'):
                        ui.label(system_title).style(f'color: {theme.colors["primary"]}; font-weight: bold; line-height: 1; letter-spacing: 1px;').classes('cyber-title')
                        ui.label('Corpo de Alunos • 1º Batalhão').style('font-size: 0.65rem; color: #64748b;')
                
                with ui.row().classes('items-center gap-3 no-wrap'):
                    # Seletor Global de Ano Letivo
                    active_year = app.storage.user.setdefault('ano_letivo_ativo', '2026')
                    
                    # Notificação inicial de conexão ao Ano Letivo
                    if not app.storage.user.get('year_notified'):
                        ui.notify(f'🟢 Conectado ao Ano Letivo {active_year}', color='positive', position='top')
                        app.storage.user['year_notified'] = True
                    
                    def change_global_year(e):
                        app.storage.user['ano_letivo_ativo'] = e.value
                        c_state = app.storage.user.get('alunos_state', {})
                        c_state['ano_letivo'] = e.value
                        app.storage.user['alunos_state'] = c_state
                        ui.notify(f'🔄 Carregando dados do Ano Letivo {e.value}...', color='primary', position='top')
                        # Força atualização/recarga da página atual
                        ui.navigate.to(app.storage.user.get('current_path', '/'))
                        
                    ui.select(
                        ['2025', '2026'], 
                        value=active_year, 
                        on_change=change_global_year
                    ).props('dark outlined dense options-dark').classes('w-24 text-xs font-bold').style('max-height: 32px;')

                    theme_toggle.render_theme_toggle()
                    notifications.render_notification_bell()
                    with ui.column().classes('items-end gap-0 gt-xs'):
                        ui.label(user_name).classes('text-white text-weight-bold text-xs')
                        ui.label(user_posto).classes('text-grey-5 text-xs')
                    user_photo = user.get('url_foto') if user else None
                    user_avatar_src = user_photo if isinstance(user_photo, str) and user_photo.startswith('http') else 'https://cdn.quasar.dev/img/boy-avatar.png'
                    ui.avatar().props('size=32px').style(f"background-image: url('{user_avatar_src}'); background-size: cover; background-position: center; border: 1px solid rgba(255, 255, 255, 0.2);")
                    with ui.button(on_click=logout, icon='logout').props('flat round color=red dense'):
                        ui.tooltip('Sair do Sistema')
        left_drawer = ui.left_drawer(value=True).classes('no-shadow').style(f'background: {theme.colors["bg_panel"]}; border-right: {theme.colors["border"]}')
        with left_drawer:
            with ui.column().classes('w-full q-py-md gap-1'):
                def render_menu_list(categories):
                    user_role = role
                    import pandas as pd
                    perms_df = data_service.get_core_data().get('permissions', pd.DataFrame())
                    
                    for cat in categories:
                        allowed_items = []
                        for item in cat['items']:
                            path_clean = item['path'].strip('/').replace('/', '_')
                            f_key = f"menu_{path_clean}"
                            
                            # Buscar allowed_roles da permissão no banco
                            row = perms_df[perms_df['feature_key'] == f_key] if not perms_df.empty else pd.DataFrame()
                            
                            if not row.empty:
                                allowed_roles_str = str(row['allowed_roles'].iloc[0])
                                allowed_roles = [r.strip().lower() for r in allowed_roles_str.split(',') if r.strip()]
                                if user_role in allowed_roles:
                                    allowed_items.append(item)
                            else:
                                if 'roles' in item:
                                    if user_role in item['roles']:
                                        allowed_items.append(item)
                                else:
                                    allowed_items.append(item)
                        
                        if not allowed_items:
                            continue
                            
                        with ui.row().classes('w-full q-px-md q-pt-sm q-pb-xs items-center gap-2'):
                            ui.label(cat['category']).classes('text-[9px] text-primary/80 text-weight-bold tracking-widest cyber-title')
                        
                        for item in allowed_items:
                            is_active = app.storage.user.get('current_path') == item['path']
                            bg_active = 'bg-primary/10 border-l-2 border-primary' if is_active else 'hover:bg-white/5'
                            text_active = theme.colors['primary'] if is_active else 'text-grey-4'
                            with ui.link(target=item['path']).classes('w-full no-underline'):
                                with ui.row().classes(f'w-full q-px-md q-py-xs items-center gap-3 transition-colors {bg_active} rounded-r-sm'):
                                    ui.icon(item['icon']).classes(f'{text_active} text-xs')
                                    ui.label(item['name']).classes(f'{text_active} text-weight-medium text-xs')

                render_menu_list(siscomca_menu_categories)

        with ui.column().classes('w-full h-full p-0'):
            page_func()

    return wrapper


def logout():
    app.storage.user.clear()
    ui.notify('Session encerrada', color='info')
    ui.navigate.to('/login')


@ui.page('/')
def index_page():
    app.storage.user['current_path'] = '/' 
    build_layout(siscomca_dashboard.render_page)()


@ui.page('/admin')
def admin_page():
    app.storage.user['current_path'] = '/admin'
    build_layout(admin.render_page)()


@ui.page('/alunos')
def alunos_page():
    app.storage.user['current_path'] = '/alunos'
    build_layout(alunos_cadastro.render_page)()


@ui.page('/presenca')
def presenca_page():
    app.storage.user['current_path'] = '/presenca'
    build_layout(alunos_presenca.render_page)()


@ui.page('/saude')
def saude_page():
    app.storage.user['current_path'] = '/saude'
    build_layout(alunos_saude.render_page)()


@ui.page('/fila')
def fila_page():
    app.storage.user['current_path'] = '/fila'
    build_layout(alunos_fila.render_page)()


@ui.page('/escalas')
def escalas_page():
    app.storage.user['current_path'] = '/escalas'
    build_layout(alunos_escalas.render_page)()


@ui.page('/pernoite')
def pernoite_page():
    app.storage.user['current_path'] = '/pernoite'
    build_layout(alunos_pernoite.render_page)()


@ui.page('/rancho')
def rancho_page():
    app.storage.user['current_path'] = '/rancho'
    build_layout(alunos_rancho.render_page)()


@ui.page('/transporte')
def transporte_page():
    app.storage.user['current_path'] = '/transporte'
    build_layout(alunos_transporte.render_page)()


@ui.page('/gestao_acoes')
def gestao_acoes_page():
    app.storage.user['current_path'] = '/gestao_acoes'
    build_layout(gestao_acoes.render_page)()


@ui.page('/pagamentos')
def pagamentos_page():
    app.storage.user['current_path'] = '/pagamentos'
    build_layout(pagamentos.render_page)()


@ui.page('/turmas')
def turmas_page():
    app.storage.user['current_path'] = '/turmas'
    build_layout(turmas.render_page)()


@ui.page('/importacao_documentos')
def importacao_documentos_page():
    app.storage.user['current_path'] = '/importacao_documentos'
    build_layout(importacao_documentos.render_page)()


@ui.page('/geracao_documentos')
def geracao_documentos_page():
    app.storage.user['current_path'] = '/geracao_documentos'
    build_layout(geracao_documentos.render_page)()


@ui.page('/revisao_geral')
def revisao_geral_page():
    app.storage.user['current_path'] = '/revisao_geral'
    build_layout(revisao_geral.render_page)()


@ui.page('/relatorio_geral')
def relatorio_geral_page():
    app.storage.user['current_path'] = '/relatorio_geral'
    build_layout(relatorio_geral.render_page)()


@ui.page('/conselho_avaliacao')
def conselho_avaliacao_page():
    app.storage.user['current_path'] = '/conselho_avaliacao'
    build_layout(conselho_avaliacao.render_page)()


@ui.page('/programacao')
def programacao_page():
    app.storage.user['current_path'] = '/programacao'
    build_layout(programacao.render_page)()


@ui.page('/relatorios')
def relatorios_page():
    app.storage.user['current_path'] = '/relatorios'
    build_layout(relatorios.render_page)()


@ui.page('/assistente_ia')
def assistente_ia_page():
    app.storage.user['current_path'] = '/assistente_ia'
    build_layout(assistente_ia.render_page)()


@ui.page('/config')
def config_page():
    app.storage.user['current_path'] = '/config'
    build_layout(config.render_page)()


@ui.page('/admin_panel')
def admin_panel_page():
    app.storage.user['current_path'] = '/admin_panel'
    build_layout(admin_panel.render_page)()



@ui.page('/siscomca_dashboard')
def siscomca_dashboard_page():
    app.storage.user['current_path'] = '/siscomca_dashboard'
    build_layout(siscomca_dashboard.render_page)()


@ui.page('/siscomca_tv')
def siscomca_tv_page():
    """Modo TV/Monitor do SisCOMCA — sem barra lateral, tela cheia."""
    check_auth()
    app.storage.user['current_path'] = '/siscomca_tv'
    app.storage.user['tv_lock_active'] = True
    siscomca_tv.render_page()


@ui.page('/login')
def login_page():
    theme.apply_global_styles()
    
    # Dialog de Solicitação de Acesso
    with ui.dialog() as reg_dialog, ui.card().classes('w-96 q-pa-md').style(
        f'background: {theme.colors["bg_panel"]}; border: {theme.colors["border"]};'
    ):
        with ui.column().classes('w-full items-center gap-4'):
            ui.label('📝 Solicitar Acesso').classes('text-white text-lg font-bold')
            ui.label('Preencha os dados para solicitar acesso').classes('text-grey-5 text-xs text-center')
            
            reg_email = ui.input('E-mail').props('dark dense outlined w-full')
            reg_pwd = ui.input('Senha', password=True).props('dark dense outlined w-full')
            reg_nome = ui.input('Nome Completo').props('dark dense outlined w-full')
            reg_guerra = ui.input('Nome de Guerra').props('dark dense outlined w-full')
            
            reg_error = ui.label('').classes('text-caption text-red')
            
            def submit_registration():
                if not reg_email.value or not reg_pwd.value or not reg_nome.value or not reg_guerra.value:
                    reg_error.text = 'Preencha todos os campos'
                    return
                if len(reg_pwd.value) < 6:
                    reg_error.text = 'A senha deve ter no mínimo 6 caracteres'
                    return
                
                from database import get_db_connection
                db_conn = get_db_connection()
                if db_conn:
                    try:
                        res = db_conn.auth.sign_up({"email": reg_email.value, "password": reg_pwd.value})
                        if res.user:
                            db_conn.table("RegistrationRequests").insert({
                                "id": res.user.id,
                                "email": reg_email.value,
                                "nome_completo": reg_nome.value,
                                "nome_guerra": reg_guerra.value,
                                "status": "pending"
                            }).execute()
                            
                            try:
                                from notifications_manager import notify_telegram
                                alert_txt = (
                                    f"🔔 **SOLICITAÇÃO DE NOVO CADASTRO**\n\n"
                                    f"👤 Nome: {reg_nome.value.upper()} ({reg_guerra.value.upper()})\n"
                                    f"📧 E-mail: {reg_email.value}\n"
                                    f"⚡ Status: Aguardando aprovação administrativa no painel."
                                )
                                notify_telegram(alert_txt, "new_user", role_required="admin")
                            except Exception as e_notif:
                                print(f"[MAIN REG NOTIFY ERROR] {e_notif}")
                                
                            ui.notify('Solicitação enviada com sucesso! Aguarde aprovação.', color='success')
                            reg_dialog.close()
                        else:
                            reg_error.text = 'Não foi possível registrar o usuário'
                    except Exception as err:
                        reg_error.text = f'Erro: {err}'
                else:
                    ui.notify('Solicitação simulada com sucesso (modo offline)', color='warning')
                    reg_dialog.close()
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancelar', on_click=reg_dialog.close).props('flat color=grey')
                ui.button('Enviar', on_click=submit_registration).props('unelevated color=amber-9 text-color=black')

    # Fundo do login
    with ui.column().classes('w-full h-screen items-center justify-center p-4 gap-4').style(
        'background: linear-gradient(135deg, #121212 0%, #1e1e2f 100%);'
    ):
        with ui.card().classes('w-full max-w-md no-shadow rounded-xl q-pa-lg').style(
            f'background: {theme.colors["bg_panel"]}; border: {theme.colors["border"]}; box-shadow: 0 10px 40px rgba(0,0,0,0.6) !important;'
        ):
            with ui.column().classes('w-full items-center gap-4'):
                
                # ── TOPO: LOGO E IDENTIFICAÇÃO ──
                ui.icon('shield', size='5.5rem', color='amber-9').classes('drop-shadow-[0_0_15px_rgba(212,175,55,0.4)]')
                ui.label('SisCOMCA').classes('cyber-title').style(
                    f'color: {theme.colors["primary"]}; font-size: 2.8rem; font-weight: 700; letter-spacing: 2px; line-height: 1;'
                )
                with ui.column().classes('gap-0 items-center text-center'):
                    ui.label('Sistema de Gestão de Alunos').classes('text-white text-md font-bold')
                    ui.label('Centro de Instrução da Marinha').classes('text-grey-4 text-xs tracking-wider q-mt-xs')
                
                ui.separator().style('background-color: rgba(0, 229, 255, 0.15); height: 1px;').classes('w-3/4 q-my-sm')
                
                # ── FORMULÁRIO DE ACESSO ──
                with ui.element('form').props('onsubmit="return false;"').classes('w-full flex flex-col gap-4 items-center').on('submit', lambda: try_login()):
                    with ui.column().classes('w-full gap-0.5 items-center text-center q-mb-xs'):
                        ui.label('🔐 ACESSO AO SISTEMA').classes('text-white text-md font-bold cyber-title tracking-widest')
                        ui.label('Entre com suas credenciais').classes('text-grey-5 text-xs')
                    
                    user = ui.input('E-mail', value=app.storage.user.get('last_username', '')).props('dark outlined w-full autocomplete=username name=username').classes('w-full text-sm')
                    pwd = ui.input('Senha', password=True).props('dark outlined w-full autocomplete=current-password name=password').classes('w-full text-sm')
                    
                    session_type = ui.radio(
                        {0: 'Manter conectado (Sempre)', 7200: 'Sessão temporária (2 horas)'}, 
                        value=0
                    ).props('dark inline dense').classes('text-[11px] text-grey q-mt-xs self-center')
                    
                    error_label = ui.label('').classes('text-xs text-red w-full text-center')
                    
                    def try_login():
                        if not user.value or not pwd.value:
                            error_label.text = 'Preencha todos os campos'
                            return
                        
                        from database import get_db_connection, authenticate_user_supabase
                        db_conn = get_db_connection()
                        
                        if not db_conn:
                            error_label.text = 'Sem conexão com o Supabase. Verifique sua rede.'
                            return
                        
                        try:
                            auth_res = authenticate_user_supabase(user.value, pwd.value)
                        except Exception as e:
                            print(f"Erro ao autenticar no Supabase: {e}")
                            auth_res = None
                        
                        if auth_res:
                            profile = auth_res['profile']
                            session_data = auth_res['session']
                            
                            import time
                            app.storage.user['authenticated'] = True
                            app.storage.user['login_time'] = time.time()
                            app.storage.user['session_duration'] = session_type.value
                            app.storage.user['last_username'] = user.value
                            app.storage.user['user_data'] = {
                                'id': profile.get('id'),
                                'username': profile.get('username'),
                                'nome_guerra': profile.get('nome', profile.get('username')),
                                'role': profile.get('role', 'compel'),
                                'email': user.value
                            }
                            app.storage.user['supabase_session'] = session_data
                            
                            role_user = str(profile.get('role', 'compel')).strip().lower()
                            target_path = '/siscomca_tv' if role_user in ('tv', 'tv_comcia') else '/'
                            app.storage.user['current_path'] = target_path
                            ui.notify(f'Bem-vindo, {profile.get("nome", user.value)}!', color='success')
                            # Força redirecionamento físico de página via JS para o gerenciador de senhas do navegador salvar as credenciais
                            ui.run_javascript(f"window.location.href = '{target_path}'")
                        else:
                            error_label.text = 'E-mail ou senha incorretos'
 
                    ui.button('🚀 Entrar no Sistema').props('type=submit unelevated color=amber-9 text-color=black w-full bold').classes('q-py-sm font-bold text-sm cyber-title w-full')
                    
                    ui.button('📝 Não tem uma conta? Solicite acesso', on_click=reg_dialog.open).props('flat color=grey no-caps').classes('w-full text-xs text-center')

        # Rodapé (Footer) centralizado fora do card principal
        ui.label('🚀 Desenvolvido por Sargento Calaça 🇧🇷').classes('text-amber-5 text-xs font-bold tracking-wider opacity-80')

def sync_menu_permissions_db():
    try:
        from database import get_db_connection
        db = get_db_connection()
        if not db:
            return
        
        # Obter todos os itens de menu
        menu_items = []
        for cat in siscomca_menu_categories:
            for item in cat['items']:
                menu_items.append(item)
                
        # Buscar permissões atuais
        res = db.table('Permissions').select('feature_key').execute()
        existing_keys = {row['feature_key'] for row in res.data} if res.data else set()
        
        # Inserir novos itens de menu se não existirem
        new_permissions = []
        for item in menu_items:
            path_clean = item['path'].strip('/').replace('/', '_')
            f_key = f"menu_{path_clean}"
            if f_key not in existing_keys:
                # Default allowed roles (as configured in main.py)
                default_roles = ",".join(item.get('roles', [])) if 'roles' in item else "admin,supervisor,operador,comcia,compel,aluno,ajosca"
                new_permissions.append({
                    'feature_key': f_key,
                    'feature_name': f"Acesso ao Menu: {item['name']}",
                    'allowed_roles': default_roles
                })
        
        if new_permissions:
            db.table('Permissions').insert(new_permissions).execute()
            print(f"[DB] Sincronizados {len(new_permissions)} novos menus com a tabela Permissions.")
    except Exception as e:
        print(f"[ERRO sync_menu_permissions_db] {e}")

# Inicializa o Bot do Telegram concorrente ao servidor
from alerts_manager import AlertsManager
app.on_startup(sync_menu_permissions_db)
app.on_startup(telegram_bot.init_bot)
app.on_startup(AlertsManager.start_alerts_scheduler)

# Loop de liberação periódica de memória RAM para manter o pico sob 400MB
async def memory_cleanup_loop():
    import gc
    import asyncio
    while True:
        await asyncio.sleep(300) # Coleta a cada 5 minutos
        gc.collect()
        # Força o coletor a limpar referências circulares e liberar blocos para o SO
app.on_startup(memory_cleanup_loop)

# Garante o encerramento limpo da sessão do bot do Telegram ao desligar ou recarregar
app.on_shutdown(telegram_bot.stop_bot)

# Configuração dinâmica para deploy na nuvem (Render, Railway, Hugging Face, etc.)
port_env = int(os.environ.get('PORT', 7860))
host_env = os.environ.get('HOST', '0.0.0.0')
secret_env = os.environ.get('STORAGE_SECRET', 'CHAVE_SECRETA_ALEATORIA')

# Desativamos o 'reload' por padrão para rodar em Modo Produção super leve, veloz, estável e sem reinícios.
ui.run(
    title='SisCOMCA', 
    dark=True, 
    storage_secret=secret_env, 
    host=host_env,
    port=port_env,
    reload=False
)
