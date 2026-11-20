"""
Células sentinelas — monitoramento. São os sensores do organismo.

Recebem (na hora, sem esperar nada) o que acontece no JARVIS:
    • cada chamada de plugin: início, fim, tempo, sucesso ou falha (via core/plugin_loader.py)
    • ferramenta que passou do limite e a que terminou atrasada (via core/vigia.py)
    • rotina de fundo com erro (via core/relogio.py)
    • erro de um órgão do próprio organismo (o sistema imune também vigia a si mesmo)
E fazem as rondas: plugins que não carregaram, queda na última execução, dependências,
integridade do DNA, arquivos de dados quebrados e configurações críticas mexidas por fora.
Cada coisa errada vira um "sintoma.falha" para as células detectoras — uma vez por mudança,
não a cada ronda (sem ruído).
"""

from __future__ import annotations

import itertools
import re
import threading
import time
from collections import deque

from biological_core.config import cfg
from biological_core.immune_system.threat_detector import sintoma
from biological_core.nervous_system.communication import Orgao
from biological_core.nervous_system.event_bus import BAIXA, NORMAL

CONFIG_VIGIADA = ("bio_desligado", "bio_autonomia", "bio_pre_autorizados", "bio_rajada_por_min", "limite_ferramenta_s",
                  "limite_ferramentas")
ENFRAQUECE = {"bio_desligado", "bio_pre_autorizados"}


class Sentinela(Orgao):
    nome = "sentinela"

    def __init__(self, bus, org):
        super().__init__(bus)
        self.org = org
        self.recentes: deque = deque(maxlen=400)          # (ts, modulo, categoria, impressao, origem)
        self.em_voo: dict[int, tuple] = {}
        self._seq = itertools.count(1)
        self._lock = threading.Lock()
        self.chamadas = 0
        self.falhas = 0
        self._vistos: dict[str, str] = {}
        self.ouvir("orgao.erro", self._erro_de_orgao)
        self.ouvir("nervo.inflamado", self._nervo)

    # ── chamadas de ferramenta ────────────────────────────────────────────────
    def inicio(self, nome: str, params: dict | None) -> int:
        tok = next(self._seq)
        with self._lock:
            self.em_voo[tok] = (nome, _acao(params), time.monotonic(), threading.get_ident())
        return tok

    def fim(self, tok: int) -> None:
        with self._lock:
            self.em_voo.pop(tok, None)

    def em_andamento(self) -> list[tuple[str, str, float]]:
        agora = time.monotonic()
        with self._lock:
            return sorted(((n, a, agora - t0) for n, a, t0, _th in self.em_voo.values()), key=lambda x: -x[2])

    def resultado(self, nome: str, params: dict | None, ms: float, ok: bool, erro=None, texto: str = "") -> None:
        self.pulsar()
        self.chamadas += 1
        acao = _acao(params)
        imune = self.org.imune
        if not ok and erro is None and not falha_forte(texto):
            imune.anomalias.latencia(nome, ms)              # "erro" no meio do texto não basta para contar como falha
            return
        for a in (imune.anomalias.latencia(nome, ms), imune.anomalias.resultado(nome, ok)):
            if a:
                self._publicar(sintoma(nome, acao, texto=a["mensagem"], origem="anomalia", categoria="anomalia",
                                       tipo=a["tipo"], gravidade="baixa", **{"anomalia": a["tipo"]}))
        if ok:
            curou = imune.isolamento.sucesso(nome, acao)
            if curou or nome in self.org.observando:
                self.enviar("sintoma.recuperado", {"modulo": nome, "acao": acao, "curou_disjuntor": curou}, NORMAL)
            return
        self.falhas += 1
        s = sintoma(nome, acao, erro=erro, texto=texto, origem="plugin", params=params, raiz=self.org.raiz)
        s["disjuntor_abriu"] = imune.isolamento.falha(nome, acao, s["mensagem"][:120], s.get("categoria") or "")
        self._publicar(s)

    def travou(self, nome: str, limite: float) -> None:
        voo = [x for x in self.em_andamento() if x[0] == nome]
        acao = voo[0][1] if voo else "*"
        s = sintoma(nome, acao, texto=f"passou de {limite:.0f} s sem terminar", origem="vigia", categoria="timeout", tipo="Travou")
        s["disjuntor_abriu"] = self.org.imune.isolamento.falha(nome, acao, "travou", "timeout")
        self._publicar(s)

    def terminou_tarde(self, nome: str, segundos: float, ok: bool) -> None:
        self.compartilhar("lentidao", {"modulo": nome, "segundos": round(segundos, 1), "ok": ok})

    def erro_rotina(self, nome: str, erro) -> None:
        mod = f"rotina:{nome}"
        s = sintoma(mod, "*", erro=erro if isinstance(erro, BaseException) else None, texto=str(erro), origem="relogio",
                    raiz=self.org.raiz)
        s["disjuntor_abriu"] = self.org.imune.isolamento.falha(mod, None, s["mensagem"][:120], s.get("categoria") or "")
        self._publicar(s)

    def _erro_de_orgao(self, ev) -> None:
        d = ev.dados
        if d.get("orgao") in ("sentinela", "detectora"):
            return                                          # não cria laço de sintomas sobre si mesma
        self._publicar(sintoma(f"orgao:{d.get('orgao')}", "*", texto=d.get("erro", ""), origem="orgao",
                               categoria="travamento", tipo="ErroDeOrgao", interno=True), unico=True)

    def _nervo(self, ev) -> None:
        self._publicar(sintoma("sistema_nervoso", ev.dados.get("assinante", "?"), texto=f"assinante desligado por erros: "
                               f"{ev.dados.get('erro', '')}", origem="orgao", categoria="travamento", tipo="NervoInflamado",
                               interno=True), unico=True)

    # ── rondas ────────────────────────────────────────────────────────────────
    def ronda_inicial(self, registro=None) -> int:
        n = 0
        det = self.org.imune.detector
        for s in (det.plugins_quebrados(registro) if registro is not None else []):
            n += self._publicar(s, unico=True)
        q = det.queda_anterior()
        if q:
            n += self._publicar(q, unico=True)
        dep = det.dependencias_ausentes()
        for p in dep["essenciais"]:
            n += self._publicar(sintoma("jarvis", "dependencias", texto=f"No module named '{p}' (pacote essencial)",
                                        origem="boot", categoria="pacote", tipo="ModuleNotFoundError", gravidade="alta"), unico=True)
        self.org.estado["dependencias"] = dep
        return n + self.ronda(completa=False)

    def ronda(self, completa: bool = False) -> int:
        n = 0
        org = self.org
        try:
            situacao = org.dna.carregar() if completa else org.dna.situacao
            if situacao in ("ok", "adulterado", "corrompido"):
                for s in org.verificador.sintomas(org.verificador.verificar()):
                    n += self._publicar(sintoma("dna", s["acao"], texto=s["mensagem"], origem="integridade",
                                                categoria="integridade", tipo="Integridade", gravidade=s["gravidade"],
                                                arquivos=s["arquivos"][:50], ameaca=s["ameaca"]), unico=True)
        except Exception as e:
            self.relatar_erro(e, "ronda de integridade")
        try:
            for r in org.imune.prevencao.checar_dados(so_mudados=not completa):
                n += self._publicar(sintoma("dados", "json", texto=r["erro"], origem="dados", categoria="json_corrompido",
                                            tipo="JSONDecodeError", arquivo=r["arquivo"], versao_boa=r["versao_boa"]), unico=True)
            if completa:
                for r in org.imune.prevencao.checar_bancos():
                    n += self._publicar(sintoma("dados", "sqlite", texto=r["erro"], origem="dados", categoria="json_corrompido",
                                                tipo="SQLiteCorrompido", arquivo=r["arquivo"], gravidade="alta"), unico=True)
        except Exception as e:
            self.relatar_erro(e, "ronda de dados")
        n += self._vigiar_config()
        return n

    def _vigiar_config(self) -> int:
        atual = {k: cfg(k) for k in CONFIG_VIGIADA}
        antes = self.org.estado.get("config_vigiada")
        self.org.estado["config_vigiada"] = atual
        if antes is None:
            return 0
        mudou = [k for k in CONFIG_VIGIADA if antes.get(k) != atual.get(k)]
        if not mudou:
            return 0
        enfraqueceu = any(k in ENFRAQUECE and atual.get(k) for k in mudou)
        return self._publicar(sintoma("configuracao", "critica", texto=f"configuração crítica mudou: {', '.join(mudou)}",
                                      origem="config", categoria="ameaca" if enfraqueceu else "integridade",
                                      tipo="ConfigAlterada", gravidade="media" if enfraqueceu else "info", ameaca=enfraqueceu))

    # ── envio ─────────────────────────────────────────────────────────────────
    def _publicar(self, s: dict, unico: bool = False) -> int:
        if unico:
            assinatura = f"{s['mensagem']}|{s.get('arquivo', '')}"
            if self._vistos.get(s["impressao"]) == assinatura:
                return 0
            self._vistos[s["impressao"]] = assinatura
        self.recentes.append((s["ts"], s["modulo"], s.get("categoria"), s["impressao"], s["origem"]))
        self.enviar("sintoma.falha", s, NORMAL if s.get("gravidade") != "info" else BAIXA, chave=f"s:{s['impressao']}")
        return 1

    def esquecer_visto(self, impressao: str) -> None:
        self._vistos.pop(impressao, None)

    def estado(self) -> dict:
        e = super().estado()
        e.update(chamadas=self.chamadas, falhas=self.falhas, em_voo=len(self.em_voo))
        return e


_FORTE = re.compile(r"^\s*(status=failed\b|\[(erro|error|falha|falhou|failed)|erro\b|error\b|falhou|falha ao|failed|"
                    r"n[aã]o consegui|sir, the '[^']+' plugin failed|plugin '[^']+' is not available)", re.I)


def falha_forte(texto: str) -> bool:
    """Resposta que é claramente uma falha (começa dizendo que falhou), não só um texto com a palavra 'erro'."""
    return bool(_FORTE.search(str(texto or "")[:200]))


def _acao(params) -> str:
    if isinstance(params, dict):
        a = params.get("action") or params.get("acao")
        if a:
            return str(a)[:40]
    return "*"
