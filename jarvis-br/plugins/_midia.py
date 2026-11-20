"""
Mídia do PC para os plugins da 1.9 (gestos, pausa quando sai, JARVIS DJ). Começa com "_": não é ferramenta.

  tecla(nome)        teclas de mídia do Windows: play_pause, proxima, anterior, parar
  alt_tab(voltar)    troca de janela (como Alt+Tab)
  tocando()          algum som está saindo agora? (medidor de pico do Windows, pycaw)
  faixa_atual()      "Artista - Música" do que está tocando (sessão de mídia do Windows
                     se o pacote winrt existir; senão, o título da janela do Spotify / YouTube)
"""

from __future__ import annotations

import re
import time

from plugins._comum import LINUX, WIN, rodar, tem

VK = {"play_pause": 0xB3, "proxima": 0xB0, "anterior": 0xB1, "parar": 0xB2}
_XDO = {"play_pause": "XF86AudioPlay", "proxima": "XF86AudioNext", "anterior": "XF86AudioPrev", "parar": "XF86AudioStop"}


def tecla(nome: str) -> bool:
    if WIN:
        try:
            import ctypes
            u32 = ctypes.windll.user32
            vk = VK[nome]
            u32.keybd_event(vk, 0, 1, 0)                        # KEYEVENTF_EXTENDEDKEY
            u32.keybd_event(vk, 0, 1 | 2, 0)                    # + KEYEVENTF_KEYUP
            return True
        except Exception:
            return False
    if LINUX and tem("xdotool"):
        return rodar(["xdotool", "key", _XDO[nome]], timeout=3)[0] == 0
    return False


def alt_tab(voltar: bool = False) -> bool:
    if WIN:
        try:
            import ctypes
            u32 = ctypes.windll.user32
            ALT, SHIFT, TAB, UP = 0x12, 0x10, 0x09, 2
            u32.keybd_event(ALT, 0, 0, 0)
            if voltar:
                u32.keybd_event(SHIFT, 0, 0, 0)
            u32.keybd_event(TAB, 0, 0, 0)
            u32.keybd_event(TAB, 0, UP, 0)
            if voltar:
                u32.keybd_event(SHIFT, 0, UP, 0)
            time.sleep(0.05)
            u32.keybd_event(ALT, 0, UP, 0)
            return True
        except Exception:
            return False
    if LINUX and tem("xdotool"):
        return rodar(["xdotool", "key", "alt+shift+Tab" if voltar else "alt+Tab"], timeout=3)[0] == 0
    return False


def pico() -> float | None:
    """0..1 do que está saindo no alto-falante agora (None se não dá para medir).
    Fork PT-BR 2.8.3: roda na thread única do COM (core/com_unico.py) — o objeto COM criado aqui em
    várias threads era solto depois na thread da janela e derrubava o JARVIS (access violation)."""
    if not WIN:
        return None
    try:
        from core import com_unico
        return com_unico.executar(_pico_com, timeout=5.0)
    except Exception:
        return None


def _pico_com() -> float | None:
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        alto = AudioUtilities.GetSpeakers()
        dev = getattr(alto, "_dev", alto)
        interface = dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        return float(cast(interface, POINTER(IAudioMeterInformation)).GetPeakValue())
    except Exception:
        return None


def tocando(amostras: int = 6, intervalo: float = 0.12, limite: float = 0.01) -> bool | None:
    """True se houve som em mais da metade das amostras (≈0,7 s)."""
    vals = []
    for _ in range(amostras):
        v = pico()
        if v is None:
            return None
        vals.append(v)
        time.sleep(intervalo)
    return sum(v > limite for v in vals) > amostras // 2


# ── o que está tocando ───────────────────────────────────────────────────────
_RE_YT = re.compile(r"^(?:\(\d+\)\s*)?(.+?) - YouTube(?: Music)?(?: — | - |$)")


def faixa_do_titulo(titulo: str, processo: str = "") -> str:
    """Título de janela → 'Artista - Música' (pura). '' se não parece música."""
    t = (titulo or "").strip()
    p = (processo or "").lower()
    if not t:
        return ""
    if "spotify" in p:
        return "" if t.lower() in ("spotify", "spotify premium", "spotify free") else t
    m = _RE_YT.match(t)
    if m:
        return m.group(1).strip()
    return ""


def _faixa_winrt() -> str:
    try:
        import asyncio

        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Gerente
    except Exception:
        return ""

    async def ler():
        g = await Gerente.request_async()
        s = g.get_current_session()
        if s is None:
            return ""
        info = await s.try_get_media_properties_async()
        artista, titulo = (info.artist or "").strip(), (info.title or "").strip()
        return f"{artista} - {titulo}" if artista and titulo else titulo
    try:
        return asyncio.run(ler())
    except Exception:
        return ""


def faixa_atual() -> str:
    f = _faixa_winrt()
    if f:
        return f
    try:
        from plugins._janelas import listar
        for j in listar():
            f = faixa_do_titulo(j.get("titulo", ""), j.get("processo", ""))
            if f:
                return f
    except Exception:
        pass
    return ""
