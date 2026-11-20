"""
core/registro_ferramentas.py — acesso central a TODAS as ferramentas (fork PT-BR 1.4).

O main.py registra aqui, ao iniciar, os dois catálogos que já existiam: as
ações de actions/ e os plugins de plugins/. Assim um plugin consegue usar
outro ("habilidades combináveis", conselho de agentes, criador de ferramentas)
pelo nome, do mesmo jeito que o modelo usaria, passando pelo mesmo caminho e
pelo mesmo registro de uso.

Sem o main.py (nos testes, por exemplo), `disponiveis()` cai para os plugins
descobertos na hora.
"""

from __future__ import annotations

from pathlib import Path

_acoes = None
_plugins = None
_player = None
_app = None


def definir(acoes, plugins, player=None, app=None) -> None:
    global _acoes, _plugins, _player, _app
    _acoes, _plugins, _player, _app = acoes, plugins, player, app


def app():
    """O JarvisLive do main.py (ou None nos testes)."""
    return _app


def player():
    return _player


def _plugins_reg():
    global _plugins
    if _plugins is None:
        from core.plugin_loader import discover_plugins
        _plugins = discover_plugins(Path(__file__).resolve().parent.parent / "plugins", set(),
                                    logger=lambda _m: None)
    return _plugins


def declaracoes() -> list[dict]:
    """name, description, parameters de cada ferramenta disponível."""
    saida = []
    try:
        if _acoes is not None:
            saida += [d for d in _acoes.get_tool_declarations()]
    except Exception:
        pass
    try:
        saida += _plugins_reg().get_tool_declarations()
    except Exception:
        pass
    return saida


def disponiveis() -> set[str]:
    return {d["name"] for d in declaracoes()}


def executar(nome: str, params: dict | None = None, player=None) -> str:
    params = dict(params or {})
    player = player if player is not None else _player
    if _acoes is not None and nome in _acoes.names():
        return _acoes.run(nome, params, {"player": player})
    reg = _plugins_reg()
    if reg.has(nome):
        return reg.run(nome, params, player=player)
    return f"A ferramenta '{nome}' não existe."


# ── plugins criados com o app aberto (criador de ferramentas) ─────────────────
def nomes_core() -> set[str]:
    try:
        return set(_acoes.names()) if _acoes is not None else set()
    except Exception:
        return set()


def carregar_plugin(caminho: Path) -> tuple[bool, str]:
    """Carrega (ou recarrega) UM plugin no registro vivo, sem reiniciar o app."""
    from core.plugin_loader import carregar_um
    return carregar_um(Path(caminho), nomes_core(), _plugins_reg())


def descarregar_plugin(nome: str) -> bool:
    reg = _plugins_reg()
    try:
        rec = reg._plugins.pop(nome, None)
        if rec is not None:
            reg._all_records = [r for r in reg._all_records if r.name != nome]
        return rec is not None
    except Exception:
        return False


def reconectar(motivo: str = "ferramentas novas", manter_conversa: bool = True) -> bool:
    """Pede ao main.py para refazer a sessão com o modelo (as declarações de
    ferramentas só são lidas na conexão). Se o servidor não aceitar retomar a
    conversa, o próprio main.py recomeça limpo."""
    a = _app
    if a is None or not hasattr(a, "request_reconnect"):
        return False
    try:
        a.request_reconnect(keep_context=manter_conversa, reason=motivo)
        return True
    except Exception as e:
        print(f"[Registro] reconectar: {e}")
        return False


def enviar_ao_painel(texto: str) -> bool:
    """Mostra uma linha no painel do celular, se ele estiver aberto."""
    a = _app
    dash = getattr(a, "_dashboard", None) if a is not None else None
    loop = getattr(a, "_loop", None) if a is not None else None
    if dash is None or loop is None:
        return False
    try:
        import asyncio
        from datetime import datetime
        asyncio.run_coroutine_threadsafe(dash.broadcast(
            {"type": "log", "speaker": "jarvis", "text": texto, "ts": datetime.now().isoformat()}), loop)
        return True
    except Exception:
        return False
