"""Impressão 3D (2.19): custo da peça (filamento + energia), escala para caber, tamanho de capacete pela cabeça e metros de filamento."""
from __future__ import annotations

import math

from plugins._lote2 import P, norm, num1, reais, rodar

PLUGIN = P("impressao_3d", "3D printing math: part cost (filament + power), scale factor between sizes, helmet scale from head circumference, filament grams to metres.",
           "custo | escala | capacete | filamento",
           "custo: gramas, horas, preco_kg (120), watts (120), tarifa (0.95). escala: atual, desejado (mm). "
           "capacete: cabeca (circumference cm), largura (model inner width mm). filamento: gramas, material (pla|petg|abs).",
           "gramas horas preco_kg watts tarifa atual desejado cabeca largura material")

DENSIDADE = {"pla": 1.24, "petg": 1.27, "abs": 1.04, "tpu": 1.21}


def custo(gramas, horas, preco_kg=120.0, watts=120.0, tarifa=0.95) -> tuple[float, float]:
    return gramas / 1000 * preco_kg, horas * watts / 1000 * tarifa


def largura_capacete(circ_cm: float, folga_mm: float = 20) -> float:
    """Largura interna em mm para a cabeça caber: a largura da cabeça é ~27% da circunferência. Pura."""
    return circ_cm * 10 * 0.272 + folga_mm


def metros(gramas: float, material: str = "pla", diametro_mm: float = 1.75) -> float:
    area_cm2 = math.pi * (diametro_mm / 20) ** 2
    return gramas / (area_cm2 * 100 * DENSIDADE.get(material, 1.24))


def _go(p, pl):
    a = p["action"]
    x = lambda k, d=0.0: num1(p, k, d)  # noqa: E731
    if a == "custo":
        mat, en = custo(x("gramas"), x("horas"), x("preco_kg", 120), x("watts", 120), x("tarifa", 0.95))
        return f"Filamento {reais(mat)} + energia {reais(en)} = {reais(mat + en)}. Para vender, some seu tempo e uma margem para falhas."
    if a == "escala":
        if not x("atual"):
            return "Qual a medida atual e a desejada?"
        return f"Escale para {x('desejado') / x('atual') * 100:.1f}% (de {x('atual'):g} para {x('desejado'):g} mm)."
    if a == "capacete":
        alvo = largura_capacete(x("cabeca", 57))
        msg = f"Para uma cabeça de {x('cabeca', 57):g} cm a largura interna deve ter uns {alvo:.0f} mm (com 2 cm de folga para espuma)."
        return msg + (f" Escale o modelo para {alvo / x('largura') * 100:.1f}%." if x("largura") else "") + " Confirme medindo a cabeça com paquímetro ou régua."
    mat = norm(p.get("material")) or "pla"
    return f"{x('gramas'):g} g de {mat.upper()} 1,75 mm são cerca de {metros(x('gramas'), mat):.1f} metros."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("custo escala capacete filamento".split(), _go), player)
