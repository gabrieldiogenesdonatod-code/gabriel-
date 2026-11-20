"""
JARVIS que se melhora (fork PT-BR 1.5).

Ele junta os ERROS de verdade que aconteceram (exceções das ferramentas e das
threads em segundo plano, com o traceback), agrupa por arquivo e linha, lê o
código em volta e propõe uma CORREÇÃO pequena. Antes de mostrar para você:

    1. aplica a correção numa CÓPIA do JARVIS (laboratório);
    2. compila e roda todos os testes nessa cópia;
    3. só então mostra o "antes e depois" (diff) e o resultado dos testes.

NADA É ALTERADO SEM VOCÊ: aplicar exige o botão CONFIRMAR (e verificação
recente, pela verificação da 1.5). Antes de mudar, guarda uma cópia
(arquivo.bak-DATA) e "Jarvis, desfaz" volta o arquivo original.
A correção vale depois de reiniciar o JARVIS.

    "Jarvis, analisa seus erros"            "Jarvis, mostra a correção 2"
    "Jarvis, aplica a correção 2"           "Jarvis, descarta a correção 2"

Sem chave de IA: mostra os erros agrupados, com a explicação local
(módulo faltando, None, arquivo não encontrado…) e onde estão.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path

from plugins._comum import BASE, CNW, MEMORIA, confirmar, desfazer, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "auto_melhoria",
    "brief": "Self-improvement: groups real errors with tracebacks, proposes small fixes tested in a sandbox copy.",
    "description": (
        "JARVIS self-improvement: collects its own exceptions (with tracebacks), groups them, and proposes small code "
        "fixes that are applied to a sandbox copy and tested before being shown. Nothing changes without approval. "
        "action='analisar' ('analyse your errors'), 'erros' (recent errors), 'listar' (proposals), 'ver' with id, "
        "'aplicar' with id (on-screen confirmation, backup, undo), 'descartar' with id."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "analisar | erros | listar | ver | aplicar | descartar"},
            "id": {"type": "STRING"},
        },
        "required": [],
    },
}

_ARQ = MEMORIA / "auto_melhoria.json"
_iniciado = threading.Event()


def agrupar(erros: list[dict]) -> list[dict]:
    """Junta erros iguais (arquivo, linha, tipo); mais frequentes primeiro (pura)."""
    grupos = defaultdict(list)
    for e in erros:
        grupos[(e.get("arquivo") or "?", int(e.get("linha") or 0), e.get("tipo") or "Erro")].append(e)
    saida = []
    for (arq, linha, tipo), lista in grupos.items():
        ultimo = lista[-1]
        saida.append({"arquivo": arq, "linha": linha, "tipo": tipo, "vezes": len(lista),
                      "mensagem": ultimo.get("mensagem", ""), "traceback": ultimo.get("traceback", ""),
                      "origens": sorted({x.get("origem", "") for x in lista})})
    return sorted(saida, key=lambda g: -g["vezes"])


def trecho(arquivo: str, linha: int, raio: int = 18) -> str:
    p = BASE / arquivo
    if not p.is_file() or not linha:
        return ""
    linhas = p.read_text(encoding="utf-8", errors="replace").splitlines()
    ini, fim = max(0, linha - raio - 1), min(len(linhas), linha + raio)
    return "\n".join(f"{i + 1:5d}{'>' if i + 1 == linha else ' '} {linhas[i]}" for i in range(ini, fim))


def diff(arquivo: str, antes: str, depois: str) -> str:
    return "".join(difflib.unified_diff(antes.splitlines(True), depois.splitlines(True),
                                        fromfile=f"a/{arquivo}", tofile=f"b/{arquivo}", n=3))


_TESTES = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
_base: dict = {"falhando": None, "quando": 0.0}


def falhando_na_saida(saida: str) -> set[str]:
    """Nomes dos testes que falharam, pela saída do unittest (pura)."""
    return set(re.findall(r"^(?:FAIL|ERROR): (\S+ \([^)]*\))", saida, re.M))


def rodar_testes(caixa: Path) -> tuple[bool, int, set[str], str]:
    """(passou, quantos rodaram, quais falharam, fim da saída) dos testes na cópia."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(caixa))
    try:
        r = subprocess.run(_TESTES, cwd=str(caixa), capture_output=True, timeout=600, env=env, **CNW)
    except subprocess.TimeoutExpired:
        return False, 0, set(), "os testes passaram de 10 minutos"
    saida = ((r.stdout or b"") + b"\n" + (r.stderr or b"")).decode("utf-8", "replace")
    m = re.search(r"Ran (\d+) tests?", saida)
    return r.returncode == 0, int(m.group(1)) if m else 0, falhando_na_saida(saida), saida.strip()[-600:]


def falhando_hoje() -> set[str] | None:
    """Testes que JÁ falham no JARVIS como está (numa cópia). Guardado por 1 h.
    Assim uma correção só precisa não criar NENHUMA falha nova."""
    from plugins import laboratorio
    if time.time() - _base["quando"] < 3600:
        return _base["falhando"]
    with tempfile.TemporaryDirectory(prefix="jarvis_base_") as tmp:
        caixa = Path(tmp) / "jarvis"
        laboratorio.copiar_projeto(BASE, caixa)
        _ok, rodados, falhando, _fim = rodar_testes(caixa)
    _base.update(falhando=falhando if rodados else None, quando=time.time())
    return _base["falhando"]


def validar(arquivo: str, trocar: str, por: str, antes: set[str] | None = None) -> tuple[bool, str, str]:
    """Aplica numa cópia do JARVIS, compila e roda os testes. (ok, resumo, diff).
    ok = compila, os testes rodam e nenhum teste que passava passou a falhar."""
    from plugins import laboratorio
    antes = antes or set()
    original = (BASE / arquivo).read_text(encoding="utf-8")
    if original.count(trocar) != 1:
        return False, "o trecho a trocar não aparece exatamente uma vez no arquivo", ""
    novo = original.replace(trocar, por, 1)
    d = diff(arquivo, original, novo)
    with tempfile.TemporaryDirectory(prefix="jarvis_melhoria_") as tmp:
        caixa = Path(tmp) / "jarvis"
        laboratorio.copiar_projeto(BASE, caixa)
        (caixa / arquivo).write_text(novo, encoding="utf-8")
        r = laboratorio.rodar_uma(caixa, [sys.executable, "-m", "py_compile", arquivo], 60)
        if not r["ok"]:
            return False, "não compila: " + r["fim"][-300:], d
        passou, rodados, falhando, fim = rodar_testes(caixa)
    if not rodados:
        return False, "os testes não rodaram: " + fim[-300:], d
    novas = sorted(falhando - antes)
    resumo = f"testes: {rodados} rodados, {len(falhando)} falha(s)"
    if antes:
        resumo += f" ({len(antes)} já falhava(m) antes da correção)"
    if novas:
        resumo += "; NOVAS falhas: " + ", ".join(novas[:3])
    return (passou or not novas), resumo, d


def propor(grupo: dict, antes: set[str] | None = None) -> dict | None:
    from plugins import _ia
    codigo = trecho(grupo["arquivo"], grupo["linha"])
    if not codigo or not _ia.disponivel():
        return None
    r = _ia.perguntar_json(
        "Você corrige bugs no projeto J.A.R.V.I.S BR (Python). Proponha a MENOR correção segura para o erro abaixo, "
        "sem mudar comportamento além do necessário. O campo 'trocar' deve ser um trecho EXATO do arquivo (copiado, "
        "com a mesma indentação, de 1 a 15 linhas) que aparece uma única vez; 'por' é o trecho novo.\n"
        f"ARQUIVO: {grupo['arquivo']} (linha {grupo['linha']})\nERRO ({grupo['vezes']}x): {grupo['tipo']}: "
        f"{grupo['mensagem']}\nTRACEBACK:\n{grupo['traceback'][-2500:]}\n\nCÓDIGO (número, '>' marca a linha):\n{codigo}\n\n"
        'Responda SÓ JSON: {"trocar": "...", "por": "...", "explicacao": "uma frase em pt-BR"}', True, 90)
    if not isinstance(r, dict) or not r.get("trocar"):
        return None
    ok, resumo, d = validar(grupo["arquivo"], str(r["trocar"]), str(r.get("por", "")), antes)
    return {"arquivo": grupo["arquivo"], "linha": grupo["linha"], "erro": f"{grupo['tipo']}: {grupo['mensagem']}",
            "vezes": grupo["vezes"], "trocar": r["trocar"], "por": r.get("por", ""), "explicacao": r.get("explicacao", ""),
            "valida": ok, "testes": resumo, "diff": d, "estado": "pendente", "criada": time.strftime("%Y-%m-%d %H:%M")}


def analisar(dias: float = 7) -> tuple[list[dict], list[dict]]:
    from core import registro_uso
    grupos = agrupar(registro_uso.erros(time.time() - dias * 86400))
    d = ler_json(_ARQ, {}) or {}
    propostas = d.get("propostas", [])
    ja = {(p["arquivo"], p["linha"], p["erro"]) for p in propostas}
    novas = []
    from plugins import _ia
    alvos = [g for g in grupos[:3] if g["arquivo"] not in ("?", "")
             and (g["arquivo"], g["linha"], f"{g['tipo']}: {g['mensagem']}") not in ja]
    antes = (falhando_hoje() or set()) if alvos and _ia.disponivel() else set()
    for g in alvos:
        prop = propor(g, antes)
        if prop:
            prop["id"] = str(max([int(p["id"]) for p in propostas] + [0]) + 1)
            propostas.append(prop)
            novas.append(prop)
    d["propostas"] = propostas[-40:]
    gravar_json(_ARQ, d)
    return grupos, novas


def aplicar(ident: str, player=None) -> str:
    d = ler_json(_ARQ, {}) or {}
    prop = next((p for p in d.get("propostas", []) if p["id"] == ident), None)
    if not prop or prop["estado"] != "pendente":
        return f"Não tenho a correção pendente {ident}."
    if not prop["valida"]:
        return f"A correção {ident} não passou nos testes ({prop['testes']}); não aplico."
    arq = (BASE / prop["arquivo"]).resolve()
    if arq.suffix != ".py" or BASE.resolve() not in arq.parents or not arq.is_file():
        return f"A correção {ident} aponta para um arquivo fora do JARVIS; não aplico."

    def fazer() -> str:
        atual = arq.read_text(encoding="utf-8")
        if atual.count(prop["trocar"]) != 1:
            return "O arquivo mudou desde a análise; analise de novo."
        copia = arq.with_name(arq.name + time.strftime(".bak-%Y%m%d-%H%M%S"))
        shutil.copy2(arq, copia)
        arq.write_text(atual.replace(prop["trocar"], prop["por"], 1), encoding="utf-8")
        prop["estado"] = "aplicada"
        gravar_json(_ARQ, d)

        def voltar() -> str:
            shutil.copy2(copia, arq)
            prop["estado"] = "desfeita"
            gravar_json(_ARQ, d)
            return f"Voltei {prop['arquivo']} para antes da correção {ident}."
        desfazer(f"correção {ident} em {prop['arquivo']}", voltar)
        return f"Correção {ident} aplicada em {prop['arquivo']} (cópia em {copia.name}). Reinicie o JARVIS para valer."

    return confirmar(f"auto_melhoria:{ident}", f"Aplicar a correção {ident} em {prop['arquivo']}?",
                     f"{prop['explicacao']}\n{prop['testes']}\n\n{prop['diff'][:1500]}", fazer)


def _guardar_excecoes_de_threads() -> None:
    antigo = threading.excepthook

    def gancho(args):
        try:
            from core import registro_uso
            registro_uso.registrar_erro(f"thread:{getattr(args.thread, 'name', '?')}", args.exc_value)
        except Exception:
            pass
        antigo(args)
    threading.excepthook = gancho


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        _guardar_excecoes_de_threads()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "analisar").lower()
    ident = str(p.get("id") or "").strip().lstrip("#")
    try:
        if acao == "aplicar":
            return aplicar(ident, player)
        d = ler_json(_ARQ, {}) or {}
        if acao == "descartar":
            for prop in d.get("propostas", []):
                if prop["id"] == ident:
                    prop["estado"] = "descartada"
            gravar_json(_ARQ, d)
            return f"Descartei a correção {ident}."
        if acao == "ver":
            prop = next((x for x in d.get("propostas", []) if x["id"] == ident), None)
            if not prop:
                return f"Não tenho a correção {ident}."
            mostrar(player, f"CORREÇÃO {ident} — {prop['arquivo']}",
                    f"Erro: {prop['erro']} ({prop['vezes']}x)\n{prop['explicacao']}\n{prop['testes']}\n\n{prop['diff']}")
            return f"A correção {ident} está no painel: {prop['explicacao']} ({prop['testes']})."
        if acao == "listar":
            pend = [x for x in d.get("propostas", []) if x["estado"] == "pendente"]
            if not pend:
                return "Nenhuma correção pendente."
            return "; ".join(f"{x['id']}: {x['arquivo']} — {x['explicacao']} ({'testes ok' if x['valida'] else 'não passou'})"
                             for x in pend[:5])
        from core import registro_uso
        if acao == "erros":
            grupos = agrupar(registro_uso.erros(time.time() - 7 * 86400))
        else:
            grupos, novas = analisar()
            if novas:
                mostrar(player, "AUTO-MELHORIA", "\n\n".join(
                    f"[{x['id']}] {x['arquivo']}:{x['linha']} — {x['erro']} ({x['vezes']}x)\n{x['explicacao']}\n{x['testes']}"
                    f"\n{x['diff'][:800]}" for x in novas))
                boas = [x for x in novas if x["valida"]]
                return (f"Analisei {len(grupos)} tipo(s) de erro e preparei {len(novas)} correção(ões); {len(boas)} passaram "
                        f"nos testes. Diga 'aplica a correção {boas[0]['id']}' se quiser." if boas else
                        f"Preparei {len(novas)} correção(ões), mas nenhuma passou nos testes. Detalhes no painel.")
        if not grupos:
            return "Nenhum erro registrado nos últimos 7 dias."
        from plugins.olha_isso import explicar_local
        mostrar(player, "ERROS DO JARVIS (7 dias)", "\n\n".join(
            f"{g['vezes']}x  {g['arquivo']}:{g['linha']}  {g['tipo']}: {g['mensagem'][:120]}\n  origem: "
            f"{', '.join(g['origens'])}\n  {explicar_local(g['traceback'])}" for g in grupos[:12]))
        return (f"{len(grupos)} tipo(s) de erro nos últimos 7 dias; o mais frequente: {grupos[0]['tipo']} em "
                f"{grupos[0]['arquivo']} ({grupos[0]['vezes']}x)." + ("" if acao == "erros" else
                                                                     " Sem IA eu não proponho correções."))
    except Exception as e:
        return f"A auto-melhoria falhou: {e}"
