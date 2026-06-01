import streamlit as st
import time
from modules.database import get_connection

def render():
    db = get_connection()
    st.subheader("📋 Sala de Guerra (Kanban)")

    # --- Adicionar Tarefa ---
    with st.expander("➕ Nova Missão / Tarefa", expanded=False):
        with st.form("form_tarefa"):
            c1, c2, c3 = st.columns(3)
            
            titulo = c1.text_input("O que deve ser feito?")
            
            # --- SELEÇÃO MÚLTIPLA ---
            opcoes_resp = ["Equipe (Todos)", "Ten Silva", "Sgt Ana", "Cb Pedro", "Sd João", "Logística", "Mídia"]
            lista_resp = c2.multiselect("Responsável(is)", options=opcoes_resp, default=["Equipe (Todos)"])
            # ------------------------

            prio = c3.selectbox("Prioridade", ["NORMAL", "URGENTE"])
            
            if st.form_submit_button("Lançar Missão 🚀"):
                if titulo:
                    # Junta a lista numa string
                    resp_final = ", ".join(lista_resp)
                    
                    try:
                        db.table("tarefas").insert({
                            "titulo": titulo, 
                            "responsavel": resp_final, 
                            "prioridade": prio, 
                            "status": "A FAZER"
                        }).execute()
                        st.success(f"Tarefa lançada para: {resp_final}")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

    # --- Kanban (Leitura) ---
    try:
        res = db.table("tarefas").select("*").execute()
        tarefas = res.data
    except:
        tarefas = []

    col1, col2, col3 = st.columns(3)

    # Coluna 1: A FAZER
    with col1:
        st.markdown("### 🟥 A FAZER")
        for t in tasks_by_status(tarefas, 'A FAZER'):
            cor = "🚨" if t.get('prioridade') == 'URGENTE' else "⬜"
            with st.container(border=True):
                st.markdown(f"**{cor} {t['titulo']}**")
                # Mostra os múltiplos responsáveis
                st.caption(f"👤 {t.get('responsavel', 'Indefinido')}")
                
                if st.button("Assumir ➤", key=f"do_{t['id']}"):
                    update_status(db, t['id'], "FAZENDO")

    # Coluna 2: FAZENDO
    with col2:
        st.markdown("### 🟨 EM ANDAMENTO")
        for t in tasks_by_status(tarefas, 'FAZENDO'):
            with st.container(border=True):
                st.markdown(f"**🔄 {t['titulo']}**")
                st.caption(f"👤 {t.get('responsavel', 'Indefinido')}")
                
                if st.button("Concluir ✅", key=f"done_{t['id']}"):
                    update_status(db, t['id'], "CONCLUIDO")

    # Coluna 3: CONCLUÍDO
    with col3:
        st.markdown("### 🟩 CONCLUÍDO")
        for t in tasks_by_status(tarefas, 'CONCLUIDO'):
            st.success(f"~~{t['titulo']}~~")
            if st.button("🗑️", key=f"del_{t['id']}"):
                db.table("tarefas").delete().eq("id", t['id']).execute()
                st.rerun()

# --- Helpers locais ---
def tasks_by_status(lista, status):
    # Filtra a lista com segurança
    return [t for t in lista if t.get('status') == status]

def update_status(db, id_tarefa, novo_status):
    try:
        db.table("tarefas").update({"status": novo_status}).eq("id", id_tarefa).execute()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")