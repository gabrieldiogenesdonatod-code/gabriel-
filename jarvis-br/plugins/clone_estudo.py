"""
Clone de estudo (fork PT-BR 2.11).

Monta provas simuladas de qualquer matéria, corrige, guarda seu desempenho e aponta
onde você erra mais — pra estudar pro SENAI, pra prova, pro que for.

    "Jarvis, faz uma prova de 5 questões de lógica de programação."
    "Jarvis, questão 1 é a letra B."     (ou "responde B")   → ele corrige e segue
    "Jarvis, como tá meu desempenho?"    "Jarvis, onde eu erro mais?"

As questões vêm do cérebro (Gemini). O desempenho por matéria fica em
memory/estudo.json, então ele sabe no que você precisa treinar mais.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "clone_estudo",
    "brief": "Study clone: makes practice exams, grades them, tracks your score per subject and your weak spots.",
    "description": (
        "Makes simulated exams and tracks study performance. action: 'prova' (materia + optional quantas = how many "
        "questions → generates a quiz with the brain), 'responder' (questao number + letra A-E → grades it), "
        "'gabarito' (reveal current quiz answers), 'desempenho' (score per subject, weak spots), 'materias' (list). "
        "Use for 'faz uma prova de X', 'questão N é a letra Y'/'responde Y', 'como está meu desempenho', 'onde eu "
        "erro mais'. Questions need Gemini; performance is saved per subject."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "prova | responder | gabarito | desempenho | materias"},
            "materia": {"type": "STRING"}, "quantas": {"type": "NUMBER"},
            "questao": {"type": "NUMBER"}, "letra": {"type": "STRING", "description": "A-E"},
        },
    },
}

ARQ = MEMORIA / "estudo.json"            # o carregador dos testes troca este caminho
_lock = threading.RLock()
MAX_Q = 10


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── pura ───────────────────────────────────────────────────────────────────────
def ler_letra(valor) -> str:
    """'B', 'letra b', 'a segunda', 'alternativa C' → 'B' (puro). '' se não achar."""
    t = dobrar(valor)
    ordinais = {"primeir": "A", "segund": "B", "terceir": "C", "quart": "D", "quint": "E"}
    for k, v in ordinais.items():          # "a segunda" é B, não o artigo "a"
        if k in t:
            return v
    m = re.search(r"\b([a-e])\b", t)
    return m.group(1).upper() if m else ""


def corrigir(questao: dict, letra: str) -> bool:
    return bool(letra) and letra.upper() == str(questao.get("correta") or "").upper()


def formatar_questao(q: dict, numero: int) -> str:
    linhas = [f"{numero}. {q.get('enunciado', '')}"]
    for letra, texto in zip("ABCDE", q.get("alternativas", [])):
        linhas.append(f"   {letra}) {texto}")
    return "\n".join(linhas)


def resumo_desempenho(materias: dict) -> str:
    if not materias:
        return "Você ainda não respondeu nenhuma questão. Diga 'faz uma prova de ...' pra começar."
    linhas, piores = [], []
    for nome, d in sorted(materias.items(), key=lambda x: _taxa(x[1])):
        total = d.get("acertos", 0) + d.get("erros", 0)
        if not total:
            continue
        taxa = round(100 * d["acertos"] / total)
        linhas.append(f"{nome}: {d['acertos']}/{total} ({taxa}%)")
        if taxa < 60:
            piores.append(nome)
    texto = "\n".join(linhas)
    if piores:
        texto += "\n\nTreinar mais: " + ", ".join(piores[:3])
    return texto


def _taxa(d: dict) -> float:
    total = d.get("acertos", 0) + d.get("erros", 0)
    return d.get("acertos", 0) / total if total else 1.0


# ── dados ──────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("materias", {})         # {materia: {"acertos", "erros"}}
    d.setdefault("prova", None)          # prova atual {"materia", "questoes":[...], "respondidas": {n: letra}}
    return d


def _gravar(d: dict) -> None:
    with _lock:
        gravar_json(ARQ, d)


def _registrar_resultado(d: dict, materia: str, acertou: bool) -> None:
    m = d["materias"].setdefault(dobrar(materia) or "geral", {"acertos": 0, "erros": 0, "nome": materia})
    m["nome"] = materia
    m["acertos" if acertou else "erros"] += 1


# ── ações ──────────────────────────────────────────────────────────────────────
def fazer_prova(materia: str, quantas) -> str:
    materia = " ".join(str(materia or "").split()).strip() or "conhecimentos gerais"
    try:
        n = int(float(quantas or 5))
    except (ValueError, TypeError):
        n = 5
    n = max(1, min(MAX_Q, n))
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return "Pra montar a prova eu preciso do cérebro (Gemini) ligado — coloque a chave em ⚙."
        j = _ia.perguntar_json(
            f"Monte uma prova de {n} questões de múltipla escolha sobre \"{materia}\", em português do Brasil, nível "
            "médio. Responda {\"questoes\": [{\"enunciado\": \"...\", \"alternativas\": [\"5 opções\"], "
            "\"correta\": \"A\"}]}. Use 5 alternativas (A-E) e varie a letra correta.", inteligente=True, segundos=45)
    except Exception as e:
        return f"Não consegui montar a prova agora ({e})."
    questoes = (j or {}).get("questoes") if isinstance(j, dict) else None
    if not questoes:
        return "O cérebro não devolveu a prova direito. Tenta de novo, ou com outra matéria."
    questoes = [q for q in questoes if q.get("enunciado") and q.get("alternativas")][:n]
    with _lock:
        d = dados()
        d["prova"] = {"materia": materia, "questoes": questoes, "respondidas": {}, "criada": time.time()}
        _gravar(d)
    primeira = formatar_questao(questoes[0], 1)
    mostrar(None, f"PROVA · {materia}", "\n\n".join(formatar_questao(q, i + 1) for i, q in enumerate(questoes)))
    return (f"Prova de {len(questoes)} questões de {materia} na tela. Vou corrigindo conforme você responde. "
            f"Comece pela 1:\n\n{primeira}\n\nResponda com a letra (ex.: 'questão 1 é a B').")


def responder(questao, letra: str) -> str:
    l = ler_letra(letra)
    with _lock:
        d = dados()
        prova = d.get("prova")
        if not prova:
            return "Não tem prova aberta agora. Diga 'faz uma prova de ...'."
        qs = prova["questoes"]
        try:
            n = int(float(questao)) if questao not in (None, "") else len(prova["respondidas"]) + 1
        except (ValueError, TypeError):
            n = len(prova["respondidas"]) + 1
        if not (1 <= n <= len(qs)):
            return f"Essa prova tem {len(qs)} questões. Qual número?"
        if not l:
            return "Qual a letra? (A a E)"
        q = qs[n - 1]
        acertou = corrigir(q, l)
        prova["respondidas"][str(n)] = l
        _registrar_resultado(d, prova["materia"], acertou)
        faltam = [i + 1 for i in range(len(qs)) if str(i + 1) not in prova["respondidas"]]
        if not faltam:
            total = len(qs)
            acertos = sum(1 for i, qq in enumerate(qs) if corrigir(qq, prova["respondidas"].get(str(i + 1), "")))
            d["prova"] = None
            _gravar(d)
            fim = f" Prova encerrada: {acertos}/{total}."
        else:
            _gravar(d)
            fim = f" Falta(m) a(s) questão(ões) {', '.join(map(str, faltam))}."
    correta = str(q.get("correta") or "?").upper()
    veredito = "Acertou! ✅" if acertou else f"Quase — era a letra {correta}."
    return f"Questão {n}: {veredito}{fim} Comente em 1 frase curta por que a {correta} é a certa."


def gabarito() -> str:
    with _lock:
        d = dados()
        prova = d.get("prova")
    if not prova:
        return "Não tem prova aberta."
    linhas = [f"{i + 1}: {q.get('correta', '?')}" for i, q in enumerate(prova["questoes"])]
    return "Gabarito da prova de " + prova["materia"] + " — " + ", ".join(linhas)


def desempenho(player=None) -> str:
    with _lock:
        materias = dados()["materias"]
    texto = resumo_desempenho(materias)
    mostrar(player, "DESEMPENHO NOS ESTUDOS", texto)
    return texto + ("\n\nResuma em 2 frases e puxe pra treinar o ponto fraco." if materias else "")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "desempenho").strip()
    try:
        if acao in ("prova", "simulado", "questoes", "teste", "fazer_prova"):
            return fazer_prova(str(p.get("materia") or ""), p.get("quantas"))
        if acao in ("responder", "responde", "resposta", "alternativa"):
            return responder(p.get("questao"), str(p.get("letra") or p.get("resposta") or ""))
        if acao in ("gabarito", "respostas"):
            return gabarito()
        if acao in ("desempenho", "nota", "pontuacao", "onde_erro"):
            return desempenho(player)
        if acao in ("materias", "lista"):
            with _lock:
                ms = dados()["materias"]
            return ("Matérias que você treinou: " + ", ".join(m.get("nome", k) for k, m in ms.items())
                    if ms else "Você ainda não treinou nenhuma matéria.")
        return desempenho(player)
    except Exception as e:
        return f"O clone de estudo falhou: {e}"
