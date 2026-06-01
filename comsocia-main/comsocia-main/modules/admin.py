import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import get_connection

def render():
    st.markdown("### 🏛️ ADM & PESSOAL (G1/G3)")
    
    db = get_connection()
    
    # --- NAVEGAÇÃO SUPERIOR ---
    if 'admin_aba' not in st.session_state: st.session_state.admin_aba = 'sentinela'
    def set_aba(aba): st.session_state.admin_aba = aba

    # 5 Botões (Agora inclui Protocolo)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.button("🛡️\nSentinela", use_container_width=True, type="primary" if st.session_state.admin_aba == 'sentinela' else "secondary", on_click=set_aba, args=('sentinela',))
    with c2: st.button("👥\nEfetivo", use_container_width=True, type="primary" if st.session_state.admin_aba == 'efetivo' else "secondary", on_click=set_aba, args=('efetivo',))
    with c3: st.button("📦\nEstoque", use_container_width=True, type="primary" if st.session_state.admin_aba == 'estoque' else "secondary", on_click=set_aba, args=('estoque',))
    with c4: st.button("🗓️\nDatas", use_container_width=True, type="primary" if st.session_state.admin_aba == 'datas' else "secondary", on_click=set_aba, args=('datas',))
    with c5: st.button("🎩\nProtocolo", use_container_width=True, type="primary" if st.session_state.admin_aba == 'protocolo' else "secondary", on_click=set_aba, args=('protocolo',))

    st.divider()
    
    # =======================================================
    # ABA 1: SENTINELA (APROVAÇÃO)
    # =======================================================
    if st.session_state.admin_aba == 'sentinela':
        st.caption("🛡️ CONTROLE DE FRONTEIRA DIGITAL")
        try:
            pendentes = db.table("efetivo").select("*").eq("status", "PENDENTE").execute().data
            if not pendentes:
                st.info("✅ Fronteira Segura. Sem solicitações.")
            else:
                for u in pendentes:
                    with st.container(border=True):
                        c_avatar, c_info = st.columns([1, 4])
                        with c_avatar: st.markdown("# 👤")
                        with c_info:
                            st.markdown(f"**{u['nome_guerra']}**")
                            st.caption(f"ID: {u['telegram_id']}")
                        
                        b1, b2 = st.columns(2)
                        if b1.button("✅ APROVAR", key=f"ok_{u['id']}", use_container_width=True):
                            db.table("efetivo").update({"status": "ATIVO"}).eq("id", u['id']).execute()
                            st.rerun()
                        if b2.button("🚫 RECUSAR", key=f"no_{u['id']}", type="primary", use_container_width=True):
                            db.table("efetivo").delete().eq("id", u['id']).execute()
                            st.rerun()
        except Exception as e: st.error(f"Erro BD: {e}")

    # =======================================================
    # ABA 2: EFETIVO
    # =======================================================
    elif st.session_state.admin_aba == 'efetivo':
        st.caption("👥 LISTAGEM DE OPERADORES")
        col_search, col_add = st.columns([3, 1])
        termo = col_search.text_input("🔍 Buscar Operador", label_visibility="collapsed")
        
        try:
            query = db.table("efetivo").select("*").eq("status", "ATIVO").order("nome_guerra")
            ativos = query.execute().data
            if termo: ativos = [x for x in ativos if termo.upper() in x['nome_guerra'].upper()]

            for militar in ativos:
                cor_perm = "#ffcc00" if militar['permissao'] == "ADMIN" else "#00cc00"
                with st.container(border=True):
                    c_detalhe, c_badge = st.columns([4, 1])
                    with c_detalhe:
                        st.markdown(f"**{militar['nome_guerra']}**")
                        st.caption(f"Permissão: {militar['permissao']}")
                    with c_badge:
                        st.markdown(f"<div style='text-align:right; color:{cor_perm}; font-size:20px;'>●</div>", unsafe_allow_html=True)
                    
                    with st.expander("🔽 Gerenciar Cadastro"):
                        with st.form(f"edit_{militar['id']}"):
                            nova_perm = st.selectbox("Nível de Acesso", ["USUARIO", "ADMIN", "SUPERVISOR", "VIP"], index=["USUARIO", "ADMIN", "SUPERVISOR", "VIP"].index(militar.get('permissao', 'USUARIO')))
                            if st.form_submit_button("💾 Salvar"):
                                db.table("efetivo").update({"permissao": nova_perm}).eq("id", militar['id']).execute()
                                st.rerun()
                            if st.form_submit_button("🗑️ Excluir", type="primary"):
                                db.table("efetivo").delete().eq("id", militar['id']).execute()
                                st.rerun()
        except: st.warning("Sem dados.")

    # =======================================================
    # ABA 3: ESTOQUE
    # =======================================================
    elif st.session_state.admin_aba == 'estoque':
        st.caption("📦 ALMOXARIFADO G4")
        with st.expander("➕ CADASTRAR MATERIAL"):
            with st.form("novo_brinde"):
                nome = st.text_input("Nome do Item")
                qtd = st.number_input("Qtd Inicial", min_value=1)
                min_q = st.number_input("Alerta Mínimo", min_value=1)
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    db.table("estoque_brindes").insert({"item": nome, "qtd_atual": int(qtd), "qtd_minima": int(min_q)}).execute()
                    st.rerun()

        estoque = db.table("estoque_brindes").select("*").execute().data
        if estoque:
            for item in estoque:
                perc = min(item['qtd_atual'] / 100, 1.0)
                cor_barra = "red" if item['qtd_atual'] <= item['qtd_minima'] else "blue"
                with st.container(border=True):
                    st.markdown(f"**{item['item']}**")
                    st.progress(perc)
                    c_info, c_action = st.columns([2, 1])
                    with c_info: st.caption(f"Em estoque: {item['qtd_atual']} (Mín: {item['qtd_minima']})")
                    with c_action:
                        with st.popover("⚙️ Ajustar"):
                            op = st.radio("Ação", ["Entrada (+)", "Saída (-)"], key=f"rad_{item['id']}")
                            val = st.number_input("Qtd", min_value=1, key=f"num_{item['id']}")
                            if st.button("Confirmar", key=f"btn_{item['id']}"):
                                novo = item['qtd_atual'] + val if op == "Entrada (+)" else item['qtd_atual'] - val
                                db.table("estoque_brindes").update({"qtd_atual": int(novo)}).eq("id", item['id']).execute()
                                st.rerun()

    # =======================================================
    # ABA 4: DATAS
    # =======================================================
    elif st.session_state.admin_aba == 'datas':
        st.caption("🗓️ CALENDÁRIO OM")
        with st.expander("➕ ADICIONAR EVENTO"):
            with st.form("add_date"):
                titulo = st.text_input("Título")
                tipo = st.selectbox("Tipo", ["Eventos", "Feriado", "Aniversario"])
                data = st.date_input("Data")
                if st.form_submit_button("Salvar", use_container_width=True):
                    db.table("datas_comemorativas").insert({"titulo": titulo, "tipo": tipo, "data_evento": data.isoformat()}).execute()
                    st.rerun()

        res = db.table("datas_comemorativas").select("*").order("data_evento").execute().data
        if res:
            for evt in res:
                dt_obj = pd.to_datetime(evt['data_evento'])
                dia = dt_obj.strftime("%d/%m")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 4, 1])
                    c1.markdown(f"### {dia}")
                    c2.markdown(f"**{evt['titulo']}**\n<span style='color:grey'>{evt['tipo']}</span>", unsafe_allow_html=True)
                    with c3:
                        if st.button("🗑️", key=f"del_dt_{evt['id']}"):
                            db.table("datas_comemorativas").delete().eq("id", evt['id']).execute()
                            st.rerun()

    # =======================================================
    # ABA 5: PROTOCOLO (Restabelecido e Adaptado)
    # =======================================================
    elif st.session_state.admin_aba == 'protocolo':
        st.caption("🎩 CERIMONIAL & CROQUI")
        
        # Mapa de Mesa (Precedência)
        with st.container(border=True):
            st.markdown("##### 📍 Precedência (Mesa Ímpar)")
            st.info("Preencha olhando para o público.")
            
            # Layout Visual de Mesa
            c_ext_e, c_esq, c_centro, c_dir, c_ext_d = st.columns(5)
            with c_centro: st.text_input("1. CENTRO", placeholder="Presidência")
            with c_dir: st.text_input("2. DIREITA", placeholder="2ª Maior")
            with c_esq: st.text_input("3. ESQUERDA", placeholder="3ª Maior")
            with c_ext_d: st.text_input("4. EXT. DIR", placeholder="4ª Maior")
            with c_ext_e: st.text_input("5. EXT. ESQ", placeholder="5ª Maior")
        
        # Vade-Mécum Rápido
        with st.container(border=True):
            st.markdown("##### 📜 Vade-Mécum Rápido")
            cargo = st.selectbox("Consulta de Tratamento", ["Almirante de Esquadra", "Vice-Almirante", "Contra-Almirante", "Capitão de Mar e Guerra"])
            
            tratamento = "Vossa Excelência"
            if cargo == "Capitão de Mar e Guerra": tratamento = "Vossa Senhoria"
            
            st.success(f"🗣️ Verbal: **{tratamento}**\n📝 Escrito: **Ilustríssimo/Excelentíssimo Senhor**")
