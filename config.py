from nicegui import ui, app
import theme
from database import get_db_connection
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
    'cargos_escala_lista': 'INSPETOR DO DIA, SUPERVISOR, AJOSCA, OSCA, OFICIAL DE SERVIÇO, ENFERMEIRO DE SERVIÇO',
    'codigo_desbloqueio_tv': '1234',
    'telegram_bot_token': ''
}

def render_page():
    def testar_som(som_key: str):
        """Executa a síntese de som diretamente no navegador do operador atual usando Web Audio API."""
        if som_key == 'silent':
            ui.notify('Silencioso ativado para este som.', color='warning')
            return
            
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
            if (ctx) {{
                if (ctx.state === 'suspended') {{
                    ctx.resume();
                }}
                const type = '{som_key}';
                const customMp3Url = "/assets/sounds/" + type + ".mp3";
                
                if (type.startsWith('naval_bell_')) {{
                    let count = 1;
                    if (type === 'naval_bell_singela') {{
                        count = 1;
                    }} else if (type === 'naval_bell_dobrada') {{
                        count = 2;
                    }} else {{
                        count = parseInt(type.split('_')[2]) || 1;
                    }}
                    
                    const singleMp3Url = "/assets/sounds/bell_single.mp3";
                    const doubleMp3Url = "/assets/sounds/bell_double.mp3";
                    
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

                    fetch(singleMp3Url, {{ method: 'HEAD' }})
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
                    fetch(customMp3Url, {{ method: 'HEAD' }})
                        .then(res => {{
                            if (res.ok) {{
                                let audio = new Audio(customMp3Url);
                                audio.volume = 1.0;
                                audio.play().catch(() => {{}});
                            }} else {{
                                playDefaultSynthesized(type);
                            }}
                        }})
                        .catch(() => {{
                            playDefaultSynthesized(type);
                        }});
                        
                    function playDefaultSynthesized(type) {{
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

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Configurações', 'Configurações de Variáveis Globais e Parâmetros de Conceito')

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
                            
                        input_ordem_text.value = ''
                        render_orders_list.refresh()
                    
                    ui.button(
                        'Adicionar Aviso', 
                        icon='add', 
                        on_click=adicionar_ordem
                    ).props('unelevated color=amber-9 text-color=black w-full dense').classes('bold')

            # --- CARD 5: PERSONALIZAÇÃO DE SONS DOS ALERTAS ---
            from alerts_manager import load_alerts_config, save_alerts_config
            alerts_config = load_alerts_config()
            sound_mappings = alerts_config.get("sound_mappings", {})
            
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
                    
                    for ocorrencia_nome, som_atual in sound_mappings.items():
                        with ui.row().classes('w-full items-center justify-between gap-2 border-b border-white/5 py-1'):
                            ui.label(ocorrencia_nome).classes('text-xs text-white')
                            with ui.row().classes('items-center gap-2'):
                                dropdown = ui.select(
                                    som_opcoes, 
                                    value=som_atual
                                ).props('dark dense outlined').classes('text-xs min-w-[200px]')
                                sound_dropdowns[ocorrencia_nome] = dropdown
                                
                                # Botão para reproduzir e testar o som correspondente localmente
                                def make_test_cb(key=ocorrencia_nome):
                                    return lambda: testar_som(sound_dropdowns[key].value)
                                
                                ui.button(
                                    icon='play_arrow', 
                                    on_click=make_test_cb(ocorrencia_nome)
                                ).props('flat round dense color=primary').classes('text-xs')

            # --- CARD 6: ALERTAS AGENDADOS E SINOS NAVAIS ---
            with theme.card_base().classes('w-full q-pa-md'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('alarm', size='2rem').style(f'color: {THEME["accent"]}')
                        ui.label('Sinos Navais e Alertas Agendados').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                    ui.separator().style(f'background-color: rgba(0, 229, 255, 0.15);')
                    
                    # Switch do Sino Automático
                    bell_enabled_switch = ui.switch(
                        '🔔 Toques automáticos do Sino da Marinha (a cada 30min)', 
                        value=alerts_config.get('bell_enabled', True)
                    ).props('dark').classes('text-xs font-bold text-white')
                    
                    ui.separator().style('background-color: rgba(255,255,255,0.05); height: 1px;')
                    ui.label('Agendar Novo Alerta Horário:').classes('text-xs font-bold text-white')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        input_alerta_time = ui.input('Hora', placeholder='07:30').props('dark dense outlined mask=##:## w-1/5').classes('text-xs')
                        input_alerta_title = ui.input('Título', placeholder='Aviso').props('dark dense outlined w-1/4').classes('text-xs')
                        input_alerta_msg = ui.input('Mensagem', placeholder='Instrução Geral no Pátio').props('dark dense outlined col-grow').classes('text-xs')
                        
                        alerta_som_opcoes = {
                            'info': 'Chime Premium',
                            'success': 'Sucesso',
                            'warning': 'Aviso',
                            'alert': 'Alerta',
                            'submarine_sonar': 'Sonar Submarino',
                            'morse_sos': 'Morse SOS',
                            'naval_horn': 'Buzina Navio',
                            'naval_bell_singela': 'Sino 1 Batida',
                            'naval_bell_dobrada': 'Sino 2 Batidas',
                            'naval_bell_4': 'Sino 4 Batidas',
                            'naval_bell_8': 'Sino 8 Batidas',
                            'silent': 'Silencioso'
                        }
                        select_alerta_sound = ui.select(alerta_som_opcoes, value='info').props('dark dense outlined').classes('text-xs min-w-[120px]')
                        ui.button(
                            icon='play_arrow', 
                            on_click=lambda: testar_som(select_alerta_sound.value)
                        ).props('flat round dense color=primary').classes('text-xs').style('margin-left:-4px')
                    
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
                                                ui.label(f"Som: {som_opcoes.get(a['sound'], a['sound'])}").classes('text-[9px] text-grey-5')
                                        
                                        def excluir_alerta(a_id=a['id']):
                                            c_config = load_alerts_config()
                                            c_config['custom_alerts'] = [item for item in c_config['custom_alerts'] if item.get('id') != a_id]
                                            save_alerts_config(c_config)
                                            ui.notify('Alerta agendado excluído!', color='success')
                                            render_custom_alerts_list.refresh()
                                            
                                        with ui.row().classes('items-center gap-1'):
                                            ui.button(
                                                icon='play_arrow', 
                                                on_click=lambda s=a['sound']: testar_som(s)
                                            ).props('flat round dense color=primary').classes('text-xs')
                                            ui.button(
                                                icon='delete', 
                                                on_click=excluir_alerta
                                            ).props('flat round dense color=red').classes('text-xs')
                    
                    render_custom_alerts_list()
                    
                    def cadastrar_novo_alerta():
                        time_val = input_alerta_time.value.strip()
                        title_val = input_alerta_title.value.strip() or 'Aviso'
                        msg_val = input_alerta_msg.value.strip()
                        
                        if not time_val or len(time_val) < 5:
                            ui.notify('Digite o horário no formato HH:MM (ex: 07:30)', color='red')
                            return
                        if not msg_val:
                            ui.notify('Digite o texto da mensagem do alerta.', color='red')
                            return
                            
                        import uuid
                        c_config = load_alerts_config()
                        novo = {
                            'id': str(uuid.uuid4())[:8],
                            'time': time_val,
                            'title': title_val,
                            'message': msg_val,
                            'sound': select_alerta_sound.value,
                            'enabled': True
                        }
                        c_config.setdefault('custom_alerts', []).append(novo)
                        save_alerts_config(c_config)
                        
                        ui.notify('Alerta agendado cadastrado com sucesso!', color='success')
                        input_alerta_time.value = ''
                        input_alerta_title.value = ''
                        input_alerta_msg.value = ''
                        render_custom_alerts_list.refresh()
                        
                    ui.button(
                        'Adicionar Alerta Agendado', 
                        icon='add', 
                        on_click=cadastrar_novo_alerta
                    ).props('unelevated color=amber-9 text-color=black w-full dense').classes('bold')

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
                input_cargos_escala.value = DEFAULT_CONFIGS['cargos_escala_lista']
                input_unlock_code.value = DEFAULT_CONFIGS['codigo_desbloqueio_tv']
                input_telegram_token.value = DEFAULT_CONFIGS['telegram_bot_token']
                
                # Reseta sons para o padrão
                save_alerts_config(DEFAULT_ALERTS_CONFIG)
                render_custom_alerts_list.refresh()
                ui.notify('Padrões restaurados na tela. Salve para persistir.', color='info')

            async def salvar_configs():
                try:
                    float(input_base.value)
                    float(input_max_acoes.value)
                    float(input_peso_acad.value)
                    float(input_fator.value)
                    int(input_polling.value)
                except ValueError:
                    ui.notify('Os campos numéricos devem conter valores decimais válidos e o Polling deve ser um número inteiro.', color='red')
                    return

                db_conn = get_db_connection()
                
                novas_configs = [
                    {'chave': 'linha_base_conceito', 'valor': str(input_base.value)},
                    {'chave': 'impacto_max_acoes', 'valor': str(input_max_acoes.value)},
                    {'chave': 'peso_academico', 'valor': str(input_peso_acad.value)},
                    {'chave': 'fator_adaptacao', 'valor': str(input_fator.value)},
                    {'chave': 'periodo_adaptacao_inicio', 'valor': str(input_ini.value)},
                    {'chave': 'periodo_adaptacao_fim', 'valor': str(input_fim.value)},
                    {'chave': 'tempo_polling_tv', 'valor': str(input_polling.value)},
                    {'chave': 'cabecalho_tv_title', 'valor': str(input_cabecalho_tv.value)},
                    {'chave': 'cargos_escala_lista', 'valor': str(input_cargos_escala.value)},
                    {'chave': 'codigo_desbloqueio_tv', 'valor': str(input_unlock_code.value)},
                    {'chave': 'telegram_bot_token', 'valor': str(input_telegram_token.value)}
                ]

                # Salva as configurações de som e o switch do sino
                new_alerts_config = load_alerts_config()
                new_alerts_config['bell_enabled'] = bell_enabled_switch.value
                for key in sound_dropdowns:
                    new_alerts_config['sound_mappings'][key] = sound_dropdowns[key].value
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
