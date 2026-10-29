"""
screenshot.py - Active Window Screen Capture
Lightweight screen capture (<15MB footprint) using mss with pywinauto active window bounding box.
"""

import os
import sys
import platform
import base64
import io
import logging
from typing import Optional, Tuple, Dict, Any
from PIL import Image
import mss

logger = logging.getLogger("screenshot")


def get_active_window_rect() -> Optional[Dict[str, int]]:
    """
    Get bounding box of currently active window.
    On Windows uses pywinauto or Win32 GetForegroundWindow.
    On Linux/macOS falls back to primary screen or xdotool/osascript.
    """
    system = platform.system()

    if system == "Windows":
        try:
            from pywinauto import Desktop
            import win32gui  # optional if installed

            # Try win32gui first for lightweight fast rect
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                # left, top, right, bottom
                return {
                    "left": max(0, rect[0]),
                    "top": max(0, rect[1]),
                    "width": max(10, rect[2] - rect[0]),
                    "height": max(10, rect[3] - rect[1]),
                }
        except Exception:
            pass

        try:
            from pywinauto import Desktop
            active_win = Desktop(backend="uia").active_window()
            rect = active_win.rectangle()
            return {
                "left": max(0, rect.left),
                "top": max(0, rect.top),
                "width": max(10, rect.width()),
                "height": max(10, rect.height()),
            }
        except Exception as e:
            logger.debug(f"pywinauto active window query failed: {e}")

    # Fallback for Linux / macOS / Headless container
    return None


def capture_active_window(output_path: Optional[str] = None) -> Tuple[Image.Image, str]:
    """
    Capture active window using mss and pywinauto bounding box.
    Returns: (PIL.Image, base64_png_data_url)
    """
    with mss.mss() as sct:
        rect = get_active_window_rect()
        if rect:
            monitor = {
                "left": rect["left"],
                "top": rect["top"],
                "width": rect["width"],
                "height": rect["height"],
            }
        else:
            monitors = sct.monitors
            monitor = monitors[1] if len(monitors) > 1 else monitors[0]

        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_str}"

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            img.save(output_path, "PNG")

        return img, data_url


def capture_full_screen(output_path: Optional[str] = None) -> Tuple[Image.Image, str]:
    """
    Capture entire primary or all-monitor desktop screen using mss.
    Returns: (PIL.Image, base64_png_data_url)
    """
    with mss.mss() as sct:
        monitors = sct.monitors
        # monitor[0] is all monitors combined, monitor[1] is primary
        monitor = monitors[1] if len(monitors) > 1 else monitors[0]

        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_str}"

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            img.save(output_path, "PNG")

        return img, data_url


def capture_selected_area(
    left: int, top: int, width: int, height: int, output_path: Optional[str] = None
) -> Tuple[Image.Image, str]:
    """
    Capture custom bounded area on desktop using mss.
    Returns: (PIL.Image, base64_png_data_url)
    """
    with mss.mss() as sct:
        monitor = {
            "left": max(0, left),
            "top": max(0, top),
            "width": max(10, width),
            "height": max(10, height),
        }
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_str}"

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            img.save(output_path, "PNG")

        return img, data_url


if __name__ == "__main__":
    print("Capturing active window...")
    _, url = capture_active_window("active_window.png")
    print(f"Captured active window successfully. Saved to active_window.png (Data URL length: {len(url)})")
