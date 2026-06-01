from nicegui import ui
import theme

def render_page():
    with ui.column().classes('w-full q-pa-lg gap-4'):
        theme.section_header('Geração de Documentos', 'Emissão de Fichas e Relatórios do Curso')
        with ui.card().classes('w-full q-pa-md border border-gray-800').style(f'background: {theme.colors["bg_panel"]}'):
            ui.label('Esta tela do SisCOMCA está em fase de planejamento para a migração completa.').classes('text-grey-4 text-subtitle2')
            ui.label('Módulo para geração automatizada de relatórios em PDF, folhas de ponto, e documentos personalizados.').classes('text-grey-5 text-caption')
