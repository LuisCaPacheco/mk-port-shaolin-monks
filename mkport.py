"""mkport.py — MK Port: busca tu ISO, valida que es Shaolin Monks, lanza Xemu + sala online.

Uso: py -3 mkport.py
"""
from __future__ import annotations
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

ROOT = Path(__file__).parent
if getattr(sys, "frozen", False):  # corriendo como MKPort.exe compilado
    ROOT = Path(sys.executable).parent
    sys.path.insert(0, str(ROOT))
else:
    sys.path.insert(0, str(ROOT))
import validator
import theme
from online import LobbyCore
from invite import make_link, parse_link, copy_clipboard

CONFIG = ROOT / "config.toml"


def local_ips() -> list[str]:
    """IPs locales de este PC (para encontrar la de ZeroTier, suele ser 10.x)."""
    out = []
    try:
        import socket
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127.") and ip not in out:
                out.append(ip)
    except Exception:
        pass
    return out


def public_ip(timeout_s: int = 6) -> str:
    """Tu IP vista desde internet (para invitar sin ZeroTier). Vacío si falla."""
    try:
        import urllib.request
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "MKPort"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            ip = r.read(60).decode("ascii", "ignore").strip()
        return ip if ip.count(".") == 3 else ""
    except Exception:
        return ""


def autodetect(system: str = "ps2") -> dict:
    """Busca emulador e ISO de Shaolin sin configurar nada (portable)."""
    found = {"image": "", "emulator": ""}
    emu_patterns = ("pcsx2*.exe",) if system == "ps2" else ("xemu*.exe",)
    search_roots = [ROOT, ROOT.parent]
    for base in search_roots:
        try:
            for pat in emu_patterns:
                for p in base.rglob(pat):
                    if "QtWebEngineProcess" not in str(p):
                        found["emulator"] = str(p)
                        break
                if found["emulator"]:
                    break
        except Exception:
            pass
        if not found["emulator"]:
            import shutil
            w = shutil.which("pcsx2") if system == "ps2" else shutil.which("xemu")
            if w:
                found["emulator"] = w
        try:
            cands = list(base.rglob("*.iso")) + list(base.rglob("*.xiso"))
            for p in cands:
                if "shaolin" not in p.name.lower():
                    continue
                try:
                    # acepta solo si la magia coincide con el sistema pedido
                    if validator.detect(str(p)) == system:
                        found["image"] = str(p)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if found["image"] and found["emulator"]:
            break
    return found


def load_config() -> dict:
    cfg = {"image": "", "emulator": "", "name": "Player", "port": "34513",
           "public_ip": "", "system": "ps2"}
    try:
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if "=" in s and not s.startswith("#"):
                k, v = s.split("=", 1)
                k, v = k.strip(), v.strip()
                if v.startswith('"'):  # respeta comillas, ignora comentario final
                    v = v[1:].split('"', 1)[0]
                else:
                    v = v.split("#", 1)[0].strip()
                if k in cfg:
                    cfg[k] = v
    except FileNotFoundError:
        pass
    if cfg["system"] not in ("ps2", "xbox"):
        cfg["system"] = "ps2"
    return cfg


def save_config(cfg: dict):
    CONFIG.write_text(
        "# MK Port — config\n"
        f'system = "{cfg["system"]}"  # ps2 | xbox\n'
        f'image = "{cfg["image"]}"\n'
        f'emulator = "{cfg["emulator"]}"\n'
        f'name = "{cfg["name"]}"\n'
        f'port = "{cfg["port"]}"\n'
        f'public_ip = "{cfg["public_ip"]}"  # tu IP pública o ZeroTier para invitar\n',
        encoding="utf-8")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        # Auto-detección portable: si falta ISO o emulador, búscalos junto al port.
        if not self.cfg.get("image") or not self.cfg.get("emulator"):
            auto = autodetect(self.cfg.get("system", "ps2"))
            if not self.cfg.get("image") and auto["image"]:
                self.cfg["image"] = auto["image"]
            if not self.cfg.get("emulator") and auto["emulator"]:
                self.cfg["emulator"] = auto["emulator"]
            save_config(self.cfg)
        self.title("MK Port — Shaolin Monks")
        self.geometry("560x700")
        self.resizable(False, False)
        theme.root(self)
        try:
            self._icon = tk.PhotoImage(file=str(theme.BASE / "assets" / "icon.png"))
            self.iconphoto(True, self._icon)
        except Exception:
            pass
        self.valid_ok = False
        self.lobby_win = None

        if theme.banner(self) is None:
            head = theme.frame(self)
            head.pack(fill="x", padx=12, pady=(10, 0))
            theme.emblem(head, size=96).pack(side="left", padx=(0, 12))
            tt = theme.frame(head)
            tt.pack(side="left", fill="y")
            theme.label(tt, text="MK Port", font=theme.DISPLAY, fg=theme.GOLD).pack(anchor="w")
            theme.label(tt, text="Mortal Kombat: Shaolin Monks", fg=theme.BONE).pack(anchor="w")
        else:
            theme.label(self, text="MK Port · Shaolin Monks", font=theme.DISPLAY_SM,
                        fg=theme.GOLD).pack(pady=(4, 0))
        rs = theme.frame(self)
        rs.pack(fill="x", padx=12, pady=(6, 0))
        self.sys_var = tk.StringVar(value=self.cfg.get("system", "ps2"))
        for val, lab in (("ps2", "PS2 + PCSX2"), ("xbox", "Xbox + Xemu")):
            theme.radio(rs, lab, self.sys_var, val, command=self._switch_system).pack(side="left", padx=(0, 10))
        theme.gold_rule(self)

        theme.section(self, "Tu disco").pack(anchor="w", padx=12)
        r1 = theme.frame(self)
        r1.pack(fill="x", padx=12)
        self.iso_var = tk.StringVar(value=self.cfg["image"])
        theme.entry(r1, textvariable=self.iso_var).pack(side="left", fill="x", expand=True)
        theme.button(r1, text="Buscar ISO…", kind="bronze", command=self._pick_iso).pack(side="left", padx=(6, 0))

        theme.section(self, "Validación").pack(anchor="w", padx=12, pady=(6, 0))
        self.checks = theme.listbox(self, height=6)
        self.checks.pack(fill="x", padx=12)
        self.result = theme.label(self, text="Sin validar", fg=theme.MUTE)
        self.result.pack()

        self.emu_label = theme.label(self, text="Tu emulador", font=theme.DISPLAY_SM, fg=theme.GOLD)
        self.emu_label.pack(anchor="w", padx=12, pady=(6, 0))
        r2 = theme.frame(self)
        r2.pack(fill="x", padx=12)
        self.emu_var = tk.StringVar(value=self.cfg["emulator"])
        theme.entry(r2, textvariable=self.emu_var).pack(side="left", fill="x", expand=True)
        self.emu_btn = theme.button(r2, text="Buscar…", kind="bronze", command=self._pick_emu)
        self.emu_btn.pack(side="left", padx=(6, 0))

        r3 = theme.frame(self)
        r3.pack(fill="x", padx=12, pady=(4, 0))
        theme.label(r3, text="Tu nombre:").pack(side="left")
        self.name_var = tk.StringVar(value=self.cfg["name"])
        theme.entry(r3, textvariable=self.name_var, width=16).pack(side="left", padx=4)
        theme.label(r3, text="Puerto:").pack(side="left")
        self.port_var = tk.StringVar(value=self.cfg["port"])
        theme.entry(r3, textvariable=self.port_var, width=8).pack(side="left")

        theme.gold_rule(self)
        r4 = theme.frame(self)
        r4.pack(pady=6)
        theme.button(r4, text="Validar ISO", kind="ghost", command=self._validate).pack(side="left", padx=4)
        self.play_btn = theme.button(r4, text="Jugar", kind="blood", command=self._play, width=16)
        self.play_btn.pack(side="left", padx=4)
        theme.button(r4, text="Sala online", kind="jade", command=self._lobby_menu, width=16).pack(side="left", padx=4)
        theme.label(self, text="Port no oficial · usa tu disco original", font=theme.SMALL,
                    fg=theme.MUTE).pack(pady=(0, 8))

        self._refresh_system_ui()
        if self.iso_var.get():
            self._validate(silent=True)

    # ---------- sistema ps2/xbox ----------
    def _switch_system(self):
        self.cfg["system"] = self.sys_var.get()
        auto = autodetect(self.cfg["system"])
        if auto["emulator"]:
            self.emu_var.set(auto["emulator"])
        self._refresh_system_ui()
        self._persist()
        self._validate(silent=True)

    def _refresh_system_ui(self):
        ps2 = self.sys_var.get() == "ps2"
        self.emu_label.config(text="Tu emulador (PCSX2)" if ps2 else "Tu emulador (Xemu)")
        self.emu_btn.config(text="Buscar PCSX2…" if ps2 else "Buscar Xemu…")
        self.play_btn.config(text="Jugar en PCSX2" if ps2 else "Jugar en Xemu")

    # ---------- juego ----------
    def _pick_iso(self):
        ps2 = self.sys_var.get() == "ps2"
        f = filedialog.askopenfilename(title="Selecciona tu MK Shaolin Monks .iso" + (" (PS2)" if ps2 else " (Xbox)"),
                                       filetypes=[("Disc", "*.iso *.xiso"), ("Todo", "*.*")])
        if f:
            self.iso_var.set(f)
            self._validate()

    def _pick_emu(self):
        ps2 = self.sys_var.get() == "ps2"
        f = filedialog.askopenfilename(title="Selecciona " + ("pcsx2.exe" if ps2 else "xemu.exe"),
                                       filetypes=[("exe", "*.exe"), ("Todo", "*.*")])
        if f:
            self.emu_var.set(f)

    def _persist(self):
        self.cfg.update(system=self.sys_var.get(), image=self.iso_var.get(), emulator=self.emu_var.get(),
                        name=self.name_var.get() or "Player", port=self.port_var.get() or "34513",
                        public_ip=self.cfg.get("public_ip", ""))
        save_config(self.cfg)

    def _validate(self, silent=False):
        self.checks.delete(0, "end")
        path = self.iso_var.get()
        if not path or not Path(path).exists():
            self.result.config(text="Elige tu ISO primero", fg="gray")
            self.valid_ok = False
            return
        ok, checks, msg = validator.validate(path, self.sys_var.get())
        for name, passed, detail in checks:
            self.checks.insert("end", f"[{'OK' if passed else 'XX'}] {name} {detail}")
        self.result.config(text=msg, fg=theme.GOOD if ok else theme.BAD)
        self.valid_ok = ok
        if ok:
            self._persist()
        elif not silent:
            messagebox.showerror("MK Port", msg)

    def _play(self):
        self._validate(silent=True)
        if not self.valid_ok:
            messagebox.showerror("MK Port", "Valida primero una ISO verdadera de Shaolin Monks.")
            return
        emu = self.emu_var.get()
        if not emu or not Path(emu).exists():
            site = "pcsx2.net" if self.sys_var.get() == "ps2" else "xemu.app"
            messagebox.showerror("MK Port", f"Falta el emulador. Descárgalo de {site}.")
            return
        self._persist()
        if self.sys_var.get() == "ps2":
            self._play_pcsx2(emu, self.iso_var.get())
        else:
            self._play_xemu(emu, self.iso_var.get())

    def _play_pcsx2(self, emu: str, iso: str):
        """PCSX2-Qt acepta ISO por parámetro (-slowboot = arranque completo,
        confirmado en el binario 2.8.2). Si tu build lo ignora, manual abajo."""
        try:
            subprocess.Popen([emu, "-slowboot", iso])
            messagebox.showinfo("MK Port", "PCSX2 abierto con tu ISO (arranque completo).\n"
                                "Si arranca sin juego: System → Boot ISO Image → tu ISO.\n"
                                "Primera vez: te pedirá la BIOS de tu PS2.")
        except Exception as e:
            messagebox.showerror("MK Port", f"No pude abrir PCSX2: {e}")

    def _play_xemu(self, emu: str, iso: str):
        if self._xemu_running():
            if not messagebox.askyesno("MK Port", "Xemu ya está abierto (sin disco).\n¿Lo cierro y lo abro con tu ISO?"):
                return
            if not self._xemu_kill_wait():
                messagebox.showerror("MK Port", "No pude cerrar Xemu. Ciérralo a mano e inténtalo de nuevo.")
                return
        self._xemu_set_disc(iso)
        log = Path(emu).parent / "xemu.log"
        try:
            mark = log.stat().st_size
        except OSError:
            mark = 0
        try:
            subprocess.Popen([emu, "-dvd_path", iso])
        except Exception as e:
            messagebox.showerror("MK Port", f"No pude abrir Xemu: {e}")
            return
        self.after(4000, lambda: self._xemu_poll_boot(iso, log, mark, 0))

    # ---------- Xemu: disco persistente + verificación ----------
    @staticmethod
    def _xemu_running() -> bool:
        try:
            import subprocess
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq xemu.exe"],
                               capture_output=True, text=True, timeout=10)
            return "xemu.exe" in r.stdout
        except Exception:
            return False

    @staticmethod
    def _xemu_kill():
        try:
            import subprocess
            subprocess.run(["taskkill", "/F", "/IM", "xemu.exe"],
                           capture_output=True, timeout=15)
        except Exception:
            pass

    @staticmethod
    def _xemu_kill_wait(timeout_s: float = 8.0) -> bool:
        """Cierra Xemu y espera a que el proceso muera (evita 2 instancias:
        la vieja se queda con el dashboard vacío y la nueva muere en silencio)."""
        import time
        App._xemu_kill()
        end = time.time() + timeout_s
        while time.time() < end:
            if not App._xemu_running():
                time.sleep(0.5)
                return True
            time.sleep(0.5)
        return not App._xemu_running()

    @staticmethod
    def _xemu_toml() -> Path | None:
        import os
        appdata = os.environ.get("APPDATA", "")
        p = Path(appdata) / "xemu" / "xemu" / "xemu.toml"
        return p if p.exists() else None

    @staticmethod
    def _xemu_set_disc(iso: str):
        """Escribe dvd_path en xemu.toml [sys.files] (clave real del binario),
        además del parámetro -dvd_path. Doble vía por si una falla."""
        toml = App._xemu_toml()
        if not toml:
            return
        try:
            lines = toml.read_text(encoding="utf-8").splitlines()
            out, in_files, done = [], False, False
            for line in lines:
                s = line.strip()
                if s.startswith("["):
                    in_files = (s == "[sys.files]")
                if in_files and s.startswith("dvd_path"):
                    out.append(f"dvd_path = '{iso}'")
                    done = True
                else:
                    out.append(line)
            if not done:
                for i, line in enumerate(out):
                    if line.strip() == "[sys.files]":
                        out.insert(i + 1, f"dvd_path = '{iso}'")
                        done = True
                        break
            if done:
                toml.write_text("\n".join(out) + "\n", encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _cdrom_loaded(log_text: str, iso: str) -> bool:
        """¿El ÚLTIMO arranque del log lleva esta ISO en el cdrom? (puro, testeable)."""
        import os
        want = os.path.basename(iso).lower()
        idx = log_text.lower().rfind("media=cdrom,file=")
        if idx < 0:
            return False
        chunk = log_text[idx + len("media=cdrom,file="):idx + 600]
        end = chunk.find(" -display")
        drive = (chunk[:end] if end >= 0 else chunk).strip().strip("'\"")
        if not drive:
            return False
        return want in drive.lower() or drive.lower() in want or want[:20] in drive.lower()

    def _xemu_poll_boot(self, iso: str, log: Path, mark: int, tries: int):
        """Relee el log hasta ~20s: solo el contenido NUEVO tras el arranque cuenta."""
        try:
            data = log.read_bytes()
        except OSError:
            data = b""
        new = data if len(data) < mark else data[mark:]  # truncate-safe
        text = new.decode("utf-8", errors="ignore")
        if "media=cdrom,file=" in text.lower():
            if App._cdrom_loaded(text, iso):
                messagebox.showinfo("MK Port", "Xemu arrancó CON tu disco. A jugar.")
            else:
                messagebox.showwarning("MK Port", "Xemu abrió pero SIN disco.\nEn Xemu: Machine → Load Disc → elige tu ISO.")
            return
        if tries < 4:
            self.after(4000, lambda: self._xemu_poll_boot(iso, log, mark, tries + 1))
        else:
            messagebox.showwarning("MK Port", "Xemu tarda en arrancar.\nSi ves 'insert disc': Machine → Load Disc → tu ISO.")

    # ---------- sala online ----------
    def _fill_ip(self, var, fn, what):
        try:
            ip = fn()
        except Exception:
            ip = ""
        if ip:
            var.set(ip)
            messagebox.showinfo("MK Port", f"{what}: {ip}\nYa quedó puesta para el link.")
        else:
            messagebox.showwarning("MK Port", f"No pude obtener {what}.\nRevisa tu internet.")

    def _howto_online(self):
        top = tk.Toplevel(self)
        theme.root(top)
        top.title("Jugar a distancia")
        top.geometry("460x430")
        top.resizable(False, False)
        theme.section(top, "Cartagena ↔ Bogotá (u otras ciudades)").pack(anchor="w", padx=12, pady=(8, 0))
        txt = (
            "OPCIÓN 1 — ZeroTier (recomendada, 10 min, sin abrir puertos):\n"
            "1. Los dos instalan ZeroTier (zerotier.com/download) y lo abren.\n"
            "2. Uno crea una red gratis en my.zerotier.com y anota el Network ID.\n"
            "3. En la red: autoriza los dos equipos (Auth) o ponla pública.\n"
            "4. Los dos: Join Network con ese ID.\n"
            "5. Cada uno ve su IP ZeroTier (empieza por 10.). Botón «Ver mis IPs».\n"
            "6. El host pone SU IP 10.x en el campo y crea la sala.\n"
            "7. Prueba: ping 10.x.x.x debe responder (<100 ms entre ciudades).\n\n"
            "OPCIÓN 2 — IP pública (solo si tu router deja abrir puertos):\n"
            "1. Host: abre UDP 34513 hacia tu PC + permite en Firewall Windows.\n"
            "2. Botón «Ver mi IP pública» y crea la sala con esa IP.\n"
            "3. Si tu operador usa CG-NAT no funcionará: vuelve a la opción 1.\n\n"
            "En ambos casos tu amigo entra con tu link mkport://."
        )
        theme.label(top, text=txt, justify="left").pack(padx=12, pady=6)

    def _lobby_menu(self):
        if self.lobby_win and self.lobby_win.winfo_exists():
            self.lobby_win.focus()
            return
        m = tk.Toplevel(self)
        theme.root(m)
        m.title("Sala online")
        m.geometry("380x320")
        m.resizable(False, False)
        theme.section(m, "Sala online").pack(anchor="w", padx=12, pady=(8, 0))
        theme.label(m, text="Cada uno abre su emulador con su ISO.\nLa sala sincroniza listos, inicio y skip de intro.",
                    fg=theme.MUTE).pack(pady=4)
        theme.label(m, text="Tu IP pública o ZeroTier (para el link):").pack()
        ip_var = tk.StringVar(value=self.cfg.get("public_ip", ""))
        theme.entry(m, textvariable=ip_var).pack(fill="x", padx=20)
        iprow = theme.frame(m)
        iprow.pack(pady=2)
        theme.button(iprow, text="Ver mi IP pública", kind="bronze",
                     command=lambda: self._fill_ip(ip_var, public_ip, "IP pública")).pack(side="left", padx=2)
        theme.button(iprow, text="Ver mis IPs", kind="bronze",
                     command=lambda: self._fill_ip(ip_var, lambda: (local_ips() or [""])[0],
                                                   "IP local (¿ZeroTier? la 10.x)")).pack(side="left", padx=2)
        theme.button(m, text="¿Cómo conectarnos a distancia?", kind="ghost",
                     command=self._howto_online).pack(pady=2)
        port = self.port_var.get() or "34513"

        def host():
            self.cfg["public_ip"] = ip_var.get()
            self._persist()
            core = LobbyCore(self.name_var.get() or "Player")
            try:
                core.start_host(int(port))
            except OSError as e:
                messagebox.showerror("MK Port", f"No pude abrir el puerto {port}: {e}")
                return
            link = make_link(ip_var.get() or "<TU-IP>", int(port), core.name)
            m.destroy()
            self._open_lobby(core, True, link)

        def join():
            from lobby_ui import LobbyWindow
            link_win = tk.Toplevel(self)
            theme.root(link_win)
            link_win.title("Unirse con link")
            link_win.geometry("360x150")
            link_win.resizable(False, False)
            theme.label(link_win, text="Pega el link mkport:// de tu amigo:").pack(pady=6)
            lv = tk.StringVar()
            theme.entry(link_win, textvariable=lv).pack(fill="x", padx=12)

            def go():
                try:
                    inv = parse_link(lv.get())
                except ValueError as e:
                    messagebox.showerror("MK Port", str(e))
                    return
                core = LobbyCore(self.name_var.get() or inv["name"])
                core.start_join(inv["host"], inv["port"])
                link_win.destroy()
                m.destroy()
                self._open_lobby(core, False)

            theme.button(link_win, text="Entrar", kind="jade", command=go, width=16).pack(pady=8)

        theme.button(m, text="Crear sala (soy host)", kind="blood", command=host).pack(fill="x", padx=40, pady=4)
        theme.button(m, text="Unirse con link", kind="jade", command=join).pack(fill="x", padx=40, pady=4)

    def _open_lobby(self, core, is_host, link=""):
        from lobby_ui import LobbyWindow

        def closed():
            self.lobby_win = None

        self.lobby_win = LobbyWindow(self, core, is_host, on_close=closed)
        if link:
            core.events.put(("log", "Tu link (pásalo a tu amigo): " + link))
            top = tk.Toplevel(self.lobby_win)
            theme.root(top)
            top.title("Link de invitación")
            top.geometry("420x140")
            theme.label(top, text="Pásale esto a tu amigo:").pack(padx=12, pady=4)
            e = theme.entry(top, width=50)
            e.pack(padx=12)
            e.insert(0, link)
            theme.button(top, text="Copiar", kind="bronze",
                         command=lambda: copy_clipboard(link)).pack(pady=6)


if __name__ == "__main__":
    App().mainloop()
