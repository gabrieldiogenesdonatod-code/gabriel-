"""
Pesquisa profunda (fork PT-BR 2.16, ideia 16).

    "Jarvis, faz uma pesquisa profunda sobre energia solar para casa em Goiânia"
    "Jarvis, pesquisa a fundo: vale a pena MEI ou ME para loja de roupa?"

1. A IA quebra o tema em 3 a 5 buscas diferentes (sem IA, usa o tema e variações).
2. Busca cada uma (DuckDuckGo, o mesmo da busca normal) e junta os melhores links,
   sem repetir site.
3. Baixa e lê até 8 páginas.
4. Escreve o relatório: resumo, pontos principais e o que as fontes discordam,
   com [1], [2]… em CADA afirmação, apontando para a fonte de onde veio.

Salva em Documentos/JARVIS/Pesquisas/<tema>.md (abre no Obsidian ou em qualquer
editor) e mostra no painel. Leva de 1 a 3 minutos; ele avisa quando terminar.
O que não está nas fontes, ele diz que não achou, em vez de inventar.
"""

from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plugins import _web
from plugins._comum import mostrar, pasta_jarvis, registrar

PLUGIN = {
    "name": "pesquisa_profunda",
    "brief": "Deep research: several searches, reads up to 8 pages, report with a cited source for each claim.",
    "description": (
        "Deep research. action='pesquisar' with tema starts a multi-source research in the background (1-3 min) and "
        "warns when done; say you started it. action='ultima' reads the last report summary. Use this when the user "
        "asks to research deeply / 'a fundo' / with sources, not for quick facts."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "pesquisar | ultima"},
                       "tema": {"type": "STRING"}},
        "required": [],
    },
}

_estado = {"rodando": False, "ultimo": None}


def buscas(tema: str) -> list[str]:
    from plugins import _ia
    if _ia.disponivel():
        r = _ia.perguntar_json(
            f"Tema de pesquisa: \"{tema}\". Gere de 3 a 5 buscas de internet DIFERENTES que cubram o tema por ângulos "
            "distintos (dados, prós e contras, custos, opinião de especialistas, notícias recentes). Em português, a "
            "menos que o tema peça inglês. Responda SÓ JSON: {\"buscas\": [\"...\"]}", False, 25)
        if isinstance(r, dict) and r.get("buscas"):
            return [str(b) for b in r["buscas"]][:5]
    return [tema, f"{tema} vantagens e desvantagens", f"{tema} 2026"]


def juntar_links(resultados: list[list[dict]], maximo: int = 8) -> list[dict]:
    """Intercala os resultados de cada busca, um site por domínio (pura)."""
    vistos, saida = set(), []
    for rodada in range(10):
        for lista in resultados:
            if rodada < len(lista):
                r = lista[rodada]
                url = r.get("href") or r.get("url") or ""
                dom = re.sub(r"^www\.", "", url.split("/")[2]) if url.count("/") >= 2 else url
                if url and dom not in vistos and not re.search(r"(youtube|facebook|instagram|tiktok)\.com", dom):
                    vistos.add(dom)
                    saida.append({"url": url, "titulo": r.get("title", ""), "trecho": r.get("body", "")})
            if len(saida) >= maximo:
                return saida
    return saida


def _ler(fonte: dict) -> dict:
    try:
        texto, titulo = _web.get_texto(fonte["url"], timeout=15, limite=12_000)
        return {**fonte, "texto": texto, "titulo": fonte["titulo"] or titulo}
    except Exception:
        return {**fonte, "texto": fonte.get("trecho", "")}


def relatorio_local(tema: str, fontes: list[dict]) -> str:
    """Sem IA: os trechos de cada fonte, citados (pura)."""
    linhas = [f"# {tema}", "", "_Sem IA disponível: abaixo, o trecho principal de cada fonte._", ""]
    for i, f in enumerate(fontes, 1):
        trecho = (f.get("texto") or f.get("trecho") or "").strip().replace("\n", " ")[:500]
        linhas.append(f"- {trecho} [{i}]")
    return "\n".join(linhas)


def _rodar(tema: str, player) -> None:
    t0 = time.time()
    try:
        from actions import ddg_isolado               # busca num processo separado: se cair, não derruba o JARVIS
        qs = buscas(tema)
        resultados = []
        for q in qs:
            try:
                resultados.append(list(ddg_isolado.buscar("text", q, 6, region="br-pt")))
            except Exception as e:
                print(f"[Pesquisa] busca '{q}': {e}")
        fontes = juntar_links(resultados)
        if not fontes:
            raise RuntimeError("a busca não trouxe resultados")
        with ThreadPoolExecutor(max_workers=6) as ex:
            fontes = [f for f in ex.map(_ler, fontes) if (f.get("texto") or "").strip()]
        from plugins import _ia
        corpo = ""
        if _ia.disponivel():
            material = "\n\n".join(f"[{i}] {f['titulo']} — {f['url']}\n{f['texto'][:5000]}" for i, f in enumerate(fontes, 1))
            corpo = _ia.perguntar(
                f"Escreva um relatório de pesquisa em português do Brasil sobre: \"{tema}\". Use SOMENTE as fontes "
                "abaixo. Formato Markdown: '# título', '## Resumo' (3-5 frases), '## Pontos principais' (lista), "
                "'## Onde as fontes discordam ou têm limites', '## Conclusão prática'. TODA afirmação factual termina "
                "com a citação [n] da fonte de onde veio; o que as fontes não dizem, diga que não foi encontrado. Não "
                "invente números.\n\nFONTES:\n" + material, True, 120) or ""
        if not corpo:
            corpo = relatorio_local(tema, fontes)
        refs = "\n".join(f"[{i}] {f['titulo'] or f['url']} — {f['url']}" for i, f in enumerate(fontes, 1))
        texto = corpo.strip() + "\n\n## Fontes\n" + refs + f"\n\n_Pesquisado em {time.strftime('%d/%m/%Y %H:%M')}._\n"
        nome = re.sub(r"[^\w\- ]", "", tema)[:60].strip() or "pesquisa"
        arq = pasta_jarvis("Pesquisas") / f"{nome}.md"
        arq.write_text(texto, encoding="utf-8")
        resumo = re.search(r"## Resumo\s*(.+?)(\n## |\Z)", corpo, re.S)
        _estado["ultimo"] = {"tema": tema, "arquivo": str(arq), "resumo": (resumo.group(1).strip() if resumo else corpo[:600]),
                             "fontes": len(fontes)}
        mostrar(player, f"PESQUISA — {tema[:40].upper()}", texto)
        from plugins._notificar import notificar
        notificar(player, f"Terminei a pesquisa sobre {tema}: {len(fontes)} fontes em {int(time.time() - t0)} s. "
                          f"Salvei em {arq.name}.", "Pesquisa profunda")
    except Exception as e:
        registrar(player, f"Pesquisa profunda falhou: {e}")
        from plugins._comum import avisar
        avisar(player, f"A pesquisa sobre {tema} falhou: {e}", "PESQUISA")
    finally:
        _estado["rodando"] = False


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "pesquisar").lower()
    if a == "ultima":
        u = _estado["ultimo"]
        if not u:
            return "Ainda não fiz nenhuma pesquisa profunda nesta sessão."
        return f"[PESQUISA] Sobre '{u['tema']}' ({u['fontes']} fontes; arquivo {Path(u['arquivo']).name}). Resumo: {u['resumo']}"
    tema = str(p.get("tema") or "").strip()
    if not tema:
        return "Sobre o que devo pesquisar?"
    if _estado["rodando"]:
        return "Já estou fazendo uma pesquisa; aviso quando terminar."
    _estado["rodando"] = True
    threading.Thread(target=_rodar, args=(tema, player), daemon=True, name="pesquisa_profunda").start()
    return f"Comecei a pesquisa sobre '{tema}'. Leva de 1 a 3 minutos; eu aviso quando terminar."

