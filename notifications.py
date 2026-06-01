from nicegui import ui, app
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
import json


def get_state(key: str, default=None):
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    return app.storage.user['app_state'].get(key, default)


def set_state(key: str, value):
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    app.storage.user['app_state'][key] = value


@dataclass
class Alert:
    id: int
    type: str  # info, warning, error, success
    title: str
    message: str
    created_at: str
    read: bool = False
    action_url: Optional[str] = None


ALERT_THRESHOLDS = {
    'pendencias_missao': 5,
    'efetivo_inativo': 3,
    'publicacoes_pendentes': 10,
}


def check_alerts():
    """Verifica condições e cria alertas automáticos"""
    alerts = []
    
    pendencias = get_state('kpis', {}).get('pendentes', 0)
    if pendencias >= ALERT_THRESHOLDS['pendencias_missao']:
        alerts.append(Alert(
            id=1,
            type='warning',
            title='Muitas Pendências',
            message=f'Você tem {pendencias} missões pendentes. Ação necessária!',
            created_at=datetime.now().isoformat()
        ))
    
    return alerts


def get_alerts() -> List[Alert]:
    return get_state('alerts', [])


def add_alert(alert: Alert):
    alerts = get_alerts()
    alerts.insert(0, alert)
    set_state('alerts', alerts[:50])


def mark_alert_read(alert_id: int):
    alerts = get_alerts()
    for a in alerts:
        if a.id == alert_id:
            a.read = True
    set_state('alerts', alerts)


def clear_alerts():
    set_state('alerts', [])


def send_broadcast(title: str, message: str, alert_type: str = 'info'):
    """Envia mensagem para todos os usuários conectados"""
    user_data = app.storage.user.get('user_data', {})
    autor = user_data.get('nome_guerra', 'Sistema')
    
    broadcast = {
        'id': int(datetime.now().timestamp()),
        'type': alert_type,
        'title': title,
        'message': message,
        'autor': autor,
        'created_at': datetime.now().isoformat(),
    }
    
    if 'broadcasts' not in app.storage.user:
        app.storage.user['broadcasts'] = []
    
    app.storage.user['broadcasts'].insert(0, broadcast)
    app.storage.user['broadcasts'] = app.storage.user['broadcasts'][:20]
    
    return True


def get_broadcasts() -> List[dict]:
    return app.storage.user.get('broadcasts', [])


def render_notification_bell():
    """Renderiza ícone de notificações com badge"""
    alerts = get_alerts()
    unread = [a for a in alerts if not a.read]
    count = len(unread)
    
    with ui.row().classes('relative-position'):
        ui.button(icon='notifications', on_click=lambda: show_notifications()).props('flat round dense color=white')
        
        if count > 0:
            ui.badge(str(count), color='red').props('floating')


def show_notifications():
    """Mostra painel de notificações"""
    alerts = get_alerts()
    
    with ui.dialog() as dialog, ui.card().classes('w-96').style('max-height: 500px'):
        ui.label('Notificações').classes('text-h6')
        
        with ui.scroll_area().classes('h-80 w-full'):
            if not alerts:
                ui.label('Nenhuma notificação').classes('text-grey italic')
            
            for alert in alerts:
                bg = 'bg-amber-9/10' if not alert.read else 'bg-transparent'
                with ui.card().classes(f'w-full q-mb-sm {bg}').props('flat'):
                    with ui.row().classes('items-start gap-2'):
                        icon = {'info': 'info', 'warning': 'warning', 'error': 'error', 'success': 'check_circle'}.get(alert.type, 'info')
                        color = {'info': 'blue', 'warning': 'orange', 'error': 'red', 'success': 'green'}.get(alert.type, 'blue')
                        ui.icon(icon, color=color)
                        
                        with ui.column().classes('gap-0'):
                            ui.label(alert.title).classes('text-body2 font-bold')
                            ui.label(alert.message).classes('text-caption text-grey')
                            ui.label(alert.created_at[:16]).classes('text-xs text-grey-6')
        
        with ui.row().classes('w-full justify-between'):
            ui.button('Limpar tudo', on_click=lambda: clear_all_notifications(dialog)).props('flat dense color=grey')
            ui.button('Fechar', on_click=dialog.close).props('flat dense')
    
    dialog.open()


def clear_all_notifications(dialog):
    clear_alerts()
    dialog.close()
    ui.notify('Notificações limpas', color='info')


def render_broadcast_banner():
    """Renderiza banner de broadcast ativo"""
    broadcasts = get_broadcasts()
    if broadcasts:
        latest = broadcasts[0]
        color = {'info': 'blue', 'warning': 'orange', 'error': 'red', 'success': 'green'}.get(latest.get('type', 'info'), 'blue')
        
        with ui.banner(icon='campaign', color=color).classes('q-mb-md'):
            with ui.row().classes('items-center justify-between w-full'):
                with ui.column().classes('gap-0'):
                    ui.label(latest.get('title', '')).classes('font-bold')
                    ui.label(latest.get('message', '')).classes('text-caption')
                ui.button(icon='close', on_click=lambda: dismiss_broadcast(latest['id'])).props('flat round dense')


def dismiss_broadcast(broadcast_id: int):
    broadcasts = get_broadcasts()
    broadcasts = [b for b in broadcasts if b.get('id') != broadcast_id]
    app.storage.user['broadcasts'] = broadcasts
    ui.navigate.to(app.storage.user.get('current_path', '/'))


def send_internal_message(to_user: str, subject: str, message: str):
    """Envia mensagem interna para outro usuário"""
    user_data = app.storage.user.get('user_data', {})
    autor = user_data.get('nome_guerra', 'Anonimo')
    
    msg = {
        'id': int(datetime.now().timestamp()),
        'from': autor,
        'to': to_user,
        'subject': subject,
        'message': message,
        'created_at': datetime.now().isoformat(),
        'read': False,
    }
    
    if 'messages' not in app.storage.user:
        app.storage.user['messages'] = []
    
    app.storage.user['messages'].insert(0, msg)
    ui.notify(f'Mensagem enviada para {to_user}', color='positive')


def get_my_messages() -> List[dict]:
    user_data = app.storage.user.get('user_data', {})
    my_name = user_data.get('nome_guerra', '')
    
    messages = app.storage.user.get('messages', [])
    return [m for m in messages if m.get('to') == my_name or m.get('to') == 'TODOS']


def render_messages_panel():
    """Painel de mensagens internas"""
    messages = get_my_messages()
    
    with ui.dialog() as dialog, ui.card().classes('w-full w-96'):
        ui.label('Mensagens Internas').classes('text-h6')
        
        with ui.scroll_area().classes('h-80 w-full'):
            if not messages:
                ui.label('Nenhuma mensagem').classes('text-grey italic')
            
            for msg in messages:
                bg = 'bg-blue-9/10' if not msg.get('read') else 'bg-transparent'
                with ui.card().classes(f'w-full q-mb-sm {bg}').props('flat'):
                    with ui.column().classes('gap-0'):
                        with ui.row().classes('justify-between w-full'):
                            ui.label(msg.get('subject', '')).classes('font-bold')
                            ui.label(msg.get('created_at', '')[:10]).classes('text-xs text-grey')
                        ui.label(f"De: {msg.get('from', '')}").classes('text-caption text-grey')
                        ui.label(msg.get('message', '')).classes('text-body2')
    
    return dialog
