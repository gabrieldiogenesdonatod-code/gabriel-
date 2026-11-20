"""
Estudos (3.2): o JARVIS vira professor — com QUADRO, aula, exercícios, gráfico e controle do tempo.

    "Jarvis, vamos estudar equação do 2º grau"         → abre o quadro e começa a sessão
    "Jarvis, explica Bhaskara no quadro"               → aula montada no quadro: passos, fórmula, exemplo
    "Jarvis, escreve no quadro a fórmula de Bhaskara"   (o JARVIS também escreve sozinho enquanto fala)
    "Jarvis, desenha o gráfico de x² - 3x + 2"          → gráfico de verdade, de -10 a 10 (ou o intervalo que pedir)
    "Jarvis, me passa 5 exercícios disso"               → perguntas no quadro, resposta escondida
    "Jarvis, mostra a resposta da 2"                    "Jarvis, limpa o quadro" / "página nova"
    "Jarvis, estuda comigo 25 minutos"                  → usa o plugin pomodoro; o tempo aparece no quadro
    "Jarvis, terminei de estudar"                        → salva o quadro, marca as revisões (revisão espaçada)
    "Jarvis, quanto eu estudei essa semana?"

O quadro abre no navegador (http://127.0.0.1:8770 — só no seu aparelho). Lá você desenha por cima,
troca lousa ↔ quadro branco e salva em Documentos/JARVIS/Estudos.
Prova simulada com correção e desempenho continua no plugin `clone_estudo`.
Aula e exercícios usam o Gemini; sem chave, o JARVIS escreve no quadro pela conversa.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from plugins import _quadro as Q
from plugins._lote2 import P, carregar, guardar, num1, rodar

PLUGIN = P("estudos", "Study system with a live whiteboard: open the board, write formulas/steps/tables/graphs on it, generate a lesson "
                      "or exercises, study timer, end session, weekly study time.",
           "estudar | quadro | escrever | explicar | grafico | exercicios | resposta | limpar | pagina | salvar | encerrar | semana",
           "Whiteboard teaching. estudar: tema, materia, minutos (optional, starts a pomodoro). quadro: open the board. "
           "escrever: tipo (titulo|texto|formula|passos|lista|codigo|tabela|destaque), conteudo (steps/list separated by ';', table "
           "rows by ';' and cells by '|') — USE THIS WHILE EXPLAINING so the user sees it. explicar: tema (builds a full lesson on "
           "the board). grafico: funcao (e.g. 'x^2-3x+2'), de, ate. exercicios: tema, quantidade. resposta: numero (or empty = all). "
           "limpar. pagina: titulo (new page). salvar. encerrar (saves board, schedules reviews). semana: study time this week.",
           "tema materia minutos tipo conteudo funcao de ate quantidade numero titulo")


def _sessoes() -> dict:
    return carregar("estudos", {"atual": None, "historico": []})


def _abrir(pl=None) -> str:
    url = Q.iniciar_servidor()
    try:
        from plugins._comum import abrir_no_sistema
        abrir_no_sistema(url)
    except Exception:
        pass
    return url


def _estudar(p, pl):
    tema = str(p.get("tema") or p.get("materia") or "").strip()
    if not tema:
        return "Qual assunto vamos estudar?"
    d = _sessoes()
    d["atual"] = {"tema": tema, "materia": str(p.get("materia") or ""), "inicio": time.time()}
    guardar("estudos", d)
    Q.nova_pagina(tema)
    Q.escrever("titulo", tema)
    url = _abrir(pl)
    extra = ""
    minutos = num1(p, "minutos", 0)
    if minutos:
        try:
            from plugins import pomodoro
            pomodoro.run({"action": "iniciar", "minutos": str(int(minutos))}, pl)
            extra = f" Pomodoro de {int(minutos)} minutos ligado; o tempo aparece no canto do quadro."
        except Exception:
            extra = ""
    return (f"Sessão de estudo de '{tema}' começou. O quadro está aberto em {url}.{extra} "
            "Explique em partes e use a ação 'escrever' para pôr no quadro cada fórmula, passo ou exemplo.")


def _quadro(p, pl):
    return f"Quadro aberto em {_abrir(pl)}."


def _escrever(p, pl):
    conteudo = p.get("conteudo")
    if not conteudo:
        return "O que escrevo no quadro?"
    tipo = str(p.get("tipo") or "texto").strip().lower()
    Q.iniciar_servidor()
    b = Q.escrever(tipo, conteudo)
    return f"Escrevi no quadro ({b['tipo']})."


def _grafico(p, pl):
    funcao = str(p.get("funcao") or p.get("conteudo") or "").strip()
    if not funcao:
        return "Qual função eu desenho? (ex.: x^2 - 3x + 2)"
    de, ate = num1(p, "de", -10), num1(p, "ate", 10)
    if de == ate:
        de, ate = -10, 10
    try:
        b = Q.grafico(funcao, de, ate)
    except (SyntaxError, ValueError) as e:
        return f"Não consegui entender a função '{funcao}': {e}."
    validos = [y for _x, y in b["pontos"] if y is not None]
    Q.iniciar_servidor()
    if not validos:
        return f"A função {funcao} não tem valores reais entre {de:g} e {ate:g}."
    return f"Desenhei o gráfico de y = {funcao} de {de:g} a {ate:g} (y vai de {min(validos):.2f} a {max(validos):.2f})."


def _ia(prompt: str):
    try:
        from core import gemini
        return gemini.as_json(prompt, tier=gemini.SMART, default=None)
    except Exception:
        return None


def aula_em_blocos(dados: dict) -> list[dict]:
    """JSON da IA → blocos válidos do quadro (descarta o que vier errado). Pura."""
    out = []
    for b in (dados or {}).get("blocos", [])[:14]:
        if not isinstance(b, dict):
            continue
        tipo = str(b.get("tipo") or "texto").lower()
        if tipo == "exemplo":
            tipo = "destaque"
        if tipo == "grafico" and b.get("funcao"):
            out.append({"tipo": "grafico", "funcao": str(b["funcao"]), "de": b.get("de", -10), "ate": b.get("ate", 10)})
        elif tipo in Q.TIPOS and tipo not in ("grafico", "pergunta") and b.get("conteudo"):
            out.append({"tipo": tipo, "conteudo": b["conteudo"]})
    return out


def _explicar(p, pl):
    tema = str(p.get("tema") or p.get("conteudo") or ((_sessoes().get("atual") or {}).get("tema")) or "").strip()
    if not tema:
        return "Explico o quê?"
    dados = _ia(f"Monte uma aula curta e clara, em português do Brasil, sobre: {tema}. Público: estudante (curso técnico/ensino médio). "
                "Responda SÓ JSON: {\"titulo\": str, \"blocos\": [{\"tipo\": \"texto|formula|passos|lista|exemplo|destaque|tabela|codigo|grafico\", "
                "\"conteudo\": str ou lista, \"funcao\": \"só para grafico, ex. x^2-1\", \"de\": -5, \"ate\": 5}]}. "
                "Entre 5 e 10 blocos: ideia em 2 frases, fórmula(s), passo a passo, um exemplo resolvido e um resumo. "
                "Passos e listas como lista de frases curtas. Tabela como lista de linhas 'a|b|c'.")
    blocos = aula_em_blocos(dados or {})
    Q.iniciar_servidor()
    if not blocos:
        Q.nova_pagina(tema)
        Q.escrever("titulo", tema)
        return (f"Sem a IA para montar a aula pronta: abri uma página '{tema}' no quadro. Explique você, em partes, usando a ação "
                "'escrever' (fórmulas, passos, exemplo) e 'grafico' quando ajudar.")
    Q.nova_pagina(str((dados or {}).get("titulo") or tema))
    Q.escrever("titulo", str((dados or {}).get("titulo") or tema))
    for b in blocos:
        try:
            if b["tipo"] == "grafico":
                Q.grafico(b["funcao"], float(b["de"]), float(b["ate"]))
            else:
                conteudo = b["conteudo"]
                if b["tipo"] == "tabela" and isinstance(conteudo, list):
                    conteudo = ";".join(conteudo) if all(isinstance(x, str) for x in conteudo) else conteudo
                Q.escrever(b["tipo"], conteudo)
        except Exception:
            continue
    _abrir(pl)
    return (f"A aula de '{tema}' está no quadro ({len(blocos)} partes). Explique em voz alta, parte por parte, de forma curta, "
            "e pergunte se ficou claro antes de seguir.")


def _exercicios(p, pl):
    tema = str(p.get("tema") or ((_sessoes().get("atual") or {}).get("tema")) or "").strip()
    if not tema:
        return "Exercícios de quê?"
    n = int(min(10, max(1, num1(p, "quantidade", 5))))
    dados = _ia(f"Crie {n} exercícios em português do Brasil sobre {tema}, do mais fácil ao mais difícil, com resposta curta. "
                "Responda SÓ JSON: {\"perguntas\": [{\"pergunta\": str, \"resposta\": str}]}.")
    perguntas = [q for q in (dados or {}).get("perguntas", []) if isinstance(q, dict) and q.get("pergunta")][:n]
    if not perguntas:
        return "Sem a IA agora: crie você mesmo os exercícios e escreva no quadro com a ação 'escrever' (tipo texto)."
    Q.nova_pagina(f"Exercícios — {tema}")
    Q.escrever("titulo", f"Exercícios — {tema}")
    for q in perguntas:
        Q.escrever("pergunta", str(q["pergunta"]), resposta=str(q.get("resposta") or ""))
    _abrir(pl)
    return (f"{len(perguntas)} exercícios no quadro, com as respostas escondidas. Leia o primeiro em voz alta e espere a resposta; "
            "para conferir use a ação 'resposta' com o número.")


def _resposta(p, pl):
    n = int(num1(p, "numero", 0)) or None
    q = Q.revelar(n)
    return (f"Revelei {q} resposta(s) no quadro." if q else "Não há pergunta com esse número no quadro.")


def _limpar(p, pl):
    Q.limpar()
    return "Quadro limpo."


def _pagina(p, pl):
    pg = Q.nova_pagina(str(p.get("titulo") or p.get("tema") or ""))
    if p.get("titulo") or p.get("tema"):
        Q.escrever("titulo", pg["titulo"])
    return f"Página nova: {pg['titulo']}."


def _salvar(p, pl):
    return f"Quadro salvo em {Q.salvar_html()}. (O botão Salvar do quadro guarda também o que você desenhou.)"


def _encerrar(p, pl):
    d = _sessoes()
    s = d.get("atual")
    if not s:
        return "Não há sessão de estudo aberta."
    minutos = max(1, round((time.time() - s["inicio"]) / 60))
    arq = Q.salvar_html(nome=s["tema"])
    d["historico"].append({"tema": s["tema"], "materia": s.get("materia", ""), "dia": date.today().isoformat(), "minutos": minutos})
    d["historico"] = d["historico"][-500:]
    d["atual"] = None
    guardar("estudos", d)
    revisao = ""
    try:
        from plugins import revisao_espacada
        revisao_espacada.run({"action": "estudei", "tema": s["tema"], "materia": s.get("materia", "")})
        revisao = " Marquei as revisões (amanhã, em 3, 7, 15, 30 e 60 dias)."
    except Exception:
        pass
    return f"Sessão de '{s['tema']}' encerrada: {minutos} min. Quadro salvo em {arq}.{revisao}"


def semana(historico: list[dict], hoje: date | None = None) -> dict:
    """Minutos por assunto nos últimos 7 dias e dias seguidos estudando. Pura."""
    hoje = hoje or date.today()
    inicio = (hoje - timedelta(days=6)).isoformat()
    por: dict[str, int] = {}
    dias = set()
    for h in historico:
        dias.add(h["dia"])
        if h["dia"] >= inicio:
            por[h["tema"]] = por.get(h["tema"], 0) + int(h["minutos"])
    seq, d = 0, hoje
    while d.isoformat() in dias:
        seq, d = seq + 1, d - timedelta(days=1)
    return {"por_tema": dict(sorted(por.items(), key=lambda x: -x[1])), "total": sum(por.values()), "sequencia": seq}


def _semana(p, pl):
    s = semana(_sessoes()["historico"])
    if not s["total"]:
        return "Nenhuma sessão de estudo nos últimos 7 dias."
    temas = ", ".join(f"{t} ({m} min)" for t, m in list(s["por_tema"].items())[:5])
    return (f"Nos últimos 7 dias você estudou {s['total'] // 60} h {s['total'] % 60} min: {temas}."
            + (f" Sequência: {s['sequencia']} dia(s) seguidos." if s["sequencia"] > 1 else ""))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estudar": _estudar, "quadro": _quadro, "escrever": _escrever, "explicar": _explicar,
                              "grafico": _grafico, "exercicios": _exercicios, "resposta": _resposta, "limpar": _limpar,
                              "pagina": _pagina, "salvar": _salvar, "encerrar": _encerrar, "semana": _semana}, player, "Estudos")
