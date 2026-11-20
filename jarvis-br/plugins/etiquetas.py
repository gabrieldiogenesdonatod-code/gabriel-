"""Etiquetas de preço (2.19): gera uma folha de etiquetas para imprimir e recortar, com nome da loja, peça, tamanho e preço."""
from __future__ import annotations

import html
import re

from plugins._lote2 import P, numeros, pagina, reais, rodar

PLUGIN = P("etiquetas", "Printable price tags sheet (HTML): store name, product, size, price; quantity prefix like '3x Body azul P 39,90'.",
           "gerar | exemplo",
           "gerar: itens separated by ';' ('3x Body azul P 39,90; Short M 25'), loja (store name, default Cristal Malhas).",
           "itens loja")

TAMANHOS = {"RN", "PP", "P", "M", "G", "GG", "XG", "U", "1", "2", "3", "4", "6", "8", "10", "12", "14", "16"}


def ler_item(t: str) -> tuple[int, str, str, float]:
    """'3x Body azul P 39,90' → (3, 'Body azul', 'P', 39.9). Pura."""
    t = t.strip()
    m = re.match(r"(\d+)\s*x\s+", t, re.I)
    qtd = int(m.group(1)) if m else 1
    t = t[m.end():] if m else t
    n = numeros(t)
    preco = n[-1] if n else 0.0
    partes = re.sub(r"(R\$\s*)?\d+(?:[.,]\d+)?\s*$", "", t).split()
    tam = partes.pop() if partes and partes[-1].upper() in TAMANHOS else ""
    return qtd, " ".join(partes), tam.upper(), preco


def _go(p, pl):
    bruto = str(p.get("itens") or "") if p["action"] == "gerar" else "2x Body azul P 39,90; Conjunto moletom 4 89,90"
    loja = html.escape(str(p.get("loja") or "Cristal Malhas"))
    tags = []
    for it in [x for x in bruto.split(";") if x.strip()]:
        qtd, nome, tam, preco = ler_item(it)
        tags += [f"<div class='e'><small>{loja}</small><b>{html.escape(nome)}</b>" + (f"<i>Tam. {tam}</i>" if tam else "") +
                 f"<strong>{reais(preco)}</strong></div>"] * min(qtd, 60)
    if not tags:
        return "Diga os itens, ex.: '3x Body azul P 39,90; Short M 25'."
    css = ("<style>.g{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.e{border:1px dashed #555;padding:8px;text-align:center;"
           "break-inside:avoid}.e small{display:block;letter-spacing:2px;font-size:9px}.e b{display:block;font-size:13px}"
           ".e i{display:block;font-size:12px}.e strong{font-size:20px}</style>")
    arq = pagina("Etiquetas", f"Etiquetas {loja}", css + "<div class='g'>" + "".join(tags) + "</div>")
    return f"{len(tags)} etiqueta(s) prontas para imprimir: {arq}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"gerar": _go, "exemplo": _go}, player)
