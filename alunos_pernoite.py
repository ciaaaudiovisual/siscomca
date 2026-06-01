from nicegui import ui, app
import pandas as pd
from datetime import datetime
import theme
from database import get_db_connection, load_data, salvar_pernoites_supabase
from services import data_service
from fpdf import FPDF
import math
import io

THEME = theme.colors

# --- CLASSE PDF PERSONALIZADA PARA GERAR O RELATÓRIO ---
class PernoitePDF(FPDF):
    def __init__(self, cabecalho_txt, rodape_txt):
        super().__init__()
        self.cabecalho_texto = cabecalho_txt
        self.rodape_texto = rodape_txt

    def footer(self):
        # Rodapé personalizado
        self.set_y(-25)
        self.set_font('Helvetica', 'I', 10)
        self.multi_cell(0, 5, self.rodape_texto, 0, 'C')
        
        # Número da página
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def desenhar_corpo_tabela(self, titulo_secao, texto_esq, texto_dir, alunos_df):
        """Desenha uma seção completa da tabela com grid de 4 números por linha"""
        self.set_font("Helvetica", '', 12)
        y_antes = self.get_y()
        self.cell(self.w / 2, 8, texto_esq, 0, 0, 'L')
        self.set_y(y_antes)
        self.cell(0, 8, texto_dir, 0, 1, 'R')
        self.ln(5)

        self.set_font("Helvetica", 'B', 12)
        self.cell(0, 10, titulo_secao, 1, 1, 'C')

        # Corpo da tabela
        self.set_font("Helvetica", '', 10)
        
        # Garante que numero_interno está ordenado
        lista_numeros_internos = []
        if not alunos_df.empty:
            lista_numeros_internos = sorted(alunos_df['numero_interno'].tolist(), key=lambda x: str(x))
            
        total_militares = len(lista_numeros_internos)

        if total_militares == 0:
            self.cell(0, 10, "Nenhum aluno selecionado para esta categoria.", 1, 1, 'C')
            self.ln(10)
            return

        num_pares_por_linha = 4
        largura_pagina = self.w - 2 * self.l_margin
        largura_par = largura_pagina / num_pares_por_linha
        largura_col_ordem = largura_par * 0.20
        largura_col_valor = largura_par * 0.80
        altura_linha = 8

        num_linhas_dados = math.ceil(total_militares / num_pares_por_linha)

        for line_idx in range(num_linhas_dados):
            for col_idx in range(num_pares_por_linha):
                idx = line_idx * num_pares_por_linha + col_idx
                if idx < total_militares:
                    ordem = str(idx + 1)
                    numero_interno = str(lista_numeros_internos[idx])
                else:
                    ordem = ""
                    numero_interno = ""

                self.cell(largura_col_ordem, altura_linha, ordem, 1, 0, 'C')
                self.cell(largura_col_valor, altura_linha, numero_interno, 1, 0, 'C')
            self.ln()
        
        self.ln(10)

def gerar_pdf_pernoite_bytes(cabecalho_principal, rodape_texto, alunos_m_df, alunos_q_df, textos_m, textos_q):
    pdf = PernoitePDF(cabecalho_principal, rodape_texto)
    pdf.add_page()

    # Desenha o cabeçalho principal
    pdf.set_font("Helvetica", 'B', 12)
    pdf.multi_cell(0, 6, pdf.cabecalho_texto, 0, 'C')
    pdf.ln(5)

    titulo_tabela = "NÚMERO INTERNO DE ALUNOS"

    # Desenha a seção para Alunos M (CAP)
    pdf.desenhar_corpo_tabela(
        titulo_tabela,
        textos_m['esquerda'],
        textos_m['direita'],
        alunos_m_df
    )

    # Desenha a seção para Alunos Q (QTPA)
    pdf.desenhar_corpo_tabela(
        titulo_tabela,
        textos_q['esquerda'],
        textos_q['direita'],
        alunos_q_df
    )

    # Retorna os bytes do PDF
    return pdf.output()

def render_page():
    # 1. Carrega dados de Alunos e Configurações
    alunos_df = data_service.get_alunos_data()
    
    # Remove pelotão 'BAIXA'
    if 'pelotao' in alunos_df.columns:
        alunos_df = alunos_df[alunos_df['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()
    else:
        alunos_df['pelotao'] = 'Sem Pelotão'
        
    if 'nome_guerra' not in alunos_df.columns:
        alunos_df['nome_guerra'] = 'Desconhecido'

    # Identificar tipo de aluno (M = CAP, Q = QTPA, Outro)
    alunos_df['numero_interno'] = alunos_df['numero_interno'].astype(str)
    def identificar_tipo(num):
        num_clean = num.strip().upper()
        if num_clean.startswith('M'): return 'M'
        elif num_clean.startswith('Q'): return 'Q'
        else: return 'Outro'
    alunos_df['tipo_aluno'] = alunos_df['numero_interno'].apply(identificar_tipo)

    # Carrega configurações
    config_df = data_service.get_config_data()
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}

    # Estado local
    state = app.storage.user.get('pernoite_state', {
        'data_selecionada': datetime.now().strftime('%Y-%m-%d'),
        'pelotao': 'Todos',
        'status_marcados': {} # indexado por aluno_id (string)
    })
    app.storage.user['pernoite_state'] = state

    # Carrega pernoites para a data selecionada
    pernoite_df = load_data('pernoite')
    
    # Se ainda não carregamos os dados do banco para esta data
    # (ou se mudou a data e precisamos sincronizar com o estado local)
    data_sel = state['data_selecionada']
    
    # Inicializa estados de checkboxes com o banco para a data selecionada
    if not pernoite_df.empty:
        pernoite_df['data'] = pd.to_datetime(pernoite_df['data']).dt.strftime('%Y-%m-%d')
        pernoite_hoje = pernoite_df[pernoite_df['data'] == data_sel]
        presentes_ids = pernoite_hoje[pernoite_hoje['presente'] == True]['aluno_id'].astype(str).tolist()
        
        # Sincroniza estado local
        for _, r in alunos_df.iterrows():
            aid = str(r['id'])
            if aid not in state['status_marcados'] or app.storage.user.get('pernoite_date_changed'):
                state['status_marcados'][aid] = aid in presentes_ids
        
        app.storage.user['pernoite_date_changed'] = False
        app.storage.user['pernoite_state'] = state

    # --- UI principal ---
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Controle de Pernoite', 'Marque os alunos autorizados a pernoitar e gere o relatório oficial.')
        
        with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap'):
            
            # Coluna Esquerda: Filtros e Seleção (7/12)
            with ui.column().classes('w-full lg:w-7/12 gap-4'):
                ui.label('CHECKLIST DE PERNOITE').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                
                # Barra de filtros
                with theme.card_base().classes('w-full q-pa-md'):
                    with ui.row().classes('w-full items-center gap-4'):
                        # Data
                        def on_date_change(e):
                            state['data_selecionada'] = e.value
                            app.storage.user['pernoite_date_changed'] = True
                            app.storage.user['pernoite_state'] = state
                            ui.navigate.reload()
                            
                        ui.input('Data do Pernoite', value=state['data_selecionada'], 
                                 on_change=on_date_change).props('dark outlined dense type=date').classes('col-grow')
                        
                        # Pelotão
                        pelotoes = ['Todos'] + sorted(list(alunos_df['pelotao'].dropna().unique()))
                        def on_pelotao_change(e):
                            state['pelotao'] = e.value
                            app.storage.user['pernoite_state'] = state
                            ui.navigate.reload()
                            
                        ui.select(pelotoes, label='Pelotão', value=state['pelotao'], 
                                  on_change=on_pelotao_change).props('dark outlined dense').classes('w-48')

                # Grid de Checkbox
                with theme.card_base().classes('w-full q-pa-md'):
                    # Filtra alunos por pelotão
                    df_exibir = alunos_df.copy()
                    if state['pelotao'] != 'Todos':
                        df_exibir = df_exibir[df_exibir['pelotao'] == state['pelotao']]
                    
                    df_exibir['num_int_num'] = pd.to_numeric(df_exibir['numero_interno'].str.replace(r'\D', '', regex=True), errors='coerce')
                    df_exibir = df_exibir.sort_values('num_int_num')
                    
                    # Botões de marcação em massa
                    with ui.row().classes('w-full justify-between items-center q-mb-md q-pb-sm').style('border-bottom: 1px solid rgba(0, 229, 255, 0.15)'):
                        ui.label(f"Militares Filtrados: {len(df_exibir)}").classes('cyber-title text-xs').style(f'color: {THEME["text_main"]}')
                        with ui.row().classes('gap-2'):
                            def marcar_todos(valor: bool):
                                for _, r in df_exibir.iterrows():
                                    state['status_marcados'][str(r['id'])] = valor
                                app.storage.user['pernoite_state'] = state
                                ui.navigate.reload()
                                
                            ui.button('Marcar Todos', on_click=lambda: marcar_todos(True)).props('outline dense no-caps').style(f'color: {THEME["success"]}; border-color: rgba(0, 230, 118, 0.3);')
                            ui.button('Desmarcar Todos', on_click=lambda: marcar_todos(False)).props('outline dense no-caps').style(f'color: {THEME["danger"]}; border-color: rgba(255, 23, 68, 0.3);')

                    # Renderiza Checkboxes
                    if df_exibir.empty:
                        ui.label('Nenhum aluno encontrado').classes('italic self-center q-my-md').style(f'color: {THEME["text_dim"]}')
                    else:
                        # Divide em CAP (M) e QTPA (Q)
                        alunos_m = df_exibir[df_exibir['tipo_aluno'] == 'M']
                        alunos_q = df_exibir[df_exibir['tipo_aluno'] == 'Q']
                        
                        # Seção M
                        if not alunos_m.empty:
                            ui.label('ALUNOS CAP (M)').classes('cyber-title text-xs q-mt-sm').style(f'color: {THEME["primary"]}')
                            with ui.grid(columns='1 xs:grid-cols-2 sm:grid-cols-3 md:grid-cols-4').classes('w-full gap-x-2 gap-y-0.5 q-mb-md'):
                                for _, r in alunos_m.iterrows():
                                    aid = str(r['id'])
                                    marcado = state['status_marcados'].get(aid, False)
                                    
                                    def make_change_handler(aid=aid):
                                        def handler(e):
                                            state['status_marcados'][aid] = e.value
                                            app.storage.user['pernoite_state'] = state
                                        return handler
                                        
                                    ui.checkbox(text=f"{r['nome_guerra']} ({r['numero_interno']})", 
                                                value=marcado, 
                                                on_change=make_change_handler()).props('dark dense').classes('text-[12px] font-medium text-grey-3')
                                    
                        # Seção Q
                        if not alunos_q.empty:
                            ui.separator().classes('q-my-sm').style('background-color: rgba(0, 229, 255, 0.1)')
                            ui.label('ALUNOS QTPA (Q)').classes('cyber-title text-xs q-mt-sm').style(f'color: {THEME["primary"]}')
                            with ui.grid(columns='1 xs:grid-cols-2 sm:grid-cols-3 md:grid-cols-4').classes('w-full gap-x-2 gap-y-0.5'):
                                for _, r in alunos_q.iterrows():
                                    aid = str(r['id'])
                                    marcado = state['status_marcados'].get(aid, False)
                                    
                                    def make_change_handler(aid=aid):
                                        def handler(e):
                                            state['status_marcados'][aid] = e.value
                                            app.storage.user['pernoite_state'] = state
                                        return handler
                                        
                                    ui.checkbox(text=f"{r['nome_guerra']} ({r['numero_interno']})", 
                                                value=marcado, 
                                                on_change=make_change_handler()).props('dark dense').classes('text-[12px] font-medium text-grey-3')

                # Botão salvar
                def salvar_pernoite():
                    registros_up = []
                    for aid, marcado in state['status_marcados'].items():
                        registros_up.append({
                            'aluno_id': int(aid),
                            'data': state['data_selecionada'],
                            'presente': marcado
                        })
                    
                    if registros_up:
                        sucesso = salvar_pernoites_supabase(registros_up)
                        if sucesso:
                            ui.notify('Controle de Pernoite salvo com sucesso!', color='positive')
                            data_service.clear_cache()
                            ui.navigate.reload()
                        else:
                            ui.notify('Erro ao salvar no banco de dados', color='negative')
                            
                ui.button('Salvar Alterações de Pernoite', icon='save', on_click=salvar_pernoite).props('unelevated no-caps w-full').style(f'background: {THEME["primary"]}; color: #0b0f19; font-weight: bold;').classes('q-mt-sm cyber-glow')

            # Coluna Direita: Customização do PDF e Download (5/12)
            with ui.column().classes('w-full lg:w-5/12 gap-4'):
                ui.label('CONFIGURAÇÕES E EXPORTAÇÃO PDF').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                
                with theme.card_base().classes('w-full q-pa-md'):
                    cabecalho_input = ui.textarea('Cabeçalho Principal do PDF', 
                                                  value=config_dict.get('cabecalho_pernoite_pdf', "Relação de Militares em Pernoite")).props('dark outlined dense w-full')
                    
                    ui.label('TEXTOS PARA ALUNOS CAP (M)').classes('text-[10px] font-bold tracking-wider q-mt-sm').style(f'color: {THEME["text_dim"]}')
                    with ui.row().classes('w-full gap-2'):
                        esq_m = ui.input('Superior Esquerdo', value=config_dict.get('texto_sup_esq_m_pdf', "Apresentação (Alunos CAP):")).props('dark outlined dense').classes('col-grow')
                        dir_m = ui.input('Superior Direito', value=config_dict.get('texto_sup_dir_m_pdf', "Assinatura (Alunos CAP):")).props('dark outlined dense').classes('col-grow')
                        
                    ui.label('TEXTOS PARA ALUNOS QTPA (Q)').classes('text-[10px] font-bold tracking-wider q-mt-sm').style(f'color: {THEME["text_dim"]}')
                    with ui.row().classes('w-full gap-2'):
                        esq_q = ui.input('Superior Esquerdo', value=config_dict.get('texto_sup_esq_q_pdf', "Apresentação (Alunos QTPA):")).props('dark outlined dense').classes('col-grow')
                        dir_q = ui.input('Superior Direito', value=config_dict.get('texto_sup_dir_q_pdf', "Assinatura (Alunos QTPA):")).props('dark outlined dense').classes('col-grow')
                        
                    rodape_input = ui.textarea('Texto do Rodapé do PDF', 
                                               value=config_dict.get('rodape_pernoite_pdf', "Texto do rodapé padrão.")).props('dark outlined dense w-full')

                    # Salvar textos padrão no config
                    def salvar_config_pdf():
                        configs = [
                            {'chave': 'cabecalho_pernoite_pdf', 'valor': cabecalho_input.value},
                            {'chave': 'rodape_pernoite_pdf', 'valor': rodape_input.value},
                            {'chave': 'texto_sup_esq_m_pdf', 'valor': esq_m.value},
                            {'chave': 'texto_sup_dir_m_pdf', 'valor': dir_m.value},
                            {'chave': 'texto_sup_esq_q_pdf', 'valor': esq_q.value},
                            {'chave': 'texto_sup_dir_q_pdf', 'valor': dir_q.value},
                        ]
                        try:
                            db_conn = get_db_connection()
                            if db_conn:
                                db_conn.table("Config").upsert(configs, on_conflict='chave').execute()
                                ui.notify('Textos padrão salvos com sucesso!', color='positive')
                            else:
                                ui.notify('[OFFLINE] Configurações de texto salvas localmente', color='warning')
                            data_service.clear_cache()
                        except Exception as ex:
                            ui.notify(f"Erro ao salvar configs: {ex}", color='negative')
                            
                    ui.button('Salvar Textos Padrão', icon='edit', on_click=salvar_config_pdf).props('flat dense no-caps w-full').classes('q-mt-sm').style(f'color: {THEME["primary"]};')

                # Botão gerar PDF
                def download_pdf():
                    ids_selecionados = [aid for aid, marcado in state['status_marcados'].items() if marcado]
                    if not ids_selecionados:
                        ui.notify('Nenhum aluno marcado em pernoite!', color='warning')
                        return
                    
                    # Filtra alunos marcados
                    alunos_marcados = alunos_df[alunos_df['id'].astype(str).isin(ids_selecionados)]
                    alunos_m = alunos_marcados[alunos_marcados['tipo_aluno'] == 'M']
                    alunos_q = alunos_marcados[alunos_marcados['tipo_aluno'] == 'Q']
                    
                    try:
                        # bytes do PDF
                        pdf_bytes = gerar_pdf_pernoite_bytes(
                            cabecalho_principal=cabecalho_input.value,
                            rodape_texto=rodape_input.value,
                            alunos_m_df=alunos_m,
                            alunos_q_df=alunos_q,
                            textos_m={'esquerda': esq_m.value, 'direita': dir_m.value},
                            textos_q={'esquerda': esq_q.value, 'direita': dir_q.value}
                        )
                        # download no NiceGUI
                        ui.download(pdf_bytes, filename=f"pernoite_{state['data_selecionada']}.pdf")
                        ui.notify('PDF Gerado com sucesso!', color='positive')
                    except Exception as ex:
                        ui.notify(f"Erro ao gerar PDF: {ex}", color='negative')
                ui.button('Gerar e Baixar PDF', icon='picture_as_pdf', on_click=download_pdf).props('unelevated no-caps w-full').style(f'background: {THEME["danger"]}; color: #ffffff; font-weight: bold;').classes('cyber-glow')
