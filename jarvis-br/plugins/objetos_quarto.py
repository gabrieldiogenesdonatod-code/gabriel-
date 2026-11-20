"""
Câmera do quarto: onde ficou o carregador? (fork PT-BR 2.5)

    "Jarvis, liga a câmera do quarto"         (desligada até você pedir)
    "Jarvis, onde está o meu fone?"           → "Vi seu fone em cima da cama às 14:20 (há 35 min)."
    "Jarvis, olha o quarto agora"             → olha na hora e conta o que viu

De tempos em tempos (e só quando a cena muda) ele olha o cômodo pela webcam ou
por uma câmera IP (as mesmas da Central) e anota onde estão os objetos da lista:
carregador, fone, chave, controle, carteira, óculos, celular… Com a chave do
Gemini ele entende qualquer objeto e descreve o lugar ("na mesa, perto do
monitor"); sem chave, usa a visão no próprio PC (MediaPipe), que só conhece
alguns objetos (celular, controle remoto, notebook, copo, livro, mochila…).

PRIVACIDADE: começa DESLIGADO. As fotos vão para o Gemini só se você ligar a
opção em ⚙ → Câmera do quarto; o JARVIS não descreve pessoas, só objetos.
Guarda só a ÚLTIMA foto (memory/quarto/ultima.jpg) e a lista em
memory/objetos_quarto.json.
"""

from __future__ import annotations

import threading
import time
import unicodedata
from datetime import datetime

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, salvar_cfg, sim

PLUGIN = {
    "name": "objetos_quarto",
    "brief": "Room camera notes where things are (charger, earphones, keys, controller); 'where is my X?'.",
    "description": (
        "Room camera that remembers where objects are. action='onde' with objeto (e.g. fone, carregador, chave, "
        "controle): where it was last seen. 'olhar': look at the room now and list objects. 'ligar' / 'desligar' "
        "the periodic watching. 'status'. It never describes people."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "onde | olhar | ligar | desligar | status"},
            "objeto": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "objetos_quarto",
    "title": "Câmera do quarto (onde deixei?)",
    "fields": [
        {"key": "ligado", "label": "Olhar o cômodo de tempos em tempos", "type": "toggle", "default": False},
        {"key": "camera", "label": "Câmera (0 = webcam; 1, 2… = câmeras IP da Central)", "type": "text",
         "default": "0"},
        {"key": "objetos", "label": "Objetos para anotar", "type": "text",
         "default": "carregador, fone de ouvido, chave, controle, carteira, óculos, celular, mochila, garrafa"},
        {"key": "intervalo_min", "label": "No mínimo a cada (minutos)", "type": "text", "default": "15"},
        {"key": "usar_ia", "label": "Mandar a foto para o Gemini (entende qualquer objeto)", "type": "toggle",
         "default": True},
    ],
}

ARQ = MEMORIA / "objetos_quarto.json"
PASTA = MEMORIA / "quarto"
_iniciou = threading.Event()
_lock = threading.Lock()
_estado = {"mini": None, "ultima": 0.0, "erro": ""}

PROMPT = (
    "Você é a câmera do quarto do JARVIS. Olhe a foto e diga ONDE estão estes objetos, se aparecerem: {lista}. "
    "Descreva o lugar com referências do cômodo (ex.: 'em cima da cama, perto do travesseiro', 'na mesa, ao lado do "
    "monitor'). NÃO descreva pessoas. Devolva SÓ JSON: {{\"objetos\": [{{\"nome\": \"um nome da lista\", \"onde\": "
    "\"…\"}}], \"outros\": [\"objetos soltos que alguém pode procurar depois\"]}}. Não invente o que não dá para ver.")


def _c() -> dict:
    return cfg("objetos_quarto", PLUGIN_SETTINGS)


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("objetos", {})
    d.setdefault("historico", [])
    return d


SINONIMOS = {"fone": ["fone", "fone de ouvido", "headset", "fones", "airpods", "earbuds"],
             "carregador": ["carregador", "cabo", "fonte"], "chave": ["chave", "chaves", "chaveiro"],
             "controle": ["controle", "controle remoto", "joystick", "manete", "controle do videogame"],
             "celular": ["celular", "telefone", "smartphone"], "oculos": ["oculos", "óculos"],
             "carteira": ["carteira"]}


def mesmo_objeto(a: str, b: str) -> bool:
    """'fone' ≈ 'fone de ouvido' ≈ 'headset' (puro)."""
    da, db = _dobrar(a), _dobrar(b)
    if not da or not db:
        return False
    if da in db or db in da:
        return True
    for lista in SINONIMOS.values():
        nomes = [_dobrar(x) for x in lista]
        if any(n in da for n in nomes) and any(n in db for n in nomes):
            return True
    return False


def anotar(achados: list[dict], quando: float, camera: int) -> int:
    """achados: [{'nome', 'onde'}] → grava o último lugar de cada objeto. Devolve quantos."""
    with _lock:
        d = dados()
        for a in achados:
            nome = str(a.get("nome") or "").strip().lower()
            onde = str(a.get("onde") or "").strip()
            if nome and onde:
                d["objetos"][nome] = {"onde": onde, "ts": quando, "camera": camera}
        d["historico"].append({"ts": quando, "itens": [f"{a.get('nome')}: {a.get('onde')}" for a in achados][:20]})
        d["historico"] = d["historico"][-200:]
        gravar_json(ARQ, d)
    return len(achados)


def ha_quanto(ts: float, agora: float | None = None) -> str:
    s = (agora or time.time()) - ts
    if s < 90:
        return "agora há pouco"
    if s < 3600:
        return f"há {int(s // 60)} min"
    if s < 86400:
        return f"há {int(s // 3600)} h"
    d = int(s // 86400)
    return "ontem" if d == 1 else f"há {d} dias"


def possessivo(nome: str) -> str:
    """'seu fone', 'sua chave', 'seus óculos' (puro)."""
    w = _dobrar(nome).split(" ")[0] if nome else ""
    fem = w in ("chave", "tv", "televisao", "bolsa", "mochila", "carteira", "garrafa", "tesoura", "caneca", "bola") \
        or (w.endswith("a") and w not in ("sofa", "pijama"))
    plural = w.endswith("s") and w not in ("mouse", "tenis", "lapis", "onibus")
    return ("suas " if fem else "seus ") + nome if plural else ("sua " if fem else "seu ") + nome


def resposta_onde(objeto: str, registros: dict, agora: float | None = None) -> str:
    achados = [(nome, r) for nome, r in registros.items() if mesmo_objeto(objeto, nome)]
    if not achados:
        return f"Não vi {objeto} nas últimas olhadas. Quer que eu olhe agora?"
    nome, r = max(achados, key=lambda x: x[1]["ts"])
    hora = datetime.fromtimestamp(r["ts"]).strftime("%H:%M")
    return f"Vi {possessivo(nome)} {r['onde']} às {hora} ({ha_quanto(r['ts'], agora)})."


def olhar(motivo: str = "") -> tuple[list[dict], str]:
    """Tira a foto, entende e anota. ([{'nome','onde'}], erro)"""
    c = _c()
    try:
        cam = int(str(c.get("camera") or "0"))
    except ValueError:
        cam = 0
    from plugins import _camera_remota
    img, erro = _camera_remota.quadro(cam, espera_s=6)
    if img is None:
        return [], erro or "sem imagem da câmera"
    import cv2
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if ok:
        PASTA.mkdir(parents=True, exist_ok=True)
        (PASTA / "ultima.jpg").write_bytes(buf.tobytes())
    achados: list[dict] = []
    if sim(c.get("usar_ia", True)) and ok:
        from plugins import _ia
        j = _ia.ver_imagem_json(PROMPT.format(lista=c.get("objetos") or ""), buf.tobytes(), inteligente=False)
        if isinstance(j, dict):
            achados = [o for o in (j.get("objetos") or []) if isinstance(o, dict)]
            achados += [{"nome": str(x), "onde": "na última foto do quarto"} for x in (j.get("outros") or [])[:6]
                        if isinstance(x, str)]
    if not achados:
        from plugins import _visao_local
        objs = _visao_local.detectar(img)
        if objs is None and not achados:
            return [], "sem chave do Gemini e sem MediaPipe para entender a foto"
        achados = [{"nome": o["nome_pt"], "onde": _visao_local.onde_na_imagem(o["caixa"])} for o in (objs or [])
                   if o["nome"] not in ("person", "chair", "bed", "couch", "dining table", "tv") and o["score"] >= 0.45]
    _estado["mini"] = _miniatura(img)
    _estado["ultima"] = time.time()
    anotar(achados, time.time(), cam)
    return achados, ""


def _miniatura(img):
    try:
        from plugins._visao_local import miniatura_cinza
        return miniatura_cinza(img)
    except Exception:
        return None


def _laco() -> None:
    time.sleep(180)
    while True:
        c = _c()
        if sim(c.get("ligado")):
            try:
                intervalo = max(5, int(float(str(c.get("intervalo_min") or 15)))) * 60
            except ValueError:
                intervalo = 900
            if time.time() - _estado["ultima"] >= intervalo:
                try:
                    from plugins import _camera_remota
                    from plugins._visao_local import mudou
                    cam = int(str(c.get("camera") or "0")) if str(c.get("camera") or "0").isdigit() else 0
                    img, _e = _camera_remota.quadro(cam, espera_s=4)
                    if img is not None and (mudou(_estado["mini"], _miniatura(img)) or
                                            time.time() - _estado["ultima"] > 6 * 3600):
                        _achados, erro = olhar("automático")
                        _estado["erro"] = erro
                except Exception as e:
                    _estado["erro"] = str(e)
                    print(f"[Quarto] {e}")
        time.sleep(60)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="objetos_quarto").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "onde").lower()
    try:
        if acao in ("ligar", "desligar"):
            salvar_cfg("objetos_quarto", {"ligado": acao == "ligar"})
            if acao == "desligar":
                return "Câmera do quarto desligada: não olho mais sozinho."
            return ("Câmera do quarto ligada: olho o cômodo quando ele mudar (no máximo a cada "
                    f"{_c().get('intervalo_min') or 15} min) e anoto onde ficam as coisas. Não descrevo pessoas.")
        if acao == "status":
            c = _c()
            d = dados()
            ultimo = max((r["ts"] for r in d["objetos"].values()), default=0)
            return (f"Câmera do quarto {'ligada' if sim(c.get('ligado')) else 'desligada'}; "
                    f"{len(d['objetos'])} objetos anotados" + (f", última olhada {ha_quanto(ultimo)}" if ultimo else "")
                    + (f". Último erro: {_estado['erro']}" if _estado["erro"] else "") + ".")
        if acao == "olhar":
            achados, erro = olhar("pedido")
            if erro:
                return f"Não consegui olhar o quarto: {erro}."
            if not achados:
                return "Olhei agora e não vi nenhum dos objetos da lista."
            texto = "\n".join(f"• {a['nome']}: {a['onde']}" for a in achados)
            mostrar(player, "NO QUARTO AGORA", texto)
            return "Vi agora:\n" + texto
        objeto = str(p.get("objeto") or "").strip()
        if not objeto:
            return "Qual objeto você está procurando?"
        resposta = resposta_onde(objeto, dados()["objetos"])
        if resposta.startswith("Não vi") and sim(_c().get("ligado")) is False:
            resposta += " (A câmera do quarto está desligada: diga 'liga a câmera do quarto'.)"
        return resposta
    except Exception as e:
        return f"A câmera do quarto falhou: {e}"
