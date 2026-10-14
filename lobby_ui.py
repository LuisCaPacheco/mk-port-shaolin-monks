"""lobby_ui.py — ventanita online aparte (tkinter) sobre LobbyCore.

Muestra: estado de conexión, jugadores con ✓/·, misión, botones listo /
empezar (host) / saltar intro, chat y ping. Sin lógica de red aquí.
"""
from __future__ import annotations
import queue
import tkinter as tk

import theme


class LobbyWindow(tk.Toplevel):
    def __init__(self, master, core, is_host: bool, on_close=None):
        super().__init__(master)
        self.core = core
        self.is_host = is_host
        self.on_close = on_close
        self.title("MK Port — Sala coop")
        self.geometry("380x600")
        self.resizable(False, False)
        theme.root(self)
        self.protocol("WM_DELETE_WINDOW", self._close)

        theme.section(self, "Sala coop").pack(anchor="w", padx=12, pady=(8, 0))
        self.status = theme.label(self, text="Conectando…", font=("Segoe UI", 10, "bold"),
                                  fg=theme.GOLD)
        self.status.pack(pady=2)
        self.ping = theme.label(self, text="ping: --", fg=theme.MUTE, font=theme.SMALL)
        self.ping.pack()

        theme.label(self, text="Guerreros").pack(anchor="w", padx=12)
        self.plist = theme.listbox(self, height=4)
        self.plist.pack(fill="x", padx=12)

        theme.label(self, text="Misión").pack(anchor="w", padx=12)
        self.mission_var = tk.StringVar()
        if is_host:
            theme.entry(self, textvariable=self.mission_var).pack(fill="x", padx=12)
            theme.button(self, text="Fijar misión", kind="bronze",
                         command=self._set_mission).pack(pady=2)
        else:
            theme.label(self, textvariable=self.mission_var, fg=theme.GOLD).pack()

        theme.gold_rule(self)
        btns = theme.frame(self)
        btns.pack(pady=4)
        self.ready_var = tk.StringVar(value="Estoy listo")
        theme.button(btns, textvariable=self.ready_var, kind="jade",
                     command=self._toggle_ready, width=14).pack(side="left", padx=3)
        if is_host:
            theme.button(btns, text="Empezar (3-2-1)", kind="blood",
                         command=self.core.host_start, width=15).pack(side="left", padx=3)
        theme.button(btns, text="Saltar intro", kind="bronze",
                     command=self.core.send_skip, width=12).pack(side="left", padx=3)

        self.flash = theme.label(self, text="", font=("Palatino Linotype", 15, "bold"),
                                 fg=theme.BLOOD)
        self.flash.pack(pady=2)

        theme.label(self, text="Sala / chat").pack(anchor="w", padx=12)
        self.log = theme.listbox(self, height=9)
        self.log.pack(fill="both", expand=True, padx=12, pady=2)
        row = theme.frame(self)
        row.pack(fill="x", padx=12, pady=4)
        self.chat_var = tk.StringVar()
        theme.entry(row, textvariable=self.chat_var).pack(side="left", fill="x", expand=True)
        theme.button(row, text="Enviar", kind="bronze",
                     command=self._send_chat).pack(side="left", padx=(6, 0))
        self.bind("<Return>", lambda e: self._send_chat())

        self._ready = False
        self._pump()

    # ---------- acciones ----------
    def _toggle_ready(self):
        self._ready = not self._ready
        self.core.set_ready(self._ready)
        self.ready_var.set("Ya no estoy listo" if self._ready else "Estoy listo")

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
            self.status.config(fg=theme.JADE if ev[1] else theme.BAD)
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
            self.flash.config(text="¡A jugar! Entren a la vez", fg=theme.GOLD)
            self._line("¡A jugar! Entren a la misión a la vez.")
            self.after(3000, lambda: self.flash.config(text=""))
        else:
            self.flash.config(text=f"Empieza en {n}…", fg=theme.GOLD)
            self.after(1000, lambda: self._countdown(n - 1))

    def _skip_flash(self, who):
        self._line(f"{who} pide saltar la intro ¡ahora!")
        self.flash.config(text="¡Saltar intro ahora!", fg=theme.BLOOD)
        self.bell()
        self.after(4000, lambda: self.flash.config(text="") if self.winfo_exists() else None)
