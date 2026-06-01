from nicegui import ui, app
import pandas as pd
import json
import os
import theme
from dotenv import load_dotenv
from database import get_db_connection
from services import data_service

load_dotenv()

THEME = theme.colors
# Caminho de persistência local como fallback robusto
RANCHO_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".nicegui", "rancho_previa.json")

def load_rancho_local() -> dict:
    """Carrega dados das semanas e escolhas de rancho locais do arquivo JSON."""
    os.makedirs(os.path.dirname(RANCHO_FILE_PATH), exist_ok=True)
    if os.path.exists(RANCHO_FILE_PATH):
        try:
            with open(RANCHO_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "weeks" not in data or not data["weeks"]:
                    data["weeks"] = ["Semana 23 (01/06 a 05/06)", "Semana 24 (08/06 a 12/06)"]
                if "bookings" not in data:
                    data["bookings"] = {}
                return data
        except Exception as e:
            print("[RANCHO] Erro ao carregar JSON local:", e)
    
    return {
        "weeks": ["Semana 23 (01/06 a 05/06)", "Semana 24 (08/06 a 12/06)"],
        "bookings": {}
    }

def save_rancho_local(data: dict):
    """Salva dados das semanas e escolhas de rancho locais no arquivo JSON."""
    os.makedirs(os.path.dirname(RANCHO_FILE_PATH), exist_ok=True)
    try:
        with open(RANCHO_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[RANCHO] Erro ao salvar JSON local:", e)

def load_all_rancho_data() -> dict:
    """Carrega dados integrados de rancho."""
    return load_rancho_local()

def save_all_rancho_data(data: dict):
    """Salva dados integrados de rancho."""
    save_rancho_local(data)


def render_page():
    # 1. Carrega dados do efetivo
    alunos_df = data_service.get_alunos_data()
    if alunos_df.empty:
        # Fallback Mock seguro
        alunos_data = [
            {'id': 1, 'numero_interno': '101', 'nome_guerra': 'Silva', 'pelotao': 'Alfa'},
            {'id': 2, 'numero_interno': '102', 'nome_guerra': 'Santos', 'pelotao': 'Alfa'},
            {'id': 3, 'numero_interno': '201', 'nome_guerra': 'Oliveira', 'pelotao': 'Bravo'},
            {'id': 4, 'numero_interno': '202', 'nome_guerra': 'Costa', 'pelotao': 'Bravo'},
            {'id': 5, 'numero_interno': '301', 'nome_guerra': 'Pereira', 'pelotao': 'Charlie'},
        ]
        alunos_df = pd.DataFrame(alunos_data)

    # 2. Obtém pelotões únicos para o filtro
    pelotoes = ['TODOS']
    if not alunos_df.empty and 'pelotao' in alunos_df.columns:
        pelotoes.extend(sorted(alunos_df['pelotao'].dropna().unique()))

    # 3. Carrega banco de dados de rancho
    rancho_db = load_all_rancho_data()
    semanas = rancho_db.get("weeks", ["Semana 23 (01/06 a 05/06)", "Semana 24 (08/06 a 12/06)"])

    # 4. Estado da interface do usuário
    if 'rancho_view_state' not in app.storage.user:
        # Define primeiro pelotão real como padrão para carregar super leve e instantâneo
        default_pel = pelotoes[1] if len(pelotoes) > 1 else 'TODOS'
        app.storage.user['rancho_view_state'] = {
            'semana': semanas[0] if semanas else '',
            'turma': default_pel,
            'busca': ''
        }
    
    view_state = app.storage.user['rancho_view_state']

    # Garante semana preenchida
    if not view_state.get('semana') and semanas:
        view_state['semana'] = semanas[0]
        app.storage.user['rancho_view_state'] = view_state

    # 5. Inicialização automática de dados da semana selecionada (com as 4 refeições)
    semana_ativa = view_state.get('semana', '')
    if semana_ativa not in rancho_db["bookings"]:
        rancho_db["bookings"][semana_ativa] = {}
        
    bookings_semana = rancho_db["bookings"][semana_ativa]
    for _, row in alunos_df.iterrows():
        ni = str(row.get('numero_interno', '')).strip().upper()
        if not ni:
            continue
        if ni not in bookings_semana:
            # Por padrão de internato militar, assume-se que o militar comerá no rancho (True) todas as 4 refeições
            bookings_semana[ni] = {
                'seg_caf': True, 'seg_alm': True, 'seg_jan': True, 'seg_cei': True,
                'ter_caf': True, 'ter_alm': True, 'ter_jan': True, 'ter_cei': True,
                'qua_caf': True, 'qua_alm': True, 'qua_jan': True, 'qua_cei': True,
                'qui_caf': True, 'qui_alm': True, 'qui_jan': True, 'qui_cei': True,
                'sex_caf': True, 'sex_alm': True, 'sex_jan': True, 'sex_cei': True
            }
    
    # Persiste inicializações caso ocorram
    save_all_rancho_data(rancho_db)

    # 6. Cálculo dos Totais Semanais de Refeições
    def get_totals():
        semana_ref = view_state.get('semana', '')
        b_sem = rancho_db["bookings"].get(semana_ref, {})
        
        totals = {
            'seg_caf': 0, 'seg_alm': 0, 'seg_jan': 0, 'seg_cei': 0,
            'ter_caf': 0, 'ter_alm': 0, 'ter_jan': 0, 'ter_cei': 0,
            'qua_caf': 0, 'qua_alm': 0, 'qua_jan': 0, 'qua_cei': 0,
            'qui_caf': 0, 'qui_alm': 0, 'qui_jan': 0, 'qui_cei': 0,
            'sex_caf': 0, 'sex_alm': 0, 'sex_jan': 0, 'sex_cei': 0
        }
        
        for _, r in alunos_df.iterrows():
            ni = str(r.get('numero_interno', '')).strip().upper()
            if ni in b_sem:
                b = b_sem[ni]
                for key in totals:
                    if b.get(key, True):
                        totals[key] += 1
        
        return totals, len(alunos_df)

    # --- DIALOG CRIAR NOVA SEMANA ---
    with ui.dialog() as nova_semana_dialog, ui.card().classes('w-96 q-pa-md').style(
        f'background: {THEME["bg_panel"]}; border: {THEME["border"]}; border-radius: 12px;'
    ):
        with ui.column().classes('w-full items-center gap-4'):
            ui.label('🗓️ Criar Semana de Rancho').classes('text-white text-lg font-bold cyber-title')
            ui.label('Insira o nome de referência para a nova semana de refeições:').classes('text-grey-5 text-xs text-center')
            
            nome_input = ui.input('Nome da Semana', placeholder='Ex: Semana 25 (15/06 a 19/06)').props('dark outlined dense w-full')
            
            def criar_semana():
                val = nome_input.value.strip()
                if not val:
                    ui.notify('Por favor, insira o nome da semana.', color='warning')
                    return
                if val in semanas:
                    ui.notify('Essa semana já existe.', color='warning')
                    return
                
                # Registra nova semana
                semanas.append(val)
                rancho_db["weeks"] = semanas
                rancho_db["bookings"][val] = {}
                save_all_rancho_data(rancho_db)
                
                # Seleciona semana criada
                view_state['semana'] = val
                app.storage.user['rancho_view_state'] = view_state
                
                nova_semana_dialog.close()
                ui.notify(f'Semana "{val}" criada e selecionada!', color='success')
                ui.run_javascript("window.location.reload()")
                
            with ui.row().classes('w-full justify-end gap-2 q-mt-md'):
                ui.button('Cancelar', on_click=nova_semana_dialog.close).props('flat color=grey')
                ui.button('Criar', on_click=criar_semana).props('unelevated color=amber-9 text-color=black')


    # --- RENDERS REATIVOS ---

    @ui.refreshable
    def render_summary_cards():
        """Card do topo com resumo e contagem total do rancho para a cozinha."""
        totals, total_efetivo = get_totals()
        
        days_info = [
            {"day": "SEGUNDA-FEIRA", "caf": "seg_caf", "alm": "seg_alm", "jan": "seg_jan", "cei": "seg_cei"},
            {"day": "TERÇA-FEIRA", "caf": "ter_caf", "alm": "ter_alm", "jan": "ter_jan", "cei": "ter_cei"},
            {"day": "QUARTA-FEIRA", "caf": "qua_caf", "alm": "qua_alm", "jan": "qua_jan", "cei": "qua_cei"},
            {"day": "QUINTA-FEIRA", "caf": "qui_caf", "alm": "qui_alm", "jan": "qui_jan", "cei": "qui_cei"},
            {"day": "SEXTA-FEIRA", "caf": "sex_caf", "alm": "sex_alm", "jan": "sex_jan", "cei": "sex_cei"}
        ]
        
        with ui.row().classes('w-full gap-2.5 justify-between no-wrap overflow-x-auto q-mb-md'):
            for d in days_info:
                caf_val = totals.get(d["caf"], 0)
                alm_val = totals.get(d["alm"], 0)
                jan_val = totals.get(d["jan"], 0)
                cei_val = totals.get(d["cei"], 0)
                
                with ui.card().classes('q-pa-sm border border-gray-900').style(
                    'background: #090e1a; min-width: 175px; flex: 1; border-radius: 8px;'
                ):
                    ui.label(d["day"]).classes('text-xs font-bold text-amber-5 tracking-widest text-center w-full cyber-title')
                    ui.separator().style('background-color: rgba(0, 229, 255, 0.1);').classes('q-my-xs')
                    
                    # Café Row
                    with ui.row().classes('w-full justify-between items-center no-wrap q-mt-xs'):
                        with ui.row().classes('items-center gap-1'):
                            ui.icon('coffee', color='amber-5', size='0.95rem')
                            ui.label('Café').classes('text-[10px] text-grey-4')
                        ui.label(f"{caf_val} / {total_efetivo}").classes('text-[11px] font-bold text-amber-4 font-mono')
                    
                    # Almoço Row
                    with ui.row().classes('w-full justify-between items-center no-wrap q-mt-xs'):
                        with ui.row().classes('items-center gap-1'):
                            ui.icon('restaurant', color='green-5', size='0.95rem')
                            ui.label('Almoço').classes('text-[10px] text-grey-4')
                        ui.label(f"{alm_val} / {total_efetivo}").classes('text-[11px] font-bold text-green-4 font-mono')
                    
                    # Jantar Row
                    with ui.row().classes('w-full justify-between items-center no-wrap q-mt-xs'):
                        with ui.row().classes('items-center gap-1'):
                            ui.icon('dinner_dining', color='blue-5', size='0.95rem')
                            ui.label('Jantar').classes('text-[10px] text-grey-4')
                        ui.label(f"{jan_val} / {total_efetivo}").classes('text-[11px] font-bold text-blue-4 font-mono')
                    
                    # Ceia Row
                    with ui.row().classes('w-full justify-between items-center no-wrap q-mt-xs'):
                        with ui.row().classes('items-center gap-1'):
                            ui.icon('nights_stay', color='purple-4', size='0.95rem')
                            ui.label('Ceia').classes('text-[10px] text-grey-4')
                        ui.label(f"{cei_val} / {total_efetivo}").classes('text-[11px] font-bold text-purple-4 font-mono')


    @ui.refreshable
    def render_student_list():
        """Lista interativa e editável dos alunos com seus respectivos checkboxes das 4 refeições."""
        semana_ref = view_state.get('semana', '')
        bookings = rancho_db["bookings"].get(semana_ref, {})
        
        # Filtros de visualização
        f_turma = view_state.get('turma', 'TODOS')
        f_busca = view_state.get('busca', '').strip().upper()
        
        filtered_df = alunos_df.copy()
        if f_turma != 'TODOS':
            filtered_df = filtered_df[filtered_df['pelotao'] == f_turma]
            
        if f_busca:
            filtered_df = filtered_df[
                filtered_df['nome_guerra'].str.upper().str.contains(f_busca) |
                filtered_df['numero_interno'].astype(str).str.upper().str.contains(f_busca)
            ]
            
        # Ordenação natural por número interno
        def sort_key(ni_val):
            import re
            parts = re.split(r'(\d+)', str(ni_val))
            return [int(p) if p.isdigit() else p for p in parts]
            
        filtered_df['sort_col'] = filtered_df['numero_interno'].apply(sort_key)
        filtered_df = filtered_df.sort_values('sort_col').drop(columns=['sort_col'])
        
        # Configuração da Grid com 22 colunas alinhadas
        grid_style = 'display: grid; grid-template-columns: minmax(180px, 3fr) 60px repeat(20, minmax(28px, 1fr)); width: 100%; align-items: center;'
        
        with ui.column().classes('w-full overflow-x-auto'):
            with ui.column().style('min-width: 950px; gap: 0;'):
                # Cabeçalho Nível 1: Dias
                with ui.row().classes('w-full q-px-md q-py-xs items-center text-weight-bold text-grey-5').style(
                    'background: #0c1224; border-top-left-radius: 8px; border-top-right-radius: 8px; border-bottom: 1px solid rgba(0, 229, 255, 0.05); ' + grid_style
                ):
                    ui.label('MILITAR').classes('text-left text-xs font-bold tracking-wider')
                    ui.label('TURMA').classes('text-center text-xs font-bold tracking-wider gt-xs')
                    
                    ui.label('SEGUNDA-FEIRA').classes('text-center text-[10px] font-bold tracking-wider').style('grid-column: span 4; border-left: 1px solid rgba(0, 229, 255, 0.1); border-right: 1px solid rgba(0, 229, 255, 0.1); py: 2px;')
                    ui.label('TERÇA-FEIRA').classes('text-center text-[10px] font-bold tracking-wider').style('grid-column: span 4; border-right: 1px solid rgba(0, 229, 255, 0.1); py: 2px;')
                    ui.label('QUARTA-FEIRA').classes('text-center text-[10px] font-bold tracking-wider').style('grid-column: span 4; border-right: 1px solid rgba(0, 229, 255, 0.1); py: 2px;')
                    ui.label('QUINTA-FEIRA').classes('text-center text-[10px] font-bold tracking-wider').style('grid-column: span 4; border-right: 1px solid rgba(0, 229, 255, 0.1); py: 2px;')
                    ui.label('SEXTA-FEIRA').classes('text-center text-[10px] font-bold tracking-wider').style('grid-column: span 4; border-right: 1px solid rgba(0, 229, 255, 0.1); py: 2px;')
                
                # Cabeçalho Nível 2: Refeições (C, A, J, Ce)
                with ui.row().classes('w-full q-px-md q-py-xs items-center text-weight-bold text-grey-5 border-b border-gray-900').style(
                    'background: #090e1a; ' + grid_style
                ):
                    ui.label('').classes('text-xs font-bold')
                    ui.label('').classes('text-xs font-bold gt-xs')
                    
                    meal_colors = {
                        'C': 'color: #ffb300;',  # Amber
                        'A': 'color: #4caf50;',  # Green
                        'J': 'color: #2196f3;',  # Blue
                        'Ce': 'color: #9c27b0;'  # Purple
                    }
                    
                    for _ in range(5):
                        ui.label('C').classes('text-center text-[9px] font-bold').style(meal_colors['C'])
                        ui.label('A').classes('text-center text-[9px] font-bold').style(meal_colors['A'])
                        ui.label('J').classes('text-center text-[9px] font-bold').style(meal_colors['J'])
                        ui.label('Ce').classes('text-center text-[9px] font-bold').style(meal_colors['Ce'])
                
                if filtered_df.empty:
                    with ui.row().classes('w-full q-pa-lg justify-center bg-[#090e1a] border-b border-gray-900'):
                        ui.label('Nenhum aluno encontrado para os filtros atuais.').classes('text-grey italic text-sm')
                    return
                
                # Renderiza a lista de alunos
                for idx, row in filtered_df.iterrows():
                    ni = str(row.get('numero_interno', '')).strip().upper()
                    ng = str(row.get('nome_guerra', '')).strip().upper()
                    turma = str(row.get('pelotao', '')).strip().upper()
                    
                    b = bookings.get(ni, {
                        'seg_caf': True, 'seg_alm': True, 'seg_jan': True, 'seg_cei': True,
                        'ter_caf': True, 'ter_alm': True, 'ter_jan': True, 'ter_cei': True,
                        'qua_caf': True, 'qua_alm': True, 'qua_jan': True, 'qua_cei': True,
                        'qui_caf': True, 'qui_alm': True, 'qui_jan': True, 'qui_cei': True,
                        'sex_caf': True, 'sex_alm': True, 'sex_jan': True, 'sex_cei': True
                    })
                    
                    bg_color = '#090e1a' if idx % 2 == 0 else '#070a14'
                    
                    with ui.row().classes('w-full q-px-md q-py-xs items-center border-b border-gray-900 hover:bg-cyan-950/10').style(
                        f'background: {bg_color}; min-height: 44px; ' + grid_style
                    ):
                        # Info Militar
                        with ui.column().classes('gap-0').style('justify-self: start;'):
                            ui.label(ng).classes('text-white text-xs font-bold')
                            ui.label(f"NI: {ni}").classes('text-[10px] text-grey')
                            
                        # Turma
                        ui.label(turma).classes('text-xs text-grey text-center gt-xs')
                        
                        # Checkboxes para as 20 refeições
                        for day_prefix in ['seg', 'ter', 'qua', 'qui', 'sex']:
                            for meal_suffix in ['caf', 'alm', 'jan', 'cei']:
                                key = f"{day_prefix}_{meal_suffix}"
                                val = b.get(key, True)
                                
                                def make_change_handler(n=ni, k=key):
                                    def handler(e):
                                        bookings[n][k] = e.value
                                        render_summary_cards.refresh()
                                    return handler
                                    
                                ui.checkbox(value=val, on_change=make_change_handler()).props('dense dark').classes('justify-center').style('margin: 0 auto;')


    # --- CORPO DA PÁGINA ---

    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Prévia de Rancho', 'Controle e Consolidado de Refeições Semanais (Café, Almoço, Jantar e Ceia)')
        
        # 1. Painel de Resumo
        render_summary_cards()

        # 2. Painel de Controle e Filtros
        with theme.card_base().classes('w-full q-pa-md'):
            with ui.row().classes('w-full items-center justify-between gap-4'):
                # Semana dropdown
                with ui.row().classes('items-center gap-2 col-grow'):
                    def on_week_changed(e):
                        view_state['semana'] = e.value
                        app.storage.user['rancho_view_state'] = view_state
                        
                        # Recarrega ou cria chaves da semana
                        sw = e.value
                        if sw not in rancho_db["bookings"]:
                            rancho_db["bookings"][sw] = {}
                        
                        b_sw = rancho_db["bookings"][sw]
                        for _, r in alunos_df.iterrows():
                            ni = str(r.get('numero_interno', '')).strip().upper()
                            if ni and ni not in b_sw:
                                b_sw[ni] = {
                                    'seg_caf': True, 'seg_alm': True, 'seg_jan': True, 'seg_cei': True,
                                    'ter_caf': True, 'ter_alm': True, 'ter_jan': True, 'ter_cei': True,
                                    'qua_caf': True, 'qua_alm': True, 'qua_jan': True, 'qua_cei': True,
                                    'qui_caf': True, 'qui_alm': True, 'qui_jan': True, 'qui_cei': True,
                                    'sex_caf': True, 'sex_alm': True, 'sex_jan': True, 'sex_cei': True
                                }
                        save_all_rancho_data(rancho_db)
                        
                        # Atualiza Renders
                        render_summary_cards.refresh()
                        render_student_list.refresh()
                        ui.notify(f'Carregada: {sw}', color='info')

                    ui.select(semanas, label='Semana da Prévia', value=view_state['semana'], on_change=on_week_changed).props('dark outlined dense').classes('w-64')
                    ui.button(icon='add', on_click=nova_semana_dialog.open).props('unelevated round color=cyan-9 text-color=black dense').classes('cyber-glow')
                    ui.tooltip('Criar Nova Semana')

                # Filtro Turma
                def on_class_changed(e):
                    view_state['turma'] = e.value
                    app.storage.user['rancho_view_state'] = view_state
                    render_student_list.refresh()
                    
                ui.select(pelotoes, label='Filtrar por Turma', value=view_state['turma'], on_change=on_class_changed).props('dark outlined dense').classes('w-44')

                # Busca Aluno
                def on_search_changed(e):
                    view_state['busca'] = e.value or ''
                    app.storage.user['rancho_view_state'] = view_state
                    render_student_list.refresh()
                    
                ui.input('Pesquisar Aluno...', value=view_state['busca'], on_change=on_search_changed).props('dark outlined dense clearable').classes('w-48')

        # 3. Ações em Lote e Salvar
        with ui.row().classes('w-full justify-between items-center bg-[#070b16] q-pa-sm border border-gray-900 rounded'):
            # Atalhos rápidos (Aplicam-se apenas à turma filtrada atualmente)
            with ui.row().classes('items-center gap-1.5'):
                ui.label('EM LOTE:').classes('text-[9px] text-grey-5 font-bold tracking-wider mr-1')
                
                # Marcar todos Café
                def batch_marcar_caf():
                    sw = view_state.get('semana', '')
                    b_sw = rancho_db["bookings"].get(sw, {})
                    f_turma = view_state.get('turma', 'TODOS')
                    
                    df_target = alunos_df.copy()
                    if f_turma != 'TODOS':
                        df_target = df_target[df_target['pelotao'] == f_turma]
                        
                    for _, r in df_target.iterrows():
                        ni = str(r.get('numero_interno', '')).strip().upper()
                        if ni in b_sw:
                            for key in ['seg_caf', 'ter_caf', 'qua_caf', 'qui_caf', 'sex_caf']:
                                b_sw[ni][key] = True
                    
                    render_summary_cards.refresh()
                    render_student_list.refresh()
                    ui.notify('Lote: Todos os Cafés marcados (filtro ativo)', color='success')

                ui.button('Cafés', icon='check', on_click=batch_marcar_caf).props('outline dense no-caps color=amber-9').classes('text-[10px]')

                # Marcar todos Almoço
                def batch_marcar_almoc():
                    sw = view_state.get('semana', '')
                    b_sw = rancho_db["bookings"].get(sw, {})
                    f_turma = view_state.get('turma', 'TODOS')
                    
                    df_target = alunos_df.copy()
                    if f_turma != 'TODOS':
                        df_target = df_target[df_target['pelotao'] == f_turma]
                        
                    for _, r in df_target.iterrows():
                        ni = str(r.get('numero_interno', '')).strip().upper()
                        if ni in b_sw:
                            for key in ['seg_alm', 'ter_alm', 'qua_alm', 'qui_alm', 'sex_alm']:
                                b_sw[ni][key] = True
                    
                    render_summary_cards.refresh()
                    render_student_list.refresh()
                    ui.notify('Lote: Todos Almoços marcados (filtro ativo)', color='success')

                ui.button('Almoços', icon='check', on_click=batch_marcar_almoc).props('outline dense no-caps color=green').classes('text-[10px]')

                # Marcar todos Jantar
                def batch_marcar_jantar():
                    sw = view_state.get('semana', '')
                    b_sw = rancho_db["bookings"].get(sw, {})
                    f_turma = view_state.get('turma', 'TODOS')
                    
                    df_target = alunos_df.copy()
                    if f_turma != 'TODOS':
                        df_target = df_target[df_target['pelotao'] == f_turma]
                        
                    for _, r in df_target.iterrows():
                        ni = str(r.get('numero_interno', '')).strip().upper()
                        if ni in b_sw:
                            for key in ['seg_jan', 'ter_jan', 'qua_jan', 'qui_jan', 'sex_jan']:
                                b_sw[ni][key] = True
                    
                    render_summary_cards.refresh()
                    render_student_list.refresh()
                    ui.notify('Lote: Todos Jantares marcados (filtro ativo)', color='success')

                ui.button('Jantares', icon='check', on_click=batch_marcar_jantar).props('outline dense no-caps color=blue').classes('text-[10px]')

                # Marcar todos Ceia
                def batch_marcar_ceia():
                    sw = view_state.get('semana', '')
                    b_sw = rancho_db["bookings"].get(sw, {})
                    f_turma = view_state.get('turma', 'TODOS')
                    
                    df_target = alunos_df.copy()
                    if f_turma != 'TODOS':
                        df_target = df_target[df_target['pelotao'] == f_turma]
                        
                    for _, r in df_target.iterrows():
                        ni = str(r.get('numero_interno', '')).strip().upper()
                        if ni in b_sw:
                            for key in ['seg_cei', 'ter_cei', 'qua_cei', 'qui_cei', 'sex_cei']:
                                b_sw[ni][key] = True
                    
                    render_summary_cards.refresh()
                    render_student_list.refresh()
                    ui.notify('Lote: Todas as Ceias marcadas (filtro ativo)', color='success')

                ui.button('Ceias', icon='check', on_click=batch_marcar_ceia).props('outline dense no-caps color=purple').classes('text-[10px]')

                # Desmarcar Todos
                def batch_desmarcar_todos():
                    sw = view_state.get('semana', '')
                    b_sw = rancho_db["bookings"].get(sw, {})
                    f_turma = view_state.get('turma', 'TODOS')
                    
                    df_target = alunos_df.copy()
                    if f_turma != 'TODOS':
                        df_target = df_target[df_target['pelotao'] == f_turma]
                        
                    for _, r in df_target.iterrows():
                        ni = str(r.get('numero_interno', '')).strip().upper()
                        if ni in b_sw:
                            for key in b_sw[ni]:
                                b_sw[ni][key] = False
                    
                    render_summary_cards.refresh()
                    render_student_list.refresh()
                    ui.notify('Lote: Todas as refeições limpas (filtro ativo)', color='warning')

                ui.button('Limpar', icon='clear', on_click=batch_desmarcar_todos).props('outline dense no-caps color=red').classes('text-[10px]')

            # Salvar e Exportar
            with ui.row().classes('items-center gap-3'):
                # Exportar CSV
                def exportar_csv():
                    try:
                        sw = view_state.get('semana', '')
                        b_sw = rancho_db["bookings"].get(sw, {})
                        
                        rows = []
                        for _, r in alunos_df.iterrows():
                            ni = str(r.get('numero_interno', '')).strip().upper()
                            ng = str(r.get('nome_guerra', '')).strip().upper()
                            turma = str(r.get('pelotao', '')).strip().upper()
                            
                            b = b_sw.get(ni, {})
                            
                            rows.append({
                                "NI": ni,
                                "Militar": ng,
                                "Pelotão": turma,
                                "Seg-Café": "Sim" if b.get("seg_caf", True) else "Não",
                                "Seg-Almoço": "Sim" if b.get("seg_alm", True) else "Não",
                                "Seg-Jantar": "Sim" if b.get("seg_jan", True) else "Não",
                                "Seg-Ceia": "Sim" if b.get("seg_cei", True) else "Não",
                                "Ter-Café": "Sim" if b.get("ter_caf", True) else "Não",
                                "Ter-Almoço": "Sim" if b.get("ter_alm", True) else "Não",
                                "Ter-Jantar": "Sim" if b.get("ter_jan", True) else "Não",
                                "Ter-Ceia": "Sim" if b.get("ter_cei", True) else "Não",
                                "Qua-Café": "Sim" if b.get("qua_caf", True) else "Não",
                                "Qua-Almoço": "Sim" if b.get("qua_alm", True) else "Não",
                                "Qua-Jantar": "Sim" if b.get("qua_jan", True) else "Não",
                                "Qua-Ceia": "Sim" if b.get("qua_cei", True) else "Não",
                                "Qui-Café": "Sim" if b.get("qui_caf", True) else "Não",
                                "Qui-Almoço": "Sim" if b.get("qui_alm", True) else "Não",
                                "Qui-Jantar": "Sim" if b.get("qui_jan", True) else "Não",
                                "Qui-Ceia": "Sim" if b.get("qui_cei", True) else "Não",
                                "Sex-Café": "Sim" if b.get("sex_caf", True) else "Não",
                                "Sex-Almoço": "Sim" if b.get("sex_alm", True) else "Não",
                                "Sex-Jantar": "Sim" if b.get("sex_jan", True) else "Não",
                                "Sex-Ceia": "Sim" if b.get("sex_cei", True) else "Não"
                            })
                            
                        export_df = pd.DataFrame(rows)
                        csv_bytes = export_df.to_csv(index=False, sep=';').encode('utf-8')
                        ui.download(csv_bytes, filename=f"previa_rancho_{sw}.csv")
                        ui.notify('CSV de rancho exportado com sucesso!', color='success')
                    except Exception as e:
                        ui.notify(f'Erro ao exportar: {e}', color='negative')

                ui.button('Exportar CSV', icon='file_download', on_click=exportar_csv).props('outline dense no-caps color=cyan-9').classes('text-xs cyber-glow')

                # Salvar definitivo
                def salvar_rancho():
                    try:
                        save_all_rancho_data(rancho_db)
                        ui.notify('Escolhas de rancho salvas com sucesso!', color='positive')
                        render_summary_cards.refresh()
                        render_student_list.refresh()
                    except Exception as e:
                        ui.notify(f'Erro ao salvar: {e}', color='negative')

                ui.button('Salvar Escolhas', icon='save', on_click=salvar_rancho).props('unelevated dense').style(f'background: {THEME["primary"]}; color: #000; font-weight: bold;').classes('px-4 cyber-glow')

        # 4. A Lista interativa
        with ui.column().classes('w-full'):
            with ui.row().classes('w-full justify-between items-center text-caption text-grey mr-1 q-mb-xs'):
                ui.label('DICA: Use o "Filtrar por Turma" para otimizar o preenchimento por pelotões de forma rápida.').classes('italic')
                ui.label('C: Café | A: Almoço | J: Jantar | Ce: Ceia').classes('font-bold text-amber-5 tracking-widest text-xs')
                
            render_student_list()
