"""
app.py - Canonical Entry Point for AI Studio
Imports and exposes the FastAPI app from main.py.
"""

import os
import uvicorn
from main import app, setup_desktop_hotkey

setup_desktop_hotkey()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
