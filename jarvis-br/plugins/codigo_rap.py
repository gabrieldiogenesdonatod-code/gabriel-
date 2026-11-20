"""
Código em rap (3.3): o JARVIS explica código como um rap geek ORIGINAL — cada verso fala de uma parte
de verdade do código (o que entra, as decisões, os loops, o que sai).

    "Jarvis, faz um rap do arquivo plugins/estudos.py"         "Jarvis, rap da função prever_semana"
    "Jarvis, faz um rap do código que eu copiei"               "Jarvis, rap do último commit"
    "Jarvis, rap da função escrever e põe no quadro"           "Jarvis, me desafia" → ele rima uma função
    "Jarvis, é a função prever_semana?" (palpite)               "Jarvis, lê o último rap de código"

Com a chave do Gemini as rimas são livres; sem ela, ele monta as rimas a partir da estrutura do código
(parâmetros, imports, if, loops, try, chamadas e return). Fica guardado em Documentos/JARVIS/Rap.
Nunca copia letra de música existente. Antes de mandar código para a IA, tira chaves e senhas do texto,
e se recusa a ler arquivos de senha/chave.
"""

from __future__ import annotations

import ast
import random
import re
import time
from collections import Counter
from pathlib import Path

from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("codigo_rap", "Explains code as an ORIGINAL geek rap: a file, function, copied code or the last git commit; guess-the-function "
                         "rap challenge.",
           "rap | commit | desafio | palpite | ultimo",
           "rap: arquivo (path, or a file name inside the JARVIS project), funcao (optional function/class name), codigo (pasted "
           "code, or 'area' for the clipboard), estilo (boom bap | trap | lento), quadro ('sim' shows it on the study board). "
           "commit: pasta (git repo; default the JARVIS project). desafio: raps a random JARVIS function without saying its name. "
           "palpite: palpite (the function name the user guessed). ultimo: last code rap.",
           "arquivo funcao codigo estilo quadro pasta palpite")

PROJETO = Path(__file__).resolve().parent.parent
BPM = {"boom bap": 90, "trap": 140, "lento": 72}
_SENSIVEIS = re.compile(r"(api[_-]?keys?|\.env\b|senha|password|token|secret|credenc|credential|cofre|wallet|\.pem$|\.key$|id_rsa)", re.I)
_SEGREDOS = [re.compile(p) for p in (r"AIza[0-9A-Za-z_\-]{30,}", r"sk-[A-Za-z0-9_\-]{20,}", r"gh[pousr]_[A-Za-z0-9]{30,}",
                                     r"xox[abp]-[A-Za-z0-9\-]{10,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")]
_ATRIB_SEGREDO = re.compile(r"""(?i)\b(\w*(?:key|token|secret|senha|password|passwd)\w*)\s*([:=])\s*(['"])[^'"\n]{6,}\3""")


# ─────────────────────────────────────────────────────────── puras ───
def sem_segredos(texto: str) -> str:
    """Tira chaves de API, tokens e senhas escritas no código antes de mandar para a IA. Pura."""
    for r in _SEGREDOS:
        texto = r.sub("«segredo removido»", texto)
    return _ATRIB_SEGREDO.sub(lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}«segredo removido»{m.group(3)}", texto)


def estrutura(codigo: str) -> dict:
    """O que o código tem: funções, classes, imports, decisões, loops, proteções, chamadas, parâmetros. Pura."""
    e = {"funcoes": [], "classes": [], "imports": [], "ifs": 0, "loops": 0, "trys": 0, "returns": 0, "chamadas": [],
         "params": [], "linhas": len([x for x in codigo.splitlines() if x.strip()]), "doc": "", "python": True, "async": False}
    try:
        arvore = ast.parse(codigo)
    except (SyntaxError, ValueError):
        e["python"] = False
        e["funcoes"] = re.findall(r"(?:function|def|func|fn)\s+([A-Za-z_]\w*)", codigo)[:12]
        e["classes"] = re.findall(r"\bclass\s+([A-Za-z_]\w*)", codigo)[:6]
        e["ifs"] = len(re.findall(r"\bif\b|\bswitch\b|\?\s", codigo))
        e["loops"] = len(re.findall(r"\bfor\b|\bwhile\b|\.forEach\(|\.map\(", codigo))
        e["trys"] = len(re.findall(r"\btry\b", codigo))
        e["returns"] = len(re.findall(r"\breturn\b", codigo))
        e["imports"] = re.findall(r"(?:import|require\(|using|#include)\s*['\"<]?([\w./@-]+)", codigo)[:8]
        return e
    chamadas: Counter = Counter()
    for n in ast.walk(arvore):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            e["funcoes"].append(n.name)
            e["async"] = e["async"] or isinstance(n, ast.AsyncFunctionDef)
        elif isinstance(n, ast.ClassDef):
            e["classes"].append(n.name)
        elif isinstance(n, ast.Import):
            e["imports"] += [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            e["imports"].append((n.module or ".").split(".")[-1])
        elif isinstance(n, (ast.If, ast.IfExp, ast.Match)):
            e["ifs"] += 1
        elif isinstance(n, (ast.For, ast.While, ast.AsyncFor, ast.comprehension)):
            e["loops"] += 1
        elif isinstance(n, ast.Try) or type(n).__name__ == "TryStar":
            e["trys"] += 1
        elif isinstance(n, ast.Return):
            e["returns"] += 1
        elif isinstance(n, ast.Call):
            f = n.func
            nome = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if nome and nome not in ("print", "str", "int", "float", "len", "list", "dict", "set", "range", "isinstance", "get"):
                chamadas[nome] += 1
    e["imports"] = list(dict.fromkeys(e["imports"]))[:8]
    e["chamadas"] = [c for c, _ in chamadas.most_common(4)]
    principal = next((n for n in arvore.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))), None)
    if principal is not None and len([n for n in arvore.body if not isinstance(n, (ast.Import, ast.ImportFrom, ast.Expr))]) == 1:
        if not isinstance(principal, ast.ClassDef):
            e["params"] = [a.arg for a in principal.args.args + principal.args.kwonlyargs if a.arg not in ("self", "cls")]
        e["doc"] = (ast.get_docstring(principal) or "").strip().split("\n")[0][:120]
    elif ast.get_docstring(arvore):
        e["doc"] = ast.get_docstring(arvore).strip().split("\n")[0][:120]
    return e


def _lista(xs: list[str], n: int = 3) -> str:
    xs = [x for x in xs if x][:n]
    if len(xs) <= 1:
        return xs[0] if xs else ""
    return ", ".join(xs[:-1]) + " e " + xs[-1]


def versos_offline(nome: str, e: dict, rng=random) -> list[str]:
    """Rimas montadas da estrutura do código (sem IA). Cada par rima por construção. Pura com rng fixo."""
    v = [f"Abre o editor, que {nome} vai rimar,", "cada linha desse código eu vou te explicar."]
    doc = re.sub(r"\s*\bPura\.?$", "", re.split(r"(?<=[.!?])\s", e.get("doc") or "")[0]).strip().rstrip(".")
    if doc:
        v += [f"A missão tá na docstring: {doc},", "e o que tá escrito ali é o que eu vou cumprir aqui."]
    if e.get("params"):
        v += [f"Chego com {_lista(e['params'])} na mão,", "parâmetro é a entrada, é o começo da missão."]
    if e.get("imports"):
        v += [f"Do {_lista(e['imports'])} eu trago o reforço,", "importo o que precisa e não faço esforço."]
    if e.get("classes"):
        v += [f"A classe {e['classes'][0]} é a minha base,", "objeto bem montado, cada método na sua fase."]
    if e.get("ifs"):
        v += [("Uma decisão" if e["ifs"] == 1 else f"São {e['ifs']} decisões") + ", é if pra cá e pra lá,",
              "cada caminho testado antes de executar."]
    if e.get("loops"):
        v += [("Um loop girando" if e["loops"] == 1 else f"{e['loops']} loops girando") + ", é volta sem parar,",
              "percorro a lista inteira até o fim chegar."]
    if e.get("trys"):
        v += ["Tem try e except, " + ("uma rede" if e["trys"] == 1 else f"{e['trys']} redes") + " de proteção,",
              "se o erro aparecer, não derruba a aplicação."]
    if e.get("chamadas"):
        v += [f"Chamo {_lista(e['chamadas'])} pra somar no rolê,", "cada função no seu lugar, é só você ver."]
    if e.get("async"):
        v += ["É async, é await, não travo ninguém,", "enquanto um espera, o outro roda também."]
    if e.get("returns"):
        v += ["No final vem o return, entrego o resultado,", "missão cumprida, código bem amarrado."]
    fechos = [(("Uma linha" if e.get("linhas", 0) == 1 else f"São {e.get('linhas', 0)} linhas") + " de pura dedicação,",
               "J.A.R.V.I.S no beat, rodando no coração."),
              ("Código explicado, pode dar o play,", "se bugar eu volto, que o debug eu já sei."),
              ("Compilou na mente, entendeu o refrão,", "programar é rimar com a lógica na mão.")]
    v += list(rng.choice(fechos))
    return v


def versos_commit(c: dict, rng=random) -> list[str]:
    """Rimas do último commit (sem IA). Pura com rng fixo."""
    arqs = c.get("arquivos", [])
    mais, menos = sum(a for a, _, _ in arqs), sum(d for _, d, _ in arqs)
    nomes = [Path(x).name for _, _, x in sorted(arqs, key=lambda t: -(t[0] + t[1]))[:3]]
    v = [f"Commit {c.get('hash', '')} chegou, mensagem na mão:", f"\"{c.get('assunto', '')[:70]}\", essa é a missão."]
    if nomes:
        v += [f"Mexi em {_lista(nomes)}, {len(arqs)} arquivo(s) no total,", "cada mudança registrada, histórico é fundamental."]
    v += [f"Mais {mais} linha(s) que entraram no jogo,", f"menos {menos} que saíram, limpei o código no fogo."]
    v += list(rng.choice([("Git log não mente, tá tudo anotado,", "o passado do projeto bem documentado."),
                          ("Push no repositório, pode conferir,", "o JARVIS evoluindo e ninguém vai me impedir.")]))
    return v


def titulo_de(alvo: str) -> str:
    """'Rap desse código', 'Rap do código que você copiou', 'Rap de soma'. Pura."""
    if alvo.startswith("esse "):
        return "Rap d" + alvo
    if alvo.startswith(("o ", "a ")):
        return "Rap d" + alvo
    return f"Rap de {alvo}"


def mesmo_nome(palpite: str, resposta: str) -> bool:
    so = lambda t: re.sub(r"[^a-z0-9]", "", norm(t))  # noqa: E731
    return bool(so(palpite)) and so(palpite) == so(resposta)


def esconder(versos: list[str], nome: str) -> list[str]:
    """Tira o nome da função dos versos do desafio (inteiro, com ou sem _). Pura."""
    padrao = re.compile(r"[_\s]?".join(map(re.escape, nome.split("_"))), re.I) if nome else None
    return [padrao.sub("███", x) if padrao else x for x in versos]


# ─────────────────────────────────────────────────────────── fontes ───
def _achar_arquivo(nome: str) -> Path | None:
    nome = nome.strip().strip('"').strip("'")
    if not nome:
        return None
    p = Path(nome).expanduser()
    for c in ([p] if p.is_absolute() else [PROJETO / p, Path.cwd() / p]):
        if c.is_file():
            return c.resolve()
    alvo = Path(nome).name.lower()
    alvo = alvo if "." in alvo else alvo + ".py"
    fora = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules", "site-packages"}
    for c in PROJETO.rglob("*"):
        if c.name.lower() == alvo and not fora.intersection(c.parts) and c.is_file():
            return c
    return None


def _achar_funcao_no_projeto(nome: str) -> tuple[Path, str] | None:
    padrao = re.compile(rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(nome)}\b", re.M)
    for pasta in ("plugins", "core", "biological_core", "actions", "memory", "celular", "."):
        base = PROJETO / pasta
        for arq in (sorted(base.rglob("*.py")) if pasta != "." else sorted(base.glob("*.py"))):
            if "__pycache__" in arq.parts or "tests" in arq.parts:
                continue
            try:
                src = arq.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if padrao.search(src):
                return arq, src
    return None


def _recorte(src: str, funcao: str) -> str | None:
    try:
        from plugins.arqueologo_codigo import achar_funcao
        lugar = achar_funcao(src, funcao)
    except (SyntaxError, ValueError):
        lugar = None
    if not lugar:
        return None
    linhas = src.splitlines()
    return "\n".join(linhas[lugar[0] - 1:lugar[1]])


def _rel(arq: Path) -> str:
    try:
        return str(arq.relative_to(PROJETO)).replace("\\", "/")
    except ValueError:
        return arq.name


def fonte(p: dict) -> tuple[str, str] | str:
    """(nome para o rap, código) ou o que falta (texto)."""
    codigo, arquivo, funcao = str(p.get("codigo") or "").strip(), str(p.get("arquivo") or "").strip(), str(p.get("funcao") or "").strip()
    if codigo and norm(codigo) in ("area", "area de transferencia", "clipboard", "copiado", "o que eu copiei", "colado"):
        try:
            import pyperclip
            codigo = (pyperclip.paste() or "").strip()
        except Exception:
            return "Não consegui ler a área de transferência (precisa do pyperclip). Cole o código aqui."
        if not codigo:
            return "A área de transferência está vazia. Copie o código e peça de novo."
        return "o código que você copiou", codigo[:60_000]
    if codigo:
        return "esse código", codigo[:60_000]
    if arquivo:
        arq = _achar_arquivo(arquivo)
        if not arq:
            return f"Não achei o arquivo '{arquivo}'."
        if _SENSIVEIS.search(arq.name):
            return "Esse arquivo parece guardar senha ou chave; não vou ler nem mandar para a IA."
        try:
            src = arq.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"Não consegui ler {arq.name}: {e}"
        if funcao:
            trecho = _recorte(src, funcao)
            return (f"{funcao} ({arq.name})", trecho) if trecho else f"Não achei '{funcao}' em {arq.name}."
        return arq.name, src[:60_000]
    if funcao:
        achado = _achar_funcao_no_projeto(funcao)
        if not achado:
            return f"Não achei a função '{funcao}' no projeto do JARVIS. Diga também o arquivo."
        trecho = _recorte(achado[1], funcao)
        return (f"{funcao} ({achado[0].name})", trecho) if trecho else f"Não achei '{funcao}'."
    return "Qual código? Diga um arquivo, uma função, cole o código ou diga 'o que eu copiei'."


# ─────────────────────────────────────────────────────────── IA ───
def _pedir(instrucao: str, material: str) -> dict | None:
    try:
        from plugins import _ia
        d = _ia.perguntar_json(instrucao + "\n\nNÃO copie nem parafraseie letras de músicas existentes; sem palavrão. "
                               "Responda SÓ com JSON: {\"titulo\": \"...\", \"resumo\": \"uma frase do que o código faz\", "
                               "\"versos\": [\"linha\", ...], \"bpm\": 90}\n\n" + sem_segredos(material), inteligente=True, segundos=45)
    except Exception as e:
        print(f"[CodigoRap] IA: {e}")
        return None
    if isinstance(d, dict) and isinstance(d.get("versos"), list) and len(d["versos"]) >= 4:
        d["versos"] = [str(x).strip() for x in d["versos"] if str(x).strip()][:32]
        return d
    return None


def compor(nome: str, codigo: str, estilo: str = "boom bap", esconder_nome: str = "") -> dict:
    e = estrutura(codigo)
    alvo = "a função misteriosa" if esconder_nome else nome.split(" (")[0]
    instr = (f"Explique este código como um rap geek ORIGINAL em português do Brasil, batida {estilo}, 12 a 20 linhas com rimas. "
             "Cada parte do rap tem que explicar algo REAL do código (o que entra, as decisões, os loops, o que sai, os erros que "
             "ele trata), sem inventar o que o código não faz. O ouvinte é programador e gosta de rap geek."
             + (f" NÃO diga o nome '{esconder_nome}' em nenhum verso: é um desafio de adivinhar." if esconder_nome else
                " Use os nomes reais das funções quando ajudar a entender."))
    d = _pedir(instr, f"Código ({alvo}):\n```\n{codigo[:7000]}\n```")
    if not d:
        d = {"titulo": titulo_de(alvo), "resumo": e.get("doc", ""), "versos": versos_offline(alvo, e), "offline": True}
    d.setdefault("bpm", BPM.get(norm(estilo), 90))
    d.update(nome=nome, estilo=estilo, ts=time.time())
    if esconder_nome:
        d["versos"], d["titulo"] = esconder(d["versos"], esconder_nome), "Desafio: que função é essa?"
        d["resumo"] = esconder([str(d.get("resumo") or "")], esconder_nome)[0]
    return d


def salvar(d: dict) -> str:
    from plugins._comum import pasta_jarvis
    slug = re.sub(r"[^a-z0-9]+", "_", norm(d.get("nome") or "codigo"))[:40].strip("_") or "codigo"
    arq = pasta_jarvis("Rap") / f"codigo_{slug}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    arq.write_text(f"{d['titulo']}\nCódigo: {d.get('nome', '')}\n(BPM sugerido: {d.get('bpm', 90)}, {d.get('estilo', 'boom bap')})\n"
                   + (f"Resumo: {d['resumo']}\n" if d.get("resumo") else "") + "\n" + "\n".join(d["versos"]) + "\n", encoding="utf-8")
    return str(arq)


def _no_quadro(d: dict, codigo: str) -> str:
    try:
        from plugins import _quadro as Q
        Q.nova_pagina(d["titulo"])
        Q.escrever("titulo", d["titulo"])
        if d.get("resumo"):
            Q.escrever("destaque", d["resumo"])
        Q.escrever("codigo", codigo[:2500])
        Q.escrever("texto", "\n".join(d["versos"]))
        url = Q.iniciar_servidor()
        from plugins._comum import abrir_no_sistema
        abrir_no_sistema(url)
        return f" Está no quadro: {url}."
    except Exception as e:
        print(f"[CodigoRap] quadro: {e}")
        return ""


def _guardar(d: dict) -> None:
    est = carregar("codigo_rap", {"raps": [], "desafio": None})
    est["raps"] = (est.get("raps", []) + [{k: d[k] for k in ("titulo", "nome", "versos", "bpm", "ts") if k in d}])[-40:]
    guardar("codigo_rap", est)


def _mostrar(pl, d: dict) -> None:
    from plugins._comum import mostrar
    mostrar(pl, f"CÓDIGO EM RAP — {str(d['titulo']).upper()}", "\n".join(d["versos"]))


# ─────────────────────────────────────────────────────────── ações ───
def _rap(p, pl):
    f = fonte(p)
    if isinstance(f, str):
        return f
    nome, codigo = f
    d = compor(nome, codigo, str(p.get("estilo") or "boom bap"))
    arq = salvar(d)
    _guardar(d)
    _mostrar(pl, d)
    quadro = _no_quadro(d, codigo) if norm(p.get("quadro")) in ("sim", "s", "yes", "true", "1", "quadro") else ""
    return (f"{d['titulo']} (BPM {d.get('bpm', 90)}){' — sem IA, rimas montadas da estrutura do código' if d.get('offline') else ''}:\n"
            + "\n".join(d["versos"]) + f"\n\nSalvo em {arq}.{quadro}")


def _commit(p, pl):
    pasta = Path(str(p.get("pasta") or PROJETO)).expanduser()
    try:
        from plugins.commit_mentiroso import commits, git
        cs = commits(pasta, 1)
        if not cs:
            return "Esse repositório ainda não tem commit."
        c = cs[0]
        diff = git(pasta, "show", "--format=%s%n%n%b", "--stat", "--patch", "--unified=2", "--no-color", "HEAD")
    except RuntimeError as e:
        return f"Não deu para ler o commit: {e}."
    except Exception as e:
        return f"Não deu para ler o commit: {e}"
    estilo = str(p.get("estilo") or "boom bap")
    d = _pedir(f"Explique as mudanças deste commit como um rap geek ORIGINAL em português do Brasil, batida {estilo}, 12 a 16 "
               "linhas com rimas: o que mudou, por quê (pela mensagem) e o que isso melhora. Não invente mudanças que não estão no diff.",
               f"Commit {c['hash']}:\n{diff[:7000]}")
    if not d:
        d = {"titulo": f"Commit {c['hash']}", "resumo": c["assunto"], "versos": versos_commit(c), "offline": True}
    d.setdefault("bpm", BPM.get(norm(estilo), 90))
    d.update(nome=f"commit {c['hash']}", estilo=estilo, ts=time.time())
    arq = salvar(d)
    _guardar(d)
    _mostrar(pl, d)
    return f"{d['titulo']}:\n" + "\n".join(d["versos"]) + f"\n\nSalvo em {arq}."


def candidatas(rng=random, max_arquivos: int = 40) -> list[tuple[str, str, str]]:
    """(nome, arquivo relativo, código) de funções públicas do JARVIS com 4 a 40 linhas."""
    arquivos = [a for pasta in ("plugins", "core") for a in (PROJETO / pasta).glob("*.py") if not a.name.startswith("__")]
    rng.shuffle(arquivos)
    out = []
    for arq in arquivos[:max_arquivos]:
        try:
            src = arq.read_text(encoding="utf-8", errors="replace")
            arvore = ast.parse(src)
        except (OSError, SyntaxError, ValueError):
            continue
        linhas = src.splitlines()
        for n in arvore.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_") and n.name not in ("run", "passo"):
                tam = getattr(n, "end_lineno", n.lineno) - n.lineno + 1
                if 4 <= tam <= 40:
                    out.append((n.name, _rel(arq), "\n".join(linhas[n.lineno - 1:n.end_lineno])))
        if len(out) >= 12:
            break
    return out


def _desafio(p, pl):
    cs = candidatas()
    if not cs:
        return "Não achei funções para o desafio."
    nome, arq, codigo = random.choice(cs)
    d = compor(nome, codigo, str(p.get("estilo") or "boom bap"), esconder_nome=nome)
    est = carregar("codigo_rap", {"raps": [], "desafio": None})
    est["desafio"] = {"nome": nome, "arquivo": arq, "tentativas": 0, "ts": time.time()}
    guardar("codigo_rap", est)
    _mostrar(pl, d)
    return ("Desafio: rimei uma função do próprio JARVIS sem dizer o nome. Qual é?\n" + "\n".join(d["versos"])
            + "\n\nDiga o seu palpite com o nome da função. Três erros e eu revelo.")


def _palpite(p, pl):
    est = carregar("codigo_rap", {"raps": [], "desafio": None})
    dz = est.get("desafio")
    if not dz:
        return "Não tem desafio rolando. Diga 'me desafia no código em rap'."
    if mesmo_nome(str(p.get("palpite") or p.get("funcao") or ""), dz["nome"]):
        est["desafio"] = None
        guardar("codigo_rap", est)
        return f"Acertou! Era a {dz['nome']}, no arquivo {dz['arquivo']}. Respeito, mestre do código."
    dz["tentativas"] = dz.get("tentativas", 0) + 1
    if dz["tentativas"] >= 3:
        est["desafio"] = None
        guardar("codigo_rap", est)
        return f"Não foi dessa vez. Era a {dz['nome']}, no arquivo {dz['arquivo']}."
    guardar("codigo_rap", est)
    dica = f" Dica: ela mora em {dz['arquivo']}." if dz["tentativas"] == 1 else f" Dica: começa com '{dz['nome'][:3]}'."
    return f"Não é essa.{dica} Mais {3 - dz['tentativas']} chance(s)."


def _ultimo(p, pl):
    raps = carregar("codigo_rap", {"raps": []}).get("raps") or []
    if not raps:
        return "Ainda não fiz nenhum rap de código. Diga 'faz um rap do arquivo …'."
    d = raps[-1]
    _mostrar(pl, d)
    return f"{d['titulo']}:\n" + "\n".join(d["versos"])


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"rap": _rap, "commit": _commit, "desafio": _desafio, "palpite": _palpite, "ultimo": _ultimo},
                 player, "Código em rap")
