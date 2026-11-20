"""
System Monitor — background metric checks with voice alert support.

Fork PT-BR 1.2: this file no longer measures anything itself. Its NVML, WMI and
psutil probes were a second copy of the HUD's, and both called
psutil.cpu_percent(interval=None), which resets one shared window — so each
reset the other's CPU reading. Every number now comes from core/telemetria.py,
the single collector the HUD, the 📊 MONITOR panel and the alerts also read.
"""
import time

import psutil

DEFAULT_THRESHOLDS = {
    "cpu":  90.0,
    "ram":  90.0,
    "temp": 85.0,
    "gpu":  95.0,
}

_COOLDOWN   = 300
_CPU_STREAK = 3

def _tel():
    """Fork PT-BR 1.2: a fonte única de métricas (core/telemetria.py)."""
    from core import telemetria
    return telemetria.get()


def get_system_status() -> dict:
    """Snapshot of current system metrics for the system_status tool.

    Fork PT-BR 1.2: read from core/telemetria.py instead of measuring again.
    The old `psutil.cpu_percent(interval=0.2)` here also reset the HUD's CPU
    window every time it ran."""
    s = _tel().snapshot()
    ram = s.get("ram") or {}
    gpu = s.get("gpu") or {}
    uptime_secs = time.time() - psutil.boot_time()
    uptime_h = int(uptime_secs // 3600)
    uptime_m = int((uptime_secs % 3600) // 60)
    discos = [{"ponto": d["ponto"], "livre_gb": round(d["livre"] / 1024 ** 3, 1),
               "uso_pct": d["pct"]} for d in s.get("particoes", [])]
    return {
        "cpu_percent":   round(float(s.get("cpu") or 0.0), 1),
        "ram_percent":   round(float(ram.get("pct") or 0.0), 1),
        "ram_used_gb":   round((ram.get("usada") or 0) / 1024 ** 3, 1),
        "ram_total_gb":  round((ram.get("total") or 0) / 1024 ** 3, 1),
        "cpu_temp_c":    round(s["cpu_temp"], 1) if s.get("cpu_temp") else None,
        "gpu_percent":   round(gpu["uso"], 1) if gpu.get("uso") is not None else None,
        "uptime":        f"{uptime_h}h {uptime_m}m",
        "process_count": s.get("total_processos") or len(psutil.pids()),
        "disks":         discos,
        "internet":      s.get("internet"),
    }


class SystemMonitor:
    """
    Stateful monitor — cooldown state persists across session reconnections.
    Call check() periodically; returns a [SYSTEM_ALERT] string or None.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds   = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._last_alert: dict[str, float] = {}
        self._cpu_streak  = 0

    def _can_alert(self, key: str) -> bool:
        return (time.monotonic() - self._last_alert.get(key, 0)) > _COOLDOWN

    def _record(self, key: str):
        self._last_alert[key] = time.monotonic()

    def check(self) -> str | None:
        # Fork PT-BR 1.2: com o plugin monitor_sistema ligado, os alertas são
        # dele (configuráveis no painel e registrados no histórico). Este
        # verificador antigo fica quieto para ninguém ouvir o mesmo aviso duas
        # vezes. Com o plugin desligado, funciona como sempre funcionou.
        try:
            from memory.config_manager import get_plugin_enabled
            import sys as _sys
            if "plugins.monitor_sistema" in _sys.modules and get_plugin_enabled("monitor_sistema"):
                return None
        except Exception:
            pass
        try:
            s    = _tel().snapshot()
            cpu  = float(s.get("cpu") or 0.0)
            ram  = float((s.get("ram") or {}).get("pct") or 0.0)
            temp = float(s["cpu_temp"]) if s.get("cpu_temp") is not None else -1.0
            gpu  = float((s.get("gpu") or {}).get("uso", -1.0)) if s.get("gpu") else -1.0
        except Exception:
            return None

        alerts: list[str] = []

        if cpu >= self.thresholds["cpu"]:
            self._cpu_streak += 1
            if self._cpu_streak >= _CPU_STREAK and self._can_alert("cpu"):
                alerts.append(
                    f"[SYSTEM_ALERT] CPU usage has been critically high ({cpu:.0f}%) "
                    "for several seconds. Warn the user in their language and suggest "
                    "closing heavy applications."
                )
                self._record("cpu")
                self._cpu_streak = 0
        else:
            self._cpu_streak = 0

        if ram >= self.thresholds["ram"] and self._can_alert("ram"):
            alerts.append(
                f"[SYSTEM_ALERT] RAM is at {ram:.0f}% — nearly exhausted. "
                "Warn the user in their language and suggest freeing memory."
            )
            self._record("ram")

        if temp > 0 and temp >= self.thresholds["temp"] and self._can_alert("temp"):
            alerts.append(
                f"[SYSTEM_ALERT] CPU temperature is {temp:.0f}°C — above the safe limit. "
                "Warn the user in their language and advise reducing system load "
                "or checking cooling."
            )
            self._record("temp")

        if gpu >= 0 and gpu >= self.thresholds["gpu"] and self._can_alert("gpu"):
            alerts.append(
                f"[SYSTEM_ALERT] GPU load is at {gpu:.0f}%. "
                "Briefly inform the user in their language."
            )
            self._record("gpu")

        return " ".join(alerts) if alerts else None
