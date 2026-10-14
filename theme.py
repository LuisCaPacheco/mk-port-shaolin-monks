"""theme.py — identidad MK del port: piedra negra, oro viejo, rojo sangre.

Si el usuario deja su logo en assets/logo.png se usa; si no, se dibuja un
sello-medallón propio (NO el dragón de MK, que es marca registrada).
Solo tkinter estándar, sin dependencias (el exe lo incluye todo).
"""
from __future__ import annotations
import sys
import tkinter as tk
from pathlib import Path

# Junto al exe compilado o junto al .py en desarrollo.
BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent

BG = "#141010"        # piedra negra cálida
PANEL = "#1e1814"     # panel
PANEL2 = "#241c16"
GOLD = "#c9a227"      # oro viejo
GOLD_DIM = "#8a6d3b"  # bronce apagado
BLOOD = "#a31621"     # rojo sangre
BLOOD_DK = "#6e0f16"
BONE = "#e8ded0"      # hueso (texto)
MUTE = "#9a8a76"      # texto apagado
JADE = "#2e6f5e"      # online
GOOD = "#7fb069"
BAD = "#d64545"

DISPLAY = ("Palatino Linotype", 22, "bold")
DISPLAY_SM = ("Palatino Linotype", 13, "bold")
BODY = ("Segoe UI", 9)
BODY_B = ("Segoe UI", 9, "bold")
SMALL = ("Segoe UI", 8)


def root(win: tk.Misc):
    try:
        win.configure(bg=BG)
    except Exception:
        pass


def frame(parent, **kw):
    kw.setdefault("bg", BG)
    return tk.Frame(parent, **kw)


def panel(parent, **kw):
    kw.setdefault("bg", PANEL)
    kw.setdefault("highlightbackground", GOLD_DIM)
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("bd", 0)
    return tk.Frame(parent, **kw)


def label(parent, text, font=BODY, fg=BONE, bg=BG, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kw)


def section(parent, text):
    return tk.Label(parent, text=text, font=DISPLAY_SM, fg=GOLD, bg=BG, anchor="w")


def entry(parent, textvariable=None, width=None, **kw):
    kw.setdefault("bg", PANEL2)
    kw.setdefault("fg", BONE)
    kw.setdefault("insertbackground", GOLD)
    kw.setdefault("relief", "flat")
    kw.setdefault("highlightbackground", GOLD_DIM)
    kw.setdefault("highlightthickness", 1)
    e = tk.Entry(parent, textvariable=textvariable, font=BODY, **kw)
    if width:
        e.config(width=width)
    return e


def button(parent, text, kind="ghost", command=None, width=None, **kw):
    """kinds: blood (acción principal), bronze, jade (online), ghost (discreto)."""
    styles = {
        "blood": dict(bg=BLOOD, fg="#f5e9d0", activebackground=BLOOD_DK,
                      activeforeground="#f5e9d0", font=("Palatino Linotype", 10, "bold")),
        "bronze": dict(bg=PANEL2, fg=GOLD, activebackground="#33271a",
                       activeforeground=GOLD, font=BODY_B),
        "jade": dict(bg="#1d3a32", fg="#cfe8cf", activebackground="#142820",
                     activeforeground="#cfe8cf", font=BODY_B),
        "ghost": dict(bg=BG, fg=MUTE, activebackground=PANEL,
                      activeforeground=BONE, font=BODY),
    }
    st = styles.get(kind, styles["ghost"])
    st.update(kw)
    b = tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                  highlightthickness=1,
                  highlightbackground=st.get("highlightbackground", GOLD_DIM), **st)
    if width:
        b.config(width=width)
    b.bind("<Enter>", lambda e: b.config(highlightbackground=GOLD))
    b.bind("<Leave>", lambda e: b.config(highlightbackground=st.get("highlightbackground", GOLD_DIM)))
    return b


def radio(parent, text, variable, value, command=None):
    return tk.Radiobutton(parent, text=text, variable=variable, value=value,
                          command=command, bg=BG, fg=MUTE, selectcolor=PANEL2,
                          activebackground=BG, activeforeground=GOLD, font=BODY)


def listbox(parent, height=6, **kw):
    kw.setdefault("bg", PANEL)
    kw.setdefault("fg", BONE)
    kw.setdefault("selectbackground", BLOOD_DK)
    kw.setdefault("selectforeground", BONE)
    kw.setdefault("relief", "flat")
    kw.setdefault("highlightbackground", GOLD_DIM)
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("font", BODY)
    return tk.Listbox(parent, height=height, **kw)


def gold_rule(parent):
    c = tk.Canvas(parent, height=2, bg=BG, highlightthickness=0, bd=0)
    c.pack(fill="x", padx=12, pady=4)

    def draw(_=None):
        c.delete("all")
        w = c.winfo_width() or 400
        c.create_line(0, 1, w, 1, fill=GOLD_DIM)
        c.create_line(0, 1, int(w * 0.25), 1, fill=GOLD, width=2)

    c.bind("<Configure>", draw)
    c.after(50, draw)
    return c


def banner(parent, width=536):
    """Cabecera con el arte del juego (assets/header.png)."""
    p = BASE / "assets" / "header.png"
    if not p.exists():
        return None
    try:
        img = tk.PhotoImage(file=str(p))
        if img.width() > width:
            k = img.width() // width + 1
            img = img.subsample(k, k)
        lab = tk.Label(parent, image=img, bg=BG, bd=0, highlightthickness=0)
        lab.image = img
        lab.pack(fill="x", padx=12, pady=(10, 0))
        return lab
    except Exception:
        return None


def emblem(parent, size=104):
    """Medallón MK: logo del usuario si existe, si no sello dibujado."""
    box = tk.Frame(parent, bg=BG, width=size, height=size + 34)
    box.pack_propagate(False)
    c = tk.Canvas(box, width=size, height=size, bg=BG, highlightthickness=0, bd=0)
    c.pack()
    logo = _find_logo()
    if logo:
        try:
            img = tk.PhotoImage(file=str(logo))
            w, h = img.width(), img.height()
            k = max(1, max(w, h) // (size - 8))
            if k > 1:
                img = img.subsample(k, k)
            c.create_image(size // 2, size // 2, image=img)
            c.image = img  # retener referencia
        except Exception:
            _draw_seal(c, size)
    else:
        _draw_seal(c, size)
    t = tk.Label(box, text="Shaolin Monks", font=("Palatino Linotype", 9, "bold"),
                 fg=GOLD, bg=BG)
    t.pack()
    s = tk.Label(box, text="port no oficial", font=SMALL, fg=MUTE, bg=BG)
    s.pack()
    return box


def _find_logo() -> Path | None:
    base = BASE / "assets"
    for name in ("logo.png", "seal.png", "logo.jpg", "mksm.png", "dragon.png"):
        p = base / name
        if p.exists():
            return p
    return None


def _draw_seal(c: tk.Canvas, size: int):
    m = size // 2
    r = m - 4
    c.create_oval(m - r, m - r, m + r, m + r, outline=GOLD, width=3)
    c.create_oval(m - r + 6, m - r + 6, m + r - 6, m + r - 6, outline=GOLD_DIM, width=1)
    c.create_oval(m - r + 10, m - r + 10, m + r - 10, m + r - 10,
                  fill=BLOOD_DK, outline=BLOOD, width=2)
    # puntas del sello (eco de medallón, dibujo propio)
    for ang in (45, 135, 225, 315):
        import math
        x = m + (r - 2) * math.cos(math.radians(ang))
        y = m - (r - 2) * math.sin(math.radians(ang))
        c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=GOLD, outline="")
    c.create_text(m, m - 2, text="MK", font=("Palatino Linotype", 30, "bold"), fill=GOLD)
