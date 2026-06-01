from nicegui import ui
import theme

def render_page():
    with ui.column().classes('w-full q-pa-lg gap-4'):
        theme.section_header('Controle Financeiro', 'Acompanhamento de Pagamentos e Taxas')
        with ui.card().classes('w-full q-pa-md border border-gray-800').style(f'background: {theme.colors["bg_panel"]}'):
            ui.label('Esta tela do SisCOMCA está em fase de planejamento para a migração completa.').classes('text-grey-4 text-subtitle2')
            ui.label('Módulo de controle de taxas, faturas e parcelas mensais de fardamento/material de alunos.').classes('text-grey-5 text-caption')
