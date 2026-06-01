from nicegui import ui, app
from datetime import datetime


def get_state(key: str, default=None):
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    return app.storage.user['app_state'].get(key, default)


def set_state(key: str, value):
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    app.storage.user['app_state'][key] = value


LOG_ACESSO_MOCK = [
    {'id': 1, 'usuario': 'Cap. Silva', 'acao': 'Login', 'modulo': 'Sistema', 'ip': '192.168.1.10', 'data': '20/02/2026 14:30', 'status': 'SUCESSO'},
    {'id': 2, 'usuario': 'Ten. Santos', 'acao': 'Visualização', 'modulo': 'Workflow', 'ip': '192.168.1.15', 'data': '20/02/2026 14:25', 'status': 'SUCESSO'},
    {'id': 3, 'usuario': 'Sgt. Oliveira', 'acao': 'Edição', 'modulo': 'Produção', 'ip': '192.168.1.20', 'data': '20/02/2026 14:20', 'status': 'SUCESSO'},
    {'id': 4, 'usuario': 'Cap. Admin', 'acao': 'Login', 'modulo': 'Sistema', 'ip': '192.168.1.10', 'data': '20/02/2026 14:15', 'status': 'FALHA'},
    {'id': 5, 'usuario': 'Maj. Rodrigues', 'acao': 'Download', 'modulo': 'Mídia Center', 'ip': '192.168.1.25', 'data': '20/02/2026 14:10', 'status': 'SUCESSO'},
    {'id': 6, 'usuario': 'Ten. Costa', 'acao': 'Publicação', 'modulo': 'Publicações', 'ip': '192.168.1.18', 'data': '20/02/2026 14:05', 'status': 'SUCESSO'},
    {'id': 7, 'usuario': 'Cap. Silva', 'acao': 'Aprovação', 'modulo': 'Workflow', 'ip': '192.168.1.10', 'data': '20/02/2026 14:00', 'status': 'SUCESSO'},
    {'id': 8, 'usuario': 'Sgt. Mendes', 'acao': 'Acesso Negado', 'modulo': 'Admin', 'ip': '192.168.1.30', 'data': '20/02/2026 13:55', 'status': 'BLOQUEADO'},
]


def log_access(acao: str, modulo: str, status: str = 'SUCESSO'):
    """Registra um acesso no log"""
    user_data = app.storage.user.get('user_data', {})
    usuario = user_data.get('nome_guerra', 'Anonimo')
    
    novo_log = {
        'id': int(datetime.now().timestamp()),
        'usuario': usuario,
        'acao': acao,
        'modulo': modulo,
        'ip': '192.168.1.X',  # Simplificado
        'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'status': status,
    }
    
    logs = get_state('log_acesso', [])
    logs.insert(0, novo_log)
    set_state('log_acesso', logs[:100])  # Mantém últimos 100


def render_page():
    logs = get_state('log_acesso', LOG_ACESSO_MOCK)
    
    with ui.column().classes('w-full h-screen q-pa-lg gap-6'):
        
        with ui.row().classes('w-full justify-between items-end'):
            ui.label('Log de Acessos').classes('text-h4 text-white')
            ui.button('Atualizar', icon='refresh', on_click=lambda: atualizar()).props('flat')
        
        # Estatísticas
        with ui.row().classes('gap-4'):
            with ui.card().props('flat').style('background: #1E1E1E; border: 1px solid #333; border-radius: 8px; padding: 16px'):
                with ui.column().classes('items-center gap-1'):
                    ui.icon('login', color='green', size='1.5rem')
                    ui.label('156').classes('text-h5 text-white font-bold')
                    ui.label('Acessos Hoje').classes('text-caption text-grey')
            
            with ui.card().props('flat').style('background: #1E1E1E; border: 1px solid #333; border-radius: 8px; padding: 16px'):
                with ui.column().classes('items-center gap-1'):
                    ui.icon('check_circle', color='blue', size='1.5rem')
                    ui.label('148').classes('text-h5 text-white font-bold')
                    ui.label('Sucesso').classes('text-caption text-grey')
            
            with ui.card().props('flat').style('background: #1E1E1E; border: 1px solid #333; border-radius: 8px; padding: 16px'):
                with ui.column().classes('items-center gap-1'):
                    ui.icon('error', color='red', size='1.5rem')
                    ui.label('5').classes('text-h5 text-white font-bold')
                    ui.label('Falhas').classes('text-caption text-grey')
            
            with ui.card().props('flat').style('background: #1E1E1E; border: 1px solid #333; border-radius: 8px; padding: 16px'):
                with ui.column().classes('items-center gap-1'):
                    ui.icon('block', color='orange', size='1.5rem')
                    ui.label('3').classes('text-h5 text-white font-bold')
                    ui.label('Bloqueados').classes('text-caption text-grey')
        
        # Filtros
        with ui.row().classes('gap-2'):
            ui.input(placeholder='Buscar usuário...').props('dark outlined dense').classes('w-48')
            ui.select(['Todos', 'Sistema', 'Workflow', 'Produção', 'Mídia Center', 'Admin'], value='Todos').props('dark dense').classes('w-40')
            ui.select(['Todos', 'SUCESSO', 'FALHA', 'BLOQUEADO'], value='Todos').props('dark dense').classes('w-32')
        
        # Tabela de logs
        with ui.card().classes('w-full no-shadow').style('background: #1E1E1E; border: 1px solid #333; border-radius: 8px'):
            with ui.row().classes('w-full q-pa-sm bg-black/30 text-grey text-caption font-bold'):
                ui.label('DATA/HORA').classes('w-1/6')
                ui.label('USUÁRIO').classes('w-1/6')
                ui.label('AÇÃO').classes('w-1/6')
                ui.label('MÓDULO').classes('w-1/6')
                ui.label('IP').classes('w-1/6')
                ui.label('STATUS').classes('w-1/6 text-center')
            
            for log in logs:
                status_colors = {
                    'SUCESSO': 'green',
                    'FALHA': 'red',
                    'BLOQUEADO': 'orange',
                }
                status_color = status_colors.get(log.get('status'), 'grey')
                
                with ui.row().classes('w-full q-pa-sm items-center border-b border-gray-800 hover:bg-white/5'):
                    ui.label(log['data']).classes('w-1/6 text-caption text-grey')
                    ui.label(log['usuario']).classes('w-1/6 text-body2 text-white')
                    ui.label(log['acao']).classes('w-1/6 text-caption')
                    ui.label(log['modulo']).classes('w-1/6 text-caption')
                    ui.label(log['ip']).classes('w-1/6 text-caption text-grey font-mono')
                    
                    with ui.column().classes('w-1/6 items-center'):
                        icon = {'SUCESSO': 'check_circle', 'FALHA': 'error', 'BLOQUEADO': 'block'}.get(log.get('status'), 'help')
                        ui.icon(icon, color=status_color)


def atualizar():
    ui.notify('Log atualizado!', color='info')
