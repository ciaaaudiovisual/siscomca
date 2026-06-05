from nicegui import ui
import theme

def render_page():
    ui.label('Ajuda / Sobre').classes('text-2xl font-bold text-white cyber-title gt-xs q-mb-md q-ml-md')
    
    with ui.card().classes('w-full max-w-5xl mx-auto q-pa-lg no-shadow rounded-xl').style(
        f'background: {theme.colors["bg_panel"]}; border: {theme.colors["border"]};'
    ):
        # Tabs para Ajuda e Sobre
        with ui.tabs().classes('w-full text-white') as tabs:
            tab_sobre = ui.tab('Sobre o Sistema', icon='info')
            tab_ajuda = ui.tab('Central de Ajuda', icon='help_outline')
            
        with ui.tab_panels(tabs, value=tab_sobre).classes('w-full bg-transparent text-white q-mt-md'):
            # Painel do SOBRE
            with ui.tab_panel(tab_sobre):
                with ui.column().classes('w-full gap-6'):
                    # Cabeçalho com Gradient e Efeito Premium
                    with ui.row().classes('w-full items-center gap-4 q-pa-md rounded-lg').style(
                        'background: linear-gradient(135deg, rgba(212,175,55,0.1) 0%, rgba(0,229,255,0.05) 100%); border: 1px solid rgba(255,255,255,0.05);'
                    ):
                        ui.icon('shield', size='4rem', color='amber-9').classes('drop-shadow-[0_0_12px_rgba(212,175,55,0.3)]')
                        with ui.column().classes('gap-0'):
                            ui.label('SisCOMCA v2.0 (Em Desenvolvimento)').classes('text-xl font-bold text-white tracking-wide')
                            ui.label('Sistema Inteligente de Gestão de Efetivo e Tomada de Decisão').classes('text-grey-4 text-xs')
                            ui.label('Desenvolvido por Sargento Calaça').classes('text-amber-5 text-xs font-bold q-mt-xs')
                    
                    # Descrição do App
                    with ui.column().classes('w-full gap-2 q-px-sm'):
                        ui.label('Sobre o Aplicativo').classes('text-md font-bold text-primary cyber-title')
                        ui.markdown(
                            'O **SisCOMCA** é uma plataforma corporativa e analítica de alta performance projetada para centralizar, '
                            'organizar e otimizar todas as rotinas administrativas e operacionais do Corpo de Alunos. '
                            'Integrando tecnologias modernas de banco de dados em tempo real, inteligência artificial e automação '
                            'via Telegram, o sistema fornece aos supervisores e administradores um panorama tático e instantâneo '
                            'do efetivo pronto, alterações de saúde, escalas de serviço e registros disciplinares.'
                        ).classes('text-grey-3 text-xs leading-relaxed')

                    ui.separator().style('background-color: rgba(255, 255, 255, 0.05);')
                    
                    # Funções Incrementadas da v1.0 para v2.0
                    with ui.column().classes('w-full gap-3 q-px-sm'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('trending_up', color='primary').classes('text-lg')
                            ui.label('Lista de Funções Incrementadas (v1.0 ➔ v2.0)').classes('text-md font-bold text-primary cyber-title')
                        
                        ui.label('Confira o registro completo de evoluções e novos recursos em desenvolvimento na versão 2.0:').classes('text-grey-4 text-xs')
                        
                        # Grid de Funcionalidades
                        with ui.grid(columns=1).classes('w-full gap-4 gt-xs').style('grid-template-columns: repeat(2, 1fr);'):
                            
                            # Card 1: Ano Letivo
                            with ui.card().classes('q-pa-md no-shadow rounded-lg').style('background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);'):
                                with ui.row().classes('items-center gap-2 q-mb-xs'):
                                    ui.icon('calendar_today', color='amber-9').classes('text-md')
                                    ui.label('Segregação por Ano Letivo').classes('text-xs font-bold text-white')
                                ui.markdown(
                                    '- **Seletor Global Reativo**: Implementado dropdown no cabeçalho do app para alternar instantaneamente entre os anos letivos.\n'
                                    '- **Segregação de Base**: Alunos, histórico de ações, chamada e dados do painel filtrados rigidamente pelo ano letivo ativo.\n'
                                    '- **Compatibilidade 2025/2026**: Cadastro inicial mantido para 2025 e nova base com padrão configurado para 2026.'
                                ).classes('text-grey-4 text-[11px] leading-relaxed')
                                
                            # Card 2: Automação Telegram
                            with ui.card().classes('q-pa-md no-shadow rounded-lg').style('background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);'):
                                with ui.row().classes('items-center gap-2 q-mb-xs'):
                                    ui.icon('smart_toy', color='amber-9').classes('text-md')
                                    ui.label('Telegram Bot 2.0').classes('text-xs font-bold text-white')
                                ui.markdown(
                                    '- **Prompt de Ano Letivo**: Validação do ano letivo do operador no início da interação com seleção via botões do chat.\n'
                                    '- **Pernoites Múltiplos**: Suporte ao lançamento em massa inserindo múltiplos números internos separados por vírgula.\n'
                                    '- **Manual `/ajuda`**: Novo menu interativo descrevendo comandos, perfis permitidos e ações disponíveis.'
                                ).classes('text-grey-4 text-[11px] leading-relaxed')

                            # Card 3: Dashboard e Modo TV
                            with ui.card().classes('q-pa-md no-shadow rounded-lg').style('background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);'):
                                with ui.row().classes('items-center gap-2 q-mb-xs'):
                                    ui.icon('tv', color='amber-9').classes('text-md')
                                    ui.label('Dashboard & Modo TV').classes('text-xs font-bold text-white')
                                ui.markdown(
                                    '- **Segregação de KPIs**: Dashboard e Modo TV atualizados para calcular estatísticas e alertas apenas com os alunos do ano selecionado.\n'
                                    '- **Filtro Supabase no Modo TV**: Conexão otimizada que reflete de forma autônoma o ano configurado na sessão do navegador.'
                                ).classes('text-grey-4 text-[11px] leading-relaxed')

                            # Card 4: Infraestrutura & Desempenho
                            with ui.card().classes('q-pa-md no-shadow rounded-lg').style('background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);'):
                                with ui.row().classes('items-center gap-2 q-mb-xs'):
                                    ui.icon('memory', color='amber-9').classes('text-md')
                                    ui.label('Otimização de RAM e Conexão').classes('text-xs font-bold text-white')
                                ui.markdown(
                                    '- **Memory Cleanup Loop**: Rotina interna concorrente que executa garbage collection periódica mantendo o consumo de memória estável abaixo de 400MB.\n'
                                    '- **Monkeypatch IPv4**: Ajuste a nível de infraestrutura para acelerar o fetch de requisições Supabase e eliminar timeouts de rede.'
                                ).classes('text-grey-4 text-[11px] leading-relaxed')

            # Painel do AJUDA
            with ui.tab_panel(tab_ajuda):
                with ui.column().classes('w-full items-center justify-center q-pa-xl gap-4 text-center'):
                    ui.icon('help_outline', size='4rem', color='grey-6')
                    ui.label('Central de Ajuda & Tutoriais').classes('text-lg font-bold text-white')
                    ui.label('Esta seção está sendo preparada e no momento não inclui documentações externas. Volte em breve para consultar tutoriais, manuais e guias passo a passo de utilização do SisCOMCA!').classes('text-grey-4 text-xs max-w-md leading-relaxed')
