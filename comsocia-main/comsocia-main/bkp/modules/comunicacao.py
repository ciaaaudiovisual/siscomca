import streamlit as st
import time
import pandas as pd

def render():
    st.subheader("📢 Central de Comunicação & IA Integrada")
    
    # Layout de 3 abas focadas no fluxo operacional
    tab_bot, tab_social, tab_triagem = st.tabs([
        "🤖 Bot Tático (Comando)", 
        "📱 Planejamento & IA",
        "📥 Triagem (Crowdsourcing)"
    ])

    # --- ABA 1: COMANDO DO BOT (O Cérebro) ---
    with tab_bot:
        c1, c2 = st.columns([1.5, 1])
        
        with c1:
            st.markdown("##### 📡 Monitoramento em Tempo Real")
            
            # Simulação de Chat (Futuro: Ler da tabela 'bot_logs')
            with st.container(border=True, height=300):
                st.chat_message("user", avatar="👮").write("Qual o uniforme para amanhã?")
                st.chat_message("assistant", avatar="🤖").write("Uniforme: Branco (5.5), conforme Ordem do Dia Nº 20.")
                st.chat_message("user", avatar="📸").write("Mandei as fotos do evento no Cais.")
                st.chat_message("assistant", avatar="🤖").write("Recebido, Sd. Silva. Enviado para a aba Triagem.")
                st.caption("Status: IA Ativa | Latência: 0.2s")

        with c2:
            st.markdown("##### 🚀 Disparo de Avisos (Broadcasting)")
            
            with st.form("form_broadcast"):
                destinatario = st.selectbox(
                    "Público Alvo", 
                    ["Todos (Geral)", "Oficiais", "Corpo de Alunos", "Equipe ComSoc"]
                )
                
                tipo_msg = st.radio("Prioridade", ["Aviso Normal", "🚨 URGENTE", "🔇 Silêncio de Rádio"], horizontal=True)
                
                msg = st.text_area("Mensagem", placeholder="Ex: O horário do rancho foi antecipado...")
                
                col_btn, col_check = st.columns([1, 1])
                verificacao = col_check.checkbox("Confirmar Envio")
                
                if st.form_submit_button("Enviar Mensagem", use_container_width=True):
                    if verificacao and msg:
                        # Aqui entraria a chamada da API do Telegram
                        st.success(f"Mensagem enviada para **{destinatario}**!")
                        if tipo_msg == "🚨 URGENTE":
                            st.toast("Notificação sonora disparada nos celulares!", icon="🔊")
                    else:
                        st.error("Confirme o envio e digite uma mensagem.")

    # --- ABA 2: PLANEJAMENTO & IA GENERATIVA ---
    with tab_social:
        c_redator, c_preview = st.columns(2)
        
        with c_redator:
            st.markdown("##### ✍️ Redator Assistido por IA")
            tema = st.text_input("Sobre o que vamos postar?", placeholder="Ex: Chegada do Navio Escola")
            tom = st.select_slider("Tom da Legenda", options=["Formal/Militar", "Informativo", "Vibrante/Jovem"])
            
            if st.button("✨ Gerar Sugestões de Legenda"):
                with st.spinner("IA analisando contexto naval..."):
                    time.sleep(1.5)
                    st.info("Sugestão Gerada:")
                    st.text_area(
                        "Legenda Sugerida", 
                        value="⚓ Hoje recebemos o Navio Escola Brasil! Nossos futuros oficiais iniciam mais uma jornada de conhecimento. #MarinhaDoBrasil #CIAA #Futuro",
                        height=150
                    )
        
        with c_preview:
            st.markdown("##### 📱 Preview (Instagram)")
            st.image("https://placehold.co/400x400/png?text=FOTO+DO+NAVIO", caption="Preview da Imagem")
            st.button("Enviar para Aprovação do Comandante")

    # --- ABA 3: TRIAGEM (A Cereja do Bolo) ---
    with tab_triagem:
        st.markdown("##### 📥 Fotos Recebidas via Bot (Crowdsourcing)")
        st.info("Aqui aparecem as fotos que os militares enviam para o Bot. Você decide o que entra no acervo.")
        
        # Simulação de Galeria de Triagem
        col1, col2, col3 = st.columns(3)
        
        # FOTO 1
        with col1:
            with st.container(border=True):
                st.image("https://placehold.co/300x200/png?text=Foto+Sd+Silva", use_column_width=True)
                st.caption("Enviado por: Sd Silva (10:05)")
                c_ok, c_del = st.columns(2)
                if c_ok.button("✅ Aprovar", key="ap1"):
                    st.toast("Foto movida para o Banco de Imagens!")
                if c_del.button("❌ Descartar", key="del1"):
                    st.toast("Foto excluída.")

        # FOTO 2
        with col2:
            with st.container(border=True):
                st.image("https://placehold.co/300x200/png?text=Foto+Ten+Joao", use_column_width=True)
                st.caption("Enviado por: Ten João (09:40)")
                c_ok2, c_del2 = st.columns(2)
                c_ok2.button("✅ Aprovar", key="ap2")
                c_del2.button("❌ Descartar", key="del2")
        
        # FOTO 3
        with col3:
            with st.container(border=True):
                st.image("https://placehold.co/300x200/png?text=Meme+Enviado", use_column_width=True)
                st.caption("Enviado por: Anônimo")
                st.error("⚠️ Conteúdo Impróprio Detectado pela IA")
                st.button("❌ Banir Usuário", key="ban3", type="primary")