"""
Relógio central (fork PT-BR 3.0): UMA thread para as rotinas periódicas dos plugins novos.

Antes, cada plugin com rotina de fundo abria a sua própria thread em loop (são 58 rodando numa
sessão). Os recursos da 2.20 em diante (sonhos, sentido de aranha, eu do passado, oráculo,
antecipação, promessas, cansaço, cofre, jornal…) agendam aqui e dividem uma thread só.

    relogio.agendar("sonhos", passo, a_cada_s=300)

Cada rotina deve ser curta (o relógio mede; uma rotina que passa de 5 s aparece no autodiagnóstico)
e nunca derruba as outras: erro numa rotina é anotado e ela roda de novo na vez seguinte.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

_tarefas: dict[str, dict] = {}
_lock = threading.Lock()
_acordar = threading.Event()
_thread: threading.Thread | None = None
_executando: tuple[str, float] | None = None      # 3.1: o coração vê se uma rotina travou o relógio
_pausa_nao_essenciais = False                     # 3.1: febre do organismo pausa o que não é essencial


def agendar(nome: str, fn: Callable[[], None], a_cada_s: float, primeira_em_s: float = 60.0, essencial: bool = False) -> None:
    """Registra (ou troca) a rotina 'nome'. Liga o relógio na primeira vez."""
    global _thread
    with _lock:
        _tarefas[nome] = {"fn": fn, "a_cada": max(5.0, float(a_cada_s)), "prox": time.time() + max(0.0, primeira_em_s),
                          "ultima_ms": 0.0, "erros": 0, "ultimo_erro": "", "essencial": bool(essencial)}
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_laco, daemon=True, name="relogio_central")
            _thread.start()
    _acordar.set()


def cancelar(nome: str) -> None:
    with _lock:
        _tarefas.pop(nome, None)


def tarefas() -> list[dict]:
    with _lock:
        return [{"nome": n, "a_cada_s": t["a_cada"], "em_s": max(0, t["prox"] - time.time()), "ultima_ms": t["ultima_ms"],
                 "erros": t["erros"], "ultimo_erro": t["ultimo_erro"], "essencial": t.get("essencial", False),
                 "pausada": _pausa_nao_essenciais and not t.get("essencial", False)} for n, t in _tarefas.items()]


def executando() -> tuple[str, float] | None:
    """(rotina, segundos rodando) ou None."""
    ex = _executando
    return (ex[0], time.monotonic() - ex[1]) if ex else None


def pausar_nao_essenciais(pausar: bool) -> None:
    global _pausa_nao_essenciais
    _pausa_nao_essenciais = bool(pausar)


def _bio(funcao: str, *args):
    import sys
    m = sys.modules.get("biological_core")
    try:
        if m is not None and m.ativo():
            return getattr(m, funcao)(*args)
    except Exception:
        pass
    return None


def rodar_vencidas(agora: float | None = None) -> list[str]:
    """Roda as rotinas cuja hora chegou. Devolve os nomes que rodaram (usado pelos testes)."""
    agora = time.time() if agora is None else agora
    with _lock:
        vencidas = [(n, t) for n, t in _tarefas.items() if t["prox"] <= agora]
        for _, t in vencidas:
            t["prox"] = agora + t["a_cada"]
    global _executando
    rodaram = []
    for nome, t in vencidas:
        if not t.get("essencial") and (_pausa_nao_essenciais or _bio("permite_rotina", nome) is False):
            continue                                      # febre ou rotina isolada: fica para a próxima vez
        t0 = time.perf_counter()
        _executando = (nome, time.monotonic())
        try:
            t["fn"]()
        except Exception as e:
            t["erros"] += 1
            t["ultimo_erro"] = str(e)[:200]
            print(f"[Relógio] {nome}: {e}")
            _bio("erro_rotina", nome, e)
        finally:
            _executando = None
        t["ultima_ms"] = (time.perf_counter() - t0) * 1000
        rodaram.append(nome)
    return rodaram


def _laco() -> None:
    while True:
        rodar_vencidas()
        with _lock:
            prox = min((t["prox"] for t in _tarefas.values()), default=time.time() + 60)
        _acordar.wait(timeout=min(60.0, max(1.0, prox - time.time())))
        _acordar.clear()
