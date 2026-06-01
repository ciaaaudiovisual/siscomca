import streamlit as st

def render():
    st.subheader("⚖️ Jurídico & LGPD")
    st.info("Verificação de Autorização de Uso de Imagem (Banco de Talentos)")
    
    col_search, col_res = st.columns([1, 2])
    
    with col_search:
        st.markdown("**Consultar Aluno**")
        nips = st.text_input("Digite o NIP ou Nome", placeholder="Ex: 12.3456-7")
        btn = st.button("Verificar Autorização")
    
    with col_res:
        st.markdown("**Resultado da Consulta**")
        if btn and nips:
            # Simulação de resposta positiva
            with st.container(border=True):
                st.success("✅ AUTORIZAÇÃO VIGENTE")
                st.json({
                    "Aluno": "Fulano de Tal",
                    "Assinatura do Termo": "20/01/2026",
                    "Restrições": "Nenhuma (Pode usar em Redes Sociais)",
                    "Validade": "Término do Curso (Dez/2026)"
                })
        elif btn:
            st.error("Digite um nome para buscar.")
        else:
            st.caption("Aguardando busca...")