"""test_lobby.py — sala host+join en loopback: listos, misión, arranque, skip, chat."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from online import LobbyCore

PORT = 34601
host = LobbyCore("LiuKang")
host.start_host(PORT)
join = LobbyCore("KungLao")
join.start_join("127.0.0.1", PORT)

# espera conexión
end = time.time() + 5
while time.time() < end and not join.connected:
    time.sleep(0.1)
assert join.connected, "join no conectó"
print("CONNECT OK")

join.set_ready(True)
time.sleep(1.5)
names = {p["name"]: p["ready"] for p in host.players}
assert names.get("KungLao") is True, host.players
print("READY OK:", host.players)

host.host_set_mission("Misión 1: Templo")
time.sleep(1.0)
assert join.mission == "Misión 1: Templo", join.mission
print("MISSION OK")

join.send_chat("listo?")
time.sleep(1.0)
host.host_start()
time.sleep(0.5)
join.send_skip()
time.sleep(1.5)

def drain(core):
    out = []
    while not core.events.empty():
        out.append(core.events.get())
    return out

he, je = drain(host), drain(join)
kinds_h = {e[0] for e in he}
kinds_j = {e[0] for e in je}
assert "countdown" in kinds_h and "countdown" in kinds_j, (kinds_h, kinds_j)
assert "skip" in kinds_h and "skip" in kinds_j, (kinds_h, kinds_j)
assert any(e[0] == "chat" and e[2] == "listo?" for e in he), he
print("START/SKIP/CHAT OK")
host.stop()
join.stop()
print("LOBBYTEST OK")
