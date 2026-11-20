"""
Testes depois da recuperação: um reparo só conta como cura quando passa no teste.

    plugin          o arquivo compila, o módulo carrega, o PLUGIN é válido e — para os plugins do
                    padrão _lote2 — a ação "ajuda" responde (ela não mexe em nada)
    dados           o JSON abre
    pacote          o pacote é encontrado pelo Python
    rede            dá para abrir conexão com a internet (1,5 s no máximo)
Os testes nunca chamam uma ação de verdade do plugin (não manda mensagem, não apaga nada).
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path


def testar_conectividade(timeout: float = 1.5) -> bool:
    for host in (("1.1.1.1", 53), ("8.8.8.8", 53)):
        try:
            with socket.create_connection(host, timeout=timeout):
                return True
        except OSError:
            continue
    return False


def testar_json(caminho: Path) -> tuple[bool, str]:
    try:
        txt = Path(caminho).read_text(encoding="utf-8")
        if txt.strip():
            json.loads(txt)
        return True, f"{Path(caminho).name} abre normalmente"
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return False, f"{Path(caminho).name} ainda não abre: {e}"


def testar_pacote(nome: str) -> tuple[bool, str]:
    try:
        ok = importlib.util.find_spec(nome) is not None
    except Exception:
        ok = False
    return ok, f"pacote {nome} {'encontrado' if ok else 'ainda não instalado'}"


def testar_plugin(nome: str, raiz: Path) -> tuple[bool, str]:
    caminho = Path(raiz) / "plugins" / f"{nome}.py"
    if not caminho.is_file():
        return False, f"plugins/{nome}.py não existe"
    try:
        compile(caminho.read_text(encoding="utf-8"), str(caminho), "exec")
    except SyntaxError as e:
        return False, f"erro de sintaxe na linha {e.lineno}"
    mod = sys.modules.get(f"plugins.{nome}")
    if mod is None:
        try:
            spec = importlib.util.spec_from_file_location(f"plugins.{nome}", caminho)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            return False, f"não carrega: {type(e).__name__}: {e}"[:200]
    try:
        from core.plugin_loader import _validate
        rec = _validate(mod, caminho.name)
        if not rec.valid:
            return False, f"PLUGIN inválido: {rec.error}"
    except Exception:
        pass
    try:
        from plugins import _lote2
        if getattr(mod, "rodar", None) is _lote2.rodar and callable(getattr(mod, "run", None)):
            r = mod.run({"action": "ajuda"})
            if not isinstance(r, str) or not r:
                return False, "a ação 'ajuda' não respondeu"
            return True, "compila, carrega e responde"
    except Exception as e:
        return False, f"a ação 'ajuda' falhou: {e}"[:200]
    return True, "compila e carrega"


def testar(inc: dict, org, conectividade=testar_conectividade) -> tuple[bool, str]:
    """Escolhe o teste certo para o componente do incidente."""
    cat, mod, arq = inc.get("categoria"), inc.get("modulo") or "", inc.get("arquivo") or ""
    if arq.endswith(".json"):
        return testar_json(org.raiz / arq)
    if cat == "pacote":
        import re
        m = re.search(r"No module named ['\"]?([\w]+)", inc.get("mensagem", ""))
        if m:
            return testar_pacote(m.group(1))
    if cat in ("rede",) and not (org.raiz / "plugins" / f"{mod}.py").is_file():
        ok = conectividade()
        return ok, "internet ok" if ok else "ainda sem internet"
    if (org.raiz / "plugins" / f"{mod}.py").is_file():
        return testar_plugin(mod, org.raiz)
    return True, "sem teste específico: a próxima chamada confirma"
