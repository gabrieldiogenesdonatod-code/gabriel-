"""
Limpeza do sistema — plugin do J.A.R.V.I.S BR.

"Jarvis, limpa o PC" → mede e mostra a prévia ("posso liberar 3,2 GB:
temporários 1,1 GB, navegadores 900 MB, lixeira 1,2 GB") e põe o botão
CONFIRMAR na tela. Só apaga depois que você confirma.

Categorias
    temporarios   pasta TEMP do usuário (e a do Windows, se der para escrever)
    navegadores   cache do Chrome, Edge, Brave, Opera, Vivaldi e Firefox
                  (só o CACHE: histórico, senhas, cookies e abas ficam)
    windows       INetCache, CrashDumps, D3DSCache, miniaturas no Linux e,
                  com administrador, o cache de download do Windows Update
    lixeira       esvazia a lixeira

Segurança
    * só mexe dentro das pastas da lista abaixo, resolvidas no momento;
    * nunca segue atalhos ou links simbólicos para fora delas;
    * pula arquivos modificados na última hora (podem estar em uso) e os que
      estão travados por algum programa;
    * modo "lixeira" (configurável): em vez de apagar, manda para a lixeira com
      o send2trash; o espaço só volta quando a lixeira for esvaziada.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from plugins._comum import (LINUX, MAC, WIN, cfg, confirmar, eh_admin, mostrar,
                            registrar, tamanho)

PLUGIN = {
    "name": "limpeza",
    "brief": "Cleanup preview with on-screen confirm: temp files, browser cache, system cache, recycle bin.",
    "description": (
        "System cleanup. action='previa' (default) measures what can be freed and puts "
        "a CONFIRM button on screen — use it for 'limpa o PC', 'libera espaço', 'limpa "
        "os temporários'. categorias optional: temporarios, navegadores, windows, "
        "lixeira (comma separated; empty = all). Never claim space was freed until the "
        "user confirmed on screen."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "previa"},
            "categorias": {"type": "STRING", "description": "temporarios, navegadores, windows, lixeira"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "limpeza",
    "title": "Limpeza do sistema",
    "fields": [
        {"key": "modo", "label": "O que fazer com os arquivos", "type": "choice",
         "options": ["apagar", "lixeira"], "default": "apagar"},
        {"key": "idade_min_horas", "label": "Só arquivos mais velhos que (horas)",
         "type": "text", "default": "1"},
    ],
}

CATEGORIAS = ("lixeira", "temporarios", "navegadores", "windows")
NOMES = {"temporarios": "temporários", "navegadores": "cache dos navegadores",
         "windows": "cache do sistema", "lixeira": "lixeira"}


def _env(nome: str) -> Path | None:
    v = os.environ.get(nome)
    return Path(v) if v else None


def _globs(base: Path | None, padroes: list[str]) -> list[Path]:
    if not base or not base.exists():
        return []
    saida = []
    for p in padroes:
        saida += [x for x in base.glob(p) if x.is_dir()]
    return saida


def raizes(categoria: str) -> list[Path]:
    """As pastas que a categoria pode limpar, neste computador, agora."""
    casa = Path.home()
    local, appdata = _env("LOCALAPPDATA"), _env("APPDATA")
    r: list[Path] = []
    if categoria == "temporarios":
        if WIN:
            r += [p for p in (_env("TEMP"), _env("TMP")) if p]
            win_temp = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
            if os.access(win_temp, os.W_OK):
                r.append(win_temp)
        elif MAC:
            r += [p for p in (_env("TMPDIR"),) if p]
        else:
            r += [casa / ".cache" / "tmp"]
    elif categoria == "navegadores":
        if WIN:
            cromo = ["*/Cache/Cache_Data", "*/Code Cache", "*/GPUCache", "*/Service Worker/CacheStorage"]
            for base in ((local / "Google/Chrome/User Data") if local else None,
                         (local / "Microsoft/Edge/User Data") if local else None,
                         (local / "BraveSoftware/Brave-Browser/User Data") if local else None,
                         (local / "Vivaldi/User Data") if local else None):
                r += _globs(base, cromo)
            if appdata:
                r += _globs(appdata / "Opera Software", ["*/Cache", "*/Code Cache", "*/GPUCache"])
            if local:
                r += _globs(local / "Mozilla/Firefox/Profiles", ["*/cache2"])
        elif MAC:
            r += _globs(casa / "Library/Caches", ["Google/Chrome", "Firefox", "BraveSoftware",
                                                   "com.microsoft.edgemac", "com.operasoftware.Opera"])
        else:
            r += [casa / ".cache" / n for n in ("google-chrome", "chromium", "BraveSoftware",
                                                "microsoft-edge", "vivaldi", "opera")]
            r += _globs(casa / ".cache/mozilla/firefox", ["*/cache2"])
    elif categoria == "windows":
        if WIN and local:
            r += [local / "Microsoft/Windows/INetCache", local / "CrashDumps", local / "D3DSCache"]
            if eh_admin():
                r.append(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SoftwareDistribution/Download")
        elif LINUX:
            r += [casa / ".cache/thumbnails"]
        elif MAC:
            r += [casa / "Library/Logs/DiagnosticReports"]
    return [p for p in r if p.exists()]


# ── lixeira ────────────────────────────────────────────────────────────────────
def tamanho_lixeira() -> int:
    if WIN:
        import ctypes

        class _INFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("i64Size", ctypes.c_longlong),
                        ("i64NumItems", ctypes.c_longlong)]
        info = _INFO()
        info.cbSize = ctypes.sizeof(_INFO)
        if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
            return int(info.i64Size)
        return 0
    pasta = Path.home() / (".Trash" if MAC else ".local/share/Trash/files")
    return sum(medir([pasta], 0).values()) if pasta.exists() else 0


def esvaziar_lixeira() -> bool:
    if WIN:
        import ctypes
        return ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4) in (0, -2147418113)
    pastas = [Path.home() / ".Trash"] if MAC else [Path.home() / ".local/share/Trash/files",
                                                     Path.home() / ".local/share/Trash/info"]
    for pasta in pastas:
        for item in pasta.iterdir() if pasta.exists() else []:
            try:
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink()
            except Exception:
                pass
    return True


# ── medir e apagar ─────────────────────────────────────────────────────────────
def _dentro(caminho: Path, raiz: Path) -> bool:
    try:
        caminho.resolve().relative_to(raiz.resolve())
        return True
    except Exception:
        return False


def _arquivos(raiz: Path, idade_min_s: float, prazo: float):
    limite = time.time() - idade_min_s
    for dirpath, dirs, nomes in os.walk(raiz, followlinks=False):
        if time.monotonic() > prazo:
            return
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(dirpath, d))]
        for n in nomes:
            caminho = os.path.join(dirpath, n)
            try:
                st = os.lstat(caminho)
            except OSError:
                continue
            if os.path.islink(caminho) or st.st_mtime > limite:
                continue
            yield caminho, st.st_size


def medir(pastas: list[Path], idade_min_s: float, segundos: float = 20) -> dict[str, int]:
    prazo = time.monotonic() + segundos
    total = {}
    for raiz in pastas:
        total[str(raiz)] = sum(t for _c, t in _arquivos(raiz, idade_min_s, prazo))
    return total


def previa(categorias: list[str], idade_min_s: float) -> dict[str, int]:
    res = {}
    for c in categorias:
        if c == "lixeira":
            res[c] = tamanho_lixeira()
        else:
            res[c] = sum(medir(raizes(c), idade_min_s).values())
    return res


def _apagar_raiz(raiz: Path, idade_min_s: float, modo: str) -> tuple[int, int]:
    """(bytes liberados, arquivos pulados)."""
    liberado, pulados = 0, 0
    if modo == "lixeira":
        try:
            from send2trash import send2trash
        except ImportError:
            modo = "apagar"
    if modo == "lixeira":
        limite = time.time() - idade_min_s
        for item in list(raiz.iterdir()):
            if item.is_symlink() or not _dentro(item, raiz):
                continue
            try:
                if item.is_dir():
                    tamanho_dir, novo = 0, False
                    for c, t in _arquivos(item, 0, time.monotonic() + 30):
                        tamanho_dir += t
                        if os.path.getmtime(c) > limite:
                            novo = True
                            break
                    if novo:
                        pulados += 1
                        continue
                    send2trash(str(item))
                    liberado += tamanho_dir
                elif item.stat().st_mtime <= limite:
                    t = item.stat().st_size
                    send2trash(str(item))
                    liberado += t
            except Exception:
                pulados += 1
        return liberado, pulados
    for caminho, t in list(_arquivos(raiz, idade_min_s, time.monotonic() + 120)):
        if not _dentro(Path(caminho), raiz):
            continue
        try:
            os.remove(caminho)
            liberado += t
        except Exception:
            pulados += 1
    # pastas que ficaram vazias
    for dirpath, _dirs, _nomes in sorted(os.walk(raiz, followlinks=False), key=lambda x: -len(x[0])):
        if dirpath != str(raiz):
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    return liberado, pulados


def executar(categorias: list[str], idade_min_s: float | None = None, modo: str | None = None) -> str:
    c = cfg("limpeza", PLUGIN_SETTINGS)
    idade = idade_min_s if idade_min_s is not None else max(0.0, float(str(c.get("idade_min_horas") or 1).replace(",", "."))) * 3600
    modo = modo or str(c.get("modo") or "apagar")
    liberado, pulados, feitos = 0, 0, []
    for cat in [x for x in CATEGORIAS if x in categorias]:      # lixeira primeiro
        if cat == "lixeira":
            antes = tamanho_lixeira()
            if antes and esvaziar_lixeira():
                liberado += antes
                feitos.append("lixeira")
            continue
        for raiz in raizes(cat):
            l, p = _apagar_raiz(raiz, idade, modo)
            liberado += l
            pulados += p
        feitos.append(NOMES[cat])
    msg = (f"Limpeza concluída: {tamanho(liberado)} "
           f"{'movidos para a lixeira' if modo == 'lixeira' else 'liberados'}"
           f" ({', '.join(feitos)}).")
    if pulados:
        msg += f" {pulados} itens estavam em uso e ficaram."
    try:
        from plugins import _monitor_db
        _monitor_db.gravar_evento("limpeza", msg)
    except Exception:
        pass
    return msg


def categorias_de(texto: str) -> list[str]:
    t = str(texto or "").lower()
    if not t.strip() or "tudo" in t or "todas" in t:
        return list(CATEGORIAS)
    escolhidas = []
    for cat, termos in {"temporarios": ("temp", "tempor"), "navegadores": ("naveg", "browser", "chrome", "edge", "firefox"),
                        "windows": ("windows", "sistema", "update", "miniatura"), "lixeira": ("lixeira", "lixo", "trash")}.items():
        if any(x in t for x in termos):
            escolhidas.append(cat)
    return escolhidas or list(CATEGORIAS)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    cats = categorias_de(p.get("categorias"))
    c = cfg("limpeza", PLUGIN_SETTINGS)
    try:
        idade = max(0.0, float(str(c.get("idade_min_horas") or 1).replace(",", "."))) * 3600
    except ValueError:
        idade = 3600.0
    modo = str(c.get("modo") or "apagar")
    registrar(player, "Medindo o que dá para limpar…")
    try:
        prev = previa(cats, idade)
    except Exception as e:
        return f"Não consegui medir: {e}"
    total = sum(prev.values())
    if total < 1024 * 1024:
        return "Está tudo limpo: não há nem 1 MB para liberar."
    linhas = [f"{NOMES[k]:<24} {tamanho(v):>10}" for k, v in prev.items() if v]
    mostrar(player, "PRÉVIA DA LIMPEZA", "\n".join(linhas) + f"\n\n{'TOTAL':<24} {tamanho(total):>10}")
    detalhe = ", ".join(f"{NOMES[k]} {tamanho(v)}" for k, v in prev.items() if v)
    acao = "mover para a lixeira" if modo == "lixeira" else "liberar"
    return confirmar("limpeza", f"Limpeza: {acao} {tamanho(total)}", detalhe,
                     lambda: executar([k for k, v in prev.items() if v], idade, modo))
