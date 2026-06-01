from nicegui import ui, app
import pandas as pd
import theme
from services import data_service

THEME = theme.colors

def render_page():
    # 1. Carrega dados de Alunos
    alunos_df = data_service.get_alunos_data()
    
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Relatórios de Ensino', 'Indicadores de Desempenho e Distribuição de Notas')
        
        if alunos_df.empty:
            with theme.card_base().classes('w-full q-pa-lg items-center justify-center text-center'):
                ui.icon('warning', color='warning', size='4rem')
                ui.label('SEM ALUNOS CADASTRADOS').classes('cyber-title text-md font-bold q-mt-md').style(f'color: {THEME["text_dim"]}')
                ui.label('Cadastre alunos no sistema para visualizar os relatórios acadêmicos.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
            return

        # Filtra alunos fora da baixa
        df_ativos = alunos_df[alunos_df['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()
        
        # Converte as médias acadêmicas para numérico de forma segura
        df_ativos['media_academica_num'] = pd.to_numeric(df_ativos['media_academica'], errors='coerce').fillna(0.0)

        # 2. Resumos Gerais (KPIs)
        media_geral_corpo = df_ativos['media_academica_num'].mean()
        max_nota = df_ativos['media_academica_num'].max()
        min_nota = df_ativos['media_academica_num'].max() # dummy to find the actual min that is > 0
        min_nota_val = df_ativos[df_ativos['media_academica_num'] > 0]['media_academica_num'].min()
        if pd.isna(min_nota_val):
            min_nota_val = 0.0
            
        abaixo_media = len(df_ativos[df_ativos['media_academica_num'] < 7.0])
        total_alunos = len(df_ativos)
        pct_aprovados = ((total_alunos - abaixo_media) / total_alunos) * 100 if total_alunos > 0 else 0.0

        # Renderiza os widgets KPI superiores
        with ui.grid(columns='1 sm:grid-cols-2 md:grid-cols-4').classes('w-full gap-4'):
            def kpi_widget(label, value, color, icon):
                with theme.card_base().classes('q-pa-md items-center text-center border').style(f'border-top: 3px solid {color} !important;'):
                    ui.icon(icon, color='grey-5', size='1.5rem').classes('q-mb-xs')
                    ui.label(value).classes('text-2xl font-black font-mono').style(f'color: {color};')
                    ui.label(label).classes('text-[10px] font-bold tracking-wider').style(f'color: {THEME["text_dim"]}')
                    
            kpi_widget('MÉDIA DO CORPO', f"{media_geral_corpo:.2f}", THEME['primary'], 'school')
            kpi_widget('ALTA DA TURMA', f"{max_nota:.2f}", THEME['success'], 'trending_up')
            kpi_widget('MÍNIMA LANÇADA', f"{min_nota_val:.2f}", '#ffb300', 'trending_down')
            kpi_widget('APROVEITAMENTO', f"{pct_aprovados:.1f}%", THEME['success'] if pct_aprovados >= 80 else THEME['danger'], 'percent')

        # --- ÁREA CENTRAL DO DASHBOARD ---
        with ui.row().classes('w-full gap-6 no-wrap wrap-mobile items-stretch'):
            
            # --- CARD ESQUERDA: DESEMPENHO POR PELOTÃO (GRÁFICO TÁTICO) ---
            with theme.card_base().classes('col-grow md:w-1/2 q-pa-md flex flex-col'):
                ui.label('📊 DESEMPENHO POR PELOTÃO').classes('cyber-title text-xs q-mb-md').style(f'color: {THEME["primary"]}')
                
                # Agrupa médias por pelotão
                pelotao_avg = df_ativos.groupby('pelotao')['media_academica_num'].mean().reset_index()
                pelotao_avg = pelotao_avg.sort_values(by='media_academica_num', ascending=False)
                
                with ui.column().classes('w-full gap-4 q-py-sm col-grow justify-center'):
                    if pelotao_avg.empty:
                        ui.label('Sem dados de pelotões.').classes('italic text-xs text-grey-5')
                    else:
                        for _, row in pelotao_avg.iterrows():
                            pel_name = row['pelotao'].upper()
                            pel_avg = row['media_academica_num']
                            # Percentual proporcional a 10 de nota máxima
                            pct = (pel_avg / 10.0) * 100
                            
                            # Cor baseada na nota do pelotao
                            bar_color = THEME['success'] if pel_avg >= 8.0 else (THEME['primary'] if pel_avg >= 7.0 else THEME['danger'])
                            
                            with ui.column().classes('w-full gap-1'):
                                with ui.row().classes('w-full justify-between items-center text-xs'):
                                    ui.label(pel_name).classes('font-bold text-white')
                                    ui.label(f"{pel_avg:.2f} / 10.0").classes('font-mono font-bold').style(f'color: {bar_color};')
                                
                                # Barra de Progresso Customizada
                                with ui.element('div').classes('w-full bg-black/40 rounded-full border').style('height: 10px; border-color: rgba(255, 255, 255, 0.05)'):
                                    ui.element('div').classes('rounded-full transition-all duration-500').style(
                                        f'height: 100%; width: {pct}%; background-color: {bar_color};'
                                    )

            # --- CARD DIREITA: DISTRIBUIÇÃO E NÍVEIS ---
            with theme.card_base().classes('col-grow md:w-1/2 q-pa-md flex flex-col justify-between'):
                ui.label('📈 NÍVEL DE APRENDIZADO (CORPO DE ALUNOS)').classes('cyber-title text-xs q-mb-md').style(f'color: {THEME["primary"]}')
                
                # Classifica alunos por faixas
                excelente = len(df_ativos[df_ativos['media_academica_num'] >= 9.0])
                bom = len(df_ativos[(df_ativos['media_academica_num'] >= 8.0) & (df_ativos['media_academica_num'] < 9.0)])
                regular = len(df_ativos[(df_ativos['media_academica_num'] >= 7.0) & (df_ativos['media_academica_num'] < 8.0)])
                insuficiente = len(df_ativos[df_ativos['media_academica_num'] < 7.0])
                
                with ui.column().classes('w-full gap-3 justify-center col-grow'):
                    def render_level_row(title, count, pct_val, color_lbl):
                        with ui.row().classes('w-full justify-between items-center text-xs q-py-1 border-b border-gray-800/40'):
                            with ui.row().classes('items-center gap-2'):
                                ui.element('span').classes('w-2 h-2 rounded-full').style(f'background-color: {color_lbl};')
                                ui.label(title).classes('text-grey-3 font-semibold')
                            with ui.row().classes('gap-4 items-center'):
                                ui.label(f"{count} alunos").classes('font-bold text-white')
                                ui.label(f"{pct_val:.1f}%").classes('font-mono font-bold').style(f'color: {color_lbl}; width: 50px; text-align: right;')
                                
                    render_level_row('Excelente (Aproveitamento >= 9.0)', excelente, (excelente/total_alunos)*100, THEME['success'])
                    render_level_row('Bom (Aproveitamento 8.0 a 8.9)', bom, (bom/total_alunos)*100, THEME['primary'])
                    render_level_row('Regular (Aproveitamento 7.0 a 7.9)', regular, (regular/total_alunos)*100, '#ffb300')
                    render_level_row('Abaixo da Média (Aproveitamento < 7.0)', insuficiente, (insuficiente/total_alunos)*100, THEME['danger'])

        # --- RANKINGS ACADÊMICOS (DESTAQUES E ALERTA) ---
        with ui.row().classes('w-full gap-6 no-wrap wrap-mobile'):
            
            # DESTAQUES ACADÊMICOS (Top 5)
            with theme.card_base().classes('col-grow p-6'):
                ui.label('🏆 DESTAQUES ACADÊMICOS (TOP 5)').classes('cyber-title text-xs q-mb-md').style(f'color: {THEME["success"]}')
                
                df_top = df_ativos.sort_values(by='media_academica_num', ascending=False).head(5)
                with ui.column().classes('w-full gap-3'):
                    if df_top.empty:
                        ui.label('Sem dados.').classes('italic text-xs text-grey-5')
                    else:
                        for idx, (_, row) in enumerate(df_top.iterrows()):
                            with ui.row().classes('w-full items-center justify-between text-xs py-1 border-b border-gray-800/40'):
                                with ui.row().classes('items-center gap-3'):
                                    ui.label(f"#{idx+1}").classes('font-mono font-black').style(f'color: {THEME["success"]}; width: 24px;')
                                    ui.label(f"{row['numero_interno']} — {row['nome_guerra'].upper()}").classes('font-bold text-white')
                                    ui.badge(row['pelotao'], color='grey-9').classes('text-[9px]')
                                ui.label(f"{row['media_academica_num']:.2f}").classes('font-mono font-bold').style(f'color: {THEME["success"]}')

            # ATENÇÃO ACADÊMICA (Notas mais baixas)
            with theme.card_base().classes('col-grow p-6'):
                ui.label('⚠️ MILITARES EM ALERTA (MÉDIAS MAIS BAIXAS)').classes('cyber-title text-xs q-mb-md').style(f'color: {THEME["danger"]}')
                
                df_low = df_ativos.sort_values(by='media_academica_num', ascending=True).head(5)
                with ui.column().classes('w-full gap-3'):
                    if df_low.empty:
                        ui.label('Sem dados.').classes('italic text-xs text-grey-5')
                    else:
                        for idx, (_, row) in enumerate(df_low.iterrows()):
                            # Só exibe se for abaixo de 7.5 ou se for as menores notas mesmo
                            with ui.row().classes('w-full items-center justify-between text-xs py-1 border-b border-gray-800/40'):
                                with ui.row().classes('items-center gap-3'):
                                    ui.label(f"🚨").classes('font-mono').style('width: 24px;')
                                    ui.label(f"{row['numero_interno']} — {row['nome_guerra'].upper()}").classes('font-bold text-white')
                                    ui.badge(row['pelotao'], color='grey-9').classes('text-[9px]')
                                ui.label(f"{row['media_academica_num']:.2f}").classes('font-mono font-bold').style(f'color: {THEME["danger"]}')
