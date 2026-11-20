"""
Alerta de cotação (fork PT-BR 2.16, ideia 3).

    "Jarvis, me avisa quando o dólar passar de 5,80"
    "Jarvis, me avisa se o bitcoin cair abaixo de 300 mil"
    "Jarvis, avisa quando PETR4 passar de 40"
    "Jarvis, quanto está o dólar?"          "Jarvis, quais alertas de cotação eu tenho?"

Confere a cada 5 minutos com o JARVIS aberto e avisa por voz, no registro e no
celular (push, se configurado). Cada alerta dispara UMA vez; depois de disparar
ele só arma de novo se a cotação voltar para o outro lado.

Fontes: AwesomeAPI (moedas e cripto, grátis, sem chave) e brapi.dev para
ações da B3 (PETR4, VALE3, MGLU3 e ITUB4 funcionam sem chave; as outras precisam
de um token gratuito do brapi.dev, em ⚙ → Alerta de cotação).
"""

from __future__ import annotations

import re
import threading
import time

from plugins import _web
from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, plugin_ligado

PLUGIN = {
    "name": "alerta_cotacao",
    "brief": "Price alerts for dollar, euro, bitcoin and B3 stocks; current quote.",
    "description": (
        "Quote alerts. action='criar' with ativo (dolar, euro, bitcoin, ethereum, libra, or a B3 ticker like PETR4), "
        "condicao (acima | abaixo) and valor (in reais), for 'me avisa quando o dólar passar de 5,80'. "
        "action='cotacao' with ativo for the current price. action='listar'; action='apagar' with ativo (or 'todos')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "criar | cotacao | listar | apagar"},
            "ativo": {"type": "STRING"}, "condicao": {"type": "STRING"}, "valor": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "alerta_cotacao",
    "title": "Alerta de cotação",
    "fields": [{"key": "brapi_token", "label": "Token do brapi.dev (ações fora das 4 grátis)", "type": "password",
                "default": ""},
               {"key": "minutos", "label": "Conferir a cada (minutos)", "type": "number", "default": 5}],
}

ARQ = MEMORIA / "alertas_cotacao.json"
MOEDAS = {"dolar": "USD", "dólar": "USD", "usd": "USD", "euro": "EUR", "eur": "EUR", "libra": "GBP",
          "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH", "peso": "ARS", "iene": "JPY",
          "dolar canadense": "CAD"}
_thread: threading.Thread | None = None


def ativo_de(texto: str) -> tuple[str, str] | None:
    """'dólar' → ('moeda', 'USD'); 'petr4' → ('acao', 'PETR4') (pura)."""
    t = str(texto or "").strip().lower()
    if t in MOEDAS:
        return "moeda", MOEDAS[t]
    if t.upper() in MOEDAS.values():
        return "moeda", t.upper()
    if re.fullmatch(r"[a-z]{4}\d{1,2}", t):
        return "acao", t.upper()
    return None


def cotacao(tipo: str, codigo: str) -> float:
    if tipo == "moeda":
        d = _web.get_json(f"https://economia.awesomeapi.com.br/json/last/{codigo}-BRL")
        return float(d[f"{codigo}BRL"]["bid"])
    token = str(cfg("alerta_cotacao", PLUGIN_SETTINGS).get("brapi_token") or "").strip()
    d = _web.get_json(f"https://brapi.dev/api/quote/{codigo}", {"token": token} if token else None)
    return float(d["results"][0]["regularMarketPrice"])


def disparou(alerta: dict, preco: float) -> bool:
    """Atravessou o alvo agora? Usa 'armado' para avisar só uma vez (muda o alerta) (pura)."""
    passou = preco >= alerta["valor"] if alerta["condicao"] == "acima" else preco <= alerta["valor"]
    if passou and alerta.get("armado", True):
        alerta["armado"] = False
        return True
    if not passou:
        alerta["armado"] = True
    return False


def _brl(v: float, casas: int = 2) -> str:
    return "R$ " + f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def checar(player=None) -> list[str]:
    alertas = ler_json(ARQ, []) or []
    avisos, cache = [], {}
    for a in alertas:
        chave = (a["tipo"], a["codigo"])
        try:
            if chave not in cache:
                cache[chave] = cotacao(*chave)
        except Exception:
            continue
        preco = cache[chave]
        a["ultimo"] = preco
        if disparou(a, preco):
            avisos.append(f"{a['nome']} {'passou de' if a['condicao'] == 'acima' else 'caiu abaixo de'} "
                          f"{_brl(a['valor'])}: está em {_brl(preco, 4 if preco < 1 else 2)}.")
    gravar_json(ARQ, alertas)
    for t in avisos:
        try:
            from plugins._notificar import notificar
            notificar(player, f"💱 {t}", "Cotação")
        except Exception:
            from plugins._comum import avisar
            avisar(player, t, "COTAÇÃO")
    return avisos


def _laco(player) -> None:
    while True:
        minutos = max(1.0, float(cfg("alerta_cotacao", PLUGIN_SETTINGS).get("minutos") or 5))
        time.sleep(minutos * 60)
        if plugin_ligado("alerta_cotacao") and ler_json(ARQ, []):
            try:
                checar(player)
            except Exception as e:
                print(f"[Cotação] {e}")


def on_session_start(player) -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_laco, args=(player,), daemon=True, name="alerta_cotacao")
        _thread.start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    try:
        if a in ("criar", "cotacao"):
            nome = str(p.get("ativo") or "").strip()
            at = ativo_de(nome)
            if not at:
                return f"Não reconheço '{nome}'. Use dólar, euro, bitcoin, ethereum ou um código da B3 como PETR4."
            preco = cotacao(*at)
            if a == "cotacao":
                return f"{nome.capitalize() if at[0] == 'moeda' else at[1]} está em {_brl(preco, 4 if preco < 1 else 2)}."
            valor = float(p.get("valor") or 0)
            if valor <= 0:
                return "Qual valor?"
            cond = "abaixo" if str(p.get("condicao") or "").lower().startswith(("abaixo", "menos", "cair", "baix")) \
                else "acima"
            alertas = ler_json(ARQ, []) or []
            novo = {"nome": nome.capitalize() if at[0] == "moeda" else at[1], "tipo": at[0], "codigo": at[1],
                    "condicao": cond, "valor": valor, "armado": True, "ultimo": preco}
            disparou(novo, preco)                              # já passou? então só avisa quando voltar e passar
            alertas.append(novo)
            gravar_json(ARQ, alertas)
            on_session_start(player)
            agora = f" Agora está em {_brl(preco)}."
            if not novo["armado"]:
                agora += " Já está desse lado; aviso quando voltar e passar de novo."
            return f"Combinado: aviso quando {novo['nome']} ficar {cond} de {_brl(valor)}.{agora}"
        if a == "listar":
            alertas = ler_json(ARQ, []) or []
            if not alertas:
                return "Você não tem alertas de cotação."
            mostrar(player, "ALERTAS DE COTAÇÃO", "\n".join(
                f"{x['nome']:<10} {x['condicao']} de {_brl(x['valor'])}   (última: {_brl(x.get('ultimo') or 0)})"
                for x in alertas))
            return f"{len(alertas)} alerta(s): " + "; ".join(f"{x['nome']} {x['condicao']} de {_brl(x['valor'])}"
                                                           for x in alertas) + "."
        if a == "apagar":
            alvo = str(p.get("ativo") or "").lower()
            alertas = ler_json(ARQ, []) or []
            at = ativo_de(alvo)
            novos = [] if alvo in ("todos", "tudo") else [x for x in alertas if not at or x["codigo"] != at[1]]
            gravar_json(ARQ, novos)
            return f"Apaguei {len(alertas) - len(novos)} alerta(s)."
        return "Use criar, cotacao, listar ou apagar."
    except _web.ErroWeb as e:
        return f"Não consegui a cotação agora: {e}."
    except Exception as e:
        return f"O alerta de cotação falhou: {e}"
