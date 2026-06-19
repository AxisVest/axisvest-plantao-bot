#!/usr/bin/env python3
"""
AxisVest Plantão de Dúvidas - Versão Minimalista
Bot de atendimento inteligente com professores especializados
"""

import os
import re
import json
import logging
import tempfile
import asyncio
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
    "matemática": {"emoji": "📐", "name": "Professor Vector"},
    "biologia": {"emoji": "🧬", "name": "Professora Dino"},
    "química": {"emoji": "⚗️", "name": "Professor Otto"},
    "física": {"emoji": "⚡", "name": "Professor César"},
    "português": {"emoji": "📖", "name": "Professora Camila"},
    "literatura": {"emoji": "✍️", "name": "Professor Lucas"},
    "história": {"emoji": "📜", "name": "Professor Marco"},
    "geografia": {"emoji": "🌍", "name": "Professora Nina"},
    "filosofia": {"emoji": "🤔", "name": "Professor Paulo"},
    "sociologia": {"emoji": "👥", "name": "Professora Sofia"},
}

SYSTEM_PROMPTS = {
    "matemática": "Você é um professor de Matemática experiente. Explique de forma clara e didática, passo a passo. Use exemplos práticos quando possível.",
    "biologia": "Você é uma professora de Biologia entusiasmada. Explique os processos biológicos de forma visual e fácil de entender.",
    "química": "Você é um professor de Química dedicado. Explique as reações e conceitos de forma lógica e estruturada.",
    "física": "Você é um professor de Física dinâmico. Explique os fenômenos físicos com clareza e use analogias do dia a dia.",
    "português": "Você é uma professora de Português atenciosa. Corrija erros com gentileza e explique as regras gramaticais.",
    "literatura": "Você é um professor de Literatura apaixonado. Analise obras e autores com profundidade e contexto histórico.",
    "história": "Você é um professor de História envolvente. Conte histórias que conectem o passado ao presente.",
    "geografia": "Você é uma professora de Geografia exploratória. Explique fenômenos geográficos com mapas mentais.",
    "filosofia": "Você é um professor de Filosofia reflexivo. Questione ideias e estimule o pensamento crítico.",
    "sociologia": "Você é uma professora de Sociologia analítica. Explique fenômenos sociais com contexto e dados.",
}

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_user_state(user_id: int) -> Dict:
    """Obtém ou cria estado do usuário"""
    if user_id not in USER_STATES:
        USER_STATES[user_id] = {
            "name": "",
            "discipline": "",
            "history": [],
            "state": "start",  # start, name, discipline, teacher, feedback
        }
    return USER_STATES[user_id]


def find_discipline(text: str) -> Optional[str]:
    """Encontra disciplina no texto"""
    text_lower = text.lower()
    for disc in DISCIPLINES.keys():
        if disc in text_lower:
            return disc
    return None


def is_continuing(text: str) -> bool:
    """Detecta se o usuário quer continuar (com word boundaries)"""
    keywords = [r"\bsim\b", r"\btenho\s+mais\b", r"\bclaro\b", r"\bcom\s+certeza\b", r"\boutra\b"]
    return any(re.search(kw, text.lower()) for kw in keywords)


def is_ending(text: str) -> bool:
    """Detecta se o usuário quer encerrar (com word boundaries)"""
    keywords = [r"\bn[ãa]o\s+tenho\b", r"\bsem\s+d[úu]vida\b", r"\bnenhuma\s+d[úu]vida\b", r"\bfinalizar\b", r"\bencerrar\b", r"\btchau\b", r"\bpronto\b"]
    return any(re.search(kw, text.lower()) for kw in keywords)


def format_discipline_selection() -> str:
    """Formata seleção de disciplinas"""
    lines = []
    for i, (disc, info) in enumerate(DISCIPLINES.items()):
        lines.append(f"{info['emoji']} {disc.capitalize()}")
        if (i + 1) % 2 == 0:
            lines.append("\n")
    return " | ".join(lines).replace("\n |", "\n")


async def send_message(user_id: int, text: str):
    """Envia mensagem para o usuário via Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        })


async def download_image(file_id: str) -> Optional[str]:
    """Baixa imagem do Telegram"""
    try:
        # Obter informações do arquivo
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"file_id": file_id})
            data = response.json()
            
            if not data.get("ok"):
                return None
            
            file_path = data["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            
            # Baixar arquivo
            response = await client.get(download_url, timeout=60)
            if response.status_code != 200:
                return None
            
            # Salvar arquivo
            temp_dir = tempfile.gettempdir()
            image_path = os.path.join(temp_dir, f"axisvest_{file_id}.jpg")
            Path(image_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(image_path, "wb") as f:
                f.write(response.content)
            
            return image_path
    except Exception as e:
        logger.error(f"❌ Erro ao baixar imagem: {e}")
        return None


async def process_with_gemini(text: str, history: list, discipline: str, is_image_path: Optional[str] = None) -> str:
    """Processa pergunta com Gemini"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Preparar histórico
        messages = []
        
        # Adicionar system prompt
        system_prompt = SYSTEM_PROMPTS.get(discipline, "Você é um professor experiente e dedicado.")
        messages.append({
            "role": "user",
            "parts": [system_prompt]
        })
        messages.append({
            "role": "model",
            "parts": ["Entendido. Vou responder como um professor especializado nesta disciplina."]
        })
        
        # Adicionar histórico
        for msg in history[-4:]:  # Últimas 4 mensagens
            messages.append({
                "role": msg["role"],
                "parts": [msg["content"]]
            })
        
        # Adicionar pergunta atual
        if is_image_path:
            # Se for imagem, fazer OCR com Gemini Vision
            with open(is_image_path, "rb") as f:
                image_data = f.read()
            
            response = model.generate_content([
                text or "Qual é a resposta para esta questão?",
                {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            ])
        else:
            # Se for texto, processar normalmente
            messages.append({
                "role": "user",
                "parts": [text]
            })
            response = model.generate_content(messages)
        
        return response.text if response else "Desculpe, não consegui processar sua pergunta."
    
    except Exception as e:
        logger.error(f"❌ Erro ao processar com Gemini: {e}")
        return "Desculpe, ocorreu um erro ao processar sua pergunta."


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "AxisVest Running"}


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
            
            # Baixar e processar imagem
            best_photo = max(photo, key=lambda p: p.get("file_size", 0))
            image_path = await download_image(best_photo.get("file_id"))
            
            if image_path:
                response = await process_with_gemini(
                    "[IMAGEM COM QUESTÃO]",
                    state["history"],
                    state["discipline"],
                    is_image_path=image_path
                )
                
                # Adicionar ao histórico
                state["history"].append({"role": "user", "content": "[IMAGEM]"})
                state["history"].append({"role": "assistant", "content": response})
                
                # Limitar histórico
                if len(state["history"]) > 10:
                    state["history"] = state["history"][-10:]
                
                # Enviar resposta
                disc_info = DISCIPLINES[state["discipline"]]
                msg_text = f"<b>{disc_info['name']} - {state['discipline'].capitalize()}:</b> {disc_info['emoji']}\n\n{response}"
                await send_message(user_id, msg_text)
                
                # Limpar arquivo
                try:
                    os.remove(image_path)
                except:
                    pass
            
            return JSONResponse({"ok": True})
        
        # ====== PRIORIDADE 2: PROCESSAR TEXTO ======
        if not text:
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: start ======
        if state["state"] == "start":
            state["name"] = text
            state["state"] = "discipline"
            msg_text = f"<b>Alice - Secretária:</b> ✨\n\nPerfeito, {text.split()[0]}!\n\nQual disciplina você tem dúvida?\n\n{format_discipline_selection()}"
            await send_message(user_id, msg_text)
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: discipline ======
        if state["state"] == "discipline":
            discipline = find_discipline(text)
            
            if not discipline:
                await send_message(user_id, "<b>Alice - Secretária:</b> 🤔\n\nDesculpe, não entendi. Qual disciplina?")
                return JSONResponse({"ok": True})
            
            state["discipline"] = discipline
            state["state"] = "teacher"
            state["history"] = []
            
            disc_info = DISCIPLINES[discipline]
            msg_text = f"<b>{disc_info['name']} - {discipline.capitalize()}:</b> {disc_info['emoji']}\n\nOlá {state['name'].split()[0]}! Qual é sua dúvida?"
            await send_message(user_id, msg_text)
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: teacher ======
        if state["state"] == "teacher":
            if text.lower() in ["voltar", "menu", "outra"]:
                state["state"] = "feedback"
                first_name = state["name"].split()[0]
                msg_text = f"<b>Alice - Secretária:</b> 💬\n\n{first_name}, gostou do nosso atendimento? Tem mais alguma dúvida?"
                await send_message(user_id, msg_text)
                return JSONResponse({"ok": True})
            
            # Adicionar ao histórico
            state["history"].append({"role": "user", "content": text})
            
            # Processar com Gemini
            response = await process_with_gemini(text, state["history"], state["discipline"])
            
            # Adicionar resposta ao histórico
            state["history"].append({"role": "assistant", "content": response})
            
            # Limitar histórico
            if len(state["history"]) > 10:
                state["history"] = state["history"][-10:]
            
            # Enviar resposta
            disc_info = DISCIPLINES[state["discipline"]]
            msg_text = f"<b>{disc_info['name']} - {state['discipline'].capitalize()}:</b> {disc_info['emoji']}\n\n{response}"
            await send_message(user_id, msg_text)
            
            return JSONResponse({"ok": True})
        
        # ====== ESTADO: feedback ======
        if state["state"] == "feedback":
            if is_ending(text):
                state["state"] = "start"
                state["name"] = ""
                state["discipline"] = ""
                state["history"] = []
                msg_text = "<b>Alice - Secretária:</b> 👋\n\nObrigada por usar o AxisVest! Até logo!"
                await send_message(user_id, msg_text)
                return JSONResponse({"ok": True})
            
            if is_continuing(text):
                state["state"] = "discipline"
                msg_text = f"<b>Alice - Secretária:</b> ✨\n\nQual disciplina agora?\n\n{format_discipline_selection()}"
                await send_message(user_id, msg_text)
                return JSONResponse({"ok": True})
            
            await send_message(user_id, "<b>Alice - Secretária:</b> 🤔\n\nDesculpe, você tem mais dúvida? (sim/não)")
            return JSONResponse({"ok": True})
        
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse({"ok": False}, status_code=500)


@app.on_event("startup")
async def startup():
    """Configura webhook ao iniciar"""
    try:
        logger.info("🚀 Configurando webhook...")
        
        webhook_url = f"{PUBLIC_URL}/webhook/{WEBHOOK_SECRET}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                json={"url": webhook_url},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Webhook configurado: {webhook_url}")
            else:
                logger.error(f"❌ Erro ao configurar webhook: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Erro ao configurar webhook: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
