"""
Conselho de agentes internos — ideia 5 (fork PT-BR 1.4).

Para um problema complexo, cinco especialistas analisam CADA UM a sua parte,
de forma independente:

    Planejador          quebra em passos e escolhe as ferramentas
    Programador         olha o código: dependências, impacto, testes (usa o
                        mapa de dependências quando o pedido envolve código)
    Pesquisador         junta o que já se sabe: memória inteligente, arquivos
                        relacionados, o estado do PC
    Revisor             procura riscos e contradições; passa cada passo pelo
                        guardião de decisões
    Gestor de Memória   diz o que vale guardar e o que pode estar desatualizado

Depois o conselho aponta onde eles DISCORDAM e monta o plano final.

COM IA: cada especialista é uma chamada separada ao modelo, com o próprio
papel e em paralelo (eles não veem a resposta um do outro), e o plano final
é escrito por uma última chamada que recebe as cinco opiniões.
SEM IA: cada especialista é um conjunto de regras e análises locais (mais
limitado para pedidos abertos, mas real: planejamento por palavras-chave
sobre o catálogo de ferramentas, análise de código, memória e guardião).

    "Jarvis, convoca o conselho: quero automatizar o relatório de vendas da loja"
    "Jarvis, pergunta ao conselho como migrar o site da Gravyz para Flask"
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from plugins._comum import mostrar

PLUGIN = {
    "name": "conselho",
    "brief": "Council of internal agents (planner, programmer, researcher, reviewer, memory keeper) → final plan.",
    "description": (
        "Council of internal agents for complex problems or plans: Planner, Programmer, Researcher, "
        "Reviewer and Memory Keeper analyse independently, then contradictions and a final plan are "
        "produced. action='convocar' with problema (the user's request, verbatim) for 'convoca o "
        "conselho', 'o que os especialistas acham', or any multi-step plan the user wants analysed. "
        "Optional pasta = a code project folder for the Programmer. Summarise the final plan and "
        "mention the main disagreement."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "convocar"},
            "problema": {"type": "STRING"}, "pasta": {"type": "STRING"},
        },
        "required": ["problema"],
    },
}

PAPEIS = {
    "Planejador": "Quebre o pedido em passos concretos e ordenados. Para cada passo diga a ferramenta "
                  "do JARVIS que usaria (da lista dada) ou 'manual'.",
    "Programador": "Avalie a parte técnica/código: o que precisa ser escrito ou alterado, dependências, "
                   "riscos de quebrar algo e que testes rodar.",
    "Pesquisador": "Liste o que é preciso saber antes de começar e o que os dados do contexto já "
                   "respondem; aponte lacunas de informação.",
    "Revisor": "Procure riscos, ações irreversíveis, suposições frágeis e o que pode dar errado. Seja "
               "crítico; não repita o plano.",
    "Gestor de Memória": "Diga quais fatos do contexto são relevantes, quais podem estar desatualizados "
                         "e o que valeria a pena guardar depois.",
}

_FORMATO = ('Responda SÓ JSON: {"avaliacao": "2-4 frases", "pontos": ["..."], "riscos": ["..."], '
            '"confianca": 0-100} em português do Brasil.')


# ── contexto comum ─────────────────────────────────────────────────────────────
def contexto(problema: str) -> dict:
    ctx: dict = {"problema": problema}
    try:
        from core import registro_ferramentas
        ctx["ferramentas"] = sorted(registro_ferramentas.disponiveis())
    except Exception:
        ctx["ferramentas"] = []
    try:
        from plugins import memoria_inteligente as mi
        ctx["memorias"] = [{"texto": r["texto"], "confianca": round(r["confianca"], 2),
                            "categoria": r["categoria"]} for r in mi.buscar(problema)[:8]]
    except Exception:
        ctx["memorias"] = []
    try:
        from core import telemetria
        s = telemetria.get().snapshot()
        ctx["pc"] = {"cpu": s.get("cpu"), "ram_pct": (s.get("ram") or {}).get("pct"),
                     "internet": s.get("internet")}
    except Exception:
        pass
    return ctx


# ── especialistas locais (sem IA) ──────────────────────────────────────────────
def planejador_local(problema: str, ferramentas: list[str]) -> dict:
    from plugins import habilidades
    plano = habilidades.planejar_local(problema)
    pontos = [f"{i + 1}. {habilidades.descrever_passo(p)}" for i, p in enumerate(plano)] or \
        ["não reconheci passos automáticos; dividir manualmente"]
    return {"avaliacao": f"Dividi em {len(plano)} passo(s) com as ferramentas disponíveis." if plano else
            "Não achei ferramentas que encaixem diretamente no pedido.",
            "pontos": pontos, "riscos": [], "confianca": 60 if plano else 25, "plano": plano}


def programador_local(problema: str, pasta: str) -> dict:
    t = problema.lower()
    if not (pasta or re.search(r"\b(c[oó]digo|python|\.py|fun[cç][aã]o|m[oó]dulo|script|projeto|api|site|bug|refator)", t)):
        return {"avaliacao": "O pedido não envolve código; nada a analisar.", "pontos": [], "riscos": [], "confianca": 70}
    from plugins import mapa_dependencias as md
    raiz = md.raiz_padrao(pasta)
    try:
        g = md.analisar(raiz)
    except Exception as e:
        return {"avaliacao": f"Não consegui analisar o código: {e}", "pontos": [], "riscos": [], "confianca": 20}
    alvo = next((m for m in g["modulos"] if m.split(".")[-1] in t), None)
    pontos = [f"{len(g['modulos'])} módulos em {raiz.name}"]
    riscos = []
    if alvo:
        imp = md.impacto(g, alvo)
        pontos.append(f"{alvo} afeta {len(imp['dependentes'])} módulo(s); testes: {', '.join(imp['testes']) or 'nenhum'}")
        if not imp["testes"]:
            riscos.append(f"não há testes cobrindo {alvo}")
    if g["ciclos"]:
        riscos.append(f"{len(g['ciclos'])} dependência(s) circular(es)")
    return {"avaliacao": "Analisei a estrutura do código antes de mexer.", "pontos": pontos, "riscos": riscos,
            "confianca": 65}


def pesquisador_local(ctx: dict) -> dict:
    pontos = [f"memória: {m['texto']} ({round(100 * m['confianca'])}%)" for m in ctx.get("memorias", [])[:4]]
    try:
        from plugins.controle_sistema import buscar
        palavras = [w for w in re.findall(r"\w{5,}", ctx["problema"].lower())][:2]
        if palavras:
            arqs = buscar(" ".join(palavras[:1]), segundos=3, limite=3)
            pontos += [f"arquivo relacionado: {a.name}" for a in arqs]
    except Exception:
        pass
    lacunas = [] if pontos else ["não encontrei nada guardado ou nos arquivos sobre isso"]
    return {"avaliacao": "Juntei o que já existe sobre o assunto." if pontos else "Pouca informação disponível.",
            "pontos": pontos, "riscos": lacunas, "confianca": 55 if pontos else 30}


def revisor_local(plano: list[dict]) -> dict:
    from plugins import _guardiao
    riscos, pontos = [], []
    for p in plano:
        av = _guardiao.avaliar(p.get("ferramenta", ""), p.get("params", {}), p.get("descricao", ""))
        if av.decisao != "automático":
            riscos.append(av.texto())
        else:
            pontos.append(f"ok: {av.acao}")
    return {"avaliacao": "Passei cada passo pelo guardião de decisões." if plano else "Sem passos para revisar.",
            "pontos": pontos, "riscos": riscos, "confianca": 75}


def gestor_local(ctx: dict) -> dict:
    velhas = [m for m in ctx.get("memorias", []) if m["confianca"] < 0.5]
    return {"avaliacao": "Conferi a memória relacionada.",
            "pontos": [f"relevante: {m['texto']}" for m in ctx.get("memorias", []) if m["confianca"] >= 0.5][:4]
            + [f"guardar depois: a decisão final sobre '{ctx['problema'][:50]}'"],
            "riscos": [f"pode estar desatualizado: {m['texto']}" for m in velhas], "confianca": 60}


# ── contradições e plano ───────────────────────────────────────────────────────
def contradicoes(opinioes: dict) -> list[str]:
    """Onde os especialistas discordam (pura)."""
    saida = []
    confs = {k: v.get("confianca", 50) for k, v in opinioes.items()}
    if confs and max(confs.values()) - min(confs.values()) >= 40:
        alto = max(confs, key=confs.get)
        baixo = min(confs, key=confs.get)
        saida.append(f"{alto} está confiante ({confs[alto]}%), mas {baixo} não ({confs[baixo]}%)")
    plan = opinioes.get("Planejador", {})
    rev = opinioes.get("Revisor", {})
    if plan.get("riscos") == [] and rev.get("riscos"):
        saida.append(f"o Planejador não viu riscos, o Revisor viu {len(rev['riscos'])}")
    pesq = opinioes.get("Pesquisador", {})
    if pesq.get("riscos") and plan.get("confianca", 0) >= 60:
        saida.append("o Planejador seguiria adiante, mas o Pesquisador aponta falta de informação")
    return saida


def convocar(problema: str, pasta: str = "") -> dict:
    from plugins import _ia
    ctx = contexto(problema)
    if _ia.disponivel():
        base = (f"Você é o {{papel}} do conselho interno do assistente JARVIS (num PC Windows). {{instrucao}}\n"
                f"Pedido do usuário: \"{problema}\"\nContexto (JSON): {json.dumps(ctx, ensure_ascii=False)[:6000]}\n"
                + _FORMATO)
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = {papel: ex.submit(_ia.perguntar_json, base.format(papel=papel, instrucao=instr), False, 40)
                    for papel, instr in PAPEIS.items()}
            opinioes = {}
            for papel, f in futs.items():
                r = f.result()
                opinioes[papel] = r if isinstance(r, dict) and r.get("avaliacao") else None
        # Revisor também usa o guardião sobre o plano local, para ter algo medido
        plano_local = planejador_local(problema, ctx["ferramentas"]).get("plano", [])
        rev_local = revisor_local(plano_local)
        if opinioes.get("Revisor"):
            opinioes["Revisor"]["riscos"] = list(opinioes["Revisor"].get("riscos", [])) + rev_local["riscos"]
        faltaram = [k for k, v in opinioes.items() if not v]
        for k in faltaram:                   # um especialista que não respondeu vira o local
            opinioes[k] = _local(k, problema, pasta, ctx, plano_local)
        final = _ia.perguntar_json(
            "Você coordena o conselho do JARVIS. Opiniões independentes (JSON): "
            + json.dumps(opinioes, ensure_ascii=False)[:9000]
            + f"\nPedido: \"{problema}\". Aponte as contradições entre eles e produza o plano final. "
            'Responda SÓ JSON: {"contradicoes": ["..."], "plano": ["passo 1", "..."], "resumo": "2 frases"} '
            "em português do Brasil.", True, 60)
        modo = "IA (5 chamadas independentes + síntese)"
        if isinstance(final, dict) and final.get("plano"):
            return {"modo": modo, "opinioes": opinioes, "contradicoes": final.get("contradicoes") or contradicoes(opinioes),
                    "plano": final["plano"], "resumo": final.get("resumo", "")}
    else:
        modo = "local (regras, análise de código, memória e guardião; sem IA)"
        plano_local = planejador_local(problema, ctx["ferramentas"]).get("plano", [])
        opinioes = {k: _local(k, problema, pasta, ctx, plano_local) for k in PAPEIS}
    from plugins import habilidades
    plano_txt = [habilidades.descrever_passo(p) for p in plano_local] or \
        ["dividir o pedido em partes menores e pedir uma de cada vez"]
    riscos = opinioes["Revisor"].get("riscos", [])
    if riscos:
        plano_txt.append("confirmar com você os passos marcados pelo Revisor antes de executar")
    return {"modo": modo, "opinioes": opinioes, "contradicoes": contradicoes(opinioes), "plano": plano_txt,
            "resumo": f"{len(plano_txt)} passo(s); {len(riscos)} risco(s) apontado(s) pelo Revisor."}


def _local(papel: str, problema: str, pasta: str, ctx: dict, plano: list[dict]) -> dict:
    if papel == "Planejador":
        r = planejador_local(problema, ctx["ferramentas"])
        r.pop("plano", None)
        return r
    if papel == "Programador":
        return programador_local(problema, pasta)
    if papel == "Pesquisador":
        return pesquisador_local(ctx)
    if papel == "Revisor":
        return revisor_local(plano)
    return gestor_local(ctx)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    problema = str(p.get("problema") or "").strip()
    if not problema:
        return "Qual problema o conselho deve analisar?"
    try:
        r = convocar(problema, str(p.get("pasta") or ""))
        linhas = [f"Modo: {r['modo']}", ""]
        for papel, op in r["opinioes"].items():
            linhas += [f"■ {papel.upper()} (confiança {op.get('confianca', '?')}%)", f"  {op.get('avaliacao', '')}"]
            linhas += [f"  • {x}" for x in op.get("pontos", [])[:6]]
            linhas += [f"  ⚠ {x}" for x in op.get("riscos", [])[:5]]
            linhas.append("")
        linhas += ["CONTRADIÇÕES"] + [f"  ↔ {c}" for c in r["contradicoes"] or ["nenhuma relevante"]]
        linhas += ["", "PLANO FINAL"] + [f"  {i}. {x}" for i, x in enumerate(r["plano"], 1)]
        mostrar(player, "CONSELHO DE AGENTES", "\n".join(linhas))
        fala = f"O conselho analisou ({r['modo'].split(' ')[0]}). {r.get('resumo', '')} Plano: " + \
            "; ".join(str(x) for x in r["plano"][:4]) + "."
        if r["contradicoes"]:
            fala += f" Ponto de discordância: {r['contradicoes'][0]}."
        return fala
    except Exception as e:
        return f"O conselho falhou: {e}"
