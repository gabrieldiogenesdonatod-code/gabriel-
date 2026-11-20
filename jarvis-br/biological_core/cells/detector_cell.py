"""
Células detectoras — identificação de anomalias: transformam sintomas em incidentes.

Para cada sintoma:
    1. classifica (regras de alta certeza; o que elas não sabem, pergunta ao classificador do cérebro);
    2. procura o anticorpo (esse erro já apareceu? quantas vezes? o que resolveu?);
    3. calcula a gravidade e separa falha normal de possível ameaça;
    4. decide se vira INCIDENTE: grave, ameaça, disjuntor que abriu, ou 3 vezes em 10 minutos.
       Uma falha solta de internet não vira incidente — vira só memória.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from biological_core.immune_system.threat_detector import eh_ameaca, gravidade
from biological_core.nervous_system.communication import Orgao
from biological_core.nervous_system.event_bus import ALTA, NORMAL

SEMPRE_INCIDENTE = {"carregamento", "dados", "integridade", "boot", "config", "orgao"}
JANELA_S = 600


class Detectora(Orgao):
    nome = "detectora"

    def __init__(self, bus, org):
        super().__init__(bus)
        self.org = org
        self._janelas: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.sintomas = 0
        self.incidentes = 0
        self.ouvir("sintoma.falha", self._sintoma)

    def _sintoma(self, ev) -> None:
        s = ev.dados
        self.sintomas += 1
        cat = s.get("categoria")
        if not cat:
            r = self.pedir_ajuda("classificar", {"texto": f"{s.get('tipo', '')} {s.get('mensagem', '')}"})
            cat, conf = (r[0][0], r[0][1]) if r else ("desconhecida", 0.0)
            s["categoria"], s["confianca"] = cat, conf
        memoria = self.org.memoria
        anticorpo = memoria.registrar_anticorpo(s["impressao"], cat, s["modulo"])
        grav = s.get("gravidade") or gravidade(cat, s["modulo"], anticorpo["vezes"] if anticorpo else 1)
        agora = time.time()
        j = self._janelas[s["impressao"]]
        for _ in range(int(s.get("repeticoes", 1))):
            j.append(agora)
        recentes = sum(1 for t in j if agora - t <= JANELA_S)
        ameaca = eh_ameaca(s)
        vira = (grav in ("alta", "critica") or ameaca or s.get("disjuntor_abriu") or recentes >= 3
                or s.get("origem") in SEMPRE_INCIDENTE or (s.get("origem") == "anomalia" and s.get("anomalia") == "vazamento_de_memoria"))
        if not vira:
            return
        detalhes = {k: s[k] for k in ("traceback", "params", "arquivos", "versao_boa", "anomalia", "confianca", "interno", "origem")
                    if s.get(k) not in (None, "", [])}
        iid, novo = memoria.abrir_incidente(s["modulo"], s.get("acao", "*"), cat, grav, s["impressao"], s.get("mensagem", ""),
                                            s.get("arquivo", ""), s.get("linha", 0), detalhes)
        if ameaca:
            memoria.registrar_ameaca(s.get("tipo", "ameaca"), s["modulo"], s.get("mensagem", ""), grav, False)
            self.enviar("imune.ameaca", {"incidente": iid, "modulo": s["modulo"], "mensagem": s.get("mensagem", ""),
                                         "gravidade": grav}, ALTA)
        inc = memoria.incidente(iid) or {}
        inc.update(tipo=s.get("tipo", ""), conhecido=(anticorpo or {}).get("tratamento_bom"), interno=s.get("interno", False),
                   anomalia=s.get("anomalia"))
        if novo:
            self.incidentes += 1
        self.enviar("incidente.novo" if novo else "incidente.recorrencia", inc, ALTA if novo else NORMAL)

    def estado(self) -> dict:
        e = super().estado()
        e.update(sintomas=self.sintomas, incidentes=self.incidentes)
        return e
