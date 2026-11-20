"""
Comemoração dos testes (fork PT-BR 1.9).

    "Jarvis, roda os testes"                      (no projeto aberto no VS Code)
    "Jarvis, roda os testes do jarvis-br"
    "Jarvis, fica de olho nos testes"             (roda de novo a cada vez que você salva um .py)
    "Jarvis, para de olhar os testes"

Passou tudo → som de vitória, o rosto flutuante comemora e ele dá os parabéns.
Falhou → ele lê qual teste quebrou e a linha do erro. Usa o unittest do
próprio Python (ou o pytest, se o projeto usar e ele estiver instalado).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from plugins._comum import CNW, BASE, falar, mostrar

PLUGIN = {
    "name": "testes_vivos",
    "brief": "Runs a project's tests: victory sound and face celebration when all pass, reads the failing test otherwise; "
             "can watch files and re-run on save.",
    "description": (
        "Project tests with celebration. action='rodar' (optional projeto: name or folder; default the project open in "
        "VS Code) runs unittest/pytest; all green = victory sound + celebration, failures = says which test failed and "
        "why. action='vigiar' re-runs whenever a .py file changes; 'parar' stops watching; 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "rodar | vigiar | parar | status"},
                       "projeto": {"type": "STRING"}},
        "required": [],
    },
}

_vigia = {"thread": None, "pasta": None, "ultimo": None}
_parar = threading.Event()


# ── leitura do resultado (pura) ────────────────────────────────────────────
def _arquivo_linha(onde: list[tuple[str, str]]) -> str:
    if not onde:
        return ""
    return re.split(r"[\\/]", onde[-1][0])[-1] + ":" + onde[-1][1]


def ler_resultado(saida: str) -> dict:
    """Saída do unittest ou do pytest → {ok, total, falhas: [{teste, erro}], ferramenta}."""
    s = saida or ""
    r = {"ok": False, "total": 0, "falhas": [], "ferramenta": "unittest"}
    m = re.search(r"Ran (\d+) tests? in", s)
    if m:
        r["total"] = int(m.group(1))
        r["ok"] = bool(re.search(r"^OK\b", s, re.M))
        for bloco in re.split(r"^={50,}\s*$", s, flags=re.M)[1:]:
            cab = re.search(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", bloco, re.M)
            if not cab:
                continue
            linhas = [l for l in bloco.strip().splitlines() if l.strip() and not l.startswith("-" * 10)]
            erro = next((l.strip() for l in reversed(linhas) if re.match(r"\s*\w*(Error|Exception|assert)", l)),
                        linhas[-1].strip() if linhas else "")
            onde = re.findall(r'File "([^"]+)", line (\d+)', bloco)
            partes = cab.group(3).split(".")                   # 3.11+: módulo.Classe.teste; antes: módulo.Classe
            classe = partes[-2] if partes[-1] == cab.group(2) and len(partes) > 1 else partes[-1]
            r["falhas"].append({"teste": f"{classe}.{cab.group(2)}", "tipo": cab.group(1),
                                "erro": erro[:200], "linha": _arquivo_linha(onde)})
        return r
    m = re.search(r"=+ (?:(\d+) failed)?[, ]*(?:(\d+) passed)?.*? in [\d.]+s", s)
    if m and (m.group(1) or m.group(2)):
        r["ferramenta"] = "pytest"
        falhou, passou = int(m.group(1) or 0), int(m.group(2) or 0)
        r["total"], r["ok"] = falhou + passou, falhou == 0
        for nome, erro in re.findall(r"^FAILED (\S+?)(?: - (.*))?$", s, re.M):
            r["falhas"].append({"teste": nome.split("::", 1)[-1], "tipo": "FAIL", "erro": (erro or "")[:200], "linha": ""})
    return r


def frase(r: dict, nome: str) -> str:
    if r["ok"]:
        return f"Todos os {r['total']} testes do {nome} passaram."
    if not r["total"] and not r["falhas"]:
        return f"Não encontrei testes no {nome} (ou eles nem rodaram)."
    f = r["falhas"]
    txt = f"{len(f)} de {r['total']} testes do {nome} falharam."
    if f:
        txt += f" O primeiro: {f[0]['teste']}" + (f", em {f[0]['linha']}" if f[0]["linha"] else "") + \
            (f": {f[0]['erro']}" if f[0]["erro"] else "") + "."
    return txt


# ── rodar ───────────────────────────────────────────────────────────────────
def achar_pasta(texto: str) -> Path | None:
    t = str(texto or "").strip().strip('"')
    if t and Path(t).is_dir():
        return Path(t)
    try:
        from plugins.memoria_projeto import achar_nome, dados
        d = dados()
        nome = achar_nome(d, t)
        caminho = d["projetos"].get(nome, {}).get("caminho") if nome else ""
        if caminho and Path(caminho).is_dir():
            return Path(caminho)
    except Exception:
        pass
    if not t or t.lower() in ("jarvis", "jarvis-br", "jarvis br"):
        return BASE
    return None


def comando(pasta: Path) -> list[str]:
    usa_pytest = (pasta / "pytest.ini").exists() or (pasta / "conftest.py").exists()
    if not usa_pytest and (pasta / "pyproject.toml").exists():
        usa_pytest = "[tool.pytest" in (pasta / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
    py = sys.executable or shutil.which("python") or "python"
    for venv in (".venv", "venv", "env"):
        cand = pasta / venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if cand.exists():
            py = str(cand)
    if usa_pytest:
        return [py, "-m", "pytest", "-q", "-rf", "--no-header"]
    return [py, "-m", "unittest", "discover", "-s", "tests" if (pasta / "tests").is_dir() else ".", "-t", "."]


def rodar(pasta: Path, timeout: float = 600) -> dict:
    try:
        r = subprocess.run(comando(pasta), cwd=str(pasta), capture_output=True, timeout=timeout, **CNW)
        saida = (r.stdout or b"").decode("utf-8", "replace") + "\n" + (r.stderr or b"").decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return {"ok": False, "total": 0, "falhas": [{"teste": "(tempo)", "tipo": "ERROR", "erro": "demorou mais de 10 min",
                                                      "linha": ""}], "ferramenta": "?", "saida": ""}
    res = ler_resultado(saida)
    res["saida"] = saida[-6000:]
    return res


def comemorar(player, r: dict, nome: str, em_voz: bool = True) -> None:
    txt = frase(r, nome)
    try:
        from plugins import _som
        if r["ok"]:
            threading.Thread(target=_som.tocar_uma, args=(_som.efeito("magia"),), daemon=True).start()
    except Exception:
        pass
    try:
        from plugins._rosto_ui import frase as balao
        balao(player, "JARVIS", ("🎉 " if r["ok"] else "❌ ") + txt, mostrar_rosto=r["ok"])
    except Exception:
        pass
    if not em_voz:
        return
    if r["ok"]:
        falar(player, f"[TESTES] Comemore em UMA frase animada (estilo Stark): {txt} Não chame nenhuma ferramenta.")
    else:
        falar(player, f"[TESTES] Diga ao usuário, em até duas frases, qual teste quebrou e o erro: {txt} "
                      "Não chame nenhuma ferramenta.")


def _assinatura(pasta: Path) -> float:
    mais = 0.0
    for raiz, dirs, arqs in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in {".git", "venv", ".venv", "node_modules", "__pycache__", "env"}]
        for a in arqs:
            if a.endswith(".py"):
                try:
                    mais = max(mais, (Path(raiz) / a).stat().st_mtime)
                except OSError:
                    pass
    return mais


def _vigiar(pasta: Path, player) -> None:
    ultima = _assinatura(pasta)
    while not _parar.is_set():
        time.sleep(3)
        agora = _assinatura(pasta)
        if agora > ultima:
            time.sleep(1.5)                                   # espera terminar de salvar
            ultima = _assinatura(pasta)
            r = rodar(pasta)
            antes = _vigia["ultimo"]
            _vigia["ultimo"] = r
            if r["ok"] != (antes or {}).get("ok") or not r["ok"]:
                comemorar(player, r, pasta.name)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "rodar").lower()
    try:
        if acao == "parar":
            _parar.set()
            return "Parei de olhar os testes."
        if acao == "status":
            t = _vigia["thread"]
            if t is not None and t.is_alive():
                return f"De olho nos testes do {_vigia['pasta'].name}." + \
                    (f" Último: {frase(_vigia['ultimo'], _vigia['pasta'].name)}" if _vigia["ultimo"] else "")
            return "Não estou olhando testes agora."
        pasta = achar_pasta(str(p.get("projeto") or ""))
        if pasta is None:
            return "De qual projeto? Diga o nome (como aparece no VS Code) ou a pasta."
        if acao == "vigiar":
            t = _vigia["thread"]
            if t is not None and t.is_alive():
                _parar.set()
                t.join(timeout=5)
            _parar.clear()
            _vigia.update(pasta=pasta, ultimo=None)
            _vigia["thread"] = threading.Thread(target=_vigiar, args=(pasta, player), daemon=True, name="testes_vivos")
            _vigia["thread"].start()
            return f"De olho no {pasta.name}: cada vez que você salvar um .py, eu rodo os testes."
        r = rodar(pasta)
        _vigia["ultimo"] = r
        if not r["ok"] and r["falhas"]:
            mostrar(player, f"TESTES — {pasta.name}", "\n".join(
                f"✗ {f['teste']}  {f['linha']}\n    {f['erro']}" for f in r["falhas"][:15]))
        comemorar(player, r, pasta.name, em_voz=False)            # a resposta da ferramenta já é falada
        return frase(r, pasta.name) + (" Comemore com o usuário em uma frase." if r["ok"] else "")
    except Exception as e:
        return f"Os testes falharam ao rodar: {e}"
