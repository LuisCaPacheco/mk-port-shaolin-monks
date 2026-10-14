"""xdvdfs.py — lector XDVDFS en Python, port fiel de OpenCE xiso.c.

Origen y crédito (obligatorio):
- Lógica y formato según OpenCE `port/linux/src/xiso.c`, que a su vez sigue a
  extract-xiso (https://github.com/XboxDev/extract-xiso, extract-xiso.c).
- Partes con copyright de in@fishtank.com, licencia BSD (ver NOTICE abajo).
  Se permite redistribuir con/sin modificación conservando este aviso.

NOTICE (de xiso.c):
  Copyright (c) 2003 in <in@fishtank.com>. All rights reserved.
  Redistribución permitida si conserva este aviso y el disclaimer.
  ESTE SOFTWARE SE DA "AS IS", SIN GARANTÍAS.

Qué hace: abre tu .xiso/.iso de Xbox, localiza la partición del juego,
lee el descriptor de volumen en 0x10000 (magia MICROSOFT*XBOX*MEDIA al inicio
y en 0x7EC), recorre las tablas de directorios (árbol binario) y extrae archivos
a data.partial -> data (igual que maps.partial -> maps en OpenCE).

Solo stdlib. No ejecuta nada del disco, solo copia archivos.
"""
from __future__ import annotations
import os
import struct

SECTOR_SIZE = 2048
VOLUME_DESCRIPTOR_OFFSET = 0x10000
ENTRY_HEADER_SIZE = 14
ATTRIBUTE_DIRECTORY = 0x10
MAXIMUM_DIRECTORY_SIZE = 4 << 20
MAXIMUM_FILES = 4096
COPY_BUFFER_SIZE = 1 << 20
VOLUME_MAGIC = b"MICROSOFT*XBOX*MEDIA"
PARTITION_OFFSETS = (0, 0x0FD90000, 0x02080000, 0x18300000)

_FORBIDDEN = set('/\\:*?"<>|')


def name_is_plain(name: str) -> bool:
    """Igual que name_is_plain() en xiso.c: sin rutas, solo ASCII imprimible seguro."""
    if not name or name in (".", ".."):
        return False
    for ch in name:
        o = ord(ch)
        if o < 0x20 or o > 0x7E or ch in _FORBIDDEN:
            return False
    return True


def names_match(a: str, b: str) -> bool:
    return a.lower() == b.lower()


class XisoError(Exception):
    pass


class XisoImage:
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "rb")
        self.size = os.fstat(self.f.fileno()).st_size
        self.partition = 0
        self.root_sector, self.root_size = self._find_volume()

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _read_at(self, offset: int, size: int) -> bytes:
        self.f.seek(offset)
        buf = self.f.read(size)
        if len(buf) != size:
            raise XisoError("No se pudo leer la imagen (¿está completa?).")
        return buf

    def _find_volume(self):
        for part in PARTITION_OFFSETS:
            off = part + VOLUME_DESCRIPTOR_OFFSET
            if off + SECTOR_SIZE > self.size:
                continue
            desc = self._read_at(off, SECTOR_SIZE)
            if desc[:20] == VOLUME_MAGIC and desc[0x7EC:0x7EC + 20] == VOLUME_MAGIC:
                self.partition = part
                root_sector = struct.unpack_from("<I", desc, 20)[0]
                root_size = struct.unpack_from("<I", desc, 24)[0]
                if root_size and root_size <= MAXIMUM_DIRECTORY_SIZE:
                    return root_sector, root_size
        raise XisoError("This is not an Xbox disc image.")

    def _read_directory(self, sector: int, size: int) -> bytes:
        if not size or size > MAXIMUM_DIRECTORY_SIZE:
            raise XisoError("The disc image's file system is damaged.")
        return self._read_at(self.partition + sector * SECTOR_SIZE, size)

    def walk(self, table: bytes, directories: bool):
        """Recorre el árbol binario como walk_directory() en xiso.c. Devuelve [(name, sector, size)]."""
        entries: list[tuple[str, int, int]] = []
        visited = 0

        def rec(offset_units: int, depth: int):
            nonlocal visited
            offset = offset_units * 4
            visited += 1
            if depth > 64 or visited > 8192 or offset + ENTRY_HEADER_SIZE > len(table):
                return
            left = table[offset] | (table[offset + 1] << 8)
            right = table[offset + 2] | (table[offset + 3] << 8)
            if left == 0xFFFF:  # padding, directorio vacío
                return
            name_len = table[offset + 13]
            is_dir = bool(table[offset + 12] & ATTRIBUTE_DIRECTORY)
            if left:
                rec(left, depth + 1)
            end = offset + ENTRY_HEADER_SIZE + name_len
            if end <= len(table) and name_len > 0 and is_dir == directories \
                    and len(entries) < MAXIMUM_FILES:
                try:
                    name = table[offset + ENTRY_HEADER_SIZE:end].decode("ascii")
                except UnicodeDecodeError:
                    name = ""
                sector = struct.unpack_from("<I", table, offset + 4)[0]
                size = struct.unpack_from("<I", table, offset + 8)[0]
                if name_is_plain(name):
                    entries.append((name, sector, size))
            if right:
                rec(right, depth + 1)

        rec(0, 0)
        return entries

    def list_root(self):
        table = self._read_directory(self.root_sector, self.root_size)
        files = self.walk(table, directories=False)
        dirs = self.walk(table, directories=True)
        return {"files": files, "dirs": [d[0] for d in dirs],
                "dirs_full": dirs, "partition": hex(self.partition)}

    def list_folder(self, folder: str):
        root = self.list_root()
        match = next((d for d in root["dirs_full"] if names_match(d[0], folder)), None)
        if match is None:
            raise XisoError(f"The disc image has no {folder} folder.")
        table = self._read_directory(match[1], match[2])
        return self.walk(table, directories=False)

    def extract_file(self, sector: int, size: int, dest: str, progress=None, fname="", done=0, total=0):
        offset = self.partition + sector * SECTOR_SIZE
        remaining = size
        with open(dest, "wb") as out:
            while remaining > 0:
                chunk = COPY_BUFFER_SIZE if remaining > COPY_BUFFER_SIZE else remaining
                self.f.seek(offset)
                buf = self.f.read(chunk)
                if len(buf) != chunk:
                    raise XisoError(f"Could not read {fname} from the disc image (is it complete?).")
                out.write(buf)
                offset += chunk
                remaining -= chunk
                done += chunk
                if progress:
                    progress(fname, done, total)
        return done

    def extract_all(self, destination: str, progress=None):
        """Extrae TODO el disco (root + subcarpetas) a destination.partial -> destination.
        Para juegos como MK cuyo layout no es maps/ como Halo."""
        root = self.list_root()
        subtables = []
        total = sum(s for _, _, s in root["files"])
        for dname, sec, sz in root["dirs_full"]:
            try:
                subtables.append((dname, self.walk(self._read_directory(sec, sz), False)))
            except XisoError:
                continue
        total += sum(z for _, t in subtables for _, _, z in t)
        partial = destination + ".partial"
        os.makedirs(partial, exist_ok=True)
        done = 0
        for name, sec, sz in root["files"]:
            done = self.extract_file(sec, sz, os.path.join(partial, name),
                                     progress, name, done, total or 1)
        for dname, entries in subtables:
            for n2, s2, z2 in entries:
                done = self.extract_file(s2, z2, os.path.join(partial, n2),
                                         progress, f"{dname}/{n2}", done, total or 1)
        try:
            if os.path.isdir(destination):
                raise XisoError(f"Could not create {destination} (ya existe).")
            os.rename(partial, destination)
        except OSError:
            raise XisoError(f"Could not create {destination}.")
        return {"files": len(root["files"]) + sum(len(t) for _, t in subtables), "bytes": total}

    def extract_folder(self, folder: str, destination: str, progress=None, require: tuple[str, ...] = ()):
        """Como xiso_extract_maps(): extrae <folder> a destination.partial y renombra a destination."""
        entries = self.list_folder(folder)
        if require:
            have = {n.lower() for n, _, _ in entries}
            for r in require:
                if r.lower() not in have:
                    raise XisoError(f"The disc image's {folder} folder has no {r}.")
        total = sum(s for _, _, s in entries)
        partial = destination + ".partial"
        os.makedirs(partial, exist_ok=True)
        done = 0
        for name, sector, size in entries:
            dest = os.path.join(partial, name)
            done = self.extract_file(sector, size, dest, progress, f"{folder}/{name}", done, total)
        try:
            if os.path.isdir(destination):
                raise XisoError(f"Could not create {destination} (ya existe).")
            os.rename(partial, destination)
        except OSError:
            raise XisoError(f"Could not create {destination}.")
        return {"files": len(entries), "bytes": total}
