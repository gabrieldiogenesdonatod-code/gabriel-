"""
Testes da 1.5 — Sentinela, ouvido ambiente, ligação, servidores e geofence.

O áudio é sintético (tons e ruído gerados aqui); nada usa câmera, microfone,
internet ou telefone.
"""
import time
import unittest

import numpy as np

import tests  # noqa: F401  (ajusta o caminho e as pastas temporárias)
from plugins import geofence, ligacao, ouvido_ambiente as oa, sentinela, servidores

T = oa.TAXA
_rng = np.random.default_rng(7)


def _tom(f, s, a=0.5):
    t = np.arange(int(s * T)) / T
    return a * np.sin(2 * np.pi * f * t)


def _sil(s):
    return np.zeros(int(s * T))


def _ruido(n, a=0.003):
    return _rng.normal(0, a, n)


def _dong(f, s):
    t = np.arange(int(s * T)) / T
    return 0.4 * np.sin(2 * np.pi * f * t) * np.exp(-t * 3) + 0.15 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 5)


class TestSentinela(unittest.TestCase):
    def test_movimento(self):
        a = np.zeros((60, 80), dtype="uint8")
        b = a.copy()
        b[:30] = 200
        self.assertAlmostEqual(sentinela.movimento(a, b), 0.5, places=2)
        self.assertEqual(sentinela.movimento(a, a), 0.0)
        self.assertEqual(sentinela.movimento(None, b), 0.0)
        c = a.copy()
        c[:30] = 10                                            # mudança pequena de luz não conta
        self.assertEqual(sentinela.movimento(a, c), 0.0)


class TestOuvidoAmbiente(unittest.TestCase):
    def test_alarme_sao_bipes_repetidos(self):
        x = np.concatenate([_sil(.15), _tom(3100, .2), _sil(.15), _tom(3100, .2), _sil(.15), _tom(3100, .2), _sil(.2)])
        x = (x + _ruido(len(x))).astype("float32")
        bipes = oa.bipes(oa.espectro(x))
        self.assertEqual(len(bipes), 3)
        self.assertTrue(oa.eh_alarme(bipes))
        um = (np.concatenate([_sil(.15), _tom(3100, .2), _sil(.4)]) + _ruido(int(.75 * T))).astype("float32")
        self.assertFalse(oa.eh_alarme(oa.bipes(oa.espectro(um))))
        ruido = _rng.normal(0, .1, T).astype("float32")
        self.assertFalse(oa.eh_alarme(oa.bipes(oa.espectro(ruido))))

    def test_som_aprendido(self):
        campainha = np.concatenate([_dong(660, .5), _dong(520, .7)])
        ensino = np.concatenate([_ruido(int(.5 * T), .002), campainha, _ruido(int(.5 * T), .002)]).astype("float32")
        modelo = np.array(oa.aprender_de(ensino), dtype="float32")
        self.assertGreater(len(modelo), 50)                    # só a parte que soa, sem o silêncio
        # a mesma campainha, mais baixa e com outro ruído de fundo, em outra posição
        janela = np.concatenate([_ruido(int(1.1 * T), .01), 0.5 * campainha, _ruido(int(.8 * T), .01)])
        self.assertGreaterEqual(oa.parecido(oa.log_mel(oa.espectro(janela.astype("float32"))), modelo), 0.70)
        outro = np.concatenate([_ruido(int(1.1 * T), .01), _dong(880, .3), _dong(1200, .3), _dong(990, .5),
                                _ruido(int(.8 * T), .01)])
        self.assertLess(oa.parecido(oa.log_mel(oa.espectro(outro.astype("float32"))), modelo), 0.70)
        self.assertIsNone(oa.aprender_de(_ruido(T, .002).astype("float32")))      # nada alto para aprender

    def test_barulho_forte(self):
        quieto = _ruido(int(1.5 * T), .002)
        estouro = np.concatenate([quieto, _rng.normal(0, .5, int(.15 * T)), quieto]).astype("float32")
        esp = oa.espectro(estouro)
        energia = 10 * np.log10(np.square(esp).sum(axis=1) + 1e-9)
        fundo = float(np.percentile(energia, 20))
        self.assertTrue(oa.barulho_forte(esp, fundo))
        clique = np.concatenate([quieto, _rng.normal(0, .5, int(.02 * T)), quieto]).astype("float32")
        self.assertFalse(oa.barulho_forte(oa.espectro(clique), fundo))          # tecla do teclado
        grave = np.concatenate([quieto, _tom(120, .3, .9), quieto]).astype("float32")
        self.assertFalse(oa.barulho_forte(oa.espectro(grave), fundo))           # porta batendo longe, música


class _InterpretadorFalso:
    """Imita o tflite Interpreter do YAMNet: entrada (1, 15600), saída (1, 521)."""

    def __init__(self, forma, indice_alto):
        self.forma, self.alto, self.recebido = forma, indice_alto, None

    def get_input_details(self):
        return [{"index": 0, "shape": np.array(self.forma)}]

    def get_output_details(self):
        return [{"index": 1}]

    def set_tensor(self, _i, valor):
        self.recebido = valor

    def invoke(self):
        pass

    def get_tensor(self, _i):
        notas = np.zeros((1, 521), dtype="float32")
        notas[0, self.alto] = 0.9
        return notas


class TestYamnet(unittest.TestCase):
    def test_rotulos_com_virgula(self):
        self.assertEqual(oa.ler_rotulos("Speech\nSmoke detector, smoke alarm\n", False)[1],
                         "Smoke detector, smoke alarm")
        csv = 'index,mid,display_name\n0,/m/09x0r,Speech\n1,/m/0ytgt,"Child speech, kid speaking"\n'
        self.assertEqual(oa.ler_rotulos(csv, True), ["Speech", "Child speech, kid speaking"])

    def test_reconhece_arquivo_tflite(self):
        self.assertTrue(oa.eh_tflite(b"\x1c\x00\x00\x00TFL3" + bytes(200_000)))
        self.assertFalse(oa.eh_tflite(b"<html>Not Found</html>" + bytes(200_000)))     # página de erro
        self.assertFalse(oa.eh_tflite(b"\x1c\x00\x00\x00TFL3"))                         # cortado

    def test_classificar_com_modelo_falso(self):
        rotulos = [f"classe {i}" for i in range(521)]
        rotulos[349] = "Doorbell"
        rotulos[393] = "Smoke detector, smoke alarm"
        guardado = oa._cache.get("yamnet", "ausente")
        try:
            for forma in ([1, 15600], [15600]):
                falso = _InterpretadorFalso(forma, 393)
                oa._cache["yamnet"] = (falso, rotulos)
                achados = oa.classificar_yamnet(np.zeros(8000, dtype="float32"))     # menos que 0,975 s
                self.assertEqual([n for n, _ in achados], ["um alarme de incêndio"])
                self.assertEqual(list(falso.recebido.shape), forma)
            oa._cache["yamnet"] = (_InterpretadorFalso([1, 15600], 349), rotulos)
            self.assertEqual(oa.classificar_yamnet(np.zeros(20000, dtype="float32"))[0][0], "a campainha")
        finally:
            if guardado == "ausente":
                oa._cache.pop("yamnet", None)
            else:
                oa._cache["yamnet"] = guardado


class TestLigacao(unittest.TestCase):
    def test_roteiro_escapa_e_repete(self):
        x = ligacao.twiml("Alarme <casa> & loja")
        self.assertIn("&lt;casa&gt; &amp; loja", x)
        self.assertEqual(x.count("<Say"), 2)
        self.assertIn('language="pt-BR"', x)

    def test_limites(self):
        guardado = dict(ligacao._controle)
        try:
            ligacao._controle.update(ultima=0.0, dia="", hoje=0)
            agora = time.time()
            self.assertTrue(ligacao.pode_ligar(agora))
            ligacao._controle.update(ultima=agora - 60, hoje=1)
            self.assertFalse(ligacao.pode_ligar(agora))        # 10 min entre ligações
            ligacao._controle.update(ultima=agora - 700, hoje=5)
            self.assertFalse(ligacao.pode_ligar(agora))        # no máximo 5 por dia
            ligacao._controle.update(hoje=4)
            self.assertTrue(ligacao.pode_ligar(agora))
        finally:
            ligacao._controle.clear()
            ligacao._controle.update(guardado)


class TestServidores(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(servidores.normalizar("meusite.com.br"), {"tipo": "http", "url": "https://meusite.com.br"})
        self.assertEqual(servidores.normalizar("http://x.com/saude"), {"tipo": "http", "url": "http://x.com/saude"})
        self.assertEqual(servidores.normalizar("1.2.3.4:22"), {"tipo": "tcp", "host": "1.2.3.4", "porta": 22})
        self.assertEqual(servidores.normalizar("https://meuvps.com/x", 2222),
                         {"tipo": "tcp", "host": "meuvps.com", "porta": 2222})


class TestGeofence(unittest.TestCase):
    def test_interpretar(self):
        self.assertEqual(geofence.interpretar("chegou abc123", "abc123"), "chegou")
        self.assertEqual(geofence.interpretar(" saiu abc123 ", "abc123"), "saiu")
        self.assertIsNone(geofence.interpretar("chegou errada", "abc123"))
        self.assertIsNone(geofence.interpretar("apaga tudo abc123", "abc123"))
        self.assertIsNone(geofence.interpretar("", "abc123"))


if __name__ == "__main__":
    unittest.main()
