from nicegui import ui, app
import pandas as pd
from datetime import datetime
import theme
from database import get_db_connection
from services import data_service
from alerts_manager import AlertsManager

THEME = theme.colors

@ui.refreshable
def render_revisao_content():
    db_conn = get_db_connection()
    
    # 1. Carrega dados essenciais
    core_data = data_service.get_core_data(force_refresh=True)
    alunos_df = core_data.get('alunos', pd.DataFrame())
    acoes_df = core_data.get('acoes', pd.DataFrame())
    tipos_acao_df = core_data.get('tipos_acao', pd.DataFrame())
    config_df = core_data.get('config', pd.DataFrame())
    
    if acoes_df.empty or alunos_df.empty or tipos_acao_df.empty:
        with ui.column().classes('w-full q-pa-lg items-center justify-center'):
            ui.icon('warning', color='warning', size='4rem')
            ui.label('Sem registros disciplinares para revisão.').classes('text-grey text-lg font-bold q-mt-md')
        return

    # Filtra apenas as ações pendentes
    pendentes_df = acoes_df[acoes_df['status'] == 'Pendente'].copy()
    
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Revisão de Ocorrências', 'Homologação e Aprovação de Lançamentos Disciplinares')
        
        if pendentes_df.empty:
            with theme.card_base().classes('w-full q-pa-lg items-center justify-center text-center'):
                ui.icon('check_circle', color='green', size='4rem').classes('animate-pulse')
                ui.label('NÃO HÁ OCORRÊNCIAS PENDENTES').classes('cyber-title text-md font-bold q-mt-md').style(f'color: {THEME["success"]}')
                ui.label('O corpo de alunos está em dia com as homologações disciplinares!').classes('text-xs q-mt-xs').style(f'color: {THEME["text_dim"]}')
            return

        ui.label(f"Aguardando Revisão: {len(pendentes_df)} ocorrência(s)").classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')

        # Mapeamento rápido de alunos por ID
        alunos_df['id_str'] = alunos_df['id'].astype(str)
        alunos_map = alunos_df.set_index('id_str').to_dict(orient='index')
        
        # Mapeamento rápido de tipos de ação por ID
        tipos_acao_df['id_str'] = tipos_acao_df['id'].astype(str)
        tipos_map = tipos_acao_df.set_index('id_str').to_dict(orient='index')

        # Listagem de ocorrencias pendentes
        with ui.column().classes('w-full gap-4'):
            for _, acao in pendentes_df.sort_values(by='data', ascending=False).iterrows():
                acao_id = acao['id']
                aluno_id = str(acao['aluno_id'])
                tipo_acao_id = str(acao['tipo_acao_id'])
                
                aluno_info = alunos_map.get(aluno_id, {})
                tipo_info = tipos_map.get(tipo_acao_id, {})
                
                nome_aluno = aluno_info.get('nome_guerra', 'Militar Desconhecido').upper()
                num_interno = aluno_info.get('numero_interno', 'N/A')
                pelotao = aluno_info.get('pelotao', 'Sem Pelotão')
                foto_url = aluno_info.get('url_foto')
                avatar_src = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else 'https://via.placeholder.com/100?text=Sem+Foto'
                
                nome_tipo = tipo_info.get('nome', acao.get('tipo', 'Ação')).upper()
                pontuacao = float(tipo_info.get('pontuacao', 0.0) or 0.0)
                
                # Cores baseadas na pontuação
                if pontuacao > 0:
                    pts_text = f"+{pontuacao:.1f} pts"
                    pts_color = THEME['success']
                    border_color = 'border-l-4 border-green-500'
                elif pontuacao < 0:
                    pts_text = f"-{abs(pontuacao):.1f} pts"
                    pts_color = THEME['danger']
                    border_color = 'border-l-4 border-red-500'
                else:
                    pts_text = "0.0 pts"
                    pts_color = THEME['text_dim']
                    border_color = 'border-l-4 border-gray-600'
                
                data_formatada = ""
                if acao.get('data'):
                    try:
                        data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        data_formatada = str(acao['data'])

                with ui.card().classes(f'w-full no-shadow q-pa-md transition-all hover:bg-white/5 {border_color}').style(
                    f'background: {THEME["bg_panel"]}; border-radius: 8px;'
                ):
                    with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                        
                        # Esquerda: Foto + Dados do Aluno + Detalhe da Ocorrência
                        with ui.row().classes('items-center gap-4 col-grow min-w-0'):
                            ui.avatar(size='54px').classes('border border-gray-800').style(f"background-image: url('{avatar_src}'); background-size: cover; background-position: center;")
                            with ui.column().classes('gap-1 col-grow min-w-0'):
                                # Identificação do Aluno
                                with ui.row().classes('items-center gap-2 flex-wrap'):
                                    ui.label(nome_aluno).classes('text-white font-bold text-sm')
                                    ui.badge(f"Nº {num_interno}", color='blue-9').classes('text-[10px]')
                                    ui.badge(pelotao, color='grey-9').classes('text-[10px]')
                                
                                # Tipo de Ação + Pontos
                                with ui.row().classes('items-center gap-2'):
                                    ui.label(nome_tipo).classes('text-xs font-black tracking-wider')
                                    ui.label(pts_text).style(f'color: {pts_color}; font-size: 0.8rem; font-weight: 900;')
                                
                                # Descrição do Fato Lançado
                                ui.label(acao.get('descricao', 'Sem descrição.')).classes('text-grey-3 text-xs italic break-words max-w-2xl')
                                
                                # Metadata: Data e Lançador
                                ui.label(f"Lançado em {data_formatada} por {acao.get('usuario', 'N/A')}. ").classes('text-[10px]').style(f'color: {THEME["text_dim"]}')
                        
                        # Direita: Botões de Decisão (Aprovar / Recusar)
                        with ui.row().classes('gap-2 items-center justify-end min-w-[200px]'):
                            # Ações assíncronas do banco
                            def homologar_fato(a_id=acao_id, al_nome=nome_aluno, ac_nome=nome_tipo):
                                if not db_conn:
                                    ui.notify('[OFFLINE] Simulação de homologação realizada!', color='warning')
                                    return
                                try:
                                    db_conn.table('Acoes').update({'status': 'Lançado'}).eq('id', a_id).execute()
                                    ui.notify(f"Ocorrência de {al_nome} homologada!", color='success')
                                    
                                    # Dispara alerta em tempo real para TV
                                    try:
                                        AlertsManager.trigger_alert(
                                            "Ocorrência Homologada",
                                            f"{al_nome} teve seu lançamento de {ac_nome} homologado!",
                                            "success"
                                        )
                                    except Exception:
                                        pass
                                    
                                    data_service.clear_cache()
                                    render_revisao_content.refresh()
                                except Exception as err:
                                    ui.notify(f"Erro ao aprovar: {err}", color='red')
                            
                            def recusar_fato(a_id=acao_id, al_nome=nome_aluno):
                                if not db_conn:
                                    ui.notify('[OFFLINE] Simulação de recusa realizada!', color='warning')
                                    return
                                try:
                                    db_conn.table('Acoes').delete().eq('id', a_id).execute()
                                    ui.notify(f"Ocorrência de {al_nome} descartada/excluída.", color='warning')
                                    data_service.clear_cache()
                                    render_revisao_content.refresh()
                                except Exception as err:
                                    ui.notify(f"Erro ao recusar: {err}", color='red')
                                    
                            ui.button(
                                'Aprovar', 
                                icon='check_circle', 
                                on_click=homologar_fato
                            ).props('unelevated dense no-caps color=green text-color=white').classes('q-px-md font-bold text-xs')
                            
                            ui.button(
                                'Recusar', 
                                icon='delete', 
                                on_click=recusar_fato
                            ).props('outline dense no-caps color=red').classes('q-px-md text-xs')

def render_page():
    render_revisao_content()
