"""
Contador de histórias (fork PT-BR 1.6).

O JARVIS narra uma história por voz — para dormir, para crianças ou de
aventura/terror — com som ambiente de fundo (chuva, mar, lareira, floresta,
noite, vento) e efeitos na hora certa (trovão, porta rangendo, passos,
batidas na porta, sino, magia, uivo). Tudo gerado aqui, sem arquivos de som.

    "Jarvis, conta uma história para dormir"
    "Jarvis, uma história de terror com chuva"
    "Jarvis, conta uma história para criança sobre um dragão"
    "Jarvis, para a história"

No modo dormir, o som ambiente vai sumindo sozinho depois de 20 minutos.
"""

from __future__ import annotations

import threading
import time

from plugins import _som

PLUGIN = {
    "name": "contador_historias",
    "brief": "Voice storyteller with generated ambient sound and sound effects (bedtime, kids, adventure, horror).",
    "description": (
        "Storyteller: action='comecar' with tema + publico (dormir|crianca|aventura|terror) + optional ambiente "
        "(chuva|mar|lareira|floresta|noite|vento); then narrate the story and, at dramatic moments, call action='efeito' "
        "with efeito = trovao | porta | passos | batidas | sino | magia | uivo (it plays at once); action='parar' stops "
        "the background sound."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "comecar | efeito | parar"},
                       "tema": {"type": "STRING"}, "publico": {"type": "STRING"}, "ambiente": {"type": "STRING"},
                       "efeito": {"type": "STRING"}},
        "required": [],
    },
}

ESTILOS = {
    "dormir": ("voz baixa e lenta, frases curtas, nada assustador, termine com tudo em paz e os personagens dormindo; "
               "cerca de 5 minutos", "chuva"),
    "crianca": ("linguagem simples, divertida, com uma pequena lição no fim, onomatopeias; uns 4 minutos", "floresta"),
    "aventura": ("ritmo rápido, suspense, escolhas difíceis; uns 6 minutos", "vento"),
    "terror": ("suspense crescente, descrições sombrias mas sem violência explícita, um final arrepiante; uns 6 minutos",
               "noite"),
}
_estado = {"laco": None, "desligar_em": 0.0}


def publico_de(texto: str) -> str:
    t = (texto or "").lower()
    return "dormir" if "dorm" in t or "ninar" in t else "crianca" if "crian" in t or "filh" in t or "infantil" in t \
        else "terror" if "terror" in t or "medo" in t or "assust" in t else "aventura"


def parar_ambiente() -> None:
    laco = _estado.get("laco")
    _estado["laco"] = None
    if laco is not None:
        threading.Thread(target=laco.parar, daemon=True).start()


def _vigia_dormir() -> None:
    while _estado["laco"] is not None:
        if _estado["desligar_em"] and time.time() > _estado["desligar_em"]:
            parar_ambiente()
            return
        time.sleep(10)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "comecar").lower()
    try:
        if acao == "parar":
            parar_ambiente()
            return "Parei o som da história."
        if acao == "efeito":
            nome = str(p.get("efeito") or "").lower().replace("ã", "a").replace("trovão", "trovao")
            nome = next((e for e in _som.EFEITOS if e.startswith(nome[:4])), "")
            if not nome:
                return f"Efeitos: {', '.join(_som.EFEITOS)}."
            try:
                _som.tocar_uma(_som.efeito(nome, semente=int(time.time()) % 1000))
            except Exception as e:
                return f"(Não consegui tocar o efeito: {e}.) Continue a narração imitando o som com a voz."
            return "Efeito tocando. Continue a narração."
        publico = publico_de(str(p.get("publico") or "") + " " + str(p.get("tema") or ""))
        jeito, amb_padrao = ESTILOS[publico]
        ambiente = str(p.get("ambiente") or "").lower()
        ambiente = next((a for a in _som.AMBIENTES if a in ambiente), amb_padrao)
        parar_ambiente()
        try:
            laco = _som.Laco(_som.ambiente(ambiente, 12, semente=int(time.time()) % 1000),
                             volume=0.18 if publico == "dormir" else 0.25)
            laco.tocar()
            _estado.update(laco=laco, desligar_em=time.time() + 20 * 60 if publico == "dormir" else 0.0)
            if publico == "dormir":
                threading.Thread(target=_vigia_dormir, daemon=True).start()
            som = f"Já está tocando som de {ambiente} ao fundo."
        except Exception as e:
            som = f"(Sem som ambiente: {e}.)"
        tema = str(p.get("tema") or "uma história original")
        return (f"[HISTÓRIA] Conte agora, em português do Brasil, uma história original sobre: {tema}. Jeito: {jeito}. "
                f"{som} Em 2 ou 3 momentos marcantes, chame contador_historias action='efeito' com um destes efeitos: "
                f"{', '.join(_som.EFEITOS)} (só quando combinar com a cena). No fim, chame action='parar'"
                + (" — no modo dormir, NÃO pare: o som some sozinho." if publico == "dormir" else ".")
                + " Comece já, sem introdução.")
    except Exception as e:
        return f"O contador de histórias falhou: {e}"
