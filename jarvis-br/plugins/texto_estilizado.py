"""Texto estilizado (2.19): letras diferentes para bio e legenda do Instagram — negrito, itálico, cursiva, bolhas, riscado, de cabeça para baixo.

Exemplos: "escreve o nome da loja com letra bonita", "fonte diferente para a bio", "letra cursiva para o post",
"texto de cabeça para baixo".
"""
from __future__ import annotations

import unicodedata

from plugins._lote2 import P, norm, rodar

PLUGIN = P("texto_estilizado", "Fancy Unicode text for Instagram bios/captions: bold, italic, script, monospace, bubbles, small caps, strikethrough, underline, spaced, upside-down; copies it.",
           "estilo | todos | estilos",
           "estilo: texto, estilo (negrito|italico|negrito_italico|cursiva|mono|bolhas|versalete|riscado|sublinhado|espacado|invertido).",
           "texto estilo")

# (maiúsculas, minúsculas, dígitos): primeiro código de cada faixa
FAIXAS = {"negrito": (0x1D5D4, 0x1D5EE, 0x1D7EC), "italico": (0x1D608, 0x1D622, None), "negrito_italico": (0x1D63C, 0x1D656, None),
          "cursiva": (0x1D4D0, 0x1D4EA, None), "mono": (0x1D670, 0x1D68A, 0x1D7F6), "bolhas": (0x24B6, 0x24D0, None)}
VERSALETE = dict(zip("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"))
INVERTIDO = dict(zip("abcdefghijklmnopqrstuvwxyz?!.,", "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz¿¡˙'"))


def estilizar(texto: str, estilo: str) -> str:
    """Troca cada letra pela versão Unicode do estilo, mantendo os acentos. Pura."""
    e = norm(estilo).replace(" ", "_") or "negrito"
    if e in ("riscado", "sublinhado"):
        return "".join(c + ("̶" if e == "riscado" else "̲") for c in texto)
    if e == "espacado":
        return " ".join(texto)
    if e == "invertido":
        return "".join(INVERTIDO.get(c, c) for c in norm(texto))[::-1]
    if e == "versalete":
        return "".join(VERSALETE.get(c, c) for c in unicodedata.normalize("NFD", texto.lower()))
    if e not in FAIXAS:
        raise ValueError("estilos: " + ", ".join(list(FAIXAS) + ["versalete", "riscado", "sublinhado", "espacado", "invertido"]))
    mai, mi, dig = FAIXAS[e]
    out = []
    for c in unicodedata.normalize("NFD", texto):
        if "A" <= c <= "Z":
            out.append(chr(mai + ord(c) - 65))
        elif "a" <= c <= "z":
            out.append(chr(mi + ord(c) - 97))
        elif c.isdigit() and c.isascii() and dig:
            out.append(chr(dig + int(c)))
        else:
            out.append(c)
    return unicodedata.normalize("NFC", "".join(out))


def _go(p, pl):
    a, t = p["action"], str(p.get("texto") or "Cristal Malhas")
    nomes = list(FAIXAS) + ["versalete", "riscado", "sublinhado", "espacado", "invertido"]
    if a == "estilos":
        return "Estilos: " + ", ".join(nomes) + "."
    if a == "todos":
        return "\n".join(f"{n}: {estilizar(t, n)}" for n in nomes)
    r = estilizar(t, p.get("estilo") or "negrito")
    try:
        import pyperclip
        pyperclip.copy(r)
    except Exception:
        pass
    return r


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estilo": _go, "todos": _go, "estilos": _go}, player, "Texto estilizado")
