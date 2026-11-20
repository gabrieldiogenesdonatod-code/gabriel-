"""
Acesso remoto pela internet (fork PT-BR 1.8).

    "Jarvis, liga o acesso remoto"        → Tailscale e/ou link da Cloudflare
    "Jarvis, me dá o link do painel"      → link de uso único (10 min) que já entra
    "Jarvis, instala o Tailscale"
    "Jarvis, desliga o acesso remoto"
    "Jarvis, status do acesso remoto"

Fora de casa, o painel do celular ganha a CENTRAL (🛰): câmeras ao vivo (webcam
do PC e câmeras IP), a tela do PC, o monitor, as TVs, celulares, PCs e luzes.
O WhatsApp é a outra porta de entrada (ferramenta whatsapp_jarvis).
"""

from __future__ import annotations

import threading

from plugins import _tunel
from plugins._comum import cfg, mostrar

PLUGIN = {
    "name": "acesso_remoto",
    "brief": "Remote access from anywhere: Tailscale and/or Cloudflare tunnel to the JARVIS phone panel "
             "(live cameras, PC screen, monitor, TVs, phones, lights).",
    "description": (
        "Remote access over the internet to the JARVIS phone panel. action='ligar' (optional modo: tailscale | "
        "cloudflare | ambos) turns it on and returns the addresses; 'link' makes a one-time login link (10 min) for "
        "each address — never read the key part aloud, it is shown on screen; 'desligar' stops the Cloudflare link; "
        "'status'; 'instalar_tailscale'; 'cameras' lists cameras. The panel's 🛰 Central page shows live cameras, the "
        "PC screen and device controls."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status | link | "
                                                                    "instalar_tailscale | cameras"},
                       "modo": {"type": "STRING", "description": "tailscale | cloudflare | ambos"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "acesso_remoto",
    "title": "Acesso remoto (internet)",
    "fields": [
        {"key": "modo", "label": "Caminho pela internet", "type": "choice",
         "options": ["ambos", "tailscale", "cloudflare"], "default": "ambos"},
        {"key": "ligar_ao_abrir", "label": "Ligar o acesso remoto quando o JARVIS abrir", "type": "toggle",
         "default": False},
        {"key": "mandar_link_whatsapp", "label": "Quando o link da Cloudflare mudar, mandar no seu WhatsApp",
         "type": "toggle", "default": True},
        {"key": "cameras_ip", "label": "Câmeras IP (Nome=rtsp://… ; separe com ponto e vírgula)", "type": "text",
         "default": ""},
    ],
}

_iniciou = threading.Event()


def _config() -> dict:
    return cfg("acesso_remoto", PLUGIN_SETTINGS)


def ligar(modo: str = "") -> str:
    modo = (modo or _config().get("modo") or "ambos").lower()
    modo = "ambos" if modo not in ("tailscale", "cloudflare") else modo
    srv = _tunel.painel()
    if srv is None:
        return ("O painel do celular não está rodando (precisa do fastapi e do uvicorn: "
                "python -m pip install fastapi \"uvicorn[standard]\"). Sem ele não há o que acessar de fora.")
    partes = []
    if modo in ("tailscale", "ambos"):
        ts = _tunel.tailscale_status()
        if ts["estado"] == "ausente":
            partes.append("Tailscale não instalado (diga 'instala o Tailscale')")
        elif ts["estado"] != "Running":
            partes.append(f"Tailscale instalado, mas não conectado ({ts['estado'] or 'parado'}): abra o Tailscale e entre "
                          "com a sua conta")
        else:
            local, _https = _tunel.endereco_local(srv)
            erro_https = _tunel.tailscale_https(local)               # 2.0: HTTPS para o app do celular
            partes.append("Tailscale ligado" + (" com HTTPS" if not erro_https else f" (sem HTTPS: {erro_https})"))
    if modo in ("cloudflare", "ambos"):
        local, https = _tunel.endereco_local(srv)
        antigo = _tunel.cloudflare_url()
        url, erro = _tunel.cloudflare_ligar(local, sem_verificar_tls=https)
        if url:
            partes.append("link da Cloudflare ligado")
            if url != antigo:
                _mandar_link_whatsapp(url)
        else:
            partes.append(f"Cloudflare falhou: {erro}")
    end = _tunel.enderecos()
    linhas = [f"{k.upper():<11} {v}" for k, v in end.items()]
    mostrar(None, "ACESSO REMOTO", "\n".join(linhas) + "\n\nNo celular: abra o endereço, entre com o link de "
            "uso único ('me dá o link do painel') e toque em 🛰 Central.")
    return "; ".join(partes) + ". Os endereços estão na tela."


def _mandar_link_whatsapp(url: str) -> None:
    if not _config().get("mandar_link_whatsapp", True):
        return
    try:
        from plugins import _whatsapp
        if _whatsapp.pronto():
            link = _tunel.link_de_entrada(url)
            _whatsapp.para_donos(f"🛰 Acesso remoto ligado.\nLink de entrada (uso único, 10 min):\n{link}\n\n"
                                 f"Endereço: {url}")
    except Exception as e:
        print(f"[AcessoRemoto] WhatsApp: {e}")


def links() -> dict:
    srv = _tunel.painel()
    return {k: _tunel.link_de_entrada(v, srv) for k, v in _tunel.enderecos().items()} if srv else {}


def status() -> str:
    srv = _tunel.painel()
    if srv is None:
        return "O painel do celular não está rodando."
    ts = _tunel.tailscale_status()
    end = _tunel.enderecos()
    estado_ts = {"ausente": "não instalado", "Running": "conectado"}.get(ts["estado"], ts["estado"] or "parado")
    txt = [f"Tailscale: {estado_ts}"]
    if end.get("tailscale"):
        txt.append(f"pelo Tailscale: {end['tailscale']}")
    txt.append(f"Cloudflare: {end['cloudflare']}" if end.get("cloudflare") else "Cloudflare: desligado")
    try:
        from plugins import _whatsapp
        txt.append(f"WhatsApp: {_whatsapp.estado().get('estado', 'desligado')}")
    except Exception:
        pass
    return ". ".join(txt) + "."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "ligar":
            return ligar(str(p.get("modo") or ""))
        if acao == "desligar":
            return "Link da Cloudflare desligado." if _tunel.cloudflare_desligar() else \
                "O link da Cloudflare já estava desligado (o Tailscale você desliga no próprio app)."
        if acao == "link":
            ls = links()
            if not ls:
                return "O painel do celular não está rodando."
            mostrar(player, "LINK DE ENTRADA (uso único, 10 min)", "\n\n".join(f"{k.upper()}\n{v}" for k, v in ls.items()))
            return ("Pus o link de entrada na tela; vale uma vez, por 10 minutos."
                    + ("" if len(ls) > 1 else " Para usar fora de casa, ligue o acesso remoto antes."))
        if acao == "instalar_tailscale":
            return _tunel.instalar_tailscale()
        if acao == "cameras":
            from plugins._camera_remota import cameras
            return "Câmeras: " + ", ".join(c["nome"] for c in cameras()) + "."
        return status()
    except Exception as e:
        return f"O acesso remoto falhou: {e}"


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if _config().get("ligar_ao_abrir"):
        import time
        time.sleep(8)                                          # o painel sobe junto com o JARVIS
        print(f"[AcessoRemoto] {ligar()}")
