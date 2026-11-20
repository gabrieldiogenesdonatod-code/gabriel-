"""
OMEGA (3.6): os 8 sistemas do JARVIS funcionando como um só — Brain, Heart, Immune, Memory, Council,
Evolution, Dream e Lab — com um painel de dados reais e um ciclo que liga um no outro.

    "Jarvis, abre o painel OMEGA"                 "Jarvis, como está o OMEGA?"
    "Jarvis, roda o ciclo OMEGA"                  → sonho → hipótese → experimento → evolução → integridade
    "Jarvis, como está o sistema IMMUNE?"         "Jarvis, o que o OMEGA propôs?"

O ciclo roda sozinho uma vez por dia e só PROPÕE: experimento novo e evolução do cérebro precisam do seu
sim. Peças que ele liga: experimento_vida (experimentos sorteados na sua vida), livro_razao (prova à prova
de adulteração), metacognicao (o quanto confiar no JARVIS), sonhos, cerebro, organismo, conselho e multiverso.
Como funciona: core/omega.py.
"""

from __future__ import annotations

import time

from core import omega as O
from plugins._lote2 import P, norm, rodar

PLUGIN = P("omega", "OMEGA: JARVIS's 8 systems as one (brain, heart, immune, memory, council, evolution, dream, lab): live panel, "
                    "status, daily cycle and its proposals.",
           "estado | painel | ciclo | sistema | propostas",
           "estado: one-line state of the whole + each system. painel: opens the live OMEGA panel. ciclo: runs the cycle now "
           "(dream → hypothesis → experiment proposal → evolution check → integrity). sistema: nome (brain, heart, immune, memory, "
           "council, evolution, dream, lab). propostas: experiments the cycle suggested. Related tools: experimento_vida "
           "(randomized life experiments), livro_razao (tamper-evident ledger), metacognicao (self-trust scoreboard).",
           "nome")

APELIDOS = {"cerebro": "brain", "coracao": "heart", "imune": "immune", "imunologico": "immune", "memoria": "memory",
            "conselho": "council", "evolucao": "evolution", "sonho": "dream", "sonhos": "dream", "laboratorio": "lab"}


def _estado(p, pl):
    ss = O.sistemas()
    return O.consciencia(ss) + "\n" + "\n".join(f"{s['nome']} ({O.ROTULO[s['estado']]}): {s['frase']}" for s in ss)


def _painel(p, pl):
    arq = O.abrir_painel()
    return f"Painel OMEGA aberto, com os dados de agora dos 8 sistemas. {O.consciencia()} Arquivo: {arq}"


def _ciclo(p, pl):
    return O.texto_ciclo(O.ciclo())


def _sistema(p, pl):
    q = norm(p.get("nome"))
    q = APELIDOS.get(q, q)
    s = next((x for x in O.sistemas() if x["id"] == q or norm(x["nome"]) == q), None)
    if not s:
        return "Qual sistema? brain, heart, immune, memory, council, evolution, dream ou lab."
    nums = "; ".join(f"{k}: {v}" for k, v in s["numeros"])
    return f"{s['nome']} — {s['papel']} ({O.ROTULO[s['estado']]}). {s['frase']}" + (f" Números: {nums}." if nums else "") + \
        (f" Peças: {', '.join(s['pecas'])}." if s["pecas"] else "")


def _propostas(p, pl):
    ps = O.propostas()
    if not ps:
        return "O ciclo não tem experimento proposto agora. Ele procura de novo a cada dia; ou diga 'roda o ciclo OMEGA'."
    return "O ciclo OMEGA sugeriu tirar a prova de:\n" + "\n".join(
        f"- {x['texto']} → \"cria um experimento: {x['tratamento']}, medindo {x['efeito']}\"" for x in ps)


def passo(player) -> None:
    """Relógio central: um ciclo por dia (depois das 7h); só fala se houver novidade."""
    ult = O.ultimo_ciclo()
    agora = time.localtime()
    if agora.tm_hour < 7 or (ult and ult.get("dia") == time.strftime("%Y-%m-%d", agora)):
        return
    reg = O.ciclo()
    if reg["novidades"]:
        from plugins._comum import avisar, mostrar
        mostrar(player, "CICLO OMEGA", O.texto_ciclo(reg))
        avisar(player, f"O ciclo OMEGA de hoje trouxe {len(reg['novidades'])} novidade(s). Está no painel.", "OMEGA")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("omega_ciclo", lambda: passo(player), a_cada_s=3600, primeira_em_s=600)
    relogio.agendar("omega_painel", O.manter_painel, a_cada_s=60, primeira_em_s=60)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estado": _estado, "painel": _painel, "ciclo": _ciclo, "sistema": _sistema,
                              "propostas": _propostas}, player, "OMEGA")
