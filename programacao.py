from nicegui import ui, app
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import theme
from database import (
    get_db_connection,
    load_data,
    salvar_conclusao_instrucao,
    reverter_conclusao_instrucao
)

THEME = theme.colors

# Estado local da página (filtros e pesquisa)
state = {
    'busca_texto': '',
    'filtro_status': 'Todas',
    'filtro_data': None  # Armazena string 'YYYY-MM-DD'
}

@ui.refreshable
def render_qts_grid():
    db_conn = get_db_connection()
    user_info = app.storage.user.get('user', {})
    username = user_info.get('username', 'militar_geral')

    # Carrega dados das tabelas
    prog_df = load_data('Programacao')
    alunos_df = load_data('Alunos')
    
    # Normalização de dados de data para comparação
    if not prog_df.empty:
        # Garante que a data está formatada como string YYYY-MM-DD
        prog_df['data_clean'] = prog_df['data'].apply(lambda x: str(x)[:10] if pd.notna(x) else '')
        
        # Filtros locais
        # 1. Filtro por status
        if state['filtro_status'] != 'Todas':
            prog_df = prog_df[prog_df['status'] == state['filtro_status']]
            
        # 2. Filtro por data
        if state['filtro_data']:
            prog_df = prog_df[prog_df['data_clean'] == state['filtro_data']]
            
        # 3. Filtro por pesquisa textual
        if state['busca_texto']:
            txt = state['busca_texto'].lower()
            prog_df = prog_df[
                prog_df['descricao'].str.lower().str.contains(txt, na=False) |
                prog_df['local'].str.lower().str.contains(txt, na=False) |
                prog_df['responsavel'].str.lower().str.contains(txt, na=False)
            ]
            
        # Ordena por data e horário (mais recentes primeiro)
        prog_df = prog_df.sort_values(by=['data_clean', 'horario'], ascending=[False, True])
        atividades = prog_df.to_dict(orient='records')
    else:
        atividades = []

    # Lista de pelotões únicos ativos no corpo de alunos
    lista_pelotoes = []
    if not alunos_df.empty and 'pelotao' in alunos_df.columns:
        lista_pelotoes = sorted(list(alunos_df['pelotao'].dropna().unique()))
    if not lista_pelotoes:
        lista_pelotoes = ['MIKE-1', 'MIKE-2', 'MIKE-3', 'MIKE-4', 'MIKE-5', 'MIKE-6', 'QTPA']

    # --- MODAIS E DIÁLOGOS DE PARTICIPAÇÃO ---
    def abrir_modal_participacao(act):
        """Abre o diálogo de confirmação de participantes e pelotões."""
        d = ui.dialog()
        
        # Determina pelotões pré-selecionados baseado nos destinatários
        pelotoes_dest = [p.strip().upper() for p in str(act.get('destinatarios', '')).split(',') if p.strip()]
        pelotoes_selecionados = [p for p in lista_pelotoes if p.upper() in pelotoes_dest]
        if not pelotoes_selecionados:
            # Caso não mapeie nada, seleciona todos
            pelotoes_selecionados = pelotoes_dest if pelotoes_dest else [lista_pelotoes[0]]

        # Controle de alunos excluídos (não participaram)
        # Exclusions armazena {aluno_id: bool (se participa ou não)}
        aluno_excluidos = {}

        # Carrega presenças do dia da instrução para sugerir exclusão automática de faltantes
        data_instrucao = act['data'][:10]
        presencas_dia = pd.DataFrame()
        indisponiveis_dia = set()
        
        if db_conn:
            try:
                # Carrega presenças da data
                res_pr = db_conn.table('presenca_ausencia').select('numero_interno,presente').eq('data', data_instrucao).execute()
                if res_pr.data:
                    presencas_dia = pd.DataFrame(res_pr.data)
                
                # Carrega indisponíveis (enfermaria, licenças, etc.) que estavam baixados ou licenciados no dia
                res_enf = db_conn.table('enfermaria').select('numero_interno,status').eq('data', data_instrucao).neq('status', 'Alta').execute()
                if res_enf.data:
                    for item in res_enf.data:
                        indisponiveis_dia.add(str(item['numero_interno']).upper())
            except Exception as e:
                print(f"[QTS] Erro ao carregar presenças/saúde do dia: {e}")

        # Identifica alunos ausentes na chamada diária
        ausentes_chamada = set()
        if not presencas_dia.empty:
            for _, r_pr in presencas_dia.iterrows():
                if not r_pr.get('presente', True):
                    ausentes_chamada.add(str(r_pr['numero_interno']).upper())

        @ui.refreshable
        def render_students_checklist(pelotoes_ativos):
            """Renderiza a lista de alunos com base nos pelotões marcados."""
            if alunos_df.empty:
                ui.label('Sem dados de alunos carregados.').classes('text-grey italic text-xs')
                return

            # Filtra alunos que pertencem a algum dos pelotões selecionados
            filtro_alunos = alunos_df[alunos_df['pelotao'].isin(pelotoes_ativos)]
            if filtro_alunos.empty:
                ui.label('Nenhum aluno encontrado nos pelotões selecionados.').classes('text-grey italic text-xs')
                return
            
            # Ordena por pelotão e nome de guerra
            filtro_alunos = filtro_alunos.sort_values(by=['pelotao', 'nome_guerra'])
            alunos_lista = filtro_alunos.to_dict(orient='records')

            ui.label('Selecione os Militares Participantes:').classes('text-white text-xs font-bold tracking-wider q-mt-md')
            
            # Grid scrollable de alunos
            with ui.scroll_area().classes('w-full h-80 border border-gray-800 rounded bg-black/20 q-pa-sm'):
                with ui.column().classes('w-full gap-1'):
                    current_pel = ""
                    for al in alunos_lista:
                        al_id = str(al['id'])
                        ni_upper = str(al['numero_interno']).upper()
                        
                        # Cabeçalho do pelotão
                        if al['pelotao'] != current_pel:
                            current_pel = al['pelotao']
                            ui.label(f"Pelotão {current_pel}").classes('text-amber-5 text-xs font-black tracking-widest q-mt-xs border-b border-gray-900/60 w-full')
                        
                        # Verifica se o aluno estava ausente ou baixado/licenciado no dia da instrução
                        is_ausente = ni_upper in ausentes_chamada
                        is_doente = ni_upper in indisponiveis_dia
                        
                        # Sugestão padrão: se estava ausente ou baixado, padrão é Desmarcado
                        status_sugestao = True
                        if is_ausente or is_doente:
                            status_sugestao = False
                        
                        # Inicializa estado no dict se não existir
                        if al_id not in aluno_excluidos:
                            aluno_excluidos[al_id] = status_sugestao
                        
                        # Cor e badge
                        label_extra = ""
                        color_name = "text-white"
                        if is_doente:
                            label_extra = " [BAIXADO/LICENÇA]"
                            color_name = "text-red-400 font-semibold"
                        elif is_ausente:
                            label_extra = " [AUSENTE CHAMADA]"
                            color_name = "text-orange-400 font-semibold"
                            
                        # Checkbox do Aluno
                        def on_toggle_aluno(val, aid=al_id):
                            aluno_excluidos[aid] = val
                            
                        with ui.row().classes('w-full items-center justify-between no-wrap hover:bg-white/5 q-px-xs rounded'):
                            ui.checkbox(
                                text=f"{al['numero_interno']} - {al['nome_guerra'].upper()}{label_extra}",
                                value=aluno_excluidos[al_id],
                                on_change=lambda e, aid=al_id: on_toggle_aluno(e.value, aid)
                            ).props('dark dense').classes(f'text-xs {color_name}')
                            
                            ui.label(al['pelotao']).classes('text-grey-5 text-[10px] font-mono')

        def salvar_conclusao():
            """Recolhe dados e marca instrução como concluída."""
            # 1. Filtra os pelotões marcados
            pelotoes_ativos = [p for p in lista_pelotoes if p in checks_pelotoes and checks_pelotoes[p].value]
            if not pelotoes_ativos:
                ui.notify('Selecione pelo menos um pelotão participante!', color='negative')
                return
            
            pel_str = ", ".join(pelotoes_ativos)
            
            # 2. Identifica alunos desmarcados (excluídos do treinamento)
            # Filtra alunos dos pelotões ativos que foram desmarcados
            alunos_do_pelotao = alunos_df[alunos_df['pelotao'].isin(pelotoes_ativos)]
            ausentes_list = []
            
            for _, al in alunos_do_pelotao.iterrows():
                al_id = str(al['id'])
                participou = aluno_excluidos.get(al_id, True)
                if not participou:
                    ausentes_list.append(f"{al['nome_guerra'].upper()} ({al['numero_interno']})")
            
            # Formata observação de ausências
            obs_exclusoes = act.get('obs') or ''
            if ausentes_list:
                str_ausentes = "Ausentes: " + ", ".join(ausentes_list)
                if obs_exclusoes:
                    obs_exclusoes = f"{obs_exclusoes} | {str_ausentes}"
                else:
                    obs_exclusoes = str_ausentes
            
            # 3. Salva no Banco de Dados
            sucesso = salvar_conclusao_instrucao(
                instrucao_id=act['id'],
                concluido_por=username,
                pelotoes=pel_str,
                obs_exclusoes=obs_exclusoes
            )
            
            if sucesso:
                ui.notify('Instrução concluída com sucesso!', color='positive')
                d.close()
                render_qts_grid.refresh()
            else:
                ui.notify('Falha ao concluir instrução no banco.', color='negative')

        # Monta a estrutura visual do modal
        with d, ui.card().classes('w-[600px] q-pa-md').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('Confirmar Realização de Instrução').classes('text-lg text-white font-black tracking-wide')
                ui.button(icon='close', on_click=d.close).props('flat dense color=grey')
            ui.separator().props('dark')
            
            # Info da instrução
            with ui.column().classes('w-full gap-0.5 bg-black/40 q-pa-sm rounded-lg border border-gray-900'):
                ui.label(act['descricao']).classes('text-amber-5 text-sm font-bold')
                with ui.row().classes('text-grey-4 text-xs gap-3 q-mt-xs'):
                    ui.label(f"🕒 {act['horario']}")
                    ui.label(f"📍 {act['local']}")
                    ui.label(f"👮 Responsável: {act['responsavel']}")
            
            # Passo 1: Seleção de Pelotões
            ui.label('Pelotões Participantes:').classes('text-white text-xs font-bold tracking-wider q-mt-sm')
            checks_pelotoes = {}
            
            # Grid de checkboxes de pelotões
            with ui.row().classes('w-full justify-between wrap bg-black/10 q-pa-xs border border-gray-900 rounded'):
                for pel in lista_pelotoes:
                    checked_state = pel in pelotoes_selecionados
                    # Quando alterar o pelotão, atualiza a lista de alunos
                    def on_change_pelotao():
                        # Obtém a lista atualizada de pelotões marcados
                        ativos = [p for p in lista_pelotoes if p in checks_pelotoes and checks_pelotoes[p].value]
                        render_students_checklist.refresh(ativos)

                    chk = ui.checkbox(
                        text=pel,
                        value=checked_state,
                        on_change=on_change_pelotao
                    ).props('dark dense').classes('text-xs text-grey-2')
                    checks_pelotoes[pel] = chk

            # Passo 2: Checklist dos Alunos (Refreshable)
            render_students_checklist(pelotoes_selecionados)
            
            # Rodapé do modal
            with ui.row().classes('w-full justify-end gap-3 q-mt-md'):
                ui.button('Cancelar', on_click=d.close).props('flat color=grey no-caps')
                ui.button('Confirmar Realização', icon='check', on_click=salvar_conclusao).props('unelevated color=green no-caps')

        d.open()

    def abrir_modal_visualizar(act):
        """Abre o diálogo para visualizar quem participou e permitir reverter."""
        d = ui.dialog()
        
        # Parseia pelotões que participaram
        pel_concluidos = [p.strip().upper() for p in str(act.get('pelotoes_concluidos', '')).split(',') if p.strip()]
        
        # Filtra alunos participantes
        participantes = []
        ausentes = []
        
        if not alunos_df.empty:
            # Lista de alunos pertencentes aos pelotões marcados
            alunos_do_pelotao = alunos_df[alunos_df['pelotao'].str.upper().isin(pel_concluidos)]
            
            # Identifica quem foi listado como ausente na observação da instrução
            obs = str(act.get('obs', ''))
            nomes_ausentes = []
            if "Ausentes:" in obs:
                # Extrai lista de nomes
                parte_ausente = obs.split("Ausentes:")[1].strip()
                # Remove barras verticais extras se houverem
                if " | " in parte_ausente:
                    parte_ausente = parte_ausente.split(" | ")[0]
                nomes_ausentes = [n.strip().upper() for n in parte_ausente.split(",") if n.strip()]

            for _, al in alunos_do_pelotao.iterrows():
                al_nome = al['nome_guerra'].upper()
                ni = al['numero_interno']
                # Verifica se o nome ou número interno está listado nos ausentes
                is_excluido = False
                for aus_entry in nomes_ausentes:
                    if al_nome in aus_entry or str(ni) in aus_entry:
                        is_excluido = True
                        break
                
                al_dict = {'ni': ni, 'nome': al_nome, 'pelotao': al['pelotao']}
                if is_excluido:
                    ausentes.append(al_dict)
                else:
                    participantes.append(al_dict)

        def reverter_conclusao():
            """Reverte conclusão da instrução de volta para 'A Realizar'."""
            sucesso = reverter_conclusao_instrucao(act['id'])
            if sucesso:
                ui.notify('Status da instrução revertido!', color='warning')
                d.close()
                render_qts_grid.refresh()
            else:
                ui.notify('Falha ao reverter status.', color='negative')

        with d, ui.card().classes('w-[500px] q-pa-md').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('Detalhes da Conclusão').classes('text-lg text-white font-black tracking-wide cyber-title')
                ui.button(icon='close', on_click=d.close).props('flat dense color=grey')
            ui.separator().props('dark')
            
            # Detalhes
            with ui.column().classes('w-full gap-1 q-mb-md'):
                ui.label(act['descricao']).classes('text-primary text-sm font-bold cyber-title')
                ui.label(f"Concluído em: {act.get('data_conclusao', 'N/A')}").classes('text-grey-4 text-xs')
                ui.label(f"Registrado por: {act.get('concluido_por', 'N/A').upper()}").classes('text-grey-4 text-xs')
                ui.label(f"Pelotões: {act.get('pelotoes_concluidos', 'N/A')}").classes('text-grey-4 text-xs')
                if act.get('obs'):
                    ui.label(f"Observações: {act['obs']}").classes('text-accent text-xs italic')

            # Lista de Participantes e Ausentes
            with ui.tabs().classes('w-full') as tabs:
                t1 = ui.tab('Participantes').classes('text-xs font-bold')
                t2 = ui.tab('Ausentes/Excluídos').classes('text-xs font-bold')
            
            with ui.tab_panels(tabs, value=t1).classes('w-full bg-transparent text-white'):
                with ui.tab_panel(t1):
                    if not participantes:
                        ui.label('Nenhum aluno registrado.').classes('text-grey italic text-xs')
                    else:
                        with ui.scroll_area().classes('w-full h-64'):
                            for p in participantes:
                                with ui.row().classes('w-full justify-between items-center q-py-xs border-b border-cyan-900/20 text-xs px-2'):
                                    ui.label(f"{p['ni']} - {p['nome']}").classes('font-medium')
                                    ui.badge(p['pelotao'], color='positive').classes('text-[9px] text-black font-bold')

                with ui.tab_panel(t2):
                    if not ausentes:
                        ui.label('Nenhum militar ausente neste treinamento.').classes('text-grey italic text-xs')
                    else:
                        with ui.scroll_area().classes('w-full h-64'):
                            for a in ausentes:
                                with ui.row().classes('w-full justify-between items-center q-py-xs border-b border-cyan-900/20 text-xs px-2'):
                                    ui.label(f"{a['ni']} - {a['nome']}").classes('text-red-400 font-medium')
                                    ui.badge(a['pelotao'], color='negative').classes('text-[9px] text-black font-bold')

            # Rodapé do modal
            with ui.row().classes('w-full justify-between items-center q-mt-md'):
                ui.button('Reverter Conclusão', icon='undo', on_click=reverter_conclusao).props('outline color=negative no-caps text-color=negative').classes('text-xs')
                ui.button('Fechar', on_click=d.close).props('unelevated color=grey no-caps')

        d.open()

    # --- GRID DE ATIVIDADES ---
    with ui.column().classes('w-full gap-3 q-mt-md'):
        if not atividades:
            with ui.card().classes('w-full q-pa-lg items-center justify-center bg-gray-900/20 border border-gray-800/60'):
                ui.icon('info', color='grey-6', size='2.5rem')
                ui.label('Nenhuma instrução cadastrada com os filtros ativos.').classes('text-grey italic text-subtitle2 q-mt-xs')
            return

        # Cabeçalho da Lista
        with ui.row().classes('w-full justify-between items-center text-grey-5 text-xs font-bold tracking-wider q-px-md'):
            ui.label('HORÁRIO & INSTRUÇÃO')
            ui.label('STATUS & AÇÕES')

        for act in atividades:
            is_concluida = act.get('status') == 'Concluído'
            left_border = 'border-l-4 border-positive' if is_concluida else 'border-l-4 border-primary'
            bg_panel = 'background: rgba(0, 230, 118, 0.03);' if is_concluida else 'background: rgba(0, 229, 255, 0.03);'

            # Conversão de data para exibição
            data_formatada = act['data']
            try:
                dt = datetime.strptime(act['data'][:10], '%Y-%m-%d')
                data_formatada = dt.strftime('%d/%m/%Y')
            except Exception:
                pass

            card = ui.card().classes(f'w-full q-pa-md border border-gray-800 {left_border}').style(f'{bg_panel} border: {THEME["border"]} !important;')
            with card:
                with ui.row().classes('w-full justify-between items-center wrap gap-4'):
                    
                    # Horário e Informações
                    with ui.row().classes('items-center gap-4 col-grow min-w-[280px]'):
                        # Hora gigante
                        ui.label(act.get('horario', '--:--')).style(
                            f'color: {THEME["primary"]}; font-size: 1.8rem; font-weight: 900; font-family: monospace; line-height: 1;'
                        ).classes('drop-shadow-[0_0_8px_rgba(0,229,255,0.35)]')
                        with ui.column().classes('gap-0.5'):
                            ui.label(act.get('descricao', '')).classes('text-white text-subtitle1 font-bold')
                            with ui.row().classes('items-center gap-3 text-grey-4 text-caption wrap q-mt-xs'):
                                ui.label(f"📅 Data: {data_formatada}").classes('font-medium')
                                ui.label(f"📍 Local: {act.get('local', 'N/A')}")
                                ui.label(f"👮 Resp: {act.get('responsavel', 'N/A')}")
                                ui.label(f"🎯 Alunos: {act.get('destinatarios', 'N/A')}")

                    # Status, Observação e Ações
                    with ui.row().classes('items-center gap-4 shrink-0'):
                        # Se concluída, mostra badge e botão visualizar
                        if is_concluida:
                            with ui.column().classes('items-end gap-1'):
                                ui.badge('CONCLUÍDO', color='positive').classes('text-xs font-bold text-black q-pa-xs')
                                ui.label(f"Por {act.get('concluido_por', 'N/A')}").classes('text-[10px] text-grey-5')
                            ui.button(
                                'Ver Participação',
                                icon='groups',
                                on_click=lambda a=act: abrir_modal_visualizar(a)
                            ).props('unelevated dense no-caps color=primary text-color=black').classes('text-xs font-bold')
                            
                        # Se pendente, mostra checkbox de conclusão rápida e botão concluir
                        else:
                            ui.badge('A REALIZAR', color='primary').classes('text-xs font-bold text-black q-pa-xs')
                            
                            ui.button(
                                'Marcar Concluído',
                                icon='check_circle',
                                on_click=lambda a=act: abrir_modal_participacao(a)
                            ).props('unelevated color=positive text-color=black no-caps dense').classes('text-xs q-px-sm font-bold')


def render_page():
    with ui.column().classes('w-full q-pa-lg gap-4'):
        # Cabeçalho da Seção
        theme.section_header('Programação de Instrução', 'Quadro de Trabalho Semanal (QTS) e Registro de Realizações')

        # --- BARRA DE FILTROS E PESQUISA ---
        with ui.card().classes('w-full q-pa-md border border-gray-800').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
            with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                
                # Input de Pesquisa
                search_input = ui.input(
                    label='Pesquisar instruções...',
                    placeholder='Digite descrição, local ou responsável...',
                    on_change=lambda e: state.update({'busca_texto': e.value}) or render_qts_grid.refresh()
                ).props('dark dense outlined').classes('col-grow min-w-[200px]')
                with search_input.add_slot('append'):
                    ui.icon('search', color='grey')

                # Filtro por Status
                ui.select(
                    options={'Todas': 'Todos os Status', 'A Realizar': 'Pendente (A Realizar)', 'Concluído': 'Concluído'},
                    value=state['filtro_status'],
                    label='Filtrar por Status',
                    on_change=lambda e: state.update({'filtro_status': e.value}) or render_qts_grid.refresh()
                ).props('dark dense outlined').classes('w-48')

                # Filtro por Data
                with ui.row().classes('items-center gap-2'):
                    ui.label('Filtrar Data:').classes('text-grey-4 text-xs font-bold')
                    
                    # Exibe data selecionada
                    date_lbl = ui.label('Todas').classes('text-white text-xs font-mono px-2 py-1 bg-black/40 border border-gray-900 rounded')
                    
                    # Diálogo do Date Picker
                    with ui.dialog() as date_dialog, ui.card().classes('q-pa-md bg-grey-9'):
                        d_picker = ui.date(on_change=lambda e: select_date(e.value))
                        ui.button('Limpar Filtro', on_click=lambda: select_date(None)).props('flat color=red no-caps').classes('w-full q-mt-xs')
                        ui.button('Fechar', on_click=date_dialog.close).props('unelevated color=grey no-caps').classes('w-full q-mt-xs')

                    def select_date(val):
                        state['filtro_data'] = val
                        date_lbl.set_text(val if val else 'Todas')
                        date_dialog.close()
                        render_qts_grid.refresh()

                    ui.button(icon='event', on_click=date_dialog.open).props('unelevated dense color=grey-9').classes('q-pa-xs')

        # --- GRID REATIVO ---
        render_qts_grid()
