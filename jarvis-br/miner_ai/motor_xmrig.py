"""Motor Monero do MINER AI: controla o XMRig (o minerador oficial e mais eficiente para processador) que VOCÊ
baixou de github.com/xmrig/xmrig. O MINER AI nunca baixa nem instala nada, e nunca mexe no antivírus.

Janela visível, prioridade mínima, API só em 127.0.0.1 com senha aleatória. Pausar/retomar pela API; reduzir a
intensidade reinicia com menos núcleos (o XMRig não tem ciclo de descanso como o motor Bitcoin).
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path

PORTA_API = 18089


class MotorXMRig:
    nome = "xmrig"
    moeda = "xmr"

    def __init__(self, cfg: dict, log=print):
        self.cfg, self.log = cfg, log
        self.proc: subprocess.Popen | None = None
        self.token = ""
        self.threads, self.carga = 1, 100.0
        self.pausado = False
        self._ultimo: dict = {}

    def comando(self, threads: int) -> list[str]:
        c = self.cfg
        cmd = [str(c["xmrig"]), "-o", str(c.get("pool_xmr") or "pool.supportxmr.com:443"), "-u", str(c["carteira_xmr"]).strip(),
               "-p", str(c.get("nome_maquina") or "jarvis"), "--coin", "monero", "-t", str(max(1, threads)), "--cpu-priority", "0",
               "--http-host", "127.0.0.1", "--http-port", str(PORTA_API), "--http-access-token", self.token,
               "--http-no-restricted", "--print-time", "60", "--randomx-mode", "auto"]
        if str(c.get("pool_xmr") or "").endswith(":443"):
            cmd.append("--tls")
        return cmd

    def problemas(self) -> list[str]:
        exe = Path(str(self.cfg.get("xmrig") or ""))
        if not self.cfg.get("xmrig"):
            return ["falta o caminho do xmrig.exe (baixe em github.com/xmrig/xmrig — o MINER AI não baixa nada sozinho)"]
        if not exe.is_file() or "xmrig" not in exe.name.lower():
            return [f"não achei o XMRig em {exe}"]
        return []

    def iniciar(self, threads: int, carga: float) -> None:
        self.threads, self.carga = max(1, int(threads)), 100.0
        self.token = secrets.token_hex(16)
        self.proc = subprocess.Popen(self.comando(self.threads), cwd=str(Path(self.cfg["xmrig"]).parent),
                                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))      # janela visível

    def parar(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except Exception:
                self.proc.kill()
        self.proc = None

    def _rpc(self, metodo: str) -> bool:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORTA_API}/json_rpc", method="POST",
                                         data=json.dumps({"id": 1, "jsonrpc": "2.0", "method": metodo}).encode(),
                                         headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
            return True
        except Exception:
            return False

    def pausar(self) -> None:
        self.pausado = self._rpc("pause") or self.pausado

    def retomar(self) -> None:
        if self._rpc("resume"):
            self.pausado = False

    def definir_carga(self, carga: float) -> None:
        """Menos carga = menos núcleos (reinicia o XMRig). 0 = pausa."""
        if carga <= 0:
            self.pausar()
            return
        alvo = max(1, round(self.threads * carga / 100))
        if self.proc and alvo < self.threads:
            self.log(f"[MINER AI] reduzindo o XMRig para {alvo} núcleo(s)")
            self.parar()
            self.iniciar(alvo, 100)

    def vivo(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def resumo(self) -> dict:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORTA_API}/2/summary", headers={"Authorization": f"Bearer {self.token}"})
            self._ultimo = json.loads(urllib.request.urlopen(req, timeout=5).read())
        except Exception:
            pass
        return self._ultimo

    def hashrate(self) -> float:
        hs = [x for x in ((self.resumo().get("hashrate") or {}).get("total") or []) if x]
        return 0.0 if self.pausado else float(hs[0]) if hs else 0.0

    def metricas(self) -> dict:
        s = self.resumo()
        r = s.get("results") or {}
        return {"motor": self.nome, "moeda": self.moeda, "hashrate": self.hashrate(), "threads": self.threads, "carga": self.carga,
                "pausado": self.pausado, "conectado": bool((s.get("connection") or {}).get("pool")), "autorizado": True,
                "dificuldade_pool": (s.get("connection") or {}).get("diff"), "shares_aceitos": int(r.get("shares_good") or 0),
                "shares_rejeitados": max(0, int(r.get("shares_total") or 0) - int(r.get("shares_good") or 0)), "blocos": 0,
                "candidatos_bloco": 0, "ultimo_share": None, "hashes_total": int(r.get("hashes_total") or 0), "erros": [],
                "vivo": self.vivo()}
