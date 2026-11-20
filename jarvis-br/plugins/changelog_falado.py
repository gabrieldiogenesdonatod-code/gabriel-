"""
Changelog falado (fork PT-BR 1.6) — "Jarvis, o que mudou em você essa semana?"

Junta o que mudou no próprio JARVIS no período: a versão e as novidades do
CHANGELOG.md, os arquivos de código alterados (e plugins novos), as
correções que a auto-melhoria aplicou, os commits (se a pasta for um
repositório git) e as ferramentas que você mais usou.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

from plugins._comum import BASE, MEMORIA, ler_json, mostrar

PLUGIN = {
    "name": "changelog_falado",
    "brief": "Spoken changelog: what changed in JARVIS this week (version notes, files, new plugins, fixes, usage).",
    "description": (
        "Spoken changelog of JARVIS itself: 'what changed in you this week/month?'. periodo = 'semana' (default), "
        "'mes', 'hoje' or a number of days."
    ),
    "parameters": {"type": "OBJECT", "properties": {"periodo": {"type": "STRING"}}, "required": []},
}


def dias_de(periodo: str) -> int:
    t = (periodo or "semana").lower()
    if re.fullmatch(r"\d+", t.strip()):
        return max(1, int(t))
    return 1 if "hoje" in t else 30 if "mes" in t or "mês" in t else 7


def ultima_versao(changelog: str) -> tuple[str, str, list[str]]:
    """('1.6', '2026-11-02', [itens]) da primeira seção do CHANGELOG (pura)."""
    m = re.search(r"^## \[([\d.]+)\] — (\S+)\n(.*?)(?=^## \[|\Z)", changelog, re.M | re.S)
    if not m:
        return "", "", []
    itens = [re.sub(r"[`*]", "", x).strip() for x in re.findall(r"^- (.+)$", m.group(3), re.M)]
    return m.group(1), m.group(2), itens


def arquivos_mudados(desde: float) -> tuple[list[str], list[str]]:
    mudados, novos = [], []
    for p in list(BASE.glob("*.py")) + list((BASE / "plugins").glob("*.py")) + list((BASE / "core").glob("*.py")):
        st = p.stat()
        if st.st_mtime >= desde:
            mudados.append(p.relative_to(BASE).as_posix())
            if getattr(st, "st_birthtime", st.st_ctime) >= desde and p.parent.name == "plugins" \
                    and not p.name.startswith("_"):
                novos.append(p.stem)
    return sorted(mudados), sorted(novos)


def run(parameters: dict, player=None, session_memory=None) -> str:
    dias = dias_de(str((parameters or {}).get("periodo") or "semana"))
    desde = time.time() - dias * 86400
    try:
        linhas, fala = [], []
        cl = BASE / "CHANGELOG.md"
        if cl.exists():
            versao, data, itens = ultima_versao(cl.read_text(encoding="utf-8", errors="replace"))
            if versao:
                recente = datetime.strptime(data, "%Y-%m-%d") >= datetime.now() - timedelta(days=dias)
                linhas += [f"VERSÃO {versao} ({data})"] + [f"  • {x[:140]}" for x in itens[:20]]
                if recente:
                    fala.append(f"virei a versão {versao} em {data}, com {len(itens)} mudança(s) anotadas")
        mudados, novos = arquivos_mudados(desde)
        if mudados:
            linhas += ["", f"ARQUIVOS DE CÓDIGO ALTERADOS ({len(mudados)})"] + [f"  {x}" for x in mudados[:40]]
            fala.append(f"{len(mudados)} arquivo(s) de código mudaram" + (f", com {len(novos)} plugin(s) novo(s)" if novos else ""))
        correcoes = [x for x in (ler_json(MEMORIA / "auto_melhoria.json", {}) or {}).get("propostas", [])
                     if x.get("estado") == "aplicada"]
        if correcoes:
            linhas += ["", "CORREÇÕES QUE EU MESMO APLIQUEI"] + [f"  {x['arquivo']}: {x['explicacao']}" for x in correcoes[-10:]]
            fala.append(f"{len(correcoes)} correção(ões) minhas aplicadas")
        try:
            from plugins._projetos import commits
            cs = commits(BASE, desde)
            if cs:
                linhas += ["", f"COMMITS ({len(cs)})"] + [f"  {datetime.fromtimestamp(c['ts']):%d/%m} {c['msg'][:90]}" for c in cs[:20]]
                fala.append(f"{len(cs)} commit(s)")
        except Exception:
            pass
        try:
            from collections import Counter

            from core import registro_uso
            uso = Counter(c.get("ferramenta") for c in registro_uso.chamadas(desde))
            if uso:
                linhas += ["", "O QUE VOCÊ MAIS ME PEDIU"] + [f"  {n:>4}× {k}" for k, n in uso.most_common(8)]
                fala.append("a ferramenta que você mais usou foi " + uso.most_common(1)[0][0])
        except Exception:
            pass
        rotulo = "hoje" if dias == 1 else f"nos últimos {dias} dias"
        mostrar(player, f"O QUE MUDOU EM MIM ({rotulo})", "\n".join(linhas) or "Nada registrado.")
        if not fala:
            return f"Nada mudou em mim {rotulo}."
        return f"[CHANGELOG] Conte em primeira pessoa, em 2 ou 3 frases: {rotulo}, " + "; ".join(fala) + \
            ". Os detalhes estão no painel."
    except Exception as e:
        return f"O changelog falhou: {e}"
