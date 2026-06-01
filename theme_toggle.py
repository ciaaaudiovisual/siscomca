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


def get_theme() -> str:
    return app.storage.user.get('theme', 'dark')


def set_theme(theme: str):
    set_state('theme', theme)
    app.storage.user['theme'] = theme


def toggle_theme():
    current = get_theme()
    new = 'light' if current == 'dark' else 'dark'
    set_theme(new)
    return new


def apply_theme():
    theme = get_theme()
    
    if theme == 'light':
        ui.colors(
            primary='#D4AF37',
            secondary='#1E1E1E',
            accent='#FF9800',
            dark='#F5F5F5',
            positive='#4CAF50',
            negative='#CF6679'
        )
        ui.query('body').style('background-color: #F5F5F5')
    else:
        ui.colors(
            primary='#D4AF37',
            secondary='#FFFFFF',
            accent='#FF9800',
            dark='#121212',
            positive='#4CAF50',
            negative='#CF6679'
        )
        ui.query('body').style('background-color: #121212')


LIGHT_THEME = {
    'bg_app': '#F5F5F5',
    'bg_panel': '#FFFFFF',
    'bg_input': '#EEEEEE',
    'text_main': '#212121',
    'text_dim': '#757575',
    'border': '1px solid #E0E0E0',
}

DARK_THEME = {
    'bg_app': '#121212',
    'bg_panel': '#1E1E1E',
    'bg_input': '#2C2C2C',
    'text_main': '#E0E0E0',
    'text_dim': '#9E9E9E',
    'border': '1px solid #333',
}


def get_colors():
    theme = get_theme()
    return LIGHT_THEME if theme == 'light' else DARK_THEME


def render_theme_toggle():
    theme = get_theme()
    
    with ui.row().classes('items-center gap-2'):
        ui.icon('dark_mode' if theme == 'dark' else 'light_mode').classes('text-xl')
        
        switch = ui.switch('', value=(theme == 'dark'), on_change=lambda e: handle_theme_change(e.value))
        switch.props('color=amber')


def handle_theme_change(is_dark: bool):
    new_theme = 'dark' if is_dark else 'light'
    set_theme(new_theme)
    ui.notify(f'Tema alterado para {"Escuro" if is_dark else "Claro"}', color='positive')
    ui.navigate.to(app.storage.user.get('current_path', '/'))
