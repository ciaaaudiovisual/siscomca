from nicegui import ui, app
import pandas as pd
from datetime import datetime
import theme
from database import carregar_presenca_hoje, salvar_presenca_supabase, deletar_presenca_supabase
from services import data_service

THEME = theme.colors

OFFLINE_AVATAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='rgb(27,37,53)'/><circle cx='50' cy='40' r='20' fill='rgb(100,116,139)'/><path d='M20,90 C20,70 80,70 80,90 Z' fill='rgb(100,116,139)'/></svg>"

# Motivos de Ausência baseados no SisCOMCA original
MOTIVOS_AUSENCIA = [
    "Doença",
    "Licença",
    "Pernoite",
    "Saída Autorizada",
    "Falta Injustificada",
    "Outro"
]

import re
from database import get_db_connection

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def render_page():
    # Estado local de filtragem
    state = app.storage.user.get('presenca_state', {
        'pelotao': 'Todos',
        'search': ''
    })
    app.storage.user['presenca_state'] = state

    @ui.refreshable
    def render_presenca_content():
        # 1. Carrega os dados de Alunos e da Chamada de Hoje
        alunos_df = data_service.get_alunos_data()
        
        # Garante colunas de perfil do aluno
        if 'pelotao' not in alunos_df.columns:
            alunos_df['pelotao'] = 'Sem Pelotão'
        if 'nome_guerra' not in alunos_df.columns:
            alunos_df['nome_guerra'] = 'Desconhecido'
        if 'url_foto' not in alunos_df.columns:
            alunos_df['url_foto'] = None
            
        # Carrega os registros de chamada de hoje
        presenca_hoje_df = carregar_presenca_hoje()
        
        # Indexa a presença por numero_interno para busca rápida (convertido para string)
        presenca_dict = {}
        if not presenca_hoje_df.empty:
            presenca_hoje_df['numero_interno'] = presenca_hoje_df['numero_interno'].astype(str)
            presenca_dict = presenca_hoje_df.set_index('numero_interno').to_dict(orient='index')

        # 2. Carrega informações de saúde e restrições ativas
        db_conn = get_db_connection()
        saude_dict = {}
        if db_conn:
            try:
                res_enf = db_conn.table('enfermaria').select('*').neq('status', 'Alta').execute()
                enfermaria_list = res_enf.data if res_enf.data else []
                for e in enfermaria_list:
                    ni = str(e['numero_interno'])
                    saude_dict[ni] = {
                        'categoria': e.get('categoria') or 'enfermaria',
                        'status': 'Encaminhado para enfermaria' if e.get('status') == 'Em Observação' else (e.get('status') or 'Encaminhado para enfermaria'),
                        'motivo': e.get('motivo') or e.get('observacao') or 'Restrição médica'
                    }
            except Exception as ex:
                print(f"[PRESENCA] Erro ao carregar saude: {ex}")

        # Filtra os alunos baseado no estado
        df_filtrado = alunos_df.copy()
        
        # Filtro de Pelotão
        if state['pelotao'] != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['pelotao'] == state['pelotao']]
            
        # Filtro de Busca por texto
        if state['search']:
            term = state['search'].lower()
            mask = (
                df_filtrado['nome_guerra'].str.lower().str.contains(term, na=False) |
                df_filtrado['numero_interno'].astype(str).str.lower().str.contains(term, na=False) |
                df_filtrado['nome_completo'].str.lower().str.contains(term, na=False)
            )
            df_filtrado = df_filtrado[mask]
            
        # Ordenação Natural Alfanumérica por numero_interno
        df_filtrado['sort_key'] = df_filtrado['numero_interno'].apply(natural_sort_key)
        df_filtrado = df_filtrado.sort_values('sort_key').drop(columns=['sort_key'])

        # --- CÁLCULO DE ESTATÍSTICAS ---
        total = len(df_filtrado)
        presentes = 0
        ausentes = 0
        sem_registro = 0
        
        for _, r in df_filtrado.iterrows():
            num = str(r['numero_interno'])
            if num in presenca_dict:
                if presenca_dict[num]['presente']:
                    presentes += 1
                else:
                    ausentes += 1
            else:
                sem_registro += 1
                
        percentual = (presentes / (presentes + ausentes) * 100) if (presentes + ausentes) > 0 else 0.0

        def registrar_presenca_aluno(aluno, presente: bool, motivo: str = None):
            try:
                num = str(aluno['numero_interno'])
                nome = str(aluno['nome_guerra'])
                pelotao = str(aluno['pelotao'])
                
                sucesso = salvar_presenca_supabase(
                    numero_interno=num,
                    nome_guerra=nome,
                    turma=pelotao,
                    presente=presente,
                    motivo_ausencia=motivo
                )
                
                if sucesso:
                    ui.notify(f"{nome} marcado como {'Presente' if presente else 'Ausente'}", color='positive')
                    data_service.clear_cache()
                    render_presenca_content.refresh()
                else:
                    ui.notify("Erro ao salvar presença no banco de dados", color='negative')
            except Exception as e:
                ui.notify(f"Erro: {e}", color='negative')

        def limpar_presenca_aluno(aluno):
            try:
                num = str(aluno['numero_interno'])
                nome = str(aluno['nome_guerra'])
                
                sucesso = deletar_presenca_supabase(numero_interno=num)
                
                if sucesso:
                    ui.notify(f"Presença de {nome} redefinida para pendente", color='info')
                    data_service.clear_cache()
                    render_presenca_content.refresh()
                else:
                    ui.notify("Erro ao redefinir presença no banco de dados", color='negative')
            except Exception as e:
                ui.notify(f"Erro: {e}", color='negative')

        def open_ausencia_dialog(aluno):
            d = ui.dialog()
            with d, ui.card().classes('w-96 q-pa-lg').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-radius: 8px;'):
                ui.label('REGISTRAR AUSÊNCIA').style(f'color: {THEME["danger"]}; font-weight: bold; font-size: 1.1rem;').classes('cyber-title')
                ui.label(f"Aluno: {aluno['nome_guerra']} ({aluno['numero_interno']})").classes('text-caption q-mb-md').style(f'color: {THEME["text_dim"]}')
                
                motivo_sel = ui.select(MOTIVOS_AUSENCIA, value='Doença', label='Motivo da Ausência').props('dark outlined dense w-full')
                obs = ui.textarea('Observações / Detalhes').props('dark outlined dense w-full')
                
                def salvar():
                    motivo_completo = motivo_sel.value
                    if obs.value:
                        motivo_completo += f" - {obs.value}"
                    
                    registrar_presenca_aluno(aluno, presente=False, motivo=motivo_completo)
                    d.close()
                    
                with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                    ui.button('Cancelar', on_click=d.close).props('flat no-caps').style(f'color: {THEME["text_dim"]};')
                    ui.button('Confirmar Ausência', on_click=salvar).props('unelevated no-caps').style(f'background: {THEME["danger"]}; color: #ffffff; font-weight: bold;').classes('cyber-glow')
            d.open()

        def marcar_todos_presentes():
            # Filtra os pendentes do pelotão atual
            pendentes = []
            for _, r in df_filtrado.iterrows():
                num = str(r['numero_interno'])
                if num not in presenca_dict:
                    pendentes.append(r)
            
            if not pendentes:
                ui.notify("Nenhum aluno pendente com os filtros atuais.", color='warning')
                return
            
            with ui.dialog() as confirm_dialog, ui.card().classes('w-96 q-pa-md').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}'):
                ui.label("CONFIRMAR CHAMADA EM LOTE").classes('font-bold text-base text-white cyber-title')
                pel_name = state['pelotao']
                ui.label(f"Deseja marcar {len(pendentes)} alunos do pelotão '{pel_name}' como PRESENTES?").classes('text-xs text-grey-4 q-my-md')
                
                def confirmar():
                    confirm_dialog.close()
                    sucessos = 0
                    with ui.spinner():
                        for student in pendentes:
                            num = str(student['numero_interno'])
                            nome = str(student['nome_guerra'])
                            pelotao = str(student['pelotao'])
                            sucesso = salvar_presenca_supabase(
                                numero_interno=num,
                                nome_guerra=nome,
                                turma=pelotao,
                                presente=True,
                                motivo_ausencia=''
                            )
                            if sucesso:
                                sucessos += 1
                    
                    if sucessos > 0:
                        ui.notify(f"{sucessos} alunos marcados como PRESENTES!", color='positive')
                        data_service.clear_cache()
                        render_presenca_content.refresh()
                    else:
                        ui.notify("Erro ao registrar chamadas em lote.", color='negative')
                
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button("Cancelar", on_click=confirm_dialog.close).props('flat color=grey')
                    ui.button("Confirmar", on_click=confirmar).props('unelevated color=primary text-color=black font-bold')
            confirm_dialog.open()

        # Dashboard de KPIs
        with ui.row().classes('w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4'):
            # Total Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["text_dim"]};'):
                ui.label('EFETIVO FILTRADO').classes('cyber-title text-xs').style(f'color: {THEME["text_dim"]}')
                ui.label(str(total)).classes('text-2xl font-bold').style(f'color: {THEME["text_main"]}')
                
            # Presentes Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["success"]};'):
                ui.label('PRESENTES').classes('cyber-title text-xs').style(f'color: {THEME["text_dim"]}')
                ui.label(str(presentes)).style(f'color: {THEME["success"]}; font-size: 1.5rem; font-weight: bold;')
                
            # Ausentes Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["danger"]};'):
                ui.label('AUSENTES').classes('cyber-title text-xs').style(f'color: {THEME["text_dim"]}')
                ui.label(str(ausentes)).style(f'color: {THEME["danger"]}; font-size: 1.5rem; font-weight: bold;')
                
            # Sem Registro Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["accent"]};'):
                ui.label('PENDENTES (SEM REGISTRO)').classes('cyber-title text-xs').style(f'color: {THEME["text_dim"]}')
                ui.label(str(sem_registro)).classes('text-2xl font-bold').style(f'color: {THEME["accent"]}')
                
            # Taxa Card
            with ui.card().classes('q-pa-md no-shadow').style(f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-left: 4px solid {THEME["primary"]};'):
                ui.label('INDICE DE PRESENÇA').classes('cyber-title text-xs').style(f'color: {THEME["text_dim"]}')
                ui.label(f"{percentual:.1f}%").style(f'color: {THEME["primary"]}; font-size: 1.5rem; font-weight: bold;')

        # Painel de Filtros e Lote
        with theme.card_base().classes('w-full q-pa-md'):
            ui.label('FILTRAR CHAMADA & OPERAÇÕES EM LOTE').style(f'font-size: 0.75rem; color: {THEME["primary"]}; font-weight: bold; letter-spacing: 1px;').classes('cyber-title')
            with ui.row().classes('w-full items-center justify-between wrap gap-4'):
                with ui.row().classes('items-center gap-4 col-grow'):
                    # Busca por nome/número
                    ui.input('Buscar Aluno por Nome ou Nº', value=state['search'], 
                             on_change=lambda e: update_state('search', e.value)).props('dark outlined dense').classes('col-grow')
                    
                    # Pelotão
                    pelotoes_list = ['Todos'] + sorted(list(alunos_df['pelotao'].dropna().unique()))
                    ui.select(pelotoes_list, label='Pelotão', value=state['pelotao'], 
                              on_change=lambda e: update_state('pelotao', e.value)).props('dark outlined dense').classes('w-64')
                
                # Ações de lote e recarga
                with ui.row().classes('items-center gap-2'):
                    ui.button('Chamada Coletiva', icon='playlist_add_check', on_click=marcar_todos_presentes).props('unelevated dense no-caps').classes('h-10 cyber-glow').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;')
                    ui.button('Limpar Cache', icon='refresh', on_click=lambda: recarregar_dados()).props('outline dense no-caps').classes('h-10').style(f'border-color: rgba(0, 229, 255, 0.3); color: {THEME["primary"]};')

        # Grid principal de duas colunas: Checklist à esquerda (70%) e Resumo de Ausentes à direita (30%)
        with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap'):
            # Checklist
            with ui.column().classes('w-full lg:w-8/12 gap-4'):
                ui.label('CHECKLIST DE PRESENÇA').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                
                with ui.column().classes('w-full gap-3'):
                    if df_filtrado.empty:
                        ui.label('Nenhum aluno encontrado').classes('italic q-my-md').style(f'color: {THEME["text_dim"]}')
                    else:
                        for _, r in df_filtrado.iterrows():
                            num = str(r['numero_interno'])
                            nome = r['nome_guerra']
                            pel = r['pelotao']
                            foto_url = r.get('url_foto')
                            ano_let = r.get('ano_letivo', '2026')
                            fallback_img = f"https://res.cloudinary.com/comcia/image/upload/alunos_app/{num}.jpg" if ano_let == '2025' else OFFLINE_AVATAR
                            image_src = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else fallback_img
                            
                            # Status atual da chamada
                            status_label = "Sem registro de chamada"
                            status_color = THEME['text_dim']
                            registro_hora = None
                            is_present = None
                            motivo_text = ""
                            
                            if num in presenca_dict:
                                is_present = presenca_dict[num]['presente']
                                registro_hora = presenca_dict[num].get('hora')
                                if is_present:
                                    status_label = "PRESENTE"
                                    status_color = THEME['success']
                                else:
                                    motivo_text = presenca_dict[num].get('motivo_ausencia') or "Motivo não informado"
                                    status_label = f"AUSENTE ({motivo_text})"
                                    status_color = THEME['danger']

                            # Mapeia informações de saúde
                            saude_info = saude_dict.get(num)
                            saude_badge_text = None
                            saude_badge_color = None
                            
                            if saude_info:
                                cat = saude_info['categoria']
                                st = saude_info['status']
                                mot = saude_info['motivo']
                                
                                if cat == 'enfermaria':
                                    if st == 'Hospitalizado':
                                        saude_badge_text = f"🚑 HOSPITALIZADO: {mot}"
                                        saude_badge_color = 'purple'
                                    elif st == 'Internado':
                                        saude_badge_text = f"🏥 BAIXADO ENFERMARIA: {mot}"
                                        saude_badge_color = 'red-5'
                                    else:
                                        saude_badge_text = f"🏥 ENCAMINHADO PARA ENFERMARIA: {mot}"
                                        saude_badge_color = 'red-4'
                                elif cat == 'licenca':
                                    saude_badge_text = f"✈️ LICENCIADO: {mot}"
                                    saude_badge_color = 'blue'
                                elif cat == 'dispensa':
                                    saude_badge_text = f"📝 DISPENSA ({st}): {mot}"
                                    saude_badge_color = 'orange'

                            with theme.card_base().classes('w-full q-pa-sm'):
                                with ui.row().classes('w-full items-center justify-between wrap md:no-wrap gap-2'):
                                    # Foto, nome, número, pelotão
                                    with ui.row().classes('items-center gap-3'):
                                        if image_src:
                                            ui.avatar(size='38px').classes('shadow border border-cyan-500/30').style(f"background-image: url('{image_src}'); background-size: cover; background-position: center;")
                                        else:
                                            ui.avatar(icon='person', size='38px').style(f'background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); color: {THEME["primary"]};')
                                            
                                        with ui.column().classes('gap-0'):
                                            with ui.row().classes('items-center gap-2'):
                                                ui.label(nome).classes('font-bold uppercase').style(f'color: {THEME["text_main"]}')
                                                ui.label(f"({num})").classes('text-xs font-mono').style(f'color: {THEME["primary"]}')
                                            
                                            with ui.row().classes('items-center gap-2 wrap'):
                                                ui.label(f"Pelotão: {pel}").classes('text-[10px]').style(f'color: {THEME["text_dim"]}')
                                                if saude_badge_text:
                                                    ui.badge(saude_badge_text, color=saude_badge_color).props('dense text-color=white').classes('text-[9px]')
                                            
                                    # Badge de Status atual
                                    with ui.row().classes('items-center gap-2'):
                                        ui.label(status_label).style(f'color: {status_color}; font-size: 0.72rem; font-weight: 700; border: 1px solid {status_color}; border-radius: 4px; padding: 2px 6px;')
                                        if registro_hora:
                                            ui.label(f"às {registro_hora}").classes('text-[9px]').style(f'color: {THEME["text_dim"]}')

                                    # Ações Rápidas (Presença / Ausência)
                                    with ui.row().classes('items-center gap-1.5'):
                                        # Botão Presente
                                        btn_pres = ui.button(icon='check', on_click=lambda r=r: registrar_presenca_aluno(r, presente=True))
                                        btn_pres.props('unelevated dense rounded').classes('w-8 h-8')
                                        if is_present is True:
                                            btn_pres.props(f'color=green')
                                        else:
                                            btn_pres.props('flat').style(f'color: {THEME["success"]};')
                                            
                                        # Botão Ausente
                                        btn_aus = ui.button(icon='close', on_click=lambda r=r: open_ausencia_dialog(r))
                                        btn_aus.props('unelevated dense rounded').classes('w-8 h-8')
                                        if is_present is False:
                                            btn_aus.props(f'color=red')
                                        else:
                                            btn_aus.props('flat').style(f'color: {THEME["danger"]};')

                                        # Botão Desfazer (Limpar registro de hoje de volta para pendente)
                                        if is_present is not None:
                                            btn_clear = ui.button(icon='undo', on_click=lambda r=r: limpar_presenca_aluno(r))
                                            btn_clear.props('flat dense rounded').classes('w-8 h-8').style(f'color: {THEME["accent"]};')
                                            with btn_clear:
                                                ui.tooltip('Desfazer chamada (Voltar para pendente)').classes('bg-slate-800 text-white text-xs')

            # Ausentes do Dia (Coluna Direita)
            with ui.column().classes('w-full lg:w-4/12 gap-4'):
                ui.label('AUSENTES REGISTRADOS HOJE').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                with theme.card_base().classes('w-full q-pa-md'):
                    # Filtra ausentes hoje do dicionário
                    ausentes_hoje = [v for k, v in presenca_dict.items() if not v['presente']]
                    
                    if not ausentes_hoje:
                        ui.label('Nenhum aluno ausente registrado hoje.').classes('italic text-xs q-my-sm').style(f'color: {THEME["text_dim"]}')
                    else:
                        ui.label(f"Total: {len(ausentes_hoje)} aluno(s)").classes('text-xs font-bold q-mb-md text-white')
                        with ui.column().classes('w-full gap-2'):
                            for a in sorted(ausentes_hoje, key=lambda x: x['nome_guerra']):
                                with ui.card().classes('w-full q-pa-sm border-l-4').style(f'background: {THEME["bg_input"]}; border-color: {THEME["danger"]}; border-top: 1px solid rgba(0, 229, 255, 0.05); border-right: 1px solid rgba(0, 229, 255, 0.05); border-bottom: 1px solid rgba(0, 229, 255, 0.05); border-radius: 4px;'):
                                    with ui.row().classes('w-full justify-between items-center'):
                                        ui.label(a['nome_guerra']).classes('text-xs font-bold uppercase').style(f'color: {THEME["text_main"]}')
                                        ui.label(a['turma']).classes('text-[10px] font-semibold').style(f'color: {THEME["primary"]}')
                                    ui.label(a.get('motivo_ausencia') or 'Sem motivo informado').classes('text-[11px] q-mt-xs').style(f'color: {THEME["text_dim"]}')
                                    if a.get('hora'):
                                        ui.label(f"Registrado às {a['hora']}").classes('text-[9px] q-mt-xxs').style(f'color: {THEME["text_dim"]}')

    def update_state(key, val):
        state[key] = val
        app.storage.user['presenca_state'] = state
        render_presenca_content.refresh()

    def recarregar_dados():
        data_service.clear_cache()
        render_presenca_content.refresh()

    render_presenca_content()
