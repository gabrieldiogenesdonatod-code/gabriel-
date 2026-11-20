"""
Índice de aplicativos — o "lançador inteligente" do J.A.R.V.I.S BR.

De onde vêm os apps
    Windows  Menu Iniciar (seu e de todos os usuários), Área de Trabalho,
             Program Files, %LOCALAPPDATA%\\Programs, apps da Microsoft Store
             (a mesma lista do shell:AppsFolder, via Get-StartApps), jogos da
             Steam e da Epic.
    Linux    arquivos .desktop (sistema, usuário, Flatpak, Snap) e Steam.
    macOS    /Applications, ~/Applications e /System/Applications.

O índice fica em config/indice_apps.json e é refeito a cada 24 h, em segundo
plano, ou quando você pede ("atualiza a lista de apps").

Apelidos
    config/apelidos_apps.json: "zap" → "WhatsApp", "vscode" → "Visual Studio
    Code" etc. Edite à mão ou por voz ("o apelido de X é Y").

Busca aproximada
    "abre o vs code", "abrir whats", "abre o lol": nomes sem acento e sem
    pontuação, comparados por igualdade, começo, palavras em comum e
    semelhança (difflib). Desinstaladores, manuais e sites são penalizados.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shlex
import threading
import time
import unicodedata
from pathlib import Path

from plugins._comum import (CONFIG, MAC, WIN, como_lista, gravar_json,
                            iniciar, ler_json, powershell_json, rodar_como_admin)

ARQ_INDICE = CONFIG / "indice_apps.json"
ARQ_APELIDOS = CONFIG / "apelidos_apps.json"
VALIDADE = 24 * 3600

APELIDOS_PADRAO = {
    "zap": "WhatsApp", "zapzap": "WhatsApp", "whats": "WhatsApp", "wpp": "WhatsApp",
    "vscode": "Visual Studio Code", "vs code": "Visual Studio Code",
    "code": "Visual Studio Code", "insta": "Instagram", "face": "Facebook",
    "lol": "League of Legends", "obs": "OBS Studio", "capcut": "CapCut",
    "calculadora": "Calculadora", "calc": "Calculadora",
    "bloco de notas": "Bloco de Notas", "notepad": "Bloco de Notas",
    "explorador": "Explorador de Arquivos", "arquivos": "Explorador de Arquivos",
    "gerenciador de tarefas": "Gerenciador de Tarefas",
    "configuracoes": "Configurações", "word": "Word", "excel": "Excel",
    "powerpoint": "PowerPoint", "edge": "Microsoft Edge",
    "chrome": "Google Chrome", "steam": "Steam", "epic": "Epic Games Launcher",
}

_RUIM = ("uninstall", "desinstal", "unins", "readme", "leia-me", "manual", "help",
         "ajuda", "documentation", "documentacao", "website", "site", "license",
         "licenca", "release notes", "setup", "updater", "update", "crash",
         "report", "migration", "repair", "reparar", "debug")

_lock = threading.Lock()
_cache: dict | None = None
_construindo = False


# ── nomes ──────────────────────────────────────────────────────────────────────
def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    palavras = [p for p in t.split() if p not in ("o", "a", "os", "as", "app", "aplicativo",
                                                  "programa", "the", "de", "do", "da")]
    return " ".join(palavras)


def _abreviacao(p: str, palavra: str) -> bool:
    """'ms' abrevia 'microsoft': mesma primeira letra e as letras em ordem."""
    if not 2 <= len(p) <= 4 or not palavra or p[0] != palavra[0]:
        return False
    resto = iter(palavra[1:])
    return all(ch in resto for ch in p[1:])


def cobre_por_partes(pedido: list[str], nome: list[str]) -> bool:
    """Toda palavra do pedido casa com o começo de uma palavra do nome (2+
    letras), com as iniciais de 2+ palavras seguidas, ou é uma abreviação."""
    if not pedido or not nome:
        return False
    iniciais = {"".join(w[0] for w in nome[i:j]) for i in range(len(nome))
                for j in range(i + 2, len(nome) + 1)}
    for p in pedido:
        if len(p) >= 2 and (p in iniciais or any(w.startswith(p) or _abreviacao(p, w) for w in nome)):
            continue
        return False
    return True


def contem_nome_inteiro(pedido: list[str], nome_junto: str) -> bool:
    """Uma palavra do pedido começa com o nome, ou palavras seguidas formam o nome."""
    if any(t.startswith(nome_junto) for t in pedido):
        return True
    return any("".join(pedido[i:j]) == nome_junto
               for i in range(len(pedido)) for j in range(i + 2, len(pedido) + 1))


def pontuar(consulta: str, nome: str) -> int:
    """0–100: quanto `nome` parece ser o app que a pessoa pediu."""
    q, n = normalizar(consulta), normalizar(nome)
    if not q or not n:
        return 0
    if q == n:
        pontos = 100
    elif q.replace(" ", "") == n.replace(" ", ""):
        pontos = 97
    elif n.startswith(q + " ") or n.startswith(q):
        pontos = 88
    else:
        qs, ns = set(q.split()), set(n.split())
        if qs and qs <= ns:
            pontos = 80
        elif cobre_por_partes(q.split(), n.split()):
            # "vs code" → Visual Studio Code: cada palavra pedida é o começo de
            # uma palavra do nome ou as iniciais de palavras seguidas
            pontos = 78
        elif len(q) >= 3 and q in n.replace(" ", ""):
            pontos = 72
        elif len(n) >= 4 and contem_nome_inteiro(q.split(), n.replace(" ", "")):
            # o pedido contém o nome inteiro, respeitando as palavras:
            # "estudos" → "estudo", "spotify premium" → "Spotify"
            # (mas "ms teams" NÃO contém "steam": está no meio de "msteams")
            pontos = 74
        else:
            iniciais = "".join(p[0] for p in n.split())
            if len(q) >= 2 and q.replace(" ", "") == iniciais:
                pontos = 70
            else:
                pontos = int(difflib.SequenceMatcher(None, q, n).ratio() * 70)
    if any(r in n for r in _RUIM) and not any(r in q for r in _RUIM):
        pontos -= 40
    return max(0, pontos)


def melhores(consulta: str, entradas: list[dict], n: int = 5, minimo: int = 55) -> list[dict]:
    pontuadas = []
    for e in entradas:
        p = pontuar(consulta, e.get("nome", ""))
        # Preferência pelo tipo, para desempatar o mesmo app achado em vários
        # lugares: atalho do Menu Iniciar > Store > jogo > exe solto.
        bonus = {"atalho": 3, "store": 2, "steam": 2, "epic": 2, "desktop": 3, "app": 3}.get(
            e.get("tipo", ""), 0)
        if p >= minimo:
            pontuadas.append((p + bonus, e))
    pontuadas.sort(key=lambda pe: (-pe[0], len(pe[1].get("nome", ""))))
    vistos, saida = set(), []
    for p, e in pontuadas:
        chave = normalizar(e["nome"])
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append({**e, "pontos": p})
        if len(saida) >= n:
            break
    return saida


# ── apelidos ───────────────────────────────────────────────────────────────────
def apelidos() -> dict:
    dados = ler_json(ARQ_APELIDOS)
    if not isinstance(dados, dict):
        dados = dict(APELIDOS_PADRAO)
        try:
            gravar_json(ARQ_APELIDOS, dados)
        except Exception:
            pass
    return {normalizar(k): v for k, v in dados.items()}


def resolver_apelido(nome: str) -> str:
    return apelidos().get(normalizar(nome), nome)


def definir_apelido(apelido: str, nome_real: str) -> str:
    dados = ler_json(ARQ_APELIDOS)
    if not isinstance(dados, dict):
        dados = dict(APELIDOS_PADRAO)
    dados[apelido.strip().lower()] = nome_real.strip()
    gravar_json(ARQ_APELIDOS, dados)
    return f"Pronto: quando você disser {apelido}, eu abro {nome_real}."


# ── coleta ─────────────────────────────────────────────────────────────────────
def _env(nome: str) -> Path | None:
    v = os.environ.get(nome)
    return Path(v) if v else None


def _atalhos(pasta: Path, profundidade: int = 6) -> list[dict]:
    out = []
    if not pasta or not pasta.exists():
        return out
    base = len(pasta.parts)
    for raiz, dirs, arquivos in os.walk(pasta):
        if len(Path(raiz).parts) - base >= profundidade:
            dirs[:] = []
        for a in arquivos:
            ext = a.lower().rsplit(".", 1)[-1] if "." in a else ""
            if ext in ("lnk", "url", "appref-ms"):
                out.append({"nome": a.rsplit(".", 1)[0], "tipo": "atalho",
                            "alvo": str(Path(raiz) / a), "fonte": "menu"})
    return out


def _exes(pasta: Path, profundidade: int = 2) -> list[dict]:
    out = []
    if not pasta or not pasta.exists():
        return out
    base = len(pasta.parts)
    try:
        for raiz, dirs, arquivos in os.walk(pasta):
            nivel = len(Path(raiz).parts) - base
            if nivel >= profundidade:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.lower().startswith(("common files", "windows", "microsoft.net",
                                                                      "reference assemblies", "dotnet"))]
            for a in arquivos:
                if a.lower().endswith(".exe") and not any(r in a.lower() for r in _RUIM):
                    nome = a[:-4]
                    # "chrome.exe" dentro de "Google\Chrome\Application" vira
                    # "Google Chrome" se a pasta disser mais que o arquivo.
                    pasta_app = Path(raiz).name
                    if normalizar(pasta_app) and normalizar(nome) in normalizar(pasta_app):
                        nome = pasta_app
                    out.append({"nome": nome, "tipo": "exe", "alvo": str(Path(raiz) / a),
                                "fonte": "programas"})
    except Exception:
        pass
    return out


def _store() -> list[dict]:
    dados = powershell_json("Get-StartApps | Select-Object Name, AppID", timeout=25)
    out = []
    for d in como_lista(dados):
        nome, app_id = d.get("Name"), d.get("AppID")
        if nome and app_id:
            out.append({"nome": nome, "tipo": "store", "alvo": app_id, "fonte": "store"})
    return out


def _vdf_bibliotecas(steam: Path) -> list[Path]:
    libs = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    try:
        for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
            libs.append(Path(m.group(1).replace("\\\\", "\\")))
    except Exception:
        pass
    return list(dict.fromkeys(libs))


def _steam() -> list[dict]:
    candidatos = []
    if WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            candidatos.append(Path(winreg.QueryValueEx(k, "SteamPath")[0]))
        except Exception:
            pass
        candidatos.append(Path(r"C:\Program Files (x86)\Steam"))
    else:
        candidatos += [Path.home() / ".steam" / "steam", Path.home() / ".local/share/Steam",
                       Path.home() / "Library/Application Support/Steam"]
    out, vistos = [], set()
    for steam in candidatos:
        if not (steam / "steamapps").exists():
            continue
        for lib in _vdf_bibliotecas(steam):
            for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
                try:
                    txt = acf.read_text(encoding="utf-8", errors="ignore")
                    appid = re.search(r'"appid"\s+"(\d+)"', txt).group(1)
                    nome = re.search(r'"name"\s+"([^"]+)"', txt).group(1)
                except Exception:
                    continue
                if appid in vistos or "redistributable" in nome.lower() or "proton" in nome.lower():
                    continue
                vistos.add(appid)
                out.append({"nome": nome, "tipo": "steam", "alvo": f"steam://rungameid/{appid}",
                            "fonte": "steam"})
        break
    return out


def _epic() -> list[dict]:
    pasta = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    out = []
    for item in pasta.glob("*.item") if pasta.exists() else []:
        try:
            d = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
            url = ("com.epicgames.launcher://apps/"
                   f"{d['CatalogNamespace']}%3A{d['CatalogItemId']}%3A{d['AppName']}"
                   "?action=launch&silent=true")
            out.append({"nome": d.get("DisplayName") or d["AppName"], "tipo": "epic",
                        "alvo": url, "fonte": "epic"})
        except Exception:
            continue
    return out


def _desktop_linux() -> list[dict]:
    pastas = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
              Path.home() / ".local/share/applications",
              Path("/var/lib/flatpak/exports/share/applications"),
              Path.home() / ".local/share/flatpak/exports/share/applications",
              Path("/var/lib/snapd/desktop/applications")]
    out = []
    for pasta in pastas:
        for arq in pasta.glob("*.desktop") if pasta.exists() else []:
            try:
                txt = arq.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            secao = txt.split("[Desktop Entry]", 1)[-1].split("\n[", 1)[0]
            campos = dict(l.split("=", 1) for l in secao.splitlines() if "=" in l)
            if campos.get("NoDisplay", "").lower() == "true" or campos.get("Type", "Application") != "Application":
                continue
            nome = campos.get("Name[pt_BR]") or campos.get("Name")
            if nome:
                out.append({"nome": nome, "tipo": "desktop", "alvo": str(arq),
                            "exec": campos.get("Exec", ""), "fonte": "desktop"})
    return out


def _apps_mac() -> list[dict]:
    out = []
    for pasta in (Path("/Applications"), Path.home() / "Applications",
                  Path("/System/Applications"), Path("/System/Applications/Utilities")):
        for app in pasta.glob("*.app") if pasta.exists() else []:
            out.append({"nome": app.stem, "tipo": "app", "alvo": str(app), "fonte": "aplicativos"})
    return out


def construir() -> dict:
    """Varre tudo e grava o índice. Pode levar alguns segundos (Store)."""
    t0 = time.time()
    entradas: list[dict] = []
    if WIN:
        appdata, progdata = _env("APPDATA"), _env("PROGRAMDATA")
        for pasta in ((appdata / "Microsoft/Windows/Start Menu/Programs") if appdata else None,
                      (progdata / "Microsoft/Windows/Start Menu/Programs") if progdata else None):
            entradas += _atalhos(pasta)
        for pasta in (Path.home() / "Desktop", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"):
            for e in _atalhos(pasta, 1):
                entradas.append({**e, "fonte": "área de trabalho"})
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            entradas += _exes(_env(var))
        local = _env("LOCALAPPDATA")
        if local:
            entradas += _exes(local / "Programs", 3)
        entradas += _store()
        entradas += _epic()
    elif MAC:
        entradas += _apps_mac()
    else:
        entradas += _desktop_linux()
    entradas += _steam()
    dados = {"criado": time.time(), "segundos": round(time.time() - t0, 1), "entradas": entradas}
    try:
        gravar_json(ARQ_INDICE, dados)
    except Exception as e:
        print(f"[Apps] não gravei o índice: {e}")
    return dados


def indice(forcar: bool = False) -> list[dict]:
    """As entradas. Usa o cache se for recente; senão reconstrói."""
    global _cache
    with _lock:
        if not forcar and _cache and time.time() - _cache.get("criado", 0) < VALIDADE:
            return _cache["entradas"]
        if not forcar:
            disco = ler_json(ARQ_INDICE)
            if isinstance(disco, dict) and time.time() - disco.get("criado", 0) < VALIDADE:
                _cache = disco
                return disco["entradas"]
        if _construindo:
            # Outra thread já está varrendo: usa o índice velho (se houver)
            # em vez de varrer tudo duas vezes ao mesmo tempo.
            disco = ler_json(ARQ_INDICE)
            if isinstance(disco, dict) and disco.get("entradas"):
                return disco["entradas"]
    dados = construir()
    with _lock:
        _cache = dados
    return dados["entradas"]


def aquecer() -> None:
    """Constrói o índice em segundo plano, se estiver velho."""
    global _construindo
    if _construindo:
        return
    _construindo = True

    def trabalho():
        global _construindo
        try:
            indice()
        finally:
            _construindo = False

    threading.Thread(target=trabalho, daemon=True, name="indice-apps").start()


def procurar(consulta: str, n: int = 5) -> list[dict]:
    nome = resolver_apelido(consulta)
    return melhores(nome, indice(), n)


# ── abrir ──────────────────────────────────────────────────────────────────────
def _exec_desktop(exec_linha: str) -> list[str]:
    limpa = re.sub(r"%[fFuUdDnNickvm]", "", exec_linha).strip()
    try:
        return shlex.split(limpa)
    except ValueError:
        return limpa.split()


def lancar(entrada: dict, admin: bool = False) -> bool:
    """Abre uma entrada do índice. True se o pedido de abertura foi aceito."""
    tipo, alvo = entrada.get("tipo"), entrada.get("alvo", "")
    try:
        if WIN:
            if admin and tipo in ("atalho", "exe"):
                return rodar_como_admin(alvo)
            if tipo == "store":
                return iniciar(["explorer.exe", f"shell:AppsFolder\\{alvo}"])
            os.startfile(alvo)                                     # noqa: S606
            return True
        if MAC:
            return iniciar(["open", alvo] if tipo != "app" else ["open", "-a", alvo])
        if tipo == "desktop":
            from shutil import which
            if which("gtk-launch"):
                return iniciar(["gtk-launch", Path(alvo).stem])
            args = _exec_desktop(entrada.get("exec", ""))
            return iniciar(args) if args else False
        return iniciar(["xdg-open", alvo])
    except Exception as e:
        print(f"[Apps] não abri {entrada.get('nome')}: {e}")
        return False


def abrir(consulta: str, admin: bool = False) -> tuple[bool, dict | None]:
    """Procura e abre. (abriu?, entrada usada)."""
    achados = procurar(consulta, 1)
    if not achados:
        return False, None
    return lancar(achados[0], admin=admin), achados[0]
