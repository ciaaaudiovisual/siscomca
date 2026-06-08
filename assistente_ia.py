from nicegui import ui, app
import pandas as pd
import re
import theme
import ai_helper
from database import get_bot_db_connection, load_data

THEME = theme.colors

OFFLINE_AVATAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='rgb(27,37,53)'/><circle cx='50' cy='40' r='20' fill='rgb(100,116,139)'/><path d='M20,90 C20,70 80,70 80,90 Z' fill='rgb(100,116,139)'/></svg>"


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


def render_page():
    db_conn = get_bot_db_connection()
    
    # Carrega dados dos alunos
    df_alunos = load_data("Alunos", db_conn=db_conn)
    if not df_alunos.empty:
        df_alunos['sort_key'] = df_alunos['numero_interno'].apply(natural_sort_key)
        df_alunos = df_alunos.sort_values(by='sort_key').drop(columns=['sort_key'])
        alunos_list = df_alunos.to_dict(orient='records')
    else:
        alunos_list = []

    # Carrega tipos de ações para cruzamento rápido
    df_tipos = load_data("Tipos_Acao", db_conn=db_conn)
    
    # State local
    state = {
        'selected_aluno': None,
        'chat_messages': [],
        'aluno_history_text': ""
    }

    with ui.column().classes('w-full q-pa-lg gap-4'):
        # Header do Painel
        theme.section_header(
            '⚓ C2-AI: Assistente Naval de IA', 
            'Aconselhamento de Conduta Disciplinar, Elaboração de Partes de Ocorrência e Redação Naval (RDM)'
        )

        # Tabs Quasar para as seções
        with ui.tabs().classes('w-full text-primary border-b border-gray-800') as tabs:
            tab_chat = ui.tab('💬 Conversa Tática')
            tab_disciplinar = ui.tab('⚖️ Partes & Regulamentos (RDM)')
            tab_redator = ui.tab('📝 Redator & Polidor Naval')

        with ui.tab_panels(tabs, value=tab_chat).classes('w-full bg-transparent no-shadow gap-0'):
            
            # ABA 1: CONVERSA TÁTICA (CHAT)
            with ui.tab_panel(tab_chat).classes('p-0 gap-4 w-full'):
                with ui.column().classes('w-full gap-4'):
                    # Card principal do Chat
                    with ui.card().classes('w-full q-pa-md h-[550px] flex flex-col justify-between border border-gray-800').style(f'background: {THEME["bg_panel"]}'):
                        
                        # Mensagem de Boas-vindas da IA
                        with ui.row().classes('w-full items-center gap-2 border-b border-gray-800 q-pb-sm'):
                            ui.avatar(icon='psychology').style(f'background: {THEME["primary"]}; color: {THEME["bg_app"]}; width: 32px; height: 32px;')
                            with ui.column().classes('gap-0'):
                                ui.label('ASSISTENTE VIRTUAL DO CORPO DE ALUNOS').classes('text-xs text-weight-bold tracking-wider text-white cyber-title')
                                ui.label('Motor Gemini 2.0 Flash • Pronto para Apoio Disciplinar Naval').classes('text-[10px] text-grey-5')
                        
                        # Área de Conversa com Scroll
                        with ui.scroll_area().classes('w-full flex-grow q-py-md') as scroll_area:
                            chat_area = ui.column().classes('w-full gap-3')
                            
                            # Bolha de boas vindas inicial
                            with chat_area:
                                with ui.row().classes('w-full gap-2 items-start justify-start'):
                                    ui.avatar(icon='psychology').style(f'background: {THEME["primary"]}; color: {THEME["bg_app"]}; width: 36px; height: 36px;')
                                    with ui.column().classes('max-w-[75%] gap-1'):
                                        ui.label('C2-AI').classes('text-[10px] text-grey-5 text-weight-bold')
                                        with ui.card().classes('q-pa-sm rounded-lg border border-gray-800').style(f'background: {THEME["bg_editor"]}; color: #e2e8f0;'):
                                            ui.label('Olá! Sou o Assistente Disciplinar e de Conduta do Corpo de Alunos da Marinha do Brasil. Posso responder dúvidas sobre o RDM, formatar Partes de Ocorrência navais, redigir correspondências ou analisar histórico comportamental. Como posso ajudar no serviço hoje?').classes('text-sm text-weight-medium')

                        # Atalhos Rápidos (Perguntas Frequentes)
                        with ui.row().classes('w-full gap-2 q-py-xs justify-center border-t border-gray-800/50'):
                            def select_fast_question(q_text):
                                chat_input.value = q_text
                                send_message()
                            
                            ui.button('📋 Como redigir uma Parte Naval?', on_click=lambda: select_fast_question('Como redigir uma Parte de Ocorrência formal no padrão da Marinha do Brasil? Quais os elementos essenciais?')).props('outline dense size=sm color=cyan').classes('text-[10px] font-bold')
                            ui.button('⚖️ O que diz o RDM sobre atrasos?', on_click=lambda: select_fast_question('O que o RDM (Regulamento Disciplinar da Marinha) diz sobre atrasos no regresso de licença ou escalas? Como classificar essa contravenção?')).props('outline dense size=sm color=cyan').classes('text-[10px] font-bold')
                            ui.button('⚓ Exemplos de Elogio Naval', on_click=lambda: select_fast_question('Escreva um exemplo de elogio militar ou anotação de destaque positivo naval para a FAIA.')).props('outline dense size=sm color=cyan').classes('text-[10px] font-bold')

                        # Caixa de Input e Envio
                        with ui.row().classes('w-full gap-2 items-center justify-between'):
                            chat_input = ui.input(placeholder='Escreva sua dúvida disciplinar ou naval aqui...').props('dark outlined dense').classes('flex-grow').style(f'background: {THEME["bg_input"]}')
                            
                            def send_message():
                                text = chat_input.value.strip()
                                if not text:
                                    return
                                
                                chat_input.value = ''
                                
                                # 1. Adiciona bolha do usuário
                                user_data = app.storage.user.get('user_data', {})
                                user_name = user_data.get('nome_guerra', 'Operador')
                                user_photo = user_data.get('url_foto')
                                
                                # Bolha de mensagem do Usuário
                                with chat_area:
                                    with ui.row().classes('w-full gap-2 items-start justify-end'):
                                        with ui.column().classes('max-w-[75%] gap-1 items-end'):
                                            ui.label(user_name).classes('text-[10px] text-grey-5 text-weight-bold')
                                            with ui.card().classes('q-pa-sm rounded-lg').style(f'background: {THEME["primary"]}; color: {THEME["bg_app"]}; font-weight: 500;'):
                                                ui.label(text).classes('text-sm text-weight-medium')
                                        if user_photo and isinstance(user_photo, str) and user_photo.startswith('http'):
                                            ui.avatar().style(f"background-image: url('{user_photo}'); background-size: cover; background-position: center; width: 36px; height: 36px;")
                                        else:
                                            ui.avatar(icon='person').style(f'background: {THEME["bg_editor"]}; color: #e2e8f0; width: 36px; height: 36px;')
                                
                                scroll_area.scroll_to(percent=1.0)
                                
                                # Bolha de Resposta (Carregamento / Spinner)
                                with chat_area:
                                    bot_row = ui.row().classes('w-full gap-2 items-start justify-start')
                                    with bot_row:
                                        ui.avatar(icon='psychology').style(f'background: {THEME["primary"]}; color: {THEME["bg_app"]}; width: 36px; height: 36px;')
                                        with ui.column().classes('max-w-[75%] gap-1'):
                                            ui.label('C2-AI').classes('text-[10px] text-grey-5 text-weight-bold')
                                            spinner = ui.spinner(color='cyan', size='md')
                                
                                scroll_area.scroll_to(percent=1.0)
                                
                                # Executa chamada de IA em segundo plano sem travar
                                def fetch_ai_response():
                                    try:
                                        ans = ai_helper.chat_with_ai(text)
                                    except Exception as e:
                                        ans = f"Erro ao contatar o assistente de IA: {e}"
                                    
                                    # Substitui o spinner pela resposta
                                    spinner.delete()
                                    with bot_row:
                                        with ui.card().classes('q-pa-sm rounded-lg border border-gray-800 w-full').style(f'background: {THEME["bg_editor"]}; color: #e2e8f0;'):
                                            ui.markdown(ans).classes('text-sm text-weight-medium w-full')
                                    scroll_area.scroll_to(percent=1.0)
                                
                                ui.timer(0.1, fetch_ai_response, once=True)

                            chat_btn = ui.button(icon='send', on_click=send_message).props('unelevated color=cyan text-color=dark').classes('q-px-sm')
                            chat_input.on('keydown.enter', send_message)

            # ABA 2: PARTES & REGULAMENTOS (OCORRÊNCIAS/SANÇÕES)
            with ui.tab_panel(tab_disciplinar).classes('p-0 gap-4 w-full'):
                with ui.row().classes('w-full gap-4 items-stretch'):
                    
                    # Coluna da Esquerda: Formulário e Histórico
                    with ui.column().classes('col-12 col-md-5 gap-4'):
                        
                        # Card de Seleção e Entrada de Fatos
                        with ui.card().classes('w-full q-pa-md border border-gray-800').style(f'background: {THEME["bg_panel"]}'):
                            ui.label('⚖️ SUBSÍDIO & REDAÇÃO DISCIPLINAR NAVAL').classes('text-xs text-weight-bold text-primary cyber-title border-b border-gray-800 q-pb-sm w-full')
                            
                            # Select de Aluno
                            options_alunos = {a['numero_interno']: f"{a['numero_interno']} - {a['nome_guerra']} ({a['pelotao']})" for a in alunos_list}
                            aluno_select = ui.select(
                                label='Selecionar Aluno Envolvido',
                                options=options_alunos,
                                with_input=True
                            ).classes('w-full').props('dark dense outlined options-dense')
                            
                            # Regulamento Aplicável
                            reg_select = ui.select(
                                label='Regulamento de Referência',
                                options=['RDM (Marinha do Brasil)', 'Regulamento da Escola (Customizado)'],
                                value='RDM (Marinha do Brasil)'
                            ).classes('w-full').props('dark dense outlined options-dense')
                            
                            # Fato Bruto Ocorrido
                            fato_input = ui.textarea(
                                label='Descrição do Fato Bruto',
                                placeholder='Descreva o que aconteceu em linguagem simples...\nExemplo: "O aluno Silva chegou 35 minutos atrasado na formatura do rancho no dia 30/05 às 11:35, alegando que se perdeu na rotina da companhia."'
                            ).classes('w-full').props('dark outlined rows=4')
                            
                            # Botão de Processar
                            generate_btn = ui.button('🚀 Analisar Histórico e Gerar Parte', on_click=lambda: start_generation()).props('unelevated color=cyan text-color=dark w-full bold').classes('q-py-xs font-bold')

                        # Card de Histórico Comportamental Pretérito (FAIA)
                        with ui.card().classes('w-full q-pa-md border border-gray-800 flex-grow').style(f'background: {THEME["bg_panel"]}'):
                            ui.label(' Ficha Comportamental do Aluno (FAIA)').classes('text-xs text-weight-bold text-grey-4 cyber-title border-b border-gray-800 q-pb-sm w-full')
                            
                            aluno_card_area = ui.column().classes('w-full gap-3')
                            
                            with aluno_card_area:
                                ui.label('Selecione um aluno para carregar o histórico disciplinar e atenuantes/agravantes.').classes('text-grey-5 text-caption q-py-md text-center w-full')

                    # Coluna da Direita: Parecer e Redação Final da IA
                    with ui.column().classes('col-12 col-md-7 gap-4'):
                        with ui.card().classes('w-full q-pa-md border border-gray-800 h-full flex flex-col justify-between').style(f'background: {THEME["bg_panel"]}'):
                            
                            # Cabeçalho da Saída
                            with ui.row().classes('w-full justify-between items-center border-b border-gray-800 q-pb-sm'):
                                ui.label('⚓ PARECER E ENQUADRAMENTO C2-AI (RDM)').classes('text-xs text-weight-bold text-primary cyber-title')
                                copy_btn = ui.button('📋 Copiar', on_click=lambda: copy_output_text()).props('flat dense color=cyan text-color=cyan size=sm').classes('hidden')
                            
                            # Corpo do Parecer
                            with ui.scroll_area().classes('w-full flex-grow q-py-md h-[480px]') as output_scroll:
                                output_area = ui.column().classes('w-full')
                                with output_area:
                                    placeholder_lbl = ui.label('Preencha os dados à esquerda e clique em "Analisar Histórico e Gerar Parte" para obter a redação oficial e enquadramento sob o RDM.').classes('text-grey-5 text-sm q-pa-md text-center w-full')
                            
                            output_state = {'text': ''}

                            def copy_output_text():
                                if output_state['text']:
                                    ui.run_javascript(f"navigator.clipboard.writeText({repr(output_state['text'])})")
                                    ui.notify("Parte de Ocorrência copiada para a área de transferência!", color="success")

                            def start_generation():
                                if not aluno_select.value:
                                    ui.notify('Selecione o aluno envolvido!', color='warning')
                                    return
                                if not fato_input.value or not fato_input.value.strip():
                                    ui.notify('Descreva o fato ocorrido!', color='warning')
                                    return
                                
                                placeholder_lbl.delete()
                                
                                # Limpa área de saída e mostra spinner
                                output_area.clear()
                                with output_area:
                                    with ui.column().classes('w-full items-center justify-center gap-2 q-py-xl'):
                                        ui.spinner(color='cyan', size='lg')
                                        ui.label('Consultando histórico, aplicando regulamento RDM e redigindo peça naval...').classes('text-cyan text-xs font-bold tracking-widest cyber-title')
                                
                                # Busca o aluno selecionado no array carregado
                                num_int = aluno_select.value
                                aluno_row = next((a for a in alunos_list if a['numero_interno'] == num_int), None)
                                if not aluno_row:
                                    ui.notify('Aluno inválido!', color='danger')
                                    return
                                
                                # Monta o Nome Completo e dados para o Prompt
                                student_name_full = f"{aluno_row['numero_interno']} - {aluno_row['nome_guerra']} ({aluno_row['pelotao']}) • Nome Completo: {aluno_row['nome_completo']}"
                                
                                # Executa em background a busca disciplinar e chamada de IA
                                def run_disciplinary_ai():
                                    # 1. Carrega histórico de Ações do Aluno
                                    nonlocal db_conn
                                    df_student_acoes = pd.DataFrame()
                                    
                                    df_acoes = load_data("Acoes", db_conn=db_conn)
                                    if not df_acoes.empty:
                                        df_student_acoes = df_acoes[df_acoes['aluno_id'] == aluno_row['id']]
                                        
                                        if not df_student_acoes.empty and not df_tipos.empty:
                                            df_student_acoes = pd.merge(
                                                df_student_acoes, 
                                                df_tipos[['id', 'nome', 'pontuacao']], 
                                                left_on='tipo_acao_id', 
                                                right_on='id', 
                                                how='left', 
                                                suffixes=('', '_tipo')
                                            )
                                    
                                    # Constrói o texto do histórico disciplinar
                                    history_lines = []
                                    if not df_student_acoes.empty:
                                        for _, row in df_student_acoes.sort_values(by='data').iterrows():
                                            data_str = pd.to_datetime(row['data']).strftime('%d/%m/%Y')
                                            tipo_lbl = row.get('nome', row.get('tipo', 'OCORRÊNCIA'))
                                            pontos = row.get('pontuacao', 0.0)
                                            desc = row.get('descricao', '')
                                            history_lines.append(f"- [{data_str}] {tipo_lbl} ({pontos:+.1f} pts): {desc}")
                                        history_text = "\n".join(history_lines)
                                    else:
                                        history_text = "Nenhuma ocorrência anterior registrada no sistema. Bons antecedentes (comportamento exemplar)."
                                    
                                    # Anonimização (LGPD) para proteção de PII enviada a serviços de terceiros
                                    real_name = str(aluno_row.get('nome_completo') or '')
                                    real_guerra = str(aluno_row.get('nome_guerra') or '')
                                    real_ni = str(aluno_row.get('numero_interno') or '')
                                    real_pelotao = str(aluno_row.get('pelotao') or '')
                                    real_nip = str(aluno_row.get('nip') or '')
                                    
                                    anon_name_full = "[ALUNO_NI] - [ALUNO_GUERRA] ([ALUNO_PELOTAO]) • Nome Completo: [ALUNO_NOME]"
                                    
                                    anon_history_text = history_text
                                    if real_name:
                                        anon_history_text = anon_history_text.replace(real_name, "[ALUNO_NOME]")
                                    if real_guerra:
                                        anon_history_text = anon_history_text.replace(real_guerra, "[ALUNO_GUERRA]")
                                    if real_ni:
                                        anon_history_text = anon_history_text.replace(real_ni, "[ALUNO_NI]")
                                    if real_nip:
                                        anon_history_text = anon_history_text.replace(real_nip, "[ALUNO_NIP]")
                                        
                                    anon_fact = fato_input.value.strip()
                                    if real_name:
                                        anon_fact = anon_fact.replace(real_name, "[ALUNO_NOME]")
                                    if real_guerra:
                                        anon_fact = anon_fact.replace(real_guerra, "[ALUNO_GUERRA]")
                                    if real_ni:
                                        anon_fact = anon_fact.replace(real_ni, "[ALUNO_NI]")
                                    if real_nip:
                                        anon_fact = anon_fact.replace(real_nip, "[ALUNO_NIP]")
                                    
                                    # Chamada de IA com dados anonimizados
                                    try:
                                        report_output = ai_helper.generate_disciplinary_report(
                                            student_name=anon_name_full,
                                            student_history=anon_history_text,
                                            new_fact=anon_fact,
                                            regulation='RDM' if 'RDM' in reg_select.value else reg_select.value
                                        )
                                        
                                        # Restaura os dados reais localmente na interface
                                        if real_name:
                                            report_output = report_output.replace("[ALUNO_NOME]", real_name).replace("[aluno_nome]", real_name)
                                        if real_guerra:
                                            report_output = report_output.replace("[ALUNO_GUERRA]", real_guerra).replace("[aluno_guerra]", real_guerra)
                                        if real_ni:
                                            report_output = report_output.replace("[ALUNO_NI]", real_ni).replace("[aluno_ni]", real_ni)
                                        if real_pelotao:
                                            report_output = report_output.replace("[ALUNO_PELOTAO]", real_pelotao).replace("[aluno_pelotao]", real_pelotao)
                                        if real_nip:
                                            report_output = report_output.replace("[ALUNO_NIP]", real_nip).replace("[aluno_nip]", real_nip)
                                    except Exception as e:
                                        report_output = f"Erro na chamada da API de IA: {str(e)}"
                                    
                                    # Exibe na tela
                                    output_area.clear()
                                    output_state['text'] = report_output
                                    copy_btn.classes(remove='hidden')
                                    with output_area:
                                        ui.markdown(report_output).classes('text-sm text-white w-full q-pa-sm')
                                    output_scroll.scroll_to(percent=0.0)

                                ui.timer(0.1, run_disciplinary_ai, once=True)

                            # Reatividade na seleção do Aluno para atualizar o Card de Histórico à esquerda
                            def on_aluno_changed(e):
                                num_int = e.value
                                aluno_row = next((a for a in alunos_list if a['numero_interno'] == num_int), None)
                                if not aluno_row:
                                    return
                                
                                # Atualiza área de informações e ficha
                                aluno_card_area.clear()
                                with aluno_card_area:
                                    with ui.row().classes('w-full items-center gap-3 q-pb-sm border-b border-gray-800/50'):
                                        # Foto do Aluno
                                        photo_url = aluno_row.get('url_foto')
                                        if not photo_url or not isinstance(photo_url, str) or pd.isna(photo_url) or not photo_url.strip():
                                            ano_let_val = aluno_row.get('ano_letivo', '2026')
                                            photo_url = f"https://res.cloudinary.com/comcia/image/upload/alunos_app/{aluno_row['numero_interno']}.jpg" if ano_let_val == '2025' else OFFLINE_AVATAR
                                        
                                        ui.avatar().style(
                                            f"background-image: url('{photo_url}'), url('https://cdn.quasar.dev/img/boy-avatar.png'); "
                                            f"background-size: cover; background-position: center; "
                                            f"width: 50px; height: 50px; border: 1px solid rgba(0, 229, 255, 0.3);"
                                        )
                                        with ui.column().classes('gap-0'):
                                            ui.label(f"{aluno_row['numero_interno']} - {aluno_row['nome_guerra']}").classes('text-sm text-weight-bold text-white')
                                            ui.label(aluno_row['nome_completo']).classes('text-[10px] text-grey-5')
                                            ui.label(f"Pelotão: {aluno_row['pelotao']} • NIP: {aluno_row.get('nip', 'N/A')}").classes('text-[9px] text-grey-5')
                                    
                                    # Carrega os lançamentos do Aluno
                                    df_student_acoes = pd.DataFrame()
                                    
                                    df_acoes = load_data("Acoes", db_conn=db_conn)
                                    if not df_acoes.empty:
                                        df_student_acoes = df_acoes[df_acoes['aluno_id'] == aluno_row['id']]
                                        if not df_student_acoes.empty and not df_tipos.empty:
                                            df_student_acoes = pd.merge(
                                                df_student_acoes, 
                                                df_tipos[['id', 'nome', 'pontuacao']], 
                                                left_on='tipo_acao_id', 
                                                right_on='id', 
                                                how='left', 
                                                suffixes=('', '_tipo')
                                            )
                                    
                                    if df_student_acoes.empty:
                                        ui.label('Nenhum registro anterior na Ficha Individual (Bons antecedentes).').classes('text-grey-5 text-xs text-italic q-py-sm text-center w-full')
                                    else:
                                        # Lista de Ações do Aluno
                                        with ui.scroll_area().classes('w-full h-[220px]') as hist_scroll:
                                            with ui.column().classes('w-full gap-2 q-pr-sm'):
                                                for _, row in df_student_acoes.sort_values(by='data', ascending=False).iterrows():
                                                    data_str = pd.to_datetime(row['data']).strftime('%d/%m/%Y')
                                                    tipo_lbl = row.get('nome', row.get('tipo', 'OCORRÊNCIA'))
                                                    pontos = row.get('pontuacao', 0.0)
                                                    pts_color = 'text-green' if pontos > 0 else ('text-red' if pontos < 0 else 'text-grey')
                                                    pts_sign = '+' if pontos > 0 else ''
                                                    
                                                    with ui.card().classes('w-full q-pa-sm border border-gray-800/80 rounded-md').style(f'background: {THEME["bg_app"]}'):
                                                        with ui.row().classes('w-full justify-between items-center gap-1'):
                                                            ui.label(f"{data_str} • {tipo_lbl}").classes('text-[10px] text-weight-bold text-grey-3')
                                                            ui.label(f"{pts_sign}{pontos:.1f} pts").classes(f'text-[9px] font-bold {pts_color}')
                                                        ui.label(row.get('descricao', '')).classes('text-[9px] text-grey-5 text-weight-medium text-justify q-mt-xs')

                            aluno_select.on('value-change', on_aluno_changed)

            # ABA 3: REDATOR & POLIDOR MILITAR
            with ui.tab_panel(tab_redator).classes('p-0 gap-4 w-full'):
                with ui.row().classes('w-full gap-4 items-stretch'):
                    
                    # Painel da Esquerda (Entrada)
                    with ui.column().classes('col-12 col-md-6 gap-4'):
                        with ui.card().classes('w-full q-pa-md border border-gray-800').style(f'background: {THEME["bg_panel"]}'):
                            ui.label('📝 POLIMENTO & ADAPTAÇÃO NAVAL').classes('text-xs text-weight-bold text-primary cyber-title border-b border-gray-800 q-pb-sm w-full')
                            
                            redator_style = ui.select(
                                label='Estilo de Destino',
                                options={
                                    'military': 'Redação Naval (Padrão Marinha do Brasil)',
                                    'formal': 'Formal & Profissional',
                                    'simple': 'Simples & Fácil de Entender'
                                },
                                value='military'
                            ).classes('w-full').props('dark dense outlined options-dense')
                            
                            redator_input = ui.textarea(
                                label='Texto Rascunhado (Entrada)',
                                placeholder='Cole o rascunho de texto que você deseja que a IA policie e adapte para os padrões da Marinha...'
                            ).classes('w-full').props('dark outlined rows=12')
                            
                            redator_btn = ui.button('✨ Adaptar Estilo do Texto', on_click=lambda: adapt_text_style()).props('unelevated color=cyan text-color=dark w-full bold').classes('q-py-xs font-bold')

                    # Painel da Direita (Saída)
                    with ui.column().classes('col-12 col-md-6 gap-4'):
                        with ui.card().classes('w-full q-pa-md border border-gray-800 h-full flex flex-col justify-between').style(f'background: {THEME["bg_panel"]}'):
                            
                            with ui.row().classes('w-full justify-between items-center border-b border-gray-800 q-pb-sm'):
                                ui.label('✨ TEXTO ADAPTADO C2-AI').classes('text-xs text-weight-bold text-primary cyber-title')
                                redator_copy_btn = ui.button('📋 Copiar', on_click=lambda: copy_redator_text()).props('flat dense color=cyan text-color=cyan size=sm').classes('hidden')
                            
                            with ui.scroll_area().classes('w-full flex-grow q-py-md h-[400px]') as redator_scroll:
                                redator_output_area = ui.column().classes('w-full')
                                with redator_output_area:
                                    redator_placeholder = ui.label('Digite ou cole um rascunho de texto no painel à esquerda e clique em "Adaptar Estilo do Texto".').classes('text-grey-5 text-sm q-pa-md text-center w-full')
                            
                            redator_state = {'text': ''}

                            def copy_redator_text():
                                if redator_state['text']:
                                    ui.run_javascript(f"navigator.clipboard.writeText({repr(redator_state['text'])})")
                                    ui.notify("Texto adaptado copiado para a área de transferência!", color="success")

                            def adapt_text_style():
                                if not redator_input.value or not redator_input.value.strip():
                                    ui.notify('Insira o rascunho de texto para adaptar!', color='warning')
                                    return
                                
                                redator_placeholder.delete()
                                
                                # Limpa e coloca spinner
                                redator_output_area.clear()
                                with redator_output_area:
                                    with ui.column().classes('w-full items-center justify-center gap-2 q-py-xl'):
                                        ui.spinner(color='cyan', size='lg')
                                        ui.label('Adaptando tom e melhorando escrita...').classes('text-cyan text-xs font-bold tracking-widest cyber-title')
                                
                                def run_redator_ai():
                                    try:
                                        ans = ai_helper.improve_text(
                                            text=redator_input.value.strip(),
                                            style=redator_style.value
                                        )
                                    except Exception as e:
                                        ans = f"Erro na chamada da API de IA: {str(e)}"
                                    
                                    redator_output_area.clear()
                                    redator_state['text'] = ans
                                    redator_copy_btn.classes(remove='hidden')
                                    with redator_output_area:
                                        ui.markdown(ans).classes('text-sm text-white w-full q-pa-sm')
                                    redator_scroll.scroll_to(percent=0.0)

                                ui.timer(0.1, run_redator_ai, once=True)
