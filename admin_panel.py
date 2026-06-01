from nicegui import ui
import theme
from database import get_db_connection
from services import data_service

THEME = theme.colors

# Opções de papéis/roles no sistema
ROLE_OPTIONS = {
    'compel': 'Compel (Aluno/Apenas Visualização)',
    'comcia': 'Comcia (Comandante de Cia/Edição Limitada)',
    'supervisor': 'Supervisor (Edição Completa)',
    'admin': 'Administrador (Acesso Total)'
}

def render_page():
    # Container principal com refresh/carregamento dinâmico
    container = ui.column().classes('w-full q-pa-lg gap-6')

    def reload_admin_data():
        container.clear()
        
        # Carregar solicitações pendentes e usuários
        db_conn = get_db_connection()
        requests_data = []
        users_data = []
        is_offline = not db_conn

        if db_conn:
            try:
                # Solicitações pendentes
                req_res = db_conn.table('RegistrationRequests').select('*').eq('status', 'pending').execute()
                requests_data = req_res.data if req_res.data else []

                # Usuários existentes
                users_res = db_conn.table('Users').select('*').execute()
                users_data = users_res.data if users_res.data else []
            except Exception as e:
                print(f"[ADMIN] Erro ao carregar dados do Supabase: {e}")
                is_offline = True

        if is_offline:
            # Fallbacks mockados para desenvolvimento offline
            requests_data = [
                {
                    'id': 'mock-req-1',
                    'email': 'joao.silva@marinha.mil.br',
                    'nome_completo': 'João da Silva Souza',
                    'nome_guerra': 'SILVA',
                    'status': 'pending',
                    'created_at': '2026-05-29T10:00:00+00'
                }
            ]
            users_data = [
                {'id': '8ff93a11-09ee-4383-b4a3-1e4a86866471', 'username': 'admin', 'nome': 'ADMILSON', 'role': 'admin'},
                {'id': 'mock-user-2', 'username': 'supervisor_teste', 'nome': 'SGT ALVES', 'role': 'supervisor'},
                {'id': 'mock-user-3', 'username': 'comcia_teste', 'nome': 'TEN DUARTE', 'role': 'comcia'}
            ]

        with container:
            theme.section_header('Usuários e Permissões', 'Gestão de Usuários e Aprovação de Credenciais')
            
            if is_offline:
                with ui.row().classes('w-full items-center q-pa-sm rounded-lg text-caption gap-2').style('background: rgba(255, 152, 0, 0.1); border: 1px solid rgba(255, 152, 0, 0.3); color: #ffb300;'):
                    ui.icon('warning', size='1.2rem')
                    ui.label('Banco de dados Supabase offline ou inacessível. Exibindo dados simulados. Ações serão apenas visuais.').classes('font-bold')

            # --- SEÇÃO 1: SOLICITAÇÕES PENDENTES ---
            with theme.card_base().classes('w-full q-pa-md'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('assignment_ind', size='2rem').style(f'color: {THEME["accent"]}')
                        ui.label(f'Solicitações Pendentes ({len(requests_data)})').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                    ui.separator().style('background-color: rgba(0, 229, 255, 0.15);')

                    if not requests_data:
                        ui.label('Não há solicitações de acesso pendentes de aprovação.').classes('italic q-py-md text-sm').style(f'color: {THEME["text_dim"]}')
                    else:
                        with ui.column().classes('w-full gap-3'):
                            for req in requests_data:
                                # Dicionário de estado do role selecionado para esta solicitação
                                state = {'role': 'compel'}
                                
                                with ui.card().classes('w-full q-pa-sm border hover:border-cyan-500/40 bg-black/20').style(f'border-color: rgba(0, 229, 255, 0.1);'):
                                    with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                                        with ui.column().classes('gap-1'):
                                            ui.label(req['nome_completo']).classes('text-subtitle2 font-bold').style(f'color: {THEME["text_main"]}')
                                            with ui.row().classes('gap-4 text-caption').style(f'color: {THEME["text_dim"]}'):
                                                ui.label(f"Guerra: {req['nome_guerra']}")
                                                ui.label(f"E-mail: {req['email']}")
                                                # Formata data
                                                date_str = req.get('created_at', '')[:10] if req.get('created_at') else ''
                                                if date_str:
                                                    ui.label(f"Solicitado em: {date_str}")
                                        
                                        # Controles de aprovação
                                        with ui.row().classes('items-center gap-3'):
                                            ui.select(
                                                ROLE_OPTIONS, 
                                                value='compel',
                                                label='Papel a Atribuir',
                                                on_change=lambda e, s=state: s.update({'role': e.value})
                                            ).props('dark outlined dense').classes('w-60')
                                            
                                            def process_request(req_id=req['id'], req_email=req['email'], req_guerra=req['nome_guerra'], action='', s=state):
                                                if is_offline:
                                                    ui.notify(f"Simulando {action} para o e-mail {req_email}", color='info')
                                                    reload_admin_data()
                                                    return

                                                conn = get_db_connection()
                                                if not conn:
                                                    ui.notify('Sem conexão com banco de dados', color='red')
                                                    return
                                                
                                                try:
                                                    if action == 'approved':
                                                        # 1. Atualiza status na solicitação
                                                        conn.table('RegistrationRequests').update({'status': 'approved'}).eq('id', req_id).execute()
                                                        # 2. Cria/atualiza o perfil de usuário
                                                        conn.table('Users').upsert({
                                                            'id': req_id,
                                                            'username': req_email.split('@')[0],
                                                            'nome': req_guerra,
                                                            'role': s['role']
                                                        }, on_conflict='id').execute()
                                                        ui.notify(f"Usuário {req_guerra} aprovado como {s['role'].upper()}!", color='success')
                                                    else:
                                                        # Rejeitado
                                                        conn.table('RegistrationRequests').update({'status': 'rejected'}).eq('id', req_id).execute()
                                                        ui.notify(f"Solicitação de {req_guerra} rejeitada.", color='warning')
                                                    
                                                    # Recarrega a tela
                                                    data_service.clear_cache()
                                                    reload_admin_data()
                                                except Exception as err:
                                                    ui.notify(f"Erro ao processar solicitação: {err}", color='red')

                                            ui.button(
                                                'Rejeitar', 
                                                on_click=lambda r_id=req['id'], r_email=req['email'], r_g=req['nome_guerra']: process_request(r_id, r_email, r_g, 'rejected')
                                            ).props('outline dense').style(f'color: {THEME["danger"]}; border-color: rgba(255, 23, 68, 0.4);')
                                            
                                            ui.button(
                                                'Aprovar Acesso', 
                                                on_click=lambda r_id=req['id'], r_email=req['email'], r_g=req['nome_guerra']: process_request(r_id, r_email, r_g, 'approved')
                                            ).props('unelevated dense').style(f'background: {THEME["success"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow')

            # --- SEÇÃO 2: USUÁRIOS ATIVOS ---
            with theme.card_base().classes('w-full q-pa-md'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('people', size='2rem').style(f'color: {THEME["accent"]}')
                        ui.label(f'Operadores Cadastrados ({len(users_data)})').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                    ui.separator().style('background-color: rgba(0, 229, 255, 0.15);')

                    if not users_data:
                        ui.label('Nenhum usuário cadastrado.').classes('italic q-py-md text-sm').style(f'color: {THEME["text_dim"]}')
                    else:
                        with ui.column().classes('w-full gap-3'):
                            for u in users_data:
                                with ui.card().classes('w-full q-pa-sm border bg-black/10').style(f'border-color: rgba(0, 229, 255, 0.1);'):
                                    with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                                        with ui.row().classes('items-center gap-3 col-grow'):
                                            ui.avatar('person', size='2rem').style(f'background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); color: {THEME["primary"]};')
                                            with ui.column().classes('gap-0'):
                                                ui.label(u['nome']).classes('font-bold text-sm').style(f'color: {THEME["text_main"]}')
                                                ui.label(f"User: {u['username']}").classes('text-[11px]').style(f'color: {THEME["text_dim"]}')
                                        
                                        # Controle do Telegram ID
                                        with ui.row().classes('items-center gap-2'):
                                            tg_input = ui.input(
                                                label='Telegram ID', 
                                                value=u.get('telegram_id', '') or ''
                                            ).props('dark outlined dense').classes('w-44 font-mono')
                                            
                                            def save_telegram_id(val, user_id=u['id'], username=u['username']):
                                                if is_offline:
                                                    ui.notify(f"[OFFLINE] Telegram ID de {username} alterado para {val}", color='info')
                                                    return
                                                conn = get_db_connection()
                                                if not conn:
                                                    ui.notify('Sem conexão com banco de dados', color='red')
                                                    return
                                                try:
                                                    conn.table('Users').update({'telegram_id': val or None}).eq('id', user_id).execute()
                                                    ui.notify(f"Telegram ID de {username} salvo com sucesso!", color='success')
                                                    data_service.clear_cache()
                                                except Exception as err:
                                                    if 'column "telegram_id" of relation "Users" does not exist' in str(err) or 'telegram_id' in str(err):
                                                        ui.notify('A coluna "telegram_id" não existe na tabela "Users". Execute a migração SQL no seu painel do Supabase.', color='red', duration=10)
                                                    else:
                                                        ui.notify(f"Erro ao salvar Telegram ID: {err}", color='red')

                                            ui.button(
                                                icon='save', 
                                                on_click=lambda e, tgi=tg_input, uid=u['id'], unm=u['username']: save_telegram_id(tgi.value, uid, unm)
                                            ).props('flat round dense color=amber').classes('text-xs')

                                        # Controle de papel
                                        with ui.row().classes('items-center gap-2'):
                                            ui.label('Papel do Usuário:').classes('text-xs').style(f'color: {THEME["text_dim"]}')
                                            
                                            def update_user_role(val, user_id=u['id'], username=u['username']):
                                                if is_offline:
                                                    ui.notify(f"Simulando papel de {username} para {val.value}", color='info')
                                                    return
                                                
                                                conn = get_db_connection()
                                                if not conn:
                                                    ui.notify('Sem conexão com banco de dados', color='red')
                                                    return
                                                
                                                try:
                                                    conn.table('Users').update({'role': val.value}).eq('id', user_id).execute()
                                                    ui.notify(f"Papel de {username} alterado para {val.value.upper()}!", color='success')
                                                    data_service.clear_cache()
                                                except Exception as err:
                                                    ui.notify(f"Erro ao alterar papel: {err}", color='red')

                                            ui.select(
                                                ROLE_OPTIONS, 
                                                value=u.get('role', 'compel'),
                                                on_change=lambda e, u_id=u['id'], u_name=u['username']: update_user_role(e, u_id, u_name)
                                            ).props('dark outlined dense').classes('w-64')

    # Primeiro carregamento
    reload_admin_data()
