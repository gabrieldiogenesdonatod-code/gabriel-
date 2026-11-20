"""
core/qt_bridge.py — deixa código de fora da thread da interface pedir que algo
rode NA thread da interface.

Plugins rodam em threads do executor. Criar ou mexer em widgets Qt fora da
thread principal derruba o app (ou, pior, funciona às vezes). Este módulo
instala, na thread principal, um objeto com um sinal; emitir esse sinal de
qualquer thread faz o Qt enfileirar a chamada na thread certa.

    from core import qt_bridge
    qt_bridge.na_interface(lambda: minha_janela.show())

`instalar()` é chamado uma vez pelo ui.py, já na thread principal. Antes disso
(ou sem interface nenhuma, como nos testes), `na_interface` devolve False e não
faz nada.
"""

from __future__ import annotations

from typing import Callable

_ponte = None


def instalar() -> None:
    """Chame uma vez, na thread da interface, depois de criar o QApplication."""
    global _ponte
    if _ponte is not None:
        return
    try:
        from PyQt6.QtCore import QObject, pyqtSignal

        class _Ponte(QObject):
            chamar = pyqtSignal(object)

            def __init__(self):
                super().__init__()
                self.chamar.connect(self._executar)

            @staticmethod
            def _executar(funcao):
                try:
                    funcao()
                except Exception as e:
                    print(f"[QtBridge] {type(e).__name__}: {e}")

        _ponte = _Ponte()
    except Exception as e:
        print(f"[QtBridge] indisponível: {e}")


def disponivel() -> bool:
    return _ponte is not None


def na_interface(funcao: Callable[[], None]) -> bool:
    """Agenda `funcao` na thread da interface. False se não há interface."""
    if _ponte is None:
        return False
    try:
        _ponte.chamar.emit(funcao)
        return True
    except Exception as e:
        print(f"[QtBridge] {e}")
        return False
