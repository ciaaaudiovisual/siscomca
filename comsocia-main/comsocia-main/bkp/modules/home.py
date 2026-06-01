import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import get_connection

def render():
    db = get_connection()
    st.header("📅 Agenda e Operações")

    # Busca nomes para o formulário
    res_pessoal = db.table("efetivo").select("nome_guerra").execute()
    lista_nomes = [p['nome_guerra'] for p in res_pessoal.data]

    with st.expander("➕ Agendar Novo Evento", expanded=False):
        with st.form("add_evento"):
            titulo = st.text_input("Título do Evento")
            data_evento = st.date_input("Data")
            hora_evento = st.time_input("Hora")
            responsaveis = st.multiselect("Responsáveis", options=lista_nomes)
            
            if st.form_submit_button("Confirmar Agendamento"):
                # Correção técnica da data para o Supabase
                dt_iso = datetime.combine(data_evento, hora_evento).isoformat()
                db.table("agenda").insert({
                    "evento": titulo, 
                    "data_hora": dt_iso, 
                    "responsavel": ", ".join(responsaveis)
                }).execute()
                st.success("Agendado!")
                st.rerun()

    # Exibição da Agenda
    res_agenda = db.table("agenda").select("*").gte("data_hora", datetime.now().isoformat()).order("data_hora").execute()
    if res_agenda.data:
        df_ag = pd.DataFrame(res_agenda.data)
        st.table(df_ag[['data_hora', 'evento', 'responsavel']])