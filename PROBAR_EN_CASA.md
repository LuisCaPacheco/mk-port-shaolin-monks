# Probar en casa — checklist (PC propio, no el del trabajo)

Todo lo de abajo es lo que NO se pudo probar en el PC del trabajo (sin escritorio
para la GUI ni BIOS). Ve en orden; si un paso falla, párate ahí y revisa.

## 0. Llevarse todo
- [ ] Carpeta `MK Port` completa (o `git clone` del repo).
- [ ] Tu ISO PS2 de Shaolin Monks + PCSX2 portable + tu BIOS de PS2.
- [ ] Para online: ZeroTier instalado (o IP pública + UDP 34513 abierto).

## 1. App abre (2 min)
- [ ] Doble clic `MKPort.exe` → ventana "MK Port — Shaolin Monks", modo PS2.
- [ ] Si Windows bloquea: Más información → Ejecutar de todas formas.
- [ ] Si no abre nada: alternativa `MKPort.bat` (requiere Python 3.10+).

## 2. Valida tu ISO (1 min)
- [ ] `Buscar ISO...` → tu ISO PS2 → debe decir
      `ISO PS2 VERDADERA de MK Shaolin Monks. Lista para PCSX2.` en verde.
- [ ] Si dice otra cosa, copia el texto exacto de la lista y revísalo con tu agente.

## 3. Arranca en PCSX2 (10 min)
- [ ] `Buscar pcsx2.exe...` → tu `pcsx2-qt.exe`.
- [ ] `JUGAR EN PCSX2` → primera vez: apunta tu BIOS cuando la pida.
- [ ] Debe salir el logo PS2 y luego el juego. Si abre sin juego:
      `System → Boot ISO Image` → tu ISO a mano.
- [ ] `Settings → Controllers` → configura tu palanca (prueba botones).

## 4. Juego local (15 min)
- [ ] Nueva partida 1P, juega la primera misión (rendimiento/jugabilidad OK).
- [ ] Mando 2: coop local 2P en la misma pantalla (Liu Kang + Kung Lao se mueven).

## 5. Online con tu amigo (20 min)
- [ ] Los dos con ISO validada en verde + ZeroTier en la misma red.
- [ ] Host: `SALA ONLINE` → `CREAR SALA` → pasa el link `mkport://...`.
- [ ] Join: `UNIRSE CON LINK` → pega el link → debe verse en la lista con ✓.
- [ ] Host fija misión → join la ve → los dos `LISTO` → `EMPEZAR` → 3-2-1 en ambos.
- [ ] En la intro: uno pulsa `SALTAR INTRO` → al otro le sale `¡SALTAR INTRO AHORA!`.
- [ ] Entran a la misión a la vez. Recuerda: cada uno juega su partida local
      coordinada (la sala sincroniza la sesión, no el gameplay frame a frame).

## 6. Si algo falla
- [ ] Abre `PARA_CASA_OPENCODE.md` con tu agente y sigue "orden de diagnóstico".
- [ ] No subas al repo ISOs, BIOS ni `config.toml` (ya están ignorados).
