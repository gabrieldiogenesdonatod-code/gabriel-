"""Respiração e alongamento guiados (2.18): o JARVIS conduz em voz com o tempo certo de cada fase."""
from __future__ import annotations

import threading
import time

from plugins._lote2 import P, falar_ja, rodar

PLUGIN = P("respiracao", "Guided breathing (box 4-4-4-4, 4-7-8, calm 4-6) and desk stretch routine, spoken step by step with timing.",
           "respirar | alongar | parar | tecnicas",
           "respirar: tecnica (caixa|478|calma), ciclos (default 4). alongar: guided 5-minute desk stretch. parar stops.",
           "tecnica ciclos")

TECNICAS = {"caixa": [("Inspire", 4), ("Segure", 4), ("Solte o ar", 4), ("Segure vazio", 4)],
            "478": [("Inspire pelo nariz", 4), ("Segure", 7), ("Solte pela boca", 8)],
            "calma": [("Inspire", 4), ("Solte devagar", 6)]}
ALONGAR = [("Gire os ombros para trás, devagar", 30), ("Incline a cabeça para a direita e segure", 20),
           ("Agora para a esquerda", 20), ("Entrelace os dedos e estique os braços para frente", 20),
           ("Braços para cima, alongue as costas", 20), ("Gire o tronco para a direita na cadeira", 20),
           ("Agora para a esquerda", 20), ("Estique os punhos, palmas para fora", 20),
           ("Levante e caminhe um pouco; olhe para longe por 20 segundos", 60)]
_parar = threading.Event()


def roteiro(tecnica: str, ciclos: int) -> list[tuple[str, int]]:
    return TECNICAS.get(tecnica, TECNICAS["caixa"]) * max(1, min(ciclos, 20))


def _guiar(passos, pl, fim):
    _parar.clear()
    for txt, s in passos:
        if _parar.is_set():
            return
        falar_ja(pl, f"{txt}… {s}")
        time.sleep(s)
    falar_ja(pl, fim)


def _go(p, pl):
    a = str(p.get("action")).lower()
    if a == "tecnicas":
        return "Caixa (4-4-4-4, foco), 4-7-8 (dormir) e calma (4-6, ansiedade)."
    if a == "parar":
        _parar.set()
        return "Parei."
    if a == "alongar":
        passos, fim = ALONGAR, "Pronto, alongamento feito. Bom trabalho."
    else:
        t = str(p.get("tecnica") or "caixa").replace("-", "")
        passos, fim = roteiro(t, int(p.get("ciclos") or 4)), "Muito bem. Respire normalmente."
    threading.Thread(target=_guiar, args=(passos, pl, fim), daemon=True).start()
    return f"Vamos lá: {sum(s for _, s in passos) // 60 or 1} minuto(s). Siga minha voz."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("respirar alongar parar tecnicas".split(), _go), player)
