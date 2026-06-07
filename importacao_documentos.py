from nicegui import ui, app
import pandas as pd
import io
import theme
import unicodedata
from database import get_db_connection
from services import data_service

THEME = theme.colors

def render_page():
    # Estado local isolado para esta sessão/cliente
    import_state = {
        'ano_letivo': '2026',
        'dados_novos': [],
        'colunas': [],
        'novos_lote': [],
        'atualizar_lote': []
    }

    # Diálogo/Modal de Confirmação Detalhado
    with ui.dialog() as confirm_dialog:
        with theme.card_base().classes('q-pa-lg').style('min-width: 800px; max-width: 95%; max-height: 90vh; display: flex; flex-direction: column;'):
            dialog_container = ui.column().classes('w-full gap-4').style('flex-grow: 1; overflow: hidden;')

    def abrir_modal_confirmacao():
        dialog_container.clear()
        
        novos = import_state['novos_lote']
        atualizar = import_state['atualizar_lote']
        
        with dialog_container:
            ui.label('📊 Confirmação de Importação de Alunos').classes('text-xl font-bold text-white')
            ui.label(f"Destino: Ano Letivo {import_state['ano_letivo']}").classes('text-xs text-grey-4')
            ui.separator().style('background-color: rgba(255,255,255,0.1);')
            
            # Resumo em cards simples
            with ui.row().classes('w-full gap-4'):
                with ui.card().props('flat').classes('col p-4 text-center bg-green-950/20 border border-green-500/20 rounded-xl'):
                    ui.label(str(len(novos))).classes('text-3xl font-bold text-green-400')
                    ui.label('Novos Cadastros').classes('text-xs text-grey-4 uppercase font-bold')
                with ui.card().props('flat').classes('col p-4 text-center bg-blue-950/20 border border-blue-500/20 rounded-xl'):
                    ui.label(str(len(atualizar))).classes('text-3xl font-bold text-blue-400')
                    ui.label('Cadastros Atualizados').classes('text-xs text-grey-4 uppercase font-bold')
            
            # Conteúdo rolável com as tabelas
            with ui.column().classes('w-full scroll-area q-py-sm gap-4').style('flex-grow: 1; overflow-y: auto; max-height: 50vh;'):
                # Tabela de Novos
                if novos:
                    ui.label('🆕 NOVOS ALUNOS (A SEREM INSERIDOS):').classes('text-xs font-bold text-green-400')
                    columns_novos = [
                        {'name': 'numero_interno', 'label': 'Nº Interno', 'field': 'numero_interno', 'align': 'left', 'sortable': True},
                        {'name': 'nome_guerra', 'label': 'Nome Guerra', 'field': 'nome_guerra', 'align': 'left', 'sortable': True},
                        {'name': 'pelotao', 'label': 'Pelotão', 'field': 'pelotao', 'align': 'left', 'sortable': True},
                        {'name': 'nome_completo', 'label': 'Nome Completo', 'field': 'nome_completo', 'align': 'left'},
                        {'name': 'nip', 'label': 'NIP', 'field': 'nip', 'align': 'left'}
                    ]
                    rows_novos = [n['mapped_data'] for n in novos]
                    ui.table(columns=columns_novos, rows=rows_novos, row_key='numero_interno').props('dark flat dense bordered').classes('w-full max-h-48 overflow-auto')
                
                # Tabela de Atualizações
                if atualizar:
                    ui.label('🔄 ATUALIZAÇÕES DE ALUNOS EXISTENTES:').classes('text-xs font-bold text-blue-400')
                    columns_up = [
                        {'name': 'numero_interno', 'label': 'Nº Interno', 'field': 'numero_interno', 'align': 'left', 'sortable': True},
                        {'name': 'nome_guerra_antigo', 'label': 'Guerra Antigo', 'field': 'nome_guerra_antigo', 'align': 'left'},
                        {'name': 'nome_guerra_novo', 'label': 'Guerra Novo', 'field': 'nome_guerra_novo', 'align': 'left'},
                        {'name': 'pelotao_antigo', 'label': 'Pelotão Antigo', 'field': 'pelotao_antigo', 'align': 'left'},
                        {'name': 'pelotao_novo', 'label': 'Pelotão Novo', 'field': 'pelotao_novo', 'align': 'left'}
                    ]
                    rows_up = []
                    for a in atualizar:
                        rows_up.append({
                            'numero_interno': a['numero_interno'],
                            'nome_guerra_antigo': a['nome_guerra_antigo'],
                            'nome_guerra_novo': a['nome_guerra_novo'],
                            'pelotao_antigo': a['pelotao_antigo'],
                            'pelotao_novo': a['mapped_data'].get('pelotao', '')
                        })
                    ui.table(columns=columns_up, rows=rows_up, row_key='numero_interno').props('dark flat dense bordered').classes('w-full max-h-48 overflow-auto')

            ui.separator().style('background-color: rgba(255,255,255,0.1);')
            
            async def processar_gravacao_bd():
                db = get_db_connection()
                if not db:
                    ui.notify("❌ Sem conexão com o banco de dados.", color='negative')
                    return
                
                try:
                    sucessos = 0
                    
                    # 1. Inserir Novos
                    for n in novos:
                        row_data = n['mapped_data'].copy()
                        row_data['ano_letivo'] = import_state['ano_letivo']
                        
                        # Garantir conversões de tipos
                        if 'media_academica' in row_data and row_data['media_academica'] is not None:
                            try:
                                row_data['media_academica'] = float(row_data['media_academica'])
                            except ValueError:
                                row_data['media_academica'] = 0.0
                        else:
                            row_data['media_academica'] = 0.0
                            
                        db.table('Alunos').insert(row_data).execute()
                        sucessos += 1
                        
                    # 2. Atualizar Existentes
                    for a in atualizar:
                        row_data = a['mapped_data'].copy()
                        row_data['ano_letivo'] = import_state['ano_letivo']
                        
                        # Garantir conversões de tipos
                        if 'media_academica' in row_data and row_data['media_academica'] is not None:
                            try:
                                row_data['media_academica'] = float(row_data['media_academica'])
                            except ValueError:
                                row_data['media_academica'] = 0.0
                        else:
                            row_data['media_academica'] = 0.0
                            
                        db.table('Alunos').update(row_data).eq('id', a['db_id']).execute()
                        sucessos += 1
                    
                    ui.notify(f"🎉 Importação concluída! {sucessos} alunos processados na tabela Alunos.", color='positive')
                    confirm_dialog.close()
                    
                    # Limpa o estado local
                    import_state['dados_novos'] = []
                    import_state['novos_lote'] = []
                    import_state['atualizar_lote'] = []
                    data_service.clear_cache()
                    
                except Exception as ex:
                    ui.notify(f"❌ Erro ao gravar dados no Supabase: {ex}", color='negative', duration=10)
 
            with ui.row().classes('w-full justify-end gap-2 q-mt-sm'):
                ui.button('Cancelar', on_click=confirm_dialog.close).props('flat color=grey no-caps')
                ui.button(
                    'Gravar no Banco de Dados (Supabase)', 
                    on_click=processar_gravacao_bd
                ).props('unelevated no-caps').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')
                
        confirm_dialog.open()

    def update_ano_letivo(val):
        import_state['ano_letivo'] = str(val).strip()

    def mapear_colunas(df_columns):
        mapeadas = {}
        
        def simplificar(c):
            c = str(c).strip().lower()
            c = "".join(x for x in unicodedata.normalize('NFD', c) if unicodedata.category(x) != 'Mn')
            return c.replace(' ', '_').replace('.', '').replace('-', '_').replace('__', '_')
        
        # 1. Mapear numero_interno
        for c in df_columns:
            sc = simplificar(c)
            if sc in ['numero_interno', 'num_interno', 'n_interno', 'numero', 'n', 'no', 'nº', 'num', 'matricula', 'id']:
                mapeadas['numero_interno'] = c
                break
                
        # 2. Mapear pelotao
        for c in df_columns:
            sc = simplificar(c)
            if sc in ['pelotao', 'pelotao_de_formacao', 'turma', 'pel']:
                mapeadas['pelotao'] = c
                break
                
        # 3. Mapear nome_completo e nome_guerra
        for c in df_columns:
            sc = simplificar(c)
            if sc in ['nome_completo', 'nome_inteiro', 'nome_todo', 'completo']:
                mapeadas['nome_completo'] = c
                break
                
        for c in df_columns:
            sc = simplificar(c)
            if sc in ['nome_guerra', 'guerra', 'nome_de_guerra']:
                mapeadas['nome_guerra'] = c
                break
                
        if 'nome_guerra' not in mapeadas:
            for c in df_columns:
                sc = simplificar(c)
                if sc == 'nome' and c != mapeadas.get('nome_completo'):
                    mapeadas['nome_guerra'] = c
                    break
                    
        if 'nome_guerra' not in mapeadas and 'nome_completo' not in mapeadas:
            for c in df_columns:
                sc = simplificar(c)
                if sc == 'nome':
                    mapeadas['nome_guerra'] = c
                    mapeadas['nome_completo'] = c
                    break
                    
        if 'nome_guerra' not in mapeadas:
            for c in df_columns:
                sc = simplificar(c)
                if 'nome' in sc:
                    mapeadas['nome_guerra'] = c
                    break
                    
        # 4. Outros campos
        outros_mapeamentos = {
            'especialidade': ['especialidade', 'esp', 'arma', 'quadro', 'especializacao'],
            'nip': ['nip'],
            'media_academica': ['media_academica', 'media', 'nota', 'coeficiente', 'cr'],
            'telefone_contato': ['telefone_contato', 'telefone', 'celular', 'contato', 'tel'],
            'endereco': ['endereco', 'rua', 'residencia', 'morada', 'bairro'],
            'contato_emergencia_nome': ['contato_emergencia_nome', 'emergencia_nome', 'nome_emergencia', 'responsavel'],
            'contato_emergencia_numero': ['contato_emergencia_numero', 'emergencia_telefone', 'telefone_emergencia', 'tel_emergencia', 'contato_emergencia'],
            'numero_armario': ['numero_armario', 'armario', 'escaninho']
        }
        
        for dest, opcoes in outros_mapeamentos.items():
            for c in df_columns:
                sc = simplificar(c)
                if sc in opcoes:
                    mapeadas[dest] = c
                    break
                    
        return mapeadas

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Cadastro de Alunos - Importação de Dados', 'Upload e Processamento de Planilhas e Fotos para o Efetivo de Alunos')

        # --- CARD PRINCIPAL: CONFIGURAÇÕES ---
        with theme.card_base().classes('w-full p-6'):
            ui.label('CONFIGURAR IMPORTAÇÃO DE CADASTROS').classes('cyber-title text-sm font-bold text-white q-mb-md')
            
            with ui.row().classes('w-full items-end gap-6 wrap'):
                # Ano Letivo Selector
                ui.input(
                    'Ano Letivo de Destino*', 
                    value=import_state['ano_letivo'],
                    on_change=lambda e: update_ano_letivo(e.value)
                ).props('dark outlined dense').classes('w-64')
                
                # Botão para baixar modelo
                def download_modelo():
                    output = io.BytesIO()
                    modelo_df = pd.DataFrame(columns=[
                        'numero_interno', 'nome_guerra', 'nome_completo', 
                        'pelotao', 'especialidade', 'nip', 'media_academica',
                        'telefone_contato', 'endereco', 'contato_emergencia_nome', 
                        'contato_emergencia_numero', 'numero_armario'
                    ])
                    modelo_df.loc[0] = [
                        '101', 'Silva', 'João da Silva', 'Alfa', 'Infantaria',
                        '12345678', '8.5', '21999998888', 'Av. Brasil, 100',
                        'Maria da Silva', '21999997777', 'A-12'
                    ]
                    
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        modelo_df.to_excel(writer, index=False, sheet_name='Alunos')
                    
                    output.seek(0)
                    ui.download(output.read(), filename="modelo_importacao_alunos.xlsx")
                
                ui.button(
                    'Baixar Planilha Modelo (.xlsx)', 
                    icon='download', 
                    on_click=download_modelo
                ).props('outline no-caps').classes('q-mb-xs').style(f'color: {THEME["primary"]}; border-color: {THEME["primary"]};')

        # --- CARD UPLOAD E PLANILHA ---
        with theme.card_base().classes('w-full p-6'):
            ui.label('CARREGAR PLANILHA DE ALUNOS (EXCEL OU CSV)').classes('cyber-title text-sm font-bold text-white q-mb-md')
            
            async def handle_file_upload(e):
                with e.client:
                    ui.notify("Lendo arquivo enviado...", color='info')
                    try:
                        e.content.seek(0)
                    except Exception:
                        pass
                    
                    file_bytes = e.content.read()
                    import inspect
                    if inspect.isawaitable(file_bytes):
                        file_bytes = await file_bytes
                    filename = e.name.lower()
                    
                    try:
                        if filename.endswith('.csv'):
                            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
                        else:
                            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
                            
                        # Limpar espaços em branco dos nomes das colunas
                        df.columns = [str(c).strip() for c in df.columns]
                        
                        col_mapping = mapear_colunas(df.columns.tolist())
                        
                        # Validar colunas obrigatórias
                        req_fields = ['numero_interno', 'nome_guerra', 'pelotao']
                        faltantes = [f for f in req_fields if f not in col_mapping]
                        
                        if faltantes:
                            ui.notify(f"❌ Não foi possível mapear as colunas obrigatórias: {', '.join(faltantes)}", color='negative', duration=7)
                            ui.notify(f"📋 Colunas encontradas na planilha: {', '.join(df.columns)}", color='warning', duration=10)
                            return
                        
                        rows = df.to_dict(orient='records')
                        db = get_db_connection()
                        if not db:
                            ui.notify("❌ Sem conexão com o banco de dados.", color='negative')
                            return
                            
                        # Carregar alunos já existentes para fazer comparação
                        res_ex = db.table('Alunos').select('id,numero_interno,nome_guerra,pelotao').eq('ano_letivo', import_state['ano_letivo']).execute()
                        existing_map = {str(r['numero_interno']).strip(): r for r in res_ex.data} if res_ex.data else {}
                        
                        novos = []
                        atualizar = []
                        
                        for rec in rows:
                            # Montar record mapeado
                            mapped_data = {}
                            for dest_key, src_key in col_mapping.items():
                                val = rec.get(src_key)
                                mapped_data[dest_key] = str(val).strip() if pd.notna(val) else None
                            
                            num_i = mapped_data.get('numero_interno')
                            nome_g = mapped_data.get('nome_guerra')
                            
                            if not num_i or not nome_g:
                                continue
                            
                            if num_i in existing_map:
                                existing_item = existing_map[num_i]
                                atualizar.append({
                                    'db_id': existing_item['id'],
                                    'numero_interno': num_i,
                                    'nome_guerra_antigo': existing_item['nome_guerra'],
                                    'nome_guerra_novo': nome_g,
                                    'pelotao_antigo': existing_item['pelotao'],
                                    'mapped_data': mapped_data
                                })
                            else:
                                novos.append({
                                    'numero_interno': num_i,
                                    'nome_guerra': nome_g,
                                    'mapped_data': mapped_data
                                })
                        
                        import_state['dados_novos'] = rows
                        import_state['colunas'] = df.columns.tolist()
                        import_state['novos_lote'] = novos
                        import_state['atualizar_lote'] = atualizar
                        
                        ui.notify("✅ Planilha processada com sucesso!", color='positive')
                        
                        try:
                            e.sender.reset()
                        except Exception:
                            pass
                            
                        # Abre o modal com os dados mapeados para o usuário confirmar
                        abrir_modal_confirmacao()
                        
                    except Exception as err:
                        ui.notify(f"❌ Erro ao ler planilha: {err}", color='negative', duration=10)
                        try:
                            e.sender.reset()
                        except Exception:
                            pass

            ui.upload(
                label='Enviar Planilha de Alunos (.xlsx ou .csv)', 
                on_upload=handle_file_upload, 
                auto_upload=True
            ).props('dark dense').classes('w-full')

        # --- CARD IMPORTAÇÃO EM LOTE DE FOTOS ---
        with theme.card_base().classes('w-full p-6'):
            ui.label('IMPORTAÇÃO EM LOTE DE FOTOS DOS ALUNOS').classes('cyber-title text-sm font-bold text-white q-mb-xs')
            ui.label('Selecione ou arraste várias fotos de uma vez (ex: M-1-101.jpg, M-1-102.png). O sistema fará o upload para o Supabase Storage vinculando o ano letivo selecionado e atualizará o perfil de cada aluno automaticamente.').classes('text-xs text-grey-4 q-mb-md')
            
            async def handle_image_batch_upload(e):
                import inspect
                import asyncio
                import os
                
                file_bytes = e.content.read()
                if inspect.isawaitable(file_bytes):
                    file_bytes = await file_bytes
                    
                raw_name, ext = os.path.splitext(e.name)
                ni_aluno = raw_name.strip()
                ano_destino = import_state['ano_letivo']
                
                db = get_db_connection()
                if not db:
                    ui.notify("❌ Sem conexão com o banco de dados.", color='negative')
                    return
                    
                try:
                    res_al = db.table('Alunos').select('id,nome_guerra').eq('numero_interno', ni_aluno).eq('ano_letivo', ano_destino).execute()
                    if not res_al.data:
                        ui.notify(f"⚠️ Aluno Nº {ni_aluno} não encontrado no ano {ano_destino}.", color='warning')
                        return
                        
                    aluno_encontrado = res_al.data[0]
                    aluno_id = aluno_encontrado['id']
                    nome_guerra = aluno_encontrado['nome_guerra']
                    
                    filename = f"alunos/{ano_destino}/{ni_aluno}{ext.lower()}"
                    
                    from database import upload_file_to_supabase_storage
                    public_url = await asyncio.to_thread(
                        upload_file_to_supabase_storage, 
                        file_bytes, 
                        filename, 
                        e.type or "image/jpeg"
                    )
                    
                    if public_url:
                        db.table('Alunos').update({'url_foto': public_url}).eq('id', aluno_id).execute()
                        ui.notify(f"📸 Foto vinculada a {nome_guerra} ({ni_aluno})!", color='positive')
                    else:
                        ui.notify(f"❌ Erro ao enviar foto de {ni_aluno} para o storage.", color='negative')
                        
                except Exception as err:
                    ui.notify(f"❌ Erro no processamento de {ni_aluno}: {err}", color='negative')

            ui.upload(
                label='Enviar Fotos de Perfil (Selecione Várias)', 
                on_upload=handle_image_batch_upload, 
                auto_upload=True,
                multiple=True
            ).props('dark dense accept="image/jpeg,image/png"').classes('w-full')
