"""
Diário por entrevista (fork PT-BR 2.4).

À noite (21h30, ajustável) o JARVIS pergunta "como foi o seu dia?" e conversa
um pouquinho — o que foi bom, o que foi difícil, o que você quer lembrar.
Você conta FALANDO. Ele guarda um resumo do dia (com as suas palavras) e
liga tudo na memória em grafo. Ele só pergunta se você estiver no PC e não
estiver jogando, numa chamada ou numa live; uma vez por dia.

Depois dá para perguntar:
    "Jarvis, o que eu estava fazendo em novembro do ano passado?"
    "Jarvis, como foi a semana passada?"     "Jarvis, o que eu contei no dia 12/03?"

Também:
    "Jarvis, vamos fazer o diário"  (entrevista agora)     "Jarvis, hoje não" (pula o de hoje)
    "Jarvis, anota no diário: …"     (sem entrevista)

Fica em memory/diario.json, só no seu PC.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, cfg, falar, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "diario",
    "brief": "Interview diary: each night asks how the day was, keeps a summary; answers 'what was I doing in …?'.",
    "description": (
        "Spoken diary. action='entrevista' starts tonight's interview now (ask how his day was, then at most 2 short "
        "follow-ups; when he finishes or says that's all, call action='encerrar'); 'encerrar' saves the day; 'contar' "
        "with texto saves an entry directly; 'consultar' with pergunta answers about a past period from the diary "
        "and memory (e.g. 'o que eu estava fazendo em novembro do ano passado?', 'como foi a semana passada?'); "
        "'pular' skips today's interview; 'listar' shows the latest days."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "entrevista | encerrar | contar | consultar | pular | listar"},
                       "texto": {"type": "STRING"}, "pergunta": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "diario",
    "title": "Diário por entrevista",
    "fields": [
        {"key": "ligado", "label": "Perguntar todo dia como foi o dia", "type": "toggle", "default": True},
        {"key": "hora", "label": "A partir de que horas (HH:MM)", "type": "text", "default": "21:30"},
    ],
}

ARQ = MEMORIA / "diario.json"
DURACAO_S = 15 * 60
MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]

_lock = threading.Lock()
_sessao = {"ativa": False, "desde": 0.0, "falas": [], "perguntas": []}
_iniciou = threading.Event()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def periodo(texto: str, hoje: date | None = None) -> tuple[date, date, str] | None:
    """Texto → (início, fim exclusivo, rótulo). None se não falar de tempo (pura)."""
    hoje = hoje or date.today()
    t = _dobrar(texto)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        d, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else hoje.year
        ano += 2000 if ano < 100 else 0
        try:
            dia = date(ano, mes, d)
        except ValueError:
            return None
        if not m.group(3) and dia > hoje:
            dia = date(ano - 1, mes, d)
        return dia, dia + timedelta(days=1), dia.strftime("%d/%m/%Y")
    if re.search(r"\banteontem\b", t):
        d = hoje - timedelta(days=2)
        return d, d + timedelta(days=1), "anteontem"
    if re.search(r"\bontem\b", t):
        d = hoje - timedelta(days=1)
        return d, d + timedelta(days=1), "ontem"
    if re.search(r"\bhoje\b", t):
        return hoje, hoje + timedelta(days=1), "hoje"
    if re.search(r"semana passada", t):
        ini = hoje - timedelta(days=hoje.weekday() + 7)
        return ini, ini + timedelta(days=7), "a semana passada"
    if re.search(r"essa semana|esta semana", t):
        ini = hoje - timedelta(days=hoje.weekday())
        return ini, hoje + timedelta(days=1), "esta semana"
    m = re.search(r"\bha (\d+|um|uma|dois|duas|tres) (dia|dias|semana|semanas|mes|meses|ano|anos)\b", t)
    if m:
        n = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3}.get(m.group(1)) or int(m.group(1))
        un = m.group(2)
        if un.startswith("dia"):
            d = hoje - timedelta(days=n)
            return d, d + timedelta(days=1), f"há {n} dia(s)"
        if un.startswith("semana"):
            d = hoje - timedelta(days=7 * n)
            ini = d - timedelta(days=d.weekday())
            return ini, ini + timedelta(days=7), f"há {n} semana(s)"
        if un.startswith("mes"):
            a, me = divmod(hoje.year * 12 + hoje.month - 1 - n, 12)
            ini = date(a, me + 1, 1)
            return ini, ini + timedelta(days=monthrange(a, me + 1)[1]), f"há {n} mês(es)"
        a = hoje.year - n
        return date(a, 1, 1), date(a + 1, 1, 1), str(a)
    for i, nome in enumerate(MESES):
        if re.search(rf"\b{nome}\b", t):
            m_ano = re.search(r"\b(20\d{2})\b", t)
            if m_ano:
                ano = int(m_ano.group(1))
            elif "ano passado" in t:
                ano = hoje.year - 1
            else:
                ano = hoje.year if i + 1 <= hoje.month else hoje.year - 1
            ini = date(ano, i + 1, 1)
            return ini, ini + timedelta(days=monthrange(ano, i + 1)[1]), f"{nome.replace('marco', 'março')} de {ano}"
    if "mes passado" in t:
        a, me = divmod(hoje.year * 12 + hoje.month - 2, 12)
        ini = date(a, me + 1, 1)
        return ini, ini + timedelta(days=monthrange(a, me + 1)[1]), "o mês passado"
    if "ano passado" in t:
        return date(hoje.year - 1, 1, 1), date(hoje.year, 1, 1), str(hoje.year - 1)
    m = re.search(r"\b(?:em|de|no ano de)\s+(20\d{2})\b", t)
    if m:
        a = int(m.group(1))
        return date(a, 1, 1), date(a + 1, 1, 1), str(a)
    return None


def deve_perguntar(agora: datetime, hora: str, ultima_data: str, pulado: str) -> bool:
    try:
        h, mi = (int(x) for x in re.findall(r"\d+", hora)[:2])
    except ValueError:
        h, mi = 21, 30
    hoje = agora.date().isoformat()
    return (agora.hour, agora.minute) >= (h, mi) and ultima_data != hoje and pulado != hoje and agora.hour < 24


def prompt_resumo(falas: list[str], perguntas: list[str], data_: str) -> str:
    conversa = "\n".join(f"- {f}" for f in falas)
    return (f"Isto é o que a pessoa contou sobre o dia {data_}, falando (transcrição, pode ter erros):\n{conversa}\n\n"
            "Escreva a entrada do diário dela em primeira pessoa, em português do Brasil, com 3 a 6 frases, usando as "
            "palavras dela, sem inventar nada e sem conselhos. Depois, numa linha separada começando com 'Humor:', uma "
            "palavra para o humor do dia.")


# ── dados ────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("entradas", [])
    d.setdefault("ultima", "")
    d.setdefault("pulado", "")
    return d


def entradas() -> list[dict]:
    return list(dados()["entradas"])


def guardar(texto: str, bruto: str = "", humor: str = "", quando: datetime | None = None) -> dict:
    quando = quando or datetime.now()
    e = {"data": quando.date().isoformat(), "ts": quando.timestamp(), "texto": texto.strip(), "bruto": bruto[:6000],
         "humor": humor}
    with _lock:
        d = dados()
        mesmo = next((x for x in d["entradas"] if x["data"] == e["data"]), None)
        if mesmo:
            mesmo["texto"] = (mesmo["texto"] + "\n" + e["texto"]).strip()
            mesmo["bruto"] = (mesmo.get("bruto", "") + "\n" + e["bruto"]).strip()[-8000:]
            mesmo["humor"] = humor or mesmo.get("humor", "")
        else:
            d["entradas"].append(e)
        d["ultima"] = e["data"]
        gravar_json(ARQ, d)
    try:
        from core import memoria_grafo
        threading.Thread(target=memoria_grafo.lembrar, args=(f"Diário de {e['data']}: {e['texto']}", "diario", e["ts"]),
                         daemon=True).start()
    except Exception:
        pass
    return e


def do_periodo(ini: date, fim: date) -> list[dict]:
    return [e for e in entradas() if ini.isoformat() <= e["data"] < fim.isoformat()]


# ── entrevista ───────────────────────────────────────────────────────────────
def _ouvir(entrada: str, saida: str, interrompido: bool) -> None:
    """Gancho de turno: enquanto a entrevista está aberta, guarda o que você conta."""
    with _lock:
        if not _sessao["ativa"]:
            return
        if time.time() - _sessao["desde"] > DURACAO_S:
            _sessao["ativa"] = False
            fechar = True
        else:
            fechar = False
            if entrada:
                _sessao["falas"].append(entrada)
            if saida:
                _sessao["perguntas"].append(saida)
    if fechar:
        encerrar()


def iniciar_entrevista(player=None) -> str:
    with _lock:
        _sessao.update(ativa=True, desde=time.time(), falas=[], perguntas=[])
    try:
        from core import ganchos_turno
        ganchos_turno.registrar(_ouvir)
    except Exception:
        pass
    return ("[DIÁRIO] Pergunte com carinho, em UMA frase, como foi o dia dele. Escute; faça no máximo 2 perguntas curtas "
            "de acompanhamento (o que foi bom, o que foi difícil, algo que ele queira lembrar). Quando ele terminar ou "
            "disser que é só isso, chame diario com action='encerrar'.")


def encerrar() -> str:
    with _lock:
        falas, perguntas = list(_sessao["falas"]), list(_sessao["perguntas"])
        _sessao.update(ativa=False, falas=[], perguntas=[])
    falas = [f for f in falas if len(f.split()) >= 2]
    if not falas:
        return "Não ouvi nada para o diário hoje; fica para amanhã."
    bruto = "\n".join(falas)
    texto, humor = bruto, ""
    try:
        from plugins import _ia
        r = _ia.perguntar(prompt_resumo(falas, perguntas, date.today().strftime("%d/%m/%Y")), False, 40) \
            if _ia.disponivel() else None
        if r:
            m = re.search(r"(?im)^\s*humor\s*:\s*(.+)$", r)
            humor = m.group(1).strip(" .") if m else ""
            texto = re.sub(r"(?im)^\s*humor\s*:.*$", "", r).strip()
    except Exception:
        pass
    guardar(texto, bruto, humor)
    return "Guardei o dia de hoje no diário." + (f" Humor: {humor}." if humor else "")


def consultar(pergunta: str) -> str:
    per = periodo(pergunta)
    if per is None:
        ultimas = entradas()[-7:]
        rotulo = "os últimos dias"
    else:
        ini, fim, rotulo = per
        ultimas = do_periodo(ini, fim)
    extras = []
    try:
        from core import memoria_grafo
        if per is not None:
            ini, fim, _r = per
            extras = memoria_grafo.buscar(pergunta, 6, desde=datetime.combine(ini, datetime.min.time()).timestamp(),
                                          ate=datetime.combine(fim, datetime.min.time()).timestamp())
    except Exception:
        extras = []
    if not ultimas and not extras:
        return f"Não tenho nada no diário sobre {rotulo}."
    material = "\n".join(f"{e['data']}: {e['texto']}" for e in ultimas[-40:])
    material += ("\n" if material else "") + "\n".join(
        f"{datetime.fromtimestamp(x['ts']):%Y-%m-%d}: {x['texto']}" for x in extras if x.get("fonte") != "diario")
    try:
        from plugins import _ia
        if _ia.disponivel() and len(material) > 300:
            r = _ia.perguntar(f"Com base SÓ nestas anotações do diário e da memória da pessoa ({rotulo}), responda em "
                              f"português, em 2 a 4 frases, à pergunta: \"{pergunta}\". Cite as datas.\n\n{material[:9000]}",
                              False, 40)
            if r:
                return r
    except Exception:
        pass
    return f"Sobre {rotulo}:\n{material[:2500]}"


def _laco(player) -> None:
    time.sleep(90)
    while True:
        try:
            c = cfg("diario", PLUGIN_SETTINGS)
            d = dados()
            if str(c.get("ligado", True)).lower() not in ("false", "0") and not _sessao["ativa"] and \
                    deve_perguntar(datetime.now(), str(c.get("hora") or "21:30"), d["ultima"], d["pulado"]):
                from core import estado_mundo
                e = estado_mundo.agora()
                if e["atividade"] in ("livre", "assistindo") and e["ocioso_s"] < 120 and not e["jarvis_falando"]:
                    with _lock:
                        d = dados()
                        d["pulado"] = date.today().isoformat()          # pergunta uma vez só (mesmo sem resposta)
                        gravar_json(ARQ, d)
                    falar(player, iniciar_entrevista(player))
        except Exception as e:
            print(f"[Diário] {e}")
        time.sleep(60)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="diario").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "consultar").lower()
    try:
        if acao == "entrevista":
            return iniciar_entrevista(player)
        if acao == "encerrar":
            return encerrar()
        if acao == "contar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que eu anoto?"
            guardar(texto, texto)
            return "Anotado no diário de hoje."
        if acao == "pular":
            with _lock:
                d = dados()
                d["pulado"] = date.today().isoformat()
                gravar_json(ARQ, d)
            return "Tudo bem, hoje sem diário."
        if acao == "listar":
            es = entradas()[-10:]
            if not es:
                return "O diário ainda está vazio."
            texto = "\n\n".join(f"{datetime.fromisoformat(e['data']):%d/%m/%Y}" + (f" ({e['humor']})" if e.get("humor") else "")
                                + f"\n{e['texto']}" for e in es)
            mostrar(player, "DIÁRIO", texto)
            registrar(player, f"Diário: {len(entradas())} dia(s) guardado(s).")
            return f"{len(entradas())} dia(s) no diário; os últimos estão na tela."
        pergunta = str(p.get("pergunta") or p.get("texto") or "").strip()
        return consultar(pergunta) if pergunta else "Sobre quando você quer saber?"
    except Exception as e:
        return f"O diário falhou: {e}"
