"""zerotier.py — automatiza ZeroTier por CLI (sin abrir su app a mano).

Cubre: detectar instalado, unirse a una red, esperar la IP 10.x y leerla.
NO puede: instalarlo (descarga en zerotier.com/download), crear la red
(eso es en my.zerotier.com) ni autorizar equipos (lo hace el admin de la red,
salvo redes públicas). Todo con timeouts y errores claros.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import time

CLI = "zerotier-cli"


def available() -> bool:
    return shutil.which(CLI) is not None


def _run(*args, timeout_s: int = 10) -> str:
    p = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=timeout_s)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "zerotier-cli falló").strip()[:200])
    return p.stdout


def info() -> str:
    """'200 info <node> <ver> ONLINE' si el servicio anda."""
    return _run("info")


def online() -> bool:
    try:
        return "ONLINE" in info().upper()
    except Exception:
        return False


def networks() -> list[dict]:
    """[{'id','name','status','ips':[...]}]. Vacío si no hay redes."""
    try:
        data = json.loads(_run("-j", "listnetworks"))
    except Exception:
        return []
    out = []
    for n in data if isinstance(data, list) else []:
        out.append({
            "id": n.get("nwid") or n.get("id") or "",
            "name": n.get("name") or "",
            "status": n.get("status") or "",
            "ips": [a.split("/")[0] for a in (n.get("assignedAddresses") or [])
                    if "/" in a and "." in a and not a.startswith("127.")],
        })
    return out


def join(net_id: str) -> str:
    net_id = (net_id or "").strip().lower()
    if len(net_id) != 16 or any(c not in "0123456789abcdef" for c in net_id):
        raise ValueError("Network ID inválido (16 hex, ej. a09acf0233xxx).")
    return _run("join", net_id)


def wait_ip(net_id: str, timeout_s: int = 60) -> str:
    """Espera la IP asignada en esa red. Lanza si autoriza/tarda."""
    end = time.time() + timeout_s
    last_status = ""
    while time.time() < end:
        for n in networks():
            if n["id"].lower() == net_id.lower():
                last_status = n["status"]
                if n["ips"]:
                    return n["ips"][0]
        time.sleep(2)
    if "ACCESS_DENIED" in last_status.upper():
        raise TimeoutError("La red no te autorizó (pide al admin que te dé Auth).")
    raise TimeoutError("Sin IP tras 60s (¿servicio caído o red inexistente?).")


def my_ip(net_id: str = "") -> str:
    """Mi primera IP ZeroTier (de esa red si la pides)."""
    for n in networks():
        if net_id and n["id"].lower() != net_id.lower():
            continue
        if n["ips"]:
            return n["ips"][0]
    return ""


def parse_networks_json(text: str) -> list[dict]:
    """Parser puro (testeable sin ZeroTier instalado)."""
    data = json.loads(text)
    out = []
    for n in data if isinstance(data, list) else []:
        out.append({
            "id": n.get("nwid") or n.get("id") or "",
            "name": n.get("name") or "",
            "status": n.get("status") or "",
            "ips": [a.split("/")[0] for a in (n.get("assignedAddresses") or [])
                    if "/" in a and "." in a and not a.startswith("127.")],
        })
    return out
