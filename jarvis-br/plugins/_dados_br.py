"""
Ajudantes compartilhados pelos plugins de dados do J.A.R.V.I.S BR.

Começa com "_" de propósito: o carregador de plugins pula esses arquivos, então
isto não vira ferramenta — é só código que os plugins importam.

Os dados ficam em CSV com ";" e codificação utf-8-sig, que é o formato que o
Excel em português abre direto com dois cliques, acentos e tudo.
"""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "memory"


def chave(texto: str) -> str:
    """'Conjunto Moletom AZUL ' → 'conjunto moletom azul' (sem acento)."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def numero(valor, padrao: float = 0.0) -> float:
    """Aceita 40, '40', '40,50', 'R$ 1.234,56', '1234.56'."""
    if isinstance(valor, (int, float)):
        return float(valor)
    t = str(valor or "").replace("R$", "").replace(" ", "").strip()
    if not t:
        return padrao
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return padrao


def reais(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def ler(nome: str) -> list[dict]:
    path = DATA_DIR / nome
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def escrever(nome: str, campos: list[str], linhas: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / nome
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for linha in linhas:
            w.writerow({c: linha.get(c, "") for c in campos})
    tmp.replace(path)


def acrescentar(nome: str, campos: list[str], linha: dict) -> None:
    linhas = ler(nome)
    linhas.append(linha)
    escrever(nome, campos, linhas)
