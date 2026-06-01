from nicegui import ui
import pandas as pd
from datetime import datetime
import theme
from database import get_db_connection
from services import data_service
import conselho_avaliacao

THEME = theme.colors

def get_student_statuses() -> dict:
    """Retorna dicionário mapeando numero_interno para o status de presença/saúde de hoje."""
    statuses = {}
    db_conn = get_db_connection()
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Carrega presença de hoje
    presenca_list = []
    if db_conn:
        try:
            res_pres = db_conn.table('presenca_ausencia').select('*').eq('data', data_hoje).execute()
            presenca_list = res_pres.data if res_pres.data else []
        except Exception as e:
            print(f"[TURMAS] Erro ao carregar presença: {e}")
    else:
        # Mock offline
        presenca_list = [
            {'numero_interno': 'M-1-101', 'presente': True, 'motivo_ausencia': ''},
            {'numero_interno': 'M-2-207', 'presente': False, 'motivo_ausencia': 'Serviço externo'}
        ]

    for p in presenca_list:
        ni = str(p['numero_interno'])
        if p['presente']:
            statuses[ni] = {'status': '🟢 Presente', 'detalhe': ''}
        else:
            motivo = p.get('motivo_ausencia') or 'Ausente'
            statuses[ni] = {'status': '🔴 Ausente', 'detalhe': motivo}

    # 2. Carrega enfermaria/saúde ativa (sobrescreve presença se ativo)
    enfermaria_list = []
    if db_conn:
        try:
            # Seleciona registros de saúde ativos (onde status não é 'Alta')
            res_enf = db_conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
            enfermaria_list = res_enf.data if res_enf.data else []
        except Exception as e:
            print(f"[TURMAS] Erro ao carregar enfermaria: {e}")
    else:
        # Mock offline
        enfermaria_list = [
            {'numero_interno': 'M-1-102', 'categoria': 'enfermaria', 'status': 'Em Observação', 'motivo': 'Gripe'},
            {'numero_interno': 'M-2-208', 'categoria': 'dispensa', 'status': 'Dispensado', 'motivo': 'Lesão no joelho'}
        ]

    for e in enfermaria_list:
        ni = str(e['numero_interno'])
        cat = e.get('categoria') or 'enfermaria'
        motivo = e.get('motivo') or e.get('observacao') or ''
        
        if cat == 'enfermaria':
            statuses[ni] = {'status': '🏥 Baixado', 'detalhe': f"Enfermaria: {motivo}"}
        elif cat == 'dispensa':
            statuses[ni] = {'status': '📝 Dispensado', 'detalhe': f"Dispensa: {motivo}"}
        elif cat == 'licenca':
            statuses[ni] = {'status': '✈️ Licenciado', 'detalhe': f"Licença: {motivo}"}

    return statuses


def render_page():
    state = {'selected_pelotao': None, 'search_query': ''}

    @ui.refreshable
    def render_content():
        # 1. Carrega todos os alunos processados com conceito final
        try:
            _, _, alunos_df, _ = conselho_avaliacao.process_turma_data("Todos", "Número Interno")
        except Exception as e:
            print(f"[TURMAS] Erro ao processar dados de alunos: {e}")
            alunos_df = pd.DataFrame()

        if alunos_df.empty:
            theme.section_header('Gestão de Turmas', 'Configuração de Turmas e Pelotões')
            with ui.column().classes('w-full q-pa-lg items-center justify-center bg-[#131a26] border border-red-500/30 rounded-xl'):
                ui.icon('warning', color='warning', size='4rem')
                ui.label('Nenhum aluno encontrado ou banco de dados offline.').classes('text-grey text-lg font-bold q-mt-md')
            return

        # 2. Carrega statuses de presença/saúde de hoje
        statuses_hoje = get_student_statuses()

        # Agrupamento por pelotão
        pelotoes = sorted(alunos_df['pelotao'].dropna().unique())
        
        theme.section_header('Gestão de Turmas', 'Análise de Efetivo, Presença e Conceitos por Pelotão')

        # --- GRID DE CARDS DOS PELOTÕES ---
        with ui.grid(columns='1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4').classes('w-full gap-6'):
            for pel in pelotoes:
                df_pel = alunos_df[alunos_df['pelotao'] == pel]
                total_alunos = len(df_pel)
                
                # Cálculo da média de conceito final
                media_conceito = df_pel['conceito_final'].mean()
                media_conceito_str = f"{media_conceito:.2f}" if not pd.isna(media_conceito) else "N/A"
                
                # Contagem de presentes e baixados hoje
                presentes = 0
                saude_ativos = 0
                for _, row in df_pel.iterrows():
                    ni = str(row['numero_interno'])
                    status_info = statuses_hoje.get(ni, {'status': '⚪ Sem Registro'})
                    if 'Presente' in status_info['status']:
                        presentes += 1
                    elif any(s in status_info['status'] for s in ['Baixado', 'Dispensado', 'Licenciado']):
                        saude_ativos += 1
                
                # Define se este card está selecionado
                is_selected = state['selected_pelotao'] == pel
                
                # Estilos do Tema Cyber Military
                if is_selected:
                    card_style = 'background: #131a26; border: 1px solid #00e5ff; box-shadow: 0 0 15px rgba(0, 229, 255, 0.25); border-radius: 8px;'
                else:
                    card_style = 'background: #131a26; border: 1px solid rgba(0, 229, 255, 0.15); border-radius: 8px;'
                
                with ui.card().classes('w-full q-pa-md transition-all cursor-pointer hover:border-cyan-400/40').style(card_style).on('click', lambda p=pel: select_pelotao(p)):
                    with ui.column().classes('w-full gap-2'):
                        with ui.row().classes('w-full items-center justify-between'):
                            ui.label(pel).classes('text-white text-lg font-bold tracking-wider cyber-title')
                            if is_selected:
                                ui.badge('Selecionado', color='primary').props('text-color=black font-bold')
                        ui.separator().props('dark').style('background-color: rgba(0, 229, 255, 0.1);')
                        
                        with ui.column().classes('gap-1 text-xs text-grey-3 w-full'):
                            with ui.row().classes('w-full justify-between'):
                                ui.label('👥 Efetivo Total:')
                                ui.label(str(total_alunos)).classes('font-bold text-white')
                            with ui.row().classes('w-full justify-between'):
                                ui.label('📈 Méd. Conceito:')
                                color_med = 'text-green-4' if media_conceito >= 8.5 else ('text-amber-4' if media_conceito >= 7.0 else 'text-red-4')
                                ui.label(media_conceito_str).classes(f'font-bold {color_med}')
                            with ui.row().classes('w-full justify-between'):
                                ui.label('✅ Presentes Hoje:')
                                ui.label(f"{presentes} / {total_alunos}").classes('font-bold text-white')
                            with ui.row().classes('w-full justify-between'):
                                ui.label('🏥 Fila de Saúde:')
                                color_saude = 'text-red-4 font-bold' if saude_ativos > 0 else 'text-grey-4'
                                ui.label(f"{saude_ativos} ativo(s)").classes(color_saude)

        # --- SEÇÃO DRILLDOWN: DETALHES DO PELOTÃO SELECIONADO ---
        if state['selected_pelotao']:
            selected = state['selected_pelotao']
            df_det = alunos_df[alunos_df['pelotao'] == selected].copy()
            
            # Filtro de busca se digitado
            if state['search_query']:
                query = state['search_query'].lower()
                df_det = df_det[
                    df_det['nome_guerra'].str.lower().str.contains(query) |
                    df_det['numero_interno'].str.lower().str.contains(query) |
                    df_det['nome_completo'].str.lower().str.contains(query)
                ]
            
            with theme.card_base().classes('w-full q-pa-md q-mt-md'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('w-full justify-between items-center wrap gap-4'):
                        with ui.row().classes('items-center gap-3'):
                            ui.icon('class', color='primary', size='2.2rem')
                            with ui.column().classes('gap-0'):
                                ui.label(f"Integrantes do Pelotão {selected}").classes('text-white text-lg font-bold cyber-title')
                                ui.label(f"Exibindo {len(df_det)} alunos").classes('text-grey-5 text-xs')
                        
                        # Barra de busca interna
                        ui.input(
                            label='Pesquisar Aluno', 
                            value=state['search_query'],
                            on_change=lambda e: update_search(e.value)
                        ).props('dark dense outlined').classes('w-64')
                    
                    ui.separator().props('dark').style('background-color: rgba(0, 229, 255, 0.1);')
                    
                    # Tabela de alunos
                    if df_det.empty:
                        ui.label('Nenhum aluno encontrado para o termo pesquisado.').classes('text-grey-5 italic text-sm')
                    else:
                        with ui.column().classes('w-full gap-1 overflow-x-auto'):
                            # Cabeçalho da tabela
                            with ui.row().classes('w-full q-py-xs text-grey-4 text-xs font-bold bg-[#0b0f19] border border-cyan-900/30 rounded q-px-sm items-center'):
                                ui.label('NI').classes('w-20 font-mono')
                                ui.label('Nome de Guerra').classes('col-grow')
                                ui.label('Conceito Disciplinar').classes('w-36 text-center')
                                ui.label('Méd. Acadêmica').classes('w-24 text-center')
                                ui.label('Status Hoje').classes('w-44')

                            # Linhas dos alunos
                            for _, row in df_det.iterrows():
                                ni = str(row['numero_interno'])
                                c_final = row['conceito_final']
                                m_acad = row.get('media_academica', 0.0)
                                status_info = statuses_hoje.get(ni, {'status': '⚪ Sem Registro', 'detalhe': ''})
                                
                                # Formata cores do conceito
                                color_c = 'bg-green-950/20 text-green-4 border-green-500/30' if c_final >= 8.5 else (
                                    'bg-amber-950/20 text-amber-4 border-amber-500/30' if c_final >= 7.0 else
                                    'bg-red-950/20 text-red-4 border-red-500/30'
                                )
                                
                                with ui.row().classes('w-full q-py-sm hover:bg-white/5 border-b border-cyan-900/10 rounded q-px-sm items-center text-xs text-grey-3'):
                                    ui.label(ni).classes('w-20 text-white font-mono')
                                    with ui.column().classes('col-grow gap-0'):
                                        ui.label(row['nome_guerra']).classes('text-white font-bold')
                                        ui.label(row['nome_completo']).classes('text-grey-5 text-[10px] gt-xs')
                                    
                                    # Conceito badge
                                    with ui.row().classes('w-36 justify-center'):
                                        ui.label(f"{c_final:.2f}").classes(f'px-2 py-0.5 rounded border text-[11px] font-bold {color_c}')
                                    
                                    # Média Acadêmica
                                    ui.label(f"{m_acad:.2f}").classes('w-24 text-center text-white')
                                    
                                    # Status Hoje
                                    with ui.column().classes('w-44 gap-0'):
                                        ui.label(status_info['status']).classes('font-bold text-[11px]')
                                        if status_info['detalhe']:
                                            ui.label(status_info['detalhe']).classes('text-grey-5 text-[9px] truncate')

    def select_pelotao(pelotao_name):
        state['selected_pelotao'] = pelotao_name
        render_content.refresh()

    def update_search(val):
        state['search_query'] = val
        render_content.refresh()

    # Container principal da página
    with ui.column().classes('w-full q-pa-lg gap-6'):
        render_content()
