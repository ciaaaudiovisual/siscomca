from nicegui import ui, app
import pandas as pd
from datetime import datetime
import zipfile
import io
import math
import theme
from database import get_db_connection, load_data
from services import data_service

THEME = theme.colors

# Lógica de cálculo idêntica à original
def calcular_pontuacao_efetiva(acoes_df: pd.DataFrame, tipos_acao_df: pd.DataFrame, config_df: pd.DataFrame) -> pd.DataFrame:
    if acoes_df.empty or tipos_acao_df.empty:
        return pd.DataFrame()
        
    acoes_copy = acoes_df.copy()
    tipos_copy = tipos_acao_df.copy()

    tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
    acoes_copy['tipo_acao_id'] = acoes_copy['tipo_acao_id'].astype(str)
    tipos_copy['id'] = tipos_copy['id'].astype(str)
    
    acoes_com_pontos = pd.merge(acoes_copy, tipos_copy[['id', 'pontuacao', 'nome']], left_on='tipo_acao_id', right_on='id', how='left')
    
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    fator_adaptacao = float(config_dict.get('fator_adaptacao', 0.25))
    try:
        inicio_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_inicio')).date()
        fim_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_fim')).date()
    except Exception:
        inicio_adaptacao, fim_adaptacao = None, None

    def aplicar_fator(row):
        pontuacao = row.get('pontuacao', 0.0)
        data_convertida = pd.to_datetime(row['data'], errors='coerce')
        if pd.isna(data_convertida):
            return pontuacao
        
        data_acao = data_convertida.date()
        if pontuacao >= 0 or not inicio_adaptacao: 
            return pontuacao
        
        if inicio_adaptacao <= data_acao <= fim_adaptacao:
            return pontuacao * fator_adaptacao
        return pontuacao
        
    acoes_com_pontos['pontuacao_efetiva'] = acoes_com_pontos.apply(aplicar_fator, axis=1)
    return acoes_com_pontos


def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df, incluir_lancador, tipos_a_incluir):
    texto = [
        "============================================================",
        "FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)\n",
        f"Pelotão: {aluno_info.get('pelotao', 'N/A')}",
        f"Aluno: {aluno_info.get('nome_completo', 'N/A')}",
        f"Nome de Guerra: {aluno_info.get('nome_guerra', 'N/A')}",
        f"Número Interno: {aluno_info.get('numero_interno', 'N/A')}",
        "\n------------------------------------------------------------",
        "LANÇAMENTOS (STATUS 'LANÇADO') EM ORDEM CRONOLÓGICA:",
        "------------------------------------------------------------\n"
    ]
    
    # Filtra apenas as lançadas
    acoes_lancadas = acoes_aluno_df[acoes_aluno_df['status'] == 'Lançado'] if not acoes_aluno_df.empty else pd.DataFrame()

    df_filtrado_por_tipo = pd.DataFrame()
    if not acoes_lancadas.empty:
        if "Positivos" in tipos_a_incluir:
            df_filtrado_por_tipo = pd.concat([df_filtrado_por_tipo, acoes_lancadas[acoes_lancadas['pontuacao_efetiva'] > 0]])
        if "Negativos" in tipos_a_incluir:
            df_filtrado_por_tipo = pd.concat([df_filtrado_por_tipo, acoes_lancadas[acoes_lancadas['pontuacao_efetiva'] < 0]])
        if "Neutros" in tipos_a_incluir:
            df_filtrado_por_tipo = pd.concat([df_filtrado_por_tipo, acoes_lancadas[acoes_lancadas['pontuacao_efetiva'] == 0]])

    if df_filtrado_por_tipo.empty:
        if acoes_lancadas.empty:
            texto.append("Nenhum lançamento com status 'Lançado' encontrado para este aluno.")
        else:
            texto.append("Nenhum lançamento encontrado para os tipos selecionados (Positivo/Negativo/Neutro).")
    else:
        for _, acao in df_filtrado_por_tipo.sort_values(by='data').iterrows():
            texto_acao = [
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
                f"Descrição: {acao.get('descricao', '')}",
            ]
            if incluir_lancador:
                texto_acao.append(f"Registrado por: {acao.get('usuario', 'N/A')}")
            
            texto_acao.append("\n-----------------------------------\n")
            texto.extend(texto_acao)

    texto.extend([
        "\n============================================================",
        f"Fim do Relatório - Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "============================================================"
    ])
    return "\n".join(texto)


def render_page():
    # Inicializa estado se não houver
    if 'gestao_state' not in app.storage.user:
        app.storage.user['gestao_state'] = {
            'selected_tab': 'Registrar Novo Lançamento',
            'new_aluno_id': None,
            'new_tipo_acao_lbl': None,
            'new_data': datetime.now().strftime('%Y-%m-%d'),
            'new_desc': '',
            'new_dispensa': False,
            'new_dispensa_inicio': datetime.now().strftime('%Y-%m-%d'),
            'new_dispensa_fim': datetime.now().strftime('%Y-%m-%d'),
            'new_dispensa_tipo': '',
            'new_confirm': False,
            'filtro_pelotao': 'Todos',
            'filtro_aluno': 'Nenhum',
            'filtro_status': 'Pendente',
            'filtro_tipo': 'Todos',
            'ordenar_por': 'Mais Recentes',
            'selected_actions': {}
        }
    render_gestao_content()


@ui.refreshable
def render_gestao_content():
    state = app.storage.user['gestao_state']

    # Carrega dados
    core_data = data_service.get_core_data()
    alunos_df = core_data.get('alunos', pd.DataFrame())
    acoes_df = core_data.get('acoes', pd.DataFrame())
    tipos_acao_df = core_data.get('tipos_acao', pd.DataFrame())
    config_df = core_data.get('config', pd.DataFrame())

    if alunos_df.empty or tipos_acao_df.empty:
        with ui.column().classes('w-full q-pa-lg items-center justify-center'):
            ui.icon('warning', color='warning', size='4rem')
            ui.label('Banco de dados vazio ou sem tipos de ações cadastrados.').classes('text-grey text-lg font-bold q-mt-md')
        return

    # Processa ações com pontos
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)

    # Constrói opções de alunos
    alunos_df_sorted = alunos_df.sort_values('nome_guerra')
    aluno_options = {str(r['id']): f"{r['numero_interno']} - {r['nome_guerra']} ({r['pelotao']})" for _, r in alunos_df_sorted.iterrows()}

    # Agrupa tipos de ação
    tipos_copy = tipos_acao_df.copy()
    tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
    sorted_tipos = tipos_copy.sort_values('nome')
    positivas = sorted_tipos[sorted_tipos['pontuacao'] > 0]
    neutras = sorted_tipos[sorted_tipos['pontuacao'] == 0]
    negativas = sorted_tipos[sorted_tipos['pontuacao'] < 0]

    opcoes_tipo_acao = []
    tipos_opcoes_map = {}
    
    if not positivas.empty:
        opcoes_tipo_acao.append("--- AÇÕES POSITIVAS ---")
        for _, r in positivas.iterrows():
            lbl = f"➕ {r['nome']} (+{r['pontuacao']:.1f} pts)"
            opcoes_tipo_acao.append(lbl)
            tipos_opcoes_map[lbl] = r
    if not neutras.empty:
        opcoes_tipo_acao.append("--- AÇÕES NEUTRAS ---")
        for _, r in neutras.iterrows():
            lbl = f"⚪ {r['nome']} (0.0 pts)"
            opcoes_tipo_acao.append(lbl)
            tipos_opcoes_map[lbl] = r
    if not negativas.empty:
        opcoes_tipo_acao.append("--- AÇÕES NEGATIVAS ---")
        for _, r in negativas.iterrows():
            lbl = f"➖ {r['nome']} ({r['pontuacao']:.1f} pts)"
            opcoes_tipo_acao.append(lbl)
            tipos_opcoes_map[lbl] = r

    # UI Principal com abas
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Lançamentos de Ações dos Alunos', 'Controle, Revisão e Exportação de FAIAs')

        with ui.tabs().classes('w-full border-b border-gray-800') as tabs:
            tab_reg = ui.tab('Registrar Novo Lançamento', icon='add').classes('cyber-title text-xs font-bold')
            tab_list = ui.tab('Fila de Revisão / Histórico', icon='list').classes('cyber-title text-xs font-bold')
            tab_exp = ui.tab('Exportar FAIA', icon='download').classes('cyber-title text-xs font-bold')

        with ui.tab_panels(tabs, value=state['selected_tab'], on_change=lambda e: update_state_tab(e.value)).classes('w-full bg-transparent p-0 q-mt-md'):
            
            # --- TAB 1: REGISTRAR ---
            with ui.tab_panel(tab_reg):
                with ui.row().classes('w-full gap-6 no-wrap wrap-mobile'):
                    
                    # Coluna do Aluno
                    with ui.card().classes('col-grow p-6 border border-gray-800').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
                        ui.label('PASSO 1: SELECIONAR ALUNO').style(f'font-size: 0.75rem; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
                        aluno_sel = ui.select(
                            aluno_options, 
                            label='Escolha um Aluno', 
                            value=state['new_aluno_id'], 
                            on_change=lambda e: update_state('new_aluno_id', e.value)
                        ).props('dark outlined dense use-input hide-selected fill-input').classes('w-full q-mt-md')
                        
                        # Mostra detalhes do aluno selecionado
                        aluno_detalhes_container = ui.column().classes('w-full q-mt-md gap-2')
                        render_aluno_detalhes(aluno_detalhes_container, state['new_aluno_id'], alunos_df)

                    # Coluna do Formulário
                    with ui.card().classes('col-grow p-6 border border-gray-800').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
                        ui.label('PASSO 2: REGISTRAR AÇÃO').style(f'font-size: 0.75rem; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
                        
                        tipo_sel = ui.select(
                            opcoes_tipo_acao, 
                            label='Tipo de Ação', 
                            value=state['new_tipo_acao_lbl'], 
                            on_change=lambda e: on_action_type_change(e.value)
                        ).props('dark outlined dense').classes('w-full q-mt-md')
                        
                        data_inp = ui.input(
                            'Data e Hora da Ação', 
                            value=state['new_data']
                        ).props('dark outlined dense type=date').classes('w-full')
                        
                        desc_inp = ui.textarea(
                            'Descrição / Justificativa (Opcional)', 
                            value=state['new_desc']
                        ).props('dark outlined dense').classes('w-full')

                        # Bloco de Saúde (Dispensa Médica)
                        dispensa_container = ui.column().classes('w-full border-t border-gray-800 q-pt-md gap-4')
                        render_dispensa_fields(dispensa_container, state)

                        confirm_chk = ui.checkbox(
                            'Confirmo que os dados estão corretos para o lançamento.', 
                            value=state['new_confirm']
                        ).props('dark').classes('q-mt-sm')
                        
                        # Botão Salvar
                        ui.button(
                            'Registrar Ação', 
                            icon='gavel', 
                            on_click=lambda: salvar_nova_acao(confirm_chk)
                        ).props('unelevated no-caps').classes('w-full font-bold q-py-sm cyber-glow').style(f'background: {THEME["primary"]}; color: #000;')

            # --- TAB 2: FILA / HISTÓRICO ---
            with ui.tab_panel(tab_list):
                # Filtros
                with ui.card().classes('w-full q-pa-md border border-gray-800 q-mb-md').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
                    ui.label('FILTROS DE VISUALIZAÇÃO').style(f'font-size: 0.75rem; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
                    
                    with ui.row().classes('w-full items-center gap-4'):
                        pelotões = ['Todos'] + sorted(list(alunos_df['pelotao'].dropna().unique()))
                        pelotao_sel = ui.select(pelotões, label='Filtrar Pelotão', value=state['filtro_pelotao'], on_change=lambda e: update_filter('filtro_pelotao', e.value)).props('dark outlined dense').classes('w-44')
                        
                        # Constrói opções de alunos dinâmicas baseado no pelotão
                        opcoes_aluno_filtro = obter_alunos_filtro_lista(state['filtro_pelotao'], alunos_df)
                        aluno_filtro_sel = ui.select(opcoes_aluno_filtro, label='Filtrar Aluno (Opcional)', value=state['filtro_aluno'], on_change=lambda e: update_filter('filtro_aluno', e.value)).props('dark outlined dense').classes('w-48')
                        
                        status_sel = ui.select(['Pendente', 'Lançado', 'Arquivado', 'Todos'], label='Filtrar Status', value=state['filtro_status'], on_change=lambda e: update_filter('filtro_status', e.value)).props('dark outlined dense').classes('w-44')
                        
                        tipos_ações = ['Todos'] + sorted(list(tipos_acao_df['nome'].dropna().unique()))
                        tipo_sel_filt = ui.select(tipos_ações, label='Tipo de Ação', value=state['filtro_tipo'], on_change=lambda e: update_filter('filtro_tipo', e.value)).props('dark outlined dense').classes('w-44')
                        
                        ordenar_sel = ui.select(['Mais Recentes', 'Mais Antigos', 'Aluno (A-Z)'], label='Ordenar por', value=state['ordenar_por'], on_change=lambda e: update_filter('ordenar_por', e.value)).props('dark outlined dense').classes('w-44')

                # Ações em Massa
                with ui.card().classes('w-full q-pa-md border border-gray-800 q-mb-md justify-between items-center').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
                    with ui.row().classes('w-full justify-between items-center wrap gap-4'):
                        # Botões
                        with ui.row().classes('gap-2'):
                            ui.button('🚀 Lançar Selecionados', on_click=lambda: bulk_status('Lançado')).props('unelevated no-caps color=positive')
                            ui.button('✏️ Editar Selecionados', on_click=lambda: bulk_edit_dialog_open(tipos_acao_df)).props('unelevated no-caps color=primary text-color=black')
                            ui.button('🗑️ Arquivar Selecionados', on_click=lambda: bulk_status('Arquivado')).props('unelevated no-caps color=negative')
                        
                        # Checkbox marq/desm
                        ui.checkbox('Marcar/Desmarcar todos os visíveis', on_change=lambda e: toggle_all_visible(e.value)).props('dark')

                # Container de Cards
                cards_container = ui.column().classes('w-full gap-4')
                render_actions_list(cards_container, acoes_com_pontos, alunos_df, tipos_acao_df, state)

            # --- TAB 3: EXPORTAR ---
            with ui.tab_panel(tab_exp):
                with ui.card().classes('w-full q-pa-lg border border-gray-800').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]};'):
                    ui.label('EXPORTAÇÃO DE RELATÓRIOS FAIA').style(f'font-size: 0.75rem; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
                    
                    st_types = app.storage.user.get('export_types', ['Positivos', 'Negativos', 'Neutros'])
                    st_launcher = app.storage.user.get('export_launcher', True)
                    
                    with ui.row().classes('w-full items-center gap-6 q-mt-md'):
                        tipos_multiselect = ui.select(
                            ['Positivos', 'Negativos', 'Neutros'], 
                            label='Incluir tipos de lançamento', 
                            value=st_types, 
                            multiple=True
                        ).props('dark outlined dense').classes('w-72')
                        
                        lancador_chk = ui.checkbox(
                            'Incluir nome de quem lançou?', 
                            value=st_launcher
                        ).props('dark')

                    ui.separator().props('dark').classes('q-my-md')
                    
                    with ui.row().classes('w-full items-end gap-6'):
                        exp_pelotao = ui.select(pelotões[1:], label='Exportar Pelotão Inteiro (.ZIP)', on_change=lambda: exp_aluno.set_value(None)).props('dark outlined dense').classes('w-72')
                        exp_aluno = ui.select(aluno_options, label='Exportar Aluno Específico (.TXT)', on_change=lambda: exp_pelotao.set_value(None)).props('dark outlined dense use-input hide-selected fill-input').classes('w-80')
                    
                    with ui.row().classes('w-full gap-3 q-mt-lg'):
                        ui.button(
                            '👁️ Pré-visualizar FAIA', 
                            icon='visibility', 
                            on_click=lambda: preview_faia(exp_aluno.value, acoes_com_pontos, alunos_df, tipos_multiselect.value, lancador_chk.value)
                        ).props('unelevated no-caps').classes('font-bold q-py-sm').style('background: #222; border: 1px solid #444; color: #fff;')
                        
                        ui.button(
                            '📥 Exportar/Baixar', 
                            icon='file_download', 
                            on_click=lambda: trigger_export(exp_pelotao.value, exp_aluno.value, acoes_com_pontos, alunos_df, tipos_multiselect.value, lancador_chk.value)
                        ).props('unelevated no-caps color=primary text-color=black font-bold q-py-sm')


def update_state_tab(tab_name):
    state = app.storage.user['gestao_state']
    state['selected_tab'] = tab_name
    app.storage.user['gestao_state'] = state


def update_state(key, val):
    state = app.storage.user['gestao_state']
    state[key] = val
    app.storage.user['gestao_state'] = state


def update_filter(key, val):
    state = app.storage.user['gestao_state']
    state[key] = val
    app.storage.user['gestao_state'] = state
    render_gestao_content.refresh()


def on_action_type_change(value):
    state = app.storage.user['gestao_state']
    state['new_tipo_acao_lbl'] = value
    
    # Determina se é saúde
    is_saude = False
    if value and not value.startswith("---"):
        lbl_upper = value.upper()
        for h in ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]:
            if h in lbl_upper:
                is_saude = True
    
    state['new_dispensa'] = is_saude
    app.storage.user['gestao_state'] = state
    render_gestao_content.refresh()


def obter_alunos_filtro_lista(pelotao, alunos_df):
    if pelotao != 'Todos':
        df = alunos_df[alunos_df['pelotao'] == pelotao]
    else:
        df = alunos_df
    df = df.sort_values('nome_guerra')
    return ['Nenhum'] + sorted(list(df['nome_guerra'].dropna().unique()))


def render_aluno_detalhes(container, aluno_id, alunos_df):
    container.clear()
    if not aluno_id:
        with container:
            ui.label('Nenhum aluno selecionado.').classes('text-grey italic text-caption')
        return

    aluno = alunos_df[alunos_df['id'].astype(str) == str(aluno_id)]
    if aluno.empty:
        return
        
    r = aluno.iloc[0]
    foto_url = r.get('url_foto')
    image_src = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else 'https://via.placeholder.com/100?text=Sem+Foto'
    
    with container:
        with ui.row().classes('items-center gap-4 q-py-sm'):
            ui.avatar(size='64px').classes('border border-gray-800').style(f"background-image: url('{image_src}'); background-size: cover; background-position: center;")
            with ui.column().classes('gap-0'):
                ui.label(r['nome_completo']).classes('text-white text-caption font-bold max-w-xs ellipsis')
                ui.label(f"Nº {r['numero_interno']} • Pelotão: {r['pelotao']}").classes('text-grey text-[11px]')
                ui.label(f"Especialidade: {r.get('especialidade') or 'N/A'}").classes('text-grey text-[11px]')


def render_dispensa_fields(container, state):
    container.clear()
    if not state['new_dispensa']:
        return

    with container:
        ui.label('GEROU DISPENSA MÉDICA').classes('text-caption text-amber-5 font-bold')
        with ui.row().classes('w-full items-center gap-4'):
            d_ini = ui.input('Início', value=state['new_dispensa_inicio']).props('dark outlined dense type=date').classes('col-grow')
            d_fim = ui.input('Fim', value=state['new_dispensa_fim']).props('dark outlined dense type=date').classes('col-grow')
            d_tipo = ui.select(['', 'Total', 'Parcial', 'Para Esforço Físico', 'Outro'], label='Tipo', value=state['new_dispensa_tipo']).props('dark outlined dense').classes('col-grow')
            
            d_ini.on_change(lambda e: update_state('new_dispensa_inicio', e.value))
            d_fim.on_change(lambda e: update_state('new_dispensa_fim', e.value))
            d_tipo.on_change(lambda e: update_state('new_dispensa_tipo', e.value))


def salvar_nova_acao(confirm_chk):
    state = app.storage.user['gestao_state']
    
    if not state['new_aluno_id']:
        ui.notify('Selecione um aluno!', color='warning')
        return
    if not state['new_tipo_acao_lbl'] or state['new_tipo_acao_lbl'].startswith("---"):
        ui.notify('Selecione um tipo de ação válido!', color='warning')
        return
    if not confirm_chk.value:
        ui.notify('Confirme que os dados estão corretos!', color='warning')
        return

    try:
        # Recupera informações reais do tipo
        tipos_copy = load_data("Tipos_Acao")
        tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
        sorted_tipos = tipos_copy.sort_values('nome')
        
        tipo_info = None
        for _, r in sorted_tipos.iterrows():
            lbl_pos = f"➕ {r['nome']} (+{r['pontuacao']:.1f} pts)"
            lbl_neu = f"⚪ {r['nome']} (0.0 pts)"
            lbl_neg = f"➖ {r['nome']} ({r['pontuacao']:.1f} pts)"
            if state['new_tipo_acao_lbl'] in [lbl_pos, lbl_neu, lbl_neg]:
                tipo_info = r
                break
                
        if tipo_info is None:
            ui.notify('Erro ao decodificar tipo de ação!', color='negative')
            return

        db_conn = get_db_connection()
        usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Anonimo')
        
        nova_acao = {
            'aluno_id': str(state['new_aluno_id']),
            'tipo_acao_id': str(tipo_info['id']),
            'tipo': tipo_info['nome'],
            'descricao': state['new_desc'],
            'data': state['new_data'],
            'usuario': usuario,
            'status': 'Pendente',
            'esta_dispensado': bool(state['new_dispensa']),
            'periodo_dispensa_inicio': state['new_dispensa_inicio'] if state['new_dispensa'] else None,
            'periodo_dispensa_fim': state['new_dispensa_fim'] if state['new_dispensa'] else None,
            'tipo_dispensa': state['new_dispensa_tipo'] if state['new_dispensa'] else None
        }

        if db_conn:
            db_conn.table('Acoes').insert(nova_acao).execute()
            ui.notify('Ação registrada com sucesso!', color='positive')
            
            # Dispara alerta em tempo real para o Modo TV
            try:
                from services import data_service
                from alerts_manager import AlertsManager
                alunos_df = data_service.get_alunos_data()
                if not alunos_df.empty:
                    match_al = alunos_df[alunos_df['id'].astype(str) == str(state['new_aluno_id'])]
                    if not match_al.empty:
                        aluno_row = match_al.iloc[0]
                        aluno_lbl = f"{aluno_row.get('numero_interno', '')} — {str(aluno_row.get('nome_guerra', '')).upper()} ({str(aluno_row.get('pelotao', '')).upper()})"
                        pts = float(tipo_info.get('pontuacao', 0.0) or 0.0)
                        
                        # Determina se é relacionado a saúde para ser laranja (warning)
                        is_saude = False
                        lbl_upper = tipo_info['nome'].upper()
                        for h in ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]:
                            if h in lbl_upper:
                                is_saude = True
                                
                        alert_type = "success" if pts > 0 else "alert" if pts < 0 else "info"
                        if is_saude:
                            alert_type = "warning"
                            
                        AlertsManager.trigger_alert(
                            "Registro de Ocorrência",
                            f"{aluno_lbl} recebeu {tipo_info['nome'].upper()} por {usuario}!",
                            alert_type
                        )
            except Exception as e_alert:
                print(f"[GESTAO] Erro ao disparar alerta em tempo real: {e_alert}")
        else:
            ui.notify('[OFFLINE] Lançamento simulado criado', color='warning')
            ui.notify('Ação registrada com sucesso!', color='positive')
        
        # Reseta formulário
        state['new_desc'] = ''
        state['new_confirm'] = False
        state['new_dispensa'] = False
        app.storage.user['gestao_state'] = state
        
        data_service.clear_cache()
        render_gestao_content.refresh()
    except Exception as e:
        ui.notify(f"Erro ao salvar: {e}", color='negative')


# Renderiza a lista de cards
def render_actions_list(container, acoes_com_pontos, alunos_df, tipos_acao_df, state):
    container.clear()
    
    if acoes_com_pontos.empty:
        with container:
            ui.label('Nenhum lançamento registrado no banco de dados.').classes('text-grey italic self-center q-my-lg')
        return

    # Merge para pegar infos dos alunos
    acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
    alunos_df['id'] = alunos_df['id'].astype(str)
    
    df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo', 'url_foto']], left_on='aluno_id', right_on='id', how='left')
    df_display['nome_guerra'].fillna('N/A (Aluno Apagado)', inplace=True)

    # Aplica filtros
    df = df_display.copy()
    if state['filtro_pelotao'] != 'Todos':
        df = df[df['pelotao'].fillna('') == state['filtro_pelotao']]
    
    if state['filtro_aluno'] != 'Nenhum':
        df = df[df['nome_guerra'] == state['filtro_aluno']]
        
    if state['filtro_status'] != 'Todos':
        df = df[df['status'].fillna('') == state['filtro_status']]
        
    if state['filtro_tipo'] != 'Todos':
        df = df[df['nome'].fillna('') == state['filtro_tipo']]

    # Ordenação
    if state['ordenar_por'] == 'Mais Antigos':
        df = df.sort_values(by="data", ascending=True)
    elif state['ordenar_por'] == 'Aluno (A-Z)':
        df = df.sort_values(by="nome_guerra", ascending=True)
    else:
        df = df.sort_values(by="data", ascending=False)

    df.drop_duplicates(subset=['id_x'], keep='first', inplace=True)
    state['visible_ids'] = df['id_x'].dropna().astype(int).tolist()
    app.storage.user['gestao_state'] = state

    if df.empty:
        with container:
            ui.label('Nenhuma ação corresponde aos filtros selecionados.').classes('text-grey italic self-center q-my-lg')
        return

    with container:
        for _, acao in df.iterrows():
            acao_id = int(acao['id_x'])
            foto_url = acao.get('url_foto')
            image_src = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else 'https://via.placeholder.com/100?text=Sem+Foto'
            pts = acao.get('pontuacao_efetiva', 0.0)
            cor_pts = 'green' if pts > 0 else 'red' if pts < 0 else 'grey'
            dt_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')

            is_selected = state['selected_actions'].get(str(acao_id), False)

            with ui.card().classes('w-full q-pa-md no-shadow transition-all hover:bg-white/5').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-radius: 8px;'):
                with ui.row().classes('w-full justify-between items-center wrap md:no-wrap gap-4'):
                    
                    with ui.row().classes('items-center gap-4'):
                        ui.checkbox(
                            value=is_selected, 
                            on_change=lambda e, aid=acao_id: update_action_selection(aid, e.value)
                        ).props('dark dense')
                        
                        ui.avatar(size='64px').classes('shadow border border-gray-800').style(f"background-image: url('{image_src}'); background-size: cover; background-position: center;")
                        
                        with ui.column().classes('gap-0.5'):
                            ui.label(f"{acao['numero_interno']} - {acao['nome_guerra']} ({acao['pelotao']})").classes('text-white font-bold text-caption uppercase')
                            ui.label(f"{acao['tipo']} ({pts:+.1f} pts)").classes('text-weight-bold').style(f'color: {cor_pts}; font-size: 0.85rem;')
                            ui.label(acao.get('descricao') or 'Sem descrição.').classes('text-grey text-[11px] max-w-md ellipsis')
                            ui.label(f"Data: {dt_fmt} • Por: {acao.get('usuario','N/A')}").classes('text-grey-5 text-[10px]')

                    with ui.row().classes('items-center gap-2'):
                        status_atual = acao.get('status', 'Pendente')
                        
                        if status_atual == 'Pendente':
                            ui.button(
                                '🚀 Lançar', 
                                on_click=lambda aid=acao_id: update_single_status(aid, 'Lançado')
                            ).props('unelevated dense no-caps color=positive').classes('text-xs')
                            
                        if status_atual != 'Arquivado':
                            ui.button(
                                '🗑️ Arquivar', 
                                on_click=lambda aid=acao_id: update_single_status(aid, 'Arquivado')
                            ).props('unelevated dense no-caps color=negative').classes('text-xs')
                            
                        ui.button(
                            '✏️ Editar', 
                            on_click=lambda a=acao: edit_acao_dialog_open(a, tipos_acao_df)
                        ).props('outline dense no-caps color=grey-4').classes('text-xs')

                        if status_atual == 'Lançado':
                            ui.badge('Lançado', color='green').props('outline rounded')
                        elif status_atual == 'Arquivado':
                            ui.badge('Arquivado', color='orange').props('outline rounded')


def update_action_selection(action_id, value):
    state = app.storage.user['gestao_state']
    state['selected_actions'][str(action_id)] = value
    app.storage.user['gestao_state'] = state


def toggle_all_visible(value):
    state = app.storage.user['gestao_state']
    vids = state.get('visible_ids', [])
    for vid in vids:
        state['selected_actions'][str(vid)] = value
    app.storage.user['gestao_state'] = state
    render_gestao_content.refresh()


def update_single_status(action_id, status):
    try:
        db_conn = get_db_connection()
        if db_conn:
            db_conn.table('Acoes').update({'status': status}).eq('id', action_id).execute()
        else:
            ui.notify(f'[OFFLINE] Status atualizado para {status}', color='warning')
        ui.notify(f"Lançamento atualizado para {status}!", color='positive')
        data_service.clear_cache()
        render_gestao_content.refresh()
    except Exception as e:
        ui.notify(f"Erro ao atualizar status: {e}", color='negative')


def bulk_status(status):
    state = app.storage.user['gestao_state']
    selected_ids = [int(aid) for aid, is_sel in state['selected_actions'].items() if is_sel and int(aid) in state.get('visible_ids', [])]
    
    if not selected_ids:
        ui.notify('Nenhuma ação selecionada!', color='warning')
        return
        
    try:
        db_conn = get_db_connection()
        if db_conn:
            db_conn.table('Acoes').update({'status': status}).in_('id', selected_ids).execute()
        else:
            ui.notify(f'[OFFLINE] {len(selected_ids)} ações atualizadas', color='warning')
            
        ui.notify(f"{len(selected_ids)} ações atualizadas para '{status}'!", color='positive')
        state['selected_actions'] = {}
        app.storage.user['gestao_state'] = state
        data_service.clear_cache()
        render_gestao_content.refresh()
    except Exception as e:
        ui.notify(f"Erro em massa: {e}", color='negative')


def edit_acao_dialog_open(acao, tipos_acao_df):
    d = ui.dialog()
    with d, ui.card().classes('w-96 q-pa-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
        ui.label('EDITAR LANÇAMENTO').style(f'color: {THEME["primary"]}; font-weight: bold; font-size: 1.1rem;')
        ui.label(f"Aluno: {acao.get('nome_guerra')}").classes('text-grey text-caption q-mb-md')
        
        opcoes = list(tipos_acao_df['nome'].unique())
        tipo_sel = ui.select(opcoes, label='Tipo de Ação', value=acao.get('nome')).props('dark outlined dense w-full')
        
        dt_atual = pd.to_datetime(acao['data']).strftime('%Y-%m-%d')
        data_sel = ui.input('Data da Ação', value=dt_atual).props('dark outlined dense type=date w-full')
        
        desc_sel = ui.textarea('Descrição', value=acao.get('descricao', '')).props('dark outlined dense w-full')

        def salvar():
            try:
                tipo_info = tipos_acao_df[tipos_acao_df['nome'] == tipo_sel.value].iloc[0]
                update_data = {
                    'tipo_acao_id': str(tipo_info['id']),
                    'tipo': tipo_sel.value,
                    'data': data_sel.value,
                    'descricao': desc_sel.value
                }
                
                db_conn = get_db_connection()
                if db_conn:
                    db_conn.table('Acoes').update(update_data).eq('id', acao['id_x']).execute()
                else:
                    ui.notify('[OFFLINE] Edição de ação simulada', color='warning')
                    
                ui.notify('Ação atualizada com sucesso!', color='positive')
                d.close()
                data_service.clear_cache()
                render_gestao_content.refresh()
            except Exception as e:
                ui.notify(f"Erro ao salvar: {e}", color='negative')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancelar', on_click=d.close).props('flat color=grey')
            ui.button('Salvar', on_click=salvar).props('unelevated').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')
    d.open()


def bulk_edit_dialog_open(tipos_acao_df):
    state = app.storage.user['gestao_state']
    selected_ids = [int(aid) for aid, is_sel in state['selected_actions'].items() if is_sel and int(aid) in state.get('visible_ids', [])]
    
    if not selected_ids:
        ui.notify('Nenhuma ação selecionada!', color='warning')
        return

    d = ui.dialog()
    with d, ui.card().classes('w-96 q-pa-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
        ui.label('EDITAR EM MASSA').style(f'color: {THEME["primary"]}; font-weight: bold; font-size: 1.1rem;')
        ui.label(f"Alterando {len(selected_ids)} lançamentos selecionados.").classes('text-grey text-caption q-mb-md')
        
        opcoes = list(tipos_acao_df['nome'].unique())
        tipo_sel = ui.select(opcoes, label='Novo Tipo de Ação').props('dark outlined dense w-full')

        def salvar():
            if not tipo_sel.value:
                ui.notify('Selecione um tipo!', color='warning')
                return
            try:
                tipo_info = tipos_acao_df[tipos_acao_df['nome'] == tipo_sel.value].iloc[0]
                update_data = {
                    'tipo_acao_id': str(tipo_info['id']),
                    'tipo': tipo_sel.value
                }
                
                db_conn = get_db_connection()
                if db_conn:
                    db_conn.table('Acoes').update(update_data).in_('id', selected_ids).execute()
                else:
                    ui.notify('[OFFLINE] Edição em massa simulada', color='warning')
                    
                ui.notify('Ações atualizadas com sucesso!', color='positive')
                state['selected_actions'] = {}
                app.storage.user['gestao_state'] = state
                d.close()
                data_service.clear_cache()
                render_gestao_content.refresh()
            except Exception as e:
                ui.notify(f"Erro ao editar em massa: {e}", color='negative')

        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Cancelar', on_click=d.close).props('flat color=grey')
            ui.button('Aplicar', on_click=salvar).props('unelevated').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')
    d.open()


def preview_faia(aluno_id, acoes_com_pontos, alunos_df, tipos, incluir_lancador):
    if not aluno_id:
        ui.notify('Selecione um aluno primeiro!', color='warning')
        return

    aluno_df = alunos_df[alunos_df['id'].astype(str) == str(aluno_id)]
    if aluno_df.empty:
        return
        
    aluno_info = aluno_df.iloc[0]
    acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == str(aluno_id)] if not acoes_com_pontos.empty else pd.DataFrame()
    
    texto = formatar_relatorio_individual_txt(aluno_info, acoes_aluno, incluir_lancador, tipos)
    
    d = ui.dialog()
    with d, ui.card().classes('w-[500px] q-pa-lg max-h-[500px] scroll').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
        ui.label(f"PRÉ-VISUALIZAÇÃO FAIA").style(f'color: {THEME["primary"]}; font-weight: bold; font-size: 1.1rem;')
        ui.textarea(value=texto).props('dark readonly outlined autogrow').classes('w-full q-mt-md text-caption font-mono')
        
        with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
            ui.button('Fechar', on_click=d.close).props('flat color=grey')
            ui.button('Baixar TXT', on_click=lambda: trigger_single_txt(aluno_info, texto)).props('unelevated color=primary text-color=black font-bold')
    d.open()


def trigger_single_txt(aluno_info, texto):
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','N-A')}.txt"
    ui.download(texto.encode('utf-8'), filename=nome_arquivo)


def trigger_export(pelotao, aluno_id, acoes_com_pontos, alunos_df, tipos, incluir_lancador):
    app.storage.user['export_types'] = tipos
    app.storage.user['export_launcher'] = incluir_lancador

    if aluno_id:
        aluno_df = alunos_df[alunos_df['id'].astype(str) == str(aluno_id)]
        if not aluno_df.empty:
            aluno_info = aluno_df.iloc[0]
            acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == str(aluno_id)] if not acoes_com_pontos.empty else pd.DataFrame()
            texto = formatar_relatorio_individual_txt(aluno_info, acoes_aluno, incluir_lancador, tipos)
            trigger_single_txt(aluno_info, texto)
            ui.notify('FAIA individual baixada!', color='positive')
    elif pelotao:
        alunos_pelotao = alunos_df[alunos_df['pelotao'] == pelotao]
        if alunos_pelotao.empty:
            ui.notify('Nenhum aluno encontrado no pelotão selecionado!', color='warning')
            return

        with ui.spinner('Gerando arquivos ZIP...'):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for _, aluno_info in alunos_pelotao.iterrows():
                    aid = str(aluno_info['id'])
                    acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == aid] if not acoes_com_pontos.empty else pd.DataFrame()
                    texto = formatar_relatorio_individual_txt(aluno_info, acoes_aluno, incluir_lancador, tipos)
                    
                    nome_txt = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','N-A')}.txt"
                    zip_file.writestr(nome_txt, texto)

            ui.download(zip_buffer.getvalue(), filename=f"relatorios_FAIA_{pelotao}.zip")
            ui.notify(f"ZIP de FAIAs do pelotão {pelotao} baixado!", color='positive')
    else:
        ui.notify('Selecione um Pelotão ou Aluno!', color='warning')
