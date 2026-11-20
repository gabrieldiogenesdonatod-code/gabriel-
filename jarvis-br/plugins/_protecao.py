"""
Lista de proteção de processos — compartilhada por todos os plugins do
J.A.R.V.I.S BR que fecham, suspendem ou mudam a prioridade de programas.

Começa com "_" de propósito: o carregador de plugins pula este arquivo, então
ele não vira ferramenta. É só código que os outros plugins importam.

A REGRA
    Nenhum plugin pode finalizar, suspender ou rebaixar:
      * o próprio JARVIS, nem nenhum processo acima dele na árvore
        (o terminal ou o atalho que o abriu);
      * o Python que está rodando o JARVIS;
      * os processos que mantêm o sistema de pé (explorer, svchost, csrss,
        winlogon, lsass, services, dwm…), no Windows, macOS e Linux;
      * PIDs muito baixos (0, 4 e afins), que são o próprio kernel.

    Vale mesmo que o nome apareça num protocolo, num modo jogo ou num pedido
    por voz. A proteção é verificada no momento da ação, não na hora de salvar
    a configuração, então editar um JSON à mão não contorna nada.
"""

from __future__ import annotations

import os
import re
import sys

# Nomes sem extensão e em minúsculas.
PROTEGIDOS: frozenset[str] = frozenset({
    # Windows — núcleo, sessão e interface
    "system", "system idle process", "idle", "registry", "memory compression",
    "secure system", "smss", "csrss", "wininit", "winlogon", "services",
    "lsass", "lsaiso", "svchost", "fontdrvhost", "dwm", "explorer", "sihost",
    "taskhostw", "ctfmon", "conhost", "runtimebroker", "searchhost",
    "searchindexer", "startmenuexperiencehost", "shellexperiencehost",
    "textinputhost", "applicationframehost", "securityhealthservice",
    "securityhealthsystray", "msmpeng", "nissrv", "mpdefendercoreservice",
    "audiodg", "spoolsv", "wudfhost", "dllhost", "smartscreen", "lsm",
    "userinit", "logonui", "csrss", "wmiprvse", "trustedinstaller",
    "tiworker", "mousocoreworker", "systemsettings",
    # o interpretador que roda o JARVIS
    "python", "pythonw", "py", "pyw", "python3",
    # macOS
    "launchd", "kernel_task", "windowserver", "loginwindow", "finder", "dock",
    "systemuiserver", "coreaudiod", "mds", "mds_stores", "cfprefsd",
    "controlcenter", "notificationcenter",
    # Linux
    "systemd", "init", "kthreadd", "xorg", "xwayland", "gnome-shell",
    "plasmashell", "kwin_x11", "kwin_wayland", "mutter", "gdm", "sddm",
    "lightdm", "pipewire", "pipewire-pulse", "wireplumber", "pulseaudio",
    "dbus-daemon", "dbus-broker", "networkmanager", "sshd", "polkitd",
    "udisksd", "xdg-desktop-portal",
})

_MAX_PID_KERNEL = 8


def nome_base(nome: str) -> str:
    """'Explorer.EXE' → 'explorer'; 'Spotify.app' → 'spotify'."""
    # separa por "/" E por "\\": um caminho do Windows também precisa virar só
    # o nome do arquivo quando a comparação roda em outro sistema
    n = re.split(r"[\\/]", str(nome or ""))[-1].strip().lower()
    for suf in (".exe", ".app", ".bin"):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return n


_cache_pids: tuple[float, set[int]] = (0.0, set())


def pids_proprios() -> set[int]:
    """O JARVIS, a cadeia ACIMA dele e os processos com o mesmo executável.

    De propósito NÃO inclui os filhos: um programa que o JARVIS abriu (o
    Bloco de Notas, o Spotify) é filho dele, e precisa poder ser fechado
    depois. Guardado por 10 s, porque procurar os "irmãos" percorre a tabela
    de processos inteira."""
    global _cache_pids
    import time
    agora = time.monotonic()
    if agora - _cache_pids[0] < 10 and _cache_pids[1]:
        return set(_cache_pids[1])
    pids = {os.getpid()}
    try:
        import psutil
        for pai in psutil.Process().parents():
            if pai.pid > 1:
                pids.add(pai.pid)
        exe = _exe_proprio()
        if exe:
            for p in psutil.process_iter(["pid", "exe"]):
                try:
                    e = p.info.get("exe")
                    if e and os.path.normcase(os.path.realpath(e)) == exe:
                        pids.add(p.info["pid"])
                except Exception:
                    continue
    except Exception:
        pass
    _cache_pids = (agora, pids)
    return set(pids)


def _exe_proprio() -> str:
    try:
        return os.path.normcase(os.path.realpath(sys.executable))
    except Exception:
        return ""


def motivo_protecao(nome: str = "", pid: int | None = None,
                    exe: str = "") -> str:
    """'' quando a ação é permitida; senão, o motivo em português."""
    if pid is not None:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            pid = None
    if pid is not None and pid <= _MAX_PID_KERNEL:
        return "é um processo do núcleo do sistema"
    if pid is not None and pid in pids_proprios():
        return "é o próprio JARVIS (ou o programa que o abriu)"
    if nome_base(nome) in PROTEGIDOS:
        return "é um processo essencial do sistema"
    if exe:
        try:
            if os.path.normcase(os.path.realpath(exe)) == _exe_proprio():
                return "é o Python que está rodando o JARVIS"
        except Exception:
            pass
    return ""


def eh_protegido(nome: str = "", pid: int | None = None, exe: str = "") -> bool:
    return bool(motivo_protecao(nome, pid, exe))


def proteger_processo(proc) -> str:
    """Igual a motivo_protecao, mas lendo direto de um psutil.Process."""
    nome, exe = "", ""
    try:
        nome = proc.name()
    except Exception:
        pass
    try:
        exe = proc.exe()
    except Exception:
        pass
    return motivo_protecao(nome, getattr(proc, "pid", None), exe)


def filtrar_nomes(nomes) -> tuple[list[str], list[str]]:
    """Separa uma lista de nomes em (permitidos, bloqueados)."""
    ok, bloq = [], []
    for n in nomes or []:
        (bloq if nome_base(n) in PROTEGIDOS else ok).append(n)
    return ok, bloq
