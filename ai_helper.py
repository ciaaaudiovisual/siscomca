import os
import warnings
# Silenciar avisos de depreciação do pacote google.generativeai
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or ""

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Define o modelo padrão de baixo custo/quase custo zero em 2026: Gemini 2.0 Flash
MODEL_NAME = "gemini-2.0-flash"


def summarize_text(text: str, lang: str = 'pt-BR') -> str:
    """Resume um texto usando Gemini"""
    if not GOOGLE_API_KEY:
        return "API Key não configurada"
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""Resuma o texto abaixo de forma clara e concisa em {lang}.
Retorne apenas o resumo, sem introduções.

Texto:
{text}"""
        
        response = model.generate_content(prompt)
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        return f"Erro ao resumir: {str(e)}"


def translate_text(text: str, target_lang: str = 'en') -> str:
    """Traduz texto usando Gemini"""
    if not GOOGLE_API_KEY:
        return "API Key não configurada"
    
    lang_map = {
        'en': 'Inglês',
        'es': 'Espanhol',
        'fr': 'Francês',
        'de': 'Alemão',
        'it': 'Italiano',
        'pt': 'Português',
    }
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""Traduza o texto abaixo para {lang_map.get(target_lang, target_lang)}.
Retorne apenas a tradução, sem explicações.

Texto original:
{text}"""
        
        response = model.generate_content(prompt)
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        return f"Erro ao traduzir: {str(e)}"


def improve_text(text: str, style: str = 'military') -> str:
    """Melhora/corrige texto usando Gemini"""
    if not GOOGLE_API_KEY:
        return "API Key não configurada"
    
    styles = {
        'formal': 'formal e profissional',
        'simple': 'simples e fácil de entender',
        'military': 'típico de comunicação e redação militar da Marinha do Brasil',
    }
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""Reescreva o texto abaixo de forma {styles.get(style, style)}.
Mantenha o significado original. Retorne apenas o texto reescrito.

Texto:
{text}"""
        
        response = model.generate_content(prompt)
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        return f"Erro ao melhorar texto: {str(e)}"


def generate_image_caption(image_url: str = None, description: str = None) -> str:
    """Gera legenda para imagem (requer URL ou descrição)"""
    if not GOOGLE_API_KEY:
        return "API Key não configurada"
    
    if not image_url and not description:
        return "Forneça URL da imagem ou descrição"
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        if image_url:
            prompt = "Descreva esta imagem em português brasileiro de forma clara e objetiva."
            response = model.generate_content([prompt, image_url])
        else:
            prompt = f"Gere uma legenda criativa e profissional para uma imagem que mostra: {description}"
            response = model.generate_content(prompt)
        
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        return f"Erro ao gerar legenda: {str(e)}"


def chat_with_ai(message: str, context: str = '') -> str:
    """Chatbot interno com contexto voltado para a Marinha do Brasil"""
    if not GOOGLE_API_KEY:
        return "API Key não configurada"
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        system_prompt = f"""Você é um assistente virtual do Corpo de Alunos da Marinha do Brasil.
Ajude militares com informações sobre regulamentos (especialmente o RDM - Regulamento Disciplinar da Marinha), diretrizes, redação de documentos (como Partes de Ocorrência) e dúvidas gerais do dia a dia naval.
Mantenha um tom formal, prestativo, extremamente profissional e confidencial.
Contexto adicional: {context}"""
        
        chat = model.start_chat(history=[
            {'role': 'user', 'parts': [system_prompt]},
            {'role': 'model', 'parts': ['Entendido. Estou pronto para atuar como o Assistente Disciplinar e Geral do Corpo de Alunos da Marinha do Brasil. Como posso ajudar o senhor hoje?']}
        ])
        
        response = chat.send_message(message)
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        return f"Erro: {str(e)}"


def analyze_sentiment(text: str) -> dict:
    """Analisa sentimento de um texto"""
    if not GOOGLE_API_KEY:
        return {"sentimento": "indisponivel", "nota": 0}
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""Analise o sentimento do texto abaixo e retorne APENAS um JSON com:
        - "sentimento": "positivo", "negativo" ou "neutro"
        - "nota": número de 0 a 10
        
        Texto: {text}"""
        
        response = model.generate_content(prompt)
        
        text_response = response.candidates[0].content.parts[0].text.lower()
        if 'positivo' in text_response:
            return {"sentimento": "positivo", "nota": 8}
        elif 'negativo' in text_response:
            return {"sentimento": "negativo", "nota": 3}
        else:
            return {"sentimento": "neutro", "nota": 5}
    except:
        return {"sentimento": "neutro", "nota": 5}


def generate_disciplinary_report(student_name: str, student_history: str, new_fact: str, regulation: str = "RDM") -> str:
    """Gera uma Parte de Ocorrência formal e propõe sanções baseadas no regulamento naval (RDM) e no histórico do aluno"""
    if not GOOGLE_API_KEY:
        return "API Key não configurada"
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""Você é um oficial experiente e Assessor Disciplinar/Jurídico da Marinha do Brasil (MB).
Seu objetivo é analisar um fato recente envolvendo o aluno {student_name}, verificar se há reincidência com base no histórico comportamental real fornecido, formular a redação oficial de uma "Parte de Ocorrência" no padrão da Marinha do Brasil e propor a recomendação da sanção disciplinar correta sob o {regulation} (Regulamento Disciplinar da Marinha).

### DADOS DO MILITAR:
- Nome/Identificação: {student_name}
- Histórico Comportamental Pretérito (FAIA):
{student_history if student_history else "Nenhuma ocorrência registrada anteriormente. Bons antecedentes (comportamento exemplar)."}

### FATO RECENTE OCORRIDO:
"{new_fact}"

### Instruções Importantes:
1. **Identifique a Reincidência**: Analise o histórico do aluno. Destaque expressamente se ele já cometeu contravenções disciplinares de natureza semelhante ou se possui outros registros de comportamento que configurem circunstâncias agravantes. Se o histórico estiver limpo, cite isso como atenuante de primeira contravenção.
2. **Redação da Parte de Ocorrência**: Escreva o texto formal em linguagem e formato estritamente navais no padrão da Marinha do Brasil (conciso, direto, impessoal, indicando fato, data, hora, local, circunstâncias e as normas infringidas do RDM, sem adjetivações emocionais). Use o cabeçalho clássico de Parte de Ocorrência Naval se necessário.
3. **Enquadramento Disciplinar**: Sugira o enquadramento regulamentar plausível sob o {regulation} (mencionando o artigo específico da contravenção disciplinar e classificando-a em leve, média ou grave).
4. **Sanção Disciplinar Recomendada**: Indique uma sanção ou medida corretiva recomendada nos termos do RDM (ex: repreensão, impedimento, detenção, etc.), justificando a dosagem de acordo com os agravantes (reincidência) ou atenuantes.

Retorne sua resposta formatada em Markdown de forma muito elegante e profissional, utilizando as seguintes seções literais:
- **1. REDAÇÃO DA PARTE DE OCORRÊNCIA** (Texto formal de comunicação oficial pronto para ser copiado e encaminhado)
- **2. ANÁLISE DE HISTÓRICO E REINCIDÊNCIA** (Análise dos antecedentes como subsídio legal para sanções navais)
- **3. ENQUADRAMENTO REGULAMENTAR ({regulation})** (Possível artigo, gravidade e infração do Regulamento Disciplinar da Marinha)
- **4. RECOMENDAÇÃO DE MEDIDA DISCIPLINAR** (Sugestão da dosagem de punição com justificativa baseada no RDM)
"""
        response = model.generate_content(prompt)
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        return f"Erro ao gerar parecer disciplinar: {str(e)}"


@lru_cache(maxsize=128)
def rewrite_to_jarvis_alert(title: str) -> str:
    """Reescreve um título de ocorrência no estilo da voz do J.A.R.V.I.S. (do Homem de Ferro)."""
    if not GOOGLE_API_KEY:
        return f"{title}."
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""Você é o J.A.R.V.I.S., a inteligência artificial desenvolvida por Tony Stark.
Sua tarefa é reescrever o título de notificação abaixo para ser anunciado por você nos auto-falantes de forma extremamente curta e concisa para economizar consumo de caracteres.

### Diretrizes de Personalidade do J.A.R.V.I.S.:
1. Responda sempre com extrema polidez e formalidade.
2. NÃO use a palavra "Senhor", "Sir" ou similares em nenhuma circunstância.
3. NÃO use a palavra "Atenção" em nenhuma circunstância.
4. Mantenha um tom sereno, controlado e analítico.
5. O texto deve ser o mais curto, direto e enxuto possível, limitando-se a exatamente 3 ou 4 palavras para minimizar o consumo de créditos de voz.
6. Remova emojis ou caracteres especiais do texto resultante.
7. Retorne APENAS a reescrita direta na voz do JARVIS, sem aspas adicionais, sem preâmbulos ou explicações.

### Título a ser reescrito:
{title}

Exemplos de Saída curtas:
- "Novo aviso publicado."
- "Alta médica confirmada."
- "Registro de ocorrência."
- "Dispensa médica registrada."
"""
        response = model.generate_content(prompt)
        text = response.candidates[0].content.parts[0].text.strip()
        # Remove eventuais aspas externas
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1].strip()
        return text
    except Exception as e:
        print(f"[JARVIS IA] Erro ao reescrever alerta: {e}")
        return f"{title}."


ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY") or ""
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID") or "N2lVS1w4EtoT3dr4eOWO" # Callum (British)


@lru_cache(maxsize=128)
def generate_elevenlabs_tts(text: str) -> str:
    """Gera áudio TTS via ElevenLabs em formato base64 se a chave estiver configurada."""
    if not ELEVENLABS_API_KEY or not text:
        return ""
        
    import requests
    import base64
    
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.8,
                "similarity_boost": 0.85
            }
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=8)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')
        else:
            print(f"[ELEVENLABS] Erro HTTP {response.status_code}: {response.text}")
            return ""
    except Exception as e:
        print(f"[ELEVENLABS] Erro na API do ElevenLabs: {e}")
        return ""


