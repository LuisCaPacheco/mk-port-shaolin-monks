"""lobby_ui.py — ventanita online aparte (tkinter) sobre LobbyCore.

Muestra: estado de conexión, jugadores con ✓/·, misión, botones LISTO /
EMPEZAR (host) / SALTAR INTRO, chat y ping. Sin lógica de red aquí.
"""
from __future__ import annotations
import queue
import tkinter as tk
from tkinter import messagebox


class LobbyWindow(tk.Toplevel):
    def __init__(self, master, core, is_host: bool, on_close=None):
        super().__init__(master)
        self.core = core
        self.is_host = is_host
        self.on_close = on_close
        self.title("MK Port — Sala coop")
        self.geometry("360x560")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.status = tk.Label(self, text="Conectando...", font=("Segoe UI", 10, "bold"))
        self.status.pack(pady=4)
        self.ping = tk.Label(self, text="ping: --", fg="gray")
        self.ping.pack()

        tk.Label(self, text="Jugadores").pack()
        self.plist = tk.Listbox(self, height=4)
        self.plist.pack(fill="x", padx=10)

        tk.Label(self, text="Misión").pack()
        self.mission_var = tk.StringVar()
        if is_host:
            self.mission = tk.Entry(self, textvariable=self.mission_var)
            self.mission.pack(fill="x", padx=10)
            tk.Button(self, text="Fijar misión", command=self._set_mission).pack(pady=2)
        else:
            tk.Label(self, textvariable=self.mission_var, fg="blue").pack()

        btns = tk.Frame(self)
        btns.pack(pady=4)
        self.ready_var = tk.StringVar(value="Estoy LISTO")
        tk.Button(btns, textvariable=self.ready_var, width=14, command=self._toggle_ready).pack(side="left", padx=3)
        if is_host:
            tk.Button(btns, text="EMPEZAR (3-2-1)", width=16, command=self.core.host_start).pack(side="left", padx=3)
        tk.Button(btns, text="SALTAR INTRO", width=14, command=self.core.send_skip).pack(side="left", padx=3)

        self.flash = tk.Label(self, text="", font=("Segoe UI", 14, "bold"), fg="red")
        self.flash.pack(pady=4)

        tk.Label(self, text="Sala / chat").pack()
        self.log = tk.Listbox(self, height=10)
        self.log.pack(fill="both", expand=True, padx=10, pady=2)
        row = tk.Frame(self)
        row.pack(fill="x", padx=10, pady=4)
        self.chat_var = tk.StringVar()
        tk.Entry(row, textvariable=self.chat_var).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Enviar", command=self._send_chat).pack(side="left")
        self.bind("<Return>", lambda e: self._send_chat())

        self._ready = False
        self._pump()

    # ---------- acciones ----------
    def _toggle_ready(self):
        self._ready = not self._ready
        self.core.set_ready(self._ready)
        self.ready_var.set("Ya NO estoy listo" if self._ready else "Estoy LISTO")

    def _set_mission(self):
        self.core.host_set_mission(self.mission_var.get())

    def _send_chat(self):
        t = self.chat_var.get().strip()
        if t:
            self.core.send_chat(t)
            self.chat_var.set("")

    def _close(self):
        try:
            self.core.stop()
        except Exception:
            pass
        if self.on_close:
            self.on_close()
        self.destroy()

    # ---------- eventos de red -> pantalla ----------
    def _pump(self):
        try:
            while True:
                ev = self.core.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._pump)

    def _handle(self, ev):
        kind = ev[0]
        if kind == "log":
            self._line(ev[1])
            self.status.config(text=ev[1][:60])
        elif kind == "conn":
            self.status.config(text="En sala ✓" if ev[1] else "Desconectado")
        elif kind == "players":
            self.plist.delete(0, "end")
            for p in ev[1]:
                mark = "✓" if p.get("ready") else "·"
                me = " (tú)" if p.get("me") else ""
                self.plist.insert("end", f"{mark} {p.get('name')}{me}")
        elif kind == "mission":
            self.mission_var.set(ev[1])
        elif kind == "chat":
            self._line(f"{ev[1]}: {ev[2]}")
        elif kind == "ping":
            self.ping.config(text=f"ping: {ev[1]:.0f} ms")
        elif kind == "countdown":
            self._countdown(int(ev[1]))
        elif kind == "skip":
            self._skip_flash(ev[1])

    def _line(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def _countdown(self, n):
        if not self.winfo_exists():
            return
        if n <= 0:
            self.flash.config(text="¡A JUGAR! Inicia la misión YA")
            self._line("¡A JUGAR! Entren a la misión a la vez.")
            self.after(3000, lambda: self.flash.config(text=""))
        else:
            self.flash.config(text=f"Empieza en {n}...")
            self.after(1000, lambda: self._countdown(n - 1))

    def _skip_flash(self, who):
        self._line(f"{who} pide SALTAR INTRO ¡ahora!")
        self.flash.config(text="¡SALTAR INTRO AHORA!")
        self.bell()
        self.after(4000, lambda: self.flash.config(text="") if self.winfo_exists() else None)
