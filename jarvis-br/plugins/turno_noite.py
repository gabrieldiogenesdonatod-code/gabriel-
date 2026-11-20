"""
Turno da noite (fork PT-BR 1.6).

Enquanto você dorme (PC ligado e parado), o JARVIS:
    • roda os testes dos seus projetos (o próprio JARVIS e os que você cadastrar);
    • confere se algum pacote Python instalado ou fixado no requirements.txt
      tem vulnerabilidade conhecida (base pública OSV, sem chave);
    • lista o que tem atualização (pip);
e de manhã, na primeira vez que você mexer no PC, entrega o relatório.

    "Jarvis, roda o turno da noite agora"     "Jarvis, como foi a noite?"
    "Jarvis, inclui a pasta C:\\projetos\\loja no turno da noite"
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from plugins._comum import CNW, CONFIG, MEMORIA, cfg, falar, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "turno_noite",
    "brief": "Night shift: runs project tests, checks vulnerable/outdated Python packages, morning report.",
    "description": (
        "Night shift: while the user sleeps it runs the tests of their projects, checks vulnerable Python packages "
        "(OSV database) and outdated ones, and gives a report in the morning. action='agora' (run now), 'relatorio' "
        "(last report), 'adicionar' with pasta (project folder), 'remover' with pasta, 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "agora | relatorio | adicionar | remover | status"},
                       "pasta": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "turno_noite",
    "title": "Turno da noite",
    "fields": [
        {"key": "ligado", "label": "Rodar de madrugada", "type": "toggle", "default": True},
        {"key": "hora", "label": "Hora de começar (0–23)", "type": "text", "default": "3"},
    ],
}

_ARQ = MEMORIA / "turno_noite.json"
_iniciado = threading.Event()


def _testar(pasta: Path) -> dict:
    """Roda unittest (ou pytest, se o projeto usa) na pasta do projeto."""
    usa_pytest = (pasta / "pytest.ini").exists() or (pasta / "conftest.py").exists() or \
        "pytest" in ((pasta / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
                     if (pasta / "pyproject.toml").exists() else "")
    if not any(pasta.glob("test*")) and not any(pasta.glob("tests/test*.py")) and not usa_pytest:
        return {"pasta": str(pasta), "rodou": False, "resumo": "sem testes"}
    py = next((str(x) for x in (pasta / ".venv" / "Scripts" / "python.exe", pasta / "venv" / "Scripts" / "python.exe",
                                pasta / ".venv" / "bin" / "python", pasta / "venv" / "bin" / "python") if x.exists()),
              sys.executable)                                   # o ambiente do próprio projeto, se tiver
    cmd = [py, "-m", "pytest", "-q"] if usa_pytest else \
        [py, "-m", "unittest", "discover", "-s", "tests" if (pasta / "tests").is_dir() else "."]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=str(pasta), capture_output=True, timeout=1800, **CNW)
        saida = ((r.stdout or b"") + b"\n" + (r.stderr or b"")).decode("utf-8", "replace")
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        saida, ok = "passou de 30 minutos", False
    from plugins.laboratorio import _contar_testes
    t = _contar_testes(saida)
    resumo = (f"{t.get('rodados', t.get('passaram', '?'))} testes, {t.get('falhas', 0)} falha(s)" if t else
              ("ok" if ok else "falhou"))
    return {"pasta": str(pasta), "rodou": True, "ok": ok, "resumo": resumo, "segundos": round(time.time() - t0),
            "fim": saida.strip()[-1500:] if not ok else ""}


def _desatualizados() -> list[str]:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "list", "--outdated", "--format=json"], capture_output=True,
                           timeout=180, **CNW)
        return [f"{p['name']} {p['version']} → {p['latest_version']}" for p in json.loads(r.stdout or b"[]")]
    except Exception:
        return []


def rodar_turno() -> dict:
    from plugins import _projetos
    pastas = [Path(p) for p in [str(_projetos.BASE)] + _projetos.cadastrados()]
    rel = {"quando": time.time(), "testes": [], "vulneraveis": {}, "desatualizados": [], "erros": [], "entregue": False}
    for p in pastas:
        if p.is_dir():
            try:
                rel["testes"].append(_testar(p))
            except Exception as e:
                rel["erros"].append(f"testes em {p}: {e}")
    try:
        pacotes = _projetos.pacotes_instalados()
        for p in pastas:
            pacotes += _projetos.requisitos(p)
        rel["vulneraveis"] = _projetos.vulnerabilidades(sorted(set(pacotes)))
    except Exception as e:
        rel["erros"].append(f"vulnerabilidades: {e}")
    rel["desatualizados"] = _desatualizados()
    gravar_json(_ARQ, rel)
    return rel


def texto(rel: dict) -> tuple[str, str]:
    """(resumo falado, painel) — pura."""
    falhas = [t for t in rel.get("testes", []) if t.get("rodou") and not t.get("ok")]
    rodados = [t for t in rel.get("testes", []) if t.get("rodou")]
    vul = rel.get("vulneraveis") or {}
    fala = (f"{len(rodados)} projeto(s) testado(s), " + (f"{len(falhas)} com falha" if falhas else "todos passando")
            + f"; {len(vul)} pacote(s) com vulnerabilidade conhecida" + f" e {len(rel.get('desatualizados') or [])} "
            "com atualização.")
    linhas = [f"TURNO DA NOITE — {datetime.fromtimestamp(rel.get('quando', 0)):%d/%m %H:%M}", "", "TESTES"]
    linhas += [f"  {'OK ' if t.get('ok') else 'FALHOU' if t.get('rodou') else '—  '}  {Path(t['pasta']).name}: "
               f"{t['resumo']}" for t in rel.get("testes", [])]
    for t in falhas:
        linhas += ["", f"  {Path(t['pasta']).name}:", *("    " + x for x in t.get("fim", "").splitlines()[-12:])]
    linhas += ["", "VULNERABILIDADES (osv.dev)"] + ([f"  {k}: {', '.join(v[:4])}" for k, v in vul.items()] or ["  nenhuma"])
    linhas += ["", "ATUALIZAÇÕES"] + ([f"  {x}" for x in (rel.get("desatualizados") or [])[:30]] or ["  tudo em dia"])
    if rel.get("erros"):
        linhas += ["", "NÃO DEU PARA CONFERIR"] + [f"  {e}" for e in rel["erros"]]
    return fala, "\n".join(linhas)


def _laco(player) -> None:
    from plugins.linha_do_tempo import ocioso_segundos
    while True:
        time.sleep(300)
        try:
            c = cfg("turno_noite", PLUGIN_SETTINGS)
            agora = datetime.now()
            rel = ler_json(_ARQ, {}) or {}
            feito_hoje = rel and datetime.fromtimestamp(rel.get("quando", 0)).date() == agora.date()
            if str(c.get("ligado", True)).lower() not in ("false", "0") and agora.hour == int(str(c.get("hora") or 3)) \
                    and not feito_hoje and ocioso_segundos() > 1200:
                rodar_turno()
                continue
            if rel and not rel.get("entregue") and 6 <= agora.hour < 13 and ocioso_segundos() < 60 \
                    and time.time() - rel.get("quando", 0) < 14 * 3600:
                rel["entregue"] = True
                gravar_json(_ARQ, rel)
                fala, painel = texto(rel)
                mostrar(player, "TURNO DA NOITE", painel)
                falar(player, f"[TURNO DA NOITE] Dê bom dia e conte em 2 frases o relatório da madrugada: {fala} "
                              "Diga que os detalhes estão no painel. Não chame nenhuma ferramenta.")
        except Exception as e:
            print(f"[TurnoNoite] {e}")


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="turno_noite").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "relatorio").lower()
    try:
        arq_proj = CONFIG / "projetos.json"
        d = ler_json(arq_proj, {}) or {}
        d.setdefault("pastas", [])
        if acao in ("adicionar", "remover"):
            pasta = str(Path(str(p.get("pasta") or "")).expanduser())
            if acao == "adicionar":
                if not Path(pasta).is_dir():
                    return f"Não achei a pasta {pasta}."
                if pasta not in d["pastas"]:
                    d["pastas"].append(pasta)
            else:
                d["pastas"] = [x for x in d["pastas"] if Path(x).name.lower() != Path(pasta).name.lower() and x != pasta]
            gravar_json(arq_proj, d)
            return f"Projetos no turno da noite: {', '.join(Path(x).name for x in d['pastas']) or 'só o JARVIS'}."
        if acao == "agora":
            rel = rodar_turno()
            rel["entregue"] = True
            gravar_json(_ARQ, rel)
            fala, painel = texto(rel)
            mostrar(player, "TURNO DA NOITE", painel)
            return fala
        rel = ler_json(_ARQ, {}) or {}
        if not rel:
            c = cfg("turno_noite", PLUGIN_SETTINGS)
            return f"Ainda não rodei nenhum turno. Rodo às {c.get('hora', 3)}h com o PC ligado, ou diga 'roda agora'."
        fala, painel = texto(rel)
        mostrar(player, "TURNO DA NOITE", painel)
        return fala
    except Exception as e:
        return f"O turno da noite falhou: {e}"
