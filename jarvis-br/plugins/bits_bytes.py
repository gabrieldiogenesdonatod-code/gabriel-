"""Bits e bytes (2.19): número em binário/hex, operações de bit, tamanho em KB/MB/GB, float em IEEE 754, hexdump e tipo real de um arquivo."""
from __future__ import annotations

import re
import struct
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("bits_bytes", "Low-level helper: int in bin/hex/octal, bitwise ops (& | ^ << >> ~), byte sizes (KB/MB/GB), float as IEEE 754, file hexdump, real file type by magic bytes.",
           "numero | bitwise | tamanho | float | hexdump | tipo_arquivo",
           "numero: valor (255, 0xff, 0b1010). bitwise: valor ('0xF0 & 0x3C', '1 << 4', '~5'). tamanho: valor ('1536 MB' or bytes). "
           "float: valor. hexdump/tipo_arquivo: arquivo.",
           "valor arquivo")

MAGIA = [(b"\x89PNG", "PNG"), (b"\xff\xd8\xff", "JPEG"), (b"GIF8", "GIF"), (b"%PDF", "PDF"), (b"PK\x03\x04", "ZIP (ou docx/xlsx/apk)"),
         (b"\x1f\x8b", "GZIP"), (b"ID3", "MP3"), (b"MZ", "executável Windows (EXE/DLL)"), (b"\x7fELF", "executável Linux (ELF)"),
         (b"SQLite format 3", "banco SQLite"), (b"7z\xbc\xaf", "7-Zip"), (b"Rar!", "RAR"), (b"BM", "BMP"), (b"OggS", "OGG")]
UN = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3, "tb": 1024 ** 4}


def inteiro(t: str) -> int:
    return int(t.strip().replace("_", ""), 0)


def humano(n: float) -> str:
    for u in ("bytes", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or u == "TB":
            return f"{n:.2f} {u}".replace(".00", "")
        n /= 1024


def bitwise(expr: str) -> int:
    m = re.fullmatch(r"\s*~\s*(\S+)\s*", expr)
    if m:
        return ~inteiro(m.group(1))
    m = re.fullmatch(r"\s*(\S+)\s*(<<|>>|&|\||\^)\s*(\S+)\s*", expr)
    if not m:
        raise ValueError("use 'a & b', 'a | b', 'a ^ b', 'a << n', 'a >> n' ou '~a'")
    x, op, y = inteiro(m.group(1)), m.group(2), inteiro(m.group(3))
    return {"&": x & y, "|": x | y, "^": x ^ y, "<<": x << min(y, 256), ">>": x >> y}[op]


def tipo_por_assinatura(b: bytes) -> str:
    if b[:4] == b"RIFF" and b[8:12] in (b"WEBP", b"WAVE", b"AVI "):
        return {"WEBP": "WEBP", "WAVE": "WAV", "AVI ": "AVI"}[b[8:12].decode()]
    if b[4:8] == b"ftyp":
        return "MP4/MOV"
    return next((nome for sig, nome in MAGIA if b.startswith(sig)), "desconhecido (talvez texto)")


def mostrar_int(v: int) -> str:
    b = bin(v)[2:] if v >= 0 else bin(v)
    grupos = " ".join(b.zfill((len(b) + 3) // 4 * 4)[i:i + 4] for i in range(0, (len(b) + 3) // 4 * 4, 4)) if v >= 0 else b
    return f"decimal {v}, hex {hex(v)}, binário {grupos}, octal {oct(v)}"


def _go(p, pl):
    a, v = p["action"], str(p.get("valor") or "")
    if a == "numero":
        return mostrar_int(inteiro(v)) + "."
    if a == "bitwise":
        return f"{v.strip()} = " + mostrar_int(bitwise(v)) + "."
    if a == "tamanho":
        m = re.match(r"\s*([\d.,]+)\s*([kmgt]?b)?", v.lower())
        n = float(m.group(1).replace(",", ".")) * UN[m.group(2) or "b"]
        return f"{n:,.0f} bytes = {humano(n)}.".replace(",", ".")
    if a == "float":
        f = float(v.replace(",", "."))
        bits = struct.unpack(">I", struct.pack(">f", f))[0]
        return f"{f} em float32: 0x{bits:08x}, sinal {bits >> 31}, expoente {(bits >> 23) & 0xff}, mantissa 0x{bits & 0x7fffff:06x}."
    arq = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser()
    if not arq.is_file():
        return "Não achei esse arquivo."
    dados = arq.read_bytes()[:256]
    if a == "tipo_arquivo":
        return f"{arq.name}: {tipo_por_assinatura(dados)} ({humano(arq.stat().st_size)})."
    return "\n".join(f"{i:04x}  {' '.join(f'{b:02x}' for b in dados[i:i + 16]):<47}  " +
                     "".join(chr(b) if 32 <= b < 127 else "." for b in dados[i:i + 16]) for i in range(0, len(dados), 16))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("numero bitwise tamanho float hexdump tipo_arquivo".split(), _go), player, "Bits")
