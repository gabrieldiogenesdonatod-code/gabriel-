"""
Aparelhos da rede (fork PT-BR 1.6) — ligar, desligar e controlar tudo que
está na MESMA rede que você, num lugar só.

    PCs da casa      ligar (Wake-on-LAN), desligar, reiniciar, suspender, bloquear,
                     abrir programa/site, fechar programa, volume, mensagem na tela,
                     print, status e rodar comandos — com o agente em agente_pc/
    TV Roku / TCL    ligar, desligar, volume, setas, abrir YouTube/Netflix… (sem instalar nada)
    TV Samsung       desligar, teclas, apps (a TV pede "Permitir" na 1ª vez); ligar pela rede
    TV LG (webOS)    desligar, volume, apps (pip install pywebostv; a TV pede "Aceitar")
    Android TV e     ligar/desligar a tela, volume, teclas, apps, digitar, print e
    celular Android  comandos — pelo ADB por Wi-Fi ("Jarvis, instala o ADB")
    Luzes/tomadas    as da casa inteligente (Tuya/Positivo) também respondem aqui

    "Jarvis, procura os aparelhos da rede"     "Jarvis, o 3 é a TV da sala"
    "Jarvis, liga o PC do quarto"              "Jarvis, desliga a TV da sala"
    "Jarvis, abre o YouTube na TV"             "Jarvis, aumenta o volume da TV"
    "Jarvis, abre o Chrome no PC da sala"      "Jarvis, roda ipconfig no PC da sala"
    "Jarvis, tira um print do celular"         "Jarvis, como está o PC do quarto?"
    "Jarvis, desliga tudo"                     (TVs e luzes; PCs pedem confirmação)

Os aparelhos ficam em config/aparelhos.json. Desligar/reiniciar um PC e
rodar comandos passam pelo botão CONFIRMAR.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import ssl
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plugins import _rede
from plugins._comum import (BASE, CONFIG, WIN, abrir_no_sistema, confirmar, gravar_json, ler_json, mostrar,
                            pasta_usuario, rodar)

PLUGIN = {
    "name": "aparelhos",
    "brief": "Controls devices on the same network: other PCs (agent + Wake-on-LAN), Roku/Samsung/LG/Android TVs, Android phones (ADB), Tuya lights.",
    "description": (
        "Network devices: other home PCs (via the JARVIS agent: wake-on-LAN, shutdown, restart, sleep, lock, "
        "open/close programs, volume, message, screenshot, status, run commands), smart TVs (Roku, Samsung, LG, "
        "Android TV), Android phones over Wi-Fi ADB, and Tuya lights/plugs. action: 'procurar' (scan the network), "
        "'listar', 'nomear' with alvo (number from the scan or IP) + nome (+ tipo), 'adicionar' with ip + nome + "
        "tipo, 'remover' with aparelho, 'parear' with aparelho + chave (PC agent key; TVs: starts the pairing "
        "prompt), 'conectar_adb' with aparelho (+ porta, codigo for Android 11+ pairing), 'instalar_adb', "
        "'ligar' | 'desligar' | 'reiniciar' | 'suspender' | 'bloquear' | 'status' | 'print' with aparelho "
        "('tudo' allowed for ligar/desligar), 'abrir' / 'fechar' with aparelho + alvo (app, program or site), "
        "'tecla' with aparelho + tecla (home, voltar, ok, cima, baixo, esquerda, direita, play, pausar, proximo, "
        "anterior, mudo), 'volume' with aparelho + direcao (mais|menos|mudo) + vezes, 'digitar' with aparelho + "
        "texto, 'mensagem' with aparelho + texto, 'rodar' with aparelho + comando (terminal command; confirmation)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"}, "aparelho": {"type": "STRING"}, "alvo": {"type": "STRING"},
            "nome": {"type": "STRING"}, "tipo": {"type": "STRING"}, "ip": {"type": "STRING"},
            "chave": {"type": "STRING"}, "porta": {"type": "INTEGER"}, "codigo": {"type": "STRING"},
            "tecla": {"type": "STRING"}, "direcao": {"type": "STRING"}, "vezes": {"type": "INTEGER"},
            "texto": {"type": "STRING"}, "comando": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_ARQ = CONFIG / "aparelhos.json"
_FERRAMENTAS = BASE / "ferramentas"
NOMES_TIPO = {"pc": "PC (agente)", "pc_windows": "PC Windows (sem agente)", "tv_roku": "TV Roku", "tv_samsung":
              "TV Samsung", "tv_lg": "TV LG", "tv_android": "Android TV", "android": "Android", "celular": "celular",
              "chromecast": "Chromecast", "tuya": "luz/tomada Tuya", "impressora": "impressora", "camera": "câmera",
              "desconhecido": "desconhecido"}

TECLAS_ROKU = {"ligar": "PowerOn", "desligar": "PowerOff", "mais": "VolumeUp", "menos": "VolumeDown",
               "mudo": "VolumeMute", "home": "Home", "voltar": "Back", "ok": "Select", "cima": "Up", "baixo": "Down",
               "esquerda": "Left", "direita": "Right", "play": "Play", "pausar": "Play", "proximo": "Fwd",
               "anterior": "Rev", "info": "Info"}
TECLAS_ADB = {"ligar": 224, "desligar": 223, "bloquear": 223, "mais": 24, "menos": 25, "mudo": 164, "home": 3,
              "voltar": 4, "ok": 23, "cima": 19, "baixo": 20, "esquerda": 21, "direita": 22, "play": 85,
              "pausar": 85, "proximo": 87, "anterior": 88, "info": 165}
TECLAS_SAMSUNG = {"desligar": "KEY_POWER", "mais": "KEY_VOLUP", "menos": "KEY_VOLDOWN", "mudo": "KEY_MUTE",
                  "home": "KEY_HOME", "voltar": "KEY_RETURN", "ok": "KEY_ENTER", "cima": "KEY_UP", "baixo": "KEY_DOWN",
                  "esquerda": "KEY_LEFT", "direita": "KEY_RIGHT", "play": "KEY_PLAY", "pausar": "KEY_PAUSE",
                  "proximo": "KEY_FF", "anterior": "KEY_REWIND", "info": "KEY_INFO"}
APPS = {  # nome falado → ids por plataforma
    "youtube": {"roku": "837", "samsung": "111299001912", "android": "com.google.android.youtube",
                "tv": "com.google.android.youtube.tv"},
    "netflix": {"roku": "12", "samsung": "3201907018807", "android": "com.netflix.mediaclient", "tv": "com.netflix.ninja"},
    "prime video": {"roku": "13", "samsung": "3201910019365", "android": "com.amazon.avod.thirdpartyclient",
                    "tv": "com.amazon.amazonvideo.livingroom"},
    "disney": {"roku": "291097", "samsung": "3201901017640", "android": "com.disney.disneyplus",
               "tv": "com.disney.disneyplus"},
    "spotify": {"roku": "22297", "samsung": "3201606009684", "android": "com.spotify.music", "tv": "com.spotify.tv.android"},
    "globoplay": {"android": "com.globo.globotv", "tv": "com.globo.globotv"},
    "whatsapp": {"android": "com.whatsapp"}, "instagram": {"android": "com.instagram.android"},
    "tiktok": {"android": "com.zhiliaoapp.musically"}, "camera": {"android": "com.android.camera"},
}
_SINONIMOS_TECLA = {"aumentar": "mais", "aumenta": "mais", "sobe": "mais", "abaixar": "menos", "abaixa": "menos",
                    "diminui": "menos", "silencio": "mudo", "inicio": "home", "inicial": "home", "enter": "ok",
                    "confirmar": "ok", "pause": "pausar", "pausa": "pausar", "continuar": "play", "proxima": "proximo",
                    "anteriores": "anterior", "subir": "cima", "descer": "baixo"}


# ── dados e nomes (puros onde dá) ──────────────────────────────────────────────
def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def carregar() -> dict:
    d = ler_json(_ARQ, {}) or {}
    d.setdefault("aparelhos", [])
    d.setdefault("vistos", [])
    return d


def achar(aparelhos: list[dict], nome: str) -> list[dict]:
    """'tv da sala', 'sala', 'tv', '192.168.0.12', 'tudo' → aparelhos (pura)."""
    t = _dobrar(nome)
    if not t:
        return []
    if t in ("tudo", "todos", "todas", "a casa", "casa toda"):
        return list(aparelhos)
    por_ip = [a for a in aparelhos if a.get("ip") == t]
    if por_ip:
        return por_ip
    exatos = [a for a in aparelhos if _dobrar(a["nome"]) == t]
    if exatos:
        return exatos
    palavras = [w for w in re.findall(r"\w{2,}", t) if w not in ("o", "a", "do", "da", "de", "no", "na", "meu", "minha")]
    if t in ("tv", "televisao", "a tv"):
        tvs = [a for a in aparelhos if a.get("tipo", "").startswith("tv_")]
        return tvs[:1] if len(tvs) == 1 else tvs
    if t in ("celular", "o celular", "meu celular"):
        return [a for a in aparelhos if a.get("tipo") in ("celular", "android")][:1]
    return [a for a in aparelhos if palavras and all(w in _dobrar(f"{a['nome']} {a.get('tipo', '')}") for w in palavras)]


def tecla_de(texto: str) -> str:
    t = _dobrar(texto).replace("volume ", "").replace("tecla ", "").strip()
    return _SINONIMOS_TECLA.get(t, t)


def app_de(texto: str) -> tuple[str, dict]:
    t = _dobrar(texto)
    for nome, ids in APPS.items():
        if nome in t or nome.split()[0] in t:
            return nome, ids
    return texto, {}


def plataforma(tipo: str) -> str:
    return {"tv_roku": "roku", "tv_samsung": "samsung", "tv_lg": "lg", "tv_android": "adb", "android": "adb",
            "celular": "adb", "pc": "pc", "pc_windows": "pc", "tuya": "tuya"}.get(tipo, "")


# ── PC (agente) ────────────────────────────────────────────────────────────────
def pc(a: dict, acao: str, args: dict | None = None, timeout: float = 15) -> dict:
    import requests
    if not a.get("chave"):
        return {"erro": f"o {a['nome']} ainda não está pareado (rode o agente nele e diga 'pareia o {a['nome']}')"}
    corpo, assinatura = _rede.pedido_assinado(a["chave"], acao, args)
    try:
        r = requests.post(f"http://{a['ip']}:{a.get('porta') or _rede.PORTA_AGENTE}/cmd", data=corpo, timeout=timeout,
                          headers={"X-Assinatura": assinatura, "Content-Type": "application/json"})
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"erro": f"o {a['nome']} não respondeu (desligado, ou o agente não está aberto)"}
    except Exception as e:
        return {"erro": str(e)}


def ola(ip: str) -> dict:
    import requests
    try:
        return requests.get(f"http://{ip}:{_rede.PORTA_AGENTE}/ola", timeout=2).json()
    except Exception:
        return {}


# ── Roku (ECP, HTTP simples) ───────────────────────────────────────────────────
def roku(ip: str, caminho: str, metodo: str = "POST") -> str:
    import requests
    r = requests.request(metodo, f"http://{ip}:8060/{caminho}", timeout=5)
    return r.text if r.ok else f"erro HTTP {r.status_code}"


# ── Samsung (WebSocket da própria TV) ──────────────────────────────────────────
def samsung(a: dict, tecla: str = "", app: str = "") -> str:
    try:
        from websockets.sync.client import connect
    except ImportError:
        return "Preciso do pacote websockets (vem com o uvicorn[standard] do setup.py)."
    nome = base64.b64encode(b"JARVIS").decode()
    url = f"wss://{a['ip']}:8002/api/v2/channels/samsung.remote.control?name={nome}"
    if a.get("token"):
        url += f"&token={a['token']}"
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE        # a TV usa certificado próprio
    with connect(url, ssl=ctx, open_timeout=8, close_timeout=2) as ws:
        msg = json.loads(ws.recv(timeout=30))                         # 1ª vez: espera você aceitar na TV
        token = (msg.get("data") or {}).get("token")
        if token and token != a.get("token"):
            d = carregar()
            for x in d["aparelhos"]:
                if x.get("ip") == a["ip"]:
                    x["token"] = token
            gravar_json(_ARQ, d)
        if msg.get("event") != "ms.channel.connect":
            return f"a TV recusou ({msg.get('event')})"
        if tecla:
            ws.send(json.dumps({"method": "ms.remote.control", "params": {
                "Cmd": "Click", "DataOfCmd": tecla, "Option": "false", "TypeOfRemote": "SendRemoteKey"}}))
        if app:
            ws.send(json.dumps({"method": "ms.channel.emit", "params": {
                "event": "ed.apps.launch", "to": "host", "data": {"appId": app, "action_type": "DEEP_LINK"}}}))
        time.sleep(0.4)
    return "ok"


# ── LG webOS (pywebostv, opcional) ─────────────────────────────────────────────
def lg(a: dict, oque: str, valor: str = "") -> str:
    try:
        from pywebostv.connection import WebOSClient
        from pywebostv.controls import ApplicationControl, MediaControl, SystemControl
    except ImportError:
        return "Para TVs LG instale: python -m pip install pywebostv"
    cliente = WebOSClient(a["ip"])
    cliente.connect()
    loja = {"client_key": a["lg_chave"]} if a.get("lg_chave") else {}
    for estado in cliente.register(loja, timeout=40):                 # 1ª vez: aceite na TV
        if estado == WebOSClient.PROMPTED:
            pass
    if loja.get("client_key") and loja["client_key"] != a.get("lg_chave"):
        d = carregar()
        for x in d["aparelhos"]:
            if x.get("ip") == a["ip"]:
                x["lg_chave"] = loja["client_key"]
        gravar_json(_ARQ, d)
    if oque == "desligar":
        SystemControl(cliente).power_off()
    elif oque in ("mais", "menos", "mudo"):
        m = MediaControl(cliente)
        m.volume_up() if oque == "mais" else m.volume_down() if oque == "menos" else m.mute(True)
    elif oque in ("play", "pausar"):
        m = MediaControl(cliente)
        m.play() if oque == "play" else m.pause()
    elif oque == "abrir":
        apps = ApplicationControl(cliente)
        alvo = next((x for x in apps.list_apps() if _dobrar(valor) in _dobrar(x["title"])), None)
        if not alvo:
            return f"não achei o app {valor} na TV"
        apps.launch(alvo)
    elif oque == "mensagem":
        SystemControl(cliente).notify(valor[:60])
    return "ok"


# ── ADB (Android TV e celular) ─────────────────────────────────────────────────
def adb_exe() -> str | None:
    local = _FERRAMENTAS / "platform-tools" / ("adb.exe" if WIN else "adb")
    return str(local) if local.exists() else shutil.which("adb")


def adb(a: dict, *args: str, timeout: float = 15) -> tuple[int, str]:
    exe = adb_exe()
    if not exe:
        return -1, "o ADB não está instalado (diga 'instala o ADB')"
    alvo = f"{a['ip']}:{a.get('porta_adb') or 5555}"
    if alvo not in rodar([exe, "devices"], timeout=6)[1]:
        rodar([exe, "connect", alvo], timeout=8)
    return rodar([exe, "-s", alvo, *args], timeout=timeout, encoding="utf-8")


def instalar_adb() -> str:
    import io
    import zipfile

    import requests
    so = "windows" if WIN else "darwin" if shutil.which("sw_vers") else "linux"
    r = requests.get(f"https://dl.google.com/android/repository/platform-tools-latest-{so}.zip", timeout=120)
    r.raise_for_status()
    _FERRAMENTAS.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(_FERRAMENTAS)
    if not WIN:
        (Path(_FERRAMENTAS) / "platform-tools" / "adb").chmod(0o755)
    return f"ADB instalado em {_FERRAMENTAS / 'platform-tools'}."


# ── ações ─────────────────────────────────────────────────────────────────────
def _salvar_print(dados: bytes, nome: str) -> Path:
    pasta = pasta_usuario("Pictures") / "JARVIS"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"print_{re.sub(r'[^a-z0-9]+', '_', _dobrar(nome))}_{time.strftime('%Y%m%d_%H%M%S')}.png"
    arq.write_bytes(dados)
    return arq


def controlar(a: dict, acao: str, p: dict) -> str:
    """Uma ação num aparelho. Devolve uma frase curta."""
    tipo, nome = a.get("tipo", ""), a["nome"]
    plat = plataforma(tipo)
    if plat == "tuya" or a.get("casa"):
        from plugins.casa_inteligente import executar
        return executar(a.get("casa") or nome, "ligar" if acao == "ligar" else "desligar" if acao == "desligar" else acao)
    if acao == "ligar" and plat in ("pc", "samsung", "lg"):
        if not a.get("mac"):
            return f"Para ligar o {nome} pela rede preciso do MAC dele (procure de novo com ele ligado)."
        _rede.acordar(a["mac"], a.get("ip", ""))
        return f"Mandei o sinal para ligar o {nome} (Wake-on-LAN; precisa estar ativado nele)."
    if plat == "pc":
        if acao in ("desligar", "reiniciar"):
            return confirmar(f"aparelhos:{acao}:{a['ip']}", f"{acao.capitalize()} o {nome}?",
                             "O que não estiver salvo nele pode se perder (ele avisa e espera 10 s).",
                             lambda: _frase_pc(nome, pc(a, acao, {"segundos": 10})))
        if acao == "rodar":
            cmd = str(p.get("comando") or "")
            return confirmar(f"aparelhos:rodar:{a['ip']}", f"Rodar no {nome}?", cmd,
                             lambda: _frase_pc(nome, pc(a, "rodar", {"comando": cmd}, timeout=75), mostrar_saida=True))
        if acao == "status":
            s = pc(a, "status")
            if s.get("erro"):
                return f"{nome}: {s['erro']}"
            partes = [f"CPU {s['cpu']:.0f}%" if "cpu" in s else "", f"RAM {s['ram']:.0f}%" if "ram" in s else "",
                      f"ligado há {s['ligado_ha_min'] // 60}h{s['ligado_ha_min'] % 60:02d}" if "ligado_ha_min" in s else "",
                      f"usando: {', '.join(s['usuarios'])}" if s.get("usuarios") else "",
                      f"bateria {s['bateria']}%" if "bateria" in s else ""]
            return f"{nome}: " + ", ".join(x for x in partes if x) + "."
        if acao == "print":
            s = pc(a, "print", timeout=40)
            if s.get("png"):
                arq = _salvar_print(base64.b64decode(s["png"]), nome)
                abrir_no_sistema(str(arq))
                return f"Print do {nome} salvo em {arq}."
            return f"{nome}: {s.get('erro', 'sem print')}"
        args = {"abrir": {"alvo": p.get("alvo")}, "fechar": {"alvo": p.get("alvo")},
                "volume": {"qual": tecla_de(p.get("direcao") or "mais")}, "mensagem": {"texto": p.get("texto")},
                "tecla": {"qual": tecla_de(p.get("tecla") or "")}}.get(acao, {})
        if acao == "tecla":
            acao = "volume"
        return _frase_pc(nome, pc(a, acao, args))
    if plat == "roku":
        if acao in ("ligar", "desligar"):
            roku(a["ip"], f"keypress/{TECLAS_ROKU[acao]}")
            return f"{'Liguei' if acao == 'ligar' else 'Desliguei'} a {nome}."
        if acao in ("tecla", "volume"):
            t = tecla_de(p.get("tecla") or p.get("direcao") or "")
            if t not in TECLAS_ROKU:
                return f"A Roku não tem a tecla {t}."
            for _ in range(max(1, min(20, int(p.get("vezes") or (3 if acao == "volume" and t != "mudo" else 1))))):
                roku(a["ip"], f"keypress/{TECLAS_ROKU[t]}")
            return "Feito."
        if acao == "abrir":
            nome_app, ids = app_de(p.get("alvo") or "")
            if not ids.get("roku"):
                return f"Não sei abrir {nome_app} na Roku."
            roku(a["ip"], f"launch/{ids['roku']}")
            return f"Abri o {nome_app} na {nome}."
        if acao == "digitar":
            for ch in str(p.get("texto") or ""):
                roku(a["ip"], "keypress/Lit_" + urllib.parse.quote(ch, safe=""))
            return "Digitei."
        if acao == "status":
            xml = roku(a["ip"], "query/device-info", "GET")
            m = re.search(r"<power-mode>(.*?)</power-mode>", xml)
            return f"{nome}: {'ligada' if m and m.group(1) == 'PowerOn' else 'em espera' if m else 'respondendo'}."
    if plat == "samsung":
        if acao in ("desligar", "tecla", "volume"):
            t = "desligar" if acao == "desligar" else tecla_de(p.get("tecla") or p.get("direcao") or "")
            if t not in TECLAS_SAMSUNG:
                return f"Não conheço a tecla {t}."
            for _ in range(max(1, min(20, int(p.get("vezes") or (3 if acao == "volume" and t != "mudo" else 1))))):
                r = samsung(a, tecla=TECLAS_SAMSUNG[t])
                if r != "ok":
                    return f"{nome}: {r}"
            return "Feito." if acao != "desligar" else f"Desliguei a {nome}."
        if acao == "abrir":
            nome_app, ids = app_de(p.get("alvo") or "")
            if not ids.get("samsung"):
                return f"Não sei abrir {nome_app} na Samsung."
            r = samsung(a, app=ids["samsung"])
            return f"Abri o {nome_app} na {nome}." if r == "ok" else f"{nome}: {r}"
        if acao == "status":
            return f"{nome}: {'ligada' if _rede.porta_aberta(a['ip'], 8002, 1) else 'desligada ou fora da rede'}."
    if plat == "lg":
        oque = {"desligar": "desligar", "abrir": "abrir", "mensagem": "mensagem"}.get(acao) or \
            tecla_de(p.get("tecla") or p.get("direcao") or "")
        r = lg(a, oque, str(p.get("alvo") or p.get("texto") or ""))
        return "Feito." if r == "ok" else f"{nome}: {r}"
    if plat == "adb":
        tv = tipo == "tv_android"
        if acao in ("ligar", "desligar", "bloquear", "tecla", "volume"):
            t = acao if acao in ("ligar", "desligar", "bloquear") else tecla_de(p.get("tecla") or p.get("direcao") or "")
            if t not in TECLAS_ADB:
                return f"Não conheço a tecla {t}."
            vezes = max(1, min(20, int(p.get("vezes") or (3 if acao == "volume" and t != "mudo" else 1))))
            for _ in range(vezes):
                cod, out = adb(a, "shell", "input", "keyevent", str(TECLAS_ADB[t]))
                if cod != 0:
                    return f"{nome}: {out[-200:]}"
            return "Feito."
        if acao == "abrir":
            nome_app, ids = app_de(p.get("alvo") or "")
            pacote = ids.get("tv" if tv else "android") or (p.get("alvo") if "." in str(p.get("alvo")) else "")
            if not pacote:
                return f"Não sei o pacote do {nome_app}. Diga o nome do pacote (ex.: com.exemplo.app)."
            cat = "android.intent.category.LEANBACK_LAUNCHER" if tv else "android.intent.category.LAUNCHER"
            cod, out = adb(a, "shell", "monkey", "-p", pacote, "-c", cat, "1")
            return f"Abri o {nome_app} no {nome}." if cod == 0 and "No activities" not in out else f"{nome}: {out[-200:]}"
        if acao == "digitar":
            texto = re.sub(r"\s", "%s", str(p.get("texto") or ""))
            cod, out = adb(a, "shell", "input", "text", texto)
            return "Digitei." if cod == 0 else out[-200:]
        if acao == "print":
            exe = adb_exe()
            if not exe:
                return "O ADB não está instalado."
            import subprocess

            from plugins._comum import CNW
            adb(a, "get-state")
            r = subprocess.run([exe, "-s", f"{a['ip']}:{a.get('porta_adb') or 5555}", "exec-out", "screencap", "-p"],
                               capture_output=True, timeout=30, **CNW)
            if r.returncode != 0 or not r.stdout.startswith(b"\x89PNG"):
                return f"{nome}: não consegui o print."
            arq = _salvar_print(r.stdout, nome)
            abrir_no_sistema(str(arq))
            return f"Print do {nome} salvo em {arq}."
        if acao == "status":
            cod, bat = adb(a, "shell", "dumpsys", "battery")
            if cod != 0:
                return f"{nome}: {bat[-200:]}"
            nivel = re.search(r"level: (\d+)", bat)
            carregando = re.search(r"(AC|USB|Wireless) powered: true", bat)
            _c, energia = adb(a, "shell", "dumpsys", "power")
            tela = "tela ligada" if "mWakefulness=Awake" in energia else "tela apagada"
            return f"{nome}: {tela}" + (f", bateria {nivel.group(1)}%" if nivel else "") + \
                (" carregando" if carregando else "") + "."
        if acao == "rodar":
            cmd = str(p.get("comando") or "")
            return confirmar(f"aparelhos:rodar:{a['ip']}", f"Rodar no {nome}?", f"adb shell {cmd}",
                             lambda: _saida(nome, *adb(a, "shell", cmd, timeout=60)))
    if acao == "status":
        return f"{nome}: {'responde na rede' if _rede.porta_aberta(a['ip'], 80, 1) or _rede.porta_aberta(a['ip'], 445, 1) else 'sem resposta'}."
    return f"O {nome} ({NOMES_TIPO.get(tipo, tipo)}) não aceita '{acao}'."


def _saida(nome: str, cod: int, out: str) -> str:
    return f"{nome} ({'ok' if cod == 0 else f'código {cod}'}): {out[-600:] or 'sem saída'}"


def _frase_pc(nome: str, r: dict, mostrar_saida: bool = False) -> str:
    if r.get("erro"):
        return f"{nome}: {r['erro']}"
    saida = str(r.get("saida") or "").strip()
    if mostrar_saida:
        return f"{nome} ({'ok' if r.get('ok') else 'código ' + str(r.get('codigo'))}): {saida[-800:] or 'sem saída'}"
    return f"{nome}: {saida[:200] or 'feito'}."


def procurar(player=None) -> str:
    achados = _rede.varrer()
    for x in achados:
        if x["tipo"] == "pc":
            info = ola(x["ip"])
            x["nome_rede"] = info.get("nome") or x["nome_rede"]
            x["mac"] = x["mac"] or info.get("mac", "")
    d = carregar()
    conhecidos = {a["ip"]: a["nome"] for a in d["aparelhos"]}
    d["vistos"] = achados
    gravar_json(_ARQ, d)
    linhas = []
    for i, x in enumerate(achados, 1):
        rotulo = conhecidos.get(x["ip"]) or ""
        linhas.append(f"{i:>2}. {x['ip']:<15} {NOMES_TIPO.get(x['tipo'], x['tipo']):<24} {x['nome_rede'][:28]:<28} "
                      f"{x['mac'] or ''} {('= ' + rotulo) if rotulo else ''}")
    mostrar(player, f"APARELHOS NA REDE ({len(achados)})", "\n".join(linhas) + "\n\nDiga: 'o 3 é a TV da sala'.")
    interessantes = [x for x in achados if x["tipo"] not in ("desconhecido",)]
    resumo = ", ".join(f"{i}: {NOMES_TIPO.get(x['tipo'])}" for i, x in enumerate(achados, 1) if x in interessantes)
    return (f"Achei {len(achados)} aparelho(s) na rede. Os que reconheci: {resumo or 'nenhum'}. A lista está no "
            "painel; diga 'o número tal é a TV da sala' para dar um nome.")


def nomear(alvo: str, nome: str, tipo: str = "") -> str:
    d = carregar()
    x = None
    if str(alvo).strip().isdigit() and 0 < int(alvo) <= len(d["vistos"]):
        x = d["vistos"][int(alvo) - 1]
    else:
        x = next((v for v in d["vistos"] if v["ip"] == str(alvo).strip()), None)
    if not x:
        return "Não achei esse número/IP na última procura. Diga 'procura os aparelhos' de novo."
    tipo = _tipo_falado(tipo) or x["tipo"]
    if re.search(r"\btv\b|televis", _dobrar(nome)) and not tipo.startswith("tv_") and tipo in ("android", "desconhecido"):
        tipo = "tv_android" if tipo == "android" else tipo
    if re.search(r"celular|telefone", _dobrar(nome)) and tipo == "android":
        tipo = "celular"
    d["aparelhos"] = [a for a in d["aparelhos"] if a.get("ip") != x["ip"] and _dobrar(a["nome"]) != _dobrar(nome)]
    d["aparelhos"].append({"nome": nome.strip(), "tipo": tipo, "ip": x["ip"], "mac": x.get("mac", "")})
    gravar_json(_ARQ, d)
    dica = {"pc": " Agora diga 'pareia o " + nome + "' com a chave que o agente mostrou.",
            "pc_windows": " Para controlar, rode o agente nele (pasta agente_pc) e pareie.",
            "tv_samsung": " Na primeira vez a TV vai pedir para permitir o JARVIS.",
            "tv_lg": " Na primeira vez a TV vai pedir para aceitar o JARVIS.",
            "tv_android": " Ative a 'depuração pela rede' nas opções do desenvolvedor e diga 'conecta o ADB na " + nome + "'.",
            "android": " Ative a 'depuração sem fio' e diga 'conecta o ADB no " + nome + "'.",
            "celular": " Ative a 'depuração sem fio' e diga 'conecta o ADB no " + nome + "'."}.get(tipo, "")
    return f"Pronto: {x['ip']} agora é '{nome}' ({NOMES_TIPO.get(tipo, tipo)}).{dica}"


def _tipo_falado(t: str) -> str:
    t = _dobrar(t)
    for chave, tipo in (("roku", "tv_roku"), ("samsung", "tv_samsung"), ("lg", "tv_lg"), ("android tv", "tv_android"),
                        ("google tv", "tv_android"), ("celular", "celular"), ("android", "android"), ("pc", "pc"),
                        ("computador", "pc"), ("notebook", "pc"), ("luz", "tuya"), ("tomada", "tuya")):
        if chave in t:
            return tipo
    return t if t in NOMES_TIPO else ""


def todos(d: dict) -> list[dict]:
    """Os aparelhos daqui + as luzes/tomadas da casa inteligente, num lugar só."""
    lista = list(d["aparelhos"])
    try:
        from plugins.casa_inteligente import carregar as casa
        nomes = {_dobrar(a["nome"]) for a in lista}
        lista += [{"nome": c["nome"], "tipo": "tuya", "ip": c.get("ip", ""), "casa": c["nome"]}
                  for c in casa()["aparelhos"] if _dobrar(c["nome"]) not in nomes]
    except Exception:
        pass
    return lista


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(p.get("action") or "listar")
    try:
        if acao == "procurar":
            return procurar(player)
        if acao == "instalar_adb":
            return instalar_adb()
        if acao == "nomear":
            return nomear(str(p.get("alvo") or p.get("ip") or ""), str(p.get("nome") or ""), str(p.get("tipo") or ""))
        d = carregar()
        if acao == "adicionar":
            ip, nome = str(p.get("ip") or "").strip(), str(p.get("nome") or "").strip()
            if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", ip) or not nome:
                return "Diga o IP e um nome (ex.: 192.168.0.20, PC do quarto)."
            tipo = _tipo_falado(str(p.get("tipo") or "")) or "desconhecido"
            d["aparelhos"] = [a for a in d["aparelhos"] if a.get("ip") != ip]
            d["aparelhos"].append({"nome": nome, "tipo": tipo, "ip": ip, "mac": ola(ip).get("mac", "") if tipo == "pc" else ""})
            gravar_json(_ARQ, d)
            return f"Adicionei {nome} ({NOMES_TIPO.get(tipo, tipo)}) em {ip}."
        if acao == "listar":
            lista = todos(d)
            if not lista:
                return "Nenhum aparelho ainda. Diga 'procura os aparelhos da rede'."
            mostrar(player, "SEUS APARELHOS", "\n".join(
                f"{a['nome']:<24} {NOMES_TIPO.get(a.get('tipo', ''), a.get('tipo', '')):<22} {a.get('ip', '')}"
                + ("  (pareado)" if a.get("chave") or a.get("token") or a.get("lg_chave") else "") for a in lista))
            return "Seus aparelhos: " + ", ".join(a["nome"] for a in lista) + "."
        alvos = achar(todos(d), str(p.get("aparelho") or ""))
        if not alvos:
            nomes = ", ".join(a["nome"] for a in todos(d)) or "nenhum"
            return f"Não achei o aparelho '{p.get('aparelho')}'. Conheço: {nomes}."
        if acao == "remover":
            d["aparelhos"] = [a for a in d["aparelhos"] if a not in alvos]
            gravar_json(_ARQ, d)
            return f"Removi {', '.join(a['nome'] for a in alvos)}."
        if acao == "parear":
            a = alvos[0]
            if a.get("tipo") in ("pc", "pc_windows"):
                chave = str(p.get("chave") or "").strip()
                if len(chave) < 16:
                    return "Diga (ou digite) a chave que o agente mostrou no outro PC."
                for x in d["aparelhos"]:
                    if x["ip"] == a["ip"]:
                        x.update(chave=chave, tipo="pc", mac=x.get("mac") or ola(a["ip"]).get("mac", ""))
                gravar_json(_ARQ, d)
                s = pc({**a, "chave": chave}, "status")
                return f"Pareado com o {a['nome']}." if not s.get("erro") else f"Guardei a chave, mas: {s['erro']}."
            if a.get("tipo") == "tv_samsung":
                return "Olhe a TV e aperte Permitir. " + samsung(a, tecla="KEY_INFO")
            if a.get("tipo") == "tv_lg":
                return "Olhe a TV e aperte Aceitar. " + lg(a, "info")
            return "Esse aparelho não precisa de pareamento (para Android use 'conecta o ADB')."
        if acao == "conectar_adb":
            a, exe = alvos[0], adb_exe()
            if not exe:
                return "Primeiro diga 'instala o ADB'."
            porta = int(p.get("porta") or a.get("porta_adb") or 5555)
            if p.get("codigo"):                                # Android 11+: "parear dispositivo com código"
                cod, out = rodar([exe, "pair", f"{a['ip']}:{porta}", str(p["codigo"])], timeout=20)
                return (f"Pareado. Agora diga 'conecta o ADB no {a['nome']}' com a porta que aparece em "
                        "'Depuração sem fio' (é diferente da do código).") if cod == 0 else out[-300:]
            cod, out = rodar([exe, "connect", f"{a['ip']}:{porta}"], timeout=12)
            if "connected" in out and "cannot" not in out:
                for x in d["aparelhos"]:
                    if x["ip"] == a["ip"]:
                        x["porta_adb"] = porta
                gravar_json(_ARQ, d)
                return f"ADB conectado no {a['nome']}. Se aparecer um aviso no aparelho, aceite (marque 'sempre')."
            return f"Não conectou: {out[-300:]}"
        if len(alvos) > 1 and acao not in ("ligar", "desligar", "status"):
            return "Qual deles? " + ", ".join(a["nome"] for a in alvos) + "."
        if len(alvos) > 1:
            # "desliga tudo": TVs e luzes direto; PCs pedem confirmação um a um, então ficam de fora
            seguros = [a for a in alvos if not (acao == "desligar" and plataforma(a.get("tipo", "")) == "pc")]
            with ThreadPoolExecutor(max_workers=8) as ex:
                res = list(ex.map(lambda a: _seguro(a, acao, p), seguros))
            pulados = len(alvos) - len(seguros)
            return " ".join(res) + (f" ({pulados} PC(s) ficaram de fora: desligue um por vez.)" if pulados else "")
        return controlar(alvos[0], acao, p)
    except ImportError as e:
        return f"Falta um pacote para isso: {e.name}."
    except Exception as e:
        return f"Os aparelhos falharam: {e}"


def _seguro(a: dict, acao: str, p: dict) -> str:
    try:
        return controlar(a, acao, p)
    except Exception as e:
        return f"{a['nome']}: {e}."
