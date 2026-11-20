"""
Modo faxina / anônimo (fork PT-BR 2.11).

Limpa o lixo do SEU PC com um comando: arquivos temporários, lixeira, lista de
"abertos recentes" e — se você pedir o modo anônimo — o cache e o histórico do
navegador. Só mexe nessas pastas de descarte conhecidas; NUNCA em documento,
foto ou arquivo de programa, e sempre pede a sua confirmação antes.

    "Jarvis, faz uma faxina no PC."              (temporários + lixeira + recentes)
    "Jarvis, modo anônimo: limpa meus rastros."  (acima + cache e histórico do navegador)
    "Jarvis, quanto dá pra limpar?"              (só mostra, não apaga)

Feche o navegador antes do modo anônimo (senão o histórico fica travado e ele pula).
"""

from __future__ import annotations

import os
import shutil
import unicodedata
from pathlib import Path

from plugins._comum import MAC, WIN, confirmar, mostrar, powershell, tamanho

PLUGIN = {
    "name": "modo_faxina",
    "brief": "PC cleanup: temp files, recycle bin, recent list, and (anonymous mode) browser cache/history.",
    "description": (
        "Cleans the user's own PC junk, with confirmation. action: 'previa'/'ver' (show what would be freed, delete "
        "nothing), 'limpar' (do it; modo='rapida' = temp+recycle bin+recent, or modo='anonimo' = also browser cache "
        "and history). Use for 'faz uma faxina', 'limpa os temporários', 'modo anônimo', 'limpa meus rastros/"
        "histórico'. Only touches known junk/temp/cache locations — never documents, photos or program files — and "
        "always confirms first. Close the browser before the anonymous mode so history isn't locked."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "previa | limpar"},
            "modo": {"type": "STRING", "description": "rapida | anonimo"},
        },
    },
}


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def modo_de(texto: str) -> str:
    t = dobrar(texto)
    if any(w in t for w in ("anonim", "rastro", "historico", "privacidade", "tudo", "completa", "navegador")):
        return "anonimo"
    return "rapida"


# ── alvos ──────────────────────────────────────────────────────────────────────
def _temp_dirs() -> list[Path]:
    dirs = []
    if WIN:
        for v in ("TEMP", "TMP"):
            if os.environ.get(v):
                dirs.append(Path(os.environ[v]))
        win = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
        dirs.append(win)
    else:
        dirs.append(Path("/tmp"))
        dirs.append(Path.home() / ".cache")
    vistos, saida = set(), []
    for d in dirs:
        try:
            r = d.resolve()
        except OSError:
            continue
        if str(r) not in vistos and _seguro(r):
            vistos.add(str(r))
            saida.append(r)
    return saida


def _recent_dir() -> Path | None:
    if WIN and os.environ.get("APPDATA"):
        p = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Recent"
        return p if p.exists() else None
    return None


def _browser_dirs(incluir_historico: bool) -> list[tuple[str, Path]]:
    """(rótulo, caminho) de cache e, se pedido, arquivos de histórico dos navegadores (puro-ish)."""
    saida = []
    if WIN:
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        perfis = [("Chrome", local / "Google/Chrome/User Data/Default"),
                  ("Edge", local / "Microsoft/Edge/User Data/Default")]
    elif MAC:
        base = Path.home() / "Library/Application Support"
        perfis = [("Chrome", base / "Google/Chrome/Default"), ("Edge", base / "Microsoft Edge/Default")]
    else:
        base = Path.home() / ".config"
        perfis = [("Chrome", base / "google-chrome/Default"), ("Edge", base / "microsoft-edge/Default")]
    for nome, perfil in perfis:
        if not perfil.exists():
            continue
        for sub in ("Cache", "Code Cache", "GPUCache"):
            d = perfil / sub
            if d.exists():
                saida.append((f"cache do {nome}", d))
        if incluir_historico:
            for arq in ("History", "Visited Links", "Top Sites"):
                f = perfil / arq
                if f.exists():
                    saida.append((f"histórico do {nome}", f))
    return saida


def _seguro(caminho: Path) -> bool:
    """Trava de segurança: o alvo tem que ser uma pasta de descarte, nunca a raiz/home/Windows (puro-ish)."""
    try:
        r = caminho.resolve()
    except OSError:
        return False
    proibidos = {Path.home().resolve(), Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()}
    if r in proibidos or r == Path(r.anchor) or len(r.parts) <= 2:
        return False
    # só o NOME do alvo precisa parecer descarte (olhar o caminho inteiro pegava "tmp" da pasta-mãe)
    marcas = ("temp", "tmp", "cache", "recent", "history", "visited", "top sites", "gpucache")
    return any(m in dobrar(r.name) for m in marcas)


def _tamanho(caminho: Path) -> int:
    try:
        if caminho.is_file():
            return caminho.stat().st_size
        total = 0
        for raiz, _dirs, arqs in os.walk(caminho):
            for a in arqs:
                try:
                    total += (Path(raiz) / a).stat().st_size
                except OSError:
                    pass
        return total
    except OSError:
        return 0


def plano(modo: str) -> list[tuple[str, Path, int]]:
    """(rótulo, caminho, bytes) de tudo que seria limpo (puro-ish: só lê)."""
    itens: list[tuple[str, Path]] = [("arquivos temporários", d) for d in _temp_dirs()]
    rec = _recent_dir()
    if rec:
        itens.append(("lista de abertos recentes", rec))
    if modo == "anonimo":
        itens += _browser_dirs(incluir_historico=True)
    return [(rot, cam, _tamanho(cam)) for rot, cam in itens if _seguro(cam) or cam == rec]


# ── limpeza ──────────────────────────────────────────────────────────────────
def _esvaziar(caminho: Path) -> int:
    """Apaga o CONTEÚDO de uma pasta (não a pasta), ou o arquivo. Devolve bytes liberados. Pula o que estiver em uso."""
    liberado = 0
    if caminho.is_file():
        try:
            liberado = caminho.stat().st_size
            caminho.unlink()
        except OSError:
            return 0
        return liberado
    for item in _listar(caminho):
        b = _tamanho(item)
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
            liberado += b
        except OSError:
            pass
    return liberado


def _listar(caminho: Path) -> list[Path]:
    try:
        return list(caminho.iterdir())
    except OSError:
        return []


def _esvaziar_lixeira() -> bool:
    if WIN:
        return powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")[0] == 0
    return False


def executar(modo: str) -> str:
    itens = plano(modo)
    liberado = 0
    for rot, caminho, _b in itens:
        if _seguro(caminho) or "recent" in dobrar(str(caminho)):
            liberado += _esvaziar(caminho)
    lixeira = _esvaziar_lixeira()
    partes = [f"{tamanho(liberado)} de lixo"]
    if lixeira:
        partes.append("lixeira esvaziada")
    if modo == "anonimo":
        partes.append("cache e histórico do navegador limpos (o que não estava em uso)")
    return "Faxina feita: " + ", ".join(partes) + "."


# ── ação ───────────────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "previa").strip()
    modo = dobrar(p.get("modo") or "") or modo_de(p.get("action") or "")
    if modo not in ("rapida", "anonimo"):
        modo = "rapida"
    try:
        itens = plano(modo)
        total = sum(b for _r, _c, b in itens)
        previa = "\n".join(f"{rot}: {tamanho(b)}" for rot, _c, b in itens) or "(nada encontrado)"
        mostrar(player, "FAXINA" + (" ANÔNIMA" if modo == "anonimo" else ""), previa)
        if acao in ("limpar", "faxina", "faz", "fazer", "pode", "confirmar", "sim", "anonimo", "tudo"):
            extra = (" Isso inclui o HISTÓRICO do navegador — feche o navegador antes." if modo == "anonimo" else "")
            return confirmar("modo_faxina", f"Faxina {'anônima' if modo == 'anonimo' else 'rápida'}",
                             f"Vou liberar cerca de {tamanho(total)} apagando temporários, a lixeira e os recentes"
                             + (", mais o cache e o histórico do navegador." if modo == "anonimo" else ".")
                             + " Só pastas de descarte; documentos e fotos ficam intactos." + extra,
                             lambda: executar(modo))
        dica = " Diga 'modo anônimo' pra incluir o histórico do navegador." if modo == "rapida" else ""
        return (f"Dá pra liberar cerca de {tamanho(total)} (temporários, lixeira, recentes"
                + (", cache e histórico" if modo == "anonimo" else "") + "). Mostrei o detalhe na tela. "
                f"Quer que eu limpe? É só dizer 'pode limpar'.{dica}")
    except Exception as e:
        return f"A faxina falhou: {e}"
