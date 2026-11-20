"""Validador (2.18): CPF, CNPJ, cartão (Luhn), e-mail, placa; gera CPF/CNPJ fictícios válidos só para teste de sistema."""
from __future__ import annotations

import random
import re

from plugins._lote2 import P, rodar

PLUGIN = P("validador_documentos", "Validate CPF, CNPJ, card number (Luhn), e-mail, car plate; generate fake valid CPF/CNPJ for software tests.",
           "validar | formatar | gerar_cpf | gerar_cnpj",
           "validar: valor (auto-detects CPF, CNPJ, card, e-mail or plate). formatar: valor (adds the mask to CPF, CNPJ, phone or CEP). "
           "gerar_*: fictitious numbers for testing code only.",
           "valor")


def _dv(nums, pesos):
    r = sum(a * b for a, b in zip(nums, pesos)) % 11
    return 0 if r < 2 else 11 - r


def cpf_ok(t) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", str(t))]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    return d[9] == _dv(d[:9], range(10, 1, -1)) and d[10] == _dv(d[:10], range(11, 1, -1))


_P1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def cnpj_ok(t) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", str(t))]
    if len(d) != 14 or len(set(d)) == 1:
        return False
    return d[12] == _dv(d[:12], _P1) and d[13] == _dv(d[:13], [6] + _P1)


def luhn_ok(t) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", str(t))][::-1]
    if not 12 <= len(d) <= 19:
        return False
    return sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10 == 0


def gerar_cpf(rng=random) -> str:
    d = [rng.randint(0, 9) for _ in range(9)]
    d.append(_dv(d, range(10, 1, -1)))
    d.append(_dv(d, range(11, 1, -1)))
    s = "".join(map(str, d))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def gerar_cnpj(rng=random) -> str:
    d = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    d.append(_dv(d, _P1))
    d.append(_dv(d, [6] + _P1))
    s = "".join(map(str, d))
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


def formatar(v: str) -> str:
    """Põe a máscara em CPF, CNPJ, telefone ou CEP (só pelos dígitos). Pura."""
    n = re.sub(r"\D", "", str(v or ""))
    if len(n) == 11 and cpf_ok(n):
        return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
    if len(n) == 14:
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    if len(n) in (10, 11):
        return f"({n[:2]}) {n[2:-4]}-{n[-4:]}"
    if len(n) == 8:
        return f"{n[:5]}-{n[5:]}"
    return "Não reconheci: preciso de CPF, CNPJ, telefone com DDD ou CEP."


def validar(v: str) -> str:
    v = str(v or "").strip()
    if "@" in v:
        return "E-mail com formato válido." if re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", v) else "E-mail inválido."
    if re.fullmatch(r"[A-Za-z]{3}-?\d[A-Za-z0-9]\d{2}", v):
        return "Placa válida (" + ("Mercosul" if v[-3].isalpha() else "modelo antigo") + ")."
    n = re.sub(r"\D", "", v)
    if len(n) == 11:
        return "CPF válido." if cpf_ok(n) else "CPF inválido."
    if len(n) == 14:
        return "CNPJ válido." if cnpj_ok(n) else "CNPJ inválido."
    if 12 <= len(n) <= 19:
        return "Número de cartão passa no Luhn." if luhn_ok(n) else "Número de cartão inválido."
    return "Não reconheci o tipo de documento."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"validar": lambda p, pl: validar(p.get("valor")), "formatar": lambda p, pl: formatar(p.get("valor")),
                              "gerar_cpf": lambda p, pl: f"CPF fictício para teste: {gerar_cpf()}",
                              "gerar_cnpj": lambda p, pl: f"CNPJ fictício para teste: {gerar_cnpj()}"}, player)
