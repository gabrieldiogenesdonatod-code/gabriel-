"""JWT (2.19): abre um token JWT e mostra o cabeçalho, os dados e quando expira. Não confere a assinatura."""
from __future__ import annotations

import base64
import json
import time

from plugins._lote2 import P, rodar

PLUGIN = P("jwt_decodificar", "Decode a JWT (header, payload, expiry) for debugging auth. Does NOT verify the signature. Uses clipboard if no token.",
           "decodificar | expira", "token = the JWT (or copy it first).", "token")


def partes(token: str) -> tuple[dict, dict]:
    ps = token.strip().split(".")
    if len(ps) < 2:
        raise ValueError("isso não parece um JWT (faltam os pontos)")
    dec = lambda s: json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)))  # noqa: E731
    return dec(ps[0]), dec(ps[1])


def validade(payload: dict, agora: float) -> str:
    exp = payload.get("exp")
    if not exp:
        return "O token não tem data de expiração."
    falta = exp - agora
    quando = time.strftime("%d/%m/%Y %H:%M", time.localtime(exp))
    return f"Expira em {quando} " + (f"(faltam {falta / 3600:.1f} h)." if falta > 0 else f"(EXPIRADO há {-falta / 3600:.1f} h).")


def _go(p, pl):
    tok = str(p.get("token") or "").strip()
    if not tok:
        try:
            import pyperclip
            tok = pyperclip.paste()
        except Exception:
            return "Me passe o token."
    h, d = partes(tok.replace("Bearer ", ""))
    if p["action"] == "expira":
        return validade(d, time.time())
    return (f"Cabeçalho: {json.dumps(h, ensure_ascii=False)}\nDados: {json.dumps(d, indent=2, ensure_ascii=False)}\n"
            f"{validade(d, time.time())} Assinatura não conferida.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"decodificar": _go, "expira": _go}, player, "JWT")
