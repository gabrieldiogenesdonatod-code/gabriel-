"""
Sistema — plugin do J.A.R.V.I.S BR.

ARQUIVOS     buscar por nome ou conteúdo, abrir (inclusive "o primeiro da
             busca"), abrir pastas conhecidas, recentes, maiores arquivos.
REDE         Wi-Fi e Bluetooth liga/desliga (rádios do Windows, sem precisar
             de administrador), conectar em rede salva, redes salvas, renovar
             IP, limpar DNS, modo avião (todos os rádios).
SERVIÇOS     listar, ver, iniciar e parar (Windows pede administrador; o JARVIS
             mostra a confirmação e depois o aviso do UAC).
INICIALIZAÇÃO listar os programas que abrem com o PC, desativar e reativar (do
             mesmo jeito que o Gerenciador de Tarefas faz), com desfazer.
ENERGIA      plano de energia: listar e trocar (economia, equilibrado, alto
             desempenho), com desfazer.
ÁREA DE TRANSFERÊNCIA ler, copiar um texto, limpar.

Desligar o Wi-Fi, ligar o modo avião e renovar o IP cortam a conexão que o
próprio JARVIS usa para falar — por isso passam pela confirmação.
"""

from __future__ import annotations

import heapq
import os
import re
import time
import unicodedata
from pathlib import Path

from plugins._comum import (LINUX, MAC, NAO_DISPONIVEL, WIN, abrir_no_sistema,
                            confirmar, desfazer, mostrar, num, pasta_usuario,
                            powershell, rodar, rodar_como_admin, sim, tamanho, tem)

PLUGIN = {
    "name": "controle_sistema",
    "brief": "Find files, Wi-Fi/Bluetooth/airplane, DNS/IP, services, startup apps, power plan, clipboard.",
    "description": (
        "System tasks. FILES: action='buscar_arquivo' (nome, conteudo=sim to search "
        "inside files, pasta optional), 'abrir_arquivo' (caminho, or indice=N from the "
        "last search), 'abrir_pasta' (pasta = downloads | documentos | imagens | videos "
        "| musicas | area de trabalho | a path), 'recentes', 'maiores' (pasta). "
        "NETWORK: 'wifi' (ligar=sim|nao), 'bluetooth' (ligar), 'conectar_wifi' (rede), "
        "'redes_salvas', 'renovar_ip', 'limpar_dns', 'modo_aviao' (ligar). "
        "SERVICES: 'servicos' (filtro), 'servico_iniciar' / 'servico_parar' (nome). "
        "STARTUP: 'inicializacao' (list), 'inicializacao_desativar' / "
        "'inicializacao_ativar' (nome). POWER PLAN: 'planos_energia', 'plano_energia' "
        "(plano = economia | equilibrado | alto desempenho). CLIPBOARD: "
        "'clipboard_ler', 'clipboard_copiar' (texto), 'clipboard_limpar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "nome": {"type": "STRING"}, "pasta": {"type": "STRING"},
            "conteudo": {"type": "STRING", "description": "buscar_arquivo: 'sim' searches file contents"},
            "caminho": {"type": "STRING"}, "indice": {"type": "NUMBER"},
            "ligar": {"type": "STRING", "description": "sim | nao"},
            "rede": {"type": "STRING"}, "filtro": {"type": "STRING"},
            "plano": {"type": "STRING"}, "texto": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_ultima_busca: list[str] = []

_IGNORAR_DIRS = {"node_modules", ".git", "__pycache__", "appdata", "$recycle.bin", ".cache",
                 "venv", ".venv", "site-packages", "library", ".npm", ".gradle", "windows",
                 "program files", "program files (x86)", "programdata", ".local", ".vscode"}
_TEXTO = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html", ".htm", ".css",
          ".xml", ".log", ".ini", ".cfg", ".yaml", ".yml", ".java", ".c", ".cpp", ".h",
          ".cs", ".php", ".sql", ".bat", ".ps1", ".sh", ".rtf", ".tex", ".go", ".rs", ".kt"}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


# ── arquivos ───────────────────────────────────────────────────────────────────
_PASTAS = {"downloads": "Downloads", "download": "Downloads", "baixados": "Downloads",
           "documentos": "Documents", "documents": "Documents", "imagens": "Pictures",
           "fotos": "Pictures", "pictures": "Pictures", "videos": "Videos", "vídeos": "Videos",
           "musicas": "Music", "músicas": "Music", "music": "Music",
           "area de trabalho": "Desktop", "área de trabalho": "Desktop", "desktop": "Desktop"}


def pasta_conhecida(nome: str) -> Path | None:
    n = _dobrar(nome).strip()
    for chave, real in _PASTAS.items():
        if _dobrar(chave) == n:
            return pasta_usuario(real)
    p = Path(os.path.expandvars(os.path.expanduser(str(nome or "")))).resolve() if nome else None
    return p if p and p.exists() else None


def raizes_busca(pasta: str = "") -> list[Path]:
    if pasta:
        p = pasta_conhecida(pasta)
        return [p] if p else []
    raizes = [pasta_usuario(n) for n in ("Desktop", "Documents", "Downloads", "Pictures", "Videos")]
    raizes.append(pasta_usuario("Music"))
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        raizes.append(Path(onedrive))
    raizes.append(Path.home())
    vistos, saida = set(), []
    for r in raizes:
        if r.exists() and str(r) not in vistos:
            vistos.add(str(r))
            saida.append(r)
    return saida


def _caminhar(raizes: list[Path], prazo: float):
    vistos = set()
    for raiz in raizes:
        for dirpath, dirs, arquivos in os.walk(raiz):
            if time.monotonic() > prazo:
                return
            chave = os.path.normcase(dirpath)
            if chave in vistos:
                dirs[:] = []
                continue
            vistos.add(chave)
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in _IGNORAR_DIRS]
            for a in arquivos:
                yield Path(dirpath) / a


def _contem(arquivo: Path, termos: list[str]) -> bool:
    ext = arquivo.suffix.lower()
    try:
        if arquivo.stat().st_size > 3 * 1024 * 1024:
            return False
        if ext in _TEXTO:
            texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".docx":
            import zipfile
            with zipfile.ZipFile(arquivo) as z:
                texto = re.sub(r"<[^>]+>", " ", z.read("word/document.xml").decode("utf-8", "ignore"))
        else:
            return False
    except Exception:
        return False
    t = _dobrar(texto)
    return all(x in t for x in termos)


def buscar(nome: str, pasta: str = "", conteudo: bool = False, limite: int = 20,
           segundos: float = 8.0) -> list[Path]:
    termos = [t for t in _dobrar(nome).split() if t]
    if not termos:
        return []
    prazo = time.monotonic() + segundos
    achados: list[tuple[float, Path]] = []
    for arq in _caminhar(raizes_busca(pasta), prazo):
        nome_arq = _dobrar(arq.name)
        if all(t in nome_arq for t in termos) or (conteudo and _contem(arq, termos)):
            try:
                achados.append((arq.stat().st_mtime, arq))
            except OSError:
                continue
            if len(achados) >= limite * 5:
                break
    achados.sort(key=lambda x: -x[0])
    return [p for _t, p in achados[:limite]]


def _buscar(p: dict, player) -> str:
    global _ultima_busca
    nome = str(p.get("nome") or "").strip()
    if not nome:
        return "O que devo procurar?"
    res = buscar(nome, str(p.get("pasta") or ""), sim(p.get("conteudo")))
    _ultima_busca = [str(r) for r in res]
    if not res:
        return f"Não encontrei arquivos com {nome}."
    mostrar(player, f"ARQUIVOS — {nome}", "\n".join(
        f"{i + 1:>2}. {r.name}\n    {r.parent}" for i, r in enumerate(res)))
    return (f"Encontrei {len(res)} arquivo(s); o mais recente é {res[0].name}. "
            "Diga 'abre o primeiro' (ou o número) para abrir.")


def _abrir_arquivo(p: dict) -> str:
    caminho = str(p.get("caminho") or "").strip()
    if not caminho and p.get("indice") not in (None, ""):
        i = int(num(p.get("indice"), 1)) - 1
        if not 0 <= i < len(_ultima_busca):
            return "Esse número não está na última busca."
        caminho = _ultima_busca[i]
    if not caminho:
        if _ultima_busca:
            caminho = _ultima_busca[0]
        else:
            return "Qual arquivo?"
    alvo = Path(os.path.expanduser(caminho))
    if not alvo.exists():
        achados = buscar(caminho, limite=1, segundos=5)
        if not achados:
            return f"Não encontrei {caminho}."
        alvo = achados[0]
    return f"Abrindo {alvo.name}." if abrir_no_sistema(str(alvo)) else f"Não consegui abrir {alvo.name}."


def _abrir_pasta(p: dict) -> str:
    nome = str(p.get("pasta") or p.get("nome") or "").strip()
    pasta = pasta_conhecida(nome) if nome else None
    if not pasta:
        return f"Não encontrei a pasta {nome}."
    return f"Abrindo {pasta}." if abrir_no_sistema(str(pasta)) else "Não consegui abrir a pasta."


def recentes(n: int = 15) -> list[Path]:
    """Arquivos mexidos por último nas pastas do usuário (funciona em todo sistema)."""
    heap: list[tuple[float, str]] = []
    prazo = time.monotonic() + 6
    for arq in _caminhar(raizes_busca()[:-1], prazo):         # sem a home inteira
        try:
            m = arq.stat().st_mtime
        except OSError:
            continue
        if len(heap) < n:
            heapq.heappush(heap, (m, str(arq)))
        elif m > heap[0][0]:
            heapq.heapreplace(heap, (m, str(arq)))
    return [Path(c) for _m, c in sorted(heap, reverse=True)]


def maiores(pasta: str = "", n: int = 15) -> list[tuple[int, Path]]:
    raizes = raizes_busca(pasta) if pasta else [Path.home()]
    heap: list[tuple[int, str]] = []
    prazo = time.monotonic() + 12
    for arq in _caminhar(raizes, prazo):
        try:
            t = arq.stat().st_size
        except OSError:
            continue
        if len(heap) < n:
            heapq.heappush(heap, (t, str(arq)))
        elif t > heap[0][0]:
            heapq.heapreplace(heap, (t, str(arq)))
    return [(t, Path(c)) for t, c in sorted(heap, reverse=True)]


# ── rede e rádios ─────────────────────────────────────────────────────────────
_RADIO_PS = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
"""


def radio(tipo: str, ligar: bool | None) -> str:
    """tipo: 'WiFi' | 'Bluetooth' | 'todos'. ligar None = só ler o estado."""
    if WIN:
        filtro = "$radios" if tipo == "todos" else f"($radios | Where-Object {{ $_.Kind -eq '{tipo}' }})"
        if ligar is None:
            script = _RADIO_PS + f"{filtro} | ForEach-Object {{ \"$($_.Kind)=$($_.State)\" }}"
        else:
            estado = "On" if ligar else "Off"
            script = _RADIO_PS + (f"{filtro} | ForEach-Object {{ Await ($_.SetStateAsync('{estado}')) "
                                  "([Windows.Devices.Radios.RadioAccessStatus]) }")
        c, out = powershell(script, timeout=25)
        if ligar is None:
            return out
        if c != 0 or "Denied" in out or "Disabled" in out.replace("DisabledByUser", ""):
            return f"O Windows não deixou ({out.strip()[:80] or 'sem resposta'})."
        if not out.strip():
            return f"Não encontrei rádio {tipo} neste PC."
        return ""
    if LINUX:
        if tipo == "WiFi" and tem("nmcli"):
            rodar(["nmcli", "radio", "wifi", "on" if ligar else "off"])
            return ""
        if tipo == "Bluetooth" and tem("rfkill"):
            rodar(["rfkill", "unblock" if ligar else "block", "bluetooth"])
            return ""
        if tipo == "todos" and tem("rfkill"):
            rodar(["rfkill", "unblock" if ligar else "block", "all"])
            return ""
        return "Preciso do nmcli/rfkill para isso."
    if MAC and tipo == "WiFi":
        rodar(["networksetup", "-setairportpower", "en0", "on" if ligar else "off"])
        return ""
    return NAO_DISPONIVEL


def _radio_cmd(tipo: str, ligar, rotulo: str) -> str:
    liga = True if ligar in (None, "") else sim(ligar)

    def fazer():
        falha = radio(tipo, liga)
        return falha or f"{rotulo} {'ligado' if liga else 'desligado'}."

    if not liga and tipo in ("WiFi", "todos"):
        return confirmar(f"radio-{tipo}", f"Desligar {rotulo}",
                         "Se a internet deste PC vem por aqui, eu perco a conexão e paro de "
                         "responder por voz até ela voltar.", fazer)
    return fazer()


def _redes_salvas() -> list[str]:
    if WIN:
        _c, out = rodar(["netsh", "wlan", "show", "profiles"], timeout=8)
        return [l.split(":", 1)[1].strip() for l in out.splitlines()
                if ":" in l and ("perfil" in l.lower() or "profile" in l.lower()) and l.split(":", 1)[1].strip()]
    if LINUX and tem("nmcli"):
        _c, out = rodar(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
        return [l.split(":")[0] for l in out.splitlines() if "wireless" in l]
    return []


def _conectar_wifi(rede: str) -> str:
    salvas = _redes_salvas()
    if not salvas:
        return "Não encontrei redes Wi-Fi salvas."
    from plugins._indice_apps import pontuar
    melhor = max(salvas, key=lambda r: pontuar(rede, r)) if rede else None
    if not melhor or pontuar(rede, melhor) < 55:
        return f"Não achei a rede {rede}. Salvas: " + ", ".join(salvas[:8]) + "."
    if WIN:
        c, out = rodar(["netsh", "wlan", "connect", f"name={melhor}"], timeout=15)
    elif LINUX:
        c, out = rodar(["nmcli", "connection", "up", melhor], timeout=30)
    else:
        return NAO_DISPONIVEL
    return f"Conectando em {melhor}." if c == 0 else f"Não consegui: {out[:100]}"


def _renovar_ip() -> str:
    def fazer():
        if WIN:
            c, out = rodar(["ipconfig", "/renew"], timeout=60)
            if c != 0 and ("elev" in out.lower() or "admin" in out.lower() or "acesso" in out.lower()):
                return "Pedi permissão de administrador." if rodar_como_admin("ipconfig", "/renew") else \
                    "Precisa de administrador e o pedido foi recusado."
            return "IP renovado." if c == 0 else f"Falhou: {out[-120:]}"
        if LINUX and tem("nmcli"):
            _c, dev = rodar(["nmcli", "-t", "-f", "DEVICE,STATE", "device"])
            ativo = next((l.split(":")[0] for l in dev.splitlines() if ":connected" in l), "")
            if ativo:
                rodar(["nmcli", "device", "reapply", ativo], timeout=30)
                return "Conexão reaplicada."
        return NAO_DISPONIVEL
    return confirmar("renovar-ip", "Renovar o IP",
                     "A internet cai por alguns segundos e eu paro de ouvir até voltar.", fazer)


def _limpar_dns() -> str:
    if WIN:
        c, out = rodar(["ipconfig", "/flushdns"], timeout=20)
        if c == 0:
            return "Cache de DNS limpo."
        return "Pedi permissão de administrador." if rodar_como_admin("ipconfig", "/flushdns") else \
            f"Não consegui: {out[:100]}"
    if MAC:
        c, _o = rodar(["dscacheutil", "-flushcache"])
        return "Cache de DNS limpo." if c == 0 else "Precisa de sudo no Mac."
    if tem("resolvectl"):
        c, out = rodar(["resolvectl", "flush-caches"])
        return "Cache de DNS limpo." if c == 0 else f"Não consegui: {out[:100]}"
    return NAO_DISPONIVEL


# ── serviços ───────────────────────────────────────────────────────────────────
def listar_servicos(filtro: str = "") -> list[dict]:
    f = _dobrar(filtro)
    if WIN:
        import psutil
        out = []
        for s in psutil.win_service_iter():
            try:
                d = s.as_dict()
            except Exception:
                continue
            if f and f not in _dobrar(d.get("name")) and f not in _dobrar(d.get("display_name")):
                continue
            out.append({"nome": d.get("name"), "exibicao": d.get("display_name"),
                        "estado": d.get("status"), "inicio": d.get("start_type")})
        return out
    if LINUX and tem("systemctl"):
        _c, txt = rodar(["systemctl", "list-units", "--type=service", "--all", "--no-pager",
                         "--plain", "--no-legend"], timeout=10)
        out = []
        for l in txt.splitlines():
            c = l.split(None, 4)
            if len(c) >= 4 and (not f or f in _dobrar(l)):
                out.append({"nome": c[0], "exibicao": c[4] if len(c) > 4 else c[0],
                            "estado": c[3], "inicio": ""})
        return out
    return []


def _servico_mudar(nome: str, iniciar_: bool) -> str:
    lista = listar_servicos(nome)
    if not lista:
        return f"Não achei o serviço {nome}."
    alvo = next((s for s in lista if _dobrar(s["nome"]) == _dobrar(nome)), lista[0])
    verbo = "iniciar" if iniciar_ else "parar"

    def fazer():
        if WIN:
            ok = rodar_como_admin("sc.exe", f'{"start" if iniciar_ else "stop"} "{alvo["nome"]}"')
            return "Comando enviado com permissão de administrador." if ok else "O pedido de administrador foi recusado."
        c, out = rodar(["systemctl", "start" if iniciar_ else "stop", alvo["nome"]], timeout=30)
        return "Feito." if c == 0 else f"Precisa de permissão: sudo systemctl {verbo} {alvo['nome']} ({out[:60]})"

    return confirmar(f"servico-{alvo['nome']}", f"{verbo.capitalize()} o serviço {alvo['exibicao']}",
                     f"Serviço {alvo['nome']} (agora: {alvo['estado']}). Parar serviços do sistema pode "
                     "desligar recursos do Windows.", fazer)


# ── programas de inicialização ─────────────────────────────────────────────────
_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APROVADO = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def _estado_aprovado(winreg, raiz, sub: str, nome: str) -> bool:
    try:
        k = winreg.OpenKey(raiz, f"{_APROVADO}\\{sub}")
        dado, _t = winreg.QueryValueEx(k, nome)
        return not (dado and dado[0] % 2 == 1)          # 03, 07… = desativado
    except Exception:
        return True


def listar_inicializacao() -> list[dict]:
    itens = []
    if WIN:
        import winreg
        for raiz, rotulo in ((winreg.HKEY_CURRENT_USER, "usuário"), (winreg.HKEY_LOCAL_MACHINE, "todos")):
            try:
                k = winreg.OpenKey(raiz, _RUN)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    nome, comando, _t = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                itens.append({"nome": nome, "comando": str(comando), "origem": f"registro ({rotulo})",
                              "ativo": _estado_aprovado(winreg, raiz, "Run", nome),
                              "chave": ("HKCU" if raiz == winreg.HKEY_CURRENT_USER else "HKLM", "Run")})
        for pasta, rotulo, raiz in (
                (Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup",
                 "pasta (usuário)", winreg.HKEY_CURRENT_USER),
                (Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\StartUp",
                 "pasta (todos)", winreg.HKEY_LOCAL_MACHINE)):
            for arq in pasta.glob("*") if pasta.exists() else []:
                if arq.name.lower() == "desktop.ini":
                    continue
                itens.append({"nome": arq.name, "comando": str(arq), "origem": rotulo,
                              "ativo": _estado_aprovado(winreg, raiz, "StartupFolder", arq.name),
                              "chave": ("HKCU" if raiz == winreg.HKEY_CURRENT_USER else "HKLM",
                                        "StartupFolder")})
    elif LINUX:
        for arq in (Path.home() / ".config/autostart").glob("*.desktop"):
            txt = arq.read_text(errors="ignore")
            nome = re.search(r"^Name=(.*)$", txt, re.M)
            ativo = not re.search(r"^(Hidden=true|X-GNOME-Autostart-enabled=false)", txt, re.M | re.I)
            itens.append({"nome": nome.group(1) if nome else arq.stem, "comando": str(arq),
                          "origem": "autostart", "ativo": ativo, "arquivo": str(arq)})
    elif MAC:
        _c, out = rodar(["osascript", "-e", 'tell application "System Events" to get the name of every login item'])
        for n in out.split(","):
            if n.strip():
                itens.append({"nome": n.strip(), "comando": "", "origem": "itens de login", "ativo": True})
    return itens


def _definir_inicializacao(item: dict, ativar: bool) -> str:
    if WIN:
        import struct
        import winreg
        raiz_nome, sub = item["chave"]
        raiz = winreg.HKEY_CURRENT_USER if raiz_nome == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        # Mesmo formato do Gerenciador de Tarefas: 12 bytes, o primeiro diz
        # 02 (ativo) ou 03 (desativado), seguido da data em FILETIME.
        filetime = int((time.time() + 11644473600) * 10_000_000)
        dado = bytes([2 if ativar else 3, 0, 0, 0]) + struct.pack("<Q", filetime)
        try:
            k = winreg.CreateKeyEx(raiz, f"{_APROVADO}\\{sub}", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(k, item["nome"], 0, winreg.REG_BINARY, dado)
            winreg.CloseKey(k)
        except PermissionError:
            return "Esse item é de todos os usuários e precisa de administrador para mudar."
        return ""
    if LINUX:
        arq = Path(item["arquivo"])
        txt = arq.read_text(errors="ignore")
        txt = re.sub(r"^X-GNOME-Autostart-enabled=.*\n?", "", txt, flags=re.M)
        txt = re.sub(r"^Hidden=.*\n?", "", txt, flags=re.M)
        if not ativar:
            txt = txt.rstrip("\n") + "\nX-GNOME-Autostart-enabled=false\n"
        arq.write_text(txt)
        return ""
    return NAO_DISPONIVEL


def _inicializacao_mudar(nome: str, ativar: bool) -> str:
    from plugins._indice_apps import pontuar
    itens = listar_inicializacao()
    if not itens:
        return "Não encontrei programas de inicialização (ou o sistema não permite ler)."
    item = max(itens, key=lambda i: pontuar(nome, i["nome"]))
    if pontuar(nome, item["nome"]) < 55:
        return f"Não achei {nome} na inicialização."
    if item["ativo"] == ativar:
        return f"{item['nome']} já está {'ativado' if ativar else 'desativado'}."

    def fazer():
        falha = _definir_inicializacao(item, ativar)
        if falha:
            return falha
        desfazer(f"inicialização de {item['nome']}",
                 lambda: (_definir_inicializacao(item, not ativar), "Inicialização como estava.")[1])
        return f"{item['nome']} {'vai' if ativar else 'não vai mais'} abrir com o PC."

    return confirmar(f"inicializacao-{item['nome']}",
                     f"{'Ativar' if ativar else 'Desativar'} {item['nome']} na inicialização",
                     f"Origem: {item['origem']}. Dá para desfazer depois.", fazer)


# ── plano de energia ────────────────────────────────────────────────────────────
PLANOS = {"economia": "a1841308-3541-4fab-bc81-f71556f20b4a",
          "equilibrado": "381b4222-f694-41f0-9685-ff5bb260df2e",
          "alto desempenho": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
          "desempenho maximo": "e9a42b02-d5df-448d-aa00-03f14749eb61"}


def planos_windows() -> tuple[str, list[tuple[str, str]]]:
    _c, out = rodar(["powercfg", "/list"], timeout=10)
    planos, ativo = [], ""
    for l in out.splitlines():
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s+\((.+?)\)(\s*\*)?", l, re.I)
        if m:
            planos.append((m.group(1).lower(), m.group(2)))
            if m.group(3):
                ativo = m.group(1).lower()
    return ativo, planos


def plano_ativo() -> str:
    if WIN:
        return planos_windows()[0]
    if LINUX and tem("powerprofilesctl"):
        return rodar(["powerprofilesctl", "get"])[1].strip()
    return ""


def definir_plano(pedido: str) -> tuple[bool, str, str]:
    """(ok, mensagem, plano anterior)."""
    q = _dobrar(pedido)
    if WIN:
        ativo, planos = planos_windows()
        guid = None
        for chave, g in PLANOS.items():
            if chave in q or (chave.split()[0] in q and chave != "desempenho maximo"):
                guid = g
        if "maximo" in q or "ultimate" in q:
            guid = PLANOS["desempenho maximo"]
        if guid is None:
            nome = next((g for g, n in planos if q and q in _dobrar(n)), None)
            guid = nome
        if guid is None:
            return False, "Planos: " + ", ".join(n for _g, n in planos), ativo
        if guid not in [g for g, _n in planos]:
            # Notebooks com Modern Standby escondem o "Alto desempenho": dá para
            # criar uma cópia dele sem administrador.
            c, out = rodar(["powercfg", "-duplicatescheme", guid], timeout=10)
            m = re.search(r"([0-9a-f-]{36})", out, re.I)
            if c != 0 or not m:
                return False, "Este PC não tem esse plano de energia.", ativo
            guid = m.group(1).lower()
        c, out = rodar(["powercfg", "/setactive", guid], timeout=10)
        return c == 0, ("Plano de energia trocado." if c == 0 else f"Não consegui: {out[:80]}"), ativo
    if LINUX and tem("powerprofilesctl"):
        ativo = plano_ativo()
        perfil = "performance" if "desempenho" in q or "performance" in q else \
            "power-saver" if "economia" in q else "balanced"
        c, out = rodar(["powerprofilesctl", "set", perfil])
        return c == 0, ("Perfil de energia trocado." if c == 0 else f"Não consegui: {out[:80]}"), ativo
    return False, NAO_DISPONIVEL, ""


def _plano(pedido: str) -> str:
    ok, msg, anterior = definir_plano(pedido)
    if ok and anterior:
        def voltar(a=anterior):
            if WIN:
                rodar(["powercfg", "/setactive", a])
            else:
                rodar(["powerprofilesctl", "set", a])
            return "Plano de energia como estava."
        desfazer("plano de energia", voltar)
    return msg


# ── área de transferência ──────────────────────────────────────────────────────
def clipboard_ler() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        if WIN:
            return powershell("Get-Clipboard -Raw")[1]
        return ""


def clipboard_copiar(texto: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(texto)
        return True
    except Exception:
        if WIN:
            # Base64 no próprio comando: acentos chegam intactos, sem depender
            # da página de código do console.
            import base64
            b64 = base64.b64encode(texto.encode("utf-8")).decode()
            return powershell("Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString("
                              f"[Convert]::FromBase64String('{b64}')))", timeout=10)[0] == 0
        return False


# ── entrada ────────────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "").strip().lower()
    try:
        if a == "buscar_arquivo":
            return _buscar(p, player)
        if a == "abrir_arquivo":
            return _abrir_arquivo(p)
        if a == "abrir_pasta":
            return _abrir_pasta(p)
        if a == "recentes":
            lista = recentes()
            if not lista:
                return "Não encontrei arquivos recentes."
            mostrar(player, "ARQUIVOS RECENTES", "\n".join(
                f"{time.strftime('%d/%m %H:%M', time.localtime(f.stat().st_mtime))}  {f.name}\n    {f.parent}"
                for f in lista if f.exists()))
            global _ultima_busca
            _ultima_busca = [str(f) for f in lista]
            return f"O mais recente é {lista[0].name}. A lista está no painel."
        if a == "maiores":
            lista = maiores(str(p.get("pasta") or ""))
            if not lista:
                return "Não encontrei arquivos."
            mostrar(player, "MAIORES ARQUIVOS", "\n".join(f"{tamanho(t):>10}  {f}" for t, f in lista))
            return "Os maiores: " + ", ".join(f"{f.name} ({tamanho(t)})" for t, f in lista[:3]) + "."
        if a == "wifi":
            return _radio_cmd("WiFi", p.get("ligar"), "Wi-Fi")
        if a == "bluetooth":
            return _radio_cmd("Bluetooth", p.get("ligar"), "Bluetooth")
        if a == "modo_aviao":
            liga = True if p.get("ligar") in (None, "") else sim(p.get("ligar"))
            # modo avião LIGADO = rádios DESLIGADOS
            return _radio_cmd("todos", not liga, "todos os rádios (modo avião)")
        if a == "conectar_wifi":
            return _conectar_wifi(str(p.get("rede") or p.get("nome") or ""))
        if a == "redes_salvas":
            r = _redes_salvas()
            return ("Redes salvas: " + ", ".join(r) + ".") if r else "Nenhuma rede salva encontrada."
        if a == "renovar_ip":
            return _renovar_ip()
        if a == "limpar_dns":
            return _limpar_dns()
        if a == "servicos":
            lista = listar_servicos(str(p.get("filtro") or p.get("nome") or ""))
            if not lista:
                return "Nenhum serviço encontrado." if (WIN or LINUX) else NAO_DISPONIVEL
            mostrar(player, "SERVIÇOS", "\n".join(
                f"{s['estado']:<9} {s['inicio'] or '':<9} {s['nome'][:28]:<28} {s['exibicao']}" for s in lista[:200]))
            rodando = sum(1 for s in lista if s["estado"] in ("running", "active"))
            return f"{len(lista)} serviços, {rodando} rodando. A lista está no painel."
        if a in ("servico_iniciar", "servico_parar"):
            nome = str(p.get("nome") or "").strip()
            return _servico_mudar(nome, a == "servico_iniciar") if nome else "Qual serviço?"
        if a == "inicializacao":
            itens = listar_inicializacao()
            if not itens:
                return "Nenhum programa de inicialização encontrado."
            mostrar(player, "INICIALIZAÇÃO", "\n".join(
                f"{'ATIVO  ' if i['ativo'] else 'inativo'}  {i['nome'][:30]:<30} {i['origem']}" for i in itens))
            ativos = [i["nome"] for i in itens if i["ativo"]]
            if not ativos:
                return f"Nenhum programa abre com o PC ({len(itens)} desativados)."
            return (f"{len(ativos)} programa{'s abrem' if len(ativos) > 1 else ' abre'} com o PC: "
                    + ", ".join(ativos[:10]) + ".")
        if a in ("inicializacao_desativar", "inicializacao_ativar"):
            nome = str(p.get("nome") or "").strip()
            return _inicializacao_mudar(nome, a.endswith("ativar") and not a.endswith("desativar")) \
                if nome else "Qual programa?"
        if a == "planos_energia":
            if WIN:
                ativo, planos = planos_windows()
                return "Planos: " + ", ".join(f"{n}{' (ativo)' if g == ativo else ''}" for g, n in planos) + "."
            return f"Perfil atual: {plano_ativo() or 'desconhecido'}."
        if a == "plano_energia":
            return _plano(str(p.get("plano") or p.get("nome") or ""))
        if a == "clipboard_ler":
            t = clipboard_ler()
            if not t:
                return "A área de transferência está vazia (ou não tem texto)."
            mostrar(player, "ÁREA DE TRANSFERÊNCIA", t[:4000])
            return f"Tem {len(t)} caracteres copiados: {t[:200]}"
        if a == "clipboard_copiar":
            t = str(p.get("texto") or "")
            return "Copiado." if t and clipboard_copiar(t) else "Não consegui copiar."
        if a == "clipboard_limpar":
            return "Área de transferência limpa." if clipboard_copiar("") else "Não consegui limpar."
        return "Ação desconhecida para o sistema."
    except Exception as e:
        return f"A tarefa de sistema falhou: {e}"
