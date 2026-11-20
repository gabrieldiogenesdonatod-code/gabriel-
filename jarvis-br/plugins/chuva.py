"""
"Recolhe a roupa!" — aviso de chuva bem local (fork PT-BR 2.5).

    "Jarvis, estendi roupa no varal"     → modo varal ligado até a noite
    "Jarvis, vai chover?"                → olha o radar e a previsão agora
    "Jarvis, recolhi a roupa"            → desliga o modo varal

Com o modo varal ligado ele fala sozinho: "Vai chover em uns 20 minutos, melhor
tirar a roupa do varal." Sem o varal, avisa só "vai chover em uns 20 minutos".

DE ONDE VEM
  • Radar de chuva (RainViewer, uso pessoal grátis): as imagens das últimas
    duas horas, de 10 em 10 minutos, em volta da sua casa. Ele mede para onde a
    chuva está andando e calcula quando chega em você ("nowcasting").
    Se a sua região não tiver radar na RainViewer, o radar vem vazio e ele usa só…
  • …a previsão de 15 em 15 minutos do Open-Meteo (grátis, sem chave).
Para ficar bem local, coloque a latitude e longitude da sua casa em ⚙ → Chuva
(no Google Maps: botão direito na sua casa → clique nos números para copiar).
"""

from __future__ import annotations

import io
import json
import math
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from plugins._comum import cfg, mostrar, salvar_cfg

PLUGIN = {
    "name": "chuva",
    "brief": "Very local rain alert (radar nowcast + 15-min forecast); 'clothesline mode' warns to take clothes in.",
    "description": (
        "Rain alerts. action='agora' checks radar and forecast now (will it rain in the next hour?). action='varal' "
        "with valor 'ligar' (user hung clothes outside: JARVIS warns before rain until the night) or 'desligar' "
        "(clothes taken in). action='status'. JARVIS warns by himself: 'Vai chover em uns 20 minutos, melhor tirar "
        "a roupa do varal.'"
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "agora | varal | status"},
            "valor": {"type": "STRING", "description": "ligar | desligar (para varal)"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "chuva",
    "title": "Chuva (recolhe a roupa!)",
    "fields": [
        {"key": "coordenadas", "label": "Latitude, longitude da sua casa (vazio = a cidade do Briefing)",
         "type": "text", "default": ""},
        {"key": "avisar", "label": "Avisar quando a chuva estiver chegando (mesmo sem roupa no varal)", "type": "toggle",
         "default": True},
        {"key": "antecedencia", "label": "Avisar com até quantos minutos de antecedência", "type": "text",
         "default": "40"},
        {"key": "radar", "label": "Usar o radar de chuva (RainViewer)", "type": "toggle", "default": True},
    ],
}

UA = {"User-Agent": "JARVIS-BR/2.5 (assistente pessoal)"}
RADAR_JSON = "https://api.rainviewer.com/public/weather-maps.json"
ZOOM = 7
RAIO_LOCAL_KM = 3.0
_iniciou = threading.Event()
_estado = {"varal_ate": 0.0, "ultimo_aviso": 0.0, "chovendo": False, "local": None, "ultima": None}


def _c() -> dict:
    return cfg("chuva", PLUGIN_SETTINGS)


def _get(url: str, timeout: float = 15) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


# ── onde ──────────────────────────────────────────────────────────────────────
def ler_coordenadas(t: str) -> tuple[float, float] | None:
    """'-16.6869, -49.2648' → (-16.6869, -49.2648)."""
    import re
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", str(t or ""))
    if len(nums) < 2:
        return None
    try:
        lat, lon = (float(n.replace(",", ".")) for n in nums[:2])
    except ValueError:
        return None
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def local() -> tuple[float, float, str] | None:
    c = ler_coordenadas(str(_c().get("coordenadas") or ""))
    if c:
        return c[0], c[1], "sua casa"
    if _estado["local"]:
        return _estado["local"]
    try:
        from plugins import briefing_br
        cidade = briefing_br._city()
    except Exception:
        cidade = ""
    if not cidade:
        return None
    geo = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": cidade, "count": 1, "language": "pt"})))
    hits = geo.get("results") or []
    if not hits:
        return None
    _estado["local"] = (float(hits[0]["latitude"]), float(hits[0]["longitude"]), hits[0].get("name") or cidade)
    return _estado["local"]


# ── radar: puro ───────────────────────────────────────────────────────────────
def km_por_pixel(lat: float, zoom: int = ZOOM, tamanho: int = 256) -> float:
    return 156.543034 * math.cos(math.radians(lat)) / (2 ** zoom) * (256 / tamanho)


def deslocamento(antes, agora) -> tuple[float, float] | None:
    """Quanto a chuva andou (dy, dx em pixels) entre as duas máscaras — correlação de fase (puro)."""
    import numpy as np
    a, b = np.asarray(antes, float), np.asarray(agora, float)
    if a.sum() < 6 or b.sum() < 6:
        return None
    fa, fb = np.fft.fft2(a), np.fft.fft2(b)
    r = fb * np.conj(fa)
    r /= np.abs(r) + 1e-9
    corr = np.fft.ifft2(r).real
    py, px = np.unravel_index(int(np.argmax(corr)), corr.shape)
    h, w = corr.shape
    py = py - h if py > h // 2 else py
    px = px - w if px > w // 2 else px
    return float(py), float(px)


def prever_chegada(antes, agora, minutos_entre: float, km_px: float, raio_km: float = RAIO_LOCAL_KM,
                   horizonte: int = 60) -> dict:
    """Máscaras de chuva (True = chuva) centradas na casa → {'chovendo', 'minutos', 'distancia_km', 'vindo_de'}."""
    import numpy as np
    m = np.asarray(agora, bool)
    h, w = m.shape
    cy, cx = (h - 1) / 2, (w - 1) / 2
    ys, xs = np.nonzero(m)
    if ys.size == 0:
        return {"chovendo": False, "minutos": None, "distancia_km": None, "vindo_de": ""}
    dist = np.hypot(ys - cy, xs - cx) * km_px
    perto = float(dist.min())
    saida = {"chovendo": perto <= raio_km, "minutos": 0 if perto <= raio_km else None,
             "distancia_km": round(perto, 1), "vindo_de": ""}
    if saida["chovendo"]:
        return saida
    d = deslocamento(antes, agora) if minutos_entre > 0 else None
    if d is not None:
        vy, vx = d[0] / minutos_entre, d[1] / minutos_entre            # pixels por minuto
        if math.hypot(vy, vx) * km_px > 2.5:                          # > 150 km/h: correlação errada
            d = None
    if d is not None and (vy or vx):
        raio_px = raio_km / km_px
        for t in range(5, horizonte + 1, 5):                           # a chuva que estará aqui em t está em centro - v·t
            py, px = cy - vy * t, cx - vx * t
            if (np.hypot(ys - py, xs - px) <= raio_px).any():
                saida["minutos"] = t
                saida["vindo_de"] = direcao(-vy, -vx)
                return saida
        return saida
    if antes is not None:                                              # sem direção: a chuva mais perto está chegando?
        ya, xa = np.nonzero(np.asarray(antes, bool))
        if ya.size:
            perto_antes = float((np.hypot(ya - cy, xa - cx) * km_px).min())
            vel = (perto_antes - perto) / minutos_entre if minutos_entre > 0 else 0
            if vel > 0.05:
                t = perto / vel
                if t <= horizonte:
                    saida["minutos"] = int(round(t / 5) * 5) or 5
    return saida


def direcao(dy: float, dx: float) -> str:
    """De onde vem (dy, dx = vetor da casa até a chuva; y cresce para o SUL na imagem)."""
    ang = (math.degrees(math.atan2(dx, -dy)) + 360) % 360           # 0 = norte, 90 = leste
    return ["do norte", "do nordeste", "do leste", "do sudeste", "do sul", "do sudoeste", "do oeste",
            "do noroeste"][int((ang + 22.5) // 45) % 8]


# ── radar: rede ───────────────────────────────────────────────────────────────
def _mascara_png(dados: bytes):
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(dados)).convert("RGBA")
    return np.asarray(im)[:, :, 3] > 40


def radar(lat: float, lon: float) -> dict | None:
    try:
        meta = json.loads(_get(RADAR_JSON))
        quadros = (meta.get("radar") or {}).get("past") or []
        if len(quadros) < 3:
            return None
        agora, antes = quadros[-1], quadros[-3]
        url = "{h}{p}/256/{z}/{la:.4f}/{lo:.4f}/2/0_0.png"
        m_agora = _mascara_png(_get(url.format(h=meta["host"], p=agora["path"], z=ZOOM, la=lat, lo=lon)))
        m_antes = _mascara_png(_get(url.format(h=meta["host"], p=antes["path"], z=ZOOM, la=lat, lo=lon)))
        minutos = max(1.0, (agora["time"] - antes["time"]) / 60)
        r = prever_chegada(m_antes, m_agora, minutos, km_por_pixel(lat))
        r["idade_min"] = round((time.time() - agora["time"]) / 60)
        return r
    except Exception as e:
        print(f"[Chuva] radar: {e}")
        return None


# ── previsão de 15 em 15 minutos (Open-Meteo) ─────────────────────────────────
def previsao(lat: float, lon: float) -> dict | None:
    try:
        d = json.loads(_get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": lat, "longitude": lon, "minutely_15": "precipitation", "forecast_minutely_15": 8,
            "hourly": "precipitation_probability", "forecast_hours": 3, "timezone": "auto"})))
        return chuva_na_previsao(d, datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=int(d.get("utc_offset_seconds") or 0)))
    except Exception as e:
        print(f"[Chuva] previsão: {e}")
        return None


def chuva_na_previsao(d: dict, agora_local: datetime, limiar_mm: float = 0.3) -> dict:
    """Resposta do Open-Meteo → {'minutos': até a 1ª faixa com chuva, 'mm': total em 2 h, 'prob': %} (puro)."""
    m = d.get("minutely_15") or {}
    minutos, total = None, 0.0
    for t, mm in zip(m.get("time") or [], m.get("precipitation") or []):
        try:
            quando = datetime.fromisoformat(t)
        except ValueError:
            continue
        falta = (quando - agora_local).total_seconds() / 60       # o valor é a soma dos 15 min ANTERIORES a `quando`
        if falta <= 0 or mm is None:
            continue
        total += mm
        if minutos is None and mm >= limiar_mm:
            minutos = max(0, int(round((falta - 15) / 5) * 5))
    h = d.get("hourly") or {}
    probs = [p for p in (h.get("precipitation_probability") or [])[:2] if p is not None]
    return {"minutos": minutos, "mm": round(total, 1), "prob": max(probs) if probs else None}


# ── decidir e falar (puro) ────────────────────────────────────────────────────
def decidir(r: dict | None, p: dict | None, antecedencia: int = 40) -> dict | None:
    """Junta radar e previsão: {'minutos', 'fonte', 'chovendo', 'vindo_de'} se vale avisar."""
    if r and r.get("chovendo"):
        return {"minutos": 0, "fonte": "radar", "chovendo": True, "vindo_de": ""}
    if r and r.get("minutos") is not None and r["minutos"] <= antecedencia:
        return {"minutos": r["minutos"], "fonte": "radar", "chovendo": False, "vindo_de": r.get("vindo_de", "")}
    if p and p.get("minutos") is not None and p["minutos"] <= antecedencia and (p.get("prob") is None or
                                                                               p["prob"] >= 50):
        return {"minutos": p["minutos"], "fonte": "previsão", "chovendo": p["minutos"] == 0, "vindo_de": ""}
    return None


def frase(dec: dict, varal: bool) -> str:
    if dec.get("chovendo"):
        return "Começou a chover aí! Se a roupa ainda está no varal, corre!" if varal else "Começou a chover aí."
    m = int(dec["minutos"])
    quando = "daqui a pouquinho" if m <= 7 else f"em uns {m} minutos"
    base = f"Vai chover {quando}"
    if dec.get("vindo_de"):
        base += f" (a chuva vem {dec['vindo_de']})"
    return base + (", melhor tirar a roupa do varal." if varal else ".")


# ── laço ──────────────────────────────────────────────────────────────────────
def varal_ligado() -> bool:
    return time.time() < _estado["varal_ate"]


def checar() -> tuple[dict | None, dict | None, dict | None, str]:
    onde = local()
    if not onde:
        return None, None, None, ""
    lat, lon, nome = onde
    r = radar(lat, lon) if _c().get("radar", True) else None
    p = previsao(lat, lon)
    try:
        ant = int(float(str(_c().get("antecedencia") or 40)))
    except ValueError:
        ant = 40
    _estado["ultima"] = {"radar": r, "previsao": p, "ts": time.time()}
    return decidir(r, p, ant), r, p, nome


def _avisar(texto: str, urgente: bool) -> None:
    try:
        from plugins._notificar import notificar
        notificar(None, texto, titulo="Chuva", etiqueta="CHUVA", prioridade="urgent" if urgente else "default")
    except Exception as e:
        print(f"[Chuva] {e}")


def _laco() -> None:
    time.sleep(100)
    while True:
        hora = datetime.now().hour
        c = _c()
        if 6 <= hora < 22 and (c.get("avisar", True) or varal_ligado()):
            try:
                dec, _r, _p, _n = checar()
                if dec is None:
                    _estado["chovendo"] = False
                elif not (dec["chovendo"] and _estado["chovendo"]) and time.time() - _estado["ultimo_aviso"] > (
                        3600 if not varal_ligado() else 1500):
                    _estado["ultimo_aviso"] = time.time()
                    _avisar(frase(dec, varal_ligado()), urgente=varal_ligado())
                if dec is not None:
                    _estado["chovendo"] = dec["chovendo"]
            except Exception as e:
                print(f"[Chuva] {e}")
        time.sleep(600)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="chuva").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "agora").lower()
    try:
        if acao == "varal":
            if str(p.get("valor") or "ligar").lower().startswith(("deslig", "recolh", "tir", "off", "não", "nao")):
                _estado["varal_ate"] = 0.0
                return "Modo varal desligado."
            fim = datetime.now().replace(hour=21, minute=0, second=0)
            if fim <= datetime.now():
                fim += timedelta(hours=12)
            _estado["varal_ate"] = fim.timestamp()
            _estado["ultimo_aviso"] = 0.0
            dec, _r, _p, nome = checar()
            agora = (" " + frase(dec, True)) if dec else " Por enquanto o céu está tranquilo."
            if not nome:
                return "Modo varal ligado, mas não sei onde você mora: coloque a cidade em ⚙ → Briefing ou as " \
                       "coordenadas em ⚙ → Chuva."
            return f"Modo varal ligado até as {fim.strftime('%H:%M')}: eu fico de olho no radar.{agora}"
        if acao == "status":
            c = _c()
            onde = local()
            return (f"Avisos de chuva {'ligados' if c.get('avisar', True) else 'desligados'}; modo varal "
                    f"{'ligado' if varal_ligado() else 'desligado'}; local: {onde[2] if onde else 'não configurado'}; "
                    f"radar {'ligado' if c.get('radar', True) else 'desligado'}.")
        if acao in ("desligar", "ligar"):
            salvar_cfg("chuva", {"avisar": acao == "ligar"})
            return f"Avisos de chuva {'ligados' if acao == 'ligar' else 'desligados'}."
        dec, r, prev, nome = checar()
        if not nome:
            return "Não sei onde você mora. Coloque a cidade em ⚙ → Briefing (ou as coordenadas em ⚙ → Chuva)."
        partes = []
        if r is not None:
            if r.get("chovendo"):
                partes.append("O radar mostra chuva em cima de você agora.")
            elif r.get("minutos") is not None:
                partes.append(f"Pelo radar, a chuva chega em uns {r['minutos']} minutos"
                              + (f", vindo {r['vindo_de']}" if r.get("vindo_de") else "") + ".")
            elif r.get("distancia_km") is not None:
                partes.append(f"O radar mostra chuva a uns {round(r['distancia_km'])} km, mas não vindo para cá.")
            else:
                partes.append("O radar não mostra chuva por perto.")
        if prev is not None:
            if prev.get("minutos") is not None:
                partes.append(f"A previsão dá chuva em uns {prev['minutos']} minutos ({prev['mm']} mm nas próximas "
                              f"2 horas{', ' + str(prev['prob']) + '% de chance' if prev.get('prob') is not None else ''}).")
            else:
                partes.append("A previsão não dá chuva nas próximas 2 horas"
                              + (f" ({prev['prob']}% de chance na hora)" if prev.get("prob") else "") + ".")
        if not partes:
            return "Não consegui olhar o radar nem a previsão agora (sem internet?)."
        texto = " ".join(partes)
        mostrar(player, f"CHUVA · {nome.upper()}", texto)
        return texto
    except Exception as e:
        return f"A chuva falhou: {e}"
