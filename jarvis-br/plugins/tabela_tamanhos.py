"""Tamanhos infantis (2.18): sugere o tamanho pela idade ou altura, para responder cliente da loja rápido."""
from __future__ import annotations

from plugins._lote2 import P, norm, numeros, rodar

PLUGIN = P("tabela_tamanhos", "Kids clothing size guide (BR): size from age or height, table, and shoe size from foot length.",
           "por_idade | por_altura | tabela | calcado",
           "por_idade: valor (e.g. '6 meses', '4 anos'). por_altura: valor cm. calcado: valor = foot length cm. "
           "Guide only — brands vary.",
           "valor")

# (tamanho, altura máx cm, idade máx meses) — referência média de mercado
TAB = [("RN", 55, 1), ("P", 62, 3), ("M", 68, 6), ("G", 74, 9), ("GG", 80, 12), ("1", 86, 18), ("2", 92, 24),
       ("3", 98, 36), ("4", 104, 48), ("6", 116, 72), ("8", 128, 96), ("10", 140, 120), ("12", 152, 144),
       ("14", 160, 168), ("16", 168, 192)]


def por_altura(cm: float) -> str:
    return next((t for t, h, _ in TAB if cm <= h), "16 ou adulto PP")


def por_idade(texto: str) -> str:
    n = (numeros(texto) or [0])[0]
    meses = n if "mes" in norm(texto) else n * 12
    return next((t for t, _, m in TAB if meses <= m), "16 ou adulto PP")


def calcado(cm: float) -> int:
    return round((cm + 1.5) * 1.5)          # numeração brasileira aproximada


def run(parameters, player=None, session_memory=None):
    v = lambda p: (numeros(p.get("valor")) or [0])[0]  # noqa: E731
    return rodar(parameters, {
        "por_idade": lambda p, pl: f"Tamanho {por_idade(p.get('valor'))} (pode variar por marca).",
        "por_altura": lambda p, pl: f"Tamanho {por_altura(v(p))}.",
        "tabela": lambda p, pl: "\n".join(f"{t}: até {h} cm / {m} meses" for t, h, m in TAB),
        "calcado": lambda p, pl: f"Número aproximado {calcado(v(p))}."}, player, "Tamanhos")
