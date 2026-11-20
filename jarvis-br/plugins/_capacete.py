"""
Modo capacete (ESP32) — o lado do servidor (fork PT-BR 1.4).

Começa com "_": não é ferramenta. O dashboard/server.py chama
`registrar_rota(app, servidor)` e o capacete vira mais um "terminal" do
MESMO JARVIS (como o microfone do celular): nada de segundo assistente.

    ESP32 → PC   frames binários: PCM 16 bits, mono, 16 kHz (microfone, só
                 enquanto o botão está apertado)
                 frames de texto: {"tipo": "ola" | "botao" | "texto", ...}
    PC → ESP32   frames binários: PCM 16 bits, mono, 24 kHz (a voz do JARVIS)
                 frames de texto: {"tipo": "ok"}

Endereço:  ws://IP-DO-PC:8000/ws/capacete?chave=CHAVE   (também em wss://…:8001)
A chave é fixa (não expira como as do celular) e fica em config/capacete.json;
"Jarvis, gera outra chave do capacete" troca.

Sem `from __future__ import annotations` de propósito: o FastAPI lê as
anotações (WebSocket) para injetar a conexão.
"""

import asyncio
import json
import secrets

from plugins._comum import CONFIG, gravar_json, ler_json

ARQ = CONFIG / "capacete.json"


def obter_chave(nova: bool = False) -> str:
    d = ler_json(ARQ, {}) or {}
    if nova or not d.get("chave"):
        d["chave"] = secrets.token_urlsafe(18)
        gravar_json(ARQ, d)
    return d["chave"]


def conectados(servidor) -> int:
    return len(getattr(servidor, "_capacetes", {}) or {})


def enviar_audio(servidor, pcm: bytes) -> None:
    """Chamado do laço de áudio do main.py (mesmo event loop). Nunca bloqueia."""
    for fila in list((getattr(servidor, "_capacetes", None) or {}).values()):
        try:
            fila.put_nowait(pcm)
        except asyncio.QueueFull:
            pass


def registrar_rota(app, servidor) -> None:
    from fastapi import WebSocket, WebSocketDisconnect

    if not hasattr(servidor, "_capacetes"):
        servidor._capacetes = {}

    @app.websocket("/ws/capacete")
    async def capacete_ws(websocket: WebSocket, chave: str = ""):
        recebida = (chave or "").strip()
        if not recebida or not secrets.compare_digest(recebida, obter_chave()):
            await websocket.close(code=4001)
            return
        pedidos = websocket.scope.get("subprotocols") or []
        await websocket.accept(subprotocol="arduino" if "arduino" in pedidos else None)
        fila: asyncio.Queue = asyncio.Queue(maxsize=60)
        servidor._capacetes[websocket] = fila

        async def enviar():
            while True:
                pcm = await fila.get()
                await websocket.send_bytes(pcm)

        tarefa = asyncio.create_task(enviar())
        try:
            await websocket.send_text(json.dumps({"tipo": "ok"}))
            asyncio.create_task(servidor.broadcast({"type": "sys", "text": "Capacete conectado."}))
            print("[Capacete] conectado")
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    try:
                        from core import verificacao
                        verificacao.marcar_origem_remota(30)       # o capacete tem a própria chave
                    except Exception:
                        pass
                    try:
                        servidor._phone_audio_queue.put_nowait({"data": msg["bytes"], "mime_type": "audio/pcm"})
                    except asyncio.QueueFull:
                        pass
                elif msg.get("text"):
                    try:
                        d = json.loads(msg["text"])
                    except Exception:
                        continue
                    if d.get("tipo") == "texto" and d.get("texto"):
                        await servidor._command_queue.put(str(d["texto"])[:500])
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[Capacete] {e}")
        finally:
            tarefa.cancel()
            servidor._capacetes.pop(websocket, None)
            print("[Capacete] desconectado")
            try:
                asyncio.create_task(servidor.broadcast({"type": "sys", "text": "Capacete desconectado."}))
            except Exception:
                pass
