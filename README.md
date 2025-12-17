# 🎓 TCC - ChatBot Acadêmico

<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-green.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![Rasa](https://img.shields.io/badge/Rasa-3.x-orange.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**Sistema completo de chatbot acadêmico para gestão universitária**

[Estrutura](#-estrutura-do-ecossistema) • [Instalação](#-instalação) • [Configuração](#-configuração) • [Uso](#-como-usar) • [Documentação](#-documentação)

</div>

---

## 📋 Sobre o Projeto

O **TCC - ChatBot Acadêmico** é um sistema completo desenvolvido para gerenciamento acadêmico universitário, composto por três componentes principais que trabalham em conjunto para fornecer uma solução robusta e integrada.

### 🎯 Objetivo

Fornecer uma plataforma completa que integra uma API REST (Backend), uma interface web administrativa (Frontend) e um chatbot inteligente baseado em IA (Rasa) para auxiliar alunos, professores e administradores no gerenciamento de informações acadêmicas.

### ✨ Características Principais

- ✅ **API REST completa** (FastAPI) para gerenciamento de dados acadêmicos
- ✅ **Interface web moderna** (Flask) para administração e visualização
- ✅ **Chatbot inteligente** (Rasa) com integração ao Telegram
- ✅ **Integração com IA** (Google Gemini) para processamento de documentos
- ✅ **Banco de dados** (Supabase) para persistência de dados
- ✅ **Autenticação e autorização** baseada em roles (Admin, Coordenador, Professor, Aluno)
- ✅ **Sistema de upload e processamento** de documentos acadêmicos

---

## 🏗️ Estrutura do Ecossistema

O projeto é composto por três componentes principais, cada um em sua própria pasta:

```
TCC-ChatBotAcademico/
│
├── chatbot_api/          # Backend API (FastAPI)
│   ├── src/              # Código fonte da API
│   ├── .venv_api/        # Ambiente virtual (não versionado)
│   └── requirements.txt  # Dependências da API
│
├── chatbot_rasa/         # Chatbot Rasa
│   ├── actions/          # Ações customizadas do bot
│   ├── data/             # Dados de treinamento (NLU, stories, rules)
│   ├── models/           # Modelos treinados (não versionado)
│   ├── .venv_rasa/       # Ambiente virtual (não versionado)
│   └── requirements.txt  # Dependências do Rasa
│
├── chatbot_web/          # Frontend Web (Flask)
│   ├── static/           # Arquivos estáticos (CSS, JS)
│   ├── templates/        # Templates HTML (Jinja2)
│   ├── venv_web/         # Ambiente virtual (não versionado)
│   └── requirements.txt  # Dependências do Flask
│
├── start_ecosystem.py    # Script para iniciar todo o ecossistema
├── supabase_bd.sql       # Schema do banco de dados
└── README.md             # Este arquivo
```

---

## 🛠️ Tecnologias Utilizadas

### Backend API (chatbot_api)
- **[FastAPI](https://fastapi.tiangolo.com/)** 0.116.1 - Framework web moderno e rápido
- **[Supabase](https://supabase.com/)** - Banco de dados PostgreSQL
- **[Google Gemini AI](https://ai.google.dev/)** - Processamento de IA
- **[Uvicorn](https://www.uvicorn.org/)** - Servidor ASGI

### Chatbot (chatbot_rasa)
- **[Rasa](https://rasa.com/)** 3.x - Framework de chatbot conversacional
- **[Telegram Bot API](https://core.telegram.org/bots/api)** - Integração com Telegram
- **[Python 3.10+](https://www.python.org/)** - Linguagem de programação

### Frontend Web (chatbot_web)
- **[Flask](https://flask.palletsprojects.com/)** 3.0.0 - Framework web Python
- **[Jinja2](https://jinja.palletsprojects.com/)** - Sistema de templates
- **HTML5/CSS3/JavaScript** - Frontend moderno e responsivo

---

## 📦 Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- **Python** 3.10 ou superior
- **pip** (gerenciador de pacotes Python)
- **Git** (para clonar o repositório)
- **Conta no Supabase** (para banco de dados)
- **Conta no Google Cloud** (para API do Gemini - opcional)
- **Bot do Telegram** (criado via @BotFather - para o chatbot)

### Verificação de Versão

```bash
python --version  # Deve retornar Python 3.10+
pip --version     # Verifica se pip está instalado
git --version     # Verifica se Git está instalado
```

---

## 🚀 Instalação

### 1. Clone o Repositório

```bash
git clone <url-do-repositorio>
cd TCC-ChatBotAcademico
```

### 2. Instalação Individual dos Componentes

Cada componente precisa ser configurado separadamente. Siga as seções abaixo para cada um.

---

## ⚙️ Configuração

### 🔧 Backend API (chatbot_api)

#### 1. Navegue para a pasta da API

```bash
cd chatbot_api
```

#### 2. Crie e ative o ambiente virtual

**Windows:**
```bash
python -m venv .venv_api
.venv_api\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv_api
source .venv_api/bin/activate
```

#### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

#### 4. Configure o arquivo `.env`

Crie um arquivo `.env` na pasta `chatbot_api/` com as seguintes variáveis:

```env
# ============================================
# Configurações do Supabase
# ============================================
SUPABASE_URL=sua-url-do-supabase
SUPABASE_SERVICE_KEY=sua-service-key-do-supabase
SUPABASE_ANON_KEY=sua-anon-key-do-supabase

# ============================================
# Configurações do Google Gemini
# ============================================
GOOGLE_API_KEY=sua-chave-api-do-google-gemini

# ============================================
# Configurações do Watcher (opcional)
# ============================================
WATCHER_TARGET_FOLDER=./temporary_documents_folder
```

**⚠️ IMPORTANTE:** O arquivo `.env` não deve ser commitado no Git (já está no `.gitignore`).

#### 5. Execute o servidor da API

```bash
# Opção 1: Com reload automático
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Opção 2: Com reload apenas da pasta src
python -m uvicorn src.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000
```

A API estará disponível em: **http://localhost:8000**

**Documentação interativa da API:** http://localhost:8000/docs

---

### 🤖 Chatbot Rasa (chatbot_rasa)

#### 1. Navegue para a pasta do Rasa

```bash
cd chatbot_rasa
```

#### 2. Crie e ative o ambiente virtual

**Windows:**
```bash
python -m venv .venv_rasa
.venv_rasa\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv_rasa
source .venv_rasa/bin/activate
```

#### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

**⚠️ Nota:** A instalação do Rasa pode levar alguns minutos e requer Visual Studio Build Tools no Windows.

**📌 Observação Importante sobre o requirements.txt:**
O arquivo `requirements.txt` do Rasa está configurado para ambiente **Linux (WSL)**. Se você estiver instalando no **Windows**, será necessário adicionar a biblioteca `uvloop` ao instalar as dependências:

```bash
# Instalar dependências do requirements.txt
pip install -r requirements.txt

# Adicionar uvloop para Windows
pip install uvloop
```

Ou instale tudo de uma vez:
```bash
pip install -r requirements.txt uvloop
```

#### 4. Configure o arquivo `.env`

Execute o script de configuração:

```bash
python setup_env.py
```

Ou crie manualmente um arquivo `.env` na pasta `chatbot_rasa/`:

```env
# ============================================
# Configurações do Telegram para Rasa
# ============================================
TELEGRAM_ACCESS_TOKEN=seu-token-do-telegram
TELEGRAM_VERIFY=seu-verify-string
TELEGRAM_WEBHOOK_URL=https://seu-ngrok-id.ngrok-free.app/webhooks/telegram/webhook
```

**Como obter o token do Telegram:**
1. Abra o Telegram e procure por @BotFather
2. Envie `/newbot` e siga as instruções
3. Copie o token fornecido

#### 5. Treine o modelo (primeira vez ou após alterações)

```bash
rasa train
```

#### 6. Execute os servidores do Rasa

**Opção 1: Usando o script automatizado (recomendado)**

```bash
python start_rasa.py
```

Este script inicia automaticamente:
- Servidor de Actions (porta 5055)
- Servidor Principal do Rasa (porta 5005)

**Opção 2: Manualmente**

Terminal 1 - Servidor de Actions:
```bash
rasa run actions
```

Terminal 2 - Servidor Principal:
```bash
rasa run -m models --enable-api --cors "*" --credentials credentials.yml.processed
```

**Opção 3: Shell interativo para testes**

```bash
rasa shell
```

#### 7. Configurar ngrok (para webhook do Telegram)

Se você deseja conectar o bot ao Telegram, precisará de um túnel ngrok:

1. **Baixe e instale o ngrok:** https://ngrok.com/

2. **Inicie o ngrok apontando para a porta do Rasa:**
```bash
ngrok http 5005
```

3. **Copie a URL HTTPS fornecida** (exemplo: `https://abc123.ngrok-free.app`)

4. **Atualize o arquivo `.env`** com a URL completa:
```env
TELEGRAM_WEBHOOK_URL=https://abc123.ngrok-free.app/webhooks/telegram/webhook
```

5. **Reinicie os servidores do Rasa**

---

### 🌐 Frontend Web (chatbot_web)

#### 1. Navegue para a pasta do Flask

```bash
cd chatbot_web
```

#### 2. Crie e ative o ambiente virtual

**Windows:**
```bash
python -m venv venv_web
venv_web\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv_web
source venv_web/bin/activate
```

#### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

#### 4. Configure o arquivo `.env`

Crie um arquivo `.env` na pasta `chatbot_web/`:

```env
# ============================================
# ⚠️ VARIÁVEIS OBRIGATÓRIAS
# ============================================

# Chave secreta para criptografia de sessões Flask
# Gere uma chave segura usando:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=sua-chave-secreta-aqui

# URL base da API Backend (ChatBot_API)
API_BASE_URL=http://127.0.0.1:8000

# ============================================
# Configurações Opcionais
# ============================================
FLASK_APP=app.py
FLASK_ENV=development
DEBUG=True
```

**Gerar SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### 5. Execute o servidor Flask

```bash
# Opção 1: Usando Flask CLI
flask run

# Opção 2: Usando Python diretamente
python app.py
```

O painel web estará disponível em: **http://127.0.0.1:5000**

---

## 🎮 Como Usar

### 🚀 Iniciar Todo o Ecossistema

Para iniciar todos os componentes de uma vez, use o script na raiz do projeto:

```bash
# Na raiz do projeto
python start_ecosystem.py
```

**Com URL do ngrok:**
```bash
python start_ecosystem.py --ngrok-url https://seu-ngrok-id.ngrok-free.app
```

Este script:
- ✅ Verifica e cria ambientes virtuais se necessário
- ✅ Inicia a API FastAPI (porta 8000)
- ✅ Inicia os servidores do Rasa (portas 5055 e 5005)
- ✅ Inicia o servidor Flask (porta 5000)
- ✅ Exibe logs de todos os serviços em tempo real
- ✅ Para todos os serviços com Ctrl+C

### 📊 Serviços Disponíveis

Após iniciar o ecossistema, os seguintes serviços estarão disponíveis:

| Serviço | URL | Descrição |
|---------|-----|-----------|
| **API FastAPI** | http://localhost:8000 | Backend REST API |
| **API Docs** | http://localhost:8000/docs | Documentação interativa da API |
| **Rasa Actions** | http://localhost:5055 | Servidor de ações customizadas |
| **Rasa Server** | http://localhost:5005 | Servidor principal do chatbot |
| **Flask Panel** | http://localhost:5000 | Interface web administrativa |

### 🔧 Comandos Úteis

#### API (chatbot_api)

```bash
# Ativar ambiente virtual
cd chatbot_api
.venv_api\Scripts\activate  # Windows
source .venv_api/bin/activate  # Linux/Mac

# Executar servidor
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Atualizar requirements.txt
pip freeze > requirements.txt
```

#### Rasa (chatbot_rasa)

```bash
# Ativar ambiente virtual
cd chatbot_rasa
.venv_rasa\Scripts\activate  # Windows
source .venv_rasa/bin/activate  # Linux/Mac

# Treinar modelo
rasa train

# Executar servidor de actions
rasa run actions

# Executar servidor principal
rasa run -m models --enable-api --cors "*" --credentials credentials.yml.processed

# Shell interativo para testes
rasa shell

# Usar script automatizado (recomendado)
python start_rasa.py
```

#### Flask (chatbot_web)

```bash
# Ativar ambiente virtual
cd chatbot_web
venv_web\Scripts\activate  # Windows
source venv_web/bin/activate  # Linux/Mac

# Executar servidor
flask run
# ou
python app.py
```

---

## 📁 Estrutura Detalhada do Projeto

```
TCC-ChatBotAcademico/
│
├── chatbot_api/                    # Backend API
│   ├── src/
│   │   ├── main.py                # Ponto de entrada da API
│   │   ├── config.py              # Configurações
│   │   ├── supabase_client.py     # Cliente Supabase
│   │   ├── routers/               # Rotas da API
│   │   │   ├── auth.py           # Autenticação
│   │   │   ├── alunos.py         # Gerenciamento de alunos
│   │   │   ├── professores.py    # Gerenciamento de professores
│   │   │   ├── aviso.py          # Avisos acadêmicos
│   │   │   ├── documento.py      # Upload de documentos
│   │   │   └── ...
│   │   └── schemas/               # Schemas Pydantic
│   ├── temporary_documents_folder/ # Pasta temporária para documentos
│   ├── .env                       # Variáveis de ambiente (não versionado)
│   └── requirements.txt
│
├── chatbot_rasa/                   # Chatbot Rasa
│   ├── actions/
│   │   └── actions.py            # Ações customizadas
│   ├── data/
│   │   ├── nlu.yml               # Dados de NLU (intenções)
│   │   ├── stories.yml           # Histórias de conversação
│   │   └── rules.yml             # Regras de diálogo
│   ├── models/                    # Modelos treinados (não versionado)
│   ├── credentials.yml           # Configuração de credenciais (template)
│   ├── credentials.yml.processed # Credenciais processadas (não versionado)
│   ├── domain.yml                # Domínio do bot
│   ├── config.yml                # Configuração do Rasa
│   ├── endpoints.yml             # Endpoints do Rasa
│   ├── start_rasa.py             # Script para iniciar servidores
│   ├── setup_env.py              # Script de configuração
│   ├── .env                      # Variáveis de ambiente (não versionado)
│   └── requirements.txt
│
├── chatbot_web/                    # Frontend Web
│   ├── static/
│   │   ├── css/                  # Folhas de estilo
│   │   └── js/                   # JavaScript
│   ├── templates/
│   │   ├── login.html           # Página de login
│   │   ├── dashboard.html       # Dashboard principal
│   │   ├── avisos/              # Templates de avisos
│   │   ├── conteudo/            # Templates de conteúdo
│   │   ├── docentes/            # Templates de docentes
│   │   ├── calendario/          # Templates de calendário
│   │   └── infos_curso/         # Templates de informações
│   ├── app.py                   # Aplicação Flask principal
│   ├── .env                     # Variáveis de ambiente (não versionado)
│   └── requirements.txt
│
├── start_ecosystem.py             # Script para iniciar todo o ecossistema
├── supabase_bd.sql                # Schema do banco de dados
├── .gitignore                     # Arquivos ignorados pelo Git
└── README.md                      # Este arquivo
```

---

## 🔌 Integração entre Componentes

```
┌─────────────────┐
│   Telegram      │
│     Bot         │
└────────┬────────┘
         │
         │ Webhook
         ▼
┌─────────────────┐      ┌─────────────────┐
│   Rasa Server   │◄────►│  Rasa Actions   │
│   (porta 5005)  │      │  (porta 5055)   │
└────────┬────────┘      └─────────────────┘
         │
         │ API Calls
         ▼
┌─────────────────┐
│   FastAPI       │◄────►│   Supabase      │
│   (porta 8000)  │      │   Database      │
└────────┬────────┘      └─────────────────┘
         │
         │ HTTP Requests
         ▼
┌─────────────────┐
│   Flask Web     │
│   (porta 5000)  │
└─────────────────┘
```

---

## 🐛 Troubleshooting

### Problema: Erro ao instalar dependências do Rasa

**Solução:**
- No Windows, instale o Visual Studio Build Tools
- Certifique-se de estar usando Python 3.10+
- Tente instalar dependências uma de cada vez

### Problema: Erro ao conectar com a API

**Solução:**
- Verifique se a API está rodando na porta 8000
- Verifique a configuração de `API_BASE_URL` no `.env` do Flask
- Verifique os logs do servidor da API

### Problema: Chatbot não responde no Telegram

**Solução:**
- Verifique se o ngrok está rodando e acessível
- Verifique se a URL do webhook no `.env` está correta
- Verifique se os servidores do Rasa estão rodando
- Verifique os logs do Rasa para erros

### Problema: Erro 401 - Não autorizado

**Solução:**
- Verifique se o token de acesso está sendo enviado corretamente
- Faça logout e login novamente no painel web
- Verifique se as credenciais estão corretas

### Problema: Modelo do Rasa não encontrado

**Solução:**
```bash
cd chatbot_rasa
source .venv_rasa/bin/activate  # ou .venv_rasa\Scripts\activate no Windows
rasa train
```

### Problema: Porta já em uso

**Solução:**
```bash
# Windows
netstat -ano | findstr ":8000"
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

---

## 📝 Variáveis de Ambiente Necessárias

### chatbot_api/.env
```env
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_ANON_KEY=
GOOGLE_API_KEY=
WATCHER_TARGET_FOLDER=./temporary_documents_folder
```

### chatbot_rasa/.env
```env
TELEGRAM_ACCESS_TOKEN=
TELEGRAM_VERIFY=
TELEGRAM_WEBHOOK_URL=
```

### chatbot_web/.env
```env
SECRET_KEY=
API_BASE_URL=http://127.0.0.1:8000
FLASK_APP=app.py
FLASK_ENV=development
DEBUG=True
```

---

## 🔒 Segurança

⚠️ **IMPORTANTE:**

- **NUNCA** faça commit de arquivos `.env` no repositório
- **NUNCA** compartilhe chaves API, tokens ou senhas publicamente
- Use diferentes chaves para desenvolvimento e produção
- O arquivo `.gitignore` na raiz protege arquivos sensíveis
- Gere `SECRET_KEY` forte usando: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## 📚 Documentação Adicional

- **API Documentation:** http://localhost:8000/docs (quando a API estiver rodando)
- **Rasa Documentation:** https://rasa.com/docs/
- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **Flask Documentation:** https://flask.palletsprojects.com/

---

## 🤝 Contribuindo

1. **Fork** o projeto
2. Crie uma **branch** para sua feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. **Push** para a branch (`git push origin feature/AmazingFeature`)
5. Abra um **Pull Request**

### Padrões de Código

- Siga o estilo PEP 8 para Python
- Use nomes descritivos para variáveis e funções
- Adicione comentários quando necessário
- Mantenha o código limpo e legível

---

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

## 👥 Autores

- **Equipe de Desenvolvimento** - *Desenvolvimento do TCC*

---

## 📞 Contato

Para dúvidas, sugestões ou problemas:

- **GitHub Issues:** [Abrir uma issue](https://github.com/seu-usuario/TCC-ChatBotAcademico/issues)

---

<div align="center">

**⭐ Se este projeto foi útil para você, considere dar uma estrela! ⭐**

Feito com ❤️ pela equipe do TCC - ChatBot Acadêmico

</div>

