"""Controlador do MINER AI: liga o motor, aplica as regras de economia a cada 5 s, mede energia e guarda histórico.

O estado sai sempre ROTULADO (real / confirmado / pendente / simulacao / custos) — ver miner_ai/__init__.py.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from miner_ai import cerebro, config, economia, rede, seguranca
from miner_ai.motor_btc import MotorBTC
from miner_ai.motor_xmrig import MotorXMRig

MOTORES = {"btc": MotorBTC, "xmr": MotorXMRig}
MAX_HISTORICO = 3000


class Controlador:
    def __init__(self, log=print, avisar=None, motores: dict | None = None, sensores: dict | None = None):
        self.log = log
        self.avisar = avisar or (lambda t: log(t))
        self.motores = motores or MOTORES
        s = sensores or {}
        self.sensor_temp = s.get("temperatura", economia.temperatura)
        self.sensor_tomada = s.get("na_tomada", economia.na_tomada)
        self.sensor_ocioso = s.get("ocioso", economia.ocioso_segundos)
        self.agora = s.get("agora", time.time)
        self.motor = None
        self.moeda = None
        self.cfg: dict = config.carregar()
        self._lock = threading.RLock()
        self._thread = None
        self._parar = threading.Event()
        self.mercado: dict = {"precos": {}, "dif": {}, "saldo": None, "ts": 0}
        self._zerar()

    def _zerar(self) -> None:
        self.inicio = self.ultimo_tick = self.ultimo_hist = self.ultimo_temp = 0.0
        self.segundos_minerando = self.kwh = self.custo = 0.0
        self.temp = None
        self.watts = 0.0
        self.carga_max = self.carga = 30.0
        self.pausa_auto = ""
        self.pausa_manual = False
        self.aviso_regulagem = ""

    # ─────────────────────────────────────────────── ligar / desligar ───
    def problemas(self, moeda: str) -> list[str]:
        cfg = config.carregar()
        ok, motivo = seguranca.pode_minerar()
        if not ok:
            return [motivo]
        if moeda not in self.motores:
            return ["moeda sem motor: use btc (Python puro) ou xmr (XMRig)"]
        erros = []
        if moeda == "btc" and not seguranca.btc_valido(cfg.get("carteira_btc")):
            erros.append("falta o seu endereço PÚBLICO de Bitcoin (o de receber, começa com 1, 3 ou bc1)")
        if moeda == "xmr":
            if not seguranca.xmr_valido(cfg.get("carteira_xmr")):
                erros.append("falta o seu endereço PÚBLICO Monero (começa com 4 ou 8)")
            if self.motores is MOTORES:
                erros += MotorXMRig(cfg).problemas()
        if cfg.get("parar_na_bateria", True) and self.sensor_tomada() is False:
            erros.append("o notebook está na bateria: ligue na tomada")
        return erros

    def iniciar(self, moeda: str) -> tuple[bool, str]:
        with self._lock:
            if self.motor:
                return False, f"o MINER AI já está minerando {self.moeda.upper()}"
            erros = self.problemas(moeda)
            if erros:
                return False, "; ".join(erros)
            self.cfg = config.carregar()
            self._zerar()
            n = cerebro.nucleos()
            threads = int(self.cfg.get("threads") or 0) or economia.threads_padrao(n, self.cfg.get("economico"))
            threads = max(1, min(threads, n))
            self.carga_max = self.carga = economia.carga_padrao(self.cfg) if moeda == "btc" else 100.0
            self.motor = self.motores[moeda](self.cfg, self.log)
            self.moeda = moeda
            self.inicio = self.ultimo_tick = self.ultimo_hist = self.agora()
            self.motor.iniciar(threads, self.carga)
            self._parar.clear()
            self._thread = threading.Thread(target=self._laco, daemon=True, name="miner-ai")
            self._thread.start()
            threading.Thread(target=self.atualizar_mercado, daemon=True).start()
            modo = "econômico" if self.cfg.get("economico") else "normal"
            return True, (f"MINER AI minerando {cerebro.MOEDAS[moeda]['nome']} de verdade com {threads} núcleo(s), modo {modo}"
                          + (f", CPU {self.carga:.0f}%" if moeda == "btc" else "") + ". Tudo aparece no painel.")

    def parar(self, motivo: str = "você pediu") -> str:
        with self._lock:
            if not self.motor:
                return "O MINER AI não está minerando."
            self._parar.set()
            self.tick(final=True)
            m = self.motor.metricas()
            self.motor.parar()
            sessao = self._resumo_sessao(m, motivo)
            sess = config.ler_json("sessoes.json", []) or []
            config.gravar_json("sessoes.json", (sess + [sessao])[-500:])
            self.motor, self.moeda = None, None
        return (f"MINER AI parado ({motivo}). {sessao['horas']:.2f} h minerando, {sessao['shares']} share(s) aceitos, "
                f"{sessao['kwh']:.3f} kWh ≈ {cerebro._r(sessao['custo'])} de luz (estimado).")

    def pausar(self) -> str:
        with self._lock:
            if not self.motor:
                return "O MINER AI não está minerando."
            self.pausa_manual = True
            self.motor.pausar()
            return "Pausado. Diga 'retomar' para continuar."

    def retomar(self) -> str:
        with self._lock:
            if not self.motor:
                return "O MINER AI não está minerando."
            self.pausa_manual = False
            if not self.pausa_auto:
                self.motor.retomar()
                return "Retomado."
            return f"Ainda pausado: {self.pausa_auto}."

    # ─────────────────────────────────────────────── regras a cada 5 s ───
    def _laco(self) -> None:
        while not self._parar.wait(5):
            try:
                self.tick()
            except Exception as e:
                self.log(f"[MINER AI] {e}")

    def tick(self, final: bool = False) -> None:
        with self._lock:
            if not self.motor:
                return
            agora = self.agora()
            dt = max(0.0, agora - self.ultimo_tick)
            self.ultimo_tick = agora
            pausado = self.motor.pausado
            if not pausado:
                self.segundos_minerando += dt
            self.kwh += economia.kwh(self.watts, dt)
            self.custo = self.kwh * float(self.cfg.get("tarifa") or 0)
            if final:
                return
            if not self.motor.vivo():
                threading.Thread(target=self.parar, args=("o motor fechou",), daemon=True).start()
                return
            horas = (agora - self.inicio) / 3600
            if horas >= float(self.cfg.get("horas_max") or 8):
                threading.Thread(target=self._parar_e_avisar, args=(f"limite de {float(self.cfg.get('horas_max') or 8):g} h",),
                                 daemon=True).start()
                return
            if agora - self.ultimo_temp >= 30:
                self.ultimo_temp = agora
                self.temp = self.sensor_temp()
            pode, motivo = economia.decidir(self.cfg, datetime.fromtimestamp(agora), self.sensor_tomada(), self.sensor_ocioso(), 0)
            carga, aviso = economia.regular(self.carga, self.temp, float(self.cfg.get("temperatura_max") or 80), self.carga_max)
            if carga <= 0:
                pode, motivo = False, aviso
            if not pode:
                if not pausado:
                    self.motor.pausar()
                    self.avisar(f"MINER AI pausado: {motivo}.")
                self.pausa_auto = motivo
            else:
                if self.pausa_auto and not self.pausa_manual:
                    self.motor.retomar()
                    self.avisar("MINER AI retomado.")
                self.pausa_auto = ""
                if carga != self.carga:
                    self.carga = carga
                    self.motor.definir_carga(carga)
                    if aviso:
                        self.aviso_regulagem = aviso
                        self.avisar(f"MINER AI: {aviso}.")
            externo = self.motor.nome == "xmrig"
            self.watts = 0.0 if self.motor.pausado else economia.watts_estimados(self.cfg, self.motor.threads, self.carga,
                                                                                  cerebro.nucleos(), externo)
            if agora - self.ultimo_hist >= 60 and not self.motor.pausado:
                self.ultimo_hist = agora
                hs = self.motor.hashrate()
                if hs > 0:
                    h = config.ler_json("historico.json", []) or []
                    h.append({"ts": agora, "motor": self.motor.nome, "threads": self.motor.threads, "carga": self.carga, "hs": hs,
                              "temp": self.temp, "watts": self.watts})
                    config.gravar_json("historico.json", h[-MAX_HISTORICO:])

    def _parar_e_avisar(self, motivo: str) -> None:
        self.avisar(self.parar(motivo))

    # ─────────────────────────────────────────────── números de fora ───
    def atualizar_mercado(self) -> None:
        cfg = config.carregar()
        precos = rede.precos_brl([m["cg"] for m in cerebro.MOEDAS.values()])
        dif = {k: rede.dificuldade(k) for k in cerebro.MOEDAS}
        saldo = None
        moeda = self.moeda
        if moeda == "btc" and cfg.get("carteira_btc"):
            saldo = rede.saldo_btc(cfg["carteira_btc"])
        elif moeda == "xmr" and cfg.get("carteira_xmr"):
            saldo = rede.saldo_pool_xmr(cfg["carteira_xmr"])
        self.mercado = {"precos": precos, "dif": dif, "saldo": saldo, "saldo_moeda": moeda, "ts": time.time()}

    def simulacoes(self, threads: int | None = None) -> dict[str, dict]:
        """O que cada moeda PODERIA render neste PC (rótulo: simulação)."""
        cfg = config.carregar()
        hist = config.ler_json("historico.json", []) or []
        n = cerebro.nucleos()
        out = {}
        for k, m in cerebro.MOEDAS.items():
            th = threads or int(cfg.get("threads") or 0) or economia.threads_padrao(n, cfg.get("economico"))
            carga = economia.carga_padrao(cfg) if k == "btc" else 100.0
            if self.motor and self.moeda == k and self.motor.hashrate() > 0:
                hs, medido = self.motor.hashrate(), True
            else:
                hs, medido = cerebro.hashrate_para(k, cfg, hist, th, carga)
            d = (self.mercado["dif"].get(k) or {}).get("valor") or m["dif_aprox"]
            watts = economia.watts_estimados(cfg, th, carga, n, k == "xmr")
            r = cerebro.rentabilidade(k, hs, d, self.mercado["precos"].get(m["cg"]), watts, float(cfg.get("tarifa") or 0))
            r.update(medido=medido, dificuldade_aprox=not self.mercado["dif"].get(k), watts=watts, threads=th, carga=carga)
            r["veredito"] = cerebro.veredito(r)
            out[k] = r
        return out

    # ─────────────────────────────────────────────── estado rotulado ───
    def estado(self) -> dict:
        cfg = config.carregar()
        with self._lock:
            m = self.motor.metricas() if self.motor else None
            moeda = self.moeda
            tempo = (self.agora() - self.inicio) if self.motor else 0.0
            sims = self.simulacoes()
            sim = sims.get(moeda) if moeda else None
            ganho_esperado = None
            if m and sim and sim.get("preco"):
                mm = cerebro.MOEDAS[moeda]
                d = (self.mercado["dif"].get(moeda) or {}).get("valor") or mm["dif_aprox"]
                ganho_esperado = m["hashes_total"] / (d * mm["fator"]) * mm["recompensa"] * sim["preco"]
            saldo = self.mercado.get("saldo") if self.mercado.get("saldo_moeda") == moeda else None
            hist = config.ler_json("historico.json", []) or []
            return {
                "rodando": bool(self.motor), "moeda": moeda, "nome_moeda": cerebro.MOEDAS[moeda]["nome"] if moeda else None,
                "endereco": seguranca.mascarar(cfg.get("carteira_btc" if moeda == "btc" else "carteira_xmr")) if moeda else None,
                "desempenho": {"hashrate": m["hashrate"] if m else 0.0, "threads": m["threads"] if m else 0, "carga": self.carga if m else 0,
                               "temperatura": self.temp, "watts": self.watts, "pausado": bool(m and m["pausado"]),
                               "motivo_pausa": self.pausa_auto or ("você pausou" if self.pausa_manual else ""),
                               "regulagem": self.aviso_regulagem, "tempo_s": tempo, "minerando_s": self.segundos_minerando,
                               "conectado": bool(m and m["conectado"]), "dificuldade_pool": m["dificuldade_pool"] if m else None},
                "real": {"shares_aceitos": m["shares_aceitos"] if m else 0, "shares_rejeitados": m["shares_rejeitados"] if m else 0,
                         "blocos": m["blocos"] if m else 0, "hashes": m["hashes_total"] if m else 0,
                         "ultimo_share": m["ultimo_share"] if m else None,
                         "explicacao": "Trabalho aceito pela pool. Na pool solo só um BLOCO paga." if moeda == "btc"
                         else "Trabalho aceito pela pool; o pagamento sai quando passa do mínimo dela."},
                "confirmado": {"valor": saldo["confirmado"] if saldo else None, "fonte": saldo["fonte"] if saldo else None,
                               "ts": saldo["ts"] if saldo else None,
                               "o_que_e": "saldo do seu endereço na blockchain" if moeda == "btc" else "já pago pela pool"},
                "pendente": {"valor": saldo["pendente"] if saldo else None, "fonte": saldo["fonte"] if saldo else None,
                             "o_que_e": "chegando no endereço (mempool)" if moeda == "btc" else "a pool deve, ainda não pagou"},
                "simulacao": {"moedas": sims, "ganho_esperado_sessao": ganho_esperado,
                              "aviso": "projeções do cérebro: o que PODERIA render, não é dinheiro"},
                "custos": {"kwh": self.kwh, "reais": self.custo, "tarifa": float(cfg.get("tarifa") or 0),
                           "watts_fonte": "medido na tomada" if cfg.get("watts_medidos") else "estimado pelo TDP"},
                "resultado_estimado": {"reais": None if ganho_esperado is None else ganho_esperado - self.custo,
                                       "o_que_e": "ganho ESPERADO (simulação) menos a luz estimada"},
                "recomendacoes": cerebro.recomendar(cfg, hist, sims),
                "mercado_ts": self.mercado.get("ts"),
                "config": {k: cfg[k] for k in ("economico", "cpu_max", "temperatura_max", "tarifa", "horarios", "horas_max")},
                "sessoes": (config.ler_json("sessoes.json", []) or [])[-10:],
            }

    def _resumo_sessao(self, m: dict, motivo: str) -> dict:
        mm = cerebro.MOEDAS[self.moeda]
        d = (self.mercado["dif"].get(self.moeda) or {}).get("valor") or mm["dif_aprox"]
        preco = self.mercado["precos"].get(mm["cg"])
        esperado = m["hashes_total"] / (d * mm["fator"]) * mm["recompensa"]
        return {"inicio": self.inicio, "fim": self.agora(), "moeda": self.moeda, "horas": (self.agora() - self.inicio) / 3600,
                "minerando_h": self.segundos_minerando / 3600, "hashes": m["hashes_total"], "shares": m["shares_aceitos"],
                "rejeitados": m["shares_rejeitados"], "blocos": m["blocos"], "kwh": self.kwh, "custo": self.custo,
                "esperado_moedas": esperado, "esperado_reais": esperado * preco if preco else None, "motivo": motivo}


_unico: Controlador | None = None
_lock_unico = threading.Lock()


def controlador(**kw) -> Controlador:
    """O controlador da máquina (um só por processo)."""
    global _unico
    with _lock_unico:
        if _unico is None:
            _unico = Controlador(**kw)
        return _unico
