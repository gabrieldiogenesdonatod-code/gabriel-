"""
Caçador de vagas (fork PT-BR 1.6).

Todo dia (de manhã) ele procura vagas de programador na sua cidade e
remotas, nos sites de vaga mais usados (Gupy, LinkedIn, Indeed, Programathor,
Catho, InfoJobs, Vagas.com), filtra as que combinam com você e avisa SÓ as
novas — por voz e no celular.

    "Jarvis, procura vagas de programador júnior em Goiânia"
    "Jarvis, quais vagas novas apareceram?"
    "Jarvis, procura também 'python' e 'remoto'"

Ele só lê a busca pública (não entra em nenhuma conta e não se candidata).
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from datetime import datetime

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "cacador_vagas",
    "brief": "Daily job hunter: searches public job sites for developer jobs in the user's city/remote, alerts new ones.",
    "description": (
        "Job hunter for developer jobs: action='buscar' (search now; optional termos = e.g. 'python junior', cidade), "
        "'novas' (list the new ones), 'configurar' with termos and/or cidade and/or remoto (true/false), 'status'. "
        "Runs once a day by itself and alerts only new jobs."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "buscar | novas | configurar | status"},
                       "termos": {"type": "STRING"}, "cidade": {"type": "STRING"}, "remoto": {"type": "BOOLEAN"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "cacador_vagas",
    "title": "Caçador de vagas",
    "fields": [
        {"key": "termos", "label": "O que procurar", "type": "text", "default": "programador júnior, desenvolvedor python"},
        {"key": "cidade", "label": "Cidade (vazio = a do briefing)", "type": "text", "default": ""},
        {"key": "remoto", "label": "Incluir vagas remotas", "type": "toggle", "default": True},
        {"key": "diario", "label": "Procurar sozinho todo dia", "type": "toggle", "default": True},
    ],
}

_ARQ = MEMORIA / "vagas.json"
SITES = ["gupy.io", "linkedin.com/jobs", "br.indeed.com", "programathor.com.br", "catho.com.br", "infojobs.com.br",
         "vagas.com.br"]
_iniciado = threading.Event()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def consultas(termos: str, cidade: str, remoto: bool) -> list[str]:
    lista = [t.strip() for t in re.split(r"[,;]", termos or "") if t.strip()] or ["programador"]
    saida = []
    for t in lista[:4]:
        if cidade:
            saida.append(f"vaga {t} {cidade}")
        if remoto:
            saida.append(f"vaga {t} remoto")
    return saida


def eh_vaga(titulo: str, url: str, texto: str = "") -> bool:
    """Descarta notícias, cursos e listas genéricas (pura)."""
    t = _dobrar(f"{titulo} {texto}")
    if re.search(r"\b(curso|bootcamp|salario medio|quanto ganha|noticia|blog|como se tornar)\b", t):
        return False
    return bool(re.search(r"\b(vaga|vagas|emprego|contrata|hiring|job|oportunidade|estagio|junior|pleno|senior)\b", t)) \
        or any(s.split("/")[0] in url for s in SITES)


def pontuar(v: dict, termos: str, cidade: str) -> int:
    t = _dobrar(f"{v['titulo']} {v.get('texto', '')}")
    p = sum(2 for termo in re.split(r"[,;\s]+", _dobrar(termos)) if len(termo) > 2 and termo in t)
    p += 2 if cidade and _dobrar(cidade) in t else 0
    p += 1 if re.search(r"remot|home office|hibrid", t) else 0
    p += 1 if re.search(r"junior|jr\b|estagi|trainee", t) else 0
    return p


def buscar(termos: str, cidade: str, remoto: bool) -> list[dict]:
    from actions.ddg_isolado import buscar                     # 2.8.2: processo separado
    achados, vistos = [], set()
    if True:
        for q in consultas(termos, cidade, remoto):
            for r in buscar("text", q, 25, region="br-pt", timelimit="w"):
                url, titulo = r.get("href") or r.get("url") or "", r.get("title") or ""
                if not url or url in vistos or not eh_vaga(titulo, url, r.get("body") or ""):
                    continue
                vistos.add(url)
                achados.append({"titulo": titulo.strip(), "url": url, "texto": (r.get("body") or "")[:300],
                                "visto": time.time()})
            time.sleep(1.5)                                     # gentil com o buscador
    return sorted(achados, key=lambda v: -pontuar(v, termos, cidade))


def _cidade(c: dict) -> str:
    if str(c.get("cidade") or "").strip():
        return str(c["cidade"]).strip()
    try:
        from plugins.briefing_br import _city
        return _city("")
    except Exception:
        return ""


def rodada() -> tuple[list[dict], int]:
    c = cfg("cacador_vagas", PLUGIN_SETTINGS)
    remoto = str(c.get("remoto", True)).lower() not in ("false", "0")
    vagas = buscar(str(c.get("termos") or ""), _cidade(c), remoto)
    d = ler_json(_ARQ, {}) or {}
    conhecidas = set(d.get("urls", []))
    novas = [v for v in vagas if v["url"] not in conhecidas]
    d["urls"] = list(conhecidas | {v["url"] for v in vagas})[-3000:]
    d["novas"] = (novas + d.get("novas", []))[:60]
    d["ultima"] = time.time()
    gravar_json(_ARQ, d)
    return novas, len(vagas)


def _laco(player) -> None:
    time.sleep(300)
    while True:
        try:
            c = cfg("cacador_vagas", PLUGIN_SETTINGS)
            d = ler_json(_ARQ, {}) or {}
            if str(c.get("diario", True)).lower() not in ("false", "0") and datetime.now().hour >= 8 and \
                    time.time() - float(d.get("ultima") or 0) > 20 * 3600:
                novas, _total = rodada()
                if novas:
                    from plugins._notificar import notificar
                    notificar(player, f"{len(novas)} vaga(s) nova(s): " + "; ".join(v["titulo"][:60] for v in novas[:3]),
                              titulo="CAÇADOR DE VAGAS", etiqueta="VAGAS", chave="vagas", intervalo_s=3600)
        except Exception as e:
            print(f"[Vagas] {e}")
        time.sleep(1800)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="cacador_vagas").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "buscar").lower()
    try:
        from plugins._comum import salvar_cfg
        if acao == "configurar" or (acao == "buscar" and (p.get("termos") or p.get("cidade"))):
            novos = {k: str(p[k]) for k in ("termos", "cidade") if p.get(k)}
            if "remoto" in p:
                novos["remoto"] = bool(p["remoto"])
            salvar_cfg("cacador_vagas", novos)
            if acao == "configurar":
                c = cfg("cacador_vagas", PLUGIN_SETTINGS)
                return f"Vou procurar: {c.get('termos')} em {_cidade(c) or 'qualquer cidade'}" + \
                    (" e remotas." if str(c.get("remoto", True)).lower() not in ("false", "0") else ".")
        if acao == "buscar":
            novas, total = rodada()
            lista = novas or (ler_json(_ARQ, {}) or {}).get("novas", [])[:10]
        else:
            d = ler_json(_ARQ, {}) or {}
            lista, novas, total = d.get("novas", [])[:15], d.get("novas", []), len(d.get("urls", []))
            if acao == "status":
                return f"Conheço {total} vaga(s); a última busca foi {datetime.fromtimestamp(d.get('ultima', 0)):%d/%m %H:%M}." \
                    if d.get("ultima") else "Ainda não procurei vagas."
        if not lista:
            return "Não achei vagas novas agora. Tente outros termos ('procura vagas de python remoto')."
        mostrar(player, "VAGAS", "\n\n".join(f"{v['titulo']}\n{v['url']}\n{v.get('texto', '')[:160]}" for v in lista[:20]))
        return (f"{len(novas)} vaga(s) nova(s) de {total} encontradas. As melhores: "
                + "; ".join(v["titulo"][:70] for v in lista[:3]) + ". Os links estão no painel.")
    except ImportError:
        return "Preciso do pacote de busca (ddgs), que vem no requirements.txt."
    except Exception as e:
        return f"O caçador de vagas falhou: {e}"
