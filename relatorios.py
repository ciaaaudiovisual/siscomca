from nicegui import ui, app
import pandas as pd
from datetime import datetime, date, timedelta
import numpy as np
import theme
from services import data_service
from conselho_avaliacao import calcular_pontuacao_efetiva, calcular_conceito_final

THEME = theme.colors

def render_page():
    # Inicializa estado na sessão do usuário
    state = app.storage.user.setdefault('relatorios_state', {
        'view_by': 'Conceito Final',  # 'Conceito Final' ou 'Variação de Pontos'
        'filtro_tipo_acao': 'Todos',
        'filtro_periodo': 'Todo o Período',
        'filtro_pelotao': 'Todos os Pelotões',
        'selected_tab': 'Gráficos',
        'grafico_selecionado': 'Média por Pelotão',
        'aluno_evolucao_id': None
    })

    # Carrega dados essenciais
    alunos_df = data_service.get_alunos_data()
    active_year = app.storage.user.get('ano_letivo_ativo', '2026')
    if 'ano_letivo' in alunos_df.columns:
        alunos_df = alunos_df[alunos_df['ano_letivo'].fillna('2025').astype(str).str.strip() == active_year]
    acoes_df = data_service.get_acoes_data()
    tipos_acao_df = data_service.get_tipos_acao_data()
    config_df = data_service.get_config_data()

    if alunos_df.empty:
        with ui.column().classes('w-full q-pa-lg gap-6 items-center justify-center text-center'):
            ui.icon('warning', color='warning', size='4rem')
            ui.label('SEM ALUNOS CADASTRADOS').classes('cyber-title text-md font-bold q-mt-md').style(f'color: {THEME["text_dim"]}')
            ui.label('Cadastre alunos no sistema para visualizar os relatórios acadêmicos.').classes('text-xs').style(f'color: {THEME["text_dim"]}')
        return

    # Opções dinâmicas para filtros
    opcoes_pelotoes = ["Todos os Pelotões"] + sorted(list(alunos_df['pelotao'].dropna().unique()))
    opcoes_tipos_acao = ["Todos"]
    if not tipos_acao_df.empty:
        opcoes_tipos_acao += sorted(list(tipos_acao_df['nome'].dropna().unique()))
    opcoes_periodos = ["Todo o Período", "Últimos 7 dias", "Últimos 30 dias", "Este Mês"]

    # --- CONTAINER PRINCIPAL ---
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Relatórios e Análises', 'Painel de Controle, Gráficos de Evolução e Rankings')

        # --- PAINEL DE CONTROLE DE FILTROS ---
        with theme.card_base().classes('w-full q-pa-md'):
            with ui.column().classes('w-full gap-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('dashboard', size='1.5rem').style(f'color: {THEME["primary"]}')
                    ui.label('Painel de Controle de Relatórios').classes('text-sm font-bold uppercase').style(f'color: {THEME["text_main"]}')
                ui.separator().style('background-color: rgba(0, 229, 255, 0.15);')

                # Filtros Grid
                with ui.grid(columns='1 sm:grid-cols-2 md:grid-cols-4').classes('w-full gap-4 items-end'):
                    # Visualizar por (Radio)
                    with ui.column().classes('gap-1'):
                        ui.label('Visualizar dados por:').classes('text-[10px] font-bold text-grey-5 uppercase')
                        ui.radio(
                            ['Conceito Final', 'Variação de Pontos'],
                            value=state['view_by'],
                            on_change=lambda e: update_state('view_by', e.value)
                        ).props('dark inline dense').classes('text-xs text-grey-3')

                    # Filtrar por Tipo de Ação (Select)
                    ui.select(
                        opcoes_tipos_acao,
                        label='Filtrar por Tipo de Ação',
                        value=state['filtro_tipo_acao'],
                        on_change=lambda e: update_state('filtro_tipo_acao', e.value)
                    ).props('dark outlined dense').classes('w-full')

                    # Filtrar Período (Select)
                    ui.select(
                        opcoes_periodos,
                        label='Filtrar Período',
                        value=state['filtro_periodo'],
                        on_change=lambda e: update_state('filtro_periodo', e.value)
                    ).props('dark outlined dense').classes('w-full')

                    # Filtrar por Pelotão (Select)
                    ui.select(
                        opcoes_pelotoes,
                        label='Filtrar por Pelotão',
                        value=state['filtro_pelotao'],
                        on_change=lambda e: update_state('filtro_pelotao', e.value)
                    ).props('dark outlined dense').classes('w-full')

        # --- PROCESSAMENTO DOS DADOS FILTRADOS ---
        # 1. Filtra alunos ativos
        df_ativos = alunos_df[alunos_df['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()
        if state['filtro_pelotao'] != 'Todos os Pelotões':
            df_ativos = df_ativos[df_ativos['pelotao'] == state['filtro_pelotao']]

        # 2. Processa ocorrências com pontos efetivos
        acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
        
        # Filtra ocorrências por período
        if not acoes_com_pontos.empty:
            acoes_com_pontos['data_dt'] = pd.to_datetime(acoes_com_pontos['data'], errors='coerce')
            
            # Filtro de tipo de ação
            if state['filtro_tipo_acao'] != 'Todos':
                acoes_com_pontos = acoes_com_pontos[acoes_com_pontos['nome'] == state['filtro_tipo_acao']]
                
            # Filtro de período de data
            hoje = datetime.now()
            if state['filtro_periodo'] == 'Últimos 7 dias':
                limite = hoje - timedelta(days=7)
                acoes_com_pontos = acoes_com_pontos[acoes_com_pontos['data_dt'] >= limite]
            elif state['filtro_periodo'] == 'Últimos 30 dias':
                limite = hoje - timedelta(days=30)
                acoes_com_pontos = acoes_com_pontos[acoes_com_pontos['data_dt'] >= limite]
            elif state['filtro_periodo'] == 'Este Mês':
                limite = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                acoes_com_pontos = acoes_com_pontos[acoes_com_pontos['data_dt'] >= limite]

        # 3. Calcula pontuação acumulada e conceito final de cada aluno
        if not acoes_com_pontos.empty:
            acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
            soma_pontos = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
        else:
            soma_pontos = pd.Series(dtype=float)

        config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
        
        df_ativos['id_str'] = df_ativos['id'].astype(str)
        soma_pontos.index = soma_pontos.index.astype(str)
        
        df_ativos['soma_pontos_acoes'] = df_ativos['id_str'].map(soma_pontos).fillna(0.0)
        df_ativos['conceito_final'] = df_ativos.apply(
            lambda r: calcular_conceito_final(
                r['soma_pontos_acoes'],
                pd.to_numeric(r.get('media_academica', 0.0), errors='coerce') or 0.0,
                alunos_df,
                config_dict
            ),
            axis=1
        )
        df_ativos['media_academica_num'] = pd.to_numeric(df_ativos['media_academica'], errors='coerce').fillna(0.0)

        # Escolhe a coluna de score a exibir/ordenar dependendo da visualização
        score_col = 'conceito_final' if state['view_by'] == 'Conceito Final' else 'soma_pontos_acoes'
        df_ativos_sorted = df_ativos.sort_values(by=score_col, ascending=False)

        # Se o aluno selecionado para a evolução não estiver definido, pega o primeiro
        if not state['aluno_evolucao_id'] and not df_ativos.empty:
            state['aluno_evolucao_id'] = str(df_ativos.iloc[0]['id'])

        # --- NAVEGAÇÃO POR ABAS ---
        with ui.tabs().classes('w-full border-b border-white/10') as tabs:
            tab_graficos = ui.tab('Gráficos', icon='bar_chart')
            tab_rankings = ui.tab('Rankings', icon='military_tech')
            tab_evolucao = ui.tab('Evolução', icon='show_chart')
        
        # Sincroniza abas com estado
        tabs.value = state['selected_tab']
        tabs.on('change', lambda e: update_state('selected_tab', e.value))

        with ui.tab_panels(tabs, value=state['selected_tab']).classes('w-full bg-transparent q-pa-none gap-6'):
            
            # ──────────────────────────────────────────────────────────
            # ABA 1: GRÁFICOS
            # ──────────────────────────────────────────────────────────
            with ui.tab_panel(tab_graficos).classes('bg-transparent q-pa-none gap-6'):
                with ui.column().classes('w-full gap-6'):
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.row().classes('w-full items-center justify-between'):
                            ui.label('Análise Gráfica').classes('cyber-title text-sm font-bold text-white')
                            ui.select(
                                ['Média por Pelotão', 'Distribuição Geral', 'Volume de Ocorrências'],
                                label='Selecione o tipo de gráfico',
                                value=state['grafico_selecionado'],
                                on_change=lambda e: update_state('grafico_selecionado', e.value)
                            ).props('dark outlined dense').classes('w-64')

                    # Renderização do gráfico selecionado
                    with theme.card_base().classes('w-full q-pa-lg items-center justify-center min-h-[400px]'):
                        if state['grafico_selecionado'] == 'Média por Pelotão':
                            # Agrupa por pelotão e tira a média
                            pel_avg = df_ativos.groupby('pelotao')[score_col].mean().reset_index()
                            pel_avg = pel_avg.sort_values(by=score_col, ascending=False)
                            
                            pels = pel_avg['pelotao'].tolist()
                            vals = [round(float(v), 2) for v in pel_avg[score_col].tolist()]
                            
                            if not vals:
                                ui.label('Sem dados para renderizar o gráfico.').classes('italic text-xs text-grey-5')
                            else:
                                ui.echart({
                                    'backgroundColor': 'transparent',
                                    'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
                                    'xAxis': {
                                        'type': 'category',
                                        'data': pels,
                                        'axisLabel': {'color': '#94a3b8'},
                                        'axisLine': {'lineStyle': {'color': 'rgba(255,255,255,0.1)'}}
                                    },
                                    'yAxis': {
                                        'type': 'value',
                                        'max': 10 if state['view_by'] == 'Conceito Final' else None,
                                        'axisLabel': {'color': '#94a3b8'},
                                        'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.05)'}}
                                    },
                                    'series': [{
                                        'name': state['view_by'],
                                        'type': 'bar',
                                        'data': vals,
                                        'itemStyle': {
                                            'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1, 'colorStops': [
                                                {'offset': 0, 'color': THEME['primary']},
                                                {'offset': 1, 'color': '#006064'}
                                            ]},
                                            'borderRadius': [4, 4, 0, 0]
                                        },
                                        'label': {'show': True, 'position': 'top', 'color': '#fff'}
                                    }]
                                }).classes('w-full h-80')

                        elif state['grafico_selecionado'] == 'Distribuição Geral':
                            if state['view_by'] == 'Conceito Final':
                                excelente = len(df_ativos[df_ativos['conceito_final'] >= 9.0])
                                bom = len(df_ativos[(df_ativos['conceito_final'] >= 8.0) & (df_ativos['conceito_final'] < 9.0)])
                                regular = len(df_ativos[(df_ativos['conceito_final'] >= 7.0) & (df_ativos['conceito_final'] < 8.0)])
                                insuficiente = len(df_ativos[df_ativos['conceito_final'] < 7.0])
                                
                                ui.echart({
                                    'backgroundColor': 'transparent',
                                    'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} alunos ({d}%)'},
                                    'legend': {'bottom': '0%', 'left': 'center', 'textStyle': {'color': '#94a3b8'}},
                                    'series': [{
                                        'type': 'pie',
                                        'radius': ['40%', '70%'],
                                        'avoidLabelOverlap': False,
                                        'itemStyle': {'borderRadius': 8, 'borderColor': '#131a26', 'borderWidth': 2},
                                        'data': [
                                            {'value': excelente, 'name': 'Excelente (>=9.0)', 'itemStyle': {'color': THEME['success']}},
                                            {'value': bom, 'name': 'Bom (8.0-8.9)', 'itemStyle': {'color': THEME['primary']}},
                                            {'value': regular, 'name': 'Regular (7.0-7.9)', 'itemStyle': {'color': '#ffb300'}},
                                            {'value': insuficiente, 'name': 'Insuficiente (<7.0)', 'itemStyle': {'color': THEME['danger']}}
                                        ]
                                    }]
                                }).classes('w-full h-80')
                            else:
                                # Distribuição por variação de pontos
                                pos = len(df_ativos[df_ativos['soma_pontos_acoes'] > 0])
                                zero = len(df_ativos[df_ativos['soma_pontos_acoes'] == 0])
                                neg = len(df_ativos[df_ativos['soma_pontos_acoes'] < 0])
                                
                                ui.echart({
                                    'backgroundColor': 'transparent',
                                    'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} alunos ({d}%)'},
                                    'legend': {'bottom': '0%', 'left': 'center', 'textStyle': {'color': '#94a3b8'}},
                                    'series': [{
                                        'type': 'pie',
                                        'radius': ['40%', '70%'],
                                        'avoidLabelOverlap': False,
                                        'itemStyle': {'borderRadius': 8, 'borderColor': '#131a26', 'borderWidth': 2},
                                        'data': [
                                            {'value': pos, 'name': 'Pontuação Positiva (> 0)', 'itemStyle': {'color': THEME['success']}},
                                            {'value': zero, 'name': 'Sem Alteração (= 0)', 'itemStyle': {'color': '#64748b'}},
                                            {'value': neg, 'name': 'Pontuação Negativa (< 0)', 'itemStyle': {'color': THEME['danger']}}
                                        ]
                                    }]
                                }).classes('w-full h-80')

                        elif state['grafico_selecionado'] == 'Volume de Ocorrências':
                            # Volume de Ocorrências por tipo
                            if acoes_com_pontos.empty:
                                ui.label('Nenhuma ocorrência registrada no período selecionado.').classes('italic text-xs text-grey-5')
                            else:
                                count_tipo = acoes_com_pontos['nome'].value_counts().reset_index()
                                count_tipo.columns = ['tipo', 'qtd']
                                count_tipo = count_tipo.head(8) # Top 8 ocorrências
                                
                                ui.echart({
                                    'backgroundColor': 'transparent',
                                    'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
                                    'xAxis': {
                                        'type': 'value',
                                        'axisLabel': {'color': '#94a3b8'},
                                        'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.05)'}}
                                    },
                                    'yAxis': {
                                        'type': 'category',
                                        'data': count_tipo['tipo'].tolist(),
                                        'axisLabel': {'color': '#94a3b8'}
                                    },
                                    'series': [{
                                        'name': 'Ocorrências',
                                        'type': 'bar',
                                        'data': count_tipo['qtd'].tolist(),
                                        'itemStyle': {
                                            'color': '#00a2ff',
                                            'borderRadius': [0, 4, 4, 0]
                                        }
                                    }]
                                }).classes('w-full h-80')

            # ──────────────────────────────────────────────────────────
            # ABA 2: RANKINGS
            # ──────────────────────────────────────────────────────────
            with ui.tab_panel(tab_rankings).classes('bg-transparent q-pa-none gap-6'):
                with theme.card_base().classes('w-full q-pa-md'):
                    ui.label('Classificação Geral (Leaderboard)').classes('cyber-title text-sm font-bold text-white q-mb-md')
                    
                    if df_ativos_sorted.empty:
                        ui.label('Nenhum aluno encontrado para os filtros selecionados.').classes('italic text-xs text-grey-5')
                    else:
                        with ui.column().classes('w-full gap-2'):
                            # Header da tabela
                            with ui.row().classes('w-full items-center justify-between text-[10px] font-bold text-grey-5 uppercase q-px-md py-1 border-b border-white/10'):
                                ui.label('Posição').classes('w-16')
                                ui.label('Militar').classes('col-grow')
                                ui.label('Pelotão').classes('w-28 text-center')
                                ui.label(state['view_by']).classes('w-32 text-right')

                            # Linhas dos alunos
                            for idx, (_, row) in enumerate(df_ativos_sorted.iterrows()):
                                rank = idx + 1
                                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                                val_lbl = f"{row[score_col]:.2f}" if score_col == 'conceito_final' else f"{row[score_col]:+.1f}"
                                score_color = THEME['success'] if row[score_col] >= 8.5 else (THEME['primary'] if row[score_col] >= 7.0 else THEME['danger'])
                                
                                with ui.row().classes('w-full items-center justify-between text-xs q-px-md py-2 border-b border-white/5 hover:bg-white/5 rounded transition-colors'):
                                    ui.label(medal).classes('w-16 font-mono font-black text-amber-5' if rank <= 3 else 'w-16 font-mono text-grey-5')
                                    ui.label(f"{row['numero_interno']} — {row['nome_guerra'].upper()}").classes('col-grow font-bold text-white')
                                    ui.label(row['pelotao']).classes('w-28 text-center text-grey-4')
                                    ui.label(val_lbl).classes('w-32 text-right font-mono font-bold').style(f'color: {score_color}')

            # ──────────────────────────────────────────────────────────
            # ABA 3: EVOLUÇÃO
            # ──────────────────────────────────────────────────────────
            with ui.tab_panel(tab_evolucao).classes('bg-transparent q-pa-none gap-6'):
                with ui.column().classes('w-full gap-6'):
                    with theme.card_base().classes('w-full q-pa-md'):
                        with ui.row().classes('w-full items-end justify-between wrap gap-4'):
                            with ui.column().classes('gap-1'):
                                ui.label('Evolução do Aluno').classes('cyber-title text-sm font-bold text-white')
                                ui.label('Selecione um aluno para traçar o gráfico de evolução histórica do seu conceito.').classes('text-[10px] text-grey-5')
                            
                            # Select de alunos para evolução
                            aluno_opcoes = {str(r['id']): f"{r['numero_interno']} - {r['nome_guerra']}" for _, r in df_ativos.iterrows()}
                            ui.select(
                                aluno_opcoes,
                                label='Militar sob Análise',
                                value=state['aluno_evolucao_id'],
                                on_change=lambda e: update_state('aluno_evolucao_id', e.value)
                            ).props('dark outlined dense search').classes('w-80')

                    # Gráfico de evolução do aluno
                    with theme.card_base().classes('w-full q-pa-lg items-center justify-center min-h-[400px]'):
                        if state['aluno_evolucao_id']:
                            dates, concepts = compute_student_evolution(
                                state['aluno_evolucao_id'],
                                alunos_df,
                                acoes_df,
                                tipos_acao_df,
                                config_df
                            )
                            
                            if not dates:
                                ui.label('Sem dados de evolução para o aluno selecionado.').classes('italic text-xs text-grey-5')
                            else:
                                ui.echart({
                                    'backgroundColor': 'transparent',
                                    'tooltip': {
                                        'trigger': 'axis',
                                        'formatter': 'Data: {b}<br/>Conceito: {c}'
                                    },
                                    'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'containLabel': True},
                                    'xAxis': {
                                        'type': 'category',
                                        'data': dates,
                                        'axisLabel': {'color': '#94a3b8'},
                                        'axisLine': {'lineStyle': {'color': 'rgba(255,255,255,0.1)'}}
                                    },
                                    'yAxis': {
                                        'type': 'value',
                                        'min': 0,
                                        'max': 10,
                                        'axisLabel': {'color': '#94a3b8'},
                                        'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.05)'}}
                                    },
                                    'series': [{
                                        'name': 'Conceito',
                                        'type': 'line',
                                        'data': concepts,
                                        'smooth': True,
                                        'itemStyle': {'color': THEME['primary']},
                                        'lineStyle': {'width': 3},
                                        'areaStyle': {
                                            'color': {
                                                'type': 'linear',
                                                'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                                'colorStops': [
                                                    {'offset': 0, 'color': 'rgba(0, 229, 255, 0.2)'},
                                                    {'offset': 1, 'color': 'rgba(0, 229, 255, 0.0)'}
                                                ]
                                            }
                                        }
                                    }]
                                }).classes('w-full h-80')
                        else:
                            ui.label('Nenhum aluno selecionado para análise.').classes('italic text-xs text-grey-5')

def update_state(key, val):
    state = app.storage.user.get('relatorios_state', {})
    state[key] = val
    app.storage.user['relatorios_state'] = state
    ui.navigate.to('/relatorios')

def compute_student_evolution(aluno_id, df_alunos, df_acoes, df_tipos_acao, df_config):
    al = df_alunos[df_alunos['id'].astype(str) == str(aluno_id)]
    if al.empty:
        return [], []
    aluno = al.iloc[0]
    
    config_dict = pd.Series(df_config.valor.values, index=df_config.chave).to_dict() if not df_config.empty else {}
    linha_base = float(config_dict.get('linha_base_conceito', 8.5))
    impacto_max_acoes = float(config_dict.get('impacto_max_acoes', 1.5))
    peso_academico = float(config_dict.get('peso_academico', 1.0))
    
    # Impacto acadêmico (fixo para este cálculo de histórico)
    impacto_academico = 0.0
    medias_validas = pd.to_numeric(df_alunos['media_academica'], errors='coerce').dropna()
    media_aluno = float(aluno.get('media_academica', 0.0))
    if not medias_validas.empty and medias_validas.max() > medias_validas.min():
        media_min_turma = medias_validas.min()
        media_max_turma = medias_validas.max()
        if (media_max_turma - media_min_turma) > 0:
            fator_normalizado = (media_aluno - media_min_turma) / (media_max_turma - media_min_turma)
            impacto_academico = fator_normalizado * peso_academico
            
    # Filtra e ordena as ações do aluno
    acoes_com_pontos = calcular_pontuacao_efetiva(df_acoes, df_tipos_acao, df_config)
    
    dates = []
    concepts = []
    
    # Ponto de partida inicial (antes de qualquer anotação)
    c_inicial = max(0.0, min(linha_base + impacto_academico, 10.0))
    
    if acoes_com_pontos.empty:
        hoje = datetime.now().strftime('%d/%m')
        return ['Início', hoje], [c_inicial, c_inicial]
        
    acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'].astype(str) == str(aluno_id)].copy()
    if acoes_aluno.empty:
        hoje = datetime.now().strftime('%d/%m')
        return ['Início', hoje], [c_inicial, c_inicial]
        
    # Ordenar por data
    acoes_aluno['data_dt'] = pd.to_datetime(acoes_aluno['data'])
    acoes_aluno = acoes_aluno.sort_values('data_dt')
    
    running_pts = 0.0
    
    dates.append('Início')
    concepts.append(round(c_inicial, 3))
    
    for _, row in acoes_aluno.iterrows():
        dt_lbl = pd.to_datetime(row['data']).strftime('%d/%m')
        pts = float(row.get('pontuacao_efetiva', 0.0))
        running_pts += pts
        
        # Calcular conceito correspondente
        imp_act = max(-impacto_max_acoes, min(running_pts, impacto_max_acoes))
        c_val = max(0.0, min(linha_base + imp_act + impacto_academico, 10.0))
        
        dates.append(dt_lbl)
        concepts.append(round(c_val, 3))
        
    return dates, concepts
