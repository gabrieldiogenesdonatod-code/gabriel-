"""
Histórico do monitoramento em SQLite (memory/monitor.db).

Uma amostra por minuto (médias do último minuto, vindas da telemetria) e os
eventos (alertas, internet caiu/voltou). A retenção é configurável no plugin
monitor_sistema; o que passa dela é apagado uma vez por dia.

Uma linha por minuto dá ~1.440 linhas por dia, ~45 mil em 30 dias: alguns MB.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "memory" / "monitor.db"

_lock = threading.Lock()
_con: sqlite3.Connection | None = None
_caminho_aberto: Path | None = None


def _conexao() -> sqlite3.Connection:
    global _con, _caminho_aberto
    if _con is None or _caminho_aberto != ARQUIVO:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        _con = sqlite3.connect(str(ARQUIVO), check_same_thread=False, timeout=5)
        _caminho_aberto = ARQUIVO
        _con.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS amostras (
                ts INTEGER PRIMARY KEY, cpu REAL, ram REAL, gpu REAL, temp REAL,
                down REAL, up REAL, leitura REAL, escrita REAL,
                disco_livre_pct REAL, ping REAL, internet INTEGER);
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, tipo TEXT,
                mensagem TEXT);
            CREATE INDEX IF NOT EXISTS ix_eventos_ts ON eventos(ts);
            -- Fork PT-BR 1.4: linha do tempo do dia (janela em foco)
            CREATE TABLE IF NOT EXISTS foco (
                id INTEGER PRIMARY KEY AUTOINCREMENT, inicio REAL, fim REAL,
                processo TEXT, app TEXT, titulo TEXT, atividade TEXT, projeto TEXT);
            CREATE INDEX IF NOT EXISTS ix_foco_inicio ON foco(inicio);
        """)
    return _con


def gravar_amostra(a: dict, ts: int | None = None) -> None:
    ts = int(ts or time.time())
    campos = ("cpu", "ram", "gpu", "temp", "down", "up", "leitura", "escrita",
              "disco_livre_pct", "ping", "internet")
    with _lock:
        c = _conexao()
        c.execute(f"INSERT OR REPLACE INTO amostras (ts, {', '.join(campos)}) "
                  f"VALUES (?, {', '.join('?' * len(campos))})",
                  (ts, *[a.get(k) for k in campos]))
        c.commit()


def gravar_evento(tipo: str, mensagem: str, ts: int | None = None) -> None:
    with _lock:
        c = _conexao()
        c.execute("INSERT INTO eventos (ts, tipo, mensagem) VALUES (?, ?, ?)",
                  (int(ts or time.time()), tipo, mensagem))
        c.commit()


def amostras(desde: float, ate: float | None = None) -> list[dict]:
    with _lock:
        c = _conexao()
        c.row_factory = sqlite3.Row
        linhas = c.execute("SELECT * FROM amostras WHERE ts >= ? AND ts <= ? ORDER BY ts",
                           (int(desde), int(ate or time.time() + 60))).fetchall()
        c.row_factory = None
    return [dict(r) for r in linhas]


def eventos(desde: float, limite: int = 200) -> list[dict]:
    with _lock:
        c = _conexao()
        c.row_factory = sqlite3.Row
        linhas = c.execute("SELECT * FROM eventos WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                           (int(desde), limite)).fetchall()
        c.row_factory = None
    return [dict(r) for r in linhas]


def limpar(retencao_dias: float) -> int:
    limite = int(time.time() - max(1.0, retencao_dias) * 86400)
    with _lock:
        c = _conexao()
        n = c.execute("DELETE FROM amostras WHERE ts < ?", (limite,)).rowcount
        n += c.execute("DELETE FROM eventos WHERE ts < ?", (limite,)).rowcount
        n += c.execute("DELETE FROM foco WHERE fim < ?", (limite,)).rowcount
        c.commit()
    return n


# ── Fork PT-BR 1.4: janela em foco (linha do tempo do dia) ─────────────────────
def gravar_foco(inicio: float, fim: float, processo: str, app: str, titulo: str,
                atividade: str, projeto: str = "") -> None:
    with _lock:
        c = _conexao()
        c.execute("INSERT INTO foco (inicio, fim, processo, app, titulo, atividade, projeto) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (float(inicio), float(fim), processo, app, (titulo or "")[:200], atividade, projeto))
        c.commit()


def focos(desde: float, ate: float | None = None) -> list[dict]:
    """Intervalos que tocam o período [desde, ate], já cortados nas pontas."""
    ate = ate or time.time() + 60
    with _lock:
        c = _conexao()
        c.row_factory = sqlite3.Row
        linhas = [dict(r) for r in c.execute(
            "SELECT * FROM foco WHERE fim > ? AND inicio < ? ORDER BY inicio", (desde, ate)).fetchall()]
        c.row_factory = None
    for l in linhas:
        l["inicio"], l["fim"] = max(l["inicio"], desde), min(l["fim"], ate)
    return linhas


def resumo(desde: float, ate: float | None = None) -> dict:
    """Médias, máximos e totais de um período, a partir das amostras."""
    linhas = amostras(desde, ate)
    evs = [e for e in eventos(desde, 1000) if e["ts"] <= (ate or time.time() + 60)]
    if not linhas:
        return {"amostras": 0, "eventos": evs}

    def col(k):
        return [r[k] for r in linhas if r.get(k) is not None]

    def media(k):
        v = col(k)
        return sum(v) / len(v) if v else None

    def maximo(k):
        v = col(k)
        return max(v) if v else None

    # Cada amostra representa um minuto: bytes/s × 60 = bytes do minuto.
    total_down = sum(v * 60 for v in col("down"))
    total_up = sum(v * 60 for v in col("up"))
    sem_internet = sum(1 for r in linhas if r.get("internet") == 0)
    return {
        "amostras": len(linhas),
        "minutos_ligado": len(linhas),
        "cpu_media": media("cpu"), "cpu_max": maximo("cpu"),
        "ram_media": media("ram"), "ram_max": maximo("ram"),
        "gpu_media": media("gpu"), "gpu_max": maximo("gpu"),
        "temp_media": media("temp"), "temp_max": maximo("temp"),
        "ping_medio": media("ping"), "ping_max": maximo("ping"),
        "disco_livre_min": min(col("disco_livre_pct")) if col("disco_livre_pct") else None,
        "total_down": total_down, "total_up": total_up,
        "minutos_sem_internet": sem_internet,
        "eventos": evs,
    }
