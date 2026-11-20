"""
Briefing BR — clima, cotação do dólar e do euro, e manchetes do Brasil.

Duas formas de usar:
    * Por voz: "Jarvis, me dá o briefing", "quanto está o dólar?",
      "como está o tempo?".
    * Automático: o resumo matinal que o JARVIS já faz ao ligar passa a incluir
      clima e cotação (veja `coletar_extras`, chamado pelo main.py). Com o
      "Iniciar com o PC" ligado, isso acontece toda vez que você liga o
      computador.

Fontes (gratuitas, sem cadastro):
    * Clima: Open-Meteo (open-meteo.com)
    * Câmbio: AwesomeAPI (economia.awesomeapi.com.br) — chave opcional
    * Notícias: o mesmo buscador de notícias que o JARVIS já usa
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PLUGIN = {
    "name": "briefing_br",
    "description": (
        "Brazilian briefing: current weather and today's forecast for the user's "
        "city, the US dollar and euro exchange rate in reais, and optionally "
        "Brazilian headlines. Use parte='tudo' for 'me dá o briefing' / 'resumo "
        "do dia', parte='cotacao' for 'quanto está o dólar/euro', parte='clima' "
        "for weather questions when no other city is named, parte='pc' for a one-line "
        "PC and internet health summary. Read the result naturally and briefly."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "parte": {"type": "STRING",
                      "description": "tudo | clima | cotacao | noticias | pc"},
            "cidade": {"type": "STRING",
                       "description": "Optional city; defaults to the configured one"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "briefing_br",
    "title": "Briefing (clima e dólar)",
    "fields": [
        {"key": "cidade", "label": "Sua cidade", "type": "text",
         "default": "", "placeholder": "ex.: Goiânia"},
        {"key": "no_resumo_matinal", "label": "Incluir clima e dólar no resumo ao ligar",
         "type": "toggle", "default": True},
        {"key": "pc_no_resumo", "label": "Incluir a saúde do PC e da internet no resumo",
         "type": "toggle", "default": True},
        {"key": "awesomeapi_token", "label": "Chave da AwesomeAPI (opcional)",
         "type": "password", "default": ""},
    ],
}

_TIMEOUT = 6
_UA = {"User-Agent": "JARVIS-BR/1.0"}

# Códigos de tempo da OMS usados pelo Open-Meteo.
_WMO = {
    0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina com geada",
    51: "garoa fraca", 53: "garoa", 55: "garoa forte",
    61: "chuva fraca", 63: "chuva", 65: "chuva forte",
    66: "chuva congelante", 67: "chuva congelante forte",
    71: "neve fraca", 73: "neve", 75: "neve forte", 77: "granizo fino",
    80: "pancadas de chuva fracas", 81: "pancadas de chuva",
    82: "pancadas de chuva fortes", 85: "pancadas de neve", 86: "neve forte",
    95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas fortes com granizo",
}


def _settings() -> dict:
    try:
        from memory.config_manager import get_plugin_config
        return get_plugin_config("briefing_br")
    except Exception:
        return {}


def _get_json(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _city(explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    city = str(_settings().get("cidade") or "").strip()
    if city:
        return city
    # Se você já contou sua cidade ao JARVIS, ela está na memória dele.
    try:
        from memory.memory_manager import load_memory
        ident = load_memory().get("identity", {})
        for k in ("city", "cidade", "location"):
            e = ident.get(k)
            v = (e.get("value") if isinstance(e, dict) else e) or ""
            if str(v).strip():
                return str(v).strip()
    except Exception:
        pass
    return ""


def clima(cidade: str = "") -> str:
    city = _city(cidade)
    if not city:
        return ("Não sei sua cidade. Diga qual é, ou configure em "
                "CONFIG. DE PLUGINS → Briefing.")
    try:
        geo = _get_json("https://geocoding-api.open-meteo.com/v1/search?"
                        + urllib.parse.urlencode({"name": city, "count": 1,
                                                  "language": "pt"}))
        hits = geo.get("results") or []
        if not hits:
            return f"Não encontrei a cidade {city}."
        lat, lon, nome = hits[0]["latitude"], hits[0]["longitude"], hits[0]["name"]
        fc = _get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        }))
        cur, day = fc.get("current", {}), fc.get("daily", {})
        agora = round(float(cur.get("temperature_2m")))
        desc = _WMO.get(int(cur.get("weather_code", -1)), "tempo indefinido")
        tmax = round(float(day["temperature_2m_max"][0]))
        tmin = round(float(day["temperature_2m_min"][0]))
        chuva = day.get("precipitation_probability_max", [None])[0]
        txt = f"Em {nome}: {agora}°C agora, {desc}. Hoje de {tmin}° a {tmax}°C"
        if chuva is not None:
            txt += f", {int(chuva)}% de chance de chuva"
        return txt + "."
    except Exception as e:
        return f"Não consegui ver o clima agora ({type(e).__name__})."


def cotacao() -> str:
    url = "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL"
    token = str(_settings().get("awesomeapi_token") or "").strip()
    if token:
        url += "?" + urllib.parse.urlencode({"token": token})
    try:
        data = _get_json(url)
        partes = []
        for key, nome in (("USDBRL", "Dólar"), ("EURBRL", "Euro")):
            q = data.get(key) or {}
            if not q.get("bid"):
                continue
            valor = f"R$ {float(q['bid']):.2f}".replace(".", ",")
            try:
                pct = float(q.get("pctChange", 0))
                var = (f", {'alta' if pct >= 0 else 'queda'} de "
                       f"{abs(pct):.2f}% hoje".replace(".", ","))
            except (TypeError, ValueError):
                var = ""
            partes.append(f"{nome} a {valor}{var}")
        return (". ".join(partes) + ".") if partes else "Cotação indisponível agora."
    except Exception as e:
        return f"Não consegui ver a cotação agora ({type(e).__name__})."


def noticias() -> str:
    try:
        from actions.web_search import _news
        return _news("principais notícias do Brasil hoje")
    except Exception as e:
        return f"Não consegui buscar as notícias ({type(e).__name__})."


def resumo_pc() -> str:
    """Uma frase sobre a saúde do PC e da internet, só com o que importa.

    Lê a telemetria (que já está medindo), então é instantâneo: nada de
    PowerShell nem varredura no meio do bom-dia."""
    try:
        from core import telemetria
        s = telemetria.get().snapshot()
    except Exception:
        return ""
    avisos = []
    for p in s.get("particoes", []):
        livre = 100 - float(p.get("pct") or 0)
        if livre < 10:
            avisos.append(f"o disco {p['ponto']} está com só {round(livre)}% livre")
    t = s.get("cpu_temp")
    if t is not None and t >= 80:
        avisos.append(f"a CPU está a {round(t)} graus")
    dias = (s.get("uptime") or 0) / 86400
    if dias >= 7:
        avisos.append(f"o PC está ligado há {int(dias)} dias sem reiniciar")
    ram = (s.get("ram") or {}).get("pct")
    if ram is not None and ram >= 85:
        avisos.append(f"a RAM já está em {round(ram)}%")
    net = s.get("internet")
    ping = ((s.get("ping") or {}).get("8.8.8.8") or {}).get("ms")
    if net is False:
        avisos.append("a internet está fora do ar")
    elif ping is not None and ping > 150:
        avisos.append(f"a internet está lenta (ping de {round(ping)} ms)")
    if avisos:
        return "PC: atenção, " + "; ".join(avisos) + "."
    internet = f", internet ok ({round(ping)} ms)" if ping is not None else ""
    return f"PC: tudo em ordem{internet}."


def coletar_extras() -> str:
    """Clima + cotação (+ saúde do PC) em paralelo, para o resumo do main.py.

    Devolve "" quando as opções estão desligadas, para o resumo seguir igual."""
    cfg_ = _settings()
    partes = []
    if cfg_.get("no_resumo_matinal", True):
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_clima, f_cot = ex.submit(clima), ex.submit(cotacao)
            partes = [f_clima.result(), f_cot.result()]
    if cfg_.get("pc_no_resumo", True):
        partes.append(resumo_pc())
    # Só o que deu certo: no resumo matinal, um erro de rede é pulado em
    # silêncio em vez de ser lido em voz alta.
    return "\n".join(p for p in partes if p and not p.startswith("Não "))


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    parte = str(p.get("parte") or "tudo").strip().lower()
    cidade = str(p.get("cidade") or "")
    if parte == "clima":
        return clima(cidade)
    if parte in ("cotacao", "cotação", "dolar", "dólar", "cambio", "câmbio"):
        return cotacao()
    if parte in ("noticias", "notícias"):
        return noticias()
    if parte in ("pc", "computador", "saude", "saúde"):
        return resumo_pc() or "Não consegui ler o estado do PC."
    with ThreadPoolExecutor(max_workers=3) as ex:
        a, b, c = ex.submit(clima, cidade), ex.submit(cotacao), ex.submit(noticias)
        resultado = "\n\n".join([x for x in (a.result(), b.result(), resumo_pc(), c.result()) if x])
    if player is not None:
        try:
            player.show_content("BRIEFING", resultado)
        except Exception:
            pass
    return resultado
