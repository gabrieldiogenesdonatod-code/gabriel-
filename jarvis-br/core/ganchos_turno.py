"""
Ganchos de fim de turno (fork PT-BR 2.4).

O main.py chama `turno(fala_do_usuario, resposta, interrompido)` sempre que
uma troca termina. Daqui vai para quem precisa saber:
  • core/evolucao.py  — aprende com a sua reação à resposta anterior;
  • quem se registrar  — ex.: o diário por entrevista guarda o que você contou.
Nada aqui pode travar ou derrubar a conversa: tudo roda numa thread curta e
os erros só vão para o console.
"""

from __future__ import annotations

import threading

_ouvintes: list = []


def registrar(fn) -> None:
    """fn(entrada, saida, interrompido)."""
    if fn not in _ouvintes:
        _ouvintes.append(fn)


def remover(fn) -> None:
    if fn in _ouvintes:
        _ouvintes.remove(fn)


def _rodar(entrada: str, saida: str, interrompido: bool) -> None:
    try:
        from core import evolucao
        evolucao.turno(entrada, saida, interrompido)
    except Exception as e:
        print(f"[Ganchos] evolução: {e}")
    try:                                              # Fork PT-BR 3.3: caixa-preta (erros que você corrigiu)
        from core import caixa_preta
        caixa_preta.turno(entrada, saida)
    except Exception as e:
        print(f"[Ganchos] caixa-preta: {e}")
    try:                                              # Fork PT-BR 3.4: cérebro local aprende frase → ferramenta
        from core import cerebro
        cerebro.turno(entrada, saida)
    except Exception as e:
        print(f"[Ganchos] cérebro: {e}")
    try:                                              # Fork PT-BR 2.13: porteiro de voz
        from core import porteiro
        porteiro.aplicar_turno(entrada, saida, interrompido)
    except Exception as e:
        print(f"[Ganchos] porteiro: {e}")
    for fn in list(_ouvintes):
        try:
            fn(entrada, saida, interrompido)
        except Exception as e:
            print(f"[Ganchos] {getattr(fn, '__name__', fn)}: {e}")


def turno(entrada: str, saida: str, interrompido: bool = False, esperar: bool = False) -> None:
    entrada, saida = str(entrada or "").strip(), str(saida or "").strip()
    if not entrada and not saida:
        return
    try:
        from core import anonimo                 # 3.2: modo anônimo — ninguém aprende nem anota a conversa
        if anonimo.ativo():
            return
    except Exception:
        pass
    if esperar:
        _rodar(entrada, saida, interrompido)
        return
    threading.Thread(target=_rodar, args=(entrada, saida, interrompido), daemon=True, name="ganchos_turno").start()
