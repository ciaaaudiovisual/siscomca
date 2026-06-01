from nicegui import ui, app
import pandas as pd
from datetime import datetime
import numpy as np
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


def calcular_conceito_final(soma_pontos_acoes: float, media_academica_aluno: float, todos_alunos_df: pd.DataFrame, config_dict: dict) -> float:
    linha_base = float(config_dict.get('linha_base_conceito', 8.5))
    impacto_max_acoes = float(config_dict.get('impacto_max_acoes', 1.5))
    peso_academico = float(config_dict.get('peso_academico', 1.0))

    impacto_acoes = max(-impacto_max_acoes, min(soma_pontos_acoes, impacto_max_acoes))
    impacto_academico = 0.0
    
    if 'media_academica' in todos_alunos_df.columns and not todos_alunos_df.empty:
        medias_validas = pd.to_numeric(todos_alunos_df['media_academica'], errors='coerce').dropna()
        if not medias_validas.empty and medias_validas.max() > medias_validas.min():
            media_min_turma = medias_validas.min()
            media_max_turma = medias_validas.max()
            if (media_max_turma - media_min_turma) > 0:
                fator_normalizado = (media_academica_aluno - media_min_turma) / (media_max_turma - media_min_turma)
                impacto_academico = fator_normalizado * peso_academico
    
    conceito_final = linha_base + impacto_acoes + impacto_academico
    return max(0.0, min(conceito_final, 10.0))


def process_turma_data(pelotao_selecionado, sort_order):
    alunos_df_orig = data_service.get_alunos_data()
    acoes_df = data_service.get_acoes_data()
    tipos_acao_df = data_service.get_tipos_acao_data()
    config_df = data_service.get_config_data()

    if alunos_df_orig.empty:
        return {}, [], pd.DataFrame(), pd.DataFrame()

    alunos_df = alunos_df_orig[alunos_df_orig['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()

    if pelotao_selecionado != "Todos":
        alunos_df = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]

    if alunos_df.empty:
        return {}, [], pd.DataFrame(), pd.DataFrame()

    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    
    if not acoes_com_pontos.empty:
        acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
        soma_pontos_por_aluno = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
    else:
        soma_pontos_por_aluno = pd.Series(dtype=float)
        
    alunos_df['id'] = alunos_df['id'].astype(str)
    soma_pontos_por_aluno.index = soma_pontos_por_aluno.index.astype(str)
    
    alunos_df['soma_pontos_acoes'] = alunos_df['id'].map(soma_pontos_por_aluno).fillna(0.0)
    
    alunos_df['conceito_final'] = alunos_df.apply(
        lambda row: calcular_conceito_final(
            row['soma_pontos_acoes'],
            float(row.get('media_academica', 0.0)),
            alunos_df_orig,
            config_dict
        ),
        axis=1
    )
    
    alunos_df['media_academica_num'] = pd.to_numeric(alunos_df['media_academica'], errors='coerce').fillna(0.0)
    alunos_df['classificacao_final_prevista'] = ((alunos_df['media_academica_num'] * 3) + (alunos_df['conceito_final'] * 2)) / 5

    # Ordenação
    if 'Conceito' in sort_order:
        ascending_flag = (sort_order == 'Conceito (Menor > Maior)')
        alunos_df = alunos_df.sort_values('conceito_final', ascending=ascending_flag)
    elif sort_order == 'Ordem Alfabética':
        alunos_df = alunos_df.sort_values('nome_guerra')
    else:  # Padrão: Número Interno
        import re
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]
        alunos_df['sort_key'] = alunos_df['numero_interno'].apply(natural_sort_key)
        alunos_df = alunos_df.sort_values('sort_key').drop(columns=['sort_key'])

    student_id_list = alunos_df['id'].tolist()
    options = {}
    for _, aluno in alunos_df.iterrows():
        indicator = "⚠️ " if aluno['conceito_final'] < 7.0 else ""
        label = f"{indicator}{aluno['numero_interno']} - {aluno['nome_guerra']}"
        options[aluno['id']] = label
        
    return options, student_id_list, alunos_df, acoes_com_pontos


@ui.refreshable
def render_conselho_content():
    state = app.storage.user.get('conselho_state', {
        'filtro_pelotao': 'Todos',
        'filtro_ordem': 'Número Interno',
        'current_student_idx': 0,
        'quick_desc': ''
    })

    # Recarrega dados essenciais
    alunos_df_geral = data_service.get_alunos_data()
    if alunos_df_geral.empty:
        with ui.column().classes('w-full q-pa-lg items-center justify-center'):
            ui.icon('warning', color='warning', size='4rem')
            ui.label('Banco de dados vazio ou sem alunos cadastrados.').classes('text-lg font-bold q-mt-md').style(f'color: {THEME["text_main"]}')
        return

    opcoes_pelotao = ["Todos"] + sorted(list(alunos_df_geral['pelotao'].dropna().unique()))
    opcoes_ordem = ['Número Interno', 'Conceito (Maior > Menor)', 'Conceito (Menor > Maior)', 'Ordem Alfabética']

    # Processamento
    opcoes_alunos, student_id_list, alunos_processados_df, acoes_com_pontos = process_turma_data(
        state['filtro_pelotao'], 
        state['filtro_ordem']
    )

    if not student_id_list:
        with ui.column().classes('w-full q-pa-lg items-center justify-center'):
            ui.label('Nenhum aluno encontrado para os filtros selecionados.').classes('italic').style(f'color: {THEME["text_dim"]}')
            ui.select(opcoes_pelotao, label='Filtrar Pelotão', value=state['filtro_pelotao'], on_change=lambda e: update_filter('filtro_pelotao', e.value)).props('dark outlined dense').classes('w-44 q-mt-md')
        return

    # Corrige índice se transbordar
    if state['current_student_idx'] >= len(student_id_list):
        state['current_student_idx'] = 0
        app.storage.user['conselho_state'] = state

    current_student_id = student_id_list[state['current_student_idx']]
    aluno_selecionado = alunos_processados_df[alunos_processados_df['id'] == current_student_id].iloc[0]

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Conselho de Avaliação', 'Painel de Mapeamento, Notas e Avaliação de Desempenho')

        # --- BARRA DE CONTROLE SUPERIOR ---
        with theme.card_base().classes('w-full q-pa-md'):
            with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                with ui.row().classes('items-center gap-4'):
                    # Pelotão
                    ui.select(opcoes_pelotao, label='Filtrar Pelotão', value=state['filtro_pelotao'], on_change=lambda e: update_filter('filtro_pelotao', e.value)).props('dark outlined dense').classes('w-40')
                    # Ordem
                    ui.select(opcoes_ordem, label='Ordenar por', value=state['filtro_ordem'], on_change=lambda e: update_filter('filtro_ordem', e.value)).props('dark outlined dense').classes('w-48')
                    # Aluno Select
                    ui.select(opcoes_alunos, label='Militar sob Avaliação', value=current_student_id, on_change=lambda e: select_student_by_id(e.value, student_id_list)).props('dark outlined dense').classes('w-64')

                # Navegação
                with ui.row().classes('gap-2'):
                    btn_prev = ui.button(
                        '< Anterior', 
                        on_click=lambda: change_student(-1, student_id_list), 
                    ).props('unelevated no-caps').classes('text-xs font-bold').style(f'background: #1b2535; border: 1px solid rgba(0, 229, 255, 0.2); color: #e2e8f0;')
                    btn_prev.enabled = (state['current_student_idx'] > 0)
                    
                    btn_next = ui.button(
                        'Próximo >', 
                        on_click=lambda: change_student(1, student_id_list), 
                    ).props('unelevated no-caps').classes('text-xs font-bold').style(f'background: #1b2535; border: 1px solid rgba(0, 229, 255, 0.2); color: #e2e8f0;')
                    btn_next.enabled = (state['current_student_idx'] < len(student_id_list) - 1)

        # --- ÁREA CENTRAL: DADOS E MÉTRICAS ---
        with ui.row().classes('w-full gap-6 no-wrap wrap-mobile items-stretch'):
            # Foto e Identificação
            with theme.card_base().classes('col-grow md:w-1/3 p-6 items-center text-center'):
                foto_url = aluno_selecionado.get('url_foto')
                
                # Fallback de avatar tático 100% offline em SVG
                OFFLINE_AVATAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='rgb(27,37,53)'/><circle cx='50' cy='40' r='20' fill='rgb(100,116,139)'/><path d='M20,90 C20,70 80,70 80,90 Z' fill='rgb(100,116,139)'/></svg>"
                
                if isinstance(foto_url, str) and (foto_url.startswith('http') or 'assets' in foto_url):
                    image_src = foto_url if foto_url.startswith('/') or foto_url.startswith('http') else '/' + foto_url
                else:
                    image_src = OFFLINE_AVATAR
                
                # ui.image garante proporção quadrada e suporta data URLs de forma nativa e isolada
                ui.image(image_src).classes('shadow q-mb-md').style(
                    f"width: 120px; height: 120px; border: {THEME['border']}; border-radius: 8px; object-fit: cover; background-color: rgb(27,37,53);"
                )
                
                ui.label(aluno_selecionado['nome_guerra']).classes('text-lg font-bold uppercase').style(f'color: {THEME["text_main"]}')
                ui.label(f"Nº Interno: {aluno_selecionado['numero_interno']}").classes('text-xs font-semibold q-mb-sm').style(f'color: {THEME["primary"]}')
                ui.label(f"Pelotão: {aluno_selecionado['pelotao']} • Esp: {aluno_selecionado.get('especialidade') or 'N/A'}").classes('text-caption').style(f'color: {THEME["text_dim"]}')
            
            # Métricas / KPIs
            with theme.card_base().classes('col-grow md:w-2/3 p-6 justify-around'):
                ui.label('MÉTRICAS OPERACIONAIS').classes('cyber-title text-xs').style(f'color: {THEME["text_dim"]}')
                
                with ui.row().classes('w-full justify-around items-center gap-4 q-mt-md'):
                    kpi_widget('PONTOS AÇÕES', f"{aluno_selecionado['soma_pontos_acoes']:+.2f}", '#00a2ff')
                    kpi_widget('CONCEITO MILITAR', f"{aluno_selecionado['conceito_final']:.3f}", THEME['success'] if aluno_selecionado['conceito_final'] >= 7.0 else THEME['danger'])
                    kpi_widget('MÉDIA ACADÊMICA', f"{aluno_selecionado['media_academica_num']:.3f}", '#ffb300')
                    kpi_widget('PREVISÃO NOTA FINAL', f"{aluno_selecionado['classificacao_final_prevista']:.3f}", '#f8fafc', help_text='Cálculo: (Média Acadêmica * 3 + Concept Final * 2) / 5')

        # --- HISTÓRICO DE ANOTAÇÕES (POSITIVAS / NEGATIVAS) ---
        acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == current_student_id].copy() if not acoes_com_pontos.empty else pd.DataFrame()
        if not acoes_aluno.empty:
            acoes_aluno['pontuacao_efetiva'] = pd.to_numeric(acoes_aluno['pontuacao_efetiva'], errors='coerce').fillna(0)
            positivas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] > 0].sort_values('data', ascending=False)
            negativas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] < 0].sort_values('data', ascending=False)
            neutras = acoes_aluno[acoes_aluno['pontuacao_efetiva'] == 0].sort_values('data', ascending=False)
        else:
            positivas, negativas, neutras = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Grid Tailwind garante alinhamento 50/50 perfeito e reponsividade
        with ui.element('div').classes('grid grid-cols-1 md:grid-cols-2 gap-6 w-full'):
            # Positivas
            with theme.card_base().classes('p-6'):
                ui.label('✅ ANOTAÇÕES POSITIVAS').classes('cyber-title text-xs').style(f'color: {THEME["success"]}')
                with ui.column().classes('w-full gap-3 q-mt-md scroll-area max-h-60 overflow-y-auto'):
                    if positivas.empty:
                        ui.label('Nenhuma anotação positiva.').classes('italic text-caption').style(f'color: {THEME["text_dim"]}')
                    else:
                        for _, acao in positivas.iterrows():
                            render_acao_item(acao, THEME['success'])

            # Negativas
            with theme.card_base().classes('p-6'):
                ui.label('⚠️ ANOTAÇÕES NEGATIVAS').classes('cyber-title text-xs').style(f'color: {THEME["danger"]}')
                with ui.column().classes('w-full gap-3 q-mt-md scroll-area max-h-60 overflow-y-auto'):
                    if negativas.empty:
                        ui.label('Nenhuma anotação negativa.').classes('italic text-caption').style(f'color: {THEME["text_dim"]}')
                    else:
                        for _, acao in negativas.iterrows():
                            render_acao_item(acao, THEME['danger'])

        # Neutras (Expander)
        with ui.expansion('⚪ Anotações Neutras', icon='info').classes('w-full rounded-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
            with ui.column().classes('w-full gap-3 q-pa-sm'):
                if neutras.empty:
                    ui.label('Nenhuma anotação neutra.').classes('italic text-caption').style(f'color: {THEME["text_dim"]}')
                else:
                    for _, acao in neutras.iterrows():
                        render_acao_item(acao, THEME['text_dim'])

        # --- ANOTAÇÃO RÁPIDA NO CONSELHO ---
        with theme.card_base().classes('w-full q-pa-md'):
            ui.label('➕ ADICIONAR ANOTAÇÃO RÁPIDA').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
            ui.label('Esta anotação será adicionada diretamente com status "Pendente" para revisão na Gestão de Ações.').classes('text-caption q-mb-md').style(f'color: {THEME["text_dim"]}')
            
            tipos_acao_df = data_service.get_tipos_acao_data()
            if tipos_acao_df.empty:
                ui.label('Sem tipos de ações no banco.').classes('italic').style(f'color: {THEME["text_dim"]}')
            else:
                with ui.row().classes('w-full items-end gap-4'):
                    tipo_opcoes = sorted(list(tipos_acao_df['nome'].unique()))
                    quick_tipo = ui.select(tipo_opcoes, label='Tipo de Ação').props('dark outlined dense').classes('w-64')
                    
                    data_atual_str = datetime.now().strftime('%d/%m/%Y')
                    default_desc = f"Anotação realizada durante o Conselho de Avaliação em {data_atual_str}."
                    quick_desc_inp = ui.input('Descrição', value=default_desc).props('dark outlined dense').classes('col-grow')
                    
                    ui.button('Registrar', on_click=lambda: salvar_anotacao_rapida(quick_tipo.value, quick_desc_inp.value, aluno_selecionado)).props('unelevated dense').style(f'background: {THEME["primary"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow q-px-md q-py-xs')

        # --- RANKINGS / CLASSIFICAÇÕES ---
        # Exclui alunos com "Q" no número (ex: Quadro Técnico/Reservistas se houver)
        df_para_classificar = alunos_processados_df[~alunos_processados_df['numero_interno'].astype(str).str.startswith('Q')].copy()

        # Classificação por Conceito
        with ui.expansion('🏆 Classificação por Conceito Final (Comportamento)', icon='military_tech').classes('w-full rounded-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
            df_class_conceito = df_para_classificar.sort_values('conceito_final', ascending=False)
            df_class_conceito.insert(0, 'Class.', range(1, 1 + len(df_class_conceito)))
            render_ranking_grid(df_class_conceito, 'conceito_final')

        # Classificação Final Prevista
        with ui.expansion('🎓 Classificação Final Prevista (Nota Acadêmica + Comportamento)', icon='school').classes('w-full rounded-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
            df_class_final = df_para_classificar.sort_values('classificacao_final_prevista', ascending=False)
            df_class_final.insert(0, 'Class.', range(1, 1 + len(df_class_final)))
            render_ranking_grid(df_class_final, 'classificacao_final_prevista')


def render_page():
    # Inicializa estado da página
    if 'conselho_state' not in app.storage.user:
        app.storage.user['conselho_state'] = {
            'filtro_pelotao': 'Todos',
            'filtro_ordem': 'Número Interno',
            'current_student_idx': 0,
            'quick_desc': ''
        }
    render_conselho_content()


def update_filter(key, val):
    state = app.storage.user['conselho_state']
    state[key] = val
    state['current_student_idx'] = 0 # Reset índice
    app.storage.user['conselho_state'] = state
    render_conselho_content.refresh()


def select_student_by_id(student_id, student_id_list):
    state = app.storage.user['conselho_state']
    if student_id in student_id_list:
        state['current_student_idx'] = student_id_list.index(student_id)
        app.storage.user['conselho_state'] = state
        render_conselho_content.refresh()


def change_student(delta, student_id_list):
    state = app.storage.user['conselho_state']
    new_idx = state['current_student_idx'] + delta
    if 0 <= new_idx < len(student_id_list):
        state['current_student_idx'] = new_idx
        app.storage.user['conselho_state'] = state
        render_conselho_content.refresh()


def kpi_widget(label, value, color, help_text=None):
    with ui.column().classes('items-center gap-0.5 q-pa-sm rounded-lg').style('background: rgba(0, 229, 255, 0.04); border: 1px solid rgba(0, 229, 255, 0.1); width: 140px;'):
        ui.label(label).style('font-size: 0.65rem; color: #888; font-weight: bold; letter-spacing: 0.5px;')
        ui.label(value).style(f'color: {color}; font-size: 1.5rem; font-weight: bold;')
        if help_text:
            ui.label('(i) Fórmula').classes('text-[9px]').style('color: #64748b; cursor: pointer;').tooltip(help_text)


def render_acao_item(acao, cor):
    dt_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
    pts = acao.get('pontuacao_efetiva', 0.0)
    with ui.row().classes('w-full justify-between items-start q-pb-xs gap-2').style('border-bottom: 1px solid rgba(0, 229, 255, 0.08)'):
        with ui.column().classes('gap-0'):
            ui.label(f"{dt_fmt} - {acao.get('nome', 'Ação')}").classes('text-xs font-semibold').style(f'color: {THEME["text_main"]}')
            ui.label(acao.get('descricao') or 'Sem descrição.').classes('text-[10px] italic').style(f'color: {THEME["text_dim"]}')
        ui.label(f"{pts:+.1f}").classes('text-xs font-bold').style(f'color: {cor};')


def render_ranking_grid(df_rank, col_score):
    if df_rank.empty:
        ui.label('Sem dados.').classes('italic text-caption q-pa-md').style(f'color: {THEME["text_dim"]}')
        return

    # Divide em até 5 colunas de forma segura para garantir objetos DataFrame nativos
    n_rows = len(df_rank)
    chunk_size = int(np.ceil(n_rows / 5)) if n_rows > 0 else 1
    cols_data = [df_rank.iloc[i : i + chunk_size] for i in range(0, n_rows, chunk_size)]
    # Garante pelo menos 5 elementos na lista para renderização simétrica
    while len(cols_data) < 5:
        cols_data.append(pd.DataFrame())
    
    with ui.row().classes('w-full gap-4 q-pa-md wrap md:no-wrap'):
        for i, c_data in enumerate(cols_data):
            if c_data.empty:
                continue
            with ui.column().classes('col-grow gap-1 q-pr-sm').style('border-right: 1px solid rgba(0, 229, 255, 0.08)' if i < len(cols_data)-1 else ''):
                for _, row in c_data.iterrows():
                    ui.label(f"{row['Class.']}º: {row['nome_guerra']} ({row[col_score]:.2f})").classes('text-xs').style(f'color: {THEME["text_main"]}')


def salvar_anotacao_rapida(tipo, desc, aluno):
    if not tipo:
        ui.notify('Selecione o tipo!', color='warning')
        return
        
    try:
        tipos_df = data_service.get_tipos_acao_data()
        tipo_info = tipos_df[tipos_df['nome'] == tipo].iloc[0]
        
        db_conn = get_db_connection()
        usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Anonimo')
        
        nova_acao = {
            'aluno_id': str(aluno['id']),
            'tipo_acao_id': str(tipo_info['id']),
            'tipo': tipo_info['nome'],
            'descricao': desc,
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'usuario': usuario,
            'status': 'Pendente'
        }
        
        if db_conn:
            db_conn.table('Acoes').insert(nova_acao).execute()
        else:
            ui.notify('[OFFLINE] Anotação rápida simulada criada', color='warning')
            
        ui.notify('Anotação rápida inserida na fila de revisão!', color='positive')
        data_service.clear_cache()
        render_conselho_content.refresh()
    except Exception as e:
        ui.notify(f"Erro ao salvar: {e}", color='negative')
