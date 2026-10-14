"""invite.py — links de sala estilo OpenCE. mkport://v2/<host>/<puerto>/<nombre_b64>"""
from __future__ import annotations
import base64

SCHEME = "mkport://v2/"
NET_VERSION = 2


def make_link(host: str, port: int, name: str = "Player") -> str:
    nb = base64.urlsafe_b64encode(name.encode("utf-8")).decode("ascii")
    return f"{SCHEME}{host}/{int(port)}/{nb}"


def parse_link(link: str) -> dict:
    link = (link or "").strip().strip('"').strip("'")
    if not link.startswith(SCHEME):
        raise ValueError("No es un link mkport:// válido (¿versión vieja?).")
    rest = link[len(SCHEME):].split("#", 1)[0].rstrip("/")
    parts = rest.split("/")
    if len(parts) < 2:
        raise ValueError("Link incompleto (falta host/puerto).")
    host, port = parts[0], int(parts[1])
    name = "Player"
    if len(parts) >= 3 and parts[2]:
        try:
            name = base64.urlsafe_b64decode(parts[2] + "==").decode("utf-8", "ignore") or name
        except Exception:
            pass
    return {"host": host, "port": port, "name": name}


def copy_clipboard(text: str) -> bool:
    import subprocess
    import sys
    if sys.platform == "win32":  # clip.exe no necesita ventana (headless-safe)
        try:
            p = subprocess.run(["clip.exe"], input=text.encode("utf-16-le"),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if p.returncode == 0:
                return True
        except Exception:
            pass
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        return False
