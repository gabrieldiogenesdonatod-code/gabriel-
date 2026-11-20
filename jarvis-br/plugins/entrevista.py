"""
Simulador de entrevista de emprego por voz (fork PT-BR 1.6).

O JARVIS vira o entrevistador: faz uma pergunta por vez (técnicas e de
comportamento, do nível que você escolher), ouve a sua resposta e, no fim,
dá o feedback — pontos fortes, o que melhorar, uma nota e como responder
melhor. Também conta vícios de fala ("tipo", "né", "aí").

    "Jarvis, simula uma entrevista para desenvolvedor Python júnior"
    "Jarvis, entrevista de suporte técnico"        "Jarvis, termina a entrevista"
"""

from __future__ import annotations

import random
import re
import time

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "entrevista",
    "brief": "Voice job-interview simulator: one question at a time, records answers, feedback and score at the end.",
    "description": (
        "Job interview simulator. action='comecar' with area (e.g. 'desenvolvedor Python', 'suporte', 'vendas') + "
        "nivel (estagio|junior|pleno|senior); then, after EACH user answer, call action='responder' with resposta (the "
        "user's answer, verbatim) to get the next question; action='terminar' gives the feedback. While it runs, act "
        "as a polite interviewer and only read the questions this tool returns."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "comecar | responder | terminar"},
                       "area": {"type": "STRING"}, "nivel": {"type": "STRING"}, "resposta": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "entrevista.json"
COMPORTAMENTAIS = [
    "Me fale um pouco sobre você e sua trajetória.",
    "Por que você quer trabalhar com isso?",
    "Conte uma situação difícil no trabalho ou nos estudos e como você resolveu.",
    "Qual foi o projeto de que você mais se orgulha? O que você fez nele?",
    "Como você lida com prazo apertado e várias tarefas ao mesmo tempo?",
    "Conte uma vez em que você errou. O que aprendeu?",
    "Como você aprende uma tecnologia ou assunto novo?",
    "Onde você se vê daqui a dois anos?",
]
TECNICAS = {
    "python": ["Qual a diferença entre lista e tupla em Python?", "O que é um dicionário e quando você usa?",
               "Explique o que é uma função lambda.", "Como você trata erros em Python?",
               "O que são ambientes virtuais e por que usar?", "Como você escreveria um teste para uma função?",
               "O que é uma API REST? Já consumiu ou criou alguma?", "Explique list comprehension com um exemplo."],
    "web": ["Qual a diferença entre GET e POST?", "O que é o DOM?", "Como você deixa um site responsivo?",
            "O que é CORS?", "Diferença entre let, const e var em JavaScript?", "Como funciona um cookie de sessão?"],
    "suporte": ["Um usuário diz que a internet não funciona. Como você investiga?", "O que é DNS?",
                "Como você explica um problema técnico para quem não é da área?", "O que você faz se não souber a resposta?",
                "Diferença entre IP público e privado?", "Como você prioriza vários chamados ao mesmo tempo?"],
    "dados": ["Qual a diferença entre INNER JOIN e LEFT JOIN?", "O que é normalização de banco de dados?",
              "Como você trataria dados faltando numa planilha?", "O que é um índice no banco e quando usar?"],
    "vendas": ["Como você abordaria um cliente que só está olhando?", "Como lida com a objeção 'está caro'?",
               "Me venda esta caneta.", "Como você fideliza um cliente?"],
}
VICIOS = ["tipo", "ne", "né", "ai", "aí", "entao", "então", "assim", "basicamente", "meio que", "sei la", "sei lá"]


def area_tecnica(area: str) -> str:
    a = area.lower()
    for chave, palavras in (("python", ("python", "backend", "back-end", "programador", "desenvolvedor", "dev")),
                            ("web", ("front", "web", "javascript", "react", "site")), ("suporte", ("suporte", "ti", "help")),
                            ("dados", ("dados", "sql", "analista", "bi")), ("vendas", ("vend", "loja", "comercial", "atend"))):
        if any(p in a for p in palavras):
            return chave
    return ""


def roteiro(area: str, nivel: str, semente: int | None = None) -> list[str]:
    """7 perguntas: abertura, técnicas da área e comportamentais (pura com semente)."""
    r = random.Random(semente)
    tec = TECNICAS.get(area_tecnica(area), [])
    perguntas = [COMPORTAMENTAIS[0]]
    perguntas += r.sample(tec, min(len(tec), 3 if nivel in ("pleno", "senior", "sênior") else 2))
    perguntas += r.sample(COMPORTAMENTAIS[1:], 7 - len(perguntas))
    return perguntas[:7]


def vicios(texto: str) -> dict[str, int]:
    t = f" {texto.lower()} "
    achados = {}
    for v in VICIOS:
        n = len(re.findall(rf"(?<!\w){re.escape(v)}(?!\w)", t))
        if n:
            achados[v] = n
    return achados


def feedback_local(respostas: list[dict]) -> dict:
    """Sem IA: tamanho das respostas e vícios de linguagem (pura)."""
    if not respostas:
        return {"nota": 0, "pontos": ["Nenhuma resposta registrada."]}
    palavras = [len(r["resposta"].split()) for r in respostas]
    curtas = sum(1 for p in palavras if p < 20)
    total_vicios: dict[str, int] = {}
    for r in respostas:
        for k, v in vicios(r["resposta"]).items():
            total_vicios[k] = total_vicios.get(k, 0) + v
    pontos = []
    if curtas:
        pontos.append(f"{curtas} resposta(s) curtas demais: use o método STAR (situação, tarefa, ação, resultado).")
    if total_vicios:
        pontos.append("Vícios de fala: " + ", ".join(f"'{k}' {v}×" for k, v in sorted(total_vicios.items(), key=lambda x: -x[1])[:4]))
    nota = max(3, min(10, 8 - curtas - sum(total_vicios.values()) // 5))
    if not pontos:
        pontos.append("Respostas com bom tamanho e sem vícios marcantes.")
    return {"nota": nota, "pontos": pontos}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "comecar").lower()
    try:
        e = ler_json(_ARQ, {}) or {}
        if acao == "comecar":
            area = str(p.get("area") or "geral").strip()
            nivel = str(p.get("nivel") or "junior").lower()
            e = {"area": area, "nivel": nivel, "perguntas": roteiro(area, nivel, int(time.time())), "respostas": [],
                 "inicio": time.time()}
            gravar_json(_ARQ, e)
            return (f"[ENTREVISTA] Você é um recrutador educado entrevistando para {area} ({nivel}). Apresente-se em uma "
                    f"frase e faça SÓ esta pergunta: \"{e['perguntas'][0]}\". Depois que o usuário responder, chame "
                    "entrevista action='responder' com a resposta dele.")
        if not e.get("perguntas"):
            return "Não há entrevista em andamento. Diga 'simula uma entrevista para …'."
        if acao == "responder":
            i = len(e["respostas"])
            if i < len(e["perguntas"]):
                e["respostas"].append({"pergunta": e["perguntas"][i], "resposta": str(p.get("resposta") or "")})
                gravar_json(_ARQ, e)
            if len(e["respostas"]) < len(e["perguntas"]):
                prox = e["perguntas"][len(e["respostas"])]
                return (f"[ENTREVISTA] Comente a resposta em no máximo 1 frase neutra (sem dar nota) e faça a pergunta "
                        f"{len(e['respostas']) + 1} de {len(e['perguntas'])}: \"{prox}\".")
            acao = "terminar"
        if acao == "terminar":
            from plugins import _ia
            fb = feedback_local(e["respostas"])
            texto_ia = ""
            if _ia.disponivel() and e["respostas"]:
                texto_ia = _ia.perguntar(
                    f"Você é um recrutador experiente. Dê o feedback desta entrevista para {e['area']} ({e['nivel']}): 3 pontos "
                    "fortes, 3 pontos a melhorar com exemplos de como responder melhor, e uma nota de 0 a 10. Português do "
                    "Brasil, direto e gentil.\n\n" + "\n\n".join(f"P: {r['pergunta']}\nR: {r['resposta']}" for r in e["respostas"]),
                    True, 90) or ""
            mostrar(player, f"FEEDBACK DA ENTREVISTA — {e['area']}", (texto_ia + "\n\n" if texto_ia else "")
                    + f"Nota (fala): {fb['nota']}/10\n" + "\n".join(f"• {x}" for x in fb["pontos"]) + "\n\n"
                    + "\n\n".join(f"P: {r['pergunta']}\nR: {r['resposta']}" for r in e["respostas"]))
            e["perguntas"] = []
            gravar_json(_ARQ, e)
            return ("[ENTREVISTA ENCERRADA] Agradeça e dê o feedback falado em até 5 frases: "
                    + (texto_ia[:1500] if texto_ia else f"nota {fb['nota']}/10; " + " ".join(fb["pontos"]))
                    + " O feedback completo está no painel.")
        return "Ações: comecar, responder, terminar."
    except Exception as ex:
        return f"A entrevista falhou: {ex}"
