---
title: Siscomca
emoji: 🛡️
colorFrom: yellow
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Guia de Implantação SisCOMCA (Hugging Face Spaces)

Este documento descreve os passos para implantar o aplicativo **SisCOMCA (NiceGUI)** nos **Hugging Face Spaces** utilizando **Docker**, aproveitando a infraestrutura gratuita de **16GB de RAM**.

---

## 🚀 Requisitos Ambientais do Hugging Face

O Hugging Face Spaces impõe regras estritas para containers Docker:
1. **Porta Obrigatória (`7860`)**: O container deve expor e escutar exclusivamente na porta **`7860`**.
2. **Execução sem Root**: A infraestrutura do Hugging Face pode executar o container sob o usuário `user` com UID `1000`.

O repositório já está preparado e otimizado com essas configurações no `Dockerfile` e no `main.py`.

---

## 📦 Implantação no Hugging Face Spaces (Passo a Passo)

Siga as etapas abaixo para criar e implantar seu Space privado:

### Passo 1: Criando o Space no Hugging Face
1. Faça login na sua conta do **[Hugging Face](https://huggingface.co/)**.
2. Clique no seu perfil no canto superior direito e selecione **"New Space"**.
3. Defina as configurações iniciais:
   * **Space Name**: Nome de sua preferência (ex: `siscomca-app`).
   * **License**: Opcional (ex: `mit`).
   * **SDK**: Selecione **"Docker"**.
   * **Docker Template**: Selecione **"Blank"** (isso fará com que o Hugging Face leia diretamente o seu arquivo `Dockerfile` personalizado).
   * **Space Hardware**: Selecione a opção padrão gratuita (**Cpu basic - 2 vCPU - 16GB RAM**).
   * **Visibility**: Selecione **"Private"** (Garante total segurança de acesso aos dados militares do Corpo de Alunos).
4. Clique em **"Create Space"**.

### Passo 2: Vinculando o Repositório
* Você pode clonar o repositório do Space localmente e enviar o código via Git CLI, ou pode conectar o repositório através de uma ferramenta de Integração Contínua (CI).
* Para enviar diretamente via Git para o repositório do Hugging Face:
  ```bash
  git remote add hf https://huggingface.co/spaces/SEU_USUARIO/SEU_SPACE
  git push hf main --force
  ```

### Passo 3: Configuração de Variáveis e Segredos (Secrets)
No painel do seu Space criado, vá em **"Settings"** e localize a seção **"Variables and Secrets"**. Adicione os seguintes itens:

* **New Secret (Segredos Criptografados - recomendados para chaves e senhas)**:
  * `SUPABASE_URL`: *URL da API do seu Supabase*
  * `SUPABASE_KEY`: *Sua Service Role Key ou Anon Key*
  * `TELEGRAM_TOKEN`: *Token do seu bot do Telegram*
  * `STORAGE_SECRET`: *Uma chave secreta aleatória longa* (necessária para criptografar as sessões do NiceGUI e manter logins ativos).

### Passo 4: Exposição dos Áudios Estáticos
* Toda a pasta `/assets` (incluindo `/assets/sounds` com os arquivos `bell_single.mp3` e `bell_double.mp3`) é exposta e servida automaticamente.
* Para verificar a URL dos áudios expostos no Space, utilize o formato:
  `https://huggingface.co/spaces/SEU_USUARIO/SEU_SPACE/assets/sounds/bell_single.mp3`

---

## 🛠️ Execução Local de Teste (Porta 7860)

Se desejar testar a imagem localmente simulando as restrições da porta do Hugging Face:

1. **Construa a imagem**:
   ```bash
   docker build -t siscomca-hf .
   ```

2. **Rode o container na porta 7860**:
   ```bash
   docker run -d -p 7860:7860 --name siscomca_local --env-file .env -e PORT=7860 -e HOST=0.0.0.0 siscomca-hf
   ```

3. **Verifique se o aplicativo está online**:
   Acesse no navegador: `http://localhost:7860`
