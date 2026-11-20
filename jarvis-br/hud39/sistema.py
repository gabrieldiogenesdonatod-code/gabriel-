"""Os números do HUD 3.9. Lê a telemetria do JARVIS (a mesma fonte do HUD e do 📊 MONITOR) e as
informações fixas do sistema, uma vez só."""
from __future__ import annotations

import getpass
import os
import platform
import re
import socket
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parent.parent
_SO = platform.system()
_IGNORAR = {"system idle process", "idle", "registry", "memory compression", "memcompression"}


def _tel():
    try:
        from core import telemetria
        return telemetria.get()
    except Exception:
        return None


# ── informações fixas ─────────────────────────────────────────────────────────
def _reg(caminho: str, nome: str):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, caminho) as k:
            return winreg.QueryValueEx(k, nome)[0]
    except Exception:
        return None


def _windows() -> dict:
    cv = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    build = str(_reg(cv, "CurrentBuild") or platform.version().split(".")[-1])
    ubr = _reg(cv, "UBR")
    nome = str(_reg(cv, "ProductName") or f"Windows {platform.release()}")
    # O registro do Windows 11 continua dizendo "Windows 10": a diferença é o build.
    if build.isdigit() and int(build) >= 22000:
        nome = nome.replace("Windows 10", "Windows 11")
    return {"so": nome, "versao": str(_reg(cv, "DisplayVersion") or ""),
            "build": f"{build}.{ubr}" if ubr is not None else build}


def _cpu_nome() -> str:
    try:
        if _SO == "Windows":
            v = _reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
            if v:
                return " ".join(str(v).split())
        elif _SO == "Linux":
            for linha in Path("/proc/cpuinfo").read_text(errors="ignore").splitlines():
                if linha.lower().startswith("model name"):
                    return linha.split(":", 1)[1].strip()
        elif _SO == "Darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                  text=True, timeout=3).stdout.strip()
    except Exception:
        pass
    return platform.processor() or platform.machine()


def _versao_jarvis() -> str:
    try:
        m = re.search(r"^## \[([\d.]+)\]", (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "3.9"


@lru_cache(maxsize=1)
def fixo() -> dict:
    """O que não muda enquanto o PC está ligado (lido uma vez)."""
    if _SO == "Windows":
        so = _windows()
    elif _SO == "Darwin":
        so = {"so": f"macOS {platform.mac_ver()[0]}", "versao": "", "build": platform.release()}
    else:
        nome = "Linux"
        try:
            for linha in Path("/etc/os-release").read_text().splitlines():
                if linha.startswith("PRETTY_NAME="):
                    nome = linha.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        so = {"so": nome, "versao": "", "build": platform.release()}
    maq = platform.machine().lower()
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = ""
    pasta_plugins = RAIZ / "plugins"
    plugins = sorted(p.stem for p in pasta_plugins.glob("*.py") if not p.stem.startswith("_")) \
        if pasta_plugins.exists() else []
    return {
        **so,
        "arquitetura": "64 bits" if ("64" in maq or sys.maxsize > 2 ** 32) else "32 bits",
        "maquina": platform.machine(),
        "computador": socket.gethostname(),
        "usuario": usuario,
        "cpu_nome": _cpu_nome(),
        "nucleos_fisicos": psutil.cpu_count(logical=False) or 0,
        "nucleos_logicos": psutil.cpu_count() or 0,
        "ram_total": psutil.virtual_memory().total,
        "python": platform.python_version(),
        "jarvis_versao": _versao_jarvis(),
        "plugins": len(plugins),
        "pasta": str(RAIZ),
    }


# ── o momento ─────────────────────────────────────────────────────────────────
def _disco_principal(particoes: list) -> dict:
    alvo = (os.environ.get("SystemDrive", "C:") + "\\") if _SO == "Windows" else "/"
    for p in particoes or []:
        if str(p.get("ponto", "")).upper() == alvo.upper():
            return {"ponto": p["ponto"], "pct": p.get("pct", 0), "usado": p.get("usado", 0),
                    "total": p.get("total", 0), "livre": p.get("livre", 0)}
    try:
        u = psutil.disk_usage(alvo)
        return {"ponto": alvo, "pct": u.percent, "usado": u.used, "total": u.total, "livre": u.free}
    except Exception:
        return {"ponto": alvo, "pct": 0, "usado": 0, "total": 0, "livre": 0}


def _particoes_psutil() -> list:
    out = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        out.append({"ponto": p.mountpoint, "tipo": p.fstype, "total": u.total, "usado": u.used,
                    "livre": u.free, "pct": u.percent})
    return out


def _cru() -> dict:
    """Sem a telemetria (não deveria acontecer): o mínimo direto do psutil."""
    vm = psutil.virtual_memory()
    return {"cpu": psutil.cpu_percent(None), "ram": {"pct": vm.percent, "usada": vm.total - vm.available,
            "total": vm.total}, "rede": {"down": 0.0, "up": 0.0}, "processos": [], "particoes": _particoes_psutil(),
            "uptime": time.time() - psutil.boot_time(), "gpu": None, "cpu_temp": None, "ping": {}}


def processos_top(lista: list, n: int = 8) -> list:
    """Os n processos que mais usam CPU, sem o 'ocioso' do Windows. Pura."""
    out = []
    for p in lista or []:
        nome = str(p.get("nome") or "?")
        if p.get("pid") in (0, None) or nome.lower().removesuffix(".exe") in _IGNORAR:
            continue
        out.append({"nome": nome.removesuffix(".exe"), "cpu": round(float(p.get("cpu") or 0), 1),
                    "ram": int(p.get("ram") or 0), "pid": p.get("pid")})
        if len(out) >= n:
            break
    return out


def momento() -> dict:
    t = _tel()
    s = t.snapshot() if t else _cru()
    particoes = s.get("particoes") or _particoes_psutil()
    ping = s.get("ping") or {}
    ping_ms = None
    for alvo in ("8.8.8.8", "1.1.1.1", "gateway"):
        v = (ping.get(alvo) or {}).get("ms") if isinstance(ping.get(alvo), dict) else None
        if v is not None:
            ping_ms = v
            break
    hist = {}
    if t:
        for k in ("cpu", "gpu", "temp", "down", "up", "ram"):
            try:
                hist[k] = [round(float(x), 2) for x in t.historico(k)[-60:]]
            except Exception:
                hist[k] = []
    gpu = s.get("gpu")
    return {
        "agora": time.time(),
        "cpu": round(float(s.get("cpu") or 0), 1),
        "cpu_temp": s.get("cpu_temp"),
        "cpu_freq": s.get("cpu_freq_mhz"),
        "nucleos": [round(float(x), 1) for x in (s.get("cpu_nucleos") or [])],
        "ram": {k: (s.get("ram") or {}).get(k) for k in ("pct", "usada", "total", "livre")},
        "disco": _disco_principal(particoes),
        "particoes": particoes,
        "rede": {"down": float((s.get("rede") or {}).get("down") or 0),
                 "up": float((s.get("rede") or {}).get("up") or 0)},
        "rede_hoje": s.get("rede_hoje") or {},
        "ping": ping_ms,
        "internet": s.get("internet"),
        "wifi": s.get("wifi") or {},
        "ip_local": s.get("ip_local") or "",
        "ip_publico": s.get("ip_publico") or "",
        "gateway": s.get("gateway") or "",
        "gpu": gpu if isinstance(gpu, dict) else None,
        "processos": processos_top(s.get("processos") or []),
        "total_processos": s.get("total_processos") or 0,
        "uptime": s.get("uptime") or (time.time() - psutil.boot_time()),
        "bateria": s.get("bateria"),
        "hist": hist,
    }
