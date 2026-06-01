import streamlit as st
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import telebot
from telebot import types
from modules.database import get_connection
import time

# --- CONFIG GEMINI ---
def configurar_ia():
    try:
        genai.configure(api_key=st.secrets["google"]["api_key"])
        return genai.GenerativeModel('gemini-2.5-flash')
    except: return None

# --- ENVIO TELEGRAM ---
def enviar_para_aprovacao(titulo, texto, id_existente=None):
    db = get_connection()
    token = st.secrets["telegram"]["token"]
    bot = telebot.TeleBot(token)
    
    dados = {
        "titulo_nota": titulo,
        "texto_gerado": texto,
        "status": "PENDENTE",
        "comentarios_chefia": None
    }
    
    if id_existente:
        db.table("fluxo_aprovacao").update(dados).eq("id", id_existente).execute()
        nota_id = id_existente
        prefixo = "🔄 **CORREÇÃO DE MINUTA**"
    else:
        res = db.table("fluxo_aprovacao").insert(dados).execute()
        if not res.data: return False, "Erro BD"
        nota_id = res.data[0]['id']
        prefixo = "🚨 **NOVA MINUTA PARA APROVAÇÃO**"
    
    admins = db.table("efetivo").select("telegram_id").in_("permissao", ["ADMIN", "SUPERVISOR"]).eq("status", "ATIVO").execute().data
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ APROVAR", callback_data=f"aprov_nota_{nota_id}"),
               types.InlineKeyboardButton("🚫 REPROVAR", callback_data=f"reprov_nota_{nota_id}"))
    
    enviados = 0
    for adm in admins:
        try:
            bot.send_message(adm['telegram_id'], f"{prefixo}\n📌 **{titulo}**\n\n👇 Texto Sugerido:", parse_mode="Markdown")
            bot.send_message(adm['telegram_id'], f"```\n{texto[:3500]}\n```", reply_markup=markup, parse_mode="Markdown")
            enviados += 1
        except: pass
    return True, f"Enviado para {enviados} decisores."

def render():
    st.markdown("### 📰 PRODUÇÃO & REDAÇÃO")
    db = get_connection()
    
    if 'prod_aba' not in st.session_state: st.session_state.prod_aba = 'redator'
    def set_aba(aba): st.session_state.prod_aba = aba

    # Menu Tático
    c1, c2, c3 = st.columns(3)
    c1.button("✍️ Redator IA", use_container_width=True, type="primary" if st.session_state.prod_aba == 'redator' else "secondary", on_click=set_aba, args=('redator',))
    c2.button("🧠 Aprendizado IA", use_container_width=True, type="primary" if st.session_state.prod_aba == 'aprendizado' else "secondary", on_click=set_aba, args=('aprendizado',))
    c3.button("🚦 Status & Arq.", use_container_width=True, type="primary" if st.session_state.prod_aba == 'status' else "secondary", on_click=set_aba, args=('status',))

    st.divider()

    # === ABA 1: REDATOR ===
    if st.session_state.prod_aba == 'redator':
        modo_edicao = 'id_nota_edicao' in st.session_state
        if modo_edicao:
            st.warning(f"✏️ EDITANDO NOTA ID: {st.session_state['id_nota_edicao']}")
            if st.button("❌ Cancelar Edição"):
                del st.session_state['id_nota_edicao']
                if 'texto_temp' in st.session_state: del st.session_state['texto_temp']
                if 'titulo_temp' in st.session_state: del st.session_state['titulo_temp']
                st.rerun()

        with st.container(border=True):
            evento = st.text_input("Título / Evento", value=st.session_state.get('titulo_temp', ''))
            
            if not modo_edicao:
                c_a, c_b = st.columns(2)
                estilo = c_a.selectbox("Formato", ["Nota Informativa", "Legenda Instagram", "Nota Oficial", "Boletim"])
                tom = c_b.select_slider("Tom", ["Vibrante", "Institucional", "Técnico"])
                detalhes = st.text_area("Tópicos / Detalhes", height=100, placeholder="- Chegada do navio às 10h\n- Presença do Almirante\n- 500 militares envolvidos")
                
                if st.button("⚡ GERAR MINUTA", type="primary", use_container_width=True):
                    model = configurar_ia()
                    if model and evento:
                        with st.spinner("Consultando doutrina e redigindo..."):
                            prompt = f"Escreva um(a) {estilo} sobre: {evento}. Tom: {tom}. Detalhes: {detalhes}. Use linguagem militar correta da Marinha."
                            try:
                                resp = model.generate_content(prompt)
                                st.session_state['texto_temp'] = resp.text
                                st.session_state['titulo_temp'] = evento
                                st.rerun()
                            except Exception as e: st.error(f"Erro IA: {e}")

        if 'texto_temp' in st.session_state:
            st.markdown("#### 📝 Revisão")
            texto_final = st.text_area("Texto Final", value=st.session_state['texto_temp'], height=400)
            
            label_btn = "📤 REENVIAR CORREÇÃO" if modo_edicao else "📤 INICIAR APROVAÇÃO"
            
            if st.button(label_btn, type="primary", use_container_width=True):
                ok, msg = enviar_para_aprovacao(
                    st.session_state.get('titulo_temp', evento), 
                    texto_final, 
                    st.session_state.get('id_nota_edicao', None)
                )
                if ok:
                    st.toast(msg)
                    # Limpeza
                    if 'texto_temp' in st.session_state: del st.session_state['texto_temp']
                    if 'id_nota_edicao' in st.session_state: del st.session_state['id_nota_edicao']
                    time.sleep(1)
                    st.rerun()

    # === ABA 2: APRENDIZADO IA (Antigo RAG) ===
    elif st.session_state.prod_aba == 'aprendizado':
        st.caption("🧠 ENSINE A IA A ESCREVER COMO VOCÊ")
        
        with st.expander("➕ Adicionar Exemplo de Escrita"):
            with st.form("add_modelo"):
                n_cat = st.text_input("Categoria (Ex: Nota Operativa)")
                n_tit = st.text_input("Título de Referência")
                n_txt = st.text_area("Cole o texto modelo aqui:", height=150)
                if st.form_submit_button("💾 Salvar na Memória"):
                    db.table("modelos_escrita").insert({"categoria": n_cat, "titulo": n_tit, "conteudo": n_txt}).execute()
                    st.success("Aprendido!")
        
        # Listagem para consulta
        try:
            dados = db.table("modelos_escrita").select("*").execute().data
            if dados:
                st.dataframe(dados, use_container_width=True, hide_index=True)
            else: st.info("Nenhum modelo cadastrado.")
        except: pass

    # === ABA 3: STATUS DETALHADO (Expandido) ===
    elif st.session_state.prod_aba == 'status':
        st.caption("🚦 FLUXO DE APROVAÇÃO & ARQUIVO")
        
        filtro_status = st.radio("Exibir:", ["EM ANDAMENTO", "CONCLUÍDOS/ARQUIVADOS"], horizontal=True)
        
        try:
            query = db.table("fluxo_aprovacao").select("*").order("data_criacao", desc=True)
            if filtro_status == "EM ANDAMENTO":
                notas = query.in_("status", ["PENDENTE", "REPROVADO"]).execute().data
            else:
                notas = query.in_("status", ["APROVADO", "ARQUIVADO"]).execute().data
            
            if not notas:
                st.info("Nenhum item nesta categoria.")
            
            for item in notas:
                # Cor do Status
                stt = item['status']
                cor = "#ffcc00" if stt=="PENDENTE" else "#ff4b4b" if stt=="REPROVADO" else "#00cc00"
                
                with st.container(border=True):
                    # Cabeçalho do Card
                    c_tit, c_bad = st.columns([3, 1])
                    c_tit.markdown(f"**{item['titulo_nota']}**")
                    c_bad.markdown(f"<span style='color:{cor}; font-weight:bold'>{stt}</span>", unsafe_allow_html=True)
                    
                    # Detalhes Expansíveis
                    with st.expander(f"📄 Ver Detalhes / Ações"):
                        st.text_area("Conteúdo:", value=item['texto_gerado'], height=150, disabled=True)
                        if item.get('comentarios_chefia'):
                            st.warning(f"💬 Comentário Chefia: {item['comentarios_chefia']}")
                        
                        # BARRA DE AÇÕES
                        b1, b2, b3 = st.columns(3)
                        
                        # 1. Editar (Carrega no Redator)
                        if b1.button("✏️ EDITAR", key=f"ed_{item['id']}", use_container_width=True):
                            st.session_state['texto_temp'] = item['texto_gerado']
                            st.session_state['titulo_temp'] = item['titulo_nota']
                            st.session_state['id_nota_edicao'] = item['id']
                            st.session_state.prod_aba = 'redator'
                            st.rerun()
                        
                        # 2. Arquivar (Se já estiver aprovado/reprovado)
                        if stt != "ARQUIVADO":
                            if b2.button("🗄️ ARQUIVAR", key=f"arq_{item['id']}", use_container_width=True):
                                db.table("fluxo_aprovacao").update({"status": "ARQUIVADO"}).eq("id", item['id']).execute()
                                st.toast("Arquivado.")
                                time.sleep(0.5)
                                st.rerun()
                                
                        # 3. Excluir (Só Admin ou dono)
                        if b3.button("🗑️ EXCLUIR", key=f"del_{item['id']}", type="primary", use_container_width=True):
                            db.table("fluxo_aprovacao").delete().eq("id", item['id']).execute()
                            st.rerun()

        except Exception as e: st.error(f"Erro ao carregar lista: {e}")
