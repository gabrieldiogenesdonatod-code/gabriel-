"""Ferramentas de texto (2.18): contar, tempo de leitura, maiúsculas, slug, sem acento, inverter, tirar duplicadas, ordenar."""
from __future__ import annotations

import re

from plugins._lote2 import P, norm, rodar

PLUGIN = P("ferramentas_texto", "Text tools: count words/chars, reading time, case, slug, strip accents, reverse, dedupe/sort lines. Uses clipboard if no text.",
           "contar | maiusculas | minusculas | titulo | slug | sem_acento | inverter | sem_duplicadas | ordenar",
           "Transforms texto (or the clipboard when texto is empty) and copies the result back to the clipboard.",
           "texto")


def contar(t: str) -> dict:
    palavras = re.findall(r"\w+", t)
    return {"palavras": len(palavras), "caracteres": len(t), "sem_espaco": len(re.sub(r"\s", "", t)),
            "linhas": t.count("\n") + 1 if t else 0, "leitura_min": round(len(palavras) / 200, 1)}


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(t)).strip("-")


def transformar(a: str, t: str) -> str:
    linhas = t.splitlines()
    return {"maiusculas": t.upper, "minusculas": t.lower, "titulo": t.title, "slug": lambda: slug(t),
            "sem_acento": lambda: _sem_acento(t), "inverter": lambda: t[::-1],
            "sem_duplicadas": lambda: "\n".join(dict.fromkeys(linhas)),
            "ordenar": lambda: "\n".join(sorted(linhas, key=norm))}[a]()


def _sem_acento(t):
    import unicodedata
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def _clip(texto=None):
    try:
        import pyperclip
        if texto is None:
            return pyperclip.paste()
        pyperclip.copy(texto)
    except Exception:
        return "" if texto is None else None


def _go(p, pl):
    a, t = str(p.get("action")).lower(), str(p.get("texto") or "") or _clip() or ""
    if not t:
        return "Me passe o texto (ou copie antes)."
    if a == "contar":
        c = contar(t)
        return (f"{c['palavras']} palavras, {c['caracteres']} caracteres ({c['sem_espaco']} sem espaço), "
                f"{c['linhas']} linha(s), ~{c['leitura_min']} min de leitura.")
    r = transformar(a, t)
    _clip(r)
    return f"Pronto, copiei: {r[:300]}"


def run(parameters, player=None, session_memory=None):
    a = "contar maiusculas minusculas titulo slug sem_acento inverter sem_duplicadas ordenar".split()
    return rodar(parameters, dict.fromkeys(a, _go), player)
