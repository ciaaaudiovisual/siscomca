import streamlit as st
import pandas as pd
import telebot
import time
import google.generativeai as genai
from modules.database import get_connection

def render():
    st.markdown("### 🤖 C2 - CENTRAL DE COMANDO E SIMULAÇÃO")
    db = get_connection()
    
    # Navegação Interna (Mantendo o estado da aba)
    if 'com_aba' not in st.session_state: st.session_state.com_aba = 'config'
    def set_aba(aba): st.session_state.com_aba = aba

    # ==============================================================================
    # MENU TÁTICO SUPERIOR (6 BOTÕES - TUDO INCLUSO)
    # ==============================================================================
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    c1.button("🧠\nCérebro", use_container_width=True, type="primary" if st.session_state.com_aba == 'config' else "secondary", on_click=set_aba, args=('config',))
    c2.button("🧪\nSimulador", use_container_width=True, type="primary" if st.session_state.com_aba == 'simulador' else "secondary", on_click=set_aba, args=('simulador',))
    c3.button("💾\nMemória", use_container_width=True, type="primary" if st.session_state.com_aba == 'memoria' else "secondary", on_click=set_aba, args=('memoria',))
    c4.button("🎉\nAutomação", use_container_width=True, type="primary" if st.session_state.com_aba == 'auto' else "secondary", on_click=set_aba, args=('auto',))
    c5.button("🛡️\nDenúncias", use_container_width=True, type="primary" if st.session_state.com_aba == 'denuncias' else "secondary", on_click=set_aba, args=('denuncias',))
    c6.button("📨\nBroadcast", use_container_width=True, type="primary" if st.session_state.com_aba == 'broadcast' else "secondary", on_click=set_aba, args=('broadcast',))

    st.divider()

    # Helpers de Configuração
    def get_val(key, default=""):
        try:
            cf = db.table("bot_config").select("*").eq("chave", key).execute()
            return cf.data[0]['valor'] if cf.data else default
        except: return default

    # ==============================================================================
    # ABA 1: CONFIGURAÇÃO (CÉREBRO & BRIEFING)
    # ==============================================================================
    if st.session_state.com_aba == 'config':
        with st.container(border=True):
            st.markdown("##### 🧠 Comando & Personalidade")
            val = get_val("system_prompt", "Você é um assistente militar útil e direto.")
            sys_p = st.text_area("System Prompt (Instrução Mestra)", value=val, height=100)
            
            st.divider()
            st.markdown("##### 📢 Briefing Diário (Dados Variáveis)")
            c1, c2, c3 = st.columns(3)
            u_dia = c1.text_input("Uniforme", value=get_val("uniforme_hoje"))
            meteo = c2.text_input("Meteo / Clima", value=get_val("meteo"))
            oficial = c3.text_input("Oficial de Dia", value=get_val("oficial_dia"))
            
            aviso = st.text_input("🚨 Aviso de Topo (Flash)", value=get_val("aviso_fixo"))

            if st.button("💾 Atualizar Parâmetros", type="primary", use_container_width=True):
                # Upsert Logic
                updates = {
                    "system_prompt": sys_p, 
                    "uniforme_hoje": u_dia, 
                    "meteo": meteo,
                    "oficial_dia": oficial,
                    "aviso_fixo": aviso
                }
                for k, v in updates.items():
                    chk = db.table("bot_config").select("*").eq("chave", k).execute()
                    if chk.data: db.table("bot_config").update({'valor': v}).eq('chave', k).execute()
                    else: db.table("bot_config").insert({'chave': k, 'valor': v}).execute()
                st.success("Parâmetros atualizados com sucesso!")

    # ==============================================================================
    # ABA 2: SIMULADOR DE BATALHA (NOVO!)
    # ==============================================================================
    elif st.session_state.com_aba == 'simulador':
        c_chat, c_info = st.columns([2, 1])
        
        with c_info:
            with st.container(border=True):
                st.info("ℹ️ **Área de Testes (Sandbox)**\n\nUse este chat para validar as respostas do Bot antes de ir para o ar. \n\nEle usa as mesmas regras de memória (`bot_memoria`) e a mesma IA (`Gemini`) do Telegram real.")
                if st.button("🗑️ Limpar Chat de Teste", use_container_width=True):
                    st.session_state.msgs_sim = []
                    st.rerun()

        with c_chat:
            with st.container(border=True):
                st.markdown("##### 📱 Preview do Telegram")
                
                # Inicializa histórico do simulador na sessão
                if "msgs_sim" not in st.session_state: 
                    st.session_state.msgs_sim = [{"role": "assistant", "content": "⚓ Pronto para o serviço. Selecione uma opção no menu."}]

                # Renderiza mensagens anteriores
                for msg in st.session_state.msgs_sim:
                    with st.chat_message(msg["role"], avatar="⚓" if msg["role"]=="assistant" else "👤"):
                        st.markdown(msg["content"])

                # Input do Usuário (Operador testando)
                if prompt := st.chat_input("Digite como se fosse um soldado..."):
                    # 1. Exibe msg usuario
                    st.session_state.msgs_sim.append({"role": "user", "content": prompt})
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(prompt)

                    # 2. Lógica do Bot (Replicada do bot_runner.py para fidelidade)
                    with st.chat_message("assistant", avatar="⚓"):
                        response_placeholder = st.empty()
                        response_placeholder.markdown("🔄 *Processando...*")
                        time.sleep(0.5)
                        
                        resposta_final = ""
                        found = False
                        
                        # A. Tenta Memória (RAG)
                        try:
                            regras = db.table("bot_memoria").select("*").eq("ativo", "true").execute().data
                            for r in regras:
                                keys = [k.strip().lower() for k in r['palavras_chave'].split(',')]
                                for k in keys:
                                    if k in prompt.lower():
                                        resposta_final = f"🤖 **[MEMÓRIA]** {r['resposta']}"
                                        found = True
                                        break
                                if found: break
                        except: found = False
                        
                        # B. Tenta IA (Gemini)
                        if not found:
                            try:
                                genai.configure(api_key=st.secrets["google"]["api_key"])
                                model = genai.GenerativeModel('gemini-2.5-flash')
                                sys_p = get_val("system_prompt", "Você é um assistente militar.")
                                resp_ia = model.generate_content(f"{sys_p}\nUsuário: {prompt}")
                                resposta_final = resp_ia.text
                            except Exception as e:
                                resposta_final = f"⚠️ Erro na IA: {e}"

                        # Exibe resultado
                        response_placeholder.markdown(resposta_final)
                        st.session_state.msgs_sim.append({"role": "assistant", "content": resposta_final})

    # ==============================================================================
    # ABA 3: MEMÓRIA (RAG MANUAL)
    # ==============================================================================
    elif st.session_state.com_aba == 'memoria':
        st.markdown("##### 💾 Ensinar o Robô (Economia de IA)")
        st.info("Cadastre perguntas frequentes. O bot responderá isso antes de gastar tokens da IA.")
        
        with st.expander("➕ Adicionar Nova Resposta", expanded=False):
            with st.form("add_mem"):
                kw = st.text_input("Palavras-chave (separe por vírgula)", placeholder="Ex: rancho, almoço, cardápio")
                resp = st.text_area("Resposta do Bot", placeholder="O rancho abre às 11h30.")
                if st.form_submit_button("Gravar na Memória", use_container_width=True):
                    if kw and resp:
                        db.table("bot_memoria").insert({"palavras_chave": kw, "resposta": resp, "ativo": True}).execute()
                        st.success("Gravado!")
                        st.rerun()
                    else: st.warning("Preencha tudo.")
        
        # Listagem
        try:
            res = db.table("bot_memoria").select("*").order("id", desc=True).execute().data
            for m in res:
                 with st.container(border=True):
                     c1, c2 = st.columns([5,1])
                     c1.markdown(f"🔑 **{m['palavras_chave']}**")
                     c1.caption(f"🤖 {m['resposta']}")
                     if c2.button("🗑️", key=f"del_{m['id']}"):
                         db.table("bot_memoria").delete().eq("id", m['id']).execute()
                         st.rerun()
        except: st.info("Memória vazia.")

    # ==============================================================================
    # ABA 4: AUTOMAÇÃO (MANTIDA DO ORIGINAL)
    # ==============================================================================
    elif st.session_state.com_aba == 'auto':
        st.markdown("##### 🎉 CICLOS AUTOMÁTICOS")
        
        # Recupera configs atuais
        cfg_tg_on = get_val("auto_niver_tg") == "True"
        cfg_tg_tpl = get_val("tpl_niver_tg", "🎉 Parabéns, {nome}! O Comando lhe deseja felicidades.")
        cfg_em_on = get_val("auto_niver_email") == "True"
        cfg_em_tpl = get_val("tpl_niver_email", "Prezado {nome},\n\nReceba os cumprimentos deste Comando.\n\nAtt,\nComSoc.")

        # Telegram Config
        with st.container(border=True):
            st.markdown("###### 📱 Telegram")
            c_tg_on, c_tg_mod = st.columns([1, 4])
            tg_active = c_tg_on.toggle("Ativar", value=cfg_tg_on, key="tg_toggle")
            tg_tpl = c_tg_mod.text_area("Template Msg", value=cfg_tg_tpl, height=80, help="Use {nome} para substituir pelo Nome de Guerra.")
            
        # Email Config
        with st.container(border=True):
            st.markdown("###### 📧 E-mail Institucional")
            c_em_on, c_em_mod = st.columns([1, 4])
            em_active = c_em_on.toggle("Ativar", value=cfg_em_on, key="em_toggle")
            em_tpl = c_em_mod.text_area("Template Corpo", value=cfg_em_tpl, height=100)
            
            with st.expander("⚙️ Credenciais SMTP"):
                st.info("Configure no `secrets.toml`: `[email]`")

        # Salvar
        if st.button("💾 SALVAR AUTOMAÇÕES", type="primary", use_container_width=True):
            updates = {
                "auto_niver_tg": str(tg_active),
                "tpl_niver_tg": tg_tpl,
                "auto_niver_email": str(em_active),
                "tpl_niver_email": em_tpl
            }
            for k, v in updates.items():
                chk = db.table("bot_config").select("*").eq("chave", k).execute()
                if chk.data: db.table("bot_config").update({'valor': v}).eq('chave', k).execute()
                else: db.table("bot_config").insert({'chave': k, 'valor': v}).execute()
            st.success("Configuração salva!")
            
            if st.button("🧪 Simular Envio (Teste)"):
                st.info(f"Simulação Telegram: {tg_tpl.format(nome='SD TESTE')}")

    # ==============================================================================
    # ABA 5: DENÚNCIAS
    # ==============================================================================
    elif st.session_state.com_aba == 'denuncias':
         st.markdown("##### 🛡️ Denúncias Recebidas")
         try:
             res = db.table("denuncias").select("*").order("id", desc=True).execute().data
             if not res: st.info("Nenhuma denúncia pendente.")
             
             for d in res:
                 cor = "red" if d['status'] == "PENDENTE" else "green"
                 with st.container(border=True):
                     st.markdown(f"**Protocolo #{d['id']}** | Status: <span style='color:{cor}'>{d['status']}</span>", unsafe_allow_html=True)
                     st.warning(f"📝 {d['texto']}")
                     
                     if d['status'] != 'ARQUIVADO':
                         c1, c2 = st.columns(2)
                         if c1.button("🕵️ Em Apuração", key=f"inv_{d['id']}"):
                             db.table("denuncias").update({"status": "EM APURACAO"}).eq("id", d['id']).execute()
                             st.rerun()
                         if c2.button("📂 Arquivar", key=f"arq_{d['id']}"):
                             db.table("denuncias").update({"status": "ARQUIVADO"}).eq("id", d['id']).execute()
                             st.rerun()
         except: pass

    # ==============================================================================
    # ABA 6: BROADCAST
    # ==============================================================================
    elif st.session_state.com_aba == 'broadcast':
        st.markdown("##### 📨 Disparo Tático")
        with st.container(border=True):
            target = st.radio("Público Alvo", ["Todos (Ativos)", "Oficiais", "Equipe ComSoc"], horizontal=True)
            msg = st.text_area("Mensagem Oficial")
            
            if st.button("🚀 ENVIAR COMUNICADO", type="primary", use_container_width=True):
                if not msg:
                    st.warning("Escreva uma mensagem.")
                else:
                    try:
                        query = db.table("efetivo").select("telegram_id, permissao").eq("status", "ATIVO")
                        if target == "Oficiais": query = query.in_("permissao", ["ADMIN", "SUPERVISOR", "VIP"])
                        elif target == "Equipe ComSoc": query = query.in_("permissao", ["ADMIN", "SUPERVISOR"])
                        
                        users = query.execute().data
                        
                        bot_sender = telebot.TeleBot(st.secrets["telegram"]["token"])
                        count = 0
                        bar = st.progress(0)
                        
                        for i, u in enumerate(users):
                            try:
                                bot_sender.send_message(u['telegram_id'], f"📢 **COMUNICADO:**\n\n{msg}", parse_mode="Markdown")
                                count += 1
                            except: pass
                            bar.progress((i+1)/len(users))
                            
                        st.success(f"Enviado para {count} militares.")
                    except Exception as e:
                        st.error(f"Erro no envio: {e}")
