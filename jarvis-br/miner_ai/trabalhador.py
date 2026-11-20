"""Processo que faz as contas do Bitcoin (um por núcleo). Conversa com o motor por linhas JSON:

entrada:  {"cmd": "job", "chave": "...", "prefixo": "<76 bytes hex>", "alvo": "<hex>", "inicio": 0}
          {"cmd": "carga", "v": 30}     {"cmd": "pausa"}     {"cmd": "sair"}
saída:    {"t": "conta", "n": 123456}   {"t": "achou", "chave": "...", "nonce": 1, "hash": "..."}   {"t": "esgotou", "chave": "..."}

Carga = % do tempo trabalhando; no resto ele dorme (é assim que o limite de CPU funciona). Prioridade mínima.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time

from miner_ai.stratum_btc import procurar


def _ler(fila: queue.Queue) -> None:
    for linha in sys.stdin:
        try:
            fila.put(json.loads(linha))
        except ValueError:
            pass
    fila.put({"cmd": "sair"})


def _dizer(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def principal() -> None:
    try:
        os.nice(19)
    except Exception:
        pass
    fila: queue.Queue = queue.Queue()
    threading.Thread(target=_ler, args=(fila,), daemon=True).start()
    job, carga, nonce, pausado = None, 30.0, 0, False
    contados, ultimo_relato = 0, time.time()
    while True:
        try:
            while True:
                c = fila.get_nowait()
                if c["cmd"] == "sair":
                    return
                if c["cmd"] == "job":
                    job = {"chave": c["chave"], "prefixo": bytes.fromhex(c["prefixo"]), "alvo": int(c["alvo"], 16)}
                    nonce = int(c.get("inicio") or 0)
                    pausado = False
                elif c["cmd"] == "carga":
                    carga = max(5.0, min(100.0, float(c["v"])))
                elif c["cmd"] == "pausa":
                    pausado = True
        except queue.Empty:
            pass
        if job is None or pausado:
            time.sleep(0.2)
            continue
        fatia = 0.2
        ligado = fatia * carga / 100
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < ligado and nonce <= 0xFFFFFFFF:
            achados, n = procurar(job["prefixo"], nonce, 4000, job["alvo"])
            nonce += n
            contados += n
            for nn, h in achados:
                _dizer({"t": "achou", "chave": job["chave"], "nonce": nn, "hash": h.hex()})
        if nonce > 0xFFFFFFFF:
            _dizer({"t": "esgotou", "chave": job["chave"]})
            job = None
        if time.time() - ultimo_relato >= 2:
            _dizer({"t": "conta", "n": contados})
            contados, ultimo_relato = 0, time.time()
        resto = fatia - (time.perf_counter() - t0)
        if resto > 0:
            time.sleep(resto)


if __name__ == "__main__":
    principal()
