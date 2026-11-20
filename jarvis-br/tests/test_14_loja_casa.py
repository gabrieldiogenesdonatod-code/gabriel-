"""1.4 — loja, casa e extras: calendário comercial, fotos → post, montador de
vídeo, vigia de preço, casa inteligente, "olha isso", personas, boot e capacete.

Nada aqui usa rede, câmera, IA ou ffmpeg (o montador é testado só nas partes
puras); os arquivos vão para pastas temporárias.
"""
import asyncio
import json
import sys
import tempfile
import types
import unittest
import wave
from datetime import date
from pathlib import Path

import tests  # noqa: F401


class TestCalendario(unittest.TestCase):
    def test_datas_moveis(self):
        from plugins import cristal_calendario as cc
        self.assertEqual(cc.pascoa(2026), date(2026, 4, 5))
        self.assertEqual(cc.pascoa(2027), date(2027, 3, 28))
        datas = {d["chave"]: d["data"] for d in cc.datas_do_ano(2026)}
        self.assertEqual(datas["carnaval"], date(2026, 2, 17))
        self.assertEqual(datas["dia_das_maes"], date(2026, 5, 10))
        self.assertEqual(datas["dia_dos_pais"], date(2026, 8, 9))
        self.assertEqual(datas["black_friday"], date(2026, 11, 27))

    def test_proximas_e_tamanhos(self):
        from plugins import cristal_calendario as cc
        prox = cc.proximas(date(2026, 9, 25), 30)
        self.assertEqual(prox[0]["nome"], "Dia das Crianças")
        self.assertEqual(prox[0]["faltam"], 17)
        itens = [{"produto": "Conjunto moletom azul 4", "quantidade": "1"},
                 {"produto": "Conjunto moletom azul 6", "quantidade": "5"},
                 {"produto": "Body bebê RN", "quantidade": "0"}]
        r = cc.tamanhos_acabando(itens, 1)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["baixos"], {"4": 1})


class TestFotos(unittest.TestCase):
    def test_tamanhos(self):
        from plugins.cristal_fotos import separar_tamanho, tamanhos_publicos
        self.assertEqual(separar_tamanho("Conjunto moletom azul 4"), ("Conjunto moletom azul", "4"))
        self.assertEqual(separar_tamanho("Body bebê RN"), ("Body bebê", "RN"))
        self.assertEqual(separar_tamanho("Camiseta tam 10"), ("Camiseta", "10"))
        itens = [{"tamanho": "4", "quantidade": 1}, {"tamanho": "6", "quantidade": 0}, {"tamanho": "8", "quantidade": 1}]
        self.assertEqual(tamanhos_publicos(itens), "Tamanhos 4 e 8 — últimas unidades!")


class TestVideo(unittest.TestCase):
    def test_partes_e_legenda(self):
        from plugins import cristal_video as cv
        self.assertEqual(cv.partes_com_som(6.0, [(2.0, 4.0)]), [(0.0, 2.15), (3.85, 6.0)])
        self.assertEqual(cv.partes_com_som(5.0, []), [(0.0, 5.0)])
        srt = cv.srt_de([(0.0, 2.0, "Olha que lindo esse conjunto de moletom azul para o inverno")])
        self.assertIn("00:00:00,000 --> 00:00:01,000", srt)
        self.assertEqual(srt.count("-->"), 2)


class TestVigiaPreco(unittest.TestCase):
    def test_precos(self):
        from plugins import vigia_preco as vp
        self.assertEqual(vp.valor_br("R$ 1.499,90"), 1499.9)
        self.assertEqual(vp.valor_br("1.499"), 1499.0)
        ld = ('<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer",'
              '"price":"1599.90","priceCurrency":"BRL"}}</script>')
        self.assertEqual(vp.preco_da_pagina(ld), 1599.9)
        self.assertEqual(vp.preco_da_pagina('<meta property="product:price:amount" content="1349.00">'), 1349.0)
        ofertas = [{"titulo": "Placa de vídeo RTX 3060 12GB", "preco": 1699.0},
                   {"titulo": "Suporte para RTX 3060", "preco": 49.0},
                   {"titulo": "RTX 3060 Asus Dual", "preco": 1549.0},
                   {"titulo": "RTX 3060 (anúncio estranho)", "preco": 300.0}]
        self.assertEqual(vp.melhor_oferta(ofertas, "RTX 3060")["preco"], 1549.0)


class TestCasa(unittest.TestCase):
    def test_comandos_falados(self):
        from plugins import casa_inteligente as ci
        self.assertEqual(ci.passo_de_texto("desligar luz do quarto"), ("desligar", "luz do quarto", None))
        self.assertEqual(ci.passo_de_texto("apaga a tomada da tv"), ("desligar", "tomada da tv", None))
        self.assertEqual(ci.passo_de_texto("luz da sala em 40%"), ("brilho", "luz da sala", "40"))
        d = {"aparelhos": [{"nome": "luz do quarto", "tipo": "lampada"}, {"nome": "tomada tv", "tipo": "tomada"},
                           {"nome": "luz sala", "tipo": "lampada"}]}
        self.assertEqual([a["nome"] for a in ci.achar(d, "luzes")], ["luz do quarto", "luz sala"])
        self.assertEqual([a["nome"] for a in ci.achar(d, "quarto")], ["luz do quarto"])
        self.assertEqual(len(ci.achar(d, "tudo")), 3)

    def test_com_tinytuya_falso(self):
        from plugins import casa_inteligente as ci
        feitos = []

        class Dev:
            def __init__(self, i, *a, **k):
                self.i = i

            def set_socketRetryLimit(self, n):
                pass

            def turn_on(self):
                feitos.append(("on", self.i))
                return {}

            def turn_off(self):
                feitos.append(("off", self.i))
                return {}
        falso = types.ModuleType("tinytuya")
        falso.OutletDevice = falso.BulbDevice = Dev
        with tempfile.TemporaryDirectory() as tmp:
            antigo, ci._ARQ = ci._ARQ, Path(tmp) / "casa.json"
            sys.modules["tinytuya"] = falso
            try:
                ci._ARQ.write_text(json.dumps({"aparelhos": [{"nome": "luz do quarto", "id": "a", "chave": "k",
                                                              "tipo": "lampada"}], "cenas": {}}))
                self.assertEqual(ci.executar("luz do quarto", "ligar"), "Liguei luz do quarto.")
                self.assertEqual(feitos, [("on", "a")])
            finally:
                sys.modules.pop("tinytuya", None)
                ci._ARQ = antigo


class TestOlhaIsso(unittest.TestCase):
    def test_explicacao_local(self):
        from plugins import olha_isso as oi
        tb = ('Traceback (most recent call last):\n  File "x.py", line 3, in f\n    a.b\n'
              "AttributeError: 'NoneType' object has no attribute 'b'")
        self.assertTrue(oi.parece_erro(tb))
        self.assertIn("None", oi.explicar_local(tb))
        self.assertIn("linha 3", oi.explicar_local(tb))
        self.assertIn("opencv-python", oi.explicar_local("ModuleNotFoundError: No module named 'cv2'"))
        self.assertFalse(oi.parece_erro("tudo certo por aqui"))
        self.assertEqual(oi._parse_atalho("ctrl+alt+j"), (0x4000 | 0x2 | 0x1, ord("J")))
        self.assertIsNone(oi._parse_atalho("banana+j"))


class TestPersonas(unittest.TestCase):
    def test_troca_por_apelido(self):
        from plugins import _personas, personas
        import memory.config_manager as cm
        salvo = {}
        originais = (cm.save_voice, cm.save_assistant_config, cm.load_api_keys)
        cm.save_voice = lambda v: salvo.update(voz=v)
        cm.save_assistant_config = lambda a, u: salvo.update(nome=a)
        cm.load_api_keys = lambda: {}
        with tempfile.TemporaryDirectory() as tmp:
            antigo, _personas.ARQ = _personas.ARQ, Path(tmp) / "p.json"
            try:
                r = personas.trocar("sexta-feira", reconectar=False)
                self.assertIn("FRIDAY", r)
                self.assertEqual(salvo, {"voz": "Kore", "nome": "FRIDAY"})
                self.assertIn("F.R.I.D.A.Y", _personas.estilo_ativo())
                personas.trocar("jarvis", reconectar=False)
                self.assertEqual(_personas.estilo_ativo(), "")
            finally:
                _personas.ARQ = antigo
                cm.save_voice, cm.save_assistant_config, cm.load_api_keys = originais


class TestBoot(unittest.TestCase):
    def test_som_gerado(self):
        from plugins import boot_cinematico as bc
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(bc.gerar_som(Path(tmp) / "b.wav"))
            with wave.open(str(arq)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth()), (1, 2))
                self.assertGreater(w.getnframes() / w.getframerate(), 3.0)
        self.assertEqual(bc.saudacao(9), "Bom dia")
        self.assertEqual(bc.saudacao(20), "Boa noite")


class TestCapacete(unittest.TestCase):
    def test_rota_websocket(self):
        falso = types.ModuleType("fastapi")
        falso.WebSocket = object
        falso.WebSocketDisconnect = type("WSD", (Exception,), {})
        guardado = sys.modules.get("fastapi")
        sys.modules["fastapi"] = falso
        from plugins import _capacete as cap

        class App:
            def websocket(self, caminho):
                def deco(fn):
                    self.fn = fn
                    return fn
                return deco

        class Srv:
            def __init__(self):
                self._phone_audio_queue = asyncio.Queue(maxsize=10)
                self._command_queue = asyncio.Queue()

            async def broadcast(self, m):
                pass

        class WS:
            def __init__(self, entradas):
                self.scope, self.entradas, self.saida, self.fechado = {"subprotocols": ["arduino"]}, entradas, [], None

            async def accept(self, subprotocol=None):
                self.sub = subprotocol

            async def close(self, code=1000):
                self.fechado = code

            async def send_text(self, t):
                self.saida.append(t)

            async def send_bytes(self, b):
                self.saida.append(len(b))

            async def receive(self):
                await asyncio.sleep(0.01)
                return self.entradas.pop(0) if self.entradas else {"type": "websocket.disconnect"}

        async def cenario():
            app, srv = App(), Srv()
            cap.registrar_rota(app, srv)
            ruim = WS([])
            await app.fn(ruim, chave="errada")
            ws = WS([{"type": "websocket.receive", "bytes": b"\x00\x01" * 256},
                     {"type": "websocket.receive", "text": json.dumps({"tipo": "texto", "texto": "oi"})}])
            asyncio.get_running_loop().call_later(0.005, cap.enviar_audio, srv, b"\x00" * 9600)
            await app.fn(ws, chave=cap.obter_chave())
            return ruim, ws, srv

        with tempfile.TemporaryDirectory() as tmp:
            antigo, cap.ARQ = cap.ARQ, Path(tmp) / "c.json"
            try:
                ruim, ws, srv = asyncio.run(cenario())
            finally:
                cap.ARQ = antigo
                if guardado is not None:
                    sys.modules["fastapi"] = guardado
                else:
                    sys.modules.pop("fastapi", None)
        self.assertEqual(ruim.fechado, 4001)
        self.assertEqual(ws.sub, "arduino")
        self.assertIn(9600, ws.saida)
        self.assertEqual(srv._phone_audio_queue.qsize(), 1)
        self.assertEqual(srv._command_queue.get_nowait(), "oi")


if __name__ == "__main__":
    unittest.main()
