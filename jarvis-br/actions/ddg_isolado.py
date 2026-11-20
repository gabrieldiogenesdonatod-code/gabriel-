"""
Busca no DuckDuckGo em um PROCESSO SEPARADO (fork PT-BR 2.8.2).

Por quê: o pacote `ddgs` usa por dentro o `primp`, uma biblioteca nativa (Rust).
Quando ela trava ou cai (no Python 3.14 isso acontece), ela derruba o Python
INTEIRO, sem mensagem nenhuma: o JARVIS voltava direto para o PowerShell logo
depois de "[WebSearch] DDG news exceeded 5s". Pior: a busca que passou do tempo
continuava rodando numa thread que ninguém podia parar.

Agora a busca roda num python.exe à parte. Se ele cair ou demorar, só ele
morre (é encerrado no tempo limite) e o JARVIS recebe "nenhum resultado".

    buscar("text", "clima goiânia", 6, region="br-pt", timelimit="w")
    python -m actions.ddg_isolado text "consulta" 6 '{"region": "br-pt"}'    (o processo filho)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def buscar(tipo: str, consulta: str, maximo: int = 8, timeout: float = 12.0, **extra) -> list[dict]:
    """tipo 'text' ou 'news'. Lista de resultados do DDGS (vazia se falhar, cair ou passar do tempo)."""
    cmd = [sys.executable, "-X", "utf8", "-m", "actions.ddg_isolado", tipo, consulta, str(int(maximo)),
           json.dumps(extra, ensure_ascii=False)]
    try:
        r = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        print(f"[WebSearch] DDG {tipo} passou de {timeout:.0f}s — busca encerrada (o JARVIS segue)")
        return []
    except Exception as e:
        print(f"[WebSearch] DDG {tipo} não rodou: {e}")
        return []
    if r.returncode != 0:
        erro = (r.stderr or "").strip().splitlines()[-1:] or [f"código {r.returncode}"]
        print(f"[WebSearch] DDG {tipo} falhou no processo separado ({erro[0][:160]}) — o JARVIS segue")
        return []
    try:
        dados = json.loads((r.stdout or "").strip().splitlines()[-1])
        return dados if isinstance(dados, list) else []
    except Exception:
        return []


def _filho(tipo: str, consulta: str, maximo: int, extra: dict) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    with DDGS() as d:
        fn = d.news if tipo == "news" else d.text
        return [dict(x) for x in (fn(consulta, max_results=maximo, **extra) or [])]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    t, q, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    ex = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
    try:
        saida = _filho(t, q, n, ex)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        saida = []
    print(json.dumps(saida, ensure_ascii=False, default=str))
