from nicegui import ui, app
import pandas as pd
from datetime import datetime
import re
import math
import theme
from database import get_db_connection, load_data
from services import data_service

THEME = theme.colors

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def render_page():
    @ui.refreshable
    def render_cadastro_content():
        # Carrega dados essenciais
        core_data = data_service.get_core_data()
        alunos_df = core_data.get('alunos', pd.DataFrame())
        acoes_df = core_data.get('acoes', pd.DataFrame())
        tipos_acao_df = core_data.get('tipos_acao', pd.DataFrame())
        config_df = core_data.get('config', pd.DataFrame())
        
        # Normaliza colunas
        novas_colunas = {
            'media_academica': 0.0, 'endereco': '', 'telefone_contato': '',
            'contato_emergencia_nome': '', 'contato_emergencia_numero': '', 'numero_armario': '',
            'url_foto': '', 'nip': '', 'especialidade': '', 'ano_letivo': '2025'
        }
        for col, default_value in novas_colunas.items():
            if col not in alunos_df.columns:
                alunos_df[col] = default_value
        
        # Garante valores válidos para o ano letivo
        alunos_df['ano_letivo'] = alunos_df['ano_letivo'].fillna('2025').astype(str).str.strip()
        alunos_df['ano_letivo'] = alunos_df['ano_letivo'].replace('', '2025')

        config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
        
        # Processa pontos
        from database import get_mock_table
        if not acoes_df.empty and not tipos_acao_df.empty:
            # Calcular pontuação efetiva
            tipos_copy = tipos_acao_df.copy()
            tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
            acoes_copy = acoes_df.copy()
            acoes_copy['tipo_acao_id'] = acoes_copy['tipo_acao_id'].astype(str)
            tipos_copy['id'] = tipos_copy['id'].astype(str)
            
            acoes_com_pontos = pd.merge(acoes_copy, tipos_copy[['id', 'pontuacao']], left_on='tipo_acao_id', right_on='id', how='left')
            
            fator_adaptacao = float(config_dict.get('fator_adaptacao', 0.25))
            try:
                inicio_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_inicio')).date()
                fim_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_fim')).date()
            except:
                inicio_adaptacao, fim_adaptacao = None, None

            def aplicar_fator(row):
                pts = row.get('pontuacao', 0.0)
                data_convertida = pd.to_datetime(row['data'], errors='coerce')
                if pd.isna(data_convertida): return pts
                data_acao = data_convertida.date()
                if pts >= 0 or not inicio_adaptacao: return pts
                if inicio_adaptacao <= data_acao <= fim_adaptacao:
                    return pts * fator_adaptacao
                return pts

            acoes_com_pontos['pontuacao_efetiva'] = acoes_com_pontos.apply(aplicar_fator, axis=1)
            soma_pontos = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
            
            alunos_df['id'] = alunos_df['id'].astype(str)
            soma_pontos.index = soma_pontos.index.astype(str)
            alunos_df['soma_pontos_acoes'] = alunos_df['id'].map(soma_pontos).fillna(0)
        else:
            alunos_df['soma_pontos_acoes'] = 0.0

        # Calcula conceito final
        def calc_conceito(row):
            linha_base = float(config_dict.get('linha_base_conceito', 8.5))
            impacto_max = float(config_dict.get('impacto_max_acoes', 1.5))
            peso_acad = float(config_dict.get('peso_academico', 1.0))
            pts_acoes = row['soma_pontos_acoes']
            media_aluno = float(row.get('media_academica', 0.0))
            
            impacto_acoes = max(-impacto_max, min(pts_acoes, impacto_max))
            impacto_academico = 0.0
            
            if 'media_academica' in alunos_df.columns and not alunos_df.empty:
                medias_validas = pd.to_numeric(alunos_df['media_academica'], errors='coerce').dropna()
                if not medias_validas.empty and medias_validas.max() > medias_validas.min():
                    media_min = medias_validas.min()
                    media_max = medias_validas.max()
                    if (media_max - media_min) > 0:
                        fator_norm = (media_aluno - media_min) / (media_max - media_min)
                        impacto_academico = fator_norm * peso_acad
            
            conceito = linha_base + impacto_acoes + impacto_academico
            return max(0.0, min(conceito, 10.0))

        alunos_df['conceito_final'] = alunos_df.apply(calc_conceito, axis=1)

        # Estado local de filtragem e paginação
        state = app.storage.user.get('alunos_state', {
            'search': '', 'pelotao': 'Todos', 'especialidade': 'Todas',
            'sort': 'Padrão (Nº Interno)', 'page': 1, 'ano_letivo': '2026'
        })
        # Garante retrocompatibilidade se já existir estado na sessão sem a chave
        if 'ano_letivo' not in state:
            state['ano_letivo'] = '2026'
        app.storage.user['alunos_state'] = state

        # --- LISTA FILTRADA ---
        def obter_alunos_filtrados():
            df = alunos_df.copy()
            
            # Filtro Ano Letivo
            if state.get('ano_letivo', 'Todos') != 'Todos':
                df = df[df['ano_letivo'] == state['ano_letivo']]
            
            # Filtro pelotão
            if state['pelotao'] != 'Todos':
                df = df[df['pelotao'] == state['pelotao']]
            
            # Filtro especialidade
            if state['especialidade'] != 'Todas':
                df = df[df['especialidade'] == state['especialidade']]
                
            # Busca texto
            if state['search']:
                term = state['search'].lower()
                mask = (
                    df['nome_guerra'].str.lower().str.contains(term, na=False) |
                    df['numero_interno'].astype(str).str.lower().str.contains(term, na=False) |
                    df['nome_completo'].str.lower().str.contains(term, na=False) |
                    df['nip'].astype(str).str.lower().str.contains(term, na=False)
                )
                df = df[mask]
                
            # Ordenação
            if state['sort'] == 'Maior Conceito':
                df = df.sort_values('conceito_final', ascending=False)
            elif state['sort'] == 'Menor Conceito':
                df = df.sort_values('conceito_final', ascending=True)
            else:
                df['sort_key'] = df['numero_interno'].apply(natural_sort_key)
                df = df.sort_values('sort_key').drop(columns=['sort_key'])
                
            return df

        with ui.row().classes('w-full justify-between items-end'):
            theme.section_header('Gestão de Alunos', 'Visualização e Controle do Efetivo de Alunos')
            
            with ui.row().classes('gap-2'):
                ui.button('Novo Aluno', icon='person_add', on_click=lambda: open_add_aluno_dialog()).props('unelevated no-caps').style(f'background: {THEME["primary"]}; color: #000; font-weight: 600;')
        
        # Filtros
        with theme.card_base().classes('w-full q-pa-md'):
            ui.label('FILTROS E BUSCA').style(f'font-size: 0.75rem; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
            
            with ui.row().classes('w-full items-center gap-4'):
                # Busca
                ui.input('Buscar por Nome, Nº ou NIP', value=state['search'], on_change=lambda e: update_state('search', e.value)).props('dark outlined dense').classes('col-grow')
                
                # Pelotão
                pelotoes = ['Todos'] + sorted(list(alunos_df['pelotao'].dropna().unique()))
                ui.select(pelotoes, label='Pelotão', value=state['pelotao'], on_change=lambda e: update_state('pelotao', e.value)).props('dark outlined dense').classes('w-48')
                
                # Especialidade
                especs = ['Todas'] + sorted(list(alunos_df['especialidade'].dropna().unique()))
                ui.select(especs, label='Especialidade', value=state['especialidade'], on_change=lambda e: update_state('especialidade', e.value)).props('dark outlined dense').classes('w-40')
                
                # Ano Letivo
                anos_letivos = ['Todos'] + sorted(list(set(list(alunos_df['ano_letivo'].dropna().unique()) + ['2025', '2026'])))
                ui.select(anos_letivos, label='Ano Letivo', value=state['ano_letivo'], on_change=lambda e: update_state('ano_letivo', e.value)).props('dark outlined dense').classes('w-40')
                
                # Ordenação
                sorts = ['Padrão (Nº Interno)', 'Maior Conceito', 'Menor Conceito']
                ui.select(sorts, label='Ordenar por', value=state['sort'], on_change=lambda e: update_state('sort', e.value)).props('dark outlined dense').classes('w-40')

        # Container dos Alunos (Grade Responsiva: 3 colunas em desktop, 2 colunas em tablet, 1 coluna em celular)
        alunos_container = ui.element('div').classes('w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4')

        # Rodapé de paginação
        pagination_row = ui.row().classes('w-full justify-center items-center gap-4 q-mt-md')

        def update_state(key, val):
            state[key] = val
            state['page'] = 1 # Reset pagina ao mudar filtros
            app.storage.user['alunos_state'] = state
            render_list()

        def render_list():
            alunos_container.clear()
            pagination_row.clear()
            
            filtered = obter_alunos_filtrados()
            total_items = len(filtered)
            
            # Usando 12 itens por página para fechar linhas perfeitamente na grade (divisível por 2 e por 3!)
            ITEMS_PER_PAGE = 12
            total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
            current_page = min(state['page'], total_pages)
            
            start_idx = (current_page - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            page_df = filtered.iloc[start_idx:end_idx]
            
            with alunos_container:
                if page_df.empty:
                    ui.label('Nenhum aluno encontrado com os filtros selecionados.').classes('text-grey italic self-center q-my-lg col-span-full text-center')
                    return
                    
                for _, r in page_df.iterrows():
                    aluno_id = str(r['id'])
                    conceito = r['conceito_final']
                    pontos = r['soma_pontos_acoes']
                    
                    cor_conceito = '#00e676' if conceito >= 8.5 else '#ff9100' if conceito >= 7.0 else '#ff1744'
                    
                    with ui.card().classes('w-full q-pa-md no-shadow transition-all hover:bg-white/5 flex flex-col justify-between').style(
                        f'background: {THEME["bg_panel"]}; border: 1px solid rgba(0, 229, 255, 0.15); border-radius: 12px; height: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.4);'
                    ):
                        # 1. Top Section: Foto, Guerra, N°, Pelotão
                        with ui.row().classes('w-full gap-3 items-center no-wrap'):
                            foto_url = r.get('url_foto')
                            image_src = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else f"https://res.cloudinary.com/comcia/image/upload/alunos_app/{r['numero_interno']}.jpg"
                            ui.element('div').classes('shadow border border-cyan-500/30 shrink-0').style(
                                f"width: 75px; height: 75px; background-image: url('{image_src}'); "
                                f"background-size: cover; background-repeat: no-repeat; "
                                f"background-position: center; background-color: #050b14; border-radius: 4px;"
                            )
                            with ui.column().classes('gap-0.5 col-grow overflow-hidden'):
                                with ui.row().classes('items-center gap-1.5 w-full no-wrap'):
                                    ui.label(r['nome_guerra']).classes('text-white text-base font-black uppercase truncate')
                                ui.label(f"Nº {r['numero_interno']} • PEL: {r['pelotao']}").classes('text-amber-5 text-[11px] font-bold font-mono')
                                ui.label(r.get('nome_completo') or 'Nome completo não informado').classes('text-grey text-[10px] truncate w-full')
                                ui.label(f"NIP: {r.get('nip') or 'N/A'} • Esp: {r.get('especialidade') or 'N/A'}").classes('text-grey-5 text-[10px] truncate')

                        ui.separator().style('background-color: rgba(255,255,255,0.05); height: 1px;').classes('my-1')

                        # 2. Middle Section: Concept and Score
                        with ui.row().classes('w-full justify-between items-center px-1 my-1'):
                            with ui.column().classes('gap-0'):
                                ui.label('CONCEITO').style(f'font-size: 8px; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
                                ui.label(f"{conceito:.2f}").style(f'color: {cor_conceito}; font-size: 1.6rem; font-weight: 900; line-height: 1;')
                            
                            with ui.column().classes('items-end gap-0'):
                                ui.label('PONTOS GERAIS').style(f'font-size: 8px; color: {THEME["text_dim"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
                                pts_color = '#00e676' if pontos > 0 else '#ff1744' if pontos < 0 else '#64748b'
                                ui.label(f"{pontos:+.1f}").style(f'color: {pts_color}; font-size: 1.4rem; font-weight: 900; font-family: monospace; line-height: 1;')

                        ui.separator().style('background-color: rgba(255,255,255,0.05); height: 1px;').classes('my-1')

                        # 3. Bottom Section: Action buttons
                        with ui.row().classes('w-full gap-1.5 justify-between no-wrap'):
                            ui.button('AÇÃO', icon='add', on_click=lambda r=r: show_registrar_acao_dialog(r)).props('unelevated dense no-caps').classes('col-grow text-[11px] font-bold').style(f'background: {THEME["bg_input"]}; border: 1px solid rgba(0, 229, 255, 0.2); color: #fff; border-radius: 4px;')
                            ui.button('HISTÓRICO', icon='history', on_click=lambda r=r: show_historico_dialog(r)).props('unelevated dense no-caps').classes('col-grow text-[11px] font-bold').style(f'background: {THEME["bg_input"]}; border: 1px solid rgba(0, 229, 255, 0.2); color: #fff; border-radius: 4px;')
                            ui.button('PERFIL', icon='manage_accounts', on_click=lambda r=r: show_info_dialog(r)).props('unelevated dense no-caps').classes('col-grow text-[11px] font-bold').style(f'background: {THEME["bg_input"]}; border: 1px solid rgba(0, 229, 255, 0.2); color: #fff; border-radius: 4px;')

            # Paginação
            with pagination_row:
                btn_prev = ui.button(icon='chevron_left', on_click=lambda: change_page(-1)).props('flat color=white dense').style('border: 1px solid rgba(0, 229, 255, 0.3); color: #00e5ff;')
                btn_prev.enabled = current_page > 1
                ui.label(f"Página {current_page} de {total_pages}").classes('text-white text-caption font-bold')
                btn_next = ui.button(icon='chevron_right', on_click=lambda: change_page(1)).props('flat color=white dense').style('border: 1px solid rgba(0, 229, 255, 0.3); color: #00e5ff;')
                btn_next.enabled = current_page < total_pages

        def change_page(delta):
            state['page'] += delta
            app.storage.user['alunos_state'] = state
            render_list()

        # --- DIALOGS E AÇÕES ---
        
        def open_add_aluno_dialog():
            d = ui.dialog()
            with d, ui.card().classes('w-96 q-pa-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
                ui.label('ADICIONAR NOVO ALUNO').style(f'color: {THEME["primary"]}; font-weight: bold; font-size: 1.1rem;').classes('cyber-title')
                
                num_int = ui.input('Número Interno*').props('dark outlined dense w-full')
                nome_g = ui.input('Nome de Guerra*').props('dark outlined dense w-full')
                nome_c = ui.input('Nome Completo').props('dark outlined dense w-full')
                pelo = ui.input('Pelotão*').props('dark outlined dense w-full')
                nip_val = ui.input('NIP').props('dark outlined dense w-full')
                espec_val = ui.input('Especialidade').props('dark outlined dense w-full')
                ano_let = ui.input('Ano Letivo*', value='2026').props('dark outlined dense w-full')
                foto_url = ui.input('URL da Foto (Opcional)').props('dark outlined dense w-full')
                
                async def handle_add_upload(e):
                    import inspect
                    import asyncio
                    file_bytes = e.file.read()
                    if inspect.isawaitable(file_bytes):
                        file_bytes = await file_bytes
                    ni = num_int.value or "temp"
                    filename = f"alunos/{ni}.jpg"
                    from database import upload_file_to_supabase_storage
                    public_url = await asyncio.to_thread(upload_file_to_supabase_storage, file_bytes, filename, e.file.content_type)
                    if public_url:
                        foto_url.value = public_url
                        ui.notify('Foto enviada com sucesso!', color='success')
                    else:
                        ui.notify('Erro ao enviar foto ao Supabase.', color='red')
                
                ui.upload(label='Enviar Foto para o Supabase', on_upload=handle_add_upload, auto_upload=True, max_files=1).props('dark dense').classes('w-full h-20')
                
                def salvar():
                    if not num_int.value or not nome_g.value or not pelo.value or not ano_let.value:
                        ui.notify('Por favor, preencha os campos obrigatórios (*)', color='warning')
                        return
                    try:
                        db_conn = get_db_connection()
                        novo = {
                            'numero_interno': num_int.value,
                            'nome_guerra': nome_g.value,
                            'nome_completo': nome_c.value or '',
                            'pelotao': pelo.value,
                            'especialidade': espec_val.value or '',
                            'ano_letivo': ano_let.value,
                            'nip': nip_val.value or '',
                            'url_foto': foto_url.value or ''
                        }
                        if db_conn:
                            db_conn.table('Alunos').insert(novo).execute()
                        else:
                            ui.notify('[OFFLINE] Aluno simulado criado com sucesso', color='warning')
                        ui.notify(f"Aluno {nome_g.value} adicionado!", color='positive')
                        d.close()
                        data_service.clear_cache()
                        render_cadastro_content.refresh()
                    except Exception as ex:
                        ui.notify(f"Erro ao salvar: {ex}", color='negative')
                
                with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                    ui.button('Cancelar', on_click=d.close).props('flat color=grey no-caps')
                    ui.button('Adicionar', on_click=salvar).props('unelevated no-caps').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')
            d.open()

        def show_registrar_acao_dialog(aluno):
            d = ui.dialog()
            with d, ui.card().classes('w-[420px] q-pa-lg rounded-2xl').style(
                f'background: {THEME["bg_panel"]}; border: 2px solid {THEME["primary"]}; box-shadow: 0 0 20px rgba(0, 229, 255, 0.25);'
            ):
                with ui.row().classes('items-center gap-2 q-mb-xs w-full'):
                    ui.icon('add_circle', color='amber', size='1.8rem')
                    with ui.column().classes('gap-0'):
                        ui.label("REGISTRAR COMPORTAMENTO").style(
                            f'color: {THEME["primary"]}; font-weight: 900; font-size: 1.1rem; letter-spacing: 1px;'
                        ).classes('cyber-title')
                        ui.label(f"Aluno: {aluno['nome_guerra'].upper()} ({aluno['numero_interno']})").classes('text-grey-4 text-xs font-mono font-semibold')
                
                ui.separator().style('background-color: rgba(0, 229, 255, 0.2); height: 2px;').classes('q-my-sm')
                
                # Agrupa tipos de acao
                tipos_copy = tipos_acao_df.copy()
                tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
                sorted_tipos = tipos_copy.sort_values('nome')
                
                opcoes_finais = []
                tipos_opcoes_map = {}
                
                positivas = sorted_tipos[sorted_tipos['pontuacao'] > 0]
                neutras = sorted_tipos[sorted_tipos['pontuacao'] == 0]
                negativas = sorted_tipos[sorted_tipos['pontuacao'] < 0]
                
                if not positivas.empty:
                    for _, r_t in positivas.iterrows():
                        lbl = f"➕ {r_t['nome']} (+{r_t['pontuacao']:.1f} pts)"
                        opcoes_finais.append(lbl)
                        tipos_opcoes_map[lbl] = r_t
                if not neutras.empty:
                    for _, r_t in neutras.iterrows():
                        lbl = f"⚪ {r_t['nome']} (0.0 pts)"
                        opcoes_finais.append(lbl)
                        tipos_opcoes_map[lbl] = r_t
                if not negativas.empty:
                    for _, r_t in negativas.iterrows():
                        lbl = f"➖ {r_t['nome']} ({r_t['pontuacao']:.1f} pts)"
                        opcoes_finais.append(lbl)
                        tipos_opcoes_map[lbl] = r_t
                
                with ui.column().classes('w-full gap-4 q-mt-sm'):
                    tipo_sel = ui.select(opcoes_finais, label='Tipo de Ação').props('dark outlined dense options-dark').classes('w-full')
                    desc = ui.textarea('Descrição / Justificativa (Opcional)').props('dark outlined dense').classes('w-full').style('min-height: 80px;')
                    data_acao = ui.input('Data da Ação', value=datetime.now().strftime('%Y-%m-%d')).props('dark outlined dense type=date').classes('w-full')
                
                def salvar():
                    if not tipo_sel.value:
                        ui.notify('Selecione um tipo de ação', color='warning')
                        return
                    try:
                        tipo_info = tipos_opcoes_map[tipo_sel.value]
                        db_conn = get_db_connection()
                        usuario = app.storage.user.get('user_data', {}).get('nome_guerra', 'Anonimo')
                        
                        nova_acao = {
                            'aluno_id': str(aluno['id']),
                            'tipo_acao_id': str(tipo_info['id']),
                            'tipo': tipo_info['nome'],
                            'descricao': desc.value or '',
                            'data': data_acao.value,
                            'usuario': usuario,
                            'status': 'Pendente'
                        }
                        if db_conn:
                            db_conn.table('Acoes').insert(nova_acao).execute()
                        else:
                            ui.notify('[OFFLINE] Ação registrada simulada', color='warning')
                        ui.notify('Ação registrada com sucesso!', color='positive')
                        
                        # Notifica a TV em tempo real para alertas instantâneos!
                        from alerts_manager import AlertsManager
                        score = float(tipo_info['pontuacao'])
                        tipo_alerta = "success" if score > 0 else "alert" if score < 0 else "info"
                        aluno_lbl = f"{aluno['numero_interno']} — {str(aluno['nome_guerra']).upper()} ({str(aluno['pelotao']).upper()})"
                        
                        AlertsManager.trigger_alert(
                            "Nova Anotação de Comportamento",
                            f"Lançado: {tipo_info['nome'].upper()} para {aluno_lbl} por {usuario.upper()}!",
                            tipo_alerta
                        )
                        
                        d.close()
                        data_service.clear_cache()
                        render_cadastro_content.refresh()
                    except Exception as ex:
                        ui.notify(f"Erro ao salvar: {ex}", color='negative')

                with ui.row().classes('w-full justify-end gap-2 q-mt-md border-t border-gray-800 q-pt-sm'):
                    ui.button('Cancelar', on_click=d.close).props('flat color=grey no-caps')
                    ui.button('REGISTRAR AÇÃO', on_click=salvar).props('unelevated no-caps').style(
                        f'background: {THEME["primary"]}; color: #000; font-weight: bold; border-radius: 6px;'
                    )
            d.open()

        def show_historico_dialog(aluno):
            d = ui.dialog()
            with d, ui.card().classes('w-[520px] q-pa-lg max-h-[600px] scroll rounded-2xl').style(
                f'background: {THEME["bg_panel"]}; border: 2px solid {THEME["primary"]}; box-shadow: 0 0 25px rgba(0, 229, 255, 0.25);'
            ):
                with ui.row().classes('items-center gap-2 q-mb-xs w-full'):
                    ui.icon('history', color='amber', size='1.8rem')
                    with ui.column().classes('gap-0'):
                        ui.label("HISTÓRICO DE COMPORTAMENTO").style(
                            f'color: {THEME["primary"]}; font-weight: 900; font-size: 1.1rem; letter-spacing: 1px;'
                        ).classes('cyber-title')
                        ui.label(f"Aluno: {aluno['nome_guerra'].upper()} ({aluno['numero_interno']})").classes('text-grey-4 text-xs font-mono font-semibold')
                
                ui.separator().style('background-color: rgba(0, 229, 255, 0.2); height: 2px;').classes('q-my-sm')
                
                # Filtra acoes
                if not acoes_df.empty:
                    aluno_actions = acoes_df[acoes_df['aluno_id'].astype(str) == str(aluno['id'])]
                else:
                    aluno_actions = pd.DataFrame()
                    
                if aluno_actions.empty:
                    with ui.column().classes('w-full items-center justify-center q-my-xl gap-2'):
                        ui.icon('assignment_late', color='grey-6', size='3.5rem').classes('animate-pulse')
                        ui.label('Nenhum registro encontrado no histórico deste aluno.').classes('text-grey-4 italic text-sm text-center')
                else:
                    # Calcula pontuação
                    tipos_copy = tipos_acao_df.copy()
                    tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
                    acoes_copy = aluno_actions.copy()
                    acoes_copy['tipo_acao_id'] = acoes_copy['tipo_acao_id'].astype(str)
                    tipos_copy['id'] = tipos_copy['id'].astype(str)
                    
                    hist_df = pd.merge(acoes_copy, tipos_copy[['id', 'pontuacao', 'nome']], left_on='tipo_acao_id', right_on='id', how='left')
                    
                    with ui.column().classes('w-full gap-3 q-mt-sm max-h-[380px] overflow-y-auto q-pr-xs'):
                        for _, row_a in hist_df.sort_values('data', ascending=False).iterrows():
                            pts = row_a.get('pontuacao', 0.0)
                            
                            # Estilo conforme pontos
                            if pts > 0:
                                border_col = '#00e676'
                                bg_card = 'rgba(0, 230, 118, 0.03)'
                                icon = 'stars'
                                score_lbl = f"+{pts:.1f} pts"
                            elif pts < 0:
                                border_col = '#ff1744'
                                bg_card = 'rgba(255, 23, 68, 0.03)'
                                icon = 'gavel'
                                score_lbl = f"{pts:.1f} pts"
                            else:
                                border_col = '#64748b'
                                bg_card = 'rgba(100, 116, 139, 0.03)'
                                icon = 'info'
                                score_lbl = "0.0 pts"
                                
                            status_acao = row_a.get('status', 'Pendente')
                            badge_color = 'green-9' if status_acao == 'Lançado' else 'amber-9'
                            badge_text = 'LANÇADO' if status_acao == 'Lançado' else 'PENDENTE'
                            
                            try:
                                dt_fmt = pd.to_datetime(row_a['data']).strftime('%d/%m/%Y')
                            except Exception:
                                dt_fmt = str(row_a['data'])
                            
                            with ui.card().classes('w-full q-pa-sm border-l-4').style(
                                f'background: {bg_card}; border-left-color: {border_col}; '
                                f'border-top: 1px solid rgba(255,255,255,0.03); '
                                f'border-right: 1px solid rgba(255,255,255,0.03); '
                                f'border-bottom: 1px solid rgba(255,255,255,0.03); border-radius: 6px;'
                            ):
                                with ui.row().classes('w-full justify-between items-center no-wrap'):
                                    with ui.row().classes('items-center gap-1.5 no-wrap'):
                                        ui.icon(icon, color=border_col, size='1.2rem')
                                        ui.label(f"{dt_fmt} - {row_a.get('nome', 'Ação').upper()}").classes('text-white text-xs font-bold font-mono')
                                    with ui.row().classes('items-center gap-2 no-wrap'):
                                        ui.badge(badge_text, color=badge_color).props('dense').classes('text-[9px] font-bold')
                                        ui.label(score_lbl).style(f'color: {border_col}; font-size: 0.85rem; font-weight: 900; font-family: monospace;')
                                
                                if row_a.get('descricao'):
                                    ui.separator().style('background-color: rgba(255,255,255,0.05); height: 1px;').classes('q-my-xs')
                                    ui.label(row_a['descricao']).classes('text-grey-4 text-[11px] italic leading-tight').style('word-break: break-word; white-space: normal;')
                                
                                with ui.row().classes('w-full justify-end text-[9px] text-grey-5 font-mono q-mt-xs'):
                                    lançado_por = row_a.get('usuario', 'Anonimo').upper()
                                    ui.label(f"LANÇADO POR: {lançado_por}")

                with ui.row().classes('w-full justify-end gap-2 q-mt-md border-t border-gray-800 q-pt-sm'):
                    ui.button('FECHAR HISTÓRICO', on_click=d.close).props('unelevated no-caps').style(
                        f'background: {THEME["primary"]}; color: #000; font-weight: bold; border-radius: 6px;'
                    )
            d.open()

        def show_info_dialog(aluno):
            def sanitize_str(val):
                return str(val).strip() if pd.notna(val) and val is not None else ""
            
            nome_c_val = sanitize_str(aluno.get('nome_completo'))
            nome_g_val = sanitize_str(aluno.get('nome_guerra'))
            num_i_val = sanitize_str(aluno.get('numero_interno'))
            nip_val_str = sanitize_str(aluno.get('nip'))
            pelo_val_str = sanitize_str(aluno.get('pelotao'))
            espec_val_str = sanitize_str(aluno.get('especialidade'))
            foto_url_val = sanitize_str(aluno.get('url_foto'))
            tel_val = sanitize_str(aluno.get('telefone_contato'))
            endereco_val = sanitize_str(aluno.get('endereco'))
            emerg_nome_val = sanitize_str(aluno.get('contato_emergencia_nome'))
            emerg_tel_val = sanitize_str(aluno.get('contato_emergencia_numero'))
            armario_val = sanitize_str(aluno.get('numero_armario'))
            ano_letivo_val = sanitize_str(aluno.get('ano_letivo'))
            if not ano_letivo_val:
                ano_letivo_val = "2025"
            
            d = ui.dialog()
            with d, ui.card().classes('w-[560px] q-pa-lg rounded-2xl').style(
                f'background: {THEME["bg_panel"]}; border: 2px solid {THEME["primary"]}; box-shadow: 0 0 25px rgba(0, 229, 255, 0.25);'
            ):
                with ui.row().classes('items-center gap-2 q-mb-xs w-full'):
                    ui.icon('manage_accounts', color='amber', size='1.8rem')
                    with ui.column().classes('gap-0'):
                        ui.label("DETALHES & EDIÇÃO DO ALUNO").style(
                            f'color: {THEME["primary"]}; font-weight: 900; font-size: 1.1rem; letter-spacing: 1px;'
                        ).classes('cyber-title')
                        ui.label(f"Militar: {aluno['nome_guerra'].upper()} ({aluno['numero_interno']})").classes('text-grey-4 text-xs font-mono font-semibold')
                
                ui.separator().style('background-color: rgba(0, 229, 255, 0.2); height: 2px;').classes('q-my-sm')
                
                with ui.tabs().classes('w-full text-white q-mb-md') as tabs:
                    tab_pessoal = ui.tab('PESSOAL', icon='person')
                    tab_contato = ui.tab('CONTATO', icon='contacts')
                    tab_acad = ui.tab('ACADÊMICO', icon='school')
                    tab_outros = ui.tab('OUTROS', icon='extension')
                    
                with ui.tab_panels(tabs, value=tab_pessoal).classes('w-full bg-transparent p-0').style('background: transparent;') as panels:
                    with ui.tab_panel(tab_pessoal).classes('q-pa-none gap-3 column'):
                        # Layout duas colunas: Esquerda (Inputs), Direita (Foto)
                        with ui.row().classes('w-full items-start no-wrap gap-4'):
                            with ui.column().classes('col-grow gap-2'):
                                nome_c = ui.input('Nome Completo', value=nome_c_val).props('dark outlined dense').classes('w-full text-xs')
                                nome_g = ui.input('Nome de Guerra', value=nome_g_val).props('dark outlined dense').classes('w-full text-xs font-bold')
                                num_i = ui.input('Número Interno', value=num_i_val).props('dark outlined dense').classes('w-full text-xs font-mono')
                            
                            # Foto de Visualização Dinâmica
                            image_src = foto_url_val if foto_url_val.startswith('http') else f"https://res.cloudinary.com/comcia/image/upload/alunos_app/{num_i_val}.jpg"
                            with ui.column().classes('items-center shrink-0 justify-center'):
                                img_box = ui.element('div').classes('shadow border border-cyan-500/30').style(
                                    f"width: 90px; height: 90px; background-image: url('{image_src}'); "
                                    f"background-size: cover; background-repeat: no-repeat; "
                                    f"background-position: center; background-color: #050b14; border-radius: 4px;"
                                )
                                ui.label('FOTO ATUAL').classes('text-[9px] text-grey-5 font-bold tracking-widest q-mt-xs')
                        
                        with ui.row().classes('w-full gap-2'):
                            pelo_val = ui.input('Pelotão', value=pelo_val_str).props('dark outlined dense').classes('col-grow text-xs')
                            espec_val = ui.input('Especialidade', value=espec_val_str).props('dark outlined dense').classes('col-grow text-xs')
                            nip_val = ui.input('NIP', value=nip_val_str).props('dark outlined dense').classes('col-grow text-xs font-mono')
                            
                        # Campo de URL da foto com binding dinâmico para atualizar a imagem no box
                        foto_url = ui.input('URL da Foto', value=foto_url_val).props('dark outlined dense').classes('w-full text-xs')
                        
                        async def handle_edit_upload(e):
                            import inspect
                            import asyncio
                            file_bytes = e.file.read()
                            if inspect.isawaitable(file_bytes):
                                file_bytes = await file_bytes
                            ni = num_i.value or aluno['numero_interno']
                            filename = f"alunos/{ni}.jpg"
                            from database import upload_file_to_supabase_storage
                            public_url = await asyncio.to_thread(upload_file_to_supabase_storage, file_bytes, filename, e.file.content_type)
                            if public_url:
                                foto_url.value = public_url
                                update_foto_preview()
                                ui.notify('Foto enviada com sucesso!', color='success')
                            else:
                                ui.notify('Erro ao enviar foto ao Supabase.', color='red')
                        
                        ui.upload(label='Enviar Foto para o Supabase', on_upload=handle_edit_upload, auto_upload=True, max_files=1).props('dark dense').classes('w-full h-20')
                        
                        def update_foto_preview():
                            src = foto_url.value.strip() if foto_url.value else ''
                            if not src.startswith('http'):
                                src = f"https://res.cloudinary.com/comcia/image/upload/alunos_app/{num_i_val}.jpg"
                            img_box.style(f"background-image: url('{src}');")
                        
                        foto_url.on('change', update_foto_preview)

                    with ui.tab_panel(tab_contato).classes('q-pa-none gap-3 column'):
                        with ui.row().classes('w-full items-center gap-2 no-wrap'):
                            tel = ui.input('Telefone de Contato', value=tel_val).props('dark outlined dense').classes('col-grow text-xs')
                            
                            # WhatsApp helper button
                            num_limpo = re.sub(r'\D', '', tel_val)
                            if len(num_limpo) >= 10:
                                with ui.button(icon='chat', on_click=lambda: ui.navigate.to(f'https://wa.me/55{num_limpo}', new_tab=True)).props('unelevated dense color=green').classes('w-10 h-10 rounded'):
                                    ui.tooltip('Chamar Militar no WhatsApp').classes('bg-slate-800 text-white text-xs')
                        
                        end = ui.textarea('Endereço Residencial', value=endereco_val).props('dark outlined dense').classes('w-full text-xs').style('min-height: 60px;')
                        
                        ui.separator().style('background-color: rgba(255,255,255,0.05); height: 1px;').classes('q-my-xs')
                        ui.label('CONTATO DE EMERGÊNCIA').classes('text-[10px] text-amber-5 font-bold tracking-widest')
                        
                        with ui.row().classes('w-full gap-2'):
                            emerg_nome = ui.input('Nome do Contato', value=emerg_nome_val).props('dark outlined dense').classes('col-grow text-xs')
                            
                            with ui.row().classes('items-center gap-2 col-grow no-wrap'):
                                emerg_tel = ui.input('Telefone de Emergência', value=emerg_tel_val).props('dark outlined dense').classes('col-grow text-xs')
                                
                                num_emerg_limpo = re.sub(r'\D', '', emerg_tel_val)
                                if len(num_emerg_limpo) >= 10:
                                    with ui.button(icon='phone_in_talk', on_click=lambda: ui.navigate.to(f'https://wa.me/55{num_emerg_limpo}', new_tab=True)).props('unelevated dense color=blue').classes('w-10 h-10 rounded'):
                                        ui.tooltip('Chamar Contato de Emergência').classes('bg-slate-800 text-white text-xs')

                    with ui.tab_panel(tab_acad).classes('q-pa-none gap-3 column'):
                        media_a = ui.number('Média Acadêmica Final', value=float(aluno.get('media_academica') or 0.0), min=0.0, max=10.0, format='%.2f').props('dark outlined dense').classes('w-full text-xs font-mono')
                        ano_let = ui.input('Ano Letivo', value=ano_letivo_val).props('dark outlined dense').classes('w-full text-xs')
                        with ui.card().classes('w-full q-pa-sm border border-cyan-500/20 bg-cyan-950/20 rounded'):
                            ui.label('💡 A média acadêmica é integrada diretamente ao cálculo do conceito de comportamento final do militar no SisCOMCA.').classes('text-[11px] text-cyan-300 leading-tight')

                    with ui.tab_panel(tab_outros).classes('q-pa-none gap-3 column'):
                        armario = ui.input('Número do Armário', value=armario_val).props('dark outlined dense').classes('w-full text-xs font-mono')
                        with ui.card().classes('w-full q-pa-sm border border-amber-500/20 bg-amber-950/20 rounded'):
                            ui.label('🔒 O controle patrimonial do número do armário permite auditorias rápidas no alojamento.').classes('text-[11px] text-amber-300 leading-tight')

                def salvar():
                    try:
                        db_conn = get_db_connection()
                        dados_up = {
                            'media_academica': media_a.value,
                            'nome_completo': nome_c.value or '',
                            'nome_guerra': nome_g.value or '',
                            'numero_interno': num_i.value or '',
                            'pelotao': pelo_val.value or '',
                            'especialidade': espec_val.value or '',
                            'ano_letivo': ano_let.value or '2025',
                            'url_foto': foto_url.value or '',
                            'nip': nip_val.value or '',
                            'endereco': end.value or '',
                            'telefone_contato': tel.value or '',
                            'contato_emergencia_nome': emerg_nome.value or '',
                            'contato_emergencia_numero': emerg_tel.value or '',
                            'numero_armario': armario.value or ''
                        }
                        if db_conn:
                            db_conn.table('Alunos').update(dados_up).eq('id', aluno['id']).execute()
                        else:
                            ui.notify('[OFFLINE] Dados de perfil atualizados de forma simulada', color='warning')
                        ui.notify('Dados atualizados com sucesso!', color='positive')
                        d.close()
                        data_service.clear_cache()
                        render_cadastro_content.refresh()
                    except Exception as ex:
                        ui.notify(f"Erro ao salvar: {ex}", color='negative')

                with ui.row().classes('w-full justify-end gap-2 q-mt-md border-t border-gray-800 q-pt-sm'):
                    ui.button('Cancelar', on_click=d.close).props('flat color=grey no-caps')
                    ui.button('SALVAR ALTERAÇÕES', on_click=salvar).props('unelevated no-caps').style(
                        f'background: {THEME["primary"]}; color: #000; font-weight: bold; border-radius: 6px;'
                    )
            d.open()

        # Render inicial da lista de alunos
        render_list()

    # Render do conteúdo principal
    with ui.column().classes('w-full q-pa-lg gap-6'):
        render_cadastro_content()
