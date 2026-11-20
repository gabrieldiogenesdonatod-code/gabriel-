"""
Um único jeito de AVISAR você (fork PT-BR 1.4) — por voz, no registro, no
painel do celular (se estiver aberto) e por notificação push no celular.

Começa com "_": não é ferramenta. Quem usa: vigia de preço, calendário da
loja, radar de anomalias, plugins criados pelo criador de ferramentas…

PUSH NO CELULAR (opcional, grátis, sem conta)
    Usa o ntfy (https://ntfy.sh): instale o app "ntfy" no celular, assine um
    tópico com um nome difícil de adivinhar (ex.: jarvis-cristal-8f3k2) e
    coloque o MESMO nome em ⚙ → PLUGINS → Notificações no celular. Pronto: os
    avisos chegam como notificação, mesmo com o painel fechado. Sem tópico,
    nada sai do PC.
"""

from __future__ import annotations

import threading
import time
import urllib.parse
import urllib.request

from plugins._comum import cfg, falar, registrar

NAMESPACE = "notificacoes"
_ultimos: dict[str, float] = {}
_lock = threading.Lock()
# Fork PT-BR 2.5: os últimos avisos (o painel de LED mostra; ninguém mais grava isto)
_recentes: list[tuple[float, str, str]] = []


def recentes(segundos: float = 600) -> list[tuple[float, str, str]]:
    """[(quando, título, texto)] dos avisos dos últimos `segundos`."""
    limite = time.time() - segundos
    with _lock:
        return [r for r in _recentes if r[0] >= limite]


# O plugin notificacoes.py publica estas configurações no painel ⚙.
PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "Notificações no celular",
    "fields": [
        {"key": "ntfy_topico", "label": "Tópico do ntfy (o mesmo assinado no app ntfy do celular)",
         "type": "text", "default": ""},
        {"key": "ntfy_servidor", "label": "Servidor do ntfy", "type": "text", "default": "https://ntfy.sh"},
        {"key": "celular", "label": "Mandar avisos para o celular", "type": "toggle", "default": True},
    ],
}


def _config() -> dict:
    return cfg(NAMESPACE, PLUGIN_SETTINGS)


def enviar_push(texto: str, titulo: str = "J.A.R.V.I.S", prioridade: str = "default",
                tags: str = "robot", esperar: bool = False) -> bool | None:
    """Manda para o ntfy se houver tópico. None = não configurado."""
    c = _config()
    topico = str(c.get("ntfy_topico") or "").strip().strip("/")
    if not topico:
        return None
    servidor = str(c.get("ntfy_servidor") or "https://ntfy.sh").rstrip("/")
    q = urllib.parse.urlencode({"title": titulo, "priority": prioridade, "tags": tags})
    url = f"{servidor}/{urllib.parse.quote(topico)}?{q}"
    resultado = {}

    def mandar():
        try:
            req = urllib.request.Request(url, data=texto.encode("utf-8"), method="POST",
                                         headers={"User-Agent": "JARVIS-BR/1.4"})
            with urllib.request.urlopen(req, timeout=8) as r:
                resultado["ok"] = 200 <= r.status < 300
        except Exception as e:
            print(f"[Notificar] push falhou: {e}")
            resultado["ok"] = False

    if esperar:
        mandar()
        return resultado.get("ok", False)
    threading.Thread(target=mandar, daemon=True).start()
    return True


def enviar_arquivo(caminho, texto: str, titulo: str = "J.A.R.V.I.S", prioridade: str = "high",
                   tags: str = "camera") -> bool | None:
    """Fork PT-BR 1.5: manda uma FOTO (ou arquivo) para o celular pelo ntfy."""
    from pathlib import Path
    c = _config()
    topico = str(c.get("ntfy_topico") or "").strip().strip("/")
    if not topico:
        return None
    arq = Path(caminho)
    servidor = str(c.get("ntfy_servidor") or "https://ntfy.sh").rstrip("/")
    q = urllib.parse.urlencode({"title": titulo, "message": texto, "filename": arq.name,
                                "priority": prioridade, "tags": tags})
    url = f"{servidor}/{urllib.parse.quote(topico)}?{q}"

    def mandar():
        try:
            req = urllib.request.Request(url, data=arq.read_bytes(), method="PUT",
                                         headers={"User-Agent": "JARVIS-BR/1.5"})
            with urllib.request.urlopen(req, timeout=30):
                pass
        except Exception as e:
            print(f"[Notificar] foto falhou: {e}")

    threading.Thread(target=mandar, daemon=True).start()
    return True


def notificar(player, texto: str, titulo: str = "J.A.R.V.I.S", falar_agora: bool = True,
              etiqueta: str = "AVISO", chave: str = "", intervalo_s: float = 0,
              prioridade: str = "default", foto=None) -> bool:
    """Avisa por todos os canais. Com `chave` + `intervalo_s`, não repete o
    mesmo aviso antes do intervalo. Devolve False se foi suprimido."""
    if chave and intervalo_s:
        with _lock:
            if time.time() - _ultimos.get(chave, 0) < intervalo_s:
                return False
            _ultimos[chave] = time.time()
    if player is None:
        try:
            from core import registro_ferramentas
            player = registro_ferramentas.player()
        except Exception:
            pass
    registrar(player, f"{titulo}: {texto}" if titulo != "J.A.R.V.I.S" else texto)
    with _lock:                                                # 2.5: para o painel de LED
        _recentes.append((time.time(), titulo, texto))
        del _recentes[:-20]
    if falar_agora:
        try:                                                   # 2.4: a fala passa pela central (urgente/normal/resumo)
            from core import central_avisos
            central_avisos.avisar(texto, central_avisos.prioridade_de(etiqueta, prioridade, texto), etiqueta, player)
        except Exception:
            falar(player, f"[{etiqueta}] Diga ao usuário, em UMA ou duas frases curtas e no idioma da "
                          f"conversa: {texto} Não chame nenhuma ferramenta.")
    try:
        from plugins import _monitor_db
        _monitor_db.gravar_evento("aviso", f"{titulo}: {texto}"[:300])
    except Exception:
        pass
    c = _config()
    if str(c.get("celular", True)).lower() not in ("false", "0", "nao", "não"):
        try:
            from core import registro_ferramentas
            registro_ferramentas.enviar_ao_painel(f"🔔 {titulo}: {texto}")
        except Exception:
            pass
        if foto:
            enviar_arquivo(foto, texto, titulo, prioridade)
        else:
            enviar_push(texto, titulo, prioridade)
        # Fork PT-BR 1.8: também no WhatsApp do dono, se a ponte estiver conectada.
        try:
            from plugins import _whatsapp
            if _whatsapp.config().get("avisos", True) and _whatsapp.rodando():
                threading.Thread(target=_whatsapp.para_donos, args=(f"🔔 {titulo}: {texto}", foto),
                                 daemon=True).start()
        except Exception:
            pass
    # Fork PT-BR 1.5: alerta crítico também pode virar LIGAÇÃO (plugin ligacao).
    if prioridade in ("urgent", "max", "critica"):
        try:
            from plugins import ligacao
            ligacao.alerta_critico(f"{titulo}. {texto}")
        except Exception as e:
            print(f"[Notificar] ligação: {e}")
    return True
