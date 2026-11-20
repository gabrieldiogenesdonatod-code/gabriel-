"""
Detector de mentira do commit (3.0): compara o que a MENSAGEM do commit diz com o que o código
realmente mudou.

    "pequeno ajuste"  mas mexeu em 23 arquivos e 900 linhas      → suspeito
    "docs: README"    mas mudou código Python                     → suspeito
    "test: …"         sem nenhum arquivo de teste                 → suspeito
    "fix"/"ajustes"/"wip" num commit gigante                      → mensagem vaga

    "Jarvis, confere os últimos 10 commits do projeto."
    "Jarvis, julga o commit a1b2c3" (com a chave do Gemini, ele lê o diff e sugere uma mensagem melhor)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from plugins._lote2 import P, norm, num1, rodar

PLUGIN = P("commit_mentiroso", "Commit lie detector: compares each commit message with what the diff changed; flags misleading or vague messages.",
           "verificar | julgar", "pasta = git repo (default current). verificar: quantidade (default 10). julgar: commit (hash).",
           "pasta quantidade commit")

VAGAS = re.compile(r"^(wip|fix|ajuste?s?|update|updates|atualiza(cao|coes)?|mudancas?|coisas|teste|commit|alteracoes|varios|misc|\.+)$")
PEQUENO = re.compile(r"\b(typo|pequen\w*|minor|small|ortografia|so um|rapidinh\w*|bobeira|detalhe)\b")


def git(pasta: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
    if r.returncode:
        erro = r.stderr.strip()
        if "not a git repository" in erro:
            raise RuntimeError("essa pasta não é um repositório Git")
        if "no such path" in erro or "no such file" in erro.lower():
            raise RuntimeError("esse arquivo não está no Git (ainda não teve commit)")
        raise RuntimeError(erro[:200] or "o git não respondeu")
    return r.stdout


def commits(pasta: Path, n: int) -> list[dict]:
    bruto = git(pasta, "log", f"-n{n}", "--numstat", "--format=\x1e%h\x1f%s")
    out = []
    for bloco in bruto.split("\x1e")[1:]:
        cab, *linhas = bloco.strip("\n").split("\n")
        h, assunto = cab.split("\x1f", 1)
        arqs = []
        for l in linhas:
            partes = l.split("\t")
            if len(partes) == 3:
                a, d, arq = partes
                arqs.append((int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0, arq))
        out.append({"hash": h, "assunto": assunto, "arquivos": arqs})
    return out


def julgar_rapido(c: dict) -> list[str]:
    """Problemas aparentes entre a mensagem e o que mudou. Pura."""
    msg, arqs = norm(c["assunto"]), c["arquivos"]
    linhas = sum(a + d for a, d, _ in arqs)
    tipo = msg.split(":")[0].split("(")[0].strip() if ":" in msg else ""
    codigo = [f for _, _, f in arqs if not re.search(r"\.(md|txt|rst)$|(^|/)docs?/|readme|license|changelog", f, re.I)]
    testes = [f for _, _, f in arqs if re.search(r"(^|/)tests?/|test_|_test\.|\.spec\.|\.test\.", f, re.I)]
    probs = []
    if PEQUENO.search(msg) and (linhas > 60 or len(arqs) > 5):
        probs.append(f"diz que é pequeno, mas mudou {len(arqs)} arquivo(s) e {linhas} linha(s)")
    if (tipo == "docs" or re.search(r"\b(readme|documenta\w*)\b", msg)) and codigo:
        probs.append(f"diz que é documentação, mas mexeu em código ({', '.join(codigo[:3])})")
    if (tipo == "test" or re.match(r"^tests?\b", msg)) and not testes:
        probs.append("diz que é teste, mas nenhum arquivo de teste mudou")
    if (tipo == "style" or "formata" in msg) and linhas > 300:
        probs.append(f"diz que é só estilo, mas são {linhas} linhas")
    if VAGAS.match(msg.strip()) and (linhas > 40 or len(arqs) > 3):
        probs.append(f"mensagem vaga ('{c['assunto']}') para {linhas} linha(s) em {len(arqs)} arquivo(s)")
    if (tipo == "feat" or msg.startswith(("adiciona", "add ", "cria "))) and linhas and sum(d for _, d, _ in arqs) > 3 * sum(a for a, _, _ in arqs):
        probs.append("diz que adiciona algo, mas quase tudo foi remoção")
    return probs


def _go(p, pl):
    pasta = Path(str(p.get("pasta") or ".")).expanduser()
    if p["action"] == "julgar":
        h = re.sub(r"[^0-9a-fA-F]", "", str(p.get("commit") or "")) or "HEAD"
        assunto = git(pasta, "log", "-1", "--format=%s", h).strip()
        stat = git(pasta, "show", "--stat", "--format=", h)[-1500:]
        diff = git(pasta, "show", "--format=", "--unified=1", h)[:6000]
        from core import gemini
        d = gemini.as_json(f"Mensagem do commit: {assunto}\nArquivos:\n{stat}\nDiff (parcial):\n{diff}\n\nA mensagem descreve bem o "
                           'que mudou? Responda SÓ JSON: {"bate": true/false, "explicacao": "uma frase em português", '
                           '"mensagem_sugerida": "tipo(escopo): descrição curta"}', tier=gemini.SMART, default=None)
        if not isinstance(d, dict):
            probs = julgar_rapido({"hash": h, "assunto": assunto, "arquivos": commits(pasta, 1)[0]["arquivos"] if h == "HEAD" else []})
            return f"Sem a IA agora. Pela conta rápida: {'; '.join(probs) or 'a mensagem parece coerente'}."
        return (f"{'Bate' if d.get('bate') else 'NÃO bate'}: {d.get('explicacao', '')} "
                + (f"Mensagem melhor: {d.get('mensagem_sugerida')}" if not d.get("bate") else ""))
    lista = commits(pasta, int(num1(p, "quantidade", 10)))
    if not lista:
        return "Esse repositório não tem commits."
    ruins = [(c, julgar_rapido(c)) for c in lista]
    ruins = [(c, pr) for c, pr in ruins if pr]
    if not ruins:
        return f"Os últimos {len(lista)} commits dizem a verdade. Mensagens honestas!"
    from plugins._comum import mostrar
    mostrar(pl, "COMMITS SUSPEITOS", "\n".join(f"{c['hash']} \"{c['assunto']}\": " + "; ".join(pr) for c, pr in ruins))
    return f"{len(ruins)} de {len(lista)} commits com mensagem que não bate: " + "; ".join(
        f"{c['hash']} ({pr[0]})" for c, pr in ruins[:3]) + ". Detalhes no painel."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"verificar": _go, "julgar": _go}, player, "Commits")
