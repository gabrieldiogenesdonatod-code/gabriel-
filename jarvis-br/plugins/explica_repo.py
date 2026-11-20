"""
"Me explica esse repositório" (fork PT-BR 1.6).

Baixa um projeto do GitHub (ou lê uma pasta do PC), mapeia a estrutura —
linguagens, pastas, pontos de entrada, dependências, README — e explica a
arquitetura por voz. Com a chave do Gemini, ele lê os arquivos principais e
explica como as partes conversam; sem ela, dá o mapa da estrutura.

    "Jarvis, me explica o repositório github.com/FatihMakes/Mark-LVI"
    "Jarvis, explica a pasta C:\\projetos\\loja"
    "Jarvis, nesse repositório, onde fica o login?"     (pergunta sobre o último)
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "explica_repo",
    "brief": "Explains a GitHub repository or local project: structure, entry points, architecture.",
    "description": (
        "Explains a code repository by voice: alvo = GitHub URL ('owner/repo' also works) or a local folder. "
        "Maps languages, folders, entry points, dependencies and README; with AI it reads the main files and "
        "explains the architecture. Optional pergunta = a specific question (e.g. 'where is the login?'); without "
        "alvo the question is about the last repository."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"alvo": {"type": "STRING"}, "pergunta": {"type": "STRING"}},
        "required": [],
    },
}

_ULTIMO = MEMORIA / "explica_repo.json"
_CACHE = Path(tempfile.gettempdir()) / "jarvis_repos"


def repo_github(texto: str) -> tuple[str, str] | None:
    """'https://github.com/a/b.git', 'github.com/a/b/tree/main', 'a/b' → ('a', 'b') (pura)."""
    t = (texto or "").strip().rstrip("/")
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+)", t) or re.fullmatch(r"([\w.-]+)/([\w.-]+)", t)
    if not m:
        return None
    return m.group(1), re.sub(r"\.git$", "", m.group(2))


def baixar(dono: str, nome: str) -> Path:
    import requests
    destino = _CACHE / f"{dono}__{nome}"
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    r = requests.get(f"https://api.github.com/repos/{dono}/{nome}/zipball", timeout=90,
                     headers={"Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        raise RuntimeError("repositório não encontrado (ou é privado)")
    r.raise_for_status()
    if len(r.content) > 150 * 1024 * 1024:
        raise RuntimeError("repositório grande demais (mais de 150 MB)")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for info in z.infolist():                            # nada de caminhos para fora da pasta
            if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                continue
            z.extract(info, destino)
    filhos = [p for p in destino.iterdir() if p.is_dir()]
    return filhos[0] if len(filhos) == 1 else destino


def _amostras(pasta: Path, e: dict, limite: int = 24000) -> str:
    """Começo dos arquivos que mais explicam o projeto, até o limite de caracteres."""
    escolhidos = list(e["entradas"]) + list(e["maiores"])
    texto, vistos = "", set()
    for rel in escolhidos:
        if rel in vistos:
            continue
        vistos.add(rel)
        p = pasta / rel
        if p.is_file() and p.stat().st_size < 400_000:
            trecho = p.read_text(encoding="utf-8", errors="replace")[:2500]
            texto += f"\n\n===== {rel} =====\n{trecho}"
        if len(texto) > limite:
            break
    return texto[:limite]


def explicar(pasta: Path, rotulo: str, pergunta: str = "", player=None) -> str:
    from plugins import _ia
    from plugins._analise_codigo import estrutura, resumo_texto
    e = estrutura(pasta)
    mapa = resumo_texto(e)
    gravar_json(_ULTIMO, {"pasta": str(pasta), "rotulo": rotulo})
    painel = [f"REPOSITÓRIO: {rotulo}", "", mapa, "", "MAIORES ARQUIVOS:"] + [f"  {m}" for m in e["maiores"]]
    if e["readme"]:
        painel += ["", "README (começo):", e["readme"][:1200]]
    if not _ia.disponivel():
        mostrar(player, "EXPLICA REPOSITÓRIO", "\n".join(painel))
        return f"[REPOSITÓRIO {rotulo}] {mapa} (Sem a chave do Gemini eu só mapeio a estrutura.)"
    prompt = (f"Você é um engenheiro sênior explicando o projeto '{rotulo}' para um programador brasileiro, por VOZ.\n"
              f"ESTRUTURA: {mapa}\nREADME:\n{e['readme'][:2500]}\nARQUIVOS PRINCIPAIS:{_amostras(pasta, e)}\n\n"
              + (f"PERGUNTA DO USUÁRIO: {pergunta}\nResponda à pergunta citando os arquivos." if pergunta else
                 "Explique: para que serve, a arquitetura (as partes e como conversam), o fluxo principal, onde "
                 "começar a ler e um ponto de atenção.")
              + " Responda em português do Brasil, em até 8 frases faladas, sem markdown.")
    resposta = _ia.perguntar(prompt, inteligente=True, segundos=90) or "Não consegui a explicação agora."
    mostrar(player, "EXPLICA REPOSITÓRIO", resposta + "\n\n" + "\n".join(painel))
    return f"[REPOSITÓRIO {rotulo}] {resposta}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    alvo, pergunta = str(p.get("alvo") or "").strip(), str(p.get("pergunta") or "").strip()
    try:
        if not alvo:
            ultimo = ler_json(_ULTIMO, {}) or {}
            if not ultimo or not Path(ultimo.get("pasta", "")).is_dir():
                return "Qual repositório? Diga o link do GitHub ou a pasta."
            return explicar(Path(ultimo["pasta"]), ultimo["rotulo"], pergunta, player)
        local = Path(alvo).expanduser()
        if local.is_dir():
            return explicar(local, local.name, pergunta, player)
        gh = repo_github(alvo)
        if not gh:
            return f"Não entendi '{alvo}'. Use o link do GitHub (dono/projeto) ou uma pasta do PC."
        pasta = baixar(*gh)
        return explicar(pasta, f"{gh[0]}/{gh[1]}", pergunta, player)
    except Exception as e:
        return f"Não consegui explicar o repositório: {e}"
