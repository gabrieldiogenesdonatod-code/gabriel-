"""
Vigia de travamento (fork PT-BR 3.0): nenhuma ferramenta segura a conversa por mais de 30 segundos.

Antes: o JARVIS esperava cada plugin terminar, SEM LIMITE, e usava o mesmo grupo de threads do
áudio. Um plugin pendurado na internet deixava a conversa muda; vários juntos podiam deixar até o
som sem thread para rodar.

Agora:
    * plugins e ferramentas rodam num grupo PRÓPRIO de threads (o áudio nunca fica sem);
    * passou do limite (30 s; "limite_ferramenta_s" em config/api_keys.json), o JARVIS responde
      na hora que continua trabalhando, a conversa segue, e quando a ferramenta terminar ele
      mostra o resultado e avisa;
    * com o grupo lotado de tarefas presas, ele diz que está ocupado em vez de enfileirar e travar.
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as _TempoEsgotado      # Python 3.10 tem classe própria
from typing import Callable

MAX_THREADS = 12
LIMITE_PADRAO = 30.0
LIMITES: dict[str, float] = {}        # 3.1: limite próprio por ferramenta (o sistema imune aumenta o de quem vive travando)

_pool: ThreadPoolExecutor | None = None
_lock = threading.Lock()
_ocupadas = 0
ATRASADAS: list[tuple[float, str, float]] = []        # (quando, ferramenta, segundos) — só as recentes


def limite_configurado() -> float:
    try:
        from memory.config_manager import load_api_keys
        return max(5.0, float(load_api_keys().get("limite_ferramenta_s", LIMITE_PADRAO)))
    except Exception:
        return LIMITE_PADRAO


def pool() -> ThreadPoolExecutor:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(MAX_THREADS, thread_name_prefix="ferramenta")
        return _pool


def ocupadas() -> int:
    return _ocupadas


def _reservar() -> bool:
    global _ocupadas
    with _lock:
        if _ocupadas >= MAX_THREADS - 1:                # deixa uma livre para o que for rápido
            return False
        _ocupadas += 1
        return True


def _embrulhar(fn: Callable[[], object]) -> Callable[[], object]:
    def rodar():
        global _ocupadas
        try:
            return fn()
        finally:
            with _lock:
                _ocupadas -= 1
    return rodar


def msg_ocupado(nome: str) -> str:
    return (f"[OCUPADO] Há {ocupadas()} tarefas ainda rodando. Diga ao usuário, em uma frase, que '{nome}' "
            "não começou para não travar e que dá para pedir de novo daqui a pouco.")


def msg_demorando(nome: str, limite: float) -> str:
    return (f"[AINDA TRABALHANDO] '{nome}' passou de {limite:.0f} s. Diga ao usuário, em uma frase, que você continua "
            "nisso em segundo plano e avisa quando terminar. NÃO chame essa ferramenta de novo.")


def _bio(funcao: str, *args) -> None:
    """3.1: conta ao organismo (Biological Core), se ele estiver ligado. Nunca levanta exceção."""
    import sys
    m = sys.modules.get("biological_core")
    try:
        if m is not None and m.ativo():
            getattr(m, funcao)(*args)
    except Exception:
        pass


def _limite(nome: str, limite: float | None) -> float:
    return limite or LIMITES.get(nome) or limite_configurado()


def _ao_terminar(nome: str, t0: float, ao_terminar_tarde):
    def entregar(f):
        dur = time.monotonic() - t0
        ATRASADAS.append((time.time(), nome, dur))
        del ATRASADAS[:-50]
        ok = True
        try:
            res = f.result()
        except Exception as e:
            res, ok = f"falhou: {e}", False
        _bio("terminou_tarde", nome, dur, ok)
        if ao_terminar_tarde:
            try:
                ao_terminar_tarde(nome, str(res or "Feito."), dur)
            except Exception as e:
                print(f"[Vigia] entrega atrasada de {nome}: {e}")
    return entregar


async def executar(fn: Callable[[], object], nome: str, limite: float | None = None,
                   ao_terminar_tarde: Callable[[str, str, float], None] | None = None) -> tuple[object, bool]:
    """Roda fn (síncrona) fora do loop. Devolve (resultado, atrasou). Exceção rápida sobe normalmente."""
    if not _reservar():
        return msg_ocupado(nome), True
    t0, lim = time.monotonic(), _limite(nome, limite)
    fut = asyncio.get_running_loop().run_in_executor(pool(), _embrulhar(fn))
    try:
        return await asyncio.wait_for(asyncio.shield(fut), lim), False
    except asyncio.TimeoutError:
        _bio("travou", nome, lim)
        fut.add_done_callback(_ao_terminar(nome, t0, ao_terminar_tarde))
        return msg_demorando(nome, lim), True


def executar_sync(fn: Callable[[], object], nome: str, limite: float | None = None,
                  ao_terminar_tarde: Callable[[str, str, float], None] | None = None) -> tuple[object, bool]:
    """Igual a executar(), para código sem asyncio (servidor do celular)."""
    if not _reservar():
        return msg_ocupado(nome), True
    t0, lim = time.monotonic(), _limite(nome, limite)
    fut: Future = pool().submit(_embrulhar(fn))
    try:
        return fut.result(timeout=lim), False
    except _TempoEsgotado:
        _bio("travou", nome, lim)
        fut.add_done_callback(_ao_terminar(nome, t0, ao_terminar_tarde))
        return msg_demorando(nome, lim), True
