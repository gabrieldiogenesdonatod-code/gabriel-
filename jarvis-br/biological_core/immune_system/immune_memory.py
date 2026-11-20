"""
Camada 6 — memória imunológica (memory/biological/imunidade.db, SQLite local).

    incidentes   cada problema: módulo, categoria, gravidade, impressão digital, ocorrências,
                 estado (aberto → tratando → resolvido / isolado / aguardando_humano), causa e tratamento
    anticorpos   cada erro já visto (pela impressão digital) e o placar de cada tratamento nele:
                 o que funcionou vira o "anticorpo"; o que falhou 2 vezes não é tentado de novo
    ameacas      o que a defesa bloqueou ou a integridade acusou
    decisoes     o que o cérebro decidiu, por quê (hipóteses) e o resultado

A impressão digital ignora números, caminhos e textos variáveis da mensagem: o mesmo defeito
com outro arquivo ou outro horário é reconhecido como o mesmo.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path

ESTADOS_ABERTOS = ("aberto", "tratando", "isolado", "observando", "aguardando_humano", "aguardando_autorizacao")

_TABELAS = """
CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY, ts_inicio REAL, ts_ultimo REAL, ts_fim REAL,
    modulo TEXT, acao TEXT, categoria TEXT, gravidade TEXT, impressao TEXT, mensagem TEXT, arquivo TEXT,
    linha INTEGER, ocorrencias INTEGER DEFAULT 1, estado TEXT DEFAULT 'aberto', causa TEXT, tratamento TEXT,
    resultado TEXT, humano INTEGER DEFAULT 0, detalhes TEXT);
CREATE INDEX IF NOT EXISTS ix_inc_imp ON incidentes(impressao, estado);
CREATE TABLE IF NOT EXISTS anticorpos (impressao TEXT PRIMARY KEY, categoria TEXT, modulo TEXT, primeira REAL,
    ultima REAL, vezes INTEGER DEFAULT 0, dias TEXT DEFAULT '[]', horas TEXT DEFAULT '[]', placar TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS ameacas (id INTEGER PRIMARY KEY, ts REAL, tipo TEXT, origem TEXT, detalhe TEXT,
    gravidade TEXT, bloqueado INTEGER);
CREATE TABLE IF NOT EXISTS decisoes (id INTEGER PRIMARY KEY, ts REAL, incidente INTEGER, tratamento TEXT,
    explicacao TEXT, hipoteses TEXT, resultado TEXT);
"""


def normalizar_mensagem(msg: str) -> str:
    m = str(msg or "").lower()
    m = re.sub(r"[a-z]:\\[^\s'\"]+|/[\w.\-/]+", "<caminho>", m)
    m = re.sub(r"'[^']{0,80}'|\"[^\"]{0,80}\"", "'…'", m)
    m = re.sub(r"0x[0-9a-f]+", "<hex>", m)
    m = re.sub(r"\d+", "#", m)
    return " ".join(m.split())[:160]


def impressao_digital(modulo: str, acao: str, tipo: str, mensagem: str, arquivo: str = "", linha: int = 0) -> str:
    base = f"{modulo}|{acao or '*'}|{tipo}|{normalizar_mensagem(mensagem)}|{arquivo}:{linha}"
    return hashlib.sha1(base.encode("utf-8", "replace")).hexdigest()[:16]


class MemoriaImune:
    def __init__(self, arquivo: Path):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.c = sqlite3.connect(str(self.arquivo), check_same_thread=False, timeout=5)
        self.c.row_factory = sqlite3.Row
        try:
            self.c.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        self.c.executescript(_TABELAS)
        self.c.commit()

    def _q(self, sql: str, args=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.c.execute(sql, args).fetchall()]

    def _x(self, sql: str, args=()) -> int:
        with self._lock:
            cur = self.c.execute(sql, args)
            self.c.commit()
            return cur.lastrowid

    # ── incidentes ────────────────────────────────────────────────────────────
    def abrir_incidente(self, modulo: str, acao: str, categoria: str, gravidade: str, impressao: str,
                        mensagem: str = "", arquivo: str = "", linha: int = 0, detalhes: dict | None = None) -> tuple[int, bool]:
        """(id, novo). Se a mesma impressão já tem incidente aberto, só soma a ocorrência."""
        aberto = self._q(f"SELECT id FROM incidentes WHERE impressao=? AND estado IN ({','.join('?' * len(ESTADOS_ABERTOS))}) "
                         "ORDER BY id DESC LIMIT 1", (impressao, *ESTADOS_ABERTOS))
        agora = time.time()
        if aberto:
            self._x("UPDATE incidentes SET ocorrencias=ocorrencias+1, ts_ultimo=? WHERE id=?", (agora, aberto[0]["id"]))
            return aberto[0]["id"], False
        iid = self._x("INSERT INTO incidentes (ts_inicio, ts_ultimo, modulo, acao, categoria, gravidade, impressao, "
                      "mensagem, arquivo, linha, detalhes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (agora, agora, modulo, acao or "*", categoria, gravidade, impressao, str(mensagem)[:500],
                       arquivo or "", int(linha or 0), json.dumps(detalhes or {}, ensure_ascii=False, default=str)[:4000]))
        return iid, True

    def atualizar(self, iid: int, **campos) -> None:
        if not campos:
            return
        if "detalhes" in campos and not isinstance(campos["detalhes"], str):
            campos["detalhes"] = json.dumps(campos["detalhes"], ensure_ascii=False, default=str)[:4000]
        sets = ", ".join(f"{k}=?" for k in campos)
        self._x(f"UPDATE incidentes SET {sets} WHERE id=?", (*campos.values(), iid))

    def fechar(self, iid: int, resultado: str, causa: str | None = None, tratamento: str | None = None,
               estado: str = "resolvido", humano: bool = False) -> None:
        self.atualizar(iid, ts_fim=time.time(), resultado=str(resultado)[:300], estado=estado, humano=int(humano),
                       **({"causa": causa} if causa else {}), **({"tratamento": tratamento} if tratamento else {}))

    def incidente(self, iid: int) -> dict | None:
        r = self._q("SELECT * FROM incidentes WHERE id=?", (iid,))
        if not r:
            return None
        d = r[0]
        try:
            d["detalhes"] = json.loads(d.get("detalhes") or "{}")
        except ValueError:
            d["detalhes"] = {}
        return d

    def incidentes(self, estado: str | None = None, desde: float = 0, limite: int = 50) -> list[dict]:
        if estado == "abertos":
            return self._q(f"SELECT * FROM incidentes WHERE estado IN ({','.join('?' * len(ESTADOS_ABERTOS))}) "
                           "ORDER BY id DESC LIMIT ?", (*ESTADOS_ABERTOS, limite))
        if estado:
            return self._q("SELECT * FROM incidentes WHERE estado=? AND ts_inicio>=? ORDER BY id DESC LIMIT ?", (estado, desde, limite))
        return self._q("SELECT * FROM incidentes WHERE ts_inicio>=? ORDER BY id DESC LIMIT ?", (desde, limite))

    def abertos(self) -> list[dict]:
        return self.incidentes("abertos", limite=200)

    # ── anticorpos ────────────────────────────────────────────────────────────
    def registrar_anticorpo(self, impressao: str, categoria: str, modulo: str) -> dict:
        agora = time.time()
        dia, hora = time.strftime("%Y-%m-%d"), time.localtime().tm_hour
        a = self.reconhecer(impressao)
        if a is None:
            self._x("INSERT INTO anticorpos (impressao, categoria, modulo, primeira, ultima, vezes, dias, horas) "
                    "VALUES (?,?,?,?,?,1,?,?)", (impressao, categoria, modulo, agora, agora, json.dumps([dia]), json.dumps([hora])))
        else:
            dias = (a["dias"] + [dia])[-60:] if dia not in a["dias"] else a["dias"]
            horas = (a["horas"] + [hora])[-200:]
            self._x("UPDATE anticorpos SET ultima=?, vezes=vezes+1, dias=?, horas=?, categoria=? WHERE impressao=?",
                    (agora, json.dumps(dias), json.dumps(horas), categoria, impressao))
        return self.reconhecer(impressao)

    def reconhecer(self, impressao: str) -> dict | None:
        r = self._q("SELECT * FROM anticorpos WHERE impressao=?", (impressao,))
        if not r:
            return None
        a = r[0]
        for k in ("dias", "horas", "placar"):
            try:
                a[k] = json.loads(a.get(k) or ("{}" if k == "placar" else "[]"))
            except ValueError:
                a[k] = {} if k == "placar" else []
        bons = [(s / (s + f), s, t) for t, (s, f) in a["placar"].items() if s >= 1]
        a["tratamento_bom"] = max(bons)[2] if bons else None
        return a

    def registrar_tratamento(self, impressao: str, tratamento: str, sucesso: bool) -> None:
        a = self.reconhecer(impressao)
        if a is None:
            return
        s, f = a["placar"].get(tratamento, [0, 0])
        a["placar"][tratamento] = [s + int(sucesso), f + int(not sucesso)]
        self._x("UPDATE anticorpos SET placar=? WHERE impressao=?", (json.dumps(a["placar"]), impressao))

    def tratamentos_que_falharam(self, impressao: str, minimo: int = 2) -> set[str]:
        a = self.reconhecer(impressao)
        return {t for t, (s, f) in (a or {}).get("placar", {}).items() if f >= minimo and s == 0}

    def contar_anticorpos(self) -> int:
        return self._q("SELECT COUNT(*) AS n FROM anticorpos")[0]["n"]

    def anticorpos(self, limite: int = 30) -> list[dict]:
        return [self.reconhecer(r["impressao"]) for r in
                self._q("SELECT impressao FROM anticorpos ORDER BY ultima DESC LIMIT ?", (limite,))]

    # ── ameaças e decisões ────────────────────────────────────────────────────
    def registrar_ameaca(self, tipo: str, origem: str, detalhe: str, gravidade: str, bloqueado: bool) -> int:
        return self._x("INSERT INTO ameacas (ts, tipo, origem, detalhe, gravidade, bloqueado) VALUES (?,?,?,?,?,?)",
                       (time.time(), tipo, origem, str(detalhe)[:500], gravidade, int(bloqueado)))

    def ameacas(self, desde: float = 0, limite: int = 30) -> list[dict]:
        return self._q("SELECT * FROM ameacas WHERE ts>=? ORDER BY id DESC LIMIT ?", (desde, limite))

    def registrar_decisao(self, incidente: int, tratamento: str, explicacao: str, hipoteses: list) -> int:
        return self._x("INSERT INTO decisoes (ts, incidente, tratamento, explicacao, hipoteses) VALUES (?,?,?,?,?)",
                       (time.time(), incidente, tratamento, explicacao[:600], json.dumps(hipoteses, ensure_ascii=False, default=str)[:3000]))

    def resultado_decisao(self, did: int, resultado: str) -> None:
        self._x("UPDATE decisoes SET resultado=? WHERE id=?", (resultado, did))

    def decisoes(self, limite: int = 20, incidente: int | None = None) -> list[dict]:
        if incidente is not None:
            return self._q("SELECT * FROM decisoes WHERE incidente=? ORDER BY id DESC LIMIT ?", (incidente, limite))
        return self._q("SELECT * FROM decisoes ORDER BY id DESC LIMIT ?", (limite,))

    # ── aprendizado e estatística ─────────────────────────────────────────────
    def causas_por_modulo(self, modulo: str) -> Counter:
        return Counter(r["causa"] for r in self._q("SELECT causa FROM incidentes WHERE modulo=? AND causa IS NOT NULL", (modulo,)))

    def padroes(self, minimo_dias: int = 3) -> list[dict]:
        """Erros que voltam em dias diferentes, com a hora em que mais acontecem."""
        out = []
        for a in self.anticorpos(200):
            if a and len(a["dias"]) >= minimo_dias:
                hora, vezes = Counter(a["horas"]).most_common(1)[0] if a["horas"] else (None, 0)
                out.append({"impressao": a["impressao"], "modulo": a["modulo"], "categoria": a["categoria"],
                            "dias": len(a["dias"]), "hora_tipica": hora if vezes >= max(2, len(a["horas"]) // 2) else None})
        return sorted(out, key=lambda p: -p["dias"])

    def estatisticas(self, desde: float = 0) -> dict:
        incs = self._q("SELECT * FROM incidentes WHERE ts_inicio>=?", (desde,))
        resolvidos = [i for i in incs if i["estado"] == "resolvido" and i["ts_fim"]]
        auto = [i for i in resolvidos if not i["humano"]]
        tempos = sorted(i["ts_fim"] - i["ts_inicio"] for i in resolvidos)
        return {"total": len(incs), "resolvidos": len(resolvidos), "automaticos": len(auto),
                "abertos": sum(1 for i in incs if i["estado"] in ESTADOS_ABERTOS),
                "tempo_mediano_s": tempos[len(tempos) // 2] if tempos else None,
                "por_categoria": Counter(i["categoria"] for i in incs).most_common(8),
                "por_modulo": Counter(i["modulo"] for i in incs).most_common(8),
                "ameacas": len(self.ameacas(desde, 10000))}

    # ── manutenção ────────────────────────────────────────────────────────────
    def limpar_antigos(self, dias: int = 90) -> int:
        limite = time.time() - dias * 86400
        with self._lock:
            n = self.c.execute("DELETE FROM incidentes WHERE ts_fim IS NOT NULL AND ts_fim < ?", (limite,)).rowcount
            self.c.execute("DELETE FROM decisoes WHERE ts < ?", (limite,))
            self.c.execute("DELETE FROM ameacas WHERE ts < ?", (limite,))
            self.c.commit()
        return n

    def compactar(self) -> None:
        with self._lock:
            self.c.execute("VACUUM")

    def verificar(self) -> bool:
        with self._lock:
            return self.c.execute("PRAGMA quick_check").fetchone()[0] == "ok"

    def fechar_conexao(self) -> None:
        with self._lock:
            try:
                self.c.close()
            except Exception:
                pass
