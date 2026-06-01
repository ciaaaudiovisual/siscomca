import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import qrcode
from io import BytesIO
from modules.database import get_connection

BOT_USERNAME = "@ComSocIA_bot"

def gerar_qr(payload):
    link = f"https://t.me/{BOT_USERNAME}?start={payload}"
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue()

def render():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Black+Ops+One&display=swap');

            #MainMenu, header, footer, [data-testid="stSidebar"] {visibility: hidden; display: none;}
            .block-container { padding: 0 !important; max-width: 100% !important; }
            
            /* HEADER TÁTICO */
            .header-tatica {
                display: flex; align-items: center; justify-content: space-between;
                background: linear-gradient(180deg, #1e1e1e 0%, #0e1117 100%);
                border-bottom: 3px solid #00cc00;
                padding: 15px 40px; margin-bottom: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.8);
            }
            .titulo-tv {
                font-family: 'Black Ops One', cursive;
                font-size: 3rem; color: #e0e0e0; letter-spacing: 4px; line-height: 1;
            }
            .relogio-tv {
                font-family: monospace; font-size: 2.5rem; color: #00cc00; font-weight: bold;
            }
            
            /* KPIs */
            .kpi-card {
                background-color: #1a1a1a; border: 1px solid #333; border-radius: 12px;
                padding: 15px; text-align: center; height: 160px;
                display: flex; flex-direction: column; justify-content: center;
                box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            }
            .kpi-val { font-family: 'Black Ops One', cursive; font-size: 4.5rem; line-height: 1; }
            .kpi-lbl { font-size: 1.1rem; text-transform: uppercase; color: #888; margin-top: 5px; font-weight: bold;}
            
            /* === MISSÃO PRINCIPAL === */
            .mission-main {
                background-color: #111; 
                border-left: 12px solid #00cc00; /* Cor dinâmica */
                padding: 25px; border-radius: 8px; margin-top: 10px; margin-bottom: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.6);
                position: relative;
            }
            .main-time { font-family: 'Black Ops One', cursive; font-size: 3rem; color: #ddd; }
            .main-title { font-size: 2.2rem; color: white; margin: 5px 0; font-weight: bold; line-height: 1.1; }
            .main-resp { font-size: 1.4rem; color: #aaa; text-transform: uppercase; margin-top: 5px;}
            
            /* Badge de Status (Atrasado/Andamento) */
            .status-badge {
                position: absolute; top: 20px; right: 20px;
                background: #ff9900; color: #000;
                padding: 5px 10px; border-radius: 4px;
                font-weight: bold; font-family: monospace; text-transform: uppercase;
            }

            /* === LISTA SECUNDÁRIA === */
            .mission-sub {
                background-color: #1e1e1e; 
                border-left: 6px solid #555; 
                padding: 15px 20px; margin-top: 10px; border-radius: 6px;
                display: flex; justify-content: space-between; align-items: center;
            }
            .sub-time { font-family: monospace; font-size: 1.5rem; color: #ddd; font-weight: bold; }
            .sub-title { font-size: 1.3rem; color: white; font-weight: 600; margin-left: 15px; flex-grow: 1; }
            .sub-resp { font-size: 1rem; color: #888; text-transform: uppercase; }

            /* Task Row */
            .task-row {
                background-color: #222; padding: 20px; margin-bottom: 15px;
                border-radius: 8px; border-left: 6px solid #ffcc00;
                display: flex; justify-content: space-between; align-items: center;
            }
        </style>
    """, unsafe_allow_html=True)

    db = get_connection()

    # Fuso Horário UTC-3
    FUSO_BR = timezone(timedelta(hours=-3))
    agora = datetime.now(FUSO_BR)
    hora_atual_str = agora.strftime('%H:%M:%S')
    hoje_iso = agora.strftime('%Y-%m-%d')
    
    # --- HEADER ---
    st.markdown(f"""
        <div class="header-tatica">
            <div class="titulo-tv">COMSOC CENTER <span style="font-size:1.5rem; color:#00cc00">// MONITOR</span></div>
            <div class="relogio-tv">{hora_atual_str}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Layout Principal
    pad1, main_cont, pad2 = st.columns([0.2, 10, 0.2])
    with main_cont:
        # 1. KPIs
        k1, k2, k3, k4 = st.columns(4)
        
        # BUSCA GERAL (Note que removi o filtro de data para Agenda Futura, pegando tudo que é CONFIRMADO)
        # Se quiser manter o KPI de "Futuro" apenas para futuro real, mantenha o filtro ali, 
        # mas na lista visual abaixo usaremos tudo.
        pend = len(db.table("agenda").select("id").eq("status", "PENDENTE").execute().data)
        
        # KPI de Agenda mostra TOTAL de missões abertas (Passadas + Futuras)
        total_aberto = len(db.table("agenda").select("id").eq("status", "CONFIRMADO").execute().data)
        
        doing = len(db.table("tarefas").select("id").eq("status", "FAZENDO").execute().data)
        
        all_dates = db.table("datas_comemorativas").select("*").eq("tipo", "Aniversario").execute().data
        niver_mes = sum(1 for d in all_dates if pd.to_datetime(d['data_evento']).month == agora.month)

        def render_kpi(col, label, val, color):
            col.markdown(f"""
                <div class="kpi-card" style="border-bottom: 6px solid {color}">
                    <div class="kpi-val" style="color: {color}">{val}</div>
                    <div class="kpi-lbl">{label}</div>
                </div>
            """, unsafe_allow_html=True)

        render_kpi(k1, "PENDÊNCIAS", pend, "#ff4b4b" if pend > 0 else "#444")
        render_kpi(k2, "MISSÕES ABERTAS", total_aberto, "#00cc00") # Alterado label para refletir realidade
        render_kpi(k3, "PRODUÇÃO", doing, "#ffcc00")
        render_kpi(k4, "ANIVERSÁRIOS", niver_mes, "#3366ff")

        st.markdown("<br>", unsafe_allow_html=True)

        # 2. ÁREA OPERACIONAL
        c_mission, c_warroom = st.columns([1.6, 1])
        
        # === COLUNA ESQUERDA: AGENDA TÁTICA ===
        with c_mission:
            st.markdown("### 🎯 RADAR DE MISSÕES")
            
            # --- LÓGICA CRÍTICA: Buscar TUDO que é CONFIRMADO, ordenado por data ---
            # Isso garante que se tiver algo de ontem, aparece primeiro (urgência)
            agenda_items = db.table("agenda").select("*").eq("status", "CONFIRMADO").order("data_hora").limit(4).execute().data
            
            if agenda_items:
                # --- ITEM PRINCIPAL (O MAIS ANTIGO ABERTO OU O PRÓXIMO) ---
                p1 = agenda_items[0]
                
                # Conversão
                iso_str = p1['data_hora'].replace('Z', '+00:00')
                dt_utc = datetime.fromisoformat(iso_str)
                dt_br = dt_utc.astimezone(FUSO_BR)
                
                dia_str = dt_br.strftime('%d/%m')
                hora_str = dt_br.strftime('%H:%M')
                resp = p1.get('responsavel') if p1.get('responsavel') else "Sem Escala"
                
                # LÓGICA DE STATUS/COR
                is_passado = dt_br < agora
                
                if is_passado:
                    # Se já passou da hora: Laranja (Atenção) + Badge
                    cor_borda = "#ff9900" # Laranja
                    cor_texto_hora = "#ff9900"
                    badge_html = f"<div class='status-badge'>EM ANDAMENTO</div>"
                else:
                    # Se é futuro: Verde (Padrão)
                    delta_h = (dt_br - agora).total_seconds() / 3600
                    cor_borda = "#ff4b4b" if delta_h < 12 else "#00cc00"
                    cor_texto_hora = "#00cc00"
                    badge_html = "" # Sem badge
                
                st.markdown(f"""
                <div class="mission-main" style="border-left-color: {cor_borda}">
                    {badge_html}
                    <div class="main-time" style="color:{cor_texto_hora}">{dia_str} <span style="color:#fff; font-size:0.6em">AS</span> {hora_str}</div>
                    <div class="main-title">{p1['evento']}</div>
                    <div class="main-resp">👮 {resp}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # --- LISTA SECUNDÁRIA ---
                subsequentes = agenda_items[1:]
                if subsequentes:
                    st.markdown("#### ⏳ NA SEQUÊNCIA")
                    for sub in subsequentes:
                        sub_iso = sub['data_hora'].replace('Z', '+00:00')
                        sub_dt = datetime.fromisoformat(sub_iso).astimezone(FUSO_BR)
                        
                        s_hora = sub_dt.strftime('%d/%m %H:%M')
                        s_resp = sub.get('responsavel', '-').split(',')[0]
                        
                        # Verifica se também está atrasado na lista secundária
                        if sub_dt < agora:
                            bord_sub = "#ff9900" # Laranja
                            s_hora = f"⚠️ {s_hora}" # Ícone de alerta
                        else:
                            bord_sub = "#3366ff" # Azul padrão
                        
                        st.markdown(f"""
                        <div class="mission-sub" style="border-left-color: {bord_sub}">
                            <div class="sub-time">{s_hora}</div>
                            <div class="sub-title">{sub['evento']}</div>
                            <div class="sub-resp">{s_resp}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="mission-main" style="border-left-color: #555; text-align:center">
                    <div class="main-title" style="color:#777">SEM MISSÕES PREVISTAS</div>
                    <div class="main-resp">Aguardando Ordens</div>
                </div>
                """, unsafe_allow_html=True)

        # === COLUNA DIREITA: TAREFAS ===
        with c_warroom:
            st.markdown("### ⚡ EM EXECUÇÃO")
            tasks = db.table("tarefas").select("*").eq("status", "FAZENDO").limit(4).execute().data
            
            if not tasks:
                st.info("Mesa limpa.")
            else:
                for t in tasks:
                    c_txt, c_qr = st.columns([3, 1])
                    with c_txt:
                        prioridade = t.get('prioridade', 'NORMAL')
                        cor_prio = "#ff4b4b" if prioridade == "URGENTE" else "#ffcc00"
                        
                        st.markdown(f"""
                        <div class="task-row">
                            <div>
                                <div style="font-size:1.3rem; font-weight:bold; color:white;">{t['titulo']}</div>
                                <div style="color:{cor_prio}; font-size:0.9rem; font-weight:bold;">⚠️ {prioridade}</div>
                                <div style="color:#888;">{t.get('responsavel', 'Equipe')}</div>
                            </div>
                        </div>""", unsafe_allow_html=True)
                    with c_qr:
                        st.image(gerar_qr(f"concluir_{t['id']}"), width=80)

        # Rodapé
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔙 VOLTAR AO DASHBOARD", use_container_width=True):
            st.session_state.pagina_atual = 'dashboard'
            st.rerun()

    time.sleep(30)
    st.rerun()
