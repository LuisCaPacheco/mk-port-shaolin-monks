# MK Port — Shaolin Monks (PS2 + Xbox)

Port mínimo y honesto: **valida tu ISO, lanza el emulador y abre sala coop.**
El emulador corre el juego; el port aporta validación de ISO verdadera +
sala online con listos/inicio/skip de intro (lo que ningún emulador trae).

```
Doble clic a MKPort.exe   (no necesitas Python ni consola)
```

¿Lo llevas a otro PC o lo probará un amigo? Lee `PROBAR_EN_CASA.md`
(checklist) y `PARA_CASA_OPENCODE.md` (contexto para tu agente si algo falla).
Al repo NO se suben ISOs, BIOS ni `config.toml` (ver `.gitignore`): cada uno
usa su disco volcado + `config.example.toml` como plantilla.

Arriba eliges sistema: **PS2 + PCSX2** (recomendado) o Xbox + Xemu.

1. **Buscar ISO** → la valida sola:
   - PS2: ISO9660 + SYSTEM.CNF/BOOT2 + huella SHAOLIN.
   - Xbox: disco real + huella (default.xbe, WADCRC.BIN, GAMEDATA.WA*,
     classic/English/front) + firma `MK Shaolin Monks` en el ejecutable.
   Un Halo u otro juego falla con "NO es Shaolin Monks".
2. **JUGAR** → abre tu ISO en PCSX2/Xemu (configura su exe una vez).
   - PCSX2 primera vez pide la BIOS de tu PS2; Xemu pide MCPX+flash de tu Xbox.
   - Si abre sin disco: System/ Machine → Boot/Load ISO o Disc → tu ISO.
3. **SALA ONLINE** → crea sala (link `mkport://` para tu amigo) o únete con link.
   Cada uno corre SU emulador con SU ISO; la sala sincroniza jugadores, listos,
   misión, cuenta 3-2-1 para empezar a la vez y botón SALTAR INTRO que avisa a ambos.

Requisito online: poder alcanzarse por UDP (puerto 34513). Sin IP pública usa ZeroTier
(los dos en la misma red virtual, el link lleva esa IP).

Archivos: `mkport.py` (launcher), `validator.py`, `xdvdfs.py` (lector XDVDFS, port de
OpenCE `xiso.c` con su crédito BSD), `online.py` (protocolo sala v2), `lobby_ui.py`,
`invite.py`, `config.toml`. Nada incluye juego, BIOS ni SDK: trae tu disco volcado.
