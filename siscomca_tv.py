"""
MODO TV TÁTICO — SisCOMCA
Painel de Altíssima Visibilidade para Projeção em Monitor/TV de 60"
Otimizado para leitura a 5 metros de distância (fontes massivas, contraste extremo)
"""

from nicegui import ui, app
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import theme
from database import get_db_connection, load_data, get_bot_db_connection
from services import data_service

THEME = theme.colors

STATUS_INFO = {
    'Internado':      ('#ff1744', 'rgba(255, 23, 68, 0.15)', 'local_hospital'),
    'Em Observação':  ('#ff9100', 'rgba(255, 145, 0, 0.15)', 'visibility'),
    'Encaminhado para enfermaria': ('#ff9100', 'rgba(255, 145, 0, 0.15)', 'visibility'),
    'baixado':        ('#ff1744', 'rgba(255, 23, 68, 0.15)', 'local_hospital'),
    'Hospital':       ('#d500f9', 'rgba(213, 0, 249, 0.15)', 'emergency'),
    'Dispensado':     ('#00b0ff', 'rgba(0, 176, 255, 0.15)', 'medical_services'),
    'Licença':        ('#00e5ff', 'rgba(0, 229, 255, 0.15)', 'beach_access'),
    'Alta':           ('#00e676', 'rgba(0, 230, 118, 0.15)', 'check_circle'),
}

# Estado persistente da sessão da TV para notificações de mudança de status
# Guarda {numero_interno: status_anterior}
SESSION_STATE = {
    'last_health_statuses': {},
    'first_run': True
}

# CSS para o marquee vertical contínuo de indisponibilidades, saúde e atividades
MARQUEE_CSS = """
<style>
@keyframes marquee-vertical {
    0%, 10% { transform: translateY(0); }
    90%, 100% { transform: translateY(-50%); }
}
@keyframes ticker-scroll {
    0% { transform: translateX(0); }
    100% { transform: translateX(-100%); }
}
.health-marquee-container {
    display: flex;
    flex-direction: column;
    animation: marquee-vertical 30s ease-in-out infinite alternate;
}
.health-marquee-container:hover {
    animation-play-state: paused;
}
.notes-marquee-container {
    display: flex;
    flex-direction: column;
    animation: marquee-vertical 45s ease-in-out infinite alternate;
}
.notes-marquee-container:hover {
    animation-play-state: paused;
}
.activities-marquee-container {
    display: flex;
    flex-direction: column;
    animation: marquee-vertical 300s ease-in-out infinite alternate;
}
.activities-marquee-container:hover {
    animation-play-state: paused;
}
.marquee-wrapper {
    overflow: hidden;
    position: relative;
    flex: 1;
    min-height: 0;
}
/* Ticker horizontal para anotacoes */
.ticker-wrapper {
    overflow: hidden;
    white-space: nowrap;
    width: 100%;
    display: flex;
}
.ticker-content {
    display: inline-block;
    animation: ticker-scroll 45s linear infinite;
    white-space: nowrap;
    padding-right: 120px;
}
.ticker-content:hover {
    animation-play-state: paused;
}
/* KPI responsivo */
.kpi-value {
    font-weight: 900;
    font-family: monospace;
    line-height: 1;
    font-size: clamp(1.8rem, 3.2vw, 3.6rem);
}
.kpi-label {
    font-weight: bold;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-size: clamp(0.55rem, 0.8vw, 0.85rem);
    color: #666;
}
/* Layout flex auto-adjust */
.tv-main-row {
    display: flex;
    flex-direction: row;
    flex: 1;
    min-height: 0;
    gap: 8px;
    width: 100%;
}
.tv-left-col {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    gap: 8px;
    height: 100%;
}
.tv-center-col {
    display: flex;
    flex-direction: column;
    flex: 3;
    min-width: 0;
    gap: 8px;
    height: 100%;
}
.tv-right-col {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    gap: 8px;
    height: 100%;
}
.tv-panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
}
/* Card Flip 3D Styles */
@keyframes card-auto-flip {
    0%, 40% { transform: rotateY(0deg); }
    45%, 90% { transform: rotateY(180deg); }
    95%, 100% { transform: rotateY(360deg); }
}
.flip-card-inner {
    position: relative;
    width: 100%;
    height: 100%;
    text-align: center;
    transition: transform 1s;
    transform-style: preserve-3d;
    animation: card-auto-flip 15s infinite;
}
.flip-card-front, .flip-card-back {
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
    -webkit-backface-visibility: hidden;
    backface-visibility: hidden;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 8px;
}
.flip-card-back {
    transform: rotateY(180deg);
}
.tv-main-container {
    background: #000;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
@media (max-width: 1024px), (orientation: portrait) {
    .tv-main-container {
        height: auto !important;
        overflow: auto !important;
    }
    .tv-main-row {
        flex-direction: column !important;
        height: auto !important;
        overflow-y: auto !important;
    }
    .tv-left-col, .tv-center-col, .tv-right-col {
        width: 100% !important;
        height: auto !important;
        min-height: 400px !important;
    }
    body {
        overflow: auto !important;
    }
}
</style>
"""

def get_tv_polling_interval() -> float:
    """Retorna o tempo de polling configurado no banco (default: 300 segundos = 5min)."""
    db_conn = get_db_connection()
    if db_conn:
        try:
            res = db_conn.table('Config').select('*').eq('chave', 'tempo_polling_tv').execute()
            if res.data:
                return float(res.data[0]['valor'])
        except Exception as e:
            print(f"[TV] Erro ao carregar tempo_polling_tv do banco: {e}")
    return 300.0


def sanitize_text(val) -> str:
    if val is None:
        return ""
    s = str(val)
    # Corrige problemas comuns de codificação/caracteres corrompidos do banco
    s = s.replace("Observao", "Observação")
    s = s.replace("Observa\ufffdo", "Observação")
    s = s.replace("Em Observao", "Em Observação")
    s = s.replace("Observaï¿½o", "Em Observação")
    return s.strip()


def _carregar_dados_tv(prog_date: datetime = None, active_year: str = '2026'):
    """Carrega dados consolidados do Supabase para o Modo TV com fallbacks offline robustos."""
    db_conn = get_bot_db_connection()
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    if prog_date is None:
        prog_date = datetime.now()
    prog_date_str = prog_date.strftime('%Y-%m-%d')
    is_offline = not db_conn

    # 0. Configurações gerais
    from services import data_service
    cabecalho_title = str(data_service.get_config_value('cabecalho_tv_title', 'SISTEMA C2') or 'SISTEMA C2').upper()

    # Dicionário final de dados
    dados = {
        'total_alunos': 0,
        'presentes_hoje': 0,
        'ausentes_hoje': 0,
        'presentes_pct': 0.0,
        'licencas_ativas': [],
        'saude_ativos': [],
        'inspetor_dia': {'nome': 'NÃO ESCALADO', 'cargo_title': 'INSPETOR DO DIA', 'photo_url': 'https://cdn.quasar.dev/img/boy-avatar.png'},
        'outros_escalados': [],
        'anotacoes_dia': [],
        'avisos_letreiro': [],
        'atividades_dia': [],
        'cabecalho_tv_title': cabecalho_title,
        'pernoite_count': 0,
        'atletas_count': 0,
        'fora_sede_count': 0,
        'is_offline': is_offline
    }

    # 1. Alunos e Efetivo Geral
    alunos_df = pd.DataFrame()
    if db_conn:
        try:
            res_al = db_conn.table('Alunos').select('id,numero_interno,nome_guerra,pelotao,especialidade').eq('ano_letivo', active_year).execute()
            alunos_df = pd.DataFrame(res_al.data) if res_al.data else pd.DataFrame()
        except Exception as e:
            print(f"[TV] Erro Alunos: {e}")
    
    if is_offline or (not db_conn and alunos_df.empty):
        # Fallback Mock
        alunos_data = [
            {'id': 1, 'numero_interno': 'M-1-101', 'nome_guerra': 'GUILHERME', 'pelotao': 'MIKE-1', 'especialidade': 'AD', 'status': 'Ativo'},
            {'id': 2, 'numero_interno': 'M-1-102', 'nome_guerra': 'SILVA', 'pelotao': 'MIKE-1', 'especialidade': 'AD', 'status': 'Ativo'},
            {'id': 3, 'numero_interno': 'M-2-207', 'nome_guerra': 'MARTINS', 'pelotao': 'MIKE-2', 'especialidade': 'EL', 'status': 'Ativo'},
            {'id': 4, 'numero_interno': 'M-2-208', 'nome_guerra': 'ALBUQUERQUE', 'pelotao': 'MIKE-2', 'especialidade': 'EL', 'status': 'Ativo'},
            {'id': 5, 'numero_interno': 'M-3-301', 'nome_guerra': 'GOMES', 'pelotao': 'MIKE-3', 'especialidade': 'AR', 'status': 'Ativo'}
        ]
        alunos_df = pd.DataFrame(alunos_data)

    if not alunos_df.empty:
        # Filtrar alunos com pelotão "BAIXA"
        if 'pelotao' in alunos_df.columns:
            alunos_df = alunos_df[alunos_df['pelotao'].str.strip().str.upper() != 'BAIXA']
        # Filtrar alunos com status "BAIXA" ou "NÃO SE APRESENTOU"
        if 'status' in alunos_df.columns:
            mask = alunos_df['status'].astype(str).str.strip().str.upper().isin(['BAIXA', 'NÃO SE APRESENTOU', 'NAO SE APRESENTOU'])
            alunos_df = alunos_df[~mask]

    dados['total_alunos'] = len(alunos_df)

    # Contagens de turmas e especialidades
    turmas_counts = []
    especialidades_counts = []
    if not alunos_df.empty:
        if 'pelotao' in alunos_df.columns:
            pel_s = alunos_df.groupby('pelotao').size()
            for pel, count in pel_s.items():
                if pel:
                    turmas_counts.append({'turma': str(pel).upper(), 'total': int(count)})
            turmas_counts.sort(key=lambda x: x['turma'])
            
        if 'especialidade' in alunos_df.columns:
            esp_s = alunos_df.groupby('especialidade').size()
            for esp, count in esp_s.items():
                esp_name = str(esp).upper().strip() if esp else 'SEM ESP.'
                if esp_name in ('', 'NONE', 'NAN'):
                    esp_name = 'SEM ESP.'
                especialidades_counts.append({'especialidade': esp_name, 'total': int(count)})
            especialidades_counts.sort(key=lambda x: x['especialidade'])

    dados['turmas_counts'] = turmas_counts
    dados['especialidades_counts'] = especialidades_counts

    # 2. Presença (Prontidão)
    presenca_df = pd.DataFrame()
    if db_conn:
        try:
            res_pr = db_conn.table('presenca_ausencia').select('*').eq('data', hoje_str).execute()
            presenca_df = pd.DataFrame(res_pr.data) if res_pr.data else pd.DataFrame()
        except Exception as e:
            print(f"[TV] Erro Presença: {e}")

    if is_offline or (not db_conn and presenca_df.empty):
        presenca_data = [
            {'numero_interno': 'M-1-101', 'presente': True},
            {'numero_interno': 'M-1-102', 'presente': True},
            {'numero_interno': 'M-2-207', 'presente': False},
            {'numero_interno': 'M-2-208', 'presente': True},
            {'numero_interno': 'M-3-301', 'presente': True}
        ]
        presenca_df = pd.DataFrame(presenca_data)

    # Cálculo dos KPIs de Presença
    if not presenca_df.empty and not alunos_df.empty:
        valid_nis = set(alunos_df['numero_interno'].astype(str).str.upper())
        presenca_df = presenca_df[presenca_df['numero_interno'].astype(str).str.upper().isin(valid_nis)]

    presentes_hoje = len(presenca_df[presenca_df['presente'] == True]) if not presenca_df.empty else 0
    ausentes_hoje = len(presenca_df[presenca_df['presente'] == False]) if not presenca_df.empty else 0
    dados['presentes_hoje'] = presentes_hoje
    dados['ausentes_hoje'] = ausentes_hoje
    if dados['total_alunos'] > 0:
        dados['presentes_pct'] = (presentes_hoje / dados['total_alunos']) * 100

    # 3. Enfermaria / Dispensas / Licenças
    enfermaria_df = pd.DataFrame()
    if db_conn:
        try:
            res_enf = db_conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
            enfermaria_df = pd.DataFrame(res_enf.data) if res_enf.data else pd.DataFrame()
            if not enfermaria_df.empty and not alunos_df.empty:
                valid_nis = set(alunos_df['numero_interno'].astype(str).str.upper())
                enfermaria_df = enfermaria_df[enfermaria_df['numero_interno'].astype(str).str.upper().isin(valid_nis)]
        except Exception as e:
            print(f"[TV] Erro Enfermaria: {e}")

    if is_offline or (not db_conn and enfermaria_df.empty):
        enfermaria_data = [
            {'numero_interno': 'M-2-207', 'nome_guerra': 'MARTINS', 'turma': 'MIKE-2', 'categoria': 'licenca', 'motivo': 'Núpcias', 'data_ini': '2026-05-28', 'data_fim': '2026-06-03', 'status': 'Licenciado'},
            {'numero_interno': 'M-2-208', 'nome_guerra': 'ALBUQUERQUE', 'turma': 'MIKE-2', 'categoria': 'enfermaria', 'motivo': 'Febre e cefaleia', 'detalhe': 'Leito A-312', 'status': 'Baixado'},
            {'numero_interno': 'M-1-102', 'nome_guerra': 'SILVA', 'turma': 'MIKE-1', 'categoria': 'dispensa', 'motivo': 'Fisioterapia joelho', 'data_ini': '2026-05-29', 'data_fim': '2026-06-05', 'status': 'Dispensado'}
        ]
        enfermaria_df = pd.DataFrame(enfermaria_data)

    # Filtragem e separação inteligente
    for _, row in enfermaria_df.iterrows():
        cat = sanitize_text(row.get('categoria') or 'enfermaria')
        status = sanitize_text(row.get('status') or 'Ativo')
        if status == 'Em Observação':
            status = 'Encaminhado para enfermaria'
        
        # Filtro de validade de datas se houver data_ini/data_fim
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

        item = {
            'id': row.get('id') or 0,
            'criado_em': row.get('criado_em') or '',
            'ni': sanitize_text(row.get('numero_interno', '')),
            'nome': sanitize_text(row.get('nome_guerra', '')).upper(),
            'turma': sanitize_text(row.get('turma', row.get('pelotao', ''))).upper(),
            'motivo': sanitize_text(row.get('motivo') or 'Sem motivo informado'),
            'detalhe': sanitize_text(row.get('detalhe') or ''),
            'data_ini': row.get('data_ini'),
            'data_fim': row.get('data_fim'),
            'categoria': cat,
            'status': status
        }

        if cat == 'licenca' or status == 'Licença':
            item['categoria'] = 'licenca'
            dados['licencas_ativas'].append(item)
        else:
            if status == 'Hospital':
                item['categoria'] = 'hospital'
            elif status in ['Internado', 'Em Observação', 'Encaminhado para enfermaria', 'baixado']:
                item['categoria'] = 'enfermaria'
            elif status == 'Dispensado':
                item['categoria'] = 'dispensa'
            dados['saude_ativos'].append(item)

    # 3.1 Cruzamento com presenças marcadas como "Ausente" devido a "Licença"
    added_nis = {x['ni'] for x in dados['licencas_ativas'] + dados['saude_ativos']}
    if not presenca_df.empty:
        for _, row in presenca_df.iterrows():
            if row.get('presente') == False:
                motivo = str(row.get('motivo_ausencia') or '')
                # Verifica se o motivo contém alguma variação de "Licença" (mesmo corrompida como 'Licen')
                if any(k in motivo.lower() for k in ['licen', 'licença', 'licenca', 'licena']):
                    ni = sanitize_text(row.get('numero_interno', ''))
                    if ni and ni not in added_nis:
                        item = {
                            'ni': ni,
                            'nome': sanitize_text(row.get('nome_guerra', '')).upper(),
                            'turma': sanitize_text(row.get('turma', row.get('pelotao', ''))).upper(),
                            'motivo': sanitize_text(row.get('motivo_ausencia') or 'Licença'),
                            'detalhe': 'Ausência por Licença',
                            'data_ini': row.get('data'),
                            'data_fim': row.get('data'),
                            'categoria': 'licenca',
                            'status': 'Licenciado'
                        }
                        dados['licencas_ativas'].append(item)
                        added_nis.add(ni)

    # Recalcula ausentes_hoje de forma a computar apenas os faltosos reais:
    # Qualquer aluno no efetivo que NÃO esteja presente e NÃO esteja de licença, baixado ou hospitalizado.
    presentes_nis = set()
    if not presenca_df.empty and 'numero_interno' in presenca_df.columns:
        presentes_nis = set(presenca_df[presenca_df['presente'] == True]['numero_interno'].astype(str).str.upper())
        
    justificados_nis = set()
    for item in dados['licencas_ativas'] + dados['saude_ativos']:
        if item.get('categoria') != 'dispensa':
            justificados_nis.add(str(item.get('ni', '')).upper())
            
    if not alunos_df.empty and 'numero_interno' in alunos_df.columns:
        todos_nis = set(alunos_df['numero_interno'].astype(str).str.upper())
        ausentes_reais_nis = todos_nis - presentes_nis - justificados_nis
        dados['ausentes_hoje'] = len(ausentes_reais_nis)
    else:
        dados['ausentes_hoje'] = 0

    # 4. Escala de Serviço
    escala_df = pd.DataFrame()
    if db_conn:
        try:
            res_es = db_conn.table('escala_diaria').select('*').eq('data', hoje_str).execute()
            escala_df = pd.DataFrame(res_es.data) if res_es.data else pd.DataFrame()
        except Exception as e:
            print(f"[TV] Erro Escala: {e}")

    # Carrega cargos configurados
    from database import get_cargos_escala
    cargos_config = get_cargos_escala()

    # Preenche dicionário com os valores reais salvos
    escala_map = {}
    if not escala_df.empty:
        for _, row in escala_df.iterrows():
            cargo_name = str(row['cargo']).upper() if row['cargo'] else ""
            if cargo_name:
                escala_map[cargo_name] = row['nome'] if row['nome'] else ""

    # 4.1 Inspetor (Destaque Principal)
    inspetor_nome = ''
    inspetor_cargo_exibido = 'INSPETOR DO DIA'
    
    # 1. Tenta achar o primeiro que contenha 'INSPETOR' e esteja preenchido
    for cargo_key, nome_val in escala_map.items():
        if 'INSPETOR' in cargo_key:
            n_clean = nome_val.strip().upper() if nome_val else ''
            if n_clean and n_clean not in {"NÃO ESCALADO", "AGUARDANDO", "N/A", "-", "NÃO DEFINIDO"}:
                inspetor_nome = nome_val
                inspetor_cargo_exibido = cargo_key
                break
                
    # 2. Se nenhum estava preenchido, pega o primeiro que contiver 'INSPETOR'
    if not inspetor_nome:
        for cargo_key, nome_val in escala_map.items():
            if 'INSPETOR' in cargo_key:
                inspetor_nome = nome_val
                inspetor_cargo_exibido = cargo_key
                break

    if not inspetor_nome:
        inspetor_nome = 'Cap. Calaça' if is_offline else 'NÃO ESCALADO'

    dados['inspetor_dia'] = {
        'nome': str(inspetor_nome or '').upper(),
        'cargo_title': str(inspetor_cargo_exibido or '').upper(),
        'photo_url': 'https://cdn.quasar.dev/img/boy-avatar.png'
    }

    # Busca foto do Inspetor no Users se estiver online
    if db_conn and inspetor_nome and inspetor_nome != 'NÃO ESCALADO':
        try:
            res_us = db_conn.table('Users').select('*').ilike('nome', f"%{inspetor_nome}%").execute()
            if res_us.data:
                dados['inspetor_dia']['photo_url'] = res_us.data[0].get('url_foto') or 'https://cdn.quasar.dev/img/boy-avatar.png'
        except Exception:
            pass

    # 4.2 OSCA e AJOSCA (Menor destaque)
    osca_val = escala_map.get('OSCA') or ('Cap. Calaça' if is_offline else 'NÃO ESCALADO')
    ajosca_val = escala_map.get('AJOSCA') or ('Ten. Santos' if is_offline else 'NÃO ESCALADO')
    dados['osca_servico'] = str(osca_val).upper()
    dados['ajosca_servico'] = str(ajosca_val).upper()

    # 4.3 Outros Escalados (excluindo o Inspetor selecionado, OSCA e AJOSCA)
    excluir_cargos = {'OSCA', 'AJOSCA', str(inspetor_cargo_exibido).upper()}
    dados['outros_escalados'] = []
    for cargo in cargos_config:
        cargo_upper = cargo.upper()
        if cargo_upper in excluir_cargos:
            continue
        nome_cargo = escala_map.get(cargo_upper) or escala_map.get(cargo) or ('Maj. Lima' if is_offline and cargo_upper == 'SUPERVISOR' else 'NÃO ESCALADO')
        dados['outros_escalados'].append({
            'cargo': str(cargo).upper(),
            'nome': str(nome_cargo).upper()
        })

    # 5. Letreiro Ticker (Avisos / Ordens Diárias)
    avisos_list = []
    if db_conn:
        try:
            res_od = db_conn.table('Ordens_Diarias').select('*').eq('data', hoje_str).execute()
            if res_od.data:
                for o in res_od.data:
                    texto = o['texto']
                    autor = o.get('autor_id')
                    if autor:
                        texto += f' <span style="font-size: 0.85rem; font-weight: normal; opacity: 0.75; margin-left: 4px;">({autor})</span>'
                    avisos_list.append(texto)
        except Exception as e:
            print(f"[TV] Erro Ordens Diárias: {e}")
    else:
        # Fallback local do app
        mock_list = getattr(app, '_mock_ordens_diarias', [])
        for o in mock_list:
            if o['data'] == hoje_str:
                texto = o['texto']
                autor = o.get('autor_id')
                if autor:
                    texto += f' <span style="font-size: 0.85rem; font-weight: normal; opacity: 0.75; margin-left: 4px;">({autor})</span>'
                avisos_list.append(texto)

    if not avisos_list:
        if is_offline:
            avisos_list = [
                '1. Formatura Geral às 07:30 Uniforme 3º A.',
                '2. Parada Diária com presença obrigatória de todos os pelotões.'
            ]
        else:
            avisos_list = ['NÃO HÁ AVISOS CADASTRADOS PARA HOJE.']
    dados['avisos_letreiro'] = avisos_list

    # 6. Anotações do Dia (Ações de Alunos hoje - Lançadas ou Pendentes com Cores/Pontos)
    anotacoes_dia_list = []
    acoes_list = []
    tipos_map = {}
    if db_conn:
        try:
            # Carrega pontuação para identificar se a anotação é positiva, negativa ou neutra
            res_ta = db_conn.table('Tipos_Acao').select('id, pontuacao').execute()
            if res_ta.data:
                for ta in res_ta.data:
                    tipos_map[str(ta['id'])] = float(ta.get('pontuacao', 0.0) or 0.0)
        except Exception as e:
            print(f"[TV] Erro Tipos_Acao: {e}")

        try:
            t_start = f"{hoje_str} 00:00:00"
            t_end = f"{hoje_str} 23:59:59"
            res_ac = db_conn.table('Acoes').select('*').gte('data', t_start).lte('data', t_end).in_('status', ['Lançado', 'Pendente']).execute()
            acoes_list = res_ac.data if res_ac.data else []
        except Exception as e:
            print(f"[TV] Erro Acoes: {e}")
    
    if acoes_list and not alunos_df.empty:
        align_map = {}
        for _, row in alunos_df.iterrows():
            aid = str(row['id'])
            align_map[aid] = {
                'ni': str(row.get('numero_interno', '')).upper(),
                'nome': str(row.get('nome_guerra', 'Militar')).upper(),
                'pelotao': str(row.get('pelotao', '')).upper()
            }
            
        for ac in acoes_list:
            aid = str(ac.get('aluno_id'))
            aluno = align_map.get(aid)
            if not aluno:
                continue
            tipo = str(ac.get('tipo', 'Anotação')).upper()
            desc = ac.get('descricao', 'Sem descrição')
            tipo_acao_id = str(ac.get('tipo_acao_id', ''))
            pts = tipos_map.get(tipo_acao_id, 0.0)
            
            anotacoes_dia_list.append({
                'ni': str(aluno['ni']).upper() if aluno and aluno.get('ni') else '',
                'nome': str(aluno['nome']).upper() if aluno else 'MILITAR',
                'pelotao': str(aluno['pelotao']).upper() if aluno and aluno.get('pelotao') else '',
                'tipo': tipo,
                'motivo': desc,
                'status': ac.get('status', 'Lançado'),
                'pts': pts
            })

    if not anotacoes_dia_list:
        if is_offline:
            anotacoes_dia_list = [
                {
                    'ni': 'M-1-102',
                    'nome': 'SILVA',
                    'pelotao': 'MIKE-1',
                    'tipo': 'ANOTAÇÃO',
                    'motivo': 'Destacou-se na instrução prática de hoje.',
                    'status': 'Lançado',
                    'pts': 0.5
                },
                {
                    'ni': 'M-2-207',
                    'nome': 'MARTINS',
                    'pelotao': 'MIKE-2',
                    'tipo': 'OBSERVAÇÃO',
                    'motivo': 'Dispensado das atividades físicas por recomendação médica.',
                    'status': 'Pendente',
                    'pts': -0.3
                }
            ]
        else:
            anotacoes_dia_list = [{
                'ni': '',
                'nome': 'NENHUM REGISTRO',
                'pelotao': '',
                'tipo': 'INFO',
                'motivo': 'NÃO HÁ ANOTAÇÕES DE ALUNOS REGISTRADAS HOJE.',
                'status': 'Lançado',
                'pts': 0.0
            }]
    dados['anotacoes_dia'] = anotacoes_dia_list

    # 7. Programação / Atividades do Dia
    prog_list = []
    if db_conn:
        try:
            # Filtra por data de hoje
            res_pr = db_conn.table('Programacao').select('*').gte('data', f"{hoje_str} 00:00:00").lte('data', f"{hoje_str} 23:59:59").execute()
            prog_list = res_pr.data if res_pr.data else []
        except Exception as e:
            print(f"[TV] Erro Programacao: {e}")

    if not prog_list:
        if is_offline:
            prog_list = [
                {'horario': '08:00', 'descricao': 'Instrução Militar Básica', 'local': 'Pátio de Formaturas'},
                {'horario': '10:30', 'descricao': 'Palestra: Liderança Naval', 'local': 'Auditório Principal'},
                {'horario': '14:00', 'descricao': 'Educação Física Supervisionada', 'local': 'Campo de Esportes'}
            ]
        else:
            prog_list = []
    dados['atividades_dia'] = prog_list

    if db_conn:
        try:
            res_pn = db_conn.table('pernoite').select('*').eq('data', hoje_str).eq('presente', True).execute()
            pn_data = res_pn.data if res_pn.data else []
            if pn_data and not alunos_df.empty:
                valid_nis = set(alunos_df['numero_interno'].astype(str).str.upper())
                pn_data = [row for row in pn_data if str(row.get('numero_interno', '')).upper() in valid_nis]
            dados['pernoite_count'] = len(pn_data)
        except Exception as e:
            print(f"[TV] Erro Pernoite: {e}")

    # 8.1 Calcular alunos pendentes de chamada (sem registro de presença/ausência hoje)
    alunos_todos_nis = set(alunos_df['numero_interno'].astype(str).str.upper()) if not alunos_df.empty else set()
    respondidos_nis = set(presenca_df['numero_interno'].astype(str).str.upper()) if not presenca_df.empty else set()
    pendentes_nis = alunos_todos_nis - respondidos_nis
    dados['pendentes_count'] = len(pendentes_nis)
    
    pendentes_mikes = []
    if not alunos_df.empty and pendentes_nis:
        pendentes_df = alunos_df[alunos_df['numero_interno'].astype(str).str.upper().isin(pendentes_nis)]
        if 'pelotao' in pendentes_df.columns:
            mikes = pendentes_df['pelotao'].dropna().astype(str).str.upper().str.strip().unique()
            pendentes_mikes = sorted([m for m in mikes if m])
    dados['pendentes_mikes'] = pendentes_mikes

    atletas_count = 0
    if db_conn:
        try:
            res_at = db_conn.table('Acoes').select('aluno_id,tipo,tipo_acao_id').in_('status', ['Lançado', 'Pendente']).execute()
            if res_at.data:
                atletas_ids = set()
                valid_aluno_ids = set(alunos_df['id'].astype(str)) if not alunos_df.empty else set()
                for ac in res_at.data:
                    aluno_id_str = str(ac.get('aluno_id', ''))
                    if aluno_id_str in valid_aluno_ids:
                        tipo_str = str(ac.get('tipo', '')).upper()
                        if 'ATLETA' in tipo_str or str(ac.get('tipo_acao_id')) == '52':
                            atletas_ids.add(ac.get('aluno_id'))
                atletas_count = len(atletas_ids)
        except Exception as e:
            print(f"[TV] Erro Atletas: {e}")
    dados['atletas_count'] = atletas_count

    fora_sede_count = 0
    if db_conn:
        try:
            hoje = datetime.now()
            # Segunda-feira da semana corrente
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            t_start = inicio_semana.strftime('%Y-%m-%d 00:00:00')
            
            res_fs = db_conn.table('Acoes').select('aluno_id,tipo,descricao').gte('data', t_start).in_('status', ['Lançado', 'Pendente']).execute()
            if res_fs.data:
                fora_sede_ids = set()
                valid_aluno_ids = set(alunos_df['id'].astype(str)) if not alunos_df.empty else set()
                for ac in res_fs.data:
                    aluno_id_str = str(ac.get('aluno_id', ''))
                    if aluno_id_str in valid_aluno_ids:
                        tipo_str = str(ac.get('tipo', '')).upper()
                        desc_str = str(ac.get('descricao', '')).upper()
                        if 'FORA DE SEDE' in tipo_str or 'FORA DE SEDE' in desc_str or 'PAPELETA' in desc_str:
                            fora_sede_ids.add(ac.get('aluno_id'))
                fora_sede_count = len(fora_sede_ids)
        except Exception as e:
            print(f"[TV] Erro Fora de Sede: {e}")
    dados['fora_sede_count'] = fora_sede_count

    # 8. Estatísticas de Anotações (Semana e Geral)
    stats_anotacoes = {
        'pos_semana': 0,
        'neg_semana': 0,
        'pos_geral': 0,
        'neg_geral': 0,
        'primeira_anotacao': None
    }
    
    if db_conn:
        try:
            # Busca todas as ações para calcular estatísticas
            res_all_ac = db_conn.table('Acoes').select('*').in_('status', ['Lançado', 'Pendente']).execute()
            all_acoes = res_all_ac.data if res_all_ac.data else []
            
            # Filtra por ano letivo/data
            hoje_dt = datetime.now()
            inicio_semana_dt = hoje_dt - timedelta(days=hoje_dt.weekday())
            t_start_semana = inicio_semana_dt.strftime('%Y-%m-%d 00:00:00')
            
            # Map para turmas dos alunos
            aluno_turma_map = {}
            if not alunos_df.empty:
                for _, row in alunos_df.iterrows():
                    aluno_turma_map[str(row['id'])] = {
                        'nome': str(row.get('nome_guerra', '')).upper(),
                        'numero_interno': str(row.get('numero_interno', '')),
                        'pelotao': str(row.get('pelotao', '')).upper()
                    }
            
            primeira_anot = None
            
            for ac in all_acoes:
                aluno_id = str(ac.get('aluno_id', ''))
                if aluno_id not in aluno_turma_map:
                    continue
                tipo_acao_id = str(ac.get('tipo_acao_id', ''))
                pts = tipos_map.get(tipo_acao_id, 0.0)
                ac_date = ac.get('data', '')
                
                is_positive = pts > 0
                is_negative = pts < 0
                
                # Geral
                if is_positive:
                    stats_anotacoes['pos_geral'] += 1
                elif is_negative:
                    stats_anotacoes['neg_geral'] += 1
                
                # Semana
                ac_date_only = ac_date.split(' ')[0] if ' ' in ac_date else ac_date
                semana_date_only = t_start_semana.split(' ')[0]
                if ac_date_only >= semana_date_only:
                    if is_positive:
                        stats_anotacoes['pos_semana'] += 1
                    elif is_negative:
                        stats_anotacoes['neg_semana'] += 1
                
                # Primeira anotação da turma (mais antiga)
                if not primeira_anot:
                    primeira_anot = ac
                else:
                    try:
                        if ac_date < primeira_anot.get('data', ''):
                            primeira_anot = ac
                        elif ac_date == primeira_anot.get('data', '') and int(ac.get('id', 0)) < int(primeira_anot.get('id', 0)):
                            primeira_anot = ac
                    except Exception:
                        pass
            
            if primeira_anot:
                al_info = aluno_turma_map.get(str(primeira_anot.get('aluno_id')))
                stats_anotacoes['primeira_anotacao'] = {
                    'nome': al_info['nome'] if al_info else 'MILITAR',
                    'ni': al_info['numero_interno'] if al_info else '',
                    'pelotao': al_info['pelotao'] if al_info else '',
                    'tipo': str(primeira_anot.get('tipo', 'Anotação')).upper(),
                    'descricao': primeira_anot.get('descricao', 'Sem descrição'),
                    'data': pd.to_datetime(primeira_anot.get('data')).strftime('%d/%m/%Y') if primeira_anot.get('data') else ''
                }
        except Exception as ex_stats:
            print(f"[TV] Erro ao carregar estatísticas de ações: {ex_stats}")
            
    # Fallback se estiver vazio para exibição rica na TV (apenas se offline)
    if is_offline and stats_anotacoes['pos_geral'] == 0 and stats_anotacoes['neg_geral'] == 0:
        stats_anotacoes.update({
            'pos_semana': 12,
            'neg_semana': 3,
            'pos_geral': 145,
            'neg_geral': 42,
            'primeira_anotacao': {
                'nome': 'SILVA',
                'ni': '101',
                'pelotao': 'ALFA',
                'tipo': 'DESTAQUE EM INSTRUÇÃO',
                'descricao': 'Demonstrou espírito de corpo e liderança excepcionais no treinamento de hoje.',
                'data': '01/06/2026'
            }
        })
        
    dados['stats_anotacoes'] = stats_anotacoes

    # 9. Polling interval configurado
    dados['polling_interval'] = get_tv_polling_interval()
    return dados


def render_page():
    # Configuração local de som e voz da sessão da TV
    audio_config = {
        'sound': True,
        'voice': True
    }

    # Estiliza o body da página para visualização em TV
    ui.query('body').style(
        'background-color:#000; overflow:hidden; margin:0; padding:0; '
        'font-family: "Share Tech Mono", "Courier New", monospace;'
    )
    ui.add_head_html(
        '<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">'
    )
    ui.add_head_html(MARQUEE_CSS)
    ui.add_head_html(
        """
        <script>
            window.globalAudioContext = null;
            function initAudioContext() {
                // Remove banner de som se existir
                const banner = document.getElementById('sound-banner-alert');
                if (banner) {
                    banner.style.display = 'none';
                }

                if (!window.globalAudioContext) {
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    if (AudioContext) {
                        window.globalAudioContext = new AudioContext();
                        console.log("[AUDIO] AudioContext initialized");
                    }
                }
                if (window.globalAudioContext) {
                    if (window.globalAudioContext.state === 'suspended') {
                        window.globalAudioContext.resume().then(() => {
                            console.log("[AUDIO] AudioContext resumed");
                        });
                    }
                    const buffer = window.globalAudioContext.createBuffer(1, 1, 22050);
                    const source = window.globalAudioContext.createBufferSource();
                    source.buffer = buffer;
                    source.connect(window.globalAudioContext.destination);
                    source.start(0);
                }
                
                // Desbloqueia Síntese de Voz (SpeechSynthesis)
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    let u = new SpeechSynthesisUtterance('');
                    window.speechSynthesis.speak(u);
                    console.log("[AUDIO] SpeechSynthesis unlocked");
                }
                
                // Remove listeners para rodar apenas uma vez
                window.removeEventListener('click', initAudioContext);
                window.removeEventListener('touchstart', initAudioContext);
                window.removeEventListener('keydown', initAudioContext);
            }
            window.addEventListener('click', initAudioContext);
            window.addEventListener('touchstart', initAudioContext);
            window.addEventListener('keydown', initAudioContext);

            // Log das vozes no console para o operador verificar as disponíveis e pré-carregar
            if ('speechSynthesis' in window) {
                const logVoices = () => {
                    const voices = window.speechSynthesis.getVoices();
                    console.log("[AUDIO] Vozes disponíveis no navegador:", voices.map(v => v.name));
                };
                window.speechSynthesis.onvoiceschanged = logVoices;
                setTimeout(logVoices, 1000);
            }
        </script>
        """
    )

    def estimate_sunset_time() -> str:
        """Calcula dinamicamente uma estimativa realista do pôr do sol para a latitude de Brasília (-15.79) baseada no dia do ano."""
        import math
        try:
            # Pega a configuração do banco se existir
            from services import data_service
            cfg_val = data_service.get_config_value('cabecalho_tv_sunset_time', '')
            if cfg_val and len(cfg_val.strip()) == 5 and ":" in cfg_val:
                return cfg_val.strip()
        except Exception:
            pass

        try:
            from datetime import datetime
            now = datetime.now()
            day_of_year = now.timetuple().tm_yday
            angle = 2 * math.pi * (day_of_year - 355) / 365
            minutes = 1095 + 27 * math.cos(angle)
            hour = int(minutes // 60)
            minute = int(minutes % 60)
            return f"{hour:02d}:{minute:02d}"
        except Exception:
            return "17:48"

    def get_pt_date_string(dt) -> str:
        """Retorna a data formatada em português de forma manual e imune a locales do OS."""
        dias_semana = {
            0: 'Segunda-feira',
            1: 'Terça-feira',
            2: 'Quarta-feira',
            3: 'Quinta-feira',
            4: 'Sexta-feira',
            5: 'Sábado',
            6: 'Domingo'
        }
        meses = {
            1: 'Janeiro',
            2: 'Fevereiro',
            3: 'Março',
            4: 'Abril',
            5: 'Maio',
            6: 'Junho',
            7: 'Julho',
            8: 'Agosto',
            9: 'Setembro',
            10: 'Outubro',
            11: 'Novembro',
            12: 'Dezembro'
        }
        try:
            dia_sem = dias_semana[dt.weekday()]
            dia = dt.day
            mes = meses[dt.month]
            ano = dt.year
            return f"{dia_sem}, {dia:02d} de {mes} de {ano}".upper()
        except Exception:
            return dt.strftime('%A, %d de %B de %Y').upper()

    client = ui.context.client
    try:
        default_active_year = app.storage.user.get('ano_letivo_ativo', '2026')
    except Exception:
        default_active_year = '2026'

    # Container da Notificação Tática Flutuante
    toast_container = ui.column().classes('absolute-top w-full z-50 q-pa-md gap-2 pointer-events-none').style('top: 20px;')

    # Dialog de Alertas Táticos em Tempo Real (Definido estaticamente para máxima confiabilidade)
    with ui.dialog() as tactical_dialog:
        dialog_card = ui.card().classes('q-pa-xl items-center text-center rounded-2xl border-4').style(
            'min-width: 700px; max-width: 90%; color: #fff; font-family: monospace;'
        )
        with dialog_card:
            dialog_icon = ui.icon('campaign', size='7rem').classes('animate-bounce')
            dialog_title = ui.label('AVISO').classes('cyber-title q-mt-md').style('font-size: 2.6rem; font-weight: 900; letter-spacing: 5px; line-height: 1.2;')
            dialog_sep = ui.separator().classes('w-3/4 q-my-md').style('height: 3px;')
            dialog_msg = ui.label('').style('color: #ffffff; font-size: 2.2rem; font-weight: 900; line-height: 1.4; white-space: normal;')

    # Estado de visualização da TV (Blur/Ocultar Anotações)
    tv_state = {'blurred': False}

    # Dialog de Desbloqueio de Área (Password Input)
    with ui.dialog() as unlock_dialog, ui.card().classes('q-pa-lg items-center text-center rounded-2xl border-4').style(
        f"background: #020813; border-color: {THEME['primary']} !important; box-shadow: 0 0 30px rgba(212, 175, 55, 0.3); color: #fff; min-width: 400px; font-family: monospace;"
    ):
        ui.icon('lock', color='amber', size='4rem')
        ui.label('ÁREA PRIVADA').style(
            f"color: {THEME['primary']}; font-size: 1.5rem; font-weight: 900; letter-spacing: 3px;"
        ).classes('q-mt-sm')
        ui.label('Insira o código de desbloqueio para visualizar as Anotações do Dia:').classes('text-grey-4 text-xs q-mb-md')
        
        unlock_input = ui.input('Código de Desbloqueio', password=True).props('dark dense outlined autofocus w-full').classes('w-full font-mono text-center text-lg')
        
        async def confirm_unlock():
            code_input = unlock_input.value.strip()
            # Busca código configurado
            code_real = '1234'
            db_conn = get_db_connection()
            if db_conn:
                try:
                    res = db_conn.table('Config').select('*').eq('chave', 'codigo_desbloqueio_tv').execute()
                    if res.data:
                        code_real = res.data[0]['valor']
                except Exception as e:
                    print(f"[TV] Erro ao buscar codigo_desbloqueio_tv: {e}")
            
            if code_input == code_real:
                tv_state['blurred'] = False
                # Remove blur do card
                anotacoes_card.style(f'background: {THEME["bg_panel"]}; width: 100%; flex: 1; min-height: 0; filter: none; transition: filter 0.3s ease;')
                eye_btn.props(replace='icon=visibility')
                eye_btn.set_text('OCULTAR DADOS')
                unlock_dialog.close()
                ui.notify('Área desbloqueada com sucesso!', color='positive')
                unlock_input.value = ''
            else:
                ui.notify('Código de desbloqueio incorreto!', color='negative')
                unlock_input.value = ''
        
        unlock_input.on('keydown.enter', confirm_unlock)
        
        with ui.row().classes('w-full justify-center gap-2 q-mt-md'):
            ui.button('CANCELAR', on_click=unlock_dialog.close).props('outline color=grey dense')
            ui.button('CONFIRMAR', on_click=confirm_unlock).props('unelevated color=amber text-color=black dense').classes('font-bold')

    def toggle_blur():
        if tv_state['blurred']:
            unlock_dialog.open()
        else:
            tv_state['blurred'] = True
            anotacoes_card.style(f'background: {THEME["bg_panel"]}; width: 100%; flex: 1; min-height: 0; filter: blur(15px); pointer-events: none; transition: filter 0.3s ease;')
            eye_btn.props(replace='icon=visibility_off')
            eye_btn.set_text('REVELAR DADOS')
            ui.notify('Anotações ocultadas com sucesso!', color='warning')

    # Dialog de Desbloqueio de Saída do Modo TV
    with ui.dialog() as exit_lock_dialog, ui.card().classes('q-pa-lg items-center text-center rounded-2xl border-4').style(
        f"background: #020813; border-color: {THEME['primary']} !important; box-shadow: 0 0 30px rgba(212, 175, 55, 0.3); color: #fff; min-width: 400px; font-family: monospace;"
    ):
        ui.icon('lock_open', color='red-5', size='4rem')
        ui.label('SAIR DO MODO TV').style(
            f"color: {THEME['primary']}; font-size: 1.5rem; font-weight: 900; letter-spacing: 3px;"
        ).classes('q-mt-sm')
        ui.label('Digite a senha do usuário autenticado para retornar ao painel:').classes('text-grey-4 text-xs q-mb-md')
        
        exit_pwd_input = ui.input('Senha', password=True).props('dark dense outlined autofocus w-full').classes('w-full font-mono text-center text-lg')
        
        async def confirm_exit():
            pwd = exit_pwd_input.value.strip()
            if not pwd:
                ui.notify('Senha não informada', color='negative')
                return
            
            # Autentica a senha usando a sessão
            from nicegui import app
            user_data = app.storage.user.get('user_data', {})
            username = user_data.get('email') or user_data.get('username')
            
            if not username:
                ui.notify('Usuário não identificado na sessão', color='negative')
                return
                
            from database import authenticate_user_supabase
            
            ui.notify('Autenticando...', color='info')
            auth_res = await asyncio.to_thread(authenticate_user_supabase, username, pwd)
            
            if auth_res:
                app.storage.user['tv_lock_active'] = False
                exit_lock_dialog.close()
                ui.notify('Modo TV desativado com sucesso!', color='positive')
                ui.navigate.to('/siscomca_dashboard')
            else:
                ui.notify('Senha incorreta! Não foi possível sair do Modo TV.', color='negative')
                exit_pwd_input.value = ''
                
        exit_pwd_input.on('keydown.enter', confirm_exit)
        
        with ui.row().classes('w-full justify-center gap-2 q-mt-md'):
            ui.button('CANCELAR', on_click=exit_lock_dialog.close).props('outline color=grey dense')
            ui.button('SAIR DO MODO TV', on_click=confirm_exit).props('unelevated color=red text-color=white dense').classes('font-bold')

    # Container Principal
    with ui.column().classes('w-full q-pa-sm gap-2 tv-main-container'):
        
        # ── CABEÇALHO TÁTICO ─────────────────────────────────────────────────────────
        with ui.row().classes('w-full items-center justify-between border-b-2 border-gray-900 q-pb-xs'):
            # Esquerda: Relógio Grande + data + Pôr do sol
            with ui.column().classes('items-start gap-0.5'):
                clock_lbl = ui.label('--:--:--').style(
                    'color:#fff; font-size:2.4rem; font-weight:900; letter-spacing:4px; font-family:monospace; line-height:1;'
                )
                with ui.row().classes('items-center gap-2'):
                    date_lbl = ui.label('').classes('text-amber-5 text-xs font-bold tracking-wider')
                    ui.label('|').classes('text-gray-700 text-xs')
                    sunset_icon = ui.icon('wb_twilight', color='orange-5').classes('text-sm')
                    sunset_lbl = ui.label('PÔR DO SOL: --:--').classes('text-orange-4 text-xs font-bold tracking-wider')

            # Centro: Título do Setor
            with ui.column().classes('items-center gap-1.5'):
                from services import data_service
                system_title = str(data_service.get_config_value('cabecalho_tv_title', 'SISTEMA C2') or 'SISTEMA C2').upper()
                system_subtitle = str(data_service.get_config_value('cabecalho_tv_subtitle', 'CORPO DE ALUNOS • COMANDO TÁTICO') or 'CORPO DE ALUNOS • COMANDO TÁTICO').upper()
                title_lbl = ui.label(system_title).style(
                    f'color:{THEME["primary"]}; font-size:2.2rem; font-weight:900; letter-spacing:4px; line-height:1.0;'
                )
                ui.label(system_subtitle).classes(
                    'text-gray-500 text-xs font-bold tracking-widest q-mt-xs'
                )

            # Direita: Status de Conectividade + Botões Descritivos Grandes
            with ui.column().classes('items-end gap-1.5 justify-center'):
                # Sublinha 1: Conectividade + Sinalizadores
                with ui.row().classes('items-center gap-2.5 no-wrap'):
                    status_dot = ui.icon('sensors', color='green').classes('text-2xl animate-pulse')
                    status_lbl = ui.label('ONLINE').classes('text-green-500 font-bold text-sm tracking-widest mr-2')
                    
                    # Indicador de Alertas Ativos
                    alerts_dot = ui.icon('notifications_active', color='cyan').classes('text-xl animate-pulse')
                    alerts_lbl = ui.label('ALERTAS ON').classes('text-cyan-5 font-bold text-xs tracking-widest')
                    
                    sound_btn = ui.button(
                        'SINAL: LIGADO', icon='volume_up'
                    ).props('outline color=amber dense no-caps').classes('text-xs font-bold px-2.5 py-1')
                    
                    voice_btn = ui.button(
                        'JARVIS: LIGADO', icon='record_voice_over'
                    ).props('outline color=amber dense no-caps').classes('text-xs font-bold px-2.5 py-1')
                    
                # Sublinha 2: Ações Extras (Privacidade / Retorno)
                with ui.row().classes('items-center gap-2.5 no-wrap'):
                    eye_btn = ui.button(
                        'OCULTAR DADOS', icon='visibility'
                    ).props('outline color=amber dense no-caps').classes('text-xs font-bold px-2.5 py-1')
                    
                    from nicegui import app
                    user_data = app.storage.user.get('user_data', {})
                    user_role = str(user_data.get('role', '')).strip().lower()
                    if user_role not in ('tv', 'tv_comcia'):
                        ui.button(
                            'DASHBOARD', icon='arrow_back',
                            on_click=exit_lock_dialog.open
                        ).props('outline color=grey dense no-caps').classes('text-xs font-bold text-grey-4 px-2.5 py-1')

                # Definição das funções de callback de áudio
                def toggle_sound():
                    audio_config['sound'] = not audio_config['sound']
                    label = "SINAL: LIGADO" if audio_config["sound"] else "SINAL: MUTADO"
                    icon = "volume_up" if audio_config["sound"] else "volume_off"
                    color = 'amber' if audio_config["sound"] else 'grey-5'
                    sound_btn.props(f'icon={icon} color={color}')
                    sound_btn.set_text(label)
                    ui.notify(f'Som de chime {"ativado" if audio_config["sound"] else "desativado"}', color='info')
                    from alerts_manager import AlertsManager
                    AlertsManager.update_tv_preferences(client.id, sound=audio_config['sound'])
                
                def toggle_voice():
                    audio_config['voice'] = not audio_config['voice']
                    label = "JARVIS: LIGADO" if audio_config["voice"] else "JARVIS: MUTADO"
                    icon = "record_voice_over" if audio_config["voice"] else "voice_over_off"
                    color = 'amber' if audio_config["voice"] else 'grey-5'
                    voice_btn.props(f'icon={icon} color={color}')
                    voice_btn.set_text(label)
                    ui.notify(f'Leitura de voz (Jarvis) {"ativada" if audio_config["voice"] else "desativada"}', color='info')
                    from alerts_manager import AlertsManager
                    AlertsManager.update_tv_preferences(client.id, voice=audio_config['voice'])

                # Associa os callbacks aos botões
                sound_btn.on_click(toggle_sound)
                voice_btn.on_click(toggle_voice)
                eye_btn.on_click(toggle_blur)

        # ── CONFIGURAÇÃO DE TRANSIÇÕES DA ESCALA ──
        current_tv_data = {'d': None}
        active_card_view = {'index': 0}
        active_notes_view = {'show_stats': False}
        hovering_card = {'value': False}

        @ui.refreshable
        def render_servico_diario_card():
            d = current_tv_data['d']
            if not d:
                with ui.column().classes('w-full h-full items-center justify-center'):
                    ui.spinner(color='amber', size='lg')
                    ui.label('CARREGANDO...').classes('text-amber-5 text-[14px]')
                return

            view_idx = active_card_view['index']
            if view_idx == 0:
                # VIEW 0: ESCALA DE SERVIÇO
                # 1. Bloco de Cima (Inspetor do Dia em Destaque)
                insp_name_raw = d['inspetor_dia']['nome']
                is_insp_defined = "DEFINIDO" not in insp_name_raw.upper() and "ESCALADO" not in insp_name_raw.upper() and insp_name_raw.strip() != ""
                
                with ui.card().classes('w-full q-pa-xs border').style(
                    f'background: rgba(212, 175, 55, 0.08) !important; border: 2px solid #D4AF37 !important; box-shadow: 0 0 25px rgba(212, 175, 55, 0.45) !important; height: 45%; display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 8px; gap: 6px;'
                ):
                    with ui.column().classes('w-full items-center justify-center gap-1.5 no-wrap'):
                        if is_insp_defined:
                            ui.avatar(size='72px').style(f"background-image: url('{d['inspetor_dia']['photo_url']}'); background-size: cover; background-position: center; border: 2px solid #D4AF37; box-shadow: 0 0 16px rgba(212, 175, 55, 0.6); shrink: 0; border-radius: 8px !important;")
                            ui.label(d['inspetor_dia']['cargo_title']).style(f'color: {THEME["primary"]}; font-size: 18px; font-weight: 900; letter-spacing: 3px; line-height: 1; text-align: center;')
                            ui.label(insp_name_raw.upper()).classes('text-white text-[30px] font-black tracking-wider leading-none text-center')
                        else:
                            ui.avatar(size='72px').style("background-image: url('https://cdn.quasar.dev/img/boy-avatar.png'); background-size: cover; background-position: center; border: 2px solid #ff9100; box-shadow: 0 0 12px rgba(255, 145, 0, 0.4); shrink: 0; border-radius: 8px !important;")
                            ui.label(d['inspetor_dia']['cargo_title']).style(f'color: {THEME["primary"]}; font-size: 18px; font-weight: 900; letter-spacing: 3px; line-height: 1; text-align: center;')
                            ui.label('AGUARDANDO').classes('text-amber-5/70 italic animate-pulse text-[30px] font-black tracking-wider leading-none text-center')

                # 2. Bloco de Baixo (Demais Serviços)
                with ui.card().classes('w-full q-pa-xs border border-gray-900/60').style(
                    'background: rgba(0,0,0,0.3); flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; border-radius: 6px;'
                ):
                    with ui.row().classes('w-full items-center justify-between px-1 q-mb-xs border-b border-gray-900/80 q-pb-0.5'):
                        ui.label('👮 DEMAIS SERVIÇOS').classes('text-amber-5 text-[12px] font-black tracking-widest')
                        ui.badge('PRONTOS', color='green-9').classes('text-[10px] font-bold')
                        
                    def is_defined(name: str) -> bool:
                        if not name:
                            return False
                        n = name.strip().upper()
                        return "DEFINIDO" not in n and "ESCALADO" not in n and n not in {"", "N/A", "-", "NÃO ESCALADO"}

                    outros_servicos = []
                    osca_name = d.get('osca_servico', '')
                    if is_defined(osca_name):
                        outros_servicos.append({'cargo': 'OSCA', 'nome': osca_name})
                    ajosca_name = d.get('ajosca_servico', '')
                    if is_defined(ajosca_name):
                        outros_servicos.append({'cargo': 'AJOSCA', 'nome': ajosca_name})
                    for esc in d.get('outros_escalados', []):
                        if is_defined(esc['nome']):
                            outros_servicos.append({'cargo': esc['cargo'], 'nome': esc['nome']})

                    if not outros_servicos:
                        with ui.column().classes('w-full h-full items-center justify-center gap-1.5').style('flex: 1; min-height: 0;'):
                            ui.icon('shield', size='2rem', color='grey-8')
                            ui.label('NENHUM OUTRO SERVIÇO DEFINIDO').classes('text-grey-6 font-bold text-[13px] tracking-wider')
                    else:
                        use_marquee = len(outros_servicos) > 4
                        classes_inner = 'health-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1'
                        items_marquee = outros_servicos * 2 if use_marquee else outros_servicos

                        with ui.column().classes('w-full').style('flex: 1; min-height: 0; overflow: hidden; position: relative;'):
                            with ui.column().classes(classes_inner):
                                for item in items_marquee:
                                    with ui.row().classes('w-full items-center justify-between px-1 q-py-0.5 border-b border-gray-900/50 hover:bg-white/5'):
                                        ui.label(item['cargo'].upper()).classes('text-grey-5 font-bold text-[14px]').style('font-family: monospace;')
                                        with ui.row().classes('items-center gap-1.5'):
                                            ui.label(item['nome'].upper()).classes('text-white font-black text-[14px]')
                                            ui.badge('PRONTO', color='green-9').classes('text-[10px] font-bold')
            
            elif view_idx == 1:
                # VIEW 1: TOTAL DE ALUNOS POR TURMA
                with ui.column().classes('w-full h-full gap-2 justify-center items-center q-pa-sm'):
                    ui.label('📊 TOTAL POR TURMA').style(f'color: {THEME["primary"]}; font-size: 16px; font-weight: 900; letter-spacing: 2px; text-align: center;')
                    ui.separator().props('dark')
                    with ui.element('div').classes('grid grid-cols-2 gap-x-2 gap-y-1.5 w-full').style('flex: 1; min-height: 0; overflow-y: auto; align-content: center;'):
                        for t in d.get('turmas_counts', []):
                            with ui.row().classes('items-center justify-between px-2.5 py-1 border-b border-gray-900/40 bg-black/20 rounded no-wrap'):
                                ui.label(f"PEL. {t['turma']}").classes('text-white font-bold text-[12px] truncate')
                                ui.label(f"{t['total']} al").classes('text-amber-5 text-[12px] font-mono font-black shrink-0')

            elif view_idx == 2:
                # VIEW 2: QUANTIDADE POR ESPECIALIDADE
                with ui.column().classes('w-full h-full gap-2 justify-center items-center q-pa-sm'):
                    ui.label('🛠️ POR ESPECIALIDADE').style(f'color: {THEME["primary"]}; font-size: 16px; font-weight: 900; letter-spacing: 2px; text-align: center;')
                    ui.separator().props('dark')
                    with ui.element('div').classes('grid grid-cols-2 gap-x-2 gap-y-1.5 w-full').style('flex: 1; min-height: 0; overflow-y: auto; align-content: center;'):
                        for esp in d.get('especialidades_counts', []):
                            with ui.row().classes('items-center justify-between px-2.5 py-1 border-b border-gray-900/40 bg-black/20 rounded no-wrap'):
                                ui.label(esp['especialidade']).classes('text-white font-bold text-[12px] truncate')
                                ui.label(f"{esp['total']} al").classes('text-cyan-4 text-[12px] font-mono font-black shrink-0')

        @ui.refreshable
        def render_anotacoes_card_content():
            d = current_tv_data['d']
            if not d:
                with ui.column().classes('w-full h-full items-center justify-center'):
                    ui.spinner(color='amber', size='md')
                    ui.label('CARREGANDO...').classes('text-amber-5 text-[14px]')
                return
            
            show_stats = active_notes_view['show_stats']
            
            with ui.column().classes('w-full gap-2 h-full'):
                if not show_stats:
                    # PAINEL 1: ANOTAÇÕES DO DIA (LISTA)
                    ui.label('📋 ANOTAÇÕES DO DIA').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center w-full')
                    ui.separator().props('dark')
                    
                    with ui.column().classes('w-full gap-1 overflow-y-auto text-grey-3 text-[16px]').style('flex: 1; min-height: 0;'):
                        anotacoes_list = d.get('anotacoes_dia', [])
                        if not anotacoes_list or (len(anotacoes_list) == 1 and anotacoes_list[0]['nome'] == 'NENHUM REGISTRO'):
                            with ui.card().classes('w-full q-pa-sm items-center justify-center bg-gray-900/30 border border-gray-800/50').style('flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center;'):
                                ui.label('NENHUM REGISTRO DE ANOTAÇÃO HOJE.').classes('text-grey-5 font-bold text-[16px] text-center')
                        else:
                            use_marquee = len(anotacoes_list) > 3
                            classes_inner = 'notes-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1'
                            
                            with ui.column().classes(classes_inner):
                                for anot in anotacoes_list:
                                    status = anot.get('status', 'Lançado')
                                    pts = anot.get('pts', 0.0)
                                    is_pendente = status == 'Pendente'
                                    
                                    if pts > 0:
                                        icon_color = '#00e676'
                                        bg_rgba = 'rgba(0, 230, 118, 0.06)'
                                        border_color = 'rgba(0, 230, 118, 0.3)'
                                    elif pts < 0:
                                        icon_color = '#ff1744'
                                        bg_rgba = 'rgba(255, 23, 68, 0.06)'
                                        border_color = 'rgba(255, 23, 68, 0.3)'
                                    else:
                                        if is_pendente:
                                            icon_color = '#ffb300'
                                            bg_rgba = 'rgba(255, 179, 0, 0.06)'
                                            border_color = 'rgba(255, 179, 0, 0.3)'
                                        elif status == 'Rejeitado':
                                            icon_color = '#ff1744'
                                            bg_rgba = 'rgba(255, 23, 68, 0.06)'
                                            border_color = 'rgba(255, 23, 68, 0.3)'
                                        else:
                                            icon_color = '#90a4ae'
                                            bg_rgba = 'rgba(144, 164, 174, 0.06)'
                                            border_color = 'rgba(144, 164, 174, 0.3)'

                                    with ui.card().classes('w-full q-pa-xs border q-mb-xs').style(f'background: {bg_rgba}; border-color: {border_color}; margin-bottom: 4px;'):
                                        motivo_lbl = anot.get('motivo') or ''
                                        if motivo_lbl and motivo_lbl.strip() != '' and motivo_lbl.upper() != 'SEM DESCRIÇÃO' and 'NENHUM REGISTRO' not in anot['nome']:
                                            with ui.tooltip().classes('bg-slate-900 text-white text-xs font-semibold max-w-sm'):
                                                ui.label(motivo_lbl).style('white-space: normal; word-break: break-word;')
                                                
                                        with ui.row().classes('w-full items-center justify-between px-1 hover:bg-white/5 no-wrap gap-2'):
                                            with ui.row().classes('items-center gap-1.5 no-wrap col-grow'):
                                                if is_pendente:
                                                    ui.icon('watch_later', color='amber-5', size='1.3rem')
                                                elif status == 'Rejeitado':
                                                    ui.icon('cancel', color='red-5', size='1.3rem')
                                                else:
                                                    if pts > 0:
                                                        ui.icon('add_circle', color='green-5', size='1.3rem')
                                                    elif pts < 0:
                                                        ui.icon('remove_circle', color='red-5', size='1.3rem')
                                                    else:
                                                        ui.icon('info', color='grey-5', size='1.3rem')
                                                
                                                with ui.column().classes('gap-0'):
                                                    ui.label(anot.get('pelotao', '').upper()).classes('text-white font-bold text-[15px] truncate')
                                                    ui.label(anot.get('tipo', '').upper()).classes('text-grey-4 text-[12px] truncate')
                                                
                else:
                    # PAINEL 2: ESTATÍSTICAS DE ANOTAÇÕES (FLIP CARD)
                    stats = d.get('stats_anotacoes', {})
                    ui.label('📊 ESTATÍSTICAS DE ANOTAÇÕES').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center w-full')
                    ui.separator().props('dark')
                    
                    with ui.column().classes('w-full gap-2 justify-center items-center').style('flex: 1; min-height: 0;'):
                        # Grid 2x2 de estatísticas
                        with ui.row().classes('w-full gap-2 justify-between no-wrap'):
                            # Positivas Semana
                            with ui.card().classes('col-grow q-pa-xs items-center justify-center').style('background: rgba(0, 230, 118, 0.05) !important; border-color: rgba(0, 230, 118, 0.2) !important;'):
                                ui.label('POSITIVAS (SEMANA)').classes('text-green-400 text-[10px] font-bold')
                                ui.label(str(stats.get('pos_semana', 0))).classes('text-white text-[20px] font-black font-mono')
                            
                            # Negativas Semana
                            with ui.card().classes('col-grow q-pa-xs items-center justify-center').style('background: rgba(255, 23, 68, 0.05) !important; border-color: rgba(255, 23, 68, 0.2) !important;'):
                                ui.label('NEGATIVAS (SEMANA)').classes('text-red-400 text-[10px] font-bold')
                                ui.label(str(stats.get('neg_semana', 0))).classes('text-white text-[20px] font-black font-mono')
                                
                        with ui.row().classes('w-full gap-2 justify-between no-wrap'):
                            # Positivas Geral
                            with ui.card().classes('col-grow q-pa-xs items-center justify-center').style('background: rgba(0, 230, 118, 0.05) !important; border-color: rgba(0, 230, 118, 0.2) !important;'):
                                ui.label('POSITIVAS (GERAL)').classes('text-green-400 text-[10px] font-bold')
                                ui.label(str(stats.get('pos_geral', 0))).classes('text-white text-[20px] font-black font-mono')
                            
                            # Negativas Geral
                            with ui.card().classes('col-grow q-pa-xs items-center justify-center').style('background: rgba(255, 23, 68, 0.05) !important; border-color: rgba(255, 23, 68, 0.2) !important;'):
                                ui.label('NEGATIVAS (GERAL)').classes('text-red-400 text-[10px] font-bold')
                                ui.label(str(stats.get('neg_geral', 0))).classes('text-white text-[20px] font-black font-mono')
                        
                        # (Primeira anotação removida)

        # ── CORPO PRINCIPAL DO PAINEL (GRID DUPLO) ─────────────────────────────
        with ui.element('div').classes('tv-main-row'):
            
            # === COLUNA ESQUERDA (1/5 - Serviço Diário + Anotações) ===
            with ui.element('div').classes('tv-left-col'):
                # Serviço Diário (Top, height: 42%) - Dividido permanentemente em 2 blocos
                with ui.element('div').classes('tv-panel border border-gray-800').style(
                    f'background: {THEME["bg_panel"]}; width: 100%; height: 42%; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; gap: 4px; padding: 6px;'
                ).on('mouseenter', lambda: hovering_card.__setitem__('value', True)).on('mouseleave', lambda: hovering_card.__setitem__('value', False)):
                    render_servico_diario_card()

                # Anotações do Dia (Bottom, flex: 1 to fill remainder of Column 1)
                with ui.card().classes('q-pa-sm border border-gray-800 tv-panel').style(f'background: {THEME["bg_panel"]}; width: 100%; flex: 1; min-height: 0; transition: filter 0.3s ease;'):
                    render_anotacoes_card_content()

            # === COLUNA CENTRAL (3/5 - KPIs + Licenças/Dispensas + Enfermaria) ===
            with ui.element('div').classes('tv-center-col'):
                # KPIs 4x2 (Top, height: 42% - to align perfectly with Servicio Diario height!)
                quant_container = ui.column().style('width: 100%; height: 42%; min-height: 0; display: flex; flex-direction: column; gap: 6px;')

                # Bottom Row inside Column 2 (Licenças/Dispensas + Enfermaria, flex: 1 to fill remainder)
                with ui.row().classes('w-full gap-2').style('flex: 1; min-height: 0;'):
                    # Licenças e Dispensas (flex: 1)
                    with ui.card().classes('q-pa-sm border border-gray-800 tv-panel').style(f'background: {THEME["bg_panel"]}; flex: 1; height: 100%;'):
                        with ui.column().classes('w-full gap-2 h-full'):
                            ui.label('✈️ LICENÇAS / DISPENSAS').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center w-full')
                            ui.separator().props('dark')
                            
                            lic_disp_marquee_div = ui.column().classes('w-full').style('flex: 1; min-height: 0; overflow: hidden; position: relative;')

                    # Enfermaria (flex: 1)
                    with ui.card().classes('q-pa-sm border border-gray-800 tv-panel').style(f'background: {THEME["bg_panel"]}; flex: 1; height: 100%;'):
                        with ui.column().classes('w-full gap-2 h-full'):
                            with ui.row().classes('w-full items-center justify-center gap-2'):
                                ui.label('🏥 SITUAÇÃO DE SAÚDE').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center')
                                enfermaria_total_lbl = ui.label('TOTAL: --').classes('text-white text-[18px] font-bold font-mono px-1.5 bg-red-9/30 border border-red-500 rounded')
                            ui.separator().props('dark')
                            
                            enfermaria_marquee_div = ui.column().classes('w-full').style('flex: 1; min-height: 0; overflow: hidden; position: relative;')

            # === COLUNA DIREITA (1/5 - Programação de Instrução) ===
            with ui.element('div').classes('tv-right-col'):
                with ui.card().classes('w-full q-pa-sm border border-gray-800 tv-panel').style(f'background: {THEME["bg_panel"]}; flex: 1; height: 100%;'):
                    with ui.column().classes('w-full gap-2 h-full'):
                        with ui.row().classes('w-full items-center justify-center gap-2'):
                            ui.label('PROGRAMAÇÃO').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center')
                        ui.separator().props('dark')
                        
                        atividades_marquee_container = ui.column().classes('w-full').style('flex: 1; min-height: 0; overflow: hidden; position: relative;')


        # ── LETREIRO DE ANOTAÇÕES + RODAPÉ ──────────────────────────────────────────────────
        with ui.column().classes('w-full gap-0 border-t-2 border-amber-900/50'):
            # Ticker horizontal de anotacoes (Dobrado de tamanho e fonte acompanhando)
            with ui.row().classes('w-full items-center bg-black/60 q-px-sm').style('height: 56px; overflow: hidden;'):
                ui.icon('campaign', color='amber', size='2.5rem')
                ticker_container = ui.element('div').classes('ticker-wrapper').style('flex: 1;')
    def _update_clock():
        """Atualiza o relógio a cada segundo e verifica status dos alertas."""
        from datetime import timezone, timedelta
        tz_gmt3 = timezone(timedelta(hours=-3))
        now_gmt3 = datetime.now(tz_gmt3)
        clock_lbl.set_text(now_gmt3.strftime('%H:%M:%S'))
        date_lbl.set_text(get_pt_date_string(now_gmt3))
        sunset_lbl.set_text(f"PÔR DO SOL: {estimate_sunset_time()}")
        
        # Atualiza status de alertas (a cada segundo)
        try:
            from alerts_manager import AlertsManager
            num_callbacks = len(AlertsManager._tv_callbacks)
            if num_callbacks > 0 and (queue_task is not None and not queue_task.done()):
                alerts_lbl.set_text('ALERTAS ON')
                alerts_dot.props('color=green')
            else:
                alerts_lbl.set_text('ALERTAS OFF')
                alerts_dot.props('color=orange')
        except Exception as e:
            pass

    # Fila de notificações em tempo real (evita colisão de modais e sons)
    toast_queue = asyncio.Queue()


    async def trigger_toast(title, msg, type_='info', jarvis_text=None, jarvis_audio=None, extra_options=None):
        """Enfileira o alerta em tempo real para ser exibido sequencialmente na TV."""
        await toast_queue.put((title, msg, type_, jarvis_text, jarvis_audio, extra_options))
        # Dispara uma atualização imediata dos dados da tela
        asyncio.create_task(_refresh())

    async def _process_toast_queue():
        """Processa a fila de alertas sequencialmente, garantindo o tempo de exibição e sons."""
        while True:
            try:
                title, msg, type_, jarvis_text, jarvis_audio, extra_options = await toast_queue.get()
                await _display_toast(title, msg, type_, jarvis_text, jarvis_audio, extra_options)
                toast_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[TV Queue] Erro ao processar alerta: {e}")
                await asyncio.sleep(1)

    async def _display_toast(title, msg, type_='info', jarvis_text=None, jarvis_audio=None, extra_options=None):
        """Gera um diálogo luminoso centralizado e ultra-premium na TV com Fade In/Out (máx 10 segundos)."""
        color_theme = {
            'info':    {'border': '#00e5ff', 'bg': '#000b1c', 'glow': 'rgba(0, 229, 255, 0.4)'},
            'success': {'border': '#00e676', 'bg': '#00140a', 'glow': 'rgba(0, 230, 118, 0.4)'},
            'alert':   {'border': '#ff1744', 'bg': '#190005', 'glow': 'rgba(255, 23, 68, 0.4)'},
            'warning': {'border': '#ff9100', 'bg': '#190a00', 'glow': 'rgba(255, 145, 0, 0.4)'}
        }
        # Resolve a chave de tema a partir do tipo do alerta (que pode ser uma lista de sons)
        theme_key = 'info'
        if isinstance(type_, str):
            theme_key = type_
        elif isinstance(type_, list) and type_:
            first_item = type_[0]
            if isinstance(first_item, dict):
                theme_key = first_item.get('som', 'info')
            else:
                theme_key = str(first_item)
        
        if theme_key not in color_theme:
            theme_key = 'info'

        cfg = color_theme.get(theme_key, color_theme['info'])
        from alerts_manager import load_alerts_config
        from database import SUPABASE_URL
        alerts_config = load_alerts_config()
        vocativo = alerts_config.get('tv_alert_vocativo', 'Atenção!')
        
        # Opções extra do alerta agendado
        visual_alert = extra_options.get('visual_alert', True) if extra_options else True
        voice_enabled = extra_options.get('voice_enabled', True) if extra_options else True
        sound_enabled = extra_options.get('sound_enabled', True) if extra_options else True
        
        import json
        from services import data_service
        basic_voice = data_service.get_config_value('basic_tts_voice', '')
        escaped_title = json.dumps(title)
        escaped_msg = json.dumps(msg)
        escaped_jarvis = json.dumps(jarvis_text) if jarvis_text else "null"
        escaped_audio = json.dumps(jarvis_audio) if jarvis_audio else "null"
        escaped_vocativo = json.dumps(vocativo)
        escaped_basic_voice = json.dumps(basic_voice)
        
        try:
            with client:
                if visual_alert:
                    icon_map = {
                        'success': 'stars',
                        'alert': 'gavel',
                        'warning': 'healing',
                        'info': 'campaign'
                    }
                    icon_name = icon_map.get(theme_key, 'info')
                    
                    # Atualiza estilos e conteúdo dinamicamente no card estático
                    dialog_card.style(
                        f"background: {cfg['bg']} !important; border-color: {cfg['border']} !important; "
                        f"box-shadow: 0 0 50px {cfg['glow']} !important; min-width: 700px; max-width: 90%; "
                        f"color: #fff; font-family: monospace;"
                    )
                    dialog_icon.name = icon_name
                    dialog_icon.style(f"color: {cfg['border']}; filter: drop-shadow(0 0 20px {cfg['glow']});")
                    dialog_title.set_text(title.upper())
                    dialog_title.style(f"color: {cfg['border']}; font-size: 2.6rem; font-weight: 900; letter-spacing: 5px; line-height: 1.2;")
                    dialog_sep.style(f"background-color: {cfg['border']}; opacity: 0.4; height: 3px;")
                    dialog_msg.set_text(msg)
                    
                    tactical_dialog.props('persistent')
                    tactical_dialog.open()
                
                play_sound_js = 'true' if (audio_config['sound'] and sound_enabled) else 'false'
                play_voice_js = 'true' if (audio_config['voice'] and voice_enabled) else 'false'

                # Toca o som (sintetizado via Web Audio API offline para evitar bloqueios de CORS/Internet)
                js_code = f"""
                try {{
                    const playSound = {play_sound_js};
                    const playVoice = {play_voice_js};
                    const supabaseBaseUrl = "{SUPABASE_URL}";
                    const type = {json.dumps(type_)};

                    let ctx = window.globalAudioContext;
                    if (!ctx) {{
                        const AudioContext = window.AudioContext || window.webkitAudioContext;
                        if (AudioContext) {{
                            ctx = new AudioContext();
                            window.globalAudioContext = ctx;
                        }}
                    }}

                    console.log("[TV ALERT JS] --- NOVO ALERTA TÁTICO ---");
                    console.log("[TV ALERT JS] Tipo/Som:", type);
                    console.log("[TV ALERT JS] playSound (config):", playSound, "| playVoice (config):", playVoice);
                    console.log("[TV ALERT JS] AudioContext state:", ctx ? ctx.state : 'não suportado');

                    function playDefaultSynthesized(type) {{
                        if (!ctx) return;
                        if (type === 'submarine_sonar') {{
                            let now = ctx.currentTime;
                            let osc = ctx.createOscillator();
                            let gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            
                            osc.type = 'sine';
                            osc.frequency.setValueAtTime(800, now);
                            osc.frequency.exponentialRampToValueAtTime(850, now + 0.15);
                            
                            gain.gain.setValueAtTime(0, now);
                            gain.gain.linearRampToValueAtTime(0.4, now + 0.005);
                            gain.gain.exponentialRampToValueAtTime(0.001, now + 1.8);
                            
                            osc.start(now);
                            osc.stop(now + 2.0);
                            
                            let echoOsc = ctx.createOscillator();
                            let echoGain = ctx.createGain();
                            echoOsc.connect(echoGain);
                            echoGain.connect(ctx.destination);
                            
                            echoOsc.type = 'sine';
                            echoOsc.frequency.setValueAtTime(810, now + 0.8);
                            echoOsc.frequency.exponentialRampToValueAtTime(830, now + 0.95);
                            
                            echoGain.gain.setValueAtTime(0, now + 0.8);
                            echoGain.gain.linearRampToValueAtTime(0.08, now + 0.805);
                            echoGain.gain.exponentialRampToValueAtTime(0.0001, now + 2.0);
                            
                            echoOsc.start(now + 0.8);
                            echoOsc.stop(now + 2.2);
                        }} else if (type === 'morse_sos') {{
                            let now = ctx.currentTime;
                            const toneFreq = 800;
                            const dot = 0.08;
                            const dash = 0.24;
                            
                            let osc = ctx.createOscillator();
                            let gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            
                            osc.type = 'sine';
                            osc.frequency.setValueAtTime(toneFreq, now);
                            gain.gain.setValueAtTime(0, now);
                            
                            function scheduleTone(start, duration) {{
                                gain.gain.setValueAtTime(0, now + start);
                                gain.gain.linearRampToValueAtTime(0.2, now + start + 0.005);
                                gain.gain.setValueAtTime(0.2, now + start + duration - 0.005);
                                gain.gain.linearRampToValueAtTime(0, now + start + duration);
                            }}
                            
                            scheduleTone(0.0, dot);
                            scheduleTone(0.16, dot);
                            scheduleTone(0.32, dot);
                            
                            scheduleTone(0.56, dash);
                            scheduleTone(0.88, dash);
                            scheduleTone(1.20, dash);
                            
                            scheduleTone(1.52, dot);
                            scheduleTone(1.68, dot);
                            scheduleTone(1.84, dot);
                            
                            osc.start(now);
                            osc.stop(now + 2.1);
                        }} else if (type === 'naval_horn') {{
                            let now = ctx.currentTime;
                            const fundamental = 72;
                            const oscillators = [fundamental, fundamental * 1.5, fundamental * 2.0, fundamental * 2.5];
                            const gains = [0.4, 0.25, 0.15, 0.08];
                            const detunes = [0, 1.2, -0.8, 0.5];
                            
                            let mainGain = ctx.createGain();
                            let filter = ctx.createBiquadFilter();
                            
                            filter.type = 'lowpass';
                            filter.frequency.setValueAtTime(250, now);
                            filter.Q.setValueAtTime(2, now);
                            
                            mainGain.connect(filter);
                            filter.connect(ctx.destination);
                            
                            mainGain.gain.setValueAtTime(0, now);
                            mainGain.gain.linearRampToValueAtTime(0.5, now + 0.25);
                            mainGain.gain.setValueAtTime(0.5, now + 1.6);
                            mainGain.gain.exponentialRampToValueAtTime(0.001, now + 2.4);
                            
                            oscillators.forEach((freq, idx) => {{
                                let osc = ctx.createOscillator();
                                osc.type = 'sawtooth';
                                osc.frequency.setValueAtTime(freq + detunes[idx], now);
                                
                                let oscGain = ctx.createGain();
                                oscGain.gain.setValueAtTime(gains[idx], now);
                                
                                osc.connect(oscGain);
                                oscGain.connect(mainGain);
                                
                                osc.start(now);
                                osc.stop(now + 2.5);
                            }});
                        }} else if (type === 'success') {{
                            let osc = ctx.createOscillator();
                            let gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            osc.type = 'sine';
                            osc.frequency.setValueAtTime(523.25, ctx.currentTime);
                            gain.gain.setValueAtTime(0.3, ctx.currentTime);
                            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                            osc.start(ctx.currentTime);
                            
                            let osc2 = ctx.createOscillator();
                            let gain2 = ctx.createGain();
                            osc2.connect(gain2);
                            gain2.connect(ctx.destination);
                            osc2.type = 'sine';
                            osc2.frequency.setValueAtTime(659.25, ctx.currentTime + 0.1);
                            gain2.gain.setValueAtTime(0.3, ctx.currentTime + 0.1);
                            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
                            osc2.start(ctx.currentTime + 0.1);
                            
                            osc.stop(ctx.currentTime + 0.2);
                            osc2.stop(ctx.currentTime + 0.4);
                        }} else if (type === 'warning') {{
                            let osc1 = ctx.createOscillator();
                            let gain1 = ctx.createGain();
                            osc1.connect(gain1);
                            gain1.connect(ctx.destination);
                            osc1.type = 'sine';
                            osc1.frequency.setValueAtTime(440, ctx.currentTime);
                            gain1.gain.setValueAtTime(0.2, ctx.currentTime);
                            gain1.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                            osc1.start(ctx.currentTime);
                            osc1.stop(ctx.currentTime + 0.2);
  
                            let osc2 = ctx.createOscillator();
                            let gain2 = ctx.createGain();
                            osc2.connect(gain2);
                            gain2.connect(ctx.destination);
                            osc2.type = 'sine';
                            osc2.frequency.setValueAtTime(440, ctx.currentTime + 0.15);
                            gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.15);
                            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                            osc2.start(ctx.currentTime + 0.15);
                            osc2.stop(ctx.currentTime + 0.35);
                        }} else if (type === 'alert') {{
                            let osc = ctx.createOscillator();
                            let gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            osc.type = 'triangle';
                            osc.frequency.setValueAtTime(150, ctx.currentTime);
                            
                            gain.gain.setValueAtTime(0.4, ctx.currentTime);
                            gain.gain.setValueAtTime(0, ctx.currentTime + 0.15);
                            gain.gain.setValueAtTime(0.4, ctx.currentTime + 0.25);
                            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.45);
                            
                            osc.start(ctx.currentTime);
                            osc.stop(ctx.currentTime + 0.5);
                        }} else if (type === 'chime_simple') {{
                            let now = ctx.currentTime;
                            let osc1 = ctx.createOscillator();
                            let gain1 = ctx.createGain();
                            osc1.connect(gain1);
                            gain1.connect(ctx.destination);
                            osc1.type = 'sine';
                            osc1.frequency.setValueAtTime(523.25, now);
                            gain1.gain.setValueAtTime(0.3, now);
                            gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.6);
                            osc1.start(now);
                            osc1.stop(now + 0.7);
                        }} else if (type === 'bell_ring') {{
                            let now = ctx.currentTime;
                            let osc1 = ctx.createOscillator();
                            let gain1 = ctx.createGain();
                            osc1.connect(gain1);
                            gain1.connect(ctx.destination);
                            osc1.type = 'sine';
                            osc1.frequency.setValueAtTime(987.77, now);
                            gain1.gain.setValueAtTime(0.25, now);
                            gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.8);
                            osc1.start(now);
                            osc1.stop(now + 0.9);
                        }} else if (type === 'digital_warning') {{
                            let now = ctx.currentTime;
                            let osc = ctx.createOscillator();
                            let gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            osc.type = 'triangle';
                            osc.frequency.setValueAtTime(150, now);
                            
                            gain.gain.setValueAtTime(0.4, now);
                            gain.gain.setValueAtTime(0, now + 0.15);
                            gain.gain.setValueAtTime(0.4, now + 0.25);
                            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.45);
                            
                            osc.start(now);
                            osc.stop(now + 0.5);
                        }} else if (type === 'info') {{
                            let osc1 = ctx.createOscillator();
                            let gain1 = ctx.createGain();
                            osc1.connect(gain1);
                            gain1.connect(ctx.destination);
                            osc1.type = 'sine';
                            osc1.frequency.setValueAtTime(600, ctx.currentTime);
                            gain1.gain.setValueAtTime(0.2, ctx.currentTime);
                            gain1.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
                            osc1.start(ctx.currentTime);
                            osc1.stop(ctx.currentTime + 0.3);
  
                            let osc2 = ctx.createOscillator();
                            let gain2 = ctx.createGain();
                            osc2.connect(gain2);
                            gain2.connect(ctx.destination);
                            osc2.type = 'sine';
                            osc2.frequency.setValueAtTime(800, ctx.currentTime + 0.08);
                            gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.08);
                            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.33);
                            osc2.start(ctx.currentTime + 0.08);
                            osc2.stop(ctx.currentTime + 0.38);
                        }}
                    }}

                    function playSingleSound(sndType) {{
                        if (sndType.startsWith('naval_bell_')) {{
                            let count = 1;
                            if (sndType === 'naval_bell_singela') {{
                                count = 1;
                            }} else if (sndType === 'naval_bell_dobrada') {{
                                count = 2;
                            }} else {{
                                count = parseInt(sndType.split('_')[2]) || 1;
                            }}
                            
                            const singleMp3Url = supabaseBaseUrl + "/storage/v1/object/public/sons/bell_single.mp3";
                            const doubleMp3Url = supabaseBaseUrl + "/storage/v1/object/public/sons/bell_double.mp3";
                            
                            function playSynthesizedBells(ctx, count) {{
                                function playNavalBellStrike(ctx, time) {{
                                    const frequencies = [240, 480, 576, 720, 960, 1200, 1440, 1920];
                                    const gains = [0.35, 0.35, 0.25, 0.15, 0.15, 0.1, 0.08, 0.05];
                                    const decays = [3.2, 2.6, 2.2, 1.8, 1.4, 1.0, 0.6, 0.4];

                                    frequencies.forEach((f, idx) => {{
                                        let osc = ctx.createOscillator();
                                        let gainNode = ctx.createGain();
                                        osc.connect(gainNode);
                                        gainNode.connect(ctx.destination);
                                        
                                        osc.type = 'sine';
                                        osc.frequency.setValueAtTime(f, time);
                                        
                                        gainNode.gain.setValueAtTime(0, time);
                                        gainNode.gain.linearRampToValueAtTime(gains[idx], time + 0.005);
                                        gainNode.gain.exponentialRampToValueAtTime(0.001, time + decays[idx]);
                                        
                                        osc.start(time);
                                        osc.stop(time + decays[idx] + 0.1);
                                    }});
                                }}

                                let now = ctx.currentTime;
                                for (let i = 0; i < count; i++) {{
                                    let pairIndex = Math.floor(i / 2);
                                    let inPairIndex = i % 2;
                                    let timeOffset = pairIndex * 2.0 + inPairIndex * 0.15;
                                    playNavalBellStrike(ctx, now + timeOffset);
                                }}
                            }}

                            fetch(singleMp3Url)
                                .then(res => {{
                                    if (res.ok) {{
                                        let pairs = Math.floor(count / 2);
                                        let remainder = count % 2;
                                        
                                        for (let p = 0; p < pairs; p++) {{
                                            setTimeout(() => {{
                                                let audio = new Audio(doubleMp3Url);
                                                audio.volume = 1.0;
                                                audio.play().catch(() => {{}});
                                            }}, p * 2000);
                                        }}
                                        
                                        if (remainder > 0) {{
                                            setTimeout(() => {{
                                                let audio = new Audio(singleMp3Url);
                                                audio.volume = 1.0;
                                                audio.play().catch(() => {{}});
                                            }}, pairs * 2000);
                                        }}
                                    }} else {{
                                        playSynthesizedBells(ctx, count);
                                    }}
                                }}).catch(() => {{
                                    playSynthesizedBells(ctx, count);
                                }});
                        }} else {{
                            const customMp3Url = supabaseBaseUrl + "/storage/v1/object/public/sons/" + encodeURIComponent(sndType) + ".mp3";
                            const customMp3UrlUpper = supabaseBaseUrl + "/storage/v1/object/public/sons/" + encodeURIComponent(sndType) + ".MP3";
                            fetch(customMp3Url)
                                .then(res => {{
                                    if (res.ok) {{
                                        let audio = new Audio(customMp3Url);
                                        audio.volume = 1.0;
                                        audio.play().catch(() => {{}});
                                    }} else {{
                                        fetch(customMp3UrlUpper)
                                            .then(res2 => {{
                                                if (res2.ok) {{
                                                    let audio2 = new Audio(customMp3UrlUpper);
                                                    audio2.volume = 1.0;
                                                    audio2.play().catch(() => {{}});
                                                }} else {{
                                                    playDefaultSynthesized(sndType);
                                                }}
                                            }}).catch(() => {{
                                                playDefaultSynthesized(sndType);
                                            }});
                                    }}
                                }}).catch(() => {{
                                    fetch(customMp3UrlUpper)
                                        .then(res2 => {{
                                            if (res2.ok) {{
                                                let audio2 = new Audio(customMp3UrlUpper);
                                                audio2.volume = 1.0;
                                                audio2.play().catch(() => {{}});
                                            }} else {{
                                                playDefaultSynthesized(sndType);
                                            }}
                                        }}).catch(() => {{
                                            playDefaultSynthesized(sndType);
                                        }});
                                }});
                        }}
                    }}

                    function getSoundDuration(sndType) {{
                        if (!sndType) return 0;
                        if (sndType === 'submarine_sonar') return 2.2;
                        if (sndType === 'morse_sos') return 2.2;
                        if (sndType === 'naval_horn') return 2.8;
                        if (sndType === 'success') return 0.6;
                        if (sndType === 'warning') return 0.6;
                        if (sndType === 'alert') return 0.7;
                        if (sndType === 'chime_simple') return 0.9;
                        if (sndType === 'bell_ring') return 1.1;
                        if (sndType === 'digital_warning') return 0.7;
                        if (sndType === 'info') return 0.6;
                        if (sndType.startsWith('naval_bell_')) {{
                            let count = 1;
                            if (sndType === 'naval_bell_singela') {{
                                count = 1;
                            }} else if (sndType === 'naval_bell_dobrada') {{
                                count = 2;
                            }} else {{
                                count = parseInt(sndType.split('_')[2]) || 1;
                            }}
                            let pairs = Math.floor(count / 2);
                            let remainder = count % 2;
                            let lastStrikeTime = 0;
                            if (pairs > 0) {{
                                lastStrikeTime = (pairs - 1) * 2.0 + 0.15;
                            }}
                            if (remainder > 0) {{
                                lastStrikeTime = pairs * 2.0;
                            }}
                            return lastStrikeTime + 3.5;
                        }}
                        return 3.0; // estimativa padrão para MP3 customizados
                    }}

                    let voiceDelay = 0; // delay em milissegundos
                    
                    if (ctx && playSound && type !== 'silent') {{
                        if (ctx.state === 'suspended') {{
                            ctx.resume();
                        }}
                        
                        let sequence = [];
                        if (Array.isArray(type)) {{
                            sequence = type;
                        }} else if (typeof type === 'string') {{
                            try {{
                                let parsed = JSON.parse(type);
                                if (Array.isArray(parsed)) {{
                                    sequence = parsed;
                                }} else {{
                                    sequence = [{{som: type, delay: 0}}];
                                }}
                            }} catch(e) {{
                                sequence = [{{som: type, delay: 0}}];
                            }}
                        }} else {{
                            sequence = [{{som: String(type), delay: 0}}];
                        }}

                        let accumulatedDelay = 0;
                        let soundEndTime = 0;
                        
                        sequence.forEach(item => {{
                            let som = 'info';
                            let delay = 0;
                            if (typeof item === 'object' && item !== null) {{
                                som = item.som || 'info';
                                delay = parseFloat(item.delay) || 0;
                            }} else {{
                                som = String(item);
                            }}
                            accumulatedDelay += delay;
                            setTimeout(() => {{
                                playSingleSound(som);
                            }}, accumulatedDelay * 1000);
                            
                            let itemDuration = getSoundDuration(som);
                            let finishTime = accumulatedDelay + itemDuration;
                            if (finishTime > soundEndTime) {{
                                soundEndTime = finishTime;
                            }}
                        }});
                        
                        // A voz deve aguardar o fim da sequência de sons para iniciar (som + folga de 0.5s)
                        voiceDelay = (soundEndTime + 0.5) * 1000;
                    }}

                    if (playVoice) {{
                        let audioBase64 = {escaped_audio};
                        if (audioBase64 && audioBase64 !== "null" && audioBase64 !== "") {{
                            setTimeout(() => {{
                                console.log("[TV ALERT JS] Reproduzindo áudio ElevenLabs/Google (Base64)...");
                                let mimeType = audioBase64.startsWith("UklGR") ? "audio/wav" : "audio/mp3";
                                let audio = new Audio("data:" + mimeType + ";base64," + audioBase64);
                                audio.volume = 1.0;
                                audio.play().catch(e => console.error("[TV ALERT JS] Erro ao tocar áudio ElevenLabs:", e));
                            }}, voiceDelay);
                        }} else {{
                            let text = {escaped_jarvis};
                            if (!text || text === "null" || text === "") {{
                                text = {escaped_vocativo} + ". " + {escaped_msg};
                            }}
                            console.log("[TV ALERT JS] Usando SpeechSynthesis (Local) para falar:", text);
                            
                            let getBestVoice = () => {{
                                let voices = window.speechSynthesis.getVoices();
                                let preferredName = {escaped_basic_voice};
                                if (preferredName) {{
                                    let pref = voices.find(v => v.name === preferredName);
                                    if (pref) return pref;
                                }}
                                
                                let ptVoices = voices.filter(v => {{
                                    let l = v.lang.toLowerCase();
                                    return l.includes('pt-br') || l.includes('pt_br') || l === 'pt';
                                }});
                                
                                let naturalMale = ptVoices.find(v => {{
                                    let name = v.name.toLowerCase();
                                    return (name.includes('natural') || name.includes('online') || name.includes('neural')) && 
                                           (name.includes('valerio') || name.includes('antonio') || name.includes('fabio') || name.includes('male') || name.includes('daniel'));
                                }});
                                if (naturalMale) return naturalMale;
                                
                                let googlePt = ptVoices.find(v => v.name.toLowerCase().includes('google'));
                                if (googlePt) return googlePt;
                                
                                let anyNatural = ptVoices.find(v => v.name.toLowerCase().includes('natural') || v.name.toLowerCase().includes('online') || v.name.toLowerCase().includes('neural'));
                                if (anyNatural) return anyNatural;
                                
                                let localMale = ptVoices.find(v => {{
                                    let name = v.name.toLowerCase();
                                    return name.includes('daniel') || name.includes('antonio') || name.includes('male') || name.includes('felipe');
                                }});
                                if (localMale) return localMale;
                                
                                return ptVoices.length > 0 ? ptVoices[0] : null;
                            }};

                            setTimeout(() => {{
                                window.speechSynthesis.cancel();
                                let utterance = new SpeechSynthesisUtterance(text);
                                utterance.lang = 'pt-BR';
                                let bestVoice = getBestVoice();
                                if (bestVoice) {{
                                    console.log("[TV ALERT JS] Utilizando voz do navegador selecionada:", bestVoice.name);
                                    utterance.voice = bestVoice;
                                }} else {{
                                    console.log("[TV ALERT JS] Voz favorita indisponível. Utilizando padrão do navegador pt-BR.");
                                }}
                                utterance.onerror = (err) => console.error("[TV ALERT JS] Erro na síntese de voz (SpeechSynthesis):", err);
                                window.speechSynthesis.speak(utterance);
                            }}, voiceDelay);
                        }}
                    }}
                }} catch(e) {{
                    console.error(e);
                }}
                """
                client.run_javascript(js_code)
        except Exception as e:
            print(f"[TV Alerta] Erro ao abrir diálogo no cliente: {e}")
            
        if visual_alert:
            from services import data_service
            try:
                tempo_cfg = data_service.get_config_value('tempo_alerta_tv', '10')
                total_duration = float(tempo_cfg)
            except Exception:
                total_duration = 10.0
            
            try:
                await asyncio.sleep(total_duration)
                with client:
                    tactical_dialog.close()
            except Exception as e:
                print(f"[TV Alerta] Erro ao fechar diálogo no cliente: {e}")
        else:
            # Apenas reprodução de áudio: aguarda tempo menor antes de liberar a fila
            await asyncio.sleep(6.0)


    async def _refresh():
        try:
            try:
                active_year = app.storage.user.get('ano_letivo_ativo', default_active_year)
            except Exception:
                active_year = default_active_year
            # Executa a busca no banco em outra thread para evitar o travamento da thread principal (WebSocket heartbeat)
            d = await asyncio.to_thread(_carregar_dados_tv, None, active_year)
            with client:

                # Atualiza título do cabeçalho
                title_lbl.set_text(str(d.get('cabecalho_tv_title') or 'SITUAÇÃO CONSOLIDADA DO CORPO DE ALUNOS').upper())

                # Status de Conectividade
                if d['is_offline']:
                    status_dot.props('color=amber-9')
                    status_lbl.set_text('LOCAL DEMO')
                    status_lbl.classes('text-amber-500', remove='text-green-500')
                else:
                    status_dot.props('color=green')
                    status_lbl.set_text('ONLINE')
                    status_lbl.classes('text-green-500', remove='text-amber-500')

                # --- REDESENHO DA TELA ---
                current_tv_data['d'] = d
                render_servico_diario_card.refresh()

                # 2. Painel de Quantitativos (KPIs 4x2)
                quant_container.clear()
                with quant_container:
                    def build_mini_kpi(val, label, color, icon, subtext=None):
                        # Se houver pendentes na chamada, aplica uma borda pulsante âmbar no KPI de ausentes
                        border_color = 'border-amber-500 animate-pulse' if subtext and label == 'Ausentes/Faltas' else 'border-gray-900'
                        with ui.card().classes(f'items-center text-center border {border_color}').style(
                            f'background:#050505; border-top: 3px solid {color}; flex: 1 1 0; min-width: 60px; margin: 0; padding: 4px !important; display: flex; flex-direction: column; justify-content: center; min-height: 0; height: 100%;'
                        ):
                            with ui.row().classes('items-center justify-center gap-1 no-wrap w-full'):
                                ui.icon(icon, color='grey-6', size='0.9rem')
                                ui.label(label).classes('kpi-label')
                            with ui.row().classes('items-center justify-center gap-1 w-full no-wrap'):
                                ui.label(str(val)).classes('kpi-value').style(f'color: {color}; margin-top: 2px;')
                            if subtext:
                                ui.label(subtext).classes('text-amber-5 text-[10px] font-black animate-pulse mt-0.5')
                
                    baixados_count = len([x for x in d['saude_ativos'] if x['categoria'] == 'enfermaria'])
                    dispensados_count = len([x for x in d['saude_ativos'] if x['categoria'] == 'dispensa'])
                    hospital_count = len([x for x in d['saude_ativos'] if x['categoria'] == 'hospital'])
                    licenciados_count = len(d.get('licencas_ativas', []))
                
                    if d['is_offline']:
                        ausentes_count = d['total_alunos'] - d['presentes_hoje']
                    else:
                        ausentes_count = d.get('ausentes_hoje', 0)
                    pernoite_count = d.get('pernoite_count', 0)
                    atletas_count = d.get('atletas_count', 0)
                    fora_sede_count = d.get('fora_sede_count', 0)
                    pendentes_val = d.get('pendentes_count', 0)

                    # Linha 1: Efetivo, Presentes, Ausentes/Faltas, Licenças Autorizadas
                    with ui.row().classes('w-full gap-1 justify-between no-wrap').style('flex: 1; min-height: 0;'):
                        build_mini_kpi(d['total_alunos'], 'Efetivo', '#D4AF37', 'groups')
                        build_mini_kpi(d['presentes_hoje'], 'Presentes', '#4CAF50', 'how_to_reg')
                        sub_str = None
                        if pendentes_val > 0:
                            mikes_list = d.get('pendentes_mikes', [])
                            if mikes_list:
                                sub_str = f"{pendentes_val} PEND: {', '.join(mikes_list)}"
                            else:
                                sub_str = f"{pendentes_val} SEM CHAMADA"
                        build_mini_kpi(ausentes_count, 'Ausentes/Faltas', '#F44336', 'person_off', subtext=sub_str)
                        build_mini_kpi(licenciados_count, 'Licenças Autorizadas', '#2196F3', 'flight_takeoff')
                
                    # Linha 2: Enfermaria, Dispensados, Pernoite, Atletas, Fora de S. Sem.
                    with ui.row().classes('w-full gap-1 justify-between no-wrap').style('flex: 1; min-height: 0;'):
                        build_mini_kpi(baixados_count + hospital_count, 'Enfermaria', '#E91E63', 'local_hospital')
                        build_mini_kpi(dispensados_count, 'Dispensados', '#FF9800', 'event_busy')
                        build_mini_kpi(pernoite_count, 'Pernoite', '#00BCD4', 'nightlight')
                        build_mini_kpi(atletas_count, 'Atletas', '#9C27B0', 'directions_run')
                        build_mini_kpi(fora_sede_count, 'Fora de S. Sem.', '#FFEB3B', 'explore')

                # 3. Anotações do Dia (Ações dos Alunos com cores positivo/negativo/neutro)
                render_anotacoes_card_content.refresh()

                # 3.1 Ticker horizontal de avisos
                ticker_container.clear()
                with ticker_container:
                    avisos = d.get('avisos_letreiro', [])
                    if avisos:
                        ticker_text = '  •  '.join(avisos) + '  •  '
                        with ui.row().classes('ticker-wrapper'):
                            ui.html(f'<div class="ticker-content" style="color: #F59E0B; font-size: 1.5rem; font-weight: bold; letter-spacing: 1px;">{ticker_text}</div>')
                            ui.html(f'<div class="ticker-content" style="color: #F59E0B; font-size: 1.5rem; font-weight: bold; letter-spacing: 1px;">{ticker_text}</div>')

                # 4. Enfermaria / Dispensas (Marquee Vertical)
                # Somente baixados e hospitalizados contam no totalizador da enfermaria
                baixados_efetivos = [x for x in d['saude_ativos'] if x['categoria'] in ['enfermaria', 'hospital']]
                # Ordena por horário de inclusão (criado_em desc, depois id desc)
                baixados_efetivos = sorted(
                    baixados_efetivos,
                    key=lambda x: (x.get('criado_em') or '', x.get('id') or 0),
                    reverse=True
                )
                enfermaria_total_lbl.set_text(f"TOTAL: {len(baixados_efetivos)}")
                enfermaria_marquee_div.clear()

                with enfermaria_marquee_div:
                    if not baixados_efetivos:
                        with ui.card().classes('w-full q-pa-sm items-center justify-center bg-gray-900 border border-gray-800'):
                            ui.icon('health_and_safety', color='green', size='2.5rem')
                            ui.label('ENFERMARIA SEM ALUNOS BAIXADOS').classes('text-green-500 font-bold text-[18px]')
                    else:
                        use_marquee = len(baixados_efetivos) > 4
                        classes_inner = 'health-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1'
                        
                        with ui.column().classes(classes_inner):
                            with ui.grid(columns=2).classes('w-full gap-1.5'):
                                for item in baixados_efetivos:
                                    cat = item.get('categoria') or 'enfermaria'
                                    status = item.get('status') or 'Baixado'
                                    motivo = item.get('motivo') or 'Sem motivo informado'
                                    detalhe = item.get('detalhe') or ''
                                
                                    # Get status info color - com fallback inteligente por substring
                                    cor, bg_rgba, ico = STATUS_INFO.get(status, ('#ff1744', 'rgba(255, 23, 68, 0.15)', 'local_hospital'))
                                    if status not in STATUS_INFO:
                                        for key, val_info in STATUS_INFO.items():
                                            if key.lower() in status.lower() or status.lower() in key.lower():
                                                cor, bg_rgba, ico = val_info
                                                break
                                
                                    border_color_style = f'border: 1px solid {cor} !important;'
                                    indicator_color_style = f'background-color: {cor} !important;'
                                    label_cat = str(status).upper()
                                    if label_cat in ['EM OBSERVAÇÃO', 'OBSERVAÇÃO', 'OBSERVACAO', 'EM OBSERVACAO', 'ENCAMINHADO PARA ENFERMARIA']:
                                        label_cat = 'ENCAMINHADO PARA ENFERMARIA'
                                    text_cat_color_style = f'color: {cor} !important;'
                                    bg_card = f'background: {bg_rgba};'
                                    is_hospital = status.lower() == 'hospital'
                                    desc_extra = (detalhe if detalhe else 'Hospital') if is_hospital else ''

                                    item_turma = str(item.get('turma') or 'N/A').upper()
                                    item_nome = str(item.get('nome') or 'MILITAR').upper()

                                    with ui.card().classes(f'w-full q-pa-xs q-mb-xs').style(f'{bg_card} {border_color_style} margin-bottom: 4px; gap: 2px !important; padding: 6px !important;'):
                                        with ui.row().classes('w-full items-center justify-between px-1'):
                                            with ui.row().classes('items-center gap-1.5'):
                                                ui.element('span').classes(f'w-1.5 h-1.5 rounded-full').style(indicator_color_style)
                                                # Exibe somente Número Interno (NI) e Nome de Guerra (sem Platoon/Mike-1!)
                                                item_ni = str(item.get('ni') or '').upper()
                                                if item_ni:
                                                    ui.label(item_ni).classes('text-grey-5 font-mono text-[15px]')
                                                ui.label(item_nome).classes('text-white font-black text-[15px] tracking-wider')
                                            ui.label(label_cat).classes(f'font-bold text-[13px] tracking-wider').style(text_cat_color_style)
                                    
                                        with ui.row().classes('w-full justify-between items-baseline px-1 text-[14px] text-grey-3').style('margin-top: -2px;'):
                                            ui.label(motivo).classes('text-white font-bold text-[14px]')
                                            if desc_extra:
                                                ui.label(desc_extra).classes('text-grey-4 font-bold text-[13px]')

                # 5. Licenciados e Dispensados (Marquee Vertical)
                lic_disp_marquee_div.clear()
                lic_disp_list = []
            
                # Licenças
                for lic in d.get('licencas_ativas', []):
                    retorno_data = lic.get('data_fim')
                    retorno_str = '--/--'
                    if retorno_data:
                        try:
                            retorno_str = datetime.strptime(str(retorno_data), '%Y-%m-%d').strftime('%d/%m')
                        except Exception:
                            retorno_str = str(retorno_data)
                
                    cor, bg_rgba, ico = STATUS_INFO.get('Licença', ('#00e5ff', 'rgba(0, 229, 255, 0.15)', 'beach_access'))
                    lic_disp_list.append({
                        'ni': str(lic.get('ni') or '').upper(),
                        'turma': str(lic.get('turma') or 'N/A').upper(),
                        'nome': str(lic.get('nome') or 'MILITAR').upper(),
                        'motivo': str(lic.get('motivo') or 'Sem motivo informado'),
                        'detalhe': str(lic.get('detalhe') or '').upper(),
                        'tipo': 'LICENÇA',
                        'retorno': retorno_str,
                        'color_tag': f'color: {cor}; border-color: {cor}; background: {bg_rgba};'
                    })
                
                # Dispensas
                for disp in d.get('saude_ativos', []):
                    if disp.get('categoria') == 'dispensa':
                        retorno_data = disp.get('data_fim')
                        retorno_str = '--/--'
                        if retorno_data:
                            try:
                                retorno_str = datetime.strptime(str(retorno_data), '%Y-%m-%d').strftime('%d/%m')
                            except Exception:
                                retorno_str = str(retorno_data)
                    
                        cor, bg_rgba, ico = STATUS_INFO.get('Dispensado', ('#00b0ff', 'rgba(0, 176, 255, 0.15)', 'medical_services'))
                        lic_disp_list.append({
                            'ni': str(disp.get('ni') or '').upper(),
                            'turma': str(disp.get('turma') or 'N/A').upper(),
                            'nome': str(disp.get('nome') or 'MILITAR').upper(),
                            'motivo': str(disp.get('motivo') or 'Sem motivo informado'),
                            'detalhe': str(disp.get('detalhe') or '').upper(),
                            'tipo': 'DISPENSA',
                            'retorno': retorno_str,
                            'color_tag': f'color: {cor}; border-color: {cor}; background: {bg_rgba};'
                        })

                with lic_disp_marquee_div:
                    if not lic_disp_list:
                        with ui.card().classes('w-full q-pa-sm items-center justify-center bg-gray-900/30 border border-gray-800/50'):
                            ui.icon('health_and_safety', color='green', size='2.5rem')
                            ui.label('SEM LICENÇAS OU DISPENSAS HOJE').classes('text-green-500 font-bold text-[18px]')
                    else:
                        use_marquee = len(lic_disp_list) > 2
                        classes_inner = 'health-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1'
                        items_marquee = lic_disp_list

                        with ui.column().classes(classes_inner):
                            for item in items_marquee:
                                with ui.card().classes('w-full q-pa-xs border q-mb-xs').style('background: rgba(255,255,255,0.01); border-color: rgba(255, 255, 255, 0.05); margin-bottom: 3px;'):
                                    with ui.row().classes('w-full items-center justify-between px-1 hover:bg-white/5'):
                                        with ui.row().classes('items-center gap-1.5'):
                                            # Exibe somente Número Interno (NI) e Nome de Guerra (sem Platoon/Mike-1!)
                                            if item['ni']:
                                                ui.label(item['ni']).classes('text-grey-5 font-mono text-[16px]')
                                            ui.label(item['nome']).classes('text-white font-black text-[16px]')
                                        ui.label(item['tipo']).classes(f"px-1 py-0.2 rounded border text-[13px] font-bold").style(item['color_tag'])
                                    
                                    with ui.row().classes('w-full justify-between items-baseline px-1 text-[16px] text-grey-3'):
                                        ui.label(f"TÉRMINO: {item['retorno']}").style(item['color_tag'].split(';')[0])
                                        if item.get('detalhe'):
                                            ui.label(item['detalhe']).classes('text-white font-black text-[15px]')

                # 6. Programação do Dia (Atividades) - Lado direito (1/3 width)
                atividades_marquee_container.clear()
            
                with atividades_marquee_container:
                    if not d['atividades_dia']:
                        with ui.card().classes('w-full q-pa-md items-center justify-center bg-gray-900/30 border border-gray-800/50'):
                            ui.label('SEM ATIVIDADES CADASTRADAS PARA HOJE').classes('text-grey-5 font-bold text-[16px]')
                    else:
                        use_marquee = len(d['atividades_dia']) > 8
                        classes_inner = 'activities-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1 overflow-y-auto'
                        items_marquee = d['atividades_dia'] * 2 if use_marquee else d['atividades_dia']
 
                        with ui.column().classes(classes_inner).style('max-height: 100%;' if not use_marquee else ''):
                            for act in items_marquee:
                                is_concluida = act.get('status') == 'Concluído'
                                left_border_color = 'border-l-4 border-green-500' if is_concluida else 'border-l-4 border-amber-500'
                                bg_card = 'background: rgba(76, 175, 80, 0.04);' if is_concluida else 'background: rgba(245, 158, 11, 0.04);'
                            
                                with ui.card().classes(f'w-full p-1.5 border border-gray-800 {left_border_color} mb-1').style(f'{bg_card}'):
                                    with ui.column().classes('w-full gap-1'):
                                        # Linha 1: Horário completo e Local
                                        with ui.row().classes('w-full justify-between items-center no-wrap'):
                                            raw_time = str(act.get('horario', '--:--'))
                                            ui.label(raw_time).style('color: #F59E0B; font-size: 14px; font-weight: 900; font-family: monospace;')
                                            ui.label(act.get('local', 'N/A').upper()).classes('px-1.5 py-0.5 bg-black/40 border border-grey-900 rounded font-mono text-[12px] text-grey-4 max-w-[65%] ellipsis')
                                    
                                        # Linha 2: Descrição da Atividade (com fonte menor)
                                        with ui.row().classes('w-full items-start gap-2'):
                                            ui.label(act.get('descricao', '')).classes('text-white font-bold col-grow text-[13px]').style('white-space: normal; word-break: break-word;')
                                        
                                        # Linha 3: Responsável abaixo
                                        with ui.row().classes('w-full justify-end items-center gap-1'):
                                            ui.label(f"👮 {act.get('responsavel', 'N/A')}").classes('text-grey-4 font-medium text-[11px] ellipsis max-w-[80%]')

                # Ajusta o timer dinamicamente com base nas configurações
                polling_interval = d.get('polling_interval', 300.0)
                refresh_timer.interval = polling_interval

        except Exception as e:
            print(f"[TV] Erro ao renderizar atualização do Modo TV: {e}")

    # Inicializa Timers e Fila de Alertas
    ui.timer(1.0, _update_clock)
    
    # Criamos o timer com valor inicial que depois será ajustado dinamicamente
    refresh_timer = ui.timer(300.0, _refresh)

    def toggle_card_view():
        if hovering_card['value']:
            return
        if current_tv_data['d'] is not None:
            active_card_view['index'] = (active_card_view['index'] + 1) % 3
            render_servico_diario_card.refresh()
            
            # Rotaciona visualização do card de anotações (Lista / Estatísticas)
            active_notes_view['show_stats'] = not active_notes_view['show_stats']
            render_anotacoes_card_content.refresh()

    ui.timer(10.0, toggle_card_view)
    
    # Variável para rastrear o loop de processamento da fila
    queue_task = None
    queue_health_check_counter = {'value': 0}

    def on_connect_setup():
        nonlocal queue_task
        from alerts_manager import AlertsManager
        
        # Garante que a fila de processamento esteja rodando
        if queue_task is None or queue_task.done():
            queue_task = asyncio.create_task(_process_toast_queue())
            print(f"[TV] [OK] Loop de fila iniciado/RESTAURADO (Client: {client.id})")
            queue_health_check_counter['value'] = 0
        else:
            print(f"[TV] [OK] Fila ja esta ativa (Client: {client.id})")
            
        # Registra a TV no AlertsManager para receber notificações em tempo real
        AlertsManager.register_tv_callback(client, trigger_toast)
        # Sincroniza o estado atual das preferências de som/voz
        AlertsManager.update_tv_preferences(client.id, voice=audio_config['voice'], sound=audio_config['sound'])
        print(f"[TV] [OK] TV CONECTADA e pronta para alertas (Client: {client.id})")
        # Força uma atualização imediata ao conectar/reconectar
        asyncio.create_task(_refresh())

    def on_disconnect_cleanup():
        nonlocal queue_task
        from alerts_manager import AlertsManager
        
        # Remove a TV do AlertsManager
        AlertsManager.unregister_tv_callback(client.id)
        
        # Cancela o loop de processamento da fila para evitar vazamento de memória
        if queue_task is not None and not queue_task.done():
            queue_task.cancel()
            print(f"[TV] [X] Fila cancelada (desconexao final, Client: {client.id})")
        
    def _health_check_queue():
        """Verifica a cada 5s se a fila está viva; se morrer, reconecta."""
        nonlocal queue_task
        if queue_task is None or queue_task.done():
            print(f"[TV] [WARN] Fila esta MORTA! Reiniciando... (Client: {client.id})")
            queue_task = asyncio.create_task(_process_toast_queue())
    
    client.on_connect(on_connect_setup)
    client.on_disconnect(lambda: print(f"[TV] ⚠ Desconexão (reconexão em andamento, Client: {client.id})"))
    client.on_delete(on_disconnect_cleanup)
    
    # Timer de health check: verifica se a fila morreu (a cada 5 segundos)
    ui.timer(5.0, _health_check_queue)
    
    # Executa setup imediatamente se já estiver conectado (evita race condition de websocket)
    if client.has_socket_connection:
        print(f"[TV] → Setup imediato (já conectado, Client: {client.id})")
        on_connect_setup()
    
    # Elemento visual flutuante para desbloquear áudio (Autoplay policy)
    ui.html("""
    <div id="sound-banner-alert" style="
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(239, 68, 68, 0.15);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 2px solid rgba(239, 68, 68, 0.5);
        box-shadow: 0 0 25px rgba(239, 68, 68, 0.3);
        padding: 14px 28px;
        border-radius: 12px;
        z-index: 99999;
        color: #fff;
        font-family: monospace;
        font-size: 14px;
        font-weight: bold;
        text-align: center;
        cursor: pointer;
        pointer-events: auto;
        animation: alert-pulse 2s infinite;
        display: flex;
        align-items: center;
        gap: 10px;
    ">
        <span style="font-size: 20px;">🔊</span>
        <span>SOM DESATIVADO: Clique em qualquer lugar da tela para ativar os alertas e anúncios por voz.</span>
    </div>
    <style>
    @keyframes alert-pulse {
        0% { opacity: 0.8; box-shadow: 0 0 10px rgba(239, 68, 68, 0.3); }
        50% { opacity: 1; box-shadow: 0 0 25px rgba(239, 68, 68, 0.6); border-color: rgba(239, 68, 68, 0.8); }
        100% { opacity: 0.8; box-shadow: 0 0 10px rgba(239, 68, 68, 0.3); }
    }
    </style>
    """)
    
    # Executa primeiro refresh imediato
    asyncio.create_task(_refresh())
