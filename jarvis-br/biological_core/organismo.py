"""
O organismo digital: monta os órgãos, liga um ao outro pelo sistema nervoso e conduz o ciclo de vida.

    cérebro ── coordena          coração ── mantém vivo        sistema nervoso ── comunica
    circulação ── leva eventos   sistema imune ── protege       DNA ── identidade e integridade
    regeneração ── conserta      células (6 tipos) ── os agentes especializados

Arquivos (memory/biological/): genoma.json · .chave_dna · celulas_tronco.zip · imunidade.db ·
quarentena.json · cerebro.json · autorizacoes.json · estado.json · diario.json · nervos.jsonl ·
evolucao.json · prevencao.json · pontos/ · painel.html
"""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path

from biological_core.autorizacao import Autorizacoes
from biological_core.brain.central_brain import Cerebro
from biological_core.cells.analyst_cell import Analista
from biological_core.cells.defender import Defensora
from biological_core.cells.detector_cell import Detectora
from biological_core.cells.memory_cell import CelulaMemoria
from biological_core.cells.repair_cell import Reparadora
from biological_core.cells.sentinel import Sentinela
from biological_core.circulation.data_flow import Circulacao
from biological_core.config import ESSENCIAIS, PASTA_PADRAO, RAIZ, cfg, gravar_json, ler_json
from biological_core.dna.digital_dna import DNA
from biological_core.dna.integrity_checker import BancoCelulasTronco, VerificadorIntegridade
from biological_core.heart.health_monitor import MonitorSaude
from biological_core.heart.heart_engine import Coracao
from biological_core.immune_system.immune_core import SistemaImune
from biological_core.immune_system.immune_memory import MemoriaImune
from biological_core.nervous_system.event_bus import ALTA, Barramento
from biological_core.regeneration import recovery_tests
from biological_core.regeneration.recovery_engine import MotorRecuperacao

ROTINAS = ("bio_ronda", "bio_rede", "bio_sono")


class Organismo:
    def __init__(self, raiz: Path = RAIZ, pasta: Path = PASTA_PADRAO, sincrono: bool = False, automatico: bool = True,
                 semente: int | None = None, agora=time.time, conectividade=recovery_tests.testar_conectividade,
                 fonte_vitais=None, intervalo: float | None = None):
        self.raiz, self.pasta = Path(raiz), Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.sincrono, self.automatico = sincrono, automatico
        self.essenciais = set(ESSENCIAIS)
        self.observando: set[str] = set()
        self.esperando_rede: set[tuple] = set()
        self.player = None
        self.ligado = False
        self.nascimento = time.time()
        self.avisos: deque = deque(maxlen=50)
        self.ouvintes_aviso: list = []
        self._conectividade = conectividade
        self._rede: tuple[float, bool | None] = (0.0, None)
        self.estado_arq = self.pasta / "estado.json"
        self.estado: dict = ler_json(self.estado_arq, {}) or {}
        self.painel_ate = 0.0

        self.bus = Barramento(log=self.pasta / "nervos.jsonl")
        self.circulacao = Circulacao(self.bus)
        self.memoria = MemoriaImune(self.pasta / "imunidade.db")
        self.autorizacoes = Autorizacoes(self.pasta / "autorizacoes.json")
        self.dna = DNA(self.raiz, self.pasta)
        self.verificador = VerificadorIntegridade(self.dna)
        self.banco = BancoCelulasTronco(self.pasta / "celulas_tronco.zip", self.raiz)
        self.saude = MonitorSaude()
        self.imune = SistemaImune(self.bus, self, self.pasta, self.raiz, agora)
        self.cerebro = Cerebro(self.bus, self, self.pasta, semente)
        self.imune.evolucao.classificador = self.cerebro.classificador
        self.sentinela = Sentinela(self.bus, self)
        self.detectora = Detectora(self.bus, self)
        self.defensora = Defensora(self.bus, self)
        self.analista = Analista(self.bus, self)
        self.reparadora = Reparadora(self.bus, self)
        self.celula_memoria = CelulaMemoria(self.bus, self, self.pasta)
        self.regeneracao = MotorRecuperacao(self, conectividade)
        self.coracao = Coracao(self.bus, self, intervalo or float(cfg("bio_batimento_s", 10) or 10), fonte_vitais)
        self.celulas = [self.sentinela, self.detectora, self.defensora, self.analista, self.reparadora, self.celula_memoria]
        for acao in ("restaurar_json", "restaurar_codigo"):
            self.autorizacoes.registrar_fabrica(acao, lambda p, a=acao: (lambda ficha: self.regeneracao.continuar_autorizado(
                (p.get("dados") or {}).get("incidente"), a, ficha)))
        self.autorizacoes.registrar_fabrica("dna_mutar", lambda p: (lambda ficha: self._mutar(ficha, p)))
        self.autorizacoes.registrar_fabrica("config_bio", lambda p: (lambda ficha: self._mudar_config(ficha, p)))

    # ── ciclo de vida ─────────────────────────────────────────────────────────
    def iniciar(self, registro=None) -> list[dict]:
        etapas = [("DNA", self._etapa_dna), ("memória imunológica", lambda: f"{len(self.memoria.abertos())} incidente(s) aberto(s)"),
                  ("sistema nervoso e circulação", self._etapa_circulacao), ("sistema imunológico", self._etapa_imune),
                  ("cérebro", lambda: f"{self.cerebro.classificador.estado()['exemplos']} exemplos no classificador"),
                  ("células", lambda: f"{len(self.celulas)} tipos ativos"), ("coração", self._etapa_coracao),
                  ("relógio", self._etapa_relogio)]
        rel = self.coracao.ciclo_inicializacao(etapas)
        self.ligado = True
        self.estado["ultimo_inicio"] = time.time()
        self.estado["inicios"] = int(self.estado.get("inicios", 0)) + 1
        self.salvar_estado()
        self.bus.publicar("organismo.iniciado", {"etapas": len(rel), "falhas": sum(not e["ok"] for e in rel)}, "organismo", ALTA)
        if self.sincrono:
            self.ronda_inicial(registro)
        else:
            threading.Thread(target=self.ronda_inicial, args=(registro,), daemon=True, name="bio_ronda_inicial").start()
        return rel

    def _etapa_dna(self) -> str:
        s = self.dna.carregar()
        if s == "sem_genoma":
            nasceu = bool(self.estado.get("nascimento"))
            self.dna.genese()
            info = self.banco.criar(list(self.dna.genoma["arquivos"]))
            self.estado["nascimento"] = self.estado.get("nascimento") or time.time()
            if nasceu:
                self.sentinela._publicar(_sintoma_dna("o DNA tinha sumido e foi recriado a partir dos arquivos de agora; "
                                                      "se você não apagou, desconfie", "critica"), unico=True)
            return f"gênese: {len(self.dna.genoma['arquivos'])} arquivos, células-tronco {info['bytes'] // 1024} KB"
        if s == "ok" and not self.banco.existe():
            self.banco.criar(list(self.dna.genoma["arquivos"]))
        return f"genoma {s} ({len((self.dna.genoma or {}).get('arquivos', {}))} arquivos)"

    def _etapa_circulacao(self) -> str:
        if not self.sincrono:
            self.circulacao.iniciar()
        return "assíncrona" if not self.sincrono else "síncrona"

    def _etapa_imune(self) -> str:
        try:
            from core import vigia
            vigia.LIMITES.update({k: float(v) for k, v in (self.estado.get("limites") or {}).items()})
        except Exception:
            pass
        return f"proteção {self.imune.nivel_protecao()}%, {len(self.imune.isolamento.listar())} isolado(s)"

    def _etapa_coracao(self) -> str:
        if self.automatico:
            self.coracao.iniciar()
        return f"batimento a cada {self.coracao.intervalo:.0f} s" if self.automatico else "manual"

    def _etapa_relogio(self) -> str:
        if not self.automatico:
            return "sem rotinas (modo manual)"
        from core import relogio
        relogio.agendar("bio_ronda", lambda: self.sentinela.ronda(completa=False), 1800, 600, essencial=True)
        relogio.agendar("bio_rede", self.verificar_rede, 60, 60, essencial=True)
        relogio.agendar("bio_sono", self.talvez_dormir, 3600, 900, essencial=True)
        return "3 rotinas no relógio central"

    def ronda_inicial(self, registro=None) -> None:
        try:
            if registro is None:
                try:
                    from core import registro_ferramentas
                    registro = registro_ferramentas._plugins
                except Exception:
                    registro = None
            self.sentinela.ronda_inicial(registro)
            try:
                from core import registro_uso
                self.imune.anomalias.semear(registro_uso.chamadas(time.time() - 7 * 86400))
            except Exception:
                pass
            self.imune.prevencao.criar_ponto("início do JARVIS")
            if not self.imune.evolucao.estado.get("exercicios"):
                self.imune.evolucao.exercitar()
        except Exception as e:
            self.sentinela.relatar_erro(e, "ronda inicial")

    def encerrar(self) -> list[dict]:
        if not self.ligado:
            return []
        self.ligado = False
        try:
            from core import relogio
            for r in ROTINAS:
                relogio.cancelar(r)
        except Exception:
            pass
        etapas = [("circulação (entregar o que falta)", lambda: self.circulacao.parar(2.0)),
                  ("cérebro (salvar aprendizado)", self.cerebro.salvar), ("diário", self.celula_memoria.salvar),
                  ("estado", self.salvar_estado), ("memória imunológica", self.memoria.fechar_conexao)]
        self.bus.publicar("organismo.encerrado", {}, "organismo", ALTA, sincrono=True)
        return self.coracao.encerramento_seguro(etapas)

    # ── entradas (chamadas pela integração) ───────────────────────────────────
    def portao(self, nome: str, params: dict | None):
        return self.defensora.portao(nome, params or {})

    def permite_rotina(self, nome: str) -> bool:
        return self.imune.isolamento.bloqueio(f"rotina:{nome}", None) is None

    # ── manutenção ────────────────────────────────────────────────────────────
    def manutencao_leve(self) -> None:
        """A cada ~1 min (batimento): avaliações vencidas, diário, nervos inflamados, boletim da manhã."""
        self.cerebro.manutencao()
        self.celula_memoria.salvar()
        if self.coracao.batimentos % 60 == 0:
            for a in self.bus.assinantes():
                if not a["ativo"]:
                    self.bus.reanimar(a["nome"])
        self.entregar_boletim()

    def verificar_rede(self) -> bool | None:
        precisa = self.esperando_rede or any(c in ("rede", "timeout") for ts, _m, c, _i, _o in list(self.sentinela.recentes)[-20:]
                                             if time.time() - ts < 600)
        if not precisa:
            return None
        ok = self.testar_rede_agora()
        if ok and self.esperando_rede:
            for mod, acao in list(self.esperando_rede):
                self.imune.isolamento.meio_abrir(mod, acao)
            self.esperando_rede.clear()
            self.bus.publicar("descoberta.rede", {"voltou": True}, "organismo")
        return ok

    def testar_rede_agora(self) -> bool:
        ok = bool(self._conectividade())
        self._rede = (time.time(), ok)
        return ok

    def conectividade_recente(self) -> bool | None:
        ts, ok = self._rede
        return ok if time.time() - ts < 300 else None

    def reanimar(self) -> list[str]:
        feitos = []
        if self.ligado and not self.sincrono and not self.circulacao.viva():
            self.circulacao.iniciar()
            feitos.append("circulação")
        for a in self.bus.assinantes():
            if not a["ativo"] and self.bus.reanimar(a["nome"]):
                feitos.append(f"nervo {a['nome']}")
        if self.ligado and self.automatico and not self.coracao.vivo_de_verdade():
            self.coracao.iniciar()
            feitos.append("coração")
        return feitos

    def talvez_dormir(self) -> str | None:
        """Sono de manutenção: entre 4h e 6h, uma vez por dia (depois dos sonhos das 3h)."""
        hoje = time.strftime("%Y-%m-%d")
        if not (4 <= time.localtime().tm_hour < 6) or self.estado.get("ultimo_sono") == hoje:
            return None
        return self.dormir()

    def dormir(self) -> str:
        feito = []
        n = self.memoria.limpar_antigos(90)
        feito.append(f"{n} incidente(s) antigo(s) arquivado(s)")
        try:
            self.memoria.compactar()
        except Exception:
            pass
        pid = self.imune.prevencao.criar_ponto("sono diário")
        feito.append(f"ponto de restauração {pid or 'sem mudanças'}")
        self.sentinela.ronda(completa=True)
        res = self.imune.evolucao.exercitar()
        feito.append(f"vacinas {sum(r['ok'] for r in res)}/{len(res)}")
        ajustes = self.imune.evolucao.ajustar()
        if ajustes:
            feito.append("limites ajustados: " + "; ".join(ajustes))
        self.estado["ultimo_sono"] = time.strftime("%Y-%m-%d")
        self.estado["boletim"] = {"dia": time.strftime("%Y-%m-%d"), "texto": self.boletim(), "entregue": False}
        self.salvar_estado()
        self.celula_memoria.anotar("sono", "; ".join(feito))
        return "; ".join(feito)

    def boletim(self) -> str:
        est = self.memoria.estatisticas(time.time() - 86400)
        partes = []
        if est["total"]:
            partes.append(f"nas últimas 24 h, {est['total']} problema(s): {est['resolvidos']} curado(s)"
                          + (f" ({est['automaticos']} sozinho)" if est["automaticos"] else ""))
        isol = self.imune.isolamento.listar()
        if isol:
            partes.append(f"{len(isol)} parte(s) isolada(s): " + ", ".join(i["chave"].replace("|*", "") for i in isol[:3]))
        pend = self.autorizacoes.pendentes()
        if pend:
            partes.append(f"{len(pend)} reparo(s) esperando o seu sim")
        ex = (self.imune.evolucao.estado.get("exercicios") or [{}])[-1].get("resultados", [])
        falhos = [r["nome"] for r in ex if not r["ok"]]
        if falhos:
            partes.append("vacina(s) falhando: " + ", ".join(falhos))
        if not partes:
            return ""
        return f"Boletim de saúde do JARVIS (nota {self.saude.ultimo['nota']}): " + "; ".join(partes) + "."

    def entregar_boletim(self) -> bool:
        b = self.estado.get("boletim") or {}
        if not b.get("texto") or b.get("entregue") or time.localtime().tm_hour < 7:
            return False
        b["entregue"] = True
        self.salvar_estado()
        self.avisar(b["texto"], "baixa")
        return True

    # ── autorizados ───────────────────────────────────────────────────────────
    def pedir_mutacao(self, motivo: str = "mudanças reconhecidas por você") -> dict:
        r = self.verificador.verificar()
        n = len(r["modificados"]) + len(r["novos"]) + len(r["ausentes"])
        return self.autorizacoes.pedir("dna_mutar", "Atualizar o DNA do JARVIS",
                                       f"{n} arquivo(s) diferentes do DNA ({len(r['modificados'])} mudaram, {len(r['novos'])} novos, "
                                       f"{len(r['ausentes'])} sumiram). Aceitar como a identidade nova? A cópia confiável "
                                       "(células-tronco) também é refeita.", None, alvo="tudo", dados={"motivo": motivo})

    def _mutar(self, ficha: str, p: dict) -> str:
        msg = self.dna.mutar(ficha, self.autorizacoes, (p.get("dados") or {}).get("motivo", "autorizado"))
        if msg.startswith("DNA atualizado"):
            self.banco.criar(list(self.dna.genoma["arquivos"]))
            self.verificador.verificar()
            for inc in self.memoria.abertos():
                if inc["categoria"] == "integridade":
                    self.memoria.fechar(inc["id"], "mudanças aceitas no DNA", causa="mudanca_no_codigo", humano=True)
            self.sentinela._vistos.clear()
        return msg

    def pedir_config(self, chave: str, valor, titulo: str, detalhe: str) -> dict:
        return self.autorizacoes.pedir("config_bio", titulo, detalhe, None, alvo=chave, dados={"chave": chave, "valor": valor})

    def _mudar_config(self, ficha: str, p: dict) -> str:
        d = p.get("dados") or {}
        if not self.autorizacoes.validar(ficha, f"config_bio:{d.get('chave')}"):
            return "Recusado: sem autorização."
        return self.gravar_config(d.get("chave"), d.get("valor"))

    def gravar_config(self, chave: str, valor) -> str:
        try:
            from memory.config_manager import _patch_config
            _patch_config(**{chave: valor})
            from biological_core.config import esquecer_cache
            esquecer_cache()
            self.estado.setdefault("config_vigiada", {})[chave] = valor     # mudança autorizada não é alarme
            self.salvar_estado()
            return f"{chave} = {valor}"
        except Exception as e:
            return f"não consegui gravar a configuração: {e}"

    # ── saída ─────────────────────────────────────────────────────────────────
    def avisar(self, texto: str, prioridade: str = "normal") -> None:
        self.avisos.append({"ts": time.time(), "texto": texto, "prioridade": prioridade})
        for ouvinte in list(self.ouvintes_aviso):
            try:
                ouvinte(texto, prioridade)
            except Exception:
                pass
        if self.sincrono:
            return
        try:
            from core import central_avisos
            central_avisos.avisar(texto, prioridade, "SAÚDE", self.player)
        except Exception:
            pass
        try:
            from core import protecao_falhas
            protecao_falhas.evento(f"organismo: {texto[:120]}")
        except Exception:
            pass

    def salvar_estado(self) -> None:
        try:
            gravar_json(self.estado_arq, self.estado)
        except Exception:
            pass

    # ── leitura ───────────────────────────────────────────────────────────────
    def estado_orgaos(self) -> dict:
        agora = time.time()
        o = {}

        def cor_reativo(org) -> str:
            return "amarelo" if org.ultimo_erro_ts and agora - org.ultimo_erro_ts < 300 else "azul"

        o["cerebro"] = {"titulo": "Cérebro", "cor": cor_reativo(self.cerebro) if self.ligado else "vermelho",
                        "detalhe": f"{self.cerebro.metricas['decisoes']} decisão(ões), acerto "
                                   + (f"{self.cerebro.aprendizado()['acerto']:.0%}" if self.cerebro.aprendizado()["acerto"] is not None else "—")}
        bate = self.coracao.ultimo_batimento
        if self.automatico and self.ligado:
            cor = "azul" if self.coracao.vivo_de_verdade() and (not bate or agora - bate < 3 * self.coracao.intervalo + 5) else "vermelho"
        else:
            cor = "azul"
        o["coracao"] = {"titulo": "Coração", "cor": "amarelo" if self.coracao.febre and cor == "azul" else cor,
                        "detalhe": f"{self.coracao.batimentos} batimentos" + (" · FEBRE (rotinas pausadas)" if self.coracao.febre else "")}
        inflamados = self.bus.estado()["inflamados"]
        o["nervos"] = {"titulo": "Sistema nervoso", "cor": "vermelho" if len(inflamados) >= 3 else ("amarelo" if inflamados else "azul"),
                       "detalhe": f"{self.bus.frequencia():.0f} eventos/min" + (f" · {len(inflamados)} inflamado(s)" if inflamados else "")}
        nivel = self.imune.nivel_protecao()
        o["imune"] = {"titulo": "Sistema imunológico", "cor": "azul" if nivel >= 80 else ("amarelo" if nivel >= 50 else "vermelho"),
                      "detalhe": f"proteção {nivel}%", "nivel": nivel}
        v = self.verificador.ultimo or {}
        vital = any(r.startswith("biological_core/") or r in ("main.py",) for r in v.get("modificados", []) + v.get("ausentes", []))
        s = self.dna.situacao
        cor = "vermelho" if s in ("adulterado", "corrompido") or vital else ("amarelo" if s != "ok" or v.get("modificados") or v.get("ausentes") else "azul")
        o["dna"] = {"titulo": "DNA", "cor": cor, "detalhe": f"integridade {v.get('integridade', 0):.0f}%" if v else s,
                    "integridade": v.get("integridade")}
        c = self.circulacao.estado()
        cor = "azul" if (c["viva"] or self.sincrono) and not c["congestionada"] else ("amarelo" if c["congestionada"] else "vermelho")
        o["circulacao"] = {"titulo": "Circulação", "cor": cor if self.ligado else "vermelho",
                           "detalhe": f"fila {c['fila']}, espera {c['espera_media_ms']:.0f} ms"}
        r = self.regeneracao.estado()
        pend = len(self.autorizacoes.pendentes())
        cor = "amarelo" if r["em_andamento"] or pend else ("verde" if agora - self.saude.ultima_recuperacao < 300 else "azul")
        o["regeneracao"] = {"titulo": "Regeneração", "cor": cor,
                            "detalhe": ("reparando agora" if r["em_andamento"] else f"{r['curados']} cura(s)")
                                       + (f" · {pend} esperando o seu sim" if pend else "")}
        doentes = [c.nome for c in self.celulas if c.ultimo_erro_ts and agora - c.ultimo_erro_ts < 300]
        o["celulas"] = {"titulo": "Células", "cor": "amarelo" if doentes else "azul",
                        "detalhe": f"{len(self.celulas)} tipos" + (f" · com erro: {', '.join(doentes)}" if doentes else "")}
        return o

    def resumo_texto(self) -> str:
        s = self.saude.ultimo
        orgs = self.estado_orgaos()
        ruins = [f"{o['titulo']}: {o['detalhe']}" for o in orgs.values() if o["cor"] in ("amarelo", "vermelho")]
        abertos = self.memoria.abertos()
        isol = self.imune.isolamento.listar()
        pend = self.autorizacoes.pendentes()
        linhas = [f"Saúde do JARVIS: {s['nota']}/100 ({s['cor']}), tendência {self.saude.tendencia()}. "
                  f"Proteção {orgs['imune']['nivel']}%, DNA {orgs['dna']['detalhe']}."]
        if ruins:
            linhas.append("Pedem atenção — " + "; ".join(ruins) + ".")
        if s.get("problemas"):
            linhas.append("Por que a nota: " + "; ".join(s["problemas"][:3]) + ".")
        if abertos:
            linhas.append(f"{len(abertos)} problema(s) em aberto: " + "; ".join(f"#{i['id']} {i['modulo']} ({i['categoria']})" for i in abertos[:4]) + ".")
        if isol:
            linhas.append("Isolados: " + "; ".join(f"{i['chave'].replace('|*', '')} ({i['motivo'][:50]})" for i in isol[:4]) + ".")
        if pend:
            linhas.append(f"{len(pend)} reparo(s) esperando o seu sim: " + "; ".join(f"{p['id']} {p['titulo']}" for p in pend[:3]) + ".")
        if len(linhas) == 1:
            linhas.append("Tudo funcionando: nenhum problema aberto, nada isolado.")
        return " ".join(linhas)


def _sintoma_dna(texto: str, grav: str) -> dict:
    from biological_core.immune_system.threat_detector import sintoma
    return sintoma("dna", "genese", texto=texto, origem="integridade", categoria="integridade", tipo="DNA", gravidade=grav, ameaca=True)
