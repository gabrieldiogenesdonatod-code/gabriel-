"""Forca (2.19): jogo da forca por voz — diga uma letra por vez ou chute a palavra; seis erros e acabou."""
from __future__ import annotations

import random

from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("forca", "Hangman by voice: new word by theme, guess a letter or the whole word, state, hint; 6 mistakes allowed.",
           "nova | letra | chutar | estado | dica",
           "nova: tema (animais|comida|tecnologia|casa|qualquer). letra/chutar: valor.", "tema valor")

PALAVRAS = {"animais": "cachorro elefante tartaruga borboleta capivara tucano jacare golfinho formiga coruja tamandua".split(),
            "comida": "pamonha feijoada macarrao brigadeiro tapioca churrasco empada pequi coxinha lasanha".split(),
            "tecnologia": "computador teclado algoritmo internet programa servidor bateria processador roteador variavel".split(),
            "casa": "geladeira travesseiro cortina chuveiro escada janela tapete vassoura armario espelho".split()}
MAX = 6


def mascara(palavra: str, letras: str) -> str:
    return " ".join(c.upper() if c in letras else "_" for c in palavra)


def _fala(e) -> str:
    erradas = [c.upper() for c in e["letras"] if c not in e["palavra"]]
    return f"{mascara(e['palavra'], e['letras'])} ({len(e['palavra'])} letras). Erros {len(erradas)} de {MAX}" + \
        (f": {', '.join(erradas)}." if erradas else ".")


def _go(p, pl):
    a, e = p["action"], carregar("forca", {})
    if a == "nova" or not e.get("palavra"):
        tema = norm(p.get("tema"))
        tema = tema if tema in PALAVRAS else random.choice(list(PALAVRAS))
        e = {"palavra": random.choice(PALAVRAS[tema]), "letras": "", "tema": tema}
        guardar("forca", e)
        return f"Forca nova, tema {tema}. " + _fala(e) + " Diga uma letra."
    w, v = e["palavra"], norm(p.get("valor")).replace(" ", "")
    if a == "dica":
        falta = [c for c in w if c not in e["letras"]]
        return f"Tema {e['tema']}. Tem a letra {random.choice(falta).upper()}." if falta else "Já está completa."
    if a == "chutar" or (a == "letra" and len(v) > 1):
        ok = v == w
        guardar("forca", {})
        return f"{'Acertou' if ok else 'Errou'}! A palavra era {w.upper()}. Diga 'nova' para jogar de novo."
    if a == "letra" and v:
        if v in e["letras"]:
            return f"Você já disse {v.upper()}. " + _fala(e)
        e["letras"] += v
        erros = sum(c not in w for c in e["letras"])
        if all(c in e["letras"] for c in w) or erros >= MAX:
            guardar("forca", {})
            return (f"Ganhou! {w.upper()}." if erros < MAX else f"Enforcou! Era {w.upper()}.") + " Diga 'nova' para outra."
        guardar("forca", e)
        return ("Tem! " if v in w else "Não tem. ") + _fala(e)
    return _fala(e)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("nova letra chutar estado dica".split(), _go), player)
