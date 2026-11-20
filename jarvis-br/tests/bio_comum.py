"""Ajudantes dos testes do Biological Core (3.1): um projeto de mentira numa pasta temporária."""
import tempfile
import time
from pathlib import Path

import tests  # noqa: F401

PLUGIN_TESTE = '''from plugins._lote2 import P, rodar
PLUGIN = P("{nome}", "Plugin de teste do organismo.", "agora | semana", "Plugin de teste do organismo.", "")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {{"agora": lambda p, pl: "ok agora", "semana": lambda p, pl: "ok semana"}}, player)
'''

ERRO_REDE = "HTTPSConnectionPool(host='api.clima.com', port=443): Max retries exceeded (getaddrinfo failed)"


def projeto(base: Path | None = None, plugin: str = "bioteste_clima") -> Path:
    base = Path(base or tempfile.mkdtemp(prefix="jarvis_bio_"))
    raiz = base / "proj"
    for pasta in ("plugins", "memory", "config", "core", "biological_core"):
        (raiz / pasta).mkdir(parents=True, exist_ok=True)
    (raiz / "plugins" / f"{plugin}.py").write_text(PLUGIN_TESTE.format(nome=plugin), encoding="utf-8")
    (raiz / "core" / "vigia.py").write_text("LIMITE = 30\n", encoding="utf-8")
    (raiz / "biological_core" / "config.py").write_text("X = 1\n", encoding="utf-8")
    (raiz / "ui.py").write_text('APP_VERSION  = "J.A.R.V.I.S BR 3.1"\n', encoding="utf-8")
    (raiz / "requirements.txt").write_text("sqlite3\n", encoding="utf-8")       # sempre instalado: o teste não depende do PC
    (raiz / "memory" / "lista.json").write_text('{"itens": [1, 2, 3]}', encoding="utf-8")
    (raiz / "config" / "app.json").write_text('{"tema": "escuro"}', encoding="utf-8")
    (raiz / "config" / "api_keys.json").write_text('{"gemini": "segredo"}', encoding="utf-8")
    return raiz


class RegistroVazio:
    """Registro de plugins de mentira: a ronda inicial não olha os plugins de verdade do PC dos testes."""
    def list_for_ui(self):
        return []


def vitais(**extra):
    base = {"ram_pc": 40.0, "ram_jarvis_mb": 200.0, "disco_livre_pct": 50.0, "threads": 12, "cpu_jarvis": 3.0}
    base.update(extra)
    return lambda: dict(base, ts=time.time())


def organismo(raiz: Path, rede=None, **kw):
    from biological_core.organismo import Organismo
    rede = rede if rede is not None else {"ok": False}
    kw.setdefault("fonte_vitais", vitais())
    org = Organismo(raiz, raiz.parent / "bio", sincrono=True, automatico=False, semente=1,
                    conectividade=lambda: rede["ok"], **kw)
    org.iniciar(RegistroVazio())
    return org
