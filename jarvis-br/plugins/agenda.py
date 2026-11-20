"""
Agenda sincronizada + hora de sair (fork PT-BR 2.16, ideias 9 e 10).

    "Jarvis, o que tenho hoje?" / "e amanhã?" / "essa semana?"
    "Jarvis, marca dentista quinta às 14h na Rua 10, Setor Oeste"
    "Jarvis, acha um horário livre de 1 hora amanhã à tarde"
    "Jarvis, que horas eu preciso sair para o dentista?"

DE ONDE VEM A AGENDA (pode usar as três juntas)
    1. Google Agenda, só leitura, sem login: no Google Agenda → Configurações da
       agenda → "Endereço secreto no formato iCal". Cole em ⚙ → Agenda.
    2. Google Agenda com leitura e ESCRITA: coloque o credentials.json (OAuth,
       app para computador) em config/google_credentials.json; na primeira vez
       abre o navegador para você autorizar. Aí "marca…" vai direto para o Google.
    3. Agenda local: memory/agenda.ics (sempre funciona; dá para importar no
       Google ou no Outlook).

HORA DE SAIR
    Com o seu endereço de casa (⚙ → Agenda) e o local do compromisso, ele calcula
    a rota de carro (OpenStreetMap: Nominatim + OSRM, grátis), soma o trânsito
    (fator do horário de pico, ou o Google Routes com trânsito real se você
    colocar uma chave) e uma folga, e AVISA sozinho na hora de sair:
    "Senhor, saia agora para chegar às 14h no dentista."
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from plugins import _web
from plugins._comum import CONFIG, MEMORIA, cfg, mostrar, plugin_ligado

PLUGIN = {
    "name": "agenda",
    "brief": "Calendar (Google iCal/OAuth or local): list, add events, find free time, when to leave (route + traffic).",
    "description": (
        "Calendar. action='listar' with quando = hoje | amanha | semana | YYYY-MM-DD. action='marcar' with titulo, "
        "inicio (YYYY-MM-DD HH:MM, resolve 'quinta às 14h' yourself to a date), optional duracao (minutes, default 60) and "
        "local (address). action='livre' with duracao (minutes), optional dia (YYYY-MM-DD) and periodo (manha | tarde | "
        "noite | dia) finds free slots. action='sair' with optional titulo (default: next event with a place) tells when "
        "to leave. action='apagar' with titulo removes a LOCAL event."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "listar | marcar | livre | sair | apagar"},
                       "quando": {"type": "STRING"}, "titulo": {"type": "STRING"}, "inicio": {"type": "STRING"},
                       "duracao": {"type": "NUMBER"}, "local": {"type": "STRING"}, "dia": {"type": "STRING"},
                       "periodo": {"type": "STRING"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "agenda",
    "title": "Agenda",
    "fields": [
        {"key": "ical", "label": "Endereços iCal (Google Agenda → Endereço secreto), um por linha", "type": "text",
         "default": ""},
        {"key": "casa", "label": "Seu endereço (para a hora de sair)", "type": "text", "default": ""},
        {"key": "folga_min", "label": "Chegar com quantos minutos de folga", "type": "number", "default": 10},
        {"key": "google_routes_key", "label": "Chave do Google Routes (trânsito real; opcional)", "type": "password",
         "default": ""},
        {"key": "avisar_sair", "label": "Avisar sozinho a hora de sair", "type": "toggle", "default": True},
        {"key": "horario_util", "label": "Horário para achar livre (ex.: 08:00-20:00)", "type": "text",
         "default": "08:00-20:00"},
    ],
}

ARQ_LOCAL = MEMORIA / "agenda.ics"
ARQ_CRED = CONFIG / "google_credentials.json"
ARQ_TOKEN = CONFIG / "google_token_agenda.json"
_cache = {"t": 0.0, "eventos": []}
_avisados: set[str] = set()
_rotas: dict[str, tuple[float, float]] = {}


# ── ICS ────────────────────────────────────────────────────────────────────────
def _data_ics(valor: str) -> datetime:
    v = valor.strip()
    if v.endswith("Z"):
        from datetime import timezone
        return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    if "T" in v:
        return datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
    return datetime.strptime(v[:8], "%Y%m%d")


def ler_ics(texto: str, de: datetime, ate: datetime) -> list[dict]:
    """Eventos entre de/ate; entende repetição diária/semanal/mensal simples (pura)."""
    texto = re.sub(r"\r?\n[ \t]", "", texto)                    # linhas dobradas
    eventos = []
    for bloco in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", texto, re.S):
        campos: dict[str, str] = {}
        for linha in bloco.strip().splitlines():
            if ":" not in linha:
                continue
            k, v = linha.split(":", 1)
            campos.setdefault(k.split(";")[0].upper(), v)
        if "DTSTART" not in campos:
            continue
        try:
            ini = _data_ics(campos["DTSTART"])
            fim = _data_ics(campos["DTEND"]) if "DTEND" in campos else ini + timedelta(hours=1)
        except ValueError:
            continue
        dia_todo = "T" not in campos["DTSTART"]
        dur = fim - ini
        base = {"titulo": _desescapar(campos.get("SUMMARY", "(sem título)")),
                "local": _desescapar(campos.get("LOCATION", "")), "dia_todo": dia_todo, "uid": campos.get("UID", "")}
        for i in _ocorrencias(ini, campos.get("RRULE", ""), de, ate):
            if i + dur >= de and i <= ate:
                eventos.append({**base, "inicio": i, "fim": i + dur})
    return sorted(eventos, key=lambda e: e["inicio"])


def _desescapar(t: str) -> str:
    return t.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").strip()


def _ocorrencias(ini: datetime, rrule: str, de: datetime, ate: datetime, limite: int = 800):
    if not rrule:
        yield ini
        return
    r = dict(p.split("=", 1) for p in rrule.split(";") if "=" in p)
    freq, passo = r.get("FREQ"), int(r.get("INTERVAL", 1))
    ate_regra = _data_ics(r["UNTIL"]) if "UNTIL" in r else None
    contagem = int(r["COUNT"]) if "COUNT" in r else None
    dias_semana = [("MO", "TU", "WE", "TH", "FR", "SA", "SU").index(d[-2:]) for d in r.get("BYDAY", "").split(",")
                   if d[-2:] in ("MO", "TU", "WE", "TH", "FR", "SA", "SU")]
    n, atual = 0, ini
    for _ in range(limite * 7):
        if (ate_regra and atual > ate_regra) or atual > ate or (contagem is not None and n >= contagem):
            return
        candidatos = [atual]
        if freq == "WEEKLY" and dias_semana:
            seg = atual - timedelta(days=atual.weekday())
            candidatos = [seg + timedelta(days=d) for d in sorted(dias_semana)]
        for c in candidatos:
            if c < ini or (ate_regra and c > ate_regra) or (contagem is not None and n >= contagem):
                continue
            n += 1
            if c >= de - timedelta(days=1):
                yield c
        if freq == "DAILY":
            atual += timedelta(days=passo)
        elif freq == "WEEKLY":
            atual += timedelta(weeks=passo)
        elif freq == "MONTHLY":
            m = atual.month - 1 + passo
            try:
                atual = atual.replace(year=atual.year + m // 12, month=m % 12 + 1)
            except ValueError:
                atual += timedelta(days=31 * passo)
        elif freq == "YEARLY":
            try:
                atual = atual.replace(year=atual.year + passo)
            except ValueError:
                atual += timedelta(days=365)
        else:
            return


def _esc(t: str) -> str:
    return str(t).replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def evento_ics(titulo: str, ini: datetime, fim: datetime, local: str = "") -> str:
    return ("BEGIN:VEVENT\r\n" f"UID:{uuid.uuid4()}@jarvis-br\r\n" f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}\r\n"
            f"DTSTART:{ini:%Y%m%dT%H%M%S}\r\n" f"DTEND:{fim:%Y%m%dT%H%M%S}\r\n" f"SUMMARY:{_esc(titulo)}\r\n"
            + (f"LOCATION:{_esc(local)}\r\n" if local else "") + "END:VEVENT\r\n")


def _local_ler() -> str:
    return ARQ_LOCAL.read_text(encoding="utf-8") if ARQ_LOCAL.exists() else ""


def _local_gravar(eventos_txt: str) -> None:
    ARQ_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    ARQ_LOCAL.write_text("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//JARVIS BR//Agenda//PT\r\n" + eventos_txt
                         + "END:VCALENDAR\r\n", encoding="utf-8")


def _local_eventos_txt() -> str:
    return "".join(re.findall(r"BEGIN:VEVENT.*?END:VEVENT\r?\n", _local_ler(), re.S))


# ── Google (opcional) ─────────────────────────────────────────────────────────
def _google():
    if not ARQ_CRED.exists():
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        return None
    escopos = ["https://www.googleapis.com/auth/calendar"]
    cred = Credentials.from_authorized_user_file(str(ARQ_TOKEN), escopos) if ARQ_TOKEN.exists() else None
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            cred = InstalledAppFlow.from_client_secrets_file(str(ARQ_CRED), escopos).run_local_server(port=0)
        ARQ_TOKEN.write_text(cred.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=cred, cache_discovery=False)


def _google_eventos(de: datetime, ate: datetime) -> list[dict]:
    srv = _google()
    if srv is None:
        return []
    from datetime import timezone
    tz = datetime.now(timezone.utc).astimezone().tzinfo
    r = srv.events().list(calendarId="primary", timeMin=de.replace(tzinfo=tz).isoformat(),
                          timeMax=ate.replace(tzinfo=tz).isoformat(), singleEvents=True, orderBy="startTime",
                          maxResults=250).execute()
    saida = []
    for e in r.get("items", []):
        s, f = e.get("start", {}), e.get("end", {})
        dia_todo = "date" in s
        ini = datetime.fromisoformat(s.get("dateTime") or s["date"]).astimezone().replace(tzinfo=None) \
            if not dia_todo else datetime.fromisoformat(s["date"])
        fim = datetime.fromisoformat(f.get("dateTime") or f["date"]).astimezone().replace(tzinfo=None) \
            if not dia_todo else datetime.fromisoformat(f["date"])
        saida.append({"titulo": e.get("summary", "(sem título)"), "local": e.get("location", ""), "inicio": ini,
                      "fim": fim, "dia_todo": dia_todo, "uid": e.get("id", ""), "google": True})
    return saida


# ── todas as fontes ───────────────────────────────────────────────────────────
def eventos(de: datetime, ate: datetime) -> list[dict]:
    todos = ler_ics(_local_ler(), de, ate)
    usou_google = False
    try:
        g = _google_eventos(de, ate)
        usou_google = bool(ARQ_CRED.exists())
        todos += g
    except Exception as e:
        print(f"[Agenda] Google: {e}")
    if not usou_google:
        for url in str(cfg("agenda", PLUGIN_SETTINGS).get("ical") or "").split():
            try:
                if time.time() - _cache["t"] > 300 or not _cache.get(url):
                    status, dados, _t = _web._req("GET", url.replace("webcal://", "https://"), timeout=20)
                    _cache[url] = dados.decode("utf-8", "replace") if status < 400 else ""
                    _cache["t"] = time.time()
                todos += ler_ics(_cache[url], de, ate)
            except Exception as e:
                print(f"[Agenda] iCal: {e}")
    vistos, unicos = set(), []
    for e in sorted(todos, key=lambda x: x["inicio"]):
        k = (e["titulo"].lower(), e["inicio"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(e)
    return unicos


def livres(evts: list[dict], dia: date, duracao_min: int, janela: tuple[str, str] = ("08:00", "20:00"),
           periodo: str = "dia", agora: datetime | None = None) -> list[tuple[datetime, datetime]]:
    """Intervalos livres de pelo menos `duracao_min` no dia (pura)."""
    faixas = {"manha": ("08:00", "12:00"), "tarde": ("12:00", "18:00"), "noite": ("18:00", "22:00")}
    a, b = faixas.get(periodo, janela)
    ini = datetime.combine(dia, datetime.strptime(a, "%H:%M").time())
    fim = datetime.combine(dia, datetime.strptime(b, "%H:%M").time())
    if agora and agora.date() == dia:
        ini = max(ini, (agora + timedelta(minutes=15 - agora.minute % 15)).replace(second=0, microsecond=0))
    ocupados = sorted((max(e["inicio"], ini), min(e["fim"], fim)) for e in evts
                      if not e.get("dia_todo") and e["fim"] > ini and e["inicio"] < fim)
    saida, cursor = [], ini
    for o_ini, o_fim in ocupados:
        if (o_ini - cursor).total_seconds() >= duracao_min * 60:
            saida.append((cursor, o_ini))
        cursor = max(cursor, o_fim)
    if (fim - cursor).total_seconds() >= duracao_min * 60:
        saida.append((cursor, fim))
    return saida


# ── rota e trânsito ───────────────────────────────────────────────────────────
def fator_transito(quando: datetime) -> float:
    """Multiplicador do tempo de carro pelo horário (estimativa, sem dado real) (pura)."""
    h = quando.hour + quando.minute / 60
    if quando.weekday() >= 5:
        return 1.1
    if 6.5 <= h <= 9 or 17 <= h <= 19.5:
        return 1.5
    if 11.5 <= h <= 14:
        return 1.25
    return 1.12


def _geocodificar(endereco: str) -> tuple[float, float]:
    r = _web.get_json("https://nominatim.openstreetmap.org/search",
                      {"format": "json", "limit": 1, "countrycodes": "br", "q": endereco})
    if not r:
        raise ValueError(f"não achei o endereço '{endereco}' no mapa")
    return float(r[0]["lat"]), float(r[0]["lon"])


def tempo_viagem(origem: str, destino: str, chegada: datetime) -> tuple[float, str]:
    """(minutos, como foi calculado)."""
    chave = str(cfg("agenda", PLUGIN_SETTINGS).get("google_routes_key") or "").strip()
    if chave:
        try:
            r = _web.post_json("https://routes.googleapis.com/directions/v2:computeRoutes",
                               {"origin": {"address": origem}, "destination": {"address": destino},
                                "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE"},
                               {"X-Goog-Api-Key": chave, "X-Goog-FieldMask": "routes.duration"})
            seg = float(str(r["routes"][0]["duration"]).rstrip("s"))
            return seg / 60, "Google, com trânsito agora"
        except Exception as e:
            print(f"[Agenda] Google Routes: {e}")
    k = f"{origem}|{destino}"
    if k not in _rotas:
        la1, lo1 = _geocodificar(origem)
        la2, lo2 = _geocodificar(destino)
        r = _web.get_json(f"https://router.project-osrm.org/route/v1/driving/{lo1},{la1};{lo2},{la2}",
                          {"overview": "false"})
        _rotas[k] = (float(r["routes"][0]["duration"]) / 60, float(r["routes"][0]["distance"]) / 1000)
    minutos, km = _rotas[k]
    f = fator_transito(chegada)
    return minutos * f, f"{km:.0f} km de carro, trânsito estimado pelo horário (×{f:.2f})".replace(".", ",")


def hora_de_sair(evento: dict) -> tuple[datetime, float, str]:
    c = cfg("agenda", PLUGIN_SETTINGS)
    casa = str(c.get("casa") or "").strip()
    if not casa:
        raise ValueError("Preciso do seu endereço de casa em ⚙ → Agenda.")
    if not evento.get("local"):
        raise ValueError(f"'{evento['titulo']}' não tem endereço.")
    minutos, como = tempo_viagem(casa, evento["local"], evento["inicio"])
    folga = float(c.get("folga_min") or 10)
    return evento["inicio"] - timedelta(minutes=minutos + folga), minutos, como


# ── aviso automático ──────────────────────────────────────────────────────────
def _laco(player) -> None:
    while True:
        time.sleep(120)
        c = cfg("agenda", PLUGIN_SETTINGS)
        if not plugin_ligado("agenda") or not c.get("avisar_sair", True) or not c.get("casa"):
            continue
        try:
            agora = datetime.now()
            for e in eventos(agora, agora + timedelta(hours=4)):
                chave = f"{e['titulo']}|{e['inicio']}"
                if not e.get("local") or e.get("dia_todo") or chave in _avisados or e["inicio"] < agora:
                    continue
                sair, minutos, _ = hora_de_sair(e)
                if agora >= sair - timedelta(minutes=2):
                    _avisados.add(chave)
                    from plugins._notificar import notificar
                    notificar(player, f"Senhor, saia agora para chegar às {e['inicio']:%H:%M} em {e['titulo']} "
                                      f"(uns {minutos:.0f} min de carro).", "Hora de sair")
        except Exception as ex:
            print(f"[Agenda] aviso: {ex}")


def on_session_start(player) -> None:
    threading.Thread(target=_laco, args=(player,), daemon=True, name="agenda_sair").start()


# ── comandos ──────────────────────────────────────────────────────────────────
DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def _intervalo(quando: str) -> tuple[datetime, datetime, str]:
    hoje = datetime.combine(date.today(), datetime.min.time())
    q = (quando or "hoje").lower()
    if q.startswith("amanh"):
        return hoje + timedelta(days=1), hoje + timedelta(days=2), "amanhã"
    if "semana" in q:
        return hoje, hoje + timedelta(days=7), "nos próximos 7 dias"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", q):
        d = datetime.strptime(q, "%Y-%m-%d")
        return d, d + timedelta(days=1), f"em {d:%d/%m}"
    return hoje, hoje + timedelta(days=1), "hoje"


def _fmt(e: dict) -> str:
    if e.get("dia_todo"):
        return f"{DIAS[e['inicio'].weekday()][:3]} {e['inicio']:%d/%m} (dia todo) {e['titulo']}"
    return f"{DIAS[e['inicio'].weekday()][:3]} {e['inicio']:%d/%m %H:%M}–{e['fim']:%H:%M} {e['titulo']}" + \
        (f" · {e['local']}" if e.get("local") else "")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    try:
        if a == "listar":
            de, ate, rotulo = _intervalo(str(p.get("quando") or "hoje"))
            evs = eventos(de, ate)
            if not evs:
                return f"Nada na agenda {rotulo}."
            mostrar(player, "AGENDA", "\n".join(_fmt(e) for e in evs))
            return f"{len(evs)} compromisso(s) {rotulo}: " + "; ".join(
                (f"{e['titulo']} às {e['inicio']:%H:%M}" if not e.get("dia_todo") else e["titulo"]) for e in evs[:5]) + "."
        if a == "marcar":
            titulo = str(p.get("titulo") or "").strip()
            ini = datetime.strptime(str(p.get("inicio") or "").strip()[:16], "%Y-%m-%d %H:%M")
            fim = ini + timedelta(minutes=float(p.get("duracao") or 60))
            local = str(p.get("local") or "").strip()
            conflito = [e for e in eventos(ini - timedelta(hours=1), fim + timedelta(hours=1))
                        if not e.get("dia_todo") and e["inicio"] < fim and e["fim"] > ini]
            onde = "na agenda local"
            srv = _google() if ARQ_CRED.exists() else None
            if srv is not None:
                corpo = {"summary": titulo, "location": local,
                         "start": {"dateTime": ini.astimezone().isoformat()}, "end": {"dateTime": fim.astimezone().isoformat()}}
                srv.events().insert(calendarId="primary", body=corpo).execute()
                onde = "no Google Agenda"
            else:
                _local_gravar(_local_eventos_txt() + evento_ics(titulo, ini, fim, local))
            msg = f"Marquei {titulo} em {DIAS[ini.weekday()]} {ini:%d/%m} às {ini:%H:%M} {onde}."
            if conflito:
                msg += f" Atenção: bate com {conflito[0]['titulo']} às {conflito[0]['inicio']:%H:%M}."
            return msg
        if a == "apagar":
            alvo = str(p.get("titulo") or "").lower()
            blocos = re.findall(r"BEGIN:VEVENT.*?END:VEVENT\r?\n", _local_ler(), re.S)
            restam = [b for b in blocos if alvo not in b.lower()]
            if len(restam) == len(blocos):
                return "Não achei esse compromisso na agenda local (os do Google eu não apago por aqui)."
            _local_gravar("".join(restam))
            return f"Apaguei {len(blocos) - len(restam)} compromisso(s) da agenda local."
        if a == "livre":
            dia = datetime.strptime(str(p["dia"]), "%Y-%m-%d").date() if p.get("dia") else date.today()
            dur = int(p.get("duracao") or 60)
            janela = tuple(str(cfg("agenda", PLUGIN_SETTINGS).get("horario_util") or "08:00-20:00").split("-"))[:2]
            d0 = datetime.combine(dia, datetime.min.time())
            ls = livres(eventos(d0, d0 + timedelta(days=1)), dia, dur, janela, str(p.get("periodo") or "dia").lower(),
                        datetime.now())
            if not ls:
                return f"Não tem {dur} minutos livres nesse período em {dia:%d/%m}."
            return f"Livre em {dia:%d/%m}: " + ", ".join(f"das {a_:%H:%M} às {b_:%H:%M}" for a_, b_ in ls[:4]) + "."
        if a == "sair":
            agora = datetime.now()
            evs = [e for e in eventos(agora, agora + timedelta(days=2)) if e.get("local") and not e.get("dia_todo")]
            alvo = str(p.get("titulo") or "").lower()
            e = next((x for x in evs if alvo in x["titulo"].lower()), None) if alvo else (evs[0] if evs else None)
            if not e:
                return "Não achei compromisso com endereço nos próximos 2 dias."
            sair, minutos, como = hora_de_sair(e)
            falta = (sair - agora).total_seconds() / 60
            quando = "agora" if falta <= 1 else f"às {sair:%H:%M} (daqui a {falta:.0f} min)"
            return (f"Para chegar às {e['inicio']:%H:%M} em {e['titulo']}, saia {quando}. A viagem leva uns "
                    f"{minutos:.0f} minutos ({como}).")
        return "Use listar, marcar, livre, sair ou apagar."
    except ValueError as e:
        return str(e) if str(e) else "Não entendi a data. Use AAAA-MM-DD HH:MM."
    except _web.ErroWeb as e:
        return f"Não consegui calcular a rota agora: {e}."
    except Exception as e:
        return f"A agenda falhou: {e}"
