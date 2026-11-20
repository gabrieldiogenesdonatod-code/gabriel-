"""
Comunicação entre órgãos: a classe base de todo órgão e célula do organismo.

Todo órgão consegue enviar informação, receber notificações, pedir ajuda, comunicar erros,
compartilhar descobertas e receber ordens do cérebro — sempre pelo sistema nervoso.
Cada mensagem enviada conta como "pulso": o coração sabe quem está vivo pelo último pulso.
"""

from __future__ import annotations

import time
from typing import Callable

from biological_core.nervous_system.event_bus import ALTA, BAIXA, NORMAL, Barramento, Evento


class Orgao:
    nome = "orgao"
    pulso_maximo_s = 0.0            # 0 = não precisa pulsar sozinho (só reage a eventos)

    def __init__(self, barramento: Barramento, nome: str | None = None):
        self.bus = barramento
        self.nome = nome or self.nome
        self.nascimento = time.time()
        self.ultimo_pulso = time.time()
        self.vivo = True
        self.erros = 0
        self.ultimo_erro = ""
        self.ultimo_erro_ts = 0.0
        self.ordens = 0
        barramento.assinar(f"ordem.{self.nome}", self._ordem, f"{self.nome}:ordens")

    def pulsar(self) -> None:
        self.ultimo_pulso = time.time()

    def enviar(self, topico: str, dados: dict | None = None, prioridade: int = NORMAL,
               chave: str | None = None, sincrono: bool = False) -> Evento:
        self.pulsar()
        return self.bus.publicar(topico, dados, self.nome, prioridade, chave, sincrono)

    def notificar(self, destino: str, assunto: str, dados: dict | None = None, prioridade: int = NORMAL) -> Evento:
        return self.enviar(f"orgao.{destino}.{assunto}", dados, prioridade)

    def pedir_ajuda(self, tipo: str, dados: dict | None = None) -> list:
        self.pulsar()
        return self.bus.solicitar(f"ajuda.{tipo}", dados, self.nome)

    def oferecer_ajuda(self, tipo: str, fn: Callable[[dict], object]) -> None:
        def ajudar(d):
            self.pulsar()
            return fn(d)
        self.bus.responder(f"ajuda.{tipo}", ajudar, self.nome)

    def relatar_erro(self, erro, contexto: str = "") -> Evento:
        self.erros += 1
        self.ultimo_erro_ts = time.time()
        self.ultimo_erro = f"{type(erro).__name__}: {erro}"[:200] if isinstance(erro, BaseException) else str(erro)[:200]
        return self.enviar("orgao.erro", {"orgao": self.nome, "erro": self.ultimo_erro, "contexto": contexto[:200]}, ALTA)

    def compartilhar(self, tipo: str, descoberta: dict) -> Evento:
        return self.enviar(f"descoberta.{tipo}", descoberta, BAIXA)

    def ouvir(self, padrao: str, fn: Callable[[Evento], None]) -> None:
        def receber(ev: Evento):
            self.pulsar()
            try:
                fn(ev)
            except Exception as e:
                self.erros += 1
                self.ultimo_erro_ts = time.time()
                self.ultimo_erro = f"{type(e).__name__}: {e}"[:200]
                raise
        self.bus.assinar(padrao, receber, f"{self.nome}:{padrao}")

    def _ordem(self, ev: Evento) -> None:
        self.pulsar()
        self.ordens += 1
        self.receber_ordem(str(ev.dados.get("ordem", "")), ev.dados)

    def receber_ordem(self, ordem: str, dados: dict) -> None:
        """Ordens que todo órgão entende. Órgãos especializados acrescentam as suas."""
        if ordem == "pulso":
            self.pulsar()

    def estado(self) -> dict:
        return {"nome": self.nome, "vivo": self.vivo, "pulso_s": round(time.time() - self.ultimo_pulso, 1),
                "erros": self.erros, "ultimo_erro": self.ultimo_erro, "erro_ha_s": round(time.time() - self.ultimo_erro_ts) if self.ultimo_erro_ts else None,
                "ordens": self.ordens}
