"""
Sistema de regeneração — SELF RECOVERY. O protocolo de 10 passos, auditável:

     1 detectar             o incidente, a categoria e o módulo
     2 identificar          qual componente (plugin, arquivo de dados, órgão interno)
     3 avaliar o risco      quanto pode dar errado se o reparo for feito agora
     4 isolar se preciso    quarentena para o que é grave ou vai mexer em arquivo
     5 consultar histórico  esse tratamento já falhou neste mesmo erro? então não repete
     6 ponto de recuperação antes de qualquer reparo que mexa em arquivo
     7 aplicar              só o que é seguro, ou o que você autorizou na tela
     8 reiniciar componente recarrega o plugin / deixa o disjuntor pronto para o teste
     9 testar               o teste de recuperação do componente
    10 informar             manda o resultado ao cérebro (que aprende com ele)

Recuperação que não funciona: o módulo fica isolado e o organismo chama você.
Nunca apaga arquivo nem reinstala nada sozinho. Cada passo fica gravado no incidente.
"""

from __future__ import annotations

import time

from biological_core.config import GRAVIDADES
from biological_core.nervous_system.event_bus import ALTA
from biological_core.regeneration import recovery_tests
from biological_core.regeneration.repair_manager import CATALOGO, GerenteReparos

ISOLAR_ANTES = {"restaurar_json", "restaurar_codigo", "recarregar_modulo"}


class MotorRecuperacao:
    def __init__(self, org, conectividade=recovery_tests.testar_conectividade):
        self.org = org
        self.reparos = GerenteReparos(org)
        self.conectividade = conectividade
        self.historico: list[dict] = []
        self.em_andamento: dict | None = None

    def _componente(self, inc: dict) -> str:
        if (inc.get("arquivo") or "").endswith(".json"):
            return f"arquivo de dados {inc['arquivo']}"
        if (self.org.raiz / "plugins" / f"{inc.get('modulo')}.py").is_file():
            return f"plugin {inc['modulo']} (plugins/{inc['modulo']}.py)"
        if str(inc.get("modulo", "")).startswith(("orgao:", "rotina:")):
            return f"parte interna {inc['modulo']}"
        return str(inc.get("modulo") or "?")

    def protocolo(self, inc: dict, tratamento: str, decisao: int | None = None, explicacao: str = "") -> dict:
        org = self.org
        rel = {"incidente": inc.get("id"), "tratamento": tratamento, "decisao": decisao, "passos": [], "inicio": time.time()}
        self.em_andamento = rel

        def passo(n: int, nome: str, detalhe: str) -> None:
            rel["passos"].append({"passo": f"{n} {nome}", "detalhe": str(detalhe)[:200], "ts": round(time.time(), 2)})

        passo(1, "detectar", f"{inc.get('categoria')} em {inc.get('modulo')} ({inc.get('ocorrencias', 1)}×): {str(inc.get('mensagem', ''))[:100]}")
        passo(2, "identificar", self._componente(inc))
        risco = org.imune.prevencao.avaliar_risco(tratamento, inc.get("arquivo") or "", inc.get("gravidade", "media"))
        passo(3, "avaliar risco", f"risco {risco:.0%}" + (f" — {explicacao[:100]}" if explicacao else ""))
        grave = GRAVIDADES.index(inc.get("gravidade", "media")) >= GRAVIDADES.index("alta")
        if (grave or tratamento in ISOLAR_ANTES) and inc.get("modulo") not in org.essenciais \
                and (org.raiz / "plugins" / f"{inc.get('modulo')}.py").is_file():
            org.imune.isolamento.isolar(inc["modulo"], None if tratamento in ISOLAR_ANTES else inc.get("acao"),
                                        f"em reparo ({tratamento})", inc.get("id"), por="regeneracao")
            passo(4, "isolar", "isolado durante o reparo")
        else:
            passo(4, "isolar", "não precisa (ou o disjuntor já cuida)")
        falharam = org.memoria.tratamentos_que_falharam(inc.get("impressao") or "")
        if tratamento in falharam:
            passo(5, "consultar histórico", f"'{tratamento}' já falhou 2+ vezes neste erro: pulei")
            return self._informar(inc, tratamento, "pulado", "já falhou antes neste erro", rel)
        anticorpo = org.memoria.reconhecer(inc.get("impressao") or "") or {}
        passo(5, "consultar histórico", f"erro visto {anticorpo.get('vezes', 1)} vez(es)"
              + (f"; o que já resolveu: {anticorpo['tratamento_bom']}" if anticorpo.get("tratamento_bom") else ""))
        if CATALOGO.get(tratamento) and CATALOGO[tratamento].escreve:
            pid = org.imune.prevencao.criar_ponto(f"antes de {tratamento}")
            passo(6, "ponto de recuperação", f"ponto {pid} criado" if pid else "o último ponto já tem tudo (nada mudou)")
        else:
            passo(6, "ponto de recuperação", "não precisa: este reparo não mexe em arquivo")
        estado, msg = self.reparos.aplicar(tratamento, inc)
        passo(7, "aplicar", f"{tratamento}: {msg}")
        if estado == "aguardando_autorizacao":
            return self._informar(inc, tratamento, estado, msg, rel)
        return self._finalizar(inc, tratamento, estado, msg, rel)

    def continuar_autorizado(self, iid: int, tratamento: str, ficha: str) -> str:
        """Você apertou CONFIRMAR: o protocolo continua do passo 7 com a ficha de autorização."""
        inc = self.org.memoria.incidente(int(iid))
        if not inc:
            return "O incidente não existe mais."
        rel = {"incidente": iid, "tratamento": tratamento, "passos": [], "inicio": time.time()}
        estado, msg = self.reparos.aplicar(tratamento, inc, ficha)
        rel["passos"].append({"passo": "7 aplicar", "detalhe": f"{tratamento} (autorizado): {msg}"[:200], "ts": round(time.time(), 2)})
        self._finalizar(inc, tratamento, estado, msg, rel)
        return msg

    def _finalizar(self, inc: dict, tratamento: str, estado: str, msg: str, rel: dict) -> dict:
        org = self.org
        if estado in ("aplicado", "resolvido"):
            if tratamento in ("esperar_rede", "isolar_temporario"):
                det8 = "o disjuntor testa sozinho quando o descanso acabar"
            elif tratamento in ("restaurar_json", "restaurar_codigo", "recarregar_modulo", "recriar_pasta"):
                det8 = "componente recarregado; a próxima chamada já é o teste"
                org.imune.isolamento.meio_abrir(inc.get("modulo") or "")
            else:
                det8 = "não precisa reiniciar"
            rel["passos"].append({"passo": "8 reiniciar componente", "detalhe": det8, "ts": round(time.time(), 2)})
            if estado == "resolvido" or tratamento in ("recarregar_modulo",):
                ok, det = recovery_tests.testar(inc, org, self.conectividade)
                rel["passos"].append({"passo": "9 testar", "detalhe": det, "ts": round(time.time(), 2)})
                if ok and estado == "resolvido":
                    org.imune.isolamento.liberar(inc.get("modulo") or "", por="regeneracao")
                elif not ok:
                    estado, msg = "falhou", f"{msg}; mas o teste falhou: {det}"
            else:
                rel["passos"].append({"passo": "9 testar", "detalhe": "o teste é a próxima chamada de verdade (observando)",
                                      "ts": round(time.time(), 2)})
        else:
            rel["passos"].append({"passo": "8 reiniciar componente", "detalhe": "não (o reparo não foi aplicado)", "ts": round(time.time(), 2)})
            rel["passos"].append({"passo": "9 testar", "detalhe": "—", "ts": round(time.time(), 2)})
        return self._informar(inc, tratamento, estado, msg, rel)

    def _informar(self, inc: dict, tratamento: str, estado: str, msg: str, rel: dict) -> dict:
        rel["passos"].append({"passo": "10 informar", "detalhe": f"resultado '{estado}' enviado ao cérebro", "ts": round(time.time(), 2)})
        rel.update(estado=estado, mensagem=msg, fim=time.time())
        self.historico.append({k: rel[k] for k in ("incidente", "tratamento", "estado", "mensagem", "fim")})
        del self.historico[:-50]
        self.em_andamento = None
        self.org.bus.publicar("reparo.resultado", {"incidente": inc, "tratamento": tratamento, "estado": estado,
                                                   "mensagem": msg, "passos": rel["passos"], "decisao": rel.get("decisao")},
                              "regeneracao", ALTA)
        return rel

    def estado(self) -> dict:
        ult = self.historico[-1] if self.historico else None
        return {"em_andamento": bool(self.em_andamento), "reparos": len(self.historico), "ultimo": ult,
                "curados": sum(1 for h in self.historico if h["estado"] == "resolvido")}
