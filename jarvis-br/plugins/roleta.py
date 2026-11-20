"""
Roleta de rolê (fork PT-BR 1.6) — "Jarvis, decide o que eu janto."

Sorteia comida, filme, série, jogo ou rolê com base no SEU gosto: aprende com
"gostei" e "não gostei", evita repetir o que saiu nos últimos dias e, se você
quiser, deixa a IA sugerir uma surpresa fora da lista.

    "Jarvis, decide o que eu janto"           "Jarvis, o que eu assisto hoje?"
    "Jarvis, adiciona sushi nas comidas"      "Jarvis, não gostei" / "gostei"
    "Jarvis, surpreende: um filme que eu não conheço"
"""

from __future__ import annotations

import random
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json

PLUGIN = {
    "name": "roleta",
    "brief": "Decides what to eat/watch/play/do based on the user's taste, learns likes, avoids repeats.",
    "description": (
        "Decision roulette: action='sortear' with categoria (comida, filme, serie, jogo, role); 'adicionar' / 'remover' "
        "with categoria + item; 'gostei' / 'nao_gostei' (about the last pick); 'surpresa' with categoria (AI suggests "
        "something new); 'listar' with categoria."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "categoria": {"type": "STRING"}, "item": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "roleta.json"
PADRAO = {
    "comida": ["pizza", "hambúrguer", "pamonha", "pequi com arroz", "sushi", "pastel", "açaí", "marmita caseira",
               "espetinho", "lanche natural", "macarrão", "frango assado", "yakisoba", "tapioca", "comida mexicana"],
    "filme": ["Homem de Ferro", "Interestelar", "Matrix", "Homem-Aranha no Aranhaverso", "Duna", "Cidade de Deus",
              "O Auto da Compadecida", "Vingadores: Ultimato", "A Origem", "Divertida Mente"],
    "serie": ["Arcane", "Stranger Things", "The Boys", "Dark", "Breaking Bad", "One Piece (live action)", "Loki",
              "Cyberpunk: Mercenários", "Sintonia"],
    "jogo": ["Valorant", "Minecraft", "Free Fire", "EA FC", "Rocket League", "GTA V", "Roblox", "um jogo indie novo"],
    "role": ["cinema", "Parque Vaca Brava", "feira hippie", "rodízio com os amigos", "caminhada no Flamboyant",
             "dia de jogos em casa", "lanchonete nova", "Parque Areião"],
}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode().strip()


def categoria_de(texto: str) -> str:
    t = _dobrar(texto)
    for cat, chaves in (("comida", ("com", "jant", "almo", "lanch", "pedir")), ("serie", ("seri",)),
                        ("filme", ("film", "assist", "cinema em casa")), ("jogo", ("jog", "game")),
                        ("role", ("role", "sair", "passe", "programa"))):
        if any(t.startswith(c) or c in t for c in chaves):
            return cat
    return "comida"


def sortear(itens: list[str], pesos: dict, recentes: list[str], rng: random.Random) -> str:
    """Sorteio com pesos (gostei aumenta, não gostei diminui) e sem repetir os últimos (pura com rng)."""
    cands = [i for i in itens if i not in recentes[-3:]] or itens
    w = [max(0.1, float(pesos.get(i, 1.0))) for i in cands]
    return rng.choices(cands, weights=w, k=1)[0]


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(str(p.get("action") or "sortear")).replace(" ", "_")
    cat = categoria_de(str(p.get("categoria") or ""))
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("listas", {k: list(v) for k, v in PADRAO.items()})
        d.setdefault("pesos", {})
        d.setdefault("historico", [])
        lista = d["listas"].setdefault(cat, list(PADRAO.get(cat, [])))
        pesos = d["pesos"].setdefault(cat, {})
        item = str(p.get("item") or "").strip()
        if acao == "adicionar" and item:
            if item not in lista:
                lista.append(item)
            gravar_json(_ARQ, d)
            return f"Adicionei {item} em {cat}."
        if acao == "remover" and item:
            d["listas"][cat] = [x for x in lista if _dobrar(x) != _dobrar(item)]
            gravar_json(_ARQ, d)
            return f"Tirei {item} de {cat}."
        if acao in ("gostei", "nao_gostei"):
            ultimo = d.get("ultimo")
            if not ultimo:
                return "Ainda não sorteei nada."
            pc = d["pesos"].setdefault(ultimo["cat"], {})
            pc[ultimo["item"]] = min(5.0, pc.get(ultimo["item"], 1.0) * 1.5) if acao == "gostei" else \
                max(0.1, pc.get(ultimo["item"], 1.0) * 0.4)
            gravar_json(_ARQ, d)
            return f"Anotado: {'mais' if acao == 'gostei' else 'menos'} {ultimo['item']} daqui pra frente."
        if acao == "listar":
            return f"{cat.capitalize()}: " + ", ".join(lista) + "."
        if acao == "surpresa":
            from plugins import _ia
            if _ia.disponivel():
                r = _ia.perguntar(f"Sugira UMA opção de {cat} que fuja destas mas combine com o gosto de quem gosta delas: "
                                  f"{', '.join(lista)}. Responda só o nome e o porquê em uma frase, em português do Brasil.",
                                  False, 20)
                if r:
                    return f"Surpresa: {r}"
        recentes = [h["item"] for h in d["historico"] if h["cat"] == cat]
        escolha = sortear(lista, pesos, recentes, random.Random())
        d["ultimo"] = {"cat": cat, "item": escolha}
        d["historico"] = (d["historico"] + [{"cat": cat, "item": escolha, "ts": time.time()}])[-100:]
        gravar_json(_ARQ, d)
        return f"[ROLETA] Anuncie com suspense, em 1 frase: a roleta escolheu {escolha}! (Se não gostar, é só dizer.)"
    except Exception as e:
        return f"A roleta falhou: {e}"
