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
from online import LobbyCore
from invite import make_link, parse_link, copy_clipboard

CONFIG = ROOT / "config.toml"


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
        self.geometry("520x470")
        self.resizable(False, False)
        self.valid_ok = False
        self.lobby_win = None

        rs = tk.Frame(self)
        rs.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(rs, text="Sistema:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.sys_var = tk.StringVar(value=self.cfg.get("system", "ps2"))
        for val, label in (("ps2", "PS2 + PCSX2"), ("xbox", "Xbox + Xemu")):
            tk.Radiobutton(rs, text=label, variable=self.sys_var, value=val,
                           command=self._switch_system).pack(side="left", padx=6)

        tk.Label(self, text="1) Tu ISO", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        r1 = tk.Frame(self)
        r1.pack(fill="x", padx=10)
        self.iso_var = tk.StringVar(value=self.cfg["image"])
        tk.Entry(r1, textvariable=self.iso_var).pack(side="left", fill="x", expand=True)
        tk.Button(r1, text="Buscar ISO...", command=self._pick_iso).pack(side="left", padx=4)

        tk.Label(self, text="Validación (debe decir Shaolin Monks)", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)
        self.checks = tk.Listbox(self, height=6)
        self.checks.pack(fill="x", padx=10)
        self.result = tk.Label(self, text="Sin validar", fg="gray")
        self.result.pack()

        self.emu_label = tk.Label(self, text="2) Emulador", font=("Segoe UI", 10, "bold"))
        self.emu_label.pack(anchor="w", padx=10)
        r2 = tk.Frame(self)
        r2.pack(fill="x", padx=10)
        self.emu_var = tk.StringVar(value=self.cfg["emulator"])
        tk.Entry(r2, textvariable=self.emu_var).pack(side="left", fill="x", expand=True)
        self.emu_btn = tk.Button(r2, text="Buscar exe...", command=self._pick_emu)
        self.emu_btn.pack(side="left", padx=4)

        r3 = tk.Frame(self)
        r3.pack(fill="x", padx=10)
        tk.Label(r3, text="Tu nombre:").pack(side="left")
        self.name_var = tk.StringVar(value=self.cfg["name"])
        tk.Entry(r3, textvariable=self.name_var, width=16).pack(side="left", padx=4)
        tk.Label(r3, text="Puerto:").pack(side="left")
        self.port_var = tk.StringVar(value=self.cfg["port"])
        tk.Entry(r3, textvariable=self.port_var, width=8).pack(side="left")

        r4 = tk.Frame(self)
        r4.pack(pady=8)
        tk.Button(r4, text="VALIDAR ISO", command=self._validate).pack(side="left", padx=4)
        self.play_btn = tk.Button(r4, text="JUGAR", command=self._play, bg="#cfe8cf")
        self.play_btn.pack(side="left", padx=4)
        tk.Button(r4, text="SALA ONLINE", command=self._lobby_menu, bg="#cfe0f5").pack(side="left", padx=4)

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
        self.emu_label.config(text="2) PCSX2" if ps2 else "2) Xemu")
        self.emu_btn.config(text="Buscar pcsx2.exe..." if ps2 else "Buscar xemu.exe...")
        self.play_btn.config(text="JUGAR EN PCSX2" if ps2 else "JUGAR EN XEMU")

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
        self.result.config(text=msg, fg="green" if ok else "red")
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
    def _lobby_menu(self):
        if self.lobby_win and self.lobby_win.winfo_exists():
            self.lobby_win.focus()
            return
        m = tk.Toplevel(self)
        m.title("Sala online")
        m.geometry("360x300")
        m.resizable(False, False)
        tk.Label(m, text="Cada jugador abre SU Xemu con SU xiso.\nLa sala sincroniza listos, inicio y skip de intro.",
                 fg="gray").pack(pady=6)
        tk.Label(m, text="Tu IP pública o ZeroTier (para el link):").pack()
        ip_var = tk.StringVar(value=self.cfg.get("public_ip", ""))
        tk.Entry(m, textvariable=ip_var).pack(fill="x", padx=20)
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
            link_win.title("Unirse con link")
            link_win.geometry("340x140")
            tk.Label(link_win, text="Pega el link mkport:// de tu amigo:").pack(pady=4)
            lv = tk.StringVar()
            tk.Entry(link_win, textvariable=lv).pack(fill="x", padx=12)

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

            tk.Button(link_win, text="ENTRAR", command=go).pack(pady=8)

        tk.Button(m, text="CREAR SALA (soy host)", command=host, bg="#cfe8cf").pack(fill="x", padx=40, pady=4)
        tk.Button(m, text="UNIRSE CON LINK", command=join, bg="#cfe0f5").pack(fill="x", padx=40, pady=4)

    def _open_lobby(self, core, is_host, link=""):
        from lobby_ui import LobbyWindow

        def closed():
            self.lobby_win = None

        self.lobby_win = LobbyWindow(self, core, is_host, on_close=closed)
        if link:
            top = tk.Toplevel(self.lobby_win)
            top.title("Link de invitación")
            tk.Label(top, text="Pásale esto a tu amigo:").pack(padx=12, pady=4)
            tk.Entry(top, width=50).pack(padx=12)
            for w in top.children.values():
                if isinstance(w, tk.Entry):
                    w.insert(0, link)
            tk.Button(top, text="Copiar",
                      command=lambda: copy_clipboard(link)).pack(pady=6)


if __name__ == "__main__":
    App().mainloop()
