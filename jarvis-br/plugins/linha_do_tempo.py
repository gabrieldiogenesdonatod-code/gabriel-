"""
Linha do tempo do seu dia (fork PT-BR 1.4).

Registra qual janela está em foco (a cada 5 s, quase sem custo) e quando
você está longe do PC (sem teclado/mouse por 5 min; vídeo tocando não conta
como ausência). Fica tudo no memory/monitor.db, tabela "foco".

    "Jarvis, o que eu fiz hoje?"
        → "4h no VS Code, 1h20 no YouTube e 40 min na Cristal Malhas."
    "Jarvis, quanto tempo gastei no projeto Jarvis essa semana?"
        → total + gráfico por dia no painel 📊 MONITOR, aba MEU DIA
    "Jarvis, abre a linha do tempo"   (página com os blocos do dia)
    "Jarvis, conta como Cristal Malhas tudo que tiver 'cristal' ou 'malhas'"

COMO ELE SABE O QUÊ
    app        pelo programa (Code.exe → VS Code, chrome.exe → Chrome…)
    atividade  pelo título: sites conhecidos (YouTube, WhatsApp, Instagram,
               GitHub…) e as suas regras (config/linha_do_tempo.json)
    projeto    pelo título do VS Code/PyCharm ("main.py - jarvis-br - Visual
               Studio Code" → jarvis-br)

PRIVACIDADE: nada sai do PC. Só o título da janela é guardado (não o
conteúdo), por 30 dias, igual ao resto do monitor.

Também é quem percebe que você VOLTOU depois de um tempo fora e chama o
relatório de "quando voltar".
"""

from __future__ import annotations

import html
import re
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from plugins._comum import CONFIG, LINUX, MEMORIA, WIN, abrir_no_sistema, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "linha_do_tempo",
    "brief": "Timeline of the user's day: time per app, site, activity and project.",
    "description": (
        "Timeline of the user's day from the focused window. action='resumo' with periodo "
        "(hoje|ontem|semana|mes) for 'what did I do today', time per app/site/project; 'tempo_em' with "
        "termo + periodo for 'how much time on project Jarvis this week' (also charts it in the MONITOR "
        "panel); 'abrir' opens the visual timeline; 'regra' with nome + palavras groups windows whose "
        "title has those words into an activity (e.g. Cristal Malhas: cristal, malhas)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "resumo | tempo_em | abrir | regra"},
            "periodo": {"type": "STRING"}, "termo": {"type": "STRING"},
            "nome": {"type": "STRING"}, "palavras": {"type": "STRING"},
        },
        "required": [],
    },
}

_REGRAS = CONFIG / "linha_do_tempo.json"
_HTML = MEMORIA / "linha_do_tempo.html"
OCIOSO_S = 300
OCIOSO_MIDIA_S = 3 * 3600
FLUSH_S = 300
_iniciado = threading.Event()

APPS = {
    "code.exe": "VS Code", "code - insiders.exe": "VS Code", "pycharm64.exe": "PyCharm",
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "opera.exe": "Opera",
    "brave.exe": "Brave", "windowsterminal.exe": "Terminal", "cmd.exe": "Terminal",
    "powershell.exe": "PowerShell", "pwsh.exe": "PowerShell", "explorer.exe": "Explorador de Arquivos",
    "whatsapp.exe": "WhatsApp", "whatsapp.root.exe": "WhatsApp", "discord.exe": "Discord",
    "spotify.exe": "Spotify", "capcut.exe": "CapCut", "obs64.exe": "OBS", "notepad.exe": "Bloco de Notas",
    "notepad++.exe": "Notepad++", "winword.exe": "Word", "excel.exe": "Excel", "powerpnt.exe": "PowerPoint",
    "steam.exe": "Steam", "steamwebhelper.exe": "Steam", "hd-player.exe": "BlueStacks",
    "leagueclientux.exe": "League of Legends", "league of legends.exe": "League of Legends",
    "valorant-win64-shipping.exe": "Valorant", "riotclientux.exe": "Riot Client",
    "python.exe": "JARVIS", "pythonw.exe": "JARVIS", "vlc.exe": "VLC", "telegram.exe": "Telegram",
    "photoshop.exe": "Photoshop", "figma.exe": "Figma", "anydesk.exe": "AnyDesk", "teams.exe": "Teams",
    "ms-teams.exe": "Teams", "zoom.exe": "Zoom", "taskmgr.exe": "Gerenciador de Tarefas",
}
_NAVEGADORES = {"Chrome", "Edge", "Firefox", "Opera", "Brave"}
SITES = [
    (r"youtube", "YouTube"), (r"whatsapp", "WhatsApp"), (r"instagram", "Instagram"),
    (r"facebook", "Facebook"), (r"tiktok", "TikTok"), (r"github", "GitHub"), (r"chatgpt", "ChatGPT"),
    (r"\bclaude\b", "Claude"), (r"gemini", "Gemini"), (r"gmail|caixa de entrada", "Gmail"),
    (r"netflix", "Netflix"), (r"twitch", "Twitch"), (r"mercado livre|mercadolivre", "Mercado Livre"),
    (r"shopee", "Shopee"), (r"stack overflow", "Stack Overflow"), (r"google docs|documentos google", "Google Docs"),
    (r"planilhas google|google sheets", "Google Planilhas"), (r"prime video", "Prime Video"),
    (r"disney\+", "Disney+"), (r"canva", "Canva"), (r"x\.com|twitter", "X/Twitter"),
]
_MIDIA = re.compile(r"youtube|netflix|twitch|prime video|disney\+|vlc|globoplay|crunchyroll|spotify|\.mp4|\.mkv", re.I)
_AUSENTE = {"lockapp.exe", "logonui.exe", ""}


# ── classificação (pura) ───────────────────────────────────────────────────────
def nome_app(processo: str) -> str:
    p = (processo or "").lower()
    return APPS.get(p) or (re.sub(r"\.exe$", "", processo or "?", flags=re.I).replace("_", " ").title() or "?")


def regras_usuario() -> dict:
    d = ler_json(_REGRAS, {}) or {}
    return d.get("atividades", {}) if isinstance(d, dict) else {}


def projeto_de(app: str, titulo: str) -> str:
    t = titulo or ""
    if app == "VS Code":
        partes = [x.strip() for x in re.split(r" [-—–] ", t) if x.strip()]
        partes = [x for x in partes if "visual studio code" not in x.lower()]
        if len(partes) >= 2:
            return partes[-1].replace("[WSL", "").strip(" ●[]")
        return partes[0].strip(" ●") if partes and "." not in partes[0] else ""
    if app == "PyCharm":
        partes = [x.strip() for x in re.split(r" [-—–] ", t) if x.strip()]
        return partes[0] if partes else ""
    if app in ("Terminal", "PowerShell"):
        m = re.search(r"[\\/]([^\\/:]+)[\\/]?\s*$", t)
        return m.group(1) if m else ""
    return ""


def classificar(processo: str, titulo: str, regras: dict | None = None) -> tuple[str, str, str]:
    """(app, atividade, projeto)."""
    app = nome_app(processo)
    t = (titulo or "").lower()
    for nome, palavras in (regras if regras is not None else regras_usuario()).items():
        if any(p.lower() in t for p in palavras if p):
            return app, nome, projeto_de(app, titulo)
    atividade = app
    if app in _NAVEGADORES or app in ("WhatsApp",):
        atividade = next((n for rx, n in SITES if re.search(rx, t)), app)
    return app, atividade, projeto_de(app, titulo)


class Rastreador:
    """Máquina de estados do foco (pura: recebe as leituras, devolve o que fechar).

    passo() devolve (intervalos_fechados, ausencia_terminada_em_segundos | None)."""

    def __init__(self, regras: dict | None = None, ocioso_s: float = OCIOSO_S):
        self.atual: dict | None = None
        self.ausente_desde: float | None = None
        self.regras = regras
        self.ocioso_s = ocioso_s

    def _fechar(self, fim: float) -> list[dict]:
        a, self.atual = self.atual, None
        if a and fim - a["inicio"] >= 2:
            a["fim"] = fim
            return [a]
        return []

    def passo(self, agora: float, processo: str, titulo: str, ocioso: float) -> tuple[list[dict], float | None]:
        fechados, voltou = [], None
        processo = (processo or "").lower()
        limite = OCIOSO_MIDIA_S if _MIDIA.search(titulo or "") else self.ocioso_s
        if processo in _AUSENTE or ocioso >= limite:
            if self.ausente_desde is None:
                inicio_ausencia = agora if processo in _AUSENTE else agora - ocioso
                fechados += self._fechar(max(inicio_ausencia, self.atual["inicio"]) if self.atual else inicio_ausencia)
                self.ausente_desde = inicio_ausencia
            return fechados, None
        if self.ausente_desde is not None:
            volta = agora - min(ocioso, agora - self.ausente_desde)
            if volta - self.ausente_desde >= 60:
                fechados.append({"inicio": self.ausente_desde, "fim": volta, "processo": "", "app": "ausente",
                                 "titulo": "", "atividade": "ausente", "projeto": ""})
                voltou = volta - self.ausente_desde
            self.ausente_desde = None
        app, atividade, projeto = classificar(processo, titulo, self.regras)
        chave = (processo, atividade, projeto)
        if self.atual is None or self.atual["chave"] != chave:
            fechados += self._fechar(agora)
            self.atual = {"inicio": agora, "processo": processo, "app": app, "titulo": titulo or "",
                          "atividade": atividade, "projeto": projeto, "chave": chave}
        elif agora - self.atual["inicio"] >= FLUSH_S:          # não perde horas se o app fechar
            fechados += self._fechar(agora)
            self.atual = {"inicio": agora, "processo": processo, "app": app, "titulo": titulo or "",
                          "atividade": atividade, "projeto": projeto, "chave": chave}
        return fechados, voltou


# ── leitura do foco e da ociosidade ────────────────────────────────────────────
_pid_nome: dict[int, str] = {}


def foco_atual() -> tuple[str, str]:
    """(processo, título) da janela em foco."""
    if WIN:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        h = u32.GetForegroundWindow()
        if not h:
            return "", ""
        n = u32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        nome = _pid_nome.get(pid.value)
        if nome is None:
            try:
                import psutil
                nome = psutil.Process(pid.value).name()
            except Exception:
                nome = "?"
            if len(_pid_nome) > 500:
                _pid_nome.clear()
            _pid_nome[pid.value] = nome
        return nome, buf.value
    try:
        from plugins._janelas import ativa
        j = ativa()
        return (j.get("processo", "?"), j.get("titulo", "")) if j else ("", "")
    except Exception:
        return "?", ""


def ocioso_segundos() -> float:
    """Segundos desde a última tecla/movimento do mouse."""
    if WIN:
        import ctypes

        class _LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = _LII()
        lii.cbSize = ctypes.sizeof(lii)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return ((ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0
        return 0.0
    if LINUX:
        from plugins._comum import rodar, tem
        if tem("xprintidle"):
            _c, out = rodar(["xprintidle"], timeout=2)
            try:
                return int(out.strip()) / 1000
            except ValueError:
                pass
    return 0.0


def _laco(player) -> None:
    from plugins import _monitor_db
    r = Rastreador()
    intervalo = 5 if WIN else 15
    ultima_regra = 0.0
    while True:
        try:
            if time.time() - ultima_regra > 120:
                r.regras, ultima_regra = regras_usuario(), time.time()
            processo, titulo = foco_atual()
            fechados, voltou = r.passo(time.time(), processo, titulo, ocioso_segundos())
            for f in fechados:
                _monitor_db.gravar_foco(f["inicio"], f["fim"], f["processo"], f["app"], f["titulo"],
                                        f["atividade"], f["projeto"])
            if voltou:
                try:
                    from plugins import quando_voltar
                    threading.Thread(target=quando_voltar.ao_voltar, args=(player, voltou, "teclado e mouse"),
                                     daemon=True).start()
                except Exception as e:
                    print(f"[LinhaDoTempo] quando_voltar: {e}")
        except Exception as e:
            print(f"[LinhaDoTempo] {e}")
        time.sleep(intervalo)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="linha_do_tempo").start()


# ── consultas ──────────────────────────────────────────────────────────────────
def periodo(texto: str, agora: datetime | None = None) -> tuple[float, float, str]:
    agora = agora or datetime.now()
    t = (texto or "hoje").lower()
    hoje0 = datetime.combine(agora.date(), datetime.min.time())
    if "ontem" in t:
        return (hoje0 - timedelta(days=1)).timestamp(), hoje0.timestamp(), "ontem"
    if "semana passada" in t:
        ini = hoje0 - timedelta(days=agora.weekday() + 7)
        return ini.timestamp(), (ini + timedelta(days=7)).timestamp(), "na semana passada"
    if "semana" in t:
        return (hoje0 - timedelta(days=agora.weekday())).timestamp(), agora.timestamp(), "nesta semana"
    if "7" in t or "sete" in t:
        return (hoje0 - timedelta(days=6)).timestamp(), agora.timestamp(), "nos últimos 7 dias"
    if "mes" in t or "mês" in t:
        return hoje0.replace(day=1).timestamp(), agora.timestamp(), "neste mês"
    return hoje0.timestamp(), agora.timestamp(), "hoje"


def resumo(desde: float, ate: float | None = None, focos: list[dict] | None = None) -> dict:
    if focos is None:
        from plugins import _monitor_db
        focos = _monitor_db.focos(desde, ate)
    apps, atividades, projetos = defaultdict(float), defaultdict(float), defaultdict(float)
    ativo = ausente = 0.0
    for f in focos:
        d = max(0.0, f["fim"] - f["inicio"])
        if f["atividade"] == "ausente":
            ausente += d
            continue
        ativo += d
        apps[f["app"]] += d
        atividades[f["atividade"]] += d
        if f.get("projeto"):
            projetos[f["projeto"]] += d
    ordem = lambda d: sorted(d.items(), key=lambda x: -x[1])      # noqa: E731
    return {"ativo_s": ativo, "ausente_s": ausente, "apps": ordem(apps), "atividades": ordem(atividades),
            "projetos": ordem(projetos), "focos": focos}


def juntar(focos: list[dict], folga_s: float = 15) -> list[dict]:
    """Une blocos seguidos da mesma atividade (o rastreador grava em pedaços de 5 min)."""
    saida: list[dict] = []
    for f in focos:
        u = saida[-1] if saida else None
        if u and (u["app"], u["atividade"], u.get("projeto")) == (f["app"], f["atividade"], f.get("projeto")) \
                and f["inicio"] - u["fim"] <= folga_s:
            u["fim"] = max(u["fim"], f["fim"])
        else:
            saida.append(dict(f))
    return saida


def tempo_em(termo: str, desde: float, ate: float | None = None, focos: list[dict] | None = None) -> tuple[float, dict]:
    if focos is None:
        from plugins import _monitor_db
        focos = _monitor_db.focos(desde, ate)
    t = termo.lower().replace("projeto ", "").strip()
    total, por_dia = 0.0, defaultdict(float)
    for f in focos:
        if f["atividade"] == "ausente":
            continue
        campos = " ".join(str(f.get(k) or "") for k in ("projeto", "atividade", "app", "titulo")).lower()
        if t and t in campos:
            d = f["fim"] - f["inicio"]
            total += d
            por_dia[date.fromtimestamp(f["inicio"]).isoformat()] += d
    return total, dict(por_dia)


def dur(s: float) -> str:
    m = int(round(s / 60))
    if m < 1:
        return "menos de 1 min"
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def frase(r: dict, n: int = 4) -> str:
    itens = [(nome, s) for nome, s in r["atividades"] if s >= 60][:n]
    if not itens:
        return ""
    partes = [f"{dur(s)} {'na' if nome in ('Cristal Malhas',) else 'no'} {nome}" for nome, s in itens]
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]


# ── página visual ──────────────────────────────────────────────────────────────
def gerar_html(dias: int = 7) -> str:
    from plugins import _monitor_db
    hoje0 = datetime.combine(date.today(), datetime.min.time())
    cores = {}
    paleta = ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8", "#fff176", "#4db6ac", "#f06292", "#90a4ae", "#a1887f"]
    linhas_html = []
    for i in range(dias - 1, -1, -1):
        ini = hoje0 - timedelta(days=i)
        fs = juntar(_monitor_db.focos(ini.timestamp(), (ini + timedelta(days=1)).timestamp()))
        blocos = []
        for f in fs:
            if f["atividade"] == "ausente":
                continue
            cor = cores.setdefault(f["atividade"], paleta[len(cores) % len(paleta)])
            x = (f["inicio"] - ini.timestamp()) / 864
            w = max(0.08, (f["fim"] - f["inicio"]) / 864)
            dica = html.escape(f"{datetime.fromtimestamp(f['inicio']):%H:%M}–{datetime.fromtimestamp(f['fim']):%H:%M} "
                               f"{f['atividade']} {('· ' + f['projeto']) if f['projeto'] else ''} — {f['titulo'][:80]}")
            blocos.append(f"<div class=b style='left:{x:.3f}%;width:{w:.3f}%;background:{cor}' title=\"{dica}\"></div>")
        r = resumo(ini.timestamp(), (ini + timedelta(days=1)).timestamp(), fs)
        linhas_html.append(f"<div class=dia><span>{ini:%a %d/%m}</span><div class=faixa>{''.join(blocos)}</div>"
                           f"<em>{dur(r['ativo_s'])}</em></div>")
    r7 = resumo((hoje0 - timedelta(days=dias - 1)).timestamp(), None)
    maior = max([s for _n, s in r7["atividades"]] or [1])
    barras = "".join(f"<div class=lin><span>{html.escape(n)}</span><div class=bar style='width:{60 * s / maior:.1f}%;"
                     f"background:{cores.get(n, '#4fc3f7')}'></div><em>{dur(s)}</em></div>" for n, s in r7["atividades"][:15])
    legenda = " ".join(f"<i style='background:{c}'></i>{html.escape(n)}" for n, c in cores.items())
    pagina = f"""<!doctype html><html lang=pt-br><meta charset=utf-8><title>Linha do tempo</title>
<style>body{{background:#06121c;color:#cfefff;font:13px Segoe UI,Arial;margin:24px}}h1{{color:#7fdcff;font-weight:500}}
.dia{{display:flex;align-items:center;gap:10px;margin:6px 0}}.dia span{{width:80px}}.dia em{{width:60px;color:#8fb}}
.faixa{{position:relative;flex:1;height:22px;background:#0b2233;border-radius:4px;overflow:hidden}}
.b{{position:absolute;top:0;height:100%}}.horas{{display:flex;justify-content:space-between;margin-left:90px;margin-right:70px;color:#577}}
.lin{{display:flex;align-items:center;gap:8px;margin:4px 0}}.lin span{{width:180px;text-align:right}}.bar{{height:14px;border-radius:3px}}
.leg i{{display:inline-block;width:10px;height:10px;margin:0 4px 0 12px;border-radius:2px}}</style>
<h1>LINHA DO TEMPO — últimos {dias} dias</h1><div class=horas>{''.join(f'<b>{h}h</b>' for h in range(0, 25, 3))}</div>
{''.join(linhas_html)}<p class=leg>{legenda}</p><h1>ONDE FOI O TEMPO</h1>{barras}
<p style=color:#577>Passe o mouse nos blocos para ver o título da janela. Gerado em {datetime.now():%d/%m/%Y %H:%M}.</p></html>"""
    _HTML.parent.mkdir(parents=True, exist_ok=True)
    _HTML.write_text(pagina, encoding="utf-8")
    return str(_HTML)


def _abrir_painel(player, termo: str = "") -> None:
    """Pede ao painel 📊 MONITOR para mostrar a aba MEU DIA (se a interface existir)."""
    try:
        from core import qt_bridge
        win = getattr(player, "_win", None) or player

        def abrir():
            fn = getattr(win, "abrir_meu_dia", None) or getattr(player, "abrir_meu_dia", None)
            if callable(fn):
                fn(termo)
        qt_bridge.na_interface(abrir)
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "resumo").lower()
    try:
        if acao == "regra":
            nome = str(p.get("nome") or "").strip()
            palavras = [w.strip() for w in re.split(r"[,;]| e ", str(p.get("palavras") or "")) if w.strip()]
            if not nome or not palavras:
                return "Diga o nome da atividade e as palavras do título que contam para ela."
            d = ler_json(_REGRAS, {}) or {}
            d.setdefault("atividades", {})[nome] = palavras
            gravar_json(_REGRAS, d)
            return f"Pronto: janelas com {', '.join(palavras)} no título contam como {nome}."
        if acao == "abrir":
            arq = gerar_html()
            return "Abri a linha do tempo." if abrir_no_sistema(arq) else f"Linha do tempo salva em {arq}."
        desde, ate, rotulo = periodo(str(p.get("periodo") or "hoje"))
        if acao == "tempo_em":
            termo = str(p.get("termo") or "").strip()
            if not termo:
                return "Tempo em quê? Um projeto, site ou programa."
            total, por_dia = tempo_em(termo, desde, ate)
            _abrir_painel(player, termo)
            if total < 60:
                return f"Não encontrei tempo em '{termo}' {rotulo}."
            dias = ", ".join(f"{datetime.fromisoformat(d):%a %d}: {dur(s)}" for d, s in sorted(por_dia.items()))
            return f"{rotulo.capitalize()} você passou {dur(total)} em {termo}. Por dia: {dias}."
        r = resumo(desde, ate)
        if r["ativo_s"] < 60:
            return (f"Ainda não tenho registro de uso {rotulo}. A linha do tempo começa a contar a partir de "
                    "agora, com o JARVIS aberto.")
        linhas = [f"Tempo no PC {rotulo}: {dur(r['ativo_s'])} (longe do PC: {dur(r['ausente_s'])})", "",
                  "ATIVIDADES"] + [f"  {dur(s):>8}  {n}" for n, s in r["atividades"][:15]]
        if r["projetos"]:
            linhas += ["", "PROJETOS"] + [f"  {dur(s):>8}  {n}" for n, s in r["projetos"][:10]]
        mostrar(player, f"MEU DIA — {rotulo.upper()}", "\n".join(linhas))
        proj = f" O projeto em que você mais mexeu foi {r['projetos'][0][0]}." if r["projetos"] else ""
        return f"{rotulo.capitalize()}: {frase(r)}. Total de {dur(r['ativo_s'])} no PC.{proj}"
    except Exception as e:
        return f"A linha do tempo falhou: {e}"
