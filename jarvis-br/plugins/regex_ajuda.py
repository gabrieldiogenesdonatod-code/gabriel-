"""Regex (2.18): testa um padrão num texto, explica o que cada pedaço faz e entrega padrões prontos."""
from __future__ import annotations

import re

from plugins._lote2 import P, norm, rodar

PLUGIN = P("regex_ajuda", "Regex helper: test a pattern on text (matches/groups), explain a pattern piece by piece, ready-made patterns (email, CPF, phone BR…).",
           "testar | explicar | pronto",
           "testar: padrao, texto. explicar: padrao. pronto: nome (email|cpf|cnpj|cep|telefone|data|url|ip|hex|placa).",
           "padrao texto nome")

PRONTOS = {"email": r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "cpf": r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
           "cnpj": r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", "cep": r"\d{5}-?\d{3}",
           "telefone": r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}", "data": r"\d{2}/\d{2}/\d{4}", "url": r"https?://[^\s]+",
           "ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "hex": r"#?[0-9a-fA-F]{6}\b", "placa": r"[A-Z]{3}-?\d[A-Z0-9]\d{2}"}
PECAS = [(r"\\d", "um dígito"), (r"\\w", "letra, número ou _"), (r"\\s", "espaço"), (r"\\b", "borda de palavra"),
         (r"\.", "qualquer caractere"), (r"\\\.", "um ponto literal"), (r"\^", "início"), (r"\$", "fim"),
         (r"\*", "0 ou mais do anterior"), (r"\+", "1 ou mais do anterior"), (r"\?", "opcional"),
         (r"\{(\d+)(,(\d*))?\}", "repetição"), (r"\[[^\]]+\]", "um destes caracteres"), (r"\(\?:", "grupo sem captura"),
         (r"\(", "início de grupo"), (r"\|", "ou")]


def testar(padrao: str, texto: str) -> list:
    return [(m.group(0), m.groups()) for m in re.finditer(padrao, texto)][:20]


def explicar(padrao: str) -> list[str]:
    out, i = [], 0
    while i < len(padrao):
        for pat, desc in PECAS:
            m = re.match(pat, padrao[i:])
            if m:
                out.append(f"{m.group(0)} → {desc}")
                i += len(m.group(0))
                break
        else:
            out.append(f"{padrao[i]} → o caractere '{padrao[i]}'")
            i += 1
    return out


def _go(p, pl):
    a = str(p.get("action")).lower()
    if a == "pronto":
        n = norm(p.get("nome"))
        return PRONTOS.get(n, "Tenho: " + ", ".join(PRONTOS))
    pad = str(p.get("padrao") or "")
    re.compile(pad)
    if a == "explicar":
        return "\n".join(explicar(pad))
    r = testar(pad, str(p.get("texto") or ""))
    return f"{len(r)} resultado(s): " + "; ".join(f"'{m}'" + (f" grupos {g}" if g else "") for m, g in r) if r else "Nenhum resultado."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("testar explicar pronto".split(), _go), player, "Regex")
