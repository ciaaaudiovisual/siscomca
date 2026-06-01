import streamlit as st
import pandas as pd
from datetime import datetime

def render():
    st.subheader("📦 Logística & Material (Cautela)")
    
    # KPIs Rápidos
    k1, k2, k3 = st.columns(3)
    k1.metric("Câmeras Disponíveis", "1/2")
    k2.metric("Cartões de Memória", "4/5")
    k3.metric("Baterias Carregadas", "80%", "4 uni")
    
    st.divider()

    # Tabela de Equipamentos
    st.markdown("##### 📋 Status do Material")
    df_equip = pd.DataFrame([
        {"Item": "Sony A7 IV (Corpo)", "Status": "🔴 Em Uso", "Quem": "Sd Pedro", "Retorno Previsto": "18:00"},
        {"Item": "Lente 24-70mm GM", "Status": "🔴 Em Uso", "Quem": "Sd Pedro", "Retorno Previsto": "18:00"},
        {"Item": "Drone DJI Mini 3", "Status": "🟢 Disponível", "Local": "Armário 02", "Retorno Previsto": "-"},
        {"Item": "Flash Godox V1", "Status": "🟢 Disponível", "Local": "Armário 01", "Retorno Previsto": "-"},
    ])
    
    # Colorir a tabela (Visual)
    st.dataframe(df_equip, use_container_width=True)
    
    # Formulário de Saída
    with st.expander("➕ Registrar Nova Saída (Cautela)"):
        with st.form("cautela_form"):
            c1, c2 = st.columns(2)
            c1.selectbox("Equipamento", ["Sony A7", "Drone", "Microfone", "Tripé"])
            c2.text_input("Militar Responsável (NIP ou Nome)")
            st.text_area("Observações (Ex: Bateria 50%)")
            
            if st.form_submit_button("Confirmar Saída"):
                st.success("Cautela registrada! (Simulação)")