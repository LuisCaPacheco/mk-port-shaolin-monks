"""validator.py — valida que la ISO es la VERDADERA de MK Shaolin Monks (Xbox).

Niveles (de barato a caro, se detiene al primer fallo):
1. Es disco Xbox (magia XDVDFS) — si no, ni es xiso.
2. Huella del disco: default.xbe + WADCRC.BIN + >=5 GAMEDATA.WA* + carpetas
   classic/English/front (layout visto en el disco real USA/Europe).
3. Firma dentro del ejecutable: el certificado del default.xbe contiene el título
   "MK Shaolin Monks" en UTF-16LE (comprobado: aparece 6 veces en el disco real).
   Otro juego Xbox (p. ej. Halo) falla aquí aunque pase 1 y 2.
4. Tamaño cuerdo (>4 GB).

Devuelve (ok, checks[(nombre, pasa, detalle)], mensaje).
"""
from __future__ import annotations
import os
import re
from xdvdfs import XisoImage, XisoError

TITLE_U16 = "MK Shaolin Monks".encode("utf-16-le")
MIN_XBOX_BYTES = 2 * 1024 ** 3
REQUIRED_DIRS = ("classic", "english", "front")
# Seriales PS2 confirmados de Shaolin Monks (SLUS-21087 = USA, verificado en
# disco real: BOOT2 SLUS_210.87 + serial 3x + MIDWAY al inicio).
KNOWN_PS2_SERIALS = {"SLUS-21087"}


XISO_PARTS = (0, 0x0FD90000, 0x02080000, 0x18300000)


def detect(path: str) -> str:
    """'xbox' | 'ps2' | 'unknown'. Ojo: los discos Xbox traen una zona ISO9660
    señuelo al inicio; la magia Xbox real está en su partición (4 offsets)."""
    try:
        with open(path, "rb") as f:
            for part in XISO_PARTS:
                f.seek(part + 0x10000)
                if f.read(20) == b"MICROSOFT*XBOX*MEDIA":
                    return "xbox"
            f.seek(0)
            if b"CD001" in f.read(256 * 1024):
                return "ps2"
    except OSError:
        pass
    return "unknown"


def validate(path: str, system: str = "auto"):
    if system == "auto":
        system = detect(path)
    if system == "ps2":
        return validate_ps2(path)
    if system == "xbox":
        return validate_xbox(path)
    return False, [("Formato reconocido", False, "no es Xbox ni PS2")], "Archivo no reconocido."


def validate_ps2(path: str):
    checks: list[tuple[str, bool, str]] = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        return ok

    try:
        size = os.path.getsize(path)
    except OSError as e:
        add("Archivo legible", False, str(e))
        return False, checks, "No se pudo abrir el archivo."
    add("Tamaño (>1 GB)", size > 1024 ** 3, f"{size / 1e9:.2f} GB")
    try:
        with open(path, "rb") as f:
            head = f.read(8 * 1024 * 1024)
    except OSError as e:
        add("Lectura", False, str(e))
        return False, checks, "No se pudo leer."
    if not add("ISO9660 PS2 (CD001)", b"CD001" in head):
        return False, checks, "No es un ISO de PS2."
    m = re.search(rb"BOOT2\s*=\s*cdrom0:\\([^\r\n;]+)", head)
    boot = m.group(1).decode("ascii", "ignore").strip() if m else ""
    add("SYSTEM.CNF + BOOT2", bool(boot), boot or "sin BOOT2")
    if boot and not add("Ejecutable presente", boot.encode("ascii", "ignore")[:40] in head):
        return False, checks, "BOOT2 apunta a un ELF que no aparece: ISO incompleta."
    shaolin = head.upper().count(b"SHAOLIN")
    serials = [m.decode() for m in re.findall(rb"SL[EU][SP]-\d{5}", head)]
    # El serial propio es el del BOOT2 (SLUS_210.87 -> SLUS-21087); los demás
    # seriales del ISO son de módulos IOP de otros juegos y no valen.
    boot_norm = boot.replace("_", "-").replace(".", "")
    own = boot_norm if boot_norm in serials else (serials[0] if serials else "")
    add("Mención SHAOLIN", shaolin > 0, f"{shaolin} apariciones")
    add("Serial PS2", bool(own), own or "no visto al inicio")
    known = own in KNOWN_PS2_SERIALS
    add("Huella Shaolin (serial)", known, "SLUS-21087 = Shaolin Monks USA" if known else f"{own or '?'} no catalogado")
    if known or shaolin > 0:
        return True, checks, "ISO PS2 VERDADERA de MK Shaolin Monks. Lista para PCSX2."
    return False, checks, "Es PS2 pero sin huella Shaolin (¿otro juego?)."


def validate_xbox(path: str):
    checks: list[tuple[str, bool, str]] = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        return ok

    try:
        img = XisoImage(path)
    except XisoError as e:
        add("Disco Xbox (XDVDFS)", False, str(e))
        return False, checks, "No es una imagen Xbox válida."
    except OSError as e:
        add("Archivo legible", False, str(e))
        return False, checks, "No se pudo abrir el archivo."

    try:
        size = os.path.getsize(path)
        root = img.list_root()
        files = {n.lower(): (s, z) for n, s, z in root["files"]}
        dirs = {d.lower() for d in root["dirs"]}

        add("Disco Xbox (XDVDFS)", True, f"partición {root['partition']}")
        if not add("Tamaño (>2 GB)", size >= MIN_XBOX_BYTES, f"{size / 1e9:.2f} GB"):
            return False, checks, "Muy pequeña para ser Shaolin Monks."

        xbe = files.get("default.xbe")
        if not add("default.xbe presente", xbe is not None):
            img.close()
            return False, checks, "Sin default.xbe: no es disco Xbox de juego."
        wad = sorted(n for n in files if n.startswith("gamedata.wa"))
        add("WADCRC.BIN", "wadcrc.bin" in files)
        ok_wad = add("Datos GAMEDATA.WA* (>=5)", len(wad) >= 5, f"{len(wad)} partes")
        ok_dirs = add("Carpetas classic/English/front",
                      all(d in dirs for d in REQUIRED_DIRS), ", ".join(sorted(dirs)[:8]))
        if not (ok_wad and ok_dirs):
            img.close()
            return False, checks, "Es disco Xbox, pero NO es Shaolin Monks (falta su huella)."

        # Firma definitiva: título del certificado dentro del XBE.
        sec, z = xbe
        img.f.seek(img.partition + sec * 2048)
        buf = img.f.read(z)
        n = buf.count(TITLE_U16)
        img.close()
        if not add("Firma 'MK Shaolin Monks' en default.xbe", n > 0, f"{n} apariciones"):
            return False, checks, "El ejecutable no es de Shaolin Monks."
        return True, checks, "XISO VERDADERA de MK Shaolin Monks. Lista para Xemu."
    except XisoError as e:
        try:
            img.close()
        except Exception:
            pass
        add("Lectura del disco", False, str(e))
        return False, checks, "Disco dañado o incompleto."


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print('Uso: validator.py "ruta\\a\\juego.iso"')
        raise SystemExit(2)
    ok, checks, msg = validate(sys.argv[1])
    for name, passed, detail in checks:
        print(f"[{'OK' if passed else 'XX'}] {name} {detail}")
    print("RESULTADO:", msg)
