"""
Professor de inglês (fork PT-BR 1.6).

Conversa por voz EM INGLÊS, no seu nível, sobre o tema que você quiser. Quando
você erra, ele corrige com gentileza (a frase certa e o porquê, curtinho) e
anota o erro. Depois, os erros viram cartões do modo professor, para revisar
com repetição espaçada.

    "Jarvis, vamos praticar inglês, nível iniciante, sobre games"
    "Jarvis, quais erros eu mais cometo?"        "Jarvis, para o inglês"
    "Jarvis, transforma meus erros em cartões"
"""

from __future__ import annotations

import time
from collections import Counter

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "professor_ingles",
    "brief": "English tutor by voice: converses in English at the user's level, corrects mistakes, turns them into flashcards.",
    "description": (
        "English conversation practice. action='comecar' with nivel (iniciante|intermediario|avancado) + tema; while "
        "practising, every time the user makes a mistake call action='anotar' with errada (user's sentence), certa "
        "(corrected) and regra (short explanation in Portuguese), then keep talking in English; action='erros' lists "
        "frequent mistakes; 'cartoes' turns them into spaced-repetition cards; 'parar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "comecar | anotar | erros | cartoes | parar"},
                       "nivel": {"type": "STRING"}, "tema": {"type": "STRING"}, "errada": {"type": "STRING"},
                       "certa": {"type": "STRING"}, "regra": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "ingles.json"
NIVEIS = {
    "iniciante": "Use very simple English (A1–A2): short sentences, common words, speak slowly; if the user is lost, "
                 "repeat in simpler words and give the key word in Portuguese.",
    "intermediario": "Use natural everyday English (B1–B2); introduce one useful expression per answer.",
    "avancado": "Use fluent, natural English (C1) with idioms; push for longer, more precise answers.",
}


def nivel_de(texto: str) -> str:
    t = (texto or "").lower()
    return "avancado" if "avan" in t or "fluent" in t else "intermediario" if "inter" in t or "medio" in t or "médio" in t \
        else "iniciante"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "comecar").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("erros", [])
        if acao == "comecar":
            nivel, tema = nivel_de(str(p.get("nivel") or "")), str(p.get("tema") or "everyday life")
            d["sessao"] = {"nivel": nivel, "tema": tema, "inicio": time.time()}
            gravar_json(_ARQ, d)
            return (f"[ENGLISH PRACTICE] From now on speak ONLY English with the user about '{tema}'. {NIVEIS[nivel]} "
                    "Ask one question at a time and keep it conversational. When the user makes a grammar, vocabulary or "
                    "pronunciation-related mistake, gently give the correct sentence and a 1-line reason in Portuguese, "
                    "AND call professor_ingles action='anotar' with errada, certa and regra. Start now with a friendly "
                    "greeting and a first question.")
        if acao == "anotar":
            errada, certa = str(p.get("errada") or "").strip(), str(p.get("certa") or "").strip()
            if errada and certa:
                d["erros"].append({"errada": errada, "certa": certa, "regra": str(p.get("regra") or ""), "ts": time.time()})
                d["erros"] = d["erros"][-500:]
                gravar_json(_ARQ, d)
            return "Noted. Continue the conversation in English."
        if acao == "parar":
            s = d.pop("sessao", None)
            gravar_json(_ARQ, d)
            novos = [e for e in d["erros"] if s and e["ts"] >= s.get("inicio", 0)]
            return (f"[FIM DO INGLÊS] Volte a falar português. Nesta conversa anotei {len(novos)} correção(ões). "
                    "Ofereça transformar os erros em cartões de revisão.")
        if acao == "erros":
            if not d["erros"]:
                return "Ainda não anotei erros. Vamos praticar?"
            regras = Counter(e["regra"] for e in d["erros"] if e.get("regra"))
            mostrar(player, "MEUS ERROS EM INGLÊS", "\n\n".join(f"✗ {e['errada']}\n✓ {e['certa']}\n  {e.get('regra', '')}"
                                                                for e in d["erros"][-30:]))
            return f"{len(d['erros'])} correção(ões) anotadas. Os pontos que mais aparecem: " + \
                ("; ".join(r for r, _n in regras.most_common(3)) or "variados") + ". A lista está no painel."
        if acao == "cartoes":
            from plugins import modo_professor
            existentes = {c["pergunta"] for c in modo_professor.carregar()}
            n = 0
            for e in d["erros"][-60:]:
                pergunta = f"Corrija em inglês: \"{e['errada']}\""
                if pergunta not in existentes:
                    modo_professor.adicionar(pergunta, e["certa"] + (f" ({e['regra']})" if e.get("regra") else ""), "inglês")
                    n += 1
            return f"Criei {n} cartão(ões) de inglês no modo professor. Diga 'me pergunta' para revisar."
        return "Ações: comecar, anotar, erros, cartoes, parar."
    except Exception as e:
        return f"O professor de inglês falhou: {e}"
