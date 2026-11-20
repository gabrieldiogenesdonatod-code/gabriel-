"""
Missões em segundo plano (fork PT-BR 2.4) — veja core/missoes.py.

    "Jarvis, organiza as fotos da pasta Imagens"           (copia para Ano/Mês; o original fica)
    "Jarvis, organiza e MOVE as fotos da pasta Downloads"   (pede confirmação; dá para desfazer)
    "Jarvis, monitora o preço do PS5 por uma semana"        ("…e me avisa se chegar a 3 mil")
    "Jarvis, converte todos os vídeos da pasta Vídeos"
    "Jarvis, missões" / "abre o painel de missões"
    "Jarvis, pausa a missão 2" / "continua a 2" / "cancela a missão 2"
"""

from __future__ import annotations

import threading
from pathlib import Path

from core import missoes as M
from plugins._comum import confirmar, mostrar, pasta_usuario

PLUGIN = {
    "name": "missoes",
    "brief": "Long background missions that survive restarts: organize photos, watch a price for days, convert videos.",
    "description": (
        "Background missions (hours/days, resume after restart, MISSÕES panel with progress/pause/cancel). "
        "action='criar' with tipo = organizar_fotos (pasta; modo copiar|mover, default copiar), monitorar_preco "
        "(produto or url, dias default 7, optional alvo price in reais, optional intervalo_h) or converter_videos "
        "(pasta; to MP4). pasta may be a full path or a user folder name (Imagens, Vídeos, Downloads, Documentos, "
        "Área de Trabalho). action='listar'; 'painel' opens the MISSÕES page; 'pausar' | 'continuar' | 'cancelar' "
        "with id; 'desfazer' with id puts moved photos back."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "criar | listar | painel | pausar | continuar | cancelar | desfazer"},
            "tipo": {"type": "STRING", "description": "organizar_fotos | monitorar_preco | converter_videos"},
            "pasta": {"type": "STRING"}, "modo": {"type": "STRING"}, "produto": {"type": "STRING"},
            "url": {"type": "STRING"}, "dias": {"type": "NUMBER"}, "alvo": {"type": "NUMBER"},
            "intervalo_h": {"type": "NUMBER"}, "id": {"type": "INTEGER"},
        },
        "required": [],
    },
}

_iniciou = threading.Event()
PASTAS = {"imagens": "Pictures", "fotos": "Pictures", "pictures": "Pictures", "videos": "Videos", "vídeos": "Videos",
          "downloads": "Downloads", "documentos": "Documents", "area de trabalho": "Desktop",
          "área de trabalho": "Desktop", "desktop": "Desktop", "musicas": "Music", "músicas": "Music"}


def resolver_pasta(texto: str) -> Path | None:
    t = str(texto or "").strip().strip('"')
    if not t:
        return None
    p = Path(t).expanduser()
    if p.is_absolute():
        return p
    chave = t.lower().replace("pasta ", "").strip()
    if chave in PASTAS:
        return pasta_usuario(PASTAS[chave])                    # respeita a pasta real (OneDrive etc.)
    return Path.home() / t


def _abrir_painel() -> bool:
    try:
        from plugins import _arcade
        return _arcade.abrir_pagina("/missoes", 900, 760)
    except Exception:
        return False


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "criar":
            tipo = str(p.get("tipo") or "").lower()
            if tipo == "monitorar_preco":
                produto, url = str(p.get("produto") or "").strip(), str(p.get("url") or "").strip()
                if not (produto or url):
                    return "Qual produto (ou link) eu monitoro?"
                params = {"produto": produto, "url": url, "dias": float(p.get("dias") or 7),
                          "alvo": float(p.get("alvo") or 0), "intervalo_h": float(p.get("intervalo_h") or 3)}
                m = M.criar(tipo, params, f"Preço: {produto or url[:40]} ({params['dias']:g} dias)")
                _abrir_painel()
                return (f"Missão {m['id']} começou: consulto o preço a cada {params['intervalo_h']:g} h por "
                        f"{params['dias']:g} dias" + (f" e aviso se chegar a R$ {params['alvo']:.2f}" if params["alvo"]
                                                      else " e aviso quando cair") + ".")
            if tipo in ("organizar_fotos", "converter_videos"):
                pasta = resolver_pasta(p.get("pasta"))
                if pasta is None:
                    return "De qual pasta?"
                if not pasta.is_dir():
                    return f"Não achei a pasta {pasta}."
                if tipo == "converter_videos":
                    m = M.criar(tipo, {"pasta": str(pasta)}, f"Converter vídeos de {pasta.name}")
                    _abrir_painel()
                    return f"Missão {m['id']} começou: converto os vídeos de {pasta.name} para MP4 em {pasta.name}\\convertidos."
                mover = str(p.get("modo") or "").lower().startswith("mov")
                params = {"pasta": str(pasta), "modo": "mover" if mover else "copiar"}
                if mover:
                    def criar_movendo() -> str:
                        m = M.criar(tipo, params, f"Organizar (mover) fotos de {pasta.name}")
                        _abrir_painel()
                        return f"Missão {m['id']} começou: movendo as fotos para {pasta.name}\\Organizadas\\Ano\\Mês."
                    return confirmar(f"missao_mover_{pasta}", "Mover fotos", f"Mover as fotos de {pasta} para "
                                     "Organizadas\\Ano\\Mês? (dá para desfazer)", criar_movendo)
                m = M.criar(tipo, params, f"Organizar fotos de {pasta.name}")
                _abrir_painel()
                return (f"Missão {m['id']} começou: copio as fotos de {pasta.name} para {pasta.name}\\Organizadas, "
                        "separadas por ano e mês. Os originais ficam onde estão.")
            return "Que tipo de missão? Organizar fotos, monitorar preço ou converter vídeos."
        if acao == "painel":
            return "Abri o painel de missões." if _abrir_painel() else "Não consegui abrir o painel (precisa do Edge ou Chrome)."
        if acao in ("pausar", "continuar", "cancelar"):
            mid = int(p.get("id") or 0)
            if not mid:
                ativas = [m for m in M.listar() if m["estado"] in ("rodando", "pausada", "fila")]
                if len(ativas) != 1:
                    return "Qual missão? Diga o número."
                mid = ativas[0]["id"]
            r = M.comando(acao, mid)
            if not r["ok"]:
                return r["erro"]
            return {"pausar": f"Missão {mid} pausada.", "continuar": f"Missão {mid} continuando de onde parou.",
                    "cancelar": f"Missão {mid} cancelada."}[acao]
        if acao == "desfazer":
            mid = int(p.get("id") or 0)
            return confirmar(f"missao_desfazer_{mid}", "Desfazer missão", f"Voltar as fotos da missão {mid} para onde "
                             "estavam?", lambda: M.desfazer_fotos(mid))
        ms = M.listar()
        if not ms:
            return "Nenhuma missão. Posso organizar fotos, monitorar um preço ou converter vídeos."
        texto = "\n".join(M.descrever(m) for m in ms[-10:])
        mostrar(player, "MISSÕES", texto)
        return texto
    except Exception as e:
        return f"As missões falharam: {e}"


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    try:
        n = M.retomar()
        if n:
            print(f"[Missões] {n} missão(ões) retomada(s) de onde pararam")
    except Exception as e:
        print(f"[Missões] {e}")
