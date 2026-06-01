from nicegui import ui, app
import pandas as pd
import io
import re
import theme
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from difflib import SequenceMatcher

THEME = theme.colors

# Colunas padrão do modelo
COLUNAS_TEMPLATE = [
    'NOME COMPLETO', 'POSTO/GRAD', 'NIP', 'ENDERECO_COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
    'SOLDO', 'DIAS_UTEIS', 'DESPESA_DIARIA',
    'EMPRESA_IDA_1', 'TRAJETO_IDA_1', 'TARIFA_IDA_1',
    'EMPRESA_VOLTA_1', 'TRAJETO_VOLTA_1', 'TARIFA_VOLTA_1'
]

def create_excel_template():
    """Cria um template .xlsx em memória"""
    df_template = pd.DataFrame(columns=COLUNAS_TEMPLATE)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Modelo')
    return output.getvalue()

def clean_text(text: str) -> str:
    if not isinstance(text, str): return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def find_best_match(target_field: str, available_columns: list, threshold=0.6) -> str:
    if not target_field or not available_columns: return ""
    clean_target = clean_text(target_field)
    best_match = ""
    highest_score = 0.0
    for option in available_columns:
        if option == "-- Não Mapear --": continue
        clean_option = clean_text(option)
        score = SequenceMatcher(None, clean_target, clean_option).ratio()
        if score > highest_score:
            highest_score, best_match = score, option
    if highest_score >= threshold:
        return best_match
    return ""

def fill_pdf_form(template_bytes: bytes, data_row: dict, mapping: dict) -> bytes:
    """Preenche um formulário PDF usando a biblioteca PyMuPDF (fitz)"""
    doc = fitz.open(stream=template_bytes, filetype="pdf")
    for page in doc:
        for widget in page.widgets():
            field_name = widget.field_name
            if field_name in mapping:
                csv_column = mapping[field_name]
                if csv_column != "-- Não Mapear --" and csv_column in data_row:
                    value = str(data_row.get(csv_column, ''))
                    widget.field_value = value
                    widget.update()
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=3, deflate=True)
    doc.close()
    return output_buffer.getvalue()

def merge_pdfs(pdf_buffers: list) -> bytes:
    """Junta uma lista de PDFs usando PyPDF2"""
    merger = PdfWriter()
    for buf in pdf_buffers:
        reader = PdfReader(io.BytesIO(buf))
        for page in reader.pages:
            merger.add_page(page)
    output_buffer = io.BytesIO()
    merger.write(output_buffer)
    merger.close()
    return output_buffer.getvalue()

def render_page():
    # Carrega dados do estado do usuário
    state = app.storage.user.get('transporte_state', {
        'dados_xlsx': [],       # list of dicts
        'colunas_xlsx': [],
        'pdf_template_bytes': None, # bytes as base64 or stored in memory
        'pdf_fields': [],
        'mapeamento_pdf': {},    # dict {field_name: csv_column}
        'pdf_resultado_bytes': None
    })
    app.storage.user['transporte_state'] = state

    # Nós mantemos os bytes brutos do PDF em uma variável global da sessão em memória
    # já que storage.user converte para JSON e pode corromper/pesar o storage se convertermos bytes longos
    if 'pdf_template_data' not in app.storage.user:
        app.storage.user['pdf_template_data'] = None
    if 'pdf_resultado_data' not in app.storage.user:
        app.storage.user['pdf_resultado_data'] = None

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Auxílio Transporte', 'Mapeamento e Geração Automatizada de Formulários de Auxílio Transporte em Lote')

        # Tabs de Etapas (Wizard)
        with ui.tabs().classes('w-full').style(f'border-bottom: {THEME["border"]}') as tabs:
            tab_carregar = ui.tab('1. Carregar Dados', icon='cloud_upload')
            tab_mapear = ui.tab('2. Mapear PDF', icon='schema')
            tab_gerar = ui.tab('3. Gerar Documentos', icon='picture_as_pdf')

        with ui.tab_panels(tabs, value=tab_carregar).classes('w-full bg-transparent p-0'):
            
            # --- ABA 1: CARREGAR DADOS ---
            with ui.tab_panel(tab_carregar):
                with ui.row().classes('w-full gap-6 wrap lg:no-wrap items-start'):
                    # Upload Card
                    with ui.column().classes('w-full lg:w-4/12 gap-4'):
                        ui.label('BAIXAR MODELO OU SUBIR ARQUIVO').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                        
                        with theme.card_base().classes('w-full q-pa-md'):
                            ui.label('Baixe o template contendo as colunas corretas antes de carregar seus dados:').classes('text-xs q-mb-md').style(f'color: {THEME["text_dim"]}')
                            
                            # Baixar modelo
                            def download_modelo():
                                template_bytes = create_excel_template()
                                ui.download(template_bytes, filename="modelo_auxilio_transporte.xlsx")
                                
                            ui.button('Baixar Modelo Excel (.xlsx)', icon='file_download', on_click=download_modelo).props('outline no-caps w-full').style(f'color: {THEME["primary"]}; border-color: {THEME["primary"]}').classes('q-mb-md')
                            
                            # Upload do Excel/CSV
                            ui.label('Carregue os dados dos alunos (CSV ou Excel):').classes('text-xs font-bold q-mb-xs').style(f'color: {THEME["text_main"]}')
                            
                            def handle_data_upload(e):
                                try:
                                    file_bytes = e.content.read()
                                    if e.name.endswith('.csv'):
                                        # Tenta diferentes encodings
                                        for encoding in ['utf-8', 'latin-1', 'cp1252']:
                                            try:
                                                df = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding=encoding, dtype=str).fillna('')
                                                break
                                            except UnicodeDecodeError:
                                                continue
                                    else:
                                        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str).fillna('')
                                        
                                    state['dados_xlsx'] = df.to_dict(orient='records')
                                    state['colunas_xlsx'] = df.columns.tolist()
                                    app.storage.user['transporte_state'] = state
                                    ui.notify(f"Arquivo '{e.name}' carregado ({len(df)} registros)", color='positive')
                                    ui.navigate.reload()
                                except Exception as ex:
                                    ui.notify(f"Erro ao processar: {ex}", color='negative')
                                    
                            ui.upload(label='Enviar CSV ou Excel', auto_upload=True, on_upload=handle_data_upload).classes('w-full dark')

                    # Preview Card
                    with ui.column().classes('w-full lg:w-8/12 gap-4'):
                        ui.label('VISUALIZAÇÃO DOS DADOS CARREGADOS').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                        
                        if not state['dados_xlsx']:
                            with ui.card().classes('w-full q-pa-lg text-center').style('background: transparent; border: 1px dashed rgba(0, 229, 255, 0.25) !important; border-radius: 8px;'):
                                ui.label('Nenhum dado de transporte carregado na planilha.').classes('italic text-sm').style(f'color: {THEME["text_dim"]}')
                        else:
                            with theme.card_base().classes('w-full q-pa-md'):
                                columns_def = [{'name': c, 'label': c, 'field': c, 'align': 'left'} for c in state['colunas_xlsx']]
                                ui.table(columns=columns_def, rows=state['dados_xlsx'], row_key='NOME COMPLETO').props('dark flat dense bordered').classes('w-full max-h-[300px] overflow-auto')
                                
                                # Botão para limpar
                                def limpar_planilha():
                                    state['dados_xlsx'] = []
                                    state['colunas_xlsx'] = []
                                    app.storage.user['transporte_state'] = state
                                    ui.notify('Planilha removida', color='info')
                                    ui.navigate.reload()
                                    
                                ui.button('Remover Tabela', icon='delete', on_click=limpar_planilha).props('flat dense no-caps').classes('q-mt-sm').style(f'color: {THEME["danger"]}')

            # --- ABA 2: MAPEAR CAMPOS PDF ---
            with ui.tab_panel(tab_mapear):
                if not state['dados_xlsx']:
                    with ui.card().classes('w-full q-pa-lg text-center').style('background: transparent; border: 1px dashed rgba(0, 229, 255, 0.25) !important; border-radius: 8px;'):
                        ui.label('Por favor, carregue os dados dos alunos na Aba 1 antes de mapear os campos do PDF.').classes('italic text-sm').style(f'color: {THEME["text_dim"]}')
                else:
                    with ui.row().classes('w-full gap-6 wrap lg:no-wrap items-start'):
                        # Upload PDF Template
                        with ui.column().classes('w-full lg:w-4/12 gap-4'):
                            ui.label('CARREGAR MODELO PDF EDITÁVEL').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                            
                            with theme.card_base().classes('w-full q-pa-md'):
                                ui.label('Envie um PDF preenchível (com campos de formulário editáveis):').classes('text-xs q-mb-sm').style(f'color: {THEME["text_dim"]}')
                                
                                def handle_pdf_upload(e):
                                    try:
                                        pdf_bytes = e.content.read()
                                        # Extrai campos do PDF
                                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                                        fields = []
                                        for page in doc:
                                            for widget in page.widgets():
                                                if widget.field_name and widget.field_name not in fields:
                                                    fields.append(widget.field_name)
                                        doc.close()
                                        
                                        if not fields:
                                            ui.notify('Nenhum campo de formulário editável encontrado no PDF!', color='warning')
                                            return
                                            
                                        # Salva em sessão
                                        app.storage.user['pdf_template_data'] = io.BytesIO(pdf_bytes).getvalue()
                                        state['pdf_fields'] = fields
                                        
                                        # Tenta mapear automaticamente
                                        df_cols = ["-- Não Mapear --"] + state['colunas_xlsx']
                                        state['mapeamento_pdf'] = {}
                                        for f in fields:
                                            suggestion = find_best_match(f, df_cols)
                                            state['mapeamento_pdf'][f] = suggestion if suggestion else "-- Não Mapear --"
                                            
                                        app.storage.user['transporte_state'] = state
                                        ui.notify(f"PDF carregado! Encontrados {len(fields)} campos.", color='positive')
                                        ui.navigate.reload()
                                    except Exception as ex:
                                        ui.notify(f"Erro ao ler PDF: {ex}", color='negative')
                                        
                                ui.upload(label='Enviar PDF Editável', auto_upload=True, on_upload=handle_pdf_upload).classes('w-full dark')

                        # Form de Mapeamento
                        with ui.column().classes('w-full lg:w-8/12 gap-4'):
                            ui.label('ASSOCIAÇÃO DE CAMPOS DO PDF').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                            
                            if not state['pdf_fields']:
                                with ui.card().classes('w-full q-pa-lg text-center').style('background: transparent; border: 1px dashed rgba(0, 229, 255, 0.25) !important; border-radius: 8px;'):
                                    ui.label('Carregue o modelo PDF para ver e associar os campos.').classes('italic text-sm').style(f'color: {THEME["text_dim"]}')
                            else:
                                with theme.card_base().classes('w-full q-pa-md max-h-[500px] overflow-auto'):
                                    ui.label('Associe os campos detectados no PDF com as colunas da sua planilha carregada:').classes('text-xs font-bold q-mb-md').style(f'color: {THEME["text_main"]}')
                                    
                                    df_cols = ["-- Não Mapear --"] + sorted(state['colunas_xlsx'])
                                    
                                    # Renderiza cada select de campo
                                    for f in sorted(state['pdf_fields']):
                                        val_atual = state['mapeamento_pdf'].get(f, "-- Não Mapear --")
                                        if val_atual not in df_cols:
                                            val_atual = "-- Não Mapear --"
                                            
                                        def make_mapping_change(campo=f):
                                            def handler(e):
                                                state['mapeamento_pdf'][campo] = e.value
                                                app.storage.user['transporte_state'] = state
                                            return handler
                                            
                                        with ui.row().classes('w-full justify-between items-center gap-4 q-py-xs').style('border-bottom: 1px solid rgba(0, 229, 255, 0.08)'):
                                            ui.label(f"`{f}`").classes('text-xs font-mono').style(f'color: {THEME["accent"]}')
                                            ui.select(df_cols, value=val_atual, on_change=make_mapping_change()).props('dark outlined dense').classes('w-64')

                                    ui.button('Confirmar Mapeamento', icon='check', on_click=lambda: ui.notify('Mapeamento confirmado!', color='positive')).props('unelevated no-caps w-full q-mt-md').style(f'background: {THEME["primary"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow')

            # --- ABA 3: GERAR DOCUMENTOS ---
            with ui.tab_panel(tab_gerar):
                if not state['dados_xlsx'] or not state['mapeamento_pdf']:
                    with ui.card().classes('w-full q-pa-lg text-center').style('background: transparent; border: 1px dashed rgba(0, 229, 255, 0.25) !important; border-radius: 8px;'):
                        ui.label('Falta carregar planilha (Aba 1) ou mapear o PDF (Aba 2) para liberar a geração.').classes('italic text-sm').style(f'color: {THEME["text_dim"]}')
                else:
                    with theme.card_base().classes('w-full q-pa-md text-center'):
                        ui.label('PRONTO PARA GERAÇÃO').classes('cyber-title text-sm q-mb-xs').style(f'color: {THEME["primary"]}')
                        ui.label(f"Registros a processar: {len(state['dados_xlsx'])}").classes('text-caption q-mb-md').style(f'color: {THEME["text_dim"]}')

                        # Botão de processamento
                        def iniciar_geracao():
                            template_bytes = app.storage.user.get('pdf_template_data')
                            if not template_bytes:
                                ui.notify('Erro: Dados do PDF expiraram em memória. Reenvie o PDF na Aba 2.', color='negative')
                                return
                                
                            try:
                                mapping = state['mapeamento_pdf']
                                records = state['dados_xlsx']
                                
                                filled_pdfs = []
                                for r in records:
                                    filled_bytes = fill_pdf_form(template_bytes, r, mapping)
                                    filled_pdfs.append(filled_bytes)
                                    
                                # Junta tudo
                                merged_pdf = merge_pdfs(filled_pdfs)
                                app.storage.user['pdf_resultado_data'] = merged_pdf
                                
                                ui.notify('PDFs preenchidos e consolidados com sucesso!', color='positive')
                                ui.navigate.reload()
                            except Exception as ex:
                                ui.notify(f"Erro na geração dos PDFs: {ex}", color='negative')
                                
                        ui.button('Processar e Gerar PDF Consolidado', icon='settings_suggest', on_click=iniciar_geracao).props('unelevated no-caps w-full').style(f'background: {THEME["success"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow q-mb-md')
                        
                        # Exibe botão de download se já gerou
                        resultado_bytes = app.storage.user.get('pdf_resultado_data')
                        if resultado_bytes:
                            def baixar_consolidado():
                                ui.download(resultado_bytes, filename="Auxilio_Transporte_Consolidado.pdf")
                                ui.notify('Download iniciado!', color='positive')
                                
                            ui.button('Baixar Relatório Consolidado (.pdf)', icon='file_download', on_click=baixar_consolidado).props('unelevated no-caps w-full').style(f'background: {THEME["danger"]}; color: #ffffff; font-weight: bold;').classes('cyber-glow')
