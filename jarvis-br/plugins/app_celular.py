"""
App do JARVIS no celular (fork PT-BR 2.0).

    "Jarvis, instala o app no meu celular"   → mostra o endereço e o passo a passo
    "Jarvis, status do app do celular"

O app (dashboard/static/movel.html) tem dois modos:
  📱 Celular — conversa por voz SOZINHO, mesmo com o PC desligado: usa a sua
     chave do Gemini direto do celular e a voz do próprio navegador. Abre
     links, toca música no Spotify/YouTube Music, prepara mensagem no WhatsApp,
     abre o discador, faz rota, lembretes e pesquisa.
  💻 PC — quando o PC está no ar, é o JARVIS completo (todas as ferramentas),
     com atalhos para a Central, o Monitor e o Holograma.

Para instalar e usar o microfone, o navegador exige HTTPS: use o Tailscale com
HTTPS ("liga o acesso remoto" faz o 'tailscale serve') ou o link da Cloudflare.
"""

from __future__ import annotations

from plugins._comum import cfg, mostrar

PLUGIN = {
    "name": "app_celular",
    "brief": "JARVIS app for the phone (installable web app): works alone (phone mode) or as the full JARVIS (PC mode).",
    "description": ("Phone app. action='instalar' shows the address (/movel over HTTPS) and the steps to install it; "
                    "'status'."),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "instalar | status"}},
                   "required": []},
}

PLUGIN_SETTINGS = {
    "namespace": "app_celular",
    "title": "App do celular",
    "fields": [
        {"key": "compartilhar_chave", "label": "Deixar o app (já logado no painel) trazer a chave do Gemini do PC",
         "type": "toggle", "default": False},
    ],
}


def chave_para_celular() -> dict:
    if not cfg("app_celular", PLUGIN_SETTINGS).get("compartilhar_chave"):
        return {"erro": "No PC, ligue ⚙ → App do celular → 'Deixar o app trazer a chave', ou cole a chave no celular."}
    try:
        from dashboard.server import _get_gemini_key
        chave = _get_gemini_key()
    except Exception:
        chave = None
    return {"chave": chave} if chave else {"erro": "O PC ainda não tem chave do Gemini."}


def enderecos_app() -> dict:
    from plugins import _tunel
    return {k: v.rstrip("/") + "/movel" for k, v in _tunel.enderecos().items()}


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "instalar").lower()
    try:
        end = enderecos_app()
        https = {k: v for k, v in end.items() if v.startswith("https://")}
        if acao == "status":
            return ("App do celular disponível em: " + ", ".join(end.values()) + "." if end else
                    "O painel do celular não está rodando.")
        if not end:
            return "O painel do celular não está rodando (precisa do fastapi e do uvicorn)."
        passos = ["1. No celular, abra no Chrome: " + (next(iter(https.values())) if https else
                                                         "um endereço HTTPS (veja abaixo)"),
                  "2. Entre com o link de uso único ('Jarvis, me dá o link do painel') para o modo PC.",
                  "3. Menu ⋮ → Instalar app (ou Adicionar à tela inicial).",
                  "4. No app, ⚙: cole a chave do Gemini (ou 'Trazer a chave do PC') para o modo Celular."]
        if not https:
            passos.append("\nSem HTTPS o navegador bloqueia o microfone e a instalação. Diga 'liga o acesso remoto': "
                          "com o Tailscale ele liga o HTTPS (tailscale serve); ou use o link da Cloudflare.")
        mostrar(player, "APP DO JARVIS NO CELULAR", "\n".join(passos) + "\n\nEndereços:\n" +
                "\n".join(f"{k.upper():<16} {v}" for k, v in end.items()))
        return "O passo a passo e os endereços estão na tela." + ("" if https else " Falta HTTPS: diga 'liga o acesso remoto'.")
    except Exception as e:
        return f"O app do celular falhou: {e}"
