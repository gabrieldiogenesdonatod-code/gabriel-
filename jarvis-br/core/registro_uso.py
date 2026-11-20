"""
core/registro_uso.py — o diário do próprio JARVIS (fork PT-BR 1.4).

Guarda, em memory/uso.db (SQLite), o que o assistente FEZ:
    chamadas   cada ferramenta chamada: quando, quanto demorou, se deu certo e
               um resumo curto do resultado;
    registro   as linhas do registro de atividade (SYS:, ERR:, falas);
    tarefas    execuções com vários passos (protocolos, cadeias de habilidades),
               com a duração de cada passo.

É a matéria-prima de várias funções da 1.4: radar de anomalias, detector de
oportunidades, criador de ferramentas, memória contrafactual, reconstrução de
acontecimentos e o gêmeo digital. Fica só no seu computador, apaga o que tem
mais de 60 dias e nunca guarda o conteúdo inteiro do que você digitou: os
parâmetros são cortados e campos com cara de segredo viram "***".

Gravar é barato (uma linha por chamada, numa thread qualquer) e NUNCA levanta
exceção: um diário com problema não pode derrubar a ferramenta que funcionou.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "memory" / "uso.db"
RETENCAO_DIAS = 60

_lock = threading.Lock()
_con: sqlite3.Connection | None = None
_aberto: Path | None = None
_ultima_limpeza = 0.0

_SEGREDO = re.compile(r"(senha|password|token|key|chave|secret|pin)", re.I)


def _c() -> sqlite3.Connection:
    global _con, _aberto
    if _con is None or _aberto != ARQUIVO:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        _con = sqlite3.connect(str(ARQUIVO), check_same_thread=False, timeout=5)
        _aberto = ARQUIVO
        _con.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS chamadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, ferramenta TEXT,
                acao TEXT, params TEXT, ms REAL, ok INTEGER, resumo TEXT);
            CREATE INDEX IF NOT EXISTS ix_ch_ts ON chamadas(ts);
            CREATE TABLE IF NOT EXISTS registro (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, linha TEXT);
            CREATE INDEX IF NOT EXISTS ix_rg_ts ON registro(ts);
            CREATE TABLE IF NOT EXISTS tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, tipo TEXT, nome TEXT,
                passos TEXT, ms REAL, ok INTEGER);
            CREATE TABLE IF NOT EXISTS erros (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, origem TEXT, tipo TEXT,
                mensagem TEXT, arquivo TEXT, linha INTEGER, traceback TEXT);
            CREATE INDEX IF NOT EXISTS ix_er_ts ON erros(ts);
        """)
    return _con


def _limpar_params(params) -> dict:
    saida = {}
    for k, v in (params or {}).items():
        if _SEGREDO.search(str(k)):
            saida[k] = "***"
        elif isinstance(v, str):
            saida[k] = v[:120]
        elif isinstance(v, (int, float, bool)) or v is None:
            saida[k] = v
        else:
            saida[k] = str(v)[:120]
    return saida


_FALHA = ("failed", "falhou", "falha", "erro", "error", "not available", "crashed",
          "não consegui", "nao consegui", "indisponível")


def parece_falha(resultado: str) -> bool:
    r = str(resultado or "")
    try:
        from core.outcome import is_problem
        if is_problem(r):
            return True
    except Exception:
        pass
    inicio = r[:160].lower()
    return any(f in inicio for f in _FALHA)


def _anonimo() -> bool:
    """3.2: no modo anônimo nada da conversa é gravado (core/anonimo.py)."""
    try:
        from core import anonimo
        return anonimo.ativo()
    except Exception:
        return False


def registrar_chamada(ferramenta: str, params: dict | None, ms: float, ok: bool,
                      resultado: str = "") -> None:
    global _ultima_limpeza
    if _anonimo():
        return
    try:
        p = _limpar_params(params)
        with _lock:
            c = _c()
            c.execute("INSERT INTO chamadas (ts, ferramenta, acao, params, ms, ok, resumo) "
                      "VALUES (?,?,?,?,?,?,?)",
                      (time.time(), ferramenta, str(p.get("action") or p.get("acao") or ""),
                       json.dumps(p, ensure_ascii=False), float(ms), int(bool(ok)),
                       str(resultado or "")[:240]))
            c.commit()
            if time.time() - _ultima_limpeza > 86400:
                _ultima_limpeza = time.time()
                limite = time.time() - RETENCAO_DIAS * 86400
                for t in ("chamadas", "registro", "tarefas", "erros"):
                    c.execute(f"DELETE FROM {t} WHERE ts < ?", (limite,))
                c.commit()
    except Exception as e:
        print(f"[RegistroUso] {e}")


def registrar_linha(linha: str) -> None:
    if _anonimo():
        return
    try:
        texto = str(linha or "").strip()
        if not texto:
            return
        with _lock:
            c = _c()
            c.execute("INSERT INTO registro (ts, linha) VALUES (?, ?)", (time.time(), texto[:500]))
            c.commit()
    except Exception as e:
        print(f"[RegistroUso] {e}")


def registrar_tarefa(tipo: str, nome: str, passos: list[dict], ms: float, ok: bool) -> None:
    """passos: [{'descricao', 'ms', 'ok', 'resultado'}]"""
    if _anonimo():
        return
    try:
        with _lock:
            c = _c()
            c.execute("INSERT INTO tarefas (ts, tipo, nome, passos, ms, ok) VALUES (?,?,?,?,?,?)",
                      (time.time(), tipo, nome, json.dumps(passos, ensure_ascii=False)[:20000],
                       float(ms), int(bool(ok))))
            c.commit()
    except Exception as e:
        print(f"[RegistroUso] {e}")


def _linhas(sql: str, args=()) -> list[dict]:
    try:
        with _lock:
            c = _c()
            c.row_factory = sqlite3.Row
            r = [dict(x) for x in c.execute(sql, args).fetchall()]
            c.row_factory = None
        return r
    except Exception as e:
        print(f"[RegistroUso] {e}")
        return []


def chamadas(desde: float = 0, ate: float | None = None, ferramenta: str | None = None) -> list[dict]:
    sql = "SELECT * FROM chamadas WHERE ts >= ? AND ts <= ?"
    args: list = [desde, ate or time.time() + 60]
    if ferramenta:
        sql += " AND ferramenta = ?"
        args.append(ferramenta)
    return _linhas(sql + " ORDER BY ts", args)


def linhas_registro(desde: float = 0, ate: float | None = None) -> list[dict]:
    return _linhas("SELECT * FROM registro WHERE ts >= ? AND ts <= ? ORDER BY ts",
                   (desde, ate or time.time() + 60))


def tarefas(desde: float = 0, tipo: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM tarefas WHERE ts >= ?", [desde]
    if tipo:
        sql += " AND tipo = ?"
        args.append(tipo)
    saida = _linhas(sql + " ORDER BY ts", args)
    for t in saida:
        try:
            t["passos"] = json.loads(t["passos"])
        except Exception:
            t["passos"] = []
    return saida


class Cronometro:
    """with Cronometro('ferramenta', params) as c: c.resultado = ..."""

    def __init__(self, ferramenta: str, params: dict | None = None):
        self.ferramenta, self.params, self.resultado = ferramenta, params, ""
        self.ok = True

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, tipo, valor, _tb):
        ms = (time.perf_counter() - self._t0) * 1000
        ok = self.ok and tipo is None and not parece_falha(self.resultado)
        registrar_chamada(self.ferramenta, self.params, ms, ok,
                          self.resultado if tipo is None else f"exceção: {valor}")
        return False


# ── Fork PT-BR 1.5: erros com traceback (para a auto-melhoria) ────────────────
_BASE = Path(__file__).resolve().parent.parent


def registrar_erro(origem: str, erro) -> None:
    """Guarda o traceback de uma exceção (ou um texto). O arquivo/linha é o
    último quadro DENTRO do projeto, que é onde costuma estar o conserto."""
    if _anonimo():
        return
    try:
        import traceback
        if isinstance(erro, BaseException):
            quadros = traceback.extract_tb(erro.__traceback__) if erro.__traceback__ else []
            tb = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
            tipo, msg = type(erro).__name__, str(erro)
        else:
            quadros, tb = [], str(erro)
            tipo, msg = "Erro", str(erro)[:300]
        arquivo, linha = "", 0
        for q in reversed(quadros):
            try:
                rel = Path(q.filename).resolve().relative_to(_BASE)
            except Exception:
                continue
            arquivo, linha = str(rel).replace("\\", "/"), int(q.lineno or 0)
            break
        with _lock:
            c = _c()
            c.execute("INSERT INTO erros (ts, origem, tipo, mensagem, arquivo, linha, traceback) VALUES (?,?,?,?,?,?,?)",
                      (time.time(), origem, tipo, msg[:500], arquivo, linha, tb[-6000:]))
            c.commit()
    except Exception as e:
        print(f"[RegistroUso] erro ao guardar erro: {e}")


def erros(desde: float = 0) -> list[dict]:
    return _linhas("SELECT * FROM erros WHERE ts >= ? ORDER BY ts", (desde,))
