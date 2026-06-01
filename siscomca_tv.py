"""
MODO TV TÁTICO — SisCOMCA
Painel de Altíssima Visibilidade para Projeção em Monitor/TV de 60"
Otimizado para leitura a 5 metros de distância (fontes massivas, contraste extremo)
"""

from nicegui import ui, app
import pandas as pd
from datetime import datetime
import asyncio
import theme
from database import get_db_connection, load_data

THEME = theme.colors

STATUS_INFO = {
    'Internado':      ('#ff1744', 'rgba(255, 23, 68, 0.15)', 'local_hospital'),
    'Em Observação':  ('#ff9100', 'rgba(255, 145, 0, 0.15)', 'visibility'),
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
    0% { transform: translateY(0); }
    100% { transform: translateY(-50%); }
}
@keyframes ticker-scroll {
    0% { transform: translateX(0); }
    100% { transform: translateX(-100%); }
}
.health-marquee-container {
    display: flex;
    flex-direction: column;
    animation: marquee-vertical 30s linear infinite;
}
.health-marquee-container:hover {
    animation-play-state: paused;
}
.activities-marquee-container {
    display: flex;
    flex-direction: column;
    animation: marquee-vertical 300s linear infinite;
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
    font-size: clamp(1.5rem, 3vw, 3.5rem);
}
.kpi-label {
    font-weight: bold;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-size: clamp(0.4rem, 0.7vw, 0.7rem);
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


def _carregar_dados_tv():
    """Carrega dados consolidados do Supabase para o Modo TV com fallbacks offline robustos."""
    db_conn = get_db_connection()
    hoje_str = datetime.now().strftime('%Y-%m-%d')
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
        'inspetor_dia': {'nome': 'NÃO ESCALADO', 'photo_url': 'https://cdn.quasar.dev/img/boy-avatar.png'},
        'outros_escalados': [],
        'anotacoes_dia': [],
        'avisos_letreiro': [],
        'atividades_dia': [],
        'cabecalho_tv_title': cabecalho_title,
        'pernoite_count': 0,
        'is_offline': is_offline
    }

    # 1. Alunos e Efetivo Geral
    alunos_df = pd.DataFrame()
    if db_conn:
        try:
            res_al = db_conn.table('Alunos').select('id,numero_interno,nome_guerra,pelotao').execute()
            alunos_df = pd.DataFrame(res_al.data) if res_al.data else pd.DataFrame()
        except Exception as e:
            print(f"[TV] Erro Alunos: {e}")
    
    if is_offline or (not db_conn and alunos_df.empty):
        # Fallback Mock
        alunos_data = [
            {'id': 1, 'numero_interno': 'M-1-101', 'nome_guerra': 'GUILHERME', 'pelotao': 'MIKE-1'},
            {'id': 2, 'numero_interno': 'M-1-102', 'nome_guerra': 'SILVA', 'pelotao': 'MIKE-1'},
            {'id': 3, 'numero_interno': 'M-2-207', 'nome_guerra': 'MARTINS', 'pelotao': 'MIKE-2'},
            {'id': 4, 'numero_interno': 'M-2-208', 'nome_guerra': 'ALBUQUERQUE', 'pelotao': 'MIKE-2'},
            {'id': 5, 'numero_interno': 'M-3-301', 'nome_guerra': 'GOMES', 'pelotao': 'MIKE-3'}
        ]
        alunos_df = pd.DataFrame(alunos_data)

    dados['total_alunos'] = len(alunos_df)

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
            elif status in ['Internado', 'Em Observação', 'baixado']:
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
            escala_map[row['cargo'].upper()] = row['nome']

    # 4.1 Inspetor do Dia
    inspetor_nome = escala_map.get('INSPETOR DO DIA', escala_map.get('INSPETOR', ''))
    if not inspetor_nome:
        inspetor_nome = 'Cap. Calaça' if is_offline else 'NÃO ESCALADO'

    dados['inspetor_dia'] = {
        'nome': inspetor_nome.upper(),
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
    dados['osca_servico'] = escala_map.get('OSCA', 'Cap. Calaça' if is_offline else 'NÃO ESCALADO').upper()
    dados['ajosca_servico'] = escala_map.get('AJOSCA', 'Ten. Santos' if is_offline else 'NÃO ESCALADO').upper()

    # 4.3 Outros Escalados (excluindo Inspetor, OSCA e AJOSCA)
    excluir_cargos = {'INSPETOR DO DIA', 'INSPETOR', 'OSCA', 'AJOSCA'}
    dados['outros_escalados'] = []
    for cargo in cargos_config:
        cargo_upper = cargo.upper()
        if cargo_upper in excluir_cargos:
            continue
        nome_cargo = escala_map.get(cargo_upper, escala_map.get(cargo, 'Maj. Lima' if is_offline and cargo_upper == 'SUPERVISOR' else 'NÃO ESCALADO'))
        dados['outros_escalados'].append({
            'cargo': cargo.upper(),
            'nome': nome_cargo.upper()
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
                        texto += f" (Inserido por: {autor})"
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
                    texto += f" (Inserido por: {autor})"
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
            ni_prefix = f"{aluno['ni']} — " if aluno and aluno['ni'] else ""
            nome_aluno = aluno['nome'] if aluno else 'MILITAR'
            pelotao_aluno = f" ({aluno['pelotao']})" if aluno and aluno['pelotao'] else ""
            tipo = str(ac.get('tipo', 'Anotação')).upper()
            desc = ac.get('descricao', '')
            desc_str = f" — {desc}" if desc else ""
            
            tipo_acao_id = str(ac.get('tipo_acao_id', ''))
            pts = tipos_map.get(tipo_acao_id, 0.0)
            
            anotacoes_dia_list.append({
                'texto': f"{ni_prefix}{nome_aluno}{pelotao_aluno}: {tipo}{desc_str}",
                'status': ac.get('status', 'Lançado'),
                'pts': pts
            })

    if not anotacoes_dia_list:
        if is_offline:
            anotacoes_dia_list = [
                {'texto': 'SILVA (MIKE-1): ANOTAÇÃO — Destacou-se na instrução prática de hoje.', 'status': 'Lançado', 'pts': 0.5},
                {'texto': 'MARTINS (MIKE-2): OBSERVAÇÃO — Dispensado das atividades físicas por recomendação médica.', 'status': 'Pendente', 'pts': -0.3}
            ]
        else:
            anotacoes_dia_list = [{'texto': 'NÃO HÁ ANOTAÇÕES DE ALUNOS REGISTRADAS HOJE.', 'status': 'Lançado', 'pts': 0.0}]
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

    # 8. Pernoite (Alunos que dormiram a bordo autorizados)
    if db_conn:
        try:
            res_pn = db_conn.table('pernoite').select('*', count='exact').eq('data', hoje_str).eq('presente', True).execute()
            dados['pernoite_count'] = res_pn.count if res_pn.count else (len(res_pn.data) if res_pn.data else 0)
        except Exception as e:
            print(f"[TV] Erro Pernoite: {e}")

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

    client = ui.context.client

    # Container da Notificação Tática Flutuante
    toast_container = ui.column().classes('absolute-top w-full z-50 q-pa-md gap-2 pointer-events-none').style('top: 20px;')

    # Dialog de Alertas Táticos em Tempo Real (Criado uma vez no contexto correto)
    with ui.dialog() as tactical_dialog:
        ui.card() # Placeholder inicial

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
            ui.notify('Anotações ocultadas com sucesso!', color='warning')



    # Container Principal
    with ui.column().classes('w-full q-pa-sm gap-2').style('background:#000; height:100vh; overflow:hidden; display:flex; flex-direction:column;'):
        
        # ── CABEÇALHO TÁTICO ─────────────────────────────────────────────────────────
        with ui.row().classes('w-full items-center justify-between border-b-2 border-gray-900 q-pb-none'):
            # Esquerda: Relógio Grande + data
            with ui.column().classes('items-start gap-0'):
                clock_lbl = ui.label('--:--:--').style(
                    'color:#fff; font-size:2.4rem; font-weight:900; letter-spacing:4px; font-family:monospace; line-height:1;'
                )
                date_lbl = ui.label('').classes('text-amber-5 text-xs font-bold tracking-wider')

            # Centro: Título do Setor
            with ui.column().classes('items-center'):
                from services import data_service
                system_title = str(data_service.get_config_value('cabecalho_tv_title', 'SISTEMA C2') or 'SISTEMA C2').upper()
                title_lbl = ui.label(system_title).style(
                    f'color:{THEME["primary"]}; font-size:1.4rem; font-weight:900; letter-spacing:4px; line-height:1;'
                )
                ui.label('CORPO DE ALUNOS • COMANDO TÁTICO').classes(
                    'text-gray-500 text-xs font-bold tracking-widest'
                )

            # Direita: Status de Conectividade + Botão
            with ui.column().classes('items-end gap-1'):
                with ui.row().classes('items-center gap-2'):
                    status_dot = ui.icon('sensors', color='green').classes('text-2xl animate-pulse')
                    status_lbl = ui.label('ONLINE').classes('text-green-500 font-bold text-sm tracking-widest mr-2')
                    
                    # Criação dos botões primeiro para evitar referências futuras
                    sound_btn = ui.button().props('outline round dense icon=volume_up').style(f'color: {THEME["primary"]}; border: 1px solid {THEME["primary"]} !important;').classes('text-xs')
                    with sound_btn:
                        ui.tooltip('Ativar/Desativar som do sinal de alerta')
                        
                    voice_btn = ui.button().props('outline round dense icon=record_voice_over').style(f'color: {THEME["primary"]}; border: 1px solid {THEME["primary"]} !important;').classes('text-xs')
                    with voice_btn:
                        ui.tooltip('Ativar/Desativar leitura de voz do Jarvis')

                    # Definição das funções de callback
                    def toggle_sound():
                        audio_config['sound'] = not audio_config['sound']
                        icon = "volume_up" if audio_config["sound"] else "volume_off"
                        color = THEME["primary"] if audio_config["sound"] else "#64748b"
                        sound_btn.props(f'icon={icon}')
                        sound_btn.style(f'color: {color} !important; border-color: {color} !important;')
                        ui.notify(f'Som de chime {"ativado" if audio_config["sound"] else "desativado"}', color='info')
                        from alerts_manager import AlertsManager
                        AlertsManager.update_tv_preferences(client.id, sound=audio_config['sound'])
                    
                    def toggle_voice():
                        audio_config['voice'] = not audio_config['voice']
                        icon = "record_voice_over" if audio_config["voice"] else "voice_over_off"
                        color = THEME["primary"] if audio_config["voice"] else "#64748b"
                        voice_btn.props(f'icon={icon}')
                        voice_btn.style(f'color: {color} !important; border-color: {color} !important;')
                        ui.notify(f'Leitura de voz (Jarvis) {"ativada" if audio_config["voice"] else "desativada"}', color='info')
                        from alerts_manager import AlertsManager
                        AlertsManager.update_tv_preferences(client.id, voice=audio_config['voice'])

                    # Associa os callbacks aos botões
                    sound_btn.on_click(toggle_sound)
                    voice_btn.on_click(toggle_voice)

                with ui.row().classes('items-center gap-2'):
                    eye_btn = ui.button(
                        on_click=toggle_blur
                    ).props('flat round dense color=amber icon=visibility').classes('text-md')
                    ui.button(
                        'Retornar ao Dashboard', icon='arrow_back',
                        on_click=lambda: ui.navigate.to('/siscomca_dashboard')
                    ).props('outline color=grey dense no-caps').classes('text-xs text-grey-4')

        # ── CORPO PRINCIPAL DO PAINEL (GRID DUPLO) ─────────────────────────────
        with ui.element('div').classes('tv-main-row'):
            
            # === COLUNA ESQUERDA (1/5 - Serviço Diário + Anotações) ===
            with ui.element('div').classes('tv-left-col'):
                # Serviço Diário (Top, height: 42%) - Dividido permanentemente em 2 blocos
                with ui.element('div').classes('tv-panel border border-gray-800').style(
                    f'background: {THEME["bg_panel"]}; width: 100%; height: 42%; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; gap: 4px; padding: 6px;'
                ):
                    # 1. Bloco de Cima (Inspetor do Dia em Destaque) - 38% de altura
                    with ui.card().classes('w-full q-pa-xs border border-amber-900/40').style(
                        f'background: rgba(212, 175, 55, 0.03); height: 38%; display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 6px;'
                    ):
                        with ui.row().classes('w-full items-center justify-between px-2 no-wrap gap-2'):
                            # Esquerda: Avatar com brilho dourado
                            insp_avatar = ui.avatar(size='46px').style('border: 2px solid #D4AF37; box-shadow: 0 0 10px rgba(212, 175, 55, 0.4); shrink: 0;')
                            # Direita: Nome e Cargo
                            with ui.column().classes('gap-0.5 col-grow justify-center'):
                                ui.label('INSPETOR DO DIA').style(f'color: {THEME["primary"]}; font-size: 11px; font-weight: 900; letter-spacing: 2px; line-height: 1;')
                                insp_nome = ui.label('CARREGANDO...').classes('text-white text-[15px] font-black tracking-wider leading-none')
                            # Badge de status dinâmico
                            insp_badge = ui.label('DE SERVIÇO').classes('text-green-500 text-[10px] font-black tracking-widest animate-pulse border border-green-500/30 px-1 py-0.5 rounded')

                    # 2. Bloco de Baixo (Demais Serviços) - 62% de altura restante
                    with ui.card().classes('w-full q-pa-xs border border-gray-900/60').style(
                        'background: rgba(0,0,0,0.3); flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; border-radius: 6px;'
                    ):
                        with ui.row().classes('w-full items-center justify-between px-1 q-mb-xs border-b border-gray-900/80 q-pb-0.5'):
                            ui.label('👮 DEMAIS SERVIÇOS').classes('text-amber-5 text-[12px] font-black tracking-widest')
                            ui.badge('PRONTOS', color='green-9').classes('text-[10px] font-bold')
                            
                        # Div de rolagem para os demais serviços
                        escala_marquee_div = ui.column().classes('w-full').style('flex: 1; min-height: 0; overflow: hidden; position: relative;')

                # Anotações do Dia (Bottom, flex: 1 to fill remainder of Column 1)
                with ui.card().classes('q-pa-sm border border-gray-800 tv-panel').style(f'background: {THEME["bg_panel"]}; width: 100%; flex: 1; min-height: 0; transition: filter 0.3s ease;') as anotacoes_card:
                    with ui.column().classes('w-full gap-2 h-full'):
                        ui.label('📋 ANOTAÇÕES DO DIA').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center w-full')
                        ui.separator().props('dark')
                        anotacoes_container = ui.column().classes('w-full gap-1 overflow-y-auto text-grey-3 text-[18px]').style('flex: 1; min-height: 0;')

            # === COLUNA CENTRAL (3/5 - KPIs + Licenças/Dispensas + Enfermaria) ===
            with ui.element('div').classes('tv-center-col'):
                # KPIs 4x2 (Top, height: 42% - to align perfectly with Servicio Diario height!)
                quant_container = ui.column().classes('gap-2 justify-center').style('width: 100%; height: 42%; min-height: 0;')

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
                                ui.label('🏥 CONTROLE DE ENFERMARIA').classes('text-amber-5 text-[18px] font-bold tracking-widest text-center')
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
        """Atualiza o relógio a cada segundo."""
        now = datetime.now()
        clock_lbl.set_text(now.strftime('%H:%M:%S'))
        date_lbl.set_text(now.strftime('%A, %d de %B de %Y').upper())

    # Fila de notificações em tempo real (evita colisão de modais e sons)
    toast_queue = asyncio.Queue()


    async def trigger_toast(title, msg, type_='info', jarvis_text=None, jarvis_audio=None):
        """Enfileira o alerta em tempo real para ser exibido sequencialmente na TV."""
        await toast_queue.put((title, msg, type_, jarvis_text, jarvis_audio))

    async def _process_toast_queue():
        """Processa a fila de alertas sequencialmente, garantindo o tempo de exibição e sons."""
        while True:
            try:
                title, msg, type_, jarvis_text, jarvis_audio = await toast_queue.get()
                await _display_toast(title, msg, type_, jarvis_text, jarvis_audio)
                toast_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[TV Queue] Erro ao processar alerta: {e}")
                await asyncio.sleep(1)

    async def _display_toast(title, msg, type_='info', jarvis_text=None, jarvis_audio=None):
        """Gera um diálogo luminoso centralizado e ultra-premium na TV com Fade In/Out (máx 10 segundos)."""
        color_theme = {
            'info':    {'border': '#00e5ff', 'bg': '#000b1c', 'glow': 'rgba(0, 229, 255, 0.4)'},
            'success': {'border': '#00e676', 'bg': '#00140a', 'glow': 'rgba(0, 230, 118, 0.4)'},
            'alert':   {'border': '#ff1744', 'bg': '#190005', 'glow': 'rgba(255, 23, 68, 0.4)'},
            'warning': {'border': '#ff9100', 'bg': '#190a00', 'glow': 'rgba(255, 145, 0, 0.4)'}
        }
        cfg = color_theme.get(type_, color_theme['info'])
        
        import json
        escaped_title = json.dumps(title)
        escaped_msg = json.dumps(msg)
        escaped_jarvis = json.dumps(jarvis_text) if jarvis_text else "null"
        escaped_audio = json.dumps(jarvis_audio) if jarvis_audio else "null"
        
        try:
            with client:
                tactical_dialog.clear()
                tactical_dialog.props('persistent')
                with tactical_dialog:
                    dialog_card = ui.card().classes('q-pa-xl items-center text-center rounded-2xl border-4').style(
                        f"background: {cfg['bg']} !important; border-color: {cfg['border']} !important; "
                        f"box-shadow: 0 0 50px {cfg['glow']} !important; min-width: 700px; max-width: 90%; "
                        f"color: #fff; font-family: monospace; opacity: 0; transition: opacity 0.5s ease-in-out;"
                    )
                    with dialog_card:
                        icon_map = {
                            'success': 'stars',
                            'alert': 'gavel',
                            'warning': 'healing',
                            'info': 'campaign'
                        }
                        icon_name = icon_map.get(type_, 'info')
                        ui.icon(icon_name, size='7rem').style(f"color: {cfg['border']}; filter: drop-shadow(0 0 20px {cfg['glow']});").classes('animate-bounce')
                        ui.label(title.upper()).style(f"color: {cfg['border']}; font-size: 2.6rem; font-weight: 900; letter-spacing: 5px; line-height: 1.2;").classes('cyber-title q-mt-md')
                        ui.separator().style(f"background-color: {cfg['border']}; opacity: 0.4; height: 3px;").classes('w-3/4 q-my-md')
                        ui.label(msg).style("color: #ffffff; font-size: 2.2rem; font-weight: 900; line-height: 1.4; white-space: normal;")
                
                tactical_dialog.open()
                ui.timer(0.1, lambda: dialog_card.style('opacity: 1;'), once=True)
                
                play_sound_js = 'true' if audio_config['sound'] else 'false'
                play_voice_js = 'true' if audio_config['voice'] else 'false'

                # Toca o som (sintetizado via Web Audio API offline para evitar bloqueios de CORS/Internet)
                js_code = f"""
                try {{
                    const playSound = {play_sound_js};
                    const playVoice = {play_voice_js};

                    let ctx = window.globalAudioContext;
                    if (!ctx) {{
                        const AudioContext = window.AudioContext || window.webkitAudioContext;
                        if (AudioContext) {{
                            ctx = new AudioContext();
                            window.globalAudioContext = ctx;
                        }}
                    }}
                    if (ctx && playSound) {{
                        if (ctx.state === 'suspended') {{
                            ctx.resume();
                        }}
                        const type = '{type_}';
                        const customMp3Url = "/assets/sounds/" + type + ".mp3";
                        
                        if (type.startsWith('naval_bell_')) {{
                            let count = 1;
                            if (type === 'naval_bell_singela') {{
                                count = 1;
                            }} else if (type === 'naval_bell_dobrada') {{
                                count = 2;
                            }} else {{
                                count = parseInt(type.split('_')[2]) || 1;
                            }}
                            
                            const singleMp3Url = "/assets/sounds/bell_single.mp3";
                            const doubleMp3Url = "/assets/sounds/bell_double.mp3";
                            
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

                            fetch(singleMp3Url, {{ method: 'HEAD' }})
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
                                }})
                                .catch(() => {{
                                    playSynthesizedBells(ctx, count);
                                }});
                        }} else if (type === 'silent') {{
                            // Silencioso
                        }} else {{
                            fetch(customMp3Url, {{ method: 'HEAD' }})
                                .then(res => {{
                                    if (res.ok) {{
                                        let audio = new Audio(customMp3Url);
                                        audio.volume = 1.0;
                                        audio.play().catch(() => {{}});
                                    }} else {{
                                        playDefaultSynthesized(type);
                                    }}
                                }})
                                .catch(() => {{
                                    playDefaultSynthesized(type);
                                }});
                                
                            function playDefaultSynthesized(type) {{
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
                        }}.connect(ctx.destination);
                            osc2.type = 'sine';
                            osc2.frequency.setValueAtTime(800, ctx.currentTime + 0.08);
                            gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.08);
                            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.33);
                            osc2.start(ctx.currentTime + 0.08);
                            osc2.stop(ctx.currentTime + 0.38);
                        }}
                    }}
                    
                    // Síntese de voz estilo Jarvis com Leitura Realista (ElevenLabs ou Web Speech API)
                    const jarvisAudio = {escaped_audio};
                    if (playVoice && jarvisAudio && jarvisAudio !== "null") {{
                        try {{
                            let audioSrc = "data:audio/mp3;base64," + jarvisAudio;
                            let audioObj = new Audio(audioSrc);
                            audioObj.volume = 1.0;
                            setTimeout(() => {{
                                audioObj.play().catch(err => console.error("[JARVIS AUDIO] Erro ao reproduzir ElevenLabs:", err));
                            }}, 300);
                        }} catch(err) {{
                            console.error("[JARVIS AUDIO] Falha ao iniciar player de ElevenLabs:", err);
                        }}
                    }} else if (playVoice && 'speechSynthesis' in window) {{
                        window.speechSynthesis.cancel();
                        let rawTitle = {escaped_title};
                        let rawMsg = {escaped_msg};
                        let jarvisText = {escaped_jarvis};
                        let cleanText = (jarvisText ? jarvisText : (rawTitle + ". " + rawMsg))
                            .replace(/[\\u2700-\\u27BF]|[\\uE000-\\uF8FF]|\\uD83C[\\uDC00-\\uDFFF]|\\uD83D[\\uDC00-\\uDFFF]|[\\u2011-\\u26FF]|\\uD83E[\\uDC00-\\uDFFF]/g, '')
                            .trim();
                        let utterance = new SpeechSynthesisUtterance(cleanText);
                        utterance.lang = 'pt-BR';
                        
                        // Função interna para obter a melhor voz natural e realista (estilo Jarvis)
                        let getBestVoice = () => {{
                            let voices = window.speechSynthesis.getVoices();
                            let ptVoices = voices.filter(v => {{
                                let l = v.lang.toLowerCase();
                                return l.includes('pt-br') || l.includes('pt_br') || l === 'pt';
                            }});
                            
                            // 1. Tenta vozes masculinas naturais premium (Ex: Microsoft Valerio/Fabio Natural)
                            let naturalMale = ptVoices.find(v => {{
                                let name = v.name.toLowerCase();
                                return (name.includes('natural') || name.includes('online') || name.includes('neural')) && 
                                       (name.includes('valerio') || name.includes('antonio') || name.includes('fabio') || name.includes('male') || name.includes('daniel'));
                            }});
                            if (naturalMale) return naturalMale;
                            
                            // 2. Tenta Google português (Muito superior e limpa no Chrome, ex: Google português do Brasil)
                            let googlePt = ptVoices.find(v => v.name.toLowerCase().includes('google'));
                            if (googlePt) return googlePt;
                            
                            // 3. Tenta qualquer voz natural online pt-BR (qualquer gênero)
                            let anyNatural = ptVoices.find(v => v.name.toLowerCase().includes('natural') || v.name.toLowerCase().includes('online') || v.name.toLowerCase().includes('neural'));
                            if (anyNatural) return anyNatural;
                            
                            // 4. Tenta vozes masculinas locais do Windows (Daniel, Antonio, Felipe)
                            let localMale = ptVoices.find(v => {{
                                let name = v.name.toLowerCase();
                                return name.includes('daniel') || name.includes('antonio') || name.includes('male') || name.includes('felipe');
                            }});
                            if (localMale) return localMale;
                            
                            return ptVoices.length > 0 ? ptVoices[0] : null;
                        }};

                        let selectedVoice = getBestVoice();
                        if (selectedVoice) {{
                            utterance.voice = selectedVoice;
                            let isNatural = selectedVoice.name.toLowerCase().includes('natural') || 
                                            selectedVoice.name.toLowerCase().includes('online') || 
                                            selectedVoice.name.toLowerCase().includes('neural');
                            // Ajuste fino dinâmico de pitch e rate para sobriedade britânica (J.A.R.V.I.S.)
                            utterance.pitch = isNatural ? 0.94 : 0.82; // Tom mais grave e autoritário
                            utterance.rate = isNatural ? 0.90 : 0.93;  // Ritmo pausado, deliberado e formal
                        }} else {{
                            utterance.pitch = 0.82;
                            utterance.rate = 0.93;
                        }}
                        
                        // Dispara a fala com um pequeno atraso após o chime
                        setTimeout(() => {{
                            window.speechSynthesis.speak(utterance);
                        }}, 300);
                    }}
                }} catch(e) {{
                    console.error(e);
                }}
                """
                client.run_javascript(js_code)
        except Exception as e:
            print(f"[TV Alerta] Erro ao abrir diálogo no cliente: {e}")
            return
            
        await asyncio.sleep(9.4)
        
        try:
            with client:
                # Fade Out: Altera opacidade para 0
                dialog_card.style('opacity: 0;')
        except Exception:
            pass
            
        await asyncio.sleep(0.6) # Aguarda transição terminar
        
        try:
            with client:
                tactical_dialog.close()
        except Exception as e:
            print(f"[TV Alerta] Erro ao fechar diálogo no cliente: {e}")


    async def _refresh():
        try:
            # Executa a busca no banco em outra thread para evitar o travamento da thread principal (WebSocket heartbeat)
            d = await asyncio.to_thread(_carregar_dados_tv)
            with client:

                # Atualiza título do cabeçalho
                title_lbl.set_text(d.get('cabecalho_tv_title', 'SITUAÇÃO CONSOLIDADA DO CORPO DE ALUNOS').upper())

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
            
                # 1. Módulo do Inspetor do Dia
                insp_name_raw = d['inspetor_dia']['nome']
                is_insp_defined = "DEFINIDO" not in insp_name_raw.upper() and "ESCALADO" not in insp_name_raw.upper() and insp_name_raw.strip() != ""
                
                if is_insp_defined:
                    insp_nome.set_text(insp_name_raw.upper())
                    insp_nome.classes('text-white', remove='text-amber-5/70 italic')
                    insp_badge.set_text('DE SERVIÇO')
                    insp_badge.classes('text-green-500 border-green-500/30', remove='text-amber-500 border-amber-500/30')
                    insp_avatar.style(f"background-image: url('{d['inspetor_dia']['photo_url']}'); background-size: cover; background-position: center; border-color: #D4AF37;")
                else:
                    insp_nome.set_text('A DEFINIR')
                    insp_nome.classes('text-amber-5/70 italic', remove='text-white')
                    insp_badge.set_text('AGUARDANDO')
                    insp_badge.classes('text-amber-500 border-amber-500/30', remove='text-green-500 border-green-500/30')
                    insp_avatar.style("background-image: url('https://cdn.quasar.dev/img/boy-avatar.png'); background-size: cover; background-position: center; border-color: #ff9100;")

                # 1.1 Demais Serviços - Bloco de Baixo
                escala_marquee_div.clear()
                with escala_marquee_div:
                    outros_servicos = []
                    
                    # 1. OSCA
                    outros_servicos.append({'cargo': 'OSCA', 'nome': d.get('osca_servico', 'NÃO ESCALADO')})
                    # 2. AJOSCA
                    outros_servicos.append({'cargo': 'AJOSCA', 'nome': d.get('ajosca_servico', 'NÃO ESCALADO')})
                    # 3. Outros Escalados (Supervisor, Oficial, Enfermeiro, etc.)
                    for esc in d.get('outros_escalados', []):
                        outros_servicos.append({'cargo': esc['cargo'], 'nome': esc['nome']})

                    def is_defined(name: str) -> bool:
                        if not name:
                            return False
                        n = name.strip().upper()
                        return "DEFINIDO" not in n and "ESCALADO" not in n and n not in {"", "N/A", "-"}

                    use_marquee = len(outros_servicos) > 4
                    classes_inner = 'health-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1'
                    items_marquee = outros_servicos * 2 if use_marquee else outros_servicos
                    
                    with ui.column().classes(classes_inner):
                        for item in items_marquee:
                            defined = is_defined(item['nome'])
                            with ui.row().classes('w-full items-center justify-between px-1 q-py-0.5 border-b border-gray-900/50 hover:bg-white/5'):
                                ui.label(item['cargo'].upper()).classes('text-grey-5 font-bold text-[14px]').style('font-family: monospace;')
                                with ui.row().classes('items-center gap-1.5'):
                                    if defined:
                                        ui.label(item['nome'].upper()).classes('text-white font-black text-[14px]')
                                        ui.badge('PRONTO', color='green-9').classes('text-[10px] font-bold')
                                    else:
                                        ui.label('A DEFINIR').classes('text-amber-5/70 italic text-[14px]')
                                        ui.badge('AGUARDANDO', color='amber-9').classes('text-[10px] font-bold text-black animate-pulse')

                # 2. Painel de Quantitativos (KPIs 4x2)
                quant_container.clear()
                with quant_container:
                    def build_mini_kpi(val, label, color, icon):
                        with ui.card().classes('q-pa-xs items-center text-center border border-gray-900').style(
                            f'background:#050505; border-top: 3px solid {color}; flex: 1 1 0; min-width: 60px; margin: 0;'
                        ):
                            ui.icon(icon, color='grey-7', size='1.2rem').classes('q-mb-0')
                            ui.label(str(val)).classes('kpi-value').style(f'color: {color};')
                            ui.label(label).classes('kpi-label')
                
                    baixados_count = len([x for x in d['saude_ativos'] if x['categoria'] == 'enfermaria'])
                    dispensados_count = len([x for x in d['saude_ativos'] if x['categoria'] == 'dispensa'])
                    hospital_count = len([x for x in d['saude_ativos'] if x['categoria'] == 'hospital'])
                    licenciados_count = len(d.get('licencas_ativas', []))
                
                    if d['is_offline']:
                        ausentes_count = d['total_alunos'] - d['presentes_hoje']
                    else:
                        ausentes_count = d.get('ausentes_hoje', 0)
                    pernoite_count = d.get('pernoite_count', 0)

                    # Linha 1: Efetivo, Presentes, Ausentes, Licenciados
                    with ui.row().classes('w-full gap-1 justify-between no-wrap'):
                        build_mini_kpi(d['total_alunos'], 'Efetivo', '#D4AF37', 'groups')
                        build_mini_kpi(d['presentes_hoje'], 'Presentes', '#4CAF50', 'how_to_reg')
                        build_mini_kpi(ausentes_count, 'Ausentes', '#F44336', 'person_off')
                        build_mini_kpi(licenciados_count, 'Licenciados', '#2196F3', 'flight_takeoff')
                
                    # Linha 2: Baixados, Dispensados, Hospital, Pernoite
                    with ui.row().classes('w-full gap-1 justify-between no-wrap'):
                        build_mini_kpi(baixados_count, 'Baixados', '#E91E63', 'local_hospital')
                        build_mini_kpi(dispensados_count, 'Dispensados', '#FF9800', 'event_busy')
                        build_mini_kpi(hospital_count, 'Hospital', '#9C27B0', 'apartment')
                        build_mini_kpi(pernoite_count, 'Pernoite', '#00BCD4', 'nightlight')

                # 3. Anotações do Dia (Ações dos Alunos com cores positivo/negativo/neutro)
                anotacoes_container.clear()
                with anotacoes_container:
                    for anot in d['anotacoes_dia']:
                        texto = anot['texto']
                        status = anot['status']
                        pts = anot.get('pts', 0.0)
                        is_pendente = status == 'Pendente'
                    
                        # Determina cores baseadas no tipo de pontuação (Positivo, Negativo ou Neutro)
                        if pts > 0:
                            icon_color = '#00e676'
                            text_color_class = 'text-green-400'
                        elif pts < 0:
                            icon_color = '#ff1744'
                            text_color_class = 'text-red-400'
                        else:
                            icon_color = 'amber-9' if not is_pendente else 'amber-5'
                            text_color_class = 'text-grey-3'
                    
                        with ui.row().classes('w-full items-start gap-1 q-py-0.5 border-b border-gray-900/60 no-wrap'):
                            if is_pendente:
                                ui.icon('watch_later', color='amber-5', size='1.2rem')
                                with ui.row().classes('items-center gap-1.5 col-grow flex-wrap'):
                                    # Mantém o texto da anotação com a cor do tipo (+/-) e sinaliza com o badge PENDENTE âmbar
                                    ui.label(texto).classes(f'{text_color_class} font-semibold').style('font-size: 18px; line-height: 1.3;')
                                    ui.badge('PENDENTE', color='amber-9').classes('text-[12px] font-bold text-black')
                            else:
                                ui.icon('chevron_right', color=icon_color, size='1.2rem')
                                ui.label(texto).classes(f'{text_color_class} font-semibold col-grow').style('font-size: 18px; line-height: 1.3;')

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
                enfermaria_total_lbl.set_text(f"TOTAL: {len(baixados_efetivos)}")
                enfermaria_marquee_div.clear()

                with enfermaria_marquee_div:
                    if not baixados_efetivos:
                        with ui.card().classes('w-full q-pa-sm items-center justify-center bg-gray-900 border border-gray-800'):
                            ui.icon('health_and_safety', color='green', size='2.5rem')
                            ui.label('ENFERMARIA SEM ALUNOS BAIXADOS').classes('text-green-500 font-bold text-[18px]')
                    else:
                        use_marquee = len(baixados_efetivos) > 2
                        classes_inner = 'health-marquee-container w-full gap-1' if use_marquee else 'w-full gap-1'
                        items_marquee = baixados_efetivos * 2 if use_marquee else baixados_efetivos
                        
                        with ui.column().classes(classes_inner):
                            for item in items_marquee:
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
                                text_cat_color_style = f'color: {cor} !important;'
                                bg_card = f'background: {bg_rgba};'
                                desc_extra = detalhe if detalhe else ('Leito não informado' if cat == 'enfermaria' else 'Internação')

                                item_turma = str(item.get('turma') or 'N/A').upper()
                                item_nome = str(item.get('nome') or 'MILITAR').upper()

                                with ui.card().classes(f'w-full q-pa-xs q-mb-xs').style(f'{bg_card} {border_color_style} margin-bottom: 4px;'):
                                    with ui.row().classes('w-full items-center justify-between px-1'):
                                        with ui.row().classes('items-center gap-1.5'):
                                            ui.element('span').classes(f'w-1.5 h-1.5 rounded-full').style(indicator_color_style)
                                            ui.label(item_turma).classes('text-grey-5 font-black text-[18px]')
                                            ui.label(item_nome).classes('text-white font-black text-[18px] tracking-wider')
                                        ui.label(label_cat).classes(f'font-bold text-[16px] tracking-wider').style(text_cat_color_style)
                                
                                    with ui.row().classes('w-full justify-between items-baseline px-1 text-[18px] text-grey-3'):
                                        ui.label(motivo).classes('font-semibold italic ellipsis').style('max-width: 60%')
                                        ui.label(desc_extra).classes('text-white font-bold text-[18px]')

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
                
                    # Get STATUS_INFO for Licença
                    cor, bg_rgba, ico = STATUS_INFO.get('Licença', ('#00e5ff', 'rgba(0, 229, 255, 0.15)', 'beach_access'))
                    lic_disp_list.append({
                        'turma': str(lic.get('turma') or 'N/A').upper(),
                        'nome': str(lic.get('nome') or 'MILITAR').upper(),
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
                    
                        # Get STATUS_INFO for Dispensado
                        cor, bg_rgba, ico = STATUS_INFO.get('Dispensado', ('#00b0ff', 'rgba(0, 176, 255, 0.15)', 'medical_services'))
                        lic_disp_list.append({
                            'turma': str(disp.get('turma') or 'N/A').upper(),
                            'nome': str(disp.get('nome') or 'MILITAR').upper(),
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
                        items_marquee = lic_disp_list * 2 if use_marquee else lic_disp_list

                        with ui.column().classes(classes_inner):
                            for item in items_marquee:
                                with ui.card().classes('w-full q-pa-xs border q-mb-xs').style('background: rgba(255,255,255,0.01); border-color: rgba(255, 255, 255, 0.05); margin-bottom: 3px;'):
                                    with ui.row().classes('w-full items-center justify-between px-1 hover:bg-white/5'):
                                        with ui.row().classes('items-center gap-1.5'):
                                            ui.label(item['turma']).classes('text-grey-5 font-black text-[18px]')
                                            ui.label(item['nome']).classes('text-white font-black text-[18px]')
                                        ui.label(item['tipo']).classes(f"px-1 py-0.2 rounded border text-[16px] font-bold").style(item['color_tag'])
                                    with ui.row().classes('w-full justify-end px-1 text-[18px] font-black').style('color: #00e5ff;'):
                                        ui.label(f"RETORNO: {item['retorno']}")

                # 6. Programação do Dia (Atividades) - Lado direito (1/3 width)
                atividades_marquee_container.clear()
            
                with atividades_marquee_container:
                    if not d['atividades_dia']:
                        with ui.card().classes('w-full q-pa-md items-center justify-center bg-gray-900/30 border border-gray-800/50'):
                            ui.label('SEM ATIVIDADES CADASTRADAS PARA HOJE').classes('text-grey-5 font-bold text-[14px]')
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
                                        # Linha 1: Horário, Local e Status
                                        with ui.row().classes('w-full justify-between items-center no-wrap'):
                                            with ui.row().classes('items-center gap-1.5'):
                                                raw_time = str(act.get('horario', '--:--'))
                                                time_formatted = raw_time[:5] if len(raw_time) >= 5 else raw_time
                                                ui.label(time_formatted).style('color: #F59E0B; font-size: 14px; font-weight: 900; font-family: monospace;')
                                                ui.label(act.get('local', 'N/A').upper()).classes('px-1 bg-black/40 border border-grey-900 rounded font-mono text-[14px] text-grey-4')
                                            if is_concluida:
                                                ui.badge('CONCLUÍDO', color='green-9').classes('text-[14px] font-bold')
                                            else:
                                                ui.badge('AGENDADO', color='amber-9').classes('text-[14px] font-bold text-black animate-pulse')
                                    
                                        # Linha 2: Descrição e Responsável
                                        with ui.row().classes('w-full justify-between items-start no-wrap gap-2 text-[14px]'):
                                            ui.label(act.get('descricao', '')).classes('text-white font-bold col-grow').style('white-space: normal; word-break: break-word;')
                                            ui.label(f"👮 {act.get('responsavel', 'N/A')}").classes('text-grey-4 font-medium shrink-0 max-w-[40%] ellipsis')

                # Ajusta o timer dinamicamente com base nas configurações
                polling_interval = d.get('polling_interval', 300.0)
                refresh_timer.interval = polling_interval

        except Exception as e:
            print(f"[TV] Erro ao renderizar atualização do Modo TV: {e}")

    # Inicializa Timers e Fila de Alertas
    ui.timer(1.0, _update_clock)
    
    # Criamos o timer com valor inicial que depois será ajustado dinamicamente
    refresh_timer = ui.timer(300.0, _refresh)
    
    # Inicia a fila de processamento de alertas
    queue_task = asyncio.create_task(_process_toast_queue())
    
    # Registra a TV no AlertsManager para receber notificações em tempo real
    from alerts_manager import AlertsManager
    AlertsManager.register_tv_callback(client, trigger_toast)
    
    # Remove a TV ao desconectar a página e cancela a fila
    def on_disconnect_cleanup():
        AlertsManager.unregister_tv_callback(client.id)
        queue_task.cancel()
        
    ui.context.client.on_disconnect(on_disconnect_cleanup)
    
    # Executa primeiro refresh imediato
    asyncio.create_task(_refresh())
