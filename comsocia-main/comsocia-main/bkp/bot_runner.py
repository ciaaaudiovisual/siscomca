import telebot
import google.generativeai as genai
from supabase import create_client
import tomllib
from datetime import datetime

# Carregamento de chaves via secrets.toml
with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

bot = telebot.TeleBot(secrets["telegram"]["token"])
genai.configure(api_key=secrets["google"]["api_key"])
model = genai.GenerativeModel('models/gemini-2.5-flash')
db = create_client(secrets["supabase"]["url"], secrets["supabase"]["key"])

@bot.message_handler(func=lambda message: True)
def fluxo_principal(message):
    chat_id = str(message.chat.id)
    text = message.text.strip().lower()

    # 1. Verificar se o militar já está validado
    res = db.table("efetivo").select("*").eq("telegram_id", chat_id).execute()

    if not res.data:
        # Se mandou algo com @, tentamos validar o e-mail
        if "@" in text:
            check = db.table("efetivo").select("*").eq("email", text).execute()
            if check.data:
                db.table("efetivo").update({"telegram_id": chat_id}).eq("email", text).execute()
                bot.reply_to(message, f"✅ Acesso liberado, {check.data[0]['nome_guerra']}! Como posso ajudar hoje?")
            else:
                bot.reply_to(message, "❌ E-mail não autorizado. Fale com a equipe da ComSoc.")
        else:
            bot.reply_to(message, "⚓ Identifique-se informando seu **e-mail funcional** pré-cadastrado.")
        return

    # 2. Se validado, processa com a IA (Consultando a Agenda real)
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Busca agenda para o prompt
    agora = datetime.now().isoformat()
    agenda_res = db.table("agenda").select("*").gte("data_hora", agora).order("data_hora").limit(5).execute()
    contexto = str(agenda_res.data)

    prompt = f"Você é um assistente militar. Use estes dados de agenda: {contexto}. Pergunta: {message.text}"
    response = model.generate_content(prompt)
    bot.reply_to(message, response.text)

bot.polling()