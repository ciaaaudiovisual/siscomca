from nicegui import app

_state = {}


def get_state(key: str, default=None):
    """Obtém estado persistente usando app.storage"""
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    return app.storage.user['app_state'].get(key, default)


def set_state(key: str, value):
    """Salva estado persistente"""
    if 'app_state' not in app.storage.user:
        app.storage.user['app_state'] = {}
    app.storage.user['app_state'][key] = value


def update_state(key: str, updates: dict):
    """Atualiza parte do estado"""
    current = get_state(key, {})
    if isinstance(current, dict):
        current.update(updates)
    else:
        current = updates
    set_state(key, current)
