"""Segurança do MINER AI: só endereços PÚBLICOS, nunca segredo, nunca em aparelho de terceiros nem escondido."""
from __future__ import annotations

import hashlib
import os
import re
import sys

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BECH = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _b58decode(s: str) -> bytes | None:
    n = 0
    for c in s:
        i = _B58.find(c)
        if i < 0:
            return None
        n = n * 58 + i
    corpo = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + corpo


def _polymod(valores: list[int]) -> int:
    g = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in valores:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= g[i] if (b >> i) & 1 else 0
    return chk


def btc_valido(endereco: str) -> bool:
    """Endereço Bitcoin da rede principal com a soma de verificação certa (1…, 3…, bc1q…, bc1p…). Pura."""
    a = str(endereco or "").strip()
    if a[:1] in "13":
        raw = _b58decode(a)
        if raw is None or len(raw) != 25 or raw[0] not in (0, 5):
            return False
        return hashlib.sha256(hashlib.sha256(raw[:-4]).digest()).digest()[:4] == raw[-4:]
    b = a.lower()
    if b != a and a.upper() != a:
        return False
    if not b.startswith("bc1") or not 14 <= len(b) <= 74 or any(c not in _BECH for c in b[3:]):
        return False
    dados = [_BECH.index(c) for c in b[3:]]
    hrp = [ord(c) >> 5 for c in "bc"] + [0] + [ord(c) & 31 for c in "bc"]
    const = _polymod(hrp + dados)
    versao = dados[0]
    return (versao == 0 and const == 1) or (versao >= 1 and const == 0x2BC830A3)


def xmr_valido(endereco: str) -> bool:
    """Endereço Monero (95 letras com 4 ou 8; 106 se integrado). Pura."""
    return bool(re.fullmatch(r"[48][1-9A-HJ-NP-Za-km-z]{94}([1-9A-HJ-NP-Za-km-z]{11})?", str(endereco or "").strip()))


def parece_segredo(texto) -> str | None:
    """Diz o que parece (chave privada, frase de recuperação…) — esse texto NUNCA deve ser guardado. Pura."""
    t = str(texto or "").strip()
    if not t:
        return None
    if re.search(r"\b[xyzt]prv[1-9A-HJ-NP-Za-km-z]{100,}", t):
        return "chave privada estendida (xprv)"
    if re.search(r"(?<![1-9A-HJ-NP-Za-km-z])[5KL][1-9A-HJ-NP-Za-km-z]{50,51}(?![1-9A-HJ-NP-Za-km-z])", t):
        return "chave privada (WIF)"
    if re.search(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])", t):
        return "chave privada (64 hexadecimais)"
    palavras = re.findall(r"[a-zà-ú]+", t.lower())
    if re.search(r"\b(seed|semente|mnemonic|frase de recupera|palavras de recupera|chave privada|private key|spend key)\b", t.lower()):
        return "frase de recuperação ou chave"
    if len(palavras) in (12, 13, 15, 18, 21, 24, 25) and len(palavras) == len(t.split()) and all(3 <= len(p) <= 8 for p in palavras):
        return "frase de recuperação (12 a 25 palavras)"
    return None


def no_celular() -> bool:
    return bool(os.environ.get("JARVIS_ANDROID") or os.environ.get("ANDROID_ROOT") or os.environ.get("TERMUX_VERSION")
                or "com.termux" in sys.prefix or sys.platform == "android")


def pode_minerar() -> tuple[bool, str]:
    """Só no próprio PC. No celular: painel e calculadora sim, minerar não (esquenta e gasta a bateria)."""
    if no_celular():
        return False, "no celular o MINER AI só mostra o painel e as contas: minerar esquenta e estraga a bateria"
    return True, ""


def mascarar(endereco: str) -> str:
    a = str(endereco or "")
    return a if len(a) < 14 else f"{a[:6]}…{a[-6:]}"
