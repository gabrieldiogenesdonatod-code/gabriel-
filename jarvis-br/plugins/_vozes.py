"""
Quem está falando? (fork PT-BR 2.5) — Começa com "_": não é ferramenta.

Uma impressão de voz por pessoa em memory/vozes/<nome>.npy (são números, não
gravação: não dá para ouvir nada a partir dela).

  • Com o resemblyzer (o mesmo da verificação de voz da 1.5), a impressão tem
    256 números e separa bem até vozes parecidas.
  • Sem ele, usa um resumo do timbre (40 bandas mel, média e variação) feito
    só com numpy: separa bem vozes diferentes (homem, mulher, criança), menos
    bem duas vozes parecidas.

O `Separador` junta os blocos do microfone em falas e entrega um trecho por
fala (assim que tem ~1,2 s de voz), para identificar quem começou a falar.
"""

from __future__ import annotations

import json
import re
import threading

from plugins._comum import MEMORIA

PASTA = MEMORIA / "vozes"
TAXA = 16000
LIMIARES = {"resemblyzer": (0.72, 0.04)}      # (mínimo, folga sobre o 2º); o timbre usa distância
_lock = threading.Lock()


def motor() -> str:
    try:
        from plugins import _voz
        return "resemblyzer" if _voz.disponivel() else "timbre"
    except Exception:
        return "timbre"


# ── timbre só com numpy ───────────────────────────────────────────────────────
def _banco_mel(n_fft: int = 512, bandas: int = 40, fmin: float = 60.0, fmax: float = 7600.0):
    import numpy as np

    def hz_mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_hz(m):
        return 700.0 * (10 ** (m / 2595.0) - 1.0)
    pontos = mel_hz(np.linspace(hz_mel(fmin), hz_mel(fmax), bandas + 2))
    bins = np.floor((n_fft + 1) * pontos / TAXA).astype(int)
    banco = np.zeros((bandas, n_fft // 2 + 1))
    for i in range(bandas):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        for k in range(a, b):
            banco[i, k] = (k - a) / max(1, b - a)
        for k in range(b, c):
            banco[i, k] = (c - k) / max(1, c - b)
    return banco


_MEL = {"banco": None}


def timbre(pcm_int16):
    """Resumo do timbre (80 números) de um trecho 16 kHz. None se tem pouca voz."""
    import numpy as np
    x = np.asarray(pcm_int16, np.float32).reshape(-1) / 32768.0
    if x.size < TAXA * 0.6:
        return None
    if _MEL["banco"] is None:
        _MEL["banco"] = _banco_mel()
    janela, passo = 400, 160
    n = 1 + (x.size - janela) // passo
    idx = np.arange(janela)[None, :] + passo * np.arange(n)[:, None]
    quadros = x[idx] * np.hanning(janela)[None, :]
    espectro = np.abs(np.fft.rfft(quadros, 512)) ** 2
    energia = espectro.sum(axis=1)
    vozeados = energia > max(np.median(energia), energia.max() * 1e-3)
    if vozeados.sum() < 30:
        return None
    logmel = np.log(espectro[vozeados] @ _MEL["banco"].T + 1e-9)
    logmel -= logmel.mean(axis=1, keepdims=True)                  # tira o volume: fica só a forma (timbre)
    return np.concatenate([logmel.mean(axis=0), logmel.std(axis=0)]).astype(np.float32)


def impressao(pcm_int16, qual: str | None = None):
    """(vetor, motor) ou (None, motor)."""
    qual = qual or motor()
    if qual == "resemblyzer":
        try:
            from plugins import _voz
            return _voz.impressao(pcm_int16), qual
        except Exception as e:
            print(f"[Vozes] resemblyzer: {e}")
            qual = "timbre"
    return timbre(pcm_int16), qual


# ── perfis ────────────────────────────────────────────────────────────────────
def _arquivo(nome: str):
    slug = re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_") or "pessoa"
    return PASTA / f"{slug}.npy"


def salvar(nome: str, vetores: list, qual: str) -> None:
    import numpy as np
    pilha = np.stack(vetores)
    v = pilha.mean(axis=0)
    raio = float(np.mean(np.linalg.norm(pilha - v, axis=1))) if len(vetores) >= 2 else None
    PASTA.mkdir(parents=True, exist_ok=True)
    with _lock:
        np.save(_arquivo(nome), v)
        meta = _meta()
        meta[_arquivo(nome).stem] = {"nome": nome, "motor": qual, "raio": raio}
        (PASTA / "pessoas.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _meta() -> dict:
    try:
        return json.loads((PASTA / "pessoas.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def esquecer(nome: str) -> bool:
    with _lock:
        arq = _arquivo(nome)
        meta = _meta()
        if not arq.exists():
            return False
        arq.unlink()
        meta.pop(arq.stem, None)
        (PASTA / "pessoas.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return True


def perfis(qual: str | None = None) -> dict:
    """{nome: vetor} das pessoas aprendidas com o motor `qual`."""
    import numpy as np
    qual = qual or motor()
    saida = {}
    for slug, m in _meta().items():
        if m.get("motor") != qual:
            continue
        try:
            saida[m["nome"]] = np.load(PASTA / f"{slug}.npy")
        except Exception:
            pass
    return saida


def nomes() -> list[str]:
    return [m["nome"] for m in _meta().values()]


def raios(qual: str | None = None) -> dict:
    """{nome: espalhamento das amostras de voz no cadastro} (só o motor 'timbre' usa)."""
    qual = qual or motor()
    return {m["nome"]: m.get("raio") for m in _meta().values() if m.get("motor") == qual}


# ── identificar (puro) ────────────────────────────────────────────────────────
def identificar(vetor, pessoas: dict, qual: str, raios_: dict | None = None) -> tuple[str | None, float]:
    """(nome, nota) ou (None, nota) se ninguém bate com folga (puro).

    resemblyzer: semelhança (cosseno) com mínimo e folga sobre o 2º.
    timbre: o mais perto, se estiver bem mais perto que o 2º (≤ 80% da distância)
    e dentro de 3,5× o espalhamento das amostras do cadastro dessa pessoa."""
    import numpy as np
    if vetor is None or not pessoas:
        return None, 0.0
    nomes_ = list(pessoas)
    m = np.stack([np.asarray(pessoas[n], np.float32) for n in nomes_])
    v = np.asarray(vetor, np.float32)
    if qual == "timbre":
        d = np.linalg.norm(m - v, axis=1)
        ordem = np.argsort(d)
        d1 = float(d[ordem[0]])
        d2 = float(d[ordem[1]]) if len(ordem) > 1 else None
        raio = (raios_ or {}).get(nomes_[ordem[0]])
        perto = d1 <= 3.5 * raio if raio else (d2 is not None)
        nota = round(1 - d1 / d2, 3) if d2 else 0.0
        if perto and (d2 is None or d1 <= 0.8 * d2):
            return nomes_[ordem[0]], nota
        return None, nota
    notas = (m @ v) / (np.linalg.norm(m, axis=1) * (np.linalg.norm(v) or 1.0) + 1e-9)
    ordem = np.argsort(-notas)
    minimo, folga = LIMIARES.get(qual, (0.7, 0.05))
    melhor = float(notas[ordem[0]])
    segundo = float(notas[ordem[1]]) if len(ordem) > 1 else -1.0
    if melhor >= minimo and melhor - segundo >= folga:
        return nomes_[ordem[0]], round(melhor, 3)
    return None, round(melhor, 3)


class Separador:
    """Junta blocos do microfone em falas; entrega UM trecho por fala para identificar."""

    def __init__(self, min_voz_s: float = 1.2, minimo_fim_s: float = 0.8, silencio_fim_s: float = 0.7,
                 limiar_rms: float = 300.0):
        self.min_voz_s, self.minimo_fim_s, self.silencio_fim_s = min_voz_s, minimo_fim_s, silencio_fim_s
        self.limiar_rms = limiar_rms
        self.zerar()

    def zerar(self) -> None:
        self.voz: list = []
        self.amostras = 0
        self.ultimo_som = 0.0
        self.entregue = False

    def bloco(self, ts: float, bloco, jarvis_falando: bool = False):
        import numpy as np
        if jarvis_falando:
            return None
        b = np.asarray(bloco).reshape(-1)
        rms = float(np.sqrt(np.mean(b.astype(np.float32) ** 2))) if b.size else 0.0
        if rms >= self.limiar_rms:
            self.voz.append(b.astype(np.int16))
            self.amostras += b.size
            self.ultimo_som = ts
            if not self.entregue and self.amostras >= self.min_voz_s * TAXA:
                self.entregue = True
                return np.concatenate(self.voz)
            return None
        if self.voz and ts - self.ultimo_som > self.silencio_fim_s:
            trecho = np.concatenate(self.voz) if not self.entregue and self.amostras >= self.minimo_fim_s * TAXA \
                else None
            self.zerar()
            return trecho
        return None
