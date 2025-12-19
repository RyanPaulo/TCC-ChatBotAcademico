# 🤖 ChatBot Acadêmico - Rasa

<div align="center">

![Rasa](https://img.shields.io/badge/Rasa-3.6.14-orange.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**Chatbot inteligente baseado em Rasa para assistência acadêmica universitária**

[Instalação](#-instalação) • [Configuração](#-configuração) • [Uso](#-como-usar) • [Arquitetura](#-arquitetura-do-chatbot)

</div>

---

## 📋 Sobre o Chatbot

O **ChatBot Acadêmico** é um assistente conversacional inteligente desenvolvido com **Rasa 3.x** que auxilia alunos, professores e coordenadores em questões acadêmicas através do Telegram. O bot utiliza processamento de linguagem natural (NLP) e machine learning para entender intenções, extrair entidades e manter conversas contextuais.

### 🎯 Funcionalidades Principais

- ✅ **Autenticação segura** via email institucional e validação de RA
- ✅ **Consulta de informações acadêmicas** (avisos, cronogramas, avaliações)
- ✅ **Busca de conteúdo** usando IA (Google Gemini)
- ✅ **Gerenciamento de atividades acadêmicas** (TCC, APS, Estágio, Horas Complementares)
- ✅ **Consulta de informações de docentes** (horários de atendimento, contatos)
- ✅ **Busca de materiais e ementas** de disciplinas
- ✅ **Sistema de inatividade** com deslogamento automático após 10 minutos
- ✅ **Integração completa** com a API Backend (FastAPI)

---

## 🧠 O que é o Rasa e Como Funciona?

### O que é Rasa?

**Rasa** é um framework open-source para construção de assistentes conversacionais baseados em IA. Ele permite criar chatbots que:

- **Entendem linguagem natural** (NLU - Natural Language Understanding)
- **Mantêm contexto** durante conversas
- **Aprendem com exemplos** através de machine learning
- **Executam ações customizadas** em Python

### Arquitetura do Rasa

O Rasa é composto por três componentes principais:

#### 1. **NLU (Natural Language Understanding)**
- **Função:** Entende a intenção do usuário e extrai entidades
- **Exemplo:** "Quando é a prova de Sistemas Distribuídos?"
  - **Intenção:** `consultar_data_avaliacao`
  - **Entidades:** `disciplina: Sistemas Distribuídos`

#### 2. **Core (Gerenciamento de Diálogo)**
- **Função:** Decide qual ação tomar baseado no contexto da conversa
- **Componentes:**
  - **Stories:** Exemplos de conversas para treinar o modelo
  - **Rules:** Regras fixas de comportamento
  - **Policies:** Algoritmos de ML que decidem a próxima ação

#### 3. **Actions (Ações Customizadas)**
- **Função:** Executa lógica customizada em Python
- **Exemplo:** Buscar dados na API, fazer cálculos, enviar mensagens

### Como o Chatbot Funciona?

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUXO DE UMA CONVERSA                     │
└─────────────────────────────────────────────────────────────┘

1. Usuário envia mensagem no Telegram
   ↓
2. Telegram envia mensagem para Rasa Server (webhook)
   ↓
3. Rasa Server processa a mensagem:
   ├─ NLU: Identifica intenção e entidades
   ├─ Core: Decide qual ação executar
   └─ Actions: Executa lógica customizada (se necessário)
   ↓
4. Actions Server faz requisições à API Backend (se necessário)
   ↓
5. Rasa Server envia resposta ao Telegram
   ↓
6. Usuário recebe resposta no Telegram
```

### Componentes do Projeto

#### 📁 Estrutura de Arquivos

```
chatbot_rasa/
│
├── actions/                    # Ações customizadas em Python
│   └── actions.py            # Todas as ações do bot (3900+ linhas)
│
├── data/                      # Dados de treinamento
│   ├── nlu.yml               # Exemplos de intenções e entidades
│   ├── stories.yml           # Histórias de conversação
│   └── rules.yml             # Regras de diálogo
│
├── models/                    # Modelos treinados (gerados automaticamente)
│   └── *.tar.gz              # Modelos compilados
│
├── config.yml                 # Configuração do pipeline NLU e políticas
├── domain.yml                 # Domínio do bot (intenções, entidades, ações)
├── endpoints.yml              # Endpoints (Actions Server, etc)
├── credentials.yml            # Template de credenciais (Telegram)
├── credentials.yml.processed  # Credenciais processadas (gerado automaticamente)
│
├── setup_env.py               # Script para configurar variáveis de ambiente
├── start_rasa.py              # Script para iniciar servidores automaticamente
├── requirements.txt           # Dependências Python
└── .env                       # Variáveis de ambiente (não versionado)
```

#### 🔧 Arquivos de Configuração

**config.yml** - Define o pipeline de NLU e políticas:
- **Pipeline NLU:** Tokenização, featurização, classificação de intenções
- **Policies:** MemoizationPolicy, RulePolicy, TEDPolicy, UnexpecTEDIntentPolicy

**domain.yml** - Define o domínio do bot:
- **Intenções:** O que o usuário pode querer fazer
- **Entidades:** Informações extraídas das mensagens
- **Ações:** Ações que o bot pode executar
- **Respostas:** Templates de mensagens

**endpoints.yml** - Configura endpoints externos:
- **action_endpoint:** URL do servidor de Actions (porta 5055)

**credentials.yml** - Configuração de canais (Telegram):
- Token do bot
- Webhook URL
- String de verificação

---

## 🏗️ Arquitetura do Chatbot

### Componentes e Comunicação

```
┌─────────────────────────────────────────────────────────────┐
│                        TELEGRAM                              │
│                    (Interface do Usuário)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Webhook HTTPS
                        │ (via ngrok)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    RASA SERVER                              │
│                  (Porta 5005)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │     NLU      │  │     Core     │  │   Actions   │      │
│  │  (Intenções) │  │  (Diálogo)   │  │  (Lógica)   │      │
│  └──────────────┘  └──────────────┘  └──────┬───────┘      │
└─────────────────────────────────────────────┼──────────────┘
                                               │
                                               │ HTTP
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  ACTIONS SERVER                             │
│                  (Porta 5055)                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  actions/actions.py                                  │  │
│  │  - Autenticação                                      │  │
│  │  - Busca de informações                              │  │
│  │  - Integração com API                                │  │
│  │  - Geração de respostas com IA                       │  │
│  └──────────────────┬───────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────────┘
                      │
                      │ HTTP REST API
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  API BACKEND (FastAPI)                      │
│                  (Porta 8000)                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - Autenticação de usuários                          │  │
│  │  - Gerenciamento de dados acadêmicos                 │  │
│  │  - Processamento de IA (Gemini)                      │  │
│  │  - Integração com Supabase                           │  │
│  └──────────────────┬───────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────────┘
                      │
                      │ SQL/PostgreSQL
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      SUPABASE                               │
│                  (Banco de Dados)                           │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Autenticação

```
1. Usuário envia saudação
   ↓
2. Bot solicita email institucional
   ↓
3. Bot busca aluno na API por email
   ↓
4. Bot gera pergunta aleatória sobre RA:
   - Primeiros N dígitos
   - Últimos N dígitos
   - Dígito em posição específica
   - RA completo (menos frequente)
   ↓
5. Usuário responde
   ↓
6. Bot valida resposta na API
   ↓
7. Se correto: Autentica e permite acesso
   Se incorreto: Nova pergunta ou erro
   ↓
8. Bot deleta mensagens sensíveis do Telegram
```

### Sistema de Inatividade

- **Timeout:** 10 minutos de inatividade
- **Verificação:** A cada interação do usuário
- **Ação:** Deslogamento automático e limpeza de sessão
- **Segurança:** Previne acesso não autorizado

---

## 🛠️ Tecnologias Utilizadas

- **[Rasa 3.6.14](https://rasa.com/)** - Framework de chatbot conversacional
- **[Rasa SDK 3.6.2](https://rasa.com/docs/rasa-sdk/)** - SDK para ações customizadas
- **[Python 3.10+](https://www.python.org/)** - Linguagem de programação
- **[Telegram Bot API](https://core.telegram.org/bots/api)** - Integração com Telegram
- **[FastAPI](https://fastapi.tiangolo.com/)** - Cliente HTTP para API Backend
- **[Supabase](https://supabase.com/)** - Cliente para banco de dados (via API)
- **[Google Gemini AI](https://ai.google.dev/)** - Processamento de IA (via API)
- **[python-dotenv](https://pypi.org/project/python-dotenv/)** - Gerenciamento de variáveis de ambiente

---

## 📦 Pré-requisitos

Antes de começar, certifique-se de ter:

- **Python 3.10 ou superior**
- **pip** (gerenciador de pacotes Python)
- **Git** (para clonar o repositório)
- **Bot do Telegram** (criado via @BotFather)
- **ngrok** (para webhook do Telegram - opcional, mas recomendado)
- **API Backend rodando** (porta 8000)

### Verificação de Versão

```bash
python --version  # Deve retornar Python 3.10+
pip --version     # Verifica se pip está instalado
```

---

## 🚀 Instalação

### 1. Navegue para a pasta do Rasa

```bash
cd chatbot_rasa
```

### 2. Crie e ative o ambiente virtual

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

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

**⚠️ Nota Importante:**
- A instalação do Rasa pode levar **10-15 minutos**
- No **Windows**, pode ser necessário instalar **Visual Studio Build Tools**
- No **Linux (WSL)**, a instalação é mais rápida

**📌 Observação sobre uvloop:**
O arquivo `requirements.txt` está configurado para ambiente **Linux (WSL)**. Se você estiver no **Windows**, pode ser necessário instalar `uvloop` separadamente:

```bash
# Instalar dependências do requirements.txt
pip install -r requirements.txt

# Adicionar uvloop para Windows (se necessário)
pip install uvloop
```

---

## ⚙️ Configuração

### 1. Configure as variáveis de ambiente

**Opção 1: Usando o script automatizado (recomendado)**

```bash
python setup_env.py
```

Este script cria automaticamente o arquivo `.env` com valores padrão.

**Opção 2: Criar manualmente**

Crie um arquivo `.env` na pasta `chatbot_rasa/`:

```env
# ============================================
# Configurações do Telegram para Rasa
# ============================================
# ⚠️ IMPORTANTE: Este arquivo contém informações sensíveis
# NUNCA compartilhe este arquivo ou faça commit no repositório

# Token de acesso do bot do Telegram
# Obtenha este token criando um bot com @BotFather no Telegram
TELEGRAM_ACCESS_TOKEN=seu-token-do-telegram

# String de verificação do webhook
# Pode ser qualquer string, mas deve ser única e segura
TELEGRAM_VERIFY=UnipChatBot

# URL do webhook do Telegram
# Esta URL deve apontar para o endpoint do Rasa
# Exemplo com ngrok: https://<seu-ngrok-id>.ngrok-free.app/webhooks/telegram/webhook
TELEGRAM_WEBHOOK_URL=https://seu-ngrok-id.ngrok-free.app/webhooks/telegram/webhook
```

### 2. Como obter o token do Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie o comando `/newbot`
3. Siga as instruções para criar um bot
4. Copie o **token** fornecido
5. Cole o token no arquivo `.env` em `TELEGRAM_ACCESS_TOKEN`

### 3. Configure o ngrok (para webhook do Telegram)

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

5. **Reinicie os servidores do Rasa** após atualizar o `.env`

**⚠️ IMPORTANTE:** 
- A URL do ngrok muda a cada vez que você reinicia o ngrok (versão gratuita)
- Para produção, considere usar um plano pago do ngrok ou um servidor com IP fixo

---

## 🎮 Como Usar

### Treinar o Modelo

Antes de usar o bot pela primeira vez ou após fazer alterações nos dados de treinamento:

```bash
# Com ambiente virtual ativado
rasa train
```

Este comando:
- Processa os arquivos em `data/` (nlu.yml, stories.yml, rules.yml)
- Treina o modelo de NLU e Core
- Gera um arquivo `.tar.gz` na pasta `models/`

**⏱️ Tempo estimado:** 5-10 minutos (dependendo do hardware)

### Iniciar os Servidores

**Opção 1: Usando o script automatizado (recomendado)**

```bash
python start_rasa.py
```

Este script:
- ✅ Verifica e cria ambiente virtual se necessário
- ✅ Verifica se existe modelo treinado (treina se necessário)
- ✅ Processa o arquivo `credentials.yml` substituindo variáveis de ambiente
- ✅ Inicia o servidor de Actions (porta 5055)
- ✅ Inicia o servidor principal do Rasa (porta 5005)
- ✅ Exibe logs de ambos os servidores em tempo real
- ✅ Para ambos os servidores com Ctrl+C

**Opção 2: Manualmente (dois terminais)**

**Terminal 1 - Servidor de Actions:**
```bash
# Ativar ambiente virtual
source .venv_rasa/bin/activate  # Linux/Mac
# ou
.venv_rasa\Scripts\activate  # Windows

# Iniciar servidor de Actions
rasa run actions
```

**Terminal 2 - Servidor Principal:**
```bash
# Ativar ambiente virtual
source .venv_rasa/bin/activate  # Linux/Mac
# ou
.venv_rasa\Scripts\activate  # Windows

# Processar credentials.yml primeiro
python -c "from dotenv import load_dotenv; import os, re; load_dotenv(); content = open('credentials.yml').read(); content = re.sub(r'\$\{([^}]+)\}', lambda m: os.getenv(m.group(1), m.group(0)), content); open('credentials.yml.processed', 'w').write(content)"

# Iniciar servidor principal
rasa run -m models --enable-api --cors "*" --credentials credentials.yml.processed
```

**Opção 3: Shell interativo para testes (sem Telegram)**

```bash
rasa shell
```

Permite testar o bot diretamente no terminal sem precisar do Telegram.

### Verificar se está funcionando

Após iniciar os servidores, você deve ver:

```
[ACTIONS] Starting Rasa server on http://0.0.0.0:5055
[RASA] Starting Rasa server on http://0.0.0.0:5005
```

Se você configurou o Telegram e o ngrok:
1. Abra o Telegram
2. Procure pelo seu bot
3. Envie uma mensagem (ex: "Olá")
4. O bot deve responder

---

## 📊 Estrutura de Ações (Actions)

O arquivo `actions/actions.py` contém todas as ações customizadas do bot. Principais categorias:

### 🔐 Ações de Autenticação
- `ActionSaudacao` - Envia saudação inicial
- `ActionVerificarAutenticacao` - Verifica se usuário está autenticado
- `ActionBuscarAlunoPorEmail` - Busca aluno por email
- `ActionAutenticarChatbot` - Autentica via validação de RA
- `ActionEscolherPerguntaRA` - Escolhe pergunta aleatória sobre RA
- `ActionFazerPerguntaRA` - Faz pergunta sobre RA ao usuário
- `ActionDeletarMensagensSensiveis` - Remove mensagens sensíveis do Telegram

### 📚 Ações de Busca e Consulta
- `ActionBuscarUltimosAvisos` - Busca avisos recentes
- `ActionBuscarCronograma` - Busca horários de disciplinas
- `ActionBuscarDataAvaliacao` - Busca datas de provas
- `ActionBuscarConteudoAvaliacao` - Busca conteúdo programático
- `ActionListarTodasProvas` - Lista todas as provas agendadas
- `ActionBuscarInfoAtividadeAcademica` - Informações sobre TCC, APS, etc.
- `ActionBuscarAtendimentoDocente` - Horários de atendimento de professores
- `ActionBuscarMaterial` - Materiais de disciplinas
- `ActionBuscarEmenta` - Ementas de disciplinas
- `ActionBuscarInfoDocente` - Informações de contato de docentes
- `ActionBuscarDuvidasFrequentes` - Dúvidas frequentes por categoria

### 🤖 Ações de IA
- `ActionGerarRespostaComIA` - Gera resposta usando Google Gemini

### 🔧 Ações Auxiliares
- `ActionVerificarInatividade` - Verifica e gerencia inatividade
- `ActionInterceptarIntencoesNaoAutenticado` - Intercepta ações sem autenticação
- `ActionConsultarQuantidadeAlunosTurma` - Consulta quantidade de alunos na turma

---

## 🔧 Comandos Úteis

### Treinamento

```bash
# Treinar modelo
rasa train

# Treinar com validação
rasa train --validation-split 0.2

# Treinar apenas NLU
rasa train nlu

# Treinar apenas Core
rasa train core
```

### Testes

```bash
# Testar com stories
rasa test

# Testar apenas NLU
rasa test nlu

# Testar apenas Core
rasa test core

# Testar com shell interativo
rasa shell
```

### Análise

```bash
# Visualizar dados de treinamento
rasa data validate

# Verificar configuração
rasa data validate --config config.yml --domain domain.yml
```

### Servidores

```bash
# Iniciar servidor de Actions
rasa run actions

# Iniciar servidor principal
rasa run -m models --enable-api --cors "*"

# Iniciar servidor com debug
rasa run -m models --enable-api --debug
```

---

## 🐛 Troubleshooting

### Problema: Erro ao instalar dependências do Rasa

**Solução:**
- No **Windows**, instale o **Visual Studio Build Tools**
- Certifique-se de estar usando **Python 3.10+**
- Tente instalar dependências uma de cada vez
- No **Linux**, certifique-se de ter `build-essential` instalado

```bash
# Linux
sudo apt-get update
sudo apt-get install build-essential
```

### Problema: Modelo não encontrado

**Solução:**
```bash
cd chatbot_rasa
source .venv_rasa/bin/activate  # Linux/Mac
# ou
.venv_rasa\Scripts\activate  # Windows

rasa train
```

### Problema: Chatbot não responde no Telegram

**Soluções:**
1. **Verifique se o ngrok está rodando:**
   ```bash
   ngrok http 5005
   ```

2. **Verifique se a URL do webhook no `.env` está correta:**
   ```env
   TELEGRAM_WEBHOOK_URL=https://seu-ngrok-id.ngrok-free.app/webhooks/telegram/webhook
   ```

3. **Verifique se os servidores do Rasa estão rodando:**
   - Actions Server (porta 5055)
   - Rasa Server (porta 5005)

4. **Verifique os logs do Rasa** para erros

5. **Teste o webhook manualmente:**
   ```bash
   curl -X POST https://seu-ngrok-id.ngrok-free.app/webhooks/telegram/webhook
   ```

### Problema: Erro "Actions server not found"

**Solução:**
- Certifique-se de que o servidor de Actions está rodando na porta 5055
- Verifique o arquivo `endpoints.yml`:
  ```yaml
  action_endpoint:
    url: "http://localhost:5055/webhook"
  ```

### Problema: Erro ao conectar com a API Backend

**Solução:**
- Verifique se a API está rodando na porta 8000
- Verifique a variável `API_URL` no arquivo `actions/actions.py`:
  ```python
  API_URL = "http://localhost:8000"
  ```
- Teste a conexão:
  ```bash
  curl http://localhost:8000/docs
  ```

### Problema: Porta já em uso

**Solução:**
```bash
# Windows
netstat -ano | findstr ":5005"
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5005 | xargs kill -9
```

### Problema: Erro de autenticação no Telegram

**Solução:**
- Verifique se o token do Telegram está correto no `.env`
- Verifique se o bot foi criado corretamente via @BotFather
- Teste o token:
  ```bash
  curl https://api.telegram.org/bot<SEU_TOKEN>/getMe
  ```

### Problema: Variáveis de ambiente não carregadas

**Solução:**
- Certifique-se de que o arquivo `.env` está na pasta `chatbot_rasa/`
- Verifique se o arquivo não tem espaços extras ou caracteres especiais
- Use o script `setup_env.py` para criar o arquivo corretamente

---

## 📝 Variáveis de Ambiente

### Arquivo `.env`

```env
# Token de acesso do bot do Telegram
TELEGRAM_ACCESS_TOKEN=seu-token-aqui

# String de verificação do webhook
TELEGRAM_VERIFY=UnipChatBot

# URL do webhook do Telegram
TELEGRAM_WEBHOOK_URL=https://seu-ngrok-id.ngrok-free.app/webhooks/telegram/webhook
```

**⚠️ IMPORTANTE:**
- O arquivo `.env` **NÃO** deve ser commitado no Git
- Use `.env.example` como template
- Mantenha o token do Telegram seguro

---

## 🔒 Segurança

### Boas Práticas Implementadas

1. **Autenticação em duas etapas:**
   - Email institucional
   - Validação parcial de RA (nunca solicita RA completo)

2. **Deleção de mensagens sensíveis:**
   - Mensagens com RA, email ou informações de autenticação são deletadas automaticamente

3. **Timeout de inatividade:**
   - Deslogamento automático após 10 minutos de inatividade

4. **Validação de token:**
   - Verificação de expiração de tokens JWT
   - Renovação automática quando necessário

5. **Logs seguros:**
   - Informações sensíveis não são logadas
   - Logs apenas de ações e erros (sem dados pessoais)

---

## 📚 Documentação Adicional

- **Rasa Documentation:** https://rasa.com/docs/
- **Rasa SDK Documentation:** https://rasa.com/docs/rasa-sdk/
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **ngrok Documentation:** https://ngrok.com/docs

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
- Adicione comentários explicativos (formato: `### FUNÇÃO PARA... ###`)
- Mantenha o código limpo e legível
- Documente novas ações e funcionalidades

---

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` na raiz do projeto para mais detalhes.

---

## 👥 Autores

- **Equipe de Desenvolvimento** - *Desenvolvimento do TCC*

---

<div align="center">

**⭐ Se este projeto foi útil para você, considere dar uma estrela! ⭐**

Feito com ❤️ pela equipe do TCC - ChatBot Acadêmico

</div>

