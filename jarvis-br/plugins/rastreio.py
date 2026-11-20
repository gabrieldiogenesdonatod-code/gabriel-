"""
Rastreio de encomendas (fork PT-BR 2.5).

    "Jarvis, rastreia esse código: QB123456789BR, é o fone da Shopee"
    "Jarvis, rastreia esse código"            (pega o código que você copiou)
    "Jarvis, cadê minhas encomendas?"         "Jarvis, mostra as encomendas" (abre a tela)
    "Jarvis, rastreia o pedido do fornecedor Malhas Sul: AB123456789BR"   (lista da LOJA)

Ele avisa sozinho quando muda alguma coisa importante:
    "Senhor, sua encomenda saiu pra entrega."   "…foi entregue."   "…está esperando retirada."
    "…está esperando o pagamento da taxa de importação."   "…não foi entregue: destinatário ausente."

Funciona com Correios, Shopee Xpress, Mercado Livre, Jadlog, Loggi, J&T,
AliExpress e milhares de transportadoras pelo 17TRACK. Para ele acompanhar
SOZINHO precisa da sua chave grátis do 17TRACK (17track.net → API → copie a
"Security Key" → ⚙ → Rastreio de encomendas). Sem a chave ele guarda a lista e
abre a página de rastreio quando você pede. Tudo em memory/encomendas.json.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from plugins import _rastreio as R
from plugins._comum import MEMORIA, abrir_no_sistema, cfg, desfazer, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "rastreio",
    "brief": "Track packages (Correios, Shopee, Mercado Livre, carriers) and warn when they move; store supplier list.",
    "description": (
        "Package tracking. action='adicionar' with codigo (empty = the code the user copied), optional apelido "
        "(what it is), loja (Shopee, Mercado Livre, AliExpress…), categoria ('loja' for the store's supplier orders, "
        "else 'pessoal') and fornecedor. 'listar' (optional categoria) or 'status' with codigo/apelido for details. "
        "'atualizar' checks now. 'recebida' marks as received; 'remover' takes it off. 'tela' opens the packages "
        "window. 'abrir' opens the carrier page in the browser. JARVIS warns by himself when it changes "
        "(out for delivery, delivered, waiting pickup, import tax, problem)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "adicionar | listar | status | atualizar | recebida | remover | "
                                                        "tela | abrir"},
            "codigo": {"type": "STRING"}, "apelido": {"type": "STRING"}, "loja": {"type": "STRING"},
            "categoria": {"type": "STRING", "description": "pessoal | loja"}, "fornecedor": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "rastreio",
    "title": "Rastreio de encomendas",
    "fields": [
        {"key": "chave_17track", "label": "Chave da API do 17TRACK (17track.net → API → Security Key)",
         "type": "password", "default": ""},
        {"key": "intervalo_min", "label": "Olhar as encomendas a cada (minutos)", "type": "text", "default": "60"},
        {"key": "cada_movimento", "label": "Avisar também cada movimento (não só os importantes)", "type": "toggle",
         "default": False},
    ],
}

ARQ = MEMORIA / "encomendas.json"
_lock = threading.Lock()
_iniciou = threading.Event()
_ultimo_giro = {"ts": 0.0}


def _c() -> dict:
    return cfg("rastreio", PLUGIN_SETTINGS)


def _chave() -> str:
    return str(_c().get("chave_17track") or "").strip()


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("encomendas", [])
    return d


def _gravar(d: dict) -> None:
    ativos = [e for e in d["encomendas"] if not e.get("arquivada")]
    velhos = [e for e in d["encomendas"] if e.get("arquivada")][-150:]
    d["encomendas"] = ativos + velhos
    gravar_json(ARQ, d)


def achar(lista: list[dict], termo: str) -> list[dict]:
    t = str(termo or "").strip().lower()
    if not t:
        return []
    c = R.limpar(t)
    exato = [e for e in lista if e["codigo"] == c]
    if exato:
        return exato
    return [e for e in lista if t in str(e.get("apelido", "")).lower() or t in str(e.get("loja", "")).lower()
            or t in str(e.get("fornecedor", "")).lower() or (len(c) >= 4 and c in e["codigo"])]


def _descrever(e: dict, detalhe: bool = False) -> str:
    nome = e.get("apelido") or e["codigo"]
    extra = []
    if e.get("categoria") == "loja":
        extra.append(f"loja{(' · ' + e['fornecedor']) if e.get('fornecedor') else ''}")
    elif e.get("loja"):
        extra.append(e["loja"])
    st = R.STATUS.get(e.get("status") or "NotFound", e.get("status"))
    if e.get("status") == "Exception" and e.get("sub_status") in R.PROBLEMAS:
        st = R.PROBLEMAS[e["sub_status"]].format(a="a")
    ids = extra + ([e["codigo"]] if e.get("apelido") else [])
    linha = f"{nome}{(' (' + ', '.join(ids) + ')') if ids else ''} — {st}"
    if e.get("evento"):
        quando = R.ha_quanto(e.get("quando", ""))
        linha += f": {e['evento']}" + (f" — {e['local']}" if e.get("local") else "") + (f", {quando}" if quando else "")
    if detalhe and e.get("eventos"):
        linha += "\n" + "\n".join(f"   • {ev['quando'][:16].replace('T', ' ')}  {ev['texto']}"
                                  + (f" ({ev['local']})" if ev.get("local") else "") for ev in e["eventos"][:8])
    return linha


def _ler_area_transferencia() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


# ── atualização ───────────────────────────────────────────────────────────────
def _avisar(texto: str, prioridade: str) -> None:
    try:
        from plugins._notificar import notificar
        notificar(None, texto, titulo="Encomendas", etiqueta="ENCOMENDA",
                  prioridade="low" if prioridade == "baixa" else "default")
    except Exception as e:
        print(f"[Rastreio] {e}")


def atualizar(codigos: list[str] | None = None) -> list[str]:
    """Pergunta ao 17TRACK pelas encomendas abertas e avisa o que mudou. Devolve as frases."""
    chave = _chave()
    if not chave:
        return []
    with _lock:
        d = dados()
        abertas = [e for e in d["encomendas"] if not e.get("arquivada") and e.get("status") not in R.FIM
                   and (codigos is None or e["codigo"] in codigos)]
    if not abertas:
        return []
    falta_registrar = [e["codigo"] for e in abertas if not e.get("registrado")]
    registro = R.registrar_17(falta_registrar, chave) if falta_registrar else {}
    leituras = R.consultar_17([e["codigo"] for e in abertas], chave)
    cada = bool(_c().get("cada_movimento"))
    falas = []
    with _lock:
        d = dados()
        for e in d["encomendas"]:
            if e["codigo"] in registro:
                r = registro[e["codigo"]]
                e["registrado"] = r in ("ok", "ja")
                e["erro"] = "" if e["registrado"] else r
            info = leituras.get(e["codigo"])
            if not info:
                continue
            e["checado"] = time.time()
            if info.get("erro"):
                e["erro"] = info["erro"]
                continue
            mud = R.mudanca(e, info, cada)
            if info.get("transportadora"):
                e["transportadora"] = info["transportadora"]
            for k in ("status", "sub_status", "evento", "local", "quando", "eventos"):
                e[k] = info.get(k, e.get(k))
            e["erro"] = ""
            if mud:
                tipo, prioridade = mud
                e.setdefault("avisos", []).append(tipo)
                e.setdefault("historico", []).append({"ts": time.time(), "tipo": tipo, "status": e["status"]})
                if tipo == "entregue":
                    e["entregue_em"] = time.time()
                falas.append((R.frase(e, tipo, info), prioridade))
        _gravar(d)
    for texto, prioridade in falas:
        _avisar(texto, prioridade)
    return [t for t, _p in falas]


def _laco() -> None:
    time.sleep(90)
    while True:
        try:
            intervalo = max(20, int(float(str(_c().get("intervalo_min") or 60)))) * 60
        except ValueError:
            intervalo = 3600
        noite = datetime.now().hour < 7
        if _chave() and time.time() - _ultimo_giro["ts"] >= (intervalo * 3 if noite else intervalo):
            _ultimo_giro["ts"] = time.time()
            try:
                atualizar()
            except Exception as e:
                print(f"[Rastreio] {e}")
            _arquivar_entregues()
        time.sleep(300)


def _arquivar_entregues(dias: int = 7) -> None:
    with _lock:
        d = dados()
        mudou = False
        for e in d["encomendas"]:
            if not e.get("arquivada") and e.get("entregue_em") and time.time() - e["entregue_em"] > dias * 86400:
                e["arquivada"] = True
                mudou = True
        if mudou:
            _gravar(d)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    _registrar_rotas()
    threading.Thread(target=_laco, daemon=True, name="rastreio").start()


# ── ações ─────────────────────────────────────────────────────────────────────
def adicionar(codigo: str, apelido: str = "", loja: str = "", categoria: str = "", fornecedor: str = "") -> str:
    c = R.limpar(codigo)
    if not c:
        achados = R.achar_codigos(_ler_area_transferencia())
        if not achados:
            return ("Não achei um código de rastreio. Copie o código (Ctrl+C) e peça de novo, ou me diga o código.")
        if len(achados) > 1:
            return "Achei mais de um código no que você copiou: " + ", ".join(achados) + ". Qual deles?"
        c = achados[0]
    if len(c) < 8:
        return f"“{codigo}” não parece um código de rastreio. Pode repetir?"
    cat = "loja" if str(categoria or "").lower().startswith(("loja", "forne", "cristal")) or fornecedor else "pessoal"
    aviso_dv = " Atenção: o dígito verificador desse código não confere, confira se não trocou um número." \
        if R.s10_valido(c) is False else ""
    with _lock:
        d = dados()
        igual = next((e for e in d["encomendas"] if e["codigo"] == c and not e.get("arquivada")), None)
        if igual:
            for k, v in (("apelido", apelido), ("loja", loja), ("fornecedor", fornecedor)):
                if v:
                    igual[k] = v
            if categoria:
                igual["categoria"] = cat
            _gravar(d)
            return f"Esse eu já acompanho: {_descrever(igual)}."
        e = {"codigo": c, "apelido": str(apelido or "").strip(), "loja": str(loja or "").strip(),
             "categoria": cat, "fornecedor": str(fornecedor or "").strip(),
             "transportadora": R.transportadora_provavel(c), "status": "NotFound", "sub_status": "", "evento": "",
             "local": "", "quando": "", "eventos": [], "criada": time.time(), "registrado": False, "avisos": []}
        d["encomendas"].append(e)
        _gravar(d)
    onde = f" ({e['transportadora']})" if e["transportadora"] else ""
    lista = " na lista de pedidos da loja" if cat == "loja" else ""
    if not _chave():
        abrir_no_sistema(R.PAGINA_WEB.format(codigo=c))
        return (f"Anotei {c}{onde}{lista} e abri a página de rastreio.{aviso_dv} Para eu acompanhar sozinho e avisar "
                "quando sair pra entrega, crie uma conta grátis em 17track.net (menu API), copie a Security Key e "
                "cole em ⚙ → Rastreio de encomendas.")
    try:
        r = R.registrar_17([c], _chave()).get(c, "ok")
    except R.Erro17 as ex:
        return f"Anotei {c}{onde}{lista}, mas o 17TRACK falhou agora ({ex}). Eu tento de novo sozinho.{aviso_dv}"
    with _lock:
        d = dados()
        for x in d["encomendas"]:
            if x["codigo"] == c:
                x["registrado"] = r in ("ok", "ja")
                x["erro"] = "" if x["registrado"] else r
        _gravar(d)
    if r not in ("ok", "ja"):
        return f"Anotei {c}{onde}{lista}, mas o 17TRACK recusou: {r}.{aviso_dv}"
    threading.Thread(target=lambda: (time.sleep(45), atualizar(codigos=[c])), daemon=True).start()
    return f"Pronto, estou acompanhando {c}{onde}{lista}. Aviso quando mudar alguma coisa.{aviso_dv}"


def _registrar_rotas() -> None:
    try:
        from plugins import _arcade
        _arcade.ROTAS_GET["/api/encomendas"] = lambda q: estado_tela()
        _arcade.ROTAS_POST["/api/encomendas/cmd"] = comando_tela
    except Exception as e:
        print(f"[Rastreio] {e}")


def estado_tela() -> dict:
    d = dados()
    itens = []
    for e in d["encomendas"]:
        st = e.get("status") or "NotFound"
        itens.append({**{k: e.get(k) for k in ("codigo", "apelido", "loja", "categoria", "fornecedor", "transportadora",
                                                "status", "sub_status", "evento", "local", "quando", "erro",
                                                "arquivada", "criada")},
                      "status_pt": R.STATUS.get(st, st), "ha": R.ha_quanto(e.get("quando", "")),
                      "eventos": (e.get("eventos") or [])[:15], "link": R.PAGINA_WEB.format(codigo=e["codigo"])})
    return {"encomendas": itens, "tem_chave": bool(_chave())}


def comando_tela(b: dict) -> dict:
    acao = str(b.get("acao") or "")
    if acao == "adicionar":
        if not R.limpar(str(b.get("codigo") or "")):
            return {"ok": False, "fala": "Digite o código de rastreio."}
        return {"ok": True, "fala": adicionar(str(b.get("codigo")), str(b.get("apelido") or ""),
                                              str(b.get("loja") or ""), str(b.get("categoria") or ""),
                                              str(b.get("fornecedor") or ""))}
    if acao == "atualizar":
        try:
            return {"ok": True, "fala": " ".join(atualizar()) or "Olhei agora: nada mudou."}
        except R.Erro17 as e:
            return {"ok": False, "fala": str(e)}
    if acao in ("recebida", "remover"):
        return {"ok": True, "fala": _marcar(str(b.get("codigo") or ""), acao)}
    return {"ok": False, "fala": "ação desconhecida"}


def _marcar(termo: str, acao: str) -> str:
    with _lock:
        d = dados()
        alvo = achar([e for e in d["encomendas"] if not e.get("arquivada")], termo)
        if not alvo:
            return "Não achei essa encomenda."
        if len(alvo) > 1:
            return "Achei mais de uma: " + "; ".join(_descrever(e) for e in alvo[:4]) + ". Qual delas?"
        e = alvo[0]
        if acao == "recebida":
            e.update(status="Delivered", entregue_em=time.time(), arquivada=True)
            _gravar(d)
            return f"Marquei {e.get('apelido') or e['codigo']} como recebida."
        d["encomendas"] = [x for x in d["encomendas"] if x is not e]
        _gravar(d)
    copia = dict(e)

    def voltar() -> str:
        with _lock:
            dd = dados()
            dd["encomendas"].append(copia)
            _gravar(dd)
        return f"Voltei {copia.get('apelido') or copia['codigo']} para a lista."
    desfazer(f"remover encomenda {e['codigo']}", voltar)
    if _chave() and e.get("registrado"):
        threading.Thread(target=R.parar_17, args=([e["codigo"]], _chave()), daemon=True).start()
    return f"Tirei {e.get('apelido') or e['codigo']} da lista (dá para desfazer)."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "adicionar":
            return adicionar(str(p.get("codigo") or ""), str(p.get("apelido") or ""), str(p.get("loja") or ""),
                             str(p.get("categoria") or ""), str(p.get("fornecedor") or ""))
        if acao in ("recebida", "remover"):
            return _marcar(str(p.get("codigo") or p.get("apelido") or ""), acao)
        if acao == "atualizar":
            if not _chave():
                return "Sem a chave do 17TRACK eu não consigo olhar sozinho. Coloque em ⚙ → Rastreio de encomendas."
            falas = atualizar()
            return ("Mudou: " + " ".join(falas)) if falas else "Olhei agora: nada mudou nas encomendas."
        if acao == "tela":
            from plugins import _arcade
            _registrar_rotas()
            ok = _arcade.abrir_pagina("/encomendas", 900, 820)
            return "Abri a tela das encomendas." if ok else "Não consegui abrir a tela."
        if acao == "abrir":
            alvo = achar(dados()["encomendas"], str(p.get("codigo") or p.get("apelido") or ""))
            codigo = alvo[0]["codigo"] if alvo else R.limpar(str(p.get("codigo") or ""))
            if not codigo:
                return "Qual encomenda?"
            abrir_no_sistema(R.PAGINA_WEB.format(codigo=codigo))
            return f"Abri o rastreio de {codigo}."
        d = dados()
        ativas = [e for e in d["encomendas"] if not e.get("arquivada")]
        if acao == "status" and (p.get("codigo") or p.get("apelido")):
            alvo = achar(d["encomendas"], str(p.get("codigo") or p.get("apelido")))
            if not alvo:
                return "Não achei essa encomenda."
            return "\n".join(_descrever(e, detalhe=True) for e in alvo[:3])
        cat = str(p.get("categoria") or "").lower()
        if cat.startswith(("loja", "forne")):
            ativas = [e for e in ativas if e.get("categoria") == "loja"]
        elif cat.startswith("pesso"):
            ativas = [e for e in ativas if e.get("categoria") != "loja"]
        if not ativas:
            vazio = "Nenhum pedido da loja sendo acompanhado." if cat.startswith(("loja", "forne")) else \
                "Nenhuma encomenda sendo acompanhada."
            return vazio + ("" if _chave() else " (Dica: com a chave do 17TRACK eu aviso sozinho.)")
        loja = [e for e in ativas if e.get("categoria") == "loja"]
        pessoal = [e for e in ativas if e.get("categoria") != "loja"]
        partes = []
        if pessoal:
            partes.append("SUAS:\n" + "\n".join("• " + _descrever(e) for e in pessoal))
        if loja:
            partes.append("PEDIDOS DA LOJA:\n" + "\n".join("• " + _descrever(e) for e in loja))
        texto = "\n\n".join(partes)
        mostrar(player, "ENCOMENDAS", texto)
        registrar(player, f"Encomendas: {len(ativas)} em andamento")
        return texto
    except R.Erro17 as e:
        return f"O rastreio falhou: {e}."
    except Exception as e:
        return f"O rastreio falhou: {e}"
