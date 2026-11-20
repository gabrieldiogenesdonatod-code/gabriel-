"""Codificador (2.18): Morse, binário, hexadecimal, bases, números romanos, cifra de César e alfabeto fonético."""
from __future__ import annotations

from plugins._lote2 import P, norm, rodar

PLUGIN = P("codificador", "Encode/decode Morse, binary, Roman numerals, Caesar cipher, number bases, NATO phonetic spelling.",
           "morse | desmorse | binario | desbinario | romano | base | cesar | soletrar",
           "Codes. texto = input. romano: number<->Roman both ways. base: texto=number, de, para (2-36). "
           "cesar: texto, chave (negative decodes). soletrar: NATO alphabet.",
           "texto chave de para")

M = dict(zip("abcdefghijklmnopqrstuvwxyz0123456789", (
    ".- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - ..- ...- .-- -..- -.-- --.. "
    "----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----.").split()))
R = {v: k for k, v in M.items()}
NATO = dict(zip("abcdefghijklmnopqrstuvwxyz", "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima "
                "Mike November Oscar Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey X-ray Yankee Zulu".split()))
_ROM = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def morse(t):
    return " / ".join(" ".join(M[c] for c in w if c in M) for w in norm(t).split())


def desmorse(t):
    return " ".join("".join(R.get(c, "?") for c in w.split()) for w in str(t).split("/"))


def para_romano(n: int) -> str:
    if not 0 < n < 4000:
        raise ValueError("romanos vão de 1 a 3999")
    s = ""
    for v, r in _ROM:
        while n >= v:
            s, n = s + r, n - v
    return s


def de_romano(s: str) -> int:
    val = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    s, tot = s.upper().strip(), 0
    if not s or set(s) - set(val):
        raise ValueError("isso não é número romano")
    for i, c in enumerate(s):
        v = val[c]
        tot += -v if i + 1 < len(s) and val[s[i + 1]] > v else v
    return tot


def cesar(t: str, k: int) -> str:
    out = []
    for c in str(t):
        if c.isalpha() and c.isascii():
            b = ord("A") if c.isupper() else ord("a")
            out.append(chr((ord(c) - b + k) % 26 + b))
        else:
            out.append(c)
    return "".join(out)


def base(n: str, de: int, para: int) -> str:
    v, dig = int(str(n).strip(), de), "0123456789abcdefghijklmnopqrstuvwxyz"
    if v == 0:
        return "0"
    s, neg, v = "", v < 0, abs(v)
    while v:
        s, v = dig[v % para] + s, v // para
    return "-" * neg + s


def _go(p, pl):
    a, t = str(p.get("action")).lower(), str(p.get("texto") or "")
    if a == "morse":
        return morse(t)
    if a == "desmorse":
        return desmorse(t)
    if a == "binario":
        return " ".join(f"{b:08b}" for b in t.encode())
    if a == "desbinario":
        return bytes(int(x, 2) for x in t.split()).decode(errors="replace")
    if a == "romano":
        return para_romano(int(t)) if t.strip().isdigit() else str(de_romano(t))
    if a == "base":
        return base(t, int(p.get("de") or 10), int(p.get("para") or 2))
    if a == "cesar":
        return cesar(t, int(p.get("chave") or 3))
    return " ".join(NATO.get(c, c) for c in norm(t) if c.strip())


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("morse desmorse binario desbinario romano base cesar soletrar".split(), _go), player)
