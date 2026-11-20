"""
Conselho do multiverso (2.21): numa decisão difícil, o JARVIS se divide em cinco versões de si
mesmo, de cinco universos diferentes. Elas discutem, discordam, respondem umas às outras e no fim
VOTAM. Você assiste à reunião de cinco JARVIS sobre a sua vida.

    "Jarvis, convoca o conselho do multiverso: abro uma segunda loja ou invisto na online?"
    "Jarvis, o que o conselho decidiu da última vez?"

Os cinco: o Stark (ousado, inventor), o Empresário (números e risco), o Sábio (calma, longo prazo,
família), o Rapper (coragem, verdade nua, rima) e o Cientista (evidência, teste pequeno antes).
(Não confundir com o plugin `conselho`, que divide uma TAREFA entre especialistas.)
"""

from __future__ import annotations

import json
import time

from plugins._lote2 import P, carregar, guardar, mostrar, rodar

PLUGIN = P("multiverso", "Multiverse council: for a hard life decision, five JARVIS versions (Stark, Businessman, Sage, Rapper, Scientist) "
           "debate, rebut each other and vote; shows the debate and the verdict.",
           "convocar | ultima | historico | membros",
           "convocar: pergunta = the decision (with context: money, time, what matters). ultima: last council. membros: who sits on it.",
           "pergunta")

MEMBROS = [("Stark", "inventor ousado e confiante: prefere construir algo novo, aceita risco calculado, pensa em tecnologia e escala"),
           ("Empresário", "frio com números: custo, retorno, fluxo de caixa, pior cenário; desconfia de empolgação"),
           ("Sábio", "calmo, pensa em dez anos e na família; pergunta o que realmente importa e o que se perde"),
           ("Rapper", "rapper geek brasileiro: coragem, verdade sem filtro, fala com rima e punchline curta, sem palavrão"),
           ("Cientista", "quer evidência: propõe um teste pequeno e barato antes de apostar tudo; diz o que ainda não se sabe")]
VOTOS = ("sim", "não", "testar antes")


def montar_prompt(pergunta: str, contexto: str = "") -> str:
    quem = "\n".join(f"- {n}: {d}" for n, d in MEMBROS)
    return (
        "Simule um conselho de cinco versões do assistente J.A.R.V.I.S, vindas de universos diferentes, discutindo a "
        f"decisão do usuário. Membros:\n{quem}\n\n"
        f"Decisão: {pergunta}\n" + (f"Contexto do usuário: {contexto}\n" if contexto else "") +
        "\nRegras: português do Brasil; cada fala com no máximo 2 frases; eles DISCORDAM de verdade e citam uns aos outros "
        "na segunda rodada; nada de conselho perigoso, ilegal ou médico/jurídico definitivo; seja concreto para a vida real "
        "de quem pergunta. Cada um vota 'sim', 'não' ou 'testar antes'.\n"
        'Responda SÓ com JSON: {"rodada1": [{"quem": "Stark", "fala": "..."}, ...5], '
        '"rodada2": [{"quem": "Empresário", "responde_a": "Stark", "fala": "..."}, ...3], '
        '"votos": [{"quem": "Stark", "voto": "sim", "porque": "uma frase"}, ...5], '
        '"veredito": "uma frase com a decisão do conselho", "primeiro_passo": "uma ação pequena para amanhã"}'
    )


def apurar(votos: list[dict]) -> tuple[str, dict[str, int]]:
    """Contagem e resultado ('sim', 'não', 'testar antes' ou 'empate'). Pura."""
    cont = {v: 0 for v in VOTOS}
    for x in votos:
        v = str(x.get("voto", "")).lower().strip()
        v = "não" if v.startswith(("nao", "não")) else "testar antes" if v.startswith("test") else "sim" if v.startswith("sim") else ""
        if v:
            cont[v] += 1
    top = max(cont.values())
    vencedores = [v for v, n in cont.items() if n == top]
    return (vencedores[0] if len(vencedores) == 1 and top else "empate"), cont


def roteiro(d: dict) -> str:
    """Texto da reunião para a tela."""
    linhas = ["RODADA 1"] + [f"{x.get('quem')}: {x.get('fala')}" for x in d.get("rodada1", [])]
    linhas += ["", "RODADA 2 (respostas)"] + [f"{x.get('quem')} → {x.get('responde_a')}: {x.get('fala')}" for x in d.get("rodada2", [])]
    resultado, cont = apurar(d.get("votos", []))
    linhas += ["", "VOTAÇÃO"] + [f"{x.get('quem')}: {x.get('voto')} — {x.get('porque')}" for x in d.get("votos", [])]
    linhas += ["", f"Placar: sim {cont['sim']} × não {cont['não']} × testar antes {cont['testar antes']} → {resultado.upper()}",
               f"Veredito: {d.get('veredito', '')}", f"Primeiro passo: {d.get('primeiro_passo', '')}"]
    return "\n".join(linhas)


def _contexto() -> str:
    try:
        from memory.memory_manager import load_memory
        m = load_memory() or {}
        return json.dumps(m, ensure_ascii=False)[:1200]
    except Exception:
        return ""


def _go(p, pl):
    a = p["action"]
    if a == "membros":
        return "O conselho: " + "; ".join(f"{n} ({d.split(':')[0]})" for n, d in MEMBROS) + "."
    hist = carregar("multiverso", [])
    if a in ("ultima", "historico"):
        if not hist:
            return "O conselho ainda não se reuniu. Diga 'convoca o conselho do multiverso' e a sua dúvida."
        if a == "historico":
            return "\n".join(f"{h['quando'][:10]}: {h['pergunta'][:60]} → {h['resultado']}" for h in hist[-10:])
        mostrar(pl, "CONSELHO DO MULTIVERSO", roteiro(hist[-1]["debate"]))
        return f"Última reunião: '{hist[-1]['pergunta']}'. Resultado: {hist[-1]['resultado']}. {hist[-1]['debate'].get('veredito', '')}"
    pergunta = str(p.get("pergunta") or "").strip()
    if len(pergunta) < 8:
        return "Qual é a decisão? Conte com um pouco de contexto (dinheiro, tempo, o que importa para você)."
    from core import gemini
    d = gemini.as_json(montar_prompt(pergunta, _contexto()), tier=gemini.SMART, default=None)
    if not isinstance(d, dict) or not d.get("votos"):
        return "O multiverso não respondeu agora (preciso da chave do Gemini e de internet). Tente de novo em instantes."
    resultado, cont = apurar(d["votos"])
    hist.append({"quando": time.strftime("%Y-%m-%d %H:%M"), "pergunta": pergunta, "resultado": resultado, "debate": d})
    guardar("multiverso", hist[-50:])
    mostrar(pl, "CONSELHO DO MULTIVERSO", roteiro(d))
    destaque = next((x for x in d.get("rodada1", []) if x.get("quem") == "Rapper"), {}).get("fala", "")
    return (f"O conselho se reuniu e votou: sim {cont['sim']}, não {cont['não']}, testar antes {cont['testar antes']}. "
            f"Veredito: {d.get('veredito', '')} Primeiro passo: {d.get('primeiro_passo', '')} "
            + (f"O Rapper mandou: {destaque} " if destaque else "") +
            "[Narre isso como se tivesse assistido à reunião de cinco versões suas; o debate completo está na tela.]")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("convocar ultima historico membros".split(), _go), player, "")
