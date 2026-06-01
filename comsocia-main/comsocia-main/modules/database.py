import streamlit as st
from supabase import create_client, Client

# Cache para não reconectar a cada clique, deixando o app rápido
@st.cache_resource
def get_connection() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error("❌ Erro ao conectar no Supabase. Verifique o arquivo .streamlit/secrets.toml")
        st.stop()