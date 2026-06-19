# AxisVest Plantão de Dúvidas - Versão Minimalista

Bot inteligente de atendimento com professores especializados em 10 disciplinas.

## 🚀 Características

- ✅ **Simples:** Apenas 1 arquivo Python
- ✅ **Rápido:** Responde em tempo real com Gemini
- ✅ **Inteligente:** 10 professores especializados
- ✅ **Multimodal:** Processa texto e imagens
- ✅ **Fácil de manter:** Código limpo e direto

## 📋 Disciplinas

- 📐 Matemática
- 🧬 Biologia
- ⚗️ Química
- ⚡ Física
- 📖 Português
- ✍️ Literatura
- 📜 História
- 🌍 Geografia
- 🤔 Filosofia
- 👥 Sociologia

## 🔧 Instalação

```bash
pip install -r requirements.txt
```

## 📝 Configuração

Defina as variáveis de ambiente:

```bash
export TELEGRAM_BOT_TOKEN="seu_token_aqui"
export GEMINI_API_KEY="sua_chave_aqui"
export PUBLIC_URL="https://seu-dominio.com"
export WEBHOOK_SECRET="seu_secret_aqui"
export PORT=8000
```

## 🏃 Execução

```bash
python bot.py
```

## 📊 Arquitetura

```
bot.py (500 linhas)
├── Configuração
├── Disciplinas e Prompts
├── Funções Auxiliares
├── FastAPI App
└── Webhook Handler
```

## 🎯 Fluxo de Conversa

1. Usuário inicia com `/start`
2. Alice (secretária) pede o nome
3. Usuário escolhe disciplina
4. Professor responde dúvidas
5. Usuário pode enviar imagens
6. Alice oferece outras disciplinas
7. Conversa encerra

## 🔐 Segurança

- Sem exposição de tokens nos logs
- Validação de word boundaries
- Tratamento de erros robusto

## 📦 Deploy

Pronto para deploy no Render, Heroku ou qualquer plataforma com Python.

---

**Status:** ✅ Pronto para Produção
