"""
Uma thread só para o COM do Windows (pycaw/comtypes) — fork PT-BR 2.8.3.

O ERRO QUE FECHAVA O JARVIS (o seu erros.log mostrou):

    Windows fatal exception: access violation
    Current thread … (a thread da JANELA):
      Garbage-collecting
      comtypes\\_post_coinit\\unknwn.py, line 420 in Release
      core\\avatar.py … paint …

O volume do Windows, o medidor "tem som tocando?" (core/estado_mundo, central de
avisos, pausa ausente…) e a lista de saídas de som usam objetos COM (pycaw). Eles
eram criados em VÁRIAS threads, cada uma com o seu COM. Quando a thread acabava,
o objeto ficava para o coletor de lixo do Python — que roda em qualquer thread,
inclusive na da janela enquanto ela desenha o rosto. Soltar (Release) um objeto
COM fora do lugar onde ele nasceu, depois que aquele COM já foi desligado, é
"access violation": o Windows fecha o programa na hora.

Agora TODO uso de pycaw/comtypes roda numa thread fixa, que vive até o fim do
programa e liga o COM uma vez só. Os objetos nascem e morrem ali (com uma coleta
de lixo logo depois de cada tarefa); para fora só saem números e textos.

    from core import com_unico
    volume = com_unico.executar(ler_volume)          # devolve o que ler_volume() devolver
"""

from __future__ import annotations

import gc
import platform
import queue
import threading

WIN = platform.system() == "Windows"
_fila: queue.Queue = queue.Queue()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _laco() -> None:
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception as e:
        print(f"[COM] não iniciei o COM: {e}")
    while True:
        tarefa = _fila.get()
        if tarefa is None:
            break
        fn, args, kwargs, caixa, pronto = tarefa
        try:
            caixa["ok"] = fn(*args, **kwargs)
        except BaseException as e:                       # noqa: BLE001 — volta para quem pediu
            caixa["erro"] = e
        finally:
            del fn, args, kwargs, tarefa
            try:
                gc.collect()                             # o lixo COM morre AQUI, não na thread da janela
            except Exception:
                pass
            pronto.set()


def _garantir() -> None:
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_laco, daemon=True, name="com_unico")
            _thread.start()


def na_thread_com() -> bool:
    return threading.current_thread() is _thread


def executar(fn, *args, timeout: float = 10.0, **kwargs):
    """Roda fn na thread do COM e devolve o resultado (ou levanta o erro dela). Fora do Windows, roda direto.
    Nunca devolva um objeto COM para fora: devolva números/textos."""
    if not WIN or na_thread_com():
        return fn(*args, **kwargs)
    _garantir()
    caixa: dict = {}
    pronto = threading.Event()
    _fila.put((fn, args, kwargs, caixa, pronto))
    if not pronto.wait(timeout):
        raise TimeoutError("o COM do Windows não respondeu a tempo")
    if "erro" in caixa:
        raise caixa["erro"]
    return caixa.get("ok")


def na_com(fn):
    """Decorador: a função sempre roda na thread do COM, venha de onde vier a chamada."""
    import functools

    @functools.wraps(fn)
    def envolvida(*args, **kwargs):
        return executar(fn, *args, timeout=30.0, **kwargs)
    return envolvida


def comtypes_fora_daqui(raiz) -> list[str]:
    """Para o teste: arquivos que importam pycaw/comtypes sem passar por aqui (pura sobre os textos)."""
    ruins = []
    for arq in raiz.rglob("*.py"):
        if "tests" in arq.parts or arq.name in ("com_unico.py", "installer.py", "por_que_fechou.py"):
            continue
        t = arq.read_text(encoding="utf-8", errors="replace")
        if ("pycaw" in t or "import comtypes" in t or "from comtypes" in t) and "com_unico" not in t:
            ruins.append(str(arq.relative_to(raiz)))
    return ruins
