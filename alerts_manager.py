"""
ALERT MANAGER — SisCOMCA
Módulo dedicado a Alertas e Notificações em Tempo Real (WebSockets Broadcast).
Permite registrar sessões ativas (como o Modo TV) e disparar avisos visuais/sonoros imediatos.
Implementa o Scheduler em background para Sinos Navais e Alertas Customizados.
"""

import asyncio
import os
import json
from datetime import datetime, date
from typing import List, Callable, Dict, Any

# Caminho do arquivo de configuração local de som e agendamento
ALERTS_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_alerts.json")

DEFAULT_ALERTS_CONFIG = {
    "bell_enabled": True,
    "tv_alert_vocativo": "Atenção!",
    "sound_mappings": {
        "Registro de Ocorrência": "alert",
        "Novo Aviso": "info",
        "Aviso de Saúde": "warning",
        "Dispensa Médica": "warning",
        "Licença Médica": "warning",
        "Alta Médica": "success",
        "Escala de Serviço": "info",
        "Escala de Serviço Atualizada": "info",
        "Chamada Diária": "info",
        "Atraso Registrado": "info"
    },
    "message_templates": {
        "Registro de Ocorrência": "🚨 {message}",
        "Novo Aviso": "📢 {message}",
        "Aviso de Saúde": "🏥 {message}",
        "Dispensa Médica": "🩹 Dispensa: {message}",
        "Licença Médica": "📋 Licença: {message}",
        "Alta Médica": "✅ Alta Médica: {message}",
        "Escala de Serviço": "📅 {message}",
        "Escala de Serviço Atualizada": "🔄 {message}",
        "Chamada Diária": "🔔 Chamada: {message}",
        "Atraso Registrado": "⏰ Atraso: {message}"
    },
    "custom_alerts": []
}

def load_alerts_config() -> dict:
    """Carrega as configurações de som e agendamento de alertas a partir do Supabase ou local."""
    try:
        from database import get_bot_db_connection
        db_conn = get_bot_db_connection()
        if db_conn:
            res = db_conn.table('Config').select('valor').eq('chave', 'config_alerts_json').execute()
            if res.data:
                data = json.loads(res.data[0]['valor'])
                merged = DEFAULT_ALERTS_CONFIG.copy()
                merged.update(data)
                if "sound_mappings" in data:
                    merged["sound_mappings"] = {**DEFAULT_ALERTS_CONFIG["sound_mappings"], **data["sound_mappings"]}
                if "message_templates" in data:
                    merged["message_templates"] = {**DEFAULT_ALERTS_CONFIG["message_templates"], **data["message_templates"]}
                # Cache local
                try:
                    with open(ALERTS_CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(merged, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                return merged
    except Exception as e:
        print(f"[ALERTA] Erro ao carregar config_alerts.json do Supabase: {e}")

    try:
        if os.path.exists(ALERTS_CONFIG_PATH):
            with open(ALERTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_ALERTS_CONFIG.copy()
                merged.update(data)
                if "sound_mappings" in data:
                    merged["sound_mappings"] = {**DEFAULT_ALERTS_CONFIG["sound_mappings"], **data["sound_mappings"]}
                if "message_templates" in data:
                    merged["message_templates"] = {**DEFAULT_ALERTS_CONFIG["message_templates"], **data["message_templates"]}
                return merged
    except Exception as e:
        print(f"[ALERTA] Erro ao carregar config_alerts.json local: {e}")
    return DEFAULT_ALERTS_CONFIG.copy()

def save_alerts_config(config: dict):
    """Salva as configurações de som e agendamento de alertas localmente e no Supabase."""
    try:
        with open(ALERTS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ALERTA] Erro ao salvar config_alerts.json local: {e}")

    try:
        from database import get_bot_db_connection
        db_conn = get_bot_db_connection()
        if db_conn:
            item = {
                'chave': 'config_alerts_json',
                'valor': json.dumps(config, ensure_ascii=False)
            }
            db_conn.table('Config').upsert(item, on_conflict='chave').execute()
    except Exception as e:
        print(f"[ALERTA] Erro ao salvar config_alerts.json no Supabase: {e}")

class AlertsManager:
    # Dicionário de callbacks ativos das telas conectadas: client_id -> {'client': client_obj, 'callback': callback, 'voice': bool, 'sound': bool}
    _tv_callbacks: Dict[str, Any] = {}
    # Lista de callbacks de atualização genérica (ex: para o Dashboard)
    _refresh_callbacks: List[Callable[[], Any]] = []
    # Referência para o loop de eventos principal do NiceGUI
    _main_loop: Any = None

    @classmethod
    def register_refresh_callback(cls, callback: Callable[[], Any]):
        """Registra um callback genérico para atualização de dados em tempo real."""
        if callback not in cls._refresh_callbacks:
            cls._refresh_callbacks.append(callback)
            print(f"[ALERTA] Callback de atualização registrado. Total: {len(cls._refresh_callbacks)}")

    @classmethod
    def unregister_refresh_callback(cls, callback: Callable[[], Any]):
        """Remove o callback genérico de atualização."""
        if callback in cls._refresh_callbacks:
            cls._refresh_callbacks.remove(callback)
            print(f"[ALERTA] Callback de atualização desregistrado. Restantes: {len(cls._refresh_callbacks)}")
    
    # Controladores internos do Scheduler
    _last_triggered_bell_slot = None  # (hour, minute)
    _triggered_custom_alerts_today = {}  # {alert_id: date_str}
    _scheduler_started = False

    @classmethod
    def prune_dead_callbacks(cls):
        """Remove callbacks de clientes que foram DEFINITIVAMENTE destruídos pelo NiceGUI.
        
        IMPORTANTE: Não remove clientes em reconexão (has_socket_connection=False temporariamente)
        """
        import nicegui
        dead_ids = []
        for cid, entry in list(cls._tv_callbacks.items()):
            client = entry.get('client')
            if not client:
                # Sem referência ao client, pode remover
                dead_ids.append(cid)
                continue
            
            # Check 1: Se o cliente tem socket ativo, está vivo
            if hasattr(client, 'has_socket_connection') and client.has_socket_connection:
                continue
                
            # Check 2: Se está em Client.instances, está vivo
            if cid in nicegui.Client.instances:
                continue
                
            # Check 3: Se tem atributo 'connected' e está True, está vivo
            if hasattr(client, 'connected') and client.connected:
                continue
                
            # Só marca para remoção se DEFINITIVAMENTE não estiver conectado
            # Aguarda um pouco antes de remover para evitar race conditions de reconexão
            dead_ids.append(cid)
            print(f"[ALERTA] Client {cid} marcado para remoção (nenhum indicador de vida)")
        
        for cid in dead_ids:
            try:
                del cls._tv_callbacks[cid]
                print(f"[ALERTA] Removido callback morto de TV ({cid}). Restantes: {len(cls._tv_callbacks)}")
            except KeyError:
                pass

    @classmethod
    def register_tv_callback(cls, client: Any, callback: Callable[[str, str, str], Any]):
        """Registra a tela de TV (associada ao seu client NiceGUI) para receber alertas.
        
        Preserva preferências de som/voz se já estava registrada (reconexão).
        """
        # Prune APENAS se for o primero registro ou se houver muitos callbacks
        if len(cls._tv_callbacks) > 20:
            cls.prune_dead_callbacks()
        
        # Preserva preferências se já estava registrada (reconexão)
        old_prefs = cls._tv_callbacks.get(client.id, {})
        cls._tv_callbacks[client.id] = {
            'client': client,
            'callback': callback,
            'voice': old_prefs.get('voice', True),
            'sound': old_prefs.get('sound', True)
        }
        try:
            cls._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        print(f"[ALERTA] ✓ TV registrada/re-registrada ({client.id}). Total ativo: {len(cls._tv_callbacks)}")

    @classmethod
    def unregister_tv_callback(cls, client_id: str):
        """Remove a tela de TV do canal de alertas ao desconectar ou recarregar."""
        if client_id in cls._tv_callbacks:
            del cls._tv_callbacks[client_id]
            print(f"[ALERTA] ✗ TV desregistrada ({client_id}). Restantes: {len(cls._tv_callbacks)}")

    @classmethod
    def update_tv_preferences(cls, client_id: str, voice: bool = None, sound: bool = None):
        """Atualiza preferências de som e voz para um cliente de TV específico."""
        if client_id in cls._tv_callbacks:
            if voice is not None:
                cls._tv_callbacks[client_id]['voice'] = voice
            if sound is not None:
                cls._tv_callbacks[client_id]['sound'] = sound
            print(f"[ALERTA] Preferências da TV {client_id} atualizadas: voice={voice}, sound={sound}")

    @classmethod
    def calculate_naval_bell_strikes(cls, dt: datetime) -> int:
        """Calcula a quantidade de baladas de sino baseada no quarto naval customizado do SisCOMCA."""
        hour = dt.hour
        minute = dt.minute
        
        # Regra explícita do usuário: às 8h00 são duas dobradas (4 badaladas)
        if hour == 8 and minute == 0:
            return 4
            
        if minute == 0:
            cycle_hour = hour % 4
            if cycle_hour == 0:
                return 8
            else:
                return cycle_hour * 2
        else:
            # Meia hora (minuto >= 30)
            cycle_hour = hour % 4
            return cycle_hour * 2 + 1

    @classmethod
    def trigger_alert(cls, title: str, message: str, type_: str = 'info', extra_options: dict = None):
        """
        Dispara um alerta em tempo real para todas as telas ativas registradas.
        Mapeia os sons baseados no título e suporta toques de sino naval e mudo.
        """
        cls.prune_dead_callbacks()
        if not cls._tv_callbacks and not cls._refresh_callbacks:
            print("[ALERTA BROADCAST] Nenhum cliente conectado (TV ou Dashboard). Pulando.")
            return

        # Carrega configuração de alertas para mapear o som correto e aplicar template
        config = load_alerts_config()
        mapped_sound = config.get("sound_mappings", {}).get(title, type_)
        
        # Sobrescreve para silencioso se som estiver desativado nas opções do alerta
        if extra_options and not extra_options.get('sound_enabled', True):
            mapped_sound = "silent"

        templates = config.get("message_templates", {})
        if title in templates:
            template = templates[title]
            try:
                if "{message}" in template:
                    message = template.format(message=message)
                else:
                    message = f"{template} {message}"
            except Exception as e:
                print(f"[ALERTA] Erro ao aplicar template para {title}: {e}")

        try:
            print(f"[ALERTA BROADCAST] {title.upper()} - {message} (Sound: {mapped_sound})")
        except UnicodeEncodeError:
            safe_msg = message.encode('ascii', errors='replace').decode('ascii')
            print(f"[ALERTA BROADCAST] {title.upper()} - {safe_msg} (Sound: {mapped_sound})")
        
        async def process_and_dispatch():
            from ai_helper import rewrite_to_jarvis_alert, generate_elevenlabs_tts
            
            # Verifica se pelo menos um cliente ativo deseja voz
            any_voice_active = any(entry.get('voice', True) for entry in cls._tv_callbacks.values())
            
            # Bypassa a geração de voz totalmente se for Toque de Sino ou se o som for silencioso ou voz desativada nas opções do alerta
            voice_enabled = extra_options.get('voice_enabled', True) if extra_options else True
            is_silent = False
            if isinstance(mapped_sound, list):
                is_silent = all((item.get('som') if isinstance(item, dict) else str(item)) == 'silent' for item in mapped_sound)
            else:
                is_silent = (mapped_sound == 'silent')
                
            if any_voice_active and title != "Toque de Sino" and not is_silent and voice_enabled:
                try:
                    loop = asyncio.get_running_loop()
                    jarvis_text = await loop.run_in_executor(None, rewrite_to_jarvis_alert, title)
                except Exception as e:
                    print(f"[ALERTA] Erro ao reescrever com Jarvis: {e}")
                    jarvis_text = f"{title}."

                try:
                    loop = asyncio.get_running_loop()
                    jarvis_audio = await loop.run_in_executor(None, generate_elevenlabs_tts, jarvis_text)
                except Exception as e:
                    print(f"[ALERTA] Erro ao gerar áudio com ElevenLabs: {e}")
                    jarvis_audio = ""
            else:
                jarvis_text = f"{title}."
                jarvis_audio = ""

            # Envia notificação por Telegram
            tg_category = None
            title_upper = title.upper()
            if any(x in title_upper for x in ["AVISO DE SAÚDE", "AVISO DE SAUDE", "DISPENSA", "LICENÇA", "LICENCA", "ALTA MÉDICA", "ALTA MEDICA"]):
                tg_category = "saude"
            elif any(x in title_upper for x in ["NOVO AVISO", "LETREIRO"]):
                tg_category = "aviso"
            elif any(x in title_upper for x in ["ESCALA"]):
                tg_category = "escala"
            elif any(x in title_upper for x in ["REGISTRO DE OCORRÊNCIA", "REGISTRO DE OCORRENCIA", "ANOTAÇÃO", "ANOTACAO", "ATRASO", "CHAMADA"]):
                tg_category = "anotacao"
                
            if tg_category:
                try:
                    from notifications_manager import broadcast_notification
                    asyncio.create_task(broadcast_notification(f"🔔 **{title.upper()}**\n\n{message}", tg_category))
                except Exception as e_tg:
                    print(f"[ALERTA] Falha ao enviar broadcast Telegram para {tg_category}: {e_tg}")

            # Faz cópia segura dos callbacks ativos e repassa o som mapeado
            active_entries = list(cls._tv_callbacks.values())
            for entry in active_entries:
                client = entry['client']
                cb = entry['callback']
                try:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(cb(title, message, mapped_sound, jarvis_text, jarvis_audio, extra_options))
                    else:
                        cb(title, message, mapped_sound, jarvis_text, jarvis_audio, extra_options)
                except Exception as e:
                    print(f"[ALERTA] Falha ao notificar tela ({client.id}): {e}")

            # Notifica os callbacks de atualização genérica (ex: Dashboard)
            for cb in list(cls._refresh_callbacks):
                try:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(cb())
                    else:
                        cb()
                except Exception as e:
                    print(f"[ALERTA] Falha ao executar callback de atualização: {e}")

        # Agenda a execução no loop de eventos do asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(process_and_dispatch())
        except RuntimeError:
            if cls._main_loop and cls._main_loop.is_running():
                print(f"[ALERTA] Fora de loop ativo. Agendando thread-safe no loop principal ({cls._main_loop})")
                asyncio.run_coroutine_threadsafe(process_and_dispatch(), cls._main_loop)
            else:
                print(f"[ALERTA] Fora de loop ativo e sem loop principal. Executando fallback síncrono.")
                fallback_text = f"{title}."
                active_entries = list(cls._tv_callbacks.values())
                for entry in active_entries:
                    client = entry['client']
                    cb = entry['callback']
                    try:
                        if not asyncio.iscoroutinefunction(cb):
                            cb(title, message, mapped_sound, fallback_text, "")
                    except Exception:
                        pass
                
                # Notifica os callbacks de atualização genérica
                for cb in list(cls._refresh_callbacks):
                    try:
                        if not asyncio.iscoroutinefunction(cb):
                            cb()
                    except Exception:
                        pass

    @classmethod
    def start_alerts_scheduler(cls):
        """Inicia o loop assíncrono do scheduler de sinos e alertas em segundo plano."""
        if cls._scheduler_started:
            return
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(cls._scheduler_loop())
            cls._scheduler_started = True
            print("[ALERTA] Scheduler de Sinos Navais e Alertas Horários ativo!")
        except RuntimeError:
            # Se for carregado em importação síncrona inicial, NiceGUI ainda não tem loop ativo.
            # Registramos para o NiceGUI startup
            from nicegui import app
            app.on_startup(cls.start_alerts_scheduler)
            print("[ALERTA] Scheduler registrado para app.on_startup.")

    @classmethod
    async def _scheduler_loop(cls):
        """Loop infinito de verificação temporal executado em background."""
        print("[ALERTA] Loop de background do Scheduler iniciado.")
        while True:
            try:
                from datetime import timezone, timedelta
                tz_gmt3 = timezone(timedelta(hours=-3))
                now = datetime.now(tz_gmt3)
                today_str = now.strftime("%Y-%m-%d")
                hour_min = now.strftime("%H:%M")
                
                # Alertas Agendados Personalizados (Sinos e Sinais Manuais)
                config = load_alerts_config()
                custom_alerts = config.get("custom_alerts", [])
                for alert in custom_alerts:
                    if alert.get("enabled", True) and alert.get("time") == hour_min:
                        alert_id = alert.get("id")
                        if cls._triggered_custom_alerts_today.get(alert_id) != today_str:
                            print(f"[SCHEDULER] Disparando alerta agendado [{alert_id}]: {alert['title']}")
                            cls.trigger_alert(
                                alert.get("title", "Aviso"),
                                alert.get("message", ""),
                                alert.get("sound", "info"),
                                extra_options={
                                    'visual_alert': alert.get('visual_alert', True),
                                    'voice_enabled': alert.get('voice_enabled', True),
                                    'sound_enabled': alert.get('sound_enabled', True)
                                }
                            )
                            cls._triggered_custom_alerts_today[alert_id] = today_str
            except Exception as e:
                print(f"[SCHEDULER ERRO] Falha no loop principal: {e}")
                
            # Verifica a cada 20 segundos
            await asyncio.sleep(20)
