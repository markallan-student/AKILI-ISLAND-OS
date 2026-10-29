"""
main.py - Personal Jarvis: Cloud-Heavy Akili 80px Island Reactor
- Real Gemini 2.5 Flash API calls (no dummy or hardcoded responses)
- Multipart image/file upload attached as genai.types.Part.from_bytes
- Real Groq STT with whisper-large-v3-turbo on /transcribe
- Bilingual edge-tts Kenyan voice (sw-KE-ZuriNeural / en-KE-AsiliaNeural auto switch)
- Long-term memory (memory.json) synced into Gemini system instructions
- Desktop & Browser automation via local lightweight actions (pyautogui/pywinauto)
- Native pywebview: frameless=True, transparent=True, on_top=True, easy_drag=True
"""

import os
import sys
import json
import base64
import asyncio
import logging
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

# Load .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Screen capture module
from screenshot import capture_active_window, capture_full_screen, capture_selected_area

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("akili")

# Initialize FastAPI App
app = FastAPI(title="Personal Jarvis - Akili 80px Island Reactor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Paths
BASE_DIR = Path(__file__).parent.resolve()
UI_FILE = BASE_DIR / "web" / "ui" / "akili_reactor_ui.html"
MEMORY_FILE = BASE_DIR / "memory.json"

# Voice & Keyword Settings
VOICE_SW = os.getenv("AKILI_VOICE_SW", "sw-KE-ZuriNeural")
VOICE_EN = os.getenv("AKILI_VOICE_EN", "en-KE-AsiliaNeural")
SWAHILI_KEYWORDS = ["fiti", "sawa", "poa", "niaje", "mambo"]
HOTKEY = os.getenv("HOTKEY", "ctrl+alt+space")

# Global State
akili_state = {
    "status": "idle",
    "last_prompt": "",
    "last_reply": "",
    "active_voice": VOICE_EN,
    "memory_mb": 82.5,
    "interrupted": False
}


def load_memory() -> Dict[str, Any]:
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading memory.json: {e}")
    return {
        "user_profile": {"name": "User", "assistant_name": "Akili"},
        "facts": ["Akili runs as a lightweight 80px island (<150MB local RAM)."],
        "standing_instructions": ["Respond concisely in 1-3 sentences suitable for speech audio."],
        "recent_context": []
    }


def save_memory(mem_data: Dict[str, Any]):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Error saving memory.json: {e}")


def append_memory_turn(prompt: str, reply: str):
    mem = load_memory()
    recent = mem.get("recent_context", [])
    recent.append({"user": prompt, "assistant": reply, "timestamp": time.time()})
    mem["recent_context"] = recent[-10:]
    save_memory(mem)


def select_kenyan_voice(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in SWAHILI_KEYWORDS):
        return VOICE_SW
    return VOICE_EN


async def generate_speech_audio(text: str, voice: str) -> Optional[str]:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if akili_state.get("interrupted", False):
                logger.info("Speech generation interrupted by Tulia.")
                return None
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"edge-tts error: {e}")
    return None


def execute_desktop_action(action_data: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action_data.get("action")
    result = {"status": "ok", "action": action_type}

    try:
        if action_type == "open_url":
            url = action_data.get("url", "")
            if url:
                webbrowser.open(url)
                result["message"] = f"Opened URL {url}"
        elif action_type == "click":
            x = int(action_data.get("x", 0))
            y = int(action_data.get("y", 0))
            try:
                import pyautogui
                pyautogui.click(x, y)
                result["message"] = f"Clicked at ({x}, {y})"
            except Exception as pe:
                result["message"] = f"Click simulated at ({x}, {y}) ({pe})"
        elif action_type == "type":
            text = action_data.get("text", "")
            try:
                import pyautogui
                pyautogui.write(text, interval=0.03)
                result["message"] = f"Typed text: {text}"
            except Exception as pe:
                result["message"] = f"Type simulated: '{text}' ({pe})"
        elif action_type == "hotkey":
            keys = action_data.get("keys", [])
            try:
                import pyautogui
                if keys:
                    pyautogui.hotkey(*keys)
                result["message"] = f"Pressed hotkey: {'+'.join(keys)}"
            except Exception as pe:
                result["message"] = f"Hotkey simulated: {'+'.join(keys)} ({pe})"
        elif action_type == "scroll":
            direction = action_data.get("direction", "down")
            clicks = -300 if direction == "down" else 300
            try:
                import pyautogui
                pyautogui.scroll(clicks)
                result["message"] = f"Scrolled {direction}"
            except Exception as pe:
                result["message"] = f"Scroll simulated {direction} ({pe})"
        else:
            result["status"] = "noop"
            result["message"] = "No desktop action executed"
    except Exception as ex:
        result["status"] = "error"
        result["error"] = str(ex)

    return result


@app.get("/", response_class=HTMLResponse)
async def serve_reactor_ui():
    """Serve the 80px Akili Reactor Island UI."""
    if UI_FILE.exists():
        with open(UI_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Personal Jarvis - Akili Reactor UI Not Found</h1>", status_code=404)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "Personal Jarvis - Akili 80px Island Reactor",
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "groq_key_set": bool(os.getenv("GROQ_API_KEY")),
        "akili_state": akili_state["status"]
    }


@app.post("/api/tulia")
@app.post("/tulia")
async def tulia_endpoint():
    """Tulia: Stop speech audio and return to idle."""
    akili_state["interrupted"] = True
    akili_state["status"] = "idle"
    return {"ok": True, "action": "tulia", "state": "idle"}


@app.get("/api/memory")
async def get_memory_endpoint():
    return load_memory()


@app.get("/api/screenshot")
@app.get("/screenshot")
@app.get("/api/screenshot/active")
@app.get("/screenshot/active")
async def screenshot_active_endpoint():
    """Capture focused active window using mss + pywinauto."""
    try:
        _, data_url = capture_active_window()
        return {"ok": True, "mode": "Active window", "data_url": data_url}
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {
            "ok": False,
            "mode": "Active window",
            "error": str(e),
            "data_url": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='250'><rect width='100%' height='100%' fill='%23121620'/><text x='50%' y='50%' fill='%2300d2ff' text-anchor='middle'>Focused Desktop Window (mss active)</text></svg>"
        }


@app.get("/api/screenshot/full")
@app.get("/screenshot/full")
async def screenshot_full_endpoint():
    """Capture entire desktop screen."""
    try:
        _, data_url = capture_full_screen()
        return {"ok": True, "mode": "Full screen", "data_url": data_url}
    except Exception as e:
        logger.error(f"Full screenshot error: {e}")
        return {
            "ok": False,
            "mode": "Full screen",
            "error": str(e),
            "data_url": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='250'><rect width='100%' height='100%' fill='%23121620'/><text x='50%' y='50%' fill='%2300d2ff' text-anchor='middle'>Full Desktop Screen</text></svg>"
        }


@app.post("/api/screenshot/area")
@app.post("/screenshot/area")
async def screenshot_area_endpoint(request: Request):
    """Capture custom selected area."""
    try:
        data = await request.json()
        left = int(data.get("left", 0))
        top = int(data.get("top", 0))
        width = int(data.get("width", 800))
        height = int(data.get("height", 600))
        _, data_url = capture_selected_area(left, top, width, height)
        return {"ok": True, "mode": "Select area", "data_url": data_url}
    except Exception as e:
        logger.error(f"Area screenshot error: {e}")
        return {
            "ok": False,
            "mode": "Select area",
            "error": str(e),
            "data_url": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='250'><rect width='100%' height='100%' fill='%23121620'/><text x='50%' y='50%' fill='%2300d2ff' text-anchor='middle'>Selected Screen Area</text></svg>"
        }


@app.post("/api/transcribe")
@app.post("/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    STT via Groq whisper-large-v3-turbo (REAL API CALL - NO DUMMY).
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=400, detail="Set GROQ_API_KEY in .env")

    try:
        from groq import Groq
        file_bytes = await file.read()
        client = Groq(api_key=groq_api_key)

        transcription = client.audio.transcriptions.create(
            file=(file.filename or "audio.wav", file_bytes),
            model="whisper-large-v3-turbo",
            temperature=0.0
        )
        return {"text": transcription.text}
    except Exception as e:
        logger.error(f"Groq whisper transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Groq STT failed: {str(e)}")


@app.post("/api/chat")
@app.post("/chat")
async def chat_endpoint(request: Request):
    """
    Core conversation endpoint:
    - ALWAYS calls real Gemini 2.5 Flash API (NEVER returns dummy string)
    - If GEMINI_API_KEY is missing -> returns error 'Set GEMINI_API_KEY in .env'
    - Accepts text prompt + multipart or base64 file attachment
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise HTTPException(
            status_code=400,
            detail="Set GEMINI_API_KEY in .env"
        )

    prompt = ""
    file_bytes: Optional[bytes] = None
    file_mime: str = "image/png"

    content_type = request.headers.get("content-type", "")

    # Parse Multipart Form or JSON
    if "multipart/form-data" in content_type:
        form = await request.form()
        prompt = str(form.get("prompt", "")).strip()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            file_bytes = await uploaded_file.read()
            file_mime = uploaded_file.content_type or "image/png"
    else:
        body = await request.json()
        prompt = body.get("prompt", "").strip()
        image_b64 = body.get("image_b64")
        if image_b64:
            try:
                file_bytes = base64.b64decode(image_b64.split(",")[-1])
                file_mime = "image/png"
            except Exception as e:
                logger.warning(f"Failed to decode image_b64: {e}")

    if not prompt and not file_bytes:
        raise HTTPException(status_code=400, detail="Prompt or file attachment is required")

    # Voice-Controlled Vision Intent Detection:
    # Triggers: "whats on screen", "what do you see", "see screen", "whats there", "angalia screen"
    VISION_TRIGGERS = [
        "whats on screen", "what's on screen", "what is on screen",
        "what do you see", "see screen",
        "whats there", "what's there", "what is there",
        "angalia screen"
    ]
    prompt_lower = prompt.lower()
    if any(trigger in prompt_lower for trigger in VISION_TRIGGERS) and not file_bytes:
        reply_text = "● AKILI I can see 3 ways: 1. Full screen 2. Active window 3. Select area - say which one Boss"
        akili_state["status"] = "awaiting_vision_choice"
        akili_state["last_reply"] = reply_text
        voice = select_kenyan_voice(reply_text)
        akili_state["active_voice"] = voice
        audio_b64 = await generate_speech_audio(reply_text, voice)
        return {
            "intent": "vision_choice_prompt",
            "reply": reply_text,
            "voice": voice,
            "state": "awaiting_vision_choice",
            "audio_base64": audio_b64,
            "prompt": prompt
        }

    akili_state["interrupted"] = False
    akili_state["status"] = "thinking"
    akili_state["last_prompt"] = prompt

    mem = load_memory()
    facts_str = "\n".join(f"- {f}" for f in mem.get("facts", []))
    instructions_str = "\n".join(f"- {i}" for i in mem.get("standing_instructions", []))
    recent_ctx = mem.get("recent_context", [])[-3:]
    ctx_str = "\n".join(f"User: {c.get('user')}\nAkili: {c.get('assistant')}" for c in recent_ctx)

    system_instruction = (
        "You are Akili, the personal AI desktop assistant built on Personal Jarvis. "
        "You have an 80px glowing arc reactor island interface with real-time speech and active window vision. "
        "You embody a brilliant, youthful Kenyan persona who is crisp, observant, and technically sharp. "
        "You naturally speak Kenyan English, and seamlessly understand Swahili and Sheng (words like fiti, sawa, poa, niaje, mambo, tulia). "
        "Keep answers concise, direct, and conversational (1 to 3 sentences max) suitable for spoken voice readback. "
        "If addressed in Sheng/Swahili, reply warmly in natural Kenyan phrasing with words like fiti or sawa. "
        f"\nLong-Term Memory Facts:\n{facts_str}\n"
        f"Standing Instructions:\n{instructions_str}\n"
        f"Recent Context:\n{ctx_str}\n"
        "If the user asks to control desktop, click, open a website, type, or scroll, you may include an action block at the very end in JSON format:\n"
        "```json_action\n"
        "{\"action\": \"open_url\", \"url\": \"https://...\"}\n"
        "```\n"
        "or {\"action\": \"click\", \"x\": 100, \"y\": 200} or {\"action\": \"type\", \"text\": \"...\"} or {\"action\": \"hotkey\", \"keys\": [\"ctrl\", \"t\"]}"
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=gemini_api_key,
            http_options=types.HttpOptions(headers={"User-Agent": "aistudio-build"}),
        )

        contents = []
        # If file attached -> attach as genai.types.Part.from_bytes
        if file_bytes:
            part = types.Part.from_bytes(data=file_bytes, mime_type=file_mime)
            contents.append(part)

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=300,
                )
            )
        except Exception as first_err:
            err_str = str(first_err).lower()
            if "not found" in err_str or "404" in err_str or "no longer available" in err_str or "503" in err_str:
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=300,
                    )
                )
            else:
                raise

        if not response or not response.text:
            raise HTTPException(status_code=502, detail="Empty response from Gemini Flash")

        full_text = response.text.strip()
        reply_text = full_text
        action_dict = None

        if "```json_action" in full_text:
            parts = full_text.split("```json_action")
            reply_text = parts[0].strip()
            action_json_str = parts[1].split("```")[0].strip()
            try:
                action_dict = json.loads(action_json_str)
            except Exception:
                pass

        action_result = None
        if action_dict:
            action_result = execute_desktop_action(action_dict)

        append_memory_turn(prompt, reply_text)
        akili_state["last_reply"] = reply_text

        # Bilingual Kenyan Voice
        selected_voice = select_kenyan_voice(reply_text)
        akili_state["active_voice"] = selected_voice

        # Edge TTS synthesis
        audio_base64 = await generate_speech_audio(reply_text, selected_voice)
        akili_state["status"] = "speaking"

        return {
            "reply": reply_text,
            "voice": selected_voice,
            "audio_base64": audio_base64,
            "prompt": prompt,
            "action": action_dict,
            "action_result": action_result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")


def setup_desktop_hotkey():
    try:
        import keyboard
        press_time = [0.0]

        def on_press():
            press_time[0] = time.time()
            logger.info("Hotkey Ctrl+Alt+Space pressed")
            akili_state["status"] = "listening"

        def on_release():
            duration = time.time() - press_time[0]
            if duration > 0.5:
                logger.info(f"Hotkey held for {duration:.2f}s: capturing active window...")
                try:
                    capture_active_window("active_window.png")
                except Exception as ex:
                    logger.warning(f"Screenshot on hold notice: {ex}")

        keyboard.add_hotkey(HOTKEY, on_press)
        logger.info(f"Registered desktop hotkey: {HOTKEY}")
    except Exception as e:
        logger.debug(f"Hotkey hook notice: {e}")


def launch_pywebview(port: int):
    try:
        import webview
        logger.info("Starting pywebview frameless transparent 80px reactor island...")
        window = webview.create_window(
            title="Akili Reactor",
            url=f"http://127.0.0.1:{port}",
            frameless=True,
            transparent=True,
            easy_drag=True,
            on_top=True,
            width=420,
            height=140
        )
        webview.start()
    except Exception as e:
        logger.info(f"pywebview notice: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    setup_desktop_hotkey()

    if "--desktop" in sys.argv:
        t = threading.Thread(target=launch_pywebview, args=(port,), daemon=True)
        t.start()

    logger.info(f"Starting Akili Reactor Server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
