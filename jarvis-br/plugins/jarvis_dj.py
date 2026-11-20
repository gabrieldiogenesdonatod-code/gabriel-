"""
JARVIS DJ (fork PT-BR 1.9): entre as músicas, ele comenta como locutor de rádio.

    "Jarvis, liga o modo DJ"       "Jarvis, desliga o modo DJ"
    "Jarvis, comenta só a cada 3 músicas"

Quando a música muda (Spotify, YouTube/YouTube Music no navegador ou qualquer
player que apareça nos controles de mídia do Windows), ele fala o nome do
artista e da música, a hora e uma curiosidade que tenha certeza de que é
verdade. Por padrão abaixa o volume enquanto fala e volta depois.
"""

from __future__ import annotations

import threading
import time

from plugins._comum import cfg, falar, salvar_cfg

PLUGIN = {
    "name": "jarvis_dj",
    "brief": "Radio-host mode: between songs JARVIS announces artist and title, the time and a true fun fact.",
    "description": ("DJ mode: when the playing song changes (Spotify, YouTube in the browser, Windows media controls) "
                    "JARVIS speaks like a radio host. action='ligar' | 'desligar' | 'status' | 'frequencia' with "
                    "a_cada (comment every N songs)."),
    "parameters": {"type": "OBJECT",
                   "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status | frequencia"},
                                  "a_cada": {"type": "INTEGER"}},
                   "required": []},
}

PLUGIN_SETTINGS = {
    "namespace": "jarvis_dj",
    "title": "JARVIS DJ",
    "fields": [
        {"key": "a_cada", "label": "Comentar a cada quantas músicas", "type": "text", "default": "1"},
        {"key": "abaixar", "label": "Abaixar a música enquanto ele fala", "type": "toggle", "default": True},
        {"key": "ligar_ao_abrir", "label": "Ligar o modo DJ quando o JARVIS abrir", "type": "toggle", "default": False},
    ],
}

_estado = {"thread": None, "faixa": "", "contador": 0, "ultima_fala": ""}
_parar = threading.Event()
_iniciou = threading.Event()


class Detector:
    """Avisa quando a faixa muda de verdade (ignora piscadas e anúncios curtos) (puro, nos testes)."""

    ESTAVEL_S = 6

    def __init__(self, a_cada: int = 1):
        self.a_cada = max(1, a_cada)
        self.atual, self.candidata, self.desde = "", "", 0.0
        self.contador = 0

    def ver(self, faixa: str, t: float) -> str:
        faixa = (faixa or "").strip()
        if not faixa or faixa == self.atual:
            self.candidata = ""
            return ""
        if faixa != self.candidata:
            self.candidata, self.desde = faixa, t
            return ""
        if t - self.desde < self.ESTAVEL_S:
            return ""
        primeira = not self.atual
        self.atual, self.candidata = faixa, ""
        if primeira:
            return ""                                           # a que já estava tocando quando ligou: não anuncia
        self.contador += 1
        return faixa if self.contador % self.a_cada == 0 else ""


def instrucao(faixa: str, hora: str) -> str:
    return (f"[DJ] Você é o locutor de rádio do usuário. Começou a tocar: {faixa}. Em NO MÁXIMO duas frases curtas e "
            f"animadas, anuncie o artista e a música, diga que são {hora} e, só se tiver CERTEZA de que é verdade, uma "
            "curiosidade sobre o artista ou a música (se não souber, não invente). Não chame nenhuma ferramenta.")


def _abaixar_e_voltar(segundos: float = 9) -> None:
    """Abaixa só os OUTROS apps (a música), não a voz do JARVIS, e devolve depois."""
    # Fork PT-BR 2.8.3: tudo pela thread única do COM; aqui só ficam PIDs e números (guardar o objeto
    # COM nesta thread fazia ele ser solto depois na thread da janela → access violation).
    try:
        from plugins.controle_audio_video import abaixar_outros, restaurar_volumes
        mexidas = abaixar_outros(0.35)
    except Exception:
        return
    time.sleep(segundos)
    restaurar_volumes(mexidas)


def _laco(player) -> None:
    from plugins import _midia
    c = cfg("jarvis_dj", PLUGIN_SETTINGS)
    try:
        a_cada = int(str(c.get("a_cada") or 1))
    except ValueError:
        a_cada = 1
    det = Detector(a_cada)
    while not _parar.is_set():
        try:
            nova = det.ver(_midia.faixa_atual(), time.monotonic())
            if det.atual and det.atual != _estado["faixa"]:
                try:                                           # 2.0: o que toca entra no perfil de gosto
                    from plugins import _gosto
                    _gosto.registrar("musica", det.atual, "tocou")
                except Exception:
                    pass
            _estado["faixa"] = det.atual
            if nova:
                if cfg("jarvis_dj", PLUGIN_SETTINGS).get("abaixar", True):
                    threading.Thread(target=_abaixar_e_voltar, daemon=True).start()
                falar(player, instrucao(nova, time.strftime("%H:%M")))
                _estado["ultima_fala"] = f"{time.strftime('%H:%M')} {nova}"
        except Exception as e:
            print(f"[DJ] {e}")
        time.sleep(3)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    t = _estado["thread"]
    ativo = t is not None and t.is_alive()
    if acao == "ligar":
        if ativo:
            return "O modo DJ já está ligado."
        _parar.clear()
        _estado["thread"] = threading.Thread(target=_laco, args=(player,), daemon=True, name="jarvis_dj")
        _estado["thread"].start()
        return "Modo DJ ligado. Na próxima música, eu entro no ar."
    if acao == "desligar":
        _parar.set()
        return "Modo DJ desligado."
    if acao == "frequencia":
        n = max(1, int(p.get("a_cada") or 1))
        salvar_cfg("jarvis_dj", {"a_cada": str(n)})
        if ativo:
            _parar.set()
            t.join(timeout=5)
            _parar.clear()
            _estado["thread"] = threading.Thread(target=_laco, args=(player,), daemon=True, name="jarvis_dj")
            _estado["thread"].start()
        return f"Vou comentar a cada {n} música{'s' if n > 1 else ''}."
    txt = "Modo DJ ligado." if ativo else "Modo DJ desligado."
    if _estado["faixa"]:
        txt += f" Tocando: {_estado['faixa']}."
    return txt


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if cfg("jarvis_dj", PLUGIN_SETTINGS).get("ligar_ao_abrir"):
        run({"action": "ligar"}, player)
