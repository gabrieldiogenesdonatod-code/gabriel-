"""
Rastreio de encomendas (fork PT-BR 2.5). Começa com "_": não é ferramenta.

Puro (testado em tests/test_26_casa.py): limpar e reconhecer o código, conferir
o dígito verificador dos Correios, traduzir o status, decidir o que avisar e
montar a frase ("Senhor, sua encomenda saiu pra entrega.").

Rede: a API v2.2 do 17TRACK (https://api.17track.net), que acompanha
Correios, Shopee Xpress, Mercado Livre, Jadlog, Loggi, J&T, Total Express,
AliExpress/Cainiao e mais de 2.000 transportadoras com um código só. A chave é
sua (conta grátis em 17track.net → API; contas novas ganham uma cota única de
números grátis). Registrar um código gasta 1 da cota; consultar não gasta.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime

API = "https://api.17track.net/track/v2.2"
PAGINA_WEB = "https://t.17track.net/pt#nums={codigo}"

STATUS = {
    "NotFound": "ainda sem informação",
    "InfoReceived": "etiqueta criada, esperando a transportadora pegar",
    "InTransit": "a caminho",
    "Expired": "parou de atualizar",
    "AvailableForPickup": "esperando retirada",
    "OutForDelivery": "saiu pra entrega",
    "DeliveryFailure": "a entrega falhou",
    "Delivered": "entregue",
    "Exception": "teve um problema",
}
# {a} vira "a" (encomenda) ou "o" (pedido)
PROBLEMAS = {
    "Exception_Returning": "está voltando para o remetente",
    "Exception_Returned": "voltou para o remetente",
    "Exception_NoBody": "não foi entregue: não tinha ninguém para receber",
    "Exception_Security": "ficou retid{a} na fiscalização",
    "Exception_Damage": "foi danificad{a}",
    "Exception_Rejected": "foi recusad{a}",
    "Exception_Delayed": "está atrasad{a}",
    "Exception_Lost": "foi extraviad{a}",
    "Exception_Destroyed": "foi destruíd{a}",
    "Exception_Cancel": "foi cancelad{a}",
}
FIM = {"Delivered", "Expired"}
TAXA = re.compile(r"(?i)aguardando pagamento|pagamento (do|de) (imposto|tributo|taxa)|tributa[çc][ãa]o|"
                  r"minhas importa[çc][õo]es")
# lojas que pedem "do" ("do Mercado Livre"); o resto vai com "da" ("da Shopee")
MASCULINAS = ("mercado livre", "aliexpress", "submarino", "carrefour", "ebay", "magazine luiza", "boticario",
              "boticário", "walmart")
ERROS = {
    -18019901: "esse código já estava registrado",
    -18019907: "acabou a cota de hoje do 17TRACK",
    -18019908: "acabou a cota de números do 17TRACK",
}


# ── código ────────────────────────────────────────────────────────────────────
def limpar(codigo: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(codigo or "").upper())


def s10_valido(codigo: str) -> bool | None:
    """Padrão S10 da UPU (Correios e correios do mundo): AA123456789BR.
    True/False = confere o dígito verificador; None = não é desse formato."""
    c = limpar(codigo)
    if not re.fullmatch(r"[A-Z]{2}\d{9}[A-Z]{2}", c):
        return None
    soma = sum(int(d) * p for d, p in zip(c[2:10], (8, 6, 4, 2, 3, 5, 9, 7)))
    dv = 11 - soma % 11
    dv = 0 if dv == 10 else 5 if dv == 11 else dv
    return dv == int(c[10])


def transportadora_provavel(codigo: str) -> str:
    """Só o que dá para afirmar pelo formato; o resto o 17TRACK descobre."""
    c = limpar(codigo)
    if s10_valido(c) is not None:
        return "Correios" if c.endswith("BR") else "Correios – internacional"
    if re.fullmatch(r"LP\d{14}", c):
        return "Cainiao (AliExpress)"
    if re.fullmatch(r"YT\d{16}", c):
        return "YunExpress"
    return ""


def achar_codigos(texto: str) -> list[str]:
    """Códigos de rastreio num texto (área de transferência, e-mail, mensagem)."""
    t = str(texto or "").upper()
    achados = []
    for m in re.finditer(r"\b[A-Z]{2}\s?\d{3}\s?\d{3}\s?\d{3}\s?[A-Z]{2}\b", t):
        c = limpar(m.group(0))
        if s10_valido(c) and c not in achados:
            achados.append(c)
    for m in re.finditer(r"\b[A-Z0-9]{10,30}\b", t):
        c = m.group(0)
        if c in achados or sum(ch.isdigit() for ch in c) < 8 or s10_valido(c) is False:
            continue
        if not re.fullmatch(r"\d+", c) or len(c) >= 12:        # só números: 12+ (telefone e CPF ficam fora)
            achados.append(c)
    return achados[:10]


def preposicao(loja: str) -> str:
    return "do" if str(loja or "").strip().lower().startswith(MASCULINAS) else "da"


def rotulo(e: dict) -> tuple[str, bool]:
    """('sua encomenda da Shopee (fone)', feminino?) — o nome falado da encomenda."""
    apelido = str(e.get("apelido") or "").strip()
    loja = str(e.get("loja") or "").strip()
    if e.get("categoria") == "loja":
        quem = str(e.get("fornecedor") or loja).strip()
        base, fem = (f"o pedido do fornecedor {quem}" if quem else "o pedido da loja"), False
    else:
        base, fem = "sua encomenda", True
        if loja:
            base += f" {preposicao(loja)} {loja}"
    if apelido:
        base += f" ({apelido})"
    elif not loja and e.get("categoria") != "loja":
        base += f" {e.get('codigo', '')}".rstrip()
    return base, fem


# ── o que mudou (puro) ─────────────────────────────────────────────────────────
def mudanca(antes: dict, depois: dict, cada_movimento: bool = False) -> tuple[str, str] | None:
    """Compara duas leituras. (tipo, prioridade) do aviso, ou None.
    tipo: saiu | entregue | retirada | falhou | problema | taxa | postada | movimento."""
    sa, sd = antes.get("status") or "NotFound", depois.get("status") or "NotFound"
    ja = set(antes.get("avisos") or [])
    texto_novo = str(depois.get("evento") or "")
    evento_novo = texto_novo and (texto_novo, depois.get("quando")) != (antes.get("evento"), antes.get("quando"))
    if evento_novo and TAXA.search(texto_novo) and "taxa" not in ja and sd not in FIM:
        return "taxa", "normal"
    if sd != sa or (sd == "Exception" and depois.get("sub_status") != antes.get("sub_status")):
        if sd == "OutForDelivery":
            return "saiu", "normal"
        if sd == "Delivered":
            return "entregue", "normal"
        if sd == "AvailableForPickup":
            return "retirada", "normal"
        if sd == "DeliveryFailure":
            return "falhou", "normal"
        if sd == "Exception":
            return "problema", "normal"
        if sd == "InTransit" and sa in ("NotFound", "InfoReceived"):
            return "postada", "baixa"
    if cada_movimento and evento_novo and sd not in FIM:
        return "movimento", "baixa"
    return None


def frase(e: dict, tipo: str, info: dict) -> str:
    nome, fem = rotulo(e)
    a = "a" if fem else "o"
    local = str(info.get("local") or "").strip()
    evento = str(info.get("evento") or "").strip().rstrip(".")
    if tipo == "saiu":
        return f"Senhor, {nome} saiu pra entrega."
    if tipo == "entregue":
        return f"Senhor, {nome} foi entregue."
    if tipo == "retirada":
        return f"Senhor, {nome} está esperando retirada" + (f" em {local}." if local else ".")
    if tipo == "falhou":
        return f"Senhor, {nome} não foi entregue" + (f": {evento}." if evento else ".")
    if tipo == "problema":
        sub = str(info.get("sub_status") or "")
        txt = PROBLEMAS.get(sub, "teve um problema").format(a=a)
        return f"Senhor, {nome} {txt}" + (f" ({evento})." if evento and sub not in PROBLEMAS else ".")
    if tipo == "taxa":
        return f"Senhor, {nome} está esperando o pagamento da taxa de importação (Minhas Importações, no site dos Correios)."
    if tipo == "postada":
        return f"{nome[0].upper()}{nome[1:]} foi postad{a} e já está a caminho."
    return f"{nome[0].upper()}{nome[1:]}: {evento}" + (f" ({local})." if local else ".")


def ha_quanto(iso: str, agora: datetime | None = None) -> str:
    try:
        quando = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    agora = agora or datetime.now(quando.tzinfo)
    s = (agora - quando).total_seconds()
    if s < 3600:
        return f"há {max(1, int(s // 60))} min"
    if s < 86400:
        return f"há {int(s // 3600)} h"
    d = int(s // 86400)
    return "ontem" if d == 1 else f"há {d} dias"


# ── 17TRACK ────────────────────────────────────────────────────────────────────
class Erro17(Exception):
    pass


def _post(caminho: str, corpo, chave: str, timeout: float = 20):
    req = urllib.request.Request(f"{API}/{caminho}", data=json.dumps(corpo).encode("utf-8"), method="POST",
                                 headers={"17token": chave, "Content-Type": "application/json",
                                          "User-Agent": "JARVIS-BR/2.5"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise Erro17("o 17TRACK pediu para ir mais devagar (muitos pedidos)") from e
        if e.code in (401, 403):
            raise Erro17("a chave do 17TRACK não foi aceita (confira em ⚙ → Rastreio)") from e
        raise Erro17(f"o 17TRACK respondeu {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Erro17(f"sem conexão com o 17TRACK ({e})") from e
    if d.get("code") not in (0, None):
        cod = d.get("code")
        raise Erro17(ERROS.get(cod) or f"o 17TRACK recusou ({cod}: {(d.get('data') or {}).get('errors') or ''})")
    return d.get("data") or {}


def _lotes(itens: list, n: int = 40):
    for i in range(0, len(itens), n):
        yield itens[i:i + n]


def registrar_17(codigos: list[str], chave: str) -> dict[str, str]:
    """código → 'ok' (registrado agora), 'ja' (já estava) ou o motivo da recusa."""
    saida = {}
    for lote in _lotes(codigos):
        d = _post("register", [{"number": c} for c in lote], chave)
        for a in d.get("accepted") or []:
            saida[str(a.get("number"))] = "ok"
        for r in d.get("rejected") or []:
            err = r.get("error") or {}
            cod = err.get("code")
            saida[str(r.get("number"))] = "ja" if cod == -18019901 else (ERROS.get(cod) or
                                                                        str(err.get("message") or cod))
    return saida


def normalizar(item: dict) -> dict:
    """Um item 'accepted' do gettrackinfo → leitura simples."""
    ti = item.get("track_info") or {}
    ls = ti.get("latest_status") or {}
    le = ti.get("latest_event") or {}
    transp, eventos = "", []
    for p in ((ti.get("tracking") or {}).get("providers") or []):
        prov = p.get("provider") or {}
        transp = transp or str(prov.get("name") or prov.get("alias") or "")
        for ev in p.get("events") or []:
            eventos.append({"quando": ev.get("time_iso") or ev.get("time_utc") or "",
                            "texto": str(ev.get("description") or ""), "local": str(ev.get("location") or "")})

    def chave_tempo(ev):
        try:
            return datetime.fromisoformat(str(ev["quando"]).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    eventos.sort(key=chave_tempo, reverse=True)
    prim = eventos[0] if eventos else {}
    return {"status": str(ls.get("status") or "NotFound"), "sub_status": str(ls.get("sub_status") or ""),
            "evento": str(le.get("description") or prim.get("texto") or ""),
            "local": str(le.get("location") or prim.get("local") or ""),
            "quando": str(le.get("time_iso") or le.get("time_utc") or prim.get("quando") or ""),
            "transportadora": transp, "eventos": eventos[:40]}


def consultar_17(codigos: list[str], chave: str) -> dict[str, dict]:
    """código → leitura normalizada (ou {'erro': ...} se o 17TRACK recusou esse código)."""
    saida = {}
    for lote in _lotes(codigos):
        d = _post("gettrackinfo", [{"number": c} for c in lote], chave)
        for a in d.get("accepted") or []:
            saida[str(a.get("number"))] = normalizar(a)
        for r in d.get("rejected") or []:
            err = r.get("error") or {}
            saida[str(r.get("number"))] = {"erro": str(err.get("message") or err.get("code") or "recusado")}
    return saida


def cota_17(chave: str) -> dict:
    return _post("getquota", {}, chave)


def parar_17(codigos: list[str], chave: str) -> None:
    """Para de acompanhar no 17TRACK (não devolve cota, só deixa a conta limpa)."""
    for lote in _lotes(codigos):
        try:
            _post("deletetrack", [{"number": c} for c in lote], chave)
        except Erro17 as e:
            print(f"[Rastreio] {e}")
