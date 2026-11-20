"""Hash e codificação (2.18): md5/sha1/sha256 de texto ou arquivo, base64, URL encode, UUID e conferir download."""
from __future__ import annotations

import base64
import hashlib
import urllib.parse
import uuid
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("codigos_hash", "Hashes (md5/sha1/sha256) of text or file, compare a download's checksum, base64 and URL encode/decode, new UUID.",
           "hash | conferir | base64 | debase64 | url | desurl | uuid",
           "texto = text or file path. hash: algoritmo (sha256 default). conferir: texto=file, esperado=checksum.",
           "texto algoritmo esperado")


def hash_de(t: str, alg: str = "sha256") -> str:
    h = hashlib.new(alg)
    pth = Path(t.strip().strip('"')) if len(t) < 260 else None
    if pth and pth.is_file():
        with open(pth, "rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
    else:
        h.update(t.encode())
    return h.hexdigest()


def _go(p, pl):
    a, t = str(p.get("action")).lower(), str(p.get("texto") or "")
    alg = str(p.get("algoritmo") or "sha256").lower().replace("-", "")
    if a == "hash":
        return f"{alg}: {hash_de(t, alg)}"
    if a == "conferir":
        esp = str(p.get("esperado") or "").strip().lower()
        alg = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}.get(len(esp), "sha256")
        return "Confere! Arquivo íntegro." if hash_de(t, alg) == esp else "NÃO confere: arquivo diferente ou corrompido."
    if a == "base64":
        return base64.b64encode(t.encode()).decode()
    if a == "debase64":
        return base64.b64decode(t + "=" * (-len(t) % 4)).decode(errors="replace")
    if a == "url":
        return urllib.parse.quote(t)
    if a == "desurl":
        return urllib.parse.unquote(t)
    return str(uuid.uuid4())


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("hash conferir base64 debase64 url desurl uuid".split(), _go), player)
