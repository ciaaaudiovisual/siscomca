import os
import json
import asyncio
import threading
from database import get_bot_db_connection as get_db_connection

PREFERENCES_FILE = r'x:\PROGRAMACAO\COMSOC_IA\telegram_preferences.json'
file_lock = threading.Lock()

DEFAULT_PREFERENCES = {
    "silence_all": False,
    "notify_new_user": True,
    "notify_aviso": True,
    "notify_saude": True,
    "notify_escala": True,
    "notify_anotacao": True
}

def load_preferences() -> dict:
    with file_lock:
        if not os.path.exists(PREFERENCES_FILE):
            return {}
        try:
            with open(PREFERENCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[PREFERENCES] Erro ao carregar preferências: {e}", flush=True)
            return {}

def save_preferences(prefs: dict):
    with file_lock:
        try:
            with open(PREFERENCES_FILE, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[PREFERENCES] Erro ao salvar preferências: {e}", flush=True)

def get_user_preferences(user_id: str) -> dict:
    prefs = load_preferences()
    return prefs.get(str(user_id), DEFAULT_PREFERENCES.copy())

def save_user_preferences(user_id: str, user_prefs: dict):
    prefs = load_preferences()
    prefs[str(user_id)] = user_prefs
    save_preferences(prefs)

def check_notification_enabled(user_id: str, notification_type: str) -> bool:
    """Verifica se o usuário habilitou o tipo de notificação específica no Telegram e não está silenciado."""
    user_prefs = get_user_preferences(user_id)
    if user_prefs.get("silence_all", False):
        return False
    
    pref_key = f"notify_{notification_type}"
    return user_prefs.get(pref_key, True)

async def _send_msg_safe(bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
        print(f"[NOTIFY] Mensagem enviada para o chat {chat_id}", flush=True)
    except Exception as e:
        print(f"[NOTIFY] Erro ao enviar mensagem para {chat_id}: {e}", flush=True)

async def send_notification_to_user(telegram_id: str, text: str):
    """Envia uma mensagem privada para um usuário específico se o bot estiver rodando."""
    import telegram_bot
    bot = telegram_bot.bot
    if not bot:
        token = telegram_bot.get_bot_token()
        if not token or os.getenv("DISABLE_TELEGRAM_BOT") == "True":
            return
        try:
            from telebot.async_telebot import AsyncTeleBot
            bot = AsyncTeleBot(token)
        except Exception:
            return
            
    try:
        await _send_msg_safe(bot, int(telegram_id), text)
    except Exception as e:
        print(f"[NOTIFY] Falha ao enviar para {telegram_id}: {e}", flush=True)

async def broadcast_notification(text: str, notification_type: str, role_required: str = None, specific_user_id: str = None):
    """Envia notificação para usuários autorizados baseando-se em preferências."""
    import telegram_bot
    bot = telegram_bot.bot
    if not bot:
        token = telegram_bot.get_bot_token()
        if not token or os.getenv("DISABLE_TELEGRAM_BOT") == "True":
            return
        try:
            from telebot.async_telebot import AsyncTeleBot
            bot = AsyncTeleBot(token)
        except Exception:
            return
            
    conn = get_db_connection()
    if not conn:
        print("[NOTIFY] Sem banco de dados para transmissão de notificação.", flush=True)
        return
        
    try:
        query = conn.table('Users').select('*')
        if role_required:
            query = query.eq('role', role_required)
        if specific_user_id:
            query = query.eq('id', specific_user_id)
        res = query.execute()
        
        if res.data:
            tasks = []
            for user in res.data:
                u_id = user.get('id')
                tg_id = user.get('telegram_id')
                if not tg_id or not str(tg_id).strip():
                    continue
                
                # Checa as preferências
                if check_notification_enabled(u_id, notification_type):
                    tasks.append(_send_msg_safe(bot, int(tg_id), text))
            
            if tasks:
                await asyncio.gather(*tasks)
    except Exception as e:
        print(f"[NOTIFY] Erro ao transmitir broadcast {notification_type}: {e}", flush=True)

def notify_telegram(text: str, notification_type: str, role_required: str = None, specific_user_id: str = None):
    """Sincronamente despacha o envio de notificação."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast_notification(text, notification_type, role_required, specific_user_id))
        else:
            loop.run_until_complete(broadcast_notification(text, notification_type, role_required, specific_user_id))
    except Exception:
        try:
            asyncio.run(broadcast_notification(text, notification_type, role_required, specific_user_id))
        except Exception as e:
            print(f"[NOTIFY] Falha ao despachar notificação de Telegram: {e}", flush=True)
