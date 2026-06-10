"""
Módulo de Saúde — SisCOMCA
Separa claramente:
  🏥 ENFERMARIA      → Internado / Encaminhado para enfermaria (na enfermaria fisicamente)
  📋 DISPENSA MÉDICA → Presente na unidade mas dispensado de atividade(s)
  🏠 LICENÇA         → Afastado da unidade por dias autorizados

Sincronização em tempo real: ui.timer(15s)
Letreiro (marquee) com últimos lançamentos
Filtro por papel: admin/supervisor = todos | comcia/compel = só seu pelotão
"""
from nicegui import ui, app
import pandas as pd
from datetime import datetime, timedelta
import theme
from database import get_db_connection, load_data
from services import data_service

THEME = theme.colors

# ─────────────────────────────────────────────────────────────────────────────
# Constantes & Configurações
# ─────────────────────────────────────────────────────────────────────────────

TIPOS_DISPENSA = [
    'Total (todas as atividades)',
    'Para Esforço Físico',
    'Para Atividades Externas',
    'Para Armamento',
    'Parcial — Especificar abaixo',
]

TIPOS_LICENCA = [
    'Licença Para Tratamento de Saúde (LTS)',
    'Licença Especial',
    'Licença Nojo',
    'Licença Gala',
    'Afastamento Autorizado',
]

# Mapeamento status → (cor_texto, cor_fundo, ícone)
STATUS_INFO = {
    'Internado':      ('#ff1744', 'rgba(255, 23, 68, 0.05)', 'local_hospital'),
    'Encaminhado para enfermaria':  ('#ff9100', 'rgba(255, 145, 0, 0.05)', 'visibility'),
    'baixado':        ('#ff1744', 'rgba(255, 23, 68, 0.05)', 'local_hospital'),
    'Hospital':       ('#d500f9', 'rgba(213, 0, 249, 0.05)', 'emergency'),
    'Dispensado':     ('#00b0ff', 'rgba(0, 176, 255, 0.05)', 'medical_services'),
    'Licença':        ('#00e5ff', 'rgba(0, 229, 255, 0.05)', 'beach_access'),
    'Alta':           ('#00e676', 'rgba(0, 230, 118, 0.05)', 'check_circle'),
}

TIPO_CATEGORIA = {
    'Internado':     'enfermaria',
    'Encaminhado para enfermaria': 'enfermaria',
    'baixado':       'enfermaria',
    'Hospital':      'hospital',
    'Dispensado':    'dispensa',
    'Licença':       'licenca',
    'Alta':          'alta',
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de banco
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_role_info():
    user = app.storage.user.get('user_data', {})
    role = user.get('role', 'viewer')
    pelotao = user.get('pelotao') if role not in ('admin', 'supervisor') else None
    return role, pelotao


def _carregar_registros_hoje(pelotao_filtro=None) -> list[dict]:
    """Carrega TODOS os registros de saúde de hoje (todos os status)."""
    db_conn = get_db_connection()
    data_hoje = datetime.now().strftime('%Y-%m-%d')

    if not db_conn:
        mock = [
            {'id': 1, 'numero_interno': 201, 'nome_guerra': 'OLIVEIRA', 'turma': 'Bravo',
             'status': 'Encaminhado para enfermaria', 'categoria': 'enfermaria',
             'motivo': 'Cefaleia forte', 'hora': '07:45',
             'data_ini': None, 'data_fim': None, 'detalhe': '', 'observacao': ''},
            {'id': 2, 'numero_interno': 302, 'nome_guerra': 'PEREIRA', 'turma': 'Charlie',
             'status': 'Dispensado', 'categoria': 'dispensa',
             'motivo': 'Lesão no joelho', 'hora': '08:10',
             'data_ini': data_hoje,
             'data_fim': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
             'detalhe': 'Para Esforço Físico', 'observacao': 'Repouso relativo'},
            {'id': 3, 'numero_interno': 105, 'nome_guerra': 'CARVALHO', 'turma': 'Alfa',
             'status': 'Licença', 'categoria': 'licenca',
             'motivo': 'Tratamento médico', 'hora': '06:30',
             'data_ini': data_hoje,
             'data_fim': (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'),
             'detalhe': 'Licença Para Tratamento de Saúde (LTS)', 'observacao': ''},
        ]
        if pelotao_filtro:
            mock = [r for r in mock if r['turma'] == pelotao_filtro]
        return mock

    try:
        # Busca todos os registros ativos (que não possuem status 'Alta')
        resp = db_conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
        registros = resp.data or []
        
        if pelotao_filtro:
            registros = [r for r in registros if r.get('turma') == pelotao_filtro]
            
        # Normaliza e filtra por período de validade para dispensas e licenças
        ativos = []
        for r in registros:
            r.setdefault('data_ini', r.get('data_licenca_ini'))
            r.setdefault('data_fim', r.get('data_licenca_fim'))
            r.setdefault('detalhe', r.get('tipo_licenca', ''))
            r.setdefault('observacao', '')
            
            status = r.get('status', '')
            if status == 'Em Observação':
                status = 'Encaminhado para enfermaria'
                r['status'] = status
            categoria = TIPO_CATEGORIA.get(status, 'outro')
            r.setdefault('categoria', categoria)
            
            # Valida validade do período se for dispensa ou licença
            if categoria in ['dispensa', 'licenca']:
                data_ini = r.get('data_ini')
                data_fim = r.get('data_fim')
                esta_valido = True
                if pd.notna(data_ini) and pd.notna(data_fim) and data_ini and data_fim:
                    try:
                        esta_valido = (str(data_ini) <= data_hoje <= str(data_fim))
                    except Exception:
                        pass
                if not esta_valido:
                    continue
            
            ativos.append(r)
            
        return ativos
    except Exception as e:
        print(f"[SAUDE] Erro carregar registros: {e}")
        return []


def _upsert_registro(
    numero_interno: str, nome_guerra: str, turma: str,
    status: str, motivo: str,
    data_ini: str = '', data_fim: str = '',
    detalhe: str = '', observacao: str = '',
    registro_id: int = 0,
) -> bool:
    db_conn = get_db_connection()
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    hora = datetime.now().strftime('%H:%M')
    categoria = TIPO_CATEGORIA.get(status, 'outro')

    payload = {
        'numero_interno': numero_interno,
        'nome_guerra': nome_guerra,
        'turma': turma,
        'status': status,
        'categoria': categoria,
        'motivo': motivo,
        'data_ini': data_ini or None,
        'data_fim': data_fim or None,
        'data_licenca_ini': data_ini or None,
        'data_licenca_fim': data_fim or None,
        'detalhe': detalhe,
        'tipo_licenca': detalhe,
        'observacao': observacao,
        'data': data_hoje,
        'hora': hora,
        'atualizado_em': datetime.now().isoformat(),
    }

    if not db_conn:
        print(f"[OFFLINE] {nome_guerra} → {status}")
        return True
    try:
        # Verifica se já existe entrada hoje para esse aluno
        if registro_id > 0:
            db_conn.table('enfermaria').update(payload).eq('id', registro_id).execute()
        else:
            resp = db_conn.table('enfermaria').select('id').eq(
                'numero_interno', numero_interno).eq('data', data_hoje).execute()
            if resp.data:
                db_conn.table('enfermaria').update(payload).eq(
                    'id', resp.data[0]['id']).execute()
            else:
                payload['criado_em'] = datetime.now().isoformat()
                db_conn.table('enfermaria').insert(payload).execute()
        
        # Grava o lançamento no histórico de ações/dossier do aluno
        aluno_id = '0'
        try:
            alunos_df = data_service.get_alunos_data()
            if not alunos_df.empty:
                match_al = alunos_df[alunos_df['numero_interno'].astype(str) == str(numero_interno)]
                if not match_al.empty:
                    aluno_id = str(match_al.iloc[0]['id'])
            if aluno_id == '0' and db_conn:
                r_al = db_conn.table('Alunos').select('id').eq('numero_interno', str(numero_interno)).execute()
                if r_al.data:
                    aluno_id = str(r_al.data[0]['id'])
        except Exception as ex_al:
            print(f"[SAUDE] Erro ao buscar aluno_id para Acoes: {ex_al}")

        if aluno_id != '0':
            # Mapeamento do Tipo de Ação
            tipo_nome = 'SAÚDE'
            if status == 'Dispensado':
                tipo_nome = 'DISPENSA MÉDICA'
            elif status == 'Hospital':
                tipo_nome = 'HOSPITAL'
            elif status in ['Encaminhado para enfermaria', 'Internado', 'baixado']:
                tipo_nome = 'ENFERMARIA'
            
            tipo_acao_id = '0'
            try:
                tipos_df = data_service.get_tipos_acao_data()
                if not tipos_df.empty:
                    match_tipo = tipos_df[tipos_df['nome'].str.upper() == tipo_nome]
                    if not match_tipo.empty:
                        tipo_acao_id = str(match_tipo.iloc[0]['id'])
            except Exception as ex_tipo:
                print(f"[SAUDE] Erro ao buscar tipo_acao_id: {ex_tipo}")

            try:
                usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Oficial de Dia')
                if status == 'Alta':
                    descricao_acao = f"Alta Médica: {motivo}"
                elif status == 'Dispensado':
                    descricao_acao = f"Dispensa Médica ({detalhe}): {motivo}"
                    if data_ini and data_fim:
                        descricao_acao += f" ({pd.to_datetime(data_ini).strftime('%d/%m')} a {pd.to_datetime(data_fim).strftime('%d/%m')})"
                elif status == 'Licença':
                    descricao_acao = f"Licença ({detalhe}): {motivo}"
                    if data_ini and data_fim:
                        descricao_acao += f" ({pd.to_datetime(data_ini).strftime('%d/%m')} a {pd.to_datetime(data_fim).strftime('%d/%m')})"
                else:
                    descricao_acao = f"Entrada na Enfermaria ({status}): {motivo}"
                    if observacao:
                        descricao_acao += f" | Obs: {observacao}"
                
                nova_acao = {
                    'aluno_id': aluno_id,
                    'tipo_acao_id': tipo_acao_id if tipo_acao_id != '0' else None,
                    'tipo': tipo_nome,
                    'descricao': descricao_acao,
                    'data': data_hoje,
                    'usuario': usuario,
                    'status': 'Lançado'
                }
                
                if status == 'Dispensado':
                    nova_acao.update({
                        'esta_dispensado': True,
                        'periodo_dispensa_inicio': data_ini,
                        'periodo_dispensa_fim': data_fim,
                        'tipo_dispensa': detalhe
                    })
                    
                db_conn.table('Acoes').insert(nova_acao).execute()
            except Exception as ex_ins:
                print(f"[SAUDE] Erro ao inserir Acao em _upsert_registro: {ex_ins}")
        
        # Dispara alertas em tempo real para as TVs
        try:
            from alerts_manager import AlertsManager
            usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Oficial de Dia').upper()
            militar_lbl = f"{numero_interno} — {str(nome_guerra).upper()} ({str(turma).upper()})"
            if status == 'Alta':
                AlertsManager.trigger_alert(
                    "Alta Médica",
                    f"Militar {militar_lbl} obteve alta médica por {usuario}!",
                    "success"
                )
            elif status in ['Internado', 'baixado', 'Hospital', 'Encaminhado para enfermaria']:
                AlertsManager.trigger_alert(
                    "Aviso de Saúde",
                    f"Militar {militar_lbl} está {str(status).upper()}. Consulte o sistema para detalhes. (Registrado por: {usuario})",
                    "warning"
                )
                
                if status == 'Hospital' or status == 'Hospitalizado':
                    try:
                        from notifications_manager import notify_telegram
                        alert_txt = (
                            f"🏥 **ALERTA: INTERNAÇÃO HOSPITALAR**\n\n"
                            f"👤 Aluno: {str(nome_guerra).upper()} ({numero_interno})\n"
                            f"🩺 Status: HOSPITALIZADO\n"
                            f"📋 Consulte o sistema para detalhes clínicos.\n"
                            f"👮 Registrado por: {usuario}"
                        )
                        notify_telegram(alert_txt, "saude")
                    except Exception as e_notif:
                        print(f"[SAUDE HOSP NOTIFY ERROR] {e_notif}")
            elif status == 'Dispensado':
                AlertsManager.trigger_alert(
                    "Dispensa Médica",
                    f"Militar {militar_lbl} está DISPENSADO ({detalhe}). Consulte o sistema para detalhes. (Registrado por: {usuario})",
                    "warning"
                )
            elif status == 'Licença':
                AlertsManager.trigger_alert(
                    "Licença Médica",
                    f"Militar {militar_lbl} está em LICENÇA. Consulte o sistema para detalhes. (Registrado por: {usuario})",
                    "warning"
                )
            else:
                AlertsManager.trigger_alert(
                    "Atualização de Saúde",
                    f"Militar {militar_lbl} atualizado para {status}. Consulte o sistema para detalhes. (Registrado por: {usuario})",
                    "warning"
                )
        except Exception as e_alert:
            print(f"[SAUDE] Erro ao disparar alerta em tempo real: {e_alert}")

        return True
    except Exception as e:
        print(f"[SAUDE] Erro upsert: {e}")
        return False


def _carregar_historico_recente(pelotao_filtro=None, limit=30) -> list[dict]:
    db_conn = get_db_connection()
    if not db_conn:
        return []
    try:
        resp = db_conn.table('enfermaria').select('*').order(
            'criado_em', desc=True).limit(limit).execute()
        hist = resp.data or []
        if pelotao_filtro:
            hist = [r for r in hist if r.get('turma') == pelotao_filtro]
        return hist
    except Exception as e:
        print(f"[SAUDE] Erro histórico: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Página Principal
# ─────────────────────────────────────────────────────────────────────────────

def render_page():
    render_saude_content()


@ui.refreshable
def render_saude_content():
    role, pelotao_filtro = _get_user_role_info()
    alunos_df     = data_service.get_alunos_data()
    acoes_df      = data_service.get_acoes_data()
    tipos_acao_df = data_service.get_tipos_acao_data()

    for col in ('pelotao', 'nome_guerra', 'numero_interno', 'id'):
        if col not in alunos_df.columns:
            alunos_df[col] = ''

    alunos_view = alunos_df.copy()
    if pelotao_filtro:
        alunos_view = alunos_view[alunos_view['pelotao'] == pelotao_filtro]

    with ui.column().classes('w-full q-pa-lg gap-5'):

        # ── CABEÇALHO ──────────────────────────────────────────────────────
        with ui.row().classes('w-full items-center justify-between'):
            with ui.column().classes('gap-0'):
                theme.section_header(
                    '⚕ Módulo de Saúde',
                    'Enfermaria • Dispensas Médicas • Licenças Autorizadas'
                )
            with ui.row().classes('items-center gap-3'):
                if pelotao_filtro:
                    ui.label(f'🎖 COMCIA — Pelotão {pelotao_filtro}').style(
                        'color:#FF9800; font-size:0.75rem; font-weight:bold;'
                        'border:1px solid #FF9800; padding:4px 10px; border-radius:20px;'
                    )
                ui.button('Atualizar', icon='refresh',
                          on_click=lambda: (data_service.clear_cache(), render_saude_content.refresh())
                          ).props('outline no-caps color=grey dense')

        # ── LETREIRO DE ÚLTIMOS LANÇAMENTOS ─────────────────────────────────
        _build_marquee(pelotao_filtro)

        # ── PAINEL DE SITUAÇÃO EM TEMPO REAL ────────────────────────────────
        _build_situacao_realtime(pelotao_filtro, alunos_df)

        # ── FORMULÁRIOS DE REGISTRO ─────────────────────────────────────────
        with ui.tabs().classes('w-full border-b border-gray-800') as tabs:
            tab_enferm = ui.tab('🏥 Registrar Enfermaria',   icon='local_hospital')
            tab_disp   = ui.tab('📋 Registrar Dispensa',     icon='medical_services')
            tab_lic    = ui.tab('🏠 Registrar Licença',      icon='beach_access')
            tab_hist   = ui.tab('📊 Histórico Completo',     icon='history')

        with ui.tab_panels(tabs, value=tab_enferm).classes('w-full bg-transparent p-0'):
            with ui.tab_panel(tab_enferm):
                _render_form_enfermaria(alunos_view, alunos_df)
            with ui.tab_panel(tab_disp):
                _render_form_dispensa(alunos_view, alunos_df, acoes_df, tipos_acao_df, pelotao_filtro)
            with ui.tab_panel(tab_lic):
                _render_form_licenca(alunos_view, alunos_df, pelotao_filtro)
            with ui.tab_panel(tab_hist):
                _render_historico(alunos_df, pelotao_filtro)


# ─────────────────────────────────────────────────────────────────────────────
# LETREIRO (Marquee) — últimos lançamentos em scroll horizontal
# ─────────────────────────────────────────────────────────────────────────────

def _build_marquee(pelotao_filtro):
    """Letreiro animado com os últimos lançamentos do dia."""
    db_conn = get_db_connection()
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    registros = []

    if db_conn:
        try:
            resp = db_conn.table('enfermaria').select(
                'nome_guerra,turma,status,motivo,hora,data'
            ).order('criado_em', desc=True).limit(20).execute()
            registros = resp.data or []
            if pelotao_filtro:
                registros = [r for r in registros if r.get('turma') == pelotao_filtro]
        except Exception:
            pass

    if not registros:
        # Mock se offline
        registros = [
            {'nome_guerra': 'OLIVEIRA', 'turma': 'Bravo', 'status': 'Encaminhado para enfermaria',
             'motivo': 'Cefaleia', 'hora': '07:45', 'data': data_hoje},
        ]

    def _icone_status(st):
        return {'Internado':'🔴','Em Observação':'🟡','Encaminhado para enfermaria':'🟡','baixado':'🔴',
                'Hospital':'🟣','Dispensado':'🔵','Licença':'🩵','Alta':'🟢'}.get(st,'⚪')

    # Constrói texto do letreiro
    itens = []
    for r in registros:
        status = r.get('status') or 'Outro'
        hora = r.get('hora') or '--:--'
        data_r = r.get('data') or ''
        # Formata data
        try:
            data_fmt = pd.to_datetime(data_r).strftime('%d/%m') if data_r else ''
        except Exception:
            data_fmt = data_r

        nome_guerra_str = str(r.get('nome_guerra') or '?').upper()
        turma_str = str(r.get('turma') or '?').upper()
        motivo_str = str(r.get('motivo') or '')[:40]

        itens.append(
            f"{_icone_status(status)} [{hora}h {data_fmt}] "
            f"{nome_guerra_str} "
            f"(Pel.{turma_str}) → {str(status).upper()}"
            f" — {motivo_str}"
        )

    texto_completo = "     •     ".join(itens) + "     •     " * 3

    with ui.card().classes('w-full no-shadow q-pa-xs overflow-hidden').style(
        'background:#080808; border:1px solid #1A1A1A; border-left:3px solid #D4AF37;'
    ):
        ui.label('📡 ÚLTIMOS LANÇAMENTOS:').style(
            f'color:{THEME["primary"]}; font-size:0.65rem; font-weight:900; '
            'letter-spacing:2px; display:inline-block; margin-right:12px;'
        )
        ui.add_head_html('''
<style>
@keyframes marquee-scroll {
  0%   { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
.marquee-track {
  display: inline-block;
  white-space: nowrap;
  animation: marquee-scroll 40s linear infinite;
  font-size: 0.72rem;
  font-family: monospace;
  color: #ccc;
  letter-spacing: 0.5px;
}
</style>
''')
        with ui.row().classes('w-full overflow-hidden').style('height:22px;'):
            ui.html(f'<div class="marquee-track">{texto_completo}</div>')


# ─────────────────────────────────────────────────────────────────────────────
# PAINEL DE SITUAÇÃO EM TEMPO REAL
# ─────────────────────────────────────────────────────────────────────────────

def _build_situacao_realtime(pelotao_filtro, alunos_df):
    """3 blocos: Enfermaria | Dispensas | Licenças — com timer de sync."""
    with ui.column().classes('w-full gap-4'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('SITUAÇÃO ATUAL').style(
                f'color:{THEME["primary"]}; font-size:0.8rem; font-weight:900; letter-spacing:3px;'
            )
            sync_lbl = ui.label('').classes('text-grey-700 text-[10px] font-mono')

        # Containers dos 3 blocos
        with ui.row().classes('w-full gap-4 items-stretch wrap lg:no-wrap'):
            bloco_enferm  = ui.column().classes('col-grow gap-2').style('min-width:280px;')
            bloco_disp    = ui.column().classes('col-grow gap-2').style('min-width:280px;')
            bloco_lic     = ui.column().classes('col-grow gap-2').style('min-width:280px;')

        def _refresh():
            registros = _carregar_registros_hoje(pelotao_filtro)
            sync_lbl.set_text(f'⟳ Sincronizado às {datetime.now().strftime("%H:%M:%S")}')

            # Separa por categoria
            enferm_list = [r for r in registros if TIPO_CATEGORIA.get(r.get('status',''),'') == 'enfermaria']
            disp_list   = [r for r in registros if TIPO_CATEGORIA.get(r.get('status',''),'') == 'dispensa']
            lic_list    = [r for r in registros if TIPO_CATEGORIA.get(r.get('status',''),'') == 'licenca']

            # ── BLOCO ENFERMARIA ──────────────────────────────────────────
            bloco_enferm.clear()
            with bloco_enferm:
                _bloco_header('🏥 ENFERMARIA', len(enferm_list), '#F44336')
                if not enferm_list:
                    _card_vazio('Nenhum aluno na enfermaria agora.')
                else:
                    for r in enferm_list:
                        _card_ativo(r, alunos_df, mostrar_alta=True)

            # ── BLOCO DISPENSAS ───────────────────────────────────────────
            bloco_disp.clear()
            with bloco_disp:
                _bloco_header('📋 COM DISPENSA MÉDICA', len(disp_list), '#2196F3')
                if not disp_list:
                    _card_vazio('Nenhum aluno com dispensa ativa hoje.')
                else:
                    for r in disp_list:
                        _card_dispensa(r, alunos_df)

            # ── BLOCO LICENÇAS ────────────────────────────────────────────
            bloco_lic.clear()
            with bloco_lic:
                _bloco_header('🏠 EM LICENÇA', len(lic_list), '#26C6DA')
                if not lic_list:
                    _card_vazio('Nenhum aluno em licença hoje.')
                else:
                    for r in lic_list:
                        _card_licenca(r, alunos_df)

        # Timer de 15 segundos
        ui.timer(15.0, _refresh)
        _refresh()


# ─────────────────────────────────────────────────────────────────────────────
# Componentes de Card
# ─────────────────────────────────────────────────────────────────────────────

def _bloco_header(titulo: str, count: int, cor: str):
    with ui.card().classes('w-full no-shadow q-px-md q-py-sm').style(
        f'background:#0A0A0A; border:1px solid #1A1A1A; border-left:4px solid {cor};'
    ):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label(titulo).style(
                f'color:{cor}; font-size:0.75rem; font-weight:900; letter-spacing:2px;'
            )
            ui.label(str(count)).style(
                f'color:{cor}; font-size:2rem; font-weight:900; '
                'font-family:monospace; line-height:1;'
            )


def _card_vazio(msg: str):
    with ui.card().classes('w-full no-shadow q-pa-sm items-center').style(
        'background:#080808; border:1px solid #111;'
    ):
        ui.label(msg).classes('text-grey-700 italic text-xs text-center')


def _abrir_anotacao_saude_dialog(numero_interno: str, nome_guerra: str, turma: str, alunos_df: pd.DataFrame):
    """Abre um diálogo para adicionar uma anotação de saúde diretamente na ficha/cadastro do aluno."""
    d = ui.dialog()
    with d, ui.card().classes('w-[420px] q-pa-lg').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]};'
    ):
        ui.label('⚕️ Adicionar Anotação de Saúde').style(f'color:{THEME["primary"]}; font-weight:bold; font-size:1.1rem;')
        ui.label(f'Militar: {nome_guerra} ({numero_interno}) • Pelotão: {turma}').classes('text-grey text-caption q-mb-md')
        
        db_conn = get_db_connection()
        tipos_df = data_service.get_tipos_acao_data()
        
        # Tipos padrão se vazio/erro
        health_types = [
            {'id': '44', 'nome': 'SAÚDE'},
            {'id': '42', 'nome': 'DISPENSA MÉDICA'},
            {'id': '37', 'nome': 'ENFERMARIA'},
            {'id': '6', 'nome': 'HOSPITAL'}
        ]
        
        if not tipos_df.empty:
            match_types = tipos_df[tipos_df['nome'].str.upper().isin(['SAÚDE', 'DISPENSA MÉDICA', 'ENFERMARIA', 'HOSPITAL'])]
            if not match_types.empty:
                health_types = match_types[['id', 'nome']].to_dict(orient='records')
        
        opcoes = {str(item['id']): item['nome'] for item in health_types}
        default_val = None
        for item in health_types:
            if item['nome'].upper() == 'SAÚDE':
                default_val = str(item['id'])
                break
        if not default_val and health_types:
            default_val = str(health_types[0]['id'])
            
        tipo_sel = ui.select(opcoes, value=default_val, label='Tipo de Anotação').props('dark outlined dense').classes('w-full q-mb-md')
        desc_inp = ui.textarea('Anotação de Saúde').props('dark outlined dense rows=3 placeholder="Descreva os sintomas, atendimento ou orientações médicas..."').classes('w-full q-mb-md')
        err = ui.label('').classes('text-caption text-red')
        
        def confirmar():
            if not desc_inp.value:
                err.text = 'Preencha a descrição da anotação.'
                return
            
            try:
                # Localizar aluno_id
                aluno_id = '0'
                if not alunos_df.empty:
                    match_al = alunos_df[alunos_df['numero_interno'].astype(str) == str(numero_interno)]
                    if not match_al.empty:
                        aluno_id = str(match_al.iloc[0]['id'])
                
                if aluno_id == '0' and db_conn:
                    r_al = db_conn.table('Alunos').select('id').eq('numero_interno', str(numero_interno)).execute()
                    if r_al.data:
                        aluno_id = str(r_al.data[0]['id'])
                
                if aluno_id == '0':
                    err.text = 'Erro: Aluno não localizado na base de dados.'
                    return
                
                usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Oficial de Dia')
                tipo_nome = opcoes[tipo_sel.value]
                
                nova_acao = {
                    'aluno_id': aluno_id,
                    'tipo_acao_id': tipo_sel.value,
                    'tipo': tipo_nome,
                    'descricao': desc_inp.value,
                    'data': datetime.now().strftime('%Y-%m-%d'),
                    'usuario': usuario,
                    'status': 'Lançado'
                }
                
                if db_conn:
                    db_conn.table('Acoes').insert(nova_acao).execute()
                    ui.notify(f"Anotação registrada para {nome_guerra}!", color='positive')
                    d.close()
                    data_service.clear_cache()
                    render_saude_content.refresh()
                else:
                    ui.notify('[OFFLINE] Conexão indisponível', color='warning')
                    d.close()
            except Exception as ex:
                print(f"[SAUDE] Erro ao adicionar anotação: {ex}")
                err.text = 'Erro ao salvar anotação.'
                
        with ui.row().classes('w-full justify-end gap-2 q-mt-sm'):
            ui.button('Cancelar', on_click=d.close).props('flat color=grey')
            ui.button('💾 Confirmar Lançamento', on_click=confirmar).props('unelevated color=primary text-color=black')

    d.open()


def _abrir_alta_dialog(rid, ni, ng, t, alunos_df):
    """Abre um diálogo/questionário de alta médica perguntando se é Alta Normal ou com Restrições/Dispensa."""
    d = ui.dialog()
    with d, ui.card().classes('w-[420px] q-pa-lg').style(
        f'background:{THEME["bg_panel"]}; border:{THEME["border"]};'
    ):
        ui.label('✅ Alta Médica').style(f'color:{THEME["primary"]}; font-weight:bold; font-size:1.1rem;')
        ui.label(f'Militar: {ng} ({ni}) • Pelotão: {t}').classes('text-grey text-caption q-mb-md')
        
        ui.label('Selecione o tipo de alta:').classes('text-white text-xs font-bold q-mb-xs')
        tipo_alta = ui.radio(
            {1: 'Alta Normal (Sem restrições)', 2: 'Alta com Dispensa / Restrições'},
            value=1
        ).props('dark').classes('text-xs text-grey-4 q-mb-md')
        
        # Container para os campos de dispensa (só visíveis se selecionar opção 2)
        disp_container = ui.column().classes('w-full gap-3 q-mb-md')
        
        # Cria os campos dentro do container de dispensa
        with disp_container:
            tipo_disp  = ui.select(TIPOS_DISPENSA, value=TIPOS_DISPENSA[0], label='Tipo de Dispensa').props('dark outlined dense').classes('w-full')
            with ui.row().classes('w-full gap-2'):
                d_ini = ui.input('Início', value=datetime.now().strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('col-grow')
                d_fim = ui.input('Fim', value=(datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('col-grow')
            motivo_inp = ui.input('Motivo / Diagnóstico resumido').props('dark outlined dense').classes('w-full')
            obs_inp    = ui.textarea('Restrições detalhadas').props('dark outlined dense rows=2').classes('w-full')
            
        # Controla a visibilidade dos campos de dispensa
        disp_container.bind_visibility_from(tipo_alta, 'value', value=2)
        
        err = ui.label('').classes('text-caption text-red')
        
        def confirmar():
            if tipo_alta.value == 1:
                # Alta Normal
                ok = _upsert_registro(ni, ng, t, 'Alta', 'Alta médica concedida (Normal)', registro_id=rid)
                if ok:
                    ui.notify(f'Alta concedida — {ng}', color='positive')
                    d.close()
                    data_service.clear_cache()
                    render_saude_content.refresh()
                else:
                    err.text = 'Erro ao registrar alta.'
            else:
                # Alta com Dispensa
                if not motivo_inp.value:
                    err.text = 'Preencha o motivo da dispensa.'
                    return
                    
                # 1. Registrar Alta na internação atual
                ok1 = _upsert_registro(ni, ng, t, 'Alta', f'Alta concedida com restrições: {motivo_inp.value}', registro_id=rid)
                
                # 2. Registrar nova Dispensa
                ok2 = _upsert_registro(
                    ni, ng, t,
                    'Dispensado',
                    motivo_inp.value,
                    data_ini=d_ini.value,
                    data_fim=d_fim.value,
                    detalhe=tipo_disp.value,
                    observacao=obs_inp.value or '',
                )
                
                # 3. Registrar Ação
                if ok1 and ok2:
                    ui.notify(f'Alta e Dispensa registradas — {ng}', color='positive')
                    d.close()
                    data_service.clear_cache()
                    render_saude_content.refresh()
                else:
                    err.text = 'Erro ao salvar registros.'
                    
        with ui.row().classes('w-full justify-end gap-2 q-mt-sm'):
            ui.button('Cancelar', on_click=d.close).props('flat color=grey')
            ui.button('💾 Confirmar', on_click=confirmar).props('unelevated color=primary text-color=black')
            
    d.open()


def _card_ativo(r: dict, alunos_df, mostrar_alta=False):
    status = r.get('status') or 'Encaminhado para enfermaria'
    cor, bg, ico = STATUS_INFO.get(status, ('#888', '#111', 'help'))
    reg_id = r.get('id', 0)
    num_int = str(r.get('numero_interno') or '')
    nome = str(r.get('nome_guerra') or '???')
    turma = str(r.get('turma') or '?')
    motivo = str(r.get('motivo') or '')
    hora = str(r.get('hora') or '--:--')

    with ui.card().classes('w-full no-shadow q-pa-sm').style(
        f'background:{bg}; border:1px solid rgba(0, 229, 255, 0.15); border-left:3px solid {cor};'
    ):
        with ui.row().classes('w-full items-start justify-between gap-2'):
            with ui.column().classes('gap-0').style('flex:1;'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon(ico, color=cor[1:] if cor.startswith('#') else cor).classes('text-sm')
                    ui.label(str(nome).upper()).style(
                        f'color:#fff; font-size:0.8rem; font-weight:900;'
                    )
                    ui.label(f'({num_int})').classes('text-grey-5 text-xs')

                with ui.row().classes('items-center gap-3 q-mt-xs'):
                    ui.label(f'🕐 {hora}h').style('color:#64748b; font-size:0.65rem; font-weight:bold;')
                    ui.label(f'Pel. {turma}').style('color:#475569; font-size:0.65rem;')

                ui.label(motivo).style(
                    'color:#94a3b8; font-size:0.7rem; font-style:italic; '
                    'white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:200px;'
                )

            with ui.column().classes('items-end gap-1').style('min-width:80px;'):
                ui.label(str(status).upper()).style(
                    f'color:{cor}; font-size:0.6rem; font-weight:bold; '
                    f'border:1px solid {cor}; padding:2px 5px; border-radius:3px; '
                    'white-space:nowrap;'
                ).classes('cyber-title')
                with ui.row().classes('items-center gap-1.5'):
                    # Botão Adicionar Anotação
                    ui.button(icon='post_add', on_click=lambda: _abrir_anotacao_saude_dialog(num_int, nome, turma, alunos_df)).props('unelevated dense round').style(
                        'background:#2a2a2a; color:#fff; font-size:0.6rem; width:22px; height:22px;'
                    )
                    if mostrar_alta:
                        # Botão Alta (abre questionário/diálogo)
                        ui.button('✅ Alta', on_click=lambda: _abrir_alta_dialog(reg_id, num_int, nome, turma, alunos_df)).props('unelevated dense no-caps').style(
                            'background:#00e676; color:#000; font-size:0.6rem; font-weight:bold; padding:2px 8px;'
                        )


def _card_dispensa(r: dict, alunos_df):
    """Card de dispensa com expandir para ver detalhes."""
    cor, bg, ico = STATUS_INFO.get('Dispensado', ('#2196F3', '#001020', 'medical_services'))
    reg_id  = r.get('id', 0)
    num_int = str(r.get('numero_interno', ''))
    nome    = str(r.get('nome_guerra', '???'))
    turma   = str(r.get('turma', '?'))
    motivo  = str(r.get('motivo', ''))
    hora    = str(r.get('hora', '--:--'))
    detalhe = str(r.get('detalhe', r.get('tipo_licenca', '')))
    data_fim = r.get('data_fim', r.get('data_licenca_fim', ''))
    obs     = str(r.get('observacao', ''))

    # Calcula dias restantes
    dias_rest = ''
    if data_fim:
        try:
            fim_dt = pd.to_datetime(data_fim).date()
            diff   = (fim_dt - datetime.now().date()).days
            if diff >= 0:
                dias_rest = f'{diff} dia(s) restante(s)'
            else:
                dias_rest = 'EXPIRADO'
        except Exception:
            pass

    with ui.expansion(
        f'{nome.upper()} ({num_int}) — {detalhe or "Dispensa"}',
        icon='medical_services'
    ).classes('w-full no-shadow').style(
        f'background:{bg}; border:1px solid rgba(0, 229, 255, 0.15); border-left:3px solid {cor};'
    ):
        with ui.column().classes('w-full gap-2 q-pa-xs'):
            with ui.row().classes('w-full gap-4 wrap'):
                _info_chip('🕐 Entrada', f'{hora}h', '#64748b')
                _info_chip('🎖 Pelotão', f'Pel. {turma}', '#94a3b8')
                if dias_rest:
                    cor_dias = '#ff1744' if 'EXPI' in dias_rest else '#00b0ff'
                    _info_chip('📅 Validade', dias_rest, cor_dias)

            ui.label(f'Motivo: {motivo}').style('color:#94a3b8; font-size:0.7rem; font-style:italic;')
            if obs:
                ui.label(f'Obs: {obs}').style('color:#64748b; font-size:0.65rem;')

            # Botão encerrar dispensa
            def _encerrar(rid=reg_id, ni=num_int, ng=nome, t=turma):
                ok = _upsert_registro(str(ni), ng, t, 'Alta', 'Dispensa encerrada', registro_id=rid)
                if ok:
                    ui.notify(f'Dispensa encerrada — {ng}', color='positive')
                    data_service.clear_cache()
                    render_saude_content.refresh()
                else:
                    ui.notify('Erro ao encerrar dispensa', color='negative')
            with ui.row().classes('items-center gap-2 q-mt-xs'):
                # Botão Adicionar Anotação
                ui.button(icon='post_add', on_click=lambda: _abrir_anotacao_saude_dialog(num_int, nome, turma, alunos_df)).props('unelevated dense round').style(
                    'background:#2a2a2a; color:#fff; font-size:0.65rem; width:26px; height:26px;'
                )
                ui.button('⬜ Encerrar Dispensa', on_click=_encerrar).props(
                    'unelevated dense no-caps'
                ).style('background:#00a2ff; color:#000; font-weight:bold; font-size:0.65rem; padding:3px 10px;')


def _card_licenca(r: dict, alunos_df):
    """Card de licença com informações de período."""
    cor, bg, ico = STATUS_INFO.get('Licença', ('#00e5ff', 'rgba(0, 229, 255, 0.05)', 'beach_access'))
    reg_id   = r.get('id', 0)
    num_int  = str(r.get('numero_interno', ''))
    nome     = str(r.get('nome_guerra', '???'))
    turma    = str(r.get('turma', '?'))
    motivo   = str(r.get('motivo', ''))
    hora     = str(r.get('hora', '--:--'))
    detalhe  = str(r.get('detalhe', r.get('tipo_licenca', 'Licença')))
    data_ini = r.get('data_ini', r.get('data_licenca_ini', ''))
    data_fim = r.get('data_fim', r.get('data_licenca_fim', ''))

    ini_fmt, fim_fmt, dias_rest = '?', '?', ''
    if data_ini:
        try:
            ini_fmt = pd.to_datetime(data_ini).strftime('%d/%m/%Y')
        except Exception:
            pass
    if data_fim:
        try:
            fim_dt  = pd.to_datetime(data_fim).date()
            fim_fmt = fim_dt.strftime('%d/%m/%Y')
            diff    = (fim_dt - datetime.now().date()).days
            dias_rest = f'{diff} dia(s) restante(s)' if diff >= 0 else 'RETORNOU'
        except Exception:
            pass

    with ui.card().classes('w-full no-shadow q-pa-sm').style(
        f'background:{bg}; border:1px solid rgba(0, 229, 255, 0.15); border-left:3px solid {cor};'
    ):
        with ui.row().classes('w-full items-start justify-between gap-2'):
            with ui.column().classes('gap-1').style('flex:1;'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon(ico, color='cyan-5').classes('text-sm')
                    ui.label(nome.upper()).style('color:#fff; font-size:0.8rem; font-weight:900;')
                    ui.label(f'({num_int}) Pel. {turma}').classes('text-grey-5 text-xs')

                ui.label(detalhe).style(
                    f'color:{cor}; font-size:0.65rem; font-weight:bold;'
                )
                ui.label(f'Motivo: {motivo}').style('color:#94a3b8; font-size:0.7rem; font-style:italic;')

                with ui.row().classes('items-center gap-3 q-mt-xs'):
                    _info_chip('🕐', hora + 'h', '#475569')
                    _info_chip('📅', f'{ini_fmt} → {fim_fmt}', '#00e5ff')
                    if dias_rest:
                        cor_d = '#ff1744' if 'RETORNOU' in dias_rest else '#00e676'
                        _info_chip('⏱', dias_rest, cor_d)

                # Botão encerrar licença
                def _encerrar_lic(rid=reg_id, ni=num_int, ng=nome, t=turma):
                    ok = _upsert_registro(str(ni), ng, t, 'Alta', 'Licença encerrada', registro_id=rid)
                    if ok:
                        ui.notify(f'Licença encerrada — {ng}', color='positive')
                        data_service.clear_cache()
                        render_saude_content.refresh()
                    else:
                        ui.notify('Erro ao encerrar licença', color='negative')
                with ui.row().classes('items-center gap-2 q-mt-xs'):
                    # Botão Adicionar Anotação
                    ui.button(icon='post_add', on_click=lambda: _abrir_anotacao_saude_dialog(num_int, nome, turma, alunos_df)).props('unelevated dense round').style(
                        'background:#2a2a2a; color:#fff; font-size:0.65rem; width:26px; height:26px;'
                    )
                    ui.button('⬜ Encerrar Licença', on_click=_encerrar_lic).props(
                        'unelevated dense no-caps'
                    ).style('background:#00e5ff; color:#000; font-weight:bold; font-size:0.65rem; padding:3px 10px;')

            ui.label('LICENÇA').style(
                f'color:{cor}; font-size:0.6rem; font-weight:bold; '
                f'border:1px solid {cor}; padding:2px 5px; border-radius:3px;'
            ).classes('cyber-title')


def _info_chip(label: str, valor: str, cor: str):
    with ui.column().classes('gap-0 items-center').style('min-width:fit-content;'):
        ui.label(label).style('color:#64748b; font-size:0.55rem; font-weight:bold;')
        ui.label(valor).style(f'color:{cor}; font-size:0.65rem; font-weight:bold;')


# ─────────────────────────────────────────────────────────────────────────────
# Formulários de Registro
# ─────────────────────────────────────────────────────────────────────────────

def _render_form_enfermaria(alunos_view, alunos_df):
    """Formulário de entrada na enfermaria (internação / observação)."""
    with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap q-pt-md'):
        with ui.column().classes('w-full lg:w-5/12 gap-4'):
            ui.label('REGISTRAR ENTRADA NA ENFERMARIA').classes(
                'text-white text-xs font-bold uppercase tracking-wider'
            )
            with ui.card().classes('w-full q-pa-md border border-gray-800').style(
                f'background:{THEME["bg_panel"]};'
            ):
                opcoes = {str(r['id']): f"{r['numero_interno']} — {r['nome_guerra']} ({r['pelotao']})"
                          for _, r in alunos_view.iterrows()}
                aluno_sel  = ui.select(opcoes, label='Aluno').props('dark outlined dense').classes('w-full')
                status_sel = ui.select(
                    ['Encaminhado para enfermaria', 'Internado', 'Hospital'],
                    value='Encaminhado para enfermaria', label='Status'
                ).props('dark outlined dense').classes('w-full')
                motivo_inp = ui.input('Motivo / Queixa Principal').props('dark outlined dense').classes('w-full')
                obs_inp    = ui.textarea('Observações Adicionais').props('dark outlined dense rows=2').classes('w-full')
                err        = ui.label('').classes('text-caption text-red')

                def _salvar():
                    if not aluno_sel.value or not motivo_inp.value:
                        err.text = 'Selecione o aluno e informe o motivo.'
                        return
                    row = alunos_df[alunos_df['id'].astype(str) == str(aluno_sel.value)]
                    if row.empty:
                        err.text = 'Aluno não encontrado.'
                        return
                    r = row.iloc[0]
                    ok = _upsert_registro(
                        str(r.get('numero_interno', '')),
                        str(r.get('nome_guerra', '')),
                        str(r.get('pelotao', '')),
                        status_sel.value,
                        motivo_inp.value,
                        observacao=obs_inp.value or '',
                    )
                    if ok:
                        ui.notify(f"✅ {r['nome_guerra']} registrado na enfermaria!", color='positive')
                        data_service.clear_cache()
                        render_saude_content.refresh()
                    else:
                        err.text = 'Erro ao salvar. Verifique a conexão.'

                ui.button('🏥 Registrar Entrada', on_click=_salvar).props(
                    'unelevated no-caps w-full'
                ).style(f'background:{THEME["primary"]}; color:#000; font-weight:700;').classes('q-mt-sm')

        # Dica visual
        with ui.column().classes('w-full lg:w-7/12 gap-4'):
            with ui.card().classes('w-full no-shadow q-pa-md border border-gray-800').style(
                f'background:{THEME["bg_panel"]};'
            ):
                ui.label('ℹ️ Sobre o módulo de Enfermaria').classes('text-amber-5 font-bold text-xs q-mb-sm')
                for item in [
                    ('🏥 Encaminhado para enfermaria', 'Aluno está na enfermaria aguardando avaliação médica.'),
                    ('🔴 Internado', 'Aluno está internado, sem previsão de alta imediata.'),
                    ('🟣 Hospital', 'Aluno foi encaminhado para unidade hospitalar externa.'),
                    ('✅ Alta', 'Alta médica concedida — aluno retorna às atividades normais.'),
                ]:
                    with ui.row().classes('items-start gap-2 q-py-xs border-b border-gray-800'):
                        ui.label(item[0]).classes('text-white text-xs font-bold').style('min-width:120px;')
                        ui.label(item[1]).classes('text-grey-4 text-xs')


def _render_form_dispensa(alunos_view, alunos_df, acoes_df, tipos_acao_df, pelotao_filtro):
    """Dispensa médica = aluno presente mas com restrição de atividade."""
    with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap q-pt-md'):
        with ui.column().classes('w-full lg:w-5/12 gap-4'):
            ui.label('LANÇAR DISPENSA MÉDICA').classes(
                'text-white text-xs font-bold uppercase tracking-wider'
            )
            with ui.card().classes('w-full q-pa-md border border-gray-800').style(
                f'background:{THEME["bg_panel"]};'
            ):
                opcoes = {str(r['id']): f"{r['numero_interno']} — {r['nome_guerra']} ({r['pelotao']})"
                          for _, r in alunos_view.iterrows()}
                aluno_sel  = ui.select(opcoes, label='Aluno').props('dark outlined dense').classes('w-full')
                tipo_disp  = ui.select(TIPOS_DISPENSA, value=TIPOS_DISPENSA[0], label='Tipo de Dispensa').props('dark outlined dense').classes('w-full')

                with ui.row().classes('w-full gap-3'):
                    data_ini = ui.input('Início', value=datetime.now().strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('col-grow')
                    data_fim = ui.input('Fim', value=(datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('col-grow')

                motivo_inp = ui.input('Motivo / Diagnóstico resumido').props('dark outlined dense').classes('w-full')
                obs_inp    = ui.textarea('Restrições detalhadas').props('dark outlined dense rows=2').classes('w-full')
                err        = ui.label('').classes('text-caption text-red')

                def _salvar():
                    if not aluno_sel.value or not motivo_inp.value:
                        err.text = 'Selecione o aluno e informe o motivo.'
                        return
                    row = alunos_df[alunos_df['id'].astype(str) == str(aluno_sel.value)]
                    if row.empty:
                        err.text = 'Aluno não encontrado.'
                        return
                    r = row.iloc[0]
                    ok = _upsert_registro(
                        str(r.get('numero_interno', '')),
                        str(r.get('nome_guerra', '')),
                        str(r.get('pelotao', '')),
                        'Dispensado',
                        motivo_inp.value,
                        data_ini=data_ini.value,
                        data_fim=data_fim.value,
                        detalhe=tipo_disp.value,
                        observacao=obs_inp.value or '',
                    )
                    # Também registra na tabela Acoes para histórico de conceito (removido duplicidade, já tratado em _upsert_registro)
                    if ok:
                        ui.notify(f"📋 Dispensa registrada para {r['nome_guerra']}!", color='positive')
                        data_service.clear_cache()
                        render_saude_content.refresh()
                    else:
                        err.text = 'Erro ao salvar.'

                ui.button('📋 Lançar Dispensa', on_click=_salvar).props(
                    'unelevated no-caps w-full'
                ).style(f'background:{THEME["primary"]}; color:#000; font-weight:700;').classes('q-mt-sm')

        # Dispensas ativas listadas
        with ui.column().classes('w-full lg:w-7/12 gap-4'):
            ui.label('DISPENSAS ATIVAS — HISTÓRICO').classes('text-white text-xs font-bold uppercase tracking-wider')
            _lista_dispensas_historico(acoes_df, alunos_df, pelotao_filtro)


def _lista_dispensas_historico(acoes_df, alunos_df, pelotao_filtro):
    """Lista dispensas registradas na tabela Acoes."""
    if acoes_df.empty:
        ui.label('Sem registros de saúde no banco.').classes('text-grey italic text-xs')
        return

    hoje = datetime.now().date()
    tipos_saude = ['DISPENSA MÉDICA', 'ENFERMARIA', 'HOSPITAL', 'NAS', 'SAÚDE']
    filtro = acoes_df[acoes_df['tipo'].isin(tipos_saude)].copy()
    if filtro.empty:
        ui.label('Nenhum registro de saúde nas ações.').classes('text-grey italic text-xs')
        return

    filtro['aluno_id'] = filtro['aluno_id'].astype(str)
    alunos_df['id'] = alunos_df['id'].astype(str)
    merged = pd.merge(filtro, alunos_df[['id', 'nome_guerra', 'numero_interno', 'pelotao']],
                      left_on='aluno_id', right_on='id', how='inner')
    if pelotao_filtro:
        merged = merged[merged['pelotao'] == pelotao_filtro]
    merged = merged.sort_values('data', ascending=False)

    if merged.empty:
        ui.label('Nenhum registro para este pelotão.').classes('text-grey italic text-xs')
        return

    for _, r in merged.iterrows():
        fim_exc = r.get('periodo_dispensa_fim')
        ativa = False
        if r.get('esta_dispensado') and pd.notna(fim_exc):
            try:
                ativa = pd.to_datetime(fim_exc).date() >= hoje
            except Exception:
                pass

        cor = '#2196F3' if ativa else '#333'
        lbl = '● ATIVA' if ativa else '○ EXPIRADA'

        with ui.card().classes('w-full no-shadow q-pa-xs').style(
            f'background:#0A0A0A; border:1px solid #1A1A1A; border-left:3px solid {cor};'
        ):
            with ui.row().classes('w-full items-start justify-between gap-2'):
                with ui.column().classes('gap-0').style('flex:1;'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(r['nome_guerra']).classes('text-white font-bold uppercase text-xs')
                        ui.label(f"({r['numero_interno']}) • Pel. {r['pelotao']}").classes('text-grey-600 text-[10px]')
                    if r.get('esta_dispensado'):
                        ini = pd.to_datetime(r['periodo_dispensa_inicio']).strftime('%d/%m/%Y') if pd.notna(r.get('periodo_dispensa_inicio')) else '?'
                        fim = pd.to_datetime(r['periodo_dispensa_fim']).strftime('%d/%m/%Y') if pd.notna(r.get('periodo_dispensa_fim')) else '?'
                        ui.label(f"{r.get('tipo_dispensa', '')} — {ini} → {fim}").style(
                            f'color:{cor}; font-size:0.65rem; font-weight:bold;'
                        )
                    ui.label(r['descricao']).style(
                        'color:#555; font-size:0.65rem; font-style:italic; '
                        'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:300px;'
                    )
                with ui.column().classes('items-end gap-1'):
                    ui.label(lbl).style(f'color:{cor}; font-size:0.6rem; font-weight:bold;')
                    ui.label(pd.to_datetime(r['data']).strftime('%d/%m/%Y')).classes('text-grey-700 text-[10px]')


def _render_form_licenca(alunos_view, alunos_df, pelotao_filtro):
    """Licença = afastamento autorizado da unidade por dias."""
    with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap q-pt-md'):
        with ui.column().classes('w-full lg:w-5/12 gap-4'):
            ui.label('AUTORIZAR LICENÇA').classes(
                'text-white text-xs font-bold uppercase tracking-wider'
            )
            with ui.card().classes('w-full q-pa-md border border-gray-800').style(
                f'background:{THEME["bg_panel"]};'
            ):
                opcoes = {str(r['id']): f"{r['numero_interno']} — {r['nome_guerra']} ({r['pelotao']})"
                          for _, r in alunos_view.iterrows()}
                aluno_sel  = ui.select(opcoes, label='Aluno').props('dark outlined dense').classes('w-full')
                tipo_lic   = ui.select(TIPOS_LICENCA, value=TIPOS_LICENCA[0], label='Tipo de Licença').props('dark outlined dense').classes('w-full')

                with ui.row().classes('w-full gap-3'):
                    data_ini = ui.input('Início', value=datetime.now().strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('col-grow')
                    data_fim = ui.input('Fim', value=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('col-grow')

                motivo_inp = ui.input('Fundamentação / Observação').props('dark outlined dense').classes('w-full')
                err        = ui.label('').classes('text-caption text-red')

                def _salvar():
                    if not aluno_sel.value or not motivo_inp.value:
                        err.text = 'Selecione o aluno e informe a fundamentação.'
                        return
                    if not data_ini.value or not data_fim.value:
                        err.text = 'Informe início e fim da licença.'
                        return
                    row = alunos_df[alunos_df['id'].astype(str) == str(aluno_sel.value)]
                    if row.empty:
                        err.text = 'Aluno não encontrado.'
                        return
                    r = row.iloc[0]
                    ok = _upsert_registro(
                        str(r.get('numero_interno', '')),
                        str(r.get('nome_guerra', '')),
                        str(r.get('pelotao', '')),
                        'Licença',
                        motivo_inp.value,
                        data_ini=data_ini.value,
                        data_fim=data_fim.value,
                        detalhe=tipo_lic.value,
                    )
                    if ok:
                        ui.notify(f"🏠 Licença autorizada — {r['nome_guerra']}!", color='positive')
                        data_service.clear_cache()
                        render_saude_content.refresh()
                    else:
                        err.text = 'Erro ao salvar.'

                ui.button('🏠 Autorizar Licença', on_click=_salvar).props(
                    'unelevated no-caps w-full'
                ).style(f'background:{THEME["primary"]}; color:#000; font-weight:700;').classes('q-mt-sm')

        # Licenças ativas
        with ui.column().classes('w-full lg:w-7/12 gap-4'):
            ui.label('LICENÇAS ATIVAS / VIGENTES').classes('text-white text-xs font-bold uppercase tracking-wider')
            _lista_licencas_ativas(pelotao_filtro)


def _lista_licencas_ativas(pelotao_filtro):
    db_conn = get_db_connection()
    hoje = datetime.now().strftime('%Y-%m-%d')
    registros = []

    if db_conn:
        try:
            resp = db_conn.table('enfermaria').select('*').eq('status', 'Licença').execute()
            registros = resp.data or []
            if pelotao_filtro:
                registros = [r for r in registros if r.get('turma') == pelotao_filtro]
        except Exception:
            pass

    if not registros:
        ui.label('Nenhuma licença vigente.').classes('text-grey italic text-xs')
        return

    for r in registros:
        _card_licenca(r, pd.DataFrame())


# ─────────────────────────────────────────────────────────────────────────────
# TAB HISTÓRICO
# ─────────────────────────────────────────────────────────────────────────────

def _render_historico(alunos_df, pelotao_filtro):
    with ui.column().classes('w-full gap-4 q-pt-md'):
        ui.label('HISTÓRICO COMPLETO DE ATENDIMENTOS').classes(
            'text-white text-xs font-bold uppercase tracking-wider'
        )
        db_conn = get_db_connection()
        if not db_conn:
            ui.label('Histórico disponível apenas com conexão ao banco.').classes('text-grey italic text-xs')
            return
        try:
            resp = db_conn.table('enfermaria').select('*').order('criado_em', desc=True).limit(150).execute()
            hist = resp.data or []
        except Exception as e:
            ui.label(f'Erro: {e}').classes('text-red text-xs')
            return

        if pelotao_filtro:
            hist = [r for r in hist if r.get('turma') == pelotao_filtro]
        if not hist:
            ui.label('Nenhum registro no histórico.').classes('text-grey italic text-xs')
            return

        # Agrupa por data
        from itertools import groupby
        hist.sort(key=lambda x: str(x.get('data') or ''), reverse=True)
        for data_ref, grupo in groupby(hist, key=lambda x: str(x.get('data') or '')):
            grupo_list = list(grupo)
            try:
                data_fmt = pd.to_datetime(data_ref).strftime('%A, %d/%m/%Y').upper()
            except Exception:
                data_fmt = str(data_ref)

            with ui.expansion(
                f'📅 {data_fmt} — {len(grupo_list)} registros',
                icon='event'
            ).classes('w-full border border-gray-800 rounded').style(
                f'background:{THEME["bg_panel"]};'
            ):
                with ui.column().classes('w-full gap-1 q-pa-sm'):
                    for r in sorted(grupo_list, key=lambda x: str(x.get('hora') or ''), reverse=True):
                        st   = r.get('status') or 'Outro'
                        cor, _, _ = STATUS_INFO.get(st, ('#888', '#111', 'help'))
                        hora = r.get('hora') or '--:--'
                        with ui.row().classes('w-full items-center justify-between q-py-xs border-b border-gray-800'):
                            with ui.row().classes('items-center gap-3'):
                                ui.label(f'🕐 {hora}h').style('color:#444; font-size:0.65rem; font-weight:bold; min-width:60px;')
                                with ui.column().classes('gap-0'):
                                    with ui.row().classes('items-center gap-1'):
                                        ui.label(str(r.get('nome_guerra') or '???')).classes('text-white text-xs font-bold uppercase')
                                        num_int = r.get('numero_interno')
                                        if num_int:
                                            ui.label(f"({num_int})").classes('text-grey-5 text-[10px]')
                                    ui.label(f"Pel. {r.get('turma') or '?'} — {r.get('motivo') or ''}").classes('text-grey text-[10px] italic')
                            with ui.row().classes('items-center gap-2'):
                                # Botão Adicionar Anotação rápida
                                num_int = r.get('numero_interno')
                                nome_g = r.get('nome_guerra')
                                turma_p = r.get('turma')
                                if num_int and nome_g:
                                    ui.button(icon='post_add', on_click=lambda num_int=num_int, nome_g=nome_g, turma_p=turma_p: _abrir_anotacao_saude_dialog(num_int, nome_g, turma_p, alunos_df)).props('unelevated dense round').style(
                                        'background:#2a2a2a; color:#fff; font-size:0.6rem; width:22px; height:22px;'
                                    )
                                ui.label(str(st).upper()).style(
                                    f'color:{cor}; font-size:0.6rem; font-weight:bold; '
                                    f'border:1px solid {cor}; padding:1px 6px; border-radius:3px;'
                                )
