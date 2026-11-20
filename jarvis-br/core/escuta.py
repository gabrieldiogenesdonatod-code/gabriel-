"""
core/escuta.py — uma cópia do microfone para quem precisa ouvir (fork PT-BR 1.5).

O main.py chama `alimentar()` dentro da callback do microfone. Aqui só se
guarda o bloco numa fila (custo de um append): nada pesado roda na thread de
áudio. Quem usa:

    • a verificação de voz — pega o ÚLTIMO TRECHO DE FALA (o próprio pedido)
      para conferir se é você;
    • o ouvido ambiente — recebe o áudio contínuo, numa thread própria, para
      reconhecer campainha, alarme etc.

Guarda só os últimos 30 s, na memória. Nada vai para o disco nem para a rede.
O microfone é 16 kHz, mono, 16 bits (o mesmo que vai para o modelo).
"""

from __future__ import annotations

import collections
import queue
import threading
import time

TAXA = 16000
_buffer: collections.deque = collections.deque(maxlen=int(30 * TAXA / 1024) + 4)   # (ts, bloco, falando)
_fila: queue.Queue = queue.Queue(maxsize=300)
_inscritos: list = []
_trabalhador = {"rodando": False}

# trechos de fala do usuário (detecção simples por energia)
_LIMIAR_RMS = 350.0          # int16; fala normal fica bem acima
_SILENCIO_FIM_S = 0.6
_trechos: collections.deque = collections.deque(maxlen=6)    # (inicio, fim, [blocos])
_atual = {"blocos": [], "inicio": 0.0, "ultimo_som": 0.0}
_lock = threading.Lock()


def alimentar(indata, mudo: bool = False, jarvis_falando: bool = False) -> None:
    """Chamado da callback do microfone. Nunca levanta exceção, nunca bloqueia."""
    try:
        bloco = indata.copy().reshape(-1)
        agora = time.time()
        _buffer.append((agora, bloco, bool(jarvis_falando)))
        if not jarvis_falando and not mudo:
            _marcar_fala(agora, bloco)
        if _inscritos:
            try:
                _fila.put_nowait((agora, bloco, bool(mudo), bool(jarvis_falando)))
            except queue.Full:
                pass
    except Exception:
        pass


def _rms(bloco) -> float:
    import numpy as np
    return float(np.sqrt(np.mean(np.square(bloco.astype("float32"))))) if len(bloco) else 0.0


def _marcar_fala(agora: float, bloco) -> None:
    alto = _rms(bloco) >= _LIMIAR_RMS
    with _lock:
        if alto:
            if not _atual["blocos"]:
                _atual["inicio"] = agora
            _atual["blocos"].append(bloco)
            _atual["ultimo_som"] = agora
        elif _atual["blocos"]:
            _atual["blocos"].append(bloco)                        # pausa curta faz parte da frase
            if agora - _atual["ultimo_som"] >= _SILENCIO_FIM_S:
                dur = len(_atual["blocos"]) * len(bloco) / TAXA
                if dur >= 0.8:
                    _trechos.append((_atual["inicio"], agora, list(_atual["blocos"])))
                _atual["blocos"] = []


_entrada = {"ts": 0.0, "origem": ""}


def marcar_entrada(origem: str = "") -> None:
    """O usuário pediu algo AGORA: fala reconhecida pelo modelo, texto digitado na
    interface ou pedido pelo celular/capacete. Usado pela proteção contra texto de
    fora (core/verificacao.py). O som do microfone sozinho NÃO conta: jogo ou vídeo
    no alto-falante também fazem barulho."""
    _entrada.update(ts=time.time(), origem=origem)


def marcar_digitado() -> None:
    marcar_entrada("digitado")


def ultima_entrada() -> float:
    """Quando o usuário pediu algo pela última vez (falou, digitou ou mandou pelo celular)."""
    return _entrada["ts"]


def ultimo_trecho(max_idade_s: float = 25.0, minimo_s: float = 1.2):
    """O último trecho de fala (numpy int16), juntando trechos recentes até ter o mínimo.
    None se não há fala recente suficiente."""
    import numpy as np
    agora = time.time()
    with _lock:
        candidatos = [t for t in _trechos if agora - t[1] <= max_idade_s]
        if _atual["blocos"] and agora - _atual["ultimo_som"] <= 2:
            candidatos.append((_atual["inicio"], agora, list(_atual["blocos"])))
    if not candidatos:
        return None
    juntos, total = [], 0.0
    for ini, fim, blocos in reversed(candidatos):
        juntos.insert(0, np.concatenate(blocos))
        total += (fim - ini)
        if total >= minimo_s * 2:
            break
    audio = np.concatenate(juntos)
    return audio if len(audio) / TAXA >= minimo_s else None


def recentes(segundos: float = 10.0):
    """Os últimos N segundos do microfone (numpy int16), sem a voz do próprio JARVIS."""
    import numpy as np
    limite = time.time() - segundos
    blocos = [b for ts, b, falando in list(_buffer) if ts >= limite and not falando]
    return np.concatenate(blocos) if blocos else None


def inscrever(funcao) -> None:
    """funcao(ts, bloco_int16, mudo, jarvis_falando) — chamada numa thread própria."""
    if funcao not in _inscritos:
        _inscritos.append(funcao)
    if not _trabalhador["rodando"]:
        _trabalhador["rodando"] = True
        threading.Thread(target=_distribuir, daemon=True, name="escuta").start()


def desinscrever(funcao) -> None:
    if funcao in _inscritos:
        _inscritos.remove(funcao)


def _distribuir() -> None:
    while True:
        ts, bloco, mudo, falando = _fila.get()
        for f in list(_inscritos):
            try:
                f(ts, bloco, mudo, falando)
            except Exception as e:
                print(f"[Escuta] {e}")


def ativo() -> bool:
    """O microfone mandou áudio nos últimos 3 s?"""
    return bool(_buffer) and time.time() - _buffer[-1][0] < 3
