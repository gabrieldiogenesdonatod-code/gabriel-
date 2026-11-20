"""
Resposta remota (fork PT-BR 1.8): quando um pedido chega de fora (WhatsApp),
o texto que o JARVIS responde volta para lá.

O main.py chama `publicar(texto)` a cada resposta completa e `silenciar()`
antes de tocar o áudio. Quem mandou o pedido (plugins/_whatsapp.py) chama
`pedir(texto, responder)`. Sem pedido pendente, nada aqui muda nada.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

ESPERA_S = 120                       # por quanto tempo as respostas ainda vão para quem pediu

_lock = threading.Lock()
_pendente: dict = {"ate": 0.0, "responder": None, "silencio": False, "fonte": ""}


def pedir(texto: str, responder: Callable[[str], None], fonte: str = "whatsapp",
          silencio: bool = True) -> bool:
    """Manda o texto para a sessão do JARVIS. True se havia sessão para receber."""
    with _lock:
        _pendente.update(ate=time.time() + ESPERA_S, responder=responder, silencio=silencio, fonte=fonte)
    try:
        from core import registro_ferramentas
        app = registro_ferramentas.app()
        fn = getattr(app, "comando_remoto", None)
        if callable(fn) and fn(texto, fonte):
            return True
    except Exception as e:
        print(f"[RespostaRemota] {e}")
    encerrar()
    return False


def ativo() -> bool:
    with _lock:
        return _pendente["responder"] is not None and time.time() < _pendente["ate"]


def silenciar() -> bool:
    """True = não tocar o áudio desta resposta no PC (pedido remoto em andamento)."""
    with _lock:
        return bool(_pendente["silencio"]) and _pendente["responder"] is not None and time.time() < _pendente["ate"]


def publicar(texto: str) -> None:
    """Chamado pelo main.py com cada resposta completa do JARVIS."""
    with _lock:
        fn = _pendente["responder"] if time.time() < _pendente["ate"] else None
        if fn is not None:
            _pendente["ate"] = time.time() + 20        # mais um pedaço pode vir (depois de uma ferramenta)
    if fn is not None and texto:
        try:
            threading.Thread(target=fn, args=(texto,), daemon=True).start()
        except Exception as e:
            print(f"[RespostaRemota] {e}")


def encerrar() -> None:
    with _lock:
        _pendente.update(ate=0.0, responder=None, silencio=False, fonte="")
