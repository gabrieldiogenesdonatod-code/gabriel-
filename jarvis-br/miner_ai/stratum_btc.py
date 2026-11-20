"""Mineração de Bitcoin em Python puro: o protocolo Stratum (o que as pools falam) e o SHA-256d do cabeçalho.

Sem instalar nada: só a biblioteca padrão (socket, hashlib, json). Funciona numa pool de verdade.
As funções de conta são puras e conferidas com o bloco gênese do Bitcoin nos testes.
"""
from __future__ import annotations

import hashlib
import json
import socket
import struct
import threading
import time

DIF1 = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
MAX_ALVO = (1 << 256) - 1


def sha256d(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def trocar_palavras(hexa: str) -> bytes:
    """Inverte cada palavra de 4 bytes (é assim que o Stratum manda o prevhash). Pura."""
    b = bytes.fromhex(hexa)
    return b"".join(b[i:i + 4][::-1] for i in range(0, len(b), 4))


def alvo_da_dificuldade(dif: float) -> int:
    """Alvo do share para a dificuldade da pool. Pura."""
    if dif <= 0:
        return MAX_ALVO
    return min(MAX_ALVO, int(DIF1 / dif))


def alvo_do_nbits(nbits_hex: str) -> int:
    """Alvo da REDE (achar um bloco de verdade). Pura."""
    n = int(nbits_hex, 16)
    return (n & 0xFFFFFF) * (1 << (8 * ((n >> 24) - 3)))


def raiz_merkle(coinb1: str, extranonce1: str, extranonce2: str, coinb2: str, ramos: list[str]) -> bytes:
    """Raiz de Merkle com a SUA transação coinbase (é ela que manda a recompensa para o seu endereço). Pura."""
    raiz = sha256d(bytes.fromhex(coinb1 + extranonce1 + extranonce2 + coinb2))
    for r in ramos:
        raiz = sha256d(raiz + bytes.fromhex(r))
    return raiz


def prefixo_cabecalho(versao: str, prevhash: str, raiz: bytes, ntime: str, nbits: str) -> bytes:
    """Os 76 primeiros bytes do cabeçalho (falta só o nonce). Pura."""
    return bytes.fromhex(versao)[::-1] + trocar_palavras(prevhash) + raiz + bytes.fromhex(ntime)[::-1] + bytes.fromhex(nbits)[::-1]


def hash_do_nonce(prefixo: bytes, nonce: int) -> bytes:
    return sha256d(prefixo + struct.pack("<I", nonce))


def valor(h: bytes) -> int:
    """O hash como número (o Bitcoin compara em little-endian). Pura."""
    return int.from_bytes(h, "little")


def procurar(prefixo: bytes, inicio: int, quantidade: int, alvo: int) -> tuple[list[tuple[int, bytes]], int]:
    """Testa `quantidade` nonces a partir de `inicio`. Devolve ([(nonce, hash)] abaixo do alvo, testados).
    Usa o "meio-estado" do SHA-256: os primeiros 64 bytes são calculados uma vez só."""
    meio = hashlib.sha256(prefixo[:64])
    cauda = prefixo[64:76]
    sha = hashlib.sha256
    pack = struct.Struct("<I").pack
    rapido = alvo < (1 << 224)                        # alvo normal: o hash precisa terminar com 4 bytes zero
    achados = []
    fim = min(0x100000000, inicio + quantidade)
    for n in range(inicio, fim):
        h = meio.copy()
        h.update(cauda + pack(n))
        d = sha(h.digest()).digest()
        if (not rapido or d[28:] == b"\0\0\0\0") and int.from_bytes(d, "little") <= alvo:
            achados.append((n, d))
    return achados, fim - inicio


def nonce_hex(nonce: int) -> str:
    """Como o Stratum espera o nonce no mining.submit (big-endian). Pura."""
    return struct.pack(">I", nonce).hex()


def hash_exibicao(h: bytes) -> str:
    """O hash como aparece nos exploradores de bloco. Pura."""
    return h[::-1].hex()


class Cliente:
    """Conexão Stratum v1: subscribe, authorize, notify, set_difficulty, submit. Reconecta sozinho."""

    def __init__(self, host: str, porta: int, usuario: str, senha: str = "x", ao_trabalho=None, ao_resultado=None, log=print):
        self.host, self.porta, self.usuario, self.senha = host, int(porta), usuario, senha
        self.ao_trabalho, self.ao_resultado, self.log = ao_trabalho, ao_resultado, log
        self.sock = None
        self.extranonce1, self.extranonce2_tam = "", 4
        self.dificuldade = 1.0
        self.trabalho = None
        self.autorizado = False
        self.conectado = False
        self._id = 0
        self._pendentes: dict = {}
        self._parar = threading.Event()
        self._escrita = threading.Lock()
        self._thread = None

    def iniciar(self) -> None:
        self._thread = threading.Thread(target=self._rodar, name="stratum", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass

    def _enviar(self, metodo: str, params: list, contexto=None) -> int:
        with self._escrita:
            self._id += 1
            self._pendentes[self._id] = (metodo, contexto)
            self.sock.sendall((json.dumps({"id": self._id, "method": metodo, "params": params}) + "\n").encode())
            return self._id

    def enviar_share(self, job_id: str, extranonce2: str, ntime: str, nonce: int, contexto=None) -> None:
        self._enviar("mining.submit", [self.usuario, job_id, extranonce2, ntime, nonce_hex(nonce)], contexto)

    def _rodar(self) -> None:
        espera = 2
        while not self._parar.is_set():
            try:
                self.sock = socket.create_connection((self.host, self.porta), timeout=30)
                self.sock.settimeout(300)
                self.conectado = True
                espera = 2
                self._enviar("mining.subscribe", ["MINER-AI/1.0"])
                self._enviar("mining.authorize", [self.usuario, self.senha])
                buf = b""
                while not self._parar.is_set():
                    pedaco = self.sock.recv(65536)
                    if not pedaco:
                        raise ConnectionError("a pool fechou a conexão")
                    buf += pedaco
                    while b"\n" in buf:
                        linha, buf = buf.split(b"\n", 1)
                        if linha.strip():
                            self._tratar(json.loads(linha))
            except Exception as e:
                self.conectado = False
                self.autorizado = False
                if self._parar.is_set():
                    break
                self.log(f"[MINER AI] pool: {e}; tentando de novo em {espera} s")
                self._parar.wait(espera)
                espera = min(120, espera * 2)

    def _tratar(self, msg: dict) -> None:
        metodo = msg.get("method")
        if metodo == "mining.set_difficulty":
            self.dificuldade = float(msg["params"][0])
            if self.trabalho and self.ao_trabalho:
                self.ao_trabalho(self.trabalho, self.dificuldade, False)
        elif metodo == "mining.notify":
            p = msg["params"]
            self.trabalho = {"job_id": p[0], "prevhash": p[1], "coinb1": p[2], "coinb2": p[3], "ramos": p[4], "versao": p[5],
                             "nbits": p[6], "ntime": p[7], "limpar": bool(p[8]), "extranonce1": self.extranonce1,
                             "extranonce2_tam": self.extranonce2_tam, "recebido": time.time()}
            if self.ao_trabalho:
                self.ao_trabalho(self.trabalho, self.dificuldade, True)
        elif metodo == "mining.set_extranonce":
            self.extranonce1, self.extranonce2_tam = msg["params"][0], int(msg["params"][1])
        elif "id" in msg and msg["id"] in self._pendentes:
            pedido, contexto = self._pendentes.pop(msg["id"])
            if pedido == "mining.subscribe" and msg.get("result"):
                self.extranonce1, self.extranonce2_tam = msg["result"][1], int(msg["result"][2])
            elif pedido == "mining.authorize":
                self.autorizado = bool(msg.get("result"))
                if not self.autorizado:
                    self.log(f"[MINER AI] a pool recusou o usuário: {msg.get('error')}")
            elif pedido == "mining.submit" and self.ao_resultado:
                self.ao_resultado(bool(msg.get("result")), msg.get("error"), contexto)
