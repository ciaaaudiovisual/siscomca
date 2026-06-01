from nicegui import ui, app
import pandas as pd
from datetime import datetime
import theme
from database import carregar_fila_atendimento, adicionar_fila_atendimento, atualizar_status_fila
from services import data_service

THEME = theme.colors

MOTIVOS_FILA = [
    "Atendimento Administrativo",
    "Documentação",
    "Saúde",
    "Disciplinar",
    "Financeiro",
    "Outro"
]

PRIORIDADES = {
    "Normal": "normal",
    "Alta": "alta",
    "Urgente": "urgente"
}

def render_page():
    # 1. Carrega dados essenciais
    alunos_df = data_service.get_alunos_data()
    fila_df = carregar_fila_atendimento()
    
    # Garante colunas de perfil do aluno
    if 'pelotao' not in alunos_df.columns:
        alunos_df['pelotao'] = 'Sem Pelotão'
    if 'nome_guerra' not in alunos_df.columns:
        alunos_df['nome_guerra'] = 'Desconhecido'

    # Estado local de filtragem
    state = app.storage.user.get('fila_state', {
        'search': ''
    })
    app.storage.user['fila_state'] = state

    # --- PROCESSA FILA ---
    # Divide a fila em "Aguardando" e "Em Atendimento"
    em_atendimento_list = []
    aguardando_list = []
    
    if not fila_df.empty:
        # Garante ordenação de prioridade correta
        ordem_prioridade = {'urgente': 0, 'alta': 1, 'normal': 2, 'baixa': 3}
        fila_df['prioridade_num'] = fila_df['prioridade'].map(ordem_prioridade).fillna(2)
        fila_df = fila_df.sort_values(['prioridade_num', 'hora'])
        
        for _, r in fila_df.iterrows():
            if r['status'] == 'em_atendimento':
                em_atendimento_list.append(r)
            elif r['status'] == 'aguardando':
                aguardando_list.append(r)

    # KPI stats
    total_fila = len(em_atendimento_list) + len(aguardando_list)
    total_aguardando = len(aguardando_list)
    total_atendimento = len(em_atendimento_list)
    total_urgentes = len([x for x in aguardando_list if x['prioridade'] == 'urgente'])

    # UI principal
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Fila de Atendimento', 'Controle de Fila, Entrada e Atendimento de Alunos na Secretaria')
        
        # Dashboard de Estatísticas
        kpi_row = ui.row().classes('w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4')
        with kpi_row:
            # Total Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["primary"]};'):
                ui.label('TOTAL NA FILA').classes('text-grey text-xs font-bold cyber-title')
                ui.label(str(total_fila)).classes('text-white text-2xl font-bold')
                
            # Em Atendimento Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid #ff9100;'):
                ui.label('EM ATENDIMENTO').classes('text-grey text-xs font-bold cyber-title')
                ui.label(str(total_atendimento)).classes('text-warning text-2xl font-bold')
                
            # Aguardando Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid #00e676;'):
                ui.label('AGUARDANDO').classes('text-grey text-xs font-bold cyber-title')
                ui.label(str(total_aguardando)).classes('text-success text-2xl font-bold')
                
            # Urgentes Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["danger"]};'):
                ui.label('URGENTES EM ESPERA').classes('text-grey text-xs font-bold cyber-title')
                ui.label(str(total_urgentes)).classes('text-danger text-2xl font-bold')

        # Grid principal
        with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap'):
            
            # Coluna Esquerda: Formulário de Inserção
            with ui.column().classes('w-full lg:w-5/12 gap-4'):
                ui.label('ADICIONAR MILITAR NA FILA').classes('text-white text-xs font-bold uppercase tracking-wider cyber-title')
                
                with ui.card().classes('w-full q-pa-md border border-gray-800').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
                    # Seleção do aluno
                    opcoes_alunos = {}
                    if not alunos_df.empty:
                        for _, r in alunos_df.iterrows():
                            opcoes_alunos[str(r['id'])] = f"{r['numero_interno']} - {r['nome_guerra']} ({r['pelotao']})"
                            
                    aluno_sel = ui.select(opcoes_alunos, label='Selecione o Aluno').props('dark outlined dense w-full')
                    motivo_sel = ui.select(MOTIVOS_FILA, value='Atendimento Administrativo', label='Motivo da Visão').props('dark outlined dense w-full')
                    
                    ui.label('Prioridade de Atendimento').classes('text-grey-4 text-xs font-bold q-mb-xs')
                    prioridade_sel = ui.radio(list(PRIORIDADES.keys()), value='Normal').props('dark horizontal')

                    def entrar_na_fila():
                        if not aluno_sel.value:
                            ui.notify('Selecione um aluno para entrar na fila', color='warning')
                            return
                            
                        aluno_id = aluno_sel.value
                        aluno_row = alunos_df[alunos_df['id'].astype(str) == str(aluno_id)].iloc[0]
                        
                        prioridade_val = PRIORIDADES[prioridade_sel.value]
                        
                        sucesso = adicionar_fila_atendimento(
                            numero_interno=str(aluno_row['numero_interno']),
                            nome_guerra=str(aluno_row['nome_guerra']),
                            turma=str(aluno_row['pelotao']),
                            motivo=str(motivo_sel.value),
                            prioridade=prioridade_val
                        )
                        
                        if sucesso:
                            ui.notify(f"{aluno_row['nome_guerra']} inserido na fila!", color='positive')
                            data_service.clear_cache()
                            ui.navigate.reload()
                        else:
                            ui.notify('Aluno já está na fila de atendimento', color='warning')

                    ui.button('Inserir na Fila', icon='add', on_click=entrar_na_fila).props('unelevated no-caps w-full').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;').classes('q-mt-sm cyber-glow')

            # Coluna Direita: Fila de Espera / Atendimentos Ativos
            with ui.column().classes('w-full lg:w-7/12 gap-4'):
                ui.label('PAINEL DE ATENDIMENTOS E ESPERA').classes('text-white text-xs font-bold uppercase tracking-wider cyber-title')
                
                # --- SUB-PAINEL 1: EM ATENDIMENTO ---
                ui.label('EM ATENDIMENTO').classes('text-warning text-caption font-bold tracking-widest cyber-title')
                
                if not em_atendimento_list:
                    with ui.card().classes('w-full q-pa-sm border border-dashed border-gray-800 text-center').style('background: transparent;'):
                        ui.label('Nenhum atendimento ativo no momento.').classes('text-grey italic text-xs q-my-sm')
                else:
                    for ea in em_atendimento_list:
                        with ui.card().classes('w-full q-pa-md border').style(f'background: {THEME["bg_panel"]}; border-color: rgba(0, 229, 255, 0.3); border-radius: 8px;'):
                            with ui.row().classes('w-full items-center justify-between'):
                                with ui.row().classes('items-center gap-3'):
                                    ui.avatar(icon='support_agent', color='primary', text_color='black')
                                    with ui.column().classes('gap-0'):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.label(ea['nome_guerra']).classes('text-white font-bold uppercase text-base')
                                            ui.label(f"({ea['numero_interno']})").classes('text-grey-4 text-xs')
                                        ui.label(f"Turma: {ea['turma']} • Chegou às {ea['hora']}").classes('text-grey-5 text-caption')
                                        ui.label(f"Motivo: {ea['motivo']}").classes('text-warning text-caption font-bold q-mt-xs')
                                        
                                with ui.row().classes('items-center'):
                                    def concluir_atendimento(fila_id=ea['id']):
                                        atualizar_status_fila(fila_id, 'concluido')
                                        ui.notify('Atendimento concluído', color='positive')
                                        data_service.clear_cache()
                                        ui.navigate.reload()
                                        
                                    ui.button('Concluir', icon='done_all', on_click=concluir_atendimento).props('unelevated dense no-caps color=positive text-color=black')

                ui.separator().classes('q-my-md')

                # --- SUB-PAINEL 2: FILA DE ESPERA ---
                ui.label('FILA DE ESPERA (MILITARES AGUARDANDO)').classes('text-success text-caption font-bold tracking-widest cyber-title')
                
                if not aguardando_list:
                    with ui.card().classes('w-full q-pa-sm border border-dashed border-gray-800 text-center').style('background: transparent;'):
                        ui.label('Nenhum aluno aguardando na fila.').classes('text-grey italic text-xs q-my-sm')
                else:
                    for idx, ag in enumerate(aguardando_list):
                        # Destaque de cor por prioridade
                        cor_prioridade = THEME['danger'] if ag['prioridade'] == 'urgente' else THEME['accent'] if ag['prioridade'] == 'alta' else 'rgba(0, 229, 255, 0.2)'
                        borda_prioridade = f"border-left: 4px solid {cor_prioridade}"
                        
                        with ui.card().classes('w-full q-pa-sm border border-gray-800').style(f'background: {THEME["bg_panel"]}; {borda_prioridade}; border: {THEME["border"]}; border-radius: 6px;'):
                            with ui.row().classes('w-full items-center justify-between wrap md:no-wrap gap-2'):
                                with ui.row().classes('items-center gap-3'):
                                    # Exibe a posição na fila
                                    ui.label(f"{idx+1}º").classes('text-grey font-bold text-lg q-px-sm')
                                    with ui.column().classes('gap-0'):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.label(ag['nome_guerra']).classes('text-white font-bold uppercase')
                                            ui.label(f"({ag['numero_interno']})").classes('text-grey-4 text-xs')
                                        ui.label(f"Pelotão: {ag['turma']} • Prioridade: {ag['prioridade'].upper()} • Chegada: {ag['hora']}").classes('text-grey-5 text-[11px]')
                                        ui.label(f"Motivo: {ag['motivo']}").classes('text-grey-3 text-[11px] font-semibold')
                                        
                                with ui.row().classes('items-center gap-1.5'):
                                    # Apenas o primeiro da fila pode iniciar atendimento
                                    is_first = (idx == 0)
                                    
                                    def chamar_atendimento(fila_id=ag['id']):
                                        atualizar_status_fila(fila_id, 'em_atendimento')
                                        ui.notify(f"Atendimento iniciado para {ag['nome_guerra']}", color='positive')
                                        data_service.clear_cache()
                                        ui.navigate.reload()
                                        
                                    def remover_fila(fila_id=ag['id']):
                                        atualizar_status_fila(fila_id, 'concluido')
                                        ui.notify(f"{ag['nome_guerra']} removido da fila", color='info')
                                        data_service.clear_cache()
                                        ui.navigate.reload()

                                    # Botão Atender (Iniciar)
                                    btn_start = ui.button('Atender', icon='play_arrow', on_click=chamar_atendimento)
                                    btn_start.props('unelevated dense no-caps color=primary text-color=black')
                                    if not is_first:
                                        btn_start.props('flat text-color=primary')
                                        
                                    # Botão Remover da fila
                                    ui.button(icon='delete', on_click=remover_fila).props('flat dense color=red').classes('w-8 h-8')
