"""
Janelas — listar, focar, minimizar, maximizar, restaurar, fechar, mover para
outro monitor, lado a lado, "sempre no topo" e minimizar tudo.

Windows: user32/dwmapi via ctypes (nenhuma dependência nova).
Linux:   wmctrl e xdotool, quando instalados (X11; no Wayland o próprio
         sistema não deixa programas mexerem nas janelas dos outros).
macOS:   listar, focar e minimizar pelo AppleScript; o resto não existe lá.
"""

from __future__ import annotations

import ctypes
import time

import psutil

from plugins._comum import LINUX, MAC, NAO_DISPONIVEL, WIN, powershell, rodar, tem
from plugins._indice_apps import normalizar, pontuar

if WIN:
    from ctypes import wintypes
    # Instâncias PRÓPRIAS das DLLs: declarar argtypes aqui não muda as funções
    # que outros módulos do JARVIS usam via ctypes.windll.
    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _dwm = ctypes.WinDLL("dwmapi")
    _H = wintypes.HWND
    for _nome, _args, _ret in (
        ("GetWindowTextLengthW", [_H], ctypes.c_int),
        ("GetWindowTextW", [_H, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        ("IsWindowVisible", [_H], wintypes.BOOL),
        ("GetWindow", [_H, wintypes.UINT], _H),
        ("GetWindowLongW", [_H, ctypes.c_int], ctypes.c_long),
        ("GetWindowThreadProcessId", [_H, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
        ("GetWindowRect", [_H, ctypes.c_void_p], wintypes.BOOL),
        ("IsIconic", [_H], wintypes.BOOL),
        ("IsZoomed", [_H], wintypes.BOOL),
        ("ShowWindow", [_H, ctypes.c_int], wintypes.BOOL),
        ("SetForegroundWindow", [_H], wintypes.BOOL),
        ("BringWindowToTop", [_H], wintypes.BOOL),
        ("GetForegroundWindow", [], _H),
        ("MoveWindow", [_H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL],
         wintypes.BOOL),
        ("PostMessageW", [_H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
        ("SetWindowPos", [_H, _H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                          wintypes.UINT], wintypes.BOOL),
        ("GetMonitorInfoW", [wintypes.HMONITOR, ctypes.c_void_p], wintypes.BOOL),
    ):
        _f = getattr(_u32, _nome)
        _f.argtypes, _f.restype = _args, _ret
    _dwm.DwmGetWindowAttribute.argtypes = [_H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT),
                    ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]

    class _WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT),
                    ("showCmd", wintypes.UINT), ("ptMinPosition", wintypes.POINT),
                    ("ptMaxPosition", wintypes.POINT), ("rcNormalPosition", _RECT)]

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _MONENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(_RECT), wintypes.LPARAM)

_SW_MAXIMIZE, _SW_MINIMIZE, _SW_RESTORE = 3, 6, 9
_WM_CLOSE = 0x0010
_HWND_TOPMOST, _HWND_NOTOPMOST = -1, -2
_SWP_NOSIZE, _SWP_NOMOVE, _SWP_SHOWWINDOW = 0x1, 0x2, 0x40
_GWL_EXSTYLE, _WS_EX_TOOLWINDOW, _WS_EX_TOPMOST = -20, 0x80, 0x8


# ── Windows ────────────────────────────────────────────────────────────────────
def _titulo(hwnd) -> str:
    n = _u32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _oculta_pelo_dwm(hwnd) -> bool:
    valor = ctypes.c_int(0)
    try:
        _dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(valor), ctypes.sizeof(valor))
    except Exception:
        return False
    return valor.value != 0


def _lista_windows() -> list[dict]:
    janelas = []
    nomes: dict[int, str] = {}

    def cb(hwnd, _lp):
        if not _u32.IsWindowVisible(hwnd) or _u32.GetWindow(hwnd, 4):     # GW_OWNER
            return True
        if _u32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
            return True
        titulo = _titulo(hwnd)
        if not titulo or _oculta_pelo_dwm(hwnd) or titulo in ("Program Manager",):
            return True
        pid = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in nomes:
            try:
                nomes[pid.value] = psutil.Process(pid.value).name()
            except Exception:
                nomes[pid.value] = "?"
        r = _RECT()
        _u32.GetWindowRect(hwnd, ctypes.byref(r))
        janelas.append({
            "id": int(hwnd), "titulo": titulo, "pid": pid.value,
            "processo": nomes[pid.value],
            "minimizada": bool(_u32.IsIconic(hwnd)),
            "maximizada": bool(_u32.IsZoomed(hwnd)),
            "no_topo": bool(_u32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOPMOST),
            "ret": (r.left, r.top, r.right, r.bottom),
        })
        return True

    _u32.EnumWindows(_WNDENUMPROC(cb), 0)
    return janelas


def monitores() -> list[dict]:
    """[{'indice', 'area': (l,t,r,b) útil, 'tela': (l,t,r,b), 'principal'}]."""
    if not WIN:
        return []
    lista = []

    def cb(hmon, _hdc, _r, _lp):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        _u32.GetMonitorInfoW(hmon, ctypes.byref(info))
        w, m = info.rcWork, info.rcMonitor
        lista.append({"area": (w.left, w.top, w.right, w.bottom),
                      "tela": (m.left, m.top, m.right, m.bottom),
                      "principal": bool(info.dwFlags & 1)})
        return True

    _u32.EnumDisplayMonitors(None, None, _MONENUMPROC(cb), 0)
    lista.sort(key=lambda m: (m["tela"][0], m["tela"][1]))
    for i, m in enumerate(lista):
        m["indice"] = i + 1
    return lista


def _monitor_de(ret) -> int:
    cx, cy = (ret[0] + ret[2]) // 2, (ret[1] + ret[3]) // 2
    for m in monitores():
        l, t, r, b = m["tela"]
        if l <= cx < r and t <= cy < b:
            return m["indice"]
    return 1


def _focar_windows(hwnd) -> bool:
    if _u32.IsIconic(hwnd):
        _u32.ShowWindow(hwnd, _SW_RESTORE)
    # O Windows só deixa trazer para a frente quem recebeu a última entrada;
    # um ALT "fantasma" destrava isso, o mesmo truque que o appidentity usa.
    _u32.keybd_event(0x12, 0, 0, 0)
    _u32.keybd_event(0x12, 0, 2, 0)
    ok = bool(_u32.SetForegroundWindow(hwnd))
    _u32.BringWindowToTop(hwnd)
    return ok


def _mover(hwnd, x, y, w, h) -> None:
    if _u32.IsZoomed(hwnd) or _u32.IsIconic(hwnd):
        _u32.ShowWindow(hwnd, _SW_RESTORE)
    _u32.MoveWindow(hwnd, int(x), int(y), int(w), int(h), True)


# ── Linux (wmctrl/xdotool) ─────────────────────────────────────────────────────
def _lista_linux() -> list[dict]:
    if not tem("wmctrl"):
        return []
    _c, out = rodar(["wmctrl", "-l", "-p", "-G"], timeout=5)
    janelas = []
    for linha in out.splitlines():
        partes = linha.split(None, 8)
        if len(partes) < 9 or partes[1] == "-1":
            continue
        hid, _desk, pid, x, y, w, h, _host, titulo = partes
        try:
            nome = psutil.Process(int(pid)).name()
        except Exception:
            nome = "?"
        janelas.append({"id": hid, "titulo": titulo, "pid": int(pid), "processo": nome,
                        "minimizada": False, "maximizada": False, "no_topo": False,
                        "ret": (int(x), int(y), int(x) + int(w), int(y) + int(h))})
    return janelas


# ── API ────────────────────────────────────────────────────────────────────────
def listar() -> list[dict]:
    try:
        if WIN:
            return _lista_windows()
        if LINUX:
            return _lista_linux()
        if MAC:
            _c, out = rodar(["osascript", "-e",
                             'tell application "System Events" to get name of every '
                             'process whose visible is true'], timeout=6)
            return [{"id": n.strip(), "titulo": n.strip(), "pid": 0, "processo": n.strip(),
                     "minimizada": False, "maximizada": False, "no_topo": False, "ret": (0, 0, 0, 0)}
                    for n in out.split(",") if n.strip()]
    except Exception as e:
        print(f"[Janelas] listar: {e}")
    return []


def ativa() -> dict | None:
    if WIN:
        h = _u32.GetForegroundWindow()
        if not h:
            return None
        for j in listar():
            if j["id"] == int(h):
                return j
        return {"id": int(h), "titulo": _titulo(h), "pid": 0, "processo": "?",
                "minimizada": False, "maximizada": bool(_u32.IsZoomed(h)), "no_topo": False,
                "ret": (0, 0, 0, 0)} if h else None
    if LINUX and tem("xdotool"):
        _c, hid = rodar(["xdotool", "getactivewindow"], timeout=3)
        try:
            alvo = f"0x{int(hid.strip()):08x}"
        except ValueError:
            return None
        return next((j for j in listar() if j["id"] == alvo), None)
    return None


def achar(texto: str) -> dict | None:
    """Pela palavra do título ou pelo nome do processo. '' ou 'ativa' = a da frente."""
    t = normalizar(texto)
    if not t or t in ("ativa", "atual", "essa", "esta", "janela", "janela atual"):
        return ativa()
    melhor, pontos = None, 0
    for j in listar():
        p = max(pontuar(texto, j["titulo"]), pontuar(texto, j["processo"].rsplit(".", 1)[0]))
        if t in normalizar(j["titulo"]):
            p = max(p, 85)
        if p > pontos:
            melhor, pontos = j, p
    return melhor if pontos >= 60 else None


def focar(j: dict) -> bool:
    if WIN:
        return _focar_windows(j["id"])
    if LINUX and tem("wmctrl"):
        return rodar(["wmctrl", "-i", "-a", str(j["id"])])[0] == 0
    if MAC:
        return rodar(["osascript", "-e", f'tell application "{j["processo"]}" to activate'])[0] == 0
    return False


def estado(j: dict, acao: str) -> str:
    """acao: minimizar | maximizar | restaurar | fechar."""
    if WIN:
        h = j["id"]
        if acao == "fechar":
            _u32.PostMessageW(h, _WM_CLOSE, 0, 0)
        else:
            _u32.ShowWindow(h, {"minimizar": _SW_MINIMIZE, "maximizar": _SW_MAXIMIZE,
                                "restaurar": _SW_RESTORE}[acao])
        return ""
    if LINUX:
        if acao == "fechar" and tem("wmctrl"):
            rodar(["wmctrl", "-i", "-c", str(j["id"])])
        elif acao == "minimizar" and tem("xdotool"):
            rodar(["xdotool", "windowminimize", str(int(str(j["id"]), 16))])
        elif acao in ("maximizar", "restaurar") and tem("wmctrl"):
            modo = "add" if acao == "maximizar" else "remove"
            rodar(["wmctrl", "-i", "-r", str(j["id"]), "-b", f"{modo},maximized_vert,maximized_horz"])
        else:
            return "Instale o wmctrl e o xdotool para eu controlar janelas no Linux."
        return ""
    if MAC and acao == "minimizar":
        rodar(["osascript", "-e", 'tell application "System Events" to set visible of process '
                                  f'"{j["processo"]}" to false'])
        return ""
    return NAO_DISPONIVEL


def sempre_no_topo(j: dict, ligar: bool) -> str:
    if WIN:
        _u32.SetWindowPos(j["id"], ctypes.c_void_p(_HWND_TOPMOST if ligar else _HWND_NOTOPMOST), 0, 0, 0, 0,
                          _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW)
        return ""
    if LINUX and tem("wmctrl"):
        rodar(["wmctrl", "-i", "-r", str(j["id"]), "-b", f"{'add' if ligar else 'remove'},above"])
        return ""
    return NAO_DISPONIVEL


def mover_para_monitor(j: dict, destino) -> str:
    if not WIN:
        return NAO_DISPONIVEL
    mons = monitores()
    if len(mons) < 2:
        return "Só encontrei um monitor."
    atual = _monitor_de(j["ret"])
    if str(destino).lower() in ("", "proximo", "próximo", "outro", "seguinte"):
        alvo = atual % len(mons) + 1
    else:
        try:
            alvo = int(float(destino))
        except (TypeError, ValueError):
            return "Diga o número do monitor."
        if not 1 <= alvo <= len(mons):
            return f"Existem só {len(mons)} monitores."
    estava_max = bool(_u32.IsZoomed(j["id"]))
    origem, dest = mons[atual - 1]["area"], mons[alvo - 1]["area"]
    l, t, r, b = j["ret"]
    w = min(r - l, dest[2] - dest[0])
    h = min(b - t, dest[3] - dest[1])
    x = dest[0] + max(0, l - origem[0])
    y = dest[1] + max(0, t - origem[1])
    x = min(x, dest[2] - w)
    y = min(y, dest[3] - h)
    _mover(j["id"], x, y, w, h)
    if estava_max:
        _u32.ShowWindow(j["id"], _SW_MAXIMIZE)
    return ""


def lado_a_lado(esq: dict, dir_: dict | None) -> str:
    if not WIN:
        return NAO_DISPONIVEL
    mons = monitores()
    area = mons[_monitor_de(esq["ret"]) - 1]["area"] if mons else (0, 0, 1920, 1040)
    l, t, r, b = area
    meio = (l + r) // 2
    _mover(esq["id"], l, t, meio - l, b - t)
    if dir_:
        _mover(dir_["id"], meio, t, r - meio, b - t)
    return ""


def minimizar_tudo(desfazer_: bool = False) -> str:
    if WIN:
        metodo = "UndoMinimizeALL" if desfazer_ else "MinimizeAll"
        c, out = powershell(f"(New-Object -ComObject Shell.Application).{metodo}()", timeout=10)
        return "" if c == 0 else f"Falhou: {out[:120]}"
    if LINUX and tem("wmctrl"):
        rodar(["wmctrl", "-k", "off" if desfazer_ else "on"])
        return ""
    if MAC:
        rodar(["osascript", "-e", 'tell application "System Events" to key code 103 using {command down}'])
        return ""
    return NAO_DISPONIVEL


def esperar_janela(texto: str, segundos: float = 10) -> dict | None:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        j = achar(texto)
        if j:
            return j
        time.sleep(0.5)
    return None
