import streamlit as st

# 1. IMPORTAR TODOS OS MÓDULOS
from modules import admin, operacional, producao, sala_guerra, inteligencia, comunicacao, cerimonial, juridico

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="ComSoc Command Center", page_icon="⚓", layout="wide")

# --- CSS ESTRUTURAL ---
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="metric-container"] {
        background-color: #1a1a1a; border: 1px solid #333;
        padding: 10px; border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR (MENU COMPLETO) ---
with st.sidebar:
    st.header("⚓ COMSOC")
    st.caption("Sistema Integrado v2.5 (Full)")
    st.divider()
    
    escolha = st.radio(
        "Navegação",
        [
            "1. 🏠 Home / Agenda", 
            "2. 📋 Sala de Guerra", 
            "3. 🧠 Inteligência (IA)", 
            "4. 📢 Comunicação",
            "5. 🏛️ Cerimonial",     # Novo
            "6. 📦 Logística",      # Novo
            "7. ⚖️ Jurídico (LGPD)", # Novo
            "8. 📚 Wiki / Ajuda",   # Novo
            "9. ⚙️ Configurações"
        ],
        label_visibility="collapsed"
    )
    st.divider()
    st.caption("Desenvolvido por @ciaaaudiovisual")

# --- ROTEADOR (ROUTING) ---
if "1." in escolha:
    operacional.render()
elif "2." in escolha:
    sala_guerra.render()
elif "3." in escolha:
    inteligencia.render()
elif "4." in escolha:
    comunicacao.render()
elif "5." in escolha:
    cerimonial.render()
elif "6." in escolha:
    producao.render()
elif "7." in escolha:
    juridico.render()
elif "8." in escolha:
    admin.render()
elif "9." in escolha:
    st.title("⚙️ Configurações")
    st.info("Aqui ficam as chaves de API e ajustes de usuário.")