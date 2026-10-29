# Akili Island OS

> A personal Jarvis that lives in your Dynamic Island.

Akili is an 80px island reactor — voice-controlled, sees your screen, speaks Swahili & English.

### What it does

- **Hears you:** `hey akili` wake word
- **Sees for you:** Say `whats on screen` / `angalia screen` → chooses from 3 vision modes (Full screen, Active window, Select area)
- **Speaks Kenyan:** Zuri & Asilia voices

### Built with

Gemini 2.5 Flash for vision, Groq Whisper for speed, cloud-heavy so local RAM stays <150MB.

### Quick start

```bash
pip install -r requirements.txt
python main.py --desktop
