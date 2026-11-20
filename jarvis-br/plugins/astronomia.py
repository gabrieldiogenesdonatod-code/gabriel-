"""Astronomia (2.18): fase da lua, nascer e pôr do sol (Goiânia por padrão) e próximas luas cheias, tudo calculado offline."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from plugins._lote2 import P, numeros, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("astronomia", "Offline sky: moon phase and illumination, sunrise/sunset (default Goiânia), next full and new moons.",
           "lua | sol | hora_dourada | estacao | proximas_luas",
           "lua/sol/hora_dourada/estacao: data (default today). sol/hora_dourada: lat, lon, fuso (default Goiânia: -16.68, -49.25, -3). "
           "hora_dourada = best soft light to film/photograph.", "data lat lon fuso")

LUA_NOVA_REF = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
SINODICO = 29.530588853
FASES = [(1.84, "Lua nova"), (5.53, "Lua crescente (fina)"), (9.22, "Quarto crescente"), (12.91, "Crescente gibosa"),
         (16.61, "Lua cheia"), (20.30, "Minguante gibosa"), (23.99, "Quarto minguante"), (27.68, "Lua minguante (fina)"),
         (29.54, "Lua nova")]


def idade_lua(d: datetime) -> float:
    return ((d - LUA_NOVA_REF).total_seconds() / 86400) % SINODICO


def fase(d: datetime) -> tuple[str, int]:
    i = idade_lua(d)
    nome = next(n for lim, n in FASES if i < lim)
    luz = round((1 - math.cos(2 * math.pi * i / SINODICO)) / 2 * 100)
    return nome, luz


def sol(d: date, lat: float, lon: float, fuso: float, zenite: float = 90.833) -> tuple[str, str]:
    """Algoritmo da NOAA simplificado (precisão de ~1-2 minutos)."""
    n = d.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                    - 0.040849 * math.sin(2 * g))
    dec = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + \
        0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)
    la = math.radians(lat)
    ha = math.degrees(math.acos(math.cos(math.radians(zenite)) / (math.cos(la) * math.cos(dec)) - math.tan(la) * math.tan(dec)))

    def hm(minutos):
        minutos %= 1440
        return f"{int(minutos // 60):02d}:{int(minutos % 60):02d}"
    nasce = 720 - 4 * (lon + ha) - eqt + fuso * 60
    poe = 720 - 4 * (lon - ha) - eqt + fuso * 60
    return hm(nasce), hm(poe)


def estacao(d: date, lat: float = -16.68) -> str:
    """Estação pela data (datas médias dos solstícios e equinócios); invertida no hemisfério norte."""
    md = (d.month, d.day)
    i = 0 if md >= (12, 21) or md < (3, 20) else 1 if md < (6, 21) else 2 if md < (9, 22) else 3
    return ["verão", "outono", "inverno", "primavera"][i if lat < 0 else (i + 2) % 4]


def proximas(agora: datetime, alvo: float, n: int = 3) -> list[datetime]:
    i = idade_lua(agora)
    falta = (alvo - i) % SINODICO
    return [agora + timedelta(days=falta + k * SINODICO) for k in range(n)]


def _go(p, pl):
    a = str(p.get("action")).lower()
    d = ler_data(p.get("data")) if p.get("data") else date.today()
    meio_dia = datetime(d.year, d.month, d.day, 15, tzinfo=timezone.utc)
    if a == "lua":
        nome, luz = fase(meio_dia)
        return f"{nome}, {luz}% iluminada."
    if a == "sol":
        x = lambda k, dft: (numeros(p.get(k)) or [dft])[0]  # noqa: E731
        lat, lon, fz = x("lat", -16.68), x("lon", -49.25), x("fuso", -3)
        n, po = sol(d, lat, lon, fz)
        return f"Sol nasce às {n} e se põe às {po}."
    if a in ("hora_dourada", "estacao"):
        x = lambda k, dft: (numeros(p.get(k)) or [dft])[0]  # noqa: E731
        lat, lon, fz = x("lat", -16.68), x("lon", -49.25), x("fuso", -3)
        if a == "estacao":
            return f"Em {d:%d/%m} é {estacao(d, lat)}."
        (n, po), (m6, t6) = sol(d, lat, lon, fz), sol(d, lat, lon, fz, 84)
        return f"Hora dourada: de manhã das {n} às {m6}, e à tarde das {t6} às {po}. É a luz mais bonita para gravar e fotografar."
    agora = datetime.now(timezone.utc)
    cheias = ", ".join(f"{x - timedelta(hours=3):%d/%m}" for x in proximas(agora, SINODICO / 2))
    novas = ", ".join(f"{x - timedelta(hours=3):%d/%m}" for x in proximas(agora, 0.0))
    return f"Luas cheias: {cheias}. Luas novas: {novas}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("lua sol hora_dourada estacao proximas_luas".split(), _go), player)
