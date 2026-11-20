"""
Mestre de RPG (fork PT-BR 1.6).

O JARVIS narra uma aventura interativa por voz: você diz o que seu personagem
faz, ele narra a consequência e pede rolagens de dados quando faz sentido. Os
dados e as fichas são de verdade (sorteio aqui no PC, não "da cabeça" da IA).

    "Jarvis, começa uma aventura de fantasia medieval"     (ou cyberpunk, terror, espacial…)
    "Jarvis, cria meu personagem: Kael, ladino"
    "Jarvis, rola 1d20+3"         "Jarvis, rola 4d6 e fica com os 3 maiores"
    "Jarvis, mostra minha ficha"  "Jarvis, perdi 5 de vida"   "Jarvis, peguei uma espada"
    "Jarvis, salva a aventura"    (continua outro dia de onde parou)
"""

from __future__ import annotations

import random
import re
import time

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "mestre_rpg",
    "brief": "Voice RPG game master: interactive adventure, real dice rolls (2d6+3, 4d6kh3), character sheets, saves.",
    "description": (
        "Tabletop RPG game master. action='nova' with tema (starts a campaign; then narrate and ask what the player "
        "does); 'rolar' with dados (e.g. '1d20+3', '2d6', '4d6kh3') + motivo — ALWAYS use this for rolls, never invent "
        "results; 'personagem' with nome + classe (rolls attributes); 'ficha' (show); 'vida' with valor (+/- HP); "
        "'item' with nome (+ remover=true); 'salvar' with resumo (scene summary to continue later); 'continuar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "tema": {"type": "STRING"}, "dados": {"type": "STRING"},
                       "motivo": {"type": "STRING"}, "nome": {"type": "STRING"}, "classe": {"type": "STRING"},
                       "valor": {"type": "INTEGER"}, "remover": {"type": "BOOLEAN"}, "resumo": {"type": "STRING"}},
        "required": ["action"],
    },
}

_ARQ = MEMORIA / "rpg.json"
ATRIBUTOS = ("Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma")
CLASSES = {"guerreiro": ("Força", 12), "ladino": ("Destreza", 9), "mago": ("Inteligência", 7), "clerigo": ("Sabedoria", 9),
           "clérigo": ("Sabedoria", 9), "bardo": ("Carisma", 8), "patrulheiro": ("Destreza", 10), "hacker": ("Inteligência", 8),
           "piloto": ("Destreza", 9), "detetive": ("Sabedoria", 8)}


def rolar(expr: str, rng: random.Random | None = None) -> dict:
    """'2d6+3', 'd20', '4d6kh3' (fica com os 3 maiores), '1d20-1' → resultado (pura com rng)."""
    rng = rng or random.Random()
    e = (expr or "").lower().replace(" ", "")
    m = re.fullmatch(r"(\d*)d(\d+)(?:k([hl])(\d+))?([+-]\d+)?", e)
    if not m:
        raise ValueError(f"não entendi os dados '{expr}' (use, por exemplo, 1d20+3)")
    qtd, lados = int(m.group(1) or 1), int(m.group(2))
    if not (1 <= qtd <= 100 and 2 <= lados <= 1000):
        raise ValueError("dados demais ou lados demais")
    jogadas = [rng.randint(1, lados) for _ in range(qtd)]
    usadas = list(jogadas)
    if m.group(3):
        k = max(1, min(qtd, int(m.group(4))))
        usadas = sorted(jogadas, reverse=m.group(3) == "h")[:k]
    bonus = int(m.group(5) or 0)
    total = sum(usadas) + bonus
    critico = "crítico!" if lados == 20 and qtd == 1 and jogadas[0] == 20 else \
        "falha crítica!" if lados == 20 and qtd == 1 and jogadas[0] == 1 else ""
    return {"expr": expr, "jogadas": jogadas, "usadas": usadas, "bonus": bonus, "total": total, "critico": critico}


def modificador(valor: int) -> int:
    return (valor - 10) // 2


def criar_personagem(nome: str, classe: str, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    valores = sorted((rolar("4d6kh3", rng)["total"] for _ in ATRIBUTOS), reverse=True)
    principal, vida_base = CLASSES.get(classe.lower(), ("Força", 8))
    ordem = [principal] + [a for a in ATRIBUTOS if a != principal]
    atrib = dict(zip(ordem, valores))
    vida = vida_base + modificador(atrib["Constituição"])
    return {"nome": nome, "classe": classe, "nivel": 1, "atributos": {a: atrib[a] for a in ATRIBUTOS},
            "vida": max(1, vida), "vida_max": max(1, vida), "itens": ["mochila", "ração (3 dias)", "tocha"], "ouro": 10}


def ficha_texto(f: dict) -> str:
    return "\n".join([f"{f['nome']} — {f['classe']} nível {f['nivel']}", f"Vida: {f['vida']}/{f['vida_max']}   Ouro: {f['ouro']}",
                      ""] + [f"{a:<13} {v:>2} ({modificador(v):+d})" for a, v in f["atributos"].items()]
                     + ["", "Itens: " + ", ".join(f["itens"])])


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        if acao == "rolar":
            r = rolar(str(p.get("dados") or "1d20"))
            d.setdefault("rolagens", []).append({**r, "motivo": p.get("motivo") or "", "ts": time.time()})
            d["rolagens"] = d["rolagens"][-50:]
            gravar_json(_ARQ, d)
            detalhe = f"{r['jogadas']}" + (f" (ficou com {r['usadas']})" if r["usadas"] != r["jogadas"] else "") + \
                (f" {r['bonus']:+d}" if r["bonus"] else "")
            return (f"[DADOS] {r['expr']}{' para ' + str(p.get('motivo')) if p.get('motivo') else ''}: {detalhe} = "
                    f"{r['total']} {r['critico']}. Narre a consequência com esse resultado.")
        if acao == "nova":
            tema = str(p.get("tema") or "fantasia medieval")
            d = {"tema": tema, "inicio": time.time(), "cena": "", "personagem": d.get("personagem")}
            gravar_json(_ARQ, d)
            return (f"[MESTRE] Você é o mestre de uma aventura de {tema}, em português do Brasil. Regras: descreva a cena "
                    "em 3 a 5 frases vívidas, termine perguntando 'o que você faz?'; quando a ação for arriscada, peça uma "
                    "rolagem e use mestre_rpg action='rolar' (nunca invente o número); acompanhe a vida e os itens com as "
                    "ações 'vida' e 'item'. " + ("" if d.get("personagem") else
                                                  "Antes de começar, pergunte o nome e a classe do personagem e chame "
                                                  "action='personagem'. ") + "Comece agora.")
        if acao == "personagem":
            nome, classe = str(p.get("nome") or "Herói"), str(p.get("classe") or "guerreiro")
            d["personagem"] = criar_personagem(nome, classe)
            gravar_json(_ARQ, d)
            mostrar(player, "FICHA", ficha_texto(d["personagem"]))
            f = d["personagem"]
            return (f"Ficha criada: {nome}, {classe}, {f['vida']} de vida. Atributos: "
                    + ", ".join(f"{a} {v}" for a, v in f["atributos"].items()) + ". A ficha está no painel.")
        f = d.get("personagem")
        if acao in ("ficha", "vida", "item") and not f:
            return "Ainda não há personagem. Diga o nome e a classe."
        if acao == "ficha":
            mostrar(player, "FICHA", ficha_texto(f))
            return f"{f['nome']}: {f['vida']}/{f['vida_max']} de vida, itens: {', '.join(f['itens'])}."
        if acao == "vida":
            f["vida"] = max(0, min(f["vida_max"], f["vida"] + int(p.get("valor") or 0)))
            gravar_json(_ARQ, d)
            return f"Vida de {f['nome']}: {f['vida']}/{f['vida_max']}." + (" Ele caiu inconsciente!" if f["vida"] == 0 else "")
        if acao == "item":
            nome = str(p.get("nome") or "").strip()
            if p.get("remover"):
                f["itens"] = [i for i in f["itens"] if i.lower() != nome.lower()]
            elif nome:
                f["itens"].append(nome)
            gravar_json(_ARQ, d)
            return "Itens: " + ", ".join(f["itens"]) + "."
        if acao == "salvar":
            d["cena"] = str(p.get("resumo") or "")
            d["salvo"] = time.time()
            gravar_json(_ARQ, d)
            return "Aventura salva. Diga 'continua a aventura' outro dia."
        if acao == "continuar":
            if not d.get("tema"):
                return "Não há aventura salva. Diga 'começa uma aventura de …'."
            return (f"[MESTRE] Continue a aventura de {d['tema']} como mestre (mesmas regras: rolagens pela ferramenta). "
                    f"Onde paramos: {d.get('cena') or 'no começo'}. Personagem: "
                    + (ficha_texto(f).replace(chr(10), '; ') if f else "nenhum") + ". Recapitule em 2 frases e pergunte o "
                    "que o personagem faz.")
        return "Ações: nova, rolar, personagem, ficha, vida, item, salvar, continuar."
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"O mestre de RPG falhou: {e}"
