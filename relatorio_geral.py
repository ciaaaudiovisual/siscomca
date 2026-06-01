from nicegui import ui, app
import pandas as pd
import theme
from services import data_service
from conselho_avaliacao import process_turma_data

THEME = theme.colors

@ui.refreshable
def render_relatorio_geral_content():
    # 1. Processa dados completos do Corpo de Alunos (Conceito, Acadêmico e Previsão Final)
    opcoes, id_list, df_processed, acoes_com_pontos = process_turma_data("Todos", "Conceito (Maior > Menor)")
    
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Relatório Geral', 'Quadro Consolidado de Desempenho Escolar e Rankings')
        
        if df_processed.empty:
            with theme.card_base().classes('w-full q-pa-lg items-center justify-center text-center'):
                ui.icon('warning', color='warning', size='4rem')
                ui.label('SEM DADOS PROCESSADOS').classes('cyber-title text-md font-bold q-mt-md').style(f'color: {THEME["text_dim"]}')
                ui.label('Cadastre alunos e ocorrências para compor o Relatório Geral.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
            return

        # 2. Quadro de Honra (Honor Roll)
        # Critério: Conceito >= 9.0 e Média Acadêmica >= 8.5
        df_honra = df_processed[
            (df_processed['conceito_final'] >= 9.0) & 
            (df_processed['media_academica_num'] >= 8.5)
        ].sort_values(by='classificacao_final_prevista', ascending=False)
        
        with theme.card_base().classes('w-full q-pa-md border').style('border: 1px solid rgba(212, 175, 55, 0.4) !important; background: linear-gradient(135deg, #131a26 0%, #1e1d15 100%);'):
            with ui.row().classes('w-full items-center gap-3 q-mb-xs'):
                ui.icon('military_tech', color='amber', size='2rem').classes('animate-pulse')
                ui.label('🎖️ QUADRO DE HONRA (HONOR ROLL)').classes('cyber-title text-sm font-bold').style('color: #D4AF37;')
            ui.label('Alunos exemplares com Conceito Militar excepcional (>= 9.0) e alto rendimento acadêmico (>= 8.5).').classes('text-[10px] q-mb-md').style(f'color: {THEME["text_dim"]}')
            
            if df_honra.empty:
                ui.label('Nenhum militar atende aos critérios do Quadro de Honra atualmente.').classes('italic text-xs text-center py-2 w-full text-grey-5')
            else:
                with ui.grid(columns='1 sm:grid-cols-2 md:grid-cols-3').classes('w-full gap-4'):
                    for idx, (_, row) in enumerate(df_honra.iterrows()):
                        foto_url = row.get('url_foto')
                        avatar_src = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else 'https://via.placeholder.com/100?text=Sem+Foto'
                        
                        with ui.card().classes('q-pa-sm border border-amber-900 bg-black/30 rounded-lg'):
                            with ui.row().classes('items-center gap-3 no-wrap'):
                                ui.avatar(size='42px').style(f"border: 2px solid #D4AF37; background-image: url('{avatar_src}'); background-size: cover; background-position: center;")
                                with ui.column().classes('gap-0 min-w-0 col-grow'):
                                    ui.label(row['nome_guerra'].upper()).classes('text-white font-black text-xs ellipsis')
                                    ui.label(f"Nº {row['numero_interno']} • {row['pelotao']}").classes('text-grey text-[9px]')
                                    with ui.row().classes('gap-2 items-center q-mt-0.5'):
                                        ui.badge(f"C: {row['conceito_final']:.2f}", color='green-9').classes('text-[9px]')
                                        ui.badge(f"A: {row['media_academica_num']:.2f}", color='blue-9').classes('text-[9px]')

        # 3. Métricas Globais (Estatísticas do Corpo)
        med_conceito = df_processed['conceito_final'].mean()
        med_academica = df_processed['media_academica_num'].mean()
        med_prevista = df_processed['classificacao_final_prevista'].mean()
        
        with ui.grid(columns='1 sm:grid-cols-3').classes('w-full gap-4 q-my-md'):
            def render_stat_box(title, val, color):
                with theme.card_base().classes('q-pa-md items-center text-center border'):
                    ui.label(f"{val:.3f}").classes('text-3xl font-black font-mono').style(f'color: {color};')
                    ui.label(title).classes('text-[10px] font-bold tracking-wider').style(f'color: {THEME["text_dim"]}')
            render_stat_box('MÉDIA CONCEITO (COMPORTAMENTO)', med_conceito, THEME['primary'])
            render_stat_box('MÉDIA ACADÊMICA (PROVAS)', med_academica, '#ffb300')
            render_stat_box('MÉDIA CLASSIFICAÇÃO FINAL PREVISTA', med_prevista, '#f8fafc')

        # 4. Rankings em Grid Duplo
        with ui.row().classes('w-full gap-6 no-wrap wrap-mobile'):
            
            # RANKING 1: COMPORTAMENTO (Conceito Final)
            with theme.card_base().classes('col-grow p-6'):
                ui.label('🛡️ CLASSIFICAÇÃO DISCIPLINAR (TOP 10)').classes('cyber-title text-xs q-mb-md').style(f'color: {THEME["primary"]}')
                df_rank_comp = df_processed.sort_values(by='conceito_final', ascending=False).head(10)
                
                with ui.column().classes('w-full gap-3'):
                    for idx, (_, row) in enumerate(df_rank_comp.iterrows()):
                        with ui.row().classes('w-full items-center justify-between text-xs py-1 border-b border-gray-800/40'):
                            with ui.row().classes('items-center gap-3'):
                                ui.label(f"#{idx+1}").classes('font-mono font-black text-primary').style('width: 24px;')
                                ui.label(f"{row['numero_interno']} — {row['nome_guerra'].upper()}").classes('font-bold text-white')
                                ui.badge(row['pelotao'], color='grey-9').classes('text-[9px]')
                            ui.label(f"{row['conceito_final']:.3f}").classes('font-mono font-bold text-primary')

            # RANKING 2: CLASSIFICAÇÃO FINAL PREVISTA
            with theme.card_base().classes('col-grow p-6'):
                ui.label('🏆 CLASSIFICAÇÃO FINAL PREVISTA (TOP 10)').classes('cyber-title text-xs q-mb-md').style(f'color: #ffb300')
                df_rank_prev = df_processed.sort_values(by='classificacao_final_prevista', ascending=False).head(10)
                
                with ui.column().classes('w-full gap-3'):
                    for idx, (_, row) in enumerate(df_rank_prev.iterrows()):
                        with ui.row().classes('w-full items-center justify-between text-xs py-1 border-b border-gray-800/40'):
                            with ui.row().classes('items-center gap-3'):
                                ui.label(f"#{idx+1}").classes('font-mono font-black').style('color: #ffb300; width: 24px;')
                                ui.label(f"{row['numero_interno']} — {row['nome_guerra'].upper()}").classes('font-bold text-white')
                                ui.badge(row['pelotao'], color='grey-9').classes('text-[9px]')
                            ui.label(f"{row['classificacao_final_prevista']:.3f}").classes('font-mono font-bold').style('color: #ffb300')

def render_page():
    render_relatorio_geral_content()
