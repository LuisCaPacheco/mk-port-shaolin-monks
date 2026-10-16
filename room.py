"""room.py — cliente del matchmaking (códigos de 6 letras) + mini-STUN.

Flujo Tenkaichi adaptado: el host publica sus direcciones y recibe un código;
el invitado entra con el código y recibe las del host; ambos se taladran UDP
(hole punching) y juegan directo, sin VPN ni puertos abiertos.
Sin TURN todavía: pares tras NAT simétrico estricto no conectarán (ver README).
"""
from __future__ import annotations
import json
import os
import socket
import struct
import urllib.request

NET_VERSION = 2
STUN_SERVERS = (("stun.l.google.com", 19302), ("stun1.l.google.com", 19302))


def _post(url: str, payload: dict, timeout_s: int = 10) -> dict:
    import urllib.error
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "MKPort"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            out = json.loads(r.read(4096).decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read(4096).decode("utf-8"))
        except Exception:
            raise RuntimeError(f"servidor respondió {e.code}")
    if "error" in out:
        raise RuntimeError({"version": "versiones distintas: actualiza el port",
                            "no-room": "código inexistente o vencido (10 min)",
                            "full": "sala llena", "limit": "límite antiabuso, espera",
                            "open": "tienes 4 salas abiertas", "addrs": "sin direcciones",
                            "busy": "servidor ocupado, reintenta"}.get(
            out["error"], out["error"]))
    return out


def stun_mapped(timeout_s: int = 3) -> tuple[str, int]:
    """Tu ip:puerto públicos vistos por STUN. Lanza si no hay respuesta."""
    import os as _os
    txn = _os.urandom(12)
    req = struct.pack(">HHI12s", 0x0001, 0, 0x2112A442, txn)
    last = None
    for host, port in STUN_SERVERS:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(timeout_s)
            s.sendto(req, (host, port))
            data, _ = s.recvfrom(512)
        except Exception as e:
            last = e
            continue
        finally:
            s.close()
        if len(data) < 20 or struct.unpack(">H", data[0:2])[0] != 0x0101:
            continue
        if data[4:8] != struct.pack(">I", 0x2112A442) or data[8:20] != txn:
            continue
        off = 20
        while off + 4 <= len(data):
            typ, ln = struct.unpack(">HH", data[off:off + 4])
            val = data[off + 4:off + 4 + ln]
            if typ == 0x0020 and len(val) >= 8 and val[1] == 0x01:
                port_out = struct.unpack(">H", val[2:4])[0] ^ 0x2112
                ip_out = socket.inet_ntoa(bytes(b ^ k for b, k in zip(
                    val[4:8], struct.pack(">I", 0x2112A442))))
                return ip_out, port_out
            off += 4 + ((ln + 3) // 4) * 4
    raise RuntimeError(f"STUN sin respuesta ({last}).")


def my_addrs(lobby_port: int) -> list[str]:
    """Direcciones a publicar: pública STUN + locales (por si comparten red)."""
    out = []
    try:
        ip, _ = stun_mapped()
        out.append(f"{ip}:{lobby_port}")
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127.") and f"{ip}:{lobby_port}" not in out:
                out.append(f"{ip}:{lobby_port}")
    except Exception:
        pass
    return out


def host_room(match_url: str, name: str, addrs: list[str]) -> dict:
    return _post(match_url.rstrip("/") + "/v1/host",
                 {"v": NET_VERSION, "name": name, "addrs": addrs})


def join_room(match_url: str, code: str, name: str, addrs: list[str]) -> dict:
    return _post(match_url.rstrip("/") + "/v1/join",
                 {"v": NET_VERSION, "code": code, "name": name, "addrs": addrs})


def poll_room(match_url: str, code: str, key: str) -> dict:
    return _post(match_url.rstrip("/") + "/v1/poll", {"code": code, "key": key})


def leave_room(match_url: str, code: str, key: str):
    try:
        _post(match_url.rstrip("/") + "/v1/leave", {"code": code, "key": key})
    except Exception:
        pass
