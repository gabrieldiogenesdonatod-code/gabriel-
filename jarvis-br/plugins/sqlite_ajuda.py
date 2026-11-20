"""SQLite (2.19): olha dentro de um arquivo .db — tabelas, colunas e consultas SELECT — sempre só para leitura."""
from __future__ import annotations

from contextlib import closing
import csv
import sqlite3
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("sqlite_ajuda", "Inspect a SQLite .db file read-only: list tables with row counts, table schema, run SELECT queries, export a query to CSV.",
           "tabelas | esquema | consulta | exportar",
           "arquivo = path to the .db. esquema: tabela. consulta/exportar: sql (SELECT only; the file is opened read-only).",
           "arquivo tabela sql")


def abrir(arq: str) -> sqlite3.Connection:
    pth = Path(str(arq).strip().strip('"')).expanduser()
    if not pth.is_file():
        raise ValueError("não achei esse arquivo .db")
    return sqlite3.connect(f"file:{pth.as_posix()}?mode=ro", uri=True)


def tabela_texto(cols: list[str], linhas: list[tuple], limite: int = 30) -> str:
    out = [" | ".join(cols)] + [" | ".join("" if v is None else str(v)[:40] for v in l) for l in linhas[:limite]]
    return "\n".join(out) + (f"\n… {len(linhas) - limite} linha(s) a mais" if len(linhas) > limite else "")


def _go(p, pl):
    a = p["action"]
    with closing(abrir(p.get("arquivo"))) as con:        # 3.6: fecha o arquivo (antes o .db ficava preso no Windows)
        nomes = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by 1")]
        entre_aspas = lambda t: '"' + t.replace('"', '""') + '"'  # noqa: E731
        if a == "tabelas":
            cont = [(t, con.execute("select count(*) from " + entre_aspas(t)).fetchone()[0]) for t in nomes]
            return "\n".join(f"{t}: {n} linha(s)" for t, n in cont) or "Banco sem tabelas."
        if a == "esquema":
            t = next((x for x in nomes if x.lower() == str(p.get("tabela") or "").lower()), None)
            if not t:
                return "Tabela não encontrada. Tenho: " + ", ".join(nomes) + "."
            cols = con.execute("pragma table_info(" + entre_aspas(t) + ")").fetchall()
            return "\n".join(f"{c[1]} {c[2]}" + (" PK" if c[5] else "") + (" NOT NULL" if c[3] else "") for c in cols)
        sql = str(p.get("sql") or "").strip().rstrip(";")
        if not sql.lower().startswith(("select", "with", "pragma")):
            return "Só rodo SELECT aqui (o arquivo é aberto só para leitura)."
        cur = con.execute(sql)
        cols, linhas = [d[0] for d in cur.description], cur.fetchmany(5000)
    if a == "exportar":
        from plugins._comum import pasta_jarvis
        dest = pasta_jarvis("Consultas") / "consulta.csv"
        with open(dest, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([cols] + linhas)
        return f"{len(linhas)} linha(s) exportadas para {dest}."
    return f"{len(linhas)} linha(s).\n" + tabela_texto(cols, linhas)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("tabelas esquema consulta exportar".split(), _go), player, "SQLite")
