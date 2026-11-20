"""
Música por voz: Spotify e YouTube Music (fork PT-BR 2.0).

    "Jarvis, toca Kaiser"                    "Jarvis, toca a playlist de treino"
    "Jarvis, toca Impossível no YouTube Music"
    "Jarvis, pausa" / "continua" / "próxima" / "volta a música" / "volume 40"
    "Jarvis, põe na fila Artista - Música"   "Jarvis, curti essa"
    "Jarvis, que música é essa?"             "Jarvis, me sugere uma música"
    "Jarvis, conecta o Spotify"              (uma vez; veja o passo a passo no INSTALAR.txt)

Com Spotify conectado (e Premium), ele toca e controla direto. Sem Spotify, ou
se você pedir, ele toca no YouTube Music pelo navegador. Tudo o que você pede,
curte ou pula vai para o seu perfil de gosto, que o companheiro usa para
oferecer coisas.
"""

from __future__ import annotations

import re
import time
import unicodedata
import urllib.parse

from plugins import _gosto, _spotify as S
from plugins._comum import abrir_no_sistema, cfg, mostrar

PLUGIN = {
    "name": "musica",
    "brief": "Music by voice on Spotify (Web API) and YouTube Music: play, pause, skip, queue, like, what's playing, "
             "suggestions from the user's taste.",
    "description": (
        "Music player. action='tocar' with pedido (song, artist, 'playlist X', 'álbum X'; empty = resume) + optional "
        "servico (spotify | youtube); 'pausar'; 'continuar'; 'proxima'; 'anterior'; 'volume' with nivel (0-100); "
        "'fila' with pedido; 'curtir' (like the current song); 'tocando' (what is playing); 'sugerir' (suggest from "
        "the user's taste; offer, do not auto-play); 'nao_gosto' with pedido (never suggest it); 'conectar' (connect "
        "Spotify); 'player' (opens the on-screen 'Now playing' window with cover, controls and playlists); 'dormir' "
        "with minutos (sleep timer: lowers and stops the music); 'despertador' with hora (HH:MM) + optional pedido "
        "(wake up with music, volume rising; pedido 'cancelar' removes it); 'humor' with pedido (mood/activity: "
        "focar, treino, relaxar, dormir, festa, triste, estudar…) plays a fitting playlist; 'radio' plays a station "
        "mixed from the user's taste; 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "tocar | pausar | continuar | proxima | anterior | "
                                                                    "volume | fila | curtir | tocando | sugerir | "
                                                                    "nao_gosto | conectar | player | dormir | "
                                                                    "despertador | humor | radio | status"},
                       "pedido": {"type": "STRING"}, "servico": {"type": "STRING"}, "nivel": {"type": "INTEGER"},
                       "minutos": {"type": "NUMBER"}, "hora": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "musica",
    "title": "Música (Spotify / YouTube Music)",
    "fields": [
        {"key": "client_id", "label": "Spotify Client ID (developer.spotify.com → Create app)", "type": "text",
         "default": ""},
        {"key": "preferido", "label": "Serviço preferido", "type": "choice", "options": ["spotify", "youtube"],
         "default": "spotify"},
        {"key": "abrir_player", "label": "Abrir a tela 'Tocando agora' quando eu pedir música", "type": "toggle",
         "default": True},
    ],
}

_ultima = {"faixa": "", "inicio": 0.0}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def servico_do_pedido(pedido: str, servico: str, spotify_ok: bool, preferido: str = "spotify") -> tuple[str, str]:
    """Qual serviço usar e o pedido sem 'no YouTube'/'no Spotify' (pura)."""
    t = _dobrar(pedido)
    s = _dobrar(servico)
    limpo = re.sub(r"(?i)\s*(no|pelo|na)\s+(youtube( music)?|spotify)\s*$", "", pedido).strip()
    if "youtube" in s or re.search(r"\b(no|pelo|na) youtube", t):
        return "youtube", limpo
    if "spotify" in s or re.search(r"\b(no|pelo) spotify", t):
        return "spotify", limpo
    if spotify_ok and preferido != "youtube":
        return "spotify", limpo
    return "youtube", limpo


def url_youtube_music(pedido: str) -> str:
    """Vídeo exato pelo yt-dlp (se instalado); senão, a busca do YouTube Music."""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "extract_flat": True, "noplaylist": True}) as y:
            r = y.extract_info(f"ytsearch1:{pedido} música", download=False)
        e = (r.get("entries") or [None])[0]
        if e and e.get("id"):
            return f"https://music.youtube.com/watch?v={e['id']}"
    except Exception:
        pass
    return "https://music.youtube.com/search?q=" + urllib.parse.quote(pedido)


def _registrar_pulo() -> None:
    if _ultima["faixa"] and time.time() - _ultima["inicio"] < 40:
        _gosto.registrar("musica", _ultima["faixa"], "pulou")


def _midia(tecla: str) -> None:
    from plugins import _midia
    _midia.tecla(tecla)


def sugerir() -> str:
    """Uma sugestão pelo gosto (lançamento de artista que você ouve, ou ideia da IA). Só oferece."""
    if S.conectado():
        try:
            for art in S.top_artistas(5):
                for alb in S.lancamentos(art["id"], 3):
                    data = alb.get("release_date", "")
                    if data >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 45 * 86400)):
                        nome = f"{art['name']} - {alb['name']}"
                        if not _gosto.ja_ofereceu(nome, 30):
                            _gosto.registrar("oferta", nome, "ofereceu", "lancamento")
                            return (f"Saiu coisa nova de {art['name']}: \"{alb['name']}\" ({data}). Quer que eu toque? "
                                    "(Se ele aceitar, use action=tocar com esse nome.)")
        except Exception as e:
            print(f"[Música] lançamentos: {e}")
    gosto = _gosto.resumo()
    from plugins import _ia
    if not gosto:
        return "Ainda não conheço seu gosto. Peça algumas músicas que eu aprendo."
    if not _ia.disponivel():
        art = _gosto.top_artistas(3)
        return f"Pelo que você ouve, que tal {art[0]}?" if art else "Ainda não conheço seu gosto."
    r = _ia.perguntar(f"Gosto musical do usuário: {gosto}. Sugira UMA música REAL (artista - título) que ele "
                      "provavelmente gosta e ainda não aparece na lista, com meia frase do porquê. Responda só: "
                      "Artista - Título | motivo", False, 25) or ""
    if "|" not in r:
        return "Não consegui pensar numa sugestão agora."
    faixa, motivo = (x.strip() for x in r.split("|", 1))
    _gosto.registrar("oferta", faixa, "ofereceu", "ia")
    return f"Sugestão: {faixa} — {motivo}. Quer ouvir? (Se aceitar, action=tocar com essa música.)"


# ── 2.2: ideias novas — timer de sono, despertador, música por humor e rádio do gosto ──
import threading  # noqa: E402

from plugins._comum import MEMORIA, falar, gravar_json, ler_json  # noqa: E402

ARQ_ALARMES = MEMORIA / "musica_alarmes.json"
HUMORES = {
    "foc": "foco concentração lofi", "estud": "estudar lofi instrumental", "trein": "treino academia rap pesado",
    "academ": "treino academia rap pesado", "corr": "corrida motivação", "relax": "relaxar chill acústico",
    "dorm": "dormir sono calmo", "fest": "festa hits brasil", "trist": "músicas tristes sad", "feliz": "bom humor feliz",
    "anim": "animada pra cima", "romant": "romântica", "jog": "gaming música para jogar", "trabalh": "foco trabalho",
    "chuv": "dia de chuva", "viag": "viagem estrada", "limp": "faxina animada", "medit": "meditação calma",
}
_sono = {"timer": None, "ate": 0.0}
_alarmes_iniciou = threading.Event()


def busca_do_humor(pedido: str, artistas: list[str] | None = None) -> str:
    """'quero focar' → 'foco concentração lofi' (+ um artista do gosto em atividades animadas) (pura)."""
    t = _dobrar(pedido)
    base = next((v for k, v in HUMORES.items() if k in t), t or "mix")
    if artistas and any(x in base for x in ("treino", "festa", "animada", "corrida", "gaming")):
        return f"{base} {artistas[0]}"
    return base


def _pausar_tudo() -> None:
    if S.conectado():
        try:
            S.api("PUT", "/me/player/pause")
            return
        except S.ErroSpotify:
            pass
    _midia("play_pause")


def dormir(minutos: float) -> str:
    if _sono["timer"]:
        _sono["timer"].cancel()
    if minutos <= 0:
        _sono.update(timer=None, ate=0.0)
        return "Timer de sono cancelado."

    def fim():
        try:
            if S.conectado():
                vol = (estado_player().get("volume") or 50)
                for passo in range(5, 0, -1):                     # vai baixando no último minuto
                    S.api("PUT", "/me/player/volume", {"volume_percent": int(vol * passo / 6)})
                    time.sleep(12)
            _pausar_tudo()
            if S.conectado():
                S.api("PUT", "/me/player/volume", {"volume_percent": int(vol)})
        except Exception as e:
            print(f"[Música] timer de sono: {e}")
        _sono.update(timer=None, ate=0.0)

    atraso = max(0.0, minutos * 60 - 60)
    _sono["timer"] = threading.Timer(atraso, fim)
    _sono["timer"].daemon = True
    _sono["timer"].start()
    _sono["ate"] = time.time() + minutos * 60
    return f"Timer de sono: daqui a {minutos:g} minutos eu abaixo a música devagar e paro. Boa noite!"


def alarmes() -> list[dict]:
    return list(ler_json(ARQ_ALARMES, []) or [])


def proximo_disparo(hora: str, agora: float) -> float:
    """'07:30' → timestamp da próxima vez que der 07:30 (pura)."""
    import datetime as _dt
    h, m = (int(x) for x in hora.split(":"))
    a = _dt.datetime.fromtimestamp(agora)
    alvo = a.replace(hour=h, minute=m, second=0, microsecond=0)
    if alvo.timestamp() <= agora:
        alvo += _dt.timedelta(days=1)
    return alvo.timestamp()


def despertador(hora: str, pedido: str) -> str:
    import re as _re
    if _dobrar(pedido).startswith("cancel") or _dobrar(hora).startswith("cancel"):
        gravar_json(ARQ_ALARMES, [])
        return "Despertador musical cancelado."
    m = _re.match(r"\s*(\d{1,2})(?:[:h](\d{2}))?", hora or "")
    if not m or int(m.group(1)) > 23:
        return "Que horas? (ex.: 07:30)"
    hm = f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"
    quando = proximo_disparo(hm, time.time())
    lista = [a for a in alarmes() if a.get("hora") != hm] + [{"hora": hm, "quando": quando, "pedido": pedido.strip()}]
    gravar_json(ARQ_ALARMES, lista)
    import datetime as _dt
    dia = "amanhã" if _dt.datetime.fromtimestamp(quando).date() > _dt.date.today() else "hoje"
    return (f"Despertador musical {dia} às {hm}" + (f" com {pedido.strip()}" if pedido.strip() else " com o que você mais "
            "ouve") + ". O PC precisa estar ligado (pode estar com a tela apagada).")


def _tocar_despertador(a: dict, player) -> None:
    pedido = a.get("pedido") or (_gosto.top_artistas(1) or ["músicas para acordar"])[0]
    try:
        if S.conectado():
            S.api("PUT", "/me/player/volume", {"volume_percent": 15})
    except Exception:
        pass
    r = run({"action": "tocar", "pedido": pedido})
    falar(player, f"[DESPERTADOR] Dê bom dia ao usuário, animado, em uma frase curta. Está tocando: {r}")
    if S.conectado():
        for vol in (25, 35, 45, 55):                           # volume subindo devagar
            time.sleep(20)
            try:
                S.api("PUT", "/me/player/volume", {"volume_percent": vol})
            except Exception:
                break


def _laco_alarmes(player) -> None:
    while True:
        try:
            agora = time.time()
            lista = alarmes()
            devidos = [a for a in lista if a.get("quando", 0) <= agora]
            if devidos:
                gravar_json(ARQ_ALARMES, [a for a in lista if a not in devidos])
                for a in devidos:
                    if agora - a["quando"] < 3600:                 # PC desligado na hora: não toca atrasado demais
                        _tocar_despertador(a, player)
        except Exception as e:
            print(f"[Música] despertador: {e}")
        time.sleep(20)


def on_session_start(player) -> None:
    if not _alarmes_iniciou.is_set():
        _alarmes_iniciou.set()
        threading.Thread(target=_laco_alarmes, args=(player,), daemon=True, name="despertador_musical").start()


def radio(c: dict) -> str:
    artistas = _gosto.top_artistas(6)
    if S.conectado():
        try:
            artistas = list(dict.fromkeys(artistas + [a["name"] for a in S.top_artistas(6)]))[:6]
        except S.ErroSpotify:
            pass
    if not artistas:
        return "Ainda não conheço seu gosto para montar uma rádio. Peça algumas músicas primeiro."
    if not S.conectado():
        abrir_no_sistema(url_youtube_music(f"mix {artistas[0]}"))
        return f"Rádio no YouTube Music com base em {artistas[0]}."
    faixas = []
    for art in artistas:
        r = S.api("GET", "/search", {"q": f"artist:{art}", "type": "track", "limit": 3, "market": "from_token"}) or {}
        faixas += [t for t in (r.get("tracks") or {}).get("items") or [] if t][:2]
    if not faixas:
        return "Não consegui montar a rádio agora."
    import random as _r
    _r.shuffle(faixas)
    S.api("PUT", "/me/player/play", corpo={"uris": [t["uri"] for t in faixas[:20]]})
    _talvez_abrir_player(c)
    return f"Rádio JARVIS no ar: {len(faixas[:20])} músicas de {', '.join(artistas[:4])}."


# ── 2.2: tela "Tocando agora" (dashboard/static/player.html, servida por plugins/_arcade.py) ──
def _capa(item: dict) -> str:
    imgs = ((item.get("album") or {}).get("images") or item.get("images") or [])
    return imgs[0]["url"] if imgs else ""


def ler_estado_spotify(r: dict | None) -> dict:
    """Resposta de GET /me/player → o que a tela mostra (pura)."""
    if not r or not r.get("item"):
        return {"servico": "spotify", "conectado": True, "vazio": True}
    it = r["item"]
    disp = r.get("device") or {}
    return {"servico": "spotify", "conectado": True, "vazio": False, "tocando": bool(r.get("is_playing")),
            "titulo": it.get("name", ""), "artistas": ", ".join(a.get("name", "") for a in it.get("artists", [])),
            "album": (it.get("album") or {}).get("name", ""), "capa": _capa(it), "uri": it.get("uri", ""),
            "id": it.get("id", ""), "progresso_ms": r.get("progress_ms") or 0, "duracao_ms": it.get("duration_ms") or 0,
            "volume": disp.get("volume_percent"), "aparelho": disp.get("name", ""),
            "aleatorio": bool(r.get("shuffle_state")), "repetir": r.get("repeat_state", "off"),
            "contexto": (r.get("context") or {}).get("uri", "")}


def estado_player() -> dict:
    if S.conectado():
        try:
            return ler_estado_spotify(S.api("GET", "/me/player", {"additional_types": "track"}))
        except S.ErroSpotify as e:
            return {"servico": "spotify", "conectado": True, "vazio": True, "erro": f"Spotify {e.codigo}"}
    from plugins import _midia
    faixa = _midia.faixa_atual()
    partes = faixa.split(" - ", 1)
    return {"servico": "outro", "conectado": False, "vazio": not faixa, "tocando": bool(faixa),
            "titulo": partes[-1] if faixa else "", "artistas": partes[0] if len(partes) == 2 else "",
            "capa": "", "progresso_ms": 0, "duracao_ms": 0}


def playlists_player() -> dict:
    if not S.conectado():
        return {"itens": [], "erro": "Conecte o Spotify para ver as suas playlists (diga 'conecta o Spotify')."}
    r = S.api("GET", "/me/playlists", {"limit": 50}) or {}
    return {"itens": [{"nome": p.get("name", ""), "uri": p.get("uri", ""), "capa": _capa(p),
                       "total": (p.get("tracks") or {}).get("total", 0), "dono": (p.get("owner") or {}).get("display_name", "")}
                      for p in r.get("items") or [] if p]}


def buscar_player(q: str) -> dict:
    q = (q or "").strip()
    if not q:
        return {"itens": []}
    if not S.conectado():
        return {"itens": [], "erro": "Sem Spotify: use 'toca … no YouTube Music' por voz."}
    r = S.api("GET", "/search", {"q": q, "type": "track,playlist,artist", "limit": 6, "market": "from_token"}) or {}
    itens = [{"tipo": "música", "nome": t.get("name", ""), "sub": ", ".join(a["name"] for a in t.get("artists", [])),
              "uri": t.get("uri", ""), "capa": _capa(t)} for t in (r.get("tracks") or {}).get("items") or [] if t]
    itens += [{"tipo": "artista", "nome": a.get("name", ""), "sub": "artista", "uri": a.get("uri", ""), "capa": _capa(a)}
              for a in (r.get("artists") or {}).get("items") or [] if a][:2]
    itens += [{"tipo": "playlist", "nome": p.get("name", ""), "sub": "playlist", "uri": p.get("uri", ""), "capa": _capa(p)}
              for p in (r.get("playlists") or {}).get("items") or [] if p][:3]
    return {"itens": itens}


def comando_player(acao: str, b: dict) -> dict:
    """Botões da tela. Sem Spotify, usa as teclas de mídia do Windows."""
    acao = _dobrar(acao)
    if not S.conectado():
        tecla = {"play": "play_pause", "pausar": "play_pause", "proxima": "proxima", "anterior": "anterior"}.get(acao)
        if tecla:
            _midia(tecla)
            return {"ok": True}
        return {"ok": False, "erro": "Isso precisa do Spotify conectado."}
    try:
        if acao in ("play", "pausar", "proxima", "anterior"):
            if acao == "proxima":
                _registrar_pulo()
            caminho, metodo = {"play": ("/me/player/play", "PUT"), "pausar": ("/me/player/pause", "PUT"),
                               "proxima": ("/me/player/next", "POST"), "anterior": ("/me/player/previous", "POST")}[acao]
            S.api(metodo, caminho)
        elif acao == "volume":
            S.api("PUT", "/me/player/volume", {"volume_percent": max(0, min(100, int(b.get("valor", 50))))})
        elif acao == "posicao":
            S.api("PUT", "/me/player/seek", {"position_ms": max(0, int(b.get("valor", 0)))})
        elif acao == "aleatorio":
            S.api("PUT", "/me/player/shuffle", {"state": "true" if b.get("valor") else "false"})
        elif acao == "repetir":
            S.api("PUT", "/me/player/repeat", {"state": str(b.get("valor") or "off")})
        elif acao == "curtir":
            t = S.tocando()
            if t:
                S.api("PUT", "/me/tracks", {"ids": t["id"]})
                _gosto.registrar("musica", t["faixa"], "curtiu")
        elif acao == "tocar":
            uri = str(b.get("uri") or "")
            tipo = uri.split(":")[1] if uri.count(":") >= 2 else ""
            nome = S.tocar_item({"uri": uri, "_tipo": "track" if tipo == "track" else tipo, "name": str(b.get("nome") or ""),
                                 "artists": []})
            if b.get("nome"):
                _gosto.registrar("musica", str(b.get("nome")), "pediu")
            return {"ok": True, "tocando": nome}
        elif acao == "fila":
            S.api("POST", "/me/player/queue", {"uri": str(b.get("uri") or "")})
        else:
            return {"ok": False, "erro": "ação desconhecida"}
        return {"ok": True}
    except S.ErroSpotify as e:
        msg = {403: "precisa de Spotify Premium", 404: "abra o Spotify em algum aparelho"}.get(e.codigo, f"erro {e.codigo}")
        return {"ok": False, "erro": msg}


def abrir_player() -> bool:
    from plugins import _arcade
    x = y = None
    try:
        from plugins._comum import WIN
        if WIN:
            import ctypes
            sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
            x, y = max(0, sw - 400), max(0, sh - 760)
    except Exception:
        pass
    return _arcade.abrir_pagina("/player", 380, 700, x, y)


_player_aberto = {"quando": 0.0}


def _talvez_abrir_player(c: dict) -> None:
    if c.get("abrir_player", True) and time.time() - _player_aberto["quando"] > 600:
        _player_aberto["quando"] = time.time()
        try:
            abrir_player()
        except Exception as e:
            print(f"[Música] player: {e}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(p.get("action") or "tocar")
    c = cfg("musica", PLUGIN_SETTINGS)
    pedido = str(p.get("pedido") or "").strip()
    try:
        if acao == "conectar":
            cid = str(c.get("client_id") or "").strip()
            if not cid:
                return ("Para conectar o Spotify: entre em developer.spotify.com/dashboard, crie um app (Web API) com o "
                        "Redirect URI http://127.0.0.1:8888/callback, copie o Client ID para ⚙ CONFIG. DE PLUGINS → "
                        "Música e peça de novo.")
            erro = S.conectar(cid)
            return "Spotify conectado! Pode pedir música." if not erro else f"Não conectei o Spotify: {erro}."
        if acao == "status":
            return (f"Spotify {'conectado' if S.conectado() else 'não conectado'}; preferido: "
                    f"{c.get('preferido', 'spotify')}. Artistas que você mais ouve: "
                    f"{', '.join(_gosto.top_artistas(5)) or 'ainda aprendendo'}.")
        if acao == "sugerir":
            return sugerir()
        if acao == "dormir":
            return dormir(float(p.get("minutos") if p.get("minutos") is not None else 30))
        if acao == "despertador":
            return despertador(str(p.get("hora") or ""), pedido)
        if acao == "humor":
            busca = busca_do_humor(pedido, _gosto.top_artistas(3))
            if S.conectado():
                item = S.buscar(busca, "playlist")
                if item:
                    nome = S.tocar_item(item)
                    _talvez_abrir_player(c)
                    return f"Para esse clima: playlist {nome}."
            abrir_no_sistema(url_youtube_music(busca))
            return f"Para esse clima, tocando {busca} no YouTube Music."
        if acao == "radio":
            return radio(c)
        if acao == "player":
            _player_aberto["quando"] = time.time()
            return "Abri a tela 'Tocando agora'." if abrir_player() else "Não consegui abrir a tela do player."
        if acao == "nao_gosto":
            alvo = pedido or _ultima["faixa"]
            if not alvo:
                return "Do que você não gosta?"
            _gosto.nao_gosto(_gosto.artista_de(alvo) or alvo)
            _gosto.registrar("musica", alvo, "pulou")
            return f"Anotado: não vou sugerir {_gosto.artista_de(alvo) or alvo}."
        usar_spotify = S.conectado()
        if acao == "tocar":
            if not pedido:
                acao = "continuar"
            else:
                servico, limpo = servico_do_pedido(pedido, str(p.get("servico") or ""), usar_spotify,
                                                   str(c.get("preferido") or "spotify"))
                if servico == "spotify":
                    item = S.buscar(limpo)
                    if not item:
                        return f"Não achei '{limpo}' no Spotify."
                    nome = S.tocar_item(item)
                else:
                    abrir_no_sistema(url_youtube_music(limpo))
                    nome = f"{limpo} (YouTube Music)"
                _gosto.registrar("musica", nome.split(" (")[0], "pediu")
                _ultima.update(faixa=nome.split(" (")[0], inicio=time.time())
                if servico == "spotify":
                    _talvez_abrir_player(c)                      # 2.2: a tela "Tocando agora"
                return f"Tocando {nome}."
        if acao in ("pausar", "continuar", "proxima", "anterior"):
            if acao == "proxima":
                _registrar_pulo()
            if usar_spotify:
                try:
                    caminho, metodo = {"pausar": ("/me/player/pause", "PUT"), "continuar": ("/me/player/play", "PUT"),
                                       "proxima": ("/me/player/next", "POST"),
                                       "anterior": ("/me/player/previous", "POST")}[acao]
                    S.api(metodo, caminho)
                    return {"pausar": "Pausado.", "continuar": "Continuando.", "proxima": "Próxima.",
                            "anterior": "Voltando."}[acao]
                except S.ErroSpotify:
                    pass                                         # cai para a tecla de mídia (YouTube, outro player)
            _midia({"pausar": "play_pause", "continuar": "play_pause", "proxima": "proxima", "anterior": "anterior"}[acao])
            return "Feito."
        if acao == "volume":
            nivel = max(0, min(100, int(p.get("nivel") if p.get("nivel") is not None else 50)))
            if usar_spotify:
                try:
                    S.api("PUT", "/me/player/volume", {"volume_percent": nivel})
                    return f"Volume da música em {nivel}%."
                except S.ErroSpotify:
                    pass
            from plugins.controle_audio_video import _volume
            return _volume(str(nivel))
        if not usar_spotify:
            return "Isso precisa do Spotify conectado (diga 'conecta o Spotify')."
        if acao == "fila":
            item = S.buscar(pedido, "track") if pedido else None
            if not item:
                return "Qual música vai para a fila?"
            S.api("POST", "/me/player/queue", {"uri": item["uri"]})
            return f"Na fila: {S.nome_item(item)}."
        if acao in ("tocando", "curtir"):
            t = S.tocando()
            if not t:
                return "Nada tocando no Spotify agora."
            if t["faixa"] != _ultima["faixa"]:
                _ultima.update(faixa=t["faixa"], inicio=time.time() - t["progresso_ms"] / 1000)
            if acao == "curtir":
                S.api("PUT", "/me/tracks", {"ids": t["id"]})
                _gosto.registrar("musica", t["faixa"], "curtiu")
                return f"Curtido: {t['faixa']}."
            mostrar(player, "TOCANDO AGORA", t["faixa"])
            return f"Tocando: {t['faixa']}."
        return "Não entendi o pedido de música."
    except S.ErroSpotify as e:
        if e.codigo == 401:
            return "O Spotify não está conectado. Diga 'conecta o Spotify'."
        if e.codigo == 403:
            return "O Spotify recusou: controlar o player precisa de conta Premium."
        if e.codigo == 404:
            return "Abra o Spotify em algum aparelho (PC ou celular) e peça de novo."
        return f"O Spotify respondeu erro {e.codigo}."
    except Exception as e:
        return f"A música falhou: {e}"
