"""
Narrador da vida (fork PT-BR 1.6).

O JARVIS descreve o seu dia como um documentário de natureza: "Aqui vemos o
programador em seu habitat natural…" — a partir do que realmente aconteceu
(linha do tempo, projetos, commits, jogos, conquistas, clima), com um som de
floresta baixinho ao fundo.

    "Jarvis, narra o meu dia"          "Jarvis, narra minha semana como documentário"
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from plugins._comum import MEMORIA, ler_json

PLUGIN = {
    "name": "narrador",
    "brief": "Narrates the user's day/week like a nature documentary, from real timeline data, with ambient sound.",
    "description": (
        "Life narrator: narrates the user's day (or periodo = 'semana') like a nature documentary, using real data "
        "(timeline activities, projects, commits, games, achievements). Read the narration with a dramatic, calm voice."
    ),
    "parameters": {"type": "OBJECT", "properties": {"periodo": {"type": "STRING"}}, "required": []},
}


def fatos(desde: float) -> list[str]:
    linhas = []
    try:
        from plugins.linha_do_tempo import resumo
        r = resumo(desde)
        if r["ativo_s"]:
            linhas.append(f"{r['ativo_s'] / 3600:.1f} horas no computador")
            linhas += [f"{k}: {v / 60:.0f} min" for k, v in r["atividades"][:5]]
            if r["projetos"]:
                linhas.append("projeto principal: " + r["projetos"][0][0])
        if r["ausente_s"] > 1800:
            linhas.append(f"{r['ausente_s'] / 3600:.1f} h longe do PC")
    except Exception:
        pass
    try:
        from plugins import _projetos
        n = sum(len(_projetos.commits(repo, desde)) for repo in _projetos.repos())
        if n:
            linhas.append(f"{n} commits")
    except Exception:
        pass
    jogos = {}
    for s in ler_json(MEMORIA / "jogos.json", []) or []:
        if s["inicio"] >= desde:
            jogos[s["jogo"]] = jogos.get(s["jogo"], 0) + (s["fim"] - s["inicio"]) / 60
    linhas += [f"jogou {j} por {m:.0f} min" for j, m in jogos.items()]
    g = ler_json(MEMORIA / "gamificacao.json", {}) or {}
    xp = sum(h["xp"] for h in g.get("historico", []) if h["ts"] >= desde)
    if xp:
        linhas.append(f"ganhou {xp} XP")
    return linhas


def run(parameters: dict, player=None, session_memory=None) -> str:
    semana = "seman" in str((parameters or {}).get("periodo") or "")
    agora = datetime.now()
    desde = (agora - timedelta(days=7) if semana else datetime.combine(agora.date(), datetime.min.time())).timestamp()
    try:
        dados = fatos(desde)
        if not dados:
            return "Ainda não tenho registros suficientes para narrar (a linha do tempo começa quando o JARVIS fica aberto)."
        try:
            from plugins import _som
            laco = _som.Laco(_som.ambiente("floresta", 12, semente=7), volume=0.12)
            laco.tocar()
            threading.Thread(target=lambda: (time.sleep(75), laco.parar()), daemon=True).start()
        except Exception:
            pass
        periodo = "desta semana" if semana else "de hoje"
        from plugins import _ia
        if _ia.disponivel():
            texto = _ia.perguntar(
                "Escreva a narração de um documentário de natureza (estilo David Attenborough, em português do Brasil, "
                "terceira pessoa, bem-humorada e carinhosa) sobre o dia " + periodo + " de um programador brasileiro, "
                "usando SÓ estes fatos: " + "; ".join(dados) + ". 6 a 8 frases, sem markdown.", False, 40)
            if texto:
                return f"[NARRADOR] Leia com voz calma e dramática de documentário: {texto}"
        return ("[NARRADOR] Narre como um documentário de natureza, voz calma e dramática, em 5 frases, usando só estes "
                f"fatos {periodo}: " + "; ".join(dados) + ".")
    except Exception as e:
        return f"O narrador falhou: {e}"
