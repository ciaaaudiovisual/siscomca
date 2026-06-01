import telebot
from telebot import types
import google.generativeai as genai
from supabase import create_client
import tomllib
import threading
import time
import schedule
import streamlit as st
from datetime import datetime, timedelta
import calendar
from dateutil import parser

# ==============================================================================
# 1. CONFIGURAÇÃO E CONEXÃO
# ==============================================================================
try:
    if "telegram" in st.secrets: secrets = st.secrets
    else:
        with open(".streamlit/secrets.toml", "rb") as f: secrets = tomllib.load(f)

    bot = telebot.TeleBot(secrets["telegram"]["token"])
    genai.configure(api_key=secrets["google"]["api_key"])
    db = create_client(secrets["supabase"]["url"], secrets["supabase"]["key"])
    model_chat = genai.GenerativeModel('gemini-2.5-flash') 

except Exception as e:
    print(f"❌ Erro Crítico: {e}")

# Memória de Estado (Conversa + Fluxos Complexos)
user_states = {} 

# ==============================================================================
# 2. UX TÁTICO (FEEDBACK VISUAL) - O "CHARME" DO NOVO BOT
# ==============================================================================

def reagir(cid, message_id, emoji="🫡"):
    """Reage à mensagem para dar feedback instantâneo"""
    try: bot.set_message_reaction(cid, message_id, [types.ReactionTypeEmoji(emoji)])
    except: pass

def digitando(cid, tempo=1.5):
    """Mostra 'escrevendo...'"""
    try:
        bot.send_chat_action(cid, 'typing')
        time.sleep(tempo)
    except: pass

def enviar_progresso(cid, texto_final):
    """Simula pensamento da IA"""
    try:
        msg = bot.send_message(cid, "🔄 *Processando solicitação...*", parse_mode="Markdown")
        time.sleep(0.5)
        bot.edit_message_text(texto_final, cid, msg.message_id, parse_mode="Markdown")
    except:
        bot.send_message(cid, texto_final, parse_mode="Markdown")

# ==============================================================================
# 3. MENUS VISUAIS (SUBSTITUEM COMANDOS DE BARRA)
# ==============================================================================

def menu_principal():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row("📢 Briefing", "📅 Agenda")
    markup.row("✍️ Redator IA", "📖 Doutrina")
    markup.row("🛡️ Denúncia", "🆘 Ajuda")
    return markup

def menu_cancelar():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Cancelar Operação")
    return markup

# ==============================================================================
# 4. FERRAMENTAS DE CALENDÁRIO (RESGATADO DO ORIGINAL)
# ==============================================================================

def gerar_calendario(ano, mes):
    markup = types.InlineKeyboardMarkup(row_width=7)
    nome_mes = calendar.month_name[mes]
    btn_prev = types.InlineKeyboardButton("⬅️", callback_data=f"NAV_CAL_{ano}_{mes-1 if mes>1 else 12}")
    btn_lbl = types.InlineKeyboardButton(f"{nome_mes} {ano}", callback_data="ignore")
    btn_next = types.InlineKeyboardButton("➡️", callback_data=f"NAV_CAL_{ano}_{mes+1 if mes<12 else 1}")
    markup.row(btn_prev, btn_lbl, btn_next)
    dias = ["D", "S", "T", "Q", "Q", "S", "S"]
    markup.row(*[types.InlineKeyboardButton(d, callback_data="ignore") for d in dias])
    cal = calendar.monthcalendar(ano, mes)
    for week in cal:
        row = []
        for day in week:
            if day == 0: row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else: row.append(types.InlineKeyboardButton(str(day), callback_data=f"CAL_{ano}-{mes:02d}-{day:02d}"))
        markup.row(*row)
    return markup

def gerar_seletor_hora(data_iso):
    markup = types.InlineKeyboardMarkup(row_width=4)
    horas = ["08:00", "09:00", "10:00", "14:00", "16:00", "20:00"]
    botoes = [types.InlineKeyboardButton(h, callback_data=f"HORA_{data_iso}_{h}") for h in horas]
    markup.add(*botoes)
    return markup

# ==============================================================================
# 5. SCHEDULER (VIGÍLIA AUTOMÁTICA) - RESGATADO DO ORIGINAL
# ==============================================================================

def job_alerta_antecipado():
    """Avisa missões do dia seguinte"""
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        res = db.table("agenda").select("*").eq("status", "CONFIRMADO").gte("data_hora", f"{amanha}T00:00:00").execute()
        if res.data:
            users = db.table("efetivo").select("telegram_id").eq("status", "ATIVO").execute().data
            for e in res.data:
                msg = f"🔔 **MISSÃO AMANHÃ:**\n📍 {e['evento']}"
                for u in users:
                    try: bot.send_message(u['telegram_id'], msg, parse_mode="Markdown")
                    except: pass
    except: pass

def run_schedule():
    schedule.every().day.at("20:00").do(job_alerta_antecipado)
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=run_schedule, daemon=True).start()

# ==============================================================================
# 6. FLUXOS E HANDLERS (A MÁGICA UNIFICADA)
# ==============================================================================

# --- START ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    cid = message.chat.id
    reagir(cid, message.message_id)
    
    # Verifica cadastro
    res = db.table("efetivo").select("*").eq("telegram_id", str(cid)).execute()
    
    if not res.data:
        # Usuário novo
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add('🚀 Solicitar Acesso')
        bot.send_message(cid, "⛔ **Acesso Restrito.**\nIdentifique-se para prosseguir.", reply_markup=markup)
    elif res.data[0]['status'] == 'PENDENTE':
        bot.send_message(cid, "⏳ Seu cadastro está em análise pela 1ª Seção.")
    else:
        # Usuário Ativo -> Menu Completo
        nome = res.data[0]['nome_guerra']
        bot.send_message(cid, f"⚓ **Pronto para o serviço, {nome}.**", reply_markup=menu_principal())

# --- SOLICITAÇÃO DE ACESSO ---
@bot.message_handler(func=lambda m: m.text == '🚀 Solicitar Acesso')
def solicitar_acesso(message):
    msg = bot.reply_to(message, "📝 Digite seu **Nome de Guerra**:")
    bot.register_next_step_handler(msg, finalizar_cadastro_step)

def finalizar_cadastro_step(message):
    cid = str(message.chat.id)
    nome = message.text.upper()
    try:
        db.table("efetivo").insert({"nome_guerra": nome, "telegram_id": cid, "status": "PENDENTE", "permissao": "USUARIO"}).execute()
        bot.reply_to(message, "✅ Solicitação enviada. Aguarde aprovação.")
        # Notifica Admins
        admins = db.table("efetivo").select("telegram_id").eq("permissao", "ADMIN").execute().data
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Aprovar", callback_data=f"aprov_user_{cid}"), 
                   types.InlineKeyboardButton("🚫 Recusar", callback_data=f"rec_user_{cid}"))
        for adm in admins:
            bot.send_message(adm['telegram_id'], f"🛡️ **Novo Usuário:** {nome}", reply_markup=markup)
    except: pass

# --- FLUXO 1: 🛡️ DENÚNCIA (NOVO UX) ---
@bot.message_handler(func=lambda m: m.text == "🛡️ Denúncia")
def iniciar_denuncia(message):
    cid = message.chat.id
    user_states[cid] = {"step": "escrevendo_denuncia"}
    bot.send_message(cid, "🛡️ **Canal Seguro**\nDigite sua denúncia (Anônimo):", reply_markup=menu_cancelar())

# --- FLUXO 2: ✍️ REDATOR IA (NOVO UX) ---
@bot.message_handler(func=lambda m: m.text == "✍️ Redator IA")
def iniciar_redator(message):
    cid = message.chat.id
    user_states[cid] = {"step": "tema_redator"}
    bot.send_message(cid, "✍️ **Redator Oficial**\nQual o tema do texto?", reply_markup=menu_cancelar())

# --- FLUXO 3: 📅 AGENDA (INTEGRADO COM CALENDÁRIO) ---
@bot.message_handler(func=lambda m: m.text == "📅 Agenda")
def ver_agenda(message):
    cid = message.chat.id
    digitando(cid)
    
    # 1. Mostra Próximos Eventos
    hoje = datetime.now().isoformat()
    res = db.table("agenda").select("*").eq("status", "CONFIRMADO").gte("data_hora", hoje).limit(3).execute().data
    txt = "📅 **PRÓXIMAS MISSÕES:**\n\n"
    if res:
        for e in res:
            dt = datetime.fromisoformat(e['data_hora'].replace('Z','')).strftime('%d/%m %H:%M')
            txt += f"🔹 {dt} | {e['evento']}\n"
    else: txt += "Nada previsto."
    
    # 2. Oferece Botão de Novo Agendamento
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Agendar Nova Missão", callback_data="novo_evento"))
    bot.send_message(cid, txt, parse_mode="Markdown", reply_markup=markup)

# --- FLUXO 4: 📢 BRIEFING ---
@bot.message_handler(func=lambda m: m.text == "📢 Briefing")
def ver_briefing(message):
    try:
        cf = db.table("bot_config").select("*").execute().data
        mapa = {i['chave']: i['valor'] for i in cf}
        txt = f"📝 **BRIEFING**\n\nUniforme: {mapa.get('uniforme_hoje','-')}\nAviso: {mapa.get('aviso_fixo','')}"
        bot.reply_to(message, txt)
    except: pass

# --- AÇÃO: ❌ CANCELAR ---
@bot.message_handler(func=lambda m: m.text == "❌ Cancelar Operação")
def cancelar(message):
    cid = message.chat.id
    if cid in user_states: del user_states[cid]
    bot.send_message(cid, "🛑 Operação cancelada.", reply_markup=menu_principal())

# ==============================================================================
# 7. CALLBACKS (ADMINISTRAÇÃO E CALENDÁRIO)
# ==============================================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    cid = str(call.message.chat.id)
    data = call.data

    # A. Aprovação de Usuário
    if data.startswith("aprov_user_"):
        uid = data.split("_")[2]
        db.table("efetivo").update({"status": "ATIVO"}).eq("telegram_id", uid).execute()
        bot.edit_message_text("✅ Liberado.", cid, call.message.message_id)
        try: bot.send_message(uid, "✅ **Acesso Liberado!**\nUse /start ou o menu.", reply_markup=menu_principal())
        except: pass

    # B. Agendamento (Novo Evento)
    elif data == "novo_evento":
        user_states[int(cid)] = {"step": "titulo_agenda"}
        bot.send_message(cid, "📝 Digite o **Nome da Missão**:", reply_markup=menu_cancelar())

    # C. Navegação Calendário
    elif data.startswith("NAV_CAL_"):
        _, _, ano, mes = data.split("_")
        markup = gerar_calendario(int(ano), int(mes))
        bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=markup)

    # D. Seleção de Dia
    elif data.startswith("CAL_"):
        dt = data.split("_")[1]
        user_states[int(cid)]["data_temp"] = dt
        markup = gerar_seletor_hora(dt)
        bot.edit_message_text(f"📅 Dia {dt}\n🕒 Selecione a Hora:", cid, call.message.message_id, reply_markup=markup)

    # E. Confirmação Final
    elif data.startswith("HORA_"):
        _, dt, hr = data.split("_")
        if int(cid) in user_states:
            titulo = user_states[int(cid)].get("titulo")
            iso = f"{dt}T{hr}:00"
            db.table("agenda").insert({"evento": titulo, "data_hora": iso, "status": "CONFIRMADO"}).execute()
            bot.edit_message_text(f"✅ **Agendado:** {titulo} em {dt} às {hr}", cid, call.message.message_id)
            del user_states[int(cid)]

# ==============================================================================
# 8. CÉREBRO PRINCIPAL (MÁQUINA DE ESTADOS + IA)
# ==============================================================================
@bot.message_handler(func=lambda m: True)
def processar_tudo(message):
    cid = message.chat.id
    txt = message.text
    
    # 1. Verifica Fluxos em Andamento
    if cid in user_states:
        stt = user_states[cid]
        step = stt.get("step")
        
        # Denúncia
        if step == "escrevendo_denuncia":
            db.table("denuncias").insert({"texto": txt, "status": "PENDENTE"}).execute()
            bot.send_message(cid, "✅ Recebido. Sigilo garantido.", reply_markup=menu_principal())
            del user_states[cid]
            return
            
        # Redator
        elif step == "tema_redator":
            digitando(cid)
            res = model_chat.generate_content(f"Escreva um texto militar formal sobre: {txt}").text
            bot.send_message(cid, res, reply_markup=menu_principal())
            del user_states[cid]
            return
            
        # Agenda (Título)
        elif step == "titulo_agenda":
            stt["titulo"] = txt
            stt["step"] = "escolhendo_data"
            now = datetime.now()
            markup = gerar_calendario(now.year, now.month)
            bot.send_message(cid, "📅 Selecione a Data:", reply_markup=markup)
            return

    # 2. Chat Inteligente (Memória + IA)
    # Memória
    try:
        regras = db.table("bot_memoria").select("*").eq("ativo", "true").execute().data
        for r in regras:
            if any(k.strip().lower() in txt.lower() for k in r['palavras_chave'].split(',')):
                reagir(cid, message.message_id)
                bot.reply_to(message, f"🤖 {r['resposta']}")
                return
    except: pass

    # IA (Gemini)
    digitando(cid)
    try:
        sys = db.table("bot_config").select("valor").eq("chave", "system_prompt").execute().data[0]['valor']
        resp = model_chat.generate_content(f"{sys}\nUser: {txt}").text
        bot.reply_to(message, resp)
    except:
        bot.reply_to(message, "⚠️ IA Indisponível.")

if __name__ == "__main__":
    print("🤖 Super Bot Iniciado...")
    bot.infinity_polling()
