"""
Conferir pagamento (3.0): ANTES de pagar, o JARVIS confere o que dá para conferir sem internet.

    • Pix copia e cola (mesmo no meio de uma mensagem): mostra PARA QUEM vai o dinheiro (nome e
      cidade gravados no código), a chave quando não é aleatória e o valor, se vier no código.
    • Boleto: confere os dígitos da linha digitável (boleto adulterado costuma errar o dígito) e lê
      o valor e o vencimento gravados nela, para você comparar com o que esperava.
    • CNPJ citado na mensagem: confere se é um CNPJ válido.
    • O texto da mensagem: passa pelo detector de golpe (plugin `detector_golpe`, da 1.6).

    "Jarvis, confere esse Pix antes de eu pagar: 00020126…"
    "Jarvis, esse boleto está certo? 23793.38128 60082.677139 …"

Dígito certo não garante quem recebe: confira sempre o nome do beneficiário no app do banco.
"""

from __future__ import annotations

import re

from plugins._lote2 import P, rodar

PLUGIN = P("conferir_pagamento", "Before paying: shows who receives a Pix copy-paste code, checks boleto digits and CNPJ, and runs the scam detector on the text.",
           "conferir", "conferir: texto (Pix code, boleto line, or the message with them).", "texto")

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_BLOCO_NUMEROS = re.compile(r"\d[\d .\-]{40,70}\d")
_LINHAS = (re.compile(r"\d{5}\.?\d{5}\s*\d{5}\.?\d{6}\s*\d{5}\.?\d{6}\s*\d\s*\d{14}"),          # banco (47)
           re.compile(r"8\d{10}[-\s]?\d\s*\d{11}[-\s]?\d\s*\d{11}[-\s]?\d\s*\d{11}[-\s]?\d"))     # contas (48)


def _campos(t: str, i: int = 0) -> tuple[dict[str, str], int]:
    """Lê campos TLV (tag 2 dígitos + tamanho 2 dígitos + valor) a partir de i. Para no CRC (63)."""
    campos: dict[str, str] = {}
    while i + 4 <= len(t):
        tag, tam = t[i:i + 2], t[i + 2:i + 4]
        if not (tag.isdigit() and tam.isdigit()) or i + 4 + int(tam) > len(t):
            break
        campos[tag] = t[i + 4:i + 4 + int(tam)]
        i += 4 + int(tam)
        if tag == "63":
            break
    return campos, i


def achar_pix(texto: str) -> tuple[int, int, dict[str, str]] | None:
    """Acha um Pix copia e cola em qualquer lugar do texto: (início, fim, campos). Pura.

    Lê pelos tamanhos gravados no código, então nome com espaço ('Fulano de Tal') não quebra."""
    t = texto or ""
    for m in re.finditer("000201", t):
        campos, fim = _campos(t, m.start())
        if "br.gov.bcb.pix" in t[m.start():fim].lower():
            return m.start(), fim, campos
    return None


def sem_pix(texto: str) -> str:
    """O texto sem o código Pix (o código em si não é mensagem para o detector de golpe). Pura."""
    achado = achar_pix(texto)
    return texto if not achado else (texto[:achado[0]] + " " + texto[achado[1]:]).strip()


def pix_destino(texto: str) -> str | None:
    """'Nome (CIDADE)' de quem recebe (campos 59 e 60), com a chave se não for aleatória. Pura."""
    achado = achar_pix(texto)
    if not achado or "59" not in achado[2]:
        return None
    c = achado[2]
    destino = f"{c['59'].strip()} ({c.get('60', '?').strip()})"
    conta = next((v for v in c.values() if "br.gov.bcb.pix" in v.lower()), "")
    chave = _campos(conta)[0].get("01", "").strip()
    if chave and not _UUID.fullmatch(chave):
        destino += f", chave {chave}"
    return destino


def pix_valor(texto: str) -> float | None:
    """Valor gravado no Pix (campo 54), se houver. Pura."""
    achado = achar_pix(texto)
    try:
        return float(achado[2]["54"]) if achado and "54" in achado[2] else None
    except ValueError:
        return None


def codigos_boleto(texto: str) -> list[str]:
    """Linhas de boleto (só os dígitos) que aparecem no texto, com dígito certo ou não. Pura.

    Confere o código do jeito que veio: não procura "pedaços que batem" dentro de um código errado."""
    achados = []
    for m in _BLOCO_NUMEROS.finditer(sem_pix(texto)):
        d = re.sub(r"\D", "", m.group(0))
        if len(d) in (44, 47, 48):
            achados.append(d)
        else:                                            # colado em outros números: pega o formato da linha
            achados += [re.sub(r"\D", "", x.group(0)) for rx in _LINHAS for x in rx.finditer(m.group(0))]
    return list(dict.fromkeys(achados))


def boletos(texto: str) -> list[tuple[str, dict | None]]:
    """[(código, leitura com valor/vencimento — ou None se o dígito não bate)]. Pura."""
    from plugins import _boleto
    return [(c, _boleto.ler_codigo(c)) for c in codigos_boleto(texto)]


def boleto_ok(texto: str) -> bool | None:
    """True se os boletos do texto têm os dígitos certos; False se algum erra; None se não há boleto. Pura."""
    achados = boletos(texto)
    return None if not achados else all(lido for _, lido in achados)


def cnpjs(texto: str) -> list[str]:
    """CNPJs escritos como CNPJ (com pontuação, ou depois da palavra CNPJ). Pura."""
    t = sem_pix(texto)
    return list(dict.fromkeys(re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", t)
                              + re.findall(r"cnpj\W{0,3}(\d{14})\b", t, re.I)))


def conferir(texto: str) -> tuple[list[str], list[str]]:
    """(problemas, informações). Pura (lê só o texto)."""
    from plugins import _boleto
    problemas, info = [], []
    dest = pix_destino(texto)
    if dest:
        v = pix_valor(texto)
        info.append(f"Este Pix vai para: {dest}" + (f", valor {_boleto.reais(v)}" if v else "") + ". É mesmo quem você quer pagar?")
    for _, lido in boletos(texto):
        if not lido:
            problemas.append("a linha do boleto tem dígito errado: boleto adulterado ou digitado errado")
            continue
        extra = [f"valor {_boleto.reais(lido['valor'])}"] if lido.get("valor") else []
        if lido.get("vencimento"):
            extra.append(f"vence {lido['vencimento']:%d/%m/%Y}")
        info.append("A linha do boleto tem os dígitos certos" + (f" ({', '.join(extra)})" if extra else "")
                    + ". Confira se o valor é o esperado e o nome do beneficiário no app do banco.")
    from plugins.validador_documentos import cnpj_ok
    problemas += [f"o CNPJ {c} é inválido" for c in cnpjs(texto) if not cnpj_ok(c)]
    return problemas, info


def _go(p, pl):
    texto = str(p.get("texto") or "").strip()
    if len(texto) < 5:
        return "Cole o Pix copia e cola, a linha do boleto ou a mensagem com eles."
    problemas, info = conferir(texto)
    partes = []
    mensagem = sem_pix(texto)
    if len(mensagem) >= 5:
        from plugins import detector_golpe
        r = detector_golpe.avaliar(mensagem)
        partes.append(f"Golpe: risco {r['nivel']} ({r['nota']} de 100)"
                      + (f" — {'; '.join(r['motivos'][:3])}" if r["motivos"] else "") + ".")
    if problemas:
        partes.append("PROBLEMA: " + "; ".join(problemas) + ". Não pague.")
    partes += info
    if not problemas and not info:
        partes.append("Não achei Pix copia e cola, boleto nem CNPJ para conferir.")
    return " ".join(partes)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"conferir": _go}, player)
