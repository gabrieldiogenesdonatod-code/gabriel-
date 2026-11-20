"""
★ SALVOS por voz (fork PT-BR 3.9.3) — o mesmo memory/salvos.json do painel ★ SALVOS.

    "Jarvis, salva que eu preciso comprar tecido amanhã"
    "Jarvis, o que eu salvei?"          "Jarvis, procura nos salvos 'tecido'"
    "Jarvis, apaga o último salvo"

Na caixa de texto também dá: "salvar: ..." (não passa pela IA). Detalhes: hud39/salvos.py.
"""
from __future__ import annotations

from plugins._lote2 import P, rodar

PLUGIN = P("salvos", "Saved items: save anything the user asks to keep, list, search and delete them.",
           "salvar | listar | procurar | apagar_ultimo",
           "The user's own saved list (★ SALVOS panel). Use 'salvar' with texto when the user says 'salva', "
           "'guarda', 'anota pra mim', 'save this'; 'listar' for 'o que eu salvei?'; 'procurar' with texto to "
           "search; 'apagar_ultimo' to delete the newest. Do NOT use for long-term memory about the user's life "
           "(that is the assistant's own memory) or for reminders at a time (use the reminder tool).",
           "texto")


def _salvar(p, player):
    from hud39 import salvos
    texto = str(p.get("texto") or "").strip()
    if not texto:
        return "O que você quer que eu salve?"
    salvos.adicionar(texto)
    return f"Salvo: {texto}"


def _listar(p, player):
    from hud39 import salvos
    itens = salvos.listar()
    if not itens:
        return "Você ainda não salvou nada."
    linhas = [f"- {i.get('titulo') or i.get('texto')} ({i.get('quando')})" for i in itens[:10]]
    extra = f"\n(e mais {len(itens) - 10})" if len(itens) > 10 else ""
    return f"Você tem {len(itens)} item(ns) salvo(s):\n" + "\n".join(linhas) + extra


def _procurar(p, player):
    from hud39 import salvos
    achados = salvos.procurar(p.get("texto") or "")
    if not achados:
        return "Não achei nada salvo com isso."
    return "\n".join(f"- {i.get('titulo') or i.get('texto')} ({i.get('quando')})" for i in achados[:10])


def _apagar_ultimo(p, player):
    from hud39 import salvos
    itens = salvos.listar()
    if not itens:
        return "Não há nada salvo."
    salvos.apagar(itens[0]["id"])
    return f"Apaguei: {itens[0].get('titulo') or itens[0].get('texto')}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    return rodar(parameters, {"salvar": _salvar, "listar": _listar, "procurar": _procurar,
                              "apagar_ultimo": _apagar_ultimo}, player, "SALVOS")
