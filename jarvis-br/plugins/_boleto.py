"""
Leitura de boletos (fork PT-BR 2.5). Começa com "_": não é ferramenta.

Entende os dois tipos de código de barras do Brasil, conferindo os dígitos
verificadores (um número lido errado não vira conta):

  • boleto de banco  — linha digitável de 47 números (ou código de barras de 44):
    traz o VALOR e o VENCIMENTO (fator de vencimento; desde 22/02/2025 o fator
    recomeçou em 1000, então os dois ciclos são considerados e fica o mais
    próximo de hoje);
  • conta de consumo / arrecadação (luz, água, telefone, prefeitura) — 48
    números começando com 8: traz o VALOR e o tipo; o vencimento vem do texto
    do PDF ("Vencimento: 14/11/2026").

Tudo puro, testado em tests/test_26_casa.py.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

BASE_1 = date(1997, 10, 7)          # fator 0 do ciclo antigo
BASE_2 = date(2025, 2, 22)          # fator 1000 do ciclo novo (22/02/2025)
SEGMENTOS = {"1": "prefeitura", "2": "água/saneamento", "3": "luz/gás", "4": "telefone/internet",
             "5": "órgão do governo", "6": "carnê", "7": "multa de trânsito", "9": "outros"}
TIPOS = [
    ("luz", r"energia|eletric|equatorial|enel\b|cemig|copel|light\b|cpfl|neoenergia|energisa|celesc|coelba|celpe|cosern"),
    ("água", r"saneamento|saneago|sabesp|copasa|cedae|caesb|embasa|compesa|sanepar|\bagua\b|aguas"),
    ("internet/telefone", r"\bvivo\b|\bclaro\b|\btim\b|\boi\b|telecom|internet|fibra|telefon|net virtua|sky\b"),
    ("cartão", r"fatura do cart|cartao de credito|nubank|cartao"),
    ("aluguel/condomínio", r"aluguel|condominio|imobiliaria"),
    ("escola/curso", r"escola|colegio|faculdade|universidade|mensalidade|curso"),
    ("saúde", r"unimed|hapvida|amil|bradesco saude|sulamerica|plano de saude|odonto"),
    ("imposto", r"\bdas\b|simples nacional|ipva|iptu|detran|darf|prefeitura|receita federal|\bgnre\b"),
]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _so_digitos(t: str) -> str:
    return re.sub(r"\D", "", str(t or ""))


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── dígitos verificadores ──────────────────────────────────────────────────────
def mod10(numero: str) -> int:
    soma, peso = 0, 2
    for d in reversed(numero):
        p = int(d) * peso
        soma += p // 10 + p % 10
        peso = 1 if peso == 2 else 2
    return (10 - soma % 10) % 10


def mod11_banco(numero: str) -> int:
    soma, peso = 0, 2
    for d in reversed(numero):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    dv = 11 - soma % 11
    return 1 if dv in (0, 10, 11) else dv


def mod11_arrecadacao(numero: str) -> int:
    soma, peso = 0, 2
    for d in reversed(numero):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


# ── boleto de banco ────────────────────────────────────────────────────────────
def linha_para_barras(linha: str) -> str | None:
    """47 dígitos → 44 do código de barras, conferindo os 3 DVs dos campos. None se não bate."""
    d = _so_digitos(linha)
    if len(d) != 47:
        return None
    for ini, fim in ((0, 9), (10, 20), (21, 31)):
        if mod10(d[ini:fim]) != int(d[fim]):
            return None
    return d[0:4] + d[32] + d[33:47] + d[4:9] + d[10:20] + d[21:31]


def barras_valida(barras: str) -> bool:
    b = _so_digitos(barras)
    if len(b) != 44:
        return False
    if b[0] == "8":
        return arrecadacao_barras_valida(b)
    return mod11_banco(b[:4] + b[5:]) == int(b[4])


def data_do_fator(fator: int, hoje: date | None = None) -> date | None:
    """Fator de vencimento → data. Ciclo antigo (base 07/10/1997) ou novo (1000 = 22/02/2025)."""
    if fator <= 0:
        return None
    hoje = hoje or date.today()
    candidatos = [BASE_1 + timedelta(days=fator)]
    if fator >= 1000:
        candidatos.append(BASE_2 + timedelta(days=fator - 1000))
    return min(candidatos, key=lambda c: abs((c - hoje).days))


def ler_bancario(codigo: str, hoje: date | None = None) -> dict | None:
    d = _so_digitos(codigo)
    barras = linha_para_barras(d) if len(d) == 47 else (d if len(d) == 44 and d[0] != "8" else None)
    if not barras or not barras_valida(barras):
        return None
    fator, valor = int(barras[5:9]), int(barras[9:19]) / 100
    return {"tipo_codigo": "bancario", "banco": barras[0:3], "valor": valor or None,
            "vencimento": data_do_fator(fator, hoje) if fator else None,
            "barras": barras, "linha": d if len(d) == 47 else barras_para_linha(barras)}


def barras_para_linha(barras: str) -> str:
    b = _so_digitos(barras)
    c1 = b[0:4] + b[19:24]
    c2 = b[24:34]
    c3 = b[34:44]
    return f"{c1}{mod10(c1)}{c2}{mod10(c2)}{c3}{mod10(c3)}{b[4]}{b[5:19]}"


# ── conta de consumo / arrecadação (começa com 8) ──────────────────────────────
def _dv_arrec(bloco: str, ident: str) -> int:
    return mod10(bloco) if ident in "67" else mod11_arrecadacao(bloco)


def arrecadacao_barras_valida(barras: str) -> bool:
    b = _so_digitos(barras)
    if len(b) != 44 or b[0] != "8" or b[2] not in "6789":
        return False
    return _dv_arrec(b[:3] + b[4:], b[2]) == int(b[3])


def ler_arrecadacao(codigo: str) -> dict | None:
    d = _so_digitos(codigo)
    if len(d) == 48 and d[0] == "8":
        blocos = [d[i:i + 12] for i in range(0, 48, 12)]
        ident = d[2]
        if ident not in "6789" or any(_dv_arrec(b[:11], ident) != int(b[11]) for b in blocos):
            return None
        barras = "".join(b[:11] for b in blocos)
    elif len(d) == 44 and d[0] == "8":
        barras = d
    else:
        return None
    if not arrecadacao_barras_valida(barras):
        return None
    valor = int(barras[4:15]) / 100 if barras[2] in "68" else None      # 7/9 = valor de referência
    return {"tipo_codigo": "arrecadacao", "segmento": SEGMENTOS.get(barras[1], "outros"), "valor": valor or None,
            "vencimento": None, "barras": barras, "linha": d if len(d) == 48 else None}


def ler_codigo(codigo: str, hoje: date | None = None) -> dict | None:
    d = _so_digitos(codigo)
    return ler_arrecadacao(d) if d[:1] == "8" else ler_bancario(d, hoje)


# ── texto do PDF / e-mail ──────────────────────────────────────────────────────
def achar_codigos(texto: str) -> list[str]:
    """Sequências de 47/48 (linha) ou 44 (barras) dígitos, com ou sem pontos e espaços."""
    achados = []
    for m in re.finditer(r"(?:\d[\d .\-]{40,70}\d)", texto or ""):
        bruto = _so_digitos(m.group(0))
        for tam in (48, 47, 44):
            for i in range(0, max(0, len(bruto) - tam) + 1):
                pedaco = bruto[i:i + tam]
                if ler_codigo(pedaco) and pedaco not in achados:
                    achados.append(pedaco)
    return achados


def achar_vencimento(texto: str) -> date | None:
    t = _dobrar(texto)
    for m in re.finditer(r"vencimento[^0-9]{0,40}(\d{2})[/.](\d{2})[/.](\d{2,4})", t):
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(a + 2000 if a < 100 else a, mes, d)
        except ValueError:
            continue
    return None


def achar_valor(texto: str) -> float | None:
    t = _dobrar(texto)
    for padrao in (r"(?:valor (?:do documento|cobrado|a pagar)|total a pagar|valor total)[^0-9]{0,30}([\d.]+,\d{2})",
                   r"r\$\s*([\d.]+,\d{2})"):
        m = re.search(padrao, t)
        if m:
            return float(m.group(1).replace(".", "").replace(",", "."))
    return None


def tipo_da_conta(texto: str, segmento: str = "") -> str:
    t = _dobrar(texto)
    for nome, padrao in TIPOS:
        if re.search(padrao, t):
            return nome
    return {"luz/gás": "luz", "água/saneamento": "água", "telefone/internet": "internet/telefone"}.get(segmento, "")


def beneficiario(texto: str) -> str:
    m = re.search(r"(?im)^\s*(?:benefici[aá]rio|cedente)\s*[:\-]?\s*(.{3,60})$", texto or "")
    return m.group(1).strip() if m else ""


def ler_texto(texto: str, hoje: date | None = None) -> dict | None:
    """Texto de um PDF/e-mail de cobrança → conta (ou None se não achou código válido)."""
    codigos = achar_codigos(texto)
    if not codigos:
        return None
    info = ler_codigo(codigos[0], hoje) or {}
    venc = info.get("vencimento") or achar_vencimento(texto)
    valor = info.get("valor") or achar_valor(texto)
    return {**info, "vencimento": venc, "valor": valor,
            "tipo": tipo_da_conta(texto, info.get("segmento", "")), "beneficiario": beneficiario(texto)}


def texto_do_pdf(caminho) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(caminho)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages[:6])
    except Exception:
        pass
    try:
        from PyPDF2 import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(caminho)).pages[:6])
    except Exception:
        return ""


# ── frase do aviso ─────────────────────────────────────────────────────────────
def reais(v: float | None) -> str:
    if v is None:
        return "valor não informado"
    if abs(v - round(v)) < 0.005:
        return f"R$ {int(round(v)):,}".replace(",", ".")
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def quando(venc: date, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    n = (venc - hoje).days
    if n == 0:
        return "hoje"
    if n == 1:
        return "amanhã"
    if n == -1:
        return "ontem"
    if 1 < n <= 6:
        return DIAS[venc.weekday()]
    return venc.strftime("%d/%m")


def nome_da_conta(conta: dict) -> str:
    """'A conta de luz', 'A fatura do cartão', 'O boleto da escola', 'A conta da Saneago'."""
    desc = str(conta.get("descricao") or "").strip()
    if not desc:
        desc = f"conta de {conta['tipo']}" if conta.get("tipo") else "conta"
    d = desc[0].lower() + desc[1:]
    if d.startswith(("conta", "fatura", "mensalidade", "parcela", "taxa")):
        return "A " + d
    if d.startswith(("boleto", "carnê", "carne", "imposto", "aluguel", "condomínio", "condominio", "ipva", "iptu")):
        return "O " + d
    return "A conta da " + desc


def frase_aviso(conta: dict, hoje: date | None = None) -> str:
    """'A conta de luz vence sexta, R$ 142.'"""
    hoje = hoje or date.today()
    venc = conta.get("vencimento")
    venc = date.fromisoformat(venc) if isinstance(venc, str) else venc
    verbo = "venceu" if (venc - hoje).days < 0 else "vence"
    return f"{nome_da_conta(conta)} {verbo} {quando(venc, hoje)}, {reais(conta.get('valor'))}."
