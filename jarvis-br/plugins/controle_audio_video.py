"""
Som e vídeo — plugin do J.A.R.V.I.S BR.

SOM     volume geral (número, "mais", "menos"), mudo explícito, volume POR
        APLICATIVO (Windows com pycaw; Linux com pactl), listar e trocar o
        dispositivo de saída (fone ↔ caixa de som).
VÍDEO   brilho, modo escuro (ligar/desligar de verdade, não só alternar), luz
        noturna, resolução (com volta automática em 20 s se você não
        confirmar, como o próprio Windows faz) e monitor principal.

Reaproveita volume_get/volume_set/brightness_get/brightness_set do
actions/computer_settings.py, para haver um jeito só de mexer nisso.
Tudo que é reversível registra desfazer.
"""

from __future__ import annotations

import ctypes
import re
import threading

from plugins._comum import (LINUX, MAC, NAO_DISPONIVEL, WIN, abrir_no_sistema,
                            desfazer, mostrar, num, rodar, sim, tem)
from plugins._indice_apps import normalizar, pontuar

PLUGIN = {
    "name": "controle_audio_video",
    "brief": "Volume (global/per app), mute, output device, brightness, dark mode, night light, resolution.",
    "description": (
        "Sound and display control. action='volume' (nivel=0-100 or 'mais'/'menos'), "
        "'mudo' (ligar=sim|nao, empty toggles), 'volume_app' (app, nivel) for one "
        "program's volume, 'apps_audio' to list programs playing sound, 'saidas' to "
        "list output devices, 'trocar_saida' (dispositivo=name, e.g. fone, caixa, "
        "HDMI), 'brilho' (nivel or mais/menos), 'modo_escuro' (ligar=sim|nao), "
        "'luz_noturna' (ligar=sim|nao), 'resolucao' (largura, altura; empty lists "
        "modes), 'manter_resolucao' to keep a new resolution, 'monitor_principal'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "nivel": {"type": "STRING", "description": "0-100, 'mais' or 'menos'"},
            "app": {"type": "STRING", "description": "volume_app: program name"},
            "ligar": {"type": "STRING", "description": "sim | nao"},
            "dispositivo": {"type": "STRING", "description": "trocar_saida: device name"},
            "largura": {"type": "NUMBER"}, "altura": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}


def _cs():
    from actions import computer_settings
    return computer_settings


def _na_com(fn):
    """Fork PT-BR 2.8.3: pycaw/COM sempre na thread única do COM (core/com_unico.py)."""
    from core import com_unico
    return com_unico.na_com(fn)


def _co_init():
    """COM precisa ser iniciado em cada thread que usa pycaw/comtypes.
    Fork PT-BR 2.8.3: na thread única do COM ele já está ligado; fora dela, nada de ligar outro."""
    from core import com_unico
    if com_unico.na_thread_com():
        return
    if WIN:
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass


def nivel_alvo(pedido, atual: int | None, passo: int = 10) -> int | None:
    """'mais' → atual+10; 'menos' → atual−10; '35' → 35. None se não entendeu."""
    t = str(pedido or "").strip().lower()
    if t in ("mais", "aumentar", "aumenta", "sobe", "+"):
        return min(100, (atual if atual is not None else 50) + passo)
    if t in ("menos", "diminuir", "diminui", "abaixa", "-"):
        return max(0, (atual if atual is not None else 50) - passo)
    if t in ("max", "máximo", "maximo", "tudo"):
        return 100
    v = num(t, -1)
    return int(max(0, min(100, v))) if v >= 0 else None


# ── volume geral e mudo ────────────────────────────────────────────────────────
@_na_com
def _volume(nivel) -> str:
    cs = _cs()
    _co_init()
    antes = cs.volume_get()
    alvo = nivel_alvo(nivel, antes)
    if alvo is None:
        return "Diga um volume de 0 a 100, ou mais/menos."
    try:
        cs.volume_set(alvo)
    except FileNotFoundError:
        return ("Não encontrei o controle de volume deste sistema "
                "(no Linux, instale o pulseaudio-utils, que traz o pactl).")
    if antes is not None:
        desfazer(f"volume {antes}% → {alvo}%", lambda b=antes: (cs.volume_set(b), f"Volume em {b}%.")[1])
    return f"Volume em {alvo}%."


@_na_com
def _definir_mudo(ligado: bool) -> None:
    _cs()._win_endpoint_volume().SetMute(int(bool(ligado)), None)


@_na_com
def _volume_por_pid(pid: int, nivel: int) -> bool:
    """Volume de um app pelo PID (0-100). Sem guardar objeto COM fora daqui."""
    from pycaw.pycaw import AudioUtilities
    for s in AudioUtilities.GetAllSessions():
        if s.Process is not None and s.Process.pid == pid:
            s.SimpleAudioVolume.SetMasterVolume(max(0, min(100, nivel)) / 100.0, None)
            return True
    return False


@_na_com
def abaixar_outros(fator: float = 0.35, pular=("python", "jarvis")) -> list[tuple[int, int]]:
    """Abaixa o som dos outros apps; devolve [(pid, volume antes)] para restaurar_volumes()."""
    mexidas = []
    for s in _sessoes_windows():
        if s["nome"].lower().startswith(tuple(pular)):
            continue
        s["obj"].SetMasterVolume(s["volume"] / 100.0 * fator, None)
        mexidas.append((s["pid"], s["volume"]))
    return mexidas


def restaurar_volumes(mexidas) -> None:
    for pid, antes in mexidas or []:
        try:
            _volume_por_pid(pid, antes)
        except Exception:
            pass


@_na_com
def _mudo(ligar) -> str:
    _co_init()
    modo = None if ligar in (None, "") else sim(ligar)
    if WIN:
        try:
            ep = _cs()._win_endpoint_volume()
            atual = bool(ep.GetMute())
            novo = (not atual) if modo is None else modo
            ep.SetMute(int(novo), None)
            # 2.8.3: o desfazer não guarda o objeto COM (ele seria solto em outra thread e derrubava o JARVIS)
            desfazer("mudo", lambda a=atual: (_definir_mudo(a), "Som como estava.")[1])
            return "Som mudo." if novo else "Som ligado."
        except Exception as e:
            return f"Não consegui mexer no mudo: {e}"
    if MAC:
        estado = "true" if modo in (None, True) else "false"
        rodar(["osascript", "-e", f"set volume output muted {estado}"])
        return "Som mudo." if estado == "true" else "Som ligado."
    valor = "toggle" if modo is None else ("1" if modo else "0")
    c, out = rodar(["pactl", "set-sink-mute", "@DEFAULT_SINK@", valor])
    return ("Pronto." if c == 0 else f"Não consegui: {out[:80]}")


# ── volume por aplicativo ───────────────────────────────────────────────────────
@_na_com
def _sessoes_windows():
    _co_init()
    from pycaw.pycaw import AudioUtilities
    out = []
    for s in AudioUtilities.GetAllSessions():
        if s.Process is None:
            continue
        try:
            vol = s.SimpleAudioVolume
            out.append({"nome": s.Process.name(), "pid": s.Process.pid,
                        "volume": round(vol.GetMasterVolume() * 100), "obj": vol})
        except Exception:
            continue
    return out


def _sessoes_linux():
    c, out = rodar(["pactl", "list", "sink-inputs"], timeout=6)
    if c != 0:
        return []
    sessoes, atual = [], None
    for linha in out.splitlines():
        m = re.match(r"\S.*#(\d+)", linha)
        if m:
            atual = {"indice": m.group(1), "nome": "?", "volume": None}
            sessoes.append(atual)
            continue
        if atual is None:
            continue
        if "application.name" in linha or "application.process.binary" in linha:
            nome = linha.split("=", 1)[-1].strip().strip('"')
            if atual["nome"] == "?" or "binary" in linha:
                atual["nome"] = nome
        mv = re.search(r"Volume:.*?(\d+)%", linha)
        if mv and atual["volume"] is None:
            atual["volume"] = int(mv.group(1))
    return sessoes


@_na_com
def _apps_audio(player) -> str:
    try:
        sessoes = _sessoes_windows() if WIN else _sessoes_linux() if LINUX else None
    except ImportError:
        return "Preciso do pycaw para isso: pip install pycaw"
    except Exception as e:
        return f"Não consegui listar: {e}"
    if sessoes is None:
        return NAO_DISPONIVEL
    if not sessoes:
        return "Nenhum programa está usando o som agora."
    mostrar(player, "PROGRAMAS COM SOM", "\n".join(f"{s['nome']:<30} {s['volume']}%" for s in sessoes))
    return "Com som: " + ", ".join(f"{s['nome'].rsplit('.', 1)[0]} ({s['volume']}%)" for s in sessoes) + "."


@_na_com
def _volume_app(app: str, nivel) -> str:
    if not app:
        return "De qual programa?"
    try:
        sessoes = _sessoes_windows() if WIN else _sessoes_linux() if LINUX else None
    except ImportError:
        return "Preciso do pycaw para isso: pip install pycaw"
    if sessoes is None:
        return NAO_DISPONIVEL
    alvo = [s for s in sessoes if pontuar(app, s["nome"].rsplit(".", 1)[0]) >= 70
            or normalizar(app) in normalizar(s["nome"])]
    if not alvo:
        return f"{app} não está tocando nada agora (o Windows só lista quem já usou o som)."
    novo = nivel_alvo(nivel, alvo[0]["volume"])
    if novo is None:
        return "Diga um volume de 0 a 100, ou mais/menos."
    for s in alvo:
        antes = s["volume"]
        if WIN:
            s["obj"].SetMasterVolume(novo / 100.0, None)
            desfazer(f"volume de {s['nome']}",                   # 2.8.3: pelo PID, sem guardar o objeto COM
                     lambda p=s["pid"], a=antes: (_volume_por_pid(p, a), "Volume do app restaurado.")[1])
        else:
            rodar(["pactl", "set-sink-input-volume", s["indice"], f"{novo}%"])
            desfazer(f"volume de {s['nome']}",
                     lambda i=s["indice"], a=antes: (rodar(["pactl", "set-sink-input-volume", i, f"{a}%"]),
                                                     "Volume do app restaurado.")[1])
    return f"Volume de {alvo[0]['nome'].rsplit('.', 1)[0]} em {novo}%."


# ── dispositivo de saída ────────────────────────────────────────────────────────
@_na_com
def _saidas_windows() -> list[dict]:
    _co_init()
    from pycaw.pycaw import AudioUtilities
    saidas = []
    padrao = ""
    try:
        padrao = AudioUtilities.GetSpeakers().id
    except Exception:
        pass
    try:
        dispositivos = AudioUtilities.GetAllDevices()
    except Exception:
        dispositivos = []
    for d in dispositivos:
        did = str(getattr(d, "id", "") or "")
        estado = str(getattr(d, "state", ""))
        # IDs de saída começam com {0.0.0.…}; de entrada (microfone) com {0.0.1.…}.
        if not did.startswith("{0.0.0.") or ("Active" not in estado and estado not in ("1", "AudioDeviceState.Active")):
            continue
        saidas.append({"id": did, "nome": d.FriendlyName or did, "padrao": did == padrao})
    return saidas


@_na_com
def _definir_padrao_windows(device_id: str) -> None:
    """IPolicyConfig: a interface (não documentada, mas estável desde o
    Windows 7) que o próprio painel de som usa para trocar a saída padrão."""
    _co_init()
    from ctypes import POINTER, c_int, c_longlong, c_void_p
    from ctypes.wintypes import LPCWSTR

    from comtypes import CLSCTX_ALL, COMMETHOD, GUID, HRESULT, IUnknown, CoCreateInstance

    class IPolicyConfig(IUnknown):
        _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
        # A ordem dos métodos é o que importa (é a vtable); só o último usado
        # precisa da assinatura exata.
        _methods_ = [
            COMMETHOD([], HRESULT, "GetMixFormat", (["in"], LPCWSTR), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "GetDeviceFormat", (["in"], LPCWSTR), (["in"], c_int), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "ResetDeviceFormat", (["in"], LPCWSTR)),
            COMMETHOD([], HRESULT, "SetDeviceFormat", (["in"], LPCWSTR), (["in"], c_void_p), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "GetProcessingPeriod", (["in"], LPCWSTR), (["in"], c_int),
                      (["in"], POINTER(c_longlong)), (["in"], POINTER(c_longlong))),
            COMMETHOD([], HRESULT, "SetProcessingPeriod", (["in"], LPCWSTR), (["in"], POINTER(c_longlong))),
            COMMETHOD([], HRESULT, "GetShareMode", (["in"], LPCWSTR), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "SetShareMode", (["in"], LPCWSTR), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "GetPropertyValue", (["in"], LPCWSTR), (["in"], c_void_p), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "SetPropertyValue", (["in"], LPCWSTR), (["in"], c_void_p), (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], LPCWSTR), (["in"], c_int)),
            COMMETHOD([], HRESULT, "SetEndpointVisibility", (["in"], LPCWSTR), (["in"], c_int)),
        ]

    cliente = CoCreateInstance(GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}"), IPolicyConfig, CLSCTX_ALL)
    for papel in (0, 1, 2):               # console, multimídia, comunicação
        cliente.SetDefaultEndpoint(device_id, papel)


def _saidas_linux() -> list[dict]:
    _c, padrao = rodar(["pactl", "get-default-sink"], timeout=5)
    c, out = rodar(["pactl", "list", "sinks"], timeout=6)
    if c != 0:
        return []
    saidas, atual = [], None
    for linha in out.splitlines():
        if linha.strip().startswith("Name:") or linha.strip().startswith("Nome:"):
            atual = {"id": linha.split(":", 1)[1].strip(), "nome": "", "padrao": False}
            atual["padrao"] = atual["id"] == padrao.strip()
            saidas.append(atual)
        elif atual and (linha.strip().startswith("Description:") or linha.strip().startswith("Descrição:")):
            atual["nome"] = linha.split(":", 1)[1].strip()
    return saidas


def _listar_saidas() -> list[dict]:
    if WIN:
        return _saidas_windows()
    if LINUX and tem("pactl"):
        return _saidas_linux()
    if MAC and tem("SwitchAudioSource"):
        _c, atual = rodar(["SwitchAudioSource", "-c"])
        _c, out = rodar(["SwitchAudioSource", "-a", "-t", "output"])
        return [{"id": n.strip(), "nome": n.strip(), "padrao": n.strip() == atual.strip()}
                for n in out.splitlines() if n.strip()]
    return []


def _saidas(player) -> str:
    try:
        s = _listar_saidas()
    except ImportError:
        return "Preciso do pycaw e do comtypes: pip install pycaw comtypes"
    if not s:
        return "Não encontrei dispositivos de saída (ou este sistema não permite listar)."
    mostrar(player, "SAÍDAS DE SOM", "\n".join(f"{'▶' if d['padrao'] else ' '} {d['nome']}" for d in s))
    atual = next((d["nome"] for d in s if d["padrao"]), "?")
    return f"Saída atual: {atual}. Disponíveis: " + ", ".join(d["nome"] for d in s) + "."


_SINONIMOS_SAIDA = {"fone": ["fone", "headphone", "headset", "auricular", "earphone", "fones"],
                    "caixa": ["alto-falante", "alto falante", "speaker", "caixa", "speakers", "realtek"],
                    "hdmi": ["hdmi", "tv", "monitor", "display"],
                    "bluetooth": ["bluetooth", "buds", "airpods", "jbl"]}


def escolher_saida(pedido: str, saidas: list[dict]) -> dict | None:
    q = normalizar(pedido)
    melhor, pontos = None, 0
    for d in saidas:
        n = normalizar(d["nome"])
        p = pontuar(pedido, d["nome"])
        for chave, termos in _SINONIMOS_SAIDA.items():
            if chave in q and any(normalizar(t) in n for t in termos):
                p = max(p, 85)
        if q and q in n:
            p = max(p, 80)
        if p > pontos:
            melhor, pontos = d, p
    return melhor if pontos >= 55 else None


def _trocar_saida(pedido: str) -> str:
    try:
        saidas = _listar_saidas()
    except ImportError:
        return "Preciso do pycaw e do comtypes: pip install pycaw comtypes"
    if not saidas:
        return NAO_DISPONIVEL if MAC else "Não encontrei dispositivos de saída."
    d = escolher_saida(pedido, saidas)
    if not d:
        return f"Não achei uma saída parecida com {pedido}. Tenho: " + ", ".join(x["nome"] for x in saidas) + "."
    anterior = next((x for x in saidas if x["padrao"]), None)
    try:
        if WIN:
            _definir_padrao_windows(d["id"])
        elif LINUX:
            rodar(["pactl", "set-default-sink", d["id"]])
        else:
            rodar(["SwitchAudioSource", "-s", d["id"]])
    except Exception as e:
        return f"Não consegui trocar a saída: {e}"
    if anterior and anterior["id"] != d["id"]:
        desfazer(f"saída de som → {d['nome']}", lambda a=anterior: (_trocar_saida(a["nome"]), "")[1])
    return f"Som saindo agora em {d['nome']}."


# ── brilho, modo escuro, luz noturna ────────────────────────────────────────────
def _brilho(nivel) -> str:
    cs = _cs()
    antes = cs.brightness_get()
    alvo = nivel_alvo(nivel, antes)
    if alvo is None:
        return "Diga um brilho de 0 a 100, ou mais/menos."
    if MAC:
        return "No Mac, use as teclas de brilho; o sistema não deixa programas mudarem direto."
    cs.brightness_set(alvo)
    depois = cs.brightness_get()
    if antes is not None:
        desfazer(f"brilho {antes}% → {alvo}%", lambda b=antes: (cs.brightness_set(b), f"Brilho em {b}%.")[1])
    if depois is None:
        return (f"Pedi brilho de {alvo}%, mas este monitor não informa o brilho (monitores externos "
                "geralmente só mudam pelos botões deles).")
    return f"Brilho em {depois}%."


def _modo_escuro_atual() -> bool | None:
    if WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except Exception:
            return None
    if MAC:
        _c, out = rodar(["osascript", "-e", 'tell app "System Events" to tell appearance '
                                            'preferences to get dark mode'])
        return out.strip() == "true"
    _c, out = rodar(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    return "dark" in out


def _definir_modo_escuro(escuro: bool) -> None:
    if WIN:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                           0, winreg.KEY_SET_VALUE)
        for nome in ("AppsUseLightTheme", "SystemUsesLightTheme"):
            winreg.SetValueEx(k, nome, 0, winreg.REG_DWORD, 0 if escuro else 1)
        winreg.CloseKey(k)
        # Avisa as janelas abertas que o tema mudou (WM_SETTINGCHANGE).
        try:
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet",
                                                     0x0002, 2000, None)
        except Exception:
            pass
    elif MAC:
        rodar(["osascript", "-e", 'tell app "System Events" to tell appearance preferences '
                                  f'to set dark mode to {"true" if escuro else "false"}'])
    else:
        rodar(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
               "prefer-dark" if escuro else "default"])


def _modo_escuro(ligar) -> str:
    atual = _modo_escuro_atual()
    novo = (not atual if atual is not None else True) if ligar in (None, "") else sim(ligar)
    try:
        _definir_modo_escuro(novo)
    except Exception as e:
        return f"Não consegui mudar o tema: {e}"
    if atual is not None and atual != novo:
        desfazer("modo escuro", lambda a=atual: (_definir_modo_escuro(a), "Tema como estava.")[1])
    return "Modo escuro ligado." if novo else "Modo claro ligado."


def _luz_noturna(ligar) -> str:
    if LINUX and tem("gsettings"):
        chave = ["org.gnome.settings-daemon.plugins.color", "night-light-enabled"]
        _c, atual = rodar(["gsettings", "get", *chave])
        novo = (atual.strip() != "true") if ligar in (None, "") else sim(ligar)
        c, out = rodar(["gsettings", "set", *chave, "true" if novo else "false"])
        if c == 0:
            return "Luz noturna ligada." if novo else "Luz noturna desligada."
        return f"Não consegui: {out[:80]}"
    if WIN:
        abrir_no_sistema("ms-settings:nightlight")
        return ("Abri as configurações de luz noturna. O Windows não oferece um jeito oficial "
                "de programas ligarem isso direto, então o botão fica com você.")
    return NAO_DISPONIVEL


# ── resolução ─────────────────────────────────────────────────────────────────
if WIN:
    from ctypes import wintypes as _W

    class _DEVMODEW(ctypes.Structure):
        _fields_ = [("dmDeviceName", _W.WCHAR * 32), ("dmSpecVersion", _W.WORD),
                    ("dmDriverVersion", _W.WORD), ("dmSize", _W.WORD), ("dmDriverExtra", _W.WORD),
                    ("dmFields", _W.DWORD), ("dmPositionX", _W.LONG), ("dmPositionY", _W.LONG),
                    ("dmDisplayOrientation", _W.DWORD), ("dmDisplayFixedOutput", _W.DWORD),
                    ("dmColor", _W.SHORT), ("dmDuplex", _W.SHORT), ("dmYResolution", _W.SHORT),
                    ("dmTTOption", _W.SHORT), ("dmCollate", _W.SHORT), ("dmFormName", _W.WCHAR * 32),
                    ("dmLogPixels", _W.WORD), ("dmBitsPerPel", _W.DWORD), ("dmPelsWidth", _W.DWORD),
                    ("dmPelsHeight", _W.DWORD), ("dmDisplayFlags", _W.DWORD),
                    ("dmDisplayFrequency", _W.DWORD), ("dmICMMethod", _W.DWORD),
                    ("dmICMIntent", _W.DWORD), ("dmMediaType", _W.DWORD), ("dmDitherType", _W.DWORD),
                    ("dmReserved1", _W.DWORD), ("dmReserved2", _W.DWORD),
                    ("dmPanningWidth", _W.DWORD), ("dmPanningHeight", _W.DWORD)]

_volta_resolucao: dict = {}


def _modos_windows() -> tuple[tuple, list[tuple]]:
    u32 = ctypes.windll.user32
    dm = _DEVMODEW()
    dm.dmSize = ctypes.sizeof(_DEVMODEW)
    u32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))           # ENUM_CURRENT_SETTINGS
    atual = (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency)
    modos, i = set(), 0
    while True:
        m = _DEVMODEW()
        m.dmSize = ctypes.sizeof(_DEVMODEW)
        if not u32.EnumDisplaySettingsW(None, i, ctypes.byref(m)):
            break
        if m.dmBitsPerPel >= 32 and m.dmPelsWidth >= 800:
            modos.add((m.dmPelsWidth, m.dmPelsHeight, m.dmDisplayFrequency))
        i += 1
    return atual, sorted(modos, reverse=True)


def _aplicar_windows(largura: int, altura: int, freq: int | None) -> int:
    u32 = ctypes.windll.user32
    dm = _DEVMODEW()
    dm.dmSize = ctypes.sizeof(_DEVMODEW)
    u32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
    dm.dmPelsWidth, dm.dmPelsHeight = largura, altura
    dm.dmFields = 0x80000 | 0x100000                                 # largura | altura
    if freq:
        dm.dmDisplayFrequency = freq
        dm.dmFields |= 0x400000
    teste = u32.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, 0x2, None)   # CDS_TEST
    if teste != 0:
        return teste
    return u32.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, 0x1, None)    # CDS_UPDATEREGISTRY


def _resolucao(largura, altura, player) -> str:
    if LINUX and tem("xrandr"):
        _c, out = rodar(["xrandr"])
        saida = re.search(r"^(\S+) connected(?: primary)?", out, re.M)
        if not saida:
            return "Não achei o monitor no xrandr."
        if not largura:
            modos = re.findall(r"^\s+(\d+x\d+)", out, re.M)
            return "Resoluções: " + ", ".join(dict.fromkeys(modos))
        c, err = rodar(["xrandr", "--output", saida.group(1), "--mode", f"{int(num(largura))}x{int(num(altura))}"])
        return "Resolução alterada." if c == 0 else f"Não consegui: {err[:100]}"
    if not WIN:
        return NAO_DISPONIVEL
    atual, modos = _modos_windows()
    if not largura:
        mostrar(player, "RESOLUÇÕES DISPONÍVEIS", "\n".join(
            f"{'▶' if (w, h, f) == atual else ' '} {w} × {h}  {f} Hz" for w, h, f in modos))
        return f"Resolução atual: {atual[0]} × {atual[1]} a {atual[2]} Hz. A lista está no painel."
    w, h = int(num(largura)), int(num(altura))
    candidatos = [m for m in modos if m[0] == w and m[1] == h]
    if not candidatos:
        return f"Este monitor não aceita {w} × {h}. Peça a lista para ver as opções."
    freq = atual[2] if any(m[2] == atual[2] for m in candidatos) else max(m[2] for m in candidatos)
    r = _aplicar_windows(w, h, freq)
    if r != 0:
        return f"O Windows recusou essa resolução (código {r})."

    # Como o painel do Windows: se ninguém confirmar em 20 s, volta sozinho
    # (a tela pode ter ficado preta e você não ter como clicar em nada).
    def voltar():
        if _volta_resolucao.get("pendente"):
            _aplicar_windows(atual[0], atual[1], atual[2])
            _volta_resolucao.clear()

    t = threading.Timer(20, voltar)
    t.daemon = True
    _volta_resolucao.update({"pendente": True, "timer": t})
    t.start()
    desfazer(f"resolução {w}×{h}", lambda a=atual: (_aplicar_windows(*a), "Resolução de volta.")[1])
    return (f"Resolução em {w} × {h}. Diga 'manter resolução' em 20 segundos, "
            "ou eu volto para a anterior sozinho.")


def _manter_resolucao() -> str:
    if not _volta_resolucao.get("pendente"):
        return "Não há mudança de resolução esperando confirmação."
    _volta_resolucao["timer"].cancel()
    _volta_resolucao.clear()
    return "Resolução mantida."


_ACOES_COM = ("volume", "mudo", "volume_app", "apps_audio", "saidas", "trocar_saida")


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Fork PT-BR 2.8.3: as ações de som (pycaw/COM) rodam na thread única do COM (core/com_unico.py)."""
    a = str((parameters or {}).get("action") or "").strip().lower()
    if a in _ACOES_COM:
        from core import com_unico
        try:
            return com_unico.executar(_run, parameters, player, session_memory, timeout=30.0)
        except TimeoutError:
            return "O controle de som do Windows não respondeu agora; tente de novo."
    return _run(parameters, player, session_memory)


def _run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "").strip().lower()
    try:
        if a == "volume":
            return _volume(p.get("nivel"))
        if a == "mudo":
            return _mudo(p.get("ligar"))
        if a == "volume_app":
            return _volume_app(str(p.get("app") or ""), p.get("nivel"))
        if a == "apps_audio":
            return _apps_audio(player)
        if a == "saidas":
            return _saidas(player)
        if a == "trocar_saida":
            return _trocar_saida(str(p.get("dispositivo") or ""))
        if a == "brilho":
            return _brilho(p.get("nivel"))
        if a == "modo_escuro":
            return _modo_escuro(p.get("ligar"))
        if a == "luz_noturna":
            return _luz_noturna(p.get("ligar"))
        if a == "resolucao":
            return _resolucao(p.get("largura"), p.get("altura"), player)
        if a == "manter_resolucao":
            return _manter_resolucao()
        if a == "monitor_principal":
            if WIN:
                abrir_no_sistema("ms-settings:display")
                return ("Abri as configurações de vídeo: escolha o monitor e marque 'Tornar esta "
                        "a minha tela principal'. O Windows não expõe isso para programas de forma segura.")
            return NAO_DISPONIVEL
        return "Ação desconhecida para som e vídeo."
    except Exception as e:
        return f"O controle de som e vídeo falhou: {e}"
