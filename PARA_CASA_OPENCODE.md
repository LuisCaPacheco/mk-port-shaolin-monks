# Contexto para OpenCode (casa) — MK Port, léeme primero si algo falla

Eres el agente de casa continuando este proyecto. Hechos verificados, no suposiciones.

## Qué es
Launcher + validador + sala online para Mortal Kombat: Shaolin Monks (PS2 primero,
Xbox como plan B). El emulador corre el juego; el port valida la ISO, lanza el
emulador y coordina la sesión online (listos, misión, 3-2-1, skip de intro).
NO sincroniza gameplay (Xemu/PCSX2 no tienen netplay determinista) y NO incluye
juego, BIOS ni SDK. Nunca pidas ni pases ISOs/BIOS con copyright.

## Estructura (`D:\proyectos luis\Ports\MK Port\` aquí; en casa, la carpeta del repo)
- `mkport.py` — GUI tkinter. Selector PS2/Xbox, validar, jugar, sala. Compilado a
  `MKPort.exe` con PyInstaller (`--onefile --noconsole`). Congelado: `ROOT` = carpeta
  del exe (ver inicio del archivo). `config.toml` está gitignored; plantilla en
  `config.example.toml`.
- `validator.py` — `validate(path, system)`. Xbox: XDVDFS en 4 offsets de partición
  (0, 0xFD90000, 0x2080000, 0x1830000) + default.xbe + WADCRC.BIN + >=5 GAMEDATA.WA*
  + carpetas classic/English/front + firma `MK Shaolin Monks` UTF-16LE en el XBE
  (6 apariciones en disco real). PS2: ISO9660 + SYSTEM.CNF/BOOT2 + serial propio
  del BOOT2 en `KNOWN_PS2_SERIALS` (hoy: `SLUS-21087` USA). OJO: los ISO traen
  seriales ajenos (módulos IOP) y los Xbox una zona ISO9660 señuelo al inicio —
  por eso `detect()` mira offsets de partición, no solo la cabecera.
- `xdvdfs.py` — lector XDVDFS, port de OpenCE `port/linux/src/xiso.c` (crédito BSD
  en el archivo). Probado contra Halo real: 24 maps, ui.map, extracción byte a byte.
- `online.py` — `LobbyCore` sin GUI (host autoritativo, JSON por UDP, v2):
  HELLO/WELCOME/READY/STATE(1Hz)/MISSION/START(3s)/SKIP/CHAT/PING/PONG/BYE,
  timeout 15s. Probado loopback en `test_lobby.py` (debe decir LOBBYTEST OK).
- `lobby_ui.py`, `invite.py` (`mkport://v2/host/puerto/nombre`, clipboard por
  `clip.exe` en Windows — tkinter crashea sin escritorio, ver abajo).

## Datos duros verificados
- ISO Xbox real: 7.83 GB, partición `0x18300000`, root con default.xbe (5.6 MB),
  GAMEDATA.WAD–WAK (2.34 GB), WADCRC.BIN, carpetas classic/English/front.
- ISO PS2 real: 3.09 GB, BOOT2 `SLUS_210.87`, serial `SLUS-21087` (3x), `MIDWAY` (3x),
  SIN "SHAOLIN" ASCII en los primeros 64 MB (no usar como condición).
- Xemu 0.8.136: clave `dvd_path` en `[sys.files]` de `%APPDATA%\xemu\xemu\xemu.toml`
  (confirmada en el binario) + flag CLI `-dvd_path <iso>`. Saga "insert disc":
  era doble instancia (la vieja sin disco) — el launcher mata-espera 8s, escribe
  toml, lanza y verifica el arranque en el log (`media=cdrom,file=`, delta del log,
  hasta 20s). Si igual abre sin disco: Machine → Load Disc manual.
- PCSX2-Qt 2.8.2: acepta ISO posicional + `-slowboot` (confirmado en el binario);
  el launcher usa `[emu, "-slowboot", iso]`. Pide BIOS de PS2 propia la 1ª vez.
- Red: UDP 34513 por defecto; sin IP pública usar ZeroTier (el link lleva esa IP).

## Trampas conocidas (no redescubrir)
1. tkinter `Tk()` hace access violation en sesiones sin escritorio (agentes/SSH).
   Nunca instancies GUI en pruebas: importa módulos y prueba lógica (`App` solo
   vive bajo `if __name__ == "__main__"`; `_cdrom_loaded`, `validate_*`,
   `LobbyCore` son headless-safe). El crash enmascara stdout (usar `flush=True`).
2. `config.toml` se corrompía al re-guardar comentarios — el parser actual respeta
   comillas e ignora `#` final. No volver al `strip('"')` ingenuo.
3. `autodetect()` solo acepta ISOs cuya magia coincide con el sistema (usa
   `validator.detect`), para no pre-cargar la ISO de Xbox en modo PS2.
4. No compilar el exe con la app abierta (Windows bloquea el archivo): matar
   `MKPort.exe` antes de `Move-Item`. Limpiar `build/ dist/ *.spec` tras compilar.
5. `test_boot.py` escribe en el xemu.toml REAL con backup/restore — avisar antes
   de correrlo en casa si ya hay config afinada.

## Si algo falla en casa, orden de diagnóstico
1. `py -3 validator.py "ruta\iso"` (Xbox y PS2) — la huella dice qué disco es.
2. `py -3 test_lobby.py` — red local OK o no.
3. Emulador a mano (Load/Boot ISO) antes de culpar al launcher.
4. Logs: `xemu.log` (junto al exe) / PCSX2 `emulog.txt` + `media=cdrom,file=` /
   `GetIsoSerialAndCRC`.
5. Recién entonces tocar código; revalidar con 1–4 y recompilar el exe.
