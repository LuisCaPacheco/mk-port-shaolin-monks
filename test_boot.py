"""test_boot.py — verifica escritura de dvd_path en xemu.toml (con backup/restore)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mkport import App

TOML = Path(r"C:\Users\Dev4\AppData\Roaming\xemu\xemu\xemu.toml")
bak = TOML.read_text(encoding="utf-8")
try:
    App._xemu_set_disc(r"X:\fake\juego.iso")
    txt = TOML.read_text(encoding="utf-8")
    assert "dvd_path = 'X:\\fake\\juego.iso'" in txt, txt
    # idempotente: segunda vez no duplica
    App._xemu_set_disc(r"X:\fake\juego.iso")
    txt2 = TOML.read_text(encoding="utf-8")
    assert txt2.count("dvd_path") == 1, txt2
    print("TOML-WRITE OK (sin duplicados)")
finally:
    TOML.write_text(bak, encoding="utf-8")
    print("xemu.toml restaurado")
