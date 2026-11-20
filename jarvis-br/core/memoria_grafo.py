"""
Memória em grafo (fork PT-BR 2.4).

A memória deixa de ser uma lista e vira uma REDE: cada lembrança é um nó
ligado às pessoas, projetos, produtos e lugares que ela cita, e essas coisas
ficam ligadas entre si. A busca é por SIGNIFICADO:

    "o que eu decidi sobre o capacete?"  → acha "Escolhi o ESP32-S3 para o Mark" mesmo sem a palavra

A nota de cada lembrança junta três coisas:
    significado (55%)  — embeddings do Gemini (se houver chave) e a rede
                         neural treinada no seu PC (core/rede_neural.py);
    palavras    (25%)  — as palavras e os pedaços delas (decidi ≈ decisão);
    grafo       (20%)  — lembranças ligadas ao que a pergunta cita (e às
                         coisas ligadas a elas).

De onde vêm as lembranças: o que você manda lembrar, a memória do Mark LVI
(memory/long_term.json), a memória inteligente da 1.4, o diário (2.4) e as
decisões que o JARVIS anotar. Tudo em memory/memoria_grafo.db, só no seu PC.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import struct
import threading
import time
from pathlib import Path

from core.rede_neural import RedeNeural, normalizar, tokenizar

BASE = Path(__file__).resolve().parent.parent
ARQ = BASE / "memory" / "memoria_grafo.db"
ARQ_REDE = BASE / "memory" / "rede_memoria.npz"
TIPOS = ("pessoa", "projeto", "produto", "lugar", "empresa", "assunto")
PESOS = {"sem": 0.55, "lex": 0.25, "grafo": 0.20}
MODELOS_GEMINI = ("gemini-embedding-001", "text-embedding-004")

_lock = threading.RLock()
_con: dict = {"c": None, "arq": None}
_rede: dict = {"r": None, "arq": None, "treinando": False}


# ── banco ────────────────────────────────────────────────────────────────────
def _c() -> sqlite3.Connection:
    if _con["c"] is None or _con["arq"] != ARQ:
        if _con["c"] is not None:
            _con["c"].close()
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(ARQ), check_same_thread=False, timeout=10)
        c.row_factory = sqlite3.Row
        c.executescript("""
            CREATE TABLE IF NOT EXISTS nos (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, nome TEXT,
                chave TEXT UNIQUE, texto TEXT, ts REAL, fonte TEXT);
            CREATE TABLE IF NOT EXISTS arestas (a INTEGER, b INTEGER, rel TEXT, peso REAL, ts REAL,
                PRIMARY KEY (a, b, rel));
            CREATE TABLE IF NOT EXISTS vetores (no INTEGER, modelo TEXT, v BLOB, PRIMARY KEY (no, modelo));
            CREATE INDEX IF NOT EXISTS i_arestas_b ON arestas (b);
        """)
        c.commit()
        _con.update(c=c, arq=ARQ)
    return _con["c"]


def _blob(v) -> bytes:
    return struct.pack(f"{len(v)}f", *[float(x) for x in v])


def _vet(b: bytes) -> list[float]:
    return list(struct.unpack(f"{len(b) // 4}f", b))


def _cos(a, b) -> float:
    if a is None or b is None or len(a) != len(b):
        return 0.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def chave_entidade(tipo: str, nome: str) -> str:
    return f"{tipo}:{normalizar(nome).strip()}"


def chave_fato(texto: str) -> str:
    return "fato:" + hashlib.sha1(normalizar(" ".join(str(texto).split())).encode()).hexdigest()[:20]


def raizes(texto: str) -> set[str]:
    """Palavras e o começo delas (5 letras): 'decidi' e 'decisão' casam por 'decid'/'decis'… (pura)."""
    saida = set()
    for w in tokenizar(texto):
        saida.add(w)
        if len(w) >= 6:
            saida.add(w[:5])
        if len(w) >= 5:
            saida.add(w[:4] + "*")
    return saida


def nota_lexica(pergunta: str, texto: str) -> float:
    q, t = raizes(pergunta), raizes(texto)
    if not q:
        return 0.0
    return len(q & t) / len(q)


INDICIOS = [
    ("projeto", r"\b(?:projeto|app|site|sistema|bot|jogo)\s+(?:do |da |de )?([A-Z][\w.\-]+(?:\s[A-Z][\w.\-]+)?)"),
    ("empresa", r"\b(?:loja|empresa|marca)\s+(?:do |da |de )?([A-Z][\w\-]+(?:\s[A-Z][\w\-]+)?)"),
    ("lugar", r"\b(?:em|para|pra|no|na)\s+(Goiânia|São Paulo|Rio de Janeiro|Brasília|Anápolis|[A-Z][a-zà-ú]+ (?:do|de) [A-Z][a-zà-ú]+)"),
    ("pessoa", r"\b(?:minha|meu|com a|com o|a|o)\s+(?:amiga|amigo|irmã|irmão|mãe|pai|vó|vô|tia|tio|prima|primo|"
               r"namorada|namorado|esposa|marido|chefe|cliente)?\s*([A-Z][a-zà-ú]{2,})\b"),
]
GENERICAS = {"Eu", "Hoje", "Amanhã", "Ontem", "Jarvis", "JARVIS", "Senhor", "Não", "Sim", "Ele", "Ela", "Isso",
             "Quando", "Onde", "Como", "Mas", "Depois", "Antes", "Se", "Para", "Por", "Que", "Também", "Já"}


def extrair_local(texto: str, conhecidas: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Entidades por regras: as que já existem no grafo + nomes com maiúscula (pura)."""
    achadas: dict[str, tuple[str, str]] = {}
    t_norm = f" {normalizar(texto)} "
    for nome_norm, (tipo, nome) in (conhecidas or {}).items():
        if len(nome_norm) >= 3 and re.search(rf"\b{re.escape(nome_norm)}\b", t_norm):
            achadas[nome_norm] = (nome, tipo)
    for tipo, rx in INDICIOS:
        for m in re.finditer(rx, texto):
            nome = m.group(1).strip()
            if nome and nome not in GENERICAS and normalizar(nome) not in achadas:
                achadas[normalizar(nome)] = (nome, tipo)
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][\w\-]{2,}(?:\s[A-Z][\w\-]{2,})?)", texto):
        nome = m.group(1)
        if nome.split()[0] in GENERICAS or normalizar(nome) in achadas:
            continue
        achadas[normalizar(nome)] = (nome, "assunto")
    return list(achadas.values())[:8]


def prompt_extracao(texto: str) -> str:
    return ("Extraia as entidades citadas nesta anotação pessoal (português). Responda SÓ JSON no formato "
            '{"entidades": [{"nome": "...", "tipo": "pessoa|projeto|produto|lugar|empresa|assunto"}], '
            '"relacoes": [{"de": "...", "rel": "verbo curto", "para": "..."}]}. No máximo 6 entidades; nomes curtos '
            "como a pessoa falaria (ex.: 'capacete', 'Cristal Malhas', 'ESP32'). Anotação: " + texto)


# ── embeddings ───────────────────────────────────────────────────────────────
def embed_gemini(textos: list[str]) -> tuple[str, list[list[float]]] | None:
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return None
        from core import gemini
        cli = gemini.client(timeout_ms=30_000)
    except Exception:
        return None
    for modelo in MODELOS_GEMINI:
        try:
            r = cli.models.embed_content(model=modelo, contents=textos)
            vs = [list(e.values) for e in r.embeddings]
            if len(vs) == len(textos):
                return modelo, vs
        except Exception as e:
            print(f"[MemóriaGrafo] embeddings {modelo}: {e}")
    return None


def rede() -> RedeNeural | None:
    if _rede["r"] is None or _rede["arq"] != ARQ_REDE:
        _rede.update(r=RedeNeural.carregar(ARQ_REDE) if ARQ_REDE.exists() else None, arq=ARQ_REDE)
    return _rede["r"]


def _vetorizar(ids_textos: list[tuple[int, str]]) -> None:
    """Guarda os vetores (Gemini e rede local) dos nós que ainda não têm."""
    if not ids_textos:
        return
    r = rede()
    with _lock:
        c = _c()
        if r is not None:
            for i, t in ids_textos:
                c.execute("INSERT OR REPLACE INTO vetores VALUES (?,?,?)", (i, "local", _blob(r.vetor_texto(t))))
        c.commit()
    for k in range(0, len(ids_textos), 50):
        lote = ids_textos[k:k + 50]
        g = embed_gemini([t for _i, t in lote])
        if not g:
            break
        modelo, vs = g
        with _lock:
            c = _c()
            for (i, _t), v in zip(lote, vs):
                c.execute("INSERT OR REPLACE INTO vetores VALUES (?,?,?)", (i, modelo, _blob(v)))
            c.commit()


# ── escrever ─────────────────────────────────────────────────────────────────
def _entidade(c, nome: str, tipo: str, agora: float) -> int:
    tipo = tipo if tipo in TIPOS else "assunto"
    nome = " ".join(str(nome).split())[:80]
    existente = c.execute("SELECT id FROM nos WHERE tipo != 'fato' AND chave LIKE ?",
                          (f"%:{normalizar(nome).strip()}",)).fetchone()
    if existente:
        return existente["id"]
    cur = c.execute("INSERT INTO nos (tipo, nome, chave, texto, ts, fonte) VALUES (?,?,?,?,?,?)",
                    (tipo, nome, chave_entidade(tipo, nome), "", agora, "grafo"))
    return cur.lastrowid


def _ligar(c, a: int, b: int, rel: str, agora: float) -> None:
    if a == b:
        return
    c.execute("INSERT INTO arestas (a, b, rel, peso, ts) VALUES (?,?,?,1,?) "
              "ON CONFLICT(a, b, rel) DO UPDATE SET peso = peso + 1, ts = excluded.ts", (a, b, rel[:40], agora))


def conhecidas() -> dict[str, tuple[str, str]]:
    with _lock:
        return {normalizar(r["nome"]): (r["tipo"], r["nome"])
                for r in _c().execute("SELECT tipo, nome FROM nos WHERE tipo != 'fato'")}


def lembrar(texto: str, fonte: str = "voce", ts: float | None = None, usar_ia: bool = True,
            vetorizar: bool = True) -> dict:
    """Guarda uma lembrança e liga às entidades que ela cita. Repetida = reforça."""
    texto = " ".join(str(texto or "").split())
    if not texto:
        return {}
    agora = ts or time.time()
    chave = chave_fato(texto)
    with _lock:
        c = _c()
        igual = c.execute("SELECT id FROM nos WHERE chave = ?", (chave,)).fetchone()
        if igual:
            return {"id": igual["id"], "repetida": True, "entidades": []}
    ents, rels = [], []
    if usar_ia:
        try:
            from plugins import _ia
            j = _ia.perguntar_json(prompt_extracao(texto), False, 20) if _ia.disponivel() else None
            if isinstance(j, dict):
                ents = [(str(e.get("nome", "")), str(e.get("tipo", "assunto"))) for e in j.get("entidades") or []
                        if isinstance(e, dict) and e.get("nome")][:6]
                rels = [(str(r.get("de", "")), str(r.get("rel", "liga")), str(r.get("para", "")))
                        for r in j.get("relacoes") or [] if isinstance(r, dict)][:6]
        except Exception:
            ents = []
    if not ents:
        ents = extrair_local(texto, conhecidas())
    with _lock:
        c = _c()
        cur = c.execute("INSERT INTO nos (tipo, nome, chave, texto, ts, fonte) VALUES (?,?,?,?,?,?)",
                        ("fato", texto[:60], chave, texto, agora, fonte))
        fid = cur.lastrowid
        ids = {}
        for nome, tipo in ents:
            if nome.strip():
                ids[normalizar(nome)] = _entidade(c, nome, tipo, agora)
                _ligar(c, fid, ids[normalizar(nome)], "cita", agora)
        for a, rel, b in rels:
            ia, ib = ids.get(normalizar(a)), ids.get(normalizar(b))
            if ia and ib:
                _ligar(c, ia, ib, rel or "liga", agora)
        lista = list(ids.values())                              # quem aparece junto fica ligado
        for i in range(len(lista)):
            for j in range(i + 1, len(lista)):
                _ligar(c, lista[i], lista[j], "junto", agora)
        c.commit()
    if vetorizar:
        _vetorizar([(fid, texto)])
    return {"id": fid, "repetida": False, "entidades": [n for n, _t in ents]}


# ── ler ──────────────────────────────────────────────────────────────────────
def _vizinhos(c, ids: set[int]) -> set[int]:
    if not ids:
        return set()
    marc = ",".join("?" * len(ids))
    rows = c.execute(f"SELECT a, b FROM arestas WHERE a IN ({marc}) OR b IN ({marc})", (*ids, *ids)).fetchall()
    return {x for r in rows for x in (r["a"], r["b"])} - ids


def buscar(pergunta: str, k: int = 5, desde: float | None = None, ate: float | None = None) -> list[dict]:
    pergunta = str(pergunta or "").strip()
    if not pergunta:
        return []
    with _lock:
        c = _c()
        fatos = [dict(r) for r in c.execute("SELECT id, texto, ts, fonte FROM nos WHERE tipo = 'fato'")]
        if desde is not None or ate is not None:
            fatos = [f for f in fatos if (desde is None or f["ts"] >= desde) and (ate is None or f["ts"] < ate)]
        if not fatos:
            return []
        vets: dict[str, dict[int, list[float]]] = {}
        for r in c.execute("SELECT no, modelo, v FROM vetores"):
            vets.setdefault(r["modelo"], {})[r["no"]] = _vet(r["v"])
        # entidades citadas na pergunta → fatos ligados (1 passo = 1.0, 2 passos = 0.5)
        citadas = {i for i in (_entidade_por_nome(c, n) for n, _t in extrair_local(pergunta, conhecidas())) if i}
        perto = _vizinhos(c, citadas)
        longe = _vizinhos(c, perto) if perto else set()
    sem: dict[int, float] = {}
    g = None
    modelo_g = next((m for m in MODELOS_GEMINI if vets.get(m)), None)
    if modelo_g:
        r = embed_gemini([pergunta])
        if r and r[0] == modelo_g:
            g = r[1][0]
            for f in fatos:
                if f["id"] in vets[modelo_g]:
                    sem[f["id"]] = _cos(g, vets[modelo_g][f["id"]])
    rl = rede()
    if rl is not None and vets.get("local"):
        q = list(rl.vetor_texto(pergunta))
        for f in fatos:
            if f["id"] in vets["local"]:
                s = _cos(q, vets["local"][f["id"]])
                sem[f["id"]] = max(sem.get(f["id"], 0.0), s) if g is None else 0.7 * sem.get(f["id"], 0.0) + 0.3 * s
    saida = []
    for f in fatos:
        grafo = 1.0 if f["id"] in perto else 0.5 if f["id"] in longe else 0.0
        lex = nota_lexica(pergunta, f["texto"])
        s = PESOS["sem"] * max(0.0, sem.get(f["id"], 0.0)) + PESOS["lex"] * lex + PESOS["grafo"] * grafo
        if not sem:                                            # sem nenhum vetor ainda: palavras e grafo valem tudo
            s = 0.65 * lex + 0.35 * grafo
        if s > 0.1:
            saida.append({**f, "nota": round(s, 3), "lex": round(lex, 2), "grafo": grafo})
    saida.sort(key=lambda x: (-x["nota"], -x["ts"]))
    return saida[:k]


def _entidade_por_nome(c, nome: str) -> int | None:
    r = c.execute("SELECT id FROM nos WHERE tipo != 'fato' AND chave LIKE ?", (f"%:{normalizar(nome).strip()}",)).fetchone()
    return r["id"] if r else None


def conexoes(nome: str) -> dict:
    with _lock:
        c = _c()
        i = _entidade_por_nome(c, nome)
        if i is None:
            alvo = normalizar(nome)
            r = c.execute("SELECT id FROM nos WHERE tipo != 'fato' AND chave LIKE ?", (f"%{alvo}%",)).fetchone()
            i = r["id"] if r else None
        if i is None:
            return {}
        no = dict(c.execute("SELECT * FROM nos WHERE id = ?", (i,)).fetchone())
        rows = c.execute("SELECT a, b, rel, peso FROM arestas WHERE a = ? OR b = ? ORDER BY peso DESC", (i, i)).fetchall()
        outros = {}
        for r in rows:
            o = r["b"] if r["a"] == i else r["a"]
            n = c.execute("SELECT id, tipo, nome, texto, ts FROM nos WHERE id = ?", (o,)).fetchone()
            if n:
                outros[o] = {**dict(n), "rel": r["rel"], "peso": r["peso"]}
    fatos = sorted((v for v in outros.values() if v["tipo"] == "fato"), key=lambda x: -x["ts"])
    coisas = sorted((v for v in outros.values() if v["tipo"] != "fato"), key=lambda x: -x["peso"])
    return {"no": no, "fatos": fatos, "ligados": coisas}


def estatisticas() -> dict:
    with _lock:
        c = _c()
        por_tipo = {r["tipo"]: r["n"] for r in c.execute("SELECT tipo, COUNT(*) n FROM nos GROUP BY tipo")}
        arestas = c.execute("SELECT COUNT(*) FROM arestas").fetchone()[0]
        modelos = {r["modelo"]: r["n"] for r in c.execute("SELECT modelo, COUNT(*) n FROM vetores GROUP BY modelo")}
    rl = rede()
    return {"tipos": por_tipo, "arestas": arestas, "vetores": modelos,
            "rede": {"palavras": len(rl.vocab), "dim": rl.dim} if rl is not None else None,
            "treinando": _rede["treinando"]}


def grafo_json(limite: int = 250) -> dict:
    """Para a página do mapa: as coisas mais ligadas e as lembranças mais novas."""
    with _lock:
        c = _c()
        ents = [dict(r) for r in c.execute(
            "SELECT n.id, n.tipo, n.nome, (SELECT COUNT(*) FROM arestas WHERE a = n.id OR b = n.id) grau "
            "FROM nos n WHERE n.tipo != 'fato' ORDER BY grau DESC LIMIT ?", (limite // 2,))]
        fatos = [dict(r) for r in c.execute("SELECT id, tipo, nome, texto, ts FROM nos WHERE tipo = 'fato' "
                                            "ORDER BY ts DESC LIMIT ?", (limite // 2,))]
        ids = {n["id"] for n in ents + fatos}
        if not ids:
            return {"nos": [], "arestas": []}
        marc = ",".join("?" * len(ids))
        ar = [dict(r) for r in c.execute(f"SELECT a, b, rel, peso FROM arestas WHERE a IN ({marc}) AND b IN ({marc})",
                                         (*ids, *ids))]
    return {"nos": ents + fatos, "arestas": ar}


# ── importar e treinar ───────────────────────────────────────────────────────
def importar(usar_ia: bool = False) -> int:
    """Traz para o grafo o que já existe nas outras memórias (sem repetir)."""
    novos = 0
    itens: list[tuple[str, str, float]] = []
    try:
        from memory.memory_manager import all_entries_for_ui
        for r in all_entries_for_ui():
            ts = time.mktime(time.strptime(r["updated"][:10], "%Y-%m-%d")) if r.get("updated") else time.time()
            itens.append((f"{r['key'].replace('_', ' ')}: {r['value']}", "mark_lvi", ts))
    except Exception:
        pass
    try:
        from plugins import memoria_inteligente
        for r in memoria_inteligente.todas():
            itens.append((r["texto"], f"memoria_{r.get('categoria', '')}", float(r.get("criada") or time.time())))
    except Exception:
        pass
    try:
        from plugins import diario
        for e in diario.entradas():
            itens.append((f"Diário de {e['data']}: {e['texto']}", "diario", float(e["ts"])))
    except Exception:
        pass
    pendentes = []
    for texto, fonte, ts in itens:
        r = lembrar(texto, fonte, ts, usar_ia=usar_ia, vetorizar=False)
        if r and not r.get("repetida"):
            novos += 1
            pendentes.append((r["id"], " ".join(texto.split())))
    _vetorizar(pendentes)
    return novos


def ligar_assuntos(minimo: int = 2, maximo_frac: float = 0.3) -> int:
    """Palavras que se repetem em várias lembranças ('capacete', 'placa') viram assuntos ligados a elas."""
    from collections import Counter
    with _lock:
        c = _c()
        fatos = [(r["id"], r["texto"], r["ts"]) for r in c.execute("SELECT id, texto, ts FROM nos WHERE tipo = 'fato'")]
        if len(fatos) < 3:
            return 0
        por_fato = {i: {w for w in tokenizar(t) if len(w) >= 5 and not w.isdigit()} for i, t, _ts in fatos}
        cont = Counter(w for ws in por_fato.values() for w in ws)
        cobertas = {w for r in c.execute("SELECT nome FROM nos WHERE tipo != 'fato'") for w in tokenizar(r["nome"])
                    if len(tokenizar(r["nome"])) > 1}          # "cristal" já está dentro de "Cristal Malhas"
        limite = minimo
        novos = 0
        for w, n in cont.items():
            if n < limite or n > max(minimo, maximo_frac * len(fatos)) or w in cobertas:
                continue
            ja = c.execute("SELECT id FROM nos WHERE tipo != 'fato' AND chave LIKE ?", (f"%:{w}",)).fetchone()
            eid = ja["id"] if ja else _entidade(c, w, "assunto", time.time())
            novos += 0 if ja else 1
            for i, t, ts in fatos:
                if w in por_fato[i]:
                    _ligar(c, i, eid, "cita", ts)
        c.commit()
    return novos


def corpus() -> list[list[str]]:
    with _lock:
        c = _c()
        textos = [r["texto"] for r in c.execute("SELECT texto FROM nos WHERE tipo = 'fato'")]
        nomes = [r["nome"] for r in c.execute("SELECT nome FROM nos WHERE tipo != 'fato'")]
    frases = [tokenizar(t) for t in textos]
    return [f for f in frases if len(f) > 1] + [tokenizar(n) for n in nomes if len(tokenizar(n)) > 1]


def treinar_rede(epocas: int = 6) -> str:
    """Treina a rede neural local com tudo o que está no grafo e refaz os vetores 'local'."""
    if _rede["treinando"]:
        return "A rede já está treinando."
    _rede["treinando"] = True
    try:
        ligar_assuntos()
        frases = corpus()
        if sum(len(f) for f in frases) < 20:
            return "Ainda tenho pouca coisa para treinar a rede (lembre mais coisas ou importe as memórias)."
        r = RedeNeural()
        pares = r.treinar(frases, epocas=epocas)
        ARQ_REDE.parent.mkdir(parents=True, exist_ok=True)
        r.salvar(ARQ_REDE)
        _rede.update(r=r, arq=ARQ_REDE)
        with _lock:
            c = _c()
            todos = [(row["id"], row["texto"]) for row in c.execute("SELECT id, texto FROM nos WHERE tipo = 'fato'")]
            for i, t in todos:
                c.execute("INSERT OR REPLACE INTO vetores VALUES (?,?,?)", (i, "local", _blob(r.vetor_texto(t))))
            c.commit()
        return f"Rede treinada: {len(r.vocab)} palavras, {pares} exemplos, {len(todos)} lembranças com vetor novo."
    finally:
        _rede["treinando"] = False


def resumo_resultados(res: list[dict]) -> str:
    if not res:
        return "Não achei nada parecido na memória."
    linhas = []
    for r in res:
        quando = time.strftime("%d/%m/%Y", time.localtime(r["ts"]))
        linhas.append(f"• ({quando}) {r['texto'][:300]}")
    return "\n".join(linhas)


def para_json(res: list[dict]) -> str:
    return json.dumps(res, ensure_ascii=False)
