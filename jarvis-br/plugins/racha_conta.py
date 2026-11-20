"""
Racha a conta (fork PT-BR 2.16, ideia 5).

    "Jarvis, racha a conta: somos 5, o João pagou tudo, 250 reais"
    "Jarvis, racha: João pagou 200, Maria pagou 50, eu, Ana e Pedro não pagamos nada"
    "Jarvis, a chave Pix do João é joao@email.com"

Calcula quem deve quanto a quem com o MENOR número de transferências, e para
cada transferência gera o Pix "copia e cola" (BR Code com o valor já
preenchido) de quem recebe — quem deve só cola no app do banco. As chaves Pix
ficam em memory/pix_contatos.json, só no seu PC.

Funciona sem internet e sem IA (as contas são feitas aqui).
"""

from __future__ import annotations

import re
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, nome_usuario

PLUGIN = {
    "name": "racha_conta",
    "brief": "Split a bill: who owes whom (fewest transfers) with Pix copy-and-paste codes; store friends' Pix keys.",
    "description": (
        "Bill splitter. action='rachar' with pagamentos = 'Nome: valor; Nome: valor' for everyone who paid (use 'eu' "
        "for the user) and pessoas = everyone in the group comma separated (or total_pessoas = how many). People "
        "who paid nothing still count. Optional total if only one person paid ('somos 5, o João pagou 250'). "
        "action='pix' with nome and chave saves a friend's Pix key (cidade optional). action='chaves' lists them."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "rachar | pix | chaves"},
            "pagamentos": {"type": "STRING"}, "pessoas": {"type": "STRING"}, "total_pessoas": {"type": "INTEGER"},
            "total": {"type": "NUMBER"}, "nome": {"type": "STRING"}, "chave": {"type": "STRING"},
            "cidade": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

ARQ = MEMORIA / "pix_contatos.json"


def _n(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


def _valor(t: str) -> float:
    t = str(t).replace("R$", "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def ler_pagamentos(texto: str) -> dict[str, float]:
    """'João: 200; Maria 50,5' → {'João': 200.0, 'Maria': 50.5} (pura)."""
    saida: dict[str, float] = {}
    for parte in re.split(r"[;\n]|,\s(?=[A-Za-zÀ-ú])|\be\b(?=\s+[A-Za-zÀ-ú]+\s*:?\s*(?:pagou\s*)?R?\$?\s*\d)", texto or ""):
        m = re.match(r"\s*([A-Za-zÀ-ú][\wÀ-ú ]*?)\s*(?::|pagou|=|-)?\s*R?\$?\s*(\d[\d.,]*)\s*(?:reais)?\s*$", parte.strip())
        if m:
            nome = m.group(1).strip()
            saida[nome] = saida.get(nome, 0.0) + _valor(m.group(2))
    return saida


def dividir(pagamentos: dict[str, float], pessoas: list[str]) -> tuple[float, list[tuple[str, str, float]]]:
    """(parte de cada um, [(quem paga, para quem, valor)]) com o mínimo de transferências
    pelo método guloso (maior devedor paga o maior credor). Centavos acertados (pura)."""
    todos = list(dict.fromkeys([*pessoas, *pagamentos]))
    total = round(sum(pagamentos.values()), 2)
    n = len(todos)
    if n == 0 or total <= 0:
        return 0.0, []
    centavos = int(round(total * 100))
    base, resto = divmod(centavos, n)
    parte = {p: base + (1 if i < resto else 0) for i, p in enumerate(todos)}
    saldo = {p: int(round(pagamentos.get(p, 0) * 100)) - parte[p] for p in todos}
    devedores = sorted([[p, -s] for p, s in saldo.items() if s < 0], key=lambda x: -x[1])
    credores = sorted([[p, s] for p, s in saldo.items() if s > 0], key=lambda x: -x[1])
    transf = []
    i = j = 0
    while i < len(devedores) and j < len(credores):
        v = min(devedores[i][1], credores[j][1])
        if v > 0:
            transf.append((devedores[i][0], credores[j][0], v / 100))
        devedores[i][1] -= v
        credores[j][1] -= v
        if devedores[i][1] == 0:
            i += 1
        if credores[j][1] == 0:
            j += 1
    return base / 100, transf


# ── Pix copia e cola (BR Code estático, padrão EMV do Banco Central) ─────────
def crc16(dados: str) -> str:
    """CRC-16/CCITT-FALSE (polinômio 0x1021, início 0xFFFF) (pura)."""
    crc = 0xFFFF
    for b in dados.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def _campo(id_: str, valor: str) -> str:
    return f"{id_}{len(valor.encode('utf-8')):02d}{valor}"


def _limpo(t: str, n: int) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", "", t)[:n].strip() or "X"


def pix_copia_cola(chave: str, nome: str, valor: float, cidade: str = "GOIANIA", txid: str = "***") -> str:
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave.strip())
    corpo = (_campo("00", "01") + _campo("26", conta) + _campo("52", "0000") + _campo("53", "986")
             + (_campo("54", f"{valor:.2f}") if valor > 0 else "") + _campo("58", "BR")
             + _campo("59", _limpo(nome, 25)) + _campo("60", _limpo(cidade, 15))
             + _campo("62", _campo("05", txid)) + "6304")
    return corpo + crc16(corpo)


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _chave_de(nome: str, chaves: dict) -> dict | None:
    eu = _n(nome) in ("eu", "mim", _n(nome_usuario() or "eu"))
    return chaves.get("eu") if eu else chaves.get(_n(nome))


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "rachar").lower()
    chaves = ler_json(ARQ, {}) or {}
    try:
        if a == "pix":
            nome, chave = str(p.get("nome") or "").strip(), str(p.get("chave") or "").strip()
            if not nome or not chave:
                return "Diga o nome e a chave Pix."
            k = "eu" if _n(nome) in ("eu", "minha", "meu") else _n(nome)
            chaves[k] = {"nome": nome if k != "eu" else (nome_usuario() or "Eu"), "chave": chave,
                         "cidade": str(p.get("cidade") or "Goiania")}
            gravar_json(ARQ, chaves)
            return f"Chave Pix de {chaves[k]['nome']} guardada."
        if a == "chaves":
            if not chaves:
                return "Nenhuma chave Pix guardada."
            return "Tenho a chave Pix de: " + ", ".join(v["nome"] for v in chaves.values()) + "."
        pag = ler_pagamentos(str(p.get("pagamentos") or ""))
        pessoas = [x.strip() for x in re.split(r",|\be\b", str(p.get("pessoas") or "")) if x.strip()]
        if not pag and p.get("total"):
            return "Quem pagou?"
        if len(pag) == 1 and p.get("total") and not list(pag.values())[0]:
            pag = {list(pag)[0]: float(p["total"])}
        n_total = int(p.get("total_pessoas") or 0)
        todos = list(dict.fromkeys([*pessoas, *pag]))
        while len(todos) < n_total:                       # "somos 5": completa com pessoas sem nome
            todos.append(f"Pessoa {len(todos) + 1}")
        parte, transf = dividir(pag, todos)
        if not transf:
            return "Ninguém deve nada a ninguém." if parte else "Preciso saber quem pagou quanto."
        linhas = [f"Total {_brl(sum(pag.values()))} · {len(todos)} pessoas · {_brl(parte)} para cada", ""]
        falas = []
        for de, para, v in transf:
            linhas.append(f"{de} → {para}: {_brl(v)}")
            falas.append(f"{de} paga {_brl(v)} para {para}")
            ch = _chave_de(para, chaves)
            if ch:
                linhas.append(f"   Pix copia e cola: {pix_copia_cola(ch['chave'], ch['nome'], v, ch.get('cidade', 'Goiania'))}")
            else:
                linhas.append(f"   (sem chave Pix de {para}; diga 'a chave Pix do {para} é …')")
        mostrar(player, "RACHA A CONTA", "\n".join(linhas))
        return f"{_brl(parte)} para cada. " + "; ".join(falas) + ". Os Pix copia e cola estão no painel."
    except Exception as e:
        return f"Não consegui rachar a conta: {e}"
