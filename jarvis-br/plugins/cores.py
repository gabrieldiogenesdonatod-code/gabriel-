"""Cores (2.18): hex↔rgb↔hsl, contraste WCAG entre duas cores e paletas (complementar, análoga, tríade, tons)."""
from __future__ import annotations

import colorsys
import re

from plugins._lote2 import P, norm, rodar

PLUGIN = P("cores", "Colors: convert hex/rgb/hsl, WCAG contrast ratio of two colors (AA/AAA), palettes (complementary, analogous, triad, shades).",
           "converter | contraste | paleta",
           "converter: cor ('#ff8800' or '255,136,0'). contraste: cor, cor2. paleta: cor, tipo (complementar|analoga|triade|tons).",
           "cor cor2 tipo")


def rgb(c: str) -> tuple[int, int, int]:
    c = str(c).strip()
    m = re.fullmatch(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", c)
    if m:
        h = m.group(1)
        h = "".join(x * 2 for x in h) if len(h) == 3 else h
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    n = [int(x) for x in re.findall(r"\d+", c)]
    if len(n) >= 3:
        return tuple(max(0, min(255, x)) for x in n[:3])
    raise ValueError("use #rrggbb ou r,g,b")


def hexa(c) -> str:
    return "#%02x%02x%02x" % tuple(c)


def luminancia(c) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = map(ch, c)
    return .2126 * r + .7152 * g + .0722 * b


def contraste(a, b) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + .05) / (lb + .05)


def girar(c, graus: float, luz: float = 0) -> tuple:
    h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in c))
    r = colorsys.hls_to_rgb((h + graus / 360) % 1, max(0, min(1, l + luz)), s)
    return tuple(round(x * 255) for x in r)


def _go(p, pl):
    a, c = str(p.get("action")).lower(), rgb(p.get("cor"))
    if a == "contraste":
        r = contraste(c, rgb(p.get("cor2")))
        nivel = "AAA" if r >= 7 else "AA" if r >= 4.5 else "AA só texto grande" if r >= 3 else "reprovado"
        return f"Contraste {r:.2f}:1 — {nivel}."
    if a == "paleta":
        t = norm(p.get("tipo") or "complementar")
        graus = {"analoga": [-30, 0, 30], "triade": [0, 120, 240]}.get(t, [0, 180])
        cores = [girar(c, 0, d) for d in (-.3, -.15, 0, .15, .3)] if t.startswith("tons") else [girar(c, g) for g in graus]
        return " ".join(hexa(x) for x in cores)
    h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in c))
    return f"{hexa(c)} = rgb{c} = hsl({h * 360:.0f}, {s * 100:.0f}%, {l * 100:.0f}%)."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("converter contraste paleta".split(), _go), player)
