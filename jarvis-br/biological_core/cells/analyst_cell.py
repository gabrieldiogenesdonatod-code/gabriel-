"""
Células analistas — investigação de falhas.

Quando o cérebro pede ajuda ("ajuda.investigar"), a analista junta as EVIDÊNCIAS:
    • quantas ferramentas falharam por rede nos últimos 5 minutos (internet caiu ou só um serviço?)
    • o teste de conexão mais recente
    • se o arquivo do plugin mudou recentemente (pelo DNA) e há quantas horas
    • memória e disco do PC, quantas tarefas estão rodando, travamentos em outros módulos
    • se a mesma ferramenta funcionou há pouco com OUTROS parâmetros (então o problema é o pedido)
    • as causas que já foram confirmadas neste módulo no passado
e passa tudo pelo motor de hipóteses, devolvendo as causas prováveis com as evidências.
"""

from __future__ import annotations

import time

from biological_core.brain.reasoning import MotorHipoteses
from biological_core.nervous_system.communication import Orgao


class Analista(Orgao):
    nome = "analista"

    def __init__(self, bus, org):
        super().__init__(bus)
        self.org = org
        self.motor = MotorHipoteses()
        self.investigacoes = 0
        self.oferecer_ajuda("investigar", self.investigar)

    def contexto(self, inc: dict) -> dict:
        org = self.org
        agora = time.time()
        recentes = list(org.sentinela.recentes)
        rede = {m for ts, m, c, _i, _o in recentes if agora - ts <= 300 and c in ("rede", "timeout")}
        if inc.get("categoria") in ("rede", "timeout"):
            rede.add(inc.get("modulo"))
        timeouts = {m for ts, m, c, _i, _o in recentes if agora - ts <= 600 and c == "timeout"}
        vit = org.coracao.vitais if org.coracao else {}
        ctx = {"categoria": inc.get("categoria"), "modulo": inc.get("modulo"), "acao": inc.get("acao"),
               "tipo": inc.get("anomalia") or inc.get("tipo"), "interno": inc.get("interno"),
               "modulos_com_rede_5min": len(rede), "conectividade": self._conexao(inc),
               "http_5xx": any(c in str(inc.get("mensagem", "")) for c in (" 500", " 502", " 503", " 504")),
               "ram_pc": vit.get("ram_pc"), "disco_livre_pct": vit.get("disco_livre_pct"),
               "vigia_ocupadas": len(org.sentinela.em_andamento()), "timeouts_modulos_10min": len(timeouts),
               "causas_anteriores": dict(org.memoria.causas_por_modulo(inc.get("modulo") or ""))}
        rel = f"plugins/{inc.get('modulo')}.py"
        if rel in ((org.verificador.ultimo or {}).get("modificados") or []):
            try:
                ctx["arquivo_modificado_h"] = (agora - (org.raiz / rel).stat().st_mtime) / 3600
            except OSError:
                pass
        ctx["falha_so_com_params"] = self._so_com_params(inc)
        return ctx

    def _conexao(self, inc: dict) -> bool | None:
        """Resultado recente do teste de internet; para erro de rede sem teste recente, testa agora (1,5 s no máximo)."""
        r = self.org.conectividade_recente()
        if r is None and inc.get("categoria") in ("rede", "timeout", "externo"):
            r = self.org.testar_rede_agora()
        return r

    def _so_com_params(self, inc: dict) -> bool:
        """A mesma ferramenta funcionou na última hora com outros parâmetros?"""
        if inc.get("categoria") not in ("bug", "desconhecida", "externo"):
            return False
        try:
            from core import registro_uso
            ok = [c for c in registro_uso.chamadas(time.time() - 3600, ferramenta=inc.get("modulo")) if c.get("ok")]
            falhos = str((inc.get("detalhes") or {}).get("params", "")) if isinstance(inc.get("detalhes"), dict) else ""
            return bool(ok) and any(str(c.get("params")) != falhos for c in ok)
        except Exception:
            return False

    def investigar(self, inc: dict) -> list[dict]:
        self.investigacoes += 1
        return self.motor.avaliar(self.contexto(inc))
