"""
"Neste dia" (fork PT-BR 2.7). Tudo software, grátis.

"Senhor, há um mês o senhor estava criando a versão 1.0 do J.A.R.V.I.S BR."
Ele relembra o que você fez nesta mesma data — há uma semana, um mês, três
meses, seis meses, um ano… — pelo diário, pela linha do tempo do PC, pelo
CHANGELOG do projeto, pelas conquistas (gamificação) e pelo seu catálogo de
filmes. Uma vez por dia, ele comenta sozinho (só quando você não está ocupado).

    "Jarvis, neste dia"               → o que tem para hoje
    "O que eu fiz em 28 de outubro?"  → uma data específica
"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime, timedelta

from plugins._comum import BASE, MEMORIA, cfg, gravar_json, ler_json, mostrar, sim

PLUGIN = {
    "name": "neste_dia",
    "brief": "'On this day': what the user did on this same date a week, month or year ago (diary, PC timeline, "
             "project changelog, achievements, movies).",
    "description": (
        "On this day memories. action: 'hoje' (memories for today's date: 1 week, 1/3/6 months, 1+ years ago), "
        "'data' (data: a specific date like '28/10' or '2026-10-28': what happened that day)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "data": {"type": "STRING"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "neste_dia",
    "title": "Neste dia",
    "fields": [
        {"key": "diario", "label": "Lembrar sozinho uma vez por dia", "type": "toggle", "default": True},
        {"key": "hora", "label": "A partir de", "type": "text", "default": "10:00"},
    ],
}

ARQ = MEMORIA / "neste_dia.json"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
_iniciou = threading.Event()


def menos_meses(d: date, meses: int) -> date:
    """Pura: a mesma data N meses antes (31/03 − 1 mês = 28 ou 29/02)."""
    ano, mes = d.year, d.month - meses
    while mes <= 0:
        mes += 12
        ano -= 1
    for dia in (d.day, 30, 29, 28):
        try:
            return date(ano, mes, min(d.day, dia))
        except ValueError:
            continue
    return date(ano, mes, 28)


def datas_alvo(hoje: date, anos: int = 5) -> list[tuple[str, date]]:
    """Pura: as datas que valem lembrar hoje."""
    alvo = [("há uma semana", hoje - timedelta(days=7)), ("há um mês", menos_meses(hoje, 1)),
            ("há três meses", menos_meses(hoje, 3)), ("há seis meses", menos_meses(hoje, 6))]
    for a in range(1, anos + 1):
        alvo.append(("há um ano" if a == 1 else f"há {a} anos", menos_meses(hoje, 12 * a)))
    return alvo


def ler_data(texto: str, hoje: date | None = None) -> date | None:
    """Pura: '28/10', '28/10/2026', '2026-10-28', '28 de outubro', 'ontem'. Data impossível → None."""
    try:
        return _ler_data(texto, hoje)
    except ValueError:
        return None


def _ler_data(texto: str, hoje: date | None = None) -> date | None:
    hoje = hoje or date.today()
    t = str(texto or "").lower().strip()
    if not t:
        return None
    if "anteontem" in t:
        return hoje - timedelta(days=2)
    if "ontem" in t:
        return hoje - timedelta(days=1)
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        ano = int(m[3]) if m[3] else hoje.year
        ano = ano + 2000 if ano < 100 else ano
        d = date(ano, int(m[2]), int(m[1]))
        return d if m[3] or d <= hoje else date(ano - 1, d.month, d.day)
    m = re.search(r"(\d{1,2}) de (" + "|".join(MESES).replace("ç", "[çc]") + r")(?: de (\d{4}))?", t)
    if m:
        mes = next(i for i, n in enumerate(MESES) if n.replace("ç", "c") == m[2].replace("ç", "c")) + 1
        d = date(int(m[3]) if m[3] else hoje.year, mes, int(m[1]))
        return d if m[3] or d <= hoje else date(d.year - 1, d.month, d.day)
    return None


def versoes_changelog(texto: str) -> dict[str, list[tuple[str, str]]]:
    """Pura: {data: [(versão, primeira novidade)]} a partir do CHANGELOG.md."""
    saida: dict[str, list[tuple[str, str]]] = {}
    blocos = re.split(r"(?m)^## ", texto)
    for b in blocos[1:]:
        m = re.match(r"\[([^\]]+)\]\s*[—-]\s*(\d{4}-\d{2}-\d{2})", b)
        if not m:
            continue
        item = re.search(r"(?m)^- (.+)$", b)
        resumo = re.sub(r"[*`]", "", item.group(1))[:160] if item else ""
        saida.setdefault(m[2], []).append((m[1], resumo))
    return saida


def do_dia(d: date) -> list[dict]:
    """O que existe registrado num dia (lê as fontes; cada uma pode faltar)."""
    iso = d.isoformat()
    achados = []
    try:
        cl = (BASE / "CHANGELOG.md").read_text(encoding="utf-8")
        for versao, resumo in versoes_changelog(cl).get(iso, []):
            achados.append({"fonte": "projeto", "texto": f"lançou a versão {versao} do J.A.R.V.I.S BR"
                                                        + (f" ({resumo})" if resumo else "")})
    except Exception:
        pass
    try:
        from plugins import diario
        for e in diario.entradas():
            if e.get("data") == iso and e.get("texto"):
                achados.append({"fonte": "diário", "texto": str(e["texto"])[:300]})
    except Exception:
        pass
    try:
        from plugins import linha_do_tempo as L
        ini = datetime.combine(d, datetime.min.time()).timestamp()
        r = L.resumo(ini, ini + 86400)
        f = L.frase(r, 3) if r else ""
        if f and "nada" not in f.lower():
            achados.append({"fonte": "PC", "texto": f})
    except Exception:
        pass
    try:
        from plugins import gamificacao
        for h in gamificacao.estado().get("historico", []):
            if datetime.fromtimestamp(h["ts"]).date() == d and h.get("xp", 0) >= 50:
                achados.append({"fonte": "conquista", "texto": h.get("motivo", "")})
    except Exception:
        pass
    try:
        from plugins import cinema
        for item in cinema.dados().get("catalogo", []):
            if iso in (item.get("historico") or []):
                achados.append({"fonte": "cinema", "texto": f"assistiu {item['titulo']}"})
    except Exception:
        pass
    return achados


def montar(lembrancas: list[tuple[str, date, list[dict]]]) -> str:
    """Pura: o texto falado."""
    partes = []
    for rotulo, _d, achados in lembrancas:
        if not achados:
            continue
        txt = "; ".join(a["texto"] for a in achados[:3])
        partes.append(f"{rotulo.capitalize()}, o senhor {txt}" if achados[0]["fonte"] in ("projeto", "cinema")
                      else f"{rotulo.capitalize()} ({achados[0]['fonte']}): {txt}")
    return ". ".join(partes) + ("." if partes else "")


def hoje_texto(hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    lemb = [(r, d, do_dia(d)) for r, d in datas_alvo(hoje)]
    txt = montar(lemb)
    if not txt:
        return "Nada registrado nesta mesma data em semanas, meses ou anos anteriores — ainda."
    mostrar(None, "NESTE DIA", txt)
    return "Neste dia: " + txt


def data_texto(texto: str) -> str:
    d = ler_data(texto)
    if not d:
        return "Não entendi a data. Exemplo: '28/10' ou '28 de outubro'."
    achados = do_dia(d)
    if not achados:
        return f"Não tenho nada registrado em {d.strftime('%d/%m/%Y')}."
    return f"Em {d.day} de {MESES[d.month - 1]} de {d.year}: " + "; ".join(
        f"({a['fonte']}) {a['texto']}" for a in achados[:6]) + "."


def _laco(player) -> None:
    time.sleep(180)
    while True:
        try:
            c = cfg("neste_dia", PLUGIN_SETTINGS)
            estado = ler_json(ARQ, {}) or {}
            hoje = date.today().isoformat()
            if sim(c.get("diario", True)) and estado.get("ultimo") != hoje and \
                    datetime.now().strftime("%H:%M") >= str(c.get("hora") or "10:00"):
                from core import estado_mundo
                if estado_mundo.pode_falar("normal"):
                    estado["ultimo"] = hoje
                    gravar_json(ARQ, estado)
                    lemb = [(r, d, do_dia(d)) for r, d in datas_alvo(date.today())]
                    txt = montar(lemb)
                    if txt:
                        from plugins._notificar import notificar
                        notificar(player, "Neste dia: " + txt, titulo="Neste dia", etiqueta="neste_dia")
        except Exception as e:
            print(f"[NesteDia] {e}")
        time.sleep(900)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="neste_dia").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "hoje").lower()
    try:
        if acao == "data" or p.get("data"):
            return data_texto(str(p.get("data") or ""))
        return hoje_texto()
    except Exception as e:
        return f"Neste dia falhou: {e}"
