import streamlit as st

def render():
    st.subheader("📚 Wiki & Base de Conhecimento")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("##### ❓ Perguntas Frequentes (FAQ)")
        with st.expander("Como catalogar fotos com a IA?"):
            st.write("""
            1. Insira o cartão de memória no PC da ComSoc.
            2. Vá no menu **Inteligência**.
            3. Copie o caminho da pasta e cole no campo indicado.
            4. Clique em 'Ler Cartão'.
            """)
            
        with st.expander("Qual a senha do Wi-Fi da Câmera?"):
            st.code("SSID: Sony_Transfer_CIAA\nSENHA: comsoc_padrao")
            
        with st.expander("Procedimento em caso de Acidente"):
            st.warning("1. Não postar nada. 2. Avisar o Oficial de Dia. 3. Aguardar Nota Oficial.")

    with col2:
        st.markdown("##### 📂 Modelos e Arquivos")
        st.button("📄 Nota à Imprensa (.docx)")
        st.button("📄 Termo de Imagem (.pdf)")
        st.button("🖼️ Logo CIAA (Vetor .ai)")
        st.button("🖼️ Logo ComSoc (.png)")