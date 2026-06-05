"""
Dashboard Principal do SisCOMCA — Painel de Situação Diária
Inclui:
  - Escala do Dia (Inspetor, Supervisor, Oficial de Serviço …) + formulário de inserção
  - Quantitativo geral e por turma (presentes, ausentes, baixados, dispensados)
  - Últimas anotações registradas
  - Desempenho médio por turma
  - Aniversariantes da semana
  - Botão Modo TV (abre /siscomca_tv em nova aba)
"""
from nicegui import ui, app
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import theme
from database import (
    load_data,
    carregar_presenca_hoje,
    carregar_enfermaria_hoje,
    carregar_escala_diaria,
    salvar_escala_diaria,
    deletar_escala_diaria,
    salvar_cargos_escala,
    get_cargos_escala,
    get_db_connection,
)
from services import data_service

THEME = theme.colors

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _calc_conceito(soma_pts: float, config_dict: dict) -> float:
    linha_base = float(config_dict.get('linha_base_conceito', 8.5))
    impacto_max = float(config_dict.get('impacto_max_acoes', 1.5))
    impacto = max(-impacto_max, min(soma_pts, impacto_max))
    return max(0.0, min(linha_base + impacto, 10.0))


def _carregar_dados_gerais():
    """Carrega e processa todos os dados necessários para o dashboard."""
    alunos_df   = data_service.get_alunos_data()
    acoes_df    = data_service.get_acoes_data()
    tipos_df    = data_service.get_tipos_acao_data()
    config_df   = data_service.get_config_data()
    presenca_df = carregar_presenca_hoje()

    db_conn = get_db_connection()
    health_ativos = []
    licencas_ativas = []
    pernoite_hoje_ids = []
    
    if db_conn:
        try:
            # Carrega registros ativos de saúde (status != Alta)
            res_enf = db_conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
            if res_enf.data:
                hoje_str = datetime.now().strftime('%Y-%m-%d')
                for row in res_enf.data:
                    cat = row.get('categoria') or 'enfermaria'
                    
                    # Filtro de validade de datas se houver data_ini/data_fim (assim como no Modo TV)
                    data_ini = row.get('data_ini')
                    data_fim = row.get('data_fim')
                    esta_valido = True
                    if pd.notna(data_ini) and pd.notna(data_fim) and data_ini and data_fim:
                        try:
                            esta_valido = (str(data_ini) <= hoje_str <= str(data_fim))
                        except Exception:
                            pass
                    if not esta_valido:
                        continue

                    status = row.get('status') or ''
                    if cat == 'licenca' or status == 'Licença':
                        licencas_ativas.append(row)
                    else:
                        health_ativos.append(row)
        except Exception as e:
            print("Erro ao carregar saúde no dashboard:", e)
            
        try:
            # Carrega pernoites autorizados para hoje
            hoje_str = datetime.now().strftime('%Y-%m-%d')
            res_pn = db_conn.table('pernoite').select('*').eq('data', hoje_str).eq('presente', True).execute()
            if res_pn.data:
                pernoite_hoje_ids = [str(o['aluno_id']) for o in res_pn.data]
        except Exception as e:
            print("Erro ao carregar pernoite no dashboard:", e)

    config_dict = (
        pd.Series(config_df.valor.values, index=config_df.chave).to_dict()
        if not config_df.empty else {}
    )

    # --- Pontos por aluno ---
    soma_pontos = pd.Series(dtype=float)
    if not acoes_df.empty and not tipos_df.empty:
        tc = tipos_df.copy()
        tc['pontuacao'] = pd.to_numeric(tc['pontuacao'], errors='coerce').fillna(0)
        ac = acoes_df.copy()
        ac['tipo_acao_id'] = ac['tipo_acao_id'].astype(str)
        tc['id'] = tc['id'].astype(str)
        m = pd.merge(ac, tc[['id', 'pontuacao']], left_on='tipo_acao_id', right_on='id', how='left')
        soma_pontos = m.groupby('aluno_id')['pontuacao'].sum()
        soma_pontos.index = soma_pontos.index.astype(str)

    if not alunos_df.empty:
        alunos_df['id'] = alunos_df['id'].astype(str)
        alunos_df['soma_pts'] = alunos_df['id'].map(soma_pontos).fillna(0)
        alunos_df['conceito'] = alunos_df['soma_pts'].apply(
            lambda p: _calc_conceito(p, config_dict)
        )

    # --- Mapeamento presença ---
    presentes_set = set()
    if not presenca_df.empty and 'numero_interno' in presenca_df.columns:
        presentes_set = set(presenca_df[presenca_df['presente'] == True]['numero_interno'].astype(str).str.strip().str.upper())

    baixados_set = set([str(x.get('numero_interno', '')).strip().upper() for x in health_ativos if x.get('status') in ['Internado', 'Em Observação', 'baixado'] or (x.get('categoria') == 'enfermaria' and x.get('status') != 'Hospital')])
    dispensados_set = set([str(x.get('numero_interno', '')).strip().upper() for x in health_ativos if x.get('status') == 'Dispensado' or x.get('categoria') == 'dispensa'])
    hospital_set = set([str(x.get('numero_interno', '')).strip().upper() for x in health_ativos if x.get('status') == 'Hospital' or x.get('categoria') == 'hospital'])
    licenciados_set = set([str(x.get('numero_interno', '')).strip().upper() for x in licencas_ativas])

    # Justificados (com licença, baixados ou hospitalizados)
    justificados_set = licenciados_set.union(baixados_set).union(hospital_set)

    # O conjunto real de Ausentes (Faltosos Sem Justificativa) são todos os alunos do efetivo
    # que NÃO estão presentes E NÃO possuem justificativa ativa de saúde/licença
    ausentes_set = set()
    if not alunos_df.empty and 'numero_interno' in alunos_df.columns:
        todos_alunos_set = set(alunos_df['numero_interno'].astype(str).str.strip().str.upper())
        ausentes_set = todos_alunos_set - presentes_set - justificados_set

    # --- Stats por turma ---
    turmas = []
    if not alunos_df.empty and 'pelotao' in alunos_df.columns:
        for pel, g in alunos_df.groupby('pelotao'):
            internos = g['numero_interno'].astype(str).str.strip().str.upper()
            turmas.append({
                'turma': str(pel),
                'total': len(g),
                'presentes':   int(internos.isin(presentes_set).sum()),
                'ausentes':    int(internos.isin(ausentes_set).sum()),
                'baixados':    int(internos.isin(baixados_set).sum()),
                'dispensados': int(internos.isin(dispensados_set).sum()),
                'media_conceito': float(g['conceito'].mean()),
            })

    # --- Totais gerais ---
    total_alunos = len(alunos_df) if not alunos_df.empty else 0
    total_pres   = len(presenca_df[presenca_df['presente'] == True]) if not presenca_df.empty else 0
    
    # Total de Ausentes Reais (Faltosos Sem Justificativa)
    total_aus = len(ausentes_set)
        
    total_bx     = len([x for x in health_ativos if x.get('status') in ['Internado', 'Em Observação', 'baixado'] or (x.get('categoria') == 'enfermaria' and x.get('status') != 'Hospital')])
    total_disp   = len([x for x in health_ativos if x.get('status') == 'Dispensado' or x.get('categoria') == 'dispensa'])
    total_hosp   = len([x for x in health_ativos if x.get('status') == 'Hospital' or x.get('categoria') == 'hospital'])
    total_lic    = len(licencas_ativas)
    total_pernoite = len(pernoite_hoje_ids)

    # --- Últimas anotações ---
    ultimas_anot = []
    if not acoes_df.empty and not alunos_df.empty:
        try:
            ac2 = acoes_df.copy()
            ac2['aluno_id'] = ac2['aluno_id'].astype(str)
            merged = pd.merge(ac2, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id', how='left')
            if not tipos_df.empty:
                tc2 = tipos_df.copy()
                tc2['id'] = tc2['id'].astype(str)
                tc2['pontuacao'] = pd.to_numeric(tc2['pontuacao'], errors='coerce').fillna(0)
                merged = pd.merge(merged, tc2[['id', 'pontuacao']], left_on='tipo_acao_id', right_on='id', how='left', suffixes=('', '_t'))
            merged['data_dt'] = pd.to_datetime(merged['data'], errors='coerce')
            merged = merged.dropna(subset=['data_dt']).sort_values('data_dt', ascending=False).head(8)
            for _, r in merged.iterrows():
                ultimas_anot.append({
                    'ni': str(r.get('numero_interno', '')).upper(),
                    'nome': str(r.get('nome_guerra', '???')),
                    'turma': str(r.get('pelotao', '?')),
                    'tipo': str(r.get('tipo', r.get('nome', 'Ação'))),
                    'desc': str(r.get('descricao', '')),
                    'data': r['data_dt'].strftime('%d/%m %H:%M'),
                    'pts': float(r.get('pontuacao', 0.0)),
                    'status': str(r.get('status', '')),
                })
        except Exception as e:
            print(f"[DASH] Erro ultimas anotações: {e}")

    # --- Aniversariantes da semana ---
    aniversariantes = []
    if not alunos_df.empty and 'data_nascimento' in alunos_df.columns:
        hoje = datetime.now().date()
        alunos_df['dn_dt'] = pd.to_datetime(alunos_df['data_nascimento'], errors='coerce')
        for _, r in alunos_df.dropna(subset=['dn_dt']).iterrows():
            nasc = r['dn_dt']
            aniv = nasc.replace(year=hoje.year).date()
            diff = (aniv - hoje).days
            if -1 <= diff <= 7:
                aniversariantes.append({
                    'nome': r['nome_guerra'],
                    'numero': r.get('numero_interno', ''),
                    'turma': r.get('pelotao', ''),
                    'dia': nasc.strftime('%d/%m'),
                    'diff': diff,
                })
        aniversariantes.sort(key=lambda x: x['diff'])

    return {
        'turmas': sorted(turmas, key=lambda x: x['turma']),
        'total_alunos': total_alunos,
        'total_pres': total_pres,
        'total_aus': total_aus,
        'total_bx': total_bx,
        'total_disp': total_disp,
        'total_hosp': total_hosp,
        'total_lic': total_lic,
        'total_pernoite': total_pernoite,
        'pernoite_hoje_ids': pernoite_hoje_ids,
        'ultimas_anot': ultimas_anot,
        'aniversariantes': aniversariantes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Renderização da página
# ─────────────────────────────────────────────────────────────────────────────

def render_page():
    client = ui.context.client
    
    async def handle_refresh():
        # Limpa o cache de dados e atualiza a tela
        data_service.clear_cache()
        render_dashboard_content.refresh()
        
    def setup_realtime():
        from alerts_manager import AlertsManager
        AlertsManager.register_refresh_callback(handle_refresh)
        
    def cleanup_realtime():
        from alerts_manager import AlertsManager
        AlertsManager.unregister_refresh_callback(handle_refresh)
        
    client.on_connect(setup_realtime)
    client.on_disconnect(cleanup_realtime)

    render_dashboard_content()


@ui.refreshable
def render_dashboard_content():
    dados = _carregar_dados_gerais()
    escala_df = carregar_escala_diaria()
    hoje_str = datetime.now().strftime('%d/%m/%Y')
    dia_semana = datetime.now().strftime('%A').upper()

    # Mapa cargo → nome atual
    escala_map = {}
    if not escala_df.empty and 'cargo' in escala_df.columns:
        for _, r in escala_df.iterrows():
            escala_map[r['cargo'].upper()] = r.get('nome', '')
            escala_map[r['cargo']] = r.get('nome', '')

    with ui.column().classes('w-full q-pa-lg gap-5'):

        # ── CABEÇALHO ──────────────────────────────────────────────────────
        with ui.row().classes('w-full items-center justify-between q-mb-xs'):
            with ui.column().classes('gap-0'):
                theme.section_header(
                    'Dashboard SisCOMCA',
                    f'Situação Consolidada do Corpo de Alunos — {dia_semana}, {hoje_str}'
                )
            with ui.row().classes('items-center gap-2'):
                ui.button(
                    'Modo TV', icon='tv',
                    on_click=lambda: ui.navigate.to('/siscomca_tv', new_tab=True)
                ).props('unelevated no-caps').style(
                    f'background:{THEME["primary"]}; color:#000; font-weight:700;'
                )
                ui.button(
                    'Atualizar', icon='refresh',
                    on_click=lambda: (data_service.clear_cache(), render_dashboard_content.refresh())
                ).props('outline no-caps color=grey')

        # ── KPIs GERAIS (TV STYLE - 8 CARDS RESPONSIVOS) ───────────────────
        with ui.element('div').classes('grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 w-full gap-3'):
            def _kpi(val, label, icon, cor):
                with ui.card().classes('no-shadow q-pa-sm items-center text-center').style(
                    f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-top:3px solid {cor}; margin:0;'
                ):
                    ui.icon(icon, color='grey-5').classes('text-lg q-mb-xs')
                    ui.label(str(val)).style(f'color:{cor}; font-size:1.8rem; font-weight:900; line-height:1;')
                    ui.label(label).classes('text-grey text-[9px] font-bold tracking-wider q-mt-xs')

            _kpi(dados['total_alunos'],   'EFETIVO TOTAL', 'groups', '#D4AF37')
            _kpi(dados['total_pres'],     'PRESENTES',     'how_to_reg', '#4CAF50')
            _kpi(dados['total_aus'],      'AUSENTES',      'person_off',  '#F44336')
            _kpi(dados['total_lic'],      'LICENCIADOS',   'flight_takeoff', '#2196F3')
            _kpi(dados['total_bx'],       'BAIXADOS',      'local_hospital', '#E91E63')
            _kpi(dados['total_disp'],     'DISPENSADOS',   'event_busy',  '#FF9800')
            _kpi(dados['total_hosp'],     'HOSPITAL',      'apartment',  '#9C27B0')
            _kpi(dados['total_pernoite'], 'PERNOITE',      'nightlight',  '#00BCD4')

        # ── SEÇÃO 1: ACÕES E AVISOS (3 Colunas) ────────────────────────────
        with ui.element('div').classes('grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 w-full gap-4 items-start'):
            # 1. Anotação Rápida
            _build_anotacao_rapida_card()
            
            # 2. Aviso Rápido (TV)
            _build_aviso_rapido_card()
            
            # 3. Últimas Anotações
            with ui.card().classes('w-full no-shadow').style(
                f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-top:3px solid #ff9100; height: 100%;'
            ):
                with ui.row().classes('items-center justify-between q-pa-md border-b border-gray-800'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('history_edu', color='amber-9').classes('text-xl')
                        ui.label('ÚLTIMAS ANOTAÇÕES').style(
                            f'color:{THEME["primary"]}; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
                        )
                    ui.button(
                        'Ver Gestão de Ações', icon='open_in_new',
                        on_click=lambda: ui.navigate.to('/gestao_acoes')
                    ).props('flat dense no-caps').classes('text-xs text-grey-5')

                with ui.column().classes('w-full q-pa-sm gap-1').style('max-height:280px; overflow-y:auto;'):
                    if not dados['ultimas_anot']:
                        ui.label('Nenhuma anotação recente.').classes('text-grey italic text-xs q-pa-md self-center')
                    else:
                        for a in dados['ultimas_anot']:
                            _build_anotacao_row(a)

        # ── SEÇÃO 2: SERVIÇO, ANIVERSÁRIOS E PERNOITE (3 Colunas) ───────────
        with ui.element('div').classes('grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 w-full gap-4 items-start'):
            # 1. Escala do Dia
            with ui.card().classes('w-full no-shadow').style(
                f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-left:3px solid {THEME["primary"]};'
            ):
                with ui.row().classes('w-full items-center justify-between q-pa-md border-b border-gray-800'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('military_tech', color='amber-9').classes('text-xl')
                        ui.label('ESCALA DO DIA').style(
                            f'color:{THEME["primary"]}; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
                        )
                    ui.label(hoje_str).classes('text-grey-5 text-xs font-bold')

                with ui.column().classes('w-full q-pa-md gap-2'):
                    cargos_exibir = get_cargos_escala()
                    for cargo in cargos_exibir:
                        nome_atual = escala_map.get(cargo, escala_map.get(cargo.upper(), escala_map.get(cargo.title(), '')))
                        with ui.row().classes('w-full items-center justify-between q-py-xs border-b border-gray-800'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('circle', color='green' if nome_atual else 'grey-8').classes('text-[8px]')
                                ui.label(cargo).classes('text-grey-4 text-xs font-bold').style('min-width:140px;')
                            if nome_atual:
                                ui.label(nome_atual).classes('text-white text-xs font-bold uppercase')
                            else:
                                ui.label('— não definido —').classes('text-grey-7 text-xs italic')

                with ui.row().classes('w-full q-pa-sm justify-center gap-2 border-t border-gray-800 flex-wrap'):
                    _build_escala_dialog()
                    _build_escala_semanal_dialog()
                    
                    def notificar_escala_manual():
                        try:
                            from database import get_db_connection
                            from database import carregar_escala_diaria
                            db_c = get_db_connection()
                            if not db_c:
                                ui.notify('Sem conexão com banco de dados', color='warning')
                                return
                            data_hoje = datetime.now().strftime('%Y-%m-%d')
                            df = carregar_escala_diaria(data_hoje)
                            if df.empty:
                                ui.notify('Nenhum militar escalado hoje.', color='warning')
                                return
                                
                            total_notified = 0
                            from notifications_manager import send_notification_to_user
                            import asyncio
                            
                            for _, r in df.iterrows():
                                cargo = r['cargo']
                                nome_mil = r['nome'].strip()
                                if nome_mil:
                                    res_u = db_c.table('Users').select('telegram_id').eq('nome', nome_mil).execute()
                                    if res_u.data and res_u.data[0].get('telegram_id'):
                                        tg_id = res_u.data[0]['telegram_id']
                                        msg = (
                                            f"👮 **Aviso de Serviço — SisCOMCA**\n\n"
                                            f"Olá! Você está de serviço **HOJE** na função de **{cargo}**."
                                        )
                                        asyncio.create_task(send_notification_to_user(tg_id, msg))
                                        total_notified += 1
                                        
                            if total_notified > 0:
                                ui.notify(f'{total_notified} militares notificados no Telegram!', color='positive')
                            else:
                                ui.notify('Nenhum militar com Telegram vinculado encontrado na escala de hoje.', color='warning')
                        except Exception as ex:
                            ui.notify(f'Erro ao notificar: {ex}', color='negative')
                            
                    ui.button(
                        '🔔 Notificar',
                        on_click=notificar_escala_manual
                    ).props('flat dense no-caps').classes('text-xs text-cyan-5 font-bold')

            # 2. Aniversariantes da Semana
            with ui.card().classes('w-full no-shadow').style(
                f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-left:3px solid #ff5722;'
            ):
                with ui.row().classes('items-center gap-2 q-pa-md border-b border-gray-800'):
                    ui.icon('cake', color='amber-9').classes('text-xl')
                    ui.label('ANIVERSARIANTES DA SEMANA').style(
                        f'color:{THEME["primary"]}; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
                    )

                with ui.column().classes('w-full q-pa-md gap-2').style('max-height:280px; overflow-y:auto;'):
                    if not dados['aniversariantes']:
                        ui.label('Nenhum aniversariante esta semana.').classes('text-grey italic text-xs')
                    else:
                        for a in dados['aniversariantes']:
                            diff = a['diff']
                            if diff == 0:
                                label_dia = '🎉 HOJE!'
                                cor_dia = '#FFD700'
                            elif diff < 0:
                                label_dia = f"Há {-diff} dia(s)"
                                cor_dia = '#888'
                            else:
                                label_dia = f"Em {diff} dia(s)"
                                cor_dia = '#4CAF50'

                            with ui.row().classes('w-full items-center justify-between q-py-xs border-b border-gray-800'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('cake', color='amber-6').classes('text-sm')
                                    with ui.column().classes('gap-0'):
                                        ui.label(str(a['nome']).upper()).classes('text-white text-xs font-bold')
                                        ui.label(f"Nº {a['numero']} • {a['turma']}").classes('text-grey text-[10px]')
                                with ui.column().classes('items-end gap-0'):
                                    ui.label(a['dia']).classes('text-amber-5 text-xs font-bold')
                                    ui.label(label_dia).style(f'color:{cor_dia}; font-size:0.6rem; font-weight:bold;')

            # 3. Controle de Pernoite para aquele dia
            _build_pernoite_dashboard_card(dados.get('pernoite_hoje_ids', []))

        # ── SEÇÃO 3: QUANTITATIVO (2 COLUNAS) E DESEMPENHO (1 COLUNA) ───────
        with ui.element('div').classes('grid grid-cols-1 lg:grid-cols-3 w-full gap-4 items-start'):
            # Quantitativo por Turma em 2 colunas (col-span-2)
            with ui.card().classes('w-full no-shadow lg:col-span-2').style(
                f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-top:3px solid #00E5FF;'
            ):
                with ui.row().classes('items-center gap-2 q-pa-md border-b border-gray-800'):
                    ui.icon('analytics', color='amber-9').classes('text-xl')
                    ui.label('QUANTITATIVO POR TURMA').style(
                        f'color:{THEME["primary"]}; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
                    )

                with ui.element('div').classes('grid grid-cols-1 md:grid-cols-2 w-full q-pa-md gap-4'):
                    if not dados['turmas']:
                        ui.label('Sem dados de turma.').classes('text-grey italic text-xs col-span-2')
                    else:
                        for t in dados['turmas']:
                            _build_turma_row(t)

            # Desempenho Médio por Turma (col-span-1)
            with ui.card().classes('w-full no-shadow lg:col-span-1').style(
                f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-top:3px solid #D4AF37;'
            ):
                with ui.row().classes('items-center gap-2 q-pa-md border-b border-gray-800'):
                    ui.icon('bar_chart', color='amber-9').classes('text-xl')
                    ui.label('DESEMPENHO MÉDIO POR TURMA').style(
                        f'color:{THEME["primary"]}; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
                    )

                with ui.column().classes('w-full q-pa-md gap-3'):
                    if not dados['turmas']:
                        ui.label('Sem dados.').classes('text-grey italic text-xs')
                    else:
                        for t in sorted(dados['turmas'], key=lambda x: x['media_conceito'], reverse=True):
                            mc = t['media_conceito']
                            cor = '#4CAF50' if mc >= 8.5 else '#FF9800' if mc >= 7.0 else '#F44336'
                            with ui.column().classes('w-full gap-1'):
                                with ui.row().classes('w-full justify-between items-center'):
                                    ui.label(f"Pelotão {t['turma']}").classes('text-white text-xs font-bold')
                                    ui.label(f"{mc:.2f} / 10.00").style(
                                        f'color:{cor}; font-weight:900; font-size:0.8rem;'
                                    )
                                ui.linear_progress(value=mc / 10.0).props('stripe').classes('h-2 rounded')


# ─────────────────────────────────────────────────────────────────────────────
# Componentes internos
# ─────────────────────────────────────────────────────────────────────────────

def _build_turma_row(t: dict):
    total = t['total'] or 1
    with ui.card().classes('w-full q-pa-sm no-shadow').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-left:3px solid {THEME["primary"]};'
    ):
        with ui.row().classes('w-full items-center justify-between q-mb-xs'):
            ui.label(f"PELOTÃO {t['turma'].upper()}").style(
                f'color:{THEME["primary"]}; font-size:0.75rem; font-weight:900; letter-spacing:2px;'
            ).classes('cyber-title')
            ui.label(f"{t['total']} militares").classes('text-grey-5 text-[10px] font-bold')

        with ui.row().classes('w-full gap-2 flex-wrap'):
            def _stat(val, label, cor):
                pct = int(val / total * 100) if total > 0 else 0
                with ui.column().classes('items-center gap-0').style('min-width:65px;'):
                    ui.label(str(val)).style(f'color:{cor}; font-size:1.4rem; font-weight:900; line-height:1;')
                    ui.label(label).style(f'color:{THEME["text_dim"]}; font-size:0.55rem; font-weight:bold; letter-spacing:1px;').classes('cyber-title')
                    ui.label(f"({pct}%)").style('color:#475569; font-size:0.55rem;')

            _stat(t['presentes'],   'PRESENTES',  '#00e676')
            ui.label('|').classes('text-slate-800 self-center')
            _stat(t['ausentes'],    'AUSENTES',   '#ff1744')
            ui.label('|').classes('text-slate-800 self-center')
            _stat(t['baixados'],    'BAIXADOS',   '#00b0ff')
            ui.label('|').classes('text-slate-800 self-center')
            _stat(t['dispensados'], 'DISPENSADOS','#ff9100')


def _build_anotacao_row(a: dict):
    pts = a['pts']
    borda = '#00e676' if pts > 0 else '#ff1744' if pts < 0 else '#475569'
    cor_pts = '#00e676' if pts > 0 else '#ff1744' if pts < 0 else '#94a3b8'
    sinal = '+' if pts > 0 else ''

    with ui.row().classes('w-full items-start justify-between q-pa-xs rounded').style(
        f'background:{THEME["bg_input"]}; border-left:3px solid {borda}; border-bottom:1px solid rgba(0, 229, 255, 0.08);'
    ):
        with ui.column().classes('gap-0').style('flex:1; overflow:hidden;'):
            with ui.row().classes('items-center gap-2'):
                ni_lbl = f"[{a.get('ni', '')}] " if a.get('ni') else ""
                ui.label(f"{ni_lbl}{a['nome'].upper()}").style('color:#fff; font-size:0.75rem; font-weight:900;')
                ui.label(f"Pel. {a['turma']}").style('color:#64748b; font-size:0.6rem;')
                if a['status'] == 'Pendente':
                    ui.label('PENDENTE').style(
                        'color:#ff9100; font-size:0.55rem; font-weight:bold; '
                        'border:1px solid #ff9100; padding:0 3px; border-radius:2px;'
                    )
            ui.label(f"{a['tipo']}{'  — ' + a['desc'][:60] if a['desc'] else ''}").style(
                'color:#94a3b8; font-size:0.65rem; font-style:italic; '
                'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'
            )
        with ui.column().classes('items-end gap-0').style('min-width:52px;'):
            ui.label(f"{sinal}{pts:.1f}").style(f'color:{cor_pts}; font-size:0.9rem; font-weight:900;')
            ui.label(a['data']).style('color:#475569; font-size:0.6rem;')


def _build_escala_dialog():
    """Cria o botão + diálogo interativo para gerenciar a escala por data, cargos e nomes."""
    state = {
        'active_date': datetime.now().strftime('%Y-%m-%d'),
        'rows': []
    }

    def carregar_dados_data(date_str: str):
        df = carregar_escala_diaria(date_str)
        items = []
        if not df.empty:
            for _, row in df.iterrows():
                items.append({'cargo': str(row['cargo']), 'nome': str(row['nome'])})
        else:
            # Tenta usar cargos configurados como padrão
            for c in get_cargos_escala():
                items.append({'cargo': c, 'nome': ''})
        return items

    with ui.dialog() as dialog, ui.card().classes('q-pa-lg').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; min-width:480px; max-width:90vw;'
    ):
        with ui.column().classes('w-full gap-3'):
            with ui.row().classes('items-center gap-2 w-full justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('edit_calendar', color='amber-9').classes('text-xl')
                    ui.label('DEFINIR ESCALA DE SERVIÇO').style(
                        f'color:{THEME["primary"]}; font-weight:900; letter-spacing:2px;'
                    )
                ui.button(icon='close', on_click=dialog.close).props('flat round dense color=grey')

            ui.separator().props('dark')

            err_lbl = ui.label('').classes('text-caption text-red')

            def change_date(offset: int):
                d_obj = datetime.strptime(state['active_date'], '%Y-%m-%d')
                new_d = d_obj + timedelta(days=offset)
                state['active_date'] = new_d.strftime('%Y-%m-%d')
                state['rows'] = carregar_dados_data(state['active_date'])
                err_lbl.text = ''
                render_rows.refresh()

            def update_state_cargo(idx: int, val: str):
                state['rows'][idx]['cargo'] = val

            def update_state_nome(idx: int, val: str):
                state['rows'][idx]['nome'] = val

            def delete_row(idx: int):
                state['rows'].pop(idx)
                render_rows.refresh()

            def add_new_row():
                state['rows'].append({'cargo': 'NOVO CARGO', 'nome': ''})
                render_rows.refresh()

            @ui.refreshable
            def render_rows():
                # Barra de controle de data
                with ui.row().classes('w-full items-center justify-between bg-black/35 q-pa-xs rounded border border-gray-800'):
                    ui.button(on_click=lambda: change_date(-1), icon='chevron_left').props('flat dense color=amber')
                    
                    d_obj = datetime.strptime(state['active_date'], '%Y-%m-%d')
                    date_display = d_obj.strftime('%d/%m/%Y')
                    weekday = d_obj.strftime('%A').upper()
                    # Tradução básica de dias da semana para português
                    dias_map = {
                        'MONDAY': 'SEGUNDA-FEIRA', 'TUESDAY': 'TERÇA-FEIRA', 'WEDNESDAY': 'QUARTA-FEIRA',
                        'THURSDAY': 'QUINTA-FEIRA', 'FRIDAY': 'SEXTA-FEIRA', 'SATURDAY': 'SÁBADO', 'SUNDAY': 'DOMINGO'
                    }
                    weekday_pt = dias_map.get(weekday, weekday)
                    ui.label(f"{date_display} — {weekday_pt}").classes('text-amber-5 text-xs font-bold tracking-widest')
                    
                    ui.button(on_click=lambda: change_date(1), icon='chevron_right').props('flat dense color=amber')

                # Renderiza cada posto como uma linha editável
                with ui.column().classes('w-full gap-2 max-h-[350px] overflow-y-auto q-pr-xs'):
                    for idx, item in enumerate(state['rows']):
                        with ui.row().classes('w-full items-center gap-2 no-wrap').style('border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 4px;'):
                            # Input editável do Cargo
                            cargo_inp = ui.input(
                                value=item['cargo'],
                                on_change=lambda e, idx=idx: update_state_cargo(idx, e.value)
                            ).props('dark dense outlined').classes('w-[160px] text-xs font-bold')
                            
                            # Input editável do Militar de serviço
                            nome_inp = ui.input(
                                placeholder='Nome completo / posto',
                                value=item['nome'],
                                on_change=lambda e, idx=idx: update_state_nome(idx, e.value)
                            ).props('dark dense outlined').classes('col-grow text-xs')
                            
                            # Botão de exclusão do posto
                            ui.button(on_click=lambda idx=idx: delete_row(idx), icon='delete').props('flat dense color=red-5 round')

                # Botão para adicionar novo posto
                with ui.row().classes('w-full justify-center mt-1'):
                    ui.button('➕ ADICIONAR NOVO POSTO', on_click=add_new_row).props('flat dense color=amber-9 no-caps').classes('text-[11px] font-bold')

            # Renderiza as linhas iniciais
            render_rows()

            def salvar_escala():
                # 0. Salva os títulos dos cargos globalmente na tabela Config para propagar para todos os outros dias
                novos_cargos = [item['cargo'].strip().upper() for item in state['rows'] if item['cargo'].strip()]
                if novos_cargos:
                    salvar_cargos_escala(novos_cargos)

                # 1. Limpa escala existente para a data para evitar duplicados ou órfãos
                deletar_escala_diaria(state['active_date'])
                
                # 2. Salva as novas linhas preenchidas
                salvou_algum = False
                for item in state['rows']:
                    cargo = item['cargo'].strip()
                    nome = item['nome'].strip()
                    if cargo:
                        # Salva mesmo com nome vazio (mostra como não definido) para preservar o posto na lista
                        ok = salvar_escala_diaria(cargo, nome, data=state['active_date'])
                        if ok:
                            salvou_algum = True

                if salvou_algum:
                    d_formatted = datetime.strptime(state['active_date'], '%Y-%m-%d').strftime('%d/%m/%Y')
                    ui.notify(f'Escala para o dia {d_formatted} salva com sucesso!', color='positive')
                    dialog.close()
                    data_service.clear_cache()
                    render_dashboard_content.refresh()
                    
                    # Notifica a TV em tempo real para recarregar imediatamente!
                    from alerts_manager import AlertsManager
                    AlertsManager.trigger_alert(
                        "Escala de Serviço Atualizada",
                        f"A escala para o dia {d_formatted} foi atualizada na Dashboard!",
                        "info"
                    )
                    
                    # Notifica os militares via Telegram automaticamente
                    try:
                        db_c = get_db_connection()
                        if db_c:
                            from notifications_manager import send_notification_to_user
                            import asyncio
                            for item in state['rows']:
                                cargo = item['cargo'].strip()
                                nome_mil = item['nome'].strip()
                                if cargo and nome_mil:
                                    res_u = db_c.table('Users').select('telegram_id').eq('nome', nome_mil).execute()
                                    if res_u.data and res_u.data[0].get('telegram_id'):
                                        tg_id = res_u.data[0]['telegram_id']
                                        d_lbl = datetime.strptime(state['active_date'], '%Y-%m-%d').strftime('%d/%m')
                                        msg = (
                                            f"👮 **Aviso de Serviço — SisCOMCA**\n\n"
                                            f"Olá! Você foi escalado para o serviço no dia **{d_lbl}** na função de **{cargo}**."
                                        )
                                        asyncio.create_task(send_notification_to_user(tg_id, msg))
                    except Exception as e_alert:
                        print(f"[ESCALA DIARIA NOTIFY ERROR] {e_alert}")
                else:
                    err_lbl.text = 'Preencha ao menos um posto de serviço antes de salvar.'

            with ui.row().classes('w-full justify-end gap-2 q-mt-md border-t border-gray-900 q-pt-sm'):
                ui.button('Cancelar', on_click=dialog.close).props('flat color=grey no-caps')
                ui.button('💾 SALVAR ESCALA', on_click=salvar_escala).props(
                    'unelevated no-caps'
                ).style(f'background:{THEME["primary"]}; color:#000; font-weight:700;')

    def open_dialog():
        state['active_date'] = datetime.now().strftime('%Y-%m-%d')
        state['rows'] = carregar_dados_data(state['active_date'])
        err_lbl.text = ''
        dialog.open()
        render_rows.refresh()

    ui.button(
        '✏️ Definir / Editar Escala do Dia',
        on_click=open_dialog
    ).props('flat dense no-caps').classes('text-xs text-amber-5 font-bold')

def _build_escala_semanal_dialog():
    """Diálogo interativo para preenchimento em lote do Inspetor para a semana inteira."""
    from database import get_db_connection
    from datetime import datetime, timedelta
    import asyncio
    
    # Busca operadores ativos
    db_conn = get_db_connection()
    operadores_opcoes = {}
    if db_conn:
        try:
            u_res = db_conn.table('Users').select('*').execute()
            if u_res.data:
                operadores_opcoes = {u['nome'].upper(): u['nome'].upper() for u in u_res.data if u.get('nome')}
        except Exception:
            pass
            
    if not operadores_opcoes:
        operadores_opcoes = {"ADMIN": "ADMIN", "CALAÇA": "CALAÇA", "AMANDA": "AMANDA", "BASTOS": "BASTOS", "ALANDESA": "ALANDESA"}
        
    state = {
        'rows': []
    }
    
    def carregar_escala_semanal():
        hoje = datetime.now().date()
        start = hoje - timedelta(days=hoje.weekday())
        
        rows = []
        dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        
        db_c = get_db_connection()
        escala_existente = {}
        if db_c:
            try:
                d_inicio = start.strftime('%Y-%m-%d')
                d_fim = (start + timedelta(days=6)).strftime('%Y-%m-%d')
                res = db_c.table('escala_diaria').select('*').eq('cargo', 'Inspetor').gte('data', d_inicio).lte('data', d_fim).execute()
                if res.data:
                    escala_existente = {r['data']: r['nome'] for r in res.data}
            except Exception:
                pass
                
        for i in range(7):
            d = start + timedelta(days=i)
            d_str = d.strftime('%Y-%m-%d')
            rows.append({
                'date_str': d_str,
                'date_display': d.strftime('%d/%m'),
                'weekday': dias_semana_pt[i],
                'nome': escala_existente.get(d_str, '')
            })
        state['rows'] = rows

    with ui.dialog() as dialog, ui.card().classes('q-pa-lg').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; min-width:480px; max-width:90vw;'
    ):
        with ui.column().classes('w-full gap-3'):
            with ui.row().classes('items-center gap-2 w-full justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('date_range', color='amber-9').classes('text-xl')
                    ui.label('ESCALA SEMANAL DE INSPETORES').style(
                        f'color:{THEME["primary"]}; font-weight:900; letter-spacing:2px;'
                    )
                ui.button(icon='close', on_click=dialog.close).props('flat round dense color=grey')

            ui.separator().props('dark')
            
            ui.label('Preencha os inspetores para a semana atual (Segunda a Domingo):').classes('text-grey-4 text-xs font-bold')

            @ui.refreshable
            def render_semana_rows():
                with ui.column().classes('w-full gap-2 max-h-[350px] overflow-y-auto q-pr-xs'):
                    for idx, row in enumerate(state['rows']):
                        with ui.row().classes('w-full items-center gap-3 no-wrap py-1 border-b border-white/5'):
                            with ui.column().classes('gap-0 w-[140px]'):
                                ui.label(row['weekday']).classes('text-white text-xs font-bold')
                                ui.label(row['date_display']).classes('text-grey text-[10px]')
                            
                            ui.select(
                                operadores_opcoes,
                                label='Inspetor',
                                value=row['nome'],
                                on_change=lambda e, idx=idx: state['rows'][idx].__setitem__('nome', e.value or '')
                            ).props('dark dense outlined clearable').classes('col-grow text-xs')

            render_semana_rows()

            def salvar_semana():
                db_c = get_db_connection()
                salvou_algum = False
                
                for row in state['rows']:
                    d_str = row['date_str']
                    nome = row['nome'].strip()
                    
                    if db_c:
                        try:
                            db_c.table('escala_diaria').delete().eq('data', d_str).eq('cargo', 'Inspetor').execute()
                            if nome:
                                db_c.table('escala_diaria').insert({
                                    'data': d_str,
                                    'cargo': 'Inspetor',
                                    'nome': nome,
                                    'observacao': 'Lançado via escala semanal'
                                }).execute()
                            salvou_algum = True
                        except Exception as e:
                            print(f"[ESCALA SEMANAL] Erro ao salvar data {d_str}: {e}")
                    else:
                        salvou_algum = True
                        
                if salvou_algum:
                    ui.notify('Escala semanal de Inspetores salva com sucesso!', color='positive')
                    dialog.close()
                    data_service.clear_cache()
                    render_dashboard_content.refresh()
                    
                    from alerts_manager import AlertsManager
                    AlertsManager.trigger_alert(
                        "Escala Semanal Atualizada",
                        "A escala de Inspetores para toda a semana foi atualizada!",
                        "info"
                    )
                    
                    try:
                        from notifications_manager import send_notification_to_user
                        if db_c:
                            for row in state['rows']:
                                nome_mil = row['nome'].strip()
                                if nome_mil:
                                    res_u = db_c.table('Users').select('telegram_id').eq('nome', nome_mil).execute()
                                    if res_u.data and res_u.data[0].get('telegram_id'):
                                        tg_id = res_u.data[0]['telegram_id']
                                        d_fmt = datetime.strptime(row['date_str'], '%Y-%m-%d').strftime('%d/%m')
                                        msg = (
                                            f"👮 **Aviso de Serviço — SisCOMCA**\n\n"
                                            f"Olá! Você foi escalado para o serviço no dia **{d_fmt}** ({row['weekday']}) como **INSPETOR DO DIA**."
                                        )
                                        asyncio.create_task(send_notification_to_user(tg_id, msg))
                    except Exception as e_alert:
                        print(f"[ESCALA SEMANAL NOTIFY ERROR] {e_alert}")
                else:
                    ui.notify('Ocorreu um erro ao salvar a escala semanal.', color='negative')

            with ui.row().classes('w-full justify-end gap-2 q-mt-md border-t border-gray-900 q-pt-sm'):
                ui.button('Cancelar', on_click=dialog.close).props('flat color=grey no-caps')
                ui.button('💾 SALVAR SEMANA', on_click=salvar_semana).props(
                    'unelevated no-caps'
                ).style(f'background:{THEME["primary"]}; color:#000; font-weight:700;')

    def open_semanal():
        carregar_escala_semanal()
        dialog.open()
        render_semana_rows.refresh()

    ui.button(
        '📅 Escala Semanal',
        on_click=open_semanal
    ).props('flat dense no-caps').classes('text-xs text-amber-5 font-bold')


def _build_anotacao_rapida_card():
    """Card de anotação rápida de aluno no dashboard."""
    alunos_df = data_service.get_alunos_data()
    tipos_df  = data_service.get_tipos_acao_data()

    with ui.card().classes('w-full no-shadow').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-left:3px solid #4CAF50;'
    ):
        with ui.row().classes('items-center gap-2 q-pa-md border-b border-gray-800'):
            ui.icon('add_circle', color='positive').classes('text-xl')
            ui.label('ANOTAÇÃO RÁPIDA').style(
                f'color:#4CAF50; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
            )

        with ui.column().classes('w-full q-pa-md gap-3'):
            if alunos_df.empty or tipos_df.empty:
                ui.label('Dados de alunos/ações não carregados.').classes('text-grey italic text-xs')
                return

            # Selects
            opcoes_alunos = {
                str(r['id']): f"{r.get('numero_interno', '?')} – {r.get('nome_guerra', '?')} ({r.get('pelotao', '?')})"
                for _, r in alunos_df.iterrows()
            }
            opcoes_tipo = {str(r['id']): r['nome'] for _, r in tipos_df.iterrows()}

            sel_aluno = ui.select(
                opcoes_alunos, label='Aluno'
            ).props('dark dense outlined').classes('w-full')

            sel_tipo = ui.select(
                opcoes_tipo, label='Tipo de Ação'
            ).props('dark dense outlined').classes('w-full')

            desc_inp = ui.input(
                'Descrição (opcional)'
            ).props('dark dense outlined').classes('w-full')

            def registrar():
                if not sel_aluno.value or not sel_tipo.value:
                    ui.notify('Selecione o aluno e o tipo de ação!', color='warning')
                    return
                try:
                    tipo_row = tipos_df[tipos_df['id'].astype(str) == sel_tipo.value].iloc[0]
                    db_conn = get_db_connection()
                    usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Dashboard')
                    nova_acao = {
                        'aluno_id': sel_aluno.value,
                        'tipo_acao_id': sel_tipo.value,
                        'tipo': tipo_row['nome'],
                        'descricao': desc_inp.value or '',
                        'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'usuario': usuario,
                        'status': 'Pendente',
                    }
                    if db_conn:
                        db_conn.table('Acoes').insert(nova_acao).execute()
                        ui.notify('Anotação registrada com sucesso!', color='positive')
                        
                        aluno_txt = opcoes_alunos.get(sel_aluno.value, 'Militar')
                        from alerts_manager import AlertsManager
                        pts = float(tipo_row.get('pontuacao', 0.0) or 0.0)
                        alert_type = "success" if pts > 0 else "alert" if pts < 0 else "info"
                        AlertsManager.trigger_alert(
                            "Registro de Ocorrência",
                            f"{aluno_txt} recebeu {tipo_row['nome'].upper()} por {usuario}!",
                            alert_type
                        )
                    else:
                        ui.notify('[OFFLINE] Anotação simulada registrada.', color='warning')
                    data_service.clear_cache()
                    render_dashboard_content.refresh()
                except Exception as e:
                    ui.notify(f'Erro: {e}', color='negative')

            ui.button(
                '⚡ Registrar Anotação', on_click=registrar
            ).props('unelevated no-caps').style(
                f'background:#1B5E20; color:#fff; font-weight:700;'
            ).classes('w-full')


def _build_aviso_rapido_card():
    """Card para publicação rápida de aviso na TV."""
    with ui.card().classes('w-full no-shadow').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-left:3px solid {THEME["accent"]};'
    ):
        with ui.row().classes('items-center gap-2 q-pa-md border-b border-gray-800'):
            ui.icon('campaign', color='accent').classes('text-xl')
            ui.label('AVISO RÁPIDO (TV)').style(
                f'color:{THEME["accent"]}; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
            )

        with ui.column().classes('w-full q-pa-md gap-3'):
            aviso_date_inp = ui.input(
                'Data do Aviso', 
                value=datetime.now().strftime('%Y-%m-%d'),
                on_change=lambda: render_avisos.refresh()
            ).props('dark dense outlined type=date').classes('w-full')
            
            aviso_text_inp = ui.input(
                'Texto do Aviso',
                placeholder='Ex: Formatura Geral às 07:30 Uniforme 3º A.'
            ).props('dark dense outlined').classes('w-full')

            def registrar_aviso():
                val = aviso_text_inp.value.strip()
                if not val:
                    ui.notify('Digite o texto do aviso!', color='warning')
                    return
                
                dt = aviso_date_inp.value
                autor = app.storage.user.get('user_data', {}).get('nome_guerra', 'DASHBOARD').upper()
                
                db_conn = get_db_connection()
                if db_conn:
                    try:
                        db_conn.table('Ordens_Diarias').insert({
                            'data': dt,
                            'texto': val,
                            'autor_id': autor,
                            'status': 'Ativo'
                        }).execute()
                        ui.notify('Aviso publicado no letreiro da TV!', color='positive')
                        
                        # Dispara alerta em tempo real para o Modo TV
                        from alerts_manager import AlertsManager
                        AlertsManager.trigger_alert(
                            "Novo Aviso",
                            f"Aviso publicado por {autor}: {val}",
                            "info"
                        )
                        
                        try:
                            from notifications_manager import notify_telegram
                            alert_txt = (
                                f"📢 **NOVO AVISO CRÍTICO PUBLICADO**\n"
                                f"👤 Autor: {autor}\n\n"
                                f"\"{val}\""
                            )
                            notify_telegram(alert_txt, "aviso")
                        except Exception as e_notif:
                            print(f"[DASHBOARD AVISO NOTIFY ERROR] {e_notif}")
                    except Exception as e:
                        ui.notify(f'Erro ao salvar aviso: {e}', color='negative')
                else:
                    if not hasattr(app, '_mock_ordens_diarias'):
                        app._mock_ordens_diarias = []
                    import random
                    app._mock_ordens_diarias.append({
                        'id': random.randint(1000, 9999),
                        'data': dt,
                        'texto': val,
                        'autor_id': autor,
                        'status': 'Ativo'
                    })
                    ui.notify('[OFFLINE] Aviso simulado salvo.', color='warning')
                
                aviso_text_inp.value = ''
                render_avisos.refresh()
                
            ui.button(
                '⚡ Publicar Aviso na TV', on_click=registrar_aviso
            ).props('unelevated no-caps').style(
                f'background:{THEME["accent"]}; color:#000; font-weight:700;'
            ).classes('cyber-glow w-full')

            @ui.refreshable
            def render_avisos():
                dt = aviso_date_inp.value
                db_conn = get_db_connection()
                avisos = []
                if db_conn:
                    try:
                        res = db_conn.table('Ordens_Diarias').select('*').eq('data', dt).execute()
                        if res.data:
                            avisos = res.data
                    except Exception as e:
                        print(f"Erro ao carregar avisos: {e}")
                else:
                    if hasattr(app, '_mock_ordens_diarias'):
                        avisos = [a for a in app._mock_ordens_diarias if a['data'] == dt]
                
                ui.label('AVISOS ATIVOS NESTE DIA:').classes('text-[10px] text-grey-5 font-bold tracking-widest q-mt-md')
                
                with ui.column().classes('w-full gap-1 q-pa-xs border border-gray-800 rounded bg-black/10').style('max-height: 180px; overflow-y: auto;'):
                    if not avisos:
                        ui.label('Nenhum aviso publicado nesta data.').classes('text-grey italic text-xs q-pa-sm self-center')
                    else:
                        for a in avisos:
                            aid = a.get('id')
                            texto = a.get('texto', '')
                            autor = a.get('autor_id', 'DASHBOARD')
                            
                            with ui.row().classes('w-full items-center justify-between q-py-1 px-2 hover:bg-white/5 rounded border-b border-gray-900'):
                                with ui.column().classes('gap-0').style('flex: 1; margin-right: 8px;'):
                                    ui.label(texto).classes('text-white text-xs font-semibold').style('word-break: break-word;')
                                    ui.label(f"Por: {autor}").classes('text-grey text-[9px]')
                                
                                with ui.row().classes('items-center gap-1 no-wrap'):
                                    def make_edit_handler(aviso_item=a):
                                        def edit_aviso():
                                            with ui.dialog() as edit_dialog, ui.card().classes('q-pa-md w-80').style(
                                                f'background:{THEME["bg_panel"]}; border:{THEME["border"]};'
                                            ):
                                                ui.label('✏️ Editar Aviso').classes('text-white text-sm font-bold')
                                                edit_inp = ui.input(value=aviso_item['texto']).props('dark dense outlined').classes('w-full text-xs')
                                                
                                                def salvar_edicao():
                                                    new_val = edit_inp.value.strip()
                                                    if not new_val:
                                                        ui.notify('Texto não pode ser vazio!', color='warning')
                                                        return
                                                    
                                                    db_c = get_db_connection()
                                                    if db_c:
                                                        try:
                                                            db_c.table('Ordens_Diarias').update({'texto': new_val}).eq('id', aviso_item['id']).execute()
                                                            ui.notify('Aviso atualizado!', color='success')
                                                            edit_dialog.close()
                                                            render_avisos.refresh()
                                                            
                                                            from alerts_manager import AlertsManager
                                                            AlertsManager.trigger_alert("Aviso Atualizado", f"Aviso atualizado por {aviso_item['autor_id']}: {new_val}", "info")
                                                        except Exception as err:
                                                            ui.notify(f'Erro: {err}', color='negative')
                                                    else:
                                                        aviso_item['texto'] = new_val
                                                        ui.notify('[OFFLINE] Edição simulada.', color='warning')
                                                        edit_dialog.close()
                                                        render_avisos.refresh()
                                                        
                                                with ui.row().classes('w-full justify-end gap-2'):
                                                    ui.button('Cancelar', on_click=edit_dialog.close).props('flat dense size=sm color=grey')
                                                    ui.button('Salvar', on_click=salvar_edicao).props('unelevated dense size=sm color=accent text-color=black')
                                            edit_dialog.open()
                                        return edit_aviso
                                    
                                    def make_delete_handler(aviso_id=aid):
                                        def delete_aviso():
                                            db_c = get_db_connection()
                                            if db_c:
                                                try:
                                                    db_c.table('Ordens_Diarias').delete().eq('id', aviso_id).execute()
                                                    ui.notify('Aviso removido!', color='info')
                                                    render_avisos.refresh()
                                                    
                                                    from alerts_manager import AlertsManager
                                                    AlertsManager.trigger_alert("Aviso Removido", "Um aviso foi removido do letreiro.", "info")
                                                except Exception as err:
                                                    ui.notify(f'Erro: {err}', color='negative')
                                            else:
                                                if hasattr(app, '_mock_ordens_diarias'):
                                                    app._mock_ordens_diarias = [item for item in app._mock_ordens_diarias if item['id'] != aviso_id]
                                                ui.notify('[OFFLINE] Remoção simulada.', color='warning')
                                                render_avisos.refresh()
                                        return delete_aviso
                                    
                                    ui.button(icon='edit', on_click=make_edit_handler()).props('flat dense size=xs color=cyan')
                                    ui.button(icon='delete', on_click=make_delete_handler()).props('flat dense size=xs color=red')

            render_avisos()


def _build_pernoite_dashboard_card(pernoite_ids: list):
    """Card para controle rápido de pernoite do dia no dashboard."""
    alunos_df = data_service.get_alunos_data()
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    
    with ui.card().classes('w-full no-shadow').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]}; border-left:3px solid #00BCD4; min-height: 380px; height: 100%;'
    ):
        with ui.row().classes('w-full items-center justify-between q-pa-md border-b border-gray-800'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('nightlight', color='cyan-5').classes('text-xl')
                ui.label('CONTROLE DE PERNOITE').style(
                    f'color:#00BCD4; font-weight:800; letter-spacing:2px; font-size:0.85rem;'
                )
            ui.label('Hoje').classes('text-grey-5 text-xs font-bold')

        with ui.column().classes('w-full q-pa-md gap-3'):
            # Seletor para adicionar aluno ao pernoite
            opcoes_alunos = {
                str(r['id']): f"{r.get('numero_interno', '?')} – {r.get('nome_guerra', '?')} ({r.get('pelotao', '?')})"
                for _, r in alunos_df.iterrows()
                if str(r['id']) not in pernoite_ids
            } if not alunos_df.empty else {}

            with ui.row().classes('w-full items-center gap-2'):
                sel_aluno = ui.select(
                    opcoes_alunos, label='Autorizar Pernoite', with_input=True
                ).props('dark dense outlined').classes('col-grow text-xs')
                
                def autorizar():
                    if not sel_aluno.value:
                        ui.notify('Selecione o militar a autorizar!', color='warning')
                        return
                    db_conn = get_db_connection()
                    if db_conn:
                        try:
                            # Upsert
                            db_conn.table('pernoite').upsert({
                                'aluno_id': int(sel_aluno.value),
                                'data': hoje_str,
                                'presente': True
                            }, on_conflict='aluno_id,data').execute()
                            ui.notify('Pernoite autorizado com sucesso!', color='positive')
                            data_service.clear_cache()
                            render_dashboard_content.refresh()
                        except Exception as e:
                            ui.notify(f'Erro ao autorizar pernoite: {e}', color='negative')
                    else:
                        ui.notify('Sem conexão com banco de dados', color='negative')

                ui.button(icon='add', on_click=autorizar).props('unelevated color=cyan-9').classes('h-10 w-10')

            # Lista dos autorizados hoje
            ui.label('MILITARES AUTORIZADOS HOJE:').classes('text-[10px] text-grey-5 font-bold tracking-widest q-mt-xs')
            
            with ui.column().classes('w-full gap-1 q-pa-xs border border-gray-800 rounded bg-black/10').style('max-height: 180px; overflow-y: auto;'):
                if not pernoite_ids:
                    ui.label('Nenhum aluno autorizado hoje.').classes('text-grey italic text-xs q-pa-sm self-center')
                else:
                    authorized_students = alunos_df[alunos_df['id'].astype(str).isin(pernoite_ids)] if not alunos_df.empty else pd.DataFrame()
                    if authorized_students.empty:
                        ui.label('Carregando autorizados...').classes('text-grey italic text-xs q-pa-sm')
                    else:
                        for _, r in authorized_students.iterrows():
                            aid = str(r['id'])
                            with ui.row().classes('w-full items-center justify-between q-py-1 px-2 hover:bg-white/5 rounded border-b border-gray-900'):
                                with ui.column().classes('gap-0'):
                                    ui.label(f"{r.get('numero_interno', '?')} – {r.get('nome_guerra', '?')}").classes('text-white text-xs font-bold uppercase')
                                    ui.label(r.get('pelotao', '?')).classes('text-grey text-[9px]')
                                
                                def make_delete_handler(student_id=aid):
                                    def delete_pernoite():
                                        db_conn = get_db_connection()
                                        if db_conn:
                                            try:
                                                db_conn.table('pernoite').delete().eq('aluno_id', int(student_id)).eq('data', hoje_str).execute()
                                                ui.notify('Autorização de pernoite removida.', color='info')
                                                data_service.clear_cache()
                                                render_dashboard_content.refresh()
                                            except Exception as e:
                                                ui.notify(f'Erro ao remover: {e}', color='negative')
                                        else:
                                            ui.notify('Sem conexão com banco de dados', color='negative')
                                    return delete_pernoite

                                ui.button(icon='delete', on_click=make_delete_handler()).props('flat dense size=sm color=red')

