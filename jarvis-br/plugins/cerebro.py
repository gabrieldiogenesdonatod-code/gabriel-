"""
Cérebro local (3.4): a IA pequena do JARVIS que aprende como VOCÊ fala e faz os comandos do dia a dia
sozinha — mais rápido, sem gastar o Gemini e funcionando sem internet.

    "Jarvis, o que o seu cérebro já aprendeu?"          "Jarvis, quais são os seus reflexos?"
    "Jarvis, o que você faria se eu dissesse 'abre a loja'?"
    "Jarvis, quando eu disser 'boa noite, chefe', liga o protocolo dormir"
    "Jarvis, esquece o comando 'abre a loja'"           "Jarvis, desliga os reflexos"

Como funciona: core/cerebro.py. Ele aprende sozinho com cada pedido que deu certo e com as suas
correções; o que você usou 2 vezes do mesmo jeito (ou ensinou) vira reflexo.
"""

from __future__ import annotations

import json

from core import cerebro as C
from plugins._lote2 import P, norm, rodar

PLUGIN = P("cerebro", "JARVIS's local brain: learns how the user phrases commands and runs known ones instantly, offline, "
                      "without Gemini. Status, test, teach, forget.",
           "estado | testar | reflexos | ensinar | esquecer | ligar | desligar",
           "estado: what it learned. testar: frase — what it would do with that sentence. reflexos: commands it runs by itself. "
           "ensinar: frase, ferramenta (exact tool name), parametros (JSON object, e.g. '{\"action\":\"ligar\"}') — when the user "
           "says the sentence, run that tool. esquecer: frase. ligar / desligar: turn instant reflexes on or off.",
           "frase ferramenta parametros")


def _cmd(e: dict) -> str:
    acao = (e.get("a") or {}).get("action")
    return f"\"{e['k']}\" → {e['f']}" + (f" ({acao})" if acao else "")


def _estado(p, pl):
    s = C.estado()
    txt = (f"Cérebro local: {s['sementes']} frases de exemplo dos plugins, {s.get('base', 0)} comandos do cérebro pronto "
           f"(+{s.get('padroes', 0)} padrões como 'abre <app>' e 'toca <música>'), {s['aprendidos']} comando(s) aprendido(s) com você "
           f"({s['ferramentas']} ferramenta(s)), {s['reflexos']} reflexo(s) prontos e {s['corrigidos']} que você corrigiu. "
           f"Reflexos {'ligados' if s['ligado'] else 'desligados'}.")
    if s["mais_usados"]:
        txt += "\nMais usados: " + "; ".join(f"{_cmd(e)} {e['ok']}×" for e in s["mais_usados"][:6]) + "."
    return txt


def _testar(p, pl):
    frase = str(p.get("frase") or "").strip()
    if not frase:
        return "Qual frase eu testo?"
    r = C.entender(frase)
    if not r["ferramenta"]:
        return f"Com \"{frase}\" eu não faria nada sozinho ({r['motivo']}); o Gemini decide."
    acao = r["args"].get("action")
    feito = "faço na hora, sem o Gemini" if r["reflexo"] else "deixo o Gemini decidir"
    alt = ", ".join(f"{f} {pr:.0%}" for f, pr in r["sugestoes"][1:3])
    return (f"Com \"{frase}\" eu penso em {r['ferramenta']}" + (f" ({acao})" if acao else "")
            + f", certeza {r['confianca']:.0%}: {feito} ({r['motivo']})." + (f" Outras: {alt}." if alt else ""))


def _reflexos(p, pl):
    firmes = C.estado()["firmes"]
    if not firmes:
        return ("Ainda não tenho reflexos. Um comando vira reflexo quando você usa do mesmo jeito 2 vezes e dá certo, "
                "ou quando você me ensina.")
    return f"{len(firmes)} reflexo(s):\n" + "\n".join(_cmd(e) for e in sorted(firmes, key=lambda e: -e["ok"])[:20])


def _ensinar(p, pl):
    frase, ferramenta = str(p.get("frase") or "").strip(), norm(p.get("ferramenta")).replace(" ", "_")
    if not frase or not ferramenta:
        return "Me diga a frase e qual ferramenta ela deve usar."
    bruto = p.get("parametros") or {}
    try:
        args = bruto if isinstance(bruto, dict) else json.loads(str(bruto) or "{}")
    except ValueError:
        return "Não entendi os parâmetros (precisa ser um objeto JSON, ex.: {\"action\": \"ligar\"})."
    if not isinstance(args, dict):
        return "Os parâmetros precisam ser um objeto JSON."
    try:
        from core import registro_ferramentas
        nomes = {d["name"] for d in registro_ferramentas.declaracoes()}
        if nomes and ferramenta not in nomes:
            return f"Não conheço a ferramenta '{ferramenta}'."
    except Exception:
        pass
    from core import verificacao
    if verificacao.nivel_de(ferramenta, args) == verificacao.CRITICO:
        return f"'{ferramenta}' é uma ferramenta crítica: não vira reflexo, sempre passa por você."
    if C.ensinar(frase, ferramenta, args) is None:
        return "Essa frase ficou vazia depois de limpar (só palavras como 'jarvis', 'por favor'). Use outra."
    return f"Aprendido: quando você disser \"{frase}\", eu uso {ferramenta}" + (f" ({args.get('action')})" if args.get("action") else "") + " na hora."


def _esquecer(p, pl):
    n = C.esquecer(str(p.get("frase") or ""))
    return f"Esqueci {n} aprendizado(s) dessa frase." if n else "Não tinha nada aprendido com essa frase."


def _ligar(p, pl):
    C.ligar_reflexos(True)
    return "Reflexos ligados: o que eu já sei faço na hora."


def _desligar(p, pl):
    C.ligar_reflexos(False)
    return "Reflexos desligados: tudo passa pelo Gemini (eu continuo aprendendo)."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estado": _estado, "testar": _testar, "reflexos": _reflexos, "ensinar": _ensinar,
                              "esquecer": _esquecer, "ligar": _ligar, "desligar": _desligar}, player, "Cérebro local")
