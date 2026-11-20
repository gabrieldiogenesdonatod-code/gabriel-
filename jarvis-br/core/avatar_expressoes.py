"""
Expressões e o rosto da SEXTA para a cabeça holográfica (fork PT-BR 2.14).

Só numpy, sem Qt: o core/avatar.py chama estas funções ao posar a malha, e os
testes chamam as mesmas funções sem precisar de interface.

    geometria(malha)                 → medidas usadas pelas expressões (boca, sobrancelhas)
    rosto_friday(v0, malha, geo)     → a cabeça da SEXTA: rosto mais fino, queixo
                                       delicado, lábios mais cheios, sobrancelha arqueada
    aplicar(v, malha, geo, e)        → sorriso/tristeza na boca, sobrancelhas de
                                       preocupação, bravas ou desconfiadas (no lugar)

`e` é o dicionário suavizado que o avatar mantém (mesmas chaves de
core/emocoes.alvos()).
"""

from __future__ import annotations

import numpy as np

# Quanto cada controle mexe, em meias-alturas da cabeça. A boca tem 0,44 de
# largura e as sobrancelhas ficam a 0,198 dos olhos; estes valores fazem a
# expressão ler de longe sem deformar o rosto.
SORRISO_Y = 0.15         # quanto o canto da boca sobe/desce no sorriso inteiro
SORRISO_X = 0.10         # quanto a boca alarga no sorriso
DENTRO_Y = 0.12          # ponta de dentro da sobrancelha (triste/bravo)
TORTO_Y = 0.10           # uma sobrancelha sobe, a outra desce


def geometria(malha: dict) -> dict:
    v = malha["verts"]
    lm = malha["landmarks"]
    lips = v[lm["lips_out"]]
    brows = v[np.concatenate([lm["brow_l"], lm["brow_r"]])]
    bx = np.abs(brows[:, 0])
    return {
        "lip_hw": float(max(1e-3, (lips[:, 0].max() - lips[:, 0].min()) / 2)),
        "lip_c": np.asarray(malha["lip_centre"], dtype=np.float32),
        "brow_in": float(bx.min()), "brow_out": float(bx.max()),
        "brow_mid": float((bx.min() + bx.max()) / 2),
        "olho_y": float(v[lm["eye_l"]][:, 1].mean()),
    }


def rosto_friday(v0: np.ndarray, malha: dict, geo: dict) -> np.ndarray:
    """A cabeça da SEXTA a partir da mesma anatomia (uma cópia; v0 não muda)."""
    v = np.array(v0, dtype=np.float32, copy=True)
    lip_c = geo["lip_c"]
    # rosto um pouco mais estreito, e o queixo afinando abaixo da boca
    v[:, 0] *= 0.93
    abaixo = np.clip((lip_c[1] - v[:, 1]) / 0.55, 0.0, 1.0)
    cabeca = (v[:, 1] > -1.0).astype(np.float32)       # o pescoço não afina
    v[:, 0] *= 1.0 - 0.10 * abaixo * cabeca
    # lábios mais cheios (crescem em volta da linha da boca) e um pouco à frente
    w = malha["lips"]
    v[:, 1] = lip_c[1] + (v[:, 1] - lip_c[1]) * (1.0 + 0.20 * w)
    v[:, 2] += 0.018 * w
    # sobrancelha arqueada: o meio sobe mais que as pontas
    bw = malha["brow"]
    ax = np.abs(v[:, 0]) / 0.93
    arco = np.clip(1.0 - np.abs(ax - geo["brow_mid"]) / max(1e-3, geo["brow_out"] - geo["brow_mid"]), 0.0, 1.0)
    v[:, 1] += bw * (0.012 + 0.030 * arco)
    return v


def aplicar(v: np.ndarray, malha: dict, geo: dict, e: dict) -> None:
    """Deforma `v` (já com o pose de fala) com a expressão `e`. No lugar."""
    sorriso = float(e.get("sorriso", 0.0))
    if abs(sorriso) > 0.01:
        w = malha["lips"]
        lip_c = geo["lip_c"]
        dx = (v[:, 0] - lip_c[0]) / geo["lip_hw"]
        f = np.clip(dx * dx, 0.0, 1.6)
        # cantos sobem (ou descem) e o meio quase não sai do lugar
        v[:, 1] += w * sorriso * SORRISO_Y * (f - 0.18)
        if sorriso > 0:
            v[:, 0] += w * sorriso * SORRISO_X * (v[:, 0] - lip_c[0])
            # bochechas sobem um pouco junto: o sorriso de verdade chega aos olhos
            bochecha = np.clip(1.0 - np.abs(v[:, 1] - (geo["olho_y"] - 0.25)) / 0.2, 0.0, 1.0)
            lado = np.clip((np.abs(v[:, 0]) - 0.15) / 0.25, 0.0, 1.0) * (v[:, 2] > 0.2)
            v[:, 1] += 0.025 * sorriso * bochecha * lado

    dentro = float(e.get("sobr_dentro", 0.0))
    torto = float(e.get("sobr_torto", 0.0))
    if abs(dentro) > 0.01 or abs(torto) > 0.01:
        bw = malha["brow"]
        ax = np.abs(v[:, 0])
        t = np.clip((ax - geo["brow_in"]) / max(1e-3, geo["brow_out"] - geo["brow_in"]), 0.0, 1.0)
        # ponta de dentro sobe e a de fora desce (triste) — ou o contrário (bravo)
        v[:, 1] += bw * dentro * DENTRO_Y * ((1.0 - t) - 0.35)
        # bravo: as duas também se aproximam do nariz
        if dentro < 0:
            v[:, 0] -= bw * (-dentro) * 0.025 * np.sign(v[:, 0]) * (1.0 - t)
        # desconfiado: a do lado esquerdo da tela sobe, a outra desce
        v[:, 1] += bw * torto * TORTO_Y * np.sign(-v[:, 0])


def lados_do_rosto(xs: np.ndarray, ys: np.ndarray, v: np.ndarray) -> dict:
    """Pontos 2D que o cabelo da SEXTA usa: topo, têmporas, maçãs e queixo."""
    topo = int(np.argmax(v[:, 1]))
    faixa_t = np.flatnonzero((v[:, 1] > 0.15) & (v[:, 1] < 0.45))
    faixa_m = np.flatnonzero((v[:, 1] > -0.45) & (v[:, 1] < -0.15))
    faixa_q = np.flatnonzero((v[:, 1] > -0.95) & (v[:, 1] < -0.75))

    def extremos(idx):
        if idx.size == 0:
            return (float(xs[topo]), float(ys[topo])), (float(xs[topo]), float(ys[topo]))
        i0, i1 = idx[np.argmin(xs[idx])], idx[np.argmax(xs[idx])]
        return (float(xs[i0]), float(ys[i0])), (float(xs[i1]), float(ys[i1]))

    te, td = extremos(faixa_t)
    me, md = extremos(faixa_m)
    qe, qd = extremos(faixa_q)
    return {"topo": (float(xs[topo]), float(ys[topo])), "tempora_e": te, "tempora_d": td,
            "maca_e": me, "maca_d": md, "queixo_e": qe, "queixo_d": qd}


def _bezier(p0, p1, p2, p3, n: int = 14) -> list[tuple[float, float]]:
    t = np.linspace(0.0, 1.0, n)[:, None]
    pts = ((1 - t) ** 3) * np.array(p0) + 3 * ((1 - t) ** 2) * t * np.array(p1) \
        + 3 * (1 - t) * (t ** 2) * np.array(p2) + (t ** 3) * np.array(p3)
    return [(float(x), float(y)) for x, y in pts]


def cabelo(lados: dict, r: float, balanco: float = 0.0, fios: int = 9) -> dict:
    """Os fios do cabelo da SEXTA em 2D: um corte chanel que emoldura o rosto,
    com a franja varrida para o lado. `balanco` (−1..1) faz as pontas balançarem.
    Devolve {'tras': [[(x,y)…]…], 'franja': [[…]…]} (pura)."""
    tx, ty = lados["topo"]
    tras = []
    for s, lado in ((-1.0, "e"), (1.0, "d")):
        te, ma, qu = lados["tempora_" + lado], lados["maca_" + lado], lados["queixo_" + lado]
        for i in range(fios):
            u = i / max(1, fios - 1)
            ponta = r * 0.05 * balanco * (0.6 + u)
            p0 = (tx + s * r * 0.06 * u, ty + r * 0.03)
            p1 = (te[0] + s * r * (0.22 + 0.10 * u), te[1] - r * 0.55)
            p2 = (ma[0] + s * r * (0.24 + 0.08 * u), ma[1] - r * 0.05)
            p3 = (qu[0] + s * r * (0.16 + 0.05 * u) + ponta, qu[1] + r * (0.12 - 0.10 * u))
            fio = _bezier(p0, p1, p2, p3)
            # pontinha virando para dentro (o "chanel")
            fx, fy = fio[-1]
            fio += [(fx - s * r * 0.03, fy + r * 0.012), (fx - s * r * 0.05, fy + r * 0.006)]
            tras.append(fio)
    franja = []
    te_e, te_d = lados["tempora_e"], lados["tempora_d"]
    for j in range(6):
        u = j / 5
        p0 = (tx + r * (0.10 - 0.04 * u), ty + r * 0.02)
        p1 = (tx + r * (0.02 - 0.10 * u), ty + r * 0.30)
        p2 = (te_e[0] + r * (0.30 + 0.12 * u), te_e[1] - r * 0.20)
        p3 = (te_e[0] + r * (0.04 + 0.14 * u), te_e[1] - r * (0.10 + 0.04 * u))
        franja.append(_bezier(p0, p1, p2, p3, 12))
    # duas mechas curtinhas do outro lado, para não ficar simétrico demais
    for j in range(2):
        franja.append(_bezier((tx + r * 0.12, ty + r * 0.03), (tx + r * 0.22, ty + r * 0.22),
                              (te_d[0] - r * 0.05, te_d[1] - r * 0.30),
                              (te_d[0] - r * (0.02 + 0.05 * j), te_d[1] - r * 0.02), 10))
    return {"tras": tras, "franja": franja}


def cilios(ex: np.ndarray, ey: np.ndarray, r: float) -> list[tuple[tuple, tuple]]:
    """Cílios: tracinhos na pálpebra de cima, mais longos no canto de fora (pura)."""
    my, mx = float(ey.mean()), float(ex.mean())
    larg = max(1e-3, float(ex.max() - ex.min()) / 2)
    out = []
    for x, y in zip(ex, ey):
        if y >= my:
            continue
        rel = (x - mx) / larg                  # −1 canto de dentro/fora … +1
        fora = abs(rel)
        comp = r * (0.022 + 0.030 * fora)
        out.append(((float(x), float(y)), (float(x + rel * comp * 0.9), float(y - comp))))
    return out
