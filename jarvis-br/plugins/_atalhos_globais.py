"""
Atalhos globais de teclado (2.16) — vários atalhos numa thread só, pelo
RegisterHotKey do Windows (sem pacote extra). Começa com "_": não vira ferramenta.

    registrar("ctrl+alt+c", funcao)     → True se o Windows aceitou

Funciona com o JARVIS minimizado. Fora do Windows, não faz nada.
O "olha isso" (Ctrl+Alt+J) tem o atalho próprio e continua como era.
"""

from __future__ import annotations

import platform
import queue
import re
import threading

WIN = platform.system() == "Windows"
_MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
_pedidos: "queue.Queue[tuple[str, callable, threading.Event, list]]" = queue.Queue()
_funcoes: dict[int, callable] = {}
_thread: threading.Thread | None = None
_tid = {"id": 0}


def interpretar(txt: str) -> tuple[int, int] | None:
    """'ctrl+alt+c' → (modificadores, tecla virtual); inválido → None (pura)."""
    partes = [p.strip().lower() for p in (txt or "").split("+") if p.strip()]
    if len(partes) < 2:
        return None
    mods = 0x4000                                              # MOD_NOREPEAT
    for p in partes[:-1]:
        if p not in _MODS:
            return None
        mods |= _MODS[p]
    tecla = partes[-1]
    if len(tecla) == 1 and tecla.isalnum():
        return mods, ord(tecla.upper())
    if re.fullmatch(r"f([1-9]|1[0-2])", tecla):
        return mods, 0x6F + int(tecla[1:])
    return None


def _laco() -> None:
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    _tid["id"] = k32.GetCurrentThreadId()
    msg = wintypes.MSG()
    proximo = 0xC10
    while True:
        while not _pedidos.empty():                            # registros pedidos por outras threads
            combo, fn, pronto, saida = _pedidos.get()
            par = interpretar(combo)
            ok = bool(par) and bool(u32.RegisterHotKey(None, proximo, par[0], par[1]))
            if ok:
                _funcoes[proximo] = fn
                proximo += 1
            saida.append(ok)
            pronto.set()
        if u32.GetMessageW(ctypes.byref(msg), None, 0, 0) == 0:
            break
        if msg.message == 0x0312 and msg.wParam in _funcoes:   # WM_HOTKEY
            threading.Thread(target=_funcoes[msg.wParam], daemon=True).start()


def registrar(combo: str, funcao) -> bool:
    global _thread
    if not WIN or not interpretar(combo):
        return False
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_laco, daemon=True, name="atalhos_globais")
        _thread.start()
        for _ in range(50):
            if _tid["id"]:
                break
            threading.Event().wait(0.02)
    pronto, saida = threading.Event(), []
    _pedidos.put((combo, funcao, pronto, saida))
    try:                                                       # acorda o GetMessage para registrar
        import ctypes
        ctypes.windll.user32.PostThreadMessageW(_tid["id"], 0x0400, 0, 0)
    except Exception:
        pass
    pronto.wait(2)
    return bool(saida and saida[0])
