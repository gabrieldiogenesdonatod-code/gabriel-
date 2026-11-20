"""
Companheiro (fork PT-BR 2.0): o JARVIS puxa conversa e oferece coisas que acha que você vai gostar.

De vez em quando (com limite por dia e nunca no horário de silêncio), ele:
  • dá bom dia com uma sugestão para o dia;
  • oferece música nova de quem você ouve, ou uma música parecida com o seu gosto;
  • lembra do projeto que ficou pela metade ("quer continuar o jarvis-br? faltava o menu…");
  • sugere um vídeo sobre um assunto que você curte, ou uma pausa;
  • puxa assunto sobre o que você gosta.
Se você está no PC, ele fala; se não, manda pelo WhatsApp, Telegram ou Discord
(com botões no Telegram). Responda "quero", "bora", "agora não"… Ele aprende com
o que você aceita e recusa, e deixa de oferecer o que você não curte.

    "Jarvis, me oferece alguma coisa"        "Jarvis, fica quieto por 3 horas"
    "Jarvis, o que você acha que eu gosto?"  "Jarvis, desliga o companheiro"
    "Jarvis, me liga às 20h"                 (ligação de verdade, se a Twilio estiver configurada)
"""

from __future__ import annotations

import random
import re
import threading
import time
import unicodedata
import urllib.parse
from datetime import datetime

from plugins import _canais, _gosto
from plugins._comum import MEMORIA, WIN, cfg, falar, gravar_json, ler_json, mostrar, salvar_cfg

PLUGIN = {
    "name": "companheiro",
    "brief": "Proactive companion: starts conversations and offers things the user probably likes (music, projects, "
             "videos, breaks) at the PC or by WhatsApp/Telegram/Discord; learns from accepted/refused offers.",
    "description": (
        "Proactive companion. action='agora' (optional tipo: musica | projeto | video | pausa | conversa | bom_dia) "
        "makes an offer now; 'quieto' with horas pauses offers; 'ligar'/'desligar' turn it on/off; 'gosto' tells what "
        "JARVIS learned the user likes; 'ligar_celular' with texto (+ optional hora 'HH:MM') calls the user's phone; "
        "'status'. When the user answers an offer ('quero', 'agora não'), call action='responder' with texto."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "agora | responder | quieto | ligar | desligar | gosto | "
                                                                    "ligar_celular | status"},
                       "tipo": {"type": "STRING"}, "texto": {"type": "STRING"}, "horas": {"type": "NUMBER"},
                       "hora": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "companheiro",
    "title": "Companheiro (conversa e ofertas)",
    "fields": [
        {"key": "ligado", "label": "Puxar conversa e oferecer coisas sozinho", "type": "toggle", "default": True},
        {"key": "por_dia", "label": "No máximo quantas vezes por dia", "type": "text", "default": "4"},
        {"key": "intervalo_h", "label": "Intervalo mínimo entre ofertas (horas)", "type": "text", "default": "2"},
        {"key": "silencio", "label": "Horário de silêncio (ex.: 23-8)", "type": "text", "default": "23-8"},
        {"key": "canais", "label": "Canais, em ordem (whatsapp, telegram, discord)", "type": "text",
         "default": "whatsapp, telegram, discord"},
    ],
}

ARQ = MEMORIA / "companheiro.json"
TIPOS = ("musica", "projeto", "video", "pausa", "conversa")
SIM = r"^(sim|quero|bora|manda|pode|claro|opa|demorou|toca|bota|vamos|aceito|beleza|blz|show|👍)"
NAO = r"^(nao|agora nao|depois|nem|passo|dispenso|nope|👎)"
_iniciou = threading.Event()
_lock = threading.Lock()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def config() -> dict:
    return cfg("companheiro", PLUGIN_SETTINGS)


def estado() -> dict:
    e = ler_json(ARQ, {}) or {}
    e.setdefault("enviadas", [])          # timestamps
    e.setdefault("pendente", None)        # oferta esperando resposta
    e.setdefault("quieto_ate", 0)
    e.setdefault("bom_dia", "")
    e.setdefault("ligacoes", [])          # {hora: 'HH:MM', texto, dia}
    return e


# ── regras (puras) ──────────────────────────────────────────────────────────
def em_silencio(hora: int, faixa: str) -> bool:
    """'23-8' → 23h..7h59 em silêncio (pura)."""
    m = re.match(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", str(faixa or ""))
    if not m:
        return False
    ini, fim = int(m.group(1)) % 24, int(m.group(2)) % 24
    return (ini <= hora < fim) if ini < fim else (hora >= ini or hora < fim)


def pode_oferecer(e: dict, c: dict, agora: float) -> bool:
    if not c.get("ligado", True) or agora < e.get("quieto_ate", 0):
        return False
    if em_silencio(datetime.fromtimestamp(agora).hour, c.get("silencio", "23-8")):
        return False
    hoje = [t for t in e["enviadas"] if t >= agora - 86400 and datetime.fromtimestamp(t).date() == datetime.fromtimestamp(agora).date()]
    try:
        por_dia, intervalo = int(str(c.get("por_dia") or 4)), float(str(c.get("intervalo_h") or 2).replace(",", "."))
    except ValueError:
        por_dia, intervalo = 4, 2.0
    if len(hoje) >= por_dia:
        return False
    return not e["enviadas"] or agora - max(e["enviadas"]) >= intervalo * 3600


def ler_resposta(texto: str) -> str:
    """'quero!' → 'sim'; 'agora não' → 'nao'; 'oferta:3:sim' (botão) → 'sim'; senão '' (pura)."""
    t = _dobrar(texto).strip(" !.?")
    m = re.match(r"oferta:\d+:(sim|nao)$", t)
    if m:
        return m.group(1)
    if len(t) > 30:
        return ""
    if re.match(NAO + r"(\b|$)", t):
        return "nao"
    if re.match(SIM + r"(\b|$)", t) or t in ("s", "y", "yes"):
        return "sim"
    return ""


def escolher_tipo(pesos_aceite: dict[str, float], rng: random.Random, permitido=TIPOS) -> str:
    """Sorteia o tipo de oferta, dando mais chance ao que ele costuma aceitar (pura com o rng)."""
    pesos = [max(0.15, pesos_aceite.get(t, 0.5)) for t in permitido]
    return rng.choices(list(permitido), weights=pesos, k=1)[0]


def aceite_por_tipo(eventos: list[dict]) -> dict[str, float]:
    contagem: dict[str, list[int]] = {}
    for ev in eventos:
        if ev.get("tipo") == "oferta" and ev.get("acao") in ("aceitou", "recusou"):
            c = contagem.setdefault(ev.get("extra", ""), [0, 0])
            c[0 if ev["acao"] == "aceitou" else 1] += 1
    return {t: (a + 1) / (a + r + 2) for t, (a, r) in contagem.items()}


# ── montar ofertas ──────────────────────────────────────────────────────────
def oferta_musica() -> dict | None:
    from plugins import musica
    txt = musica.sugerir()
    m = re.search(r'Saiu coisa nova de (.+?): "(.+?)"', txt) or re.search(r"Sugestão: (.+?) — ", txt)
    if not m:
        return None
    alvo = f"{m.group(1)} - {m.group(2)}" if m.lastindex == 2 else m.group(1)
    texto = txt.split(" (Se ")[0]
    link = "https://music.youtube.com/search?q=" + urllib.parse.quote(alvo)
    return {"tipo": "musica", "texto": f"🎵 {texto}", "acao": {"ferramenta": "musica", "params": {"action": "tocar", "pedido": alvo}},
            "link": link, "item": alvo}


def oferta_projeto() -> dict | None:
    try:
        from plugins import memoria_projeto as mp
        d = mp.dados()
        nome = d.get("ultimo") or d.get("atual")
        p = d["projetos"].get(nome) if nome else None
        if not p or nome in d["abertos"]:
            return None
        notas = p.get("notas") or []
        dica = f" Você deixou anotado: {notas[-1]['texto']}." if notas else ""
        return {"tipo": "projeto", "texto": f"💻 Bora continuar o {nome}?{dica}", "item": nome,
                "acao": {"ferramenta": "memoria_projeto", "params": {"action": "onde_parei", "projeto": nome}}}
    except Exception:
        return None


def oferta_video() -> dict | None:
    from plugins import _ia
    gosto = _gosto.resumo()
    if not gosto or not _ia.disponivel():
        return None
    r = _ia.perguntar(f"Gosto do usuário: {gosto}. Sugira UM assunto de vídeo do YouTube que ele provavelmente curtiria "
                      "agora (algo específico, para buscar). Responda só: termo de busca | frase curta e animada oferecendo",
                      False, 25) or ""
    if "|" not in r:
        return None
    termo, frase = (x.strip() for x in r.split("|", 1))
    if _gosto.ja_ofereceu(termo, 7):
        return None
    link = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(termo)
    return {"tipo": "video", "texto": f"📺 {frase}", "item": termo, "link": link, "acao": {"abrir": link}}


def oferta_pausa() -> dict:
    ideias = ["Que tal 5 minutinhos de pausa? Água, alongar as costas e descansar a vista.",
              "Faz tempo que você está nisso. Bora levantar 2 minutos? Eu seguro as pontas aqui.",
              "Pausa rápida? Um copo d'água agora vale ouro."]
    return {"tipo": "pausa", "texto": "☕ " + random.choice(ideias), "item": "pausa", "acao": None}


def oferta_conversa() -> dict | None:
    from plugins import _ia
    gosto = _gosto.resumo()
    if not _ia.disponivel():
        return None
    r = _ia.perguntar("Você é o J.A.R.V.I.S, amigo e assistente do usuário (brasileiro). Puxe assunto com UMA pergunta curta, "
                      "leve e natural, sobre algo que ele curte" + (f" ({gosto})" if gosto else "") +
                      ". Sem inventar fatos ou notícias. Só a pergunta.", False, 20) or ""
    return {"tipo": "conversa", "texto": f"💬 {r.strip()}", "item": r[:60], "acao": None} if r.strip() else None


def oferta_bom_dia() -> dict:
    hora = datetime.now().hour
    saud = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
    extra = ""
    for f in (oferta_projeto, oferta_musica):
        try:
            o = f()
        except Exception:
            o = None
        if o:
            extra = " " + o["texto"]
            return {**o, "tipo": "bom_dia", "texto": f"{saud}, senhor!{extra}"}
    return {"tipo": "bom_dia", "texto": f"{saud}, senhor! Estou por aqui se precisar.", "item": "bom_dia", "acao": None}


MONTAR = {"musica": oferta_musica, "projeto": oferta_projeto, "video": oferta_video, "pausa": oferta_pausa,
          "conversa": oferta_conversa, "bom_dia": oferta_bom_dia}


# ── entregar e responder ─────────────────────────────────────────────────────
def ocioso_s() -> float:
    """Há quanto tempo ninguém mexe no PC (teclado/mouse)."""
    if not WIN:
        return 0.0
    try:
        import ctypes

        class LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        li = LII()
        li.cbSize = ctypes.sizeof(LII)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
        return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0
    except Exception:
        return 0.0


def entregar(o: dict, player=None, onde: str = "") -> str:
    with _lock:
        e = estado()
        o = {**o, "id": int(time.time()) % 100000, "ts": time.time()}
        no_pc = onde == "pc" or (not onde and ocioso_s() < 300)
        canais_usados = []
        if no_pc:
            falar(player, f"[COMPANHEIRO] Diga isto ao usuário de forma natural, em no máximo duas frases, e espere a "
                          f"resposta (se ele aceitar ou recusar, chame companheiro action=responder): {o['texto']}")
            o["onde"] = "pc"
        else:
            botoes = [[("👍 Quero", f"oferta:{o['id']}:sim"), ("👎 Agora não", f"oferta:{o['id']}:nao")]] \
                if o.get("acao") or o.get("link") else None
            canais_usados = _canais.mandar(o["texto"], botoes=botoes, preferidos=config().get("canais", ""))
            if not canais_usados:
                return "Não tenho canal para te achar fora do PC (ligue o WhatsApp, o Telegram ou o Discord)."
            o["onde"] = canais_usados[0]
        e["pendente"] = o
        e["enviadas"] = (e["enviadas"] + [time.time()])[-50:]
        gravar_json(ARQ, e)
    _gosto.registrar("oferta", o.get("item") or o["texto"][:60], "ofereceu", o["tipo"])
    return o["texto"] if no_pc else f"Mandei pelo {_canais.NOMES[canais_usados[0]]}: {o['texto']}"


def responder_oferta(texto: str) -> str:
    """Resposta do dono a uma oferta pendente (chamado pelos canais e pela ferramenta). '' se não era resposta."""
    r = ler_resposta(texto)
    if not r:
        return ""
    with _lock:
        e = estado()
        o = e.get("pendente")
        if not o or time.time() - o.get("ts", 0) > 3 * 3600:
            return ""
        e["pendente"] = None
        gravar_json(ARQ, e)
    _gosto.registrar("oferta", o.get("item") or o["texto"][:60], "aceitou" if r == "sim" else "recusou", o["tipo"])
    if r == "nao":
        if o["tipo"] == "musica" and o.get("item"):
            _gosto.registrar("musica", o["item"], "recusou")
        return random.choice(["Sem problema, fica para outra.", "Beleza, anotado.", "Tranquilo!"])
    acao = o.get("acao") or {}
    if o.get("onde") != "pc" and o.get("link"):
        return f"Aqui está: {o['link']}"
    if r == "sim" and not acao and not o.get("link"):
        return random.choice(["Boa! Me conta mais.", "Show! 😄", "Fechou."])
    if acao.get("abrir"):
        from plugins._comum import abrir_no_sistema
        abrir_no_sistema(acao["abrir"])
        return "Abri para você."
    if acao.get("ferramenta"):
        try:
            import importlib
            mod = importlib.import_module(f"plugins.{acao['ferramenta']}")
            return mod.run(acao["params"]) or "Feito."
        except Exception as ex:
            return f"Tentei, mas falhou: {ex}"
    return "Boa! Me conta mais."


def oferecer(player=None, tipo: str = "", rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    hora = datetime.now().hour
    e = estado()
    hoje = datetime.now().strftime("%Y-%m-%d")
    if not tipo and 6 <= hora < 11 and e.get("bom_dia") != hoje:
        tipo = "bom_dia"
        e["bom_dia"] = hoje
        gravar_json(ARQ, e)
    tentativas = [tipo] if tipo else []
    pesos = aceite_por_tipo(_gosto.dados()["eventos"])
    while len(tentativas) < 4:
        t = escolher_tipo(pesos, rng)
        if t not in tentativas:
            tentativas.append(t)
    for t in tentativas:
        try:
            o = MONTAR.get(t, oferta_conversa)()
        except Exception as ex:
            print(f"[Companheiro] {t}: {ex}")
            o = None
        if o:
            return entregar(o, player)
    return "Não tenho nada bom para oferecer agora."


def _ligacoes_agendadas(e: dict, agora: datetime) -> list[dict]:
    hm = agora.strftime("%H:%M")
    hoje = agora.strftime("%Y-%m-%d")
    devidas = [x for x in e["ligacoes"] if x["dia"] == hoje and x["hora"] <= hm]
    e["ligacoes"] = [x for x in e["ligacoes"] if x not in devidas and x["dia"] >= hoje]
    return devidas


def _laco(player) -> None:
    time.sleep(240)
    rng = random.Random()
    while True:
        try:
            e = estado()
            agora = datetime.now()
            devidas = _ligacoes_agendadas(e, agora)
            if devidas:
                gravar_json(ARQ, e)
                for x in devidas:
                    print(f"[Companheiro] ligação: {_canais.ligar(x['texto'])}")
            if pode_oferecer(e, config(), time.time()) and rng.random() < 0.35:
                print(f"[Companheiro] {oferecer(player, rng=rng)}")
        except Exception as ex:
            print(f"[Companheiro] {ex}")
        time.sleep(600)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="companheiro").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(p.get("action") or "status")
    try:
        if acao == "agora":
            tipo = _dobrar(p.get("tipo") or "")
            tipo = next((t for t in MONTAR if t.startswith(tipo[:4])), "") if tipo else ""
            return oferecer(player, tipo)
        if acao == "responder":
            return responder_oferta(str(p.get("texto") or "")) or "Não havia nenhuma oferta esperando resposta."
        if acao == "quieto":
            horas = float(p.get("horas") or 3)
            e = estado()
            e["quieto_ate"] = time.time() + horas * 3600
            gravar_json(ARQ, e)
            return f"Fico quieto por {horas:g} hora(s)."
        if acao in ("ligar", "desligar"):
            salvar_cfg("companheiro", {"ligado": acao == "ligar"})
            return "Companheiro ligado: de vez em quando eu puxo assunto." if acao == "ligar" else \
                "Companheiro desligado: só falo quando você chamar."
        if acao == "gosto":
            g = _gosto.resumo()
            if not g:
                return "Ainda estou aprendendo do que você gosta. Peça músicas, resuma vídeos, jogue… eu vou anotando."
            mostrar(player, "O QUE EU ACHO QUE VOCÊ GOSTA", g.replace("; ", "\n"))
            taxa = _gosto.taxa_aceite()
            return f"Pelo que aprendi: {g}." + (f" Você aceita {taxa * 100:.0f}% das minhas ofertas." if taxa is not None else "")
        if acao == "ligar_celular":
            texto = str(p.get("texto") or "Oi! Aqui é o Jarvis, passando para saber como você está.")
            hora = str(p.get("hora") or "").strip()
            if hora:
                m = re.match(r"(\d{1,2})(?:[:h](\d{2}))?", hora)
                if not m:
                    return "Que horas? (ex.: 20:00)"
                hm = f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"
                e = estado()
                e["ligacoes"].append({"hora": hm, "texto": texto[:300], "dia": datetime.now().strftime("%Y-%m-%d")})
                gravar_json(ARQ, e)
                return f"Combinado: te ligo às {hm}."
            return _canais.ligar(texto)
        c = config()
        e = estado()
        quieto = e["quieto_ate"] > time.time()
        return (f"Companheiro {'ligado' if c.get('ligado', True) else 'desligado'}"
                + (f", quieto até {datetime.fromtimestamp(e['quieto_ate']):%H:%M}" if quieto else "")
                + f"; até {c.get('por_dia', 4)} ofertas por dia, silêncio {c.get('silencio', '23-8')}; canais: "
                + (", ".join(_canais.NOMES[x] for x in _canais.ativos()) or "só o PC") + ".")
    except Exception as ex:
        return f"O companheiro falhou: {ex}"
