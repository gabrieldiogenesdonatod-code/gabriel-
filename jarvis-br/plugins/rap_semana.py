"""
Rap da semana (3.0): todo domingo o JARVIS junta o que aconteceu na sua semana — vendas, hábitos,
corrida, o treino da IA, o sonho — e escreve um verso de rap geek ORIGINAL sobre ela.

    "Jarvis, faz o rap da semana."     "Jarvis, lê o último rap."     "Jarvis, me mostra todos os raps."

Fica guardado em Documentos/JARVIS/Rap. Com a chave do Gemini as rimas são livres; sem ela, ele
monta com rimas prontas. Nunca copia letra de música existente.
"""

from __future__ import annotations

import random
import time
from datetime import date, timedelta

from plugins import _fatos
from plugins._lote2 import P, carregar, guardar, rodar

PLUGIN = P("rap_semana", "Weekly rap: gathers your week (sales, habits, runs, AI training, the dream) and writes an ORIGINAL geek rap verse "
           "about it, saved to Documents/JARVIS/Rap; automatic on Sundays.",
           "escrever | ultimo | todos", "escrever: write this week's rap now (estilo optional: boom bap, trap, lento).", "estilo")

BASE = [("O sistema ligou, o reator acendeu,", "e a semana inteira quem fez fui eu."),
        ("No código e na loja, eu não paro, não,", "cada linha que eu escrevo é uma revolução."),
        ("Se o bug aparece, eu dou debug na hora,", "J.A.R.V.I.S do lado, ninguém me segura agora."),
        ("Promessa é palavra, palavra é missão,", "fazer o impossível é a minha profissão.")]


def offline(frases: list[str], rng=random) -> list[str]:
    versos = [BASE[0][0], BASE[0][1]]
    for f in frases[:4]:
        versos += [f"Essa semana {f},", rng.choice(["e o placar só subiu, pode crer, meu irmão.", "cada passo contado na palma da mão.",
                                                     "anota no HUD, que é informação.", "é dado na tela, é pura evolução."])]
    versos += list(rng.choice(BASE[1:]))
    return versos


def escrever(estilo: str = "boom bap", hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    ini = hoje - timedelta(6)
    frases = _fatos.frases(_fatos.periodo(ini, hoje))
    from core import gemini
    d = gemini.as_json(
        "Escreva um verso de rap ORIGINAL em português do Brasil, estilo rap geek (referências a tecnologia, HUD, código, heróis "
        f"de forma genérica), batida {estilo}, 12 a 16 linhas com rimas, sobre a semana desta pessoa: {'; '.join(frases) or 'uma semana de corre e trabalho'}. "
        "Ele é programador, tem uma loja de roupa infantil e constrói um J.A.R.V.I.S. NÃO copie nem parafraseie letras de músicas existentes; "
        "sem palavrão. Responda SÓ com JSON: {\"titulo\": \"...\", \"versos\": [\"linha\", ...], \"bpm\": 90}",
        tier=gemini.SMART, default=None)
    if not isinstance(d, dict) or not d.get("versos"):
        d = {"titulo": f"Semana {hoje:%d/%m}", "versos": offline(frases), "bpm": 88, "offline": True}
    d.update(semana=hoje.isoformat(), fatos=frases)
    return d


def salvar(d: dict) -> str:
    from plugins._comum import pasta_jarvis
    arq = pasta_jarvis("Rap") / f"rap_{d['semana']}.txt"
    arq.write_text(f"{d['titulo']}\n(BPM sugerido: {d.get('bpm', 90)})\n\n" + "\n".join(d["versos"]) + "\n", encoding="utf-8")
    return str(arq)


def passo(player) -> None:
    agora = time.localtime()
    raps = carregar("raps", [])
    if agora.tm_wday == 6 and agora.tm_hour >= 18 and (not raps or raps[-1]["semana"] != date.today().isoformat()):
        d = escrever()
        salvar(d)
        guardar("raps", (raps + [d])[-60:])
        from plugins._comum import avisar, mostrar
        mostrar(player, f"RAP DA SEMANA — {d['titulo'].upper()}", "\n".join(d["versos"]))
        avisar(player, f"Saiu o rap da semana: '{d['titulo']}'. Está no painel.", "RAP")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("rap_semana", lambda: passo(player), a_cada_s=1800, primeira_em_s=200)


def _go(p, pl):
    a, raps = p["action"], carregar("raps", [])
    from plugins._comum import mostrar
    if a == "todos":
        return "\n".join(f"{r['semana']}: {r['titulo']}" for r in raps) or "Ainda não escrevi nenhum rap."
    if a == "ultimo":
        if not raps:
            return "Ainda não escrevi nenhum rap. Diga 'faz o rap da semana'."
        mostrar(pl, f"RAP — {raps[-1]['titulo'].upper()}", "\n".join(raps[-1]["versos"]))
        return f"{raps[-1]['titulo']}:\n" + "\n".join(raps[-1]["versos"])
    d = escrever(str(p.get("estilo") or "boom bap"))
    arq = salvar(d)
    guardar("raps", (raps + [d])[-60:])
    mostrar(pl, f"RAP DA SEMANA — {d['titulo'].upper()}", "\n".join(d["versos"]))
    return f"{d['titulo']} (BPM {d.get('bpm', 90)}):\n" + "\n".join(d["versos"]) + f"\n\nSalvo em {arq}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("escrever ultimo todos".split(), _go), player, "Rap da semana")
