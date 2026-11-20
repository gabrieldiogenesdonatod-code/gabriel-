"""Mini jogos (2.19): pedra-papel-tesoura, par ou ímpar e adivinhe o número (quente ou frio) contra o JARVIS, com placar."""
from __future__ import annotations

import random

from plugins._lote2 import P, carregar, guardar, norm, numeros, rodar

PLUGIN = P("mini_jogos", "Quick voice games vs JARVIS: rock-paper-scissors, odds or evens, guess the number 1-100 (higher/lower), scoreboard.",
           "pedra_papel_tesoura | par_impar | adivinhe | placar",
           "pedra_papel_tesoura: valor (pedra|papel|tesoura). par_impar: valor ('par 3'). adivinhe: valor (guess; empty starts a new number).",
           "valor")

VENCE = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}


def ppt(eu: str, ele: str) -> int:
    return 0 if eu == ele else 1 if VENCE[eu] == ele else -1


def _ponto(e, r):
    e["eu" if r > 0 else "jarvis" if r < 0 else "empates"] = e.get("eu" if r > 0 else "jarvis" if r < 0 else "empates", 0) + 1


def _go(p, pl):
    a, e, v = p["action"], carregar("mini_jogos", {}), norm(p.get("valor"))
    if a == "placar":
        return f"Você {e.get('eu', 0)}, JARVIS {e.get('jarvis', 0)}, empates {e.get('empates', 0)}."
    if a == "pedra_papel_tesoura":
        eu = next((k for k in VENCE if k in v), None)
        if not eu:
            return "Pedra, papel ou tesoura?"
        ele = random.choice(list(VENCE))
        r = ppt(eu, ele)
        _ponto(e, r)
        guardar("mini_jogos", e)
        return f"Eu joguei {ele}. " + ("Você ganhou!" if r > 0 else "Ganhei!" if r < 0 else "Empate.")
    n = numeros(v)
    if a == "par_impar":
        if not n or ("par" not in v and "impar" not in v):
            return "Diga 'par' ou 'ímpar' e um número de 0 a 10."
        meu = random.randint(0, 10)
        soma, quer_par = int(n[0]) + meu, "impar" not in v
        r = 1 if (soma % 2 == 0) == quer_par else -1
        _ponto(e, r)
        guardar("mini_jogos", e)
        return f"Eu pus {meu}, deu {soma}, {'par' if soma % 2 == 0 else 'ímpar'}. " + ("Você ganhou!" if r > 0 else "Ganhei!")
    if not n or "segredo" not in e:
        e["segredo"], e["tentativas"] = random.randint(1, 100), 0
        guardar("mini_jogos", e)
        return "Pensei num número de 1 a 100. Qual é o seu palpite?"
    e["tentativas"] += 1
    g, s = int(n[0]), e["segredo"]
    if g == s:
        t = e.pop("tentativas")
        e.pop("segredo")
        _ponto(e, 1)
        guardar("mini_jogos", e)
        return f"Acertou em {t} tentativa(s)! Era {s}."
    guardar("mini_jogos", e)
    perto = " Está quente!" if abs(g - s) <= 5 else ""
    return ("É maior." if g < s else "É menor.") + perto


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("pedra_papel_tesoura par_impar adivinhe placar".split(), _go), player)
