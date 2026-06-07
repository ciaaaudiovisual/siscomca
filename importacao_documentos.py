from nicegui import ui, app
import pandas as pd
import io
import asyncio
import inspect as _inspect
import unicodedata
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

    # ──────────────────────────────────────────────
    # Modal de Confirmação
    # ──────────────────────────────────────────────
    confirm_dialog = ui.dialog().props('persistent')

    def abrir_modal_confirmacao():
        confirm_dialog.clear()
        novos   = import_state['novos_lote']
        atualizar = import_state['atualizar_lote']

        with confirm_dialog, theme.card_base().classes('q-pa-lg').style(
            'min-width: 820px; max-width: 96vw; max-height: 88vh; '
            'display: flex; flex-direction: column; gap: 12px;'
        ):
            # ── Cabeçalho ──
            ui.label('📊 Confirmação de Importação — Cadastro de Alunos').classes('text-xl font-bold text-white')
            ui.label(f"📅 Destino: Tabela  Alunos  ·  Ano Letivo  {import_state['ano_letivo']}").classes('text-xs text-grey-4')
            ui.separator().style('background-color: rgba(255,255,255,0.12);')

            # ── Cards de resumo ──
            with ui.row().classes('w-full gap-4'):
                with ui.card().props('flat').classes(
                    'col p-4 text-center rounded-xl'
                ).style('background: rgba(0,200,80,0.08); border: 1px solid rgba(0,200,80,0.30);'):
                    ui.label(str(len(novos))).classes('text-4xl font-bold text-green-400')
                    ui.label('Novos Cadastros').classes('text-xs text-grey-4 uppercase font-bold q-mt-xs')
                with ui.card().props('flat').classes(
                    'col p-4 text-center rounded-xl'
                ).style('background: rgba(33,150,243,0.08); border: 1px solid rgba(33,150,243,0.30);'):
                    ui.label(str(len(atualizar))).classes('text-4xl font-bold text-blue-400')
                    ui.label('Cadastros Atualizados').classes('text-xs text-grey-4 uppercase font-bold q-mt-xs')

            # ── Área rolável com as tabelas ──
            with ui.scroll_area().classes('w-full').style('flex: 1 1 auto; max-height: 42vh;'):
                if novos:
                    ui.label('🆕 NOVOS ALUNOS (SERÃO INSERIDOS NO BD):').classes('text-xs font-bold text-green-400 q-mb-xs')
                    columns_novos = [
                        {'name': 'numero_interno', 'label': 'Nº Interno',    'field': 'numero_interno', 'align': 'left', 'sortable': True},
                        {'name': 'nome_guerra',    'label': 'Nome Guerra',   'field': 'nome_guerra',    'align': 'left', 'sortable': True},
                        {'name': 'pelotao',        'label': 'Pelotão',       'field': 'pelotao',        'align': 'left'},
                        {'name': 'nome_completo',  'label': 'Nome Completo', 'field': 'nome_completo',  'align': 'left'},
                        {'name': 'nip',            'label': 'NIP',           'field': 'nip',            'align': 'left'},
                        {'name': 'especialidade',  'label': 'Especialidade', 'field': 'especialidade',  'align': 'left'},
                    ]
                    rows_novos = [n['mapped_data'] for n in novos]
                    ui.table(
                        columns=columns_novos, rows=rows_novos, row_key='numero_interno'
                    ).props('dark flat dense bordered').classes('w-full q-mb-md')

                if atualizar:
                    ui.label('🔄 ALUNOS EXISTENTES (SERÃO ATUALIZADOS):').classes('text-xs font-bold text-blue-400 q-mb-xs')
                    columns_up = [
                        {'name': 'numero_interno',    'label': 'Nº Interno',     'field': 'numero_interno',    'align': 'left', 'sortable': True},
                        {'name': 'nome_guerra_antigo','label': 'Nome (atual)',    'field': 'nome_guerra_antigo','align': 'left'},
                        {'name': 'nome_guerra_novo',  'label': 'Nome (novo)',     'field': 'nome_guerra_novo',  'align': 'left'},
                        {'name': 'pelotao_antigo',    'label': 'Pelotão (atual)', 'field': 'pelotao_antigo',    'align': 'left'},
                        {'name': 'pelotao_novo',      'label': 'Pelotão (novo)',  'field': 'pelotao_novo',      'align': 'left'},
                    ]
                    rows_up = [{
                        'numero_interno':     a['numero_interno'],
                        'nome_guerra_antigo': a['nome_guerra_antigo'],
                        'nome_guerra_novo':   a['nome_guerra_novo'],
                        'pelotao_antigo':     a['pelotao_antigo'],
                        'pelotao_novo':       a['mapped_data'].get('pelotao', ''),
                    } for a in atualizar]
                    ui.table(
                        columns=columns_up, rows=rows_up, row_key='numero_interno'
                    ).props('dark flat dense bordered').classes('w-full')

                if not novos and not atualizar:
                    ui.label('⚠️ Nenhum dado válido encontrado na planilha.').classes('text-sm text-orange-400')

            ui.separator().style('background-color: rgba(255,255,255,0.12);')

            # ── Botões de ação — SEMPRE visíveis ──
            async def processar_gravacao_bd():
                db = get_db_connection()
                if not db:
                    ui.notify('❌ Sem conexão com o banco de dados.', color='negative')
                    return

                ano = import_state['ano_letivo']
                sucessos = 0
                try:
                    # 1. Inserir Novos
                    for n in novos:
                        row_data = n['mapped_data'].copy()
                        row_data['ano_letivo'] = ano          # ← preenche ano_letivo

                        # Conversão de tipos sensíveis
                        ma = row_data.get('media_academica')
                        try:
                            row_data['media_academica'] = float(ma) if ma else 0.0
                        except (ValueError, TypeError):
                            row_data['media_academica'] = 0.0

                        # Remove chaves None para não sobrescrever colunas com null
                        row_data = {k: v for k, v in row_data.items() if v is not None and str(v).strip() not in ('', 'nan', 'None')}
                        row_data['ano_letivo'] = ano  # garante novamente após limpeza

                        db.table('Alunos').insert(row_data).execute()
                        sucessos += 1

                    # 2. Atualizar Existentes
                    for a in atualizar:
                        row_data = a['mapped_data'].copy()
                        row_data['ano_letivo'] = ano          # ← preenche ano_letivo

                        ma = row_data.get('media_academica')
                        try:
                            row_data['media_academica'] = float(ma) if ma else 0.0
                        except (ValueError, TypeError):
                            row_data['media_academica'] = 0.0

                        row_data = {k: v for k, v in row_data.items() if v is not None and str(v).strip() not in ('', 'nan', 'None')}
                        row_data['ano_letivo'] = ano

                        db.table('Alunos').update(row_data).eq('id', a['db_id']).execute()
                        sucessos += 1

                    ui.notify(
                        f'🎉 Importação concluída! {sucessos} aluno(s) gravados na tabela Alunos (Ano Letivo {ano}).',
                        color='positive', duration=6
                    )
                    confirm_dialog.close()

                    import_state['dados_novos'] = []
                    import_state['novos_lote']  = []
                    import_state['atualizar_lote'] = []
                    data_service.clear_cache()

                except Exception as ex:
                    ui.notify(f'❌ Erro ao gravar no Supabase: {ex}', color='negative', duration=10)

            with ui.row().classes('w-full justify-end gap-3'):
                ui.button('Cancelar', on_click=confirm_dialog.close).props('flat color=grey no-caps')
                ui.button(
                    f'✅ Gravar {len(novos) + len(atualizar)} aluno(s) no Supabase',
                    on_click=processar_gravacao_bd
                ).props('unelevated no-caps').style(
                    f'background: {THEME.get("primary","#00e5ff")}; color: #000; font-weight: bold; font-size: 0.85rem;'
                )

        confirm_dialog.open()

    # ──────────────────────────────────────────────
    # Mapeamento automático de colunas
    # ──────────────────────────────────────────────
    def _norm(c):
        c = str(c).strip().lower()
        c = ''.join(x for x in unicodedata.normalize('NFD', c) if unicodedata.category(x) != 'Mn')
        return c.replace(' ', '_').replace('.', '').replace('-', '_').replace('__', '_')

    def mapear_colunas(cols):
        mapeadas = {}

        _map = {
            'numero_interno':           ['numero_interno','num_interno','n_interno','numero','nro','no','nº','num','matricula','id','cod'],
            'nome_guerra':              ['nome_guerra','guerra','nome_de_guerra'],
            'nome_completo':            ['nome_completo','nome_inteiro','nome_todo','completo','nome_civil'],
            'pelotao':                  ['pelotao','pelotao_de_formacao','turma','pel'],
            'especialidade':            ['especialidade','esp','arma','quadro','especializacao','funcao'],
            'nip':                      ['nip'],
            'media_academica':          ['media_academica','media','nota','coeficiente','cr','iea'],
            'telefone_contato':         ['telefone_contato','telefone','celular','tel','fone'],
            'endereco':                 ['endereco','rua','residencia','morada','bairro','logradouro'],
            'contato_emergencia_nome':  ['contato_emergencia_nome','emergencia_nome','nome_emergencia','responsavel','familiar'],
            'contato_emergencia_numero':['contato_emergencia_numero','emergencia_telefone','telefone_emergencia','tel_emergencia','contato_emergencia'],
            'numero_armario':           ['numero_armario','armario','escaninho'],
        }

        for dest, aliases in _map.items():
            for c in cols:
                if _norm(c) in aliases:
                    mapeadas[dest] = c
                    break

        # Fallback para nome_guerra: qualquer coluna que contenha 'nome'
        if 'nome_guerra' not in mapeadas:
            for c in cols:
                if 'nome' in _norm(c) and c != mapeadas.get('nome_completo'):
                    mapeadas['nome_guerra'] = c
                    break

        return mapeadas

    # ──────────────────────────────────────────────
    # Layout da Página
    # ──────────────────────────────────────────────
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header(
            'Cadastro de Alunos — Importação de Dados',
            'Importe planilhas (.xlsx/.csv) para preencher ou atualizar a tabela Alunos no Supabase'
        )

        # ── Card 1: Configurações ──────────────────
        with theme.card_base().classes('w-full p-6'):
            ui.label('⚙️ CONFIGURAÇÕES DA IMPORTAÇÃO').classes('cyber-title text-sm font-bold text-white q-mb-md')

            with ui.row().classes('w-full items-end gap-6 wrap'):
                ui.input(
                    'Ano Letivo de Destino *',
                    value=import_state['ano_letivo'],
                    on_change=lambda e: import_state.update({'ano_letivo': str(e.value).strip()})
                ).props('dark outlined dense').classes('w-52').tooltip(
                    'O ano aqui definido será gravado na coluna ano_letivo de cada aluno importado'
                )

                def download_modelo():
                    output = io.BytesIO()
                    modelo_df = pd.DataFrame(columns=[
                        'numero_interno', 'nome_guerra', 'nome_completo',
                        'pelotao', 'especialidade', 'nip', 'media_academica',
                        'telefone_contato', 'endereco',
                        'contato_emergencia_nome', 'contato_emergencia_numero',
                        'numero_armario'
                    ])
                    modelo_df.loc[0] = [
                        'M-1-101', 'SILVA', 'JOÃO DA SILVA SOUZA',
                        'MIKE-1', 'AD', '25.1234.56', '8.5',
                        '21999998888', 'Av. Brasil, 100 — Rio de Janeiro/RJ',
                        'Maria da Silva', '21999997777', 'A-12'
                    ]
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        modelo_df.to_excel(writer, index=False, sheet_name='Alunos')
                    output.seek(0)
                    ui.download(output.read(), filename='modelo_importacao_alunos.xlsx')

                ui.button(
                    '⬇ Baixar Planilha Modelo (.xlsx)',
                    on_click=download_modelo
                ).props('outline no-caps').style(
                    f'color: {THEME.get("primary","#00e5ff")}; border-color: {THEME.get("primary","#00e5ff")};'
                )

            ui.label(
                '💡 Use a planilha modelo acima para garantir que as colunas sejam reconhecidas corretamente. '
                'A coluna ano_letivo é preenchida automaticamente com o valor do campo acima.'
            ).classes('text-xs text-grey-5 q-mt-sm')

        # ── Card 2: Upload da Planilha ─────────────
        with theme.card_base().classes('w-full p-6'):
            ui.label('📂 CARREGAR PLANILHA DE ALUNOS (.xlsx ou .csv)').classes(
                'cyber-title text-sm font-bold text-white q-mb-xs'
            )
            ui.label(
                'Selecione o arquivo → clique em  ▶ Upload  para processar → revise os dados no modal → confirme o envio ao Supabase.'
            ).classes('text-xs text-grey-4 q-mb-md')

            status_label = ui.label('').classes('text-xs text-grey-5')

            async def handle_file_upload(e):
                with e.client:
                    status_label.set_text('🔄 Lendo e processando arquivo…')
                    ui.notify('Lendo arquivo enviado…', color='info')

                    try:
                        e.content.seek(0)
                    except Exception:
                        pass

                    file_bytes = e.content.read()
                    if _inspect.isawaitable(file_bytes):
                        file_bytes = await file_bytes

                    filename = e.name.lower()

                    try:
                        if filename.endswith('.csv'):
                            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
                        else:
                            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)

                        df.columns = [str(c).strip() for c in df.columns]

                        col_mapping = mapear_colunas(df.columns.tolist())

                        req_fields = ['numero_interno', 'nome_guerra', 'pelotao']
                        faltantes  = [f for f in req_fields if f not in col_mapping]

                        if faltantes:
                            status_label.set_text(f'❌ Colunas não encontradas: {", ".join(faltantes)}')
                            ui.notify(
                                f'❌ Não foi possível mapear: {", ".join(faltantes)}',
                                color='negative', duration=8
                            )
                            ui.notify(
                                f'📋 Colunas da planilha: {", ".join(df.columns)}',
                                color='warning', duration=10
                            )
                            return

                        rows = df.to_dict(orient='records')
                        db   = get_db_connection()
                        if not db:
                            status_label.set_text('❌ Sem conexão com o banco de dados.')
                            ui.notify('❌ Sem conexão com o banco de dados.', color='negative')
                            return

                        # Busca registros existentes para o ano letivo atual
                        res_ex = db.table('Alunos').select(
                            'id,numero_interno,nome_guerra,pelotao'
                        ).eq('ano_letivo', import_state['ano_letivo']).execute()

                        existing_map = {
                            str(r['numero_interno']).strip(): r
                            for r in (res_ex.data or [])
                        }

                        novos     = []
                        atualizar = []

                        for rec in rows:
                            mapped_data = {}
                            for dest_key, src_key in col_mapping.items():
                                val = rec.get(src_key)
                                mapped_data[dest_key] = (
                                    str(val).strip() if val is not None and pd.notna(val) else None
                                )

                            num_i  = mapped_data.get('numero_interno')
                            nome_g = mapped_data.get('nome_guerra')

                            if not num_i or not nome_g:
                                continue

                            if num_i in existing_map:
                                existing_item = existing_map[num_i]
                                atualizar.append({
                                    'db_id':              existing_item['id'],
                                    'numero_interno':     num_i,
                                    'nome_guerra_antigo': existing_item['nome_guerra'],
                                    'nome_guerra_novo':   nome_g,
                                    'pelotao_antigo':     existing_item.get('pelotao', ''),
                                    'mapped_data':        mapped_data,
                                })
                            else:
                                novos.append({
                                    'numero_interno': num_i,
                                    'nome_guerra':    nome_g,
                                    'mapped_data':    mapped_data,
                                })

                        import_state['dados_novos']    = rows
                        import_state['colunas']        = df.columns.tolist()
                        import_state['novos_lote']     = novos
                        import_state['atualizar_lote'] = atualizar

                        total = len(novos) + len(atualizar)
                        status_label.set_text(
                            f'✅ Planilha lida: {total} aluno(s) identificados '
                            f'({len(novos)} novos, {len(atualizar)} para atualizar). '
                            'Revise os dados no modal aberto abaixo.'
                        )
                        ui.notify(f'✅ Planilha processada! {total} registro(s) prontos para confirmação.', color='positive')

                        try:
                            e.sender.reset()
                        except Exception:
                            pass

                        abrir_modal_confirmacao()

                    except Exception as err:
                        status_label.set_text(f'❌ Erro: {err}')
                        ui.notify(f'❌ Erro ao ler planilha: {err}', color='negative', duration=10)
                        try:
                            e.sender.reset()
                        except Exception:
                            pass

            # auto_upload=False → exibe o botão de upload visivelmente
            ui.upload(
                label='Selecionar Planilha de Alunos (.xlsx ou .csv)',
                on_upload=handle_file_upload,
                auto_upload=False,
                max_files=1,
            ).props('dark color=primary no-caps').classes('w-full').style('min-height: 80px;')

        # ── Card 3: Importação de Fotos ────────────
        with theme.card_base().classes('w-full p-6'):
            ui.label('🖼️ IMPORTAÇÃO EM LOTE DE FOTOS DOS ALUNOS').classes('cyber-title text-sm font-bold text-white q-mb-xs')
            ui.label(
                'Nomeie os arquivos com o número interno do aluno (ex: M-1-101.jpg). '
                'O sistema fará upload para o Supabase Storage e vinculará automaticamente ao perfil.'
            ).classes('text-xs text-grey-4 q-mb-md')

            async def handle_image_batch_upload(e):
                import os
                file_bytes = e.content.read()
                if _inspect.isawaitable(file_bytes):
                    file_bytes = await file_bytes

                raw_name, ext = os.path.splitext(e.name)
                ni_aluno     = raw_name.strip()
                ano_destino  = import_state['ano_letivo']

                db = get_db_connection()
                if not db:
                    ui.notify('❌ Sem conexão com o banco de dados.', color='negative')
                    return

                try:
                    res_al = (
                        db.table('Alunos')
                        .select('id,nome_guerra')
                        .eq('numero_interno', ni_aluno)
                        .eq('ano_letivo', ano_destino)
                        .execute()
                    )
                    if not res_al.data:
                        ui.notify(f'⚠️ Aluno Nº {ni_aluno} não encontrado para o ano {ano_destino}.', color='warning')
                        return

                    aluno_id   = res_al.data[0]['id']
                    nome_guerra = res_al.data[0]['nome_guerra']
                    filename   = f'alunos/{ano_destino}/{ni_aluno}{ext.lower()}'

                    from database import upload_file_to_supabase_storage
                    public_url = await asyncio.to_thread(
                        upload_file_to_supabase_storage,
                        file_bytes, filename, e.type or 'image/jpeg'
                    )
                    if public_url:
                        db.table('Alunos').update({'url_foto': public_url}).eq('id', aluno_id).execute()
                        ui.notify(f'📸 Foto vinculada a {nome_guerra} ({ni_aluno})!', color='positive')
                    else:
                        ui.notify(f'❌ Erro ao enviar foto de {ni_aluno} para o storage.', color='negative')

                except Exception as err:
                    ui.notify(f'❌ Erro no processamento de {ni_aluno}: {err}', color='negative')

            ui.upload(
                label='Enviar Fotos de Perfil (Selecione Várias)',
                on_upload=handle_image_batch_upload,
                auto_upload=False,
                multiple=True,
            ).props('dark color=primary no-caps accept="image/jpeg,image/png"').classes('w-full').style('min-height: 80px;')
