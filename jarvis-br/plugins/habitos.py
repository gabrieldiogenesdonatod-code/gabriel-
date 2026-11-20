"""
JARVIS aprende seus hábitos (fork PT-BR 1.5).

Olha a linha do tempo (qual programa/site você abre e a que horas) e percebe
padrões: "você abre o VS Code perto das 19h em 6 dos últimos 10 dias". Daí em
diante, perto do horário, se você está no PC e ainda não abriu, ele OFERECE:

    "São 19h, quer que eu abra o VS Code?"

Se você aceitar algumas vezes, ele pergunta se pode abrir sozinho — e passa
a abrir (avisando). Recusou? Diga "para de oferecer o YouTube".

    "Jarvis, que hábitos você percebeu?"
    "Jarvis, pode abrir o VS Code sozinho"     "Jarvis, para de oferecer o YouTube"
"""

from __future__ import annotations

import threading
import time
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, falar, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "habitos",
    "brief": "Learns daily app/site habits from the timeline and offers to open them at the usual time.",
    "description": (
        "Habits learned from the focus timeline (apps/sites opened at a similar time on several days); near the "
        "usual time JARVIS offers to open them, or opens them by itself if allowed. action='listar' ('what "
        "habits did you notice?'), 'automatico' with nome (open by itself), 'ignorar' with nome (stop offering), "
        "'oferecer' with nome (offer again), 'abrir' with nome (open now)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "listar | automatico | ignorar | oferecer | abrir"},
            "nome": {"type": "STRING"},
        },
        "required": [],
    },
}

_ARQ = MEMORIA / "habitos.json"
_IGNORAR_APPS = {"ausente", "JARVIS", "Explorador de Arquivos", "Gerenciador de Tarefas", "Terminal", "PowerShell"}
_SITES_URL = {"YouTube": "https://www.youtube.com", "WhatsApp": "https://web.whatsapp.com",
              "Instagram": "https://www.instagram.com", "GitHub": "https://github.com", "Gmail": "https://mail.google.com",
              "ChatGPT": "https://chatgpt.com", "Claude": "https://claude.ai", "Netflix": "https://www.netflix.com",
              "Twitch": "https://www.twitch.tv", "Mercado Livre": "https://www.mercadolivre.com.br",
              "Canva": "https://www.canva.com", "TikTok": "https://www.tiktok.com"}
_iniciado = threading.Event()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


# ── detecção (pura) ────────────────────────────────────────────────────────────
def primeiras_aberturas(focos: list[dict], minimo_s: float = 120) -> dict:
    """{atividade: {data: minuto_do_dia}} — a primeira vez no dia que cada coisa
    ficou em foco por pelo menos 2 min (somando a sessão)."""
    por = defaultdict(dict)
    acumulado = defaultdict(float)
    for f in sorted(focos, key=lambda x: x["inicio"]):
        nome = f.get("atividade") or f.get("app")
        if not nome or nome in _IGNORAR_APPS:
            continue
        d = datetime.fromtimestamp(f["inicio"])
        chave = (nome, d.date())
        if d.date() in por[nome]:
            continue
        acumulado[chave] += f["fim"] - f["inicio"]
        if acumulado[chave] >= minimo_s:
            por[nome][d.date()] = d.hour * 60 + d.minute
    return por


def detectar(focos: list[dict], hoje: date | None = None, dias: int = 14, min_dias: int = 5,
             tolerancia: int = 30) -> list[dict]:
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias)
    saida = []
    for nome, por_dia in primeiras_aberturas(focos).items():
        recentes = {d: m for d, m in por_dia.items() if inicio <= d < hoje}
        if len(recentes) < min_dias:
            continue
        minutos = sorted(recentes.values())
        mediana = minutos[len(minutos) // 2]
        perto = {d: m for d, m in recentes.items() if abs(m - mediana) <= tolerancia}
        if len(perto) < min_dias:
            continue
        dias_semana = sorted({d.weekday() for d in perto})
        uteis = set(dias_semana) <= {0, 1, 2, 3, 4} and len(dias_semana) >= 3
        saida.append({"nome": nome, "minuto": mediana, "hora": f"{mediana // 60:02d}:{mediana % 60:02d}",
                      "dias": len(perto), "de": len(recentes), "dias_semana": [0, 1, 2, 3, 4] if uteis else []})
    return sorted(saida, key=lambda h: h["minuto"])


def hora_de_oferecer(h: dict, agora: datetime, ja_abriu_hoje: bool, oferecido_hoje: bool) -> bool:
    if ja_abriu_hoje or oferecido_hoje:
        return False
    if h.get("dias_semana") and agora.weekday() not in h["dias_semana"]:
        return False
    m = agora.hour * 60 + agora.minute
    return h["minuto"] - 5 <= m <= h["minuto"] + 15


# ── estado e ações ─────────────────────────────────────────────────────────────
def _estado() -> dict:
    e = ler_json(_ARQ, {}) or {}
    e.setdefault("habitos", [])
    e.setdefault("preferencias", {})          # nome → "oferecer" | "automatico" | "ignorar"
    e.setdefault("oferecidos", {})            # nome → data
    e.setdefault("aceites", {})               # nome → quantas vezes aceitou
    return e


def atualizar() -> list[dict]:
    from plugins import _monitor_db
    e = _estado()
    e["habitos"] = detectar(_monitor_db.focos(time.time() - 21 * 86400))
    e["atualizado"] = time.time()
    gravar_json(_ARQ, e)
    return e["habitos"]


def abrir(nome: str, player=None) -> str:
    from core import registro_ferramentas
    if nome in _SITES_URL:
        import webbrowser
        webbrowser.open(_SITES_URL[nome], new=2)
        return f"Abri o {nome}."
    return registro_ferramentas.executar("controle_pc", {"action": "abrir", "alvo": nome}, player)


def _achar(e: dict, nome: str) -> dict | None:
    t = _dobrar(nome)
    return next((h for h in e["habitos"] if t and (t in _dobrar(h["nome"]) or _dobrar(h["nome"]) in t)), None)


def _laco(player) -> None:
    time.sleep(120)
    while True:
        try:
            e = _estado()
            if time.time() - float(e.get("atualizado") or 0) > 6 * 3600:
                atualizar()
                e = _estado()
            agora = datetime.now()
            hoje = agora.date().isoformat()
            from plugins import _monitor_db
            from plugins.linha_do_tempo import ocioso_segundos
            presente = ocioso_segundos() < 300
            hoje0 = datetime.combine(agora.date(), datetime.min.time()).timestamp()
            abertos_hoje = {f.get("atividade") for f in _monitor_db.focos(hoje0)}
            for h in e["habitos"]:
                pref = e["preferencias"].get(h["nome"], "oferecer")
                if pref == "ignorar" or not presente:
                    continue
                oferecido = e["oferecidos"].get(h["nome"]) == hoje
                if not hora_de_oferecer(h, agora, h["nome"] in abertos_hoje, oferecido):
                    continue
                e["oferecidos"][h["nome"]] = hoje
                gravar_json(_ARQ, e)
                if pref == "automatico":
                    registrar(player, f"Hábito: abrindo {h['nome']} ({h['hora']}).")
                    abrir(h["nome"], player)
                    falar(player, f"[HÁBITO] Você abriu o {h['nome']} sozinho porque o usuário permitiu. Avise em "
                                  "UMA frase curta. Não chame nenhuma ferramenta.")
                else:
                    extra = (" Ele já aceitou outras vezes: pergunte também se pode abrir sozinho daqui pra frente "
                             "(se ele disser que sim, chame habitos com action='automatico').") \
                        if e["aceites"].get(h["nome"], 0) >= 3 else ""
                    falar(player, f"[HÁBITO] São {agora:%H:%M} e o usuário costuma abrir o {h['nome']} por volta das "
                                  f"{h['hora']}. Pergunte em UMA frase curta se ele quer que você abra. Se aceitar, chame "
                                  f"habitos com action='abrir' e nome='{h['nome']}'.{extra}")
                break                                            # uma oferta por vez
        except Exception as ex:
            print(f"[Hábitos] {ex}")
        time.sleep(60)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="habitos").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        e = _estado()
        if acao == "listar":
            habitos = atualizar()
            if not habitos:
                return ("Ainda não percebi hábitos firmes. Preciso de umas duas semanas de linha do tempo (o JARVIS "
                        "aberto) para ver padrões.")
            mostrar(player, "HÁBITOS", "\n".join(
                f"{h['hora']}  {h['nome']:<20} {h['dias']} de {h['de']} dias"
                f"{' (dias úteis)' if h['dias_semana'] else ''} — {e['preferencias'].get(h['nome'], 'oferecer')}"
                for h in habitos))
            return "Percebi: " + "; ".join(f"{h['nome']} perto das {h['hora']}" for h in habitos[:5]) + "."
        h = _achar(e, str(p.get("nome") or ""))
        if not h:
            return "Não achei esse hábito. Diga 'que hábitos você percebeu?' para ver a lista."
        if acao == "abrir":
            e["aceites"][h["nome"]] = e["aceites"].get(h["nome"], 0) + 1
            gravar_json(_ARQ, e)
            return abrir(h["nome"], player)
        if acao in ("automatico", "ignorar", "oferecer"):
            e["preferencias"][h["nome"]] = acao
            gravar_json(_ARQ, e)
            return {"automatico": f"Combinado: perto das {h['hora']} eu abro o {h['nome']} sozinho.",
                    "ignorar": f"Tudo bem, não ofereço mais o {h['nome']}.",
                    "oferecer": f"Vou voltar a oferecer o {h['nome']} perto das {h['hora']}."}[acao]
        return "Ações: listar, abrir, automatico, ignorar, oferecer."
    except Exception as ex:
        return f"Os hábitos falharam: {ex}"
