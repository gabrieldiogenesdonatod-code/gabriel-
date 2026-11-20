"""
Testes da 1.6 — aparelhos da rede e o agente dos outros PCs.

Sem rede de verdade: o agente roda numa porta local e as partes de
descoberta/classificação são puras.
"""
import importlib.util
import json
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

import tests
from plugins import _rede, aparelhos as ap

_spec = importlib.util.spec_from_file_location("jarvis_agente", tests.RAIZ / "agente_pc" / "jarvis_agente.py")
agente = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agente)
agente.LOG, agente.ARQ = tests.TMP / "agente.log", tests.TMP / "agente.json"     # nada na pasta do projeto


class TestClassificar(unittest.TestCase):
    def test_tipos(self):
        self.assertEqual(_rede.classificar({8060}), "tv_roku")
        self.assertEqual(_rede.classificar({8002}), "tv_samsung")
        self.assertEqual(_rede.classificar(set(), "Linux/3.0 UPnP/1.0 webOS/1.0"), "tv_lg")
        self.assertEqual(_rede.classificar({5555}, "", "MiBox-sala"), "tv_android")
        self.assertEqual(_rede.classificar({5555}, "", "Galaxy-S21"), "android")
        self.assertEqual(_rede.classificar({_rede.PORTA_AGENTE, 445}), "pc")
        self.assertEqual(_rede.classificar({445}), "pc_windows")
        self.assertEqual(_rede.classificar({6668}), "tuya")
        self.assertEqual(_rede.classificar(set(), "", "Redmi-Note"), "celular")
        self.assertEqual(_rede.classificar(set()), "desconhecido")

    def test_ssdp_e_wol(self):
        cab = _rede.ler_ssdp("HTTP/1.1 200 OK\r\nSERVER: Roku/9.4.0 UPnP/1.0\r\nST: roku:ecp\r\n")
        self.assertEqual(cab["server"], "Roku/9.4.0 UPnP/1.0")
        pacote = _rede.pacote_magico("aa-bb-cc-dd-ee-ff")
        self.assertEqual(len(pacote), 102)
        self.assertEqual(pacote[:6], b"\xff" * 6)
        self.assertEqual(pacote[6:12], bytes.fromhex("aabbccddeeff"))
        with self.assertRaises(ValueError):
            _rede.pacote_magico("12:34")


class TestNomes(unittest.TestCase):
    LISTA = [{"nome": "TV da sala", "tipo": "tv_roku", "ip": "192.168.0.5"},
             {"nome": "PC do quarto", "tipo": "pc", "ip": "192.168.0.7"},
             {"nome": "Celular", "tipo": "celular", "ip": "192.168.0.9"}]

    def test_achar(self):
        nomes = lambda x: [a["nome"] for a in ap.achar(self.LISTA, x)]  # noqa: E731
        self.assertEqual(nomes("tv"), ["TV da sala"])
        self.assertEqual(nomes("quarto"), ["PC do quarto"])
        self.assertEqual(nomes("192.168.0.9"), ["Celular"])
        self.assertEqual(nomes("o celular"), ["Celular"])
        self.assertEqual(len(ap.achar(self.LISTA, "tudo")), 3)
        self.assertEqual(ap.achar(self.LISTA, "geladeira"), [])

    def test_teclas_e_apps(self):
        self.assertEqual(ap.tecla_de("aumentar"), "mais")
        self.assertEqual(ap.tecla_de("volume menos"), "menos")
        self.assertEqual(ap.app_de("abre o YouTube")[0], "youtube")
        self.assertEqual(ap.app_de("Netflix")[1]["roku"], "12")
        self.assertEqual(ap.plataforma("tv_android"), "adb")
        for t in ("mais", "menos", "mudo", "home", "voltar", "ok"):
            self.assertIn(t, ap.TECLAS_ROKU)
            self.assertIn(t, ap.TECLAS_ADB)


class TestAgente(unittest.TestCase):
    CHAVE = "chave-de-teste-1234567890abc"

    def test_conferir(self):
        corpo, ass = _rede.pedido_assinado(self.CHAVE, "status")
        ok, motivo, pedido = agente.conferir(self.CHAVE, corpo, ass)
        self.assertTrue(ok, motivo)
        self.assertEqual(pedido["acao"], "status")
        self.assertFalse(agente.conferir(self.CHAVE, corpo, ass)[0])                  # repetido
        self.assertFalse(agente.conferir("outra-chave-qualquer-123", corpo, ass)[0])  # chave errada
        velho = json.dumps({"acao": "status", "ts": time.time() - 3600, "nonce": "x1"}).encode()
        self.assertIn("velho", agente.conferir(self.CHAVE, velho, _rede.assinar(self.CHAVE, velho))[1])

    def test_servidor_de_verdade(self):
        porta = _porta_livre()
        cfg = {"chave": self.CHAVE, "porta": porta, "permitir_comandos": True, "nome": "teste"}
        original = agente.config
        agente.config = lambda: cfg
        servidor = ThreadingHTTPServer(("127.0.0.1", porta), agente.Atendente)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        try:
            a = {"nome": "PC teste", "ip": "127.0.0.1", "porta": porta, "chave": self.CHAVE, "tipo": "pc"}
            self.assertIn("nome", ap.pc(a, "status"))
            r = ap.pc(a, "rodar", {"comando": "echo oi"})
            self.assertEqual(r.get("saida", "").strip().splitlines()[-1], "oi")
            self.assertIn("assinatura", ap.pc({**a, "chave": "errada-errada-errada-1"}, "status").get("erro", ""))
            cfg["permitir_comandos"] = False
            self.assertIn("não aceita", ap.pc(a, "rodar", {"comando": "echo oi"}).get("erro", ""))
        finally:
            servidor.shutdown()
            servidor.server_close()
            agente.config = original


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    unittest.main()
