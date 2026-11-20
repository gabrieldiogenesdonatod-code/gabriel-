"""Economia de energia do MINER AI: quanto gasta, quando pode rodar, quando pausa e quando reduz."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime


def threads_padrao(nucleos: int | None, economico: bool) -> int:
    """Modo econômico: 1 núcleo. Normal: metade dos núcleos (o PC continua usável). Pura."""
    return 1 if economico else max(1, int(nucleos or 2) // 2)


def carga_padrao(cfg: dict) -> float:
    return min(float(cfg.get("cpu_max") or 50), 30.0) if cfg.get("economico") else float(cfg.get("cpu_max") or 50)


def watts_estimados(cfg: dict, threads: int, carga_pct: float, nucleos: int | None = None, motor_externo: bool = False) -> float:
    """Watts A MAIS por estar minerando. Pura.
    Com medidor de tomada (watts_medidos), vale a medida (proporcional à carga). Sem ele: TDP × fração dos núcleos
    × carga — uma estimativa (o real pode ser maior: ventoinha, memória)."""
    nucleos = max(1, int(nucleos or os.cpu_count() or 2))
    fracao = min(1.0, max(0, threads) / nucleos) * max(0.0, min(100.0, carga_pct)) / 100
    if motor_externo:                                   # o XMRig não tem ciclo de descanso: usa a CPU inteira dos núcleos
        fracao = min(1.0, max(0, threads) / nucleos)
    medidos = float(cfg.get("watts_medidos") or 0)
    if medidos > 0:
        return round(medidos * (fracao / min(1.0, max(1, threads) / nucleos)) if not motor_externo else medidos, 2)
    return round(float(cfg.get("tdp_watts") or 15) * fracao * 1.6, 2)        # turbo do notebook passa do TDP


def kwh(watts: float, segundos: float) -> float:
    return max(0.0, watts) * max(0.0, segundos) / 3600 / 1000


def no_horario(janelas: list[str], agora: datetime) -> bool:
    """'22:00-07:00' atravessa a meia-noite. Lista vazia = qualquer hora. Pura."""
    if not janelas:
        return True
    m = agora.hour * 60 + agora.minute
    for j in janelas:
        try:
            a, b = [x.strip() for x in str(j).split("-")]
            ma = int(a.split(":")[0]) * 60 + int((a.split(":") + ["0"])[1])
            mb = int(b.split(":")[0]) * 60 + int((b.split(":") + ["0"])[1])
        except Exception:
            continue
        if (ma <= m < mb) if ma < mb else (m >= ma or m < mb):
            return True
    return False


def regular(carga: float, temp: float | None, temp_max: float, carga_max: float) -> tuple[float, str]:
    """Redução automática pela temperatura. Pura.
    ≥ máximo → 0 (pausa); a 5 °C do máximo → reduz 25%; 10 °C abaixo → sobe 10% até o limite."""
    if temp is None:
        return min(carga, carga_max), ""
    if temp >= temp_max:
        return 0.0, f"pausado: {temp:.0f} °C (limite {temp_max:.0f} °C)"
    if temp >= temp_max - 5:
        return max(10.0, round(carga * 0.75, 1)), f"reduzi a intensidade: {temp:.0f} °C"
    if temp <= temp_max - 10 and carga < carga_max:
        return min(carga_max, round(carga + max(5.0, carga * 0.10), 1)), ""
    return min(carga, carga_max), ""


def decidir(cfg: dict, agora: datetime, na_tomada: bool | None, ocioso_s: float | None, horas: float) -> tuple[bool, str]:
    """Pode rodar AGORA? (sim/não, motivo). Pura."""
    if horas >= float(cfg.get("horas_max") or 8):
        return False, f"chegou no limite de {float(cfg.get('horas_max') or 8):g} h"
    if cfg.get("parar_na_bateria", True) and na_tomada is False:
        return False, "na bateria"
    if not no_horario(cfg.get("horarios") or [], agora):
        return False, "fora do horário combinado"
    if cfg.get("economico") and ocioso_s is not None and ocioso_s < float(cfg.get("ocioso_min") or 0) * 60:
        return False, "você está usando o PC (modo econômico)"
    return True, ""


# ─────────────────────────────────────────────────────────── sensores (melhor esforço) ───
def na_tomada() -> bool | None:
    try:
        import psutil
        b = psutil.sensors_battery()
        return None if b is None else bool(b.power_plugged)
    except Exception:
        return None


def temperatura() -> float | None:
    """°C do processador. Linux: psutil. Windows: WMI (nem todo notebook informa). None = não dá para ler."""
    if os.name != "nt":
        try:
            import psutil
            t = [x.current for v in (psutil.sensors_temperatures() or {}).values() for x in v if x.current]
            return round(max(t), 1) if t else None
        except Exception:
            return None
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop "
                            "| Measure-Object -Property CurrentTemperature -Maximum).Maximum"],
                           capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        v = float(r.stdout.strip().replace(",", "."))
        return round(v / 10 - 273.15, 1) if v > 0 else None
    except Exception:
        return None


def ocioso_segundos() -> float | None:
    """Há quanto tempo ninguém mexe no teclado/mouse (Windows). None em outros sistemas."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(li)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
        return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0
    except Exception:
        return None
