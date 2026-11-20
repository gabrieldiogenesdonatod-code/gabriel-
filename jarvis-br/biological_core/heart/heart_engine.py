"""
Coração digital — JARVIS HEART. Mantém o organismo funcionando.

Bate numa thread PRÓPRIA (uma só, leve: dorme entre batimentos) — de propósito fora do relógio
central, para conseguir perceber até o relógio travado. A cada batimento (10 s):
    • sinais vitais: CPU e memória do JARVIS, RAM e disco do PC, threads, temperatura (lida da
      core/telemetria.py, a fonte única do projeto, quando ela está rodando)
    • batimentos digitais: eventos por minuto no sistema nervoso
    • órgãos vivos? módulos travados? (ferramenta presa além do limite, rotina do relógio parada,
      fila da circulação velha, assinante do sistema nervoso inflamado)
    • reflexos — respostas rápidas sem esperar o cérebro:
        memória alta → coleta de lixo e limpa caches
        FEBRE (saúde abaixo de 50 por 3 batimentos) → pausa as rotinas de fundo que não são
        essenciais até a saúde voltar a 70+; temperatura crítica → aviso urgente
    • manda a nota de saúde e as cores para o painel

Também conduz o ciclo de inicialização (órgãos na ordem certa, cada etapa cronometrada; uma etapa
que falha não impede as outras) e o encerramento seguro.
"""

from __future__ import annotations

import gc
import threading
import time
from typing import Callable

from biological_core.nervous_system.communication import Orgao
from biological_core.nervous_system.event_bus import ALTA, BAIXA, NORMAL

_PROC = None


def vitais_padrao(raiz) -> dict:
    """Sinais vitais baratos (sem interferir na medição de CPU da telemetria)."""
    global _PROC
    v = {"ts": time.time(), "threads": threading.active_count()}
    try:
        import psutil
        if _PROC is None:
            _PROC = psutil.Process()
            _PROC.cpu_percent(None)
        with _PROC.oneshot():
            v["cpu_jarvis"] = round(_PROC.cpu_percent(None) / max(1, psutil.cpu_count() or 1), 1)
            v["ram_jarvis_mb"] = round(_PROC.memory_info().rss / 1e6, 1)
        v["ram_pc"] = float(psutil.virtual_memory().percent)
        v["disco_livre_pct"] = round(100.0 - psutil.disk_usage(str(raiz)).percent, 1)
    except Exception:
        pass
    try:
        from core import telemetria
        inst = getattr(telemetria, "_instancia", None)
        if inst is not None:
            s = inst.snapshot()
            v["temp_cpu"] = s.get("cpu_temp")
            v["cpu_pc"] = s.get("cpu")
    except Exception:
        pass
    return v


class Coracao(Orgao):
    nome = "coracao"

    def __init__(self, bus, org, intervalo: float = 10.0, fonte_vitais: Callable[[], dict] | None = None):
        super().__init__(bus)
        self.org = org
        self.intervalo = max(2.0, float(intervalo))
        self.fonte_vitais = fonte_vitais or (lambda: vitais_padrao(org.raiz))
        self.vitais: dict = {}
        self.batimentos = 0
        self.ultimo_batimento = 0.0
        self.duracao_ms = 0.0
        self.febre = False
        self._febre_n = 0
        self._ok_n = 0
        self.inicializacao: list[dict] = []
        self.encerramento: list[dict] = []
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self.caches: list[Callable[[], None]] = []
        self.reflexos = 0

    # ── ciclo de vida ─────────────────────────────────────────────────────────
    def ciclo_inicializacao(self, etapas: list[tuple[str, Callable[[], object]]]) -> list[dict]:
        rel = []
        for nome, fn in etapas:
            t0 = time.perf_counter()
            try:
                r = fn()
                rel.append({"etapa": nome, "ok": True, "ms": round((time.perf_counter() - t0) * 1000, 1),
                            "detalhe": str(r)[:120] if r is not None else ""})
            except Exception as e:
                rel.append({"etapa": nome, "ok": False, "ms": round((time.perf_counter() - t0) * 1000, 1),
                            "detalhe": f"{type(e).__name__}: {e}"[:160]})
        self.inicializacao = rel
        return rel

    def encerramento_seguro(self, etapas: list[tuple[str, Callable[[], object]]]) -> list[dict]:
        self.parar()
        rel = []
        for nome, fn in etapas:
            try:
                fn()
                rel.append({"etapa": nome, "ok": True})
            except Exception as e:
                rel.append({"etapa": nome, "ok": False, "detalhe": str(e)[:160]})
        self.encerramento = rel
        return rel

    def iniciar(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, daemon=True, name="coracao")
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    def vivo_de_verdade(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _laco(self) -> None:
        while not self._parar.wait(self.intervalo):
            try:
                self.bater()
            except Exception as e:
                self.relatar_erro(e, "batimento")

    # ── batimento ─────────────────────────────────────────────────────────────
    def bater(self) -> dict:
        t0 = time.perf_counter()
        org = self.org
        v = self.fonte_vitais() or {}
        v["bpm"] = round(self.bus.frequencia(), 1)
        self.vitais = v
        self.batimentos += 1
        travados = self.travados()
        imune = org.imune
        for a in (imune.anomalias.memoria(v.get("ts", time.time()), v.get("ram_jarvis_mb")),
                  imune.anomalias.taxa_eventos(v["bpm"]), imune.anomalias.threads(v.get("threads", 0))):
            if a:
                from biological_core.immune_system.threat_detector import sintoma
                org.sentinela._publicar(sintoma("jarvis", a["tipo"], texto=a["mensagem"], origem="anomalia", categoria="anomalia",
                                                tipo=a["tipo"], gravidade="media", anomalia=a["tipo"]))
        for nome, acao, seg in travados:
            if nome.startswith(("rotina:", "orgao:")):
                from biological_core.immune_system.threat_detector import sintoma
                org.sentinela._publicar(sintoma(nome, acao, texto=f"parado há {seg:.0f} s", origem="coracao",
                                                categoria="travamento", tipo="Travado", interno=True), unico=True)
        orgaos = org.estado_orgaos()
        saude = org.saude.avaliar(v, orgaos, travados, org.memoria.abertos(), len(imune.isolamento.listar()))
        self._reflexos(v, saude)
        cor_antes = getattr(self, "_cor", None)
        self._cor = saude["cor"]
        self.enviar("coracao.batimento", {"n": self.batimentos, "nota": saude["nota"], "cor": saude["cor"], "bpm": v["bpm"]},
                    BAIXA, chave="batimento")
        if cor_antes and cor_antes != saude["cor"]:
            self.enviar("saude.mudou", {"de": cor_antes, "para": saude["cor"], "nota": saude["nota"],
                                        "problemas": saude["problemas"][:3]}, NORMAL)
        if self.batimentos % 6 == 0:
            org.manutencao_leve()
        if time.time() < getattr(org, "painel_ate", 0):
            try:
                from biological_core.dashboard.biological_dashboard import escrever
                escrever(org)
            except Exception as e:
                self.relatar_erro(e, "painel")
        self.ultimo_batimento = time.time()
        self.duracao_ms = round((time.perf_counter() - t0) * 1000, 1)
        return saude

    def travados(self) -> list[tuple[str, str, float]]:
        org = self.org
        out = []
        try:
            from core import vigia
            limite = vigia.limite_configurado()
        except Exception:
            limite = 30.0
        for nome, acao, seg in org.sentinela.em_andamento():
            if seg > limite + 15:
                out.append((nome, acao, seg))
        try:
            from core import relogio
            ex = relogio.executando()
            if ex and ex[1] > 60:
                out.append((f"rotina:{ex[0]}", "*", ex[1]))
        except Exception:
            pass
        circ = org.circulacao
        if circ.ativa and (not circ.viva() or circ.fila.idade_mais_antiga() > 30):
            out.append(("orgao:circulacao", "*", circ.fila.idade_mais_antiga()))
        return out

    # ── reflexos ──────────────────────────────────────────────────────────────
    def reflexo_memoria(self) -> int:
        for limpar in list(self.caches):
            try:
                limpar()
            except Exception:
                pass
        self.reflexos += 1
        return gc.collect()

    def _reflexos(self, v: dict, saude: dict) -> None:
        ram, rss = v.get("ram_pc"), v.get("ram_jarvis_mb")
        if (ram is not None and ram >= 92) or (rss is not None and rss >= 2500):
            if time.time() - getattr(self, "_ult_reflexo_mem", 0) > 600:
                self._ult_reflexo_mem = time.time()
                n = self.reflexo_memoria()
                self.compartilhar("reflexo", {"tipo": "memoria", "coletados": n, "ram_pc": ram, "rss": rss})
        temp = v.get("temp_cpu")
        if temp is not None and temp >= 95 and time.time() - getattr(self, "_ult_temp", 0) > 1800:
            self._ult_temp = time.time()
            self.org.avisar(f"A CPU está a {temp:.0f} °C. Pausei as rotinas de fundo; vale deixar o PC respirar.", "urgente")
            self._febre(True)
        if saude["nota"] < 50:
            self._febre_n, self._ok_n = self._febre_n + 1, 0
            if self._febre_n >= 3 and not self.febre:
                self._febre(True)
        elif saude["nota"] >= 70:
            self._ok_n, self._febre_n = self._ok_n + 1, 0
            if self._ok_n >= 3 and self.febre:
                self._febre(False)
        else:
            self._febre_n = self._ok_n = 0

    def _febre(self, liga: bool) -> None:
        self.febre = liga
        try:
            from core import relogio
            relogio.pausar_nao_essenciais(liga)
        except Exception:
            pass
        self.enviar("coracao.febre", {"febre": liga}, ALTA)
        self.reflexos += 1

    def estado(self) -> dict:
        e = super().estado()
        e.update(batimentos=self.batimentos, intervalo_s=self.intervalo, duracao_ms=self.duracao_ms, febre=self.febre,
                 vivo=self.vivo_de_verdade(), reflexos=self.reflexos)
        return e
