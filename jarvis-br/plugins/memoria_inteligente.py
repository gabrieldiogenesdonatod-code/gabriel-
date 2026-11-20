"""
Memória com esquecimento inteligente — ideia 4 (fork PT-BR 1.4).

Cada lembrança guarda:
    categoria     fato · preferência · decisão · experiência · temporária
    origem        de onde veio ("você disse", "vi no PC", "deduzi", "a IA sugeriu")
    criada / confirmada em
    validade      temporárias expiram sozinhas (padrão: 1 dia)
    confiança     começa alta para o que você disse e baixa para o que foi
                  deduzido, e CAI com o tempo sem confirmação, cada categoria
                  num ritmo (meia-vida): fato 1 ano · preferência 6 meses ·
                  decisão 4 meses · experiência 3 meses.

Ao responder, o JARVIS diz o quanto confia e há quanto tempo foi confirmado,
e avisa quando uma lembrança "pode estar desatualizada", em vez de tratá-la
como verdade atual.

    "Jarvis, lembra que eu prefiro tema escuro"           → preferência
    "Jarvis, anota que decidimos usar Flask no projeto"    → decisão
    "Jarvis, lembra que hoje o cliente vem às 15h"         → temporária (expira)
    "Jarvis, o que você sabe sobre o projeto?"             → com confiança
    "Jarvis, isso ainda vale" / "confirma a do Flask"      → confiança volta a 100%
    "Jarvis, o que pode estar desatualizado?"              → revisão
    "Jarvis, esquece a do tema"

Fica em memory/memoria_inteligente.db, só no seu PC. Convive com a memória
original do Mark LVI (memory/long_term.json), que continua funcionando.
"""

from __future__ import annotations

import math
import re
import sqlite3
import threading
import time
import unicodedata

from plugins._comum import MEMORIA, mostrar

PLUGIN = {
    "name": "memoria_inteligente",
    "brief": "Memory with categories, source, confidence decay and expiry: save, query, confirm, forget, review.",
    "description": (
        "Memory with intelligent forgetting. action='lembrar' (texto; categoria = fato | preferencia | "
        "decisao | experiencia | temporaria, inferred if empty; origem; validade_dias for temporary) for "
        "'lembra que…', 'anota que…'. action='consultar' (termo) for 'o que você sabe sobre…' — answer "
        "with the confidence and age it returns and say when something may be outdated. "
        "action='confirmar' (termo or id) for 'isso ainda vale'; 'corrigir' (id or termo, texto); "
        "'esquecer' (termo or id); 'revisar' lists what may be outdated; 'listar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "texto": {"type": "STRING"}, "termo": {"type": "STRING"}, "id": {"type": "NUMBER"},
            "categoria": {"type": "STRING"}, "origem": {"type": "STRING"},
            "validade_dias": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}

ARQUIVO = MEMORIA / "memoria_inteligente.db"
MEIA_VIDA_DIAS = {"fato": 365, "preferencia": 180, "decisao": 120, "experiencia": 90, "temporaria": 1}
CONFIANCA_ORIGEM = {"usuario": 1.0, "observado": 0.85, "deduzido": 0.6, "ia": 0.5}
ROTULO_ORIGEM = {"usuario": "você disse", "observado": "vi no PC", "deduzido": "deduzi", "ia": "a IA sugeriu"}
ROTULO_CAT = {"fato": "fato", "preferencia": "preferência", "decisao": "decisão",
              "experiencia": "experiência", "temporaria": "temporária"}
LIMIAR_DESATUALIZADA = 0.5

_lock = threading.Lock()
_con = None
_aberto = None


def _d(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


def _c():
    global _con, _aberto
    if _con is None or _aberto != ARQUIVO:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        if _con is not None:                       # 3.6: trocou de arquivo — solta o anterior (no Windows ficava travado)
            try:
                _con.close()
            except Exception:
                pass
        _con = sqlite3.connect(str(ARQUIVO), check_same_thread=False, timeout=5)
        _aberto = ARQUIVO
        _con.row_factory = sqlite3.Row
        _con.execute("""CREATE TABLE IF NOT EXISTS lembrancas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, texto TEXT, chave TEXT, categoria TEXT,
            origem TEXT, criada REAL, confirmada REAL, expira REAL, base REAL, vezes INTEGER DEFAULT 1)""")
        _con.commit()
    return _con


def inferir_categoria(texto: str) -> str:
    t = _d(texto)
    if re.search(r"\b(hoje|amanha|agora|essa semana|esta semana|daqui a|mais tarde|hoje a noite|as \d)", t):
        return "temporaria"
    if re.search(r"\b(prefiro|gosto|nao gosto|odeio|adoro|curto|quero sempre|sempre quero|favorit)", t):
        return "preferencia"
    if re.search(r"\b(decid|vamos usar|ficou definido|combinamos|escolhemos|optamos|a partir de agora)", t):
        return "decisao"
    if re.search(r"\b(aconteceu|deu errado|deu certo|funcionou|tentei|fiz|quebrou|aprendi)", t):
        return "experiencia"
    return "fato"


def _origem(texto: str) -> str:
    t = _d(texto)
    if t in CONFIANCA_ORIGEM:
        return t
    for k, rot in ROTULO_ORIGEM.items():
        if _d(rot) in t:
            return k
    if "ia" in t.split() or "modelo" in t:
        return "ia"
    if "dedu" in t or "acho" in t:
        return "deduzido"
    if "vi " in t or "observ" in t or "pc" in t:
        return "observado"
    return "usuario"


def confianca(linha: dict, agora: float | None = None) -> float:
    """Confiança atual: base da origem × decaimento exponencial pela meia-vida."""
    agora = agora or time.time()
    if linha.get("expira") and agora > linha["expira"]:
        return 0.0
    dias = max(0.0, (agora - (linha.get("confirmada") or linha.get("criada") or agora)) / 86400)
    meia = MEIA_VIDA_DIAS.get(linha.get("categoria"), 180)
    reforco = min(0.15, 0.03 * ((linha.get("vezes") or 1) - 1))     # dito várias vezes = mais firme
    return max(0.0, min(1.0, (float(linha.get("base") or 0.8) + reforco) * math.pow(0.5, dias / meia)))


def _chave(texto: str) -> str:
    palavras = [p for p in re.findall(r"[a-z0-9]+", _d(texto)) if len(p) > 2]
    return " ".join(sorted(set(palavras)))


def lembrar(texto: str, categoria: str = "", origem: str = "", validade_dias: float | None = None,
            agora: float | None = None) -> dict:
    agora = agora or time.time()
    cat = _d(categoria).replace("ê", "e")
    cat = cat if cat in MEIA_VIDA_DIAS else inferir_categoria(texto)
    org = _origem(origem) if origem else "usuario"
    expira = None
    if cat == "temporaria":
        expira = agora + (validade_dias if validade_dias else 1) * 86400
    elif validade_dias:
        expira = agora + float(validade_dias) * 86400
    chave = _chave(texto)
    with _lock:
        c = _c()
        igual = c.execute("SELECT * FROM lembrancas WHERE chave = ?", (chave,)).fetchone()
        if igual:                           # repetir é confirmar
            c.execute("UPDATE lembrancas SET confirmada=?, vezes=vezes+1, base=max(base, ?), expira=? WHERE id=?",
                      (agora, CONFIANCA_ORIGEM[org], expira, igual["id"]))
            c.commit()
            return {**dict(igual), "repetida": True}
        cur = c.execute("INSERT INTO lembrancas (texto, chave, categoria, origem, criada, confirmada, expira, base) "
                        "VALUES (?,?,?,?,?,?,?,?)", (texto.strip(), chave, cat, org, agora, agora, expira,
                                                     CONFIANCA_ORIGEM[org]))
        c.commit()
    if cat != "temporaria":                                    # 2.4: também vai para a memória em grafo
        try:
            import threading as _th

            from core import memoria_grafo
            _th.Thread(target=memoria_grafo.lembrar, args=(texto, f"memoria_{cat}", agora), daemon=True).start()
        except Exception:
            pass
    return {"id": cur.lastrowid, "texto": texto, "categoria": cat, "origem": org, "expira": expira,
            "repetida": False}


def todas(agora: float | None = None, incluir_expiradas: bool = False) -> list[dict]:
    agora = agora or time.time()
    with _lock:
        linhas = [dict(r) for r in _c().execute("SELECT * FROM lembrancas").fetchall()]
    saida = []
    for r in linhas:
        r["confianca"] = confianca(r, agora)
        if not incluir_expiradas and r.get("expira") and agora > r["expira"]:
            continue
        saida.append(r)
    return saida


def buscar(termo: str, agora: float | None = None) -> list[dict]:
    palavras = [p for p in re.findall(r"[a-z0-9]+", _d(termo)) if len(p) > 2]
    res = []
    for r in todas(agora):
        t = _d(r["texto"])
        acertos = sum(1 for p in palavras if p in t)
        if palavras and acertos == 0:
            continue
        res.append((acertos, r["confianca"], r))
    res.sort(key=lambda x: (-x[0], -x[1]))
    return [r for _a, _c2, r in res]


def _idade(r: dict, agora: float | None = None) -> str:
    dias = ((agora or time.time()) - (r.get("confirmada") or r["criada"])) / 86400
    if dias < 1:
        return "hoje"
    if dias < 2:
        return "ontem"
    if dias < 60:
        return f"há {int(dias)} dias"
    return f"há {int(dias / 30)} meses"


def descrever(r: dict) -> str:
    conf = round(100 * r["confianca"])
    aviso = " — PODE ESTAR DESATUALIZADA" if r["confianca"] < LIMIAR_DESATUALIZADA else ""
    exp = ""
    if r.get("expira"):
        horas = (r["expira"] - time.time()) / 3600
        exp = f", expira em {int(horas)} h" if horas < 48 else f", expira em {int(horas / 24)} dias"
    return (f"#{r['id']} [{ROTULO_CAT.get(r['categoria'], r['categoria'])}] {r['texto']} "
            f"({ROTULO_ORIGEM.get(r['origem'], r['origem'])}, confirmada {_idade(r)}, confiança {conf}%{exp}){aviso}")


def _alvo(p: dict) -> dict | None:
    if p.get("id") not in (None, ""):
        try:
            iid = int(float(p["id"]))
        except (TypeError, ValueError):
            iid = -1
        return next((r for r in todas(incluir_expiradas=True) if r["id"] == iid), None)
    achados = buscar(str(p.get("termo") or p.get("texto") or ""))
    return achados[0] if achados else None


def limpar_expiradas() -> int:
    with _lock:
        c = _c()
        n = c.execute("DELETE FROM lembrancas WHERE expira IS NOT NULL AND expira < ?",
                      (time.time() - 7 * 86400,)).rowcount
        c.commit()
    return n


def on_session_start(player) -> None:
    try:
        limpar_expiradas()
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = _d(p.get("action") or "consultar")
    try:
        if a == "lembrar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que devo lembrar?"
            r = lembrar(texto, str(p.get("categoria") or ""), str(p.get("origem") or ""),
                        p.get("validade_dias"))
            if r.get("repetida"):
                return f"Isso eu já sabia; marquei como confirmado agora (#{r['id']})."
            extra = " Expira sozinha." if r["categoria"] == "temporaria" else ""
            return f"Anotado como {ROTULO_CAT[r['categoria']]} (#{r['id']}).{extra}"
        if a == "consultar":
            achados = buscar(str(p.get("termo") or p.get("texto") or ""))
            if not achados:
                return "Não tenho nada sobre isso na memória."
            mostrar(player, "MEMÓRIA", "\n".join(descrever(r) for r in achados[:20]))
            partes = []
            for r in achados[:3]:
                t = f"{r['texto']} (confiança {round(100 * r['confianca'])}%, {ROTULO_ORIGEM.get(r['origem'])}, {_idade(r)})"
                if r["confianca"] < LIMIAR_DESATUALIZADA:
                    t += " — pode estar desatualizado, vale confirmar"
                partes.append(t)
            return "; ".join(partes) + "."
        if a == "confirmar":
            r = _alvo(p)
            if not r:
                return "Não achei essa lembrança."
            with _lock:
                _c().execute("UPDATE lembrancas SET confirmada=?, base=max(base, 0.95), vezes=vezes+1 WHERE id=?",
                             (time.time(), r["id"]))
                _c().commit()
            return f"Confirmado: {r['texto']}."
        if a == "corrigir":
            r = _alvo({**p, "texto": p.get("termo")})
            novo = str(p.get("texto") or "").strip()
            if not r or not novo:
                return "Diga qual lembrança e o texto novo."
            with _lock:
                _c().execute("UPDATE lembrancas SET texto=?, chave=?, confirmada=?, base=1.0, origem='usuario' "
                             "WHERE id=?", (novo, _chave(novo), time.time(), r["id"]))
                _c().commit()
            return f"Corrigido: antes '{r['texto']}', agora '{novo}'."
        if a == "esquecer":
            r = _alvo(p)
            if not r:
                return "Não achei essa lembrança."
            with _lock:
                _c().execute("DELETE FROM lembrancas WHERE id=?", (r["id"],))
                _c().commit()
            return f"Esqueci: {r['texto']}."
        if a == "revisar":
            velhas = sorted((r for r in todas() if r["confianca"] < LIMIAR_DESATUALIZADA),
                            key=lambda r: r["confianca"])
            if not velhas:
                return "Nada parece desatualizado na memória."
            mostrar(player, "MEMÓRIA — PODE ESTAR DESATUALIZADO", "\n".join(descrever(r) for r in velhas[:40]))
            return (f"{len(velhas)} lembrança(s) podem estar desatualizadas; a mais antiga: {velhas[0]['texto']}. "
                    "Diga 'isso ainda vale' para confirmar ou 'esquece' para apagar.")
        if a == "listar":
            rs = sorted(todas(), key=lambda r: -r["confianca"])
            if not rs:
                return "A memória inteligente está vazia."
            mostrar(player, "MEMÓRIA INTELIGENTE", "\n".join(descrever(r) for r in rs[:80]))
            por_cat: dict[str, int] = {}
            for r in rs:
                por_cat[r["categoria"]] = por_cat.get(r["categoria"], 0) + 1
            return f"{len(rs)} lembranças: " + ", ".join(f"{n} {ROTULO_CAT[c]}" for c, n in por_cat.items()) + "."
        return "Use lembrar, consultar, confirmar, corrigir, esquecer, revisar ou listar."
    except Exception as e:
        return f"A memória inteligente falhou: {e}"
