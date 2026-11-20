"""Lista de espera da loja (2.19): cliente quer uma peça ou tamanho que acabou; quando chegar, o JARVIS diz quem avisar."""
from __future__ import annotations

from plugins._lote2 import P, carregar, guardar, hoje, norm, rodar

PLUGIN = P("lista_espera", "Store waitlist: customer wants an out-of-stock item/size; when it arrives, who to notify (with message); most-requested items.",
           "adicionar | chegou | avisado | pendentes | mais_pedidos",
           "adicionar: cliente, produto, tamanho, telefone. chegou: produto, tamanho -> customers to notify. avisado: cliente.",
           "cliente produto tamanho telefone")


def interessados(fila: list[dict], produto: str, tamanho: str = "") -> list[dict]:
    q, t = norm(produto), norm(tamanho)
    return [x for x in fila if (q in norm(x["produto"]) or norm(x["produto"]) in q) and (not t or not x["tamanho"] or norm(x["tamanho"]) == t)]


def _go(p, pl):
    a, fila = p["action"], carregar("lista_espera", [])
    if a == "adicionar":
        fila.append({"cliente": str(p.get("cliente") or "").strip(), "produto": str(p.get("produto") or "").strip(),
                     "tamanho": str(p.get("tamanho") or "").strip(), "fone": str(p.get("telefone") or ""), "desde": hoje()})
        guardar("lista_espera", fila)
        return f"{p.get('cliente')} na espera de {p.get('produto')} {p.get('tamanho') or ''}".strip() + "."
    if a == "chegou":
        quem = interessados(fila, p.get("produto"), p.get("tamanho"))
        if not quem:
            return "Ninguém estava esperando essa peça."
        return "Avise: " + "; ".join(f"{x['cliente']} {x['fone']}".strip() for x in quem) + \
            f".\nMensagem: Oi! Chegou {p.get('produto')} {p.get('tamanho') or ''} que você pediu 💛 Quer que eu separe?"
    if a == "avisado":
        q = norm(p.get("cliente"))
        nova = [x for x in fila if not (q and q in norm(x["cliente"]))]
        guardar("lista_espera", nova)
        return f"Tirei {len(fila) - len(nova)} pedido(s) da espera."
    if a == "mais_pedidos":
        cont: dict = {}
        for x in fila:
            k = f"{x['produto']} {x['tamanho']}".strip().lower()
            cont[k] = cont.get(k, 0) + 1
        return "; ".join(f"{k}: {n}" for k, n in sorted(cont.items(), key=lambda kv: -kv[1])[:8]) or "Lista vazia."
    return "\n".join(f"{x['cliente']}: {x['produto']} {x['tamanho']} (desde {x['desde']})" for x in fila) or "Ninguém na espera."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar chegou avisado pendentes mais_pedidos".split(), _go), player, "Lista de espera")
