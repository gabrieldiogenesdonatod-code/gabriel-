"""
Modo professor — repetição espaçada (fork PT-BR 1.5).

Você estuda; o JARVIS faz perguntas em dias diferentes, cada vez mais
espaçadas (algoritmo SM-2, o dos aplicativos de flashcard): errou, a pergunta
volta amanhã; acertou fácil, volta daqui a semanas. Assim o conteúdo fixa.

    "Jarvis, anota pra revisar: o que é PWM? Resposta: variar a largura do pulso…"
    "Jarvis, cria perguntas sobre o arquivo anotacoes_esp32.md"   (com IA)
    "Jarvis, me faz uma revisão"   → ele pergunta, você responde falando,
                                     ele corrige e agenda a próxima
    "Jarvis, como estão as revisões?"

Por volta das 19h30 (configurável), se houver revisões do dia e você estiver
no PC, ele oferece uma vez. Cartões em memory/professor.json.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, cfg, falar, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "modo_professor",
    "brief": "Spaced-repetition tutor: add/generate flashcards, quiz the user by voice, schedule reviews (SM-2).",
    "description": (
        "Teacher mode with spaced repetition. action='adicionar' (pergunta, resposta, tema); 'gerar' with tema or "
        "arquivo or texto (AI creates cards); 'proxima' returns the next due question — ask it to the user; then "
        "'responder' with resposta (the user's answer, verbatim) or nota (errei|difícil|bom|fácil) to grade and "
        "reschedule; 'status' (due today, stats); 'apagar' with tema."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "adicionar | gerar | proxima | responder | status | apagar"},
            "pergunta": {"type": "STRING"}, "resposta": {"type": "STRING"}, "tema": {"type": "STRING"},
            "arquivo": {"type": "STRING"}, "texto": {"type": "STRING"}, "nota": {"type": "STRING"},
            "quantidade": {"type": "INTEGER"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "modo_professor",
    "title": "Modo professor",
    "fields": [{"key": "hora", "label": "Oferecer revisões por volta de (HH:MM)", "type": "text", "default": "19:30"}],
}

_ARQ = MEMORIA / "professor.json"
_atual = {"id": None}
_iniciado = threading.Event()


# ── SM-2 (puro) ────────────────────────────────────────────────────────────────
def agendar(card: dict, q: int, hoje: date | None = None) -> dict:
    """q: 0–5 (0–2 errou, 3 difícil, 4 bom, 5 fácil). Devolve o cartão atualizado."""
    hoje = hoje or date.today()
    ef = float(card.get("ef", 2.5))
    rep = int(card.get("rep", 0))
    intervalo = int(card.get("intervalo", 0))
    if q < 3:
        rep, intervalo = 0, 1
    else:
        rep += 1
        intervalo = 1 if rep == 1 else 6 if rep == 2 else max(1, round(intervalo * ef))
    ef = max(1.3, ef + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    card.update(ef=round(ef, 3), rep=rep, intervalo=intervalo, proxima=(hoje + timedelta(days=intervalo)).isoformat())
    card.setdefault("historico", []).append([hoje.isoformat(), q])
    return card


def nota_de_texto(t: str) -> int | None:
    t = (t or "").lower()
    for chaves, q in ((("errei", "não sei", "nao sei", "esqueci"), 1), (("difícil", "dificil", "quase"), 3),
                      (("fácil", "facil", "moleza"), 5), (("bom", "acertei", "certo", "sei"), 4)):
        if any(c in t for c in chaves):
            return q
    return None


def nota_local(resposta: str, esperada: str) -> int:
    """Sem IA: quantas palavras importantes da resposta certa apareceram."""
    def palavras(x):
        return {w for w in re.findall(r"\w{4,}", x.lower())}
    alvo = palavras(esperada)
    if not alvo:
        return 3
    acerto = len(alvo & palavras(resposta)) / len(alvo)
    return 5 if acerto >= 0.8 else 4 if acerto >= 0.5 else 3 if acerto >= 0.3 else 1


# ── cartões ────────────────────────────────────────────────────────────────────
def carregar() -> list[dict]:
    d = ler_json(_ARQ, [])
    return d if isinstance(d, list) else []


def devidos(cards: list[dict], hoje: date | None = None) -> list[dict]:
    hoje = (hoje or date.today()).isoformat()
    return sorted((c for c in cards if c.get("proxima", hoje) <= hoje), key=lambda c: (c.get("proxima", ""), c["id"]))


def adicionar(pergunta: str, resposta: str, tema: str = "") -> dict:
    cards = carregar()
    c = {"id": str(max([int(x["id"]) for x in cards] + [0]) + 1), "pergunta": pergunta.strip(),
         "resposta": resposta.strip(), "tema": tema.strip() or "geral", "criado": date.today().isoformat(),
         "proxima": date.today().isoformat(), "ef": 2.5, "rep": 0, "intervalo": 0}
    cards.append(c)
    gravar_json(_ARQ, cards)
    return c


def gerar(tema: str = "", texto: str = "", quantidade: int = 8) -> list[dict]:
    from plugins import _ia
    if not _ia.disponivel():
        pares = re.findall(r"(?:^|\n)\s*(?:P|Pergunta)\s*:\s*(.+?)\s*\n\s*(?:R|Resposta)\s*:\s*(.+?)(?=\n\s*(?:P|Pergunta)\s*:|\Z)",
                           texto or "", re.S | re.I)
        return [adicionar(p, r, tema) for p, r in pares]
    r = _ia.perguntar_json(
        f"Crie {quantidade} cartões de estudo (pergunta curta e resposta objetiva, em português do Brasil) "
        + (f"sobre: {tema}. " if tema else "") + ("Baseie-se SÓ neste conteúdo:\n" + texto[:12000] if texto else "")
        + '\nResponda SÓ JSON: {"cartoes": [{"pergunta": "...", "resposta": "..."}]}', True, 60)
    lista = (r or {}).get("cartoes", []) if isinstance(r, dict) else []
    return [adicionar(c["pergunta"], c["resposta"], tema) for c in lista if c.get("pergunta") and c.get("resposta")]


def corrigir(card: dict, resposta: str) -> tuple[int, str]:
    from plugins import _ia
    if _ia.disponivel():
        r = _ia.perguntar_json(
            f"Pergunta: {card['pergunta']}\nResposta esperada: {card['resposta']}\nResposta do aluno: {resposta}\n"
            'Avalie de 0 a 5 (0-2 errou, 3 difícil/parcial, 4 certo, 5 perfeito). Responda SÓ JSON: '
            '{"nota": 0-5, "comentario": "uma frase em pt-BR, corrigindo se preciso"}', False, 20)
        if isinstance(r, dict) and str(r.get("nota", "")).isdigit():
            return int(r["nota"]), str(r.get("comentario") or "")
    q = nota_local(resposta, card["resposta"])
    return q, ("" if q >= 4 else f"A resposta esperada era: {card['resposta']}.")


def _laco(player) -> None:
    time.sleep(300)
    ofereceu = ""
    while True:
        try:
            agora = datetime.now()
            hh, mm = (str(cfg("modo_professor", PLUGIN_SETTINGS).get("hora") or "19:30") + ":00").split(":")[:2]
            alvo = agora.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            pend = devidos(carregar())
            if pend and ofereceu != agora.date().isoformat() and alvo <= agora <= alvo + timedelta(hours=2):
                from plugins.linha_do_tempo import ocioso_segundos
                if ocioso_segundos() < 300:
                    ofereceu = agora.date().isoformat()
                    falar(player, f"[PROFESSOR] Há {len(pend)} revisão(ões) de estudo para hoje. Pergunte em UMA frase "
                                  "se o usuário quer fazer agora; se ele aceitar, chame modo_professor com "
                                  "action='proxima'.")
        except Exception as e:
            print(f"[Professor] {e}")
        time.sleep(300)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="modo_professor").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "proxima").lower()
    try:
        if acao == "adicionar":
            if not p.get("pergunta") or not p.get("resposta"):
                return "Preciso da pergunta e da resposta."
            c = adicionar(str(p["pergunta"]), str(p["resposta"]), str(p.get("tema") or ""))
            return f"Anotado (cartão {c['id']}). Pergunto hoje mesmo, na próxima revisão."
        if acao == "gerar":
            texto = str(p.get("texto") or "")
            if p.get("arquivo"):
                from pathlib import Path
                from plugins.habilidades import ler_um
                from plugins.controle_sistema import buscar
                arq = Path(str(p["arquivo"]))
                if not arq.exists():
                    achados = buscar(str(p["arquivo"]), limite=1, segundos=6)
                    arq = achados[0] if achados else arq
                texto = ler_um(arq) if arq.exists() else ""
                if not texto:
                    return f"Não achei o arquivo {p['arquivo']}."
            novos = gerar(str(p.get("tema") or ""), texto, int(p.get("quantidade") or 8))
            if not novos:
                return ("Não consegui criar cartões. Sem IA, mande o texto no formato 'P: pergunta' e 'R: resposta'.")
            return f"Criei {len(novos)} cartão(ões). A primeira revisão é hoje."
        if acao == "proxima":
            pend = devidos(carregar())
            if not pend:
                return "Nenhuma revisão pendente hoje. Bom trabalho!"
            _atual["id"] = pend[0]["id"]
            return (f"[PROFESSOR] Faça esta pergunta ao usuário e espere a resposta dele ({len(pend)} pendente(s)): "
                    f"\"{pend[0]['pergunta']}\". Depois chame modo_professor action='responder' com a resposta dele.")
        if acao == "responder":
            cards = carregar()
            card = next((c for c in cards if c["id"] == _atual["id"]), None) or (devidos(cards) or [None])[0]
            if not card:
                return "Não há pergunta em andamento."
            q = nota_de_texto(str(p.get("nota") or ""))
            comentario = ""
            if q is None:
                q, comentario = corrigir(card, str(p.get("resposta") or ""))
            agendar(card, q)
            gravar_json(_ARQ, cards)
            restam = len(devidos(cards))
            quando = "amanhã" if card["intervalo"] == 1 else f"daqui a {card['intervalo']} dias"
            partes = [f"{'Certo' if q >= 4 else 'Quase' if q == 3 else 'Não foi dessa vez'}.", comentario,
                      f"Volto nessa pergunta {quando}.",
                      f"Ainda há {restam} hoje; quer a próxima?" if restam else "Revisões de hoje concluídas!"]
            return " ".join(x for x in partes if x)
        if acao == "apagar":
            tema = str(p.get("tema") or "").lower()
            cards = carregar()
            restantes = [c for c in cards if tema not in c.get("tema", "").lower()]
            gravar_json(_ARQ, restantes)
            return f"Apaguei {len(cards) - len(restantes)} cartão(ões)."
        cards = carregar()
        if not cards:
            return "Nenhum cartão ainda. Diga 'anota pra revisar' ou 'cria perguntas sobre' um tema ou arquivo."
        hist = [h for c in cards for h in c.get("historico", []) if h[0] >= (date.today() - timedelta(days=7)).isoformat()]
        acertos = sum(1 for h in hist if h[1] >= 4)
        mostrar(player, "MODO PROFESSOR", "\n".join(
            f"[{c['id']}] {c['tema']}: {c['pergunta'][:70]} — próxima {c.get('proxima')}" for c in cards[:60]))
        return (f"{len(cards)} cartão(ões), {len(devidos(cards))} para hoje. "
                + (f"Nos últimos 7 dias você acertou {acertos} de {len(hist)}." if hist else ""))
    except Exception as e:
        return f"O modo professor falhou: {e}"
