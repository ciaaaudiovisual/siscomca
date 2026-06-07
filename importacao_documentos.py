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


# ─────────────────────────────────────────────────────────────────────────────
# Normaliza texto para comparação de nomes de colunas
# ─────────────────────────────────────────────────────────────────────────────
def _norm(c: str) -> str:
    c = str(c).strip().lower()
    c = ''.join(x for x in unicodedata.normalize('NFD', c) if unicodedata.category(x) != 'Mn')
    return c.replace(' ', '_').replace('.', '').replace('-', '_').replace('__', '_')


def _mapear_colunas(cols: list) -> dict:
    """Mapeia os cabeçalhos da planilha para os campos canônicos da tabela Alunos."""
    _MAP = {
        'numero_interno':            ['numero_interno','num_interno','n_interno','numero','nro','no','nº','num','matricula','id','cod'],
        'nome_guerra':               ['nome_guerra','guerra','nome_de_guerra'],
        'nome_completo':             ['nome_completo','nome_inteiro','nome_todo','completo','nome_civil'],
        'pelotao':                   ['pelotao','pelotao_de_formacao','turma','pel'],
        'especialidade':             ['especialidade','esp','arma','quadro','especializacao','funcao'],
        'nip':                       ['nip'],
        'media_academica':           ['media_academica','media','nota','coeficiente','cr','iea'],
        'telefone_contato':          ['telefone_contato','telefone','celular','tel','fone'],
        'endereco':                  ['endereco','rua','residencia','morada','bairro','logradouro'],
        'contato_emergencia_nome':   ['contato_emergencia_nome','emergencia_nome','nome_emergencia','responsavel','familiar'],
        'contato_emergencia_numero': ['contato_emergencia_numero','emergencia_telefone','telefone_emergencia','tel_emergencia','contato_emergencia'],
        'numero_armario':            ['numero_armario','armario','escaninho'],
    }
    mapeadas = {}
    for dest, aliases in _MAP.items():
        for c in cols:
            if _norm(c) in aliases:
                mapeadas[dest] = c
                break
    # Fallback: qualquer coluna que contenha 'nome' pode ser nome_guerra
    if 'nome_guerra' not in mapeadas:
        for c in cols:
            nc = _norm(c)
            if 'nome' in nc and c != mapeadas.get('nome_completo'):
                mapeadas['nome_guerra'] = c
                break
    return mapeadas


def _limpar_row(row_data: dict, ano_letivo: str) -> dict:
    """Remove valores nulos/nan e garante o ano_letivo correto."""
    limpo = {}
    for k, v in row_data.items():
        if v is None:
            continue
        sv = str(v).strip()
        if sv.lower() in ('', 'nan', 'none'):
            continue
        limpo[k] = sv
    # tipo específico para media_academica
    if 'media_academica' in limpo:
        try:
            limpo['media_academica'] = float(limpo['media_academica'])
        except (ValueError, TypeError):
            limpo.pop('media_academica', None)
    # ano_letivo é SEMPRE obrigatório
    limpo['ano_letivo'] = ano_letivo
    return limpo


# ─────────────────────────────────────────────────────────────────────────────
def render_page():
    import_state = {
        'ano_letivo': '2026',
    }

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header(
            'Cadastro de Alunos — Importação de Dados',
            'Importe planilhas (.xlsx/.csv) para preencher ou atualizar a tabela Alunos no Supabase'
        )

        # ── Card 1: Configurações ─────────────────────────────────────────────
        with theme.card_base().classes('w-full p-6'):
            ui.label('⚙️ CONFIGURAÇÕES DA IMPORTAÇÃO').classes('cyber-title text-sm font-bold text-white q-mb-md')

            with ui.row().classes('w-full items-end gap-6 flex-wrap'):
                ano_input = ui.input(
                    'Ano Letivo de Destino *',
                    value=import_state['ano_letivo'],
                    on_change=lambda e: import_state.update({'ano_letivo': str(e.value).strip()})
                ).props('dark outlined dense').classes('w-52').tooltip(
                    'Este ano será gravado na coluna ano_letivo de cada aluno importado'
                )

                def download_modelo():
                    buf = io.BytesIO()
                    df_m = pd.DataFrame(columns=[
                        'numero_interno', 'nome_guerra', 'nome_completo',
                        'pelotao', 'especialidade', 'nip', 'media_academica',
                        'telefone_contato', 'endereco',
                        'contato_emergencia_nome', 'contato_emergencia_numero',
                        'numero_armario'
                    ])
                    df_m.loc[0] = [
                        'M-1-101', 'SILVA', 'JOÃO DA SILVA SOUZA',
                        'MIKE-1', 'AD', '25.1234.56', '8.5',
                        '21999998888', 'Av. Brasil, 100',
                        'Maria da Silva', '21999997777', 'A-12'
                    ]
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                        df_m.to_excel(wr, index=False, sheet_name='Alunos')
                    buf.seek(0)
                    ui.download(buf.read(), filename='modelo_importacao_alunos.xlsx')

                ui.button(
                    '⬇ Baixar Planilha Modelo (.xlsx)',
                    on_click=download_modelo
                ).props('outline no-caps').style(
                    f'color:{THEME.get("primary","#00e5ff")};border-color:{THEME.get("primary","#00e5ff")};'
                )

            ui.label(
                '💡 A coluna ano_letivo NÃO precisa estar na planilha — ela é preenchida automaticamente '
                'pelo valor do campo acima.'
            ).classes('text-xs text-grey-5 q-mt-sm')

        # ── Card 2: Upload da Planilha ────────────────────────────────────────
        with theme.card_base().classes('w-full p-6'):
            ui.label('📂 CARREGAR PLANILHA DE ALUNOS (.xlsx ou .csv)').classes(
                'cyber-title text-sm font-bold text-white q-mb-xs'
            )
            ui.label(
                '1. Selecione o arquivo  →  2. Clique em ▶ Upload  →  '
                '3. Revise os dados no painel que abrirá  →  4. Confirme o envio ao Supabase.'
            ).classes('text-xs text-grey-4 q-mb-sm')

            # Barra de progresso + status textuais
            progress_bar  = ui.linear_progress(value=0).props('color=cyan instant-feedback').classes('w-full').style('height:6px;')
            status_label  = ui.label('Aguardando arquivo…').classes('text-xs text-grey-5 q-mt-xs')

            # ── Painel inline de confirmação (substitui modal externo) ────────
            review_panel = ui.column().classes('w-full gap-4 q-mt-md').style('display:none;')

            async def handle_file_upload(e):
                """
                NiceGUI v3: o arquivo fica em e.file (FileUpload).
                e.file.read() é async e retorna bytes diretamente.
                """
                with e.client:
                    # — passo 1: leitura —
                    progress_bar.set_value(0.1)
                    status_label.set_text('🔄 Passo 1/4 — Lendo arquivo do disco…')

                    try:
                        # NiceGUI v3 API: e.file é um FileUpload com read() assíncrono
                        raw = await e.file.read()
                    except Exception as err:
                        status_label.set_text(f'❌ Falha na leitura do arquivo: {err}')
                        ui.notify(f'❌ Leitura falhou: {err}', color='negative', duration=8)
                        progress_bar.set_value(0)
                        return

                    filename = e.file.name.lower()
                    progress_bar.set_value(0.25)
                    status_label.set_text('🔄 Passo 2/4 — Interpretando planilha…')

                    # — passo 2: parse —
                    try:
                        if filename.endswith('.csv'):
                            df = await asyncio.to_thread(
                                lambda: pd.read_csv(io.BytesIO(raw), dtype=str)
                            )
                        else:
                            df = await asyncio.to_thread(
                                lambda: pd.read_excel(io.BytesIO(raw), dtype=str)
                            )
                        df.columns = [str(c).strip() for c in df.columns]
                    except Exception as err:
                        status_label.set_text(f'❌ Erro ao interpretar planilha: {err}')
                        ui.notify(f'❌ Erro planilha: {err}', color='negative', duration=8)
                        progress_bar.set_value(0)
                        return

                    progress_bar.set_value(0.45)
                    status_label.set_text('🔄 Passo 3/4 — Mapeando colunas…')

                    col_mapping = _mapear_colunas(df.columns.tolist())
                    req_fields  = ['numero_interno', 'nome_guerra', 'pelotao']
                    faltantes   = [f for f in req_fields if f not in col_mapping]

                    if faltantes:
                        msg = (
                            f'❌ Colunas obrigatórias não encontradas: {", ".join(faltantes)}\n'
                            f'Colunas presentes na planilha: {", ".join(df.columns.tolist())}'
                        )
                        status_label.set_text(msg)
                        ui.notify(msg, color='negative', duration=10)
                        progress_bar.set_value(0)
                        return

                    # — passo 3: comparação com o BD (filtra por numero_interno + ano_letivo) —
                    # Assim: mesmo aluno em anos diferentes = registros independentes.
                    progress_bar.set_value(0.60)
                    ano = import_state['ano_letivo']
                    status_label.set_text(f'🔄 Passo 4/4 — Comparando com o BD (Ano {ano})…')

                    try:
                        db = await asyncio.to_thread(get_db_connection)
                        if not db:
                            raise RuntimeError('Sem conexão com Supabase.')
                        # Busca somente os registros do ano selecionado.
                        # A chave composta (numero_interno + ano_letivo) permite o mesmo aluno
                        # em anos diferentes como registros separados.
                        res_ex = await asyncio.to_thread(
                            lambda: db.table('Alunos')
                                      .select('id,numero_interno,nome_guerra,pelotao,ano_letivo')
                                      .eq('ano_letivo', ano)
                                      .execute()
                        )
                    except Exception as err:
                        status_label.set_text(f'❌ Erro ao conectar ao BD: {err}')
                        ui.notify(f'❌ BD: {err}', color='negative', duration=8)
                        progress_bar.set_value(0)
                        return

                    existing_map = {
                        str(r['numero_interno']).strip(): r
                        for r in (res_ex.data or [])
                    }

                    novos     = []
                    atualizar = []
                    rows      = df.to_dict(orient='records')

                    for rec in rows:
                        mapped = {}
                        for dest_key, src_key in col_mapping.items():
                            val = rec.get(src_key)
                            if val is not None and pd.notna(val) and str(val).strip().lower() not in ('nan','none',''):
                                mapped[dest_key] = str(val).strip()
                            else:
                                mapped[dest_key] = None

                        num_i  = mapped.get('numero_interno')
                        nome_g = mapped.get('nome_guerra')
                        if not num_i or not nome_g:
                            continue

                        if num_i in existing_map:
                            ex = existing_map[num_i]
                            atualizar.append({
                                'db_id':              ex['id'],
                                'numero_interno':     num_i,
                                'nome_guerra_antigo': ex['nome_guerra'],
                                'nome_guerra_novo':   nome_g,
                                'pelotao_antigo':     ex.get('pelotao',''),
                                'ano_letivo_atual':   ex.get('ano_letivo',''),
                                'mapped':             mapped,
                            })
                        else:
                            novos.append({
                                'numero_interno': num_i,
                                'nome_guerra':    nome_g,
                                'mapped':         mapped,
                            })

                    progress_bar.set_value(1.0)
                    total = len(novos) + len(atualizar)
                    status_label.set_text(
                        f'✅ Planilha carregada — {total} aluno(s): '
                        f'{len(novos)} novos · {len(atualizar)} a atualizar · Ano {ano}. '
                        'Revise abaixo e confirme o envio.'
                    )

                    try:
                        e.sender.reset()
                    except Exception:
                        pass

                    if total == 0:
                        ui.notify('⚠️ Nenhum aluno válido encontrado na planilha.', color='warning')
                        return

                    # ── Painel de revisão inline ──────────────────────────────
                    review_panel.clear()
                    review_panel.style('display:flex;')

                    with review_panel:
                        # Cabeçalho do painel
                        with ui.row().classes('w-full items-center gap-3'):
                            ui.label('📋 REVISÃO DOS DADOS — CONFIRME ANTES DE GRAVAR').classes(
                                'cyber-title text-sm font-bold text-white'
                            )

                        ui.label(
                            f'📅 Destino: tabela Alunos · Ano Letivo {ano}'
                        ).classes('text-xs text-grey-4')

                        # Resumo
                        with ui.row().classes('w-full gap-4 q-my-sm'):
                            with ui.card().props('flat').classes('col p-3 text-center rounded-xl').style(
                                'background:rgba(0,200,80,0.08);border:1px solid rgba(0,200,80,0.3);'
                            ):
                                ui.label(str(len(novos))).classes('text-4xl font-bold text-green-400')
                                ui.label('Novos Cadastros').classes('text-xs text-grey-5 uppercase font-bold q-mt-xs')
                            with ui.card().props('flat').classes('col p-3 text-center rounded-xl').style(
                                'background:rgba(33,150,243,0.08);border:1px solid rgba(33,150,243,0.3);'
                            ):
                                ui.label(str(len(atualizar))).classes('text-4xl font-bold text-blue-400')
                                ui.label('Atualizações').classes('text-xs text-grey-5 uppercase font-bold q-mt-xs')

                        # Tabela de novos
                        if novos:
                            ui.label('🆕 NOVOS ALUNOS (INSERÇÃO):').classes('text-xs font-bold text-green-400 q-mb-xs')
                            cols_n = [
                                {'name':'numero_interno','label':'Nº Interno','field':'numero_interno','align':'left','sortable':True},
                                {'name':'nome_guerra','label':'Nome Guerra','field':'nome_guerra','align':'left','sortable':True},
                                {'name':'pelotao','label':'Pelotão','field':'pelotao','align':'left'},
                                {'name':'nome_completo','label':'Nome Completo','field':'nome_completo','align':'left'},
                                {'name':'nip','label':'NIP','field':'nip','align':'left'},
                            ]
                            rows_n = [n['mapped'] for n in novos]
                            ui.table(columns=cols_n, rows=rows_n, row_key='numero_interno').props(
                                'dark flat dense bordered'
                            ).classes('w-full max-h-56 overflow-auto q-mb-sm')

                        # Tabela de atualizações
                        if atualizar:
                            ui.label('🔄 ATUALIZAÇÕES (ALUNOS EXISTENTES):').classes('text-xs font-bold text-blue-400 q-mb-xs')
                            cols_u = [
                                {'name':'numero_interno','label':'Nº Interno','field':'numero_interno','align':'left','sortable':True},
                                {'name':'nome_guerra_antigo','label':'Nome Atual','field':'nome_guerra_antigo','align':'left'},
                                {'name':'nome_guerra_novo','label':'Nome Novo','field':'nome_guerra_novo','align':'left'},
                                {'name':'pelotao_antigo','label':'Pelotão Atual','field':'pelotao_antigo','align':'left'},
                                {'name':'pelotao_novo','label':'Pelotão Novo','field':'pelotao_novo','align':'left'},
                                {'name':'ano_letivo_atual','label':'Ano no BD','field':'ano_letivo_atual','align':'left'},
                            ]
                            rows_u = [{
                                'numero_interno':     a['numero_interno'],
                                'nome_guerra_antigo': a['nome_guerra_antigo'],
                                'nome_guerra_novo':   a['nome_guerra_novo'],
                                'pelotao_antigo':     a['pelotao_antigo'],
                                'pelotao_novo':       a['mapped'].get('pelotao',''),
                                'ano_letivo_atual':   a.get('ano_letivo_atual',''),
                            } for a in atualizar]
                            ui.table(columns=cols_u, rows=rows_u, row_key='numero_interno').props(
                                'dark flat dense bordered'
                            ).classes('w-full max-h-56 overflow-auto q-mb-sm')

                        ui.separator().style('background-color:rgba(255,255,255,0.1);')

                        # Botões de confirmação
                        gravar_btn = ui.button(
                            f'✅  Gravar {total} aluno(s) na tabela Alunos — Ano {ano}',
                        ).props('unelevated no-caps').style(
                            f'background:{THEME.get("primary","#00e5ff")};color:#000;font-weight:bold;'
                        )
                        cancelar_btn = ui.button('✖ Cancelar / Limpar', ).props('flat color=grey no-caps')
                        with ui.row().classes('w-full justify-end gap-3'):
                            cancelar_btn.move(None)
                            gravar_btn.move(None)

                        # Ações dos botões
                        def cancelar():
                            review_panel.clear()
                            review_panel.style('display:none;')
                            progress_bar.set_value(0)
                            status_label.set_text('Aguardando arquivo…')

                        cancelar_btn.on_click(cancelar)

                        async def gravar():
                            gravar_btn.props('disabled loading')
                            status_label.set_text('💾 Gravando no Supabase…')
                            db2 = await asyncio.to_thread(get_db_connection)
                            if not db2:
                                ui.notify('❌ Sem conexão com o banco.', color='negative')
                                gravar_btn.props(remove='disabled loading')
                                return
                            try:
                                ins_ok = 0
                                upd_ok = 0

                                for n in novos:
                                    row = _limpar_row(n['mapped'], ano)
                                    # Consulta se o aluno já existe para este ano letivo
                                    res_check = await asyncio.to_thread(
                                        lambda r=row: db2.table('Alunos')
                                                          .select('id')
                                                          .eq('numero_interno', r['numero_interno'])
                                                          .eq('ano_letivo', ano)
                                                          .execute()
                                    )
                                    if res_check.data:
                                        # Se por acaso já existe, atualiza pelo ID
                                        student_id = res_check.data[0]['id']
                                        await asyncio.to_thread(
                                            lambda r=row, sid=student_id: db2.table('Alunos')
                                                                             .update(r)
                                                                             .eq('id', sid)
                                                                             .execute()
                                        )
                                        upd_ok += 1
                                    else:
                                        # Se não existe, insere novo
                                        await asyncio.to_thread(
                                            lambda r=row: db2.table('Alunos')
                                                            .insert(r)
                                                            .execute()
                                        )
                                        ins_ok += 1

                                for a in atualizar:
                                    row = _limpar_row(a['mapped'], ano)
                                    await asyncio.to_thread(
                                        lambda r=row: db2.table('Alunos')
                                                        .upsert(r, on_conflict='numero_interno,ano_letivo')
                                                        .execute()
                                    )
                                    upd_ok += 1

                                partes = []
                                if ins_ok:
                                    partes.append(f'{ins_ok} inserido(s)')
                                if upd_ok:
                                    partes.append(f'{upd_ok} atualizado(s)')

                                ui.notify(
                                    f'🎉 Concluído! {", ".join(partes)} na tabela Alunos — Ano {ano}.',
                                    color='positive', duration=6
                                )
                                data_service.clear_cache()
                                cancelar()

                            except Exception as ex:
                                msg = str(ex)
                                if '23505' in msg and 'numero_interno_key' in msg:
                                    ui.notify(
                                        '❌ Constraint antiga detectada! Execute no Supabase SQL Editor:\n'
                                        'ALTER TABLE "Alunos" DROP CONSTRAINT IF EXISTS "Alunos_numero_interno_key";',
                                        color='negative', duration=15
                                    )
                                else:
                                    ui.notify(f'❌ Erro ao gravar: {ex}', color='negative', duration=10)
                                status_label.set_text(f'❌ Erro: {ex}')
                                gravar_btn.props(remove='disabled loading')

                        gravar_btn.on_click(gravar)

            # ── Componente de upload ──────────────────────────────────────────
            ui.upload(
                label='Selecionar Planilha de Alunos (.xlsx ou .csv)',
                on_upload=handle_file_upload,
                auto_upload=False,
                max_files=1,
            ).props('dark color=primary no-caps').classes('w-full').style('min-height:72px;')

        # ── Card 3: Importação em Lote de Fotos ──────────────────────────────
        with theme.card_base().classes('w-full p-6'):
            ui.label('🖼️ IMPORTAÇÃO EM LOTE DE FOTOS DOS ALUNOS').classes('cyber-title text-sm font-bold text-white q-mb-xs')
            ui.label(
                'Nomeie os arquivos com o número interno do aluno (ex: M-1-101.jpg). '
                'O sistema fará upload para o Supabase Storage e vinculará ao perfil automaticamente.'
            ).classes('text-xs text-grey-4 q-mb-md')

            async def handle_image_batch_upload(e):
                import os
                # NiceGUI v3: e.file.read() é async
                file_bytes = await e.file.read()

                raw_name, ext = os.path.splitext(e.file.name)
                ni_aluno    = raw_name.strip()
                ano_destino = import_state['ano_letivo']

                db = get_db_connection()
                if not db:
                    ui.notify('❌ Sem conexão com o banco.', color='negative')
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
                        ui.notify(f'⚠️ Aluno Nº {ni_aluno} não encontrado — Ano {ano_destino}.', color='warning')
                        return

                    aluno_id    = res_al.data[0]['id']
                    nome_guerra = res_al.data[0]['nome_guerra']
                    filename    = f'alunos/{ano_destino}/{ni_aluno}{ext.lower()}'

                    from database import upload_file_to_supabase_storage
                    public_url = await asyncio.to_thread(
                        upload_file_to_supabase_storage,
                        file_bytes, filename, e.file.content_type or 'image/jpeg'
                    )
                    if public_url:
                        db.table('Alunos').update({'url_foto': public_url}).eq('id', aluno_id).execute()
                        ui.notify(f'📸 Foto de {nome_guerra} ({ni_aluno}) vinculada!', color='positive')
                    else:
                        ui.notify(f'❌ Falha ao enviar foto de {ni_aluno} ao storage.', color='negative')

                except Exception as err:
                    ui.notify(f'❌ Erro em {ni_aluno}: {err}', color='negative')

            ui.upload(
                label='Enviar Fotos de Perfil (Selecione Várias)',
                on_upload=handle_image_batch_upload,
                auto_upload=False,
                multiple=True,
            ).props('dark color=primary no-caps accept="image/jpeg,image/png"').classes('w-full').style('min-height:72px;')
