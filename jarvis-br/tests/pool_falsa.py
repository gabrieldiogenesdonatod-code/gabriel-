"""Uma pool Stratum de mentira (só para os testes do MINER AI). Confere cada share com uma conta independente."""
import hashlib
import json
import os
import socket
import struct
import threading
import time


def _sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


class PoolFalsa:
    def __init__(self, dificuldade=0.0001, usuario_ok=None):
        self.dificuldade = dificuldade
        self.usuario_ok = usuario_ok
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.porta = self.sock.getsockname()[1]
        self.extranonce1 = "f000000f"
        self.job = {"id": "j1", "prevhash": os.urandom(32).hex(), "coinb1": os.urandom(40).hex(), "coinb2": os.urandom(30).hex(),
                    "ramos": [os.urandom(32).hex(), os.urandom(32).hex()], "versao": "20000000", "nbits": "1d00ffff",
                    "ntime": format(int(time.time()), "08x")}
        self.aceitos, self.recusados, self.usuarios = [], [], []
        self.parar = False
        threading.Thread(target=self._aceitar, daemon=True).start()

    def _aceitar(self):
        while not self.parar:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._cliente, args=(c,), daemon=True).start()

    def _confere(self, ex2, ntime, nonce_hex):
        j = self.job
        raiz = _sha256d(bytes.fromhex(j["coinb1"] + self.extranonce1 + ex2 + j["coinb2"]))
        for r in j["ramos"]:
            raiz = _sha256d(raiz + bytes.fromhex(r))
        prev = bytes.fromhex(j["prevhash"])
        prev = b"".join(prev[i:i + 4][::-1] for i in range(0, 32, 4))
        cab = struct.pack("<I", int(j["versao"], 16)) + prev + raiz + struct.pack("<I", int(ntime, 16)) + \
            struct.pack("<I", int(j["nbits"], 16)) + struct.pack("<I", int(nonce_hex, 16))
        h = _sha256d(cab)
        alvo = int(0x00000000FFFF0000000000000000000000000000000000000000000000000000 / self.dificuldade)
        return int.from_bytes(h, "little") <= alvo

    def _cliente(self, c):
        f = c.makefile("rwb")

        def enviar(m):
            f.write((json.dumps(m) + "\n").encode())
            f.flush()
        for linha in f:
            m = json.loads(linha)
            if m["method"] == "mining.subscribe":
                enviar({"id": m["id"], "result": [[["mining.notify", "abc"]], self.extranonce1, 4], "error": None})
            elif m["method"] == "mining.authorize":
                self.usuarios.append(m["params"][0])
                ok = self.usuario_ok is None or self.usuario_ok(m["params"][0])
                enviar({"id": m["id"], "result": ok, "error": None if ok else [24, "usuario invalido", None]})
                if ok:
                    enviar({"id": None, "method": "mining.set_difficulty", "params": [self.dificuldade]})
                    j = self.job
                    enviar({"id": None, "method": "mining.notify", "params": [j["id"], j["prevhash"], j["coinb1"], j["coinb2"], j["ramos"],
                                                                              j["versao"], j["nbits"], j["ntime"], True]})
            elif m["method"] == "mining.submit":
                _, job_id, ex2, ntime, nonce = m["params"]
                ok = job_id == self.job["id"] and self._confere(ex2, ntime, nonce)
                (self.aceitos if ok else self.recusados).append(m["params"])
                enviar({"id": m["id"], "result": ok, "error": None if ok else [23, "share invalido", None]})

    def fechar(self):
        self.parar = True
        self.sock.close()
