"""Calculadora de IA (2.19): para quem treina modelo de linguagem — nº de parâmetros de um GPT, memória, tempo de treino, taxa de aprendizado e perplexidade."""
from __future__ import annotations

import math
import re

from plugins._lote2 import P, rodar

PLUGIN = P("calculadora_ia", "Math for training language models: GPT parameter count, memory (weights/training), training ETA, cosine LR schedule with warmup, perplexity, steps per epoch.",
           "parametros | memoria | tempo_treino | lr | perplexidade | epocas",
           "Numbers accept k/M/B. parametros: vocab, d_model, camadas, contexto, d_ff (default 4*d_model). memoria: parametros, precisao "
           "(fp32|fp16|int8). tempo_treino: passos, velocidade (steps/s). lr: passo, warmup, total, lr_max, lr_min. perplexidade: loss. "
           "epocas: tokens (dataset), lote, contexto.",
           "vocab d_model camadas contexto d_ff parametros precisao passos velocidade passo warmup total lr_max lr_min loss tokens lote")

BYTES = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1, "int4": 0.5}


def grande(t, padrao: float = 0.0) -> float:
    """'124M' → 124e6; '50k' → 50000; '3e-4' → 0.0003. Pura."""
    m = re.search(r"(-?\d+(?:[.,]\d+)?(?:e-?\d+)?)\s*([kmb])?", str(t or "").lower())
    if not m:
        return padrao
    return float(m.group(1).replace(",", ".")) * {"k": 1e3, "m": 1e6, "b": 1e9, None: 1}[m.group(2)]


def parametros_gpt(vocab: int, d: int, camadas: int, contexto: int, d_ff: int | None = None) -> int:
    """GPT só-decodificador com posições aprendidas e saída amarrada ao embedding (GPT-2 pequeno = 124,4 M). Pura."""
    d_ff = d_ff or 4 * d
    camada = 4 * d * d + 4 * d + 2 * d * d_ff + d_ff + d + 4 * d
    return vocab * d + contexto * d + camadas * camada + 2 * d


def lr_cosseno(passo: int, warmup: int, total: int, lr_max: float, lr_min: float = 0.0) -> float:
    if passo < warmup:
        return lr_max * (passo + 1) / max(1, warmup)
    if passo >= total:
        return lr_min
    return lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos(math.pi * (passo - warmup) / max(1, total - warmup)))


def curto(n: float) -> str:
    return f"{n / 1e9:.2f} B" if n >= 1e9 else f"{n / 1e6:.2f} M" if n >= 1e6 else f"{n / 1e3:.1f} k" if n >= 1e3 else f"{n:g}"


def _go(p, pl):
    a = p["action"]
    x = lambda k, d=0.0: grande(p.get(k), d)  # noqa: E731
    if a == "parametros":
        n = parametros_gpt(int(x("vocab", 50257)), int(x("d_model", 768)), int(x("camadas", 12)), int(x("contexto", 1024)), int(x("d_ff")) or None)
        exato = f"{n:,}".replace(",", ".")
        return f"{curto(n)} de parâmetros ({exato}), com a saída amarrada ao embedding. Em fp32 são {n * 4 / 1e9:.2f} GB só de pesos."
    if a == "memoria":
        n, b = x("parametros"), BYTES.get(str(p.get("precisao") or "fp32").lower(), 4)
        return (f"{curto(n)} parâmetros em {p.get('precisao') or 'fp32'}: {n * b / 1e9:.2f} GB para rodar. Para treinar com AdamW conte pelo menos "
                f"{n * 4 * 4 / 1e9:.2f} GB (pesos, gradientes e 2 momentos em fp32), mais as ativações do lote.")
    if a == "tempo_treino":
        s = x("passos") / max(1e-9, x("velocidade", 1))
        return f"{curto(x('passos'))} passos a {x('velocidade', 1):g} passo(s)/s: {s / 3600:.1f} horas ({s / 86400:.1f} dias)."
    if a == "lr":
        v = lr_cosseno(int(x("passo")), int(x("warmup")), int(x("total", 1)), x("lr_max", 3e-4), x("lr_min"))
        return f"No passo {int(x('passo'))} a taxa de aprendizado é {v:.3g}."
    if a == "perplexidade":
        l = x("loss")
        return f"Loss {l:g}: perplexidade {math.exp(l):.2f}, {l / math.log(2):.3f} bits por token. Chute aleatório num vocabulário de 50k daria loss 10,8."
    por_epoca = x("tokens") / max(1, x("lote", 32) * x("contexto", 256))
    return f"{curto(x('tokens'))} tokens com lote {x('lote', 32):g} e contexto {x('contexto', 256):g}: {curto(por_epoca)} passos por época."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("parametros memoria tempo_treino lr perplexidade epocas".split(), _go), player)
