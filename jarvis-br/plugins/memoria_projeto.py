"""
Memória por projeto (fork PT-BR 1.9).

O JARVIS percebe qual projeto está aberto no VS Code (ou Cursor) pelo título da
janela, acompanha os arquivos em que você mexe e, quando você fecha o projeto,
guarda sozinho um resumo da sessão: quanto tempo, quais arquivos, o que mudou
no git e as suas anotações.

    "Jarvis, onde eu parei?"                       (no projeto aberto ou no último)
    "Jarvis, onde eu parei no jarvis-br?"
    "Jarvis, anota no projeto: falta o menu de transparência"
    "Jarvis, o que eu fiz essa semana no jarvis-br?"
    "Jarvis, quais projetos você acompanha?"

Tudo fica em memory/projetos_memoria.json, no seu PC.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
from pathlib import Path

from plugins._comum import MEMORIA, WIN, gravar_json, ler_json, mostrar, rodar

PLUGIN = {
    "name": "memoria_projeto",
    "brief": "Per-project memory from the open VS Code folder: 'where did I stop?', project notes, session summaries.",
    "description": (
        "Per-project memory. JARVIS watches which project is open in VS Code/Cursor and saves a session summary when "
        "it is closed. action='onde_parei' (optional projeto) answers 'where did I stop?'; 'anotar' with texto (+ "
        "optional projeto) saves a note for the project; 'historico' with projeto (+ dias) lists recent sessions; "
        "'listar' lists tracked projects; 'esquecer' with projeto removes its memory."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "onde_parei | anotar | historico | listar | esquecer"},
                       "projeto": {"type": "STRING"}, "texto": {"type": "STRING"}, "dias": {"type": "INTEGER"}},
        "required": [],
    },
}

ARQ = MEMORIA / "projetos_memoria.json"
EDITORES = ("Visual Studio Code", "Cursor", "VSCodium", "Code - Insiders")
TICK_S = 15
FECHADO_TICKS = 3                       # ~45 s sem a janela = projeto fechado
_iniciou = threading.Event()
_lock = threading.Lock()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


# ── regras puras ────────────────────────────────────────────────────────────
def ler_titulo(titulo: str) -> tuple[str, str]:
    """'● ui.py - jarvis-br - Visual Studio Code' → ('jarvis-br', 'ui.py'). ('', '') se não é editor (pura)."""
    t = (titulo or "").strip().lstrip("●").strip()
    partes = [p.strip() for p in t.split(" - ")]
    if len(partes) < 2 or not any(partes[-1].startswith(e) or partes[-1] == e for e in EDITORES):
        return "", ""
    resto = partes[:-1]
    if resto and resto[-1].startswith("[") and resto[-1].endswith("]"):     # perfil do VS Code
        resto = resto[:-1]
    if not resto:
        return "", ""
    projeto = re.sub(r"\s*\((Workspace|Espaço de Trabalho|WSL.*|SSH.*)\)$", "", resto[-1]).strip()
    arquivo = resto[0] if len(resto) >= 2 else ""
    if projeto.lower() in ("welcome", "bem-vindo", "get started", "introdução"):
        return "", ""
    if arquivo.lower() in ("welcome", "bem-vindo", "settings", "configurações", "extension"):
        arquivo = ""
    return projeto, arquivo


def caminho_do_projeto(nome: str, uris: list[str]) -> str:
    """Acha a pasta do projeto entre as URIs recentes do VS Code (pura)."""
    alvo = nome.lower()
    for u in uris:
        if not u.startswith("file://"):
            continue
        p = urllib.parse.unquote(u[len("file://"):])
        if re.match(r"^/[a-zA-Z]:", p):
            p = p[1:]
        if Path(p.rstrip("/")).name.lower() == alvo:
            return p.replace("/", "\\") if WIN else p
    return ""


def uris_vscode() -> list[str]:
    bases = []
    if WIN:
        bases = [Path(os.environ.get("APPDATA", "")) / n for n in ("Code", "Cursor", "VSCodium", "Code - Insiders")]
    else:
        bases = [Path.home() / ".config" / n for n in ("Code", "Cursor", "VSCodium")] + \
                [Path.home() / "Library" / "Application Support" / n for n in ("Code", "Cursor")]
    achadas = []
    for b in bases:
        arq = b / "User" / "globalStorage" / "storage.json"
        try:
            achadas += re.findall(r'"(file:///[^"]+)"', arq.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return achadas


def frase_onde_parei(nome: str, p: dict) -> str:
    """O texto do 'onde eu parei?' (pura)."""
    sessoes = p.get("sessoes") or []
    notas = p.get("notas") or []
    if not sessoes and not notas:
        return f"Ainda não tenho nada guardado do {nome}."
    partes = []
    if sessoes:
        s = sessoes[-1]
        arqs = sorted((s.get("arquivos") or {}).items(), key=lambda x: -x[1])
        quando = time.strftime("%d/%m às %H:%M", time.localtime(s.get("fim") or s.get("inicio", 0)))
        txt = f"No {nome}, na última sessão ({quando}, {round(s.get('minutos', 0))} min)"
        if arqs:
            txt += f", você estava mexendo no {arqs[0][0]}"
            if len(arqs) > 1:
                txt += " e também em " + ", ".join(a for a, _ in arqs[1:4])
        partes.append(txt)
        if s.get("git"):
            partes.append(s["git"])
        if s.get("resumo"):
            partes.append(s["resumo"])
    else:
        partes.append(f"No {nome}")
    if notas:
        partes.append(f"deixou anotado: {notas[-1]['texto']}" + (f" (e mais {len(notas) - 1} notas)" if len(notas) > 1 else ""))
    return ". ".join(x.rstrip(".") for x in partes) + "."


# ── dados ──────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("projetos", {})
    d.setdefault("abertos", {})            # nome → {inicio, arquivos{arq: s}, sem_ver, ultimo_arquivo}
    d.setdefault("ultimo", "")
    return d


def _projeto(d: dict, nome: str) -> dict:
    return d["projetos"].setdefault(nome, {"caminho": "", "sessoes": [], "notas": []})


def achar_nome(d: dict, texto: str) -> str:
    t = _dobrar(texto)
    if not t:
        return d.get("atual") or d.get("ultimo") or ""
    for n in d["projetos"]:
        if _dobrar(n) == t:
            return n
    for n in d["projetos"]:
        if t in _dobrar(n) or _dobrar(n) in t:
            return n
    return ""


def resumo_git(caminho: str, desde: float) -> str:
    if not caminho or not (Path(caminho) / ".git").exists():
        return ""
    _c, branch = rodar(["git", "-C", caminho, "rev-parse", "--abbrev-ref", "HEAD"], timeout=8, encoding="utf-8")
    _c, st = rodar(["git", "-C", caminho, "status", "--porcelain"], timeout=8, encoding="utf-8")
    _c, log = rodar(["git", "-C", caminho, "log", f"--since={int(desde)}", "--format=%s"], timeout=8, encoding="utf-8")
    mudados = [l for l in st.splitlines() if l.strip()]
    commits = [l for l in log.splitlines() if l.strip() and "fatal" not in l]
    partes = [f"no branch {branch.strip()}"] if branch.strip() and "fatal" not in branch else []
    if commits:
        partes.append(f"{len(commits)} commit(s): " + "; ".join(commits[:3]))
    if mudados:
        partes.append(f"{len(mudados)} arquivo(s) alterado(s) sem commit")
    return ("Git: " + ", ".join(partes)) if partes else ""


def fechar_sessao(d: dict, nome: str, agora: float | None = None) -> dict | None:
    a = d["abertos"].pop(nome, None)
    if not a:
        return None
    agora = agora or time.time()
    minutos = (agora - a["inicio"]) / 60
    if minutos < 2 and not a.get("arquivos"):
        return None
    p = _projeto(d, nome)
    s = {"inicio": a["inicio"], "fim": agora, "minutos": round(minutos, 1),
         "arquivos": {k: round(v) for k, v in sorted(a.get("arquivos", {}).items(), key=lambda x: -x[1])[:12]}}
    try:
        s["git"] = resumo_git(p.get("caminho", ""), a["inicio"])
    except Exception:
        s["git"] = ""
    p["sessoes"] = (p["sessoes"] + [s])[-60:]
    d["ultimo"] = nome
    return s


def tick(d: dict, janelas: list[dict], ativa: dict | None, agora: float, uris: list[str] | None = None) -> list[str]:
    """Um passo do acompanhamento (puro com os dados que recebe). Devolve os projetos que fecharam."""
    abertos_agora = set()
    for j in janelas:
        nome, _arq = ler_titulo(j.get("titulo", ""))
        if nome:
            abertos_agora.add(nome)
    for nome in abertos_agora:
        if nome not in d["abertos"]:
            d["abertos"][nome] = {"inicio": agora, "arquivos": {}, "sem_ver": 0}
            p = _projeto(d, nome)
            if not p.get("caminho") and uris:
                p["caminho"] = caminho_do_projeto(nome, uris)
        d["abertos"][nome]["sem_ver"] = 0
    if ativa:
        nome, arq = ler_titulo(ativa.get("titulo", ""))
        if nome and arq:
            a = d["abertos"].setdefault(nome, {"inicio": agora, "arquivos": {}, "sem_ver": 0})
            a["arquivos"][arq] = a["arquivos"].get(arq, 0) + TICK_S
        if nome:
            d["atual"] = nome
    fechados = []
    for nome in list(d["abertos"]):
        if nome not in abertos_agora:
            d["abertos"][nome]["sem_ver"] = d["abertos"][nome].get("sem_ver", 0) + 1
            if d["abertos"][nome]["sem_ver"] >= FECHADO_TICKS:
                if fechar_sessao(d, nome, agora):
                    fechados.append(nome)
                else:
                    d["abertos"].pop(nome, None)
    return fechados


# ── laço ──────────────────────────────────────────────────────────────────────
def _resumo_ia(nome: str, s: dict, notas: list[dict]) -> str:
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return ""
        return (_ia.perguntar(
            f"Em UMA frase curta em português, diga em que o programador estava trabalhando no projeto {nome}, com base "
            f"nos arquivos (segundos em cada): {json.dumps(s.get('arquivos'), ensure_ascii=False)}; {s.get('git', '')}; "
            f"anotações: {[n['texto'] for n in notas[-3:]]}. Não invente detalhes.", False, 25) or "").strip()
    except Exception:
        return ""


def _laco(player) -> None:
    from plugins import _janelas
    uris, uris_quando = [], 0.0
    while True:
        try:
            if time.time() - uris_quando > 600:
                uris, uris_quando = uris_vscode(), time.time()
            janelas = _janelas.listar()
            ativa = _janelas.ativa()
            with _lock:
                d = dados()
                antes = d.get("atual")
                fechados = tick(d, janelas, ativa, time.time(), uris)
                gravar_json(ARQ, d)
            for nome in fechados:
                with _lock:
                    d = dados()
                    p = _projeto(d, nome)
                    if p["sessoes"]:
                        r = _resumo_ia(nome, p["sessoes"][-1], p["notas"])
                        if r:
                            p["sessoes"][-1]["resumo"] = r
                            gravar_json(ARQ, d)
                print(f"[MemóriaProjeto] sessão do {nome} guardada.")
            novo = d.get("atual")
            if novo and novo != antes and d["projetos"].get(novo, {}).get("sessoes"):
                mostrar(player, f"PROJETO {novo.upper()}", frase_onde_parei(novo, d["projetos"][novo]))
        except Exception as e:
            print(f"[MemóriaProjeto] {e}")
        time.sleep(TICK_S)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="memoria_projeto").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "onde_parei").lower()
    try:
        with _lock:
            d = dados()
        if acao == "listar":
            if not d["projetos"]:
                return "Ainda não acompanhei nenhum projeto. Abra uma pasta no VS Code."
            return "Projetos: " + ", ".join(f"{n} ({len(x['sessoes'])} sessões)" for n, x in d["projetos"].items()) + "."
        nome = achar_nome(d, str(p.get("projeto") or ""))
        if not nome:
            return "Qual projeto? " + (", ".join(d["projetos"]) or "Ainda não acompanhei nenhum.")
        proj = _projeto(d, nome)
        if acao == "anotar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que eu anoto?"
            with _lock:
                d = dados()
                _projeto(d, nome)["notas"].append({"ts": time.time(), "texto": texto[:500]})
                gravar_json(ARQ, d)
            return f"Anotado no {nome}."
        if acao == "historico":
            dias = int(p.get("dias") or 7)
            ses = [s for s in proj["sessoes"] if s["inicio"] >= time.time() - dias * 86400]
            if not ses:
                return f"Nenhuma sessão no {nome} nos últimos {dias} dias."
            total = sum(s["minutos"] for s in ses)
            linhas = [f"{time.strftime('%d/%m %H:%M', time.localtime(s['inicio']))}  {round(s['minutos'])} min  "
                      + ", ".join(list(s.get("arquivos", {}))[:4]) + (f"  — {s['resumo']}" if s.get("resumo") else "")
                      for s in ses]
            mostrar(player, f"{nome.upper()} — ÚLTIMOS {dias} DIAS", "\n".join(linhas))
            return f"{len(ses)} sessões no {nome}, {total / 60:.1f} horas no total. A lista está na tela."
        if acao == "esquecer":
            with _lock:
                d = dados()
                d["projetos"].pop(nome, None)
                d["abertos"].pop(nome, None)
                gravar_json(ARQ, d)
            return f"Apaguei a memória do {nome}."
        aberto = d["abertos"].get(nome)
        txt = frase_onde_parei(nome, proj)
        if aberto and aberto.get("arquivos"):
            agora_arq = max(aberto["arquivos"].items(), key=lambda x: x[1])[0]
            txt += f" Agora há pouco você estava no {agora_arq}."
        return txt
    except Exception as e:
        return f"A memória de projeto falhou: {e}"
