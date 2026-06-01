import streamlit as st
import pandas as pd

def render():
    st.subheader("🏛️ Cerimonial & Protocolo")
    
    c1, c2 = st.columns([1, 1.5])
    
    with c1:
        st.markdown("##### 📜 Próximos Eventos")
        # No futuro, isso virá da tabela 'agenda' do Supabase
        st.info("Eventos confirmados no calendário:")
        st.checkbox("20/01 - Passagem de Comando", value=True)
        st.checkbox("25/01 - Entrega de Medalhas")
        st.checkbox("10/02 - Aula Inaugural")
        
        st.divider()
        st.markdown("##### 🎩 Check-list Rápido")
        st.checkbox("Bandeira Nacional (Hasteada)")
        st.checkbox("Púlpito + Microfone (Testado)")
        st.checkbox("Água para Autoridades")
    
    with c2:
        st.markdown("##### 👔 Nominata de Autoridades (Precedência)")
        st.caption("Ordem de composição da mesa diretiva:")
        
        df_auth = pd.DataFrame({
            "Ordem": [1, 2, 3, 4],
            "Cargo": ["Comandante do CIAA", "Prefeito da Cidade", "Imediato", "Capitão dos Portos"],
            "Nome": ["CF Anthony", "Sr. Eduardo", "CC Bruno", "CF Silva"],
            "Tratamento": ["V.Sa.", "V.Exa.", "V.Sa.", "V.Sa."]
        })
        st.dataframe(df_auth, hide_index=True, use_container_width=True)