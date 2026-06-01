from nicegui import app
from enum import Enum
from functools import wraps
from typing import List, Optional


class Role(Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    OPERADOR = "operador"
    VISITANTE = "visitante"


PERMISSIONS = {
    Role.ADMIN: [
        "dashboard.view",
        "workflow.create", "workflow.edit", "workflow.delete", "workflow.approve",
        "producao.create", "producao.edit", "producao.delete", "producao.publish",
        "midia.upload", "midia.delete",
        "efetivo.create", "efetivo.edit", "efetivo.delete",
        "admin.panel",
        "config.view", "config.edit",
        "reports.export",
    ],
    Role.SUPERVISOR: [
        "dashboard.view",
        "workflow.create", "workflow.edit", "workflow.approve",
        "producao.create", "producao.edit", "producao.publish",
        "midia.upload",
        "efetivo.view", "efetivo.edit",
        "reports.view",
    ],
    Role.OPERADOR: [
        "dashboard.view",
        "workflow.create", "workflow.edit",
        "producao.create", "producao.edit",
        "midia.upload",
    ],
    Role.VISITANTE: [
        "dashboard.view",
        "workflow.view",
        "producao.view",
        "midia.view",
    ],
}


def get_user_role() -> Role:
    """Obtém a role do usuário atual"""
    user_data = app.storage.user.get('user_data', {})
    role_str = user_data.get('permissao', '').upper()
    
    try:
        return Role(role_str)
    except:
        return Role.VISITANTE


def has_permission(permission: str) -> bool:
    """Verifica se o usuário atual tem uma permissão"""
    role = get_user_role()
    return permission in PERMISSIONS.get(role, [])


def require_permission(permission: str):
    """Decorator para proteger rotas por permissão"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                return {"error": "Acesso negado", "permission": permission}, 403
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_user_permissions() -> List[str]:
    """Retorna lista de permissões do usuário atual"""
    role = get_user_role()
    return PERMISSIONS.get(role, [])


def can_access(module: str, action: str = 'view') -> bool:
    """Verifica acesso a um módulo específico"""
    permission = f"{module}.{action}"
    return has_permission(permission)


def log_audit(action: str, details: dict = None):
    """Registra ação no log de auditoria"""
    from datetime import datetime
    
    user_data = app.storage.user.get('user_data', {})
    
    audit_entry = {
        'timestamp': datetime.now().isoformat(),
        'user': user_data.get('nome_guerra', 'Anonimo'),
        'user_id': user_data.get('telegram_id', 0),
        'role': get_user_role().value,
        'action': action,
        'details': details or {},
    }
    
    if 'audit_log' not in app.storage.user:
        app.storage.user['audit_log'] = []
    
    app.storage.user['audit_log'].append(audit_entry)
    print(f"📋 AUDIT: {audit_entry['user']} - {action}")


def get_audit_log(limit: int = 50) -> List[dict]:
    """Retorna log de auditoria"""
    return app.storage.user.get('audit_log', [])[-limit:]


def check_session_timeout(timeout_minutes: int = 60) -> bool:
    """Verifica se a sessão expirou"""
    last_activity = app.storage.user.get('last_activity')
    
    if not last_activity:
        return False
    
    from datetime import datetime, timedelta
    
    try:
        last = datetime.fromisoformat(last_activity)
        now = datetime.now()
        
        if (now - last).total_seconds() > timeout_minutes * 60:
            return True  # Expired
        return False
    except:
        return False


def update_activity():
    """Atualiza timestamp de última atividade"""
    from datetime import datetime
    app.storage.user['last_activity'] = datetime.now().isoformat()


def logout_session():
    """ Faz logout e limpa sessão"""
    app.storage.user.clear()
