import streamlit as st
import google.generativeai as genai
from PIL import Image
from modules.database import get_connection

# --- CONFIG IA VISUAL ---
def configurar_ia_visual():
    try:
        genai.configure(api_key=st.secrets["google"]["api_key"])
        # Modelo otimizado para visão
        return genai.GenerativeModel('gemini-1.5-flash')
    except: return None

def render():
    st.markdown("### 📸 MÍDIA & INTELIGÊNCIA VISUAL")
    
    # Navegação Interna
    if 'midia_aba' not in st.session_state: st.session_state.midia_aba = 'triagem'
    def set_aba(aba): st.session_state.midia_aba = aba

    c1, c2, c3 = st.columns(3)
    c1.button("👁️ Triagem IA", use_container_width=True, type="primary" if st.session_state.midia_aba == 'triagem' else "secondary", on_click=set_aba, args=('triagem',))
    c2.button("☁️ Drive & Up", use_container_width=True, type="primary" if st.session_state.midia_aba == 'drive' else "secondary", on_click=set_aba, args=('drive',))
    c3.button("👤 Face ID", use_container_width=True, type="primary" if st.session_state.midia_aba == 'faceid' else "secondary", on_click=set_aba, args=('faceid',))

    st.divider()

    # === ABA 1: TRIAGEM DE FOTOS (IA) ===
    if st.session_state.midia_aba == 'triagem':
        st.caption("📥 ANÁLISE AUTOMÁTICA DE CONTEÚDO")
        model = configurar_ia_visual()
        
        with st.container(border=True):
            uploaded = st.file_uploader("Carregar Fotos da Operação", type=['jpg', 'png', 'jpeg'], accept_multiple_files=False)
            
            if uploaded:
                img = Image.open(uploaded)
                st.image(img, use_column_width=True)
                
                if model:
                    if st.button("🔍 ANALISAR COM GEMINI", type="primary", use_container_width=True):
                        with st.spinner("Identificando uniformes, equipamentos e ambiente..."):
                            prompt = """
                            Você é um especialista em ComSoc da Marinha. Analise esta imagem:
                            1. Descreva a ação ocorrendo.
                            2. Liste uniformes e equipamentos visíveis.
                            3. Sugira 3 hashtags para Instagram.
                            4. Gere uma legenda técnica para arquivamento.
                            """
                            try:
                                resp = model.generate_content([prompt, img])
                                st.subheader("Relatório de Inteligência:")
                                st.markdown(resp.text)
                                st.success("Metadados gerados com sucesso.")
                            except Exception as e:
                                st.error(f"Erro de conexão IA: {e}")
                else:
                    st.warning("⚠️ Chave API do Google não configurada.")

    # === ABA 2: DRIVE & UPLOAD (Placeholder) ===
    elif st.session_state.midia_aba == 'drive':
        st.info("🚧 MÓDULO EM DESENVOLVIMENTO")
        st.markdown("""
        **Funcionalidades Previstas:**
        * 📁 Criação automática de pastas no GDrive (Ex: `2026-01-22_Operacao_Verao`).
        * 📤 Upload em lote sem sair do app.
        * 📧 Envio de link de download com validade para imprensa.
        """)
        
        with st.container(border=True):
            st.text_input("Nome da Pasta (Evento)")
            st.date_input("Data do Evento")
            st.button("Criar Estrutura no Drive (Demo)", disabled=True)

    # === ABA 3: FACE ID (Placeholder) ===
    elif st.session_state.midia_aba == 'faceid':
        st.info("🚧 MÓDULO EM DESENVOLVIMENTO")
        st.markdown("""
        **Funcionalidades Previstas:**
        * 👤 Indexação de rostos de autoridades.
        * 🔍 Busca: "Encontre fotos do Comandante X em Janeiro".
        * 📂 Organização automática por pessoa identificada.
        """)
        
        col_bus, col_upl = st.columns(2)
        with col_bus:
            st.text_input("Buscar Pessoa (Nome)")
            st.button("🔍 Localizar no Banco", disabled=True)
