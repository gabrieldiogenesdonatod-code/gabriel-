"""
Rede neural da memória (fork PT-BR 2.4) — uma rede de verdade, treinada no SEU PC.

É um skip-gram com subpalavras (a ideia do word2vec/fastText): uma rede rasa
de duas camadas que aprende um vetor para cada pedaço de palavra tentando
prever as palavras vizinhas nas suas próprias memórias, diário e decisões.
Treina com numpy, sem baixar modelo nenhum, e o resultado fica em
memory/rede_memoria.npz.

O que ela aprende:
  • palavras que aparecem juntas nas SUAS coisas ficam perto ("capacete" perto
    de "ESP32", "LED", "Mark") — então "o que eu decidi sobre o capacete?" acha
    a nota que fala da placa, mesmo sem a palavra "capacete";
  • pedaços de palavra (3 a 5 letras) ligam "decidi", "decisão" e "decidimos",
    plurais e erros de digitação.

Ela é pequena e só conhece o que você escreveu; sinônimos do português em
geral vêm dos embeddings do Gemini, quando há chave (core/memoria_grafo.py
usa os dois juntos).
"""

from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter
from pathlib import Path

PARADAS = set("""a o as os um uma uns umas de da do das dos em no na nos nas por pelo pela pelos pelas para pra pro
com sem que e ou mas se ja nao sim eu tu ele ela nos vos eles elas meu minha meus minhas seu sua seus suas
esse essa isso este esta isto aquele aquela aquilo ao aos a la lo ser estar ter foi era sao sou esta estao vai
vou tem tinha muito mais menos bem tambem so como quando onde qual quais quem me te lhe the of to and is it""".split())


def normalizar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def tokenizar(texto: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", normalizar(texto)) if len(w) > 1 and w not in PARADAS]


def subpalavras(w: str, n_min: int = 3, n_max: int = 5) -> list[str]:
    m = f"<{w}>"
    saida = [m]
    for n in range(n_min, n_max + 1):
        saida += [m[i:i + n] for i in range(0, max(0, len(m) - n + 1))]
    return saida


class RedeNeural:
    def __init__(self, dim: int = 48, baldes: int = 1 << 14, semente: int = 7):
        import numpy as np
        self.np = np
        self.dim, self.baldes = dim, baldes
        self.rng = np.random.default_rng(semente)
        self.entrada = ((self.rng.random((baldes, dim)) - 0.5) / dim).astype("float32")
        self.vocab: dict[str, int] = {}
        self.freq: Counter = Counter()
        self.saida = np.zeros((0, dim), "float32")
        self.treinada = False

    def _ids(self, w: str) -> list[int]:
        return [zlib.crc32(s.encode()) % self.baldes for s in subpalavras(w)]

    def vetor_palavra(self, w: str):
        return self.entrada[self._ids(w)].mean(axis=0)

    def treinar(self, frases: list[list[str]], epocas: int = 5, janela: int = 3, negativos: int = 4,
                taxa: float = 0.05, max_tokens: int = 40_000) -> int:
        """Treina; devolve quantos pares (palavra, vizinha) viu."""
        np = self.np
        frases = [f for f in frases if len(f) > 1]
        total = 0
        cortadas = []
        for f in frases:
            if total >= max_tokens:
                break
            cortadas.append(f[:max_tokens - total])
            total += len(cortadas[-1])
        self.freq = Counter(w for f in cortadas for w in f)
        self.vocab = {w: i for i, w in enumerate(sorted(self.freq))}
        if not self.vocab:
            return 0
        self.saida = np.zeros((len(self.vocab), self.dim), "float32")
        # tabela de negativos ∝ freq^0.75
        palavras = list(self.vocab)
        pesos = np.array([self.freq[w] ** 0.75 for w in palavras], "float64")
        pesos /= pesos.sum()
        tabela = self.rng.choice(len(palavras), size=max(1000, 20 * len(palavras)), p=pesos)
        ids_cache = {w: self._ids(w) for w in palavras}
        pares = 0
        n_passos = max(1, epocas * sum(len(f) for f in cortadas))
        passo = 0
        for _ep in range(epocas):
            for f in cortadas:
                for i, w in enumerate(f):
                    passo += 1
                    lr = taxa * max(0.05, 1 - passo / n_passos)
                    sub = ids_cache[w]
                    h = self.entrada[sub].mean(axis=0)
                    j = int(self.rng.integers(1, janela + 1))
                    for k in range(max(0, i - j), min(len(f), i + j + 1)):
                        if k == i:
                            continue
                        alvos = [self.vocab[f[k]]] + [int(x) for x in tabela[self.rng.integers(0, len(tabela), negativos)]]
                        rot = np.zeros(len(alvos), "float32")
                        rot[0] = 1.0
                        sa = self.saida[alvos]
                        p = 1.0 / (1.0 + np.exp(-np.clip(sa @ h, -10, 10)))
                        g = (rot - p) * lr                      # gradiente do log-verossimilhança
                        grad_h = g @ sa
                        self.saida[alvos] += np.outer(g, h)
                        self.entrada[sub] += grad_h / len(sub)
                        h = self.entrada[sub].mean(axis=0)
                        pares += 1
        self.treinada = True
        return pares

    def vetor_texto(self, texto: str):
        """Média ponderada (palavras raras pesam mais), normalizada."""
        np = self.np
        toks = tokenizar(texto)
        if not toks:
            return np.zeros(self.dim, "float32")
        total = sum(self.freq.values()) or 1
        vs, ps = [], []
        for w in toks:
            vs.append(self.vetor_palavra(w))
            ps.append(1e-3 / (1e-3 + self.freq.get(w, 0) / total))
        v = (np.array(vs) * np.array(ps)[:, None]).sum(axis=0)
        n = float(np.linalg.norm(v))
        return (v / n).astype("float32") if n else v.astype("float32")

    def parecidas(self, w: str, n: int = 5) -> list[tuple[str, float]]:
        np = self.np
        if not self.vocab:
            return []
        alvo = self.vetor_palavra(normalizar(w))
        alvo = alvo / (np.linalg.norm(alvo) or 1)
        saida = []
        for p in self.vocab:
            if p == normalizar(w):
                continue
            v = self.vetor_palavra(p)
            saida.append((p, float(v @ alvo / (np.linalg.norm(v) or 1))))
        return sorted(saida, key=lambda x: -x[1])[:n]

    def salvar(self, arq: Path) -> None:
        np = self.np
        palavras = list(self.vocab)
        np.savez_compressed(str(arq), entrada=self.entrada, saida=self.saida,
                            palavras=np.array(palavras, dtype=object),
                            freq=np.array([self.freq[w] for w in palavras], "int64"),
                            meta=np.array([self.dim, self.baldes], "int64"))

    @classmethod
    def carregar(cls, arq: Path) -> "RedeNeural | None":
        try:
            import numpy as np
            d = np.load(str(arq), allow_pickle=True)
            dim, baldes = (int(x) for x in d["meta"])
            r = cls(dim, baldes)
            r.entrada, r.saida = d["entrada"], d["saida"]
            palavras = [str(x) for x in d["palavras"]]
            r.vocab = {w: i for i, w in enumerate(palavras)}
            r.freq = Counter(dict(zip(palavras, (int(x) for x in d["freq"]))))
            r.treinada = True
            return r
        except Exception:
            return None
