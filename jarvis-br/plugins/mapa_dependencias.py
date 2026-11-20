"""
Mapa vivo de dependências — ideia 10 (fork PT-BR 1.4).

Lê o código Python de um projeto (o próprio JARVIS por padrão, ou qualquer
pasta) com o módulo `ast`, sem executar nada, e monta o grafo:

    módulo → o que ele importa (do próprio projeto e de fora)
    módulo → quem depende dele (direto e indireto)
    módulo → quais funções/classes ele define e quais nomes os outros usam dele
    ciclos de importação (componentes fortemente conexos, algoritmo de Tarjan)

Com isso responde "se eu mudar X, o que pode quebrar?": dependentes diretos,
dependentes indiretos, os NOMES de X que cada um usa e os testes que cobrem.

    "Jarvis, mostra o mapa de dependências"
    "Jarvis, se eu mudar o _comum, o que quebra?"
    "Jarvis, tem import circular no projeto?"
    "Jarvis, mapa do projeto C:\\Users\\voce\\Desktop\\meu-projeto"

O mapa visual (HTML com layout de forças, sem internet) fica em
memory/mapa_dependencias.html.
"""

from __future__ import annotations

import ast
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from plugins._comum import BASE, MEMORIA, abrir_no_sistema, mostrar

PLUGIN = {
    "name": "mapa_dependencias",
    "brief": "Python dependency map: what imports what, impact of changing a module, import cycles.",
    "description": (
        "Living dependency map of a Python project (JARVIS itself by default, or pasta = any project "
        "folder), built by static analysis. action: 'mapa' (summary: modules, most depended-upon, "
        "external packages, cycles), 'impacto' with alvo = module/file name ('if I change X what "
        "breaks', 'quem usa X'): direct and indirect dependents, names used, covering tests; "
        "'ciclos' (circular imports); 'abrir' (visual HTML map)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mapa | impacto | ciclos | abrir"},
            "alvo": {"type": "STRING", "description": "module or file for impacto"},
            "pasta": {"type": "STRING", "description": "project folder (optional)"},
        },
        "required": ["action"],
    },
}

_PULAR = {".git", "venv", ".venv", "env", "node_modules", "__pycache__", "build", "dist",
          "site-packages", ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}
_HTML = MEMORIA / "mapa_dependencias.html"
_cache: dict[str, tuple[float, dict]] = {}


def raiz_padrao(pasta: str = "") -> Path:
    if pasta:
        p = Path(pasta).expanduser()
        if p.is_dir():
            return p.resolve()
        if p.is_file():
            return p.parent.resolve()
    return BASE


def _arquivos(raiz: Path, limite: int) -> list[Path]:
    saida = []
    pilha = [raiz]
    while pilha and len(saida) < limite:
        d = pilha.pop()
        try:
            itens = sorted(d.iterdir())
        except OSError:
            continue
        for it in itens:
            if it.is_dir():
                if it.name not in _PULAR and not it.name.startswith("."):
                    pilha.append(it)
            elif it.suffix == ".py":
                saida.append(it)
    return saida


def nome_modulo(raiz: Path, arq: Path) -> str:
    rel = arq.relative_to(raiz).with_suffix("")
    partes = list(rel.parts)
    if partes and partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes) or raiz.name


def _resolver(mod_atual: str, eh_pacote: bool, no: ast.ImportFrom) -> str:
    if not no.level:
        return no.module or ""
    base = mod_atual.split(".")
    if not eh_pacote:
        base = base[:-1]
    if no.level > 1:
        base = base[:len(base) - (no.level - 1)]
    return ".".join([*base, *([no.module] if no.module else [])])


def analisar(raiz: Path, limite: int = 3000) -> dict:
    """Grafo de dependências do projeto em `raiz` (puro: só lê arquivos)."""
    raiz = Path(raiz)
    chave = str(raiz)
    arqs = _arquivos(raiz, limite)
    assinatura = max((a.stat().st_mtime for a in arqs), default=0) + len(arqs)
    if chave in _cache and _cache[chave][0] == assinatura:
        return _cache[chave][1]

    modulos: dict[str, dict] = {}
    arvores = {}
    for a in arqs:
        nome = nome_modulo(raiz, a)
        try:
            fonte = a.read_text(encoding="utf-8", errors="replace")
            arvore = ast.parse(fonte, filename=str(a))
        except (SyntaxError, ValueError, OSError) as e:
            modulos[nome] = {"arquivo": str(a.relative_to(raiz)), "erro": str(e)[:120], "importa": [],
                             "externos": [], "defs": [], "linhas": 0, "usa": {}}
            continue
        arvores[nome] = (arvore, a.name == "__init__.py")
        defs = [n.name for n in arvore.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        defs += [t.id for n in arvore.body if isinstance(n, ast.Assign) for t in n.targets
                 if isinstance(t, ast.Name) and t.id.isupper()]
        modulos[nome] = {"arquivo": str(a.relative_to(raiz)), "importa": [], "externos": [],
                         "defs": defs, "linhas": fonte.count("\n") + 1, "usa": {}}

    internos = set(modulos)
    tops_internos = {m.split(".")[0] for m in internos}

    def interno(alvo: str) -> str | None:
        """O módulo interno mais específico que corresponde a `alvo`."""
        partes = alvo.split(".")
        while partes:
            m = ".".join(partes)
            if m in internos:
                return m
            partes.pop()
        return None

    for nome, (arvore, eh_pacote) in arvores.items():
        imp, ext, usa = set(), set(), defaultdict(set)
        apelidos = {}
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                for a in no.names:
                    m = interno(a.name)
                    if m:
                        imp.add(m)
                        if a.asname:                 # import plugins._comum as c → c.x usa _comum
                            apelidos[a.asname] = m
                        else:                        # import core.gemini → o nome ligado é "core"
                            apelidos[a.name.split(".")[0]] = a.name.split(".")[0]
                    elif a.name.split(".")[0] not in tops_internos:
                        ext.add(a.name.split(".")[0])
            elif isinstance(no, ast.ImportFrom):
                base = _resolver(nome, eh_pacote, no)
                for a in no.names:
                    completo = f"{base}.{a.name}" if base else a.name
                    m = interno(completo)
                    if m == completo:            # `from plugins import limpeza` → o submódulo
                        imp.add(m)
                        apelidos[a.asname or a.name] = m
                    elif m:
                        imp.add(m)
                        usa[m].add(a.name)
                    elif base and base.split(".")[0] not in tops_internos and not no.level:
                        ext.add(base.split(".")[0])
            elif isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name):
                alvo = apelidos.get(no.value.id)
                if alvo and alvo in internos:
                    usa[alvo].add(no.attr)
        imp.discard(nome)
        modulos[nome]["importa"] = sorted(imp)
        modulos[nome]["externos"] = sorted(ext)
        modulos[nome]["usa"] = {k: sorted(v) for k, v in usa.items() if k != nome}

    dependentes = defaultdict(set)
    for nome, info in modulos.items():
        for m in info["importa"]:
            dependentes[m].add(nome)
    g = {"raiz": str(raiz), "modulos": modulos,
         "dependentes": {k: sorted(v) for k, v in dependentes.items()},
         "ciclos": ciclos({k: v["importa"] for k, v in modulos.items()}),
         "externos": Counter(e for v in modulos.values() for e in v["externos"]),
         "gerado": time.time()}
    _cache[chave] = (assinatura, g)
    return g


def ciclos(grafo: dict[str, list[str]]) -> list[list[str]]:
    """Componentes fortemente conexos com mais de um módulo (Tarjan, iterativo)."""
    indice, baixo, pilha, na_pilha, saida = {}, {}, [], set(), []
    contador = [0]
    for inicio in grafo:
        if inicio in indice:
            continue
        trabalho = [(inicio, iter(grafo.get(inicio, [])))]
        indice[inicio] = baixo[inicio] = contador[0]
        contador[0] += 1
        pilha.append(inicio)
        na_pilha.add(inicio)
        while trabalho:
            v, filhos = trabalho[-1]
            avancou = False
            for w in filhos:
                if w not in grafo:
                    continue
                if w not in indice:
                    indice[w] = baixo[w] = contador[0]
                    contador[0] += 1
                    pilha.append(w)
                    na_pilha.add(w)
                    trabalho.append((w, iter(grafo.get(w, []))))
                    avancou = True
                    break
                if w in na_pilha:
                    baixo[v] = min(baixo[v], indice[w])
            if avancou:
                continue
            trabalho.pop()
            if trabalho:
                baixo[trabalho[-1][0]] = min(baixo[trabalho[-1][0]], baixo[v])
            if baixo[v] == indice[v]:
                comp = []
                while True:
                    w = pilha.pop()
                    na_pilha.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    saida.append(sorted(comp))
    return saida


def achar_modulo(g: dict, alvo: str) -> str | None:
    a = alvo.strip().replace("\\", "/").removesuffix(".py").replace("/", ".").lower()
    mods = list(g["modulos"])
    for criterio in (lambda m: m.lower() == a,
                     lambda m: m.lower().endswith("." + a),
                     lambda m: m.split(".")[-1].lower() == a.split(".")[-1],
                     lambda m: a.split(".")[-1] in m.split(".")[-1].lower()):
        achados = [m for m in mods if criterio(m)]
        if achados:
            return min(achados, key=len)
    return None


def impacto(g: dict, alvo: str) -> dict:
    mod = achar_modulo(g, alvo) or alvo
    diretos = g["dependentes"].get(mod, [])
    vistos, fila = set(), list(diretos)
    while fila:
        m = fila.pop()
        if m in vistos or m == mod:
            continue
        vistos.add(m)
        fila.extend(g["dependentes"].get(m, []))
    testes = sorted(m for m in vistos if m.split(".")[-1].startswith("test") or ".tests." in f".{m}.")
    usos = {m: g["modulos"][m]["usa"].get(mod, []) for m in diretos if m in g["modulos"]}
    return {"alvo": mod, "existe": mod in g["modulos"], "diretos": diretos,
            "dependentes": sorted(vistos), "indiretos": sorted(vistos - set(diretos)),
            "testes": testes, "usos": usos}


def mais_dependidos(g: dict, n: int = 8) -> list[tuple[str, int]]:
    return sorted(((m, len(d)) for m, d in g["dependentes"].items()), key=lambda x: -x[1])[:n]


# ── mapa visual ────────────────────────────────────────────────────────────────
def gerar_html(g: dict, destino: Path = _HTML) -> Path:
    nos = [{"id": m, "grupo": m.split(".")[0], "linhas": v.get("linhas", 0),
            "dep": len(g["dependentes"].get(m, []))} for m, v in g["modulos"].items()]
    arestas = [[m, d] for m, v in g["modulos"].items() for d in v["importa"]]
    dados = json.dumps({"nos": nos, "arestas": arestas,
                        "ciclos": g["ciclos"], "raiz": g["raiz"]}, ensure_ascii=False)
    html = _MODELO_HTML.replace("__DADOS__", dados)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


_MODELO_HTML = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Mapa de dependências</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#06121c;color:#bfe9ff;font:13px Segoe UI,Arial}
#info{position:fixed;left:12px;top:10px;max-width:420px;background:#0b2233cc;padding:10px 12px;
border:1px solid #1d4d6b;border-radius:8px}#info b{color:#7fdcff}canvas{display:block}
input{background:#04101a;color:#bfe9ff;border:1px solid #1d4d6b;border-radius:4px;padding:4px;width:200px}</style>
</head><body><div id="info"><b>MAPA DE DEPENDÊNCIAS</b><br><span id="raiz"></span><br>
<input id="busca" placeholder="procurar módulo…"><div id="det">Clique num módulo para ver quem depende dele.
Arraste para mover; roda do mouse = zoom.</div></div><canvas id="c"></canvas><script>
const D=__DADOS__;document.getElementById('raiz').textContent=D.raiz+' — '+D.nos.length+' módulos, '+D.arestas.length+' importações, '+D.ciclos.length+' ciclo(s)';
const cv=document.getElementById('c'),cx=cv.getContext('2d');let W,H;function tam(){W=cv.width=innerWidth;H=cv.height=innerHeight}tam();onresize=tam;
const cores={},pal=['#4fc3f7','#ffb74d','#81c784','#e57373','#ba68c8','#fff176','#4db6ac','#f06292','#90a4ae'];
const N=D.nos.map((n,i)=>(cores[n.grupo]=cores[n.grupo]||pal[Object.keys(cores).length%pal.length],
{...n,x:W/2+Math.cos(i)*200*Math.random(),y:H/2+Math.sin(i)*200*Math.random(),vx:0,vy:0}));
const idx=Object.fromEntries(N.map((n,i)=>[n.id,i])),A=D.arestas.filter(a=>a[1] in idx).map(a=>[idx[a[0]],idx[a[1]]]);
const ciclo=new Set(D.ciclos.flat());let sel=-1,z=1,ox=0,oy=0,arr=-1,pan=null;
function passo(){for(let i=0;i<N.length;i++){const a=N[i];for(let j=i+1;j<N.length;j++){const b=N[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01;
if(d2>90000)continue;const f=900/d2;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f}}
for(const[s,t]of A){const a=N[s],b=N[t];const dx=b.x-a.x,dy=b.y-a.y;a.vx+=dx*.002;a.vy+=dy*.002;b.vx-=dx*.002;b.vy-=dy*.002}
for(const n of N){n.vx+=(W/2-n.x)*.0008;n.vy+=(H/2-n.y)*.0008;if(N.indexOf(n)!==arr){n.x+=n.vx;n.y+=n.vy}n.vx*=.82;n.vy*=.82}}
function desenha(){cx.setTransform(1,0,0,1,0,0);cx.clearRect(0,0,W,H);cx.setTransform(z,0,0,z,ox,oy);
const viz=new Set();if(sel>=0)for(const[s,t]of A){if(t===sel)viz.add(s);if(s===sel)viz.add(t)}
for(const[s,t]of A){const a=N[s],b=N[t];const on=sel>=0&&(s===sel||t===sel);cx.strokeStyle=on?(t===sel?'#ffb74d':'#7fdcff'):'rgba(127,220,255,.10)';
cx.lineWidth=on?1.6:.6;cx.beginPath();cx.moveTo(a.x,a.y);cx.lineTo(b.x,b.y);cx.stroke()}
N.forEach((n,i)=>{const r=3+Math.sqrt(n.dep)*2.2;cx.fillStyle=cores[n.grupo];cx.globalAlpha=sel<0||i===sel||viz.has(i)?1:.25;
cx.beginPath();cx.arc(n.x,n.y,r,0,7);cx.fill();if(ciclo.has(n.id)){cx.strokeStyle='#ff5252';cx.lineWidth=2;cx.stroke()}
if(n.dep>3||i===sel||viz.has(i)){cx.fillStyle='#e8f7ff';cx.fillText(n.id,n.x+r+2,n.y+3)}cx.globalAlpha=1})}
function laco(){passo();desenha();requestAnimationFrame(laco)}laco();
function mundo(e){return[(e.clientX-ox)/z,(e.clientY-oy)/z]}
function perto(e){const[x,y]=mundo(e);let m=-1,md=144;N.forEach((n,i)=>{const d=(n.x-x)**2+(n.y-y)**2;if(d<md){md=d;m=i}});return m}
cv.onmousedown=e=>{const i=perto(e);if(i>=0){arr=i;mostra(i)}else pan=[e.clientX-ox,e.clientY-oy]};
cv.onmousemove=e=>{if(arr>=0){const[x,y]=mundo(e);N[arr].x=x;N[arr].y=y}else if(pan){ox=e.clientX-pan[0];oy=e.clientY-pan[1]}};
onmouseup=()=>{arr=-1;pan=null};cv.onwheel=e=>{e.preventDefault();const k=e.deltaY<0?1.1:.9;ox=e.clientX-(e.clientX-ox)*k;oy=e.clientY-(e.clientY-oy)*k;z*=k};
function mostra(i){sel=i;const n=N[i];const usa=A.filter(a=>a[0]===i).map(a=>N[a[1]].id),dep=A.filter(a=>a[1]===i).map(a=>N[a[0]].id);
document.getElementById('det').innerHTML='<b>'+n.id+'</b> ('+n.linhas+' linhas)<br><span style="color:#ffb74d">depende dele ('+dep.length+'):</span> '+(dep.join(', ')||'ninguém')+'<br><span style="color:#7fdcff">importa ('+usa.length+'):</span> '+(usa.join(', ')||'nada do projeto')}
document.getElementById('busca').oninput=e=>{const t=e.target.value.toLowerCase();const i=N.findIndex(n=>n.id.toLowerCase().includes(t));if(t&&i>=0)mostra(i)};
</script></body></html>"""


# ── voz ────────────────────────────────────────────────────────────────────────
def _resumo(g: dict) -> str:
    mods = g["modulos"]
    linhas = sum(v.get("linhas", 0) for v in mods.values())
    erros = [m for m, v in mods.items() if v.get("erro")]
    txt = [f"Projeto: {g['raiz']}", f"{len(mods)} módulos, {linhas:,} linhas".replace(",", "."), "",
           "MAIS USADOS (quem mais tem dependentes):"]
    txt += [f"  {m}: {n} módulo(s) dependem dele" for m, n in mais_dependidos(g)]
    txt += ["", "PACOTES EXTERNOS MAIS IMPORTADOS:"]
    txt += [f"  {e}: {n}" for e, n in g["externos"].most_common(10)]
    txt += ["", f"CICLOS DE IMPORTAÇÃO: {len(g['ciclos'])}"]
    txt += [f"  {' ↔ '.join(c)}" for c in g["ciclos"][:10]]
    if erros:
        txt += ["", "NÃO CONSEGUI LER (erro de sintaxe):"] + [f"  {m}: {mods[m]['erro']}" for m in erros[:10]]
    return "\n".join(txt)


def texto_impacto(r: dict) -> str:
    if not r["existe"]:
        return f"Não achei o módulo '{r['alvo']}' no projeto."
    linhas = [f"Se mudar {r['alvo']}:",
              f"  {len(r['diretos'])} módulo(s) importam ele diretamente",
              f"  {len(r['indiretos'])} dependem dele indiretamente", ""]
    for m in r["diretos"]:
        nomes = r["usos"].get(m) or []
        linhas.append(f"  • {m}" + (f" — usa: {', '.join(nomes[:8])}" if nomes else ""))
    linhas += ["", "Testes que cobrem: " + (", ".join(r["testes"]) or "nenhum (cuidado)")]
    return "\n".join(linhas)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "mapa").lower()
    try:
        raiz = raiz_padrao(str(p.get("pasta") or ""))
        g = analisar(raiz)
        if not g["modulos"]:
            return f"Não achei arquivos Python em {raiz}."
        if acao == "impacto":
            alvo = str(p.get("alvo") or "").strip()
            if not alvo:
                return "Qual módulo ou arquivo você quer mudar?"
            r = impacto(g, alvo)
            mostrar(player, f"IMPACTO — {r['alvo']}", texto_impacto(r))
            if not r["existe"]:
                return texto_impacto(r)
            return (f"Mudar {r['alvo']} afeta {len(r['diretos'])} módulo(s) direto e "
                    f"{len(r['indiretos'])} indireto. "
                    + (f"Mais sensíveis: {', '.join(r['diretos'][:4])}. " if r["diretos"] else "")
                    + (f"Testes para rodar: {', '.join(r['testes'][:4])}." if r["testes"] else
                       "Nenhum teste cobre esse módulo."))
        if acao == "ciclos":
            if not g["ciclos"]:
                return "Nenhum import circular no projeto."
            return f"{len(g['ciclos'])} ciclo(s): " + "; ".join(" ↔ ".join(c) for c in g["ciclos"][:5])
        if acao == "abrir":
            arq = gerar_html(g)
            return "Abri o mapa visual." if abrir_no_sistema(str(arq)) else f"Mapa salvo em {arq}."
        gerar_html(g)
        mostrar(player, "MAPA DE DEPENDÊNCIAS", _resumo(g))
        top = mais_dependidos(g, 3)
        return (f"{len(g['modulos'])} módulos. Os mais usados: "
                + ", ".join(f"{m} ({n})" for m, n in top)
                + f". {len(g['ciclos'])} ciclo(s) de importação. O mapa visual está pronto se quiser abrir.")
    except Exception as e:
        return f"Não consegui montar o mapa: {e}"
