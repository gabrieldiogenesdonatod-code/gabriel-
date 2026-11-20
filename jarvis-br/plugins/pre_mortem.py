"""
Pré-mortem (3.0): antes de começar um projeto, o JARVIS imagina que já é daqui a um mês e que ele
DEU ERRADO — e conta por quê. Assim você vê os riscos enquanto ainda dá para evitar.

    "Jarvis, faz um pré-mortem da loja online."      "Jarvis, pré-mortem do meu modelo de IA, prazo 2 meses."

Depois do prazo ele pergunta o que realmente aconteceu e vai aprendendo onde os seus projetos
costumam tropeçar. Sem a chave do Gemini, usa uma lista de tropeços comuns.
"""

from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import P, carregar, guardar, num1, numeros, rodar

PLUGIN = P("pre_mortem", "Pre-mortem: imagines your project already failed in N weeks and lists the most likely causes, warning signs and "
           "prevention; later asks what really happened and learns your usual pitfalls.",
           "analisar | listar | ver | aconteceu | tropecos",
           "analisar: projeto, prazo (weeks, default 4), contexto. ver: projeto. aconteceu: projeto, numeros (causes that "
           "happened, e.g. '1 3'). tropecos: what usually goes wrong for you.",
           "projeto prazo contexto numeros")

COMUNS = [("O prazo era otimista demais", "a primeira semana passou e menos de 25% estava pronto", "corte o escopo pela metade hoje"),
          ("Ninguém de fora testou antes", "você é a única pessoa que viu o projeto", "mostre para 2 pessoas nesta semana"),
          ("O escopo cresceu no meio do caminho", "apareceu 'só mais uma coisa' três vezes", "anote as ideias novas para a versão 2"),
          ("Faltou dinheiro ou tempo reservado", "você não sabe quanto já gastou", "defina um teto de gasto e de horas"),
          ("Dependia de uma coisa fora do seu controle", "você está esperando alguém responder", "tenha um plano B para essa peça")]


def gerar(projeto: str, semanas: int, contexto: str = "") -> dict:
    from core import gemini
    pedido = (f"Faça um PRÉ-MORTEM. Imagine que hoje é {semanas} semana(s) no futuro e que o projeto abaixo FRACASSOU. "
              "Liste as 5 causas mais prováveis, específicas para este projeto (não genéricas), em português do Brasil.\n"
              f"Projeto: {projeto}\n" + (f"Contexto: {contexto}\n" if contexto else "") +
              'Responda SÓ com JSON: {"causas": [{"causa": "...", "chance": "alta|média|baixa", "sinal": "o primeiro sinal de '
              'que isso está acontecendo", "prevencao": "o que fazer agora"}], "primeira_acao": "uma ação para amanhã"}')
    d = gemini.as_json(pedido, tier=gemini.SMART, default=None)
    if isinstance(d, dict) and d.get("causas"):
        return d
    return {"causas": [{"causa": c, "chance": "média", "sinal": s, "prevencao": pv} for c, s, pv in COMUNS],
            "primeira_acao": "Escreva em uma frase o que conta como 'deu certo'.", "offline": True}


def texto(pm: dict) -> str:
    linhas = [f"{i}. {c['causa']} (chance {c.get('chance', '?')})\n   sinal: {c.get('sinal', '')}\n   evitar: {c.get('prevencao', '')}"
              for i, c in enumerate(pm["causas"], 1)]
    return "\n".join(linhas) + f"\nPrimeira ação: {pm.get('primeira_acao', '')}"


def _achar(lista: list[dict], q: str) -> dict | None:
    q = (q or "").lower().strip()
    return next((x for x in reversed(lista) if q and q in x["projeto"].lower()), lista[-1] if lista and not q else None)


def _go(p, pl):
    a, lista = p["action"], carregar("pre_mortem", [])
    if a == "analisar":
        proj = str(p.get("projeto") or "").strip()
        if len(proj) < 3:
            return "Qual é o projeto?"
        sem = int(num1(p, "prazo", 4))
        pm = gerar(proj, sem, str(p.get("contexto") or ""))
        lista.append({"projeto": proj, "feito": date.today().isoformat(), "revisar": (date.today() + timedelta(7 * sem)).isoformat(),
                      **pm, "aconteceu": None})
        guardar("pre_mortem", lista[-40:])
        from plugins._comum import mostrar
        mostrar(pl, f"PRÉ-MORTEM — {proj.upper()}", texto(pm))
        return (f"Imaginei {proj} fracassado daqui a {sem} semana(s). A causa mais provável: {pm['causas'][0]['causa']}. "
                f"Primeira ação: {pm.get('primeira_acao', '')}" + (" (lista genérica: sem a IA agora)" if pm.get("offline") else ""))
    if a == "listar":
        return "\n".join(f"{x['projeto']} (feito {x['feito']}, revisar {x['revisar']})" + (" ✓" if x.get("aconteceu") is not None else "")
                         for x in lista) or "Nenhum pré-mortem ainda."
    if a == "tropecos":
        ocorridas = [c["causa"] for x in lista if x.get("aconteceu") for i, c in enumerate(x["causas"], 1) if i in x["aconteceu"]]
        if not ocorridas:
            return "Ainda não revisamos nenhum projeto. Depois do prazo, diga quais causas aconteceram."
        return "O que mais derrubou os seus projetos: " + "; ".join(ocorridas[-6:]) + "."
    x = _achar(lista, p.get("projeto"))
    if not x:
        return "Não achei esse pré-mortem."
    if a == "ver":
        return f"{x['projeto']}:\n" + texto(x)
    x["aconteceu"] = [int(n) for n in numeros(p.get("numeros"))]
    guardar("pre_mortem", lista)
    return f"Anotado: {len(x['aconteceu'])} das {len(x['causas'])} causas aconteceram em {x['projeto']}. Vou lembrar disso nos próximos."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("analisar listar ver aconteceu tropecos".split(), _go), player, "Pré-mortem")
