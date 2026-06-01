import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date, time
import telebot
from modules.database import get_connection

# --- FUNÇÕES AUXILIARES ---

def combinar_data_hora(data_obj, hora_obj):
    """Funde Data (Calendário) e Hora (Relógio) em ISO para o Banco"""
    try:
        dt_combinada = datetime.combine(data_obj, hora_obj)
        return dt_combinada.isoformat()
    except: return None

def extrair_data_hora(iso_str):
    """Separa ISO do banco em objetos Date e Time para os seletores"""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z',''))
        if dt.tzinfo: dt = dt.replace(tzinfo=None)
        return dt.date(), dt.time()
    except:
        return datetime.now().date(), datetime.now().time()

def formatar_br(iso_str):
    """Apenas para exibição visual (Texto)"""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z',''))
        if dt.tzinfo: dt = dt.replace(tzinfo=None)
        return dt.strftime('%d/%m/%Y às %H:%M')
    except: return iso_str

def notificar_conclusao(tipo, titulo, responsaveis):
    try:
        db = get_connection()
        token = st.secrets["telegram"]["token"]
        bot = telebot.TeleBot(token)
        destinatarios = db.table("efetivo").select("telegram_id").in_("permissao", ["ADMIN", "SUPERVISOR"]).eq("status", "ATIVO").execute().data
        msg = f"✅ **MISSÃO CUMPRIDA ({tipo})**\n📌 **{titulo}**\n👮 {responsaveis}\n📅 {datetime.now().strftime('%d/%m %H:%M')}"
        for d in destinatarios:
            try: bot.send_message(d['telegram_id'], msg, parse_mode="Markdown")
            except: pass
    except: pass

def render():
    st.title("📊 Dashboard Operacional")
    
    db = get_connection()
    
    # --- 1. TOOLBAR UNIFICADA (HUD + FILTROS) ---
    # Container único para economizar espaço
    with st.container(border=True):
        # Linha 1: Métricas Principais (Compactas)
        k1, k2, k3, k4 = st.columns([1.5, 1.5, 1.5, 2])
        
        # Buscas Iniciais para Métricas
        pendencias = db.table("agenda").select("*").eq("status", "PENDENTE").execute().data
        tarefas_ativas = db.table("tarefas").select("*").eq("status", "FAZENDO").execute().data
        
        # Filtro de Período (Lógica Prévia)
        periodo_selecao = ["Hoje", "Próx. 7 Dias", "Mês Atual", "Todos"]
        
        # Linha 2: Filtros de Ação
        c_search, c_filter, c_view = st.columns([3, 2, 2])
        search_term = c_search.text_input("🔎", placeholder="Buscar...", label_visibility="collapsed")
        periodo = c_filter.selectbox("📅", periodo_selecao, label_visibility="collapsed")
        modo_view = c_view.radio("👁️", ["Detalhado", "Compacto"], horizontal=True, label_visibility="collapsed")
        
        # Lógica de Dados da Agenda baseada no Filtro
        hoje_iso = datetime.now().strftime('%Y-%m-%d')
        query = db.table("agenda").select("*").eq("status", "CONFIRMADO").order("data_hora")
        
        if periodo == "Hoje":
            query = query.gte("data_hora", f"{hoje_iso}T00:00:00").lte("data_hora", f"{hoje_iso}T23:59:59")
        elif periodo == "Próx. 7 Dias":
            sem_iso = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            query = query.gte("data_hora", hoje_iso).lte("data_hora", sem_iso)
        elif periodo == "Mês Atual":
            query = query.gte("data_hora", f"{datetime.now().year}-{datetime.now().month:02d}-01")
            
        agenda_dados = query.execute().data

        # Filtro Textual Global
        if search_term:
            t = search_term.lower()
            pendencias = [x for x in pendencias if t in x['evento'].lower()]
            agenda_dados = [x for x in agenda_dados if t in x['evento'].lower()]
            tarefas_ativas = [x for x in tarefas_ativas if t in x['titulo'].lower()]

        # Renderiza Métricas na Linha 1 (Agora que temos os dados)
        k1.metric("🔔 Pendentes", len(pendencias), delta="Aprovar" if pendencias else None, delta_color="inverse")
        k2.metric("📅 Agenda", len(agenda_dados))
        k3.metric("⚡ Tarefas", len(tarefas_ativas))
        
        with k4:
            if st.button("➕ Nova Missão", type="primary", use_container_width=True):
                st.session_state['modal_missao'] = not st.session_state.get('modal_missao', False)

    # --- MODAL NOVA DEMANDA (COM CALENDÁRIO) ---
    if st.session_state.get('modal_missao', False):
        with st.container(border=True):
            st.markdown("##### 📝 Nova Demanda")
            with st.form("form_missao"):
                c_evt, c_date, c_time = st.columns([3, 1.5, 1])
                evt = c_evt.text_input("Título")
                
                # SELETORES VISUAIS
                d_input = c_date.date_input("Dia", value=datetime.now())
                t_input = c_time.time_input("Hora", value=time(9, 0)) # Padrão 09:00
                
                try:
                    militares = [m['nome_guerra'] for m in db.table("efetivo").select("nome_guerra").eq("status", "ATIVO").execute().data]
                except: militares = []
                
                resp = st.multiselect("Responsáveis", militares)
                
                if st.form_submit_button("🚀 Lançar"):
                    data_final = combinar_data_hora(d_input, t_input)
                    resp_str = ", ".join(resp) if resp else "Aguardando Escala"
                    
                    db.table("agenda").insert({
                        "evento": evt, "data_hora": data_final, 
                        "responsavel": resp_str, "status": "CONFIRMADO", "tipo": "Manual"
                    }).execute()
                    st.toast("Salvo!")
                    st.session_state['modal_missao'] = False
                    st.rerun()

    # --- 2. PAINEL PRINCIPAL ---
    col_aprov, col_agenda, col_tarefas = st.columns(3)
    
    try:
        mils_db = db.table("efetivo").select("nome_guerra").eq("status", "ATIVO").execute().data
        mils_names = [m['nome_guerra'] for m in mils_db]
    except: mils_names = []

    # === COLUNA 1: APROVAÇÕES ===
    with col_aprov:
        st.subheader("🚨 Aprovações")
        if not pendencias: st.info("✅ Limpo")
        else:
            for p in pendencias:
                dt_str = formatar_br(p['data_hora'])
                with st.container(border=True):
                    st.markdown(f"**{p['evento']}**")
                    st.caption(f"📅 {dt_str} | ID: {p.get('solicitante_id')}")
                    
                    with st.expander("Decidir"):
                        esc = st.multiselect("Escalar:", mils_names, key=f"s_{p['id']}")
                        obs = st.text_input("Obs:", key=f"o_{p['id']}")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Sim", key=f"ok_{p['id']}", use_container_width=True):
                            r = ", ".join(esc) if esc else "A Definir"
                            db.table("agenda").update({"status": "CONFIRMADO", "responsavel": r}).eq("id", p['id']).execute()
                            st.rerun()
                        if c2.button("🚫 Não", key=f"no_{p['id']}", use_container_width=True):
                            db.table("agenda").update({"status": "RECUSADO"}).eq("id", p['id']).execute()
                            st.rerun()

    # === COLUNA 2: AGENDA (COM CALENDÁRIO NA EDIÇÃO) ===
    with col_agenda:
        st.subheader("📅 Agenda")
        
        # Botão Relatório (Compacto no Header da Coluna)
        if agenda_dados:
            txt_rep = f"PAUTA - {datetime.now().strftime('%d/%m')}\n\n" + "\n".join([f"[{formatar_br(i['data_hora'])}] {i['evento']} ({i.get('responsavel')})" for i in agenda_dados])
            st.download_button("📄 Baixar Pauta", txt_rep, file_name="pauta.txt", use_container_width=True)

        if not agenda_dados: st.info("Vazio.")
        else:
            for item in agenda_dados:
                dt_str = formatar_br(item['data_hora'])
                dt_obj, _ = extrair_data_hora(item['data_hora']) # Pega só date para comparar urgência
                
                # Urgência
                atrasado = datetime.combine(dt_obj, time(0,0)) < datetime.now() if isinstance(dt_obj, date) else False
                cor = "#ff4b4b" if atrasado else "#00cc00"
                
                with st.container():
                    # Card
                    if modo_view == "Compacto":
                        st.markdown(f"""<div style="border-left:5px solid {cor}; padding:8px; background:#262730; margin-bottom:5px; border-radius:4px;"><b>{dt_str.split(' ')[2]}</b> {item['evento']}</div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="border-left:5px solid {cor}; padding:10px; background:#262730; border-radius:8px; margin-bottom:10px;">
                            <div><b>{dt_str}</b></div>
                            <div style="font-size:14px;">{item['evento']}</div>
                            <div style="font-size:12px; color:#bbb; margin-top:4px;">👮 {item.get('responsavel', '-')}</div>
                        </div>""", unsafe_allow_html=True)
                    
                    # EDIÇÃO COM CALENDÁRIO
                    with st.expander("✏️ Editar"):
                        with st.form(f"ed_{item['id']}"):
                            # Prepara valores iniciais
                            d_atual, t_atual = extrair_data_hora(item['data_hora'])
                            r_str = item.get('responsavel', '')
                            r_list = [x.strip() for x in r_str.split(',')] if r_str else []
                            defs = [x for x in r_list if x in mils_names]
                            
                            # Inputs
                            n_resp = st.multiselect("Equipe", mils_names, default=defs)
                            
                            c_d, c_t = st.columns(2)
                            n_date = c_d.date_input("Dia", value=d_atual)
                            n_time = c_t.time_input("Hora", value=t_atual)
                            
                            n_stt = st.selectbox("Status", ["CONFIRMADO", "CONCLUIDO", "CANCELADO"])
                            link = st.text_input("Link Fotos")
                            
                            if st.form_submit_button("Salvar"):
                                iso_new = combinar_data_hora(n_date, n_time)
                                rf = ", ".join(n_resp)
                                db.table("agenda").update({"responsavel": rf, "status": n_stt, "data_hora": iso_new}).eq("id", item['id']).execute()
                                if n_stt == "CONCLUIDO": notificar_conclusao("Missão", item['evento'], rf)
                                st.rerun()

    # === COLUNA 3: TAREFAS ===
    with col_tarefas:
        st.subheader("📋 Tarefas")
        with st.expander("⚡ Criar Rápido"):
            with st.form("qt"):
                tn = st.text_input("Tarefa")
                tp = st.selectbox("Prioridade", ["NORMAL", "URGENTE"])
                tr = st.multiselect("Equipe", mils_names)
                if st.form_submit_button("Criar"):
                    db.table("tarefas").insert({"titulo": tn, "status": "FAZENDO", "prioridade": tp, "responsavel": ", ".join(tr)}).execute()
                    st.rerun()
        
        if not tarefas_ativas: st.info("Vazio.")
        else:
            for t in tarefas_ativas:
                cp = "#ff4b4b" if t.get('prioridade') == "URGENTE" else "#3366ff"
                with st.container():
                    st.markdown(f"""<div style="border-left:5px solid {cp}; padding:10px; background:#262730; border-radius:5px; margin-bottom:10px;"><b>{t['titulo']}</b><br><span style="font-size:12px; color:#bbb;">{t.get('responsavel','-')}</span></div>""", unsafe_allow_html=True)
                    with st.expander("Ações"):
                        if st.button("Concluir", key=f"dn_{t['id']}", use_container_width=True):
                            db.table("tarefas").update({"status": "CONCLUIDO"}).eq("id", t['id']).execute()
                            notificar_conclusao("Tarefa", t['titulo'], t.get('responsavel','-'))
                            st.rerun()
                        if st.button("Excluir", key=f"dl_{t['id']}", use_container_width=True):
                            db.table("tarefas").delete().eq("id", t['id']).execute()
                            st.rerun()
