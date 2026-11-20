"""
Super consulta Brasil + frete rápido (fork PT-BR 2.16, ideias 1 e 7).

    "Jarvis, consulta o CNPJ 19.131.243/0001-97"
    "Jarvis, qual o endereço do CEP 74000-000?"
    "Jarvis, quanto vale um Gol 2015 na FIPE?"     (ou pelo código FIPE: 005340-6)
    "Jarvis, de onde é o DDD 62?"
    "Jarvis, que banco é o 260?"
    "Jarvis, quanto fica o frete para o CEP 01001-000, 400 gramas?"
        → calcula pelo Melhor Envio e já escreve a resposta para o cliente

De onde vêm os dados (todos gratuitos):
    BrasilAPI (brasilapi.com.br) — CNPJ, CEP, DDD, bancos e preço FIPE por código; sem chave.
    API FIPE do Parallelum — FIPE pelo nome do carro; sem chave (tem limite diário).
    Melhor Envio — frete; precisa de um token GRATUITO (melhorenvio.com.br →
    Integrações → Permissões de acesso → gerar token com "shipping-calculate").
    Cole em ⚙ → Super consulta Brasil, junto com o CEP de onde você envia.
"""

from __future__ import annotations

import re

from plugins import _web
from plugins._comum import cfg, mostrar

PLUGIN = {
    "name": "consulta_brasil",
    "brief": "Brazil lookups: CNPJ, CEP, FIPE car price, DDD, bank code; shipping quote (Melhor Envio) with reply text.",
    "description": (
        "Brazilian public data. action='cnpj' (valor = CNPJ), 'cep' (valor = CEP), 'ddd' (valor = 2 digits), "
        "'banco' (valor = bank code or name), 'fipe' (valor = 'Gol 2015' or a FIPE code like 005340-6; optional tipo = "
        "carros | motos | caminhoes), 'frete' (cep = destination CEP, peso in grams, optional altura/largura/comprimento "
        "in cm, optional valor_declarado, optional cliente = customer name) — returns options and a ready reply for the "
        "customer. Read the key facts back briefly."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "cnpj | cep | ddd | banco | fipe | frete"},
            "valor": {"type": "STRING"}, "tipo": {"type": "STRING"}, "cep": {"type": "STRING"},
            "peso": {"type": "NUMBER"}, "altura": {"type": "NUMBER"}, "largura": {"type": "NUMBER"},
            "comprimento": {"type": "NUMBER"}, "valor_declarado": {"type": "NUMBER"}, "cliente": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "consulta_brasil",
    "title": "Super consulta Brasil",
    "fields": [
        {"key": "melhor_envio_token", "label": "Token do Melhor Envio (para o frete)", "type": "password", "default": ""},
        {"key": "cep_origem", "label": "CEP de onde você envia", "type": "text", "default": ""},
        {"key": "sandbox", "label": "Usar o sandbox do Melhor Envio (testes)", "type": "toggle", "default": False},
        {"key": "medidas_padrao", "label": "Caixa padrão em cm (altura x largura x comprimento)", "type": "text",
         "default": "4x20x25"},
    ],
}

BRASILAPI = "https://brasilapi.com.br/api"
FIPE = "https://fipe.parallelum.com.br/api/v2"


def digitos(t) -> str:
    return re.sub(r"\D", "", str(t or ""))


def cnpj_valido(c: str) -> bool:
    """Confere os dígitos verificadores (pura)."""
    c = digitos(c)
    if len(c) != 14 or c == c[0] * 14:
        return False
    def dv(base, pesos):
        s = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return "0" if s < 2 else str(11 - s)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(c[:12], p1)
    d2 = dv(c[:12] + d1, [6] + p1)
    return c[12:] == d1 + d2


def _brl(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── consultas ─────────────────────────────────────────────────────────────────
def cnpj(valor: str) -> tuple[str, str]:
    c = digitos(valor)
    if not cnpj_valido(c):
        return "Esse CNPJ não é válido (os dígitos não conferem).", ""
    d = _web.get_json(f"{BRASILAPI}/cnpj/v1/{c}")
    nome = d.get("nome_fantasia") or d.get("razao_social")
    linhas = [f"Razão social: {d.get('razao_social')}", f"Nome fantasia: {d.get('nome_fantasia') or '—'}",
              f"Situação: {d.get('descricao_situacao_cadastral')}", f"Abertura: {d.get('data_inicio_atividade')}",
              f"Atividade: {d.get('cnae_fiscal_descricao')}",
              f"Endereço: {d.get('logradouro', '')}, {d.get('numero', '')} — {d.get('bairro', '')}, "
              f"{d.get('municipio', '')}/{d.get('uf', '')}, CEP {d.get('cep', '')}",
              f"Porte: {d.get('porte') or '—'}   Capital social: {_brl(d.get('capital_social') or 0)}"]
    socios = [s.get("nome_socio") for s in d.get("qsa") or [] if s.get("nome_socio")]
    if socios:
        linhas.append("Sócios: " + ", ".join(socios[:6]))
    fala = (f"{nome}: situação {str(d.get('descricao_situacao_cadastral') or '').lower()}, de "
            f"{d.get('municipio', '').title()}/{d.get('uf', '')}, atividade {str(d.get('cnae_fiscal_descricao') or '').lower()}.")
    return fala, "\n".join(linhas)


def cep(valor: str) -> tuple[str, str]:
    c = digitos(valor)
    if len(c) != 8:
        return "O CEP precisa ter 8 números.", ""
    d = _web.get_json(f"{BRASILAPI}/cep/v2/{c}")
    end = ", ".join(x for x in (d.get("street"), d.get("neighborhood"), f"{d.get('city')}/{d.get('state')}") if x)
    return f"CEP {c[:5]}-{c[5:]}: {end}.", end


def ddd(valor: str) -> tuple[str, str]:
    n = digitos(valor)[:2]
    d = _web.get_json(f"{BRASILAPI}/ddd/v1/{n}")
    cidades = sorted(c.title() for c in d.get("cities") or [])
    return (f"O DDD {n} é de {d.get('state')}, com {len(cidades)} cidades, como " + ", ".join(cidades[:4]) + ".",
            "\n".join(cidades))


def banco(valor: str) -> tuple[str, str]:
    v = str(valor or "").strip()
    if digitos(v) and len(digitos(v)) <= 3:
        d = _web.get_json(f"{BRASILAPI}/banks/v1/{int(digitos(v))}")
        return f"O código {d.get('code')} é {d.get('fullName') or d.get('name')}.", ""
    todos = _web.get_json(f"{BRASILAPI}/banks/v1")
    achados = [b for b in todos if v.lower() in str(b.get("fullName") or b.get("name") or "").lower() and b.get("code")]
    if not achados:
        return f"Não achei banco com '{v}'.", ""
    return ("; ".join(f"{b['name']}: código {b['code']}" for b in achados[:5]) + ".",
            "\n".join(f"{b['code']:>4}  {b.get('fullName')}" for b in achados))


def _escolher(lista: list[dict], termo: str, campo: str = "name") -> dict | None:
    t = termo.lower()
    exatos = [x for x in lista if str(x.get(campo, "")).lower() == t]
    if exatos:
        return exatos[0]
    parecidos = [x for x in lista if t in str(x.get(campo, "")).lower()]
    return min(parecidos, key=lambda x: len(str(x.get(campo, "")))) if parecidos else None


def separar_carro(texto: str) -> tuple[str, str]:
    """'Gol 1.6 2015' → ('gol 1.6', '2015') (pura)."""
    m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", texto)
    ano = m.group(1) if m else ""
    nome = re.sub(r"\b(19[5-9]\d|20[0-4]\d)\b", "", texto).strip(" ,-")
    return nome.lower(), ano


def fipe(valor: str, tipo: str = "carros") -> tuple[str, str]:
    v = str(valor or "").strip()
    if re.fullmatch(r"\d{6}-?\d", v):                         # código FIPE → BrasilAPI
        d = _web.get_json(f"{BRASILAPI}/fipe/preco/v1/{v if '-' in v else v[:6] + '-' + v[6:]}")
        if not d:
            return "Não achei esse código FIPE.", ""
        linhas = [f"{x.get('anoModelo')} {x.get('combustivel')}: {x.get('valor')}" for x in d]
        return (f"{d[0].get('marca')} {d[0].get('modelo')}: " + "; ".join(linhas[:3]) +
                f" (referência {d[0].get('mesReferencia')}).", "\n".join(linhas))
    tipo = {"carro": "cars", "carros": "cars", "moto": "motorcycles", "motos": "motorcycles",
            "caminhao": "trucks", "caminhoes": "trucks"}.get(str(tipo or "carros").lower(), "cars")
    nome, ano = separar_carro(v)
    marcas = _web.get_json(f"{FIPE}/{tipo}/brands")
    marca = next((m for m in marcas if m["name"].lower() in nome or nome.split()[0] in m["name"].lower()), None)
    candidatos = [marca] if marca else marcas[:0]
    modelo = None
    for mc in candidatos or []:
        modelos = _web.get_json(f"{FIPE}/{tipo}/brands/{mc['code']}/models")
        resto = nome.replace(mc["name"].lower(), "").strip() or nome
        modelo = _escolher(modelos, resto)
        if modelo:
            marca = mc
            break
    if not modelo:
        return ("Pelo nome só, não achei esse modelo. Diga a marca junto (ex.: 'Volkswagen Gol 2015') "
                "ou o código FIPE.", "")
    anos = _web.get_json(f"{FIPE}/{tipo}/brands/{marca['code']}/models/{modelo['code']}/years")
    ano_e = next((a for a in anos if ano and a["name"].startswith(ano)), anos[0] if anos else None)
    if not ano_e:
        return "Não há anos para esse modelo na FIPE.", ""
    d = _web.get_json(f"{FIPE}/{tipo}/brands/{marca['code']}/models/{modelo['code']}/years/{ano_e['code']}")
    fala = (f"{d.get('brand')} {d.get('model')} {d.get('modelYear')}: {d.get('price')} na FIPE "
            f"({d.get('referenceMonth')}).")
    if ano and not ano_e["name"].startswith(ano):
        fala += f" Não achei {ano}; usei {ano_e['name']}."
    return fala, f"Código FIPE {d.get('codeFipe')} · {d.get('fuel')}"


# ── frete ─────────────────────────────────────────────────────────────────────
def medidas(txt: str) -> tuple[float, float, float]:
    n = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", str(txt or ""))]
    return tuple(n[:3]) if len(n) >= 3 else (4.0, 20.0, 25.0)


def opcoes_frete(resposta) -> list[dict]:
    """Resposta do Melhor Envio → [{servico, preco, dias}] ordenado pelo preço (pura)."""
    saida = []
    for o in resposta if isinstance(resposta, list) else []:
        if o.get("error") or not o.get("price"):
            continue
        empresa = (o.get("company") or {}).get("name", "")
        saida.append({"servico": f"{empresa} {o.get('name', '')}".strip(),
                      "preco": float(str(o.get("custom_price") or o["price"]).replace(",", ".")),
                      "dias": int(o.get("custom_delivery_time") or o.get("delivery_time") or 0)})
    return sorted(saida, key=lambda x: x["preco"])


def texto_cliente(opcoes: list[dict], cep_dest: str, cliente: str = "") -> str:
    ola = f"Oi, {cliente.split()[0]}!" if cliente else "Oi!"
    linhas = [f"{ola} Fiz a cotação do frete para o CEP {cep_dest}:"]
    for o in opcoes[:3]:
        linhas.append(f"• {o['servico']}: {_brl(o['preco'])} — chega em até {o['dias']} dias úteis")
    linhas.append("Qual prefere? 😊")
    return "\n".join(linhas)


def frete(p: dict) -> tuple[str, str]:
    c = cfg("consulta_brasil", PLUGIN_SETTINGS)
    token, origem = str(c.get("melhor_envio_token") or "").strip(), digitos(c.get("cep_origem"))
    if not token or len(origem) != 8:
        return ("Para calcular o frete eu preciso do token gratuito do Melhor Envio e do seu CEP de origem, em "
                "⚙ → Super consulta Brasil.", "")
    destino = digitos(p.get("cep") or p.get("valor"))
    if len(destino) != 8:
        return "Qual o CEP do cliente?", ""
    peso_g = float(p.get("peso") or 300)
    a, l, cp = medidas(c.get("medidas_padrao"))
    a, l, cp = float(p.get("altura") or a), float(p.get("largura") or l), float(p.get("comprimento") or cp)
    corpo = {"from": {"postal_code": origem}, "to": {"postal_code": destino},
             "package": {"height": a, "width": l, "length": cp, "weight": round(peso_g / 1000, 3)},
             "options": {"insurance_value": float(p.get("valor_declarado") or 0), "receipt": False, "own_hand": False}}
    base = "https://sandbox.melhorenvio.com.br" if c.get("sandbox") else "https://melhorenvio.com.br"
    resp = _web.post_json(f"{base}/api/v2/me/shipment/calculate", corpo,
                          {"Authorization": f"Bearer {token}", "Accept": "application/json"})
    ops = opcoes_frete(resp)
    if not ops:
        return "O Melhor Envio não devolveu nenhuma opção para esse CEP e peso.", ""
    pronto = texto_cliente(ops, f"{destino[:5]}-{destino[5:]}", str(p.get("cliente") or ""))
    barato, rapido = ops[0], min(ops, key=lambda o: o["dias"])
    fala = f"Mais barato: {barato['servico']}, {_brl(barato['preco'])} em {barato['dias']} dias"
    if rapido is not barato:
        fala += f"; mais rápido: {rapido['servico']}, {_brl(rapido['preco'])} em {rapido['dias']} dias"
    return fala + ". Deixei a resposta pronta para o cliente no painel.", pronto


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "").lower()
    funcs = {"cnpj": lambda: cnpj(p.get("valor")), "cep": lambda: cep(p.get("valor") or p.get("cep")),
             "ddd": lambda: ddd(p.get("valor")), "banco": lambda: banco(p.get("valor")),
             "fipe": lambda: fipe(p.get("valor"), p.get("tipo") or "carros"), "frete": lambda: frete(p)}
    if a not in funcs:
        return "Use cnpj, cep, ddd, banco, fipe ou frete."
    try:
        fala, painel = funcs[a]()
    except _web.ErroWeb as e:
        if e.status == 404:
            return "Não encontrei isso na base pública."
        return f"Não consegui consultar agora: {e}."
    except Exception as e:
        return f"A consulta falhou: {e}"
    if painel:
        mostrar(player, f"CONSULTA — {a.upper()}", painel)
    return fala
