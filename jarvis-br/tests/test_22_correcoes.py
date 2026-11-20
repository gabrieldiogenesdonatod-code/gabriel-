"""
Testes da 2.2 — orçamento de ferramentas, tela do QR do WhatsApp, tela
"Tocando agora", ideias novas de música e tela ao vivo.
"""
import json
import time
import unittest
import urllib.request
from datetime import datetime
from unittest import mock

import tests
from core import orcamento_ferramentas as O
from plugins import _arcade, _spotify as S, _whatsapp as W, musica as M, tela_ao_vivo


def decl(nome, props=("action",)):
    return {"name": nome, "description": f"faz {nome}", "parameters": {"type": "OBJECT",
            "properties": {p: {"type": "STRING", "description": "a | b"} for p in props}}}


class TestOrcamento(unittest.TestCase):
    def test_dividir(self):
        decls = [decl("nucleo")] + [decl(f"p{i}") for i in range(10)] + [decl("musica")]
        mantidas, extras = O.dividir(decls, 5, uso={"p7": 9, "p3": 4}, protegidas={"nucleo"})
        nomes = [O.nome_de(d) for d in mantidas]
        self.assertEqual(len(mantidas), 4)                                       # + 1 vaga da ferramenta de apoio
        self.assertEqual(set(nomes), {"nucleo", "musica", "p7", "p3"})        # núcleo, fixa e as mais usadas
        self.assertEqual(len(extras), 8)
        self.assertEqual(O.dividir(decls, 0)[1], [])                           # 0 = sem limite
        self.assertEqual(O.dividir(decls, 50)[1], [])

    def test_apoio_e_desembrulhar(self):
        d = O.declaracao_apoio([decl("quiz_geek", ("action", "tema"))])
        self.assertEqual(d["name"], O.NOME_APOIO)
        self.assertIn("quiz_geek(action, tema)", d["description"])
        self.assertEqual(O.desembrulhar(O.NOME_APOIO, {"nome": "quiz_geek", "parametros": '{"tema": "anime"}'}),
                         ("quiz_geek", {"tema": "anime"}))
        self.assertEqual(O.desembrulhar(O.NOME_APOIO, {"nome": "roleta", "parametros": "sortear"}),
                         ("roleta", {"action": "sortear"}))
        self.assertEqual(O.desembrulhar("musica", {"action": "tocar"}), ("musica", {"action": "tocar"}))

    def test_projeto_real_cabe(self):
        from pathlib import Path

        from core.action_loader import discover_actions
        from core.plugin_loader import discover_plugins
        a = discover_actions(tests.RAIZ / "actions", set(), lambda m: None)
        p = discover_plugins(Path(tests.RAIZ / "plugins"), set(), lambda m: None)
        decls = a.get_tool_declarations() + p.get_tool_declarations()
        mantidas, extras = O.dividir(decls, O.LIMITE_PADRAO, protegidas=set(a.names()))
        self.assertLessEqual(len(mantidas) + 1, O.LIMITE_PADRAO)
        self.assertTrue(extras)
        nomes = {O.nome_de(d) for d in mantidas}
        for fixa in ("musica", "whatsapp_jarvis", "aparelhos", "controle_pc"):
            self.assertIn(fixa, nomes)


class TestMusicaNova(unittest.TestCase):
    def setUp(self):
        from plugins import _gosto
        self._g = _gosto.ARQ
        _gosto.ARQ = tests.TMP / "gosto_22.json"                    # nada do teste vai para o seu perfil de gosto

    def tearDown(self):
        from plugins import _gosto
        _gosto.ARQ = self._g

    def test_estado_spotify(self):
        r = {"is_playing": True, "progress_ms": 1000, "shuffle_state": True, "repeat_state": "track",
             "device": {"name": "PC", "volume_percent": 40},
             "item": {"name": "Impossível", "id": "x", "uri": "spotify:track:x", "duration_ms": 200000,
                      "artists": [{"name": "Kaiser"}, {"name": "Outro"}], "album": {"name": "A", "images": [{"url": "u"}]}}}
        e = M.ler_estado_spotify(r)
        self.assertEqual((e["titulo"], e["artistas"], e["capa"], e["volume"], e["aleatorio"], e["repetir"]),
                         ("Impossível", "Kaiser, Outro", "u", 40, True, "track"))
        self.assertTrue(M.ler_estado_spotify(None)["vazio"])

    def test_humor_e_despertador(self):
        self.assertEqual(M.busca_do_humor("quero focar"), "foco concentração lofi")
        self.assertEqual(M.busca_do_humor("bora treinar", ["Kaiser"]), "treino academia rap pesado Kaiser")
        base = datetime(2026, 11, 4, 20, 0).timestamp()
        self.assertEqual(datetime.fromtimestamp(M.proximo_disparo("07:30", base)), datetime(2026, 11, 5, 7, 30))
        self.assertEqual(datetime.fromtimestamp(M.proximo_disparo("21:00", base)), datetime(2026, 11, 4, 21, 0))
        arq = M.ARQ_ALARMES
        M.ARQ_ALARMES = tests.TMP / "alarmes_t.json"
        try:
            self.assertIn("às 07:30 com Kaiser", M.despertador("7h30", "Kaiser"))
            self.assertEqual(M.alarmes()[0]["pedido"], "Kaiser")
            self.assertIn("cancelado", M.despertador("", "cancelar"))
            self.assertEqual(M.alarmes(), [])
            self.assertIn("Que horas", M.despertador("25", ""))
        finally:
            M.ARQ_ALARMES = arq

    def test_comandos_da_tela(self):
        chamadas = []
        with mock.patch.object(S, "conectado", lambda: True), \
                mock.patch.object(S, "api", lambda m, c, p=None, corpo=None: chamadas.append((m, c, p)) or {}):
            self.assertTrue(M.comando_player("volume", {"valor": 130})["ok"])
            self.assertTrue(M.comando_player("aleatorio", {"valor": True})["ok"])
            self.assertFalse(M.comando_player("xyz", {})["ok"])
        self.assertEqual(chamadas, [("PUT", "/me/player/volume", {"volume_percent": 100}),
                                    ("PUT", "/me/player/shuffle", {"state": "true"})])
        with mock.patch.object(S, "conectado", lambda: True), \
                mock.patch.object(S, "api", side_effect=S.ErroSpotify(403, "x")):
            self.assertEqual(M.comando_player("proxima", {}), {"ok": False, "erro": "precisa de Spotify Premium"})


class TestPaginasLocais(unittest.TestCase):
    def setUp(self):
        self.url = _arcade.iniciar()
        self.base = self.url.split("/?")[0]

    def tearDown(self):
        _arcade.parar()

    def _get(self, caminho):
        with urllib.request.urlopen(f"{self.base}{caminho}{'&' if '?' in caminho else '?'}t={_arcade.TOKEN}", timeout=10) as r:
            return r.read()

    def test_paginas_e_apis(self):
        self.assertIn(b"WHATSAPP DO J.A.R.V.I.S", self._get("/whatsapp"))
        self.assertIn(b"TOCANDO AGORA", self._get("/player"))
        with mock.patch.object(W, "estado_para_tela", lambda: {"estado": "qr", "qr": "data:x", "etapa": "ligada"}):
            self.assertEqual(json.loads(self._get("/api/whatsapp"))["estado"], "qr")
        with mock.patch.object(M, "estado_player", lambda: {"servico": "spotify", "titulo": "Impossível"}):
            self.assertEqual(json.loads(self._get("/api/musica"))["titulo"], "Impossível")
        with mock.patch.object(M, "buscar_player", lambda q: {"itens": [{"nome": q}]}):
            self.assertEqual(json.loads(self._get("/api/musica/buscar?q=kaiser"))["itens"][0]["nome"], "kaiser")

    def test_estado_whatsapp_sem_ponte(self):
        with mock.patch.object(W, "rodando", lambda: False):
            e = W.estado_para_tela()
        self.assertEqual(e["estado"], "desligado")
        self.assertIn("navegador", e)


class TestTelaAoVivo(unittest.TestCase):
    def test_sem_jarvis(self):
        with mock.patch.object(tela_ao_vivo, "_app", lambda: None):
            self.assertIn("só funciona com o JARVIS aberto", tela_ao_vivo.run({"action": "ligar"}))

    def test_liga_e_desliga(self):
        pedidos = []

        class App:
            _tela_viva = {"ate": time.time() + 300, "enviados": 12}

            def tela_ao_vivo(self, ligar, minutos=10, intervalo_s=1.0):
                pedidos.append((ligar, minutos))
                return ""
        with mock.patch.object(tela_ao_vivo, "_app", App), mock.patch.object(tela_ao_vivo, "registrar", lambda *a: None):
            self.assertIn("[TELA AO VIVO] Ligado por 60 minutos", tela_ao_vivo.run({"action": "ligar", "minutos": 999}))
            self.assertIn("12 quadros", tela_ao_vivo.run({"action": "status"}))
            self.assertEqual(tela_ao_vivo.run({"action": "desligar"}), "Parei de olhar a tela.")
        self.assertEqual(pedidos, [(True, 60.0), (False, 10)])


if __name__ == "__main__":
    unittest.main()
