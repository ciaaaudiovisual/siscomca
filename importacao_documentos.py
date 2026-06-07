from nicegui import ui
import pandas as pd
import io
import theme
from database import get_db_connection
from services import data_service

THEME = theme.colors

# Estado local para a importação
import_state = {
    'ano_letivo': '2026',
    'dados_novos': [],
    'colunas': []
}

def render_page():
    @ui.refreshable
    def render_import_content():
        with ui.column().classes('w-full gap-6'):
            # --- CARD PRINCIPAL: INSTRUÇÕES E CONFIGURAÇÕES ---
            with theme.card_base().classes('w-full p-6'):
                ui.label('CONFIGURAR IMPORTAÇÃO').classes('cyber-title text-sm font-bold text-white q-mb-md')
                
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
                        # Cria um DataFrame modelo com as colunas padrão
                        modelo_df = pd.DataFrame(columns=[
                            'numero_interno', 'nome_guerra', 'nome_completo', 
                            'pelotao', 'especialidade', 'nip', 'media_academica',
                            'telefone_contato', 'endereco', 'contato_emergencia_nome', 
                            'contato_emergencia_numero', 'numero_armario'
                        ])
                        # Adiciona uma linha de exemplo
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
                        'Baixar Modelo Excel (.xlsx)', 
                        icon='download', 
                        on_click=download_modelo
                    ).props('outline no-caps').classes('q-mb-xs').style(f'color: {THEME["primary"]}; border-color: {THEME["primary"]};')

            # --- CARD UPLOAD E PLANILHA ---
            with theme.card_base().classes('w-full p-6'):
                ui.label('CARREGAR PLANILHA (EXCEL OU CSV)').classes('cyber-title text-sm font-bold text-white q-mb-md')
                
                async def handle_file_upload(e):
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
                            
                        # Limpa espaços em branco dos cabeçalhos
                        df.columns = [c.strip().lower() for c in df.columns]
                        
                        # Validação mínima de colunas obrigatórias
                        colunas_req = ['numero_interno', 'nome_guerra', 'pelotao']
                        colunas_faltantes = [c for c in colunas_req if c not in df.columns]
                        
                        if colunas_faltantes:
                            ui.notify(f"❌ Colunas obrigatórias faltando na planilha: {', '.join(colunas_faltantes)}", color='negative')
                            return
                            
                        import_state['dados_novos'] = df.to_dict(orient='records')
                        import_state['colunas'] = df.columns.tolist()
                        ui.notify(f"✅ Planilha carregada! {len(df)} alunos detectados.", color='positive')
                        render_import_content.refresh()
                        
                    except Exception as err:
                        ui.notify(f"❌ Erro ao ler planilha: {err}", color='negative')

                ui.upload(
                    label='Enviar Arquivo', 
                    on_upload=handle_file_upload, 
                    auto_upload=True,
                    max_files=1
                ).props('dark dense accept=".xlsx,.csv"').classes('w-full h-24')

            # --- CARD IMPORTAÇÃO EM LOTE DE FOTOS ---
            with theme.card_base().classes('w-full p-6'):
                ui.label('IMPORTAÇÃO EM LOTE DE FOTOS').classes('cyber-title text-sm font-bold text-white q-mb-xs')
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
                        # Busca o aluno correspondente pelo número interno e ano letivo
                        res_al = db.table('Alunos').select('id,nome_guerra').eq('numero_interno', ni_aluno).eq('ano_letivo', ano_destino).execute()
                        if not res_al.data:
                            ui.notify(f"⚠️ Aluno Nº {ni_aluno} não encontrado no ano {ano_destino}.", color='warning')
                            return
                            
                        aluno_encontrado = res_al.data[0]
                        aluno_id = aluno_encontrado['id']
                        nome_guerra = aluno_encontrado['nome_guerra']
                        
                        # Formata o nome do arquivo para o bucket adicionando em uma subpasta por ano
                        filename = f"alunos/{ano_destino}/{ni_aluno}{ext.lower()}"
                        
                        # Realiza o upload para o Supabase Storage
                        from database import upload_file_to_supabase_storage
                        public_url = await asyncio.to_thread(
                            upload_file_to_supabase_storage, 
                            file_bytes, 
                            filename, 
                            e.type or "image/jpeg"
                        )
                        
                        if public_url:
                            # Vincula a URL ao registro correspondente do aluno
                            db.table('Alunos').update({'url_foto': public_url}).eq('id', aluno_id).execute()
                            ui.notify(f"📸 Foto vinculada a {nome_guerra} ({ni_aluno})!", color='positive')
                        else:
                            ui.notify(f"❌ Erro ao enviar foto de {ni_aluno} para o storage.", color='negative')
                            
                    except Exception as err:
                        ui.notify(f"❌ Erro no processamento de {ni_aluno}: {err}", color='negative')

                ui.upload(
                    label='Enviar Fotos (Selecione Várias)', 
                    on_upload=handle_image_batch_upload, 
                    auto_upload=True,
                    multiple=True
                ).props('dark dense accept="image/jpeg,image/png"').classes('w-full h-32')

            # --- PRÉVIA E INGESTÃO ---
            if import_state['dados_novos']:
                with theme.card_base().classes('w-full p-6'):
                    ui.label(f"PRÉVIA DOS DADOS (ANO LETIVO DE DESTINO: {import_state['ano_letivo']})").classes('cyber-title text-sm font-bold text-white q-mb-md')
                    
                    # Mostra tabela rápida de prévia (limitado a 5 linhas)
                    preview_data = import_state['dados_novos'][:5]
                    columns_def = [{'name': c, 'label': c, 'field': c, 'align': 'left'} for c in import_state['colunas']]
                    
                    ui.table(
                        columns=columns_def, 
                        rows=preview_data, 
                        row_key='numero_interno'
                    ).props('dark flat dense bordered').classes('w-full overflow-auto max-h-48 q-mb-md')
                    
                    if len(import_state['dados_novos']) > 5:
                        ui.label(f"... e mais {len(import_state['dados_novos']) - 5} alunos.").classes('text-caption text-grey-5 italic q-mb-md')
                        
                    async def executar_importacao():
                        db = get_db_connection()
                        if not db:
                            ui.notify("❌ Sem conexão com o banco de dados.", color='negative')
                            return
                            
                        try:
                            # 1. Carrega alunos existentes para atualizar ou inserir
                            res_ex = db.table('Alunos').select('id,numero_interno').execute()
                            existing_map = {str(r['numero_interno']).strip(): r['id'] for r in res_ex.data} if res_ex.data else {}
                            
                            sucessos = 0
                            erros = 0
                            
                            for rec in import_state['dados_novos']:
                                num_i = str(rec.get('numero_interno', '')).strip()
                                if not num_i or not rec.get('nome_guerra'):
                                    continue
                                    
                                # Prepara dados para o Supabase
                                row_data = {
                                    'numero_interno': num_i,
                                    'nome_guerra': str(rec.get('nome_guerra')).strip(),
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
                                
                                # Se já existir o número interno, faz update. Caso contrário, faz insert.
                                if num_i in existing_map:
                                    db.table('Alunos').update(row_data).eq('id', existing_map[num_i]).execute()
                                else:
                                    db.table('Alunos').insert(row_data).execute()
                                    
                                sucessos += 1
                                
                            ui.notify(f"🎉 Importação concluída! {sucessos} alunos processados com sucesso.", color='positive')
                            
                            # Limpa estado
                            import_state['dados_novos'] = []
                            import_state['colunas'] = []
                            data_service.clear_cache()
                            render_import_content.refresh()
                            
                        except Exception as ex:
                            ui.notify(f"❌ Erro ao salvar dados no Supabase: {ex}", color='negative')
                            
                    with ui.row().classes('w-full justify-end gap-2'):
                        ui.button(
                            'Cancelar', 
                            on_click=lambda: limpar_estado()
                        ).props('flat color=grey no-caps')
                        
                        ui.button(
                            f'CONFIRMAR IMPORTAÇÃO DE {len(import_state["dados_novos"])} ALUNOS', 
                            on_click=executar_importacao
                        ).props('unelevated no-caps').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')

    def update_ano_letivo(val):
        import_state['ano_letivo'] = str(val).strip()
        
    def limpar_estado():
        import_state['dados_novos'] = []
        import_state['colunas'] = []
        render_import_content.refresh()

    with ui.column().classes('w-full q-pa-lg gap-4'):
        theme.section_header('Importação de Dados', 'Upload e Processamento de Arquivos e Planilhas')
        render_import_content()
