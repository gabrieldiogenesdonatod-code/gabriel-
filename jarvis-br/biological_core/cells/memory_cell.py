"""
Células de memória — armazenamento de incidentes e do que o organismo aprende.

Guardam no lugar certo o que circula pelo sistema nervoso:
    • o relatório do protocolo de regeneração vai para os detalhes do incidente;
    • cada incidente resolvido entra no boletim de saúde do dia;
    • descobertas das outras células (lentidão, anomalias leves) viram um diário curto
      (memory/biological/diario.json, últimos 200), que o painel e o boletim usam.
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path

from biological_core.config import gravar_json, ler_json
from biological_core.nervous_system.communication import Orgao


class CelulaMemoria(Orgao):
    nome = "memoria"

    def __init__(self, bus, org, pasta: Path):
        super().__init__(bus)
        self.org = org
        self.arquivo = Path(pasta) / "diario.json"
        self.diario: deque = deque(ler_json(self.arquivo, []) or [], maxlen=200)
        self._sujo = False
        self.ouvir("reparo.resultado", self._reparo)
        self.ouvir("incidente.resolvido", self._resolvido)
        self.ouvir("descoberta.*", self._descoberta)
        self.ouvir("imune.bloqueio", self._bloqueio)

    def anotar(self, tipo: str, texto: str) -> None:
        self.diario.append({"ts": time.time(), "tipo": tipo, "texto": texto[:240]})
        self._sujo = True

    def _reparo(self, ev) -> None:
        r = ev.dados
        try:
            inc = self.org.memoria.incidente(int(r["incidente"]["id"])) or {}
            det = inc.get("detalhes") or {}
            det["protocolo"] = {"tratamento": r["tratamento"], "estado": r["estado"], "passos": r.get("passos", [])[-10:],
                                "ts": time.time()}
            self.org.memoria.atualizar(int(r["incidente"]["id"]), detalhes=det)
        except Exception as e:
            self.relatar_erro(e, "guardar protocolo")
        self.anotar("reparo", f"{r['incidente'].get('modulo')}: {r['tratamento']} → {r['estado']} ({str(r.get('mensagem', ''))[:120]})")

    def _resolvido(self, ev) -> None:
        d = ev.dados
        self.anotar("cura", f"{d.get('modulo')} curado ({d.get('como', '')})" + (f" com {d['tratamento']}" if d.get("tratamento") else ""))

    def _descoberta(self, ev) -> None:
        d = ev.dados
        if ev.topico == "descoberta.lentidao":
            self.anotar("lentidao", f"{d.get('modulo')} terminou atrasado ({d.get('segundos')} s)")
        else:
            self.anotar(ev.topico.split(".", 1)[1], str(d)[:200])

    def _bloqueio(self, ev) -> None:
        d = ev.dados
        self.anotar("defesa", f"bloqueado em {d.get('modulo')}: {d.get('motivo')}")

    def salvar(self) -> None:
        if self._sujo:
            try:
                gravar_json(self.arquivo, list(self.diario))
                self._sujo = False
            except Exception:
                pass

    def hoje(self) -> list[dict]:
        inicio = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        return [d for d in self.diario if d["ts"] >= inicio]
