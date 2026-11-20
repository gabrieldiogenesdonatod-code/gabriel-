"""Trava-línguas (2.19): os clássicos do folclore brasileiro para brincar, aquecer a voz antes de gravar ou desafiar a família."""
from __future__ import annotations

import random

from plugins._lote2 import P, norm, rodar

PLUGIN = P("trava_linguas", "Brazilian traditional tongue twisters: draw one by level, 3x speed challenge, list; good vocal warm-up before recording.",
           "sortear | desafio | listar", "sortear: nivel (facil|medio|dificil).", "nivel")

TRAVAS = {
    "facil": ["O rato roeu a roupa do rei de Roma.", "Casa suja, chão sujo.", "O peito do pé de Pedro é preto.",
              "Bagre branco, branco bagre.", "Sabia que o sabiá sabia assobiar?", "A aranha arranha a rã. A rã arranha a aranha."],
    "medio": ["Três pratos de trigo para três tigres tristes.", "Fala, arara loura. A arara loura falará.",
              "Larga a tia, lagartixa! Lagartixa, larga a tia!", "A vaca malhada foi molhada por outra vaca molhada e malhada.",
              "Farofa feita com muita farinha fofa faz uma fofoca feia.", "A Iara agarra e amarra a rara arara de Araraquara."],
    "dificil": ["Num ninho de mafagafos há sete mafagafinhos. Quem os desmafagafizar, bom desmafagafizador será.",
                "O tempo perguntou pro tempo quanto tempo o tempo tem. O tempo respondeu pro tempo que o tempo tem tanto tempo quanto tempo o tempo tem.",
                "Se o papa papasse papa, se o papa papasse pão, o papa tudo papava, seria um papa papão.",
                "O doce perguntou pro doce qual é o doce mais doce que o doce de batata-doce.",
                "Paulo Pereira Pinto Peixoto, pobre pintor português, pinta perfeitamente portas, paredes e pias por parco preço, patrão."],
}


def sortear(nivel: str = "", rng=random) -> str:
    n = norm(nivel)
    n = "facil" if n.startswith("fac") else "dificil" if n.startswith("dif") else "medio" if n.startswith("med") else rng.choice(list(TRAVAS))
    return rng.choice(TRAVAS[n])


def _go(p, pl):
    a = p["action"]
    if a == "listar":
        return "\n".join(f"{k}: " + " | ".join(v) for k, v in TRAVAS.items())
    t = sortear(p.get("nivel"))
    return t if a == "sortear" else f"Desafio: diga três vezes seguidas, cada vez mais rápido, sem errar: {t}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"sortear": _go, "desafio": _go, "listar": _go}, player, "Trava-línguas")
