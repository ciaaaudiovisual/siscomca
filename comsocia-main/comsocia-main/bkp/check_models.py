import google.generativeai as genai
import tomllib

# Carrega a chave
with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
genai.configure(api_key=secrets["google"]["api_key"])

print("🔍 Listando modelos disponíveis para sua chave:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")