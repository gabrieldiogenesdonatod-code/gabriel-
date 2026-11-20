"""
Laboratório de experiências — ideia 6 (fork PT-BR 1.4).

Antes de mudar algo de verdade, o JARVIS testa num AMBIENTE SEPARADO:

    1. copia o projeto para uma pasta temporária (sem .git, venv,
       node_modules, caches e dados);
    2. roda o comando (testes, script, build) na cópia ORIGINAL, N vezes —
       essa é a linha de base;
    3. aplica a mudança proposta na cópia ("troque X por Y no arquivo Z");
    4. roda de novo, N vezes, e compara: tempo médio, se passou, quantos
       testes passaram/falharam, e o fim da saída;
    5. guarda o resultado em memory/laboratorio.json. O projeto original
       nunca é tocado.

    "Jarvis, testa no laboratório se os testes do Jarvis passam"
    "Jarvis, experimenta trocar 'WORKERS = 4' por 'WORKERS = 8' no config.py
     do projeto da loja e vê se fica mais rápido"
    "Jarvis, o que deu o último experimento?"

Também é usado pelo criador de ferramentas: todo plugin novo é carregado
primeiro numa cópia do JARVIS, num processo separado, antes de você aprovar.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from plugins._comum import BASE, CNW, MEMORIA, WIN, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "laboratorio",
    "brief": "Test a change in a throwaway copy of a project and compare with the original.",
    "description": (
        "Experiment lab: copies a project to a temporary sandbox, runs a command there before and "
        "after a proposed change, and compares time, success and test counts; the real project is "
        "never touched. action='experimentar' with pasta (project folder; empty = JARVIS), comando "
        "(empty = the project's tests), arquivo + trocar + por for the change (optional: without a "
        "change it only measures), repeticoes. action='historico' lists past experiments, 'ver' "
        "shows the last one in detail."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "experimentar | historico | ver"},
            "pasta": {"type": "STRING"}, "comando": {"type": "STRING"},
            "arquivo": {"type": "STRING"}, "trocar": {"type": "STRING"}, "por": {"type": "STRING"},
            "regex": {"type": "BOOLEAN", "description": "true = 'trocar' is a regular expression"},   # 3.6: faltava declarar
            "repeticoes": {"type": "INTEGER"},
        },
        "required": ["action"],
    },
}

_HIST = MEMORIA / "laboratorio.json"
_PULAR = {".git", "venv", ".venv", "env", "node_modules", "__pycache__", "build", "dist", ".mypy_cache",
          ".pytest_cache", ".idea", ".vscode", ".tox", ".next", "target", "modelos_rosto", "rostos"}
_PULAR_EXT = {".db", ".db-wal", ".db-shm", ".sqlite", ".onnx", ".npy", ".mp4", ".mkv", ".avi", ".zip",
              ".7z", ".rar", ".iso", ".exe", ".msi", ".pt", ".bin", ".safetensors"}
LIMITE_MB = 600


# ── cópia ──────────────────────────────────────────────────────────────────────
def copiar_projeto(origem: Path, destino: Path, limite_mb: float = LIMITE_MB) -> tuple[int, int]:
    """Copia o que importa para rodar o projeto. (arquivos, bytes). Levanta se passar do limite."""
    origem, destino = Path(origem), Path(destino)
    total, n = 0, 0
    for raiz, dirs, arqs in os.walk(origem):
        dirs[:] = [d for d in dirs if d not in _PULAR and not d.startswith(".")]
        rel = Path(raiz).relative_to(origem)
        for a in arqs:
            src = Path(raiz) / a
            if src.suffix.lower() in _PULAR_EXT or a.endswith((".tmp", ".log")):
                continue
            # dados do JARVIS (memória, chaves) não vão para o laboratório
            if rel.parts[:1] == ("memory",) and src.suffix != ".py":
                continue
            if rel.parts[:1] == ("config",) and a == "api_keys.json":
                continue
            try:
                tam = src.stat().st_size
            except OSError:
                continue
            total += tam
            if total > limite_mb * 1024 * 1024:
                raise RuntimeError(f"o projeto passa de {limite_mb:.0f} MB; aponte uma pasta menor")
            alvo = destino / rel / a
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, alvo)
            n += 1
    return n, total


def aplicar_variante(raiz: Path, v: dict) -> str | None:
    """Aplica "troque X por Y" num arquivo da cópia. None = ok; texto = erro."""
    arq = str(v.get("arquivo") or "").strip().replace("\\", "/")
    trocar, por = str(v.get("trocar") or ""), str(v.get("por") or "")
    if not arq or not trocar:
        return "a mudança precisa de arquivo e do trecho a trocar"
    alvos = [raiz / arq] if (raiz / arq).is_file() else sorted(raiz.rglob(Path(arq).name))
    if not alvos:
        return f"não achei {arq} no projeto"
    caminho = alvos[0]
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    if trocar in texto:
        novo = texto.replace(trocar, por)
    elif v.get("regex"):
        try:
            novo, qtd = re.subn(trocar, por, texto)
        except re.error as e:
            return f"expressão inválida: {e}"
        if not qtd:
            return f"o padrão não aparece em {caminho.name}"
    else:
        # tolera diferença de espaços: "WORKERS=4" acha "WORKERS = 4"
        padrao = r"\s*".join(re.escape(p) for p in re.split(r"\s+", trocar.strip()) if p)
        padrao = re.sub(r"(\\=|=)", r"\\s*=\\s*", padrao)
        novo, qtd = re.subn(padrao, lambda _m: por, texto)
        if not qtd:
            return f"'{trocar}' não aparece em {caminho.name}"
    caminho.write_text(novo, encoding="utf-8")
    return None


# ── execução ───────────────────────────────────────────────────────────────────
def comando_padrao(raiz: Path) -> list[str]:
    if (raiz / "tests").is_dir() or list(raiz.glob("test_*.py")):
        if (raiz / "pytest.ini").exists() or (raiz / "conftest.py").exists():
            return [sys.executable, "-m", "pytest", "-q"]
        return [sys.executable, "-m", "unittest", "discover", "-s", "tests" if (raiz / "tests").is_dir() else "."]
    if (raiz / "package.json").exists():
        return ["npm.cmd" if WIN else "npm", "test"]
    if (raiz / "main.py").exists():
        return [sys.executable, "-m", "py_compile", "main.py"]
    return [sys.executable, "-c", "print('nada para rodar')"]


def montar_comando(comando: str | list | None, raiz: Path) -> list[str]:
    if not comando:
        return comando_padrao(raiz)
    if isinstance(comando, list):
        args = list(comando)
    else:
        args = shlex.split(comando, posix=not WIN)
    if args and args[0].lower() in ("python", "python3", "py", "python.exe"):
        args[0] = sys.executable
    if WIN and args and args[0].lower() in ("npm", "npx", "yarn", "pnpm"):
        args[0] += ".cmd"
    return args


def _contar_testes(saida: str) -> dict:
    d = {}
    m = re.search(r"Ran (\d+) tests?", saida)
    if m:
        d["rodados"] = int(m.group(1))
        f = re.search(r"FAILED \((.*?)\)", saida)
        d["falhas"] = sum(int(x) for x in re.findall(r"(?:failures|errors)=(\d+)", f.group(1))) if f else 0
    m = re.search(r"(\d+) passed", saida)
    if m:
        d["passaram"] = int(m.group(1))
        f = re.search(r"(\d+) failed", saida)
        d["falhas"] = int(f.group(1)) if f else 0
    return d


def rodar_uma(raiz: Path, args: list[str], timeout: float = 300) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = str(raiz)
    t0 = time.perf_counter()
    try:
        r = subprocess.run(args, cwd=str(raiz), capture_output=True, timeout=timeout, env=env, **CNW)
        codigo = r.returncode
        saida = ((r.stdout or b"") + b"\n" + (r.stderr or b"")).decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        codigo, saida = -9, f"passou de {timeout:.0f} s e foi interrompido"
    except FileNotFoundError:
        codigo, saida = -1, f"{args[0]} não encontrado"
    seg = time.perf_counter() - t0
    return {"segundos": round(seg, 3), "codigo": codigo, "ok": codigo == 0,
            "testes": _contar_testes(saida), "fim": saida.strip()[-600:]}


def _resumir(rodadas: list[dict]) -> dict:
    tempos = [r["segundos"] for r in rodadas]
    return {"tempo_medio": round(statistics.mean(tempos), 3) if tempos else 0,
            "tempo_desvio": round(statistics.pstdev(tempos), 3) if len(tempos) > 1 else 0,
            "sucessos": sum(r["ok"] for r in rodadas), "rodadas": len(rodadas),
            "testes": rodadas[-1]["testes"] if rodadas else {}, "fim": rodadas[-1]["fim"] if rodadas else ""}


def comparar(base: dict, variante: dict) -> list[str]:
    """Conclusões em português (pura)."""
    out = []
    tb, tv = base["tempo_medio"], variante["tempo_medio"]
    if tb > 0:
        dif = (tv - tb) / tb * 100
        ruido = max(base.get("tempo_desvio", 0), variante.get("tempo_desvio", 0)) / tb * 100
        if abs(dif) <= max(5, 2 * ruido):
            out.append(f"tempo praticamente igual ({tb:.2f} s → {tv:.2f} s; diferença dentro do ruído)")
        else:
            out.append(f"{'mais rápido' if dif < 0 else 'mais lento'}: {tb:.2f} s → {tv:.2f} s ({dif:+.0f}%)")
    sb, sv = base["sucessos"] / max(1, base["rodadas"]), variante["sucessos"] / max(1, variante["rodadas"])
    if sv < sb:
        out.append(f"PIOROU a estabilidade: {variante['sucessos']}/{variante['rodadas']} rodadas ok "
                   f"(antes {base['sucessos']}/{base['rodadas']})")
    elif sv > sb:
        out.append(f"melhorou: {variante['sucessos']}/{variante['rodadas']} rodadas ok (antes {base['sucessos']}/{base['rodadas']})")
    fb, fv = base["testes"].get("falhas"), variante["testes"].get("falhas")
    if fb is not None and fv is not None and fb != fv:
        out.append(f"testes com falha: {fb} → {fv}")
    return out


def experimentar(pasta: str = "", comando=None, variantes: list[dict] | None = None,
                 repeticoes: int = 3, timeout: float = 300) -> dict:
    origem = Path(pasta).expanduser() if pasta else BASE
    if not origem.is_dir():
        raise RuntimeError(f"a pasta {origem} não existe")
    repeticoes = max(1, min(10, int(repeticoes or 3)))
    with tempfile.TemporaryDirectory(prefix="jarvis_lab_") as tmp:
        caixa = Path(tmp) / origem.name
        n, tam = copiar_projeto(origem, caixa)
        args = montar_comando(comando, caixa)
        base = _resumir([rodar_uma(caixa, args, timeout) for _ in range(repeticoes)])
        resultado = {"quando": time.strftime("%Y-%m-%d %H:%M"), "pasta": str(origem), "comando": " ".join(args[1:] if args[0] == sys.executable else args),
                     "arquivos_copiados": n, "mb": round(tam / 1048576, 1), "base": base, "variantes": []}
        for v in variantes or []:
            erro = aplicar_variante(caixa, v)
            if erro:
                resultado["variantes"].append({"mudanca": v, "erro": erro})
                continue
            res = _resumir([rodar_uma(caixa, args, timeout) for _ in range(repeticoes)])
            resultado["variantes"].append({"mudanca": v, "resultado": res, "conclusoes": comparar(base, res)})
    hist = ler_json(_HIST, []) or []
    hist.append(resultado)
    gravar_json(_HIST, hist[-30:])
    return resultado


# ── validação de plugin numa cópia do JARVIS ───────────────────────────────────
_CHECAGEM = r'''
import json, sys, threading
from pathlib import Path
raiz = Path(sys.argv[1]); nome_arq = sys.argv[2]; testar_run = sys.argv[3] == "1"
sys.path.insert(0, str(raiz))
out = {"ok": False, "erros": [], "avisos": []}
try:
    from core.plugin_loader import discover_plugins
    reg = discover_plugins(raiz / "plugins", set(), logger=lambda m: None)
    recs = [p for p in reg.list_for_ui() if p["file"] == nome_arq]
    if not recs:
        out["erros"].append("o carregador não encontrou o arquivo")
    elif not recs[0]["valid"]:
        out["erros"].append("rejeitado pelo carregador: " + str(recs[0]["error"]))
    else:
        nome = recs[0]["name"]; out["nome"] = nome
        decl = [d for d in reg.get_tool_declarations() if d["name"] == nome]
        if decl:
            d = decl[0]; props = d["parameters"].get("properties", {})
            for k, v in props.items():
                if v.get("type") not in ("STRING", "NUMBER", "INTEGER", "BOOLEAN", "OBJECT", "ARRAY"):
                    out["erros"].append(f"parâmetro {k} sem tipo válido")
            for r in d["parameters"].get("required", []):
                if r not in props:
                    out["erros"].append(f"'required' cita {r}, que não existe")
            if len(d["description"]) >= 1500:
                out["erros"].append("descrição longa demais (>= 1500)")
            out["declaracao"] = {"name": d["name"], "description": d["description"][:300]}
        if testar_run and not out["erros"]:
            res = {}
            def chamar():
                try:
                    res["r"] = reg.run(nome, {"action": "status"})
                except Exception as e:
                    res["e"] = repr(e)
            t = threading.Thread(target=chamar, daemon=True); t.start(); t.join(25)
            if t.is_alive():
                out["avisos"].append("run() demorou mais de 25 s no teste")
            elif "e" in res:
                out["erros"].append("run() levantou exceção: " + res["e"])
            elif not isinstance(res.get("r"), str):
                out["erros"].append("run() não devolveu texto")
            else:
                out["resposta_teste"] = res["r"][:300]
        out["ok"] = not out["erros"]
except Exception as e:
    out["erros"].append(repr(e))
print("@@JSON@@" + json.dumps(out, ensure_ascii=True) + "@@FIM@@")
'''


def validar_plugin(codigo: str, nome_arquivo: str, testar_run: bool = True, timeout: float = 60) -> dict:
    """Carrega o plugin numa cópia mínima do JARVIS, em OUTRO processo."""
    import py_compile
    with tempfile.TemporaryDirectory(prefix="jarvis_lab_plugin_") as tmp:
        caixa = Path(tmp) / "jarvis"
        for pasta in ("core", "providers"):
            if (BASE / pasta).is_dir():
                shutil.copytree(BASE / pasta, caixa / pasta, ignore=shutil.ignore_patterns("__pycache__", "*.obj"))
        (caixa / "memory").mkdir(parents=True)
        for f in (BASE / "memory").glob("*.py"):
            shutil.copy2(f, caixa / "memory" / f.name)
        (caixa / "config").mkdir()
        (caixa / "config" / "__init__.py").write_text("", encoding="utf-8")
        (caixa / "plugins").mkdir()
        for f in (BASE / "plugins").glob("_*.py"):        # só os ajudantes + o plugin novo
            shutil.copy2(f, caixa / "plugins" / f.name)
        alvo = caixa / "plugins" / nome_arquivo
        alvo.write_text(codigo, encoding="utf-8")
        try:
            py_compile.compile(str(alvo), doraise=True)
        except py_compile.PyCompileError as e:
            return {"ok": False, "erros": [f"erro de sintaxe: {e.msg.strip()[-300:]}"], "avisos": []}
        script = Path(tmp) / "checar.py"
        script.write_text(_CHECAGEM, encoding="utf-8")
        r = rodar_uma(caixa, [sys.executable, str(script), str(caixa), nome_arquivo, "1" if testar_run else "0"], timeout)
        m = re.search(r"@@JSON@@(.*)@@FIM@@", r["fim"], re.S)
        if not m:
            return {"ok": False, "erros": ["o teste não terminou: " + r["fim"][-300:]], "avisos": []}
        return json.loads(m.group(1))


# ── voz ────────────────────────────────────────────────────────────────────────
def _texto(res: dict) -> str:
    b = res["base"]
    linhas = [f"Projeto: {res['pasta']}  ({res['arquivos_copiados']} arquivos, {res['mb']} MB copiados)",
              f"Comando: {res['comando']}", "",
              f"ORIGINAL: {b['sucessos']}/{b['rodadas']} ok, {b['tempo_medio']:.2f} s (±{b['tempo_desvio']:.2f})"
              + (f", testes {b['testes']}" if b["testes"] else "")]
    for v in res["variantes"]:
        mud = v["mudanca"]
        linhas.append(f"\nMUDANÇA: em {mud.get('arquivo')}: '{mud.get('trocar')}' → '{mud.get('por')}'")
        if v.get("erro"):
            linhas.append(f"  não apliquei: {v['erro']}")
            continue
        r = v["resultado"]
        linhas.append(f"  {r['sucessos']}/{r['rodadas']} ok, {r['tempo_medio']:.2f} s" + (f", testes {r['testes']}" if r["testes"] else ""))
        linhas += [f"  → {c}" for c in v["conclusoes"]]
    linhas += ["", "Fim da saída (última rodada):", b["fim"][-500:]]
    return "\n".join(linhas)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "experimentar").lower()
    try:
        if acao in ("historico", "ver"):
            hist = ler_json(_HIST, []) or []
            if not hist:
                return "Nenhum experimento ainda."
            if acao == "ver":
                mostrar(player, "LABORATÓRIO — ÚLTIMO EXPERIMENTO", _texto(hist[-1]))
                ult = hist[-1]
                concl = [c for v in ult["variantes"] for c in v.get("conclusoes", [])]
                return f"Último experimento ({ult['quando']}): " + ("; ".join(concl) or
                       f"{ult['base']['sucessos']}/{ult['base']['rodadas']} rodadas ok, {ult['base']['tempo_medio']:.2f} s")
            return "; ".join(f"{h['quando']} em {Path(h['pasta']).name}: {len(h['variantes'])} mudança(s)" for h in hist[-5:])
        variantes = []
        if p.get("trocar"):
            variantes.append({"arquivo": p.get("arquivo"), "trocar": p.get("trocar"), "por": p.get("por", ""),
                              "regex": bool(p.get("regex"))})
        comando = str(p.get("comando") or "").strip() or None
        from plugins import _guardiao
        av = _guardiao.avaliar("laboratorio", {"comando": comando or ""}, comando or "")
        if av.decisao == "bloquear":
            return "Não rodo esse comando nem no laboratório: " + av.texto()
        res = experimentar(str(p.get("pasta") or ""), comando, variantes, int(p.get("repeticoes") or 3))
        mostrar(player, "LABORATÓRIO", _texto(res))
        b = res["base"]
        fala = f"Experimento pronto. Original: {b['sucessos']} de {b['rodadas']} rodadas ok, média de {b['tempo_medio']:.1f} segundos."
        for v in res["variantes"]:
            fala += (f" A mudança não foi aplicada: {v['erro']}." if v.get("erro")
                     else " Com a mudança: " + "; ".join(v["conclusoes"] or ["sem diferença"]) + ".")
        return fala + " O projeto original não foi alterado."
    except Exception as e:
        return f"O laboratório falhou: {e}"
