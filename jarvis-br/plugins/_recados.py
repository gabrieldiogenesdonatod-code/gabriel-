"""
Recados (fork PT-BR 2.3). Começa com "_": não é ferramenta.

Quem te ligou e deixou recado — pelo WhatsApp (a secretária recusa a ligação
e pede o recado por mensagem) ou pelo número da Twilio (o atendente de voz
anota). Fica em memory/recados.json, só no seu PC.

    "Jarvis, tem recado?" / "lê os recados" / "apaga os recados"
"""

from __future__ import annotations

import threading
import time

from plugins._comum import MEMORIA, gravar_json, ler_json

ARQ = MEMORIA / "recados.json"
_lock = threading.Lock()


def todos() -> list[dict]:
    r = ler_json(ARQ, []) or []
    return r if isinstance(r, list) else []


def adicionar(origem: str, nome: str, numero: str, texto: str, chat: str = "") -> dict:
    """Guarda (ou junta ao recado aberto da mesma pessoa nos últimos 10 min)."""
    texto = str(texto or "").strip()
    with _lock:
        rs = todos()
        agora = time.time()
        r = next((x for x in reversed(rs) if x.get("origem") == origem and x.get("numero") == numero
                  and (chat == "" or x.get("chat") == chat) and agora - x.get("ts", 0) < 600 and not x.get("lido")), None)
        if r is not None and texto:
            r["texto"] = (r["texto"] + "\n" + texto).strip()[-3000:]
            r["ts"] = agora
        elif r is None:
            r = {"id": (max([x.get("id", 0) for x in rs], default=0) % 9999) + 1, "origem": origem, "nome": nome or "",
                 "numero": numero or "", "chat": chat, "texto": texto[-3000:], "ts": agora, "lido": False}
            rs.append(r)
        gravar_json(ARQ, rs[-100:])
        return dict(r)


def novos() -> list[dict]:
    return [r for r in todos() if not r.get("lido")]


def texto_lista(rs: list[dict], agora: float | None = None) -> str:
    """Lista legível (pura)."""
    if not rs:
        return "Nenhum recado."
    agora = agora or time.time()
    linhas = []
    for r in rs[-15:]:
        min_ = max(0, int((agora - r.get("ts", agora)) // 60))
        quando = "agora há pouco" if min_ < 2 else (f"há {min_} min" if min_ < 120 else
                                                    time.strftime("%d/%m %H:%M", time.localtime(r.get("ts", agora))))
        via = {"whatsapp": "WhatsApp", "telefone": "telefone"}.get(r.get("origem"), r.get("origem", ""))
        quem = r.get("nome") or r.get("numero") or "alguém"
        linhas.append(f"#{r.get('id')} {quem} ({via}, {quando}): {r.get('texto') or '(ligou e não deixou recado)'}")
    return "\n".join(linhas)


def marcar_lidos() -> int:
    with _lock:
        rs = todos()
        n = sum(1 for r in rs if not r.get("lido"))
        for r in rs:
            r["lido"] = True
        gravar_json(ARQ, rs)
        return n


def limpar() -> int:
    with _lock:
        n = len(todos())
        gravar_json(ARQ, [])
        return n
