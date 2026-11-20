"""
Assistente de viagem (fork PT-BR 2.11).

Ajuda a planejar: lista do que levar (pelo tipo de viagem e pelos dias), diferença
de fuso, uma noção de câmbio e, com a chave do Gemini, um roteiro dia a dia.

    "Jarvis, vou 5 dias pra praia em Salvador, monta a lista do que levar."
    "Jarvis, que horas são em Lisboa agora?"       (fuso)
    "Jarvis, monta um roteiro de 3 dias em São Paulo."
    "Jarvis, quanto é 100 dólares em real?"        (usa a cotação do briefing, se tiver)

A lista do que levar e o fuso funcionam sem internet. O roteiro usa o cérebro.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from plugins._comum import mostrar, num

PLUGIN = {
    "name": "assistente_viagem",
    "brief": "Travel helper: packing list by trip type+days, timezone difference, rough currency, AI day itinerary.",
    "description": (
        "Helps plan a trip. action: 'mala'/'lista' (what to pack — destino, dias, tipo like praia/frio/trabalho/"
        "trilha/cidade), 'fuso' (time difference / what time it is in a place — lugar), 'roteiro' (AI day-by-day "
        "itinerary — destino, dias), 'cambio' (rough currency conversion — valor, de, para). Use for 'o que levar "
        "pra X dias em Y', 'que horas são em Lisboa', 'monta um roteiro de N dias em Z', 'quanto é X dólares em "
        "real'. The packing list and timezone work offline; the itinerary needs Gemini."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mala | fuso | roteiro | cambio"},
            "destino": {"type": "STRING"}, "dias": {"type": "NUMBER"}, "tipo": {"type": "STRING",
                "description": "praia | frio | trabalho | trilha | cidade (optional, guessed from the request)"},
            "lugar": {"type": "STRING", "description": "city/country for 'fuso'"},
            "valor": {"type": "NUMBER"}, "de": {"type": "STRING"}, "para": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

# fusos (UTC) de lugares comuns — chave sem acento
FUSOS = {
    "lisboa": 0, "portugal": 0, "porto": 0, "londres": 0, "reino unido": 0, "madri": 1, "madrid": 1, "espanha": 1,
    "paris": 1, "franca": 1, "roma": 1, "italia": 1, "berlim": 1, "alemanha": 1, "nova york": -5, "new york": -5,
    "eua": -5, "estados unidos": -5, "miami": -5, "orlando": -5, "los angeles": -8, "california": -8, "toquio": 9,
    "japao": 9, "china": 8, "pequim": 8, "dubai": 4, "india": 5, "australia": 10, "sidney": 10, "buenos aires": -3,
    "argentina": -3, "chile": -4, "santiago": -4, "mexico": -6, "cidade do mexico": -6, "canada": -5, "toronto": -5,
    "brasilia": -3, "brasil": -3, "sao paulo": -3, "rio de janeiro": -3,
}
MOEDAS = {"dolar": "USD", "dolares": "USD", "usd": "USD", "euro": "EUR", "euros": "EUR", "eur": "EUR",
          "real": "BRL", "reais": "BRL", "brl": "BRL", "libra": "GBP", "libras": "GBP", "peso": "ARS"}
# cotações aproximadas de reserva (atualizadas pela cotação real do briefing quando houver)
APROX = {"USD": 5.4, "EUR": 5.9, "GBP": 6.9, "ARS": 0.005, "BRL": 1.0}

BASE_MALA = ["documento (RG/passaporte)", "dinheiro e cartão", "celular e carregador", "fones de ouvido",
             "escova e pasta de dente", "desodorante", "remédios de sempre", "carregador portátil"]
POR_TIPO = {
    "praia": ["roupa de banho", "protetor solar", "óculos de sol", "chinelo", "boné", "toalha de praia", "repelente"],
    "frio": ["casaco pesado", "blusa de frio", "touca e luva", "cachecol", "meias grossas", "hidratante labial"],
    "trabalho": ["roupa social", "notebook e carregador", "crachá/credencial", "bloco e caneta", "cabo e adaptador"],
    "trilha": ["tênis/bota de trilha", "mochila", "garrafa de água", "capa de chuva", "lanterna", "kit primeiros "
               "socorros", "repelente"],
    "cidade": ["tênis confortável", "guarda-chuva pequeno", "mochila pequena", "power bank"],
}
PALAVRAS_TIPO = [("praia", r"praia|litoral|mar\b|salvador|maceio|fortaleza|caribe|cancun"),
                 ("frio", r"frio|neve|serra|gramado|campos do jord|inverno|europa"),
                 ("trabalho", r"trabalho|neg[óo]cio|confer[êe]ncia|congresso|reuni[ãa]o|evento"),
                 ("trilha", r"trilha|acampar|camping|montanha|cachoeira|ecoturismo")]


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── pura ───────────────────────────────────────────────────────────────────────
def tipo_de(destino: str, pedido: str = "") -> str:
    t = dobrar(destino) + " " + dobrar(pedido)
    for nome, rx in PALAVRAS_TIPO:
        if re.search(rx, t):
            return nome
    return "cidade"


def lista_mala(tipo: str, dias: int) -> list[str]:
    """Itens a levar pelo tipo e pela quantidade de dias (puro)."""
    dias = max(1, min(60, int(dias or 1)))
    itens = list(BASE_MALA)
    camisetas = min(dias, 10)
    roupa = [f"{camisetas} camisetas/blusas", f"{min(dias, 7)} mudas de roupa íntima", f"{min(dias, 7)} pares de meia"]
    if dias >= 4:
        roupa.append("sabão/lavar roupa no meio da viagem")
    itens += roupa + POR_TIPO.get(tipo, POR_TIPO["cidade"])
    return itens


def offset_de(lugar: str):
    l = dobrar(lugar).strip()
    if l in FUSOS:
        return FUSOS[l]
    for nome, off in FUSOS.items():
        if nome in l or l in nome:
            return off
    return None


def hora_no_lugar(lugar: str, agora_utc: datetime):
    off = offset_de(lugar)
    if off is None:
        return None
    return agora_utc + timedelta(hours=off)


def frase_fuso(lugar: str, agora_local: datetime, off_local_h: float) -> str:
    agora_utc = agora_local - timedelta(hours=off_local_h)
    off = offset_de(lugar)
    if off is None:
        return (f"Não tenho o fuso de “{lugar}” na memória. Me diga outro lugar conhecido (Lisboa, Nova York, "
                "Tóquio…) ou peça pra eu pesquisar.")
    la = agora_utc + timedelta(hours=off)
    dif = off - off_local_h
    sinal = "na mesma hora que aqui" if abs(dif) < 0.5 else (f"{abs(dif):.0f}h à frente" if dif > 0
                                                             else f"{abs(dif):.0f}h atrás")
    return f"Em {lugar} agora são {la:%H:%M} ({sinal} do seu horário)."


def converter(valor: float, de: str, para: str, cotacoes: dict | None = None) -> tuple[float, str, str] | None:
    """valor em `de` → `para` (puro). Usa cotações passadas; senão as aproximadas. None se não reconhecer."""
    c = dict(APROX)
    c.update(cotacoes or {})
    md = MOEDAS.get(dobrar(de).strip())
    mp = MOEDAS.get(dobrar(para).strip()) or "BRL"
    if not md or md not in c or mp not in c:
        return None
    em_reais = float(valor) * c[md]
    return em_reais / c[mp], md, mp


# ── cotação real (do briefing, se existir) ───────────────────────────────────
def _cotacoes_reais() -> dict:
    import sys
    try:
        mod = sys.modules.get("plugins.briefing_br")
        fn = getattr(mod, "cotacao_usd", None) if mod else None
        if callable(fn):
            v = float(fn())
            if v > 0:
                return {"USD": v}
    except Exception:
        pass
    return {}


# ── ações ──────────────────────────────────────────────────────────────────────
def _mala(destino: str, dias, tipo: str, player) -> str:
    tipo = dobrar(tipo).strip() or tipo_de(destino, destino)
    if tipo not in POR_TIPO:
        tipo = tipo_de(tipo, destino)
    d = int(num(dias, 0)) or _dias_do_texto(destino) or 3
    itens = lista_mala(tipo, d)
    mostrar(player, f"MALA · {destino or tipo} ({d} dias)", "\n".join(f"□ {i}" for i in itens))
    return (f"Lista pra {d} dias ({tipo}){' em ' + destino if destino else ''}: {len(itens)} itens, mostrei na "
            f"tela. Quer que eu ajuste pra algum detalhe (bebê, pet, academia)?")


def _dias_do_texto(texto: str) -> int:
    m = re.search(r"(\d+)\s*dias?", dobrar(texto))
    return int(m.group(1)) if m else 0


def _fuso(lugar: str) -> str:
    agora = datetime.now()
    try:
        off_local = datetime.now().astimezone().utcoffset().total_seconds() / 3600
    except Exception:
        off_local = -3.0        # Brasília como padrão
    return frase_fuso(lugar, agora, off_local)


def _roteiro(destino: str, dias) -> str:
    d = int(num(dias, 0)) or _dias_do_texto(destino) or 3
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return (f"Pra montar o roteiro de {destino} eu preciso do cérebro (Gemini) ligado. Mas já posso fazer a "
                    "lista do que levar sem internet — quer?")
    except Exception:
        pass
    return (f"[VIAGEM] Monte um roteiro de {d} dias em {destino or 'destino'}, em português do Brasil. Por dia: "
            "manhã, tarde e noite, com 1 ou 2 lugares cada e uma dica de comida típica. Seja realista com distâncias. "
            "No máximo uma tela. Responda direto ao usuário; não chame nenhuma ferramenta.")


def _cambio(valor, de: str, para: str) -> str:
    v = num(valor, 0)
    if v <= 0:
        return "Quanto você quer converter? (ex.: 100 dólares em real)"
    r = converter(v, de or "dolar", para or "real", _cotacoes_reais())
    if not r:
        return "Trabalho com dólar, euro, libra, peso e real. Qual é a conversão?"
    convertido, md, mp = r
    tem_real = "USD" in _cotacoes_reais()
    nota = "" if tem_real else " (cotação aproximada; pra valor exato eu pesquiso na hora)"
    return f"{v:g} {md} ≈ {convertido:,.2f} {mp}{nota}.".replace(",", "X").replace(".", ",").replace("X", ".")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "mala").strip()
    destino = str(p.get("destino") or p.get("lugar") or "")
    try:
        if acao in ("mala", "lista", "levar", "bagagem"):
            return _mala(destino, p.get("dias"), str(p.get("tipo") or ""), player)
        if acao in ("fuso", "hora", "horario", "fuso_horario"):
            return _fuso(str(p.get("lugar") or p.get("destino") or ""))
        if acao in ("roteiro", "itinerario", "programacao"):
            return _roteiro(destino, p.get("dias"))
        if acao in ("cambio", "converter", "moeda", "cotacao"):
            return _cambio(p.get("valor"), str(p.get("de") or ""), str(p.get("para") or ""))
        return _mala(destino, p.get("dias"), str(p.get("tipo") or ""), player)
    except Exception as e:
        return f"O assistente de viagem falhou: {e}"
