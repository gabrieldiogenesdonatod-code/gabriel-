"""
Sistema nervoso digital: a rede de eventos entre os órgãos.

Cada evento tem identificação, tópico, origem, prioridade, horário e dados, e fica no histórico.
Os eventos importantes (prioridade crítica ou alta) também vão para memory/biological/nervos.jsonl.

    bus.assinar("incidente.*", funcao)              # recebe tudo que começa com "incidente."
    bus.publicar("incidente.novo", {...}, origem="detectora", prioridade=ALTA)
    respostas = bus.solicitar("ajuda.investigar", {...})   # pede ajuda e junta as respostas

Um assinante que dá erro 5 vezes seguidas é desligado ("nervo inflamado") e isso vira evento:
um órgão com defeito nunca derruba a comunicação dos outros.
"""

from __future__ import annotations

import fnmatch
import itertools
import json
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CRITICA, ALTA, NORMAL, BAIXA = 0, 1, 2, 3
NOMES_PRIORIDADE = {CRITICA: "crítica", ALTA: "alta", NORMAL: "normal", BAIXA: "baixa"}
_seq = itertools.count(1)


@dataclass
class Evento:
    topico: str
    dados: dict = field(default_factory=dict)
    origem: str = "?"
    prioridade: int = NORMAL
    chave: str | None = None            # eventos com a mesma chave esperando na fila viram um só
    id: str = ""
    ts: float = 0.0

    def __post_init__(self):
        self.id = self.id or f"e{next(_seq):07d}"
        self.ts = self.ts or time.time()

    def resumo(self) -> dict:
        return {"id": self.id, "topico": self.topico, "origem": self.origem, "prioridade": self.prioridade,
                "ts": round(self.ts, 3), "dados": {k: v for k, v in self.dados.items() if _simples(v)}}


def _simples(v) -> bool:
    return isinstance(v, (str, int, float, bool, type(None))) or (isinstance(v, (list, tuple)) and len(v) <= 20)


class Barramento:
    def __init__(self, historico: int = 500, log: Path | None = None, max_erros: int = 5, log_max_bytes: int = 1_000_000):
        self._assin: list[dict] = []
        self._resp: dict[str, list[tuple[str, Callable]]] = {}
        self._hist: deque[Evento] = deque(maxlen=historico)
        self._ts: deque[float] = deque(maxlen=6000)
        self._lock = threading.RLock()
        self._log_lock = threading.Lock()
        self.por_topico: Counter = Counter()
        self.total = 0
        self.falhas_entrega = 0
        self.log = Path(log) if log else None
        self.log_max_bytes = log_max_bytes
        self.max_erros = max_erros
        self.circulacao = None              # data_flow.Circulacao liga a entrega assíncrona

    # ── assinaturas ───────────────────────────────────────────────────────────
    def assinar(self, padrao: str, fn: Callable[[Evento], None], nome: str | None = None) -> None:
        with self._lock:
            self._assin.append({"padrao": padrao, "fn": fn, "nome": nome or getattr(fn, "__name__", "?"),
                                "erros": 0, "ativo": True, "entregues": 0, "ultimo_erro": ""})

    def cancelar(self, nome: str) -> int:
        with self._lock:
            antes = len(self._assin)
            self._assin = [a for a in self._assin if a["nome"] != nome]
            return antes - len(self._assin)

    def responder(self, tipo: str, fn: Callable[[dict], object], nome: str = "?") -> None:
        with self._lock:
            self._resp.setdefault(tipo, []).append((nome, fn))

    def reanimar(self, nome: str) -> bool:
        """Religa um assinante desligado por erros (o coração tenta de vez em quando)."""
        with self._lock:
            achou = False
            for a in self._assin:
                if a["nome"] == nome and not a["ativo"]:
                    a["ativo"], a["erros"], achou = True, 0, True
            return achou

    # ── envio ─────────────────────────────────────────────────────────────────
    def publicar(self, topico: str, dados: dict | None = None, origem: str = "?", prioridade: int = NORMAL,
                 chave: str | None = None, sincrono: bool = False) -> Evento:
        ev = Evento(topico, dict(dados or {}), origem, prioridade, chave)
        with self._lock:
            self._hist.append(ev)
            self._ts.append(ev.ts)
            self.por_topico[topico] += 1
            self.total += 1
        if prioridade <= ALTA and self.log is not None:
            self._gravar(ev)
        circ = self.circulacao
        if circ is not None and circ.ativa and not sincrono:
            circ.enfileirar(ev)
        else:
            self.entregar(ev)
        return ev

    def entregar(self, ev: Evento) -> int:
        with self._lock:
            alvos = [a for a in self._assin if a["ativo"] and fnmatch.fnmatchcase(ev.topico, a["padrao"])]
        for a in alvos:
            try:
                a["fn"](ev)
                a["erros"] = 0
                a["entregues"] += 1
            except Exception as e:
                self.falhas_entrega += 1
                a["erros"] += 1
                a["ultimo_erro"] = f"{type(e).__name__}: {e}"[:200]
                if a["erros"] >= self.max_erros:
                    a["ativo"] = False
                    if not ev.topico.startswith("nervo."):
                        self.publicar("nervo.inflamado", {"assinante": a["nome"], "erro": a["ultimo_erro"]},
                                      "sistema_nervoso", ALTA, sincrono=True)
        return len(alvos)

    def solicitar(self, tipo: str, dados: dict | None = None, origem: str = "?") -> list:
        """Pede ajuda a quem se ofereceu para 'tipo' e devolve as respostas (na hora, sem fila)."""
        with self._lock:
            ajudantes = list(self._resp.get(tipo, []))
        respostas = []
        for _nome, fn in ajudantes:
            try:
                r = fn(dict(dados or {}))
                if r is not None:
                    respostas.append(r)
            except Exception:
                self.falhas_entrega += 1
        return respostas

    # ── leitura ───────────────────────────────────────────────────────────────
    def frequencia(self, janela_s: float = 60.0) -> float:
        """Eventos por minuto na última janela: os "batimentos" do sistema nervoso."""
        limite = time.time() - janela_s
        with self._lock:
            n = sum(1 for t in reversed(self._ts) if t >= limite) if self._ts else 0
        return n * 60.0 / janela_s

    def historico(self, padrao: str = "*", n: int = 50) -> list[Evento]:
        with self._lock:
            evs = [e for e in self._hist if fnmatch.fnmatchcase(e.topico, padrao)]
        return evs[-n:]

    def assinantes(self) -> list[dict]:
        with self._lock:
            return [{k: a[k] for k in ("nome", "padrao", "ativo", "erros", "entregues", "ultimo_erro")} for a in self._assin]

    def estado(self) -> dict:
        ass = self.assinantes()
        return {"eventos": self.total, "por_minuto": round(self.frequencia(), 1), "assinantes": len(ass),
                "inflamados": [a["nome"] for a in ass if not a["ativo"]], "falhas_entrega": self.falhas_entrega,
                "topicos": self.por_topico.most_common(6)}

    # ── registro em disco (só o importante) ───────────────────────────────────
    def _gravar(self, ev: Evento) -> None:
        try:
            with self._log_lock:
                self.log.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log, "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev.resumo(), ensure_ascii=False, default=str) + "\n")
                if self.log.stat().st_size > self.log_max_bytes:
                    self._encolher()
        except Exception:
            pass

    def _encolher(self) -> None:
        linhas = self.log.read_text(encoding="utf-8", errors="replace").splitlines()
        tmp = self.log.with_suffix(".tmp")
        tmp.write_text("\n".join(linhas[len(linhas) // 2:]) + "\n", encoding="utf-8")
        tmp.replace(self.log)

    def ler_log(self, n: int = 100) -> list[dict]:
        try:
            linhas = self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
            return [json.loads(l) for l in linhas if l.strip()]
        except Exception:
            return []
