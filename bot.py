#!/usr/bin/env python3
"""
AxisVest Plantão de Dúvidas - Versão 3.0
Novo fluxo: Secretária → Professor → Secretária
Com processamento Google + Gemini
"""

import os
import re
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import google.generativeai as genai

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
PORT = int(os.getenv("PORT", 8000))

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Estado dos usuários (em memória)
USER_STATES: Dict[int, Dict] = {}

# ============================================================================
# DISCIPLINAS E PROFESSORES
# ============================================================================

DISCIPLINES = {
    "1": {"name": "Matemática", "emoji": "📐", "professor": "Vector"},
    "2": {"name": "Física", "emoji": "⚡", "professor": "Dino"},
    "3": {"name": "Química", "emoji": "🧪", "professor": "Otto"},
    "4": {"name": "Biologia", "emoji": "🧬", "professor": "César"},
    "5": {"name": "História", "emoji": "📚", "professor": "Dante"},
    "6": {"name": "Geografia", "emoji": "🌍", "professor": "Euler"},
    "7": {"name": "Português", "emoji": "✍️", "professor": "Fibonacci"},
    "8": {"name": "Inglês", "emoji": "🌐", "professor": "Gauss"},
    "9": {"name": "Literatura", "emoji": "📖", "professor": "Hertz"},
    "10": {"name": "Redação", "emoji": "📝", "professor": "Turing"},
}

PROFESSOR_PROMPTS = {
    "Vector": """Você é o Professor Vector, especialista em Matemática.
Seu estilo é direto, didático e usa muitos exemplos práticos.
Sempre use a personalidade de um professor apaixonado por números.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Dino": """Você é o Professor Dino, especialista em Física.
Seu estilo é entusiasmado e sempre relaciona conceitos com a natureza.
Sempre use a personalidade de um professor que adora explicar fenômenos naturais.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Otto": """Você é o Professor Otto, especialista em Química.
Seu estilo é estruturado e lógico, explicando reações passo a passo.
Sempre use a personalidade de um professor dedicado e preciso.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "César": """Você é o Professor César, especialista em Biologia.
Seu estilo é visual e conecta conceitos com exemplos do corpo humano.
Sempre use a personalidade de um professor que adora a vida.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Dante": """Você é o Professor Dante, especialista em História.
Seu estilo é narrativo e conecta eventos ao contexto social.
Sempre use a personalidade de um professor que adora contar histórias.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Euler": """Você é o Professora Euler, especialista em Geografia.
Seu estilo é exploratório e usa referências espaciais.
Sempre use a personalidade de uma professora que adora mapas.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Fibonacci": """Você é a Professora Fibonacci, especialista em Português.
Seu estilo é atencioso e corrige com gentileza.
Sempre use a personalidade de uma professora dedicada à língua.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Gauss": """Você é o Professor Gauss, especialista em Inglês.
Seu estilo é prático e focado em aplicação real.
Sempre use a personalidade de um professor que adora idiomas.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Hertz": """Você é o Professor Hertz, especialista em Literatura.
Seu estilo é apaixonado e analisa obras com profundidade.
Sempre use a personalidade de um professor que adora livros.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
    
    "Turing": """Você é a Professora Turing, especialista em Redação.
Seu estilo é construtivo e focado em melhorar a escrita.
Sempre use a personalidade de uma professora que adora textos bem escritos.
Responda em português brasileiro, de forma clara e objetiva.
Use emojis ocasionalmente para tornar a resposta mais engajante.
Responda apenas com a resposta, sem explicações adicionais.
Você consegue processar imagens e extrair texto delas para responder questões.
Se o aluno enviar uma imagem, analise-a e responda normalmente.""",
}

SECRETARY_GREETINGS = [
    "Olá! 👋 Bem-vindo ao AxisVest Plantão! Qual é o seu nome?",
    "Oi! 😊 Tudo bem? Me diga seu nome para começarmos!",
    "Bem-vindo! 🎓 Qual é o seu nome, por favor?",
]

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_user_state(user_id: int) -> Dict:
    """Obtém ou cria estado do usuário"""
    if user_id not in USER_STATES:
        USER_STATES[user_id] = {
            "name": None,
            "discipline": None,
            "professor": None,
            "history": [],
            "state": "greeting",  # greeting, discipline, teacher, feedback
        }
    return USER_STATES[user_id]


def validate_name(name: str) -> bool:
    """Valida se o nome tem mais de 4 letras"""
    return len(name.strip()) > 4


def is_valid_discipline(choice: str) -> bool:
    """Valida se a escolha de disciplina é válida"""
    return choice in DISCIPLINES


def format_disciplines() -> str:
    """Formata a lista de disciplinas"""
    lines = []
    for key, value in DISCIPLINES.items():
        lines.append(f"{key}. {value['emoji']} {value['name']}")
    return "\n".join(lines)


def is_ending_conversation(text: str) -> bool:
    """Detecta se o usuário quer encerrar (com word boundaries)"""
    keywords = [r"\bnão tenho mais dúvida\b", r"\bsem mais dúvida\b", r"\bnenhuma dúvida\b", 
                r"\bfinalizar\b", r"\bencerrar\b", r"\btchau\b", r"\bpronto\b", r"\bobrigado\b"]
    return any(re.search(kw, text.lower()) for kw in keywords)


async def send_message(user_id: int, text: str):
    """Envia mensagem para o usuário via Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={
                "chat_id": user_id,
                "text": text,
                "parse_mode": "HTML"
            }, timeout=30)
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")


async def download_image(file_id: str) -> Optional[str]:
    """Baixa imagem do Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"file_id": file_id}, timeout=30)
            data = response.json()
            
            if not data.get("ok"):
                return None
            
            file_path = data["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            
            response = await client.get(download_url, timeout=60)
            if response.status_code != 200:
                return None
            
            temp_dir = tempfile.gettempdir()
            image_path = os.path.join(temp_dir, f"axisvest_{file_id}.jpg")
            Path(image_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(image_path, "wb") as f:
                f.write(response.content)
            
            return image_path
    except Exception as e:
        logger.error(f"Erro ao baixar imagem: {e}")
        return None


async def process_question(text: str, history: list, discipline: str, professor: str, image_path: Optional[str] = None) -> str:
    """Processa pergunta com Gemini"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        professor_prompt = PROFESSOR_PROMPTS.get(professor, PROFESSOR_PROMPTS["Vector"])
        
        if image_path:
            # Processar imagem
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            prompt = f"""{professor_prompt}

Um aluno enviou uma imagem com uma questão de {discipline}.
Leia a questão na imagem e responda de forma clara, didática e completa."""
            
            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
        else:
            # Processar texto
            prompt = f"""{professor_prompt}

Um aluno fez a seguinte pergunta sobre {discipline}:

"{text}"

Responda de forma clara, didática e completa."""
            
            response = model.generate_content(prompt)
        
        return response.text if response else "Desculpe, não consegui processar sua pergunta."
    
    except Exception as e:
        logger.error(f"Erro ao processar com Gemini: {e}")
        return "Desculpe, ocorreu um erro ao processar sua pergunta."


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "AxisVest v3.0 Running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def webhook(request: Request):
    """Webhook para Telegram"""
    try:
        data = await request.json()
        
        if "message" not in data:
            return JSONResponse({"ok": True})
        
        msg = data["message"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "").strip()
        photo = msg.get("photo")
        
        state = get_user_state(user_id)
        
        # ====== PRIORIDADE 1: PROCESSAR IMAGENS ======
        if photo:
            if state["state"] != "teacher":
                await send_message(user_id, "<b>Alice - Secretária:</b> 👋\n\nPor favor, escolha uma disciplina primeiro!")
                return JSONResponse({"ok": True})
            
            best_photo = max(photo, key=lambda p: p.get("file_size", 0))
            image_path = await download_image(best_photo.get("file_id"))
            
            if image_path:
                response = await process_question(
                    "",
                    state["history"],
                    state["discipline"],
                    state["professor"],
                    image_path=image_path
                )
                
                state["history"].append({"role": "user", "content": "[IMAGEM]"})
                state["history"].append({"role": "assistant", "content": response})
                
                if len(state["history"]) > 10:
                    state["history"] = state["history"][-10:]
                
                disc_info = DISCIPLINES[next(k for k, v in DISCIPLINES.items() if v["professor"] == state["professor"])]
                msg_text = f"<b>{state['professor']} - {disc_info['name']}:</b> {disc_info['emoji']}\n\n{response}\n\n---\n\nVocê entendeu? Se tiver mais dúvidas, é só me chamar! 😊"
                await send_message(user_id, msg_text)
                
                try:
                    os.remove(image_path)
                except:
                    pass
            
            return JSONResponse({"ok": True})
        
        # ====== PRIORIDADE 2: PROCESSAR TEXTO ======
        if not text:
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: greeting (Secretária coleta nome) ======
        if state["state"] == "greeting":
            if validate_name(text):
                state["name"] = text.split()[0]
                state["state"] = "discipline"
                
                disciplines_list = format_disciplines()
                msg_text = f"""<b>Alice - Secretária:</b> ✨

Ótimo, {state['name']}! 😊 Qual disciplina você gostaria de tirar uma dúvida?

{disciplines_list}

Responda apenas com o número (1-10)."""
                await send_message(user_id, msg_text)
            else:
                await send_message(user_id, "❌ O nome deve ter mais de 4 letras. Tente novamente!")
            
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: discipline (Secretária coleta disciplina) ======
        if state["state"] == "discipline":
            if is_valid_discipline(text):
                discipline_info = DISCIPLINES[text]
                state["discipline"] = discipline_info["name"]
                state["professor"] = discipline_info["professor"]
                state["state"] = "teacher"
                
                msg_text = f"""<b>{discipline_info['professor']} - {discipline_info['name']}:</b> {discipline_info['emoji']}

Oi {state['name']}! 👋 Bem-vindo à aula de {state['discipline']}!

Qual é sua dúvida? Pode enviar em texto ou imagem! 📸"""
                
                await send_message(user_id, msg_text)
            else:
                await send_message(user_id, "❌ Disciplina inválida! Escolha um número entre 1 e 10.")
            
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: teacher (Professor atendendo) ======
        if state["state"] == "teacher":
            if is_ending_conversation(text):
                state["state"] = "feedback"
                
                msg_text = f"""<b>{state['professor']}:</b> 👋

Ótimo, {state['name']}! Fico feliz em ter ajudado! 💙

Vou passar você para a secretária agora."""
                
                await send_message(user_id, msg_text)
                
                msg_text2 = f"""<b>Alice - Secretária:</b> ✨

{state['name']}, obrigado por usar nosso serviço! 🙏

Precisa de ajuda com outra disciplina? (sim/não)"""
                
                await send_message(user_id, msg_text2)
            else:
                response = await process_question(
                    text,
                    state["history"],
                    state["discipline"],
                    state["professor"]
                )
                
                state["history"].append({"role": "user", "content": text})
                state["history"].append({"role": "assistant", "content": response})
                
                if len(state["history"]) > 10:
                    state["history"] = state["history"][-10:]
                
                disc_info = DISCIPLINES[next(k for k, v in DISCIPLINES.items() if v["professor"] == state["professor"])]
                msg_text = f"<b>{state['professor']} - {disc_info['name']}:</b> {disc_info['emoji']}\n\n{response}\n\n---\n\nVocê entendeu? Se tiver mais dúvidas, é só me chamar! 😊"
                await send_message(user_id, msg_text)
            
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: feedback (Secretária finalizando) ======
        if state["state"] == "feedback":
            if text.lower() in ["sim", "s", "sim!", "claro", "com certeza", "outra"]:
                state["state"] = "discipline"
                disciplines_list = format_disciplines()
                msg_text = f"""<b>Alice - Secretária:</b> ✨

Qual disciplina agora?

{disciplines_list}

Responda apenas com o número (1-10)."""
                await send_message(user_id, msg_text)
            else:
                msg_text = f"""<b>Alice - Secretária:</b> 👋

Tudo bem, {state['name']}! Até logo! 💙

Sempre que precisar, estaremos por aqui! 🎓"""
                await send_message(user_id, msg_text)
                del USER_STATES[user_id]
            
            return JSONResponse({"ok": True})
        
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return JSONResponse({"ok": False, "error": str(e)})


@app.on_event("startup")
async def startup():
    """Configurar webhook ao iniciar"""
    try:
        webhook_url = f"{PUBLIC_URL}/webhook/{WEBHOOK_SECRET}"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        payload = {"url": webhook_url}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30)
            logger.info(f"Webhook configurado: {response.status_code}")
    except Exception as e:
        logger.error(f"Erro ao configurar webhook: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
