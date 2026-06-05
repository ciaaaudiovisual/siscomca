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
from fastapi import Request
from dotenv import load_dotenv


# Mapeia a pasta local de assets para servir arquivos estáticos no navegador
assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
os.makedirs(assets_dir, exist_ok=True)
app.add_static_files('/assets', assets_dir)

import theme
from logo_base64 import LOGO_BASE64
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
import ajuda_sobre
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
    },
    {
        'category': 'SISTEMA E AJUDA',
        'items': [
            {'name': 'Ajuda / Sobre', 'icon': 'help_outline', 'path': '/ajuda_sobre'},
        ]
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# Mapeamento de rotas → roles permitidos (construído a partir do menu)
# Rotas sem restrição de role ficam abertas a qualquer usuário autenticado.
# ─────────────────────────────────────────────────────────────────────────────
ROUTE_ROLES: dict[str, list[str]] = {}
for _cat in siscomca_menu_categories:
    for _item in _cat['items']:
        if 'roles' in _item:
            ROUTE_ROLES[_item['path']] = _item['roles']


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

        # ── AUTORIZAÇÃO SERVER-SIDE: verifica role contra rotas protegidas ──
        current_path = app.storage.user.get('current_path', '/')
        path_clean = current_path.strip('/').replace('/', '_')
        f_key = f"menu_{path_clean}"
        
        import pandas as pd
        perms_df = data_service.get_core_data().get('permissions', pd.DataFrame())
        row = perms_df[perms_df['feature_key'] == f_key] if not perms_df.empty else pd.DataFrame()
        
        allowed_roles = []
        if not row.empty:
            allowed_roles_str = str(row['allowed_roles'].iloc[0])
            allowed_roles = [r.strip().lower() for r in allowed_roles_str.split(',') if r.strip()]
        elif current_path in ROUTE_ROLES:
            allowed_roles = ROUTE_ROLES[current_path]
            
        if allowed_roles:
            if role_user not in allowed_roles:
                ui.notify('⛔ Acesso não autorizado para esta página.', color='negative')
                app.storage.user['current_path'] = '/'
                ui.navigate.to('/')
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
                        'email': user_cached.get('email', ''),
                        'url_foto': p_row.get('url_foto')
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
                    ui.image(LOGO_BASE64).style('width: 46px; height: 46px; box-shadow: 0 0 15px rgba(0, 229, 255, 0.5); border-radius: 50%; border: 1px solid rgba(0, 229, 255, 0.3);').classes('drop-shadow-[0_0_10px_rgba(0,229,255,0.4)]')
                    with ui.column().classes('gap-0'):
                        ui.label(system_title).style(f'color: {theme.colors["primary"]}; font-weight: bold; line-height: 1; letter-spacing: 1.5px; font-size: 1.2rem;').classes('cyber-title')
                        ui.label('Corpo de Alunos • 1º Batalhão').style('font-size: 0.75rem; color: #64748b;')
                
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
                    ui.element('div').classes('shadow shrink-0').style(
                        f"width: 32px; height: 32px; background-image: url('{user_avatar_src}'); "
                        f"background-size: cover; background-position: center; border-radius: 4px; "
                        f"border: 1.5px solid rgba(0, 229, 255, 0.4); box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);"
                    )

                    with ui.button(on_click=lambda: open_change_password_dialog(user), icon='vpn_key').props('flat round color=amber-9 dense'):
                        ui.tooltip('Alterar Minha Senha')
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


def open_change_password_dialog(user):
    with ui.dialog() as pwd_dialog, ui.card().classes('w-96 q-pa-md').style(
        f'background: {theme.colors["bg_panel"]}; border: {theme.colors["border"]};'
    ):
        with ui.column().classes('w-full gap-4'):
            with ui.row().classes('items-center gap-2 w-full justify-between'):
                ui.label('🔑 ALTERAR MINHA SENHA').classes('text-white text-md font-black cyber-title')
                ui.icon('lock_reset', size='1.5rem').style('color: #ffb300;')
            ui.separator().style('background-color: rgba(255, 179, 0, 0.15);')
            
            ui.label(f"Militar: {user.get('nome_guerra', '').upper()}").classes('text-xs text-grey-4')
            new_pwd = ui.input('Nova Senha', password=True).props('dark outlined dense w-full')
            confirm_pwd = ui.input('Confirmar Nova Senha', password=True).props('dark outlined dense w-full')
            pwd_error = ui.label('').classes('text-xs text-red w-full text-center')
            
            def handle_password_change():
                if not new_pwd.value or len(new_pwd.value) < 6:
                    pwd_error.text = 'A senha deve conter no mínimo 6 caracteres.'
                    return
                if new_pwd.value != confirm_pwd.value:
                    pwd_error.text = 'As senhas digitadas não coincidem.'
                    return
                
                from database import get_db_connection, get_service_db_connection
                db_conn = get_db_connection()
                if not db_conn:
                    ui.notify('Sem conexão com banco de dados', color='red')
                    return
                
                try:
                    # 1. Atualiza no Supabase Auth
                    db_conn.auth.update_user({"password": new_pwd.value})
                    
                    # 2. Atualiza a tabela efetivo se houver e-mail
                    user_email = user.get('email')
                    if user_email:
                        import bcrypt
                        pwd_hash = bcrypt.hashpw(new_pwd.value.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
                        
                        # Usa conexão de serviço para contornar RLS
                        svc_conn = get_service_db_connection()
                        if svc_conn:
                            try:
                                svc_conn.table('efetivo').update({'senha_hash': pwd_hash}).eq('email', user_email).execute()
                            except Exception as db_err:
                                print(f"[DB ERR SYNC PASSWORD] {db_err}")
                    
                    ui.notify('Sua senha foi alterada com sucesso!', color='success')
                    pwd_dialog.close()
                except Exception as err:
                    pwd_error.text = f"Erro ao atualizar: {err}"
            
            with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                ui.button('Cancelar', on_click=pwd_dialog.close).props('flat color=grey')
                ui.button('Salvar Senha', on_click=handle_password_change).props('unelevated color=amber-9 text-color=black')
    pwd_dialog.open()


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


@ui.page('/ajuda_sobre')
def ajuda_sobre_page():
    app.storage.user['current_path'] = '/ajuda_sobre'
    build_layout(ajuda_sobre.render_page)()



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
def login_page(request: Request):
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
                
                from database import get_db_connection, get_service_db_connection
                db_conn = get_db_connection()
                if db_conn:
                    try:
                        svc_conn = get_service_db_connection()
                        auth_id = None
                        created_via_admin = False
                        
                        # 1. Tenta criar via Service Role Admin (bypassa confirmação de e-mail e rate limit)
                        if svc_conn and hasattr(svc_conn, 'auth') and hasattr(svc_conn.auth, 'admin'):
                            try:
                                res = svc_conn.auth.admin.create_user({
                                    "email": reg_email.value,
                                    "password": reg_pwd.value,
                                    "email_confirm": True
                                })
                                if res and res.user:
                                    auth_id = res.user.id
                                    created_via_admin = True
                            except Exception as admin_err:
                                print(f"[ADMIN SIGNUP REGISTER ERR] {admin_err}")
                                
                        # 2. Se falhar ou não tiver a chave, tenta signup normal
                        if not auth_id:
                            try:
                                res = db_conn.auth.sign_up({"email": reg_email.value, "password": reg_pwd.value})
                                if res and res.user:
                                    auth_id = res.user.id
                            except Exception as signup_err:
                                print(f"[NORMAL SIGNUP REGISTER ERR] {signup_err}")
                                
                        # 3. Se ainda assim falhar (ex: rate limit exceeded), cria no banco local/Postgres diretamente
                        if not auth_id:
                            import uuid
                            auth_id = str(uuid.uuid4())
                            ui.notify('Limite de e-mails atingido. Criando conta no banco local...', color='warning', duration=6)
                            
                        # Determina conexão a ser usada para as inserções no banco
                        svc_conn_to_use = svc_conn if svc_conn else db_conn
                        
                        # 1. Cria a solicitação pendente para aprovação/controle posterior
                        try:
                            svc_conn_to_use.table("RegistrationRequests").insert({
                                "id": auth_id,
                                "email": reg_email.value,
                                "nome_completo": reg_nome.value,
                                "nome_guerra": reg_guerra.value,
                                "status": "pending"
                            }).execute()
                        except Exception as req_err:
                            print(f"[REG REQUEST ERR] {req_err}")
                            
                        # 2. Cria imediatamente o perfil de acesso limitado (aluno) para evitar bloqueio inicial
                        try:
                            svc_conn_to_use.table("Users").insert({
                                "id": auth_id,
                                "username": reg_email.value.split('@')[0],
                                "nome": reg_guerra.value.upper(),
                                "role": "aluno"
                            }).execute()
                        except Exception as users_err:
                            print(f"[REG USERS ERR] {users_err}")
                            
                        # 3. Cria o hash e insere na tabela efetivo
                        import bcrypt
                        pwd_hash = bcrypt.hashpw(reg_pwd.value.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
                        try:
                            svc_conn_to_use.table('efetivo').insert({
                                'nome_guerra': reg_guerra.value.upper(),
                                'email': reg_email.value,
                                'senha_hash': pwd_hash,
                                'role': 'aluno'
                            }).execute()
                        except Exception as e_ef:
                            print(f"[REG EFETIVO ERR] {e_ef}")
                            
                        try:
                            from notifications_manager import notify_telegram
                            alert_txt = (
                                f"🔔 **NOVA SOLICITAÇÃO DE ACESSO**\n\n"
                                f"👤 Nome: {reg_nome.value.upper()} ({reg_guerra.value.upper()})\n"
                                f"📧 E-mail: {reg_email.value}\n"
                                f"⚡ Papel Temporário: `aluno` (Acesso Liberado com limites).\n"
                                f"⚙️ Ação: O administrador pode alterar as permissões deste usuário no painel a qualquer momento."
                            )
                            notify_telegram(alert_txt, "new_user", role_required="admin", request_id=auth_id)
                        except Exception as e_notif:
                            print(f"[MAIN REG NOTIFY ERROR] {e_notif}")
                            
                        ui.notify('Solicitação enviada e acesso inicial liberado! Efetue o login.', color='success')
                        reg_dialog.close()
                    except Exception as err:
                        reg_error.text = f'Erro: {err}'
                else:
                    ui.notify('Solicitação simulada com sucesso (modo offline)', color='warning')
                    reg_dialog.close()
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancelar', on_click=reg_dialog.close).props('flat color=grey')
                ui.button('Enviar', on_click=submit_registration).props('unelevated color=amber-9 text-color=black')

    # Dialog de Recuperação de Senha
    with ui.dialog() as rec_pwd_dialog, ui.card().classes('w-96 q-pa-md').style(
        f'background: {theme.colors["bg_panel"]}; border: {theme.colors["border"]};'
    ):
        with ui.column().classes('w-full items-center gap-4'):
            ui.label('🔑 Recuperar Senha').classes('text-white text-lg font-bold')
            ui.label('Insira seu e-mail cadastrado para solicitar a recuperação da senha.').classes('text-grey-5 text-xs text-center')
            
            rec_email = ui.input('E-mail').props('dark dense outlined w-full')
            rec_error = ui.label('').classes('text-caption text-red')
            
            def submit_recovery():
                if not rec_email.value:
                    rec_error.text = 'Preencha o campo de e-mail'
                    return
                
                from database import get_db_connection
                db_conn = get_db_connection()
                if db_conn:
                    try:
                        # 1. Envia link de recuperação pelo Supabase Auth
                        db_conn.auth.reset_password_for_email(rec_email.value)
                        
                        # 2. Alerta o administrador no Telegram (para contingência caso o SMTP atinja limite)
                        try:
                            from notifications_manager import notify_telegram
                            alert_txt = (
                                f"🔑 **SOLICITAÇÃO DE RECUPERAÇÃO DE SENHA**\n\n"
                                f"📧 E-mail: {rec_email.value}\n"
                                f"⚡ Ação: Caso o e-mail automático não chegue devido a limites de SMTP do Supabase, "
                                f"você pode redefinir a senha deste militar no painel web em *Usuários e Permissões*."
                            )
                            notify_telegram(alert_txt, "saude", role_required="admin")
                        except Exception as e_notif:
                            print(f"[RECOVERY NOTIFY ERROR] {e_notif}")
                        
                        ui.notify('Solicitação enviada! Verifique seu e-mail ou fale com o administrador.', color='success')
                        rec_pwd_dialog.close()
                    except Exception as err:
                        rec_error.text = f'Erro: {err}'
                else:
                    ui.notify('Solicitação simulada com sucesso (modo offline)', color='warning')
                    rec_pwd_dialog.close()
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancelar', on_click=rec_pwd_dialog.close).props('flat color=grey')
                ui.button('Enviar', on_click=submit_recovery).props('unelevated color=amber-9 text-color=black')

    # Fundo do login
    with ui.column().classes('w-full h-screen items-center justify-center p-4 gap-4').style(
        'background: linear-gradient(135deg, #121212 0%, #1e1e2f 100%);'
    ):
        with ui.card().classes('w-full max-w-md no-shadow rounded-xl q-pa-lg').style(
            f'background: {theme.colors["bg_panel"]}; border: {theme.colors["border"]}; box-shadow: 0 10px 40px rgba(0,0,0,0.6) !important;'
        ):
            with ui.column().classes('w-full items-center gap-4'):
                
                # ── TOPO: LOGO E IDENTIFICAÇÃO ──
                ui.image(LOGO_BASE64).style('width: 180px; height: 180px; box-shadow: 0 0 35px rgba(0, 229, 255, 0.65); border-radius: 50%; border: 2px solid rgba(0, 229, 255, 0.4);').classes('drop-shadow-[0_0_20px_rgba(0,229,255,0.5)]')
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
                    
                    user = ui.input('E-mail ou Usuário', value=app.storage.user.get('last_username', '')).props('dark outlined w-full autocomplete=username name=username').classes('w-full text-sm')
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
                        
                        # Rate Limiting contra Brute-Force (A6)
                        from rate_limit import rate_limiter, get_client_ip
                        client_ip = get_client_ip()
                        key = f"login_attempt:{client_ip}"
                        if not rate_limiter.is_allowed(key, max_requests=5, window_seconds=600):
                            error_label.text = 'Muitas tentativas. Login bloqueado por 10 minutos.'
                            import log_acessos
                            log_acessos.log_access(f"Tentativa de login bloqueada (Brute-force)", "Autenticação", "BLOQUEADO")
                            return
                        
                        from database import get_db_connection, authenticate_user_supabase
                        db_conn = get_db_connection()
                        
                        if not db_conn:
                            error_label.text = 'Sem conexão com o Supabase. Verifique sua rede.'
                            return
                        
                        # Resolve o login para e-mail caso o usuário tenha inserido o username/nome de guerra
                        login_email = user.value.strip()
                        if '@' not in login_email:
                            try:
                                from database import get_service_db_connection
                                svc_db = get_service_db_connection()
                                if svc_db:
                                    # Busca no efetivo pelo nome_guerra (case-insensitive)
                                    res_ef = svc_db.table('efetivo').select('email').eq('nome_guerra', login_email.upper()).execute()
                                    if res_ef.data and res_ef.data[0].get('email'):
                                        login_email = res_ef.data[0]['email']
                                    else:
                                        # Tenta buscar pelo username em Users
                                        res_u = svc_db.table('Users').select('nome').eq('username', login_email.lower()).execute()
                                        if res_u.data:
                                            guerra = res_u.data[0]['nome']
                                            res_ef2 = svc_db.table('efetivo').select('email').eq('nome_guerra', guerra.upper()).execute()
                                            if res_ef2.data and res_ef2.data[0].get('email'):
                                                login_email = res_ef2.data[0]['email']
                            except Exception as lookup_err:
                                print(f"[LOGIN LOOKUP ERR] {lookup_err}")
                        
                        try:
                            auth_res = authenticate_user_supabase(login_email, pwd.value)
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
                                'email': login_email
                            }
                            app.storage.user['supabase_session'] = session_data
                            
                            role_user = str(profile.get('role', 'compel')).strip().lower()
                            target_path = '/siscomca_tv' if role_user in ('tv', 'tv_comcia') else '/'
                            app.storage.user['current_path'] = target_path
                            ui.notify(f'Bem-vindo, {profile.get("nome", user.value)}!', color='success')
                            
                            # Registrar no log SQLite real (A8)
                            import log_acessos
                            log_acessos.log_access("Login", "Autenticação", "SUCESSO")
                            
                            # Força redirecionamento físico de página via JS para o gerenciador de senhas do navegador salvar as credenciais
                            ui.run_javascript(f"window.location.href = '{target_path}'")
                        else:
                            # Fallback para autenticação local no banco efetivo (caso tenha sido criado sem Auth por rate limits)
                            from database import authenticate_user
                            local_user = authenticate_user(login_email, pwd.value)
                            if local_user:
                                profile = {
                                    'id': local_user.get('id') or local_user.get('telegram_id') or 'local-fallback',
                                    'username': local_user.get('email', '').split('@')[0] if local_user.get('email') else local_user.get('nome_guerra', 'militar'),
                                    'nome': local_user.get('nome_guerra', 'militar'),
                                    'role': local_user.get('role', 'compel')
                                }
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
                                    'email': login_email
                                }
                                app.storage.user['supabase_session'] = None
                                
                                role_user = str(profile.get('role', 'compel')).strip().lower()
                                target_path = '/siscomca_tv' if role_user in ('tv', 'tv_comcia') else '/'
                                app.storage.user['current_path'] = target_path
                                ui.notify(f'Bem-vindo (Autenticação Direta), {profile.get("nome", user.value)}!', color='success')
                                
                                import log_acessos
                                log_acessos.log_access("Login", "Autenticação Local", "SUCESSO")
                                ui.run_javascript(f"window.location.href = '{target_path}'")
                            else:
                                error_label.text = 'E-mail, usuário ou senha incorretos'
                                import log_acessos
                                log_acessos.log_access(f"Falha de Login: {user.value}", "Autenticação", "FALHA")
  
                    ui.button('🚀 Entrar no Sistema').props('type=submit unelevated color=amber-9 text-color=black w-full bold').classes('q-py-sm font-bold text-sm cyber-title w-full')
                    
                    with ui.row().classes('w-full justify-between items-center q-mt-xs'):
                        ui.button('📝 Solicitar acesso', on_click=reg_dialog.open).props('flat color=grey no-caps').classes('text-xs')
                        ui.button('🔑 Esqueci a senha', on_click=rec_pwd_dialog.open).props('flat color=grey no-caps').classes('text-xs')

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
# SEGURANÇA: Exige STORAGE_SECRET no ambiente para segurança de sessão
secret_env = os.environ.get('STORAGE_SECRET')
if not secret_env:
    raise RuntimeError(
        "A variável de ambiente STORAGE_SECRET é OBRIGATÓRIA para fins de segurança de sessão! "
        "Defina STORAGE_SECRET no seu .env com um segredo aleatório forte (ex: python -c \"import os; print(os.urandom(32).hex())\")."
    )

# Desativamos o 'reload' por padrão para rodar em Modo Produção super leve, veloz, estável e sem reinícios.
ui.run(
    title='SisCOMCA', 
    dark=True, 
    storage_secret=secret_env, 
    host=host_env,
    port=port_env,
    reload=False
)
