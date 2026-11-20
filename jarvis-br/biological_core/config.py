"""
Configuração e utilidades compartilhadas do Biological Core (fork PT-BR 3.1).

Opções em config/api_keys.json (todas opcionais):
    "bio_desligado": true            desliga o organismo (ele avisa no início que está desligado)
    "bio_autonomia": "normal"        "normal": faz sozinho só o que é seguro e PEDE o resto;
                                     "observar": só detecta, isola o que trava e avisa
    "bio_pre_autorizados": [...]     reparos que você já autorizou de antemão (ex.: ["restaurar_json"])
    "bio_batimento_s": 10            intervalo do coração
    "bio_rajada_por_min": 30         chamadas seguidas da mesma ferramenta antes da pausa anti-loop
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PADRAO = RAIZ / "memory" / "biological"

AUTONOMIAS = ("observar", "normal")

# Nunca entram em quarentena: sem eles o JARVIS não consegue nem pedir ajuda ou se consertar.
ESSENCIAIS = frozenset({"organismo", "catalogo", "outras_ferramentas", "modos", "autodiagnostico",
                        "auto_melhoria", "backup_dados"})

# Níveis de permissão de cada ação do organismo.
SEGURA = "segura"                # faz sozinho (não muda arquivo seu)
AUTORIZACAO = "autorizacao"      # só com o seu SIM na tela
PROIBIDA = "proibida"            # nunca (apagar arquivo, desligar antivírus/firewall, mudar o DNA sozinho)

GRAVIDADES = ("info", "baixa", "media", "alta", "critica")

_cache: dict = {"t": 0.0, "d": {}}
_lock = threading.Lock()


def cfg(chave: str, padrao=None):
    """Lê config/api_keys.json com cache de 30 s (o portão roda a cada ferramenta; não pode ler disco toda vez)."""
    with _lock:
        if time.monotonic() - _cache["t"] > 30:
            try:
                from memory.config_manager import load_api_keys
                _cache["d"] = load_api_keys() or {}
            except Exception:
                _cache["d"] = {}
            _cache["t"] = time.monotonic()
        return _cache["d"].get(chave, padrao)


def esquecer_cache() -> None:
    with _lock:
        _cache["t"] = 0.0


def autonomia() -> str:
    a = str(cfg("bio_autonomia", "normal") or "normal").lower()
    return a if a in AUTONOMIAS else "normal"


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def gravar_json(caminho: Path, dados) -> None:
    """Gravação atômica: escreve num .tmp e troca. Queda de energia não deixa JSON pela metade."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, caminho)


def agora_txt(ts: float | None = None) -> str:
    return time.strftime("%d/%m %H:%M", time.localtime(ts or time.time()))


def duracao(s: float) -> str:
    s = max(0, int(s))
    if s < 90:
        return f"{s} s"
    if s < 5400:
        return f"{round(s / 60)} min"
    if s < 172800:
        return f"{s / 3600:.1f} h".replace(".", ",")
    return f"{round(s / 86400)} dias"
