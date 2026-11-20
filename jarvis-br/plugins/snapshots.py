"""
Backup e snapshot automático dos projetos (fork PT-BR 1.9).

A cada hora, nos projetos que mudaram:
  • com git: um commit "snapshot" numa referência separada (refs/jarvis/snapshots).
    Não mexe no seu branch, no seu stage nem no histórico normal; "git log" nem
    mostra. Respeita o .gitignore.
  • sem git: um .zip em Documentos\\JARVIS\\snapshots\\<projeto>.
  • e, se você escolher uma pasta de backup (pendrive, OneDrive, Google Drive
    para PC…), um .zip de cada projeto vai para lá também.

    "Jarvis, faz um snapshot agora"
    "Jarvis, volta o jarvis-br pra como estava às 15h"      (com confirmação; dá para desfazer)
    "Jarvis, lista os snapshots do jarvis-br"
    "Jarvis, adiciona a pasta C:\\projetos\\loja nos snapshots"
    "Jarvis, faz backup no pendrive E:"

Os projetos são os da memória por projeto (o que você abre no VS Code) e os
que você adicionar.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from plugins._comum import MEMORIA, cfg, confirmar, desfazer, gravar_json, ler_json, pasta_usuario, rodar, salvar_cfg

PLUGIN = {
    "name": "snapshots",
    "brief": "Hourly automatic snapshots/backups of the user's projects (hidden git ref or zip) and restore to a time.",
    "description": (
        "Project snapshots and backups. Every hour, projects that changed get a snapshot (git: hidden ref "
        "refs/jarvis/snapshots, never touching branches; no git: zip) and an optional zip copy to a backup folder "
        "(USB drive or cloud folder). action='agora' (snapshot now, optional projeto), 'listar' with projeto, 'voltar' "
        "with projeto + hora (e.g. '15h', 'ontem 18:30') restores with on-screen confirmation, 'adicionar'/'remover' "
        "with pasta, 'destino' with pasta (backup folder, '' to turn off), 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "agora | listar | voltar | adicionar | remover | "
                                                                    "destino | status"},
                       "projeto": {"type": "STRING"}, "hora": {"type": "STRING"}, "pasta": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "snapshots",
    "title": "Snapshots e backup",
    "fields": [
        {"key": "ligado", "label": "Snapshot automático a cada hora", "type": "toggle", "default": True},
        {"key": "destino", "label": "Pasta de backup (pendrive ou nuvem; vazio = só local)", "type": "text",
         "default": ""},
        {"key": "manter", "label": "Quantos .zip guardar por projeto", "type": "text", "default": "48"},
        {"key": "pastas", "label": "Pastas extras (separadas por ;)", "type": "text", "default": ""},
    ],
}

ARQ = MEMORIA / "snapshots.json"
REF = "refs/jarvis/snapshots"
PULAR = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build", ".next", "target",
         ".idea", ".mypy_cache", ".pytest_cache", ".gradle"}
MAX_ARQ = 50 * 1024 * 1024
_iniciou = threading.Event()
_lock = threading.Lock()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def config() -> dict:
    return cfg("snapshots", PLUGIN_SETTINGS)


# ── hora falada (pura) ─────────────────────────────────────────────────────
def alvo_hora(texto: str, agora: datetime | None = None) -> datetime | None:
    """'15h', '15:30', 'às 9', 'ontem 18h30', 'hoje de manhã' → datetime (pura)."""
    agora = agora or datetime.now()
    t = _dobrar(texto)
    dia = agora.date()
    if "anteontem" in t:
        dia -= timedelta(days=2)
    elif "ontem" in t:
        dia -= timedelta(days=1)
    m = re.search(r"ha\s+(\d+)\s*(hora|minuto)", t)
    if m:
        n = int(m.group(1))
        return agora - (timedelta(hours=n) if m.group(2) == "hora" else timedelta(minutes=n))
    m = re.search(r"(\d{1,2})\s*(?:h|:|horas?)\s*(\d{2})?", t) or re.search(r"\bas\s+(\d{1,2})()\b", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
    elif "manha" in t:
        h, mi = 9, 0
    elif "tarde" in t:
        h, mi = 15, 0
    elif "noite" in t:
        h, mi = 20, 0
    else:
        return None
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    alvo = datetime.combine(dia, datetime.min.time()).replace(hour=h, minute=mi)
    if alvo > agora and "ontem" not in t and "hoje" not in t:
        alvo -= timedelta(days=1)                              # "15h" às 10h = ontem às 15h
    return alvo


def escolher(snaps: list[tuple[int, str]], alvo_ts: float) -> tuple[int, str] | None:
    """O snapshot mais recente que não passa da hora pedida (pura)."""
    antes = [s for s in snaps if s[0] <= alvo_ts]
    return max(antes) if antes else None


# ── projetos ─────────────────────────────────────────────────────────────────
def projetos() -> dict[str, Path]:
    saida: dict[str, Path] = {}
    try:
        from plugins.memoria_projeto import dados as dm
        for nome, p in dm()["projetos"].items():
            if p.get("caminho") and Path(p["caminho"]).is_dir():
                saida[nome] = Path(p["caminho"])
    except Exception:
        pass
    for pasta in str(config().get("pastas") or "").split(";"):
        pasta = pasta.strip().strip('"')
        if pasta and Path(pasta).is_dir():
            saida[Path(pasta).name] = Path(pasta)
    return saida


def achar(texto: str) -> tuple[str, Path] | None:
    ps = projetos()
    t = _dobrar(texto)
    if not t:
        try:
            from plugins.memoria_projeto import dados as dm
            atual = dm().get("atual") or dm().get("ultimo")
            if atual in ps:
                return atual, ps[atual]
        except Exception:
            pass
        return None
    for n, p in ps.items():
        if _dobrar(n) == t or t in _dobrar(n):
            return n, p
    return None


def _git(pasta: Path, *args, env: dict | None = None, timeout: float = 120) -> tuple[int, str]:
    if env is None:
        return rodar(["git", "-C", str(pasta), *args], timeout=timeout, encoding="utf-8")
    import subprocess

    from plugins._comum import CNW
    try:
        r = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, timeout=timeout,
                           env={**os.environ, **env}, **CNW)
        return r.returncode, ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace").strip()
    except Exception as e:
        return -1, str(e)


def eh_git(pasta: Path) -> bool:
    return (pasta / ".git").exists()


_ID = {"GIT_AUTHOR_NAME": "JARVIS", "GIT_AUTHOR_EMAIL": "jarvis@localhost",
       "GIT_COMMITTER_NAME": "JARVIS", "GIT_COMMITTER_EMAIL": "jarvis@localhost"}


def snapshot_git(pasta: Path, rotulo: str = "") -> str:
    """Commit do estado atual (inclusive o que não foi commitado) na ref escondida. '' = nada mudou."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**_ID, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        tem_head = _git(pasta, "rev-parse", "--verify", "HEAD")[0] == 0
        if tem_head:
            _git(pasta, "read-tree", "HEAD", env=env)
        c, out = _git(pasta, "add", "-A", ".", env=env, timeout=300)
        if c != 0:
            raise RuntimeError(out[-300:])
        c, arvore = _git(pasta, "write-tree", env=env)
        if c != 0:
            raise RuntimeError(arvore[-300:])
        arvore = arvore.strip().splitlines()[-1]
    c, pai = _git(pasta, "rev-parse", "--verify", REF)
    pai = pai.strip() if c == 0 else ""
    if pai and _git(pasta, "rev-parse", f"{pai}^{{tree}}")[1].strip() == arvore:
        return ""
    msg = f"snapshot JARVIS {datetime.now():%Y-%m-%d %H:%M}" + (f" — {rotulo}" if rotulo else "")
    c, commit = _git(pasta, "commit-tree", arvore, *(["-p", pai] if pai else []), "-m", msg, env=_ID)
    if c != 0:
        raise RuntimeError(commit[-300:])
    commit = commit.strip().splitlines()[-1]
    _git(pasta, "update-ref", REF, commit)
    return commit


def snaps_git(pasta: Path) -> list[tuple[int, str]]:
    c, out = _git(pasta, "log", REF, "--format=%ct %H", "-n", "500")
    if c != 0:
        return []
    saida = []
    for linha in out.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[0].isdigit():
            saida.append((int(partes[0]), partes[1]))
    return saida


def pasta_local(nome: str) -> Path:
    return pasta_usuario("Documents") / "JARVIS" / "snapshots" / nome


def zipar(pasta: Path, destino_dir: Path, nome: str) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    arq = destino_dir / f"{nome}_{datetime.now():%Y%m%d_%H%M}.zip"
    tmp = arq.with_suffix(".parcial")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for raiz, dirs, arqs in os.walk(pasta):
            dirs[:] = [d for d in dirs if d not in PULAR]
            for a in arqs:
                p = Path(raiz) / a
                try:
                    if p.stat().st_size <= MAX_ARQ:
                        z.write(p, p.relative_to(pasta))
                except OSError:
                    pass
    tmp.replace(arq)
    try:
        manter = max(3, int(str(config().get("manter") or 48)))
    except ValueError:
        manter = 48
    for velho in sorted(destino_dir.glob(f"{nome}_*.zip"))[:-manter]:
        velho.unlink(missing_ok=True)
    return arq


def snaps_zip(nome: str) -> list[tuple[int, str]]:
    saida = []
    for z in pasta_local(nome).glob(f"{nome}_*.zip"):
        m = re.search(r"_(\d{8}_\d{4})\.zip$", z.name)
        if m:
            saida.append((int(datetime.strptime(m.group(1), "%Y%m%d_%H%M").timestamp()), str(z)))
    return saida


def ultima_mudanca(pasta: Path) -> float:
    mais = 0.0
    for raiz, dirs, arqs in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in PULAR]
        for a in arqs:
            try:
                mais = max(mais, (Path(raiz) / a).stat().st_mtime)
            except OSError:
                pass
    return mais


def fazer(nome: str, pasta: Path, forcar: bool = False) -> str:
    estado = ler_json(ARQ, {}) or {}
    info = estado.setdefault(nome, {})
    mudou = ultima_mudanca(pasta)
    if not forcar and mudou <= info.get("mudanca", 0):
        return ""
    feito = []
    if eh_git(pasta):
        if shutil.which("git"):
            if snapshot_git(pasta):
                feito.append("snapshot git")
    else:
        zipar(pasta, pasta_local(nome), nome)
        feito.append("zip local")
    destino = str(config().get("destino") or "").strip().strip('"')
    if destino:
        if Path(Path(destino).anchor or destino).exists():
            zipar(pasta, Path(destino) / "JARVIS-backup" / nome, nome)
            feito.append("backup")
        else:
            feito.append("backup NÃO feito (pasta de backup não encontrada: pendrive tirado?)")
    info.update(mudanca=mudou, quando=time.time())
    gravar_json(ARQ, estado)
    return f"{nome}: " + ", ".join(feito) if feito else ""


def todos(forcar: bool = False) -> list[str]:
    feitos = []
    with _lock:
        for nome, pasta in projetos().items():
            try:
                r = fazer(nome, pasta, forcar)
                if r:
                    feitos.append(r)
            except Exception as e:
                feitos.append(f"{nome}: falhou ({e})")
    return feitos


def voltar(nome: str, pasta: Path, alvo: datetime) -> str:
    ts = alvo.timestamp()
    if eh_git(pasta):
        s = escolher(snaps_git(pasta), ts)
        if not s:
            return f"Não tenho snapshot do {nome} de antes de {alvo:%d/%m %H:%M}."

        def restaurar():
            seguranca = snapshot_git(pasta, "antes de voltar") or _git(pasta, "rev-parse", REF)[1].strip()
            c, out = _git(pasta, "restore", f"--source={s[1]}", "--worktree", "--", ".")
            if c != 0:
                c, out = _git(pasta, "checkout", s[1], "--", ".")
            if c != 0:
                return f"O git recusou: {out[-200:]}"
            desfazer(f"voltar {nome} para {datetime.fromtimestamp(s[0]):%H:%M}",
                     lambda: (_git(pasta, "restore", f"--source={seguranca}", "--worktree", "--", "."),
                              f"{nome} voltou para como estava antes.")[1])
            return f"{nome} voltou para {datetime.fromtimestamp(s[0]):%d/%m %H:%M}. Arquivos novos depois disso continuam lá."
    else:
        s = escolher(snaps_zip(nome), ts)
        if not s:
            return f"Não tenho snapshot do {nome} de antes de {alvo:%d/%m %H:%M}."

        def restaurar():
            seguranca = zipar(pasta, pasta_local(nome), nome)
            with zipfile.ZipFile(s[1]) as z:
                for membro in z.namelist():
                    destino = (pasta / membro).resolve()
                    if not str(destino).startswith(str(pasta.resolve())):
                        continue                                  # nada fora da pasta do projeto
                    z.extract(membro, pasta)
            desfazer(f"voltar {nome}", lambda: (zipfile.ZipFile(seguranca).extractall(pasta),
                                                f"{nome} voltou para como estava antes.")[1])
            return f"{nome} voltou para {datetime.fromtimestamp(s[0]):%d/%m %H:%M}."
    return confirmar(f"snapshots:voltar:{nome}", f"Voltar {nome} para {datetime.fromtimestamp(s[0]):%d/%m %H:%M}?",
                     "Antes eu salvo o estado atual, então dá para desfazer.", restaurar)


def _laco() -> None:
    time.sleep(300)
    while True:
        try:
            if config().get("ligado", True):
                for r in todos():
                    print(f"[Snapshots] {r}")
        except Exception as e:
            print(f"[Snapshots] {e}")
        time.sleep(3600)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="snapshots").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao in ("adicionar", "remover"):
            pasta = str(p.get("pasta") or "").strip().strip('"')
            atuais = [x.strip() for x in str(config().get("pastas") or "").split(";") if x.strip()]
            if acao == "adicionar":
                if not Path(pasta).is_dir():
                    return f"Não achei a pasta {pasta}."
                atuais = list(dict.fromkeys(atuais + [pasta]))
            else:
                atuais = [x for x in atuais if _dobrar(Path(x).name) != _dobrar(Path(pasta).name) and x != pasta]
            salvar_cfg("snapshots", {"pastas": ";".join(atuais)})
            return "Pronto." if acao == "remover" else f"{Path(pasta).name} entra nos snapshots."
        if acao == "destino":
            pasta = str(p.get("pasta") or "").strip().strip('"')
            if re.fullmatch(r"[A-Za-z]:?", pasta):
                pasta = pasta[0].upper() + ":\\"
            salvar_cfg("snapshots", {"destino": pasta})
            return f"Backup vai para {pasta}." if pasta else "Backup externo desligado (só snapshots locais)."
        if acao == "agora":
            if p.get("projeto"):
                a = achar(str(p["projeto"]))
                if not a:
                    return "Não achei esse projeto. Diga 'adiciona a pasta … nos snapshots'."
                with _lock:
                    r = fazer(a[0], a[1], forcar=True)
                return r or f"{a[0]}: nada mudou desde o último snapshot."
            r = todos(forcar=True)
            return ("Snapshots: " + "; ".join(r) + ".") if r else "Nenhum projeto para salvar ainda."
        if acao in ("listar", "voltar"):
            a = achar(str(p.get("projeto") or ""))
            if not a:
                return "De qual projeto? " + (", ".join(projetos()) or "nenhum projeto ainda") + "."
            nome, pasta = a
            snaps = snaps_git(pasta) if eh_git(pasta) else snaps_zip(nome)
            if acao == "listar":
                if not snaps:
                    return f"Nenhum snapshot do {nome} ainda."
                linhas = [datetime.fromtimestamp(t).strftime("%d/%m %H:%M") for t, _x in sorted(snaps, reverse=True)[:30]]
                from plugins._comum import mostrar
                mostrar(player, f"SNAPSHOTS — {nome}", "\n".join(linhas))
                return f"{len(snaps)} snapshots do {nome}; o mais recente é de {linhas[0]}."
            alvo = alvo_hora(str(p.get("hora") or ""))
            if alvo is None:
                return "Para qual hora? Diga, por exemplo, '15h' ou 'ontem às 18h'."
            return voltar(nome, pasta, alvo)
        ps = projetos()
        destino = config().get("destino") or "nenhum"
        return (f"Snapshots {'ligados' if config().get('ligado', True) else 'desligados'}, a cada hora. Projetos: "
                f"{', '.join(ps) or 'nenhum ainda'}. Backup externo: {destino}.")
    except Exception as e:
        return f"Os snapshots falharam: {e}"
