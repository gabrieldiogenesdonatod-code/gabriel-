"""
Sistema de habilidades combináveis — ideia 13 (fork PT-BR 1.4).

Em vez de cada função ser isolada, o JARVIS tem habilidades PEQUENAS que se
encaixam umas nas outras, e a saída de uma vira a entrada da próxima:

    buscar_arquivos → ler_arquivos → resumir → gerar_relatorio → abrir

Além das habilidades internas, QUALQUER ferramenta do JARVIS pode ser um
passo (limpeza, downloads, controle_pc, protocolos, plugins novos…).

    "Jarvis, procura os arquivos do orçamento, resume e gera um relatório"
    "Jarvis, organiza os downloads e depois mostra a saúde do PC"
    "Jarvis, salva essa sequência como 'relatório semanal'"   (vira uma
                                                               habilidade maior)
    "Jarvis, roda a habilidade relatório semanal"

O PLANO vem do modelo de IA quando há chave (ele recebe o catálogo de
habilidades e devolve a cadeia em JSON) e, sem IA, de regras locais por
palavras-chave. Antes de rodar, CADA passo passa pelo guardião de decisões: se
algum for arriscado, a cadeia inteira pede UMA confirmação na tela; se algum
for bloqueado, nada roda.

Cadeias salvas ficam em memory/habilidades.json.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

from plugins._comum import (MEMORIA, abrir_no_sistema, confirmar, gravar_json, ler_json, mostrar,
                            pasta_usuario, registrar)

PLUGIN = {
    "name": "habilidades",
    "brief": "Chain small skills (search files, read, summarise, report, any tool) into one task.",
    "description": (
        "Composable skills: turns a multi-step request into a chain where each step's output feeds the "
        "next (search files → read → summarise → report → open, or any JARVIS tool as a step). "
        "action='executar' with pedido = the user's full request (e.g. 'find the budget files, "
        "summarise them and make a report'); 'planejar' shows the chain without running; 'salvar' "
        "with nome saves the last chain as a named skill; 'rodar' with nome runs a saved one; "
        "'listar' lists skills. Risky steps ask for one on-screen confirmation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "executar | planejar | salvar | rodar | listar | apagar"},
            "pedido": {"type": "STRING"}, "nome": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_ARQ = MEMORIA / "habilidades.json"
_ultimo: dict = {}          # último plano, para "salva essa sequência"


# ── habilidades internas ───────────────────────────────────────────────────────
def _caminhos(entrada) -> list[Path]:
    if isinstance(entrada, (list, tuple)):
        return [Path(x) for x in entrada if isinstance(x, (str, Path)) and Path(x).exists()]
    if isinstance(entrada, (str, Path)) and str(entrada) and Path(str(entrada)).exists():
        return [Path(entrada)]
    return []


def h_buscar_arquivos(params: dict, entrada=None):
    from plugins.controle_sistema import buscar
    termo = str(params.get("termo") or "").strip()
    if not termo:
        return []
    return buscar(termo, pasta=str(params.get("pasta") or ""), conteudo=bool(params.get("conteudo")),
                  limite=int(params.get("limite") or 10), segundos=float(params.get("segundos") or 8))


_TEXTO = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html", ".htm", ".css", ".log", ".ini",
          ".xml", ".yml", ".yaml", ".bat", ".ps1", ".sql"}


def ler_um(arq: Path, limite: int = 20000) -> str:
    suf = arq.suffix.lower()
    try:
        if suf in _TEXTO:
            return arq.read_text(encoding="utf-8", errors="replace")[:limite]
        if suf == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return "(PDF: instale pypdf para ler)"
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(arq)).pages[:30])[:limite]
        if suf == ".docx":
            try:
                import docx
            except ImportError:
                return "(Word: instale python-docx para ler)"
            return "\n".join(par.text for par in docx.Document(str(arq)).paragraphs)[:limite]
        if suf in (".xlsx", ".xlsm"):
            try:
                import openpyxl
            except ImportError:
                return "(Excel: instale openpyxl para ler)"
            wb = openpyxl.load_workbook(str(arq), read_only=True, data_only=True)
            linhas = []
            for ws in wb.worksheets[:3]:
                for row in ws.iter_rows(max_row=200, values_only=True):
                    linhas.append(" | ".join("" if v is None else str(v) for v in row))
            return "\n".join(linhas)[:limite]
    except Exception as e:
        return f"(não consegui ler: {e})"
    return f"(tipo {suf or 'sem extensão'} não é lido como texto)"


def h_ler_arquivos(params: dict, entrada=None):
    arqs = _caminhos(entrada) or _caminhos(params.get("arquivos") or params.get("caminho"))
    return {a.name: ler_um(a) for a in arqs[:int(params.get("limite") or 8)]}


_PARADAS = set("""a o e é de da do das dos em no na nos nas um uma uns umas para por com sem que se
como mais mas ou ao aos à às pelo pela pelos pelas este esta isso isto esse essa seu sua seus suas
the and of to in is it for on with as at be this that are was""".split())


def resumo_extrativo(texto: str, frases: int = 5) -> str:
    """Resumo sem IA: escolhe as frases com as palavras mais frequentes do texto."""
    partes = [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n{2,}", texto) if len(f.strip()) > 25]
    if len(partes) <= frases:
        return " ".join(partes) if partes else texto[:600]
    palavras = Counter(w for w in re.findall(r"\w{3,}", texto.lower()) if w not in _PARADAS)
    def nota(f: str) -> float:
        ws = [w for w in re.findall(r"\w{3,}", f.lower()) if w not in _PARADAS]
        return sum(palavras[w] for w in ws) / (len(ws) ** 0.7 or 1)
    escolhidas = sorted(sorted(range(len(partes)), key=lambda i: -nota(partes[i]))[:frases])
    return " ".join(partes[i] for i in escolhidas)


def h_resumir(params: dict, entrada=None):
    if isinstance(entrada, dict):
        blocos = {k: v for k, v in entrada.items() if isinstance(v, str)}
    else:
        blocos = {"texto": str(entrada if entrada is not None else params.get("texto") or "")}
    from plugins import _ia
    saida = {}
    for nome, txt in blocos.items():
        if not txt.strip():
            continue
        r = _ia.perguntar("Resuma em português do Brasil, em até 5 frases objetivas, o conteúdo abaixo.\n\n"
                          + txt[:12000], inteligente=False) if _ia.disponivel() else None
        saida[nome] = r or resumo_extrativo(txt, int(params.get("frases") or 5))
    return saida


def h_gerar_relatorio(params: dict, entrada=None) -> str:
    titulo = str(params.get("titulo") or "Relatório do JARVIS")
    pasta = MEMORIA / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = []
    if isinstance(entrada, dict):
        for k, v in entrada.items():
            corpo.append(f"<h2>{_esc(k)}</h2><p>{_esc(str(v)).replace(chr(10), '<br>')}</p>")
    elif isinstance(entrada, (list, tuple)):
        corpo.append("<ul>" + "".join(f"<li>{_esc(str(x))}</li>" for x in entrada) + "</ul>")
    else:
        corpo.append(f"<p>{_esc(str(entrada or params.get('texto') or '')).replace(chr(10), '<br>')}</p>")
    html = (f"<!doctype html><html lang='pt-br'><meta charset='utf-8'><title>{_esc(titulo)}</title>"
            "<body style='font:15px Segoe UI,Arial;max-width:860px;margin:30px auto;color:#123'>"
            f"<h1>{_esc(titulo)}</h1><p style='color:#678'>Gerado pelo J.A.R.V.I.S BR em "
            f"{time.strftime('%d/%m/%Y %H:%M')}</p>{''.join(corpo)}</body></html>")
    arq = pasta / f"{re.sub(r'[^0-9A-Za-zÀ-ú]+', '_', titulo).strip('_')[:50]}_{time.strftime('%Y%m%d_%H%M%S')}.html"
    arq.write_text(html, encoding="utf-8")
    return str(arq)


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def h_salvar_arquivo(params: dict, entrada=None) -> str:
    nome = re.sub(r'[<>:"/\\|?*]+', "_", str(params.get("nome") or f"jarvis_{time.strftime('%Y%m%d_%H%M%S')}.txt"))
    if "." not in nome:
        nome += ".txt"
    pasta = pasta_usuario("Documents") / "JARVIS"
    pasta.mkdir(parents=True, exist_ok=True)
    conteudo = entrada if entrada is not None else params.get("texto", "")
    if not isinstance(conteudo, str):
        conteudo = json.dumps(conteudo, ensure_ascii=False, indent=2, default=str)
    arq = pasta / nome
    arq.write_text(conteudo, encoding="utf-8")
    return str(arq)


def h_abrir(params: dict, entrada=None) -> str:
    alvos = _caminhos(entrada) or _caminhos(params.get("caminho"))
    if not alvos:
        return "nada para abrir"
    abrir_no_sistema(str(alvos[0]))
    return f"abri {alvos[0].name}"


def h_recentes(params: dict, entrada=None):
    from plugins.controle_sistema import recentes
    return recentes(int(params.get("n") or 10))


INTERNAS = {
    "buscar_arquivos": (h_buscar_arquivos, "procura arquivos por nome (termo, pasta, conteudo)"),
    "arquivos_recentes": (h_recentes, "lista os arquivos mexidos por último (n)"),
    "ler_arquivos": (h_ler_arquivos, "lê o texto dos arquivos recebidos (txt, md, código, pdf, docx, xlsx)"),
    "resumir": (h_resumir, "resume o texto recebido (com IA quando houver; senão, resumo extrativo)"),
    "gerar_relatorio": (h_gerar_relatorio, "gera um relatório HTML com o que recebeu (titulo)"),
    "salvar_arquivo": (h_salvar_arquivo, "salva o que recebeu em Documentos/JARVIS (nome)"),
    "abrir": (h_abrir, "abre o arquivo recebido no programa padrão"),
}


# ── planejamento ───────────────────────────────────────────────────────────────
_VERBOS = (r"abr|fech|resum|salv|ger|cri|mostr|organiz|limp|procur|busc|ach|encontr|faz|fa[cç]|tir|"
           r"l[eê]|coloc|bot|aument|diminu|baix|sub|lig|deslig|bloque|pesquis|anot|lembr|rod|execut|"
           r"verific|diagnostic|me\s+(?:mostr|diz|fal|avis)")
_NOMES = r"volume\b|brilho\b|modo\s+(?:jogo|escuro)|protocolo\b|luz\b|luzes\b|tomada\b|cena\b"
_CORTE = re.compile(r"\s*(?:;|\.\s+|,?\s+e\s+depois\s+|,?\s+depois\s+|,?\s+e\s+ent[aã]o\s+|,?\s+em\s+seguida\s+|"
                    r",\s+(?=(?:e\s+)?(?:" + _VERBOS + r"|" + _NOMES + r"))|\s+e\s+(?=(?:" + _VERBOS + r"|" + _NOMES + r")))", re.I)


def dividir(pedido: str) -> list[str]:
    return [p.strip(" ,.") for p in _CORTE.split(pedido or "") if p and p.strip(" ,.")]


def _p(ferramenta: str, params: dict, descricao: str) -> dict:
    return {"ferramenta": ferramenta, "params": params, "descricao": descricao}


_REGRAS: list[tuple[str, callable]] = [
    (r"(?:pesquis\w*|procur\w*\s+na\s+internet|busc\w*\s+na\s+internet|(?:procur|busc)\w*\s+no\s+google)"
     r"\s+(?:sobre\s+|por\s+)?(?P<x>.+)",
     lambda m, t: _p("web_search", {"query": m["x"]}, f"pesquisar '{m['x']}' na internet")),
    (r"\babr\w*\s+(?:o|a)\s+(?:relat[oó]rio|arquivo|resultado|resumo)",
     lambda m, t: _p("abrir", {}, "abrir o resultado")),
    (r"\bsalv\w*\s+(?:tudo\s+|isso\s+)?(?:em|num|como)?\s*(?:um\s+)?arquivo",
     lambda m, t: _p("salvar_arquivo", {}, "salvar em arquivo")),
    (r"(?:procur|busc|ach|encontr)\w*\s+(?:os\s+|as\s+|o\s+|a\s+|meus\s+|minhas\s+)?"
     r"(?:arquivos?|documentos?|planilhas?|fotos?|pdfs?|notas?)?\s*(?:de|do|da|dos|das|sobre|com|chamad\w+)?\s*(?P<x>.+)",
     lambda m, t: _p("buscar_arquivos", {"termo": m["x"], "conteudo": "conteúdo" in t or "conteudo" in t},
                     f"procurar arquivos de '{m['x']}'")),
    (r"(?:arquivos?|documentos?)\s+(?:recentes|de hoje|que mexi)",
     lambda m, t: _p("arquivos_recentes", {"n": 10}, "listar arquivos recentes")),
    (r"\b(?:l[eê]|leia|ler)\b", lambda m, t: _p("ler_arquivos", {}, "ler os arquivos")),
    (r"resum", lambda m, t: _p("resumir", {}, "resumir")),
    (r"relat[oó]rio", lambda m, t: _p("gerar_relatorio", {"titulo": _titulo(t)}, "gerar relatório")),
    (r"organiz\w*\s+(?:os\s+|a\s+pasta\s+de\s+)?downloads?",
     lambda m, t: _p("downloads", {"action": "organizar"}, "organizar os downloads")),
    (r"\blimp\w*", lambda m, t: _p("limpeza", {"action": "previa"}, "ver quanto a limpeza liberaria")),
    (r"(?:sa[uú]de|status|diagn[oó]stico)\s+(?:do\s+)?(?:pc|computador|sistema)",
     lambda m, t: _p("saude_pc", {"action": "verificar"}, "checar a saúde do PC")),
    (r"internet|\brede\b|wi-?fi", lambda m, t: _p("assistente_rede", {"action": "diagnosticar"}, "diagnosticar a internet")),
    (r"\b(?:clima|previs[aã]o do tempo)\b", lambda m, t: _p("weather_report", {"city": ""}, "ver o clima")),
    (r"\bvolume\s+(?:para\s+|em\s+|no\s+)?(?P<x>\d{1,3}|mais|menos)",
     lambda m, t: _p("controle_audio_video", {"action": "volume", "nivel": m["x"]}, f"volume {m['x']}")),
    (r"\b(?:muta|mudo|silenci)", lambda m, t: _p("controle_audio_video", {"action": "mudo", "ligar": "sim"}, "silenciar")),
    (r"modo\s+jogo", lambda m, t: _p("modo_jogo", {"action": "ligar"}, "ligar o modo jogo")),
    (r"protocolo\s+(?P<x>[\w ]+)", lambda m, t: _p("protocolos", {"action": "executar", "nome": m["x"].strip()},
                                                  f"rodar o protocolo {m['x'].strip()}")),
    (r"\b(?:anot|lembr|guard)\w*\s+(?:que\s+)?(?P<x>.+)",
     lambda m, t: _p("memoria_inteligente", {"action": "lembrar", "texto": m["x"]}, f"guardar: {m['x']}")),
    (r"\b(?P<v>lig|deslig|apag|acend)\w*\s+(?:a\s+|o\s+|as\s+)?(?P<x>(?:luz|luzes|l[aâ]mpada|tomada|ventilador)\b.*)",
     lambda m, t: _p("casa_inteligente", {"action": "ligar" if m["v"].lower() in ("lig", "acend") else "desligar",
                                         "aparelho": m["x"]}, f"{'ligar' if m['v'].lower() in ('lig', 'acend') else 'desligar'} {m['x']}")),
    (r"\bcena\s+(?P<x>[\w ]+)", lambda m, t: _p("casa_inteligente", {"action": "cena", "nome": m["x"].strip()},
                                                f"cena {m['x'].strip()}")),
    (r"bloque\w*\s+(?:a\s+)?(?:tela|pc|computador)", lambda m, t: _p("controle_pc", {"action": "bloquear"}, "bloquear a tela")),
    (r"\bfech\w*\s+(?:o\s+|a\s+)?(?P<x>.+)",
     lambda m, t: _p("controle_pc", {"action": "fechar", "alvo": m["x"]}, f"fechar {m['x']}")),
    (r"\b(?:abr|inici)\w*\s+(?:o\s+|a\s+)?(?P<x>.+)",
     lambda m, t: _p("controle_pc", {"action": "abrir", "alvo": m["x"]}, f"abrir {m['x']}")),
]


def _titulo(t: str) -> str:
    m = re.search(r"relat[oó]rio\s+(?:de|do|da|sobre)\s+(.+)", t, re.I)
    return f"Relatório — {m.group(1).strip()}" if m else "Relatório do JARVIS"


def planejar_local(pedido: str) -> list[dict]:
    """Cadeia de passos por regras, sem IA (pura)."""
    passos = []
    for parte in dividir(pedido):
        t = parte.lower()
        for rx, fazer in _REGRAS:
            m = re.search(rx, parte, re.I)
            if m:
                passo = fazer(m, t)
                passos.append(passo)
                # "procura X e resume" → ler antes de resumir
                break
        else:
            passos.append(_p("manual", {}, parte))
    # costura: depois de buscar arquivos, resumir/relatório precisam do texto
    saida = []
    for i, p in enumerate(passos):
        anterior = saida[-1]["ferramenta"] if saida else ""
        if p["ferramenta"] in ("resumir", "gerar_relatorio") and anterior in ("buscar_arquivos", "arquivos_recentes"):
            saida.append(_p("ler_arquivos", {}, "ler os arquivos"))
        if p["ferramenta"] == "abrir" and anterior in ("resumir", "ler_arquivos"):
            saida.append(_p("gerar_relatorio", {"titulo": _titulo(pedido)}, "gerar relatório"))
        saida.append(p)
    return saida


def descrever_passo(p: dict) -> str:
    f = p.get("ferramenta", "?")
    if f == "manual":
        return f"(manual) {p.get('descricao', '')}"
    return p.get("descricao") or f


def catalogo() -> str:
    linhas = [f"- {k}: {v[1]}" for k, v in INTERNAS.items()]
    try:
        from core import registro_ferramentas
        for d in registro_ferramentas.declaracoes():
            linhas.append(f"- {d.get('name')}: {(d.get('brief') or d.get('description') or '')[:160]} "
                          f"params={list(((d.get('parameters') or {}).get('properties') or {}).keys())}")
    except Exception:
        pass
    return "\n".join(linhas)


def planejar(pedido: str) -> tuple[list[dict], str]:
    from plugins import _ia
    if _ia.disponivel():
        r = _ia.perguntar_json(
            "Você monta cadeias de passos para o assistente JARVIS. Cada passo usa UMA habilidade do "
            "catálogo; a saída de um passo é entregue ao próximo automaticamente (habilidades internas "
            "recebem a saída como entrada; em ferramentas, use o texto {saida_anterior} num parâmetro "
            "para injetá-la). Use o mínimo de passos.\nCATÁLOGO:\n" + catalogo()[:9000]
            + f"\n\nPedido: \"{pedido}\"\nResponda SÓ JSON: "
            '{"passos": [{"ferramenta": "nome", "params": {}, "descricao": "curta, pt-BR"}]}', True, 45)
        passos = (r or {}).get("passos") if isinstance(r, dict) else None
        if isinstance(passos, list) and passos and all(isinstance(x, dict) and x.get("ferramenta") for x in passos):
            return [_p(str(x["ferramenta"]), x.get("params") or {}, str(x.get("descricao") or x["ferramenta"]))
                    for x in passos[:12]], "IA"
    return planejar_local(pedido), "regras locais"


# ── execução ───────────────────────────────────────────────────────────────────
def _injetar(params: dict, saida) -> dict:
    txt = saida if isinstance(saida, str) else json.dumps(saida, ensure_ascii=False, default=str)
    return {k: (v.replace("{saida_anterior}", txt[:3000]) if isinstance(v, str) else v) for k, v in params.items()}


def _texto_saida(saida) -> str:
    if isinstance(saida, list):
        return f"{len(saida)} item(ns): " + ", ".join(Path(str(x)).name for x in saida[:5])
    if isinstance(saida, dict):
        return "; ".join(f"{k}: {str(v)[:120]}" for k, v in list(saida.items())[:3])
    return str(saida)[:200]


def rodar_cadeia(passos: list[dict], player=None, nome: str = "cadeia") -> list[dict]:
    """Executa sem perguntar nada (quem chama já passou pelo guardião)."""
    from core import registro_ferramentas, registro_uso
    saida, registros, t_ini = None, [], time.perf_counter()
    for p in passos:
        t0 = time.perf_counter()
        ok, res = True, None
        try:
            f = p.get("ferramenta")
            if f in INTERNAS:
                res = INTERNAS[f][0](p.get("params") or {}, saida)
            elif f == "manual":
                ok, res = False, "precisa ser feito à mão"
            else:
                res = registro_ferramentas.executar(f, _injetar(p.get("params") or {}, saida), player)
                ok = not registro_uso.parece_falha(str(res))
        except Exception as e:
            ok, res = False, f"erro: {e}"
        registros.append({"descricao": descrever_passo(p), "ms": int((time.perf_counter() - t0) * 1000),
                          "ok": ok, "resultado": _texto_saida(res)})
        registrar(player, f"Habilidade: {descrever_passo(p)} → {'ok' if ok else 'falhou'}")
        if not ok and p.get("ferramenta") != "manual":
            break
        saida = res
    try:
        registro_uso.registrar_tarefa("habilidades", nome, registros,
                                      int((time.perf_counter() - t_ini) * 1000), all(r["ok"] for r in registros))
    except Exception:
        pass
    return registros


def avaliar_cadeia(passos: list[dict]) -> tuple[str, list[str]]:
    """'automático' | 'confirmar' | 'bloquear' para a cadeia inteira, com os motivos."""
    from plugins import _guardiao
    pior, motivos = "automático", []
    ordem = {"automático": 0, "confirmar": 1, "bloquear": 2}
    for p in passos:
        if p.get("ferramenta") in INTERNAS or p.get("ferramenta") == "manual":
            continue
        av = _guardiao.avaliar(p.get("ferramenta", ""), p.get("params") or {}, p.get("descricao", ""))
        if ordem[av.decisao] > 0:
            motivos.append(av.texto())
        if ordem[av.decisao] > ordem[pior]:
            pior = av.decisao
    return pior, motivos


def executar(passos: list[dict], player=None, nome: str = "cadeia") -> str:
    if not passos:
        return "Não consegui montar passos para esse pedido."
    decisao, motivos = avaliar_cadeia(passos)
    lista = "\n".join(f"{i}. {descrever_passo(p)}" for i, p in enumerate(passos, 1))
    if decisao == "bloquear":
        mostrar(player, "HABILIDADES — BLOQUEADO", lista + "\n\n" + "\n".join(motivos))
        return "Não rodei a cadeia: o guardião bloqueou um dos passos. " + (motivos[0] if motivos else "")

    def fazer() -> str:
        regs = rodar_cadeia(passos, player, nome)
        ok = sum(1 for r in regs if r["ok"])
        mostrar(player, "HABILIDADES — RESULTADO",
                "\n".join(f"{'✔' if r['ok'] else '✖'} {r['descricao']} ({r['ms']} ms) → {r['resultado']}" for r in regs))
        ultimo = regs[-1]["resultado"] if regs else ""
        return f"Cadeia concluída: {ok} de {len(passos)} passo(s) ok. Último resultado: {ultimo}"

    if decisao == "confirmar":
        return confirmar(f"habilidades:{nome}", f"Rodar {len(passos)} passo(s)?",
                         lista + "\n\nPor quê confirmar:\n" + "\n".join(motivos[:5]), fazer)
    return fazer()


def run(parameters: dict, player=None, session_memory=None) -> str:
    global _ultimo
    p = parameters or {}
    acao = str(p.get("action") or "executar").lower()
    salvas = ler_json(_ARQ, {}) or {}
    try:
        if acao == "listar":
            internas = ", ".join(INTERNAS)
            nomes = ", ".join(salvas) or "nenhuma ainda"
            return f"Habilidades internas: {internas}. Habilidades salvas: {nomes}. Qualquer ferramenta também vira passo."
        if acao == "salvar":
            nome = str(p.get("nome") or "").strip().lower()
            if not nome or not _ultimo:
                return "Diga o nome, e antes rode ou planeje uma cadeia para eu salvar."
            salvas[nome] = dict(_ultimo, criada=time.strftime("%Y-%m-%d %H:%M"))
            gravar_json(_ARQ, salvas)
            return f"Salvei a habilidade '{nome}' com {len(_ultimo['passos'])} passo(s)."
        if acao == "apagar":
            nome = str(p.get("nome") or "").strip().lower()
            if salvas.pop(nome, None) is None:
                return f"Não tenho habilidade '{nome}'."
            gravar_json(_ARQ, salvas)
            return f"Apaguei a habilidade '{nome}'."
        if acao == "rodar":
            nome = str(p.get("nome") or "").strip().lower()
            h = salvas.get(nome) or next((v for k, v in salvas.items() if nome and nome in k), None)
            if not h:
                return f"Não tenho a habilidade '{nome}'. Salvas: {', '.join(salvas) or 'nenhuma'}."
            return executar(h["passos"], player, nome)
        pedido = str(p.get("pedido") or "").strip()
        if not pedido:
            return "Qual é o pedido?"
        passos, origem = planejar(pedido)
        _ultimo = {"pedido": pedido, "passos": passos}
        if acao == "planejar":
            lista = "\n".join(f"{i}. {descrever_passo(x)}" for i, x in enumerate(passos, 1))
            mostrar(player, f"PLANO ({origem})", lista)
            return f"Plano com {len(passos)} passo(s), feito por {origem}: " + "; ".join(descrever_passo(x) for x in passos)
        return executar(passos, player, pedido[:40])
    except Exception as e:
        return f"As habilidades falharam: {e}"
