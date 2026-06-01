from nicegui import ui, app
import pandas as pd
from datetime import datetime
import theme
from database import carregar_oficiais_hoje, salvar_oficial_servico
from services import data_service

THEME = theme.colors

CARGOS_PADRAO = [
    "Oficial de Dia",
    "Oficial de Serviço - Alfa",
    "Oficial de Serviço - Bravo",
    "Oficial de Serviço - Charlie",
    "Oficial de Rondas"
]

def render_page():
    # 1. Carrega dados essenciais
    alunos_df = data_service.get_alunos_data()
    oficiais_df = carregar_oficiais_hoje()

    # UI principal
    with ui.column().classes('w-full q-pa-lg gap-6'):
        theme.section_header('Escalas de Serviço', 'Oficiais e Ajudantes de Serviço Escalados para Hoje')
        
        # Grid layout: Form à esquerda (5/12), Lista à direita (7/12)
        with ui.row().classes('w-full gap-6 items-start wrap lg:no-wrap'):
            
            # Coluna Esquerda: Formulário de Lançamento
            with ui.column().classes('w-full lg:w-5/12 gap-4'):
                ui.label('ESCALAR OFICIAL E AJUDANTE').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                
                with theme.card_base().classes('w-full q-pa-md'):
                    # Tipo/Função de Serviço
                    cargo_sel = ui.select(CARGOS_PADRAO, value='Oficial de Dia', label='Cargo / Função de Serviço').props('dark outlined dense w-full')
                    
                    # Nome do Oficial (pode ser texto ou autocompletado do efetivo)
                    # Fornecemos autocomplete a partir dos alunos/militar para facilitar, mas deixamos input de texto aberto
                    nomes_sugestoes = []
                    if not alunos_df.empty:
                        nomes_sugestoes = sorted(alunos_df['nome_guerra'].dropna().unique().tolist())
                        
                    oficial_input = ui.input('Nome do Oficial de Serviço', 
                                             autocomplete=nomes_sugestoes).props('dark outlined dense w-full')
                    
                    ajudante_input = ui.input('Nome do Ajudante (Opcional)', 
                                              autocomplete=nomes_sugestoes).props('dark outlined dense w-full')

                    def salvar_escala():
                        if not oficial_input.value:
                            ui.notify('Por favor, informe o nome do Oficial', color='warning')
                            return
                            
                        sucesso = salvar_oficial_servico(
                            nome=str(oficial_input.value),
                            cargo=str(cargo_sel.value),
                            ajudante=str(ajudante_input.value) if ajudante_input.value else None
                        )
                        
                        if sucesso:
                            ui.notify(f"Escala de {cargo_sel.value} salva com sucesso!", color='positive')
                            data_service.clear_cache()
                            ui.navigate.reload()
                        else:
                            ui.notify('Falha ao salvar a escala de serviço', color='negative')

                    ui.button('Registrar Oficial de Serviço', icon='assignment_turned_in', on_click=salvar_escala).props('unelevated no-caps w-full').style(f'background: {THEME["primary"]}; color: #0b0f19; font-weight: bold;').classes('cyber-glow q-mt-sm')

            # Coluna Direita: Relação do Plantão de Hoje
            with ui.column().classes('w-full lg:w-7/12 gap-4'):
                ui.label('ESCALA DE SERVIÇO DE HOJE').classes('cyber-title text-xs').style(f'color: {THEME["primary"]}')
                
                if oficiais_df.empty:
                    ui.label('Nenhum Oficial de Serviço escalado para hoje.').classes('italic self-center q-my-lg').style(f'color: {THEME["text_dim"]}')
                else:
                    with ui.column().classes('w-full gap-3'):
                        for _, o in oficiais_df.iterrows():
                            # Se for Oficial de Dia, usa destaque em Gold/Cyan. Se for outros cargos, usa ciano opaco.
                            cor_escala = THEME['primary'] if o['cargo'] == "Oficial de Dia" else THEME['accent']
                            borda_escala = f"border-left: 4px solid {cor_escala}"
                            
                            with theme.card_base().classes('w-full q-pa-md').style(f'{borda_escala};'):
                                with ui.row().classes('w-full items-center justify-between'):
                                    with ui.row().classes('items-center gap-3'):
                                        ui.avatar(icon='shield_person').style(f'background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); color: {THEME["primary"]};')
                                        with ui.column().classes('gap-0.5'):
                                            ui.label(o['cargo'].upper()).style(f'color: {cor_escala}; font-weight: 700; font-size: 0.8rem; letter-spacing: 0.5px;')
                                            ui.label(f"👤 Oficial: {o['nome']}").classes('font-bold text-base').style(f'color: {THEME["text_main"]}')
                                            
                                            ajudante_nome = o.get('ajudante')
                                            if ajudante_nome and pd.notna(ajudante_nome) and ajudante_nome != "None":
                                                ui.label(f"🤝 Ajudante: {ajudante_nome}").classes('text-sm font-semibold').style(f'color: {THEME["text_main"]}')
                                            else:
                                                ui.label("🤝 Sem ajudante designado").classes('text-xs italic').style(f'color: {THEME["text_dim"]}')
                                                
                                    with ui.column().classes('items-end justify-center'):
                                        # Data de plantão
                                        dt_format = datetime.now().strftime('%d/%m/%Y')
                                        if 'data' in o and pd.notna(o['data']):
                                            try:
                                                dt_format = pd.to_datetime(o['data']).strftime('%d/%m/%Y')
                                            except:
                                                dt_format = str(o['data'])
                                        ui.label(dt_format).classes('text-xs font-bold').style(f'color: {THEME["text_dim"]}')
                                        ui.label('EM SERVIÇO').classes('font-bold text-[9px] tracking-wider q-mt-xs').style(f'border: 1px solid {THEME["success"]}; color: {THEME["success"]}; border-radius: 3px; padding: 1px 4px;')
