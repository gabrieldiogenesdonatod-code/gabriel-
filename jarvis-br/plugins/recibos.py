"""Recibos e orçamentos (2.18): valor por extenso e um HTML pronto para imprimir/enviar (Documentos/JARVIS/Recibos)."""
from __future__ import annotations

import html
import time

from plugins._comum import abrir_no_sistema, nome_usuario, pasta_jarvis
from plugins._lote2 import P, lista, numeros, reais, rodar

PLUGIN = P("recibos", "Receipts and quotes: amount in words (Portuguese), printable HTML receipt or quote with items.",
           "extenso | recibo | orcamento",
           "extenso: valor. recibo: cliente, valor, referente (what for). orcamento: cliente, itens ('2 body 39,90; 1 short 25'), "
           "validade (days).",
           "valor cliente referente itens validade")

_U = "zero um dois três quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete dezoito dezenove".split()
_D = "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()
_C = "_ cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos".split()


def _ate999(n: int) -> str:
    if n == 100:
        return "cem"
    c, r = divmod(n, 100)
    partes = [_C[c]] if c else []
    if r:
        partes.append(_U[r] if r < 20 else _D[r // 10] + (f" e {_U[r % 10]}" if r % 10 else ""))
    return " e ".join(partes)


def extenso(n: int) -> str:
    if n == 0:
        return "zero"
    grupos, out = [], []
    while n:
        n, r = divmod(n, 1000)
        grupos.append(r)
    nomes = [("", ""), ("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões")]
    for i in range(len(grupos) - 1, -1, -1):
        g = grupos[i]
        if not g:
            continue
        txt = "mil" if i == 1 and g == 1 else _ate999(g) + (f" {nomes[i][0 if g == 1 else 1]}" if i else "")
        out.append(txt)
    if len(out) > 1 and (grupos[0] < 100 or grupos[0] % 100 == 0) and grupos[0]:
        return " ".join(out[:-1]) + " e " + out[-1]
    return " ".join(out)


def reais_extenso(v: float) -> str:
    r, c = int(v), round((v - int(v)) * 100)
    partes = []
    if r:
        partes.append(extenso(r) + (" de" if r >= 1_000_000 and r % 1_000_000 == 0 else "") + (" real" if r == 1 else " reais"))
    if c:
        partes.append(extenso(c) + (" centavo" if c == 1 else " centavos"))
    return " e ".join(partes) or "zero real"


def _salvar(tipo: str, corpo: str) -> str:
    arq = pasta_jarvis("Recibos") / f"{tipo}_{time.strftime('%Y%m%d_%H%M%S')}.html"
    arq.write_text(f"<html><meta charset='utf-8'><body style='font-family:sans-serif;max-width:640px;margin:40px auto'>"
                   f"{corpo}<p style='margin-top:60px'>______________________<br>{html.escape(nome_usuario() or '')}</p>"
                   f"<p>{time.strftime('%d/%m/%Y')}</p></body></html>", encoding="utf-8")
    abrir_no_sistema(str(arq))
    return str(arq)


def _go(p, pl):
    a, v = str(p.get("action")).lower(), (numeros(p.get("valor")) or [0])[0]
    cli = html.escape(str(p.get("cliente") or ""))
    if a == "extenso":
        return f"{reais(v)}: {reais_extenso(v)}."
    if a == "recibo":
        arq = _salvar("recibo", f"<h2>RECIBO — {reais(v)}</h2><p>Recebi de <b>{cli}</b> a quantia de {reais(v)} "
                                f"({reais_extenso(v)}), referente a {html.escape(str(p.get('referente') or ''))}.</p>")
        return f"Recibo gerado e aberto: {arq}"
    linhas, total = [], 0.0
    bruto = str(p.get("itens") or "")
    for it in [x for x in bruto.split(";") if x.strip()] if ";" in bruto else lista(bruto):
        n = numeros(it)
        q, pr = (n[0], n[-1]) if len(n) > 1 else (1, n[0] if n else 0)
        desc = " ".join(w for w in it.split() if not any(ch.isdigit() for ch in w))
        total += q * pr
        linhas.append(f"<tr><td>{q:g}</td><td>{html.escape(desc)}</td><td>{reais(pr)}</td><td>{reais(q * pr)}</td></tr>")
    val = int((numeros(p.get("validade")) or [7])[0])
    arq = _salvar("orcamento", f"<h2>ORÇAMENTO</h2><p>Cliente: <b>{cli}</b></p><table border=1 cellpadding=6 "
                               f"style='border-collapse:collapse;width:100%'><tr><th>Qtd</th><th>Item</th><th>Unit.</th>"
                               f"<th>Total</th></tr>{''.join(linhas)}</table><h3>Total: {reais(total)}</h3>"
                               f"<p>Válido por {val} dias.</p>")
    return f"Orçamento de {reais(total)} gerado: {arq}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("extenso recibo orcamento".split(), _go), player)
