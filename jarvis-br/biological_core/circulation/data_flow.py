"""
Sistema circulatório: leva os eventos do sistema nervoso até os órgãos, em segundo plano.

Quem publica não espera ninguém processar (o portão das ferramentas continua instantâneo):
o evento entra na fila de prioridade e UMA thread ("circulacao") entrega. Ela mede o fluxo
(eventos por tópico e por minuto, tempo de espera) e percebe congestionamento — fila grande
ou evento velho esperando. Congestionada, ela alivia sozinha descartando o que é de baixa
prioridade e avisa (no máximo uma vez por minuto).
"""

from __future__ import annotations

import threading
import time
from collections import Counter, deque

from biological_core.circulation.task_queue import FilaPrioridade
from biological_core.nervous_system.event_bus import ALTA, BAIXA, Barramento, Evento


class Circulacao:
    nome = "circulacao"

    def __init__(self, barramento: Barramento, limite_fila: int = 5000, congestao: int = 500, idade_max_s: float = 10.0):
        self.bus = barramento
        self.fila = FilaPrioridade(limite_fila)
        self.congestao = congestao
        self.idade_max_s = idade_max_s
        self.ativa = False
        self._thread: threading.Thread | None = None
        self.entregues = 0
        self.erros = 0
        self._esperas: deque[float] = deque(maxlen=300)
        self.fluxo: Counter = Counter()
        self._minutos: deque[list] = deque(maxlen=60)          # [minuto, entregues]
        self.congestionamentos = 0
        self._ultimo_aviso = 0.0
        self.ultimo_pulso = time.time()
        barramento.circulacao = self

    def iniciar(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.ativa = True
        self._thread = threading.Thread(target=self._laco, daemon=True, name="circulacao")
        self._thread.start()

    def parar(self, drenar_s: float = 2.0) -> int:
        """Para a thread e entrega o que sobrou (até drenar_s). Eventos novos passam a ser entregues na hora."""
        self.ativa = False
        self.fila.acordar()
        if self._thread:
            self._thread.join(timeout=1.0)
        return self.drenar(prazo_s=drenar_s)

    def viva(self) -> bool:
        return bool(self.ativa and self._thread and self._thread.is_alive())

    def enfileirar(self, ev: Evento) -> None:
        self.fila.colocar(ev, ev.prioridade, ev.chave)
        if len(self.fila) > self.congestao:
            self._congestionou()

    def _laco(self) -> None:
        while self.ativa:
            x = self.fila.tirar(timeout=1.0)
            self.ultimo_pulso = time.time()
            if x is not None:
                self._entregar(*x)

    def _entregar(self, ev: Evento, repeticoes: int, espera: float) -> None:
        if repeticoes > 1:
            ev.dados["repeticoes"] = repeticoes
        try:
            self.bus.entregar(ev)
        except Exception:
            self.erros += 1
        self.entregues += 1
        self._esperas.append(espera)
        self.fluxo[ev.topico.split(".")[0]] += 1
        minuto = int(time.time() // 60)
        if self._minutos and self._minutos[-1][0] == minuto:
            self._minutos[-1][1] += 1
        else:
            self._minutos.append([minuto, 1])

    def drenar(self, max_itens: int = 100000, prazo_s: float | None = None) -> int:
        """Entrega agora tudo o que está na fila (testes e desligamento)."""
        n, t0 = 0, time.monotonic()
        while n < max_itens and (prazo_s is None or time.monotonic() - t0 < prazo_s):
            x = self.fila.tirar(timeout=0)
            if x is None:
                break
            self._entregar(*x)
            n += 1
        return n

    def _congestionou(self) -> None:
        self.congestionamentos += 1
        aliviados = self.fila.descartar_abaixo(BAIXA)              # reflexo: baixa prioridade sai
        if time.time() - self._ultimo_aviso > 60:
            self._ultimo_aviso = time.time()
            self.bus.publicar("circulacao.congestionada", {"fila": len(self.fila), "aliviados": aliviados},
                              "circulacao", ALTA, sincrono=True)

    def congestionada(self) -> bool:
        return len(self.fila) > self.congestao or self.fila.idade_mais_antiga() > self.idade_max_s

    def estado(self) -> dict:
        esperas = list(self._esperas)
        return {"viva": self.viva(), "fila": len(self.fila), "espera_media_ms": round(1000 * sum(esperas) / len(esperas), 1) if esperas else 0.0,
                "mais_antigo_s": round(self.fila.idade_mais_antiga(), 1), "entregues": self.entregues,
                "juntados": self.fila.coalescidos, "descartados": self.fila.descartados,
                "congestionada": self.congestionada(), "congestionamentos": self.congestionamentos,
                "por_minuto": [n for _m, n in list(self._minutos)[-30:]], "fluxo": self.fluxo.most_common(6)}
