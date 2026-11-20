"""
Radionovela (fork PT-BR 2.7). Tudo software, grátis.

JARVIS, FRIDAY e um narrador interpretam uma história em capítulos, cada um com
a sua voz, efeitos sonoros (porta, trovão, suspense) e vinheta. No fim de cada
capítulo aparecem 2 ou 3 caminhos, e você decide o rumo.

    "Jarvis, começa uma radionovela de ficção científica"   → capítulo 1
    "Opção 2" / "a radionovela continua com a opção 1"      → guarda a escolha e toca o próximo
    "Próximo capítulo da radionovela"                       → toca o de hoje
    "Resumo da radionovela"                                 → o que aconteceu até aqui
Com "capítulo diário" ligado, ele avisa (sem interromper) quando sai o capítulo do dia.
Estado em memory/radionovela.json.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, num, sim

PLUGIN = {
    "name": "radionovela",
    "brief": "Radio soap opera in daily chapters with JARVIS, FRIDAY and a narrator, sound effects, and the user "
             "chooses what happens next.",
    "description": (
        "Radio drama in chapters, voiced by JARVIS, FRIDAY and a NARRADOR with effects. action: 'nova' (tema: "
        "start a new story, plays chapter 1), 'capitulo' (play the next chapter), 'escolher' (opcao number or "
        "text: choose the path at the end of the chapter, then plays the next one), 'resumo' (story so far), "
        "'parar'. After a chapter, stay silent while it plays."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "tema": {"type": "STRING"}, "opcao": {"type": "STRING"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "radionovela",
    "title": "Radionovela",
    "fields": [
        {"key": "diario", "label": "Avisar quando sair o capítulo do dia", "type": "toggle", "default": True},
        {"key": "hora", "label": "Horário do capítulo do dia", "type": "text", "default": "20:30"},
        {"key": "falas", "label": "Falas por capítulo", "type": "text", "default": "14"},
    ],
}

ARQ = MEMORIA / "radionovela.json"
ELENCO = ["NARRADOR", "JARVIS", "FRIDAY"]
EFEITOS = ("porta", "trovao", "suspense", "vinheta", "whoosh")
_iniciou = threading.Event()


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("capitulos", [])
    d.setdefault("opcoes", [])
    return d


def escolha_de(texto: str, opcoes: list[str]) -> int | None:
    """Pura: 'opção 2', '2', 'a segunda', ou parte do texto → índice."""
    t = str(texto or "").lower().strip()
    if not opcoes:
        return None
    m = re.search(r"\d+", t)
    if m and 1 <= int(m.group()) <= len(opcoes):
        return int(m.group()) - 1
    for i, palavra in enumerate(("primeir", "segund", "terceir")):
        if palavra in t and i < len(opcoes):
            return i
    for i, o in enumerate(opcoes):
        if t and len(t) > 3 and t in o.lower():
            return i
    return None


def prompt_capitulo(d: dict, n_falas: int = 14) -> str:
    """Pura: o pedido do próximo capítulo."""
    caps = d.get("capitulos") or []
    n = len(caps) + 1
    anteriores = "\n".join(f"Capítulo {i + 1} ({c.get('titulo', '')}): {c.get('resumo', '')}"
                           + (f" → o ouvinte escolheu: {c['escolha']}" if c.get("escolha") else "")
                           for i, c in enumerate(caps[-8:]))
    return (f"Escreva o CAPÍTULO {n} de uma radionovela em português do Brasil. Tema/gênero: {d.get('tema')}. "
            f"Personagens/vozes: NARRADOR (narra e faz os outros personagens da história), JARVIS e FRIDAY (são "
            f"personagens da história, com as personalidades de sempre).\n"
            + (f"Até aqui:\n{anteriores}\n" if anteriores else "Este é o primeiro capítulo: apresente o mundo e o "
                                                               "conflito.\n") +
            f"Use cerca de {n_falas} falas curtas (no máximo 2 frases cada), suspense, humor leve, e termine num "
            f"gancho com 2 ou 3 caminhos para o ouvinte escolher. Efeitos possíveis (opcionais, no máximo 4): "
            f"{', '.join(EFEITOS)}.\nResponda SÓ JSON: "
            '{"titulo": "...", "falas": [{"quem": "NARRADOR", "texto": "...", "efeito": "trovao"}], '
            '"opcoes": ["...", "..."], "resumo": "2 frases do que aconteceu"}')


def validar(cap) -> dict | None:
    """Pura: limpa o JSON do modelo."""
    if not isinstance(cap, dict):
        return None
    falas = []
    for f in cap.get("falas") or []:
        if not isinstance(f, dict) or not str(f.get("texto") or "").strip():
            continue
        quem = str(f.get("quem") or "NARRADOR").upper()
        quem = quem if quem in ELENCO else "NARRADOR"
        item = {"quem": quem, "texto": str(f["texto"]).strip()[:400]}
        if f.get("efeito") in EFEITOS:
            item["efeito"] = f["efeito"]
        falas.append(item)
    if len(falas) < 3:
        return None
    opcoes = [str(o).strip()[:160] for o in (cap.get("opcoes") or []) if str(o).strip()][:3]
    return {"titulo": str(cap.get("titulo") or "Sem título")[:80], "falas": falas, "opcoes": opcoes,
            "resumo": str(cap.get("resumo") or "")[:400]}


def capitulo() -> str:
    from plugins import _dupla as D
    from plugins import _ia
    if D.rodando():
        return "Já tem uma cena tocando."
    d = dados()
    if not d.get("tema"):
        return "Ainda não há radionovela. Diga 'começa uma radionovela de (gênero)'."
    if d.get("opcoes") and not d.get("escolha_pendente"):
        return "O capítulo anterior terminou com uma escolha. Diga 'opção 1', 'opção 2'…"
    n_falas = int(num(cfg("radionovela", PLUGIN_SETTINGS).get("falas"), 14) or 14)
    cap = validar(_ia.perguntar_json(prompt_capitulo(d, n_falas), inteligente=True, segundos=60))
    if not cap:
        return "Não consegui escrever o capítulo agora (preciso da chave do Gemini e de internet)."
    n = len(d["capitulos"]) + 1
    falas = [{"quem": "NARRADOR", "texto": f"{d.get('nome', 'A radionovela')}. Capítulo {n}: {cap['titulo']}.",
              "efeito": "vinheta"}] + cap["falas"]
    d["capitulos"].append({"titulo": cap["titulo"], "resumo": cap["resumo"], "data": date.today().isoformat(),
                           "opcoes": cap["opcoes"]})
    d["opcoes"] = cap["opcoes"]
    d.pop("escolha_pendente", None)
    d["ultimo_dia"] = date.today().isoformat()
    gravar_json(ARQ, d)
    D.encenar(falas, f"Radionovela · Capítulo {n}", ELENCO, opcoes=cap["opcoes"],
              rodape="Diga 'opção 1', 'opção 2'… para escolher o rumo")
    mostrar(None, f"RADIONOVELA · CAP. {n}", D.texto_falas(falas) + "\n\nEscolhas:\n" +
            "\n".join(f"{i + 1}. {o}" for i, o in enumerate(cap["opcoes"])))
    return f"Tocando o capítulo {n}, '{cap['titulo']}'. Fique em silêncio; no fim o senhor escolhe o rumo."


def nova(tema: str) -> str:
    tema = tema.strip() or "ficção científica com mistério"
    gravar_json(ARQ, {"tema": tema, "nome": f"Radionovela: {tema[:40]}", "capitulos": [], "opcoes": [],
                      "criada": datetime.now().isoformat(timespec="minutes")})
    return capitulo()


def escolher(opcao: str) -> str:
    d = dados()
    i = escolha_de(opcao, d.get("opcoes") or [])
    if i is None:
        if not d.get("opcoes"):
            return capitulo()
        return "Não entendi a escolha. As opções são: " + "; ".join(
            f"{k + 1}. {o}" for k, o in enumerate(d["opcoes"]))
    d["capitulos"][-1]["escolha"] = d["opcoes"][i]
    d["escolha_pendente"] = True
    gravar_json(ARQ, d)
    return capitulo()


def resumo() -> str:
    d = dados()
    if not d.get("capitulos"):
        return "Nenhum capítulo ainda."
    return f"{d.get('nome')}: " + " ".join(
        f"Capítulo {i + 1}: {c.get('resumo', '')}" + (f" (o senhor escolheu: {c['escolha']})" if c.get("escolha")
                                                      else "")
        for i, c in enumerate(d["capitulos"][-6:]))


def _laco(player) -> None:
    time.sleep(90)
    while True:
        try:
            c = cfg("radionovela", PLUGIN_SETTINGS)
            d = dados()
            hora = str(c.get("hora") or "20:30")
            if sim(c.get("diario", True)) and d.get("tema") and d.get("aviso_dia") != date.today().isoformat() \
                    and d.get("ultimo_dia") != date.today().isoformat() and datetime.now().strftime("%H:%M") >= hora:
                d["aviso_dia"] = date.today().isoformat()
                gravar_json(ARQ, d)
                from plugins._notificar import notificar
                notificar(player, f"Saiu o capítulo {len(d['capitulos']) + 1} da radionovela. Diga 'próximo "
                                  "capítulo' quando quiser ouvir.", titulo="Radionovela", etiqueta="radionovela",
                          prioridade="baixa")
        except Exception as e:
            print(f"[Radionovela] {e}")
        time.sleep(600)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="radionovela").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "").lower()
    try:
        if acao == "nova":
            return nova(str(p.get("tema") or ""))
        if acao in ("capitulo", "continuar", "proximo"):
            return capitulo()
        if acao == "escolher":
            return escolher(str(p.get("opcao") or ""))
        if acao == "resumo":
            return resumo()
        if acao == "parar":
            from plugins import _dupla as D
            D.parar()
            return "Radionovela pausada."
        return "Ações: nova, capitulo, escolher, resumo, parar."
    except Exception as e:
        return f"Radionovela falhou: {e}"
