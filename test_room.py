"""test_room.py — flujo de códigos contra stub local + STUN real (best-effort)."""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import room as roomcl
from online import LobbyCore

ROOMS = {}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, o, code=200):
        b = json.dumps(o).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0) or 0) or b"{}")
        if self.path == "/v1/host":
            if body.get("v") != 2:
                return self._send({"error": "version"})
            ROOMS["ABC234"] = {"host_key": "hk", "join_key": None,
                               "host_name": body.get("name"), "host_addrs": body.get("addrs")}
            return self._send({"code": "ABC234", "key": "hk", "you": "9.9.9.9"})
        if self.path == "/v1/join":
            r = ROOMS.get(str(body.get("code", "")).upper())
            if not r:
                return self._send({"error": "no-room"}, 404)
            r.update(join_key="jk", join_name=body.get("name"), join_addrs=body.get("addrs"))
            return self._send({"key": "jk", "you": "8.8.8.8",
                               "peer": {"name": r["host_name"], "addrs": r["host_addrs"]}})
        if self.path == "/v1/poll":
            r = ROOMS.get(str(body.get("code", "")).upper())
            if not r:
                return self._send({"error": "no-room"}, 404)
            if body.get("key") == "hk" and r.get("join_addrs"):
                return self._send({"peer": {"name": r["join_name"], "addrs": r["join_addrs"]}})
            return self._send({"peer": None})
        return self._send({"error": "path"}, 404)


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}"

h = roomcl.host_room(URL, "LiuKang", ["127.0.0.1:34711"])
assert h["code"] == "ABC234" and h["key"] == "hk", h
print("HOST-CODE OK")
try:
    roomcl.join_room(URL, "ZZZZZZ", "X", ["127.0.0.1:1"])
    raise SystemExit("debió fallar código malo")
except RuntimeError as e:
    print("BAD-CODE OK:", e)
j = roomcl.join_room(URL, "abc234", "KungLao", ["127.0.0.1:34712"])
assert j["peer"]["name"] == "LiuKang", j
print("JOIN-CODE OK:", j["peer"])
p = roomcl.poll_room(URL, "ABC234", "hk")
assert p["peer"]["name"] == "KungLao", p
print("POLL OK")

host = LobbyCore("LiuKang")
host.start_host(34711)
join = LobbyCore("KungLao")
join.start_join_addrs([("127.0.0.1", 34711)])
end = time.time() + 5
while time.time() < end and not join.connected:
    time.sleep(0.1)
assert join.connected, "punch loopback falló"
join.set_ready(True)
time.sleep(1.2)
assert any(pl["name"] == "KungLao" and pl["ready"] for pl in host.players), host.players
print("PUNCH+READY OK")
host.stop()
join.stop()

try:
    ip, port = roomcl.stun_mapped()
    print(f"STUN-LIVE OK: {ip}:{port}")
except Exception as e:
    print(f"STUN-LIVE no disponible aquí ({e}) — en casa reintentar")
print("ROOMTEST OK")
