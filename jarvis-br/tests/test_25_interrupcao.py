"""
Testes da 2.4.1 — interromper o JARVIS (core/interrupcao.py), a correção do
core/echo.py (bloco do microfone em 2 dimensões) e o plugin `interrupcao`.
Os sinais são sintéticos: vogais com formantes, eco atrasado, estalos de tecla.
"""
import unittest
from unittest import mock

import numpy as np

from core import interrupcao as I
from core.echo import EchoGuard, band_energies

LEVEL_FLOOR, LEVEL_FULL = 60.0, 2600.0          # os mesmos do _pcm_level do main.py


def nivel(x):
    rms = float(np.sqrt(np.mean(np.asarray(x, np.float32) ** 2)))
    return 0.0 if rms <= LEVEL_FLOOR else min(1.0, (rms - LEVEL_FLOOR) / (LEVEL_FULL - LEVEL_FLOOR))


def vogal(t, f0, formantes, amp, silaba=4.0):
    s = np.zeros_like(t)
    for h in range(1, int(4000 / f0)):
        f = h * f0
        s += (sum(np.exp(-((f - F) / 120.0) ** 2) for F in formantes) + 0.05) * np.sin(2 * np.pi * f * t + h)
    s *= 0.55 + 0.45 * np.sin(2 * np.pi * silaba * t) ** 2
    return amp * s / (np.sqrt(np.mean(s ** 2)) + 1e-9)


def jarvis(t):
    vogais = [((700, 1200), 130), ((300, 2300), 125), ((500, 900), 135), ((450, 1800), 128)]
    out = np.zeros_like(t)
    idx = ((t // 0.4).astype(int)) % len(vogais)
    for k, (form, f0) in enumerate(vogais):
        m = idx == k
        if m.any():
            out[m] = vogal(t[m], f0, form, 2200.0)
    return out


def simular(ganho_eco, voz_amp=0.0, inicio_voz=3.0, dur=6.0, teclado=False, seed=0):
    """Momento em que a voz cortou o JARVIS (None = não cortou)."""
    rng = np.random.default_rng(seed)
    guarda, det = EchoGuard(), I.DetectorVoz()
    for i in range(40):                                        # 2,5 s com o JARVIS calado (fundo)
        det.ambiente(nivel(rng.normal(0, 40, 1024)))
    prox, corte = 0.0, None
    for i in range(int(dur * 16000 / 1024)):
        t0 = i * 1024 / 16000.0
        while prox <= t0 + 0.3:
            ts = prox + np.arange(4800) / 24000.0
            pcm = jarvis(ts)
            guarda.note_output(pcm, 24000, nivel(pcm), when=prox)
            prox += 0.2
        t = t0 + np.arange(1024) / 16000.0
        b = ganho_eco * jarvis(t - 0.05) + rng.normal(0, 40, t.size)
        if teclado and rng.random() < 0.5:
            p = rng.integers(0, 1000)
            b[p:p + 20] += rng.normal(0, 6000, 20)
        if voz_amp and t0 >= inicio_voz:
            b = b + vogal(t, 230, (650, 1100), voz_amp)
        b = np.clip(b, -32000, 32000).astype(np.int16).reshape(-1, 1)     # como o sounddevice entrega
        v = I.eh_voz(guarda, det, b, 16000, nivel(b), nivel(jarvis(t)), agora=t0)
        if det.bloco(b.tobytes(), v, guarda.required_blocks, agora=t0) == "interromper" and corte is None:
            corte = t0
    return corte


class TestEstado(unittest.TestCase):
    def test_esc_depois_da_resposta_inteira_nao_cala_a_proxima(self):
        """O bug: ESC depois do fim do turno fazia a PRÓXIMA resposta sair muda."""
        e = I.EstadoInterrupcao()
        self.assertFalse(e.audio_chegou(0.0))                 # resposta A chega inteira…
        self.assertFalse(e.fim_do_turno())                    # …e o turno fecha antes de acabar de tocar
        self.assertFalse(e.pedir(1.0))                        # ESC: nada mais de A vai chegar
        self.assertFalse(e.audio_chegou(2.0))                 # a resposta B TOCA

    def test_esc_com_resposta_chegando(self):
        e = I.EstadoInterrupcao()
        e.audio_chegou(0.0)
        ep = e.epoca
        self.assertTrue(e.pedir(0.5))
        self.assertGreater(e.epoca, ep)                        # o áudio na fila fica velho
        self.assertTrue(e.audio_chegou(0.6))                   # resto de A: fora
        self.assertTrue(e.fim_do_turno())                      # fim da resposta cortada
        self.assertFalse(e.audio_chegou(1.0))                  # B toca

    def test_servidor_interrompeu_e_seguranca(self):
        e = I.EstadoInterrupcao()
        e.audio_chegou(0.0)
        e.pedir(0.1)
        ep = e.epoca
        self.assertTrue(e.servidor_interrompeu())
        self.assertGreater(e.epoca, ep)
        self.assertFalse(e.audio_chegou(0.2))
        e.pedir(1.0)                                          # descartando de novo…
        self.assertFalse(e.vencido(3.0))
        self.assertTrue(e.vencido(5.5))                       # …e o servidor sumiu: volta ao normal
        self.assertFalse(e.descartando)


class TestSaida(unittest.TestCase):
    def test_escrever_cortavel(self):
        escritos, ep = [], {"v": 7}

        def escrever(d):
            escritos.append(len(d))
            if len(escritos) == 2:
                ep["v"] = 8                                    # ESC no meio do lote
        self.assertFalse(I.escrever_cortavel(escrever, b"x" * 9600, lambda: ep["v"], 7))
        self.assertEqual(escritos, [1920, 1920])               # parou em 80 ms, não em 200
        self.assertTrue(I.escrever_cortavel(lambda d: None, b"x" * 9600, lambda: 1, 1))

    def test_sem_descarte_na_placa(self):
        """2.7.3: o abort()+start() da placa (que fechava o JARVIS no botão INTERROMPER) não existe mais."""
        self.assertFalse(hasattr(I, "descartar_saida"))


class TestDetector(unittest.TestCase):
    def test_blocos_seguidos_preroll_e_envio(self):
        d = I.DetectorVoz()
        for k in range(20):                                    # 1,3 s antigos: não podem ir junto
            d.bloco(b"velho", False, 5, agora=k * 0.064)
        acoes = [d.bloco(b"voz", True, 5, agora=10.0 + k * 0.064) for k in range(5)]
        self.assertEqual(acoes, ["nada"] * 4 + ["interromper"])
        self.assertEqual(d.esvaziar(agora=10.3), [b"voz"] * 5)
        self.assertEqual(d.bloco(b"x", False, 5, agora=10.4), "enviar")      # já cortou: manda direto
        self.assertEqual(d.bloco(b"x", True, 5, agora=12.5), "nada")

    def test_fundo_e_fone(self):
        d = I.DetectorVoz()
        self.assertEqual(d.piso_voz, I.NIVEL_VOZ_FONE)
        for _ in range(40):
            d.ambiente(0.17)                                   # TV ligada
        self.assertAlmostEqual(d.piso_voz, 0.38, places=2)
        self.assertFalse(d.sem_eco)
        for _ in range(35):
            d.observar(0.17, 0.8)                              # o JARVIS fala e o microfone só ouve a TV
        self.assertTrue(d.sem_eco)                             # = fone de ouvido
        d.zerar()
        self.assertTrue(d.sem_eco)                             # a fala nova não esquece isso

    def test_continuo(self):
        t = np.arange(1024) / 16000.0
        self.assertTrue(I.continuo(vogal(t, 200, (500, 1500), 2000.0)))
        estalo = np.random.default_rng(1).normal(0, 30, 1024)
        estalo[400:420] += 9000
        self.assertFalse(I.continuo(estalo))


class TestEco(unittest.TestCase):
    def test_bloco_do_microfone_em_duas_dimensoes(self):
        """O sounddevice entrega (1024, 1): antes isso dava IndexError e a voz era jogada fora."""
        x = (np.random.default_rng(0).normal(0, 1000, 1024)).astype(np.int16)
        np.testing.assert_allclose(band_energies(x.reshape(-1, 1), 16000), band_energies(x, 16000), rtol=1e-5)
        g = EchoGuard()
        t24 = np.arange(4800) / 24000.0
        for k in range(20):
            g.note_output(jarvis(t24 + 0.2 * k), 24000, 0.8, when=0.2 * k)
        for k in range(20):                                    # aquece com eco puro
            t = 4.0 + k * 0.064 + np.arange(1024) / 16000.0
            b = (0.3 * jarvis(t)).astype(np.int16).reshape(-1, 1)
            g.is_user_speech(b, 16000, nivel(b), when=3.9)
        t = 5.4 + np.arange(1024) / 16000.0
        voz = (vogal(t, 230, (650, 3300), 2500.0)).astype(np.int16).reshape(-1, 1)
        self.assertTrue(g.is_user_speech(voz, 16000, nivel(voz), when=3.9))

    def test_voz_alta_nao_vira_eco(self):
        g = EchoGuard()
        g._gain, g._seen, g._floor, g._head = 0.3, 50, 0.12, 0.3
        g._residuals = [0.12] * 30
        t24 = np.arange(4800) / 24000.0
        saida = jarvis(t24)
        g.note_output(saida, 24000, nivel(saida), when=0.0)
        t16 = np.arange(1024) / 16000.0
        alto = (jarvis(t16) * 0.9).astype(np.int16)           # o mesmo som, bem mais alto que o eco de sempre
        for _ in range(15):
            g.is_user_speech(alto, 16000, nivel(alto), when=0.1)
        self.assertLess(g.gain, 0.35)                          # não ensina o ganho (antes subia para ~0,9)
        normal = (jarvis(t16) * 0.25).astype(np.int16)         # eco do tamanho de sempre: ensina
        for _ in range(15):
            g.is_user_speech(normal, 16000, nivel(normal), when=0.1)
        self.assertNotAlmostEqual(g.gain, 0.3, places=3)


class TestVozSintetica(unittest.TestCase):
    def test_fone_corta_rapido(self):
        corte = simular(0.0, voz_amp=1600.0)
        self.assertIsNotNone(corte)
        self.assertLess(corte - 3.0, 0.5)

    def test_eco_sozinho_nao_corta(self):
        for ganho in (0.05, 0.3, 1.0, 1.5):
            self.assertIsNone(simular(ganho), f"cortou só com o eco (ganho {ganho})")

    def test_teclado_nao_corta(self):
        for ganho in (0.0, 0.3):
            self.assertIsNone(simular(ganho, teclado=True), f"cortou com o teclado (ganho {ganho})")

    def test_caixa_de_som_com_voz_alta(self):
        corte = simular(0.3, voz_amp=3000.0)
        self.assertIsNotNone(corte)
        self.assertGreaterEqual(corte, 3.0)


class TestPluginEAtalho(unittest.TestCase):
    def test_atalho(self):
        from core import hotkey
        self.assertEqual(hotkey.chord_label(I.ATALHO), "Ctrl+Alt+P")
        self.assertTrue(all(k in hotkey._VK for k in I.ATALHO))

    def test_plugin(self):
        from plugins import interrupcao as P

        class App:
            _interromper_por_voz = True
            _atalho_intr = object()
        salvos = []
        app = App()
        with mock.patch.object(P, "_app", lambda: app), mock.patch.object(P, "salvar_cfg",
                                                                            lambda ns, v: salvos.append((ns, v))):
            self.assertIn("desligada", P.run({"action": "voz", "valor": "desligar"}))
            self.assertFalse(app._interromper_por_voz)
            self.assertIn("falar por cima está DESLIGADO", P.run({"action": "status"}))
            self.assertIn("Ctrl+Alt+P", P.run({"action": "status"}))
            self.assertIn("ligada", P.run({"action": "voz", "valor": "ligar"}))
        self.assertEqual(salvos, [("interrupcao", {"por_voz": False}), ("interrupcao", {"por_voz": True})])


if __name__ == "__main__":
    unittest.main()
