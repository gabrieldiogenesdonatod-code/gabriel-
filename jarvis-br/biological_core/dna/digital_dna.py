"""
DNA digital: a identidade do JARVIS.

O genoma (memory/biological/genoma.json) registra os módulos oficiais, a versão, as dependências
e a impressão digital SHA-256 de cada arquivo de código. Ele é ASSINADO (HMAC-SHA256 com uma chave
aleatória gerada no primeiro início), então uma edição escondida no próprio genoma é percebida.

Regras de identidade:
    • a gênese (primeiro genoma) acontece sozinha no primeiro início — ainda não existe identidade;
    • depois disso, o DNA só muda com uma ficha de autorização (o seu SIM na tela). Nem o próprio
      organismo consegue mudar a identidade ou desligar as proteções sem ela;
    • o que muda sozinho (dados em memory/, config/*.json) NÃO é DNA: isso é cuidado pela
      prevenção (pontos de restauração e checagem de JSON).

Limite honesto: a chave fica no seu PC. Ela pega mudança acidental e adulteração ingênua, não um
invasor que já tem controle total da máquina.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

from biological_core.config import gravar_json, ler_json

EXTENSOES = {".py", ".html", ".js", ".css", ".svg", ".bat", ".sh", ".ino", ".cpp", ".h", ".webmanifest", ".json"}
EXTRAS = {"requirements.txt"}
IGNORAR = {"__pycache__", ".git", ".pytest_cache", "node_modules", ".venv", "venv", "env", ".idea", ".vscode"}

VITAIS = ("biological_core/", "core/plugin_loader.py", "core/vigia.py", "core/confirm.py", "core/relogio.py",
          "core/verificacao.py", "core/registro_ferramentas.py", "main.py", "memory/config_manager.py")
ESSENCIAIS_PACOTES = ("PyQt6", "numpy", "google-genai", "sounddevice")


def classe_de(rel: str) -> str:
    """vital (protege o organismo) · nucleo · plugin · celular · teste · outro."""
    if any(rel == v or (v.endswith("/") and rel.startswith(v)) for v in VITAIS):
        return "vital"
    if rel.startswith("tests/"):
        return "teste"
    if rel.startswith("plugins/"):
        return "plugin"
    if rel.startswith("celular/"):
        return "celular"
    if rel.startswith(("core/", "actions/", "providers/", "memory/")) or rel in ("ui.py", "login.py", "setup.py"):
        return "nucleo"
    return "outro"


def listar_arquivos(raiz: Path) -> list[str]:
    """Os arquivos que são DNA (código e páginas). Dados e configurações ficam de fora."""
    raiz = Path(raiz)
    out = []
    for pasta, subs, arqs in os.walk(raiz):
        rel_pasta = Path(pasta).relative_to(raiz).as_posix()
        subs[:] = sorted(s for s in subs if s not in IGNORAR and not s.startswith("."))
        partes = [] if rel_pasta == "." else rel_pasta.split("/")
        if partes[:1] == ["memory"] and len(partes) > 1:
            subs[:] = []
            continue
        for a in sorted(arqs):
            rel = a if not partes else f"{rel_pasta}/{a}"
            suf = Path(a).suffix.lower()
            if a.endswith((".tmp", ".pyc")) or ".mutante-" in a or ".corrompido-" in a:
                continue
            if partes[:1] == ["memory"] and suf != ".py":
                continue
            if partes[:1] == ["config"] and suf == ".json":
                continue                                   # config/*.json são dados (mudam sozinhos)
            if suf in EXTENSOES or a in EXTRAS:
                out.append(rel)
    return out


def sha256_arquivo(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def _canonico(g: dict) -> bytes:
    return json.dumps({k: v for k, v in g.items() if k != "assinatura"}, sort_keys=True, ensure_ascii=False).encode()


class DNA:
    def __init__(self, raiz: Path, pasta: Path):
        self.raiz = Path(raiz)
        self.pasta = Path(pasta)
        self.arquivo = self.pasta / "genoma.json"
        self.arq_chave = self.pasta / ".chave_dna"
        self.genoma: dict | None = None
        self.situacao = "sem_genoma"
        self._stat: dict[str, tuple[int, int, str]] = {}

    # ── chave e assinatura ────────────────────────────────────────────────────
    def _chave(self) -> bytes:
        try:
            return bytes.fromhex(self.arq_chave.read_text(encoding="utf-8").strip())
        except Exception:
            self.pasta.mkdir(parents=True, exist_ok=True)
            k = secrets.token_bytes(32)
            self.arq_chave.write_text(k.hex(), encoding="utf-8")
            return k

    def assinar(self, g: dict) -> str:
        return hmac.new(self._chave(), _canonico(g), hashlib.sha256).hexdigest()

    # ── leitura ───────────────────────────────────────────────────────────────
    def carregar(self) -> str:
        """'ok', 'sem_genoma', 'corrompido' (não abre) ou 'adulterado' (assinatura não bate)."""
        if not self.arquivo.exists():
            self.genoma, self.situacao = None, "sem_genoma"
            return self.situacao
        g = ler_json(self.arquivo, None)
        if not isinstance(g, dict) or "arquivos" not in g:
            self.genoma, self.situacao = None, "corrompido"
            return self.situacao
        ok = hmac.compare_digest(str(g.get("assinatura", "")), self.assinar(g))
        self.genoma, self.situacao = g, ("ok" if ok else "adulterado")
        return self.situacao

    def impressao_atual(self, rel: str) -> str | None:
        """SHA-256 do arquivo agora (só recalcula se a data ou o tamanho mudaram)."""
        p = self.raiz / rel
        try:
            st = p.stat()
        except OSError:
            return None
        cache = self._stat.get(rel)
        if cache and cache[0] == st.st_mtime_ns and cache[1] == st.st_size:
            return cache[2]
        try:
            h = sha256_arquivo(p)
        except OSError:
            return None
        self._stat[rel] = (st.st_mtime_ns, st.st_size, h)
        return h

    def versao_app(self) -> str:
        try:
            m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (self.raiz / "ui.py").read_text(encoding="utf-8", errors="replace"))
            return m.group(1) if m else "?"
        except OSError:
            return "?"

    def dependencias(self) -> dict:
        try:
            linhas = (self.raiz / "requirements.txt").read_text(encoding="utf-8").splitlines()
        except OSError:
            linhas = []
        nomes = sorted({re.split(r"[<>=!~\[; ]", l.split("#")[0].strip())[0] for l in linhas} - {""})
        return {"requirements": [n for n in nomes if not n.startswith("-")], "essenciais": list(ESSENCIAIS_PACOTES)}

    # ── escrita ───────────────────────────────────────────────────────────────
    def _montar(self, motivo: str, base: dict | None = None, so: list[str] | None = None) -> dict:
        arquivos = dict((base or {}).get("arquivos", {})) if so else {}
        for rel in (so if so else listar_arquivos(self.raiz)):
            h = self.impressao_atual(rel)
            if h is None:
                arquivos.pop(rel, None)
            else:
                arquivos[rel] = {"sha256": h, "tam": (self.raiz / rel).stat().st_size, "classe": classe_de(rel)}
        hist = list((base or {}).get("historico", []))[-30:]
        hist.append({"ts": time.time(), "motivo": motivo, "arquivos": len(arquivos)})
        g = {"versao_genoma": 1, "criado": (base or {}).get("criado", time.time()), "atualizado": time.time(),
             "app_versao": self.versao_app(), "python": sys.version.split()[0], "arquivos": arquivos,
             "modulos": {"plugins": sorted(Path(r).stem for r in arquivos if r.startswith("plugins/") and r.endswith(".py")
                                           and not Path(r).stem.startswith("_"))},
             "dependencias": self.dependencias(), "historico": hist}
        g["assinatura"] = self.assinar(g)
        return g

    def genese(self) -> dict | None:
        """O primeiro genoma. Só acontece quando ainda não existe nenhum (nascimento)."""
        if self.arquivo.exists():
            return None
        g = self._montar("gênese")
        gravar_json(self.arquivo, g)
        self.genoma, self.situacao = g, "ok"
        return g

    def mutar(self, ficha: str | None, autorizacoes, motivo: str, so: list[str] | None = None) -> str:
        """Aceita as mudanças atuais no DNA. EXIGE a ficha que só a sua autorização cria."""
        alvo = ",".join(sorted(so)) if so else "tudo"
        if not autorizacoes.validar(ficha, f"dna_mutar:{alvo}"):
            return "Recusado: mudar o DNA precisa da sua autorização na tela."
        base = self.genoma if self.situacao == "ok" else None
        g = self._montar(motivo, base, so)
        gravar_json(self.arquivo, g)
        self.genoma, self.situacao = g, "ok"
        return f"DNA atualizado ({len(so) if so else len(g['arquivos'])} arquivo(s)): {motivo}."

    def resumo(self) -> dict:
        g = self.genoma or {}
        return {"situacao": self.situacao, "arquivos": len(g.get("arquivos", {})), "versao": g.get("app_versao", "?"),
                "atualizado": g.get("atualizado"), "mutacoes": max(0, len(g.get("historico", [])) - 1)}
