import streamlit as st
import pandas as pd
from modules.database import get_connection

def render():
    db = get_connection()
    st.subheader("👥 Gestão de Efetivo (Whitelist)")
    
    tab1, tab2 = st.tabs(["📋 Militares Cadastrados", "➕ Pré-Cadastro"])
    
    with tab1:
        try:
            res = db.table("efetivo").select("*").eq("ativo", True).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                # Criar coluna de status visual para o Telegram
                df['Status Bot'] = df['telegram_id'].apply(lambda x: "🟢 Ativo" if x else "🔴 Pendente")
                
                st.dataframe(
                    df[['posto_grad', 'nome_guerra', 'email', 'Status Bot']],
                    column_config={"nome_guerra": "Nome", "email": "E-mail de Validação"},
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Nenhum militar pré-cadastrado.")
        except Exception as e:
            st.error(f"Erro ao carregar lista: {e}")

    with tab2:
        with st.form("form_precadastro"):
            st.write("**Adicionar Militar à Lista de Permissões**")
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome de Guerra").upper()
            posto = c2.selectbox("Posto/Grad", ["CF", "CC", "CT", "1T", "2T", "SO", "1SG", "2SG", "3SG", "CB", "MN"])
            
            email = st.text_input("E-mail Funcional (Chave de Acesso)")
            st.caption("O militar deverá digitar este e-mail no Telegram para validar o acesso.")
            
            if st.form_submit_button("Autorizar Acesso"):
                if nome and email:
                    try:
                        db.table("efetivo").insert({
                            "nome_guerra": nome, "posto_grad": posto, "email": email.lower()
                        }).execute()
                        st.success(f"Acesso autorizado para {nome}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: E-mail já cadastrado ou erro no banco.")