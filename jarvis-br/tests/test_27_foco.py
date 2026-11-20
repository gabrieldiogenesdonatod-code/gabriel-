"""
Testes da 2.5 — foco, câmera e ESP32: celular na mão durante o pomodoro,
negociação de distração, câmera do quarto, planta com sede, painel de LED,
luva repulsor e o servidor dos aparelhos. Sem câmera, sem rede de verdade
(só 127.0.0.1) e sem som.
"""
import json
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

import numpy as np

from plugins import _negociacao as N
from tests import TMP


class TestNegociacao(unittest.TestCase):
    def test_proposta_programando(self):
        r = N.propor(5, "YouTube", 20 * 60, "programando", 0, 5, 1000.0)
        self.assertEqual(r["resposta"], "Libero 5 se você terminar essa função primeiro.")
        texto, lib = N.cumprir(r["acordo"], 1100.0)
        self.assertIn("5 minutos de YouTube liberados", texto)
        self.assertTrue(N.liberado(lib, "YouTube", 1200.0))
        self.assertTrue(N.liberado(lib, "youtube", 1200.0))
        self.assertFalse(N.liberado(lib, "Instagram", 1200.0))
        self.assertFalse(N.liberado(lib, "YouTube", 1100.0 + 5 * 60 + 1))

    def test_limites(self):
        self.assertIn("Faltam só", N.propor(5, "YouTube", 6 * 60, "livre", 0, 5, 0)["resposta"])
        self.assertIn("Já liberei 2 vezes", N.propor(5, "YouTube", 20 * 60, "livre", 2, 5, 0)["resposta"])
        self.assertIn("é muito", N.propor(30, "YouTube", 20 * 60, "programando", 0, 5, 0)["resposta"])
        r = N.propor(5, "TikTok", 20 * 60, "livre", 0, 5, 0)
        self.assertEqual(r["acordo"]["condicao"], "tempo")
        self.assertIn("Ainda faltam", N.cumprir(r["acordo"], 60)[0])

    def test_fiado_e_frase_do_celular(self):
        texto, lib, divida = N.fiado(None, "Instagram", 5, 0.0)
        self.assertEqual(divida, 300)
        self.assertIn("fica devendo", texto)
        self.assertEqual(N.frase_celular(12 * 60 - 3), "Senhor, o celular pode esperar mais 12 minutos.")

    def test_pomodoro_cobra_a_divida(self):
        from plugins import pomodoro as P
        falas = []
        with mock.patch.object(P, "avisar", lambda pl, t, e="": falas.append(t)), \
                mock.patch("core.estado_mundo.agora", lambda *a, **k: {"atividade": "programando"}):
            P._estado.clear()
            P._estado.update({"fase": "foco", "fim": time.time() + 20 * 60, "duracao_foco": 1500,
                              "duracao_pausa": 300, "ciclo": 0, "pausado": False})
            self.assertIn("terminar essa função", P.run({"action": "negociar", "o_que": "YouTube", "minutos": 5}))
            self.assertIn("fica devendo", P.run({"action": "fiado"}))
            self.assertEqual(P._estado["divida_s"], 300)
            P._estado["liberado"]["ate"] = time.time() - 1
            P._acordos_no_tempo(None)
        self.assertIn("Combinado é combinado", falas[-1])
        P._estado.clear()
        P._estado["fase"] = None


class TestCelularNaMao(unittest.TestCase):
    def test_mao_encostando_no_celular(self):
        from plugins import _visao_local as V
        cel = [{"nome": "cell phone", "score": 0.7, "caixa": (0.4, 0.3, 0.1, 0.2)}]
        mao_no_cel = [[(0.45, 0.42), (0.5, 0.6)]]
        mao_longe = [[(0.9, 0.9), (0.95, 0.95)]]
        self.assertTrue(V.celular_na_mao_puro(cel, mao_no_cel))
        self.assertFalse(V.celular_na_mao_puro(cel, mao_longe))
        self.assertTrue(V.celular_na_mao_puro(cel, None))                 # sem detector de mãos: erguido e nítido
        self.assertFalse(V.celular_na_mao_puro([{**cel[0], "caixa": (0.4, 0.85, 0.1, 0.1)}], None))
        self.assertEqual(V.onde_na_imagem((0.0, 0.7, 0.2, 0.2)), "à esquerda, embaixo da imagem")
        a = np.zeros((48, 64))
        self.assertFalse(V.mudou(a, a + 2))
        self.assertTrue(V.mudou(a, a + 30))


class TestQuarto(unittest.TestCase):
    def test_onde_esta(self):
        from plugins import objetos_quarto as Q
        Q.ARQ, Q.PASTA = TMP / "objetos_quarto.json", TMP / "quarto"
        img = np.zeros((120, 160, 3), np.uint8)
        resposta = {"objetos": [{"nome": "fone de ouvido", "onde": "em cima da cama"},
                                {"nome": "chave", "onde": "na mesa, ao lado do monitor"}]}
        with mock.patch("plugins._camera_remota.quadro", lambda cam, espera_s=6: (img, "")), \
                mock.patch("plugins._ia.ver_imagem_json", lambda *a, **k: resposta), \
                mock.patch.object(Q, "_c", lambda: {"usar_ia": True, "camera": "0", "objetos": "fone, chave"}):
            achados, erro = Q.olhar()
        self.assertEqual((len(achados), erro), (2, ""))
        self.assertTrue(Q.run({"action": "onde", "objeto": "fone"}).startswith("Vi seu fone de ouvido em cima da cama"))
        self.assertTrue(Q.run({"action": "onde", "objeto": "chaves"}).startswith("Vi sua chave na mesa"))
        self.assertTrue(Q.mesmo_objeto("headset", "fone de ouvido"))
        self.assertEqual(Q.possessivo("óculos"), "seus óculos")


class TestPlantas(unittest.TestCase):
    def test_seca_avisa_e_rega(self):
        from plugins import plantas as P
        P.ARQ = TMP / "plantas.json"
        P.ARQ.unlink(missing_ok=True)
        self.assertEqual(P.porcentagem(2150), 50.0)
        self.assertFalse(P.receber({"id": "sala", "bruto": 1500})["seca"])
        self.assertTrue(P.receber({"id": "sala", "bruto": 2700})["seca"])
        agora = time.time()
        d = P.dados()
        d["plantas"]["sala"]["seca_desde"] = agora - 7 * 3600
        P.gravar_json(P.ARQ, d)
        with mock.patch("plugins._notificar.notificar", lambda *a, **k: True):
            self.assertEqual(P.verificar(agora), ["A planta da sala está com sede: a terra está em 18%."])
            self.assertEqual(P.verificar(agora), [])
            d = P.dados()
            d["plantas"]["sala"]["seca_desde"] = agora - 50 * 3600
            d["plantas"]["sala"]["avisos"]["dia"] = "outro dia"
            P.gravar_json(P.ARQ, d)
            self.assertEqual(P.verificar(agora), ["A planta da sala está seca há 2 dias."])
        self.assertFalse(P.receber({"id": "sala", "bruto": 1450})["seca"])          # regou
        self.assertIn("samambaia", P.run({"action": "nomear", "id": "sala", "nome": "samambaia"}))


class TestPainelELuva(unittest.TestCase):
    def test_letreiro(self):
        from plugins import painel_led as PL
        self.assertEqual(PL.ascii_painel("Goiânia ♪ Matuê — ção"), "Goiania > Matue - cao")
        t = PL.montar("15:42", "Quer Voar - Matuê", "Hoje: 3 vendas, R$ 245", ["Conta de luz vence sexta"], "Oi!")
        self.assertTrue(t.startswith("Oi! * 15:42 * > Quer Voar - Matue"))
        self.assertIn("Aviso: Conta de luz", t)

    def test_luva(self):
        from plugins import luva_repulsor as L
        som = L.som_repulsor()
        self.assertGreater(len(som), 22050 * 0.7)
        feitos = []
        conf = {"ligada": True, "som": False, "repulsor": "fechar_janela", "tapa_direita": "proximo_slide"}
        with mock.patch.object(L, "executar", lambda a: feitos.append(a) or a), mock.patch.object(L, "_c", lambda: conf):
            L._estado["ultimo"] = 0
            self.assertEqual(L.receber({"gesto": "repulsor"})["acao"], "fechar_janela")
            self.assertIn("rápido", L.receber({"gesto": "tapa_direita"})["acao"])
            self.assertFalse(L.receber({"gesto": "voar"})["ok"])
            conf["ligada"] = False
            L._estado["ultimo"] = 0
            self.assertEqual(L.receber({"gesto": "repulsor"})["acao"], "travada")
        self.assertEqual(feitos, ["fechar_janela"])
        self.assertEqual(L._janela_pode_fechar({"titulo": "J.A.R.V.I.S BR", "processo": "python.exe"}),
                         "é a janela do JARVIS")


class TestServidorESP32(unittest.TestCase):
    def test_rotas_e_chave(self):
        from plugins import _esp32 as E
        E.ARQ = TMP / "esp32.json"
        E.registrar_rota("POST", "/esp32/teste", lambda corpo, q: {"eco": corpo.get("x")})
        with mock.patch.object(E, "porta", lambda: 0):
            self.assertEqual(E.iniciar(liberar_firewall=False), "")
        porta = E._srv["servidor"].server_address[1]
        k = E.obter_chave()

        def pedir(caminho, corpo=None, chave=k):
            req = urllib.request.Request(f"http://127.0.0.1:{porta}{caminho}?k={chave}",
                                         data=json.dumps(corpo).encode() if corpo is not None else None,
                                         method="POST" if corpo is not None else "GET")
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())
        try:
            self.assertEqual(pedir("/esp32/teste", {"x": 7}), (200, {"eco": 7}))
            self.assertEqual(pedir("/esp32/teste", {"x": 7}, chave="errada")[0], 401)
            self.assertEqual(pedir("/esp32/ping")[1]["ok"], True)
            self.assertEqual(pedir("/esp32/nada")[0], 404)
            self.assertGreater(E.visto("teste"), 0)
        finally:
            E.parar()


if __name__ == "__main__":
    unittest.main()
