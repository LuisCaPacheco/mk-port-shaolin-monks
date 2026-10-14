"""online.py — sala coop: lobby, listos, arranque conjunto y skip de intro.

Modelo honesto: cada jugador corre SU Xemu con SU xiso en SU PC.
Esta sala NO sincroniza el gameplay (eso exigiría netplay determinista que Xemu
no tiene); sincroniza la SESIÓN: quién está, quién está listo, misión elegida,
cuenta atrás para empezar a la vez y señal de "saltar intro ahora".
Sin GUI aquí (LobbyCore puro) para poder probarlo sin ventana.
"""
from __future__ import annotations
import json
import queue
import socket
import threading
import time

NET_VERSION = 2
TICK = 0.05
PEER_TIMEOUT = 15.0
MAX_DATAGRAM = 1400


def _now():
    return time.time()


class LobbyCore:
    def __init__(self, name="Player"):
        self.name = (name or "Player")[:16]
        self.events: queue.Queue = queue.Queue()
        self.is_host = False
        self.running = False
        self.players: list[dict] = []   # [{name, ready, me}]
        self.mission = ""
        self.connected = False
        self.ping_ms: float | None = None
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._peers: dict = {}          # host: addr -> {name, ready, last}
        self._host_addr = None          # join: (host, port)
        self._ready = False
        self._last_state = 0.0
        self._ping_t = 0
        self._ping_sent: dict[int, float] = {}
        self._rtts: list[float] = []

    # ---------- ciclo de vida ----------
    def start_host(self, port: int):
        self.is_host = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", port))
        self._sock.settimeout(0.2)
        self._begin()
        self._push(("log", f"Sala abierta en UDP {port}. Pasa tu link."))
        self._refresh_players()

    def start_join(self, host: str, port: int):
        self.is_host = False
        self._host_addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(0.2)
        self._begin()
        self._push(("log", f"Conectando a {host}:{port} ..."))

    def _begin(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        if self.running and self._sock:
            try:
                msg = {"t": "BYE", "v": NET_VERSION, "name": self.name}
                if self.is_host:
                    for addr in list(self._peers):
                        self._send(msg, addr)
                elif self._host_addr:
                    self._send(msg, self._host_addr)
            except Exception:
                pass
        self.running = False
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass

    # ---------- acciones ----------
    def set_ready(self, ready: bool):
        self._ready = bool(ready)
        if self.is_host:
            self._refresh_players()
            self._broadcast_state()
        elif self._host_addr:
            self._send({"t": "READY", "v": NET_VERSION, "name": self.name, "ready": self._ready},
                       self._host_addr)

    def send_chat(self, text: str):
        text = (text or "")[:200]
        if not text:
            return
        if self.is_host:
            self._push(("chat", self.name, text))
            self._broadcast({"t": "CHAT", "v": NET_VERSION, "name": self.name, "text": text})
        elif self._host_addr:
            self._send({"t": "CHAT", "v": NET_VERSION, "name": self.name, "text": text},
                       self._host_addr)
            self._push(("chat", self.name, text))

    def host_set_mission(self, text: str):
        if not self.is_host:
            return
        self.mission = (text or "")[:80]
        self._peers_ready_reset()
        self._push(("mission", self.mission))
        self._broadcast({"t": "MISSION", "v": NET_VERSION, "text": self.mission})
        self._broadcast_state()

    def host_start(self):
        """Solo host, idealmente con todos listos. Cuenta atrás 3s en ambas ventanas."""
        if not self.is_host:
            return
        self._broadcast({"t": "START", "v": NET_VERSION, "at": _now() + 3})
        self._push(("countdown", 3))

    def send_skip(self):
        msg = {"t": "SKIP", "v": NET_VERSION, "name": self.name}
        if self.is_host:
            self._broadcast(msg)
            self._push(("skip", self.name))
        elif self._host_addr:
            self._send(msg, self._host_addr)

    # ---------- red ----------
    def _send(self, msg: dict, addr):
        try:
            self._sock.sendto(json.dumps(msg).encode("utf-8")[:MAX_DATAGRAM], addr)
        except Exception:
            pass

    def _broadcast(self, msg: dict):
        for addr in list(self._peers):
            self._send(msg, addr)

    def _push(self, ev):
        self.events.put(ev)

    def _loop(self):
        hello_every = 0.0
        while self.running:
            now = _now()
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                data, addr = None, None
            except OSError:
                break
            if data:
                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    msg = None
                if isinstance(msg, dict) and msg.get("v") == NET_VERSION:
                    self._on_msg(msg, addr)
            if self.is_host:
                # Limpia caídos (15s, como OpenCE) y publica estado 1Hz
                drop = [a for a, p in self._peers.items() if now - p["last"] > PEER_TIMEOUT]
                for a in drop:
                    self._push(("log", f"{self._peers[a]['name']} salió (timeout)."))
                    del self._peers[a]
                    self._refresh_players()
                if now - self._last_state >= 1.0:
                    self._last_state = now
                    self._broadcast_state()
            else:
                if not self.connected and now >= hello_every:
                    hello_every = now + 1.0
                    self._send({"t": "HELLO", "v": NET_VERSION, "name": self.name}, self._host_addr)
                if self.connected:
                    if now - self._ping_t >= 2.0:
                        self._ping_t = now
                        t = int(now * 1000) & 0xFFFFFFFF
                        self._ping_sent[t] = now
                        self._send({"t": "PING", "v": NET_VERSION, "t2": t}, self._host_addr)

    def _on_msg(self, msg: dict, addr):
        t = msg.get("t")
        now = _now()
        if self.is_host:
            if t == "HELLO":
                name = str(msg.get("name", "P?"))[:16]
                new = addr not in self._peers
                self._peers[addr] = {"name": name, "ready": False, "last": now}
                self._send({"t": "WELCOME", "v": NET_VERSION, "name": self.name,
                            "mission": self.mission}, addr)
                if new:
                    self._push(("log", f"{name} entró a la sala."))
                self._refresh_players()
                self._broadcast_state()
            elif addr in self._peers:
                self._peers[addr]["last"] = now
                if t == "READY":
                    self._peers[addr]["ready"] = bool(msg.get("ready"))
                    self._refresh_players()
                    self._broadcast_state()
                elif t == "CHAT":
                    text = str(msg.get("text", ""))[:200]
                    self._push(("chat", self._peers[addr]["name"], text))
                    relay = {"t": "CHAT", "v": NET_VERSION,
                             "name": self._peers[addr]["name"], "text": text}
                    for a in list(self._peers):
                        if a != addr:
                            self._send(relay, a)
                elif t == "SKIP":
                    who = self._peers[addr]["name"]
                    self._push(("skip", who))
                    self._broadcast({"t": "SKIP", "v": NET_VERSION, "name": who})
                elif t == "PING":
                    self._send({"t": "PONG", "v": NET_VERSION, "t2": msg.get("t2", 0)}, addr)
                elif t == "BYE":
                    self._push(("log", f"{self._peers[addr]['name']} salió."))
                    del self._peers[addr]
                    self._refresh_players()
                    self._broadcast_state()
        else:
            if addr != self._host_addr:
                return
            if t == "WELCOME":
                if not self.connected:
                    self.connected = True
                    self._push(("conn", True))
                    self._push(("log", "Conectado a la sala. Márcate LISTO."))
                self.mission = str(msg.get("mission", ""))
                self._push(("mission", self.mission))
            elif t == "STATE":
                self.connected = True
                self.players = msg.get("players", [])
                self._push(("players", self.players))
            elif t == "MISSION":
                self.mission = str(msg.get("text", ""))
                self._push(("mission", self.mission))
                self._push(("log", f"Misión: {self.mission or '(sin definir)'}"))
            elif t == "START":
                self._push(("countdown", 3))
            elif t == "SKIP":
                self._push(("skip", str(msg.get("name", "?"))))
            elif t == "CHAT":
                self._push(("chat", str(msg.get("name", "?")), str(msg.get("text", ""))[:200]))
            elif t == "PONG":
                sent = self._ping_sent.pop(int(msg.get("t2", -1)), None)
                if sent is not None:
                    self._rtts.append((now - sent) * 1000.0)
                    self._rtts = self._rtts[-10:]
                    self.ping_ms = sum(self._rtts) / len(self._rtts)
                    self._push(("ping", self.ping_ms))
            elif t == "BYE":
                self._push(("log", "El host cerró la sala."))
                self.connected = False
                self._push(("conn", False))

    # ---------- estado local (host) ----------
    def _peers_ready_reset(self):
        self._ready = False
        for p in self._peers.values():
            p["ready"] = False

    def _refresh_players(self):
        self.players = [{"name": self.name, "ready": self._ready, "me": True}]
        for p in self._peers.values():
            self.players.append({"name": p["name"], "ready": p["ready"], "me": False})
        self._push(("players", self.players))

    def _broadcast_state(self):
        self._refresh_players()
        self._send_state_to_all()

    def _send_state_to_all(self):
        self._broadcast({"t": "STATE", "v": NET_VERSION, "players": self.players,
                         "mission": self.mission})
