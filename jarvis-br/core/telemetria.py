"""
core/telemetria.py — a ÚNICA fonte de métricas do PC no J.A.R.V.I.S BR.

POR QUE EXISTE
    Antes, a CPU era medida em dois lugares ao mesmo tempo: o HUD (ui.py) e o
    alerta de sistema (actions/system_monitor.py), os dois com
    `psutil.cpu_percent(interval=None)`. Essa chamada mede "desde a última
    chamada" — global, para o processo inteiro — então cada um zerava a janela
    de medição do outro e o alerta de CPU lia números que não eram reais.

    Agora há um coletor só. O HUD, o painel 📊 MONITOR, os alertas, o
    `system_status` e os plugins leem uma fotografia (`snapshot()`) dele. A CPU
    é calculada pelos deltas de `cpu_times()`, que não interferem em ninguém.

CICLOS (para ficar abaixo de ~2% de CPU)
    rápido   2 s   CPU total e por núcleo, RAM, swap, rede por interface,
                   leitura/escrita de disco
    lento    6 s   GPU (NVML), temperatura, bateria, ventoinhas, frequência,
                   tabela de processos
    preguiça 30 s  partições, conexões por processo, Wi-Fi, ping
    raro     5 min gateway, DNS, IP público (10 min)
    sob demanda    SMART, teste de velocidade, dispositivos da rede local

    O ping roda numa thread própria: um gateway que não responde nunca atrasa
    a medição de CPU. Nada aqui toca na thread da interface.
"""

from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import psutil

_SO = platform.system()
_WIN = _SO == "Windows"
_CNW: dict = {"creationflags": subprocess.CREATE_NO_WINDOW} if _WIN else {}
_BASE = Path(__file__).resolve().parent.parent

RAPIDO = 2.0
LENTO_A_CADA = 3          # × RAPIDO = 6 s
PREGUICA_A_CADA = 15      # × RAPIDO = 30 s
RARO = 300.0
IP_PUBLICO_A_CADA = 600.0
HISTORICO_PONTOS = 300    # 10 minutos a cada 2 s, para os mini gráficos

ALVOS_PING = ("gateway", "8.8.8.8", "1.1.1.1")


def _rodar(args, timeout=10, encoding=None):
    enc = encoding or ("oem" if _WIN else "utf-8")
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, **_CNW)
        try:
            return r.returncode, (r.stdout or b"").decode(enc, "replace")
        except LookupError:
            return r.returncode, (r.stdout or b"").decode("utf-8", "replace")
    except Exception as e:
        return -1, str(e)


def _ps_json(script: str, timeout=15):
    if not _WIN:
        return None
    pre = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$ErrorActionPreference='SilentlyContinue';"
    code, out = _rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        pre + script + " | ConvertTo-Json -Depth 3 -Compress"],
                       timeout=timeout, encoding="utf-8")
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out[min(i for i in (out.find("["), out.find("{")) if i >= 0):])
    except Exception:
        return None


# ── GPU (NVML) ─────────────────────────────────────────────────────────────────
class _NVML:
    """Lê a GPU NVIDIA pelo pynvml, ou direto da DLL com ctypes. Sem subprocess."""

    def __init__(self):
        self.ok: bool | None = None
        self._py = None
        self._h = None
        self._lib = None
        self._dev = None

    def _iniciar(self) -> bool:
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            self._py = pynvml
            self._h = pynvml.nvmlDeviceGetHandleByIndex(0)
            return True
        except Exception:
            self._py = None
        nomes = (("nvml", r"C:\Windows\System32\nvml.dll",
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll")
                 if _WIN else ("libnvidia-ml.so.1", "libnvidia-ml.so",
                               "libnvidia-ml.dylib"))
        for n in nomes:
            try:
                lib = ctypes.CDLL(n)
                if lib.nvmlInit_v2() != 0:
                    continue
                dev = ctypes.c_void_p()
                if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev)) != 0:
                    continue
                self._lib, self._dev = lib, dev
                return True
            except Exception:
                continue
        return False

    def ler(self) -> dict | None:
        if self.ok is False:
            return None
        if self.ok is None:
            self.ok = self._iniciar()
            if not self.ok:
                return None
        try:
            if self._py:
                p, h = self._py, self._h
                u = p.nvmlDeviceGetUtilizationRates(h)
                m = p.nvmlDeviceGetMemoryInfo(h)
                nome = p.nvmlDeviceGetName(h)
                nome = nome.decode() if isinstance(nome, bytes) else str(nome)
                try:
                    temp = float(p.nvmlDeviceGetTemperature(h, 0))
                except Exception:
                    temp = None
                try:
                    clock = float(p.nvmlDeviceGetClockInfo(h, 0))
                except Exception:
                    clock = None
                return {"nome": nome, "uso": float(u.gpu), "vram_usada": float(m.used),
                        "vram_total": float(m.total), "temp": temp, "clock_mhz": clock}

            lib, dev = self._lib, self._dev

            class _Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            class _Mem(ctypes.Structure):
                _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                            ("used", ctypes.c_ulonglong)]

            u, m = _Util(), _Mem()
            lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
            lib.nvmlDeviceGetMemoryInfo(dev, ctypes.byref(m))
            t, c = ctypes.c_uint(0), ctypes.c_uint(0)
            temp = float(t.value) if lib.nvmlDeviceGetTemperature(dev, 0, ctypes.byref(t)) == 0 else None
            clock = float(c.value) if lib.nvmlDeviceGetClockInfo(dev, 0, ctypes.byref(c)) == 0 else None
            buf = ctypes.create_string_buffer(96)
            nome = buf.value.decode(errors="replace") if lib.nvmlDeviceGetName(dev, buf, 96) == 0 else "NVIDIA"
            return {"nome": nome, "uso": float(u.gpu), "vram_usada": float(m.used),
                    "vram_total": float(m.total), "temp": temp, "clock_mhz": clock}
        except Exception:
            self.ok = False
            return None


# ── temperatura ────────────────────────────────────────────────────────────────
class _Temperatura:
    _PREFERIDOS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal",
                   "acpitz", "it8688")

    def __init__(self):
        self._wmi = None
        self._wmi_ok: bool | None = None

    def cpu(self) -> float | None:
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            for nome in self._PREFERIDOS:
                if temps.get(nome):
                    return float(temps[nome][0].current)
            for lista in temps.values():
                if lista:
                    return float(lista[0].current)
        except Exception:
            pass
        if _WIN and self._wmi_ok is not False:
            try:
                if self._wmi is None:
                    import wmi  # type: ignore
                    self._wmi = wmi.WMI(namespace="root/wmi")
                zonas = self._wmi.MSAcpi_ThermalZoneTemperature()
                if zonas:
                    self._wmi_ok = True
                    return round(zonas[0].CurrentTemperature / 10.0 - 273.15, 1)
            except Exception:
                self._wmi_ok, self._wmi = False, None
        return None


# ── ping (TCP como alternativa quando não há ICMP) ─────────────────────────────
_RE_TEMPO = re.compile(r"(?:time|tempo|zeit|temps|tiempo)\s*[=<]\s*([\d.,]+)\s*ms", re.I)


def medir_latencia(host: str, tentativas: int = 3, timeout: float = 1.0) -> dict:
    """{'ms': média ou None, 'perda': 0..100}. Usa ping; sem ele, mede o tempo
    de conexão TCP (uma recusa também é uma resposta e serve de medida)."""
    if not host:
        return {"ms": None, "perda": 100.0}
    from shutil import which
    if which("ping"):
        if _WIN:
            args = ["ping", "-n", str(tentativas), "-w", str(int(timeout * 1000)), host]
        elif _SO == "Darwin":
            args = ["ping", "-c", str(tentativas), "-W", str(int(timeout * 1000)), host]
        else:
            args = ["ping", "-c", str(tentativas), "-W", str(max(1, int(timeout))), host]
        _code, out = _rodar(args, timeout=tentativas * (timeout + 1) + 2)
        tempos = [float(x.replace(",", ".")) for x in _RE_TEMPO.findall(out)]
        if tempos or "ttl" in out.lower():
            perda = 100.0 * (tentativas - len(tempos)) / tentativas
            return {"ms": round(sum(tempos) / len(tempos), 1) if tempos else None,
                    "perda": round(max(0.0, perda), 1)}
    tempos = []
    for _ in range(tentativas):
        for porta in (53, 443, 80):
            t0 = time.perf_counter()
            try:
                with socket.create_connection((host, porta), timeout=timeout):
                    pass
                tempos.append((time.perf_counter() - t0) * 1000)
                break
            except ConnectionRefusedError:
                tempos.append((time.perf_counter() - t0) * 1000)
                break
            except OSError:
                continue
    perda = 100.0 * (tentativas - len(tempos)) / tentativas
    return {"ms": round(sum(tempos) / len(tempos), 1) if tempos else None,
            "perda": round(perda, 1)}


# ── rede: gateway, DNS, Wi-Fi, IP ──────────────────────────────────────────────
def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return ""


def rede_local() -> ipaddress.IPv4Network | None:
    """A sub-rede do IP local (no máximo /24, para a varredura ficar leve)."""
    ip = ip_local()
    if not ip:
        return None
    mascara = "255.255.255.0"
    try:
        for _nic, enderecos in psutil.net_if_addrs().items():
            for a in enderecos:
                if a.family == socket.AF_INET and a.address == ip and a.netmask:
                    mascara = a.netmask
    except Exception:
        pass
    try:
        net = ipaddress.IPv4Network(f"{ip}/{mascara}", strict=False)
        if net.prefixlen < 24:
            net = ipaddress.IPv4Network(f"{ip}/24", strict=False)
        return net
    except Exception:
        return None


def gateway_e_dns() -> tuple[str, list[str]]:
    if _WIN:
        dados = _ps_json(
            "$g=(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric |"
            " Select-Object -First 1).NextHop;"
            "$d=(Get-DnsClientServerAddress -AddressFamily IPv4 |"
            " Where-Object {$_.ServerAddresses} | Select-Object -ExpandProperty ServerAddresses);"
            "@{g=$g; d=@($d)}")
        if isinstance(dados, dict):
            dns = [d for d in (dados.get("d") or []) if d]
            return str(dados.get("g") or ""), list(dict.fromkeys(dns))
        return "", []
    gw, dns = "", []
    if _SO == "Linux":
        try:
            for linha in Path("/proc/net/route").read_text().splitlines()[1:]:
                c = linha.split()
                if len(c) > 2 and c[1] == "00000000" and c[2] != "00000000":
                    gw = socket.inet_ntoa(bytes.fromhex(c[2])[::-1])
                    break
        except Exception:
            pass
    else:
        _c, out = _rodar(["route", "-n", "get", "default"], timeout=5)
        m = re.search(r"gateway:\s*(\S+)", out)
        gw = m.group(1) if m else ""
    try:
        for linha in Path("/etc/resolv.conf").read_text().splitlines():
            if linha.strip().startswith("nameserver"):
                dns.append(linha.split()[1])
    except Exception:
        pass
    return gw, dns


def wifi_atual() -> dict:
    """{'ssid': str, 'sinal': 0..100 ou None} ou {} sem Wi-Fi."""
    if _WIN:
        code, out = _rodar(["netsh", "wlan", "show", "interfaces"], timeout=6)
        if code != 0:
            return {}
        ssid, sinal = "", None
        for linha in out.splitlines():
            chave, _, valor = linha.partition(":")
            chave = chave.strip().lower()
            if chave == "ssid":
                ssid = valor.strip()
            elif "%" in valor and ("sinal" in chave or "signal" in chave):
                try:
                    sinal = int(valor.strip().rstrip("%").strip())
                except ValueError:
                    pass
        return {"ssid": ssid, "sinal": sinal} if ssid else {}
    if _SO == "Linux":
        code, out = _rodar(["nmcli", "-t", "-f", "active,ssid,signal", "dev", "wifi"], timeout=6)
        for linha in out.splitlines():
            partes = linha.split(":")
            if len(partes) >= 3 and partes[0] in ("yes", "sim"):
                try:
                    return {"ssid": partes[1], "sinal": int(partes[2])}
                except ValueError:
                    return {"ssid": partes[1], "sinal": None}
        return {}
    code, out = _rodar(["networksetup", "-getairportnetwork", "en0"], timeout=5)
    m = re.search(r":\s*(.+)$", out.strip())
    return {"ssid": m.group(1), "sinal": None} if code == 0 and m else {}


def ip_publico() -> str:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-BR"})
            with urllib.request.urlopen(req, timeout=5) as r:
                ip = r.read().decode().strip()
                ipaddress.ip_address(ip)
                return ip
        except Exception:
            continue
    return ""


# ── o coletor ──────────────────────────────────────────────────────────────────
class Telemetria:
    def __init__(self):
        self._lock = threading.Lock()
        self._dados: dict = {
            "cpu": 0.0, "cpu_nucleos": [], "cpu_freq_mhz": None, "cpu_temp": None,
            "cpu_nucleos_fisicos": psutil.cpu_count(logical=False) or 0,
            "cpu_nucleos_logicos": psutil.cpu_count() or 0,
            "ram": {}, "swap": {}, "gpu": None,
            "rede": {"interfaces": {}, "down": 0.0, "up": 0.0},
            "rede_hoje": {"down": 0, "up": 0, "dia": date.today().isoformat()},
            "disco_io": {"leitura": 0.0, "escrita": 0.0},
            "particoes": [], "bateria": None, "ventoinhas": [],
            "uptime": 0.0, "boot": psutil.boot_time(),
            "processos": [], "total_processos": 0,
            "conexoes_por_pid": {}, "wifi": {}, "ping": {},
            "internet": None, "gateway": "", "dns": [], "ip_local": "",
            "ip_publico": "", "atualizado": 0.0,
        }
        self._hist = {k: deque(maxlen=HISTORICO_PONTOS)
                      for k in ("cpu", "ram", "gpu", "down", "up", "leitura", "escrita", "temp")}
        self._nvml = _NVML()
        self._temp = _Temperatura()
        self._procs: dict[int, psutil.Process] = {}
        self._usuarios: dict[int, str] = {}
        self._io_ant: dict[int, tuple[float, int]] = {}
        self._tempos_ant = None
        self._rede_ant = None
        self._disco_ant = None
        self._t_ant = time.monotonic()
        self._tick = 0
        self._ultimo_raro = 0.0
        self._ultimo_ip_pub = 0.0
        self._ping_rodando = False
        self._parar = threading.Event()
        self._ouvintes: list = []
        self._carregar_rede_hoje()
        # Duas leituras rápidas já aqui (0,1 s): quem pedir o primeiro
        # snapshot recebe CPU, RAM e rede de verdade, e não zeros.
        self._seguro("inicial", self._ciclo_rapido)
        time.sleep(0.1)
        self._seguro("inicial", self._ciclo_rapido)
        self._thread = threading.Thread(target=self._laco, daemon=True, name="telemetria")
        self._thread.start()

    # -- API pública ----------------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            d = dict(self._dados)
            d["ram"] = dict(d["ram"])
            d["swap"] = dict(d["swap"])
            d["rede"] = {**d["rede"], "interfaces": dict(d["rede"]["interfaces"])}
            d["processos"] = list(d["processos"])
            d["particoes"] = list(d["particoes"])
            d["ping"] = dict(d["ping"])
        return d

    def historico(self, chave: str) -> list[float]:
        with self._lock:
            return list(self._hist.get(chave, []))

    def ouvir(self, funcao) -> None:
        """funcao(snapshot) a cada ciclo rápido, numa thread. Leve, por favor."""
        self._ouvintes.append(funcao)

    def parar(self) -> None:
        self._parar.set()

    def medir_ping_agora(self) -> dict:
        self._ciclo_ping()
        return self.snapshot()["ping"]

    # -- laço -------------------------------------------------------------------
    def _laco(self):
        self._seguro("lento", self._ciclo_lento)
        self._seguro("30s", self._ciclo_preguica)
        threading.Thread(target=self._ciclo_raro, daemon=True).start()
        while not self._parar.wait(RAPIDO):
            self._tick += 1
            self._seguro("rápido", self._ciclo_rapido)
            if self._tick % LENTO_A_CADA == 0:
                self._seguro("lento", self._ciclo_lento)
            if self._tick % PREGUICA_A_CADA == 0:
                self._seguro("30s", self._ciclo_preguica)
            if time.monotonic() - self._ultimo_raro > RARO:
                self._ultimo_raro = time.monotonic()
                threading.Thread(target=self._ciclo_raro, daemon=True).start()
            snap = None
            for f in list(self._ouvintes):
                try:
                    snap = snap or self.snapshot()
                    f(snap)
                except Exception as e:
                    print(f"[Telemetria] ouvinte falhou: {e}")

    @staticmethod
    def _seguro(nome, fn):
        try:
            fn()
        except Exception as e:
            print(f"[Telemetria] ciclo {nome} falhou: {e}")

    # -- ciclo rápido -------------------------------------------------------------
    def _cpu_por_tempos(self):
        atuais = psutil.cpu_times(percpu=True)
        ant, self._tempos_ant = self._tempos_ant, atuais
        if not ant or len(ant) != len(atuais):
            return None, []
        nucleos, ocupado_t, total_t = [], 0.0, 0.0
        for a, b in zip(ant, atuais):
            ocioso_a = a.idle + getattr(a, "iowait", 0.0)
            ocioso_b = b.idle + getattr(b, "iowait", 0.0)
            total = sum(b) - sum(a)
            ocupado = total - (ocioso_b - ocioso_a)
            nucleos.append(round(max(0.0, min(100.0, 100.0 * ocupado / total)), 1) if total > 0 else 0.0)
            ocupado_t += max(0.0, ocupado)
            total_t += max(0.0, total)
        geral = round(100.0 * ocupado_t / total_t, 1) if total_t > 0 else 0.0
        return max(0.0, min(100.0, geral)), nucleos

    def _ciclo_rapido(self):
        agora = time.monotonic()
        dt = max(0.001, agora - self._t_ant)
        self._t_ant = agora

        cpu, nucleos = self._cpu_por_tempos()
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        ram = {"total": vm.total, "usada": vm.total - vm.available,
               "livre": vm.available, "pct": vm.percent,
               "cache": getattr(vm, "cached", 0) or getattr(vm, "buffers", 0) or 0}
        swap = {"total": sw.total, "usada": sw.used, "pct": sw.percent}

        nics = psutil.net_io_counters(pernic=True)
        interfaces, down, up = {}, 0.0, 0.0
        if self._rede_ant:
            for nome, c in nics.items():
                a = self._rede_ant.get(nome)
                if not a:
                    continue
                d_rx = max(0, c.bytes_recv - a.bytes_recv)
                d_tx = max(0, c.bytes_sent - a.bytes_sent)
                interfaces[nome] = {"down": d_rx / dt, "up": d_tx / dt,
                                    "total_down": c.bytes_recv, "total_up": c.bytes_sent}
                if not nome.lower().startswith(("lo", "loopback")):
                    down += d_rx / dt
                    up += d_tx / dt
        self._rede_ant = nics

        leitura = escrita = 0.0
        try:
            io = psutil.disk_io_counters()
            if io and self._disco_ant:
                leitura = max(0, io.read_bytes - self._disco_ant.read_bytes) / dt
                escrita = max(0, io.write_bytes - self._disco_ant.write_bytes) / dt
            self._disco_ant = io
        except Exception:
            pass

        hoje = date.today().isoformat()
        with self._lock:
            rh = self._dados["rede_hoje"]
            if rh["dia"] != hoje:
                rh.update({"dia": hoje, "down": 0, "up": 0})
            rh["down"] += int(down * dt)
            rh["up"] += int(up * dt)
            if cpu is not None:
                self._dados["cpu"] = cpu
                self._dados["cpu_nucleos"] = nucleos
            self._dados.update({
                "ram": ram, "swap": swap,
                "rede": {"interfaces": interfaces, "down": down, "up": up},
                "disco_io": {"leitura": leitura, "escrita": escrita},
                "uptime": time.time() - self._dados["boot"],
                "atualizado": time.time(),
            })
            g = self._dados["gpu"]
            for k, v in (("cpu", self._dados["cpu"]), ("ram", vm.percent),
                         ("gpu", g["uso"] if g else 0.0), ("down", down), ("up", up),
                         ("leitura", leitura), ("escrita", escrita),
                         ("temp", self._dados["cpu_temp"] or 0.0)):
                self._hist[k].append(v)

    # -- ciclo lento --------------------------------------------------------------
    def _ciclo_lento(self):
        gpu = self._nvml.ler()
        temp = self._temp.cpu()
        try:
            f = psutil.cpu_freq()
            freq = round(f.current) if f and f.current else None
        except Exception:
            freq = None
        bateria = None
        try:
            b = psutil.sensors_battery()
            if b is not None:
                bateria = {"pct": round(b.percent, 1), "na_tomada": bool(b.power_plugged),
                           "restante_s": (None if b.secsleft in (psutil.POWER_TIME_UNLIMITED,
                                                                 psutil.POWER_TIME_UNKNOWN)
                                          else int(b.secsleft))}
        except Exception:
            pass
        ventoinhas = []
        try:
            if hasattr(psutil, "sensors_fans"):
                for nome, lista in (psutil.sensors_fans() or {}).items():
                    for v in lista:
                        ventoinhas.append({"nome": v.label or nome, "rpm": v.current})
        except Exception:
            pass
        processos, total = self._tabela_processos()
        with self._lock:
            self._dados.update({"gpu": gpu, "cpu_temp": temp, "cpu_freq_mhz": freq,
                                "bateria": bateria, "ventoinhas": ventoinhas,
                                "processos": processos, "total_processos": total})

    def _tabela_processos(self):
        agora = time.monotonic()
        vistos, linhas = set(), []
        conexoes = self._dados.get("conexoes_por_pid", {})
        ncpu = psutil.cpu_count() or 1
        for p in psutil.process_iter(["pid", "name", "num_threads",
                                      "create_time", "memory_info", "status"]):
            pid = p.info["pid"]
            vistos.add(pid)
            proc = self._procs.get(pid)
            if proc is None or proc.info.get("create_time") != p.info.get("create_time"):
                self._procs[pid] = proc = p
                try:
                    proc.cpu_percent(None)       # prepara a medição
                except Exception:
                    pass
                # O dono do processo não muda: lido uma vez só, porque no
                # Windows essa consulta é a mais cara da tabela.
                try:
                    self._usuarios[pid] = (p.username() or "").split("\\")[-1]
                except Exception:
                    self._usuarios[pid] = ""
                cpu = 0.0
            else:
                proc.info = p.info
                try:
                    cpu = proc.cpu_percent(None) / ncpu
                except Exception:
                    cpu = 0.0
            disco = 0.0
            try:
                io = proc.io_counters()
                total_io = io.read_bytes + io.write_bytes
                ant = self._io_ant.get(pid)
                if ant:
                    disco = max(0, total_io - ant[1]) / max(0.5, agora - ant[0])
                self._io_ant[pid] = (agora, total_io)
            except Exception:
                pass
            mem = p.info.get("memory_info")
            linhas.append({
                "pid": pid, "nome": p.info.get("name") or "?",
                "usuario": self._usuarios.get(pid, ""),
                "cpu": round(cpu, 1), "ram": mem.rss if mem else 0,
                "disco": disco, "threads": p.info.get("num_threads") or 0,
                "inicio": p.info.get("create_time") or 0,
                "status": p.info.get("status") or "",
                "conexoes": conexoes.get(pid, 0),
            })
        for pid in list(self._procs):
            if pid not in vistos:
                self._procs.pop(pid, None)
                self._io_ant.pop(pid, None)
                self._usuarios.pop(pid, None)
        linhas.sort(key=lambda r: (r["cpu"], r["ram"]), reverse=True)
        return linhas, len(linhas)

    # -- ciclo de 30 s ----------------------------------------------------------------
    def _ciclo_preguica(self):
        particoes = []
        for p in psutil.disk_partitions(all=False):
            if "cdrom" in p.opts or not p.fstype:
                continue
            # Somente leitura (imagens squashfs, ISOs, snaps) aparece sempre
            # "100% cheia" e geraria alerta falso de disco.
            opcoes = {o.strip() for o in p.opts.split(",")}
            if "ro" in opcoes or p.fstype.lower() in ("squashfs", "iso9660", "udf"):
                continue
            if p.mountpoint.startswith(("/snap", "/boot/efi", "/var/lib/docker")):
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
            except Exception:
                continue
            particoes.append({"ponto": p.mountpoint, "dispositivo": p.device,
                              "tipo": p.fstype, "total": u.total, "usado": u.used,
                              "livre": u.free, "pct": u.percent})
        por_pid: dict[int, int] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid and c.raddr:
                    por_pid[c.pid] = por_pid.get(c.pid, 0) + 1
        except Exception:
            pass
        wifi = {}
        try:
            wifi = wifi_atual()
        except Exception:
            pass
        with self._lock:
            self._dados.update({"particoes": particoes, "conexoes_por_pid": por_pid,
                                "wifi": wifi, "ip_local": ip_local()})
        if not self._ping_rodando:
            threading.Thread(target=self._ciclo_ping, daemon=True, name="telemetria-ping").start()
        self._salvar_rede_hoje()

    def _ciclo_ping(self):
        self._ping_rodando = True
        try:
            gw = self._dados.get("gateway") or ""
            alvos = {"gateway": gw, "8.8.8.8": "8.8.8.8", "1.1.1.1": "1.1.1.1"}
            with ThreadPoolExecutor(max_workers=3) as ex:
                futs = {k: ex.submit(medir_latencia, h, 3) for k, h in alvos.items() if h}
                res = {k: f.result() for k, f in futs.items()}
            internet = any(v["ms"] is not None for k, v in res.items() if k != "gateway")
            with self._lock:
                self._dados["ping"] = res
                self._dados["internet"] = internet
        finally:
            self._ping_rodando = False

    def _ciclo_raro(self):
        try:
            gw, dns = gateway_e_dns()
            with self._lock:
                self._dados["gateway"] = gw
                self._dados["dns"] = dns
        except Exception as e:
            print(f"[Telemetria] gateway/DNS: {e}")
        if time.monotonic() - self._ultimo_ip_pub > IP_PUBLICO_A_CADA or not self._dados["ip_publico"]:
            ip = ip_publico()
            if ip:
                self._ultimo_ip_pub = time.monotonic()
                with self._lock:
                    self._dados["ip_publico"] = ip

    # -- total de rede do dia, sobrevive a reinícios do JARVIS -----------------------
    def _arquivo_rede(self) -> Path:
        return _BASE / "memory" / "rede_hoje.json"

    def _carregar_rede_hoje(self):
        try:
            d = json.loads(self._arquivo_rede().read_text(encoding="utf-8"))
            if d.get("dia") == date.today().isoformat():
                self._dados["rede_hoje"] = {"dia": d["dia"], "down": int(d.get("down", 0)),
                                            "up": int(d.get("up", 0))}
        except Exception:
            pass

    def _salvar_rede_hoje(self):
        try:
            caminho = self._arquivo_rede()
            caminho.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                dados = dict(self._dados["rede_hoje"])
            caminho.write_text(json.dumps(dados), encoding="utf-8")
        except Exception:
            pass


# ── sob demanda ─────────────────────────────────────────────────────────────────
_smart_cache: tuple[float, list] = (0.0, [])


def saude_discos(forcar: bool = False) -> list[dict]:
    """[{'disco', 'saude', 'detalhe'}]. Cache de 1 hora: é uma consulta cara."""
    global _smart_cache
    if not forcar and time.monotonic() - _smart_cache[0] < 3600 and _smart_cache[1]:
        return _smart_cache[1]
    res: list[dict] = []
    if _WIN:
        dados = _ps_json("Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,"
                         "OperationalStatus,MediaType,Size", timeout=20)
        for d in (dados if isinstance(dados, list) else [dados] if dados else []):
            saude = str(d.get("HealthStatus", "?"))
            res.append({"disco": d.get("FriendlyName", "?"),
                        "saude": {"Healthy": "saudável", "Warning": "ATENÇÃO",
                                  "Unhealthy": "COM PROBLEMA", "0": "saudável",
                                  "1": "ATENÇÃO", "2": "COM PROBLEMA"}.get(saude, saude),
                        "detalhe": f"{d.get('MediaType', '')} {round((d.get('Size') or 0) / 1e9)} GB".strip()})
    elif _SO == "Darwin":
        code, out = _rodar(["diskutil", "info", "disk0"], timeout=10)
        m = re.search(r"SMART Status:\s*(.+)", out)
        if m:
            estado = m.group(1).strip()
            res.append({"disco": "disk0", "saude": "saudável" if "Verified" in estado else estado,
                        "detalhe": "SMART"})
    else:
        from shutil import which
        if which("smartctl"):
            for dev in sorted({p.device.rstrip("0123456789").replace("nvme0n1p", "nvme0n1")
                               for p in psutil.disk_partitions() if p.device.startswith("/dev/")}):
                code, out = _rodar(["smartctl", "-H", dev], timeout=10)
                if "PASSED" in out or "OK" in out:
                    res.append({"disco": dev, "saude": "saudável", "detalhe": "SMART"})
                elif "FAILED" in out:
                    res.append({"disco": dev, "saude": "COM PROBLEMA", "detalhe": "SMART"})
    _smart_cache = (time.monotonic(), res)
    return res


def teste_velocidade(bytes_down: int = 25_000_000, bytes_up: int = 5_000_000) -> dict:
    """Download e upload contra o servidor da Cloudflare. ~10 s, só sob comando."""
    res = {"down_mbps": None, "up_mbps": None, "ping_ms": None, "erro": ""}
    try:
        lat = medir_latencia("speed.cloudflare.com", 3)
        res["ping_ms"] = lat["ms"]
        t0 = time.perf_counter()
        req = urllib.request.Request(f"https://speed.cloudflare.com/__down?bytes={bytes_down}",
                                     headers={"User-Agent": "JARVIS-BR"})
        recebido = 0
        with urllib.request.urlopen(req, timeout=30) as r:
            while True:
                bloco = r.read(256 * 1024)
                if not bloco:
                    break
                recebido += len(bloco)
                if time.perf_counter() - t0 > 15:
                    break
        dt = time.perf_counter() - t0
        res["down_mbps"] = round(recebido * 8 / dt / 1e6, 1)
        dados = os.urandom(bytes_up)
        t0 = time.perf_counter()
        req = urllib.request.Request("https://speed.cloudflare.com/__up", data=dados,
                                     headers={"User-Agent": "JARVIS-BR",
                                              "Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        dt = time.perf_counter() - t0
        res["up_mbps"] = round(len(dados) * 8 / dt / 1e6, 1)
    except Exception as e:
        res["erro"] = f"{type(e).__name__}: {e}"
    return res


def tabela_arp() -> dict[str, str]:
    """{ip: mac} do cache ARP do sistema."""
    pares: dict[str, str] = {}
    if _SO == "Linux":
        try:
            for linha in Path("/proc/net/arp").read_text().splitlines()[1:]:
                c = linha.split()
                if len(c) >= 4 and c[3] != "00:00:00:00:00:00":
                    pares[c[0]] = c[3].lower()
            return pares
        except Exception:
            pass
    code, out = _rodar(["arp", "-a"], timeout=8)
    for m in re.finditer(r"(\d{1,3}(?:\.\d{1,3}){3})\D+?([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})", out):
        mac = m.group(2).replace("-", ":").lower()
        if mac not in ("ff:ff:ff:ff:ff:ff",) and not mac.startswith("01:00:5e"):
            pares[m.group(1)] = mac
    return pares


def dispositivos_rede(varrer: bool = True, tempo_max: float = 8.0) -> list[dict]:
    """Aparelhos da SUA rede local (no máximo a /24 do seu IP).

    A varredura é leve: tenta abrir uma conexão TCP rápida em algumas portas
    comuns de cada endereço, o que faz o sistema preencher a tabela ARP. Não
    lê nada dos aparelhos, não testa senhas e não sai da sua sub-rede."""
    net = rede_local()
    if net is None:
        return []
    meu_ip = ip_local()
    if varrer:
        portas = (80, 443, 445, 22, 62078, 8009)
        inicio = time.monotonic()

        def toque(ip: str):
            if time.monotonic() - inicio > tempo_max:
                return
            for porta in portas[:2]:
                try:
                    with socket.create_connection((ip, porta), timeout=0.25):
                        return
                except OSError:
                    continue

        with ThreadPoolExecutor(max_workers=64) as ex:
            list(ex.map(toque, [str(h) for h in net.hosts() if str(h) != meu_ip]))
    arp = tabela_arp()
    gw = get().snapshot().get("gateway") or gateway_e_dns()[0]
    ips = []
    for ip in sorted(arp, key=lambda k: tuple(int(x) for x in k.split("."))):
        try:
            if ipaddress.IPv4Address(ip) in net:
                ips.append(ip)
        except Exception:
            continue

    def nome_de(ip: str) -> str:
        try:
            return socket.gethostbyaddr(ip)[0]
        except Exception:
            return ""

    # Nomes em paralelo, cada um com prazo; sem mexer no timeout global de
    # sockets, que vale para o programa inteiro.
    nomes: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ip: ex.submit(nome_de, ip) for ip in ips}
        for ip, f in futs.items():
            try:
                nomes[ip] = f.result(timeout=2.0)
            except Exception:
                nomes[ip] = ""
    lista = [{"ip": ip, "mac": arp[ip], "nome": nomes.get(ip, ""),
              "papel": "roteador" if ip == gw else ""} for ip in ips]
    if meu_ip:
        lista.insert(0, {"ip": meu_ip, "mac": "", "nome": socket.gethostname(),
                         "papel": "este PC"})
    return lista


def conexoes_ativas(limite: int = 300) -> list[dict]:
    """Conexões estilo netstat, com o nome do processo."""
    nomes: dict[int, str] = {}
    linhas = []
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception:
        return []
    for c in conns[:limite * 3]:
        if not c.raddr and c.status != "LISTEN":
            continue
        if c.pid and c.pid not in nomes:
            try:
                nomes[c.pid] = psutil.Process(c.pid).name()
            except Exception:
                nomes[c.pid] = "?"
        linhas.append({
            "pid": c.pid or 0, "processo": nomes.get(c.pid or 0, "?"),
            "local": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
            "remoto": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
            "remoto_ip": c.raddr.ip if c.raddr else "",
            "remoto_porta": c.raddr.port if c.raddr else 0,
            "estado": c.status, "tipo": "TCP" if c.type == socket.SOCK_STREAM else "UDP",
        })
        if len(linhas) >= limite:
            break
    return linhas


# ── singleton ───────────────────────────────────────────────────────────────────
_instancia: Telemetria | None = None
_inst_lock = threading.Lock()


def get() -> Telemetria:
    """O coletor único. Começa na primeira chamada."""
    global _instancia
    if _instancia is None:
        with _inst_lock:
            if _instancia is None:
                _instancia = Telemetria()
    return _instancia
