"""
Detector de golpe (fork PT-BR 1.6).

Cole (ou dite) um link ou uma mensagem suspeita: o JARVIS analisa sinais de
phishing e dos golpes mais comuns no Brasil — Pix, "troquei de número",
falso banco, falsa entrega, prêmio, código do WhatsApp — e dá o veredito com
os motivos. Com a chave do Gemini, ainda pede uma segunda leitura à IA.

    "Jarvis, isso é golpe? <mensagem ou link>"
    "Jarvis, analisa o que eu copiei"           (lê a área de transferência)

Ele NÃO abre o link: só lê o texto do endereço.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import urlparse

PLUGIN = {
    "name": "detector_golpe",
    "brief": "Scam/phishing detector for links and messages (Brazilian scams: Pix, fake bank, new number, prizes).",
    "description": (
        "Scam detector: analyses a suspicious link or message (texto) for phishing and common Brazilian scams (Pix, "
        "'troquei de número', fake bank/delivery, prizes, WhatsApp code requests) and returns a risk level with "
        "reasons. Without texto it reads the clipboard. Never opens the link."
    ),
    "parameters": {"type": "OBJECT", "properties": {"texto": {"type": "STRING"}}, "required": []},
}

ENCURTADORES = {"bit.ly", "tinyurl.com", "cutt.ly", "is.gd", "t.co", "goo.gl", "ow.ly", "rebrand.ly", "shorturl.at",
                "encurtador.com.br", "abre.ai", "l1nq.com", "rb.gy", "t.ly", "s.id", "tiny.cc", "u.to", "v.gd"}
TLDS_RUINS = {"xyz", "top", "click", "zip", "mov", "tk", "ml", "ga", "cf", "gq", "icu", "cyou", "rest", "sbs", "lol",
              "monster", "buzz", "live", "shop", "online", "site", "store", "fun", "info", "work", "support"}
MARCAS = {  # marca → domínios oficiais
    "nubank": ["nubank.com.br"], "itau": ["itau.com.br"], "bradesco": ["bradesco.com.br"],
    "santander": ["santander.com.br"], "caixa": ["caixa.gov.br"], "bancodobrasil": ["bb.com.br"], "bb": ["bb.com.br"],
    "inter": ["bancointer.com.br", "inter.co"], "mercadopago": ["mercadopago.com.br"], "mercadolivre": ["mercadolivre.com.br"],
    "picpay": ["picpay.com"], "correios": ["correios.com.br"], "receita": ["gov.br"], "gov": ["gov.br"],
    "serasa": ["serasa.com.br"], "shopee": ["shopee.com.br"], "amazon": ["amazon.com.br", "amazon.com"],
    "magalu": ["magazineluiza.com.br", "magalu.com"], "netflix": ["netflix.com"], "whatsapp": ["whatsapp.com"],
    "instagram": ["instagram.com"], "facebook": ["facebook.com"], "microsoft": ["microsoft.com", "live.com"],
    "google": ["google.com"], "apple": ["apple.com"], "steam": ["steampowered.com", "steamcommunity.com"],
    "detran": ["gov.br"], "enel": ["enel.com.br"], "equatorial": ["equatorialenergia.com.br"], "sabesp": ["sabesp.com.br"],
}
PISTAS = [  # (regex no texto sem acento, peso, motivo)
    (r"\b(urgente|imediatamente|ultimas? horas|ultimo aviso|hoje ainda|em ate \d+ ?h)", 2, "pressa/urgência"),
    (r"\b(bloquead|suspens|desativad|cancelad)\w*", 2, "ameaça de bloqueio ou cancelamento"),
    (r"\b(pix|transferencia|deposito|boleto|chave aleatoria)\b", 2, "pede dinheiro / Pix"),
    (r"\b(troquei de numero|novo numero|esse e meu numero novo|salva (esse|meu) numero)", 4, "golpe do 'número novo'"),
    (r"\b(codigo de (verificacao|seguranca|6 digitos)|me (passa|manda) o codigo|codigo que chegou)", 4,
     "pede código de verificação (golpe do WhatsApp clonado)"),
    (r"\b(senha|cvv|codigo de seguranca do cartao|token|dados do cartao)\b", 3, "pede senha ou dados do cartão"),
    (r"\b(voce (foi sorteado|ganhou)|premio|resgate (seu|o) (premio|bonus)|cashback garantido)", 3, "prêmio/sorteio"),
    (r"\b(taxa (de liberacao|alfandegaria|de entrega)|encomenda (retida|taxada)|pacote (retido|parado))", 3,
     "falsa taxa de entrega"),
    (r"\b(atualiz\w+ (seu )?cadastro|regulariz\w+|pendencia|cpf (irregular|bloqueado|suspenso))", 2,
     "falsa pendência/cadastro"),
    (r"\b(renda extra|ganhe r\$|lucro garantido|investimento garantido|dobr\w+ seu dinheiro)", 3, "dinheiro fácil"),
    (r"\b(clique (aqui|no link)|acesse o link|link abaixo)\b", 1, "empurra para um link"),
    (r"\b(mae|pai|filh[oa]|tia|vo)\b.{0,40}\b(pix|transfer|emprest|preciso de dinheiro)", 3,
     "parente pedindo dinheiro"),
]


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def links(texto: str) -> list[str]:
    achados = re.findall(r"(?:https?://|www\.)[^\s<>\"']+|\b[\w-]+(?:\.[\w-]+)+\.[a-z]{2,}(?:/[^\s<>\"']*)?",
                         texto or "", re.I)
    return list(dict.fromkeys(a.rstrip(".,;)") for a in achados))


def avaliar_link(url: str) -> list[tuple[int, str]]:
    """Sinais de risco de um endereço (pura)."""
    u = url if re.match(r"^https?://", url, re.I) else "http://" + url
    p = urlparse(u)
    host = (p.hostname or "").lower()
    sinais = []
    if not host:
        return [(2, "endereço estranho")]
    partes = host.split(".")
    tld = partes[-1]
    base = ".".join(partes[-3:]) if host.endswith((".com.br", ".gov.br", ".org.br", ".net.br")) else ".".join(partes[-2:])
    if host in ENCURTADORES or base in ENCURTADORES:
        sinais.append((2, f"link encurtado ({host}) esconde o destino"))
    if "xn--" in host:
        sinais.append((4, "domínio com letras disfarçadas (punycode)"))
    try:
        ipaddress.ip_address(host)
        sinais.append((3, "endereço é um IP, não um site"))
    except ValueError:
        pass
    if tld in TLDS_RUINS:
        sinais.append((2, f"terminação .{tld}, muito usada em golpes"))
    if "@" in (p.netloc or ""):
        sinais.append((4, "tem '@' no endereço (engana para onde vai)"))
    if len(partes) >= 5:
        sinais.append((1, "muitos subdomínios"))
    if p.scheme == "http" and url.lower().startswith("http://"):
        sinais.append((1, "sem cadeado (http)"))
    sem_pontos = _dobrar(host).replace("-", "").replace(".", "")
    for marca, oficiais in MARCAS.items():
        if len(marca) < 3:
            continue
        if marca in sem_pontos and not any(host == d or host.endswith("." + d) for d in oficiais):
            sinais.append((6, f"usa o nome '{marca}' mas NÃO é o site oficial ({', '.join(oficiais)})"))
            break
    if re.search(r"(login|senha|verific|seguranc|atualiz|desbloque|resgat)", _dobrar(p.path + " " + host)):
        sinais.append((1, "endereço fala de login/atualização"))
    return sinais


def avaliar(texto: str) -> dict:
    """Nota de risco 0–100, nível e motivos (pura)."""
    t = _dobrar(texto)
    motivos: list[tuple[int, str]] = []
    for padrao, peso, motivo in PISTAS:
        if re.search(padrao, t):
            motivos.append((peso, motivo))
    for url in links(texto):
        for peso, motivo in avaliar_link(url):
            motivos.append((peso, f"{motivo} — {url[:60]}"))
    pontos = sum(p for p, _m in motivos)
    nota = min(100, pontos * 9)
    nivel = "ALTO" if nota >= 55 else "MÉDIO" if nota >= 25 else "BAIXO"
    return {"nota": nota, "nivel": nivel, "motivos": [m for _p, m in sorted(motivos, key=lambda x: -x[0])],
            "links": links(texto)}


def run(parameters: dict, player=None, session_memory=None) -> str:
    texto = str((parameters or {}).get("texto") or "").strip()
    try:
        if not texto:
            from plugins.olha_isso import _clipboard
            texto = _clipboard().strip()
            if not texto:
                return "Cole ou dite a mensagem ou o link suspeito."
        r = avaliar(texto)
        from plugins import _ia
        opiniao = ""
        if _ia.disponivel():
            opiniao = _ia.perguntar(
                "Você é um especialista brasileiro em golpes digitais. Em 2 frases: isto parece golpe? Por quê? O que a "
                f"pessoa deve fazer? Não abra links.\nTEXTO: {texto[:3000]}", False, 30) or ""
        from plugins._comum import mostrar
        mostrar(player, f"DETECTOR DE GOLPE — risco {r['nivel']} ({r['nota']}/100)",
                "\n".join(f"• {m}" for m in r["motivos"]) + (f"\n\nIA: {opiniao}" if opiniao else "")
                + "\n\nNa dúvida: não clique, não pague, ligue para o número oficial (do cartão/site) ou para a pessoa.")
        base = (f"Risco {r['nivel']} ({r['nota']} de 100). " + ("Sinais: " + "; ".join(r["motivos"][:4]) + ". "
                                                              if r["motivos"] else "Não achei sinais clássicos de golpe. "))
        dica = ("Não clique, não pague e confirme por um canal oficial." if r["nivel"] != "BAIXO" else
                "Mesmo assim, desconfie de pedidos de dinheiro ou código.")
        return base + dica + (f" Segunda opinião: {opiniao}" if opiniao else "")
    except Exception as e:
        return f"O detector de golpe falhou: {e}"
