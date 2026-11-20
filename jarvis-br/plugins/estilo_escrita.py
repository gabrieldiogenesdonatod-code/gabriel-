"""
Responder no seu estilo (fork PT-BR 1.6).

O JARVIS aprende COMO você escreve — tamanho das mensagens, gírias e
abreviações ("vc", "tbm", "kkk"), emojis, pontuação, maiúsculas — a partir de
mensagens suas: uma conversa exportada do WhatsApp, um texto que você cola ou
os pedidos que você digita para ele. Depois sugere respostas que parecem suas.

    "Jarvis, aprende meu jeito de escrever com a conversa exportada do WhatsApp"
        (no WhatsApp: conversa → ⋮ → Mais → Exportar conversa → sem mídia → salve no PC)
    "Jarvis, como eu responderia: 'bora no cinema amanhã?'"
    "Jarvis, como é o meu estilo?"

O perfil fica em memory/estilo_escrita.json (só números, palavras frequentes e
até 40 exemplos curtos). O "eu virtual" também usa este perfil.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from pathlib import Path

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, nome_usuario

PLUGIN = {
    "name": "estilo_escrita",
    "brief": "Learns how the user writes (WhatsApp export, pasted text) and suggests replies in their style.",
    "description": (
        "Writes like the user: action='aprender' with arquivo (WhatsApp exported chat .txt; autor = the user's name in "
        "it) or texto (messages written by the user); 'sugerir' with mensagem (a message the user received; returns "
        "2-3 replies in the user's style); 'perfil' (describe the style); 'esquecer'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "aprender | sugerir | perfil | esquecer"},
                       "arquivo": {"type": "STRING"}, "autor": {"type": "STRING"}, "texto": {"type": "STRING"},
                       "mensagem": {"type": "STRING"}},
        "required": [],
    },
}

ARQ = MEMORIA / "estilo_escrita.json"
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_GIRIAS = ["vc", "vcs", "tbm", "tb", "pq", "q", "kkk", "kkkk", "rs", "mano", "mn", "slk", "pdp", "tmj", "blz", "vlw",
           "eae", "eai", "fmz", "fml", "sla", "nd", "ngm", "td", "msm", "dps", "hj", "amn", "bora", "tlgd", "pfv", "obg",
           "dmr", "top", "show", "massa", "uai", "trem", "sô", "ss", "n", "ctz", "aff", "oxe", "véi", "vei", "parça"]

# linhas do export do WhatsApp (Android e iPhone)
_LINHA = re.compile(r"^\[?(\d{1,2}/\d{1,2}/\d{2,4})[,\s]+(\d{1,2}:\d{2})(?::\d{2})?\]?\s*[-–]?\s*([^:]{1,60}):\s(.*)$")


def ler_whatsapp(texto: str) -> list[dict]:
    """Export do WhatsApp → [{data, hora, autor, texto}] (pura). Linhas que continuam a anterior são juntadas."""
    msgs: list[dict] = []
    for linha in (texto or "").splitlines():
        linha = linha.replace("‎", "").replace(" ", " ").strip()
        m = _LINHA.match(linha)
        if m:
            msgs.append({"data": m.group(1), "hora": m.group(2), "autor": m.group(3).strip(), "texto": m.group(4).strip()})
        elif msgs and linha:
            msgs[-1]["texto"] += "\n" + linha
    return [x for x in msgs if not re.fullmatch(r"<(Mídia|Media) (oculta|omitted)>|.*(arquivo de mídia oculto|omitted).*",
                                                  x["texto"], re.I)]


def perfil_de(mensagens: list[str]) -> dict:
    """Números do estilo (puro)."""
    msgs = [m.strip() for m in mensagens if m and m.strip() and not m.startswith("http")]
    if not msgs:
        return {}
    palavras = [w for m in msgs for w in re.findall(r"[\wÀ-ÿ']+", m.lower())]
    giria = Counter(w for w in palavras if w in _GIRIAS or re.fullmatch(r"k{3,}|(rs)+|ha(ha)+|hue+", w))
    emojis = Counter(e for m in msgs for e in _EMOJI.findall(m))
    return {
        "mensagens": len(msgs),
        "tamanho_medio": round(statistics.mean(len(m.split()) for m in msgs), 1),
        "comeca_maiuscula": round(sum(m[0].isupper() for m in msgs) / len(msgs), 2),
        "termina_ponto": round(sum(m.rstrip()[-1:] in ".!?" for m in msgs) / len(msgs), 2),
        "exclamacoes": round(sum(m.count("!") for m in msgs) / len(msgs), 2),
        "girias": [w for w, _n in giria.most_common(12)],
        "emojis": [e for e, _n in emojis.most_common(8)],
        "usa_emoji": round(sum(bool(_EMOJI.search(m)) for m in msgs) / len(msgs), 2),
        "exemplos": [m for m in msgs if 2 <= len(m.split()) <= 25][-40:],
    }


def descrever(p: dict) -> str:
    if not p:
        return "Ainda não sei como você escreve."
    partes = [f"mensagens de {p['tamanho_medio']:.0f} palavras em média",
              "quase sempre começa com minúscula" if p["comeca_maiuscula"] < 0.3 else
              "começa com maiúscula" if p["comeca_maiuscula"] > 0.7 else "às vezes com maiúscula",
              "quase nunca põe ponto final" if p["termina_ponto"] < 0.25 else "costuma pontuar",
              ("usa " + ", ".join(p["girias"][:6])) if p["girias"] else "quase sem gírias",
              ("emojis: " + " ".join(p["emojis"][:5])) if p["usa_emoji"] > 0.1 else "pouco emoji"]
    return "; ".join(partes) + "."


def carregar() -> dict:
    return ler_json(ARQ, {}) or {}


def aprender(mensagens: list[str]) -> dict:
    antigo = carregar()
    todas = (antigo.get("exemplos") or []) + mensagens
    p = perfil_de(todas)
    p["mensagens"] = (antigo.get("mensagens") or 0) + len(mensagens)
    gravar_json(ARQ, p)
    return p


def _suas(msgs: list[dict], autor: str) -> list[str]:
    autores = Counter(m["autor"] for m in msgs)
    if autor:
        alvo = next((a for a in autores if autor.lower() in a.lower()), "")
    else:
        nome = nome_usuario().lower()
        alvo = next((a for a in autores if nome and nome.split()[0] in a.lower()), "")
        alvo = alvo or next((a for a in autores if a.lower() in ("você", "voce", "you")), "")
    return [m["texto"] for m in msgs if m["autor"] == alvo] if alvo else []


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "perfil").lower()
    try:
        if acao == "aprender":
            if p.get("arquivo"):
                arq = Path(str(p["arquivo"]).strip().strip('"')).expanduser()
                if not arq.is_file():
                    return f"Não achei o arquivo {arq}."
                msgs = ler_whatsapp(arq.read_text(encoding="utf-8", errors="replace"))
                minhas = _suas(msgs, str(p.get("autor") or ""))
                if not minhas:
                    autores = ", ".join(a for a, _n in Counter(m["autor"] for m in msgs).most_common(6))
                    return f"Qual destes nomes é você na conversa? {autores}."
            else:
                minhas = [x for x in re.split(r"\n+", str(p.get("texto") or "")) if x.strip()]
                if not minhas:
                    return "Mande um arquivo exportado do WhatsApp ou cole mensagens suas."
            perfil = aprender(minhas)
            return f"Aprendi com {len(minhas)} mensagem(ns) suas. Seu estilo: {descrever(perfil)}"
        perfil = carregar()
        if acao == "esquecer":
            gravar_json(ARQ, {})
            return "Esqueci o seu estilo de escrita."
        if acao == "perfil":
            return "Seu estilo: " + descrever(perfil)
        if acao == "sugerir":
            recebida = str(p.get("mensagem") or "").strip()
            if not recebida:
                return "Qual mensagem você recebeu?"
            if not perfil:
                return "Primeiro me ensine como você escreve (uma conversa exportada do WhatsApp serve)."
            from plugins import _ia
            if not _ia.disponivel():
                return f"Sem a chave do Gemini eu não escrevo as respostas, mas lembre do seu estilo: {descrever(perfil)}"
            exemplos = "\n".join(f"- {x}" for x in perfil.get("exemplos", [])[-25:])
            r = _ia.perguntar_json(
                f"Escreva 3 respostas curtas para a mensagem abaixo EXATAMENTE no estilo desta pessoa (mesmo tamanho, "
                f"gírias, emojis, pontuação e maiúsculas). Estilo: {descrever(perfil)}\nExemplos reais dela:\n{exemplos}\n\n"
                f"MENSAGEM RECEBIDA: {recebida}\n"
                'Responda SÓ JSON {"respostas": ["...", "...", "..."]} (uma positiva, uma neutra, uma negativa/adiando).',
                False, 30)
            respostas = [str(x) for x in (r or {}).get("respostas", [])][:3] if isinstance(r, dict) else []
            if not respostas:
                return "Não consegui sugerir agora."
            mostrar(player, "RESPOSTAS NO SEU ESTILO", "\n\n".join(f"{i}. {x}" for i, x in enumerate(respostas, 1)))
            return "Sugestões no seu estilo: " + " | ".join(f"{i}) {x}" for i, x in enumerate(respostas, 1)) + \
                ". Se quiser mandar uma, diga qual e para quem."
        return "Ações: aprender, sugerir, perfil, esquecer."
    except Exception as e:
        return f"O estilo de escrita falhou: {e}"
