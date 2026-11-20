"""
Monitor de saúde: transforma sinais vitais e o estado dos órgãos numa nota de 0 a 100 e em cores.

    azul      funcionamento normal (nota 80+)
    amarelo   atenção (50–79)
    vermelho  falha ou ameaça (abaixo de 50, ou órgão vital parado)
    verde     recuperação concluída nos últimos 5 minutos (e nada vermelho)

A nota sempre vem com os motivos ("RAM do PC em 93%: -15"), para dar para conferir por que ela caiu.
"""

from __future__ import annotations

import time
from collections import deque

PESO_ORGAO = {"cerebro": 20, "imune": 20, "circulacao": 12, "nervos": 12, "dna": 10, "regeneracao": 8, "celulas": 6}


def cor_da_nota(nota: float) -> str:
    return "azul" if nota >= 80 else ("amarelo" if nota >= 50 else "vermelho")


class MonitorSaude:
    def __init__(self, recuperacao_s: float = 300):
        self.historico: deque = deque(maxlen=360)
        self.ultima_recuperacao = 0.0
        self.recuperacao_s = recuperacao_s
        self.ultimo: dict = {"nota": 100, "cor": "azul", "problemas": [], "orgaos": {}}

    def registrar_recuperacao(self, ts: float | None = None) -> None:
        self.ultima_recuperacao = ts or time.time()

    def avaliar(self, vitais: dict, orgaos: dict, travados: list, incidentes: list, isolados: int, agora: float | None = None) -> dict:
        agora = agora or time.time()
        nota, problemas = 100.0, []

        def tirar(pontos: float, motivo: str) -> None:
            nonlocal nota
            nota -= pontos
            problemas.append((round(pontos), motivo))

        cores = {}
        for nome, o in orgaos.items():
            if o.get("cor") == "vermelho":
                tirar(PESO_ORGAO.get(nome, 5), f"{o.get('titulo', nome)} com falha: {o.get('detalhe', '')}")
            elif o.get("cor") == "amarelo":
                tirar(PESO_ORGAO.get(nome, 5) / 3, f"{o.get('titulo', nome)} pede atenção: {o.get('detalhe', '')}")
            cores[nome] = o.get("cor", "azul")
        ram = vitais.get("ram_pc")
        if ram is not None and ram >= 90:
            tirar(15, f"RAM do PC em {ram:.0f}%")
        elif ram is not None and ram >= 80:
            tirar(6, f"RAM do PC em {ram:.0f}%")
        rss = vitais.get("ram_jarvis_mb")
        if rss is not None and rss >= 2000:
            tirar(10, f"o JARVIS está usando {rss:.0f} MB")
        disco = vitais.get("disco_livre_pct")
        if disco is not None and disco < 5:
            tirar(15, f"só {disco:.0f}% de disco livre")
        elif disco is not None and disco < 10:
            tirar(6, f"só {disco:.0f}% de disco livre")
        temp = vitais.get("temp_cpu")
        if temp is not None and temp >= 90:
            tirar(15, f"CPU a {temp:.0f} °C")
        elif temp is not None and temp >= 80:
            tirar(6, f"CPU a {temp:.0f} °C")
        cpu = vitais.get("cpu_jarvis")
        if cpu is not None and cpu >= 80:
            tirar(8, f"o JARVIS usando {cpu:.0f}% de CPU")
        if travados:
            tirar(min(20, 5 * len(travados)), f"{len(travados)} parte(s) travada(s): {', '.join(t[0] for t in travados[:3])}")
        pesos = {"critica": 20, "alta": 10, "media": 4, "baixa": 1, "info": 0}
        soma = sum(pesos.get(i.get("gravidade"), 1) for i in incidentes)
        if soma:
            tirar(min(30, soma), f"{len(incidentes)} problema(s) em aberto")
        if isolados:
            tirar(min(10, 2 * isolados), f"{isolados} parte(s) isolada(s)")
        nota = max(0.0, min(100.0, nota))
        cor = cor_da_nota(nota)
        if "vermelho" in cores.values() and cores.get("cerebro") == "vermelho":
            cor = "vermelho"
        if cor != "vermelho" and agora - self.ultima_recuperacao <= self.recuperacao_s:
            cor = "verde"
        self.historico.append((agora, round(nota)))
        self.ultimo = {"nota": round(nota), "cor": cor, "problemas": [m for _p, m in sorted(problemas, reverse=True)][:8],
                       "orgaos": cores, "ts": agora}
        return self.ultimo

    def tendencia(self, janela: int = 30) -> str:
        pts = [n for _t, n in list(self.historico)[-janela:]]
        if len(pts) < 6:
            return "estável"
        metade = len(pts) // 2
        a, b = sum(pts[:metade]) / metade, sum(pts[metade:]) / (len(pts) - metade)
        return "melhorando" if b - a >= 5 else ("piorando" if a - b >= 5 else "estável")
