# Usa uma imagem oficial leve do Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do servidor do Hugging Face
WORKDIR /app

# Copia o arquivo de dependências primeiro (otimiza o carregamento)
COPY requirements.txt .

# Instala as dependências do seu siscomca
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do seu código para dentro do container
COPY . .

# EXTREMAMENTE IMPORTANTE: O Hugging Face Free exige que o app rode na porta 7860
EXPOSE 7860

# Comando para rodar o seu script principal (ajuste 'main.py' se o seu arquivo tiver outro nome)
CMD ["python", "main.py"]
