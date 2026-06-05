import os
from supabase import create_client
from dotenv import load_dotenv
from typing import Optional, Any

# Carrega o .env a partir do diretório absoluto do arquivo
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
# SEGURANÇA: Usa a chave anon (que respeita RLS) como padrão.
# A service_role_key é usada APENAS em get_bot_db_connection() / get_service_db_connection().
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

db: Any = None


def get_bot_db_connection():
    """Retorna uma conexão dedicada para tarefas de segundo plano (como o Bot do Telegram).
    Usa a SUPABASE_SERVICE_ROLE_KEY para contornar RLS se configurada, caso contrário cai no fallback."""
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        except Exception as e:
            print(f"[ERRO BOT DB CLIENT] Falha ao criar cliente com service_role: {e}")
    return get_db_connection()


def get_service_db_connection():
    """Retorna uma conexão com service_role_key para operações admin privilegiadas.
    NUNCA use para operações de usuário comum."""
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        except Exception as e:
            print(f"[ERRO SERVICE DB] Falha ao criar cliente service_role: {e}")
    return None



def get_db_connection():
    try:
        from nicegui import app
        has_storage = app.storage.user is not None
    except Exception:
        has_storage = False

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERRO DB] Chaves do Supabase nao encontradas no .env")
        return None

    session = None
    if has_storage:
        try:
            session = app.storage.user.get('supabase_session')
        except Exception:
            pass

    if session:
        try:
            access_token = session.get('access_token')
            refresh_token = session.get('refresh_token')
            if access_token and refresh_token:
                user_db = create_client(SUPABASE_URL, SUPABASE_KEY)
                user_db.auth.set_session(access_token, refresh_token)
                return user_db
        except Exception as e:
            print(f"[ERRO DB SET SESSION] {e}")

    global db
    if db:
        return db

    try:
        db = create_client(SUPABASE_URL, SUPABASE_KEY)
        return db
    except Exception as e:
        print(f"[ERRO CRITICO DB] {e}")
        return None


def authenticate_user_supabase(email: str, password: str) -> Optional[dict]:
    """
    Autentica o usuario no Supabase Auth e carrega seu perfil na tabela 'Users'.
    Retorna um dicionario com o perfil ('profile') e os dados de sessao ('session').
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        db_conn = create_client(SUPABASE_URL, SUPABASE_KEY)
        auth_response = db_conn.auth.sign_in_with_password({"email": email, "password": password})
        if auth_response and auth_response.user:
            user_id = auth_response.user.id
            db_conn.auth.set_session(auth_response.session.access_token, auth_response.session.refresh_token)
            result = db_conn.table('Users').select('*').eq('id', user_id).execute()
            if result.data:
                profile = result.data[0]
                return {
                    'profile': profile,
                    'session': {
                        'access_token': auth_response.session.access_token,
                        'refresh_token': auth_response.session.refresh_token
                    }
                }
        return None
    except Exception as e:
        print(f"[ERRO autenticacao supabase] {e}")
        return None


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Autentica usuário contra a tabela 'efetivo'.
    username: pode ser telegram_id, nome_guerra ou email
    password: senha em texto plano (comparada contra hash bcrypt no banco)
    """
    import hashlib
    import bcrypt
    
    db = get_db_connection()
    if not db:
        return None
    
    try:
        # Busca por telegram_id, nome_guerra ou email
        result = db.table('efetivo').select('*').or_(
            f'telegram_id.eq.{username},nome_guerra.eq.{username},email.eq.{username}'
        ).execute()
        
        if not result.data:
            return None
        
        user = result.data[0]
        stored_password = user.get('senha_hash', '')
        
        if not stored_password:
            return None
        
        password_valid = False
        needs_upgrade = False
        
        # 1. Tenta verificar como bcrypt (formato moderno)
        if stored_password.startswith('$2b$') or stored_password.startswith('$2a$'):
            try:
                password_valid = bcrypt.checkpw(
                    password.encode('utf-8'),
                    stored_password.encode('utf-8')
                )
            except Exception:
                password_valid = False
        else:
            # 2. Fallback: verifica como SHA-256 legado (para migração)
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if stored_password == password_hash:
                password_valid = True
                needs_upgrade = True  # Marcar para upgrade para bcrypt
        
        if password_valid:
            # Auto-upgrade: migra hash SHA-256 legado para bcrypt
            if needs_upgrade:
                try:
                    new_hash = bcrypt.hashpw(
                        password.encode('utf-8'),
                        bcrypt.gensalt(rounds=12)
                    ).decode('utf-8')
                    db.table('efetivo').update(
                        {'senha_hash': new_hash}
                    ).eq('id', user['id']).execute()
                    print(f"[SEGURANÇA] Hash migrado para bcrypt: {username}")
                except Exception as e:
                    print(f"[SEGURANÇA] Erro ao migrar hash: {e}")
            
            # Remove senha antes de retornar
            user.pop('senha_hash', None)
            return user
        
        return None
    except Exception as e:
        print(f"[ERRO autenticacao] {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Busca usuário pelo ID (telegram_id)"""
    db = get_db_connection()
    if not db:
        return None
    
    try:
        result = db.table('efetivo').select('*').eq('telegram_id', user_id).execute()
        if result.data:
            user = result.data[0]
            user.pop('senha_hash', None)
            return user
        return None
    except Exception as e:
        print(f"[ERRO buscar usuario] {e}")
        return None


# --- FUNÇÕES DO CONTROLE DE ALUNOS (MIGRAÇÃO SISCOMCA) ---

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict

def salvar_presenca_supabase(numero_interno: Any, nome_guerra: str, turma: str, 
                             presente: bool, motivo_ausencia: Optional[str] = None) -> bool:
    """Salva registro de presença com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Salvar presença simulada")
        return True
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        hora = datetime.now().strftime('%H:%M:%S')
        
        response = db.table('presenca_ausencia').select('*').eq(
            'numero_interno', numero_interno
        ).eq('data', data_hoje).execute()
        
        registro = {
            'numero_interno': numero_interno,
            'nome_guerra': nome_guerra,
            'turma': turma,
            'presente': presente,
            'motivo_ausencia': motivo_ausencia or '',
            'data': data_hoje,
            'hora': hora,
            'criado_em': datetime.now().isoformat()
        }
        
        if response.data:
            db.table('presenca_ausencia').update(registro).eq(
                'numero_interno', numero_interno
            ).eq('data', data_hoje).execute()
        else:
            db.table('presenca_ausencia').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar presença: {e}")
        return False


def deletar_presenca_supabase(numero_interno: Any) -> bool:
    """Deleta o registro de presença de hoje do aluno (resetando para pendente)"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Deletar presença simulada")
        return True
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        db.table('presenca_ausencia').delete().eq(
            'numero_interno', numero_interno
        ).eq('data', data_hoje).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao deletar presença: {e}")
        return False


def carregar_presenca_hoje(turma: Optional[str] = None) -> pd.DataFrame:
    """Carrega presença de hoje com fallback offline (dados fictícios)"""
    db = get_db_connection()
    if not db:
        mock_data = [
            {'id': 1, 'numero_interno': 101, 'nome_guerra': 'Silva', 'turma': 'Alfa', 'presente': True, 'motivo_ausencia': '', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '07:30:00'},
            {'id': 2, 'numero_interno': 102, 'nome_guerra': 'Santos', 'turma': 'Alfa', 'presente': True, 'motivo_ausencia': '', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '07:31:00'},
            {'id': 3, 'numero_interno': 201, 'nome_guerra': 'Oliveira', 'turma': 'Bravo', 'presente': False, 'motivo_ausencia': 'Serviço externo', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '07:32:00'},
            {'id': 4, 'numero_interno': 202, 'nome_guerra': 'Costa', 'turma': 'Bravo', 'presente': True, 'motivo_ausencia': '', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '07:33:00'},
            {'id': 5, 'numero_interno': 301, 'nome_guerra': 'Pereira', 'turma': 'Charlie', 'presente': True, 'motivo_ausencia': '', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '07:34:00'},
        ]
        df = pd.DataFrame(mock_data)
        if turma:
            df = df[df['turma'] == turma]
        return df
        
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        query = db.table('presenca_ausencia').select('*').eq('data', data_hoje)
        if turma:
            query = query.eq('turma', turma)
        response = query.execute()
        if response.data:
            return pd.DataFrame(response.data).sort_values('numero_interno')
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar presença: {e}")
        return pd.DataFrame()


def salvar_enfermaria_supabase(numero_interno: Any, nome_guerra: str, turma: str,
                               status: str, motivo: str = "") -> bool:
    """Salva registro de enfermaria com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Salvar enfermaria simulada")
        return True
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        hora = datetime.now().strftime('%H:%M:%S')
        
        response = db.table('enfermaria').select('*').eq(
            'numero_interno', numero_interno
        ).eq('data', data_hoje).execute()
        
        registro = {
            'numero_interno': numero_interno,
            'nome_guerra': nome_guerra,
            'turma': turma,
            'status': status,
            'motivo': motivo,
            'data': data_hoje,
            'hora': hora,
            'criado_em': datetime.now().isoformat()
        }
        
        if response.data:
            db.table('enfermaria').update(registro).eq(
                'numero_interno', numero_interno
            ).eq('data', data_hoje).execute()
        else:
            db.table('enfermaria').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar enfermaria: {e}")
        return False


def carregar_enfermaria_hoje(turma: Optional[str] = None) -> pd.DataFrame:
    """Carrega enfermaria de hoje com fallback offline (dados fictícios)"""
    db = get_db_connection()
    if not db:
        mock_data = [
            {'id': 1, 'numero_interno': 201, 'nome_guerra': 'Oliveira', 'turma': 'Bravo', 'status': 'baixado', 'motivo': 'Gripe Forte', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '08:00:00'},
            {'id': 2, 'numero_interno': 102, 'nome_guerra': 'Santos', 'turma': 'Alfa', 'status': 'apresentado', 'motivo': 'Dor de cabeça', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '09:30:00'},
        ]
        df = pd.DataFrame(mock_data)
        if turma:
            df = df[df['turma'] == turma]
        return df
        
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        query = db.table('enfermaria').select('*').eq('data', data_hoje)
        if turma:
            query = query.eq('turma', turma)
        response = query.execute()
        if response.data:
            return pd.DataFrame(response.data).sort_values('numero_interno')
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar enfermaria: {e}")
        return pd.DataFrame()


def salvar_oficial_servico(nome: str, cargo: str, ajudante: str = None) -> bool:
    """Salva oficial de serviço com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Salvar oficial de serviço simulado")
        return True
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        registro = {
            'nome': nome,
            'cargo': cargo,
            'ajudante': ajudante,
            'data': data_hoje,
            'criado_em': datetime.now().isoformat()
        }
        
        response = db.table('oficiais_servico').select('*').eq('cargo', cargo).eq('data', data_hoje).execute()
        if response.data:
            db.table('oficiais_servico').update(registro).eq('id', response.data[0]['id']).execute()
        else:
            db.table('oficiais_servico').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar oficial: {e}")
        return False


def carregar_oficiais_hoje() -> pd.DataFrame:
    """Carrega oficiais de serviço de hoje com fallback offline (dados fictícios)"""
    db = get_db_connection()
    if not db:
        mock_data = [
            {'id': 1, 'nome': 'Cap. Calaça', 'cargo': 'Oficial de Dia', 'ajudante': 'Sgt. Silva', 'data': datetime.now().strftime('%Y-%m-%d')},
            {'id': 2, 'nome': 'Ten. Santos', 'cargo': 'Oficial de Rondas', 'ajudante': 'Cabo Oliveira', 'data': datetime.now().strftime('%Y-%m-%d')},
        ]
        return pd.DataFrame(mock_data)
        
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        response = db.table('oficiais_servico').select('*').eq('data', data_hoje).execute()
        if response.data:
            return pd.DataFrame(response.data).sort_values('cargo')
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar oficiais: {e}")
        return pd.DataFrame()



# ──────────────────────────────────────────────────────────────────────────────
# ESCALA DIÁRIA (Inspetor, Supervisor, Oficial de Serviço, etc.)
# Tabela: escala_diaria  |  Colunas: id, data, cargo, nome, observacao, criado_em
# ──────────────────────────────────────────────────────────────────────────────

CARGOS_ESCALA = [
    'INSPETOR DO DIA',
    'SUPERVISOR',
    'AJOSCA',
    'OSCA',
    'OFICIAL DE SERVIÇO',
    'ENFERMEIRO DE SERVIÇO'
]


def get_cargos_escala() -> list:
    """Retorna os cargos ativos da escala cadastrados nas configurações do Supabase."""
    db_conn = get_db_connection()
    if db_conn:
        try:
            res = db_conn.table('Config').select('*').eq('chave', 'cargos_escala_lista').execute()
            if res.data:
                return [c.strip() for c in res.data[0]['valor'].split(',') if c.strip()]
        except Exception as e:
            print(f"[DB] Erro ao carregar cargos_escala_lista: {e}")
    return CARGOS_ESCALA


def salvar_cargos_escala(cargos: list) -> bool:
    """Atualiza a lista global de cargos cadastrados na tabela Config do Supabase."""
    db_conn = get_db_connection()
    cargos_str = ", ".join([c.strip().upper() for c in cargos if c.strip()])
    
    if not db_conn:
        print(f"[OFFLINE] Salvar cargos_escala_lista simulado: {cargos_str}")
        return True
        
    try:
        # Verifica se já existe
        resp = db_conn.table('Config').select('id').eq('chave', 'cargos_escala_lista').execute()
        registro = {
            'chave': 'cargos_escala_lista',
            'valor': cargos_str,
            'updated_at': datetime.now().isoformat()
        }
        if resp.data:
            db_conn.table('Config').update(registro).eq('id', resp.data[0]['id']).execute()
        else:
            db_conn.table('Config').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar cargos_escala_lista na tabela Config: {e}")
        return False


def salvar_escala_diaria(cargo: str, nome: str, data: str = None, observacao: str = '') -> bool:
    """Upsert de um cargo na escala do dia (tabela escala_diaria)."""
    db_conn = get_db_connection()
    data_ref = data or datetime.now().strftime('%Y-%m-%d')
    registro = {
        'data': data_ref,
        'cargo': cargo,
        'nome': nome,
        'observacao': observacao or '',
        'criado_em': datetime.now().isoformat(),
    }
    if not db_conn:
        print(f"[OFFLINE] Escala simulada: {cargo} → {nome} na data {data_ref}")
        return True
    try:
        resp = db_conn.table('escala_diaria').select('id').eq('data', data_ref).eq('cargo', cargo).execute()
        if resp.data:
            db_conn.table('escala_diaria').update(registro).eq('id', resp.data[0]['id']).execute()
        else:
            db_conn.table('escala_diaria').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar escala_diaria: {e}")
        # Tenta criar como oficiais_servico como fallback
        try:
            salvar_oficial_servico(nome, cargo)
            return True
        except Exception:
            return False


def deletar_escala_diaria(data: str) -> bool:
    """Remove toda a escala de uma data específica."""
    db_conn = get_db_connection()
    if not db_conn:
        print(f"[OFFLINE] Deletar escala diária simulada para data {data}")
        return True
    try:
        db_conn.table('escala_diaria').delete().eq('data', data).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao deletar escala_diaria: {e}")
        return False


def carregar_escala_diaria(data: str = None) -> pd.DataFrame:
    """Carrega escala do dia especificado (ou hoje)."""
    db_conn = get_db_connection()
    data_ref = data or datetime.now().strftime('%Y-%m-%d')
    if not db_conn:
        mock = [
            {'id': 1, 'data': data_ref, 'cargo': 'Inspetor do Dia', 'nome': 'Ten. Calaça', 'observacao': ''},
            {'id': 2, 'data': data_ref, 'cargo': 'Oficial de Serviço', 'nome': 'Cap. Santos', 'observacao': ''},
            {'id': 3, 'data': data_ref, 'cargo': 'Supervisor', 'nome': 'Maj. Lima', 'observacao': ''},
        ]
        return pd.DataFrame(mock)
    try:
        resp = db_conn.table('escala_diaria').select('*').eq('data', data_ref).execute()
        if resp.data:
            return pd.DataFrame(resp.data).sort_values('cargo')
        # Tenta fallback em oficiais_servico
        resp2 = db_conn.table('oficiais_servico').select('*').eq('data', data_ref).execute()
        if resp2.data:
            df = pd.DataFrame(resp2.data)
            df['observacao'] = ''
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar escala_diaria: {e}")
        return pd.DataFrame()


def adicionar_fila_atendimento(numero_interno: Any, nome_guerra: str, 
                               turma: str, motivo: str, prioridade: str = "normal") -> bool:
    """Adiciona registro na fila de atendimento com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Adicionar fila simulado")
        return True
    try:
        registro = {
            'numero_interno': numero_interno,
            'nome_guerra': nome_guerra,
            'turma': turma,
            'motivo': motivo,
            'prioridade': prioridade,
            'status': 'aguardando',
            'data': datetime.now().strftime('%Y-%m-%d'),
            'hora': datetime.now().strftime('%H:%M:%S'),
            'criado_em': datetime.now().isoformat()
        }
        db.table('fila_atendimento').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao adicionar fila: {e}")
        return False


def carregar_fila_atendimento() -> pd.DataFrame:
    """Carrega fila de atendimento com fallback offline (dados fictícios)"""
    db = get_db_connection()
    if not db:
        mock_data = [
            {'id': 1, 'numero_interno': 101, 'nome_guerra': 'Silva', 'turma': 'Alfa', 'motivo': 'Justificativa de Falta', 'prioridade': 'normal', 'status': 'aguardando', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '08:30:00'},
            {'id': 2, 'numero_interno': 202, 'nome_guerra': 'Costa', 'turma': 'Bravo', 'motivo': 'Apresentar Atestado', 'prioridade': 'alta', 'status': 'aguardando', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '08:45:00'},
            {'id': 3, 'numero_interno': 301, 'nome_guerra': 'Pereira', 'turma': 'Charlie', 'motivo': 'Solicitação de Fardamento', 'prioridade': 'normal', 'status': 'em_atendimento', 'data': datetime.now().strftime('%Y-%m-%d'), 'hora': '08:15:00'},
        ]
        df = pd.DataFrame(mock_data)
        ordem_prioridade = {'urgente': 0, 'alta': 1, 'normal': 2, 'baixa': 3}
        df['prioridade_num'] = df['prioridade'].map(ordem_prioridade).fillna(2)
        return df.sort_values(['prioridade_num', 'hora'])
        
    try:
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        response = db.table('fila_atendimento').select('*').eq('data', data_hoje).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            ordem_prioridade = {'urgente': 0, 'alta': 1, 'normal': 2, 'baixa': 3}
            df['prioridade_num'] = df['prioridade'].map(ordem_prioridade).fillna(2)
            return df.sort_values(['prioridade_num', 'hora'])
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar fila: {e}")
        return pd.DataFrame()


def atualizar_status_fila(id: int, status: str) -> bool:
    """Atualiza status da fila com fallback offline"""
    db = get_db_connection()
    if not db:
        print(f"[OFFLINE] Atualizar status fila ID {id} para {status}")
        return True
    try:
        db.table('fila_atendimento').update({
            'status': status,
            'atualizado_em': datetime.now().isoformat()
        }).eq('id', id).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao atualizar status fila: {e}")
        return False


def adicionar_aviso_critico(titulo: str, mensagem: str, 
                            prioridade: str = "alta", turma: str = None) -> bool:
    """Adiciona aviso crítico com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Adicionar aviso simulado")
        return True
    try:
        registro = {
            'titulo': titulo,
            'mensagem': mensagem,
            'prioridade': prioridade,
            'turma': turma,
            'status': 'ativo',
            'data': datetime.now().strftime('%Y-%m-%d'),
            'hora': datetime.now().strftime('%H:%M:%S'),
            'criado_em': datetime.now().isoformat()
        }
        db.table('avisos_criticos').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao adicionar aviso: {e}")
        return False


def carregar_avisos_criticos() -> pd.DataFrame:
    """Carrega avisos críticos com fallback offline (dados fictícios)"""
    db = get_db_connection()
    if not db:
        mock_data = [
            {'id': 1, 'titulo': 'Formatura Geral', 'mensagem': 'Formatura com Uniforme 3º A às 07:30.', 'prioridade': 'critica', 'turma': None, 'status': 'ativo', 'data': datetime.now().strftime('%Y-%m-%d')},
            {'id': 2, 'titulo': 'Inspeção de Armário', 'mensagem': 'Inspeção na Cia Bravo às 13:00.', 'prioridade': 'alta', 'turma': 'Bravo', 'status': 'ativo', 'data': datetime.now().strftime('%Y-%m-%d')},
        ]
        return pd.DataFrame(mock_data)
        
    try:
        ontem = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        response = db.table('avisos_criticos').select('*').gte('data', ontem).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df = df[df['status'] == 'ativo']
            ordem_prioridade = {'critica': 0, 'alta': 1, 'media': 2, 'baixa': 3}
            df['prioridade_num'] = df['prioridade'].map(ordem_prioridade).fillna(2)
            return df.sort_values(['prioridade_num', 'criado_em'], ascending=[True, False])
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar avisos: {e}")
        return pd.DataFrame()


def atualizar_status_aviso(id: int, status: str) -> bool:
    """Atualiza status de um aviso com fallback offline"""
    db = get_db_connection()
    if not db:
        print(f"[OFFLINE] Atualizar status aviso ID {id} para {status}")
        return True
    try:
        db.table('avisos_criticos').update({
            'status': status,
            'atualizado_em': datetime.now().isoformat()
        }).eq('id', id).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao atualizar aviso: {e}")
        return False


def adicionar_tarefa_pendente(titulo: str, descricao: str, 
                              responsavel: str, prioridade: str = "normal", 
                              turma: str = None, prazo: str = None) -> bool:
    """Adiciona tarefa pendente com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Adicionar tarefa simulada")
        return True
    try:
        registro = {
            'titulo': titulo,
            'descricao': descricao,
            'responsavel': responsavel,
            'prioridade': prioridade,
            'turma': turma,
            'prazo': prazo,
            'status': 'pendente',
            'data': datetime.now().strftime('%Y-%m-%d'),
            'criado_em': datetime.now().isoformat()
        }
        db.table('tarefas_pendentes').insert(registro).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao adicionar tarefa: {e}")
        return False


def carregar_tarefas_pendentes() -> pd.DataFrame:
    """Carrega tarefas pendentes com fallback offline (dados fictícios)"""
    db = get_db_connection()
    if not db:
        mock_data = [
            {'id': 1, 'titulo': 'Livro de Registro', 'descricao': 'Entregar o livro na secretaria', 'responsavel': 'Sgt. Silva', 'prioridade': 'normal', 'turma': None, 'prazo': datetime.now().strftime('%Y-%m-%d'), 'status': 'pendente', 'data': datetime.now().strftime('%Y-%m-%d')},
            {'id': 2, 'titulo': 'Quadro de Escala', 'descricao': 'Definir ajudantes para o final de semana', 'responsavel': 'Cap. Calaça', 'prioridade': 'urgente', 'turma': None, 'prazo': datetime.now().strftime('%Y-%m-%d'), 'status': 'pendente', 'data': datetime.now().strftime('%Y-%m-%d')},
        ]
        return pd.DataFrame(mock_data)
        
    try:
        response = db.table('tarefas_pendentes').select('*').neq('status', 'concluida').execute()
        if response.data:
            df = pd.DataFrame(response.data)
            ordem_prioridade = {'urgente': 0, 'alta': 1, 'normal': 2, 'baixa': 3}
            df['prioridade_num'] = df['prioridade'].map(ordem_prioridade).fillna(2)
            return df.sort_values(['prioridade_num', 'data'], ascending=[True, False])
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERRO] Falha ao carregar tarefas: {e}")
        return pd.DataFrame()


def atualizar_status_tarefa(id: int, status: str) -> bool:
    """Atualiza status de uma tarefa com fallback offline"""
    db = get_db_connection()
    if not db:
        print(f"[OFFLINE] Atualizar status tarefa ID {id} para {status}")
        return True
    try:
        db.table('tarefas_pendentes').update({
            'status': status,
            'atualizado_em': datetime.now().isoformat()
        }).eq('id', id).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao atualizar tarefa: {e}")
        return False


def get_mock_table(table_name: str) -> pd.DataFrame:
    """Retorna dados simulados para desenvolvimento offline do SisCOMCA"""
    table_name_lower = table_name.lower()
    if table_name_lower == 'alunos':
        mock_data = [
            {'id': '1', 'numero_interno': '101', 'nome_guerra': 'Silva', 'nome_completo': 'Silva Junior', 'pelotao': 'Alfa', 'especialidade': 'Infantaria', 'nip': '12345678', 'url_foto': '', 'media_academica': 8.5, 'endereco': 'Rua Alfa, 1', 'telefone_contato': '21999998888', 'contato_emergencia_nome': 'Maria', 'contato_emergencia_numero': '21999997777', 'numero_armario': 'A-01'},
            {'id': '2', 'numero_interno': '102', 'nome_guerra': 'Santos', 'nome_completo': 'Santos Souza', 'pelotao': 'Alfa', 'especialidade': 'Artilharia', 'nip': '87654321', 'url_foto': '', 'media_academica': 7.9, 'endereco': 'Rua Bravo, 2', 'telefone_contato': '21988887777', 'contato_emergencia_nome': 'Jose', 'contato_emergencia_numero': '21988886666', 'numero_armario': 'A-02'},
            {'id': '3', 'numero_interno': '201', 'nome_guerra': 'Oliveira', 'nome_completo': 'Oliveira Santos', 'pelotao': 'Bravo', 'especialidade': 'Comunicações', 'nip': '11223344', 'url_foto': '', 'media_academica': 6.8, 'endereco': 'Rua Charlie, 3', 'telefone_contato': '21977776666', 'contato_emergencia_nome': 'Ana', 'contato_emergencia_numero': '21977775555', 'numero_armario': 'B-01'},
            {'id': '4', 'numero_interno': '202', 'nome_guerra': 'Costa', 'nome_completo': 'Costa Pereira', 'pelotao': 'Bravo', 'especialidade': 'Intendência', 'nip': '44332211', 'url_foto': '', 'media_academica': 9.2, 'endereco': 'Rua Delta, 4', 'telefone_contato': '21966665555', 'contato_emergencia_nome': 'Paulo', 'contato_emergencia_numero': '21966664444', 'numero_armario': 'B-02'},
            {'id': '5', 'numero_interno': '301', 'nome_guerra': 'Pereira', 'nome_completo': 'Pereira Alves', 'pelotao': 'Charlie', 'especialidade': 'Infantaria', 'nip': '55667788', 'url_foto': '', 'media_academica': 8.0, 'endereco': 'Rua Echo, 5', 'telefone_contato': '21955554444', 'contato_emergencia_nome': 'Carlos', 'contato_emergencia_numero': '21955553333', 'numero_armario': 'C-01'},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'acoes':
        mock_data = [
            {'id': '1', 'aluno_id': '1', 'tipo_acao_id': '1', 'tipo': 'Elogio', 'descricao': 'Excelente atitude no rancho', 'data': datetime.now().strftime('%Y-%m-%d'), 'usuario': 'Cap. Calaça', 'status': 'Lançado'},
            {'id': '2', 'aluno_id': '3', 'tipo_acao_id': '2', 'tipo': 'Atraso', 'descricao': 'Atraso na formatura', 'data': datetime.now().strftime('%Y-%m-%d'), 'usuario': 'Ten. Santos', 'status': 'Lançado'},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'tipos_acao':
        mock_data = [
            {'id': '1', 'nome': 'Elogio', 'pontuacao': 0.5},
            {'id': '2', 'nome': 'Atraso', 'pontuacao': -0.3},
            {'id': '3', 'nome': 'Uniforme Desalinhado', 'pontuacao': -0.2},
            {'id': '4', 'nome': 'Serviço Excelente', 'pontuacao': 0.8},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'config':
        mock_data = [
            {'chave': 'linha_base_conceito', 'valor': '8.5'},
            {'chave': 'impacto_max_acoes', 'valor': '1.5'},
            {'chave': 'peso_academico', 'valor': '1.0'},
            {'chave': 'fator_adaptacao', 'valor': '0.25'},
            {'chave': 'periodo_adaptacao_inicio', 'valor': '2026-02-01'},
            {'chave': 'periodo_adaptacao_fim', 'valor': '2026-02-28'},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'permissions':
        mock_data = [
            {'feature_key': 'pode_editar_aluno', 'allowed_roles': 'admin,supervisor'},
            {'feature_key': 'pode_importar_alunos', 'allowed_roles': 'admin'},
            {'feature_key': 'pode_ver_conceito_final', 'allowed_roles': 'admin,supervisor,operador'},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'users':
        mock_data = [
            {'id': '1', 'username': 'admin', 'nome': 'Sargento Calaça', 'role': 'admin'},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'pernoite':
        mock_data = [
            {'aluno_id': 1, 'data': datetime.now().strftime('%Y-%m-%d'), 'presente': True},
            {'aluno_id': 3, 'data': datetime.now().strftime('%Y-%m-%d'), 'presente': False},
        ]
        return pd.DataFrame(mock_data)
    elif table_name_lower == 'programacao':
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        mock_data = [
            {'id': 1, 'data': data_hoje, 'horario': '08:00', 'descricao': 'Instrução Militar Básica', 'local': 'Pátio de Formaturas', 'responsavel': 'Ten. Silva', 'obs': '', 'data_conclusao': None, 'concluido_por': None, 'destinatarios': 'MIKE-1, MIKE-2', 'status': 'A Realizar', 'pelotoes_concluidos': None},
            {'id': 2, 'data': data_hoje, 'horario': '10:30', 'descricao': 'Palestra: Liderança Naval', 'local': 'Auditório Principal', 'responsavel': 'Cap. Calaça', 'obs': '', 'data_conclusao': None, 'concluido_por': None, 'destinatarios': 'MIKE-1, MIKE-2, MIKE-3', 'status': 'A Realizar', 'pelotoes_concluidos': None},
            {'id': 3, 'data': data_hoje, 'horario': '14:00', 'descricao': 'Educação Física Supervisionada', 'local': 'Campo de Esportes', 'responsavel': 'Ten. Santos', 'obs': 'Trazer garrafa de água', 'data_conclusao': None, 'concluido_por': None, 'destinatarios': 'MIKE-3, MIKE-4', 'status': 'A Realizar', 'pelotoes_concluidos': None},
            {'id': 4, 'data': data_hoje, 'horario': '16:00', 'descricao': 'OGSA (Organização Geral da Marinha)', 'local': 'Sala 12', 'responsavel': 'Ten. Silva', 'obs': '', 'data_conclusao': '2026-05-30 16:30:00', 'concluido_por': 'calaca', 'destinatarios': 'MIKE-1, MIKE-2, MIKE-3, MIKE-4', 'status': 'Concluído', 'pelotoes_concluidos': 'MIKE-1, MIKE-2'},
        ]
        return pd.DataFrame(mock_data)
    return pd.DataFrame()


def salvar_conclusao_instrucao(instrucao_id: int, concluido_por: str, pelotoes: str, obs_exclusoes: Optional[str] = None) -> bool:
    """Salva a conclusão de uma instrução no Supabase com fallback offline"""
    db = get_db_connection()
    data_conclusao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    registro = {
        'status': 'Concluído',
        'data_conclusao': data_conclusao,
        'concluido_por': concluido_por,
        'pelotoes_concluidos': pelotoes
    }
    if obs_exclusoes is not None:
        registro['obs'] = obs_exclusoes

    if not db:
        print(f"[OFFLINE] Concluir instrução ID {instrucao_id}: {registro}")
        return True
    try:
        db.table('Programacao').update(registro).eq('id', instrucao_id).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar conclusão da instrução: {e}")
        return False


def reverter_conclusao_instrucao(instrucao_id: int) -> bool:
    """Reverte o status de uma instrução para 'A Realizar' no Supabase com fallback offline"""
    db = get_db_connection()
    registro = {
        'status': 'A Realizar',
        'data_conclusao': None,
        'concluido_por': None,
        'pelotoes_concluidos': None
    }
    if not db:
        print(f"[OFFLINE] Reverter instrução ID {instrucao_id}")
        return True
    try:
        db.table('Programacao').update(registro).eq('id', instrucao_id).execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao reverter conclusão da instrução: {e}")
        return False


def salvar_pernoites_supabase(registros: List[Dict]) -> bool:
    """Salva registros de pernoite em lote no Supabase com fallback offline"""
    db = get_db_connection()
    if not db:
        print("[OFFLINE] Salvar pernoites simulado")
        return True
    try:
        db.table('pernoite').upsert(registros, on_conflict='aluno_id,data').execute()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao salvar pernoites: {e}")
        return False


def load_data(table_name: str, db_conn = None) -> pd.DataFrame:
    """Carrega dados de uma tabela com paginação direto do Supabase"""
    db = db_conn or get_db_connection()
    if not db:
        return get_mock_table(table_name)
    try:
        all_data = []
        page = 0
        page_size = 1000
        while True:
            start_index = page * page_size
            end_index = start_index + page_size - 1
            response = db.table(table_name).select("*").range(start_index, end_index).execute()
            current_page_data = response.data
            if not current_page_data:
                break
            all_data.extend(current_page_data)
            if len(current_page_data) < page_size:
                break
            page += 1
        return pd.DataFrame(all_data)
    except Exception as e:
        print(f"[ERRO] Falha ao carregar tabela {table_name}: {e}")
        return pd.DataFrame()


def upload_file_to_supabase_storage(file_bytes: bytes, filename: str, content_type: str = "image/jpeg", bucket_name: str = "fotos-efetivos") -> Optional[str]:
    """
    Realiza o upload de um arquivo para um bucket do Supabase Storage.
    Retorna a URL pública do arquivo ou None em caso de falha.
    """
    conn = get_bot_db_connection()
    if not conn:
        conn = get_db_connection()
    if not conn:
        print("[STORAGE UPLOAD] Sem conexão com Supabase.")
        return None
    try:
        # Realiza o upload (upsert=true permite substituir arquivos com o mesmo nome)
        conn.storage.from_(bucket_name).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        # Pega a URL pública
        public_url = conn.storage.from_(bucket_name).get_public_url(filename)
        if public_url and public_url.endswith('?'):
            public_url = public_url.rstrip('?')
        return public_url
    except Exception as e:
        print(f"[STORAGE UPLOAD ERROR] {e}")
        return None


def get_signed_url_from_supabase_storage(filename: str, bucket_name: str = "fotos-alunos", expires_in: int = 3600) -> Optional[str]:
    """
    Gera uma URL assinada temporária para acessar arquivos em buckets privados (ex: 'fotos-alunos').
    """
    if not filename:
        return None
    conn = get_bot_db_connection()
    if not conn:
        conn = get_db_connection()
    if not conn:
        print("[STORAGE SIGNED URL] Sem conexão com Supabase.")
        return None
    try:
        res = conn.storage.from_(bucket_name).create_signed_url(filename, expires_in)
        if isinstance(res, dict) and "signedURL" in res:
            return res["signedURL"]
        return res
    except Exception as e:
        # Se for erro 404 (arquivo não existe), silencia ou avisa com debug
        print(f"[STORAGE SIGNED URL DEBUG] {filename} no bucket {bucket_name}: {e}")
        return None


def confirm_supabase_user(user_id: str) -> bool:
    """
    Confirma o e-mail de um usuário pendente no Supabase Auth usando o client service_role.
    """
    if not user_id:
        return False
    conn = get_service_db_connection()
    if not conn:
        conn = get_bot_db_connection()
    if conn and hasattr(conn, 'auth') and hasattr(conn.auth, 'admin'):
        try:
            conn.auth.admin.update_user_by_id(user_id, {"email_confirm": True})
            print(f"[AUTH CONFIRMATION] Confirmado email do usuário {user_id}")
            return True
        except Exception as e:
            print(f"[AUTH CONFIRMATION ERROR] Erro ao confirmar usuário {user_id}: {e}")
    return False
