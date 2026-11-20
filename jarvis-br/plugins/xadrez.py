"""
Xadrez e damas por voz (fork PT-BR 1.6; motor próprio na 1.7 — não precisa instalar nada).

    XADREZ:   "Jarvis, vamos jogar xadrez"   "cavalo para f3"
        "peão e4"  "e2 e4"  "bispo come em c4"  "roque pequeno"  "peão e8 vira dama"
    DAMAS (regras brasileiras):  "Jarvis, vamos jogar damas"
        "c3 d4"   "b6 para a5"   "c3 e5 c7"  (captura em sequência)
    "Jarvis, mostra o tabuleiro"   "Jarvis, desisto"   "Jarvis, nível difícil"

O tabuleiro aparece no painel e também no Arcade ("Jarvis, abre os jogos"):
a partida é a mesma, dá para alternar entre clicar e falar. Nas damas valem a
captura obrigatória, a lei da maioria, o peão capturando para trás e a dama
que anda várias casas.
"""

from __future__ import annotations

import random
import re
import unicodedata

from plugins import _xadrez_motor as motor
from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "xadrez",
    "brief": "Chess (own engine, nothing to install) and Brazilian checkers by voice, against JARVIS.",
    "description": (
        "Voice chess and Brazilian checkers (damas) against JARVIS. action='novo' with jogo (xadrez|damas) + optional "
        "nivel (facil|medio|dificil) + cor (brancas|pretas); action='lance' with lance exactly as the user said it "
        "(e.g. 'cavalo para f3', 'e2 e4', 'roque pequeno', 'c3 d4', 'c3 e5 c7'); 'tabuleiro'; 'desistir'. Read JARVIS's "
        "answer move as returned. The same game is shown in the Arcade window (tool jogos)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "novo | lance | tabuleiro | desistir"},
                       "jogo": {"type": "STRING"}, "nivel": {"type": "STRING"}, "cor": {"type": "STRING"},
                       "lance": {"type": "STRING"}},
        "required": [],
    },
}

ARQ = MEMORIA / "xadrez.json"


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


# ═══ XADREZ (motor próprio: plugins/_xadrez_motor.py) ═════════════════════════
def lance_xadrez(pos: motor.Posicao, fala: str):
    """Texto falado → (lance, '') ou (None, motivo/pergunta)."""
    return motor.ler_lance(pos, fala)


def falar_lance(pos: motor.Posicao, lance) -> str:
    return motor.falar_lance(pos, lance)


def desenho_xadrez(pos: motor.Posicao, brancas_embaixo: bool = True) -> str:
    return motor.desenho(pos, brancas_embaixo)


def _fim_xadrez(pos: motor.Posicao, voce_brancas: bool) -> str:
    r = pos.resultado()
    if not r:
        return ""
    if r.startswith("mate"):
        venceu_brancas = r == "mate_brancas"
        return "Xeque-mate: você venceu! Parabéns." if venceu_brancas == voce_brancas else "Xeque-mate: eu venci desta vez!"
    return "Afogado: empate." if r == "afogado" else "Empate."


def novo_xadrez(nivel: str = "medio", voce: str = "brancas", rng: random.Random | None = None) -> tuple[dict, str]:
    """Começa uma partida; se você é de pretas, JARVIS já joga. Devolve (estado, fala)."""
    pos = motor.Posicao()
    d = {"jogo": "xadrez", "nivel": nivel, "voce": voce, "fen": pos.fen(), "lances": [], "ultimo": None}
    if voce == "pretas":
        m = motor.melhor_lance(pos, nivel, rng)
        fala = motor.falar_lance(pos, m)
        pos = pos.jogar(m)
        d.update(fen=pos.fen(), lances=[fala], ultimo=[m[0], m[1]])
        return d, f"Você joga de pretas. Meu primeiro lance: {fala}. Sua vez."
    return d, f"Xadrez, nível {nivel}. Você joga de brancas: diga seu lance, como 'peão e4' ou 'cavalo f3'."


def jogada_xadrez(d: dict, lance, rng: random.Random | None = None) -> str:
    """Aplica o lance do usuário (já legal) e a resposta do JARVIS; muda d e devolve a fala."""
    pos = motor.Posicao(d["fen"])
    voce_brancas = d.get("voce", "brancas") == "brancas"
    seu = motor.falar_lance(pos, lance)
    pos = pos.jogar(lance)
    d["ultimo"] = [lance[0], lance[1]]
    fim = _fim_xadrez(pos, voce_brancas)
    if fim:
        d.update(fen=pos.fen(), jogo=None, lances=(d.get("lances", []) + [seu])[-200:])
        return f"Você jogou {seu}. {fim}"
    meu_lance = motor.melhor_lance(pos, d.get("nivel", "medio"), rng)
    meu = motor.falar_lance(pos, meu_lance)
    pos = pos.jogar(meu_lance)
    d.update(fen=pos.fen(), ultimo=[meu_lance[0], meu_lance[1]], lances=(d.get("lances", []) + [seu, meu])[-200:])
    fim = _fim_xadrez(pos, voce_brancas)
    if fim:
        d["jogo"] = None
    return f"Você: {seu}. Eu: {meu}." + (f" {fim}" if fim else "")


# ═══ DAMAS (regras brasileiras) ═══════════════════════════════════════════════
# casas (col, lin) de 0 a 7; a1 = (0, 0) é casa escura; peças: 'b'/'B' (brancas, sobem), 'p'/'P' (pretas, descem)
def damas_inicial() -> dict:
    tab = {}
    for lin in range(8):
        for col in range(8):
            if (col + lin) % 2 == 0:
                if lin <= 2:
                    tab[f"{col},{lin}"] = "b"
                elif lin >= 5:
                    tab[f"{col},{lin}"] = "p"
    return tab


def _casa(nome: str) -> tuple[int, int]:
    return ord(nome[0]) - 97, int(nome[1]) - 1


def _nome(c: tuple[int, int]) -> str:
    return f"{chr(97 + c[0])}{c[1] + 1}"


def _peca(tab, c):
    return tab.get(f"{c[0]},{c[1]}")


def _dentro(c):
    return 0 <= c[0] < 8 and 0 <= c[1] < 8


def _inimiga(p, q):
    return q is not None and p.lower() != q.lower()


def _capturas_de(tab, origem, peca, capturadas, visitadas):
    """Todas as sequências de captura a partir de origem: listas de casas [origem, ..., fim] e peças comidas."""
    seqs = []
    dama = peca.isupper()
    for dc, dl in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        c = (origem[0] + dc, origem[1] + dl)
        if dama:
            while _dentro(c) and _peca(tab, c) is None:
                c = (c[0] + dc, c[1] + dl)
        if not _dentro(c) or not _inimiga(peca, _peca(tab, c)) or c in capturadas:
            continue
        alvo = c
        destino = (alvo[0] + dc, alvo[1] + dl)
        while _dentro(destino) and (_peca(tab, destino) is None or destino in visitadas):
            if _peca(tab, destino) is not None and destino not in visitadas:
                break
            continuar = _capturas_de(tab, destino, peca, capturadas | {alvo}, visitadas | {destino})
            if continuar:
                seqs += [([origem] + s, [alvo] + comidas) for s, comidas in continuar]
            else:
                seqs.append(([origem, destino], [alvo]))
            if not dama:
                break
            destino = (destino[0] + dc, destino[1] + dl)
    return seqs


def damas_lances(tab: dict, cor: str) -> list[tuple[list, list]]:
    """Lances legais (sequência de casas, peças capturadas) com a lei da maioria (pura)."""
    capturas, simples = [], []
    for chave, peca in list(tab.items()):
        if peca.lower() != cor:
            continue
        o = tuple(map(int, chave.split(",")))
        sem = dict(tab)
        del sem[chave]                                         # a peça que se move libera a casa de origem
        capturas += _capturas_de(sem, o, peca, frozenset(), frozenset({o}))
        frente = 1 if cor == "b" else -1
        dirs = ((1, 1), (-1, 1), (1, -1), (-1, -1)) if peca.isupper() else ((1, frente), (-1, frente))
        for dc, dl in dirs:
            c = (o[0] + dc, o[1] + dl)
            while _dentro(c) and _peca(tab, c) is None:
                simples.append(([o, c], []))
                if not peca.isupper():
                    break
                c = (c[0] + dc, c[1] + dl)
    if capturas:
        maximo = max(len(x[1]) for x in capturas)
        return [x for x in capturas if len(x[1]) == maximo]
    return simples


def damas_jogar(tab: dict, lance: tuple[list, list]) -> dict:
    novo = dict(tab)
    casas, comidas = lance
    peca = novo.pop(f"{casas[0][0]},{casas[0][1]}")
    for c in comidas:
        novo.pop(f"{c[0]},{c[1]}", None)
    fim = casas[-1]
    if (peca == "b" and fim[1] == 7) or (peca == "p" and fim[1] == 0):
        peca = peca.upper()
    novo[f"{fim[0]},{fim[1]}"] = peca
    return novo


def damas_valor(tab: dict) -> int:
    return sum((3 if p.isupper() else 1) * (1 if p.lower() == "b" else -1) for p in tab.values())


def damas_escolher(tab: dict, cor: str, rng: random.Random, nivel: str) -> tuple[list, list] | None:
    lances = damas_lances(tab, cor)
    if not lances:
        return None
    if nivel == "facil":
        return rng.choice(lances)
    sinal = 1 if cor == "b" else -1
    outra = "p" if cor == "b" else "b"

    def nota(lance):
        depois = damas_jogar(tab, lance)
        resp = damas_lances(depois, outra)
        pior = min((sinal * damas_valor(damas_jogar(depois, r)) for r in resp), default=sinal * damas_valor(depois) + 50)
        return pior
    notas = [(nota(x), x) for x in lances]
    melhor = max(n for n, _x in notas)
    return rng.choice([x for n, x in notas if n == melhor])


def damas_ler_lance(tab: dict, cor: str, fala: str):
    casas = [_casa(a + b) for a, b in re.findall(r"\b([a-h])\s*([1-8])\b", _dobrar(fala))]
    legais = damas_lances(tab, cor)
    if not casas:
        return None, "Diga as casas, como 'c3 d4'."
    cands = [x for x in legais if x[0][-1] == casas[-1] and (len(casas) < 2 or x[0][0] == casas[0])
             and all(c in x[0] for c in casas)]
    if len(cands) == 1:
        return cands[0], ""
    if not cands:
        obrig = " (a captura é obrigatória e tem que comer o máximo de peças)" if legais and legais[0][1] else ""
        return None, "Esse lance não vale" + obrig + ". Lances possíveis: " + \
            ", ".join(" ".join(_nome(c) for c in x[0]) for x in legais[:6]) + "."
    return None, "Qual deles: " + " ou ".join(" ".join(_nome(c) for c in x[0]) for x in cands) + "?"


def desenho_damas(tab: dict) -> str:
    simbolos = {"b": "○", "B": "◎", "p": "●", "P": "◉"}
    linhas = [f"{lin + 1} " + " ".join(simbolos.get(tab.get(f"{col},{lin}"), "·" if (col + lin) % 2 == 0 else " ")
                                       for col in range(8)) for lin in range(7, -1, -1)]
    return "\n".join(linhas + ["  a b c d e f g h", "", "○ suas  ◎ sua dama   ● minhas  ◉ minha dama"])


def novo_damas(nivel: str = "medio") -> tuple[dict, str]:
    return ({"jogo": "damas", "nivel": nivel, "tab": damas_inicial(), "lances": []},
            "Damas, regras brasileiras. Você joga com as brancas, de baixo: diga as casas, como 'c3 d4'.")


def jogada_damas(d: dict, lance, rng: random.Random | None = None) -> str:
    """Aplica o lance do usuário (já legal) e a resposta do JARVIS; muda d e devolve a fala."""
    rng = rng or random.Random()
    tab = damas_jogar(d["tab"], lance)
    seu = " ".join(_nome(c) for c in lance[0]) + (f", comeu {len(lance[1])}" if lance[1] else "")
    meu_l = damas_escolher(tab, "p", rng, d.get("nivel", "medio"))
    if meu_l is None:
        d.update(tab=tab, jogo=None)
        return f"Você: {seu}. Fiquei sem lances: você venceu!"
    tab = damas_jogar(tab, meu_l)
    meu = " ".join(_nome(c) for c in meu_l[0]) + (f", comi {len(meu_l[1])}" if meu_l[1] else "")
    fim = "" if damas_lances(tab, "b") else " Você ficou sem lances: eu venci!"
    d.update(tab=tab, jogo=None if fim else "damas", ultimo_damas=[list(c) for c in meu_l[0]])
    return f"Você: {seu}. Eu: {meu}.{fim}"


# ═══ jogo ═════════════════════════════════════════════════════════════════════
def _salvar(d):
    gravar_json(ARQ, d)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "tabuleiro").lower()
    rng = random.Random()
    try:
        d = ler_json(ARQ, {}) or {}
        if acao == "novo":
            jogo_txt = _dobrar(str(p.get("jogo") or ""))
            jogo = "damas" if "dama" in jogo_txt and "xadrez" not in jogo_txt else "xadrez"
            nivel = next((n for n in ("facil", "medio", "dificil") if n in _dobrar(str(p.get("nivel") or ""))), "medio")
            if jogo == "xadrez":
                voce = "pretas" if "pret" in _dobrar(str(p.get("cor") or "")) else "brancas"
                d, fala = novo_xadrez(nivel, voce, rng)
                _salvar(d)
                mostrar(player, "XADREZ", desenho_xadrez(motor.Posicao(d["fen"]), voce == "brancas"))
                return fala
            d, fala = novo_damas(nivel)
            _salvar(d)
            mostrar(player, "DAMAS", desenho_damas(d["tab"]))
            return fala
        if not d.get("jogo"):
            return "Não há partida. Diga 'vamos jogar xadrez' ou 'vamos jogar damas'."
        if acao == "desistir":
            d["jogo"] = None
            _salvar(d)
            return "Partida encerrada. Boa partida! Quando quiser, a revanche."
        if d["jogo"] == "xadrez":
            pos = motor.Posicao(d["fen"])
            embaixo = d.get("voce", "brancas") == "brancas"
            if acao == "tabuleiro":
                mostrar(player, "XADREZ", desenho_xadrez(pos, embaixo))
                return "O tabuleiro está no painel."
            if (pos.vez == "w") != embaixo:
                return "Agora é a minha vez; um instante."
            lance, erro = lance_xadrez(pos, str(p.get("lance") or ""))
            if not lance:
                return erro
            fala = jogada_xadrez(d, lance, rng)
            _salvar(d)
            mostrar(player, "XADREZ", desenho_xadrez(motor.Posicao(d["fen"]), embaixo))
            return fala
        if acao == "tabuleiro":
            mostrar(player, "DAMAS", desenho_damas(d["tab"]))
            return "O tabuleiro está no painel."
        lance, erro = damas_ler_lance(d["tab"], "b", str(p.get("lance") or ""))
        if not lance:
            return erro
        fala = jogada_damas(d, lance, rng)
        _salvar(d)
        mostrar(player, "DAMAS", desenho_damas(d["tab"]))
        return fala
    except Exception as e:
        return f"O jogo falhou: {e}"
