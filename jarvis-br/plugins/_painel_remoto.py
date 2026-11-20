"""
Monitor e controle pelo celular — rotas extras do painel remoto (FastAPI).

Começa com "_": não é ferramenta de voz. O dashboard/server.py chama
`registrar_rotas(app, auth, ler_estatico)` ao montar o servidor, e estas rotas
passam a existir no mesmo endereço do QR code de ◉ CONTROLE REMOTO:

    GET  /monitor                → página com status ao vivo, top de processos
                                   e botões (bloquear, desligar, abrir app…)
    GET  /api/monitor/status     → métricas (da mesma core/telemetria.py do HUD)
    GET  /api/monitor/processos  → top de processos (?ordem=cpu|ram|disco|rede)
    POST /api/monitor/acao       → {"acao": "...", "alvo": "..."}

SEGURANÇA
    Toda rota de API exige o MESMO token de login do painel (o que o celular
    ganha ao parear com a chave de 8 caracteres). Sem token: 401.
    Desligar e reiniciar dão 60 segundos de aviso e podem ser cancelados; a
    página pergunta "tem certeza?" antes de mandar. Finalizar processo respeita
    a lista de proteção (plugins/_protecao.py).

Sem `from __future__ import annotations` aqui de propósito: o FastAPI lê as
anotações das funções para saber que `req` é a requisição.
"""

import asyncio
import time

try:
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, Response
except ImportError:                              # sem FastAPI, o painel nem sobe
    Request = None


def resumo_status() -> dict:
    from core import telemetria
    s = telemetria.get().snapshot()
    g = s.get("gpu") or {}
    ping = ((s.get("ping") or {}).get("8.8.8.8") or {}).get("ms")
    procs = sorted(s.get("processos") or [], key=lambda p: p["cpu"], reverse=True)[:5]
    extras = {}
    try:
        from plugins._comum import ler_json, MEMORIA
        extras["modo_jogo"] = bool((ler_json(MEMORIA / "modo_jogo.json", {}) or {}).get("ativo"))
    except Exception:
        pass
    try:
        from plugins import gravador_tela
        extras["gravando"] = bool(gravador_tela._estado.get("ativo"))
    except Exception:
        pass
    return {
        "cpu": round(s.get("cpu") or 0, 1), "nucleos": s.get("cpu_nucleos", []),
        "cpu_temp": s.get("cpu_temp"), "freq": s.get("cpu_freq_mhz"),
        "ram": (s.get("ram") or {}).get("pct"), "ram_usada": (s.get("ram") or {}).get("usada"),
        "ram_total": (s.get("ram") or {}).get("total"),
        "gpu": g.get("uso"), "gpu_temp": g.get("temp"), "gpu_nome": g.get("nome"),
        "down": (s.get("rede") or {}).get("down"), "up": (s.get("rede") or {}).get("up"),
        "hoje_down": (s.get("rede_hoje") or {}).get("down"), "hoje_up": (s.get("rede_hoje") or {}).get("up"),
        "internet": s.get("internet"), "ping": ping, "wifi": s.get("wifi") or {},
        "discos": [{"ponto": p["ponto"], "pct": p["pct"], "livre": p["livre"]} for p in s.get("particoes", [])],
        "bateria": s.get("bateria"), "uptime": s.get("uptime"),
        "processos": s.get("total_processos"),
        "top": [{"pid": p["pid"], "nome": p["nome"], "cpu": p["cpu"], "ram": p["ram"]} for p in procs],
        "hora": time.strftime("%H:%M:%S"), **extras,
    }


def lista_processos(ordem: str = "cpu", n: int = 40) -> list[dict]:
    from core import telemetria
    from plugins.monitor_sistema import ordenar_processos
    procs = ordenar_processos(telemetria.get().snapshot().get("processos") or [], ordem)
    return [{"pid": p["pid"], "nome": p["nome"], "cpu": p["cpu"], "ram": p["ram"],
             "disco": p["disco"], "conexoes": p.get("conexoes", 0)} for p in procs[:n]]


def _evento(msg: str) -> None:
    print(f"[Celular] {msg}")
    try:
        from plugins import _monitor_db
        _monitor_db.gravar_evento("celular", msg)
    except Exception:
        pass


def executar_acao(acao: str, alvo: str = "") -> str:
    """Ações do celular. Quem chama já passou pelo login do painel."""
    acao = str(acao or "").strip().lower()
    alvo = str(alvo or "").strip()
    from plugins._comum import WIN, rodar
    if acao == "bloquear":
        from plugins.controle_pc import bloquear_tela
        r = bloquear_tela()
    elif acao in ("desligar", "reiniciar"):
        if WIN:
            c, out = rodar(["shutdown", "/s" if acao == "desligar" else "/r", "/t", "60"])
            r = (f"O PC vai {acao} em 60 segundos. Toque em CANCELAR para desistir."
                 if c == 0 else f"O Windows recusou: {out[:80]}")
        else:
            import threading

            from plugins import controle_pc
            fn = controle_pc._cmd_energia(acao)
            if fn is None:
                return "Não disponível neste sistema."
            t = threading.Timer(60, fn)
            t.daemon = True
            controle_pc._agendamento.update({"operacao": acao, "timer": t})
            t.start()
            r = f"O PC vai {acao} em 60 segundos. Toque em CANCELAR para desistir."
    elif acao == "cancelar":
        from plugins.controle_pc import _cancelar_agendamento
        r = _cancelar_agendamento()
    elif acao == "abrir_app":
        if not alvo:
            return "Qual app?"
        from plugins import _indice_apps
        ok, e = _indice_apps.abrir(alvo)
        if not ok:
            from actions.open_app import open_app
            open_app({"app_name": alvo})
            r = f"Pedi para abrir {alvo}."
        else:
            r = f"Abrindo {e['nome']}."
    elif acao == "finalizar":
        from plugins import _processos
        r = _processos.finalizar(_processos.achar_pids([alvo]) if alvo.isdigit() else _processos.achar(alvo))
    elif acao == "modo_jogo":
        from plugins import modo_jogo
        r = modo_jogo.desligar(None) if alvo in ("desligar", "normal") else modo_jogo.ligar(None)
    elif acao == "mudo":
        from plugins.controle_audio_video import _mudo
        r = _mudo(None)
    elif acao == "volume":
        from plugins.controle_audio_video import _volume
        r = _volume(alvo or "50")
    else:
        return "Ação desconhecida."
    _evento(f"{acao}{(' ' + alvo) if alvo else ''}: {r}")
    return r


# ── 1.8: aparelhos pela Central ───────────────────────────────────────────
ACOES_APARELHO = {"ligar", "desligar", "reiniciar", "suspender", "bloquear", "status", "tecla", "volume",
                  "abrir", "fechar"}


def lista_aparelhos() -> list[dict]:
    from plugins import aparelhos as ap
    return [{"nome": a["nome"], "tipo": a.get("tipo", ""), "plataforma": ap.plataforma(a.get("tipo", "")),
             "nome_tipo": ap.NOMES_TIPO.get(a.get("tipo", ""), a.get("tipo", ""))} for a in ap.todos(ap.carregar())]


def acao_aparelho(corpo: dict) -> str:
    """Pedido da Central → ferramenta aparelhos (só ações de controle; 'rodar' e 'remover' ficam de fora)."""
    acao = str(corpo.get("acao") or "").strip().lower()
    nome = str(corpo.get("aparelho") or "").strip()
    if acao not in ACOES_APARELHO or not nome:
        return "Ação não permitida pela Central."
    params = {"action": acao, "aparelho": nome}
    for k in ("tecla", "alvo", "direcao", "vezes"):
        if corpo.get(k) not in (None, ""):
            params[k] = str(corpo[k])[:120]
    from plugins import aparelhos
    if acao in ("desligar", "reiniciar") and corpo.get("confirmado"):
        # A página já perguntou "tem certeza?" no celular; o botão CONFIRMAR do HUD não dá para apertar de longe.
        alvos = aparelhos.achar(aparelhos.todos(aparelhos.carregar()), nome)
        if len(alvos) == 1 and aparelhos.plataforma(alvos[0].get("tipo", "")) == "pc":
            a = alvos[0]
            return aparelhos._frase_pc(a["nome"], aparelhos.pc(a, acao, {"segundos": 10}))
    return aparelhos.run(params)


def registrar_rotas(app, auth, ler_estatico) -> None:
    if Request is None:
        return

    def negar():
        return JSONResponse({"erro": "Não autorizado"}, status_code=401)

    # Fork PT-BR 2.3: a Twilio pergunta o que fazer quando alguém liga (plugins/_atendente_voz.py).
    # Não usa o token do painel (a Twilio não tem): vale a assinatura X-Twilio-Signature.
    @app.post("/twilio/{etapa}")
    async def twilio_webhook(etapa: str, req: Request):
        import urllib.parse

        from plugins import _atendente_voz as A
        if etapa not in ("voz", "pin", "fala", "aguardar", "fim"):
            return Response("rota", status_code=404)
        corpo = (await req.body())[:20000].decode("utf-8", "replace")
        params = dict(urllib.parse.parse_qsl(corpo, keep_blank_values=True))
        c = A._c()
        urls = A.urls_candidatas(str(c.get("url_publica") or ""), req.url.path, req.url.query,
                                 req.headers.get("host", ""))
        if not A.assinatura_valida(urls, params, req.headers.get("x-twilio-signature", ""), str(c.get("token") or "").strip()):
            return Response("assinatura", status_code=403)
        xml = await asyncio.to_thread(A.tratar, etapa, params)
        return Response(xml, media_type="application/xml")

    # Fork PT-BR 1.6: armadura (status do traje) e realidade aumentada no celular.
    @app.get("/armadura", response_class=HTMLResponse)
    async def pagina_armadura():
        return HTMLResponse(ler_estatico("armadura.html"))

    @app.get("/ar", response_class=HTMLResponse)
    async def pagina_ar():
        return HTMLResponse(ler_estatico("ar.html"))

    @app.get("/api/armadura")
    async def api_armadura(req: Request):
        if not auth(req):
            return negar()
        from plugins.armadura import status_traje
        return JSONResponse(await asyncio.to_thread(status_traje, False))

    @app.post("/api/ar/perguntar")
    async def api_ar(req: Request):
        if not auth(req):
            return negar()
        try:
            corpo = await req.json()
        except Exception:
            corpo = {}
        from plugins.realidade_aumentada import perguntar_imagem
        texto = await asyncio.to_thread(perguntar_imagem, str(corpo.get("imagem") or ""),
                                        str(corpo.get("pergunta") or ""))
        return JSONResponse({"texto": texto})

    # Fork PT-BR 1.8: CENTRAL — câmeras ao vivo, tela do PC e aparelhos (para usar de fora de casa).
    # Fork PT-BR 2.0: app do celular (PWA). A casca é pública (é só HTML); tudo que mexe no PC pede o token.
    @app.get("/movel", response_class=HTMLResponse)
    async def pagina_movel():
        return HTMLResponse(ler_estatico("movel.html"))

    @app.get("/movel.webmanifest")
    async def manifesto_movel():
        return Response(ler_estatico("movel.webmanifest"), media_type="application/manifest+json")

    @app.get("/sw-movel.js")
    async def sw_movel():
        return Response(ler_estatico("sw-movel.js"), media_type="text/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

    @app.get("/icone-jarvis.svg")
    async def icone_jarvis():
        return Response(ler_estatico("icone-jarvis.svg"), media_type="image/svg+xml")

    @app.get("/api/movel/chave")
    async def chave_movel(req: Request):
        if not auth(req):
            return negar()
        from plugins.app_celular import chave_para_celular
        return JSONResponse(chave_para_celular())

    # Fork PT-BR 1.9: holograma de pirâmide (o rosto do JARVIS em 4 lados).
    @app.get("/holograma", response_class=HTMLResponse)
    async def pagina_holograma():
        return HTMLResponse(ler_estatico("holograma.html"))

    @app.get("/central", response_class=HTMLResponse)
    async def pagina_central():
        return HTMLResponse(ler_estatico("central.html"))

    @app.get("/api/remoto/cameras")
    async def remoto_cameras(req: Request):
        if not auth(req):
            return negar()
        from plugins._camera_remota import cameras
        return JSONResponse({"cameras": [{"id": c["id"], "nome": c["nome"]} for c in cameras()]})

    @app.get("/api/remoto/camera/{cam_id}")
    async def remoto_camera(cam_id: int, req: Request):
        if not auth(req):
            return negar()
        from plugins._camera_remota import foto_jpeg
        dados, erro = await asyncio.to_thread(foto_jpeg, cam_id)
        if not dados:
            return JSONResponse({"erro": erro}, status_code=503)
        return Response(dados, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/remoto/tela")
    async def remoto_tela(req: Request):
        if not auth(req):
            return negar()
        from plugins._camera_remota import tela_jpeg
        dados, erro = await asyncio.to_thread(tela_jpeg)
        if not dados:
            return JSONResponse({"erro": erro}, status_code=503)
        return Response(dados, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/remoto/aparelhos")
    async def remoto_aparelhos(req: Request):
        if not auth(req):
            return negar()
        return JSONResponse({"aparelhos": await asyncio.to_thread(lista_aparelhos)})

    @app.post("/api/remoto/aparelho")
    async def remoto_aparelho(req: Request):
        if not auth(req):
            return negar()
        try:
            corpo = await req.json()
        except Exception:
            corpo = {}
        msg = await asyncio.to_thread(acao_aparelho, corpo)
        _evento(f"aparelho {corpo.get('aparelho')} {corpo.get('acao')}: {msg}")
        return JSONResponse({"ok": True, "mensagem": msg})

    @app.get("/monitor", response_class=HTMLResponse)
    async def pagina_monitor():
        # Como a página principal: o login é conferido pelo JavaScript (token
        # no sessionStorage) e de novo, no servidor, em cada chamada de API.
        return HTMLResponse(ler_estatico("monitor.html"))

    @app.get("/api/monitor/status")
    async def monitor_status(req: Request):
        if not auth(req):
            return negar()
        return JSONResponse(await asyncio.to_thread(resumo_status))

    @app.get("/api/monitor/processos")
    async def monitor_processos(req: Request, ordem: str = "cpu"):
        if not auth(req):
            return negar()
        return JSONResponse({"processos": await asyncio.to_thread(lista_processos, ordem)})

    @app.post("/api/monitor/acao")
    async def monitor_acao(req: Request):
        if not auth(req):
            return negar()
        try:
            corpo = await req.json()
        except Exception:
            corpo = {}
        try:
            msg = await asyncio.to_thread(executar_acao, corpo.get("acao"), corpo.get("alvo"))
        except Exception as e:
            msg = f"Falhou: {e}"
        return JSONResponse({"ok": True, "mensagem": msg})
