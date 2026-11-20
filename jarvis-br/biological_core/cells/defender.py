"""
Células defensoras — aplicam as regras de proteção.

São elas que ficam no PORTÃO de cada ferramenta (core/plugin_loader.py chama portao() antes de
rodar qualquer plugin): primeiro a defesa (comando perigoso? laço? arquivo vital?), depois o
isolamento (parte em quarentena ou descansando?). Tudo em microssegundos — plugin saudável
fazendo coisa normal passa direto.

Também reagem às ameaças: avisam você na hora quando a gravidade é crítica e marcam como
"comprometido" o plugin cujo arquivo mudou e que passou a falhar (as ações perigosas dele
passam a pedir o seu sim).
"""

from __future__ import annotations

from biological_core.immune_system.defense_engine import BLOQUEAR, CONFIRMAR
from biological_core.nervous_system.communication import Orgao


class Defensora(Orgao):
    nome = "defensora"

    def __init__(self, bus, org):
        super().__init__(bus)
        self.org = org
        self.verificadas = 0
        self.bloqueadas = 0
        self.confirmacoes = 0
        self.ouvir("imune.ameaca", self._ameaca)

    def estado_modulo(self, nome: str) -> str:
        """'comprometido' = o arquivo do plugin está diferente do DNA E ele está falhando."""
        rel = f"plugins/{nome}.py"
        ultimo = self.org.verificador.ultimo or {}
        if rel in (ultimo.get("modificados") or []):
            d = self.org.imune.isolamento.disjuntores
            if any(k.split("|")[0] == nome and v.get("falhas", 0) >= 2 for k, v in d.items()):
                return "comprometido"
        return "saudavel"

    def portao(self, nome: str, params: dict | None) -> tuple | None:
        """None (pode seguir) · ("bloquear", mensagem) · ("confirmar", titulo, detalhe)."""
        self.verificadas += 1
        imune = self.org.imune
        v = imune.defesa.validar(nome, params or {}, self.estado_modulo(nome))
        if v.acao == BLOQUEAR:
            self.bloqueadas += 1
            if v.regra != "anti_laco":
                self.org.memoria.registrar_ameaca(v.regra, nome, v.motivo, "alta", True)
                self.enviar("imune.bloqueio", {"modulo": nome, "regra": v.regra, "motivo": v.motivo})
            return ("bloquear", f"[BLOQUEADO PELO SISTEMA IMUNE] {v.motivo}. Diga ao usuário, em uma frase, que isso foi "
                                "bloqueado para proteger o PC e o JARVIS. Não tente de outro jeito.")
        msg = imune.isolamento.bloqueio(nome, params.get("action") if isinstance(params, dict) else None)
        if msg:
            self.bloqueadas += 1
            return ("bloquear", msg)
        if v.acao == CONFIRMAR:
            self.confirmacoes += 1
            return ("confirmar", f"🛡️ Confirmar: {nome}", f"O sistema imune pediu a sua confirmação: {v.motivo}.")
        return None

    def _ameaca(self, ev) -> None:
        d = ev.dados
        if d.get("gravidade") == "critica":
            self.org.avisar(f"Alerta do sistema imune: {d.get('mensagem', '')[:180]}", "urgente")

    def estado(self) -> dict:
        e = super().estado()
        e.update(verificadas=self.verificadas, bloqueadas=self.bloqueadas, confirmacoes=self.confirmacoes)
        return e
