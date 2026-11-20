"""
Torneio entre amigos (fork PT-BR 2.17).

    "Jarvis, cria um torneio de Roblox com João, Pedro, Ana e eu"     → chaveamento sorteado
    "Jarvis, o João ganhou do Pedro"                                  → avança no chaveamento
    "Jarvis, como está o torneio?"
    "Jarvis, placar: João 3 pontos, Ana 5 pontos"                     → modo pontos corridos

Mata-mata (com folga automática quando o número não é potência de 2) ou pontos
corridos. Fica em memory/torneio.json; o campeão é anunciado com festa.
"""

from __future__ import annotations

import random

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "torneio",
    "brief": "Tournament with friends: knockout bracket or points table, results by voice, champion announcement.",
    "description": (
        "Tournament. action='criar' with jogadores (comma separated), optional jogo and tipo (mata_mata | pontos). "
        "action='resultado' with vencedor (and perdedor) for knockout. action='pontos' with placar 'Nome: n; Nome: n' "
        "adds points. action='status'. action='encerrar'."
    ),
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING"}, "jogadores": {"type": "STRING"}, "jogo": {"type": "STRING"},
        "tipo": {"type": "STRING"}, "vencedor": {"type": "STRING"}, "perdedor": {"type": "STRING"},
        "placar": {"type": "STRING"}}, "required": ["action"]},
}

ARQ = MEMORIA / "torneio.json"


def chaveamento(jogadores: list[str], rng: random.Random | None = None) -> list[list]:
    """Primeira rodada: pares; quem sobra passa direto (None = folga) (pura)."""
    js = list(jogadores)
    (rng or random).shuffle(js)
    tam = 1
    while tam < len(js):
        tam *= 2
    js += [None] * (tam - len(js))
    return [[js[i], js[tam - 1 - i]] for i in range(tam // 2)]


def avancar(rodada: list[list], vencedores: dict) -> list[list] | None:
    """Próxima rodada quando todos os jogos têm vencedor (folga conta sozinha) (pura)."""
    ganhou = []
    for a, b in rodada:
        if b is None or a is None:
            ganhou.append(a or b)
        elif f"{a}|{b}" in vencedores:
            ganhou.append(vencedores[f"{a}|{b}"])
        else:
            return None
    if len(ganhou) == 1:
        return [[ganhou[0], "CAMPEÃO"]]
    return [[ganhou[i], ganhou[i + 1]] for i in range(0, len(ganhou), 2)]


def _desenho(t: dict) -> str:
    if t["tipo"] == "pontos":
        return "\n".join(f"{n:<15} {p:>4}" for n, p in sorted(t["pontos"].items(), key=lambda x: -x[1]))
    linhas = []
    for i, r in enumerate(t["rodadas"], 1):
        linhas.append(f"RODADA {i}")
        for a, b in r:
            v = t["vencedores"].get(f"{a}|{b}")
            linhas.append(f"  {a or 'folga'} x {b or 'folga'}" + (f"  → {v}" if v else ""))
    return "\n".join(linhas)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "status").lower()
    t = ler_json(ARQ, {}) or {}
    try:
        if a == "criar":
            js = [x.strip() for x in str(p.get("jogadores") or "").replace(" e ", ",").split(",") if x.strip()]
            if len(js) < 2:
                return "Preciso de pelo menos 2 jogadores."
            tipo = "pontos" if "pont" in str(p.get("tipo") or "").lower() else "mata_mata"
            t = {"jogo": str(p.get("jogo") or ""), "tipo": tipo, "jogadores": js, "vencedores": {},
                 "pontos": {j: 0 for j in js}, "rodadas": [chaveamento(js)] if tipo == "mata_mata" else []}
            gravar_json(ARQ, t)
            mostrar(player, f"TORNEIO {t['jogo'].upper()}", _desenho(t))
            if tipo == "pontos":
                return f"Torneio de pontos com {len(js)} jogadores criado. Me diga o placar a cada partida."
            jogos = [f"{x} contra {y}" if x and y else f"{x or y} passa direto" for x, y in t["rodadas"][0]]
            return "Chaveamento sorteado: " + "; ".join(jogos) + ". Que comecem os jogos!"
        if not t:
            return "Não tem torneio rolando. Diga 'cria um torneio com…'."
        if a == "resultado":
            v, perd = str(p.get("vencedor") or "").strip(), str(p.get("perdedor") or "").strip()
            rodada = t["rodadas"][-1]
            jogo = next((j for j in rodada if v in j and (not perd or perd in j)), None)
            if not jogo or None in jogo:
                return f"Não achei um jogo do {v} nesta rodada."
            t["vencedores"][f"{jogo[0]}|{jogo[1]}"] = v
            prox = avancar(rodada, t["vencedores"])
            msg = f"Anotado: {v} venceu."
            if prox and prox[0][1] == "CAMPEÃO":
                try:
                    from core import emocoes
                    emocoes.definir("animado", 6)
                except Exception:
                    pass
                msg += f" E temos um campeão: {prox[0][0]}! 🏆"
                t["campeao"] = prox[0][0]
            elif prox:
                t["rodadas"].append(prox)
                msg += " Próxima rodada: " + "; ".join(f"{x} x {y}" for x, y in prox) + "."
            gravar_json(ARQ, t)
            return msg
        if a == "pontos":
            for parte in str(p.get("placar") or "").split(";"):
                if ":" in parte:
                    n, v = parte.split(":", 1)
                    n = n.strip()
                    t["pontos"][n] = t["pontos"].get(n, 0) + int("".join(c for c in v if c.isdigit() or c == "-") or 0)
            gravar_json(ARQ, t)
            lider = max(t["pontos"].items(), key=lambda x: x[1])
            return f"Placar atualizado. Liderando: {lider[0]} com {lider[1]} pontos."
        if a == "encerrar":
            gravar_json(ARQ, {})
            return "Torneio encerrado."
        mostrar(player, f"TORNEIO {t.get('jogo', '').upper()}", _desenho(t))
        return f"Campeão: {t['campeao']}." if t.get("campeao") else "O chaveamento está no painel."
    except Exception as e:
        return f"O torneio falhou: {e}"
