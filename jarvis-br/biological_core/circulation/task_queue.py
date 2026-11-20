"""
Fila de tarefas com prioridade da circulação.

    • prioridade: crítica sai antes de alta, que sai antes de normal e baixa;
    • sem duplicar: um evento com a mesma "chave" de um que ainda espera vira um só
      (e conta quantas repetições juntou);
    • com limite: cheia, ela descarta primeiro o menos importante — nunca o crítico.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import time


class FilaPrioridade:
    def __init__(self, limite: int = 5000):
        self._heap: list[list] = []
        self._seq = itertools.count()
        self._chaves: dict[str, list] = {}
        self._cond = threading.Condition()
        self.limite = limite
        self.entraram = 0
        self.coalescidos = 0
        self.descartados = 0

    def colocar(self, item, prioridade: int = 2, chave: str | None = None) -> bool:
        """True se entrou; False se juntou com um igual ou foi descartado."""
        with self._cond:
            if chave and chave in self._chaves:
                self._chaves[chave][3] += 1
                self.coalescidos += 1
                return False
            if len(self._heap) >= self.limite:
                pior = max(self._heap, key=lambda e: (e[0], e[1]))
                if pior[0] <= prioridade:                     # o que chega é o menos importante
                    self.descartados += 1
                    return False
                self._heap.remove(pior)
                heapq.heapify(self._heap)
                if pior[5]:
                    self._chaves.pop(pior[5], None)
                self.descartados += 1
            entrada = [prioridade, next(self._seq), time.monotonic(), 1, item, chave]
            heapq.heappush(self._heap, entrada)
            if chave:
                self._chaves[chave] = entrada
            self.entraram += 1
            self._cond.notify()
            return True

    def tirar(self, timeout: float | None = None):
        """(item, repetições, espera_s) ou None se nada chegou no tempo."""
        with self._cond:
            if not self._heap:
                self._cond.wait(timeout)
            if not self._heap:
                return None
            _p, _s, t0, rep, item, chave = heapq.heappop(self._heap)
            if chave:
                self._chaves.pop(chave, None)
            return item, rep, time.monotonic() - t0

    def acordar(self) -> None:
        with self._cond:
            self._cond.notify_all()

    def descartar_abaixo(self, prioridade_minima: int) -> int:
        """Joga fora o que é menos importante que 'prioridade_minima' (alívio de congestionamento)."""
        with self._cond:
            fica = [e for e in self._heap if e[0] < prioridade_minima]
            n = len(self._heap) - len(fica)
            if n:
                self._heap = fica
                heapq.heapify(self._heap)
                self._chaves = {e[5]: e for e in fica if e[5]}
                self.descartados += n
            return n

    def idade_mais_antiga(self) -> float:
        with self._cond:
            return max((time.monotonic() - e[2] for e in self._heap), default=0.0)

    def __len__(self) -> int:
        with self._cond:
            return len(self._heap)
