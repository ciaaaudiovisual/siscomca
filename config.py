from nicegui import ui, app
import theme
import os
from database import get_db_connection, SUPABASE_URL, get_bot_db_connection as get_admin_db_connection
from services import data_service
from datetime import date

# Cores do tema
THEME = theme.colors

# Configurações padrão
DEFAULT_CONFIGS = {
    'linha_base_conceito': '8.5',
    'impacto_max_acoes': '1.5',
    'peso_academico': '1.0',
    'fator_adaptacao': '0.25',
    'periodo_adaptacao_inicio': '2026-02-01',
    'periodo_adaptacao_fim': '2026-02-28',
    'tempo_polling_tv': '300',
    'cabecalho_tv_title': 'SITUAÇÃO CONSOLIDADA DO CORPO DE ALUNOS',
    'cabecalho_tv_subtitle': 'CORPO DE ALUNOS • COMANDO TÁTICO',
    'cabecalho_tv_sunset_time': '17:48',
    'cargos_escala_lista': 'INSPETOR DO DIA, SUPERVISOR, AJOSCA, OSCA, OFICIAL DE SERVIÇO, ENFERMEIRO DE SERVIÇO',
    'codigo_desbloqueio_tv': '1234',
    'tempo_alerta_tv': '10',
    'telegram_bot_token': '',
    'tts_engine': 'basic',
    'elevenlabs_api_key': '',
    'elevenlabs_voice_id': 'N2lVS1w4EtoT3dr4eOWO',
    'tts_piper_path': 'piper.exe',
    'tts_piper_voice': 'pt_BR-fabricio-medium'
}

def render_page():
    def testar_som(som_key: str):
        """Executa a síntese de som diretamente no navegador do operador atual usando Web Audio API."""
        if som_key == 'silent':
            ui.notify('Silencioso ativado para este som.', color='warning')
            return
            
        supabase_base_url = (SUPABASE_URL.rstrip('/') if SUPABASE_URL else "")
        js_code = f"""
        try {{
            let ctx = window.globalAudioContext;
            if (!ctx) {{
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (AudioContext) {{
                    ctx = new AudioContext();
                    window.globalAudioContext = ctx;
                }}
            }}
            
            function playDefaultSynthesized(type) {{
                if (!ctx) return;
                if (type === 'submarine_sonar') {{
                    let now = ctx.currentTime;
                    let osc = ctx.createOscillator();
                    let gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(800, now);
                    osc.frequency.exponentialRampToValueAtTime(850, now + 0.15);
                    
                    gain.gain.setValueAtTime(0, now);
                    gain.gain.linearRampToValueAtTime(0.4, now + 0.005);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 1.8);
                    
                    osc.start(now);
                    osc.stop(now + 2.0);
                    
                    let echoOsc = ctx.createOscillator();
                    let echoGain = ctx.createGain();
                    echoOsc.connect(echoGain);
                    echoGain.connect(ctx.destination);
                    
                    echoOsc.type = 'sine';
                    echoOsc.frequency.setValueAtTime(810, now + 0.8);
                    echoOsc.frequency.exponentialRampToValueAtTime(830, now + 0.95);
                    
                    echoGain.gain.setValueAtTime(0, now + 0.8);
                    echoGain.gain.linearRampToValueAtTime(0.08, now + 0.805);
                    echoGain.gain.exponentialRampToValueAtTime(0.0001, now + 2.0);
                    
                    echoOsc.start(now + 0.8);
                    echoOsc.stop(now + 2.2);
                }} else if (type === 'morse_sos') {{
                    let now = ctx.currentTime;
                    const toneFreq = 800;
                    const dot = 0.08;
                    const dash = 0.24;
                    
                    let osc = ctx.createOscillator();
                    let gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(toneFreq, now);
                    gain.gain.setValueAtTime(0, now);
                    
                    function scheduleTone(start, duration) {{
                        gain.gain.setValueAtTime(0, now + start);
                        gain.gain.linearRampToValueAtTime(0.2, now + start + 0.005);
                        gain.gain.setValueAtTime(0.2, now + start + duration - 0.005);
                        gain.gain.linearRampToValueAtTime(0, now + start + duration);
                    }}
                    
                    scheduleTone(0.0, dot);
                    scheduleTone(0.16, dot);
                    scheduleTone(0.32, dot);
                    
                    scheduleTone(0.56, dash);
                    scheduleTone(0.88, dash);
                    scheduleTone(1.20, dash);
                    
                    scheduleTone(1.52, dot);
                    scheduleTone(1.68, dot);
                    scheduleTone(1.84, dot);
                    
                    osc.start(now);
                    osc.stop(now + 2.1);
                }} else if (type === 'naval_horn') {{
                    let now = ctx.currentTime;
                    const fundamental = 72;
                    const oscillators = [fundamental, fundamental * 1.5, fundamental * 2.0, fundamental * 2.5];
                    const gains = [0.4, 0.25, 0.15, 0.08];
                    const detunes = [0, 1.2, -0.8, 0.5];
                    
                    let mainGain = ctx.createGain();
                    let filter = ctx.createBiquadFilter();
                    
                    filter.type = 'lowpass';
                    filter.frequency.setValueAtTime(250, now);
                    filter.Q.setValueAtTime(2, now);
                    
                    mainGain.connect(filter);
                    filter.connect(ctx.destination);
                    
                    mainGain.gain.setValueAtTime(0, now);
                    mainGain.gain.linearRampToValueAtTime(0.5, now + 0.25);
                    mainGain.gain.setValueAtTime(0.5, now + 1.6);
                    mainGain.gain.exponentialRampToValueAtTime(0.001, now + 2.4);
                    
                    oscillators.forEach((freq, idx) => {{
                        let osc = ctx.createOscillator();
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(freq + detunes[idx], now);
                        
                        let oscGain = ctx.createGain();
                        oscGain.gain.setValueAtTime(gains[idx], now);
                        
                        osc.connect(oscGain);
                        oscGain.connect(mainGain);
                        
                        osc.start(now);
                        osc.stop(now + 2.5);
                    }});
                }} else if (type === 'success') {{
                    let osc = ctx.createOscillator();
                    let gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(523.25, ctx.currentTime);
                    gain.gain.setValueAtTime(0.3, ctx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                    osc.start(ctx.currentTime);
                    
                    let osc2 = ctx.createOscillator();
                    let gain2 = ctx.createGain();
                    osc2.connect(gain2);
                    gain2.connect(ctx.destination);
                    osc2.type = 'sine';
                    osc2.frequency.setValueAtTime(659.25, ctx.currentTime + 0.1);
                    gain2.gain.setValueAtTime(0.3, ctx.currentTime + 0.1);
                    gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
                    osc2.start(ctx.currentTime + 0.1);
                    
                    osc.stop(ctx.currentTime + 0.2);
                    osc2.stop(ctx.currentTime + 0.4);
                }} else if (type === 'warning') {{
                    let osc1 = ctx.createOscillator();
                    let gain1 = ctx.createGain();
                    osc1.connect(gain1);
                    gain1.connect(ctx.destination);
                    osc1.type = 'sine';
                    osc1.frequency.setValueAtTime(440, ctx.currentTime);
                    gain1.gain.setValueAtTime(0.2, ctx.currentTime);
                    gain1.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                    osc1.start(ctx.currentTime);
                    osc1.stop(ctx.currentTime + 0.2);

                    let osc2 = ctx.createOscillator();
                    let gain2 = ctx.createGain();
                    osc2.connect(gain2);
                    gain2.connect(ctx.destination);
                    osc2.type = 'sine';
                    osc2.frequency.setValueAtTime(440, ctx.currentTime + 0.15);
                    gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.15);
                    gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                    osc2.start(ctx.currentTime + 0.15);
                    osc2.stop(ctx.currentTime + 0.35);
                }} else if (type === 'alert') {{
                    let osc = ctx.createOscillator();
                    let gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(150, ctx.currentTime);
                    
                    gain.gain.setValueAtTime(0.4, ctx.currentTime);
                    gain.gain.setValueAtTime(0, ctx.currentTime + 0.15);
                    gain.gain.setValueAtTime(0.4, ctx.currentTime + 0.25);
                    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.45);
                    
                    osc.start(ctx.currentTime);
                    osc.stop(ctx.currentTime + 0.5);
                }} else if (type === 'info') {{
                    let osc1 = ctx.createOscillator();
                    let gain1 = ctx.createGain();
                    osc1.connect(gain1);
                    gain1.connect(ctx.destination);
                    osc1.type = 'sine';
                    osc1.frequency.setValueAtTime(600, ctx.currentTime);
                    gain1.gain.setValueAtTime(0.2, ctx.currentTime);
                    gain1.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
                    osc1.start(ctx.currentTime);
                    osc1.stop(ctx.currentTime + 0.3);

                    let osc2 = ctx.createOscillator();
                    let gain2 = ctx.createGain();
                    osc2.connect(gain2);
                    gain2.connect(ctx.destination);
                    osc2.type = 'sine';
                    osc2.frequency.setValueAtTime(800, ctx.currentTime + 0.08);
                    gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.08);
                    gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.33);
                    osc2.start(ctx.currentTime + 0.08);
                    osc2.stop(ctx.currentTime + 0.38);
                }}
            }}

            if (ctx) {{
                if (ctx.state === 'suspended') {{
                    ctx.resume();
                }}
                const type = '{som_key}';
                const customMp3Url = "{supabase_base_url}/storage/v1/object/public/sons/" + encodeURIComponent(type) + ".mp3";
                const customMp3UrlUpper = "{supabase_base_url}/storage/v1/object/public/sons/" + encodeURIComponent(type) + ".MP3";
                
                if (type.startsWith('naval_bell_')) {{
                    let count = 1;
                    if (type === 'naval_bell_singela') {{
                        count = 1;
                    }} else if (type === 'naval_bell_dobrada') {{
                        count = 2;
                    }} else {{
                        count = parseInt(type.split('_')[2]) || 1;
                    }}
                    
                    const singleMp3Url = "{supabase_base_url}/storage/v1/object/public/sons/bell_single.mp3";
                    const doubleMp3Url = "{supabase_base_url}/storage/v1/object/public/sons/bell_double.mp3";
                    
                    function playSynthesizedBells(ctx, count) {{
                        function playNavalBellStrike(ctx, time) {{
                            const frequencies = [240, 480, 576, 720, 960, 1200, 1440, 1920];
                            const gains = [0.35, 0.35, 0.25, 0.15, 0.15, 0.1, 0.08, 0.05];
                            const decays = [3.2, 2.6, 2.2, 1.8, 1.4, 1.0, 0.6, 0.4];

                            frequencies.forEach((f, idx) => {{
                                let osc = ctx.createOscillator();
                                let gainNode = ctx.createGain();
                                osc.connect(gainNode);
                                gainNode.connect(ctx.destination);
                                
                                osc.type = 'sine';
                                osc.frequency.setValueAtTime(f, time);
                                
                                gainNode.gain.setValueAtTime(0, time);
                                gainNode.gain.linearRampToValueAtTime(gains[idx], time + 0.005);
                                gainNode.gain.exponentialRampToValueAtTime(0.001, time + decays[idx]);
                                
                                osc.start(time);
                                osc.stop(time + decays[idx] + 0.1);
                            }});
                        }}

                        let now = ctx.currentTime;
                        for (let i = 0; i < count; i++) {{
                            let pairIndex = Math.floor(i / 2);
                            let inPairIndex = i % 2;
                            let timeOffset = pairIndex * 2.0 + inPairIndex * 0.15;
                            playNavalBellStrike(ctx, now + timeOffset);
                        }}
                    }}

                    fetch(singleMp3Url)
                        .then(res => {{
                            if (res.ok) {{
                                let pairs = Math.floor(count / 2);
                                let remainder = count % 2;
                                
                                for (let p = 0; p < pairs; p++) {{
                                    setTimeout(() => {{
                                        let audio = new Audio(doubleMp3Url);
                                        audio.volume = 1.0;
                                        audio.play().catch(() => {{}});
                                    }}, p * 2000);
                                }}
                                
                                if (remainder > 0) {{
                                    setTimeout(() => {{
                                        let audio = new Audio(singleMp3Url);
                                        audio.volume = 1.0;
                                        audio.play().catch(() => {{}});
                                    }}, pairs * 2000);
                                }}
                            }} else {{
                                playSynthesizedBells(ctx, count);
                            }}
                        }})
                        .catch(() => {{
                            playSynthesizedBells(ctx, count);
                        }});
                }} else {{
                    fetch(customMp3Url)
                        .then(res => {{
                            if (res.ok) {{
                                let audio = new Audio(customMp3Url);
                                audio.volume = 1.0;
                                audio.play().catch(() => {{}});
                            }} else {{
                                fetch(customMp3UrlUpper)
                                    .then(res2 => {{
                                        if (res2.ok) {{
                                            let audio2 = new Audio(customMp3UrlUpper);
                                            audio2.volume = 1.0;
                                            audio2.play().catch(() => {{}});
                                        }} else {{
                                            playDefaultSynthesized(type);
                                        }}
                                    }}).catch(() => {{
                                        playDefaultSynthesized(type);
                                    }});
                            }}
                        }})
                        .catch(() => {{
                            fetch(customMp3UrlUpper)
                                .then(res2 => {{
                                    if (res2.ok) {{
                                        let audio2 = new Audio(customMp3UrlUpper);
                                        audio2.volume = 1.0;
                                        audio2.play().catch(() => {{}});
                                    }} else {{
                                        playDefaultSynthesized(type);
                                    }}
                                }}).catch(() => {{
                                    playDefaultSynthesized(type);
                                }});
                        }});
                }}
            }}
        }} catch (e) {{
            console.error("[AUDIO TEST] Erro ao reproduzir som:", e);
        }}
        """
        ui.run_javascript(js_code)

    # Carrega dados atuais
    try:
        config_df = data_service.get_config_data(force_refresh=True)
        if not config_df.empty:
            db_configs = dict(zip(config_df['chave'], config_df['valor']))
        else:
            db_configs = {}
    except Exception as e:
        print(f"[CONFIG] Erro ao carregar configurações: {e}")
        db_configs = {}

    # Mescla configurações carregadas com as padrões caso faltem chaves
    current_configs = {k: db_configs.get(k, v) for k, v in DEFAULT_CONFIGS.items()}

    from alerts_manager import load_alerts_config, save_alerts_config
    alerts_config = load_alerts_config()
    sound_mappings = alerts_config.get("sound_mappings", {})

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Configurações', 'Configurações de Variáveis Globais e Parâmetros de Conceito')
        ui.add_head_html('''
        <style>
        .config-tabs .q-tabs__content {
            flex-wrap: wrap !important;
        }
        .config-tabs .q-tab {
            white-space: normal !important;
            min-height: 40px;
            height: auto !important;
            flex-shrink: 1 !important;
        }
        </style>
        ''')
        active_tab = {'name': 'geral'}
        
        @ui.refreshable
        def render_config_tabs_bar():
            with ui.row().classes('w-full border-b border-white/10 gap-2 q-mb-md no-wrap overflow-x-auto q-pb-xs'):
                tabs_def = [
                    ('geral', 'Parâmetros Gerais', 'settings'),
                    ('sons', 'Personalização de Sons', 'volume_up'),
                    ('sinos', 'Sinos & Alertas Agendados', 'alarm'),
                    ('templates', 'Modelos de Mensagens', 'chat'),
                    ('telegram', 'Notificações Telegram', 'notifications'),
                    ('tts', 'Configuração de Voz (TTS)', 'record_voice_over'),
                    ('tipos_acao', 'Tipos de Ações (Notas)', 'calculate'),
                    ('permissoes', 'Gerenciar Permissões', 'admin_panel_settings'),
                ]
                for key, label, icon in tabs_def:
                    is_active = active_tab['name'] == key
                    color = THEME['primary'] if is_active else '#64748b'
                    bg_color = 'rgba(0, 229, 255, 0.1)' if is_active else 'transparent'
                    border = f'1px solid {THEME["primary"]}' if is_active else '1px solid rgba(255,255,255,0.05)'
                    
                    def click_tab(k=key):
                        active_tab['name'] = k
                        panels.value = k
                        render_config_tabs_bar.refresh()
                        
                    ui.button(
                        label, 
                        icon=icon, 
                        on_click=click_tab
                    ).props('unelevated no-caps dense').style(
                        f'background: {bg_color}; color: {color}; border: {border}; border-radius: 6px; font-weight: bold; font-size: 0.8rem; padding: 6px 12px;'
                    )
        
        render_config_tabs_bar()
        panels = ui.tab_panels(value='geral').classes('w-full bg-transparent')
        with panels:
            with ui.tab_panel('geral').classes('bg-transparent q-pa-none gap-6'):
                with ui.grid(columns='1 md:grid-cols-2').classes('w-full gap-6'):
                    
                    # --- CARD 1: CÁLCULO DE CONCEITOS ---
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('calculate', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Parâmetros de Conceito').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            ui.label('Define como as notas acadêmicas e as ações disciplinares calculam o conceito final do aluno.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                            
                            input_base = ui.input(
                                'Linha Base de Conceito', 
                                value=current_configs['linha_base_conceito']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Conceito de partida comum a todos os alunos (Padrão: 8.5).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')
                            
                            input_max_acoes = ui.input(
                                'Impacto Máximo de Ações (Elogios/Sanções)', 
                                value=current_configs['impacto_max_acoes']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Valor limite absoluto que a pontuação de ações disciplinares pode somar ou subtrair do conceito (Padrão: 1.5).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_peso_acad = ui.input(
                                'Peso Acadêmico', 
                                value=current_configs['peso_academico']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Peso normalizado do desempenho acadêmico (Média do Aluno comparada à média da turma) no conceito final (Padrão: 1.0).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                    # --- CARD 2: PERÍODO DE ADAPTAÇÃO ---
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('shield', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Atenuação de Adaptação').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            ui.label('Define as datas e o fator atenuante para sanções disciplinares aplicadas a novos alunos no período de adaptação.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                            
                            input_fator = ui.input(
                                'Fator de Adaptação', 
                                value=current_configs['fator_adaptacao']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Multiplicador aplicado a punições/atrasos ocorridos no período de adaptação. Reduz o impacto de sanções (Ex: 0.25 = reduz punição a 25%).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            with ui.row().classes('w-full gap-4'):
                                # Data Início
                                with ui.column().classes('col-grow gap-1'):
                                    ui.label('Início da Adaptação').classes('text-[11px]').style(f'color: {THEME["text_dim"]}')
                                    input_ini = ui.input(value=current_configs['periodo_adaptacao_inicio']).props('dark dense outlined type=date').classes('w-full')
                                
                                # Data Fim
                                with ui.column().classes('col-grow gap-1'):
                                    ui.label('Fim da Adaptação').classes('text-[11px]').style(f'color: {THEME["text_dim"]}')
                                    input_fim = ui.input(value=current_configs['periodo_adaptacao_fim']).props('dark dense outlined type=date').classes('w-full')

                    # --- CARD 3: PAINEL DE PROJEÇÃO / MODO TV ---
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('tv', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Painel de Projeção (Modo TV)').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            ui.label('Configurações visuais e de sincronização do painel de monitoramento da TV de 60".').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                            
                            input_polling = ui.input(
                                'Tempo de Polling/Atualização (segundos)', 
                                value=current_configs['tempo_polling_tv']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Tempo de intervalo em segundos para a TV buscar novas atualizações no Supabase (Padrão: 300 segundos = 5 min).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_cabecalho_tv = ui.input(
                                'Título do Cabeçalho da TV', 
                                value=current_configs['cabecalho_tv_title']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Título principal exibido no topo da tela da TV (Padrão: SITUAÇÃO CONSOLIDADA DO CORPO DE ALUNOS).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_subcabecalho_tv = ui.input(
                                'Subtítulo do Cabeçalho da TV', 
                                value=current_configs.get('cabecalho_tv_subtitle', 'CORPO DE ALUNOS • COMANDO TÁTICO')
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Subtítulo secundário exibido no topo da tela da TV (Padrão: CORPO DE ALUNOS • COMANDO TÁTICO).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_sunset_tv = ui.input(
                                'Horário do Pôr do Sol da TV (HH:MM)', 
                                value=current_configs.get('cabecalho_tv_sunset_time', '17:48')
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Configura o horário do pôr do sol para a sua localidade/base militar. Se deixado vazio, o sistema calculará automaticamente o horário ideal estimado para o dia do ano.').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_cargos_escala = ui.input(
                                'Funções/Cargos da Escala (separados por vírgula)', 
                                value=current_configs['cargos_escala_lista']
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Lista de cargos da escala diária disponíveis para preenchimento (ex: INSPETOR DO DIA, SUPERVISOR, etc.).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_unlock_code = ui.input(
                                'Código de Desbloqueio da TV (Blur)', 
                                value=current_configs.get('codigo_desbloqueio_tv', '1234')
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Código padrão exigido para reexibir as anotações do dia quando ocultadas no Modo TV (Padrão: 1234).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_alerta_tv = ui.input(
                                'Tempo de Exibição de Alertas da TV (segundos)', 
                                value=current_configs.get('tempo_alerta_tv', '10')
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Tempo padrão em segundos de exibição dos alertas visuais/toasts no Modo TV (Padrão: 10 segundos).').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                            input_telegram_token = ui.input(
                                'Token do Bot do Telegram', 
                                value=current_configs.get('telegram_bot_token', ''),
                                password=True
                            ).props('dark dense outlined w-full').classes('w-full')
                            ui.label('Token de autenticação do Telegram Bot (obtido via @BotFather). Se vazio, usará a variável TELEGRAM_TOKEN do arquivo .env.').classes('text-[10px] q-mt-xs').style(f'color: {THEME["text_dim"]}')

                    # --- CARD 4: GESTÃO DE ORDENS DIÁRIAS (AVISOS DA TV) ---
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('campaign', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Ordens Diárias e Avisos (TV)').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            ui.label('Adicione avisos e ordens para rodar no painel de anotações e letreiro da TV de 60".').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                            
                            order_state = {
                                'date': date.today().strftime('%Y-%m-%d'),
                            }
                            
                            with ui.row().classes('w-full items-center gap-2'):
                                date_input = ui.input(
                                    'Data dos Avisos', 
                                    value=order_state['date']
                                ).props('dark dense outlined type=date').classes('col-grow')
                                
                                def on_date_change():
                                    order_state['date'] = date_input.value
                                    render_orders_list.refresh()
                                date_input.on('change', on_date_change)
                            
                            @ui.refreshable
                            def render_orders_list():
                                db_conn = get_db_connection()
                                orders = []
                                if db_conn:
                                    try:
                                        res = db_conn.table('Ordens_Diarias').select('*').eq('data', order_state['date']).execute()
                                        orders = res.data if res.data else []
                                    except Exception as e:
                                        print(f"[CONFIG] Erro ao carregar ordens: {e}")
                                else:
                                    mock_list = getattr(app, '_mock_ordens_diarias', [])
                                    orders = [o for o in mock_list if o['data'] == order_state['date']]
                                    
                                with ui.column().classes('w-full gap-2 border border-white/5 q-pa-sm rounded bg-black/10').style('max-height: 150px; overflow-y: auto;'):
                                    if not orders:
                                        ui.label('Sem avisos cadastrados para esta data.').classes('text-xs italic text-grey-5 text-center w-full py-2')
                                    else:
                                        for o in orders:
                                            with ui.row().classes('w-full justify-between items-center no-wrap py-1 border-b border-white/5'):
                                                with ui.column().classes('gap-0 col-grow min-w-0'):
                                                    ui.label(o['texto']).classes('text-xs text-white break-words')
                                                    ui.label(f"Por: {o.get('autor_id', 'ADMIN')}").classes('text-[9px] text-grey-5')
                                                
                                                def excluir_ordem(o_id=o.get('id'), o_text=o.get('texto')):
                                                    db_c = get_db_connection()
                                                    if db_c:
                                                        try:
                                                            if o_id:
                                                                db_c.table('Ordens_Diarias').delete().eq('id', o_id).execute()
                                                            else:
                                                                db_c.table('Ordens_Diarias').delete().eq('data', order_state['date']).eq('texto', o_text).execute()
                                                            ui.notify('Aviso excluído com sucesso!', color='success')
                                                        except Exception as err:
                                                            ui.notify(f'Erro ao excluir: {err}', color='red')
                                                    else:
                                                        mock_m = getattr(app, '_mock_ordens_diarias', [])
                                                        if o_id:
                                                            mock_m = [item for item in mock_m if item.get('id') != o_id]
                                                        else:
                                                            mock_m = [item for item in mock_m if not (item['data'] == order_state['date'] and item['texto'] == o_text)]
                                                        app._mock_ordens_diarias = mock_m
                                                        ui.notify('Aviso excluído localmente.', color='warning')
                                                    render_orders_list.refresh()
                                                
                                                with ui.row().classes('items-center gap-1 shrink-0'):
                                                    def abrir_editar_ordem_dialog(order=o):
                                                        d_edit = ui.dialog()
                                                        with d_edit, ui.card().classes('w-[360px] q-pa-md bg-slate-900 border border-cyan-5'):
                                                            ui.label('✏️ EDITAR AVISO').classes('text-white text-sm font-black cyber-title q-mb-xs')
                                                            edit_inp = ui.input('Texto do Aviso', value=order['texto']).props('dark outlined dense w-full').classes('w-full')
                                                            
                                                            def salvar_edicao():
                                                                txt_val = edit_inp.value.strip()
                                                                if not txt_val:
                                                                    ui.notify('O texto não pode ser vazio.', color='warning')
                                                                    return
                                                                db_u = get_db_connection()
                                                                if db_u:
                                                                    try:
                                                                        db_u.table('Ordens_Diarias').update({'texto': txt_val}).eq('id', order['id']).execute()
                                                                        ui.notify('Aviso editado com sucesso!', color='success')
                                                                    except Exception as err:
                                                                        ui.notify(f'Erro ao atualizar: {err}', color='red')
                                                                else:
                                                                    mock_m = getattr(app, '_mock_ordens_diarias', [])
                                                                    for item in mock_m:
                                                                        if item.get('id') == order.get('id') or (item['data'] == order['data'] and item['texto'] == order['texto']):
                                                                            item['texto'] = txt_val
                                                                            break
                                                                    app._mock_ordens_diarias = mock_m
                                                                    ui.notify('Aviso editado localmente.', color='warning')
                                                                d_edit.close()
                                                                render_orders_list.refresh()
                                                                
                                                            with ui.row().classes('w-full justify-end gap-2 q-mt-sm'):
                                                                ui.button('Cancelar', on_click=d_edit.close).props('flat color=grey no-caps')
                                                                ui.button('Salvar', on_click=salvar_edicao).props('unelevated color=cyan-9 text-color=white no-caps')
                                                        d_edit.open()
                                                        
                                                    ui.button(
                                                        icon='edit', 
                                                        on_click=abrir_editar_ordem_dialog
                                                    ).props('flat round dense color=cyan').classes('text-xs')
                                                    
                                                    ui.button(
                                                        icon='delete', 
                                                        on_click=excluir_ordem
                                                    ).props('flat round dense color=red').classes('text-xs')
                            
                            render_orders_list()
                            
                            input_ordem_text = ui.input(
                                'Novo Aviso',
                                placeholder='Ex: Formatura Geral às 07:30 Uniforme 3º A.'
                            ).props('dark dense outlined w-full').classes('w-full')
                            
                            def adicionar_ordem():
                                val = input_ordem_text.value.strip()
                                if not val:
                                    ui.notify('Digite o texto do aviso.', color='red')
                                    return
                                
                                autor = app.storage.user.get('user_data', {}).get('nome_guerra', 'ADMIN').upper()
                                db_conn = get_db_connection()
                                if db_conn:
                                    try:
                                        db_conn.table('Ordens_Diarias').insert({
                                            'data': order_state['date'],
                                            'texto': val,
                                            'autor_id': autor,
                                            'status': 'Ativo'
                                        }).execute()
                                        ui.notify('Aviso adicionado com sucesso!', color='success')
                                    except Exception as err:
                                        ui.notify(f'Erro ao salvar no banco: {err}', color='red')
                                else:
                                    if not hasattr(app, '_mock_ordens_diarias'):
                                        app._mock_ordens_diarias = []
                                    import random
                                    app._mock_ordens_diarias.append({
                                        'id': random.randint(1000, 9999),
                                        'data': order_state['date'],
                                        'texto': val,
                                        'autor_id': autor,
                                        'status': 'Ativo'
                                    })
                                    ui.notify('Aviso adicionado localmente (offline)!', color='warning')
                                
                                # Transmite à TV em tempo real
                                try:
                                    from alerts_manager import AlertsManager
                                    AlertsManager.trigger_alert(
                                        "Novo Aviso",
                                        f"Aviso publicado por {autor}: {val}",
                                        "info"
                                    )
                                except Exception as e_alert:
                                    print(f"[CONFIG] Erro ao disparar alerta de aviso: {e_alert}")
                                    
                                # Envia notificação Telegram
                                try:
                                    from notifications_manager import notify_telegram
                                    alert_txt = (
                                        f"📢 **NOVO AVISO CRÍTICO PUBLICADO**\n"
                                        f"👤 Autor: {autor}\n\n"
                                        f"\"{val}\""
                                    )
                                    notify_telegram(alert_txt, "aviso")
                                except Exception as e_notif:
                                    print(f"[CONFIG AVISO NOTIFY ERROR] {e_notif}")
                                    
                                input_ordem_text.value = ''
                                render_orders_list.refresh()
                            
                            ui.button(
                                'Adicionar Aviso', 
                                icon='add', 
                                on_click=adicionar_ordem
                            ).props('unelevated color=amber-9 text-color=black w-full dense').classes('bold')
                    
                    # --- ABA 2: PERSONALIZAÇÃO DE SONS ---
            with ui.tab_panel('sons').classes('bg-transparent q-pa-none gap-6'):
                # --- CARD 5: PERSONALIZAÇÃO DE SONS DOS ALERTAS ---
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('volume_up', size='2rem').style(f'color: {THEME["accent"]}')
                            ui.label('Personalização de Sons').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                        ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                        
                        ui.label('Configure o efeito sonoro reproduzido no Modo TV para cada evento:').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                        
                        sound_dropdowns = {}
                        som_opcoes = {
                            'info': 'Chime Digital Premium 🎵',
                            'success': 'Chime de Sucesso (Do-Mi) 🎉',
                            'warning': 'Aviso Duplo Ping 🔔',
                            'alert': 'Alerta Tático Grave ⚠️',
                            'submarine_sonar': 'Sonar Submarino 📡',
                            'morse_sos': 'Código Morse SOS 🆘',
                            'naval_horn': 'Buzina de Navio (Grave) 🚢',
                            'naval_bell_singela': 'Sino Marinheiro Singelo (1 Batida) ⚓',
                            'naval_bell_dobrada': 'Sino Marinheiro Dobrado (2 Batidas) ⚓',
                            'naval_bell_4': 'Sino da Marinha (4 Baladas / 2 Dobradas) ⚓',
                            'naval_bell_8': 'Sino da Marinha (8 Baladas / 4 Dobradas) ⚓',
                            'silent': 'Silencioso 🔕'
                        }
                        
                        def atualizar_opcoes_de_sons():
                            nonlocal som_opcoes
                            som_opcoes = {
                                'info': 'Chime Digital Premium 🎵',
                                'success': 'Chime de Sucesso (Do-Mi) 🎉',
                                'warning': 'Aviso Duplo Ping 🔔',
                                'alert': 'Alerta Tático Grave ⚠️',
                                'submarine_sonar': 'Sonar Submarino 📡',
                                'morse_sos': 'Código Morse SOS 🆘',
                                'naval_horn': 'Buzina de Navio (Grave) 🚢',
                                'naval_bell_singela': 'Sino Marinheiro Singelo (1 Batida) ⚓',
                                'naval_bell_dobrada': 'Sino Marinheiro Dobrado (2 Batidas) ⚓',
                                'naval_bell_4': 'Sino da Marinha (4 Baladas / 2 Dobradas) ⚓',
                                'naval_bell_8': 'Sino da Marinha (8 Baladas / 4 Dobradas) ⚓',
                                'silent': 'Silencioso 🔕'
                            }
                            db_conn = get_admin_db_connection() or get_db_connection()
                            if db_conn:
                                try:
                                    res = db_conn.storage.from_('sons').list()
                                    if res:
                                        for item in res:
                                            f = item.get('name')
                                            if f and f.lower().endswith('.mp3'):
                                                key = f[:-4]
                                                if key not in som_opcoes:
                                                    friendly_name = key.replace('_', ' ').replace('-', ' ').title()
                                                    som_opcoes[key] = f"Arquivo: {friendly_name} 🎵"
                                except Exception as e:
                                    print(f"[CONFIG] Erro ao listar sons: {e}")

                            
                            # Atualiza dropdowns de eventos
                            for o_name, d_el in sound_dropdowns.items():
                                d_el.options = som_opcoes
                                d_el.update()
                            # Atualiza dropdown de agendamento se inicializado
                            try:
                                select_alerta_sound.options = som_opcoes
                                select_alerta_sound.update()
                            except Exception:
                                pass
                            # Atualiza dropdown de edição se inicializado
                            try:
                                edit_sound.options = som_opcoes
                                edit_sound.update()
                            except Exception:
                                pass

                        # Carrega dinamicamente arquivos MP3 na inicialização do Supabase
                        db_conn = get_admin_db_connection() or get_db_connection()
                        if db_conn:
                            try:
                                res = db_conn.storage.from_('sons').list()
                                if res:
                                    for item in res:
                                        f = item.get('name')
                                        if f and f.lower().endswith('.mp3'):
                                            key = f[:-4]
                                            if key not in som_opcoes:
                                                friendly_name = key.replace('_', ' ').replace('-', ' ').title()
                                                som_opcoes[key] = f"Arquivo: {friendly_name} 🎵"
                            except Exception as e:
                                print(f"[CONFIG] Erro na inicialização ao listar sons do Supabase: {e}")
                        
                        def build_sound_sequence_editor(ocorrencia_nome, val_som):
                            # val_som pode ser uma string (legado) ou uma lista de dicionarios/strings
                            sequence = []
                            if isinstance(val_som, list):
                                for item in val_som:
                                    if isinstance(item, dict):
                                        sequence.append({'som': item.get('som', 'info'), 'delay': float(item.get('delay', 0.0))})
                                    else:
                                        sequence.append({'som': str(item), 'delay': 0.0})
                            elif isinstance(val_som, str):
                                sequence.append({'som': val_som, 'delay': 0.0})
                            
                            if not sequence:
                                sequence.append({'som': 'info', 'delay': 0.0})

                            sound_dropdowns[ocorrencia_nome] = sequence

                            @ui.refreshable
                            def render_sequence():
                                ui.label(ocorrencia_nome).classes('text-xs text-white font-bold')
                                with ui.column().classes('w-full gap-2 pl-4 border-l border-cyan-500/20 q-mb-md'):
                                    for idx, seq_item in enumerate(sequence):
                                        with ui.row().classes('w-full items-center gap-2'):
                                            # Dropdown de seleção de som
                                            sel = ui.select(
                                                som_opcoes,
                                                value=seq_item['som'],
                                                on_change=lambda e, i=idx: [sequence[i].update({'som': e.value})]
                                            ).props('dark dense outlined').classes('text-xs min-w-[200px]')
                                            
                                            # Campo de atraso (delay) antes do som
                                            ui.label('Atraso:').classes('text-[11px] text-grey-5')
                                            delay_input = ui.number(
                                                value=seq_item['delay'],
                                                min=0.0,
                                                max=30.0,
                                                step=0.5,
                                                format='%.1f'
                                            ).props('dark dense outlined').classes('w-16 text-xs').style('margin-right: 4px;')
                                            delay_input.on('change', lambda e, i=idx: [sequence[i].update({'delay': float(e.value or 0.0)})])
                                            
                                            # Botão de teste para este som individual
                                            ui.button(
                                                icon='play_arrow',
                                                on_click=lambda _, idx=idx: testar_som(sequence[idx]['som'])
                                            ).props('flat round dense color=primary').classes('text-xs')
                                            
                                            # Botão de remoção (se houver mais de 1 som)
                                            if len(sequence) > 1:
                                                ui.button(
                                                    icon='delete',
                                                    on_click=lambda _, i=idx: [sequence.pop(i), render_sequence.refresh()]
                                                ).props('flat round dense color=red').classes('text-xs')
                                    
                                    # Botão para adicionar som na sequência
                                    ui.button(
                                        'Adicionar Som na Sequência',
                                        icon='add',
                                        on_click=lambda: [sequence.append({'som': 'info', 'delay': 1.0}), render_sequence.refresh()]
                                    ).props('outline dense no-caps color=primary').classes('text-[11px] self-start')

                            render_sequence()

                        for ocorrencia_nome, som_atual in sound_mappings.items():
                            with ui.row().classes('w-full items-center justify-between gap-2 border-b border-white/5 py-2'):
                                build_sound_sequence_editor(ocorrencia_nome, som_atual)

                # --- CARD: GERENCIADOR DE ARQUIVOS DE SOM ---
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('folder_open', size='2rem').style(f'color: {THEME["accent"]}')
                            ui.label('Gerenciamento de Arquivos de Som').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                        ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                        
                        ui.label('Envie arquivos .mp3 customizados para usar como toques de alerta e sinos.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                        
                        # Upload de Som
                        async def handle_sound_upload(e):
                            try:
                                import inspect
                                
                                # Extrai o nome de forma robusta
                                filename = getattr(e, 'name', None) or getattr(getattr(e, 'file', None), 'name', None)
                                if not filename:
                                    filename = 'som_upload.mp3'
                                    
                                if not filename.lower().endswith('.mp3'):
                                    ui.notify('Apenas arquivos no formato .mp3 são suportados!', color='red')
                                    return
                                
                                if filename in ('bell_single.mp3', 'bell_double.mp3'):
                                    ui.notify('Não é permitido sobrescrever arquivos de sistema.', color='red')
                                    return
                                    
                                # Extrai o conteúdo (bytes) de forma robusta
                                file_bytes = None
                                file_obj = getattr(e, 'file', None) or getattr(e, 'content', None)
                                if file_obj and hasattr(file_obj, 'read'):
                                    file_bytes = file_obj.read()
                                    if inspect.isawaitable(file_bytes):
                                        file_bytes = await file_bytes
                                        
                                if not file_bytes:
                                    ui.notify('Falha ao ler o conteúdo do arquivo enviado.', color='red')
                                    return
                                    
                                from database import upload_file_to_supabase_storage
                                import asyncio
                                
                                async def process_upload():
                                     public_url = await asyncio.to_thread(
                                         upload_file_to_supabase_storage,
                                         file_bytes,
                                         filename,
                                         "audio/mpeg",
                                         "sons"
                                     )
                                     if public_url:
                                         ui.notify(f'Som "{filename}" enviado com sucesso!', color='success')
                                         atualizar_opcoes_de_sons()
                                         render_sound_files_list.refresh()
                                         try:
                                             render_custom_alerts_list.refresh()
                                         except Exception:
                                             pass
                                     else:
                                         ui.notify('Erro ao enviar som ao Supabase.', color='red')
                                
                                await process_upload()
                            except Exception as ex:
                                ui.notify(f'Erro ao salvar arquivo: {ex}', color='red')
                                
                        ui.upload(label='Enviar Som (.mp3)', auto_upload=True, on_upload=handle_sound_upload).props('dark accept=.mp3 max-files=1').classes('w-full h-24')
                        
                        # Helpers de integridade para renomear e excluir sons da config
                        def renomear_som_no_config(old_key, new_key):
                            c_config = load_alerts_config()
                            mappings = c_config.get('sound_mappings', {})
                            for event, sound in mappings.items():
                                if sound == old_key:
                                    mappings[event] = new_key
                            for item in c_config.get('custom_alerts', []):
                                if item.get('sound') == old_key:
                                    item['sound'] = new_key
                            save_alerts_config(c_config)

                        def remover_som_no_config(sound_key):
                            c_config = load_alerts_config()
                            mappings = c_config.get('sound_mappings', {})
                            for event, sound in mappings.items():
                                if sound == sound_key:
                                    mappings[event] = 'info'
                            for item in c_config.get('custom_alerts', []):
                                if item.get('sound') == sound_key:
                                    item['sound'] = 'info'
                            save_alerts_config(c_config)

                        # Diálogos para renomear som
                        with ui.dialog() as rename_sound_dialog:
                            with theme.card_base().classes('q-pa-md').style('min-width: 350px;'):
                                with ui.column().classes('w-full gap-4'):
                                    ui.label('✏️ Renomear Arquivo de Som').classes('text-lg font-bold text-white')
                                    ui.separator().style('background-color: rgba(255,255,255,0.1);')
                                    
                                    orig_sound_name = ui.label('').classes('hidden')
                                    input_new_sound_name = ui.input('Nome do Arquivo (sem .mp3)', placeholder='Ex: alerta_especial').props('dark dense outlined').classes('w-full')
                                    
                                    def confirmar_renomeacao():
                                        old_filename = orig_sound_name.text
                                        new_name = input_new_sound_name.value.strip().lower()
                                        new_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in ('_', '-')])
                                        if not new_name:
                                            ui.notify('Nome de arquivo inválido!', color='red')
                                            return
                                        new_filename = new_name + '.mp3'
                                        
                                        if new_filename in ('bell_single.mp3', 'bell_double.mp3'):
                                            ui.notify('Não é permitido usar nomes de arquivos de sistema.', color='red')
                                            return
                                            
                                        db_conn = get_admin_db_connection() or get_db_connection()
                                        if not db_conn:
                                            ui.notify('Sem conexão com o banco de dados.', color='red')
                                            return
                                            
                                        try:
                                            existing = db_conn.storage.from_('sons').list()
                                            if any(item.get('name') == new_filename for item in existing):
                                                ui.notify('Já existe um arquivo de som com este nome.', color='red')
                                                return
                                                
                                            db_conn.storage.from_('sons').move(old_filename, new_filename)
                                            old_key = old_filename[:-4]
                                            new_key = new_name
                                            renomear_som_no_config(old_key, new_key)
                                            
                                            ui.notify('Arquivo renomeado com sucesso!', color='success')
                                            rename_sound_dialog.close()
                                            atualizar_opcoes_de_sons()
                                            render_sound_files_list.refresh()
                                            render_custom_alerts_list.refresh()
                                        except Exception as ex:
                                            ui.notify(f'Erro ao renomear: {ex}', color='red')
                                            
                                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                                        ui.button('Cancelar', on_click=rename_sound_dialog.close).props('outline dense color=grey')
                                        ui.button('Confirmar', on_click=confirmar_renomeacao).props('unelevated dense color=primary')

                        @ui.refreshable
                        def render_sound_files_list():
                            custom_files = []
                            db_conn = get_admin_db_connection() or get_db_connection()
                            if db_conn:
                                try:
                                    res = db_conn.storage.from_('sons').list()
                                    if res:
                                        for item in res:
                                            f = item.get('name')
                                            if f and f.lower().endswith('.mp3') and f.lower() not in ('bell_single.mp3', 'bell_double.mp3'):
                                                custom_files.append(f)
                                except Exception as e:
                                    print(f"[CONFIG] Erro ao listar arquivos de som: {e}")
                                    
                            with ui.column().classes('w-full gap-2 border border-white/5 q-pa-sm rounded bg-black/10').style('max-height: 200px; overflow-y: auto;'):
                                if not custom_files:
                                    ui.label('Sem arquivos de som customizados (apenas sons de sistema ativos).').classes('text-xs italic text-grey-5 text-center w-full py-2')
                                else:
                                    for f in sorted(custom_files):
                                        with ui.row().classes('w-full justify-between items-center no-wrap py-1 border-b border-white/5'):
                                            ui.label(f).classes('text-xs text-white truncate col-grow')
                                            
                                            def make_play_cb(filename=f):
                                                return lambda: testar_som(filename[:-4])
                                                
                                            def abrir_renomear(filename=f):
                                                orig_sound_name.set_text(filename)
                                                input_new_sound_name.value = filename[:-4]
                                                rename_sound_dialog.open()
                                                
                                            def excluir_som(filename=f):
                                                async def processar_exclusao():
                                                    db_conn = get_admin_db_connection() or get_db_connection()
                                                    if not db_conn:
                                                        ui.notify('Sem conexão com o banco de dados.', color='red')
                                                        return
                                                    try:
                                                        db_conn.storage.from_('sons').remove([filename])
                                                        remover_som_no_config(filename[:-4])
                                                        ui.notify(f'Som "{filename}" excluído com sucesso!', color='success')
                                                        atualizar_opcoes_de_sons()
                                                        render_sound_files_list.refresh()
                                                        render_custom_alerts_list.refresh()
                                                    except Exception as ex:
                                                        ui.notify(f'Erro ao excluir: {ex}', color='red')
                                                        
                                                confirm_dialog = ui.dialog()
                                                with confirm_dialog, theme.card_base().classes('q-pa-md'):
                                                    with ui.column().classes('items-center text-center gap-4'):
                                                        ui.icon('warning', size='3rem', color='red')
                                                        ui.label(f'Deseja excluir definitivamente o arquivo "{filename}"?').classes('text-sm font-bold text-white')
                                                        with ui.row().classes('gap-2 q-mt-md'):
                                                            ui.button('Cancelar', on_click=confirm_dialog.close).props('outline dense color=grey')
                                                            ui.button('Excluir', on_click=lambda: [confirm_dialog.close(), processar_exclusao()]).props('unelevated dense color=red')
                                                confirm_dialog.open()
                                            
                                            with ui.row().classes('items-center gap-1'):
                                                ui.button(icon='play_arrow', on_click=make_play_cb(f)).props('flat round dense color=primary').classes('text-xs')
                                                ui.button(icon='edit', on_click=lambda _, fn=f: abrir_renomear(fn)).props('flat round dense color=primary').classes('text-xs')
                                                ui.button(icon='delete', on_click=lambda _, fn=f: excluir_som(fn)).props('flat round dense color=red').classes('text-xs')
                                                
                        render_sound_files_list()

            # --- ABA 3: SINOS & ALERTAS AGENDADOS ---
            with ui.tab_panel('sinos').classes('bg-transparent q-pa-none gap-6'):
                # --- CARD 6: ALERTAS AGENDADOS E SINOS NAVAIS ---
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('alarm', size='2rem').style(f'color: {THEME["accent"]}')
                            ui.label('Sinos Navais e Alertas Agendados').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                        ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                        
                        # Switch do Sino Automático
                        input_tv_vocativo = ui.input(
                            'Vocativo Personalizado de Alerta (Modo TV)',
                            value=alerts_config.get('tv_alert_vocativo', 'Atenção!')
                        ).props('dark dense outlined').classes('w-full text-xs').style('max-width: 400px;')
                        
                        ui.separator().style('background-color: rgba(255,255,255,0.05); height: 1px;')
                        ui.label('Agendar Novo Alerta Horário:').classes('text-xs font-bold text-white')
                        
                        with ui.row().classes('w-full items-center gap-2'):
                            input_alerta_time = ui.input('Hora', placeholder='07:30').props('dark dense outlined mask=##:## w-1/5').classes('text-xs')
                            input_alerta_title = ui.input('Título', placeholder='Aviso').props('dark dense outlined w-1/4').classes('text-xs')
                            input_alerta_msg = ui.input('Mensagem', placeholder='Instrução Geral no Pátio').props('dark dense outlined col-grow').classes('text-xs')
                            
                            alerta_som_opcoes = som_opcoes
                            select_alerta_sound = ui.select(alerta_som_opcoes, value='info').props('dark dense outlined').classes('text-xs min-w-[120px]')
                            ui.button(
                                icon='play_arrow', 
                                on_click=lambda: testar_som(select_alerta_sound.value)
                            ).props('flat round dense color=primary').classes('text-xs').style('margin-left:-4px')

                        with ui.row().classes('w-full items-center gap-4 q-mb-sm'):
                            switch_visual = ui.checkbox('Exibição Visual (TV)', value=True).props('dark').classes('text-xs text-white')
                            switch_voice = ui.checkbox('Fala (Voz)', value=True).props('dark').classes('text-xs text-white')
                            switch_sound = ui.checkbox('Efeito Sonoro', value=True).props('dark').classes('text-xs text-white')
                        
                        # Diálogo de Edição de Alerta Horário
                        with ui.dialog() as edit_dialog:
                            with theme.card_base().classes('q-pa-md').style('min-width: 400px;'):
                                with ui.column().classes('w-full gap-4'):
                                    ui.label('✏️ Editar Alerta Agendado').classes('text-lg font-bold text-white')
                                    ui.separator().style('background-color: rgba(255,255,255,0.1);')
                                    
                                    edit_time = ui.input('Hora', placeholder='07:30').props('dark dense outlined mask=##:##').classes('w-full')
                                    edit_title = ui.input('Título', placeholder='Aviso').props('dark dense outlined').classes('w-full')
                                    edit_msg = ui.input('Mensagem', placeholder='Texto do Alerta').props('dark dense outlined').classes('w-full')
                                    edit_sound = ui.select(som_opcoes, label='Som').props('dark dense outlined').classes('w-full')
                                    
                                    with ui.row().classes('w-full items-center gap-2'):
                                        edit_visual = ui.checkbox('Exibição Visual (TV)', value=True).props('dark').classes('text-xs text-white')
                                        edit_voice = ui.checkbox('Fala (Voz)', value=True).props('dark').classes('text-xs text-white')
                                        edit_sound_enabled = ui.checkbox('Efeito Sonoro', value=True).props('dark').classes('text-xs text-white')
                                    
                                    alerta_editando_id = ui.label('').classes('hidden')
                                    
                                    def salvar_edicao():
                                        a_id = alerta_editando_id.text
                                        time_val = edit_time.value.strip()
                                        title_val = edit_title.value.strip()
                                        msg_val = edit_msg.value.strip()
                                        
                                        if not time_val or len(time_val) < 5:
                                            ui.notify('Digite o horário no formato HH:MM (ex: 07:30)', color='red')
                                            return
                                            
                                        c_config = load_alerts_config()
                                        for idx, item in enumerate(c_config.get('custom_alerts', [])):
                                            if item.get('id') == a_id:
                                                c_config['custom_alerts'][idx] = {
                                                    'id': a_id,
                                                    'time': time_val,
                                                    'title': title_val,
                                                    'message': msg_val,
                                                    'sound': edit_sound.value,
                                                    'visual_alert': edit_visual.value,
                                                    'voice_enabled': edit_voice.value,
                                                    'sound_enabled': edit_sound_enabled.value,
                                                    'enabled': item.get('enabled', True)
                                                }
                                                break
                                        save_alerts_config(c_config)
                                        ui.notify('Alerta atualizado com sucesso!', color='success')
                                        edit_dialog.close()
                                        render_custom_alerts_list.refresh()
                                        
                                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                                        ui.button('Cancelar', on_click=edit_dialog.close).props('outline dense color=grey')
                                        ui.button('Salvar', on_click=salvar_edicao).props('unelevated dense color=primary')

                        alerta_duplicar_item = [None]
                        with ui.dialog() as duplicate_dialog:
                            with theme.card_base().classes('q-pa-md').style('min-width: 320px;'):
                                with ui.column().classes('w-full gap-4'):
                                    ui.label('👯 Duplicar Alerta Agendado').classes('text-md font-bold text-white')
                                    ui.separator().style('background-color: rgba(255,255,255,0.1);')
                                    
                                    dup_time = ui.input('Novo Horário', placeholder='07:30').props('dark dense outlined mask=##:##').classes('w-full')
                                    
                                    def salvar_duplicacao():
                                        time_val = dup_time.value.strip()
                                        if not time_val or len(time_val) < 5:
                                            ui.notify('Digite o horário no formato HH:MM (ex: 07:30)', color='red')
                                            return
                                        ref_item = alerta_duplicar_item[0]
                                        if not ref_item:
                                            return
                                        
                                        import uuid
                                        c_config = load_alerts_config()
                                        novo = {
                                            'id': str(uuid.uuid4())[:8],
                                            'time': time_val,
                                            'title': ref_item.get('title', ''),
                                            'message': ref_item.get('message', ''),
                                            'sound': ref_item.get('sound', 'info'),
                                            'visual_alert': ref_item.get('visual_alert', True),
                                            'voice_enabled': ref_item.get('voice_enabled', True),
                                            'sound_enabled': ref_item.get('sound_enabled', True),
                                            'enabled': True
                                        }
                                        c_config.setdefault('custom_alerts', []).append(novo)
                                        save_alerts_config(c_config)
                                        ui.notify('Alerta duplicado com sucesso!', color='success')
                                        duplicate_dialog.close()
                                        render_custom_alerts_list.refresh()
                                    
                                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                                        ui.button('Cancelar', on_click=duplicate_dialog.close).props('outline dense color=grey')
                                        ui.button('Duplicar', on_click=salvar_duplicacao).props('unelevated dense color=primary')
                                        
                        def abrir_duplicar(alerta_item):
                            alerta_duplicar_item[0] = alerta_item
                            dup_time.value = alerta_item['time']
                            duplicate_dialog.open()

                        @ui.refreshable
                        def render_custom_alerts_list():
                            curr_config = load_alerts_config()
                            alerts = curr_config.get("custom_alerts", [])
                            
                            with ui.column().classes('w-full gap-2 border border-white/5 q-pa-sm rounded bg-black/10').style('max-height: 150px; overflow-y: auto;'):
                                if not alerts:
                                    ui.label('Sem alertas horários agendados.').classes('text-xs italic text-grey-5 text-center w-full py-2')
                                else:
                                    for a in alerts:
                                        with ui.row().classes('w-full justify-between items-center no-wrap py-1 border-b border-white/5'):
                                            with ui.row().classes('items-center gap-2 col-grow min-w-0'):
                                                ui.label(a['time']).classes('text-xs text-amber-5 bold')
                                                with ui.column().classes('gap-0 min-w-0'):
                                                    ui.label(f"{a['title']}: {a['message']}").classes('text-xs text-white break-words')
                                                    opts = []
                                                    if a.get('visual_alert', True): opts.append('📺 TV')
                                                    if a.get('voice_enabled', True): opts.append('🗣️ Voz')
                                                    if a.get('sound_enabled', True): opts.append('🔊 Som')
                                                    opts_str = " | ".join(opts) if opts else "Silencioso"
                                                    ui.label(f"Som: {som_opcoes.get(a['sound'], a['sound'])} ({opts_str})").classes('text-[9px] text-grey-5')
                                            
                                            def excluir_alerta(a_id):
                                                c_config = load_alerts_config()
                                                c_config['custom_alerts'] = [item for item in c_config['custom_alerts'] if item.get('id') != a_id]
                                                save_alerts_config(c_config)
                                                ui.notify('Alerta agendado excluído!', color='success')
                                                render_custom_alerts_list.refresh()
                                                
                                            def carregar_e_abrir_editar(alerta_item=a):
                                                alerta_editando_id.set_text(alerta_item['id'])
                                                edit_time.value = alerta_item['time']
                                                edit_title.value = alerta_item['title']
                                                edit_msg.value = alerta_item['message']
                                                edit_sound.value = alerta_item['sound'] if alerta_item['sound'] in som_opcoes else 'info'
                                                edit_visual.value = alerta_item.get('visual_alert', True)
                                                edit_voice.value = alerta_item.get('voice_enabled', True)
                                                edit_sound_enabled.value = alerta_item.get('sound_enabled', True)
                                                edit_dialog.open()

                                            with ui.row().classes('items-center gap-1'):
                                                ui.button(
                                                    icon='play_arrow', 
                                                    on_click=lambda _, s=a['sound']: testar_som(s)
                                                ).props('flat round dense color=primary').classes('text-xs').tooltip('Testar')
                                                ui.button(
                                                    icon='content_copy', 
                                                    on_click=lambda _, a_item=a: abrir_duplicar(a_item)
                                                ).props('flat round dense color=primary').classes('text-xs').tooltip('Duplicar')
                                                ui.button(
                                                    icon='edit', 
                                                    on_click=lambda _, a_item=a: carregar_e_abrir_editar(a_item)
                                                ).props('flat round dense color=primary').classes('text-xs').tooltip('Editar')
                                                ui.button(
                                                    icon='delete', 
                                                    on_click=lambda _, a_id=a['id']: excluir_alerta(a_id)
                                                ).props('flat round dense color=red').classes('text-xs').tooltip('Excluir')
                        
                        render_custom_alerts_list()
                        
                        def cadastrar_novo_alerta():
                            time_val = input_alerta_time.value.strip()
                            title_val = input_alerta_title.value.strip()
                            msg_val = input_alerta_msg.value.strip()
                            
                            if not time_val or len(time_val) < 5:
                                ui.notify('Digite o horário no formato HH:MM (ex: 07:30)', color='red')
                                return
                                
                            import uuid
                            c_config = load_alerts_config()
                            novo = {
                                'id': str(uuid.uuid4())[:8],
                                'time': time_val,
                                'title': title_val,
                                'message': msg_val,
                                'sound': select_alerta_sound.value,
                                'visual_alert': switch_visual.value,
                                'voice_enabled': switch_voice.value,
                                'sound_enabled': switch_sound.value,
                                'enabled': True
                            }
                            c_config.setdefault('custom_alerts', []).append(novo)
                            save_alerts_config(c_config)
                            
                            ui.notify('Alerta agendado cadastrado com sucesso!', color='success')
                            input_alerta_time.value = ''
                            input_alerta_title.value = ''
                            input_alerta_msg.value = ''
                            switch_visual.value = True
                            switch_voice.value = True
                            switch_sound.value = True
                            render_custom_alerts_list.refresh()
                            
                        ui.button(
                            'Adicionar Alerta Agendado', 
                            icon='add', 
                            on_click=cadastrar_novo_alerta
                        ).props('unelevated color=amber-9 text-color=black w-full dense').classes('bold')

            # --- ABA 4: MODELOS DE MENSAGENS DOS MODAIS ---
            with ui.tab_panel('templates').classes('bg-transparent q-pa-none gap-6'):
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('chat', size='2rem').style(f'color: {THEME["accent"]}')
                            ui.label('Modelos de Mensagens (Modais)').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                        ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                        
                        ui.label('Personalize o formato do texto exibido nos modais de alertas do Modo TV. Use {message} para indicar onde a mensagem dinâmica do sistema será inserida.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                        
                        template_inputs = {}
                        default_templates = alerts_config.get("message_templates", {})
                        
                        # Renderiza campos de texto para cada template existente
                        for key, val in default_templates.items():
                            with ui.row().classes('w-full items-center justify-between gap-2 border-b border-white/5 py-2'):
                                with ui.column().classes('gap-0 w-1/3'):
                                    ui.label(key).classes('text-xs text-white font-bold')
                                    ui.label('Exemplo: ' + val.replace('{message}', 'Texto do Alerta')).classes('text-[9px] text-grey-5')
                                
                                input_field = ui.input(
                                    value=val
                                ).props('dark dense outlined').classes('text-xs col-grow')
                                template_inputs[key] = input_field

            # --- ABA 5: NOTIFICAÇÕES TELEGRAM ---
            with ui.tab_panel('telegram').classes('bg-transparent q-pa-none gap-6'):
                with ui.column().classes('w-full gap-6'):
                    
                    # 1. Minhas Preferências (Painel Pessoal)
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('person', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Minhas Preferências de Notificação').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            logged_in_user = app.storage.user.get('user_data', {})
                            u_id = logged_in_user.get('id')
                            u_name = logged_in_user.get('nome', 'Operador').upper()
                            
                            if not u_id:
                                ui.label('Efetue o login para gerenciar suas preferências.').classes('text-grey italic text-xs')
                            else:
                                from notifications_manager import get_user_preferences, save_user_preferences
                                user_prefs = get_user_preferences(u_id)
                                
                                ui.label(f'Operador Logado: {u_name}').classes('text-xs text-amber-5 font-bold')
                                
                                silence_switch = ui.switch(
                                    '🔇 Silenciar todas as notificações', 
                                    value=user_prefs.get('silence_all', False)
                                ).props('dark')
                                
                                with ui.column().classes('w-full gap-2 q-pl-md border-l border-white/5') as sub_pref_container:
                                    pref_new_user = ui.checkbox('🔔 Nova Solicitação de Cadastro', value=user_prefs.get('notify_new_user', True)).props('dark')
                                    pref_aviso = ui.checkbox('📢 Aviso Crítico na TV', value=user_prefs.get('notify_aviso', True)).props('dark')
                                    pref_saude = ui.checkbox('🏥 Internação Hospitalar (Saúde)', value=user_prefs.get('notify_saude', True)).props('dark')
                                    pref_escala = ui.checkbox('👮 Alertas de Escala Diária', value=user_prefs.get('notify_escala', True)).props('dark')
                                
                                # Desabilita as opções finas se "Silenciar todas" estiver ativo
                                pref_new_user.bind_enabled_from(silence_switch, 'value', backward=lambda x: not x)
                                pref_aviso.bind_enabled_from(silence_switch, 'value', backward=lambda x: not x)
                                pref_saude.bind_enabled_from(silence_switch, 'value', backward=lambda x: not x)
                                pref_escala.bind_enabled_from(silence_switch, 'value', backward=lambda x: not x)
                                
                                def salvar_minhas_prefs():
                                    new_prefs = {
                                        "silence_all": bool(silence_switch.value),
                                        "notify_new_user": bool(pref_new_user.value),
                                        "notify_aviso": bool(pref_aviso.value),
                                        "notify_saude": bool(pref_saude.value),
                                        "notify_escala": bool(pref_escala.value)
                                    }
                                    save_user_preferences(u_id, new_prefs)
                                    ui.notify('Preferências salvas com sucesso!', color='positive')
                                    
                                silence_switch.on('change', salvar_minhas_prefs)
                                pref_new_user.on('change', salvar_minhas_prefs)
                                pref_aviso.on('change', salvar_minhas_prefs)
                                pref_saude.on('change', salvar_minhas_prefs)
                                pref_escala.on('change', salvar_minhas_prefs)
                                
                    # 2. Configuração Global (Apenas para Admins e Supervisores)
                    role = logged_in_user.get('role', 'compel')
                    if role in ('admin', 'supervisor'):
                        with theme.card_base().classes('w-full q-pa-md'):
                            with ui.column().classes('w-full gap-4'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('admin_panel_settings', size='2rem').style(f'color: {THEME["accent"]}')
                                    ui.label('Configuração Global de Notificações').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                                ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                                
                                ui.label('Gerencie quais notificações cada militar vinculado receberá no Telegram.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                                
                                @ui.refreshable
                                def render_global_preferences_table():
                                    db_c = get_db_connection()
                                    users = []
                                    if db_c:
                                        try:
                                            res = db_c.table('Users').select('*').execute()
                                            users = res.data or []
                                        except Exception:
                                            pass
                                    if not users:
                                        # Mock
                                        users = [
                                            {'id': '1', 'username': 'admin', 'nome': 'CALAÇA', 'role': 'admin', 'telegram_id': '123456789'},
                                            {'id': '2', 'username': 'supervisor', 'nome': 'AMANDA', 'role': 'supervisor', 'telegram_id': '987654321'},
                                        ]
                                        
                                    from notifications_manager import get_user_preferences, save_user_preferences
                                    
                                    with ui.column().classes('w-full gap-3 max-h-[300px] overflow-y-auto q-pr-xs'):
                                        for u in users:
                                            user_tg = u.get('telegram_id') or ''
                                            user_lbl = f"{u['nome'].upper()} ({u['role'].upper()})"
                                            
                                            with ui.row().classes('w-full items-center justify-between border-b border-white/5 py-2 hover:bg-white/5 px-2 rounded'):
                                                with ui.column().classes('gap-0 w-[160px]'):
                                                    ui.label(user_lbl).classes('text-white text-xs font-bold')
                                                    if user_tg:
                                                        ui.label(f'ID: {user_tg}').classes('text-[10px] text-cyan-5 font-mono')
                                                    else:
                                                        ui.label('Não Vinculado').classes('text-[10px] text-grey-6 italic')
                                                        
                                                if user_tg:
                                                    u_prefs = get_user_preferences(u['id'])
                                                    # Checkboxes
                                                    with ui.row().classes('gap-4 items-center'):
                                                        cb_silence = ui.checkbox('Silenciar', value=u_prefs.get('silence_all', False)).props('dark dense')
                                                        
                                                        cb_nu = ui.checkbox('Novo Cadastro', value=u_prefs.get('notify_new_user', True)).props('dark dense')
                                                        cb_av = ui.checkbox('Aviso TV', value=u_prefs.get('notify_aviso', True)).props('dark dense')
                                                        cb_sd = ui.checkbox('Saúde', value=u_prefs.get('notify_saude', True)).props('dark dense')
                                                        cb_es = ui.checkbox('Escala', value=u_prefs.get('notify_escala', True)).props('dark dense')
                                                        
                                                        # Bindings
                                                        cb_nu.bind_enabled_from(cb_silence, 'value', backward=lambda x: not x)
                                                        cb_av.bind_enabled_from(cb_silence, 'value', backward=lambda x: not x)
                                                        cb_sd.bind_enabled_from(cb_silence, 'value', backward=lambda x: not x)
                                                        cb_es.bind_enabled_from(cb_silence, 'value', backward=lambda x: not x)
                                                        
                                                        def make_change_handler(user_id=u['id'], cb_s=cb_silence, cb_n=cb_nu, cb_a=cb_av, cb_h=cb_sd, cb_e=cb_es):
                                                            def on_change():
                                                                n_prefs = {
                                                                    "silence_all": bool(cb_s.value),
                                                                    "notify_new_user": bool(cb_n.value),
                                                                    "notify_aviso": bool(cb_a.value),
                                                                    "notify_saude": bool(cb_h.value),
                                                                    "notify_escala": bool(cb_e.value)
                                                                }
                                                                save_user_preferences(user_id, n_prefs)
                                                            return on_change
                                                            
                                                        handler = make_change_handler()
                                                        cb_silence.on('change', handler)
                                                        cb_nu.on('change', handler)
                                                        cb_av.on('change', handler)
                                                        cb_sd.on('change', handler)
                                                        cb_es.on('change', handler)
                                                else:
                                                    ui.label('Associe o Telegram ID no painel de operadores primeiro.').classes('text-[10px] text-grey italic')
                                                    
                                render_global_preferences_table()
                                
                    # 3. Envio de Mensagem Privada Nominal (Chat Direto)
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('send', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Enviar Notificação Nominal Privada').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            ui.label('Selecione um militar para enviar uma notificação personalizada privada via bot do Telegram.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                            
                            db_c = get_db_connection()
                            users_with_tg = []
                            if db_c:
                                try:
                                    res = db_c.table('Users').select('*').execute()
                                    if res.data:
                                        users_with_tg = [u for u in res.data if u.get('telegram_id')]
                                except Exception:
                                    pass
                                    
                            opcoes_envio = {
                                str(u['telegram_id']): f"{u['nome'].upper()} (ID: {u['telegram_id']})"
                                for u in users_with_tg
                            } if users_with_tg else {"123456789": "CALAÇA (Mock)"}
                            
                            sel_militar_envio = ui.select(opcoes_envio, label='Selecione o Militar').props('dark dense outlined w-full').classes('w-full')
                            txt_mensagem_privada = ui.input('Mensagem do Alerta', placeholder='Ex: Favor comparecer à Comissaria urgente.').props('dark dense outlined w-full').classes('w-full')
                            
                            def enviar_privada():
                                tg_id = sel_militar_envio.value
                                msg_txt = txt_mensagem_privada.value.strip()
                                if not tg_id or not msg_txt:
                                    ui.notify('Selecione o militar e digite a mensagem!', color='warning')
                                    return
                                    
                                try:
                                    from notifications_manager import send_notification_to_user
                                    import asyncio
                                    
                                    asyncio.create_task(send_notification_to_user(tg_id, f"✉️ **Mensagem Direta — SisCOMCA**\n\n{msg_txt}"))
                                    ui.notify('Mensagem enviada com sucesso no privado!', color='positive')
                                    txt_mensagem_privada.value = ''
                                except Exception as ex:
                                    ui.notify(f'Erro ao enviar: {ex}', color='red')
                                    
                            ui.button(
                                '⚡ Enviar Mensagem Direta', on_click=enviar_privada
                            ).props('unelevated no-caps').style(
                                f'background:{THEME["accent"]}; color:#000; font-weight:700;'
                            ).classes('w-full')

                    # 4. Solicitações de Acesso Pendentes (Apenas para Admins e Supervisores)
                    if role in ('admin', 'supervisor'):
                        with theme.card_base().classes('w-full q-pa-md q-mt-4'):
                            with ui.column().classes('w-full gap-4'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('assignment_ind', size='2rem').style(f'color: {THEME["accent"]}')
                                    ui.label('Solicitações de Acesso Pendentes').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                                ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                                
                                @ui.refreshable
                                def render_pending_requests_tab():
                                    db_c = get_db_connection()
                                    reqs = []
                                    if db_c:
                                        try:
                                            res_req = db_c.table('RegistrationRequests').select('*').eq('status', 'pending').execute()
                                            reqs = res_req.data or []
                                        except Exception as e:
                                            print(f"[CONFIG REQ ERR] {e}")
                                    
                                    if not reqs:
                                        ui.label('Não há solicitações pendentes no momento.').classes('italic text-xs text-grey-5')
                                    else:
                                        with ui.column().classes('w-full gap-3'):
                                            for r in reqs:
                                                with ui.row().classes('w-full items-center justify-between border-b border-white/5 py-2 hover:bg-white/5 px-2 rounded'):
                                                    with ui.column().classes('gap-0'):
                                                        ui.label(r.get('nome_completo', '').upper()).classes('text-white text-xs font-bold')
                                                        ui.label(f"Email: {r.get('email', '')} | Guerra: {r.get('nome_guerra', '').upper()}").classes('text-[10px] text-grey-5')
                                                    
                                                    # Ações rápidas
                                                    with ui.row().classes('gap-2 items-center'):
                                                        def make_approve_handler(req_id=r['id'], req_email=r['email'], req_guerra=r['nome_guerra']):
                                                            def approve():
                                                                try:
                                                                    db_c.table('RegistrationRequests').update({'status': 'approved'}).eq('id', req_id).execute()
                                                                    db_c.table('Users').upsert({
                                                                        'id': req_id,
                                                                        'username': req_email.split('@')[0],
                                                                        'nome': req_guerra.upper(),
                                                                        'role': 'compel'
                                                                    }, on_conflict='id').execute()
                                                                    try:
                                                                        from database import confirm_supabase_user
                                                                        confirm_supabase_user(req_id)
                                                                    except Exception as conf_err:
                                                                        print(f"[CONFIRM ERR] {conf_err}")
                                                                    
                                                                    # Notifica o usuário aprovado via Telegram
                                                                    try:
                                                                        user_res = db_c.table('Users').select('telegram_id, nome').eq('id', req_id).execute()
                                                                        if user_res.data and user_res.data[0].get('telegram_id'):
                                                                            from notifications_manager import notify_telegram
                                                                            tg_id = str(user_res.data[0]['telegram_id'])
                                                                            nome_aprovado = user_res.data[0].get('nome', req_guerra).upper()
                                                                            msg_tg = (
                                                                                f"✅ *Acesso ao SisCOMCA Aprovado!*\n\n"
                                                                                f"Olá, *{nome_aprovado}*! Seu acesso foi aprovado pelo administrador.\n\n"
                                                                                f"🔑 Papel atribuído: `compel`\n"
                                                                                f"📱 Você já pode usar o bot normalmente.\n"
                                                                                f"🌐 Acesse também o sistema web para operações avançadas."
                                                                            )
                                                                            notify_telegram(msg_tg, "system", specific_user_id=req_id)
                                                                    except Exception as notif_err:
                                                                        print(f"[CONFIG NOTIFY APPROVED ERR] {notif_err}")

                                                                    ui.notify('Solicitação aprovada!', color='success')
                                                                    render_pending_requests_tab.refresh()
                                                                except Exception as ex:
                                                                    ui.notify(f'Erro ao aprovar: {ex}', color='red')
                                                            return approve
                                                            
                                                        def make_reject_handler(req_id=r['id']):
                                                            def reject():
                                                                try:
                                                                    db_c.table('RegistrationRequests').update({'status': 'rejected'}).eq('id', req_id).execute()
                                                                    ui.notify('Solicitação rejeitada.', color='warning')
                                                                    render_pending_requests_tab.refresh()
                                                                except Exception as ex:
                                                                    ui.notify(f'Erro ao rejeitar: {ex}', color='red')
                                                            return reject
                                                        
                                                        ui.button('Rejeitar', on_click=make_reject_handler()).props('outline dense color=red').classes('text-xs')
                                                        ui.button('Aprovar', on_click=make_approve_handler()).props('unelevated dense color=green').classes('text-xs text-white')
                                
                                render_pending_requests_tab()

            # --- ABA 6: CONFIGURAÇÃO DE VOZ (TTS) ---
            with ui.tab_panel('tts').classes('bg-transparent q-pa-none gap-6'):
                with ui.column().classes('w-full gap-6'):
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('record_voice_over', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Configuração de Text-To-Speech (TTS)').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            ui.label('Gerencie o motor de voz utilizado para sintetizar mensagens nos painéis e TVs.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                            
                            tts_engines_opts = {
                                'basic': 'Basic SpeechSynthesis (Navegador / Offline)',
                                'google': 'Google Tradutor (Online / Gratuito)',
                                'elevenlabs': 'ElevenLabs (Neural / API Key)',
                                'piper': 'Piper TTS (Local / Executável)'
                            }
                            input_tts_engine = ui.select(tts_engines_opts, label='Motor TTS Ativo', value=current_configs.get('tts_engine', 'basic')).props('dark dense outlined w-full').classes('w-full')
                            
                    # ElevenLabs Config Card
                    with theme.card_base().classes('w-full q-pa-md') as elevenlabs_card:
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('api', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Configuração do ElevenLabs').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            input_elevenlabs_api_key = ui.input('ElevenLabs API Key', value=current_configs.get('elevenlabs_api_key', ''), password=True, password_toggle_button=True).props('dark dense outlined w-full').classes('w-full')
                            input_elevenlabs_voice_id = ui.input('Voice ID', value=current_configs.get('elevenlabs_voice_id', 'N2lVS1w4EtoT3dr4eOWO')).props('dark dense outlined w-full').classes('w-full')
                    
                    # Piper Config Card
                    with theme.card_base().classes('w-full q-pa-md') as piper_card:
                        with ui.column().classes('w-full gap-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('terminal', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Configuração do Piper (TTS Local)').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                            
                            input_tts_piper_path = ui.input('Caminho para o piper.exe', value=current_configs.get('tts_piper_path', 'piper.exe')).props('dark dense outlined w-full').classes('w-full')
                            input_tts_piper_voice = ui.input('Modelo de voz (.onnx)', value=current_configs.get('tts_piper_voice', 'pt_BR-fabricio-medium')).props('dark dense outlined w-full').classes('w-full')
                            
                    elevenlabs_card.bind_visibility_from(input_tts_engine, 'value', backward=lambda x: x == 'elevenlabs')
                    piper_card.bind_visibility_from(input_tts_engine, 'value', backward=lambda x: x == 'piper')

            # --- ABA 7: TIPOS DE AÇÕES (PONTOS/NOTAS) ---
            with ui.tab_panel('tipos_acao').classes('bg-transparent q-pa-none gap-6'):
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center justify-between w-full'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('calculate', size='2rem').style(f'color: {THEME["accent"]}')
                                ui.label('Tipos de Ação e Pesos de Notas').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                            
                            def abrir_dialogo_novo_tipo():
                                d_tipo = ui.dialog()
                                with d_tipo, ui.card().classes('w-[380px] q-pa-md bg-slate-900 border border-cyan-5'):
                                    ui.label('🆕 NOVO TIPO DE AÇÃO').classes('text-white text-sm font-black cyber-title q-mb-xs')
                                    nome_inp = ui.input('Nome do Tipo de Ação', placeholder='Ex: Elogio de Serviço').props('dark outlined dense w-full').classes('w-full')
                                    pontos_inp = ui.input('Pontuação / Peso (Ex: 0.5 ou -0.3)', value='0.0').props('dark outlined dense w-full').classes('w-full q-mt-xs')
                                    
                                    def salvar_novo():
                                        name = nome_inp.value.strip().upper()
                                        if not name:
                                            ui.notify('Nome é obrigatório.', color='red')
                                            return
                                        try:
                                            pts = float(pontos_inp.value)
                                        except ValueError:
                                            ui.notify('Pontuação deve ser um número decimal válido.', color='red')
                                            return
                                        
                                        db_c = get_db_connection()
                                        if db_c:
                                            try:
                                                db_c.table('Tipos_Acao').insert({'nome': name, 'pontuacao': pts, 'ativo': True}).execute()
                                                ui.notify('Novo tipo de ação criado!', color='success')
                                                d_tipo.close()
                                                render_tipos_list.refresh()
                                                data_service.clear_cache()
                                            except Exception as err:
                                                ui.notify(f'Erro ao salvar: {err}', color='red')
                                        else:
                                            ui.notify('Offline: Operação indisponível sem conexão com banco.', color='warning')
                                    
                                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                                        ui.button('Cancelar', on_click=d_tipo.close).props('flat color=grey no-caps')
                                        ui.button('Salvar', on_click=salvar_novo).props('unelevated color=cyan-9 text-color=white no-caps')
                                d_tipo.open()
                                
                            ui.button('Adicionar Tipo de Ação', icon='add', on_click=abrir_dialogo_novo_tipo).props('unelevated dense color=cyan-9 text-color=white no-caps').classes('cyber-glow')
                        
                        ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                        
                        busca_tipos = ui.input(placeholder='🔍 Buscar tipos de ação...').props('dark dense outlined').classes('w-full max-w-sm')
                        
                        @ui.refreshable
                        def render_tipos_list():
                            db_c = get_db_connection()
                            tipos_data = []
                            if db_c:
                                try:
                                    res = db_c.table('Tipos_Acao').select('*').order('nome').execute()
                                    tipos_data = res.data if res.data else []
                                except Exception as e:
                                    print(f"Erro ao carregar tipos: {e}")
                            
                            query = busca_tipos.value.strip().upper() if busca_tipos.value else ''
                            filtered_tipos = [t for t in tipos_data if query in str(t.get('nome','')).upper()] if query else tipos_data
                            
                            # Separar por grupos e ordenar em ordem alfabética
                            positivas = sorted([t for t in filtered_tipos if t.get('pontuacao', 0.0) > 0], key=lambda x: x.get('nome', ''))
                            neutras = sorted([t for t in filtered_tipos if t.get('pontuacao', 0.0) == 0], key=lambda x: x.get('nome', ''))
                            negativas = sorted([t for t in filtered_tipos if t.get('pontuacao', 0.0) < 0], key=lambda x: x.get('nome', ''))
                            
                            with ui.column().classes('w-full gap-4').style('max-height: 500px; overflow-y: auto;'):
                                if not filtered_tipos:
                                    ui.label('Nenhum tipo de ação encontrado.').classes('text-xs italic text-grey-5 text-center w-full py-4')
                                else:
                                    def render_grupo(titulo, cor, lista):
                                        if not lista:
                                            return
                                        with ui.column().classes('w-full gap-1 q-mb-md'):
                                            with ui.row().classes('items-center gap-2 q-mb-xs'):
                                                ui.badge(text=titulo, color=cor).classes('text-[10px] font-bold')
                                            for t in lista:
                                                t_nome = t['nome']
                                                t_pts = t.get('pontuacao', 0.0)
                                                pts_color = 'text-green-400' if t_pts > 0 else ('text-red-400' if t_pts < 0 else 'text-grey-4')
                                                pts_sign = f"+{t_pts}" if t_pts > 0 else str(t_pts)
                                                
                                                with ui.row().classes('w-full justify-between items-center py-2 px-2 border-b border-white/5 bg-white/[0.01] hover:bg-white/[0.03] rounded no-wrap'):
                                                    ui.label(t_nome).classes('text-xs font-bold text-white truncate col-grow')
                                                    
                                                    with ui.row().classes('items-center gap-4 shrink-0'):
                                                        ui.label(pts_sign).classes(f'text-xs font-mono font-bold {pts_color} min-w-[50px] text-right')
                                                        
                                                        def abrir_dialogo_editar(item=t):
                                                            d_edit = ui.dialog()
                                                            with d_edit, ui.card().classes('w-[380px] q-pa-md bg-slate-900 border border-cyan-5'):
                                                                ui.label('✏️ EDITAR TIPO DE AÇÃO').classes('text-white text-sm font-black cyber-title q-mb-xs')
                                                                nome_inp = ui.input('Nome do Tipo de Ação', value=item['nome']).props('dark outlined dense w-full').classes('w-full')
                                                                pontos_inp = ui.input('Pontuação / Peso', value=str(item.get('pontuacao', 0.0))).props('dark outlined dense w-full').classes('w-full q-mt-xs')
                                                                
                                                                def salvar_edicao():
                                                                    name = nome_inp.value.strip().upper()
                                                                    if not name:
                                                                        ui.notify('Nome é obrigatório.', color='red')
                                                                        return
                                                                    try:
                                                                        pts = float(pontos_inp.value)
                                                                    except ValueError:
                                                                        ui.notify('Pontuação deve ser um número decimal válido.', color='red')
                                                                        return
                                                                    
                                                                    db_u = get_db_connection()
                                                                    if db_u:
                                                                        try:
                                                                            db_u.table('Tipos_Acao').update({'nome': name, 'pontuacao': pts}).eq('id', item['id']).execute()
                                                                            ui.notify('Tipo de ação editado com sucesso!', color='success')
                                                                            d_edit.close()
                                                                            render_tipos_list.refresh()
                                                                            data_service.clear_cache()
                                                                        except Exception as err:
                                                                            ui.notify(f'Erro ao salvar: {err}', color='red')
                                                                    else:
                                                                            ui.notify('Offline: Operação indisponível.', color='warning')
                                                                            
                                                                with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                                                                    ui.button('Cancelar', on_click=d_edit.close).props('flat color=grey no-caps')
                                                                    ui.button('Salvar', on_click=salvar_edicao).props('unelevated color=cyan-9 text-color=white no-caps')
                                                            d_edit.open()
                                                            
                                                        def excluir_tipo(item=t):
                                                            db_d = get_db_connection()
                                                            if db_d:
                                                                try:
                                                                    db_d.table('Tipos_Acao').delete().eq('id', item['id']).execute()
                                                                    ui.notify('Tipo de ação excluído!', color='success')
                                                                    render_tipos_list.refresh()
                                                                    data_service.clear_cache()
                                                                except Exception as err:
                                                                    ui.notify(f'Erro ao excluir: {err}', color='red')
                                                            else:
                                                                ui.notify('Offline: Operação indisponível.', color='warning')
                                                                
                                                        ui.button(icon='edit', on_click=abrir_dialogo_editar).props('flat round dense color=cyan').classes('text-xs')
                                                        ui.button(icon='delete', on_click=excluir_tipo).props('flat round dense color=red').classes('text-xs')
                                    
                                    render_grupo('🟢 POSITIVAS', 'green', positivas)
                                    render_grupo('⚪ NEUTRAS', 'grey', neutras)
                                    render_grupo('🔴 NEGATIVAS', 'red', negativas)
                        
                        busca_tipos.on('input', render_tipos_list.refresh)
                        render_tipos_list()

            # --- ABA 8: GERENCIAR PERMISSÕES ---
            with ui.tab_panel('permissoes').classes('bg-transparent q-pa-none gap-6'):
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('admin_panel_settings', size='2rem').style(f'color: {THEME["accent"]}')
                            ui.label('Gerenciar Permissões por Função').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                        ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                        
                        ui.label('Defina quais perfis (Cargos/Funções) têm acesso às operações do painel e do Telegram Bot.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                        
                        @ui.refreshable
                        def render_permissions_editor():
                            db_c = get_db_connection()
                            perms_data = []
                            if db_c:
                                try:
                                    res = db_c.table('Permissions').select('*').execute()
                                    perms_data = res.data if res.data else []
                                except Exception as e:
                                    print(f"Erro ao carregar permissões: {e}")
                            
                            with ui.column().classes('w-full gap-4'):
                                if not perms_data:
                                    ui.label('Nenhuma regra de permissão cadastrada no Supabase.').classes('text-xs italic text-grey-5 text-center w-full py-4')
                                else:
                                    # Separar as permissões
                                    general_perms = sorted([p for p in perms_data if not p['feature_key'].startswith('menu_')], key=lambda x: x.get('feature_name', x.get('description', x['feature_key'])))
                                    menu_perms = sorted([p for p in perms_data if p['feature_key'].startswith('menu_')], key=lambda x: x.get('feature_name', x.get('description', x['feature_key'])))
                                    
                                    def render_permissions_group(title, subtitle, list_data):
                                        if not list_data:
                                            return
                                        with ui.column().classes('w-full gap-2 q-mb-md'):
                                            with ui.row().classes('items-center gap-2 q-mt-sm q-mb-xs'):
                                                ui.badge(text=title, color='cyan-9').classes('text-xs font-bold')
                                                ui.label(subtitle).classes('text-xs text-grey-5 italic')
                                            for p in list_data:
                                                f_key = p['feature_key']
                                                f_desc = p.get('feature_name', p.get('description', f_key))
                                                f_roles = [r.strip().lower() for r in str(p.get('allowed_roles', '')).split(',') if r.strip()]
                                                
                                                with ui.column().classes('w-full border border-white/5 q-pa-sm rounded bg-black/10 hover:bg-black/20 gap-2'):
                                                    with ui.row().classes('w-full items-baseline justify-between no-wrap gap-2'):
                                                        ui.label(f_desc).classes('text-xs font-bold text-white')
                                                        ui.label(f_key).classes('text-[10px] text-grey-5 font-mono shrink-0')
                                                    
                                                    with ui.row().classes('w-full gap-4 items-center'):
                                                        roles_list = ['admin', 'supervisor', 'operador', 'comcia', 'compel', 'aluno', 'ajosca']
                                                        checkboxes = {}
                                                        for role in roles_list:
                                                            is_checked = role in f_roles
                                                            checkboxes[role] = ui.checkbox(role.upper(), value=is_checked).props('dark dense').classes('text-xs text-grey-3')
                                                        
                                                        def make_save_handler(key=f_key, cbs=checkboxes):
                                                            def save_perms():
                                                                selected_roles = [r for r, cb in cbs.items() if cb.value]
                                                                roles_str = ",".join(selected_roles)
                                                                db_u = get_db_connection()
                                                                if db_u:
                                                                    try:
                                                                        db_u.table('Permissions').update({'allowed_roles': roles_str}).eq('feature_key', key).execute()
                                                                        ui.notify(f'Permissões para "{key}" atualizadas!', color='success')
                                                                        data_service.clear_cache()
                                                                    except Exception as err:
                                                                        ui.notify(f'Erro ao salvar: {err}', color='red')
                                                                else:
                                                                    ui.notify('Offline: Operação indisponível.', color='warning')
                                                            return save_perms
                                                        
                                                        ui.button('Aplicar', on_click=make_save_handler()).props('unelevated dense color=cyan-10 text-color=white no-caps text-xs').classes('ml-auto px-3')
                                    
                                    render_permissions_group('🛡️ OPERAÇÕES E REGRAS GERAIS', 'Permissões e capacidades dentro das telas do sistema e bot', general_perms)
                                    render_permissions_group('📋 ACESSO AOS MENUS LATERAIS', 'Definição de quais menus de navegação aparecem para cada perfil', menu_perms)
                        
                        render_permissions_editor()

        # --- AÇÕES ---
        # --- AÇÕES ---
        with ui.row().classes('w-full justify-end gap-3 q-mt-md'):
            def restaurar_padroes():
                input_base.value = DEFAULT_CONFIGS['linha_base_conceito']
                input_max_acoes.value = DEFAULT_CONFIGS['impacto_max_acoes']
                input_peso_acad.value = DEFAULT_CONFIGS['peso_academico']
                input_fator.value = DEFAULT_CONFIGS['fator_adaptacao']
                input_ini.value = DEFAULT_CONFIGS['periodo_adaptacao_inicio']
                input_fim.value = DEFAULT_CONFIGS['periodo_adaptacao_fim']
                input_polling.value = DEFAULT_CONFIGS['tempo_polling_tv']
                input_cabecalho_tv.value = DEFAULT_CONFIGS['cabecalho_tv_title']
                input_subcabecalho_tv.value = DEFAULT_CONFIGS['cabecalho_tv_subtitle']
                input_sunset_tv.value = DEFAULT_CONFIGS['cabecalho_tv_sunset_time']
                input_cargos_escala.value = DEFAULT_CONFIGS['cargos_escala_lista']
                input_unlock_code.value = DEFAULT_CONFIGS['codigo_desbloqueio_tv']
                input_alerta_tv.value = DEFAULT_CONFIGS['tempo_alerta_tv']
                input_telegram_token.value = DEFAULT_CONFIGS['telegram_bot_token']
                input_tts_engine.value = DEFAULT_CONFIGS['tts_engine']
                input_elevenlabs_api_key.value = DEFAULT_CONFIGS['elevenlabs_api_key']
                input_elevenlabs_voice_id.value = DEFAULT_CONFIGS['elevenlabs_voice_id']
                input_tts_piper_path.value = DEFAULT_CONFIGS['tts_piper_path']
                input_tts_piper_voice.value = DEFAULT_CONFIGS['tts_piper_voice']
                
                # Reseta sons e templates para o padrão
                save_alerts_config(DEFAULT_ALERTS_CONFIG)
                
                for key, val in DEFAULT_ALERTS_CONFIG.get('message_templates', {}).items():
                    if key in template_inputs:
                        template_inputs[key].value = val
                        
                for key, val in DEFAULT_ALERTS_CONFIG.get('sound_mappings', {}).items():
                    if key in sound_dropdowns:
                        sound_dropdowns[key].value = val
                
                render_custom_alerts_list.refresh()
                ui.notify('Padrões restaurados na tela. Salve para persistir.', color='info')

            async def salvar_configs():
                try:
                    float(input_base.value)
                    float(input_max_acoes.value)
                    float(input_peso_acad.value)
                    float(input_fator.value)
                    int(input_polling.value)
                    float(input_alerta_tv.value)
                except ValueError:
                    ui.notify('Os campos numéricos devem conter valores decimais válidos, o Tempo de Alerta deve ser um número e o Polling deve ser um número inteiro.', color='red')
                    return

                db_conn = get_admin_db_connection() or get_db_connection()
                
                novas_configs = [
                    {'chave': 'linha_base_conceito', 'valor': str(input_base.value)},
                    {'chave': 'impacto_max_acoes', 'valor': str(input_max_acoes.value)},
                    {'chave': 'peso_academico', 'valor': str(input_peso_acad.value)},
                    {'chave': 'fator_adaptacao', 'valor': str(input_fator.value)},
                    {'chave': 'periodo_adaptacao_inicio', 'valor': str(input_ini.value)},
                    {'chave': 'periodo_adaptacao_fim', 'valor': str(input_fim.value)},
                    {'chave': 'tempo_polling_tv', 'valor': str(input_polling.value)},
                    {'chave': 'cabecalho_tv_title', 'valor': str(input_cabecalho_tv.value)},
                    {'chave': 'cabecalho_tv_subtitle', 'valor': str(input_subcabecalho_tv.value)},
                    {'chave': 'cabecalho_tv_sunset_time', 'valor': str(input_sunset_tv.value)},
                    {'chave': 'cargos_escala_lista', 'valor': str(input_cargos_escala.value)},
                    {'chave': 'codigo_desbloqueio_tv', 'valor': str(input_unlock_code.value)},
                    {'chave': 'tempo_alerta_tv', 'valor': str(input_alerta_tv.value)},
                    {'chave': 'telegram_bot_token', 'valor': str(input_telegram_token.value)},
                    {'chave': 'tts_engine', 'valor': str(input_tts_engine.value)},
                    {'chave': 'elevenlabs_api_key', 'valor': str(input_elevenlabs_api_key.value)},
                    {'chave': 'elevenlabs_voice_id', 'valor': str(input_elevenlabs_voice_id.value)},
                    {'chave': 'tts_piper_path', 'valor': str(input_tts_piper_path.value)},
                    {'chave': 'tts_piper_voice', 'valor': str(input_tts_piper_voice.value)}
                ]

                # Salva as configurações de som
                new_alerts_config = load_alerts_config()
                new_alerts_config['tv_alert_vocativo'] = input_tv_vocativo.value
                for key in sound_dropdowns:
                    new_alerts_config['sound_mappings'][key] = sound_dropdowns[key]
                    
                # Salva os templates customizados de mensagens
                new_alerts_config['message_templates'] = {}
                for key in template_inputs:
                    new_alerts_config['message_templates'][key] = template_inputs[key].value
                
                save_alerts_config(new_alerts_config)

                if db_conn:
                    try:
                        for item in novas_configs:
                            db_conn.table('Config').upsert(item, on_conflict='chave').execute()
                        ui.notify('Configurações salvas no Supabase com sucesso!', color='success')
                    except Exception as err:
                        ui.notify(f'Erro ao salvar no Supabase: {err}. Salvando apenas localmente.', color='warning')
                else:
                    ui.notify('Modo Offline: Configurações salvas temporariamente na sessão.', color='warning')

                data_service.clear_cache()

                try:
                    import telegram_bot
                    await telegram_bot.restart_bot()
                except Exception as bot_err:
                    print(f"[CONFIG] Erro ao reiniciar bot: {bot_err}", flush=True)

            ui.button('Restaurar Padrões', on_click=restaurar_padroes).props('outline dense').style(f'color: {THEME["text_dim"]}; border-color: rgba(255, 255, 255, 0.2);')
            ui.button('Salvar Configurações', on_click=salvar_configs).props('unelevated dense').style(f'background: {THEME["primary"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow px-4')
