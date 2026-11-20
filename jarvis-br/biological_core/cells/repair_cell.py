"""
Células reparadoras — recuperação de componentes.

Recebem a ordem do cérebro ("ordem.reparar") e rodam o protocolo de regeneração de 10 passos
(regeneration/recovery_engine.py). Um reparo de cada vez por incidente: se a mesma ordem chega
duas vezes, a segunda é ignorada enquanto a primeira não termina.
"""

from __future__ import annotations

import threading

from biological_core.nervous_system.communication import Orgao


class Reparadora(Orgao):
    nome = "reparadora"

    def __init__(self, bus, org):
        super().__init__(bus)
        self.org = org
        self.reparos = 0
        self._em_curso: set[int] = set()
        self._lock = threading.Lock()
        self.ouvir("ordem.reparar", self._ordem_reparar)

    def _ordem_reparar(self, ev) -> None:
        d = ev.dados
        iid = int(d["incidente"]["id"])
        with self._lock:
            if iid in self._em_curso:
                return
            self._em_curso.add(iid)
        try:
            self.reparos += 1
            self.org.regeneracao.protocolo(d["incidente"], d["tratamento"], d.get("decisao"), d.get("explicacao", ""))
        finally:
            with self._lock:
                self._em_curso.discard(iid)

    def estado(self) -> dict:
        e = super().estado()
        e.update(reparos=self.reparos, em_curso=len(self._em_curso))
        return e
