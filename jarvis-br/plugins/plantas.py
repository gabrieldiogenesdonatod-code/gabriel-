"""
Planta com sede (fork PT-BR 2.5) — sensor de umidade da terra com ESP32.

    "Jarvis, configura a planta"          → liga o servidor e diz o IP e a CHAVE para o sketch
    "Jarvis, como estão as plantas?"
    "Jarvis, o sensor da sala é a samambaia"      (dá nome)
    "Jarvis, calibra o sensor da sala: está no ar" / "está na água"

O ESP32 (esp32/planta) acorda de 30 em 30 minutos, mede a terra e manda para
o PC. Ele avisa sozinho:
    "A planta da sala está com sede: a terra está em 22%."   (depois de umas horas seca)
    "A planta da sala está seca há 2 dias."                 (um lembrete por dia, de dia)
e percebe quando você rega. Dados em memory/plantas.json.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime

from plugins import _esp32
from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "plantas",
    "brief": "Thirsty plant: ESP32 soil-moisture sensors; warns when a plant is dry; setup, names, calibration.",
    "description": (
        "Plants with ESP32 soil sensors. action='status' (how are the plants). 'configurar' gives the PC IP and key "
        "for the ESP32 sketch. 'nomear' with id and nome (e.g. id 'sala', nome 'samambaia'). 'limite' with id and "
        "valor (dry below this %). 'calibrar' with id and estado ('seco' = sensor in the air, 'molhado' = in water). "
        "'regada' with id (I just watered). JARVIS warns by himself when a plant stays dry."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | configurar | nomear | limite | calibrar | regada"},
            "id": {"type": "STRING"}, "nome": {"type": "STRING"}, "valor": {"type": "NUMBER"},
            "estado": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "plantas",
    "title": "Plantas (sensor ESP32)",
    "fields": [
        {"key": "limite", "label": "Terra seca abaixo de (%)", "type": "text", "default": "30"},
        {"key": "horas_aviso", "label": "Avisar depois de quantas horas seca", "type": "text", "default": "6"},
    ],
}

ARQ = MEMORIA / "plantas.json"
SECO_PADRAO, MOLHADO_PADRAO = 3000, 1300          # ADC de 12 bits do ESP32 com sensor capacitivo v1.2 em 3,3 V
_lock = threading.Lock()
_iniciou = threading.Event()


def _c() -> dict:
    return cfg("plantas", PLUGIN_SETTINGS)


def _limite_padrao() -> float:
    try:
        return float(str(_c().get("limite") or 30))
    except ValueError:
        return 30.0


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("plantas", {})
    return d


# ── regras (puras) ─────────────────────────────────────────────────────────────
def porcentagem(bruto: float, seco: float = SECO_PADRAO, molhado: float = MOLHADO_PADRAO) -> float:
    """Leitura do ADC → % de umidade (seco no ar = 0 %, na água = 100 %)."""
    if seco == molhado:
        return 0.0
    return round(max(0.0, min(100.0, (seco - bruto) / (seco - molhado) * 100)), 1)


def nome_da_planta(p: dict, id_: str) -> str:
    """'a planta da sala' / 'a samambaia'."""
    nome = str(p.get("nome") or "").strip()
    if nome:
        return nome if nome.lower().startswith(("a ", "o ", "as ", "os ")) else f"a {nome}"
    return f"a planta da {id_}" if id_ not in ("planta", "") else "a planta"


def atualizar(p: dict, umidade: float, agora: float, limite: float) -> str | None:
    """Aplica uma leitura. Devolve 'secou' | 'regou' | None (puro, mexe só em p)."""
    antes = p.get("umidade")
    p["umidade"], p["ts"] = umidade, agora
    p.setdefault("historico", []).append([round(agora), umidade])
    p["historico"] = p["historico"][-400:]
    evento = None
    if umidade < limite:
        if not p.get("seca_desde"):
            p["seca_desde"] = agora
            evento = "secou"
    elif p.get("seca_desde") and umidade >= limite + 8:
        p["seca_desde"] = None
        p["avisos"] = {}
        evento = "regou"
    if antes is not None and umidade - antes >= 15:
        p["seca_desde"], p["avisos"] = None, {}
        evento = "regou"
    return evento


def aviso_devido(p: dict, id_: str, agora: float, horas_aviso: float, hoje: str) -> str | None:
    """Frase a falar agora (ou None). Primeiro 'está com sede', depois um lembrete por dia (puro)."""
    desde = p.get("seca_desde")
    if not desde:
        return None
    avisos = p.setdefault("avisos", {})
    horas = (agora - desde) / 3600
    nome = nome_da_planta(p, id_)
    if horas >= horas_aviso and "sede" not in avisos:
        avisos["sede"], avisos["dia"] = agora, hoje
        return f"{nome[0].upper()}{nome[1:]} está com sede: a terra está em {round(p.get('umidade') or 0)}%."
    dias = int(horas // 24)
    if dias >= 1 and avisos.get("dia") != hoje:
        avisos["dia"] = hoje
        return f"{nome[0].upper()}{nome[1:]} está seca há {dias} dia{'s' if dias > 1 else ''}."
    return None


# ── o ESP32 manda ─────────────────────────────────────────────────────────────
def receber(corpo: dict, _q: dict | None = None) -> dict:
    id_ = "".join(ch for ch in str(corpo.get("id") or "planta").lower() if ch.isalnum() or ch in "-_")[:24] or "planta"
    with _lock:
        d = dados()
        p = d["plantas"].setdefault(id_, {"criada": time.time()})
        if corpo.get("bruto") is not None:
            p["bruto"] = float(corpo["bruto"])
            umidade = porcentagem(p["bruto"], p.get("seco", SECO_PADRAO), p.get("molhado", MOLHADO_PADRAO))
        else:
            umidade = max(0.0, min(100.0, float(corpo.get("umidade") or 0)))
        if corpo.get("bateria") is not None:
            p["bateria"] = float(corpo["bateria"])
        evento = atualizar(p, umidade, time.time(), float(p.get("limite") or _limite_padrao()))
        gravar_json(ARQ, d)
    if evento == "regou":
        from plugins._comum import registrar
        registrar(None, f"Plantas: {nome_da_planta(p, id_)} foi regada ({umidade}%).")
    return {"ok": True, "umidade": umidade, "seca": bool(p.get("seca_desde")), "dormir_min": 30}


def verificar(agora: float | None = None) -> list[str]:
    agora = agora or time.time()
    try:
        horas = float(str(_c().get("horas_aviso") or 6))
    except ValueError:
        horas = 6.0
    falas = []
    hoje = date.fromtimestamp(agora).isoformat()
    with _lock:
        d = dados()
        for id_, p in d["plantas"].items():
            f = aviso_devido(p, id_, agora, horas, hoje)
            if f:
                falas.append(f)
            if p.get("ts") and agora - p["ts"] > 6 * 3600 and p.get("avisos", {}).get("mudo") != hoje:
                p.setdefault("avisos", {})["mudo"] = hoje
                falas.append(f"O sensor d{nome_da_planta(p, id_)} parou de mandar dados (bateria ou Wi-Fi?).")
        if falas:
            gravar_json(ARQ, d)
    for f in falas:
        try:
            from plugins._notificar import notificar
            notificar(None, f, titulo="Plantas", etiqueta="PLANTA", prioridade="low" if "parou" in f else "default")
        except Exception as e:
            print(f"[Plantas] {e}")
    return falas


def _laco() -> None:
    time.sleep(90)
    while True:
        if 9 <= datetime.now().hour < 20:
            try:
                verificar()
            except Exception as e:
                print(f"[Plantas] {e}")
        time.sleep(900)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    _esp32.registrar_rota("POST", "/esp32/planta", receber)
    _esp32.iniciar_se_ligado()
    threading.Thread(target=_laco, daemon=True, name="plantas").start()


def _descrever(id_: str, p: dict) -> str:
    nome = nome_da_planta(p, id_)
    if p.get("umidade") is None:
        return f"{nome} ({id_}): ainda sem leitura"
    quando = datetime.fromtimestamp(p["ts"]).strftime("%d/%m %H:%M")
    estado = "SECA" if p.get("seca_desde") else "ok"
    extra = f", bateria {p['bateria']:.2f} V" if p.get("bateria") else ""
    return f"{nome[0].upper()}{nome[1:]} ({id_}): {round(p['umidade'])}% — {estado} (às {quando}{extra})"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "configurar":
            _esp32.registrar_rota("POST", "/esp32/planta", receber)
            return _esp32.configuracao("planta") + " Use um ID diferente em cada planta (ex.: sala, quarto)."
        id_ = str(p.get("id") or "").strip().lower()
        with _lock:
            d = dados()
            if acao in ("nomear", "limite", "calibrar", "regada"):
                if not id_ and len(d["plantas"]) == 1:
                    id_ = next(iter(d["plantas"]))
                if id_ not in d["plantas"]:
                    return f"Não conheço o sensor '{id_}'. Sensores: {', '.join(d['plantas']) or 'nenhum ainda'}."
                pl = d["plantas"][id_]
                if acao == "nomear":
                    pl["nome"] = str(p.get("nome") or "").strip()
                    msg = f"Pronto: o sensor {id_} agora é {nome_da_planta(pl, id_)}."
                elif acao == "limite":
                    pl["limite"] = max(5.0, min(90.0, float(p.get("valor") or 30)))
                    msg = f"{nome_da_planta(pl, id_)} fica seca abaixo de {pl['limite']:.0f}%."
                elif acao == "calibrar":
                    if pl.get("bruto") is None:
                        return "Ainda não recebi leitura desse sensor para calibrar."
                    chave = "molhado" if str(p.get("estado") or "").lower().startswith(("molh", "agua", "água")) \
                        else "seco"
                    pl[chave] = pl["bruto"]
                    msg = f"Calibrado: {chave} = {pl['bruto']:.0f}. Faça o outro ({'seco' if chave == 'molhado' else 'molhado'}) também."
                else:
                    pl["seca_desde"], pl["avisos"] = None, {}
                    msg = f"Anotei que você regou {nome_da_planta(pl, id_)}."
                gravar_json(ARQ, d)
                return msg
        if not d["plantas"]:
            return ("Nenhum sensor de planta mandou dados ainda. Diga 'configura a planta' para ver o IP e a chave do "
                    "sketch (pasta esp32/planta).")
        texto = "\n".join(_descrever(i, pl) for i, pl in d["plantas"].items())
        mostrar(player, "PLANTAS", texto)
        return texto
    except Exception as e:
        return f"As plantas falharam: {e}"
