"""
Anti-eco (3.2): o JARVIS não responde mais a própria voz que volta pela caixa de som.

    "Jarvis, como está o anti-eco?"      "Jarvis, zera o anti-eco" (trocou a caixa de som pelo fone, por exemplo)

Como funciona: core/anti_eco.py. Ajuste fino em config/api_keys.json: "eco_cauda_minima_ms" (padrão 600).
"""

from __future__ import annotations

from core import anti_eco
from plugins._lote2 import P, rodar

PLUGIN = P("anti_eco", "Echo protection status: stops JARVIS from hearing and answering its own voice from the speakers; reset it.",
           "status | zerar",
           "status: what the echo guard learned (extra tail, echoes caught, voice interruption). zerar: forget it (e.g. after switching "
           "speakers to headphones).", "")


def _status(p, pl):
    e = anti_eco.get().estado()
    return (f"Anti-eco: {e['ecos_total']} eco(s) da minha própria voz pegos até hoje; espero mais "
            f"{e['cauda_extra_s']:.2f} s depois de falar antes de voltar a ouvir; interrupção por voz "
            f"{e['interrupcao_por_voz']}. Com fone de ouvido não há eco; na caixa de som, afastá-la do microfone ajuda.")


def _zerar(p, pl):
    anti_eco.get().zerar()
    return "Anti-eco zerado: voltei à espera mínima e a interrupção por voz está permitida de novo."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"status": _status, "zerar": _zerar}, player)
