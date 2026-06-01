import streamlit as st
import threading
import time
from datetime import datetime
from dateutil import parser
import schedule 

# Importa módulos
from modules import dashboard, producao, comunicacao, midia, admin, tv_dashboard
from modules.database import get_connection
from bot_runner import bot

# --- CONFIGURAÇÃO GLOBAL ---
st.set_page_config(
    page_title="ComSoc Command Center", 
    page_icon="⚓", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 🎨 CSS TÁTICO GLOBAL (MOBILE FRIENDLY) ---
st.markdown("""
    <style>
    /* 1. Fonte Militar */
    @import url('https://fonts.googleapis.com/css2?family=Black+Ops+One&display=swap');

    /* 2. Ajuste de Margens (Topo Limpo) */
    .block-container { 
        padding-top: 1rem !important; 
        padding-bottom: 3rem !important; 
        padding-left: 0.5rem !important; 
        padding-right: 0.5rem !important;
    }
    
    /* 3. Limpeza Geral */
    header[data-testid="stHeader"] { display: none; }
    footer { display: none; }
    
    /* 4. Cabeçalho Tático */
    .header-tatica {
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(180deg, #1e1e1e 0%, #0e1117 100%);
        border-bottom: 2px solid #00cc00;
        padding: 10px 0;
        margin-bottom: 15px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
    }
    .titulo-app {
        font-family: 'Black Ops One', cursive;
        color: #e0e0e0;
        font-size: 24px;
        letter-spacing: 2px;
    }
    
    /* 5. BOTÕES GRANDES (GRADE) */
    .stButton button { 
        min-height: 60px !important; /* Altura boa para o dedo */
        width: 100%; 
        font-weight: bold; 
        border-radius: 8px;
        border: 1px solid #333;
        font-size: 14px;
    }
    /* Destaque para o botão ativo */
    .stButton button:focus {
        border-color: #00cc00 !important;
        color: #00cc00 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔒 LOGIN RESPONSIVO ---
if 'logado' not in st.session_state: st.session_state.logado = False

def tela_login():
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("<h2 style='text-align:center; font-family:Black Ops One; color:#00cc00'>ACESSO RESTRITO</h2>", unsafe_allow_html=True)
        senha = st.text_input("Credencial Operacional", type="password", placeholder="Digite a senha...")
        if st.button("🔓 ACESSAR SISTEMA", type="primary", use_container_width=True):
            if senha == "MB2026": 
                st.session_state.logado = True
                st.rerun()
            else: st.error("⛔ Credencial Inválida.")

if not st.session_state.logado:
    tela_login()
    st.stop()

# --- VIGÍLIA (THREADS) ---
@st.cache_resource
def iniciar_operacao_bot():
    def thread_bot():
        try: bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except: pass
    def thread_sched():
        while True:
            schedule.run_pending()
            time.sleep(60)
    threading.Thread(target=thread_bot, daemon=True).start()
    threading.Thread(target=thread_sched, daemon=True).start()

iniciar_operacao_bot()

# --- NAVEGAÇÃO ---
if 'pagina_atual' not in st.session_state: st.session_state.pagina_atual = 'dashboard'

# Status Bot
def check_status():
    db = get_connection()
    try:
        res = db.table("bot_config").select("valor").eq("chave", "bot_heartbeat").execute()
        if res.data:
            last = parser.parse(res.data[0]['valor']).replace(tzinfo=None)
            if (datetime.now() - last).total_seconds()/60 < 3: return "ON"
    except: pass
    return "OFF"

s_bot = check_status()
icon_bot = "🟢" if s_bot == "ON" else "🔴"

# --- ROTEAMENTO ---
if st.session_state.pagina_atual == 'tv_mode':
    tv_dashboard.render()
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔙 SAIR DO MODO TV", use_container_width=True):
        st.session_state.pagina_atual = 'dashboard'
        st.rerun()
else:
    # Cabeçalho
    st.markdown(f"""
        <div class="header-tatica">
            <span class="titulo-app">COMSOC C2</span>
        </div>
    """, unsafe_allow_html=True)

    # =================================================================
    # MENU EM GRADE (GRID) - A SOLUÇÃO "APP ICON"
    # =================================================================
    # Função auxiliar para mudar página
    def ir_para(pag):
        st.session_state.pagina_atual = pag
        st.rerun()

    # Define estilo do botão (Primary se for a página atual, Secondary se não)
    def estilo(p): return "primary" if st.session_state.pagina_atual == p else "secondary"

    # LINHA 1 (3 Botões)
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("📊\nSALA", use_container_width=True, type=estilo('dashboard')): ir_para('dashboard')
    with c2: 
        if st.button("📰\nPRODUÇÃO", use_container_width=True, type=estilo('producao')): ir_para('producao')
    with c3: 
        if st.button("📸\nMÍDIA", use_container_width=True, type=estilo('midia')): ir_para('midia')

    # LINHA 2 (3 Botões)
    c4, c5, c6 = st.columns(3)
    with c4: 
        if st.button("🤖\nBOT", use_container_width=True, type=estilo('comunicacao')): ir_para('comunicacao')
    with c5: 
        if st.button("🏛️\nADMINISTRAÇÃO", use_container_width=True, type=estilo('admin')): ir_para('admin')
    with c6: 
        # Botão TV com status visual
        if st.button(f"📺 {icon_bot}\nMONITOR", use_container_width=True, type="secondary"): ir_para('tv_mode')

    st.divider()

    # Renderiza Módulo Selecionado
    if st.session_state.pagina_atual == 'dashboard': dashboard.render()
    elif st.session_state.pagina_atual == 'producao': producao.render()
    elif st.session_state.pagina_atual == 'midia': midia.render()
    elif st.session_state.pagina_atual == 'comunicacao': comunicacao.render()
    elif st.session_state.pagina_atual == 'admin': admin.render()
