"""
Síntese de som simples (fork PT-BR 1.6). Começa com "_": não é ferramenta.

Bateria (bumbo, caixa, chimbal, palma, 808), ambientes (chuva, mar, lareira,
floresta, noite, vento) e efeitos (trovão, porta rangendo, passos, sino,
magia, uivo, batidas na porta) — tudo gerado com numpy, sem arquivos de som.
Toca em segundo plano pelo sounddevice, no mesmo alto-falante do JARVIS.
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path

TAXA = 44100


def _np():
    import numpy as np
    return np


def tempo(segundos: float, taxa: int = TAXA):
    np = _np()
    return np.arange(int(segundos * taxa)) / taxa


def ruido(segundos: float, rng=None, taxa: int = TAXA):
    np = _np()
    rng = rng or np.random.default_rng(0)
    return rng.standard_normal(int(segundos * taxa)).astype("float32")


def filtrar(x, baixa: float | None = None, alta: float | None = None, taxa: int = TAXA, inclinacao: float = 0.0):
    """Filtro pela FFT: passa-baixa/passa-alta e 'cor' do ruído (inclinação em dB/oitava, -3 = rosa)."""
    np = _np()
    if not len(x):
        return x
    f = np.fft.rfftfreq(len(x), 1 / taxa)
    X = np.fft.rfft(x)
    ganho = np.ones_like(f)
    if baixa:
        ganho *= 1 / np.sqrt(1 + (f / baixa) ** 4)
    if alta:
        ganho *= 1 / np.sqrt(1 + (alta / np.maximum(f, 1e-3)) ** 4)
    if inclinacao:
        ganho *= np.where(f > 20, (np.maximum(f, 20) / 1000) ** (inclinacao / 6.02), (20 / 1000) ** (inclinacao / 6.02))
    y = np.fft.irfft(X * ganho, len(x))
    return (y / (np.max(np.abs(y)) or 1)).astype("float32")


def normalizar(x, pico: float = 0.9):
    np = _np()
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return (x * (pico / m)).astype("float32") if m > 0 else x


# ── bateria ───────────────────────────────────────────────────────────────────
def bumbo(taxa: int = TAXA):
    np = _np()
    t = tempo(0.45, taxa)
    freq = 45 + 110 * np.exp(-t * 28)
    fase = 2 * np.pi * np.cumsum(freq) / taxa
    return (np.sin(fase) * np.exp(-t * 7) + 0.3 * np.exp(-t * 300) * np.sin(2 * np.pi * 1500 * t)).astype("float32")


def caixa(taxa: int = TAXA, rng=None):
    np = _np()
    t = tempo(0.25, taxa)
    corpo = 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
    chiado = filtrar(ruido(0.25, rng, taxa), alta=1800, taxa=taxa) * np.exp(-t * 18)
    return normalizar(corpo + 0.8 * chiado, 0.8)


def chimbal(taxa: int = TAXA, rng=None, aberto: bool = False):
    np = _np()
    dur = 0.3 if aberto else 0.06
    t = tempo(dur, taxa)
    return normalizar(filtrar(ruido(dur, rng, taxa), alta=7000, taxa=taxa) * np.exp(-t * (9 if aberto else 70)), 0.45)


def palma(taxa: int = TAXA, rng=None):
    np = _np()
    t = tempo(0.2, taxa)
    env = sum(np.exp(-np.maximum(t - d, 0) * 60) * (t >= d) for d in (0, 0.01, 0.022))
    return normalizar(filtrar(ruido(0.2, rng, taxa), baixa=2500, alta=900, taxa=taxa) * env, 0.6)


def baixo808(freq: float, segundos: float, taxa: int = TAXA, deslize_de: float | None = None):
    np = _np()
    t = tempo(segundos, taxa)
    f = np.full_like(t, freq) if not deslize_de else freq + (deslize_de - freq) * np.exp(-t * 18)
    onda = np.sin(2 * np.pi * np.cumsum(f) / taxa)
    onda = np.tanh(onda * 1.8)                                 # um pouco de saturação, como o 808 de verdade
    return (onda * np.minimum(1, t * 200) * np.exp(-t * 1.6)).astype("float32")


# ── ambientes (laços de alguns segundos) ───────────────────────────────────────
def ambiente(nome: str, segundos: float = 12.0, taxa: int = 22050, semente: int = 1):
    np = _np()
    rng = np.random.default_rng(semente)
    t = tempo(segundos, taxa)
    n = len(t)
    if nome == "chuva":
        base = filtrar(ruido(segundos, rng, taxa), baixa=6000, alta=300, taxa=taxa, inclinacao=-3)
        gotas = np.zeros(n, "float32")
        for i in rng.integers(0, n - 800, int(segundos * 40)):
            gotas[i:i + 800] += np.exp(-np.arange(800) / 90) * rng.uniform(0.1, 0.4) * np.sin(np.arange(800) * rng.uniform(0.3, 0.9))
        x = 0.7 * base + gotas
    elif nome == "mar":
        onda = 0.55 + 0.45 * np.sin(2 * np.pi * t / 7.5) ** 2
        x = filtrar(ruido(segundos, rng, taxa), baixa=1800, taxa=taxa, inclinacao=-4) * onda
    elif nome == "lareira":
        x = 0.5 * filtrar(ruido(segundos, rng, taxa), baixa=500, taxa=taxa, inclinacao=-6)
        for i in rng.integers(0, n - 300, int(segundos * 14)):
            x[i:i + 300] += rng.uniform(0.2, 0.8) * rng.standard_normal(300) * np.exp(-np.arange(300) / 40)
    elif nome == "floresta":
        x = 0.35 * filtrar(ruido(segundos, rng, taxa), baixa=3000, alta=200, taxa=taxa, inclinacao=-3)
        for inicio in rng.uniform(0, segundos - 0.5, int(segundos / 1.5)):
            i, d = int(inicio * taxa), int(0.18 * taxa)
            tt = np.arange(d) / taxa
            f = rng.uniform(2500, 4200) + 900 * np.sin(2 * np.pi * rng.uniform(8, 16) * tt)
            x[i:i + d] += 0.25 * np.sin(2 * np.pi * np.cumsum(f) / taxa) * np.hanning(d)
    elif nome == "noite":
        x = 0.15 * filtrar(ruido(segundos, rng, taxa), baixa=1200, taxa=taxa, inclinacao=-4)
        grilo = np.sin(2 * np.pi * 4400 * t) * ((np.sin(2 * np.pi * 28 * t) > 0.3) * (np.sin(2 * np.pi * 0.9 * t) > 0))
        x = x + 0.12 * grilo
    # Fork PT-BR 2.8: ruídos para dormir (o ruído "colorido" esconde barulho de rua e de vizinho)
    elif nome == "ruido_branco":
        x = filtrar(ruido(segundos, rng, taxa), baixa=9000, alta=40, taxa=taxa)
    elif nome == "ruido_rosa":
        x = filtrar(ruido(segundos, rng, taxa), baixa=8000, alta=30, taxa=taxa, inclinacao=-3)
    elif nome == "ruido_marrom":
        x = filtrar(ruido(segundos, rng, taxa), baixa=2500, alta=25, taxa=taxa, inclinacao=-6)
    elif nome == "ventilador":
        pas = 0.88 + 0.12 * np.sin(2 * np.pi * 7.5 * t)          # as pás passando
        x = filtrar(ruido(segundos, rng, taxa), baixa=1500, alta=60, taxa=taxa, inclinacao=-4) * pas
        x = x + 0.06 * np.sin(2 * np.pi * 120 * t) + 0.03 * np.sin(2 * np.pi * 240 * t)   # o motor
    else:                                                      # vento
        lfo = 0.4 + 0.6 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 5.3)) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 2.1))
        x = filtrar(ruido(segundos, rng, taxa), baixa=900, alta=150, taxa=taxa) * lfo
    fade = int(0.5 * taxa)                                     # costura o laço sem estalo
    x[:fade] = x[:fade] * np.linspace(0, 1, fade) + x[-fade:] * np.linspace(1, 0, fade)
    return normalizar(x[:-fade], 0.6)


# ── efeitos ───────────────────────────────────────────────────────────────────
def efeito(nome: str, taxa: int = 22050, semente: int = 2):
    np = _np()
    rng = np.random.default_rng(semente)
    if nome == "trovao":
        t = tempo(3.5, taxa)
        x = filtrar(ruido(3.5, rng, taxa), baixa=250, taxa=taxa, inclinacao=-6) * (np.exp(-t * 1.1) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t)))
        x[: int(0.08 * taxa)] += filtrar(ruido(0.08, rng, taxa), alta=1500, taxa=taxa)
    elif nome == "porta":
        t = tempo(1.6, taxa)
        f = 180 + 120 * np.sin(2 * np.pi * 0.7 * t) + 40 * rng.standard_normal(len(t)).cumsum() / len(t) * 50
        x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / taxa)) * 0.3 * (np.sin(np.pi * t / 1.6) ** 0.5)
        x = filtrar(x.astype("float32"), baixa=2500, taxa=taxa)
    elif nome == "passos":
        x = np.zeros(int(2.4 * taxa), "float32")
        for k in range(4):
            i = int((0.15 + 0.55 * k) * taxa)
            d = int(0.12 * taxa)
            x[i:i + d] += filtrar(ruido(0.12, rng, taxa), baixa=600, taxa=taxa) * np.exp(-np.arange(d) / (0.02 * taxa))
    elif nome == "batidas":
        x = np.zeros(int(1.4 * taxa), "float32")
        for k in range(3):
            i, d = int(0.1 * taxa + k * 0.32 * taxa), int(0.1 * taxa)
            tt = np.arange(d) / taxa
            x[i:i + d] += np.sin(2 * np.pi * 110 * tt) * np.exp(-tt * 45) + 0.4 * filtrar(ruido(0.1, rng, taxa), baixa=1200, taxa=taxa) * np.exp(-tt * 60)
    elif nome == "sino":
        t = tempo(4.0, taxa)
        x = sum(a * np.sin(2 * np.pi * 523 * r * t) * np.exp(-t * dmp) for r, a, dmp in
                ((1, 1, 0.9), (2.0, 0.5, 1.4), (2.76, 0.35, 1.8), (5.4, 0.2, 3), (8.9, 0.1, 4)))
    elif nome == "magia":
        x = np.zeros(int(2.2 * taxa), "float32")
        for k, nota in enumerate((523, 659, 784, 1047, 1319, 1568)):
            i, d = int(k * 0.11 * taxa), int(1.2 * taxa)
            tt = np.arange(min(d, len(x) - i)) / taxa
            x[i:i + len(tt)] += 0.35 * np.sin(2 * np.pi * nota * tt) * np.exp(-tt * 3) * (1 + 0.3 * np.sin(2 * np.pi * 7 * tt))
    else:                                                      # uivo
        t = tempo(3.0, taxa)
        f = 380 + 330 * np.sin(np.pi * np.minimum(t / 2.4, 1)) + 8 * np.sin(2 * np.pi * 5.5 * t)
        x = (np.sin(2 * np.pi * np.cumsum(f) / taxa) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / taxa)) * np.sin(np.pi * t / 3.0)
    return normalizar(np.asarray(x, dtype="float32"), 0.8)


EFEITOS = ("trovao", "porta", "passos", "batidas", "sino", "magia", "uivo")
AMBIENTES = ("chuva", "mar", "lareira", "floresta", "noite", "vento",
             "ruido_branco", "ruido_rosa", "ruido_marrom", "ventilador")      # 2.8: ruídos para dormir


# ── arquivo e reprodução ──────────────────────────────────────────────────────
def salvar_wav(caminho: Path, audio, taxa: int = TAXA) -> Path:
    np = _np()
    a = np.asarray(audio, dtype="float32")
    canais = 1 if a.ndim == 1 else a.shape[1]
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
    return Path(caminho)


class Laco:
    """Toca um áudio em laço, baixinho, até parar(). Fade de entrada e saída."""

    def __init__(self, audio, taxa: int = 22050, volume: float = 0.25):
        self.audio, self.taxa, self.volume = audio, taxa, volume
        self.pos, self.alvo, self.atual = 0, volume, 0.0
        self._stream = None
        self._lock = threading.Lock()

    def _cb(self, saida, frames, _t, _s):
        np = _np()
        with self._lock:
            idx = (self.pos + np.arange(frames)) % len(self.audio)
            self.pos = int((self.pos + frames) % len(self.audio))
            maximo = frames / (self.taxa * 1.5)                   # 1,5 s para ir de 0 ao volume
            delta = max(-maximo, min(maximo, self.alvo - self.atual))
            ganho = np.linspace(self.atual, self.atual + delta, frames, dtype="float32")
            self.atual += delta
            saida[:, 0] = self.audio[idx] * ganho

    def tocar(self) -> None:
        import sounddevice as sd
        self._stream = sd.OutputStream(samplerate=self.taxa, channels=1, dtype="float32", callback=self._cb)
        self._stream.start()

    def parar(self, fade: float = 1.5) -> None:
        import time
        self.alvo = 0.0
        time.sleep(fade)
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


def tocar_uma(audio, taxa: int = 22050, volume: float = 0.6) -> None:
    """Toca uma vez, sem esperar (efeitos)."""
    import sounddevice as sd
    sd.play((audio * volume).astype("float32"), taxa, blocking=False)
