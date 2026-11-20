"""
Cupom fiscal vira gasto (fork PT-BR 2.16, ideia 4).

    "Jarvis, lê essa nota"                 (a foto mais nova de Downloads, da pasta de cupons ou do WhatsApp)
    "Jarvis, registra o cupom C:\\fotos\\nota.jpg"
    Mandar a FOTO da nota pelo seu WhatsApp do JARVIS com a legenda "nota" ou "cupom"

Ele lê a foto (com a IA de visão), acha o estabelecimento, a data, o total e os
itens, escolhe a categoria e registra no controle de gastos (memory/gastos.csv,
o mesmo do "gastei 40 no almoço"). Se a nota tiver o QR Code da NFC-e, o link
da consulta na SEFAZ fica junto no painel.

Não registra a mesma nota duas vezes (confere total + data + estabelecimento).
Precisa da chave do Gemini (a visão). Sem ela, diga o valor por voz.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, pasta_jarvis

PLUGIN = {
    "name": "cupom_fiscal",
    "brief": "Read a receipt photo (OCR/vision) and record it as an expense with category.",
    "description": (
        "Receipt to expense. action='ler' with optional arquivo (image path; default = newest photo in Downloads, "
        "Documentos/JARVIS/Cupons or the WhatsApp media folder) reads store, date, total and items, picks the category "
        "and records it in the expense tracker. action='ultimos' lists recent receipts. Say the store and total back."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ler | ultimos"}, "arquivo": {"type": "STRING"}},
        "required": [],
    },
}

ARQ = MEMORIA / "cupons_lidos.json"
_IMG = {".jpg", ".jpeg", ".png", ".webp"}
CATEGORIAS = ("alimentacao", "transporte", "casa", "contas", "loja", "lazer", "saude", "compras", "outros")


def _pastas() -> list[Path]:
    pastas = [Path.home() / "Downloads", pasta_jarvis("Cupons")]
    try:
        from plugins import _whatsapp as W
        pastas.append(Path(W.config().get("sessao") or "") / "midia")
    except Exception:
        pass
    for base in (MEMORIA / "whatsapp" / "midia", MEMORIA / "whatsapp_sessao" / "midia"):
        pastas.append(base)
    return [p for p in pastas if p and p.exists()]


def foto_mais_nova(max_horas: float = 48) -> Path | None:
    limite = time.time() - max_horas * 3600
    achadas = []
    for pasta in _pastas():
        for f in pasta.iterdir():
            try:
                if f.suffix.lower() in _IMG and f.stat().st_mtime >= limite:
                    achadas.append((f.stat().st_mtime, f))
            except OSError:
                continue
    return max(achadas)[1] if achadas else None


def qr_nfce(caminho: Path) -> str:
    try:
        import cv2
        img = cv2.imread(str(caminho))
        if img is None:
            return ""
        txt, _pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return txt if txt.startswith("http") else ""
    except Exception:
        return ""


def categoria_de(estabelecimento: str, itens: list) -> str:
    """Categoria pelo nome da loja e itens, quando a IA não escolher (pura)."""
    t = (estabelecimento + " " + " ".join(map(str, itens))).lower()
    regras = (("alimentacao", ("supermerc", "mercado", "atacad", "padaria", "restaur", "lanch", "pizz", "açougue",
                               "acougue", "hortifr", "ifood", "burger", "cafe", "café", "assai", "assaí")),
              ("saude", ("farm", "drog", "clinic", "laborat", "pague menos", "raia")),
              ("transporte", ("posto", "combust", "gasolina", "etanol", "estacion", "uber", "99")),
              ("casa", ("constru", "materia", "leroy", "eletro", "móveis", "moveis")),
              ("lazer", ("cinema", "bar ", "show", "ingresso", "parque")))
    for cat, palavras in regras:
        if any(p in t for p in palavras):
            return cat
    return "compras"


def ler_nota(caminho: Path) -> dict:
    from plugins import _ia
    if not _ia.disponivel():
        raise RuntimeError("preciso da chave do Gemini para ler a foto; diga o valor por voz que eu anoto")
    from google.genai import types as gtypes

    from core import gemini
    mime = "image/png" if caminho.suffix.lower() == ".png" else "image/jpeg"
    prompt = ("Esta é a foto de um cupom/nota fiscal brasileira. Responda SÓ JSON: {\"estabelecimento\": \"...\", "
              "\"data\": \"AAAA-MM-DD\", \"total\": 0.00, \"itens\": [\"...\"], \"forma_pagamento\": \"...\", "
              "\"categoria\": \"" + " | ".join(CATEGORIAS) + "\", \"legivel\": true}. O total é o VALOR A PAGAR final. "
              "Se não for uma nota, legivel=false.")
    resp = gemini.call([gtypes.Part.from_bytes(data=caminho.read_bytes(), mime_type=mime), prompt],
                       tier=gemini.FAST, timeout_ms=45_000)
    texto = (getattr(resp, "text", "") or "") if resp is not None else ""
    import json
    import re
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise RuntimeError("não consegui ler a nota")
    return json.loads(m.group(0))


def registrar_nota(dados: dict) -> str:
    total = float(str(dados.get("total") or 0).replace(",", "."))
    if total <= 0 or dados.get("legivel") is False:
        return ""
    loja = str(dados.get("estabelecimento") or "compra").strip()[:60]
    cat = str(dados.get("categoria") or "").lower()
    if cat not in CATEGORIAS:
        cat = categoria_de(loja, dados.get("itens") or [])
    marca = hashlib.sha1(f"{loja.lower()}|{dados.get('data')}|{total:.2f}".encode()).hexdigest()[:12]
    lidos = ler_json(ARQ, []) or []
    if any(x.get("marca") == marca for x in lidos):
        return "repetida"
    from plugins import gastos
    gastos._registrar({"valor": total, "descricao": f"{loja} (cupom)", "categoria": cat})
    lidos.append({"marca": marca, "loja": loja, "data": dados.get("data"), "total": total, "categoria": cat,
                  "lido_em": time.strftime("%Y-%m-%d %H:%M")})
    gravar_json(ARQ, lidos[-300:])
    return cat


def processar(caminho: Path, player=None) -> str:
    dados = ler_nota(caminho)
    if dados.get("legivel") is False or not dados.get("total"):
        return "Não consegui ler o total dessa foto. Tente uma foto mais de perto e reta."
    qr = qr_nfce(caminho)
    cat = registrar_nota(dados)
    total = float(str(dados["total"]).replace(",", "."))
    valor = "R$ " + f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    mostrar(player, "CUPOM FISCAL", "\n".join(
        [f"Estabelecimento: {dados.get('estabelecimento')}", f"Data: {dados.get('data')}", f"Total: {valor}",
         f"Pagamento: {dados.get('forma_pagamento') or '—'}", f"Categoria: {cat or '—'}", "",
         "Itens:"] + [f"  • {i}" for i in (dados.get("itens") or [])[:40]] + ([f"", f"NFC-e: {qr}"] if qr else [])))
    if cat == "repetida":
        return f"Essa nota ({dados.get('estabelecimento')}, {valor}) já estava registrada; não anotei de novo."
    return f"Registrei {valor} em {dados.get('estabelecimento')} como {cat}."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "ler").lower()
    try:
        if a == "ultimos":
            lidos = (ler_json(ARQ, []) or [])[-10:]
            if not lidos:
                return "Ainda não li nenhum cupom."
            return "Últimos cupons: " + "; ".join(f"{x['loja']} R$ {x['total']:.2f}".replace(".", ",") for x in lidos[-5:]) + "."
        arq = Path(str(p.get("arquivo") or "").strip().strip('"')) if p.get("arquivo") else foto_mais_nova()
        if not arq or not arq.exists():
            return "Não achei a foto da nota. Mande pelo WhatsApp do JARVIS ou salve em Downloads."
        return processar(arq, player)
    except Exception as e:
        return f"Não consegui registrar o cupom: {e}"
