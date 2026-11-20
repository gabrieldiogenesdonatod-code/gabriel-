"""
Sistema imunológico artificial — JARVIS IMMUNE SYSTEM. Junta as 8 camadas:

    1 detecção        threat_detector + anomaly_detector (+ células sentinelas)
    2 identificação   threat_detector (+ células detectoras e o classificador do cérebro)
    3 defesa          defense_engine (+ células defensoras no portão de cada ferramenta)
    4 isolamento      isolation_manager (quarentena parcial e disjuntores)
    5 reparação       regeneration/ (protocolo de 10 passos, células reparadoras)
    6 memória         immune_memory (incidentes, anticorpos, ameaças, decisões)
    7 prevenção       prevention_engine (pontos de restauração, checagem de dados, risco)
    8 evolução        evolution (relatório, vacinas, limites adaptativos)
"""

from __future__ import annotations

import time
from pathlib import Path

from biological_core.config import cfg
from biological_core.immune_system.anomaly_detector import DetectorAnomalias
from biological_core.immune_system.defense_engine import MotorDefesa
from biological_core.immune_system.evolution import Evolucao
from biological_core.immune_system.isolation_manager import GerenciadorIsolamento
from biological_core.immune_system.prevention_engine import Prevencao
from biological_core.immune_system.threat_detector import DetectorAmeacas
from biological_core.nervous_system.communication import Orgao


class SistemaImune(Orgao):
    nome = "imune"

    def __init__(self, bus, org, pasta: Path, raiz: Path, agora=time.time):
        super().__init__(bus)
        self.org = org
        self.detector = DetectorAmeacas(raiz)
        self.anomalias = DetectorAnomalias()
        self.defesa = MotorDefesa(int(cfg("bio_rajada_por_min", 30) or 30))
        self.isolamento = GerenciadorIsolamento(Path(pasta) / "quarentena.json", org.essenciais, agora)
        self.memoria = org.memoria
        self.prevencao = Prevencao(raiz, pasta)
        self.evolucao = Evolucao(pasta, org.memoria, self.isolamento, self.anomalias)

    def camadas(self) -> list[dict]:
        org = self.org
        ex = (self.evolucao.estado.get("exercicios") or [{}])[-1].get("resultados", [])
        pontos = self.prevencao.pontos()
        return [
            {"camada": 1, "nome": "Detecção", "ok": org.sentinela.vivo, "detalhe": f"{org.sentinela.chamadas} chamadas vigiadas"},
            {"camada": 2, "nome": "Identificação", "ok": org.detectora.vivo, "detalhe": f"{org.detectora.sintomas} sintomas, {org.detectora.incidentes} incidentes"},
            {"camada": 3, "nome": "Defesa", "ok": True, "detalhe": f"{org.defensora.bloqueadas} bloqueios"},
            {"camada": 4, "nome": "Isolamento", "ok": True, "detalhe": f"{len(self.isolamento.listar())} parte(s) isolada(s), {self.isolamento.curas} cura(s)"},
            {"camada": 5, "nome": "Reparação", "ok": org.reparadora.vivo, "detalhe": f"{org.reparadora.reparos} reparo(s)"},
            {"camada": 6, "nome": "Memória", "ok": True, "detalhe": f"{self.memoria.contar_anticorpos()} anticorpo(s)"},
            {"camada": 7, "nome": "Prevenção", "ok": bool(pontos), "detalhe": f"{len(pontos)} ponto(s) de restauração"},
            {"camada": 8, "nome": "Evolução", "ok": all(r["ok"] for r in ex) if ex else None,
             "detalhe": (f"{sum(r['ok'] for r in ex)}/{len(ex)} vacinas ok" if ex else "vacinas ainda não rodaram")},
        ]

    def nivel_protecao(self) -> int:
        nivel = 100
        for c in self.camadas():
            if c["ok"] is False:
                nivel -= 12
            elif c["ok"] is None:
                nivel -= 4
        if self.org.dna.situacao != "ok":
            nivel -= 20
        criticos = [i for i in self.memoria.abertos() if i["gravidade"] in ("alta", "critica")]
        nivel -= min(30, 10 * len(criticos))
        pontos = self.prevencao.pontos()
        if pontos and time.time() - pontos[-1]["ts"] > 3 * 86400:
            nivel -= 5
        if cfg("bio_desligado"):
            nivel = 0
        return max(0, min(100, nivel))
