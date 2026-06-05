from nicegui import ui, app
import theme
from database import get_db_connection
from datetime import datetime

THEME = theme.colors
db = get_db_connection()


def get_state(key: str, default=None):
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    return app.storage.user['app_state'].get(key, default)


def set_state(key: str, value):
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    app.storage.user['app_state'][key] = value


state = {
    'users': [],
    'logs': [],
    'loading': False
}

def fetch_data():
    """Busca dados reais da tabela efetivo"""
    if not db:
        state['users'] = []
        state['logs'] = []
        return

    try:
        state['loading'] = True
        
        res = db.table('efetivo').select('*').order('nome_guerra').execute()
        state['users'] = res.data

        state['logs'] = sorted(state['users'], key=lambda x: x.get('created_at', ''), reverse=True)[:5]
        
        set_state('admin_users', state['users'])
        set_state('admin_logs', state['logs'])
        
    except Exception as e:
        ui.notify(f"Erro ao carregar efetivo: {e}", color='negative')
        state['users'] = []
        state['logs'] = []
    finally:
        state['loading'] = False

def update_user(id, field, value):
    """Atualiza um campo específico do usuário com restrições de segurança"""
    if not db: return
    
    # SEGURANÇA: Verificação de autorização server-side
    user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
    if user_role not in ('ADMIN', 'SUPERVISOR'):
        ui.notify("⛔ Operação não autorizada. Apenas administradores ou supervisores.", color='negative')
        return
        
    # SEGURANÇA: Whitelist de campos permitidos
    if field not in ('permissao', 'status'):
        ui.notify("⛔ Alteração de campo não permitida.", color='negative')
        return
        
    try:
        db.table('efetivo').update({field: value}).eq('id', id).execute()
        ui.notify(f"Usuário atualizado: {value}", color='positive')
        # Recarrega a página para atualizar a tabela
        ui.navigate.to('/admin')
    except Exception as e:
        ui.notify(f"Erro ao atualizar: {e}", color='negative')

def delete_user(id):
    """Remove um usuário do sistema com restrições de segurança"""
    if not db: return
    
    # SEGURANÇA: Apenas administradores reais podem excluir usuários
    user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
    if user_role != 'ADMIN':
        ui.notify("⛔ Operação não autorizada. Apenas administradores podem remover usuários.", color='negative')
        return
        
    try:
        db.table('efetivo').delete().eq('id', id).execute()
        ui.notify("Usuário removido.", color='warning')
        ui.navigate.to('/admin')
    except Exception as e:
        ui.notify(f"Erro: {e}", color='negative')

def add_user_dialog():
    """Dialog para adicionar militar manualmente"""
    nome_ref = {'value': ''}
    id_ref = {'value': ''}

    with ui.dialog() as dialog, ui.card().classes('q-pa-md').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
        ui.label('Cadastrar Novo Militar').classes('text-h6 text-white')
        
        ui.input('Nome de Guerra').bind_value(nome_ref, 'value').props('dark outlined dense').classes('w-full')
        ui.input('Telegram ID (Numérico)').bind_value(id_ref, 'value').props('dark outlined dense').classes('w-full')
        
        def save():
            if not nome_ref['value'] or not id_ref['value']:
                ui.notify('Preencha todos os campos', color='warning')
                return
            
            try:
                db.table('efetivo').insert({
                    'nome_guerra': nome_ref['value'].upper(),
                    'telegram_id': id_ref['value'],
                    'status': 'ATIVO',
                    'permissao': 'USUARIO'
                }).execute()
                ui.notify('Militar cadastrado!', color='positive')
                dialog.close()
                ui.navigate.to('/admin')
            except Exception as e:
                ui.notify(f"Erro: {e}", color='negative')

        with ui.row().classes('w-full justify-end q-mt-md'):
            ui.button('Cancelar', on_click=dialog.close).props('flat color=grey')
            ui.button('Cadastrar', on_click=save).props('unelevated color=primary text-color=black')
    
    dialog.open()

# --- COMPONENTES VISUAIS ---

def render_page():
    if get_state('admin_loaded') is None:
        set_state('admin_loaded', True)
        if not db:
            state['users'] = [
                {'id': 1, 'nome_guerra': 'Cap. Silva', 'telegram_id': '123456', 'status': 'ATIVO', 'permissao': 'ADMIN'},
                {'id': 2, 'nome_guerra': 'Ten. Santos', 'telegram_id': '234567', 'status': 'ATIVO', 'permissao': 'SUPERVISOR'},
                {'id': 3, 'nome_guerra': 'Sgt. Oliveira', 'telegram_id': '345678', 'status': 'ATIVO', 'permissao': 'USUARIO'},
            ]
            state['logs'] = state['users'][:3]
            set_state('admin_users', state['users'])
            set_state('admin_logs', state['logs'])
        else:
            fetch_data()
    else:
        state['users'] = get_state('admin_users', [])
        state['logs'] = get_state('admin_logs', [])

    with ui.column().classes('w-full h-screen q-pa-lg gap-6'):
        
        # --- HEADER ---
        with ui.row().classes('w-full justify-between items-end'):
            theme.section_header('Gestão de Efetivo', 'Controle de Acesso e Permissões')
            
            # Botão Adicionar
            ui.button('Cadastrar Militar', icon='person_add', on_click=add_user_dialog).props('unelevated no-caps color=primary text-color=black')

        # --- CONTEÚDO DIVIDIDO (70% Tabela / 30% Logs) ---
        with ui.row().classes('w-full col-grow gap-6 no-wrap wrap-mobile'):
            
            # --- ÁREA 1: TABELA DE USUÁRIOS ---
            with ui.card().classes('col-grow no-shadow column min-w-[300px]').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
                
                # Cabeçalho da Tabela
                with ui.row().classes('w-full q-pa-sm items-center justify-between border-b border-gray-800'):
                    ui.label(f"Total: {len(state['users'])} Militares").classes('text-caption text-grey')
                    ui.button(icon='refresh', on_click=lambda: ui.navigate.to('/admin')).props('flat round dense color=grey')

                # Tabela Customizada (Usando ui.row para cada item pois permite mais controle que ui.table puro)
                with ui.scroll_area().classes('w-full col-grow'):
                    # Header
                    with ui.row().classes('w-full q-pa-sm bg-black/20 text-grey text-caption font-bold'):
                        ui.label('MILITAR').classes('w-1/4')
                        ui.label('TELEGRAM ID').classes('w-1/4')
                        ui.label('PERMISSÃO').classes('w-1/6 text-center')
                        ui.label('STATUS').classes('w-1/6 text-center')
                        ui.label('AÇÕES').classes('w-1/6 text-right')
                    
                    # Rows
                    if not state['users']:
                        ui.label('Nenhum usuário encontrado.').classes('q-pa-md text-grey italic')

                    for user in state['users']:
                        bg_hover = 'hover:bg-white/5 transition-colors'
                        with ui.row().classes(f'w-full q-pa-sm items-center border-b border-gray-800 {bg_hover}'):
                            
                            # Nome
                            with ui.row().classes('w-1/4 items-center gap-2'):
                                ui.avatar(icon='person', color='grey-8', text_color='white').props('size=sm')
                                ui.label(user.get('nome_guerra', 'Desconhecido')).classes('text-white font-medium')
                            
                            # ID
                            ui.label(user.get('telegram_id', '-')).classes('w-1/4 text-grey font-mono text-xs')
                            
                            # Permissão (Dropdown)
                            with ui.row().classes('w-1/6 justify-center'):
                                perm_color = '#D4AF37' if user['permissao'] == 'ADMIN' else ('#2196F3' if user['permissao'] == 'SUPERVISOR' else 'grey')
                                ui.select(['ADMIN', 'SUPERVISOR', 'USUARIO'], 
                                          value=user['permissao'], 
                                          on_change=lambda e, u=user: update_user(u['id'], 'permissao', e.value)).props('dark dense borderless options-dense').classes('text-xs font-bold').style(f'color: {perm_color}; width: 100px')

                            # Status (Chip Clicável)
                            with ui.row().classes('w-1/6 justify-center'):
                                is_active = user.get('status') == 'ATIVO'
                                color = 'green' if is_active else ('orange' if user.get('status') == 'PENDENTE' else 'red')
                                icon = 'check_circle' if is_active else 'block'
                                
                                new_status = 'INATIVO' if is_active else 'ATIVO'
                                user_id = user.get('id', 0)
                                ui.chip(user.get('status', 'N/A'), icon=icon, on_click=lambda u=user, s=new_status: update_user(u.get('id', 0), 'status', s)).props(f'dense outline color={color} clickable')

                            # Ações
                            with ui.row().classes('w-1/6 justify-end'):
                                user_id = user.get('id', 0)
                                ui.button(icon='delete', on_click=lambda u=user: delete_user(u.get('id', 0))).props('flat dense size=sm color=red')

            # --- ÁREA 2: AUDITORIA / LOGS (Lateral) ---
            with ui.column().classes('w-full md:w-1/3 gap-4'):
                
                # Card de Logs Recentes (Baseado em novos cadastros)
                with ui.card().classes('w-full col-grow no-shadow q-pa-md scroll').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
                    with ui.row().classes('items-center gap-2 q-mb-md'):
                        ui.icon('history', color='grey-5')
                        ui.label('Últimos Cadastros').classes('text-weight-bold text-grey-5')

                    with ui.list().props('dark dense separator'):
                        if not state['logs']:
                            ui.label('Sem registros recentes.').classes('text-grey italic text-xs')
                        
                        for log in state['logs']:
                            with ui.item():
                                with ui.item_section().props('side'):
                                    # Data formatada
                                    dt = log.get('created_at', '')[:10]
                                    ui.label(dt).classes('text-xs text-amber-9 font-mono')
                                
                                with ui.item_section():
                                    ui.label(f"Novo usuário: {log.get('nome_guerra')}").classes('text-caption text-grey-3')
                                    ui.label(f"ID: {log.get('telegram_id')}").style('font-size: 0.6rem; color: #666')

                # Card de Estatísticas
                count_ativos = sum(1 for u in state['users'] if u['status'] == 'ATIVO')
                count_admins = sum(1 for u in state['users'] if u['permissao'] == 'ADMIN')

                with ui.card().classes('w-full no-shadow q-pa-md').style(f'background: {THEME["bg_input"]}; border: {THEME["border"]}'):
                    ui.label('Resumo Operacional').classes('text-caption text-grey q-mb-sm')
                    with ui.row().classes('justify-between'):
                        stat_item('Total', str(len(state['users'])))
                        stat_item('Ativos', str(count_ativos))
                        stat_item('Admins', str(count_admins))

def stat_item(label, value):
    with ui.column().classes('items-center'):
        ui.label(value).classes('text-h6 text-white text-weight-bold')
        ui.label(label).classes('text-xs text-grey')