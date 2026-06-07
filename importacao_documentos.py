from nicegui import ui, app
import pandas as pd
import io
import theme
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
    with ui.dialog() as confirm_dialog, theme.card_base().classes('q-pa-lg').style('min-width: 650px; max-width: 90%; max-height: 85vh; display: flex; flex-direction: column;'):
        dialog_container = ui.column().classes('w-full gap-4 scroll-area').style('flex-grow: 1; overflow-y: auto;')

    def abrir_modal_confirmacao():
        dialog_container.clear()
        
        novos = import_state['novos_lote']
        atualizar = import_state['atualizar_lote']
        
        with dialog_container:
            ui.label('📊 Confirmação de Importação de Alunos').classes('text-lg font-bold text-white')
            ui.label(f"Destino: Ano Letivo {import_state['ano_letivo']}").classes('text-xs text-grey-4')
            ui.separator().style('background-color: rgba(255,255,255,0.1);')
            
            # Resumo em cards simples
            with ui.row().classes('w-full gap-4'):
                with ui.card().props('flat').classes('col p-3 text-center bg-green-950/20 border border-green-500/20 rounded'):
                    ui.label(str(len(novos))).classes('text-2xl font-bold text-green-400')
                    ui.label('Novos Cadastros').classes('text-[10px] text-grey-4 uppercase')
                with ui.card().props('flat').classes('col p-3 text-center bg-blue-950/20 border border-blue-500/20 rounded'):
                    ui.label(str(len(atualizar))).classes('text-2xl font-bold text-blue-400')
                    ui.label('Cadastros Atualizados').classes('text-[10px] text-grey-4 uppercase')
            
            # Seção: Novos Cadastros
            if novos:
                ui.label('🆕 NOVOS ALUNOS (A SEREM INSERIDOS):').classes('text-xs font-bold text-green-400 q-mt-md')
                with ui.column().classes('w-full border border-white/5 q-pa-sm rounded bg-black/25 max-h-40 overflow-y-auto'):
                    for n in novos:
                        ui.label(f"Nº {n['numero_interno']} - {n['nome_guerra']} ({n['row_data'].get('pelotao', 'Sem Pelotão')})").classes('text-xs text-white/90 font-mono')
            
            # Seção: Atualizações
            if atualizar:
                ui.label('🔄 ATUALIZAÇÃO DE ALUNOS EXISTENTES:').classes('text-xs font-bold text-blue-400 q-mt-md')
                with ui.column().classes('w-full border border-white/5 q-pa-sm rounded bg-black/25 max-h-40 overflow-y-auto'):
                    for a in atualizar:
                        alteracao_nome = ""
                        if a['nome_guerra_antigo'] != a['nome_guerra_novo']:
                            alteracao_nome = f" (Altera nome de {a['nome_guerra_antigo']} -> {a['nome_guerra_novo']})"
                        ui.label(f"Nº {a['numero_interno']} - {a['nome_guerra_novo']}{alteracao_nome}").classes('text-xs text-white/80 font-mono')

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
                        rec = n['row_data']
                        row_data = {
                            'numero_interno': str(n['numero_interno']),
                            'nome_guerra': str(n['nome_guerra']),
                            'nome_completo': str(rec.get('nome_completo', '')).strip(),
                            'pelotao': str(rec.get('pelotao')).strip(),
                            'especialidade': str(rec.get('especialidade', '')).strip(),
                            'nip': str(rec.get('nip', '')).strip(),
                            'media_academica': float(rec.get('media_academica')) if pd.notna(rec.get('media_academica')) and str(rec.get('media_academica')).strip() else 0.0,
                            'telefone_contato': str(rec.get('telefone_contato', '')).strip(),
                            'endereco': str(rec.get('endereco', '')).strip(),
                            'contato_emergencia_nome': str(rec.get('contato_emergencia_nome', '')).strip(),
                            'contato_emergencia_numero': str(rec.get('contato_emergencia_numero', '')).strip(),
                            'numero_armario': str(rec.get('numero_armario', '')).strip(),
                            'ano_letivo': import_state['ano_letivo']
                        }
                        db.table('Alunos').insert(row_data).execute()
                        sucessos += 1
                        
                    # 2. Atualizar Existentes
                    for a in atualizar:
                        rec = a['row_data']
                        row_data = {
                            'nome_guerra': str(a['nome_guerra_novo']),
                            'nome_completo': str(rec.get('nome_completo', '')).strip(),
                            'pelotao': str(rec.get('pelotao')).strip(),
                            'especialidade': str(rec.get('especialidade', '')).strip(),
                            'nip': str(rec.get('nip', '')).strip(),
                            'media_academica': float(rec.get('media_academica')) if pd.notna(rec.get('media_academica')) and str(rec.get('media_academica')).strip() else 0.0,
                            'telefone_contato': str(rec.get('telefone_contato', '')).strip(),
                            'endereco': str(rec.get('endereco', '')).strip(),
                            'contato_emergencia_nome': str(rec.get('contato_emergencia_nome', '')).strip(),
                            'contato_emergencia_numero': str(rec.get('contato_emergencia_numero', '')).strip(),
                            'numero_armario': str(rec.get('numero_armario', '')).strip(),
                            'ano_letivo': import_state['ano_letivo']
                        }
                        db.table('Alunos').update(row_data).eq('id', a['db_id']).execute()
                        sucessos += 1
                    
                    ui.notify(f"🎉 Sucesso! {sucessos} cadastros processados na tabela Alunos.", color='positive')
                    confirm_dialog.close()
                    
                    # Limpa o estado local
                    import_state['dados_novos'] = []
                    import_state['novos_lote'] = []
                    import_state['atualizar_lote'] = []
                    data_service.clear_cache()
                    
                except Exception as ex:
                    ui.notify(f"❌ Erro ao gravar dados no Supabase: {ex}", color='negative', duration=10)

            with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                ui.button('Cancelar', on_click=confirm_dialog.close).props('flat color=grey no-caps')
                ui.button(
                    'Gravar no Banco de Dados (Supabase)', 
                    on_click=processar_gravacao_bd
                ).props('unelevated no-caps').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')
                
        confirm_dialog.open()

    def update_ano_letivo(val):
        import_state['ano_letivo'] = str(val).strip()
        
    def limpar_estado():
        import_state['dados_novos'] = []
        import_state['colunas'] = []
        import_state['novos_lote'] = []
        import_state['atualizar_lote'] = []

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Cadastro de Alunos - Importação de Dados', 'Upload e Processamento de Planilhas e Fotos para o Efetivo de Alunos')

        # --- CARD PRINCIPAL: CONFIGURAÇÕES ---
        with theme.card_base().classes('w-full p-6'):
            ui.label('CONFIGURAR IMPORTAÇÃO DE CADASTROS').classes('cyber-title text-sm font-bold text-white q-mb-md')
            
            with ui.row().classes('w-full items-end gap-6 wrap'):
                # Ano Letivo Selector
                ano_input = ui.input(
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
                # Executa no contexto do cliente WebSocket correto
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
                            
                        df.columns = [str(c).strip().lower() for c in df.columns]
                        
                        colunas_req = ['numero_interno', 'nome_guerra', 'pelotao']
                        colunas_faltantes = [c for c in colunas_req if c not in df.columns]
                        
                        if colunas_faltantes:
                            ui.notify(f"❌ Colunas obrigatórias faltando: {', '.join(colunas_faltantes)}", color='negative', duration=5)
                            ui.notify(f"📋 Colunas encontradas na sua planilha: {', '.join(df.columns)}", color='warning', duration=10)
                            return
                        
                        rows = df.to_dict(orient='records')
                        db = get_db_connection()
                        if not db:
                            ui.notify("❌ Sem conexão com o banco de dados.", color='negative')
                            return
                            
                        # Carrega alunos já existentes para o ano letivo selecionado para fazer o split (insert/update)
                        res_ex = db.table('Alunos').select('id,numero_interno,nome_guerra').eq('ano_letivo', import_state['ano_letivo']).execute()
                        existing_map = {str(r['numero_interno']).strip(): r for r in res_ex.data} if res_ex.data else {}
                        
                        novos = []
                        atualizar = []
                        
                        for rec in rows:
                            num_i = str(rec.get('numero_interno', '')).strip()
                            if not num_i or not rec.get('nome_guerra'):
                                continue
                            
                            if num_i in existing_map:
                                existing_item = existing_map[num_i]
                                atualizar.append({
                                    'db_id': existing_item['id'],
                                    'numero_interno': num_i,
                                    'nome_guerra_antigo': existing_item['nome_guerra'],
                                    'nome_guerra_novo': str(rec.get('nome_guerra')).strip(),
                                    'row_data': rec
                                })
                            else:
                                novos.append({
                                    'numero_interno': num_i,
                                    'nome_guerra': str(rec.get('nome_guerra')).strip(),
                                    'row_data': rec
                                })
                        
                        import_state['dados_novos'] = rows
                        import_state['colunas'] = df.columns.tolist()
                        import_state['novos_lote'] = novos
                        import_state['atualizar_lote'] = atualizar
                        
                        ui.notify("✅ Planilha processada!", color='positive')
                        
                        try:
                            e.sender.reset()
                        except Exception:
                            pass
                            
                        # Abre o modal com os dados separados para o usuário confirmar
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
