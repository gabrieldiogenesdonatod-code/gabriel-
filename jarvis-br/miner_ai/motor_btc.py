"""Motor Bitcoin do MINER AI: Python puro, sem instalar nada. Liga numa pool (solo, por padrão) com o SEU endereço
público como usuário e faz SHA-256d em processos de prioridade mínima, um por núcleo, respeitando o limite de CPU.

Na pool SOLO (solo.ckpool.org) não existe "saldo acumulado": cada share aceito é trabalho real, mas só um BLOCO
inteiro paga — e aí a recompensa vai direto para o seu endereço, na blockchain. Por isso o painel mostra os shares
como "real" e o saldo como o que está no seu endereço público (confirmado), nunca como estimativa.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from miner_ai import stratum_btc as S

RAIZ = Path(__file__).resolve().parent.parent


class MotorBTC:
    nome = "btc"
    moeda = "btc"

    def __init__(self, cfg: dict, log=print, python: str | None = None):
        self.cfg, self.log = cfg, log
        self.python = python or sys.executable
        self.cliente: S.Cliente | None = None
        self.trabalhadores: list[subprocess.Popen] = []
        self.threads, self.carga = 1, 30.0
        self.pausado = False
        self._ex2 = 0
        self._jobs: dict[str, dict] = {}                 # chave → dados para enviar o share
        self._por_trab: dict[int, str] = {}
        self._contas: deque = deque()                    # (ts, hashes)
        self._lock = threading.Lock()
        self._escrita = threading.Lock()
        self.shares_aceitos = self.shares_rejeitados = self.blocos_aceitos = 0
        self.candidatos_bloco = 0
        self.ultimo_share = None
        self.hashes_total = 0
        self.erros: deque = deque(maxlen=5)

    # ───────────────────────────── ciclo de vida ─────────────────────────────
    def iniciar(self, threads: int, carga: float) -> None:
        host, porta = (str(self.cfg.get("pool_btc") or "solo.ckpool.org:3333").rsplit(":", 1) + ["3333"])[:2]
        usuario = f"{self.cfg['carteira_btc']}.{self.cfg.get('nome_maquina') or 'jarvis'}"
        self.threads, self.carga = max(1, int(threads)), float(carga)
        self.cliente = S.Cliente(host, int(porta), usuario, "x", self._novo_trabalho, self._resultado, self.log)
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "IDLE_PRIORITY_CLASS", 0x40) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = {**os.environ, "PYTHONPATH": str(RAIZ) + os.pathsep + os.environ.get("PYTHONPATH", "")}
        for i in range(self.threads):
            p = subprocess.Popen([self.python, "-m", "miner_ai.trabalhador"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 text=True, bufsize=1, cwd=str(RAIZ), env=env, creationflags=flags)
            self.trabalhadores.append(p)
            threading.Thread(target=self._ouvir, args=(i, p), daemon=True, name=f"trab-{i}").start()
        self.definir_carga(self.carga)
        self.cliente.iniciar()

    def parar(self) -> None:
        if self.cliente:
            self.cliente.parar()
        for p in self.trabalhadores:
            try:
                self._mandar(p, {"cmd": "sair"})
                p.wait(5)
            except Exception:
                p.kill()
        self.trabalhadores = []

    def definir_carga(self, carga: float) -> None:
        self.carga = max(5.0, min(100.0, float(carga)))
        for p in self.trabalhadores:
            self._mandar(p, {"cmd": "carga", "v": self.carga})

    def pausar(self) -> None:
        self.pausado = True
        for p in self.trabalhadores:
            self._mandar(p, {"cmd": "pausa"})

    def retomar(self) -> None:
        self.pausado = False
        if self.cliente and self.cliente.trabalho:
            self._novo_trabalho(self.cliente.trabalho, self.cliente.dificuldade, True)

    def vivo(self) -> bool:
        return bool(self.trabalhadores) and all(p.poll() is None for p in self.trabalhadores)

    # ───────────────────────────── trabalho ─────────────────────────────
    def _mandar(self, p: subprocess.Popen, msg: dict) -> None:
        try:
            with self._escrita:
                p.stdin.write(json.dumps(msg) + "\n")
                p.stdin.flush()
        except Exception:
            pass

    def _job_para(self, i: int, t: dict, dif: float) -> None:
        with self._lock:
            self._ex2 = (self._ex2 + 1) % (1 << (8 * t["extranonce2_tam"]))
            ex2 = format(self._ex2, f"0{t['extranonce2_tam'] * 2}x")
            raiz = S.raiz_merkle(t["coinb1"], t["extranonce1"], ex2, t["coinb2"], t["ramos"])
            prefixo = S.prefixo_cabecalho(t["versao"], t["prevhash"], raiz, t["ntime"], t["nbits"])
            chave = f"{t['job_id']}|{ex2}|{i}"
            self._jobs[chave] = {"job_id": t["job_id"], "ex2": ex2, "ntime": t["ntime"], "rede": S.alvo_do_nbits(t["nbits"])}
            velho = self._por_trab.get(i)
            if velho:
                self._jobs.pop(velho, None)
            self._por_trab[i] = chave
        self._mandar(self.trabalhadores[i], {"cmd": "job", "chave": chave, "prefixo": prefixo.hex(),
                                             "alvo": format(S.alvo_da_dificuldade(dif), "x"), "inicio": 0})

    def _novo_trabalho(self, t: dict, dif: float, novo: bool) -> None:
        if self.pausado:
            return
        for i in range(len(self.trabalhadores)):
            self._job_para(i, t, dif)

    def _ouvir(self, i: int, p: subprocess.Popen) -> None:
        for linha in p.stdout:
            try:
                m = json.loads(linha)
            except ValueError:
                continue
            if m["t"] == "conta":
                with self._lock:
                    self._contas.append((time.time(), m["n"]))
                    self.hashes_total += m["n"]
            elif m["t"] == "achou":
                job = self._jobs.get(m["chave"])
                if job and self.cliente:
                    h = bytes.fromhex(m["hash"])
                    bloco = S.valor(h) <= job["rede"]
                    if bloco:
                        self.candidatos_bloco += 1
                        self.log("[MINER AI] hash abaixo do alvo da REDE: possível BLOCO! enviando…")
                    self.cliente.enviar_share(job["job_id"], job["ex2"], job["ntime"], m["nonce"], {"bloco": bloco})
            elif m["t"] == "esgotou" and self.cliente and self.cliente.trabalho and not self.pausado:
                self._job_para(i, self.cliente.trabalho, self.cliente.dificuldade)

    def _resultado(self, ok: bool, erro, contexto) -> None:
        if ok:
            self.shares_aceitos += 1
            self.ultimo_share = time.time()
            if (contexto or {}).get("bloco"):
                self.blocos_aceitos += 1
        else:
            self.shares_rejeitados += 1
            self.erros.append(str(erro))

    # ───────────────────────────── números ─────────────────────────────
    def hashrate(self, janela: float = 30.0) -> float:
        agora = time.time()
        with self._lock:
            while self._contas and agora - self._contas[0][0] > janela:
                self._contas.popleft()
            soma = sum(n for _, n in self._contas)
        return soma / janela

    def metricas(self) -> dict:
        c = self.cliente
        return {"motor": self.nome, "moeda": self.moeda, "hashrate": self.hashrate(), "threads": self.threads, "carga": self.carga,
                "pausado": self.pausado, "conectado": bool(c and c.conectado), "autorizado": bool(c and c.autorizado),
                "dificuldade_pool": c.dificuldade if c else None, "shares_aceitos": self.shares_aceitos,
                "shares_rejeitados": self.shares_rejeitados, "blocos": self.blocos_aceitos, "candidatos_bloco": self.candidatos_bloco,
                "ultimo_share": self.ultimo_share, "hashes_total": self.hashes_total, "erros": list(self.erros), "vivo": self.vivo()}
