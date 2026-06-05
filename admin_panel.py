from nicegui import ui, app
import theme
from database import get_db_connection
from services import data_service

THEME = theme.colors

# Opções de papéis/roles no sistema
ROLE_OPTIONS = {
    'compel': 'Compel (Aluno/Apenas Visualização)',
    'comcia': 'Comcia (Comandante de Cia/Edição Limitada)',
    'supervisor': 'Supervisor (Edição Completa)',
    'admin': 'Administrador (Acesso Total)',
    'aluno': 'Aluno (Visualização)',
    'ajosca': 'Ajosca (Acesso Ajosca)',
    'tv': 'Modo TV/Monitor'
}

def render_page():
    # Container principal com refresh/carregamento dinâmico
    container = ui.column().classes('w-full q-pa-lg gap-6')
    selected_user_ids = set()

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
            
            # Vamos garantir que os dados mockados possuam url_foto e telegram_id para testes perfeitos
            users_data = [
                {'id': '8ff93a11-09ee-4383-b4a3-1e4a86866471', 'username': 'admin', 'nome': 'ADMILSON', 'role': 'admin', 'telegram_id': '123456789', 'url_foto': 'https://cdn.quasar.dev/img/avatar.png'},
                {'id': 'mock-user-2', 'username': 'supervisor_teste', 'nome': 'SGT ALVES', 'role': 'supervisor', 'telegram_id': '987654321', 'url_foto': ''},
                {'id': 'mock-user-3', 'username': 'comcia_teste', 'nome': 'TEN DUARTE', 'role': 'comcia', 'telegram_id': '', 'url_foto': ''}
            ]

        # --- DIÁLOGOS ADMINISTRATIVOS ---

        # 1. Diálogo de Criação de Operador
        def open_create_dialog():
            with ui.dialog() as create_dialog, ui.card().classes('w-[420px] q-pa-md bg-slate-900 border').style(f'border-color: {THEME["accent"]};'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center gap-2 w-full justify-between'):
                        ui.label('➕ CADASTRAR OPERADOR').classes('text-white text-md font-black cyber-title')
                        ui.icon('person_add', size='1.5rem').style(f'color: {THEME["accent"]}')
                    ui.separator().style('background-color: rgba(0, 229, 255, 0.15);')

                    c_email = ui.input('E-mail (Login)', placeholder='militar@marinha.mil.br').props('dark outlined dense w-full')
                    c_pwd = ui.input('Senha Inicial', password=True).props('dark outlined dense w-full')
                    c_nome = ui.input('Nome de Guerra').props('dark outlined dense w-full')
                    c_tg = ui.input('Telegram ID (Opcional)').props('dark outlined dense w-full')
                    c_foto = ui.input('URL da Foto (Opcional)').props('dark outlined dense w-full')
                    
                    async def handle_c_upload(e):
                        import re
                        import uuid
                        import inspect
                        import asyncio
                        file_bytes = e.file.read()
                        if inspect.isawaitable(file_bytes):
                            file_bytes = await file_bytes
                        clean_name = re.sub(r'\W+', '', c_nome.value or 'operador').lower()
                        filename = f"operadores/{clean_name}_{uuid.uuid4().hex[:8]}.jpg"
                        from database import upload_file_to_supabase_storage
                        public_url = await asyncio.to_thread(upload_file_to_supabase_storage, file_bytes, filename, e.file.content_type)
                        if public_url:
                            c_foto.value = public_url
                            ui.notify('Foto enviada com sucesso!', color='success')
                        else:
                            ui.notify('Erro ao enviar foto ao Supabase.', color='red')
                    
                    ui.upload(label='Enviar Foto para o Supabase', on_upload=handle_c_upload, auto_upload=True, max_files=1).props('dark dense').classes('w-full h-20')
                    
                    c_role = ui.select(ROLE_OPTIONS, label='Papel do Usuário', value='compel').props('dark outlined dense w-full')
                    
                    c_error = ui.label('').classes('text-xs text-red w-full text-center')
                    
                    def handle_create():
                        try:
                            # SEGURANÇA: Verificação de privilégios server-side
                            user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
                            if user_role not in ('ADMIN', 'SUPERVISOR'):
                                ui.notify("⛔ Acesso negado. Apenas administradores ou supervisores.", color='negative')
                                return
                            if not c_email.value or not c_pwd.value or not c_nome.value:
                                c_error.text = 'E-mail, Senha e Nome de Guerra são obrigatórios.'
                                return
                            
                            import bcrypt
                            pwd_hash = bcrypt.hashpw(c_pwd.value.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
                            
                            if is_offline:
                                ui.notify(f"[OFFLINE] Novo operador {c_nome.value.upper()} cadastrado!", color='success')
                                users_data.append({
                                    'id': f'mock-uid-{len(users_data)+1}',
                                    'username': c_email.value.split('@')[0],
                                    'nome': c_nome.value.upper(),
                                    'role': c_role.value,
                                    'telegram_id': c_tg.value or '',
                                    'url_foto': c_foto.value or ''
                                })
                                create_dialog.close()
                                reload_admin_data()
                                return
                            
                            conn = get_db_connection()
                            if not conn:
                                ui.notify('Sem conexão com banco de dados', color='red')
                                return
                            
                            auth_id = None
                            admin_conn = None
                            from database import get_bot_db_connection
                            try:
                                admin_conn = get_bot_db_connection()
                            except Exception:
                                pass
                            
                            if admin_conn and hasattr(admin_conn, 'auth') and hasattr(admin_conn.auth, 'admin'):
                                try:
                                    res = admin_conn.auth.admin.create_user({
                                        "email": c_email.value,
                                        "password": c_pwd.value,
                                        "email_confirm": True
                                    })
                                    if res and res.user:
                                        auth_id = res.user.id
                                except Exception as auth_err:
                                    print(f"[AUTH ERROR] Tentando signup direto: {auth_err}")
                            
                            if not auth_id:
                                # Fallback para signup regular
                                try:
                                    res = conn.auth.sign_up({"email": c_email.value, "password": c_pwd.value})
                                    if res and res.user:
                                        auth_id = res.user.id
                                except Exception as sign_err:
                                    print(f"[SIGNUP ERR] {sign_err}")
                                    ui.notify("Limite do Supabase Auth atingido. Criando usuário no banco local...", color='warning', duration=5)
                            
                            if not auth_id:
                                import uuid
                                auth_id = str(uuid.uuid4())
                                ui.notify('Operador registrado com sucesso no banco de dados local!', color='success')

                            # Insere na tabela Users
                            try:
                                conn.table('Users').insert({
                                    'id': auth_id,
                                    'username': c_email.value.split('@')[0],
                                    'nome': c_nome.value.upper(),
                                    'role': c_role.value,
                                    'telegram_id': c_tg.value or None,
                                    'url_foto': c_foto.value or None
                                }).execute()
                            except Exception as db_err:
                                if 'url_foto' in str(db_err):
                                    # Fallback: salva sem a coluna url_foto
                                    conn.table('Users').insert({
                                        'id': auth_id,
                                        'username': c_email.value.split('@')[0],
                                        'nome': c_nome.value.upper(),
                                        'role': c_role.value,
                                        'telegram_id': c_tg.value or None
                                    }).execute()
                                    ui.notify('Operador cadastrado sem foto. Adicione a coluna url_foto no Supabase!', color='warning', duration=6)
                                else:
                                    raise db_err
                            
                            # Cria também na tabela efetivo para manter integridade
                            try:
                                try:
                                    conn.table('efetivo').insert({
                                        'telegram_id': c_tg.value or None,
                                        'nome_guerra': c_nome.value.upper(),
                                        'email': c_email.value,
                                        'senha_hash': pwd_hash,
                                        'role': c_role.value,
                                        'url_foto': c_foto.value or None
                                    }).execute()
                                except Exception as db_err:
                                    if 'url_foto' in str(db_err):
                                        conn.table('efetivo').insert({
                                            'telegram_id': c_tg.value or None,
                                            'nome_guerra': c_nome.value.upper(),
                                            'email': c_email.value,
                                            'senha_hash': pwd_hash,
                                            'role': c_role.value
                                        }).execute()
                                    else:
                                        raise db_err
                            except Exception as db_err:
                                print(f"[DB WARN] Sincronização parcial em efetivo: {db_err}")
                            
                            ui.notify(f"Operador {c_nome.value.upper()} cadastrado com sucesso!", color='success')
                            data_service.clear_cache()
                            create_dialog.close()
                            reload_admin_data()
                        except Exception as err:
                            c_error.text = f"Erro: {err}"
                    
                    with ui.row().classes('w-full justify-end gap-2'):
                        ui.button('Cancelar', on_click=create_dialog.close).props('flat color=grey')
                        ui.button('Cadastrar', on_click=handle_create).props('unelevated color=cyan-9 text-color=white')
            create_dialog.open()

        # 2. Diálogo de Edição de Operador
        def open_edit_dialog(user):
            user_email = ""
            db_conn = get_db_connection()
            if db_conn:
                try:
                    res_ef = db_conn.table('efetivo').select('email').eq('nome_guerra', user.get('nome', '').upper()).execute()
                    if res_ef.data and res_ef.data[0].get('email'):
                        user_email = res_ef.data[0]['email']
                    else:
                        if user.get('telegram_id'):
                            res_ef2 = db_conn.table('efetivo').select('email').eq('telegram_id', user['telegram_id']).execute()
                            if res_ef2.data and res_ef2.data[0].get('email'):
                                user_email = res_ef2.data[0]['email']
                except Exception as ef_err:
                    print(f"[EDIT EMAIL LOOKUP ERR] {ef_err}")

            with ui.dialog() as edit_dialog, ui.card().classes('w-[420px] q-pa-md bg-slate-900 border').style(f'border-color: {THEME["accent"]};'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center gap-2 w-full justify-between'):
                        ui.label('✏️ EDITAR OPERADOR').classes('text-white text-md font-black cyber-title')
                        ui.icon('edit', size='1.5rem').style(f'color: {THEME["accent"]}')
                    ui.separator().style('background-color: rgba(0, 229, 255, 0.15);')

                    e_nome = ui.input('Nome de Guerra', value=user.get('nome', '')).props('dark outlined dense w-full')
                    e_email = ui.input('E-mail (Login)', value=user_email).props('dark outlined dense w-full')
                    e_unm = ui.input('Username (Login)', value=user.get('username', '')).props('dark outlined dense w-full')
                    e_tg = ui.input('Telegram ID', value=user.get('telegram_id', '') or '').props('dark outlined dense w-full')
                    
                    # Layout de duas colunas: Esquerda (URL), Direita (Preview da foto)
                    with ui.row().classes('w-full items-start gap-4 no-wrap'):
                        with ui.column().classes('col-grow gap-2'):
                            e_foto = ui.input('URL da Foto', value=user.get('url_foto', '') or '').props('dark outlined dense w-full').classes('text-xs')
                        
                        # Preview do Avatar
                        user_photo = user.get('url_foto') or ''
                        user_avatar_src = user_photo if isinstance(user_photo, str) and user_photo.startswith('http') else 'https://cdn.quasar.dev/img/boy-avatar.png'
                        with ui.column().classes('items-center justify-center shrink-0'):
                            img_box = ui.element('div').classes('shadow border border-cyan-500/30').style(
                                f"width: 72px; height: 72px; background-image: url('{user_avatar_src}'); "
                                f"background-size: cover; background-repeat: no-repeat; "
                                f"background-position: center; background-color: #050b14; border-radius: 4px;"
                            )
                            ui.label('FOTO').classes('text-[9px] text-grey-5 font-bold tracking-widest q-mt-xs')
                    
                    # Uploader de arquivos
                    async def handle_e_upload(e):
                        import re
                        import inspect
                        import asyncio
                        file_bytes = e.file.read()
                        if inspect.isawaitable(file_bytes):
                            file_bytes = await file_bytes
                        clean_name = re.sub(r'\W+', '', e_nome.value or 'operador').lower()
                        filename = f"operadores/{clean_name}_{user['id'][:8]}.jpg"
                        from database import upload_file_to_supabase_storage
                        public_url = await asyncio.to_thread(upload_file_to_supabase_storage, file_bytes, filename, e.file.content_type)
                        if public_url:
                            e_foto.value = public_url
                            img_box.style(f"background-image: url('{public_url}');")
                            ui.notify('Foto enviada com sucesso!', color='success')
                        else:
                            ui.notify('Erro ao enviar foto ao Supabase.', color='red')
                            
                    ui.upload(label='Fazer Upload de Nova Foto', on_upload=handle_e_upload, auto_upload=True, max_files=1).props('dark dense').classes('w-full h-20')
                    
                    def update_foto_preview():
                        src = e_foto.value.strip() if e_foto.value else ''
                        if not src.startswith('http'):
                            src = 'https://cdn.quasar.dev/img/boy-avatar.png'
                        img_box.style(f"background-image: url('{src}');")
                        
                    e_foto.on('change', update_foto_preview)
                    
                    e_role = ui.select(ROLE_OPTIONS, label='Papel do Usuário', value=user.get('role', 'compel')).props('dark outlined dense w-full')
                    
                    e_error = ui.label('').classes('text-xs text-red w-full text-center')
                    
                    def handle_edit():
                        # SEGURANÇA: Verificação de privilégios server-side
                        user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
                        if user_role not in ('ADMIN', 'SUPERVISOR'):
                            ui.notify("⛔ Acesso negado. Apenas administradores ou supervisores.", color='negative')
                            return
                        if not e_nome.value or not e_unm.value:
                            e_error.text = 'Nome de Guerra e Username são obrigatórios.'
                            return
                        
                        if is_offline:
                            ui.notify(f"[OFFLINE] Dados de {user['username']} atualizados!", color='success')
                            user['nome'] = e_nome.value.upper()
                            user['username'] = e_unm.value
                            user['telegram_id'] = e_tg.value or ''
                            user['url_foto'] = e_foto.value or ''
                            user['role'] = e_role.value
                            edit_dialog.close()
                            reload_admin_data()
                            return
                        
                        conn = get_db_connection()
                        if not conn:
                            ui.notify('Sem conexão com banco de dados', color='red')
                            return
                        
                        try:
                            # 1. Atualiza o e-mail no Supabase Auth se fornecido e alterado
                            if e_email.value and e_email.value.strip() != user_email:
                                from database import get_bot_db_connection
                                admin_conn = None
                                try:
                                    admin_conn = get_bot_db_connection()
                                except Exception:
                                    pass
                                if admin_conn and hasattr(admin_conn, 'auth') and hasattr(admin_conn.auth, 'admin'):
                                    try:
                                        admin_conn.auth.admin.update_user_by_id(user['id'], {"email": e_email.value.strip()})
                                    except Exception as auth_email_err:
                                        print(f"[AUTH EMAIL UPDATE ERR] {auth_email_err}")

                            # 2. Atualiza a tabela Users
                            try:
                                conn.table('Users').update({
                                    'nome': e_nome.value.upper(),
                                    'username': e_unm.value,
                                    'telegram_id': e_tg.value or None,
                                    'url_foto': e_foto.value or None,
                                    'role': e_role.value
                                }).eq('id', user['id']).execute()
                            except Exception as db_err:
                                if 'url_foto' in str(db_err):
                                    conn.table('Users').update({
                                        'nome': e_nome.value.upper(),
                                        'username': e_unm.value,
                                        'telegram_id': e_tg.value or None,
                                        'role': e_role.value
                                    }).eq('id', user['id']).execute()
                                    ui.notify('Operador atualizado sem foto. Adicione a coluna url_foto no Supabase!', color='warning', duration=6)
                                else:
                                    raise db_err
                            
                            # 3. Tenta manter a integridade da tabela efetivo
                            try:
                                update_fields = {
                                    'nome_guerra': e_nome.value.upper(),
                                    'telegram_id': e_tg.value or None,
                                    'role': e_role.value,
                                    'email': e_email.value or None,
                                    'url_foto': e_foto.value or None
                                }
                                try:
                                    ef_query = conn.table('efetivo').update(update_fields)
                                    if user_email:
                                        ef_query.eq('email', user_email).execute()
                                    elif user.get('telegram_id'):
                                        ef_query.eq('telegram_id', user.get('telegram_id')).execute()
                                    else:
                                        ef_query.eq('nome_guerra', user.get('nome', '').upper()).execute()
                                except Exception as db_err:
                                    if 'url_foto' in str(db_err):
                                        update_fields.pop('url_foto', None)
                                        ef_query_alt = conn.table('efetivo').update(update_fields)
                                        if user_email:
                                            ef_query_alt.eq('email', user_email).execute()
                                        elif user.get('telegram_id'):
                                            ef_query_alt.eq('telegram_id', user.get('telegram_id')).execute()
                                        else:
                                            ef_query_alt.eq('nome_guerra', user.get('nome', '').upper()).execute()
                                    else:
                                        raise db_err
                            except Exception as sync_err:
                                print(f"[DB WARN] Erro ao sincronizar efetivo: {sync_err}")
                            
                            ui.notify(f"Cadastro de {e_nome.value.upper()} atualizado!", color='success')
                            data_service.clear_cache()
                            edit_dialog.close()
                            reload_admin_data()
                        except Exception as err:
                            e_error.text = f"Erro: {err}"
                            
                    # Botões de Ação (recuados para ficarem dentro da coluna do diálogo)
                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                        ui.button('Cancelar', on_click=edit_dialog.close).props('flat color=grey')
                        ui.button('Salvar', on_click=handle_edit).props('unelevated color=cyan-9 text-color=white')
            edit_dialog.open()

        # 3. Diálogo de Redefinição de Senha
        def open_password_dialog(user):
            with ui.dialog() as pwd_dialog, ui.card().classes('w-[380px] q-pa-md bg-slate-900 border border-amber-500/30'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center gap-2 w-full justify-between'):
                        ui.label('🔑 ALTERAR SENHA').classes('text-white text-md font-black cyber-title')
                        ui.icon('lock_reset', size='1.5rem').style('color: #ffb300;')
                    ui.separator().style('background-color: rgba(255, 179, 0, 0.15);')
                    
                    ui.label(f"Alterar senha para: {user['nome']}").classes('text-xs text-grey-4')
                    new_pwd = ui.input('Nova Senha', password=True).props('dark outlined dense w-full')
                    pwd_error = ui.label('').classes('text-xs text-red w-full text-center')
                    
                    def handle_password():
                        # SEGURANÇA: Verificação de privilégios server-side
                        user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
                        if user_role not in ('ADMIN', 'SUPERVISOR'):
                            ui.notify("⛔ Acesso negado. Apenas administradores ou supervisores.", color='negative')
                            return
                        if not new_pwd.value or len(new_pwd.value) < 6:
                            pwd_error.text = 'A senha deve conter no mínimo 6 caracteres.'
                            return
                        
                        import bcrypt
                        pwd_hash = bcrypt.hashpw(new_pwd.value.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
                        
                        if is_offline:
                            ui.notify(f"[OFFLINE] Senha de {user['nome']} redefinida!", color='success')
                            pwd_dialog.close()
                            return
                        
                        conn = get_db_connection()
                        if not conn:
                            ui.notify('Sem conexão com banco de dados', color='red')
                            return
                        
                        try:
                            from database import get_bot_db_connection
                            admin_conn = None
                            try:
                                admin_conn = get_bot_db_connection()
                            except Exception:
                                pass
                            
                            auth_updated = False
                            if admin_conn and hasattr(admin_conn, 'auth') and hasattr(admin_conn.auth, 'admin'):
                                try:
                                    admin_conn.auth.admin.update_user_by_id(user['id'], {"password": new_pwd.value})
                                    auth_updated = True
                                except Exception as auth_err:
                                    print(f"[AUTH PASSWORD UPDATE ERROR] {auth_err}")
                            
                            # Atualiza também a tabela efetivo
                            try:
                                if user.get('telegram_id'):
                                    conn.table('efetivo').update({'senha_hash': pwd_hash}).or_(f"telegram_id.eq.{user['telegram_id']},nome_guerra.eq.{user.get('nome', '').upper()}").execute()
                                else:
                                    conn.table('efetivo').update({'senha_hash': pwd_hash}).eq('nome_guerra', user.get('nome', '').upper()).execute()
                            except Exception as db_err:
                                print(f"[DB PASSWORD UPDATE ERR] {db_err}")
                            
                            if auth_updated:
                                ui.notify(f"Senha de {user['nome']} alterada com sucesso!", color='success')
                            else:
                                ui.notify(f"Senha atualizada no DB! Nota: Sem permissão service_role para redefinir no Auth.", color='warning')
                            
                            data_service.clear_cache()
                            pwd_dialog.close()
                        except Exception as err:
                            pwd_error.text = f"Erro: {err}"
            
                    # Botões de Ação (dentro da coluna do diálogo)
                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                        ui.button('Cancelar', on_click=pwd_dialog.close).props('flat color=grey')
                        ui.button('Alterar Senha', on_click=handle_password).props('unelevated color=amber-9 text-color=black')
            pwd_dialog.open()

        # 4. Diálogo de Confirmação de Exclusão
        def open_delete_dialog(user):
            with ui.dialog() as del_dialog, ui.card().classes('w-[380px] q-pa-md bg-slate-900 border border-red-500/30'):
                with ui.column().classes('w-full gap-4 items-center text-center'):
                    ui.icon('warning', color='red', size='3rem').classes('animate-pulse')
                    ui.label('CONFIRMAR EXCLUSÃO').classes('text-white text-md font-black cyber-title')
                    ui.label(f"Tem certeza que deseja excluir o acesso de {user['nome']} ({user['username']})?").classes('text-sm text-grey-4')
                    ui.label('Esta ação removerá definitivamente o militar das permissões do painel.').classes('text-xs text-red-400 font-bold')
                    
                    del_error = ui.label('').classes('text-xs text-red w-full')
                    
                    def handle_delete():
                        # SEGURANÇA: Apenas administradores reais podem excluir
                        user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
                        if user_role != 'ADMIN':
                            ui.notify("⛔ Acesso negado. Apenas administradores podem excluir operadores.", color='negative')
                            return
                        if is_offline:
                            ui.notify(f"[OFFLINE] Operador {user['nome']} removido!", color='success')
                            if user in users_data:
                                users_data.remove(user)
                            del_dialog.close()
                            reload_admin_data()
                            return
                        
                        conn = get_db_connection()
                        if not conn:
                            ui.notify('Sem conexão com banco de dados', color='red')
                            return
                        
                        try:
                            from database import get_bot_db_connection
                            admin_conn = None
                            try:
                                admin_conn = get_bot_db_connection()
                            except Exception:
                                pass
                            
                            if admin_conn and hasattr(admin_conn, 'auth') and hasattr(admin_conn.auth, 'admin'):
                                try:
                                    admin_conn.auth.admin.delete_user(user['id'])
                                except Exception as auth_err:
                                    print(f"[AUTH DELETE ERROR] {auth_err}")
                            
                            # Remove das tabelas locais
                            conn.table('Users').delete().eq('id', user['id']).execute()
                            try:
                                conn.table('efetivo').delete().eq('telegram_id', user.get('telegram_id')).execute()
                            except Exception:
                                pass
                            
                            ui.notify(f"Operador {user['nome']} removido!", color='success')
                            data_service.clear_cache()
                            del_dialog.close()
                            reload_admin_data()
                        except Exception as err:
                            del_error.text = f"Erro: {err}"
            
                    # Botões de Ação (dentro da coluna do diálogo)
                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                        ui.button('Cancelar', on_click=del_dialog.close).props('flat color=grey')
                        ui.button('Confirmar Exclusão', on_click=handle_delete).props('unelevated color=red text-color=white')
            del_dialog.open()

        # 5. Diálogo de Confirmação de Exclusão em Lote
        def open_batch_delete_dialog(uids):
            selected_users_objs = [u for u in users_data if u['id'] in uids]
            names_str = ", ".join([u['nome'] for u in selected_users_objs])
            with ui.dialog() as batch_del_dialog, ui.card().classes('w-[420px] q-pa-md bg-slate-900 border border-red-500/30'):
                with ui.column().classes('w-full gap-4 items-center text-center'):
                    ui.icon('warning', color='red', size='3rem').classes('animate-pulse')
                    ui.label('CONFIRMAR EXCLUSÃO EM LOTE').classes('text-white text-md font-black cyber-title')
                    ui.label(f"Tem certeza que deseja excluir o acesso de {len(uids)} operadores selecionados?").classes('text-sm text-grey-4')
                    ui.label(f"Operadores: {names_str}").classes('text-xs text-amber-400 font-mono max-h-24 overflow-y-auto w-full')
                    ui.label('Esta ação removerá definitivamente todos os militares selecionados.').classes('text-xs text-red-400 font-bold')
                    
                    del_error = ui.label('').classes('text-xs text-red w-full')
                    
                    def handle_batch_delete():
                        # SEGURANÇA: Apenas administradores reais podem excluir em lote
                        user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
                        if user_role != 'ADMIN':
                            ui.notify("⛔ Acesso negado. Apenas administradores podem excluir operadores em lote.", color='negative')
                            return
                        if is_offline:
                            ui.notify(f"[OFFLINE] Removido {len(uids)} operadores!", color='success')
                            for uid in list(uids):
                                for u in list(users_data):
                                    if u['id'] == uid:
                                        users_data.remove(u)
                            uids.clear()
                            batch_del_dialog.close()
                            reload_admin_data()
                            return
                        
                        conn = get_db_connection()
                        if not conn:
                            ui.notify('Sem conexão com banco de dados', color='red')
                            return
                        
                        try:
                            from database import get_bot_db_connection
                            admin_conn = None
                            try:
                                admin_conn = get_bot_db_connection()
                            except Exception:
                                pass
                            
                            # Tenta remover do Auth para cada usuário
                            for uid in uids:
                                if admin_conn and hasattr(admin_conn, 'auth') and hasattr(admin_conn.auth, 'admin'):
                                    try:
                                        admin_conn.auth.admin.delete_user(uid)
                                    except Exception as auth_err:
                                        print(f"[AUTH BATCH DELETE ERROR] {auth_err} for uid {uid}")
                            
                            # Remove da tabela Users
                            conn.table('Users').delete().in_('id', list(uids)).execute()
                            
                            # Tenta remover também da tabela efetivo
                            for u in selected_users_objs:
                                if u.get('telegram_id'):
                                    try:
                                        conn.table('efetivo').delete().eq('telegram_id', u['telegram_id']).execute()
                                    except Exception:
                                        pass
                            
                            ui.notify(f"{len(uids)} operadores removidos com sucesso!", color='success')
                            uids.clear()
                            data_service.clear_cache()
                            batch_del_dialog.close()
                            reload_admin_data()
                        except Exception as err:
                            del_error.text = f"Erro: {err}"
            
                    # Botões de Ação (dentro da coluna do diálogo)
                    with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                        ui.button('Cancelar', on_click=batch_del_dialog.close).props('flat color=grey')
                        ui.button('Confirmar Exclusão em Lote', on_click=handle_batch_delete).props('unelevated color=red text-color=white')
            batch_del_dialog.open()

        # --- FIM DIÁLOGOS ---

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
                                state = {'role': 'compel'}
                                
                                with ui.card().classes('w-full q-pa-sm border hover:border-cyan-500/40 bg-black/20').style(f'border-color: rgba(0, 229, 255, 0.1);'):
                                    with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                                        with ui.column().classes('gap-1'):
                                            ui.label(req['nome_completo']).classes('text-subtitle2 font-bold').style(f'color: {THEME["text_main"]}')
                                            with ui.row().classes('gap-4 text-caption').style(f'color: {THEME["text_dim"]}'):
                                                ui.label(f"Guerra: {req['nome_guerra']}")
                                                ui.label(f"E-mail: {req['email']}")
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
                                                # SEGURANÇA: Verificação de privilégios server-side
                                                user_role = str(app.storage.user.get('user_data', {}).get('role', '')).upper()
                                                if user_role not in ('ADMIN', 'SUPERVISOR'):
                                                    ui.notify("⛔ Acesso negado. Apenas administradores ou supervisores podem aprovar/rejeitar solicitações.", color='negative')
                                                    return
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
                                                        conn.table('RegistrationRequests').update({'status': 'approved'}).eq('id', req_id).execute()
                                                        conn.table('Users').upsert({
                                                            'id': req_id,
                                                            'username': req_email.split('@')[0],
                                                            'nome': req_guerra,
                                                            'role': s['role']
                                                        }, on_conflict='id').execute()
                                                        ui.notify(f"Usuário {req_guerra} aprovado como {s['role'].upper()}!", color='success')
                                                    else:
                                                        conn.table('RegistrationRequests').update({'status': 'rejected'}).eq('id', req_id).execute()
                                                        ui.notify(f"Solicitação de {req_guerra} rejeitada.", color='warning')
                                                    
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

            # --- SEÇÃO 2: USUÁRIOS ATIVOS (CRUD COMPLETO) ---
            with theme.card_base().classes('w-full q-pa-md'):
                with ui.column().classes('w-full gap-4'):
                    with ui.row().classes('items-center justify-between w-full'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('people', size='2rem').style(f'color: {THEME["accent"]}')
                            ui.label(f'Operadores Cadastrados ({len(users_data)})').classes('text-lg font-bold').style(f'color: {THEME["text_main"]}')
                        
                        with ui.row().classes('gap-2 items-center'):
                            # Selecionar/Desselecionar Todos
                            all_ids = {u['id'] for u in users_data}
                            all_selected = all_ids == selected_user_ids if all_ids else False
                            
                            def toggle_select_all():
                                if all_selected:
                                    selected_user_ids.clear()
                                else:
                                    selected_user_ids.update(all_ids)
                                reload_admin_data()
                                
                            ui.button(
                                '⬜ DESSELECIONAR TODOS' if all_selected else '☑️ SELECIONAR TODOS',
                                on_click=toggle_select_all
                            ).props('outline dense color=cyan').classes('text-xs px-3 py-1.5')

                            # Botão de exclusão em lote
                            batch_count = len(selected_user_ids)
                            batch_del_btn = ui.button(
                                f'🗑️ EXCLUIR SELECIONADOS ({batch_count})',
                                on_click=lambda: open_batch_delete_dialog(selected_user_ids)
                            ).props('unelevated dense color=red').classes('text-xs px-3 py-1.5')
                            batch_del_btn.set_visibility(batch_count > 0)
                            
                            # Botão administrativo para novo cadastro direto
                            ui.button(
                                '➕ CADASTRAR OPERADOR',
                                on_click=open_create_dialog
                            ).props('unelevated dense').style(f'background: {THEME["accent"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow text-xs px-3 py-1.5')

                    ui.separator().style('background-color: rgba(0, 229, 255, 0.15);')

                    if not users_data:
                        ui.label('Nenhum operador cadastrado.').classes('italic q-py-md text-sm').style(f'color: {THEME["text_dim"]}')
                    else:
                        with ui.column().classes('w-full gap-3'):
                            for u in users_data:
                                with ui.card().classes('w-full q-pa-sm border bg-black/10 hover:border-cyan-500/20 transition-all').style(f'border-color: rgba(0, 229, 255, 0.1);'):
                                    with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                                        # 1. Informações básicas + Foto de Perfil Quadrada
                                        with ui.row().classes('items-center gap-3 col-grow'):
                                            # Checkbox para seleção em lote
                                            def on_checkbox_change(e, uid=u['id']):
                                                if e.value:
                                                    selected_user_ids.add(uid)
                                                else:
                                                    selected_user_ids.discard(uid)
                                                count = len(selected_user_ids)
                                                batch_del_btn.set_visibility(count > 0)
                                                batch_del_btn.text = f'🗑️ EXCLUIR SELECIONADOS ({count})'
                                            
                                            ui.checkbox(
                                                value=u['id'] in selected_user_ids,
                                                on_change=on_checkbox_change
                                            ).props('dense dark color=red')

                                            # Foto de Perfil Tática
                                            user_photo = u.get('url_foto') or ''
                                            user_avatar_src = user_photo if isinstance(user_photo, str) and user_photo.startswith('http') else 'https://cdn.quasar.dev/img/boy-avatar.png'
                                            role_color = '#00e676' if u.get('role') == 'admin' else '#00b0ff' if u.get('role') == 'supervisor' else '#e040fb' if u.get('role') == 'comcia' else '#ff9100' if u.get('role') == 'aluno' else '#d500f9' if u.get('role') == 'ajosca' else '#90a4ae'
                                            ui.element('div').classes('shadow border shrink-0').style(
                                                f"width: 48px; height: 48px; background-image: url('{user_avatar_src}'); "
                                                f"background-size: cover; background-repeat: no-repeat; "
                                                f"background-position: center; background-color: #050b14; "
                                                f"border: 2px solid {role_color}; border-radius: 4px;"
                                            )
                                            with ui.column().classes('gap-0.5'):
                                                with ui.row().classes('items-center gap-2'):
                                                    ui.label(u['nome']).classes('font-black text-sm uppercase').style(f'color: {THEME["text_main"]}')
                                                    role_text = ROLE_OPTIONS.get(u.get('role', 'compel'), 'Compel').split(' (')[0]
                                                    ui.label(role_text.upper()).classes('text-[9px] font-bold px-1.5 py-0.5 rounded border').style(
                                                        f"color: {role_color}; border-color: {role_color}40; background: {role_color}10;"
                                                    )
                                                with ui.row().classes('items-center gap-4 text-[11px]').style(f'color: {THEME["text_dim"]}'):
                                                    ui.label(f"User: {u['username']}")
                                                    if u.get('telegram_id'):
                                                        ui.label(f"TG ID: {u['telegram_id']}").classes('font-mono text-cyan-400')
                                                    else:
                                                        ui.label("TG ID: não associado").classes('italic')
                                        
                                        # 2. Ações Administrativas (Editar Perfil, Alterar Senha, Excluir)
                                        with ui.row().classes('items-center gap-2'):
                                            # Editar Perfil
                                            ui.button(
                                                icon='edit',
                                                on_click=lambda e, user=u: open_edit_dialog(user)
                                            ).props('flat round dense color=primary').classes('text-xs').style('background: rgba(0, 229, 255, 0.05);')
                                            ui.tooltip('Editar Perfil')
                                            
                                            # Alterar Senha
                                            ui.button(
                                                icon='vpn_key',
                                                on_click=lambda e, user=u: open_password_dialog(user)
                                            ).props('flat round dense color=amber-9').classes('text-xs').style('background: rgba(255, 193, 7, 0.05);')
                                            ui.tooltip('Redefinir Senha')
                                            
                                            # Excluir
                                            ui.button(
                                                icon='delete',
                                                on_click=lambda e, user=u: open_delete_dialog(user)
                                            ).props('flat round dense color=red').classes('text-xs').style('background: rgba(255, 23, 68, 0.05);')
                                            ui.tooltip('Excluir Operador')

    # Primeiro carregamento
    reload_admin_data()
