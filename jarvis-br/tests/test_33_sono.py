"""
Testes da 2.8 — modo dormir (core/sono.py + plugins/modo_dormir.py) e as correções.

O JARVIS dorme sem a palavra de ativação, guarda os avisos, só o urgente passa,
volta dormindo depois de reiniciar, acorda com duas palmas / "Jarvis, acorda" /
hora marcada, volta a dormir se acordar de madrugada; boa noite, bom dia,
despertador (toca uma vez só), soneca, cochilo, ciclos, diário do sono, sons e
respiração. Sem Gemini, sem placa de som e sem o main.py: um "app" falso faz o
papel do JarvisLive.
"""
import ast
import io
import sys
import time
import tokenize
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import numpy as np

from core import sono
from plugins import modo_dormir as M
from tests import RAIZ, TMP

SR = 16000
_rng = np.random.default_rng(11)


# ── sinais sintéticos ────────────────────────────────────────────────────────
def _palma(amp=18000):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    return (_rng.standard_normal(n) * np.exp(-t / 0.012) * amp
            + _rng.standard_normal(n) * np.exp(-t / 0.08) * amp * 0.04)


def _batida(amp=20000):
    t = np.arange(int(0.25 * SR)) / SR
    return np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.03) * amp


def _tecla(amp=9000):
    t = np.arange(int(0.06 * SR)) / SR
    return _rng.standard_normal(len(t)) * np.exp(-t / 0.004) * amp


def _fala(seg=1.5, amp=7000):
    t = np.arange(int(seg * SR)) / SR
    env = np.clip(np.sin(2 * np.pi * 4 * t), 0, None) ** 0.6
    voz = sum(np.sin(2 * np.pi * f * t) / (k + 1) for k, f in enumerate([140, 280, 420, 560, 700, 900, 1300]))
    return voz * env * amp / 3


def _montar(total, eventos, fundo=60):
    x = _rng.standard_normal(int(total * SR)) * fundo
    for t0, s in eventos:
        i = int(t0 * SR)
        x[i:i + len(s)] += s[:len(x) - i]
    return np.clip(x, -32768, 32767).astype(np.int16)


def _disparos(x) -> int:
    d = sono.DetectorPalmas()
    return sum(bool(d.bloco(x[i:i + 1024].reshape(-1, 1))) for i in range(0, len(x) - 1023, 1024))


class AppFalso:
    """Faz o papel do JarvisLive do main.py: dorme e acorda pelo core/sono e chama os plugins."""

    def __init__(self):
        self._is_speaking = False
        self.acordou = []

    def sleep(self, reason="", manual=False, ate=0.0, rotina=False, alarme=False):
        sono.dormir(reason, ate=ate, rotina=rotina, alarme=alarme)

    def wake(self, reason=""):
        info = sono.acordar(reason)
        self.acordou.append(reason)
        if info:
            sono.avisar_ouvintes(info)

    def _como_acordar(self):
        return sono.como_acordar(palmas=True)


class _Base(unittest.TestCase):
    def setUp(self):
        sono.ARQ = TMP / "sono_estado.json"
        sono.limpar()
        sono._ultimo.update(acordou=0.0, motivo="")
        M.ARQ = TMP / "modo_dormir.json"
        M.ARQ.unlink(missing_ok=True)
        sono.ao_acordar(M._ao_acordar, chave="modo_dormir")       # o carregador pode ter trocado o módulo
        padroes = {f["key"]: f["default"] for f in M.PLUGIN_SETTINGS["fields"]}
        self.cfg = dict(padroes)
        self._p = [mock.patch.object(M, "_c", lambda: self.cfg),
                   mock.patch.object(M, "plugin_ligado", lambda n: True),
                   mock.patch.object(M, "_app", lambda: None)]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()
        sono.limpar()


# ── core/sono.py ─────────────────────────────────────────────────────────────
class TestEstado(_Base):
    def test_dorme_guarda_e_acorda(self):
        ate = time.time() + 3600
        sono.dormir("boa noite", ate=ate, rotina=True, alarme=True)
        self.assertTrue(sono.dormindo())
        self.assertTrue(sono.segurar("[DOWNLOAD] Diga ao usuário, em UMA frase curta e no idioma da conversa: "
                                     "o filme baixou. Não chame nenhuma ferramenta."))
        self.assertTrue(sono.segurar("[DOWNLOAD] Diga ao usuário, em UMA frase curta e no idioma da conversa: "
                                     "o filme baixou. Não chame nenhuma ferramenta."))      # repetido: 1 só
        self.assertFalse(sono.segurar("[SENTINELA] alguém desconhecido na câmera"))
        self.assertEqual([r["texto"] for r in sono.estado()["recados"]], ["o filme baixou."])
        info = sono.acordar("duas palmas", agora=ate - 600)
        self.assertFalse(sono.dormindo())
        self.assertTrue(info["rotina"] and info["tem_alarme"])
        self.assertFalse(info["alarme"])                 # acordou ANTES da hora: o despertador não tocou
        self.assertEqual(len(info["recados"]), 1)
        self.assertIsNone(sono.acordar("de novo"))
        self.assertEqual(sono.ultimo_acordar()["motivo"], "duas palmas")

    def test_pela_hora_e_despertador(self):
        sono.dormir("cochilo", ate=time.time() - 1, alarme=True)
        self.assertTrue(sono.deve_acordar())
        self.assertEqual(sono.motivo_da_hora(), "despertador")
        info = sono.acordar(sono.motivo_da_hora())
        self.assertTrue(info["alarme"] and info["pela_hora"])
        sono.dormir("pedido")                            # sem hora: só quando chamarem
        self.assertFalse(sono.deve_acordar())
        self.assertEqual(sono.motivo_da_hora(), "hora de acordar")
        self.assertTrue(sono.acordar("despertador")["alarme"])     # o plugin acordou pelo despertador dele

    def test_volta_dormindo_depois_de_reiniciar(self):
        agora = time.time()
        sono.dormir("boa noite", ate=agora + 3600, rotina=True, alarme=True)
        sono.segurar("[AVISO] Diga ao usuário, em UMA frase curta e no idioma da conversa: x. Não chame nenhuma "
                     "ferramenta.")
        sono._estado.update(sono._vazio())               # "fechou o programa"
        e = sono.restaurar(agora + 60)
        self.assertTrue(e and e["dormindo"] and e["rotina"] and e["alarme"])
        self.assertEqual(len(e["recados"]), 1)
        # despertador que passou faz mais de 3 h (PC desligado): não volta dormindo
        sono.dormir("boa noite", ate=agora - 4 * 3600)
        sono._estado.update(sono._vazio())
        self.assertIsNone(sono.restaurar(agora))
        self.assertFalse(sono.ARQ.exists())
        # sem hora marcada: só se reiniciar em até 6 h
        sono.dormir("pedido", agora=agora - 7 * 3600)
        sono._estado.update(sono._vazio())
        self.assertIsNone(sono.restaurar(agora))

    def test_volta_a_dormir_de_madrugada(self):
        agora = time.time()
        sono.voltar_a_dormir(120, ate=agora + 3 * 3600, rotina=True, alarme=True, agora=agora)
        self.assertIsNone(sono.retorno_pendente(agora + 60, 200))      # cedo demais
        self.assertIsNone(sono.retorno_pendente(agora + 130, 30))      # alguém falou há pouco
        r = sono.retorno_pendente(agora + 130, 130)
        self.assertTrue(r and r["rotina"] and r["alarme"])
        self.assertIsNone(sono.retorno_pendente(agora + 140, 140))     # uma vez só
        sono.voltar_a_dormir(120, ate=agora + 100, agora=agora)
        self.assertIsNone(sono.retorno_pendente(agora + 130, 130))     # já passou da hora: fica acordado

    def test_urgente_e_texto_do_aviso(self):
        self.assertTrue(sono.eh_urgente("[SENTINELA] Diga ao usuário…"))
        self.assertTrue(sono.eh_urgente("[DESPERTADOR] Dê bom dia"))
        self.assertTrue(sono.eh_urgente("[CRÍTICO] temperatura"))
        self.assertTrue(sono.eh_urgente("[AVISO] Diga ao usuário, em UMA frase curta e no idioma da conversa: "
                                        "fumaça na cozinha. Não chame nenhuma ferramenta."))
        self.assertFalse(sono.eh_urgente("[DOWNLOAD] Diga ao usuário, em UMA frase curta e no idioma da conversa: "
                                         "a internet caiu. Não chame nenhuma ferramenta."))
        self.assertFalse(sono.eh_urgente("O companheiro quer puxar assunto"))
        self.assertEqual(sono.texto_do_aviso("[X] Diga ao usuário, em UMA ou duas frases curtas e no idioma da "
                                             "conversa: chegou a encomenda. Não chame nenhuma ferramenta."),
                         "chegou a encomenda.")
        self.assertEqual(sono.instrucao_recados([]), "")
        t = sono.instrucao_recados([{"ts": time.time(), "texto": "chegou a encomenda."}])
        self.assertIn("Enquanto eu dormia", t)
        self.assertIn("chegou a encomenda.", t)

    def test_horarios_falados(self):
        casos = {"07:30": (7, 30), "7h30": (7, 30), "7h": (7, 0), "às 7": (7, 0), "7 e meia": (7, 30),
                 "6 e 45": (6, 45), "sete e meia": (7, 30), "seis e quarenta e cinco": (6, 45),
                 "meia-noite": (0, 0), "meio-dia": (12, 0), "10 da noite": (22, 0), "vinte e duas": (22, 0),
                 "22h15": (22, 15), "7.30": (7, 30), "25:00": None, "abc": None, "": None}
        for texto, esperado in casos.items():
            self.assertEqual(sono.ler_hora(texto), esperado, texto)
        agora = datetime(2026, 11, 7, 23, 40)
        self.assertEqual(sono.interpretar_hora("06:30", agora), datetime(2026, 11, 8, 6, 30))
        self.assertEqual(sono.interpretar_hora("23:50", agora), datetime(2026, 11, 7, 23, 50))

    def test_como_acordar(self):
        t = sono.como_acordar(hey_jarvis=True, palmas=True, voz=True, atalho=True)
        for parte in ("Hey Jarvis", "Jarvis, acorda", "duas palmas", "Ctrl+Alt+D", "ACORDAR AGORA"):
            self.assertIn(parte, t)
        self.assertNotIn("palmas", sono.como_acordar(palmas=False))

    def test_tem_voz(self):
        self.assertFalse(sono.tem_voz(bytes(2048)))
        self.assertTrue(sono.tem_voz((np.ones(1024) * 3000).astype(np.int16).tobytes()))
        self.assertFalse(sono.tem_voz(b""))


class TestPalmas(unittest.TestCase):
    def test_duas_ou_tres_palmas_acordam(self):
        self.assertEqual(_disparos(_montar(4, [(1.0, _palma()), (1.35, _palma())])), 1)
        self.assertEqual(_disparos(_montar(4, [(1.0, _palma(6000)), (1.4, _palma(6500))])), 1)
        self.assertEqual(_disparos(_montar(4, [(1.0, _palma()), (1.3, _palma()), (1.62, _palma())])), 1)
        self.assertEqual(_disparos(_montar(4, [(0.5, _fala(0.7)), (1.6, _palma()), (1.9, _palma())])), 1)

    def test_outros_sons_nao_acordam(self):
        self.assertEqual(_disparos(_montar(4, [(1.0, _palma())])), 0, "uma palma")
        self.assertEqual(_disparos(_montar(5, [(1.0 + 0.22 * k, _palma()) for k in range(6)])), 0, "aplauso")
        self.assertEqual(_disparos(_montar(4, [(1.0, _batida()), (1.3, _batida())])), 0, "toc toc")
        teclas = [(0.5 + 0.18 * k + _rng.uniform(0, 0.05), _tecla()) for k in range(15)]
        self.assertEqual(_disparos(_montar(5, teclas)), 0, "digitando")
        self.assertEqual(_disparos(_montar(4, [(0.5, _fala(2.5))])), 0, "fala")
        self.assertEqual(_disparos(_montar(6, [(0.2, _fala(5.5, 5000))])), 0, "TV")

    def test_blocos_de_qualquer_tamanho(self):
        x = _montar(4, [(1.0, _palma()), (1.35, _palma())])
        d = sono.DetectorPalmas()
        self.assertEqual(sum(bool(d.bloco(x[i:i + 700])) for i in range(0, len(x), 700)), 1)


class TestOuvido(unittest.TestCase):
    def test_chamado(self):
        for t in ("Jarvis, acorda!", "ei Jarbas", "JARVIS", "o jarvis tá aí?"):
            self.assertTrue(sono.contem_chamado(t), t)
        for t in ("já viste isso", "acorda Pedrinho", "", "jardim"):
            self.assertFalse(sono.contem_chamado(t), t)

    def test_separa_falas_curtas(self):
        def segs(x):
            o = sono.OuvidoAcordar(lambda: None, transcrever=lambda a: "")
            return [len(r) / SR for r in (o.segmentar(x[i:i + 1024]) for i in range(0, len(x) - 1023, 1024))
                    if r is not None]
        self.assertEqual(len(segs(_montar(3, [(1.0, _fala(0.8, 6000))], fundo=80))), 1)
        self.assertEqual(segs(_montar(3, [(1.0, _fala(0.15, 6000))], fundo=80)), [])      # estalo curto

    def test_reconhece_e_acorda(self):
        chamado = []
        o = sono.OuvidoAcordar(lambda: chamado.append(1), transcrever=lambda a: "Jarvis, acorda")
        self.assertTrue(o.iniciar())
        x = _montar(3, [(1.0, _fala(0.8, 6000))], fundo=80)
        for i in range(0, len(x) - 1023, 1024):
            o.feed(x[i:i + 1024].reshape(-1, 1))
        t0 = time.time()
        while not chamado and time.time() - t0 < 5:
            time.sleep(0.05)
        o.parar()
        self.assertEqual(chamado, [1])

    def test_sem_faster_whisper_nem_liga(self):
        with mock.patch.object(sono.OuvidoAcordar, "disponivel", staticmethod(lambda: False)):
            self.assertFalse(sono.OuvidoAcordar(lambda: None).iniciar())


# ── plugins/modo_dormir.py ───────────────────────────────────────────────────
class TestRegras(unittest.TestCase):
    def test_ciclos(self):
        t = M.frase_ciclos(agora=datetime(2026, 11, 7, 23, 40))
        self.assertIn("05:55", t)
        self.assertIn("07:25", t)
        t = M.frase_ciclos(acordar_as="06:30", agora=datetime(2026, 11, 7, 22, 0))
        self.assertIn("22:45", t)
        self.assertIn("00:15", t)
        self.assertNotIn("21:15", t)                    # 6 ciclos já passou
        self.assertIn("Que horas", M.frase_ciclos(acordar_as="xyz"))

    def test_manha_ou_madrugada(self):
        deitou = datetime(2026, 11, 7, 23, 0).timestamp()
        alarme = datetime(2026, 11, 8, 6, 30).timestamp()
        self.assertFalse(M.eh_manha(deitou, datetime(2026, 11, 8, 3, 0).timestamp(), alarme))
        self.assertTrue(M.eh_manha(deitou, datetime(2026, 11, 8, 5, 0).timestamp(), alarme))
        self.assertFalse(M.eh_manha(deitou, datetime(2026, 11, 8, 3, 30).timestamp()))
        self.assertTrue(M.eh_manha(deitou, datetime(2026, 11, 8, 7, 30).timestamp()))

    def test_estatisticas(self):
        noites = []
        for d in range(7):
            base = datetime(2026, 11, 1 + d, 23, 30) if d % 2 else datetime(2026, 11, 2 + d, 0, 30)
            noites.append({"deitou": base.timestamp(), "acordou": (base + timedelta(hours=7)).timestamp()})
        e = M.estatisticas(noites, agora=datetime(2026, 11, 8, 12, 0).timestamp(), meta_h=8)
        self.assertEqual(e["n"], 7)
        self.assertAlmostEqual(e["media_s"], 7 * 3600)
        self.assertAlmostEqual(e["divida_s"], 7 * 3600)
        self.assertIn(e["deitar_medio"], ("23:55", "23:56", "00:00", "00:04"))   # atravessa a meia-noite
        self.assertLess(e["desvio_min"], 35)
        self.assertEqual(M.estatisticas([])["n"], 0)

    def test_noite_manual_e_lembrete(self):
        r = M.noite_manual("23h30", "7h", datetime(2026, 11, 8, 10, 0))
        self.assertEqual(r, (datetime(2026, 11, 7, 23, 30).timestamp(), datetime(2026, 11, 8, 7, 0).timestamp()))
        self.assertIsNone(M.noite_manual("x", "7h"))
        self.assertEqual(M.hora_de_dormir_vencida("23:30", datetime(2026, 11, 8, 0, 15)), "2026-11-07")
        self.assertIsNone(M.hora_de_dormir_vencida("23:30", datetime(2026, 11, 8, 4, 0)))
        self.assertIsNone(M.hora_de_dormir_vencida("23:30", datetime(2026, 11, 7, 22, 0)))

    def test_nomes(self):
        self.assertEqual(M.nome_som("ruído branco"), "ruido_branco")
        self.assertEqual(M.nome_som("barulho de chuva"), "chuva")
        self.assertEqual(M.nome_som("xyz"), "")
        self.assertEqual(M.op_pc("suspende"), "suspender")
        self.assertEqual(M.op_pc("não"), "")
        self.assertEqual(M.duracao_txt(26100), "7h15")
        self.assertEqual(M.duracao_txt(2700), "45 min")

    def test_respiracao(self):
        _n, fases, _c = M.TECNICAS["478"]
        a = M.audio_respiracao(fases, 2)
        self.assertEqual(len(a), 2 * 19 * 22050)
        self.assertLessEqual(float(np.abs(a).max()), 1.0)

    def test_sons_novos(self):
        from plugins import _som
        for n in ("ruido_branco", "ruido_rosa", "ruido_marrom", "ventilador"):
            self.assertIn(n, _som.AMBIENTES)
            x = _som.ambiente(n, segundos=2.0)
            self.assertTrue(len(x) > 22050 and float(np.abs(x).max()) <= 1.0, n)


class TestRotina(_Base):
    def test_dormir_pela_ferramenta(self):
        r = M.run({"action": "dormir", "minutos": 30})
        self.assertIn("Modo dormir ligado", r)
        self.assertTrue(sono.dormindo())
        self.assertAlmostEqual(sono.estado()["ate"], time.time() + 1800, delta=5)
        self.assertIn("Até que horas", M.run({"action": "dormir", "ate": "xyz"}))

    def test_boa_noite_madrugada_e_bom_dia(self):
        falas = []
        with mock.patch.object(M, "_rotina_noite", lambda *a: None), \
                mock.patch.object(M, "falar", lambda p, t: falas.append(t)), \
                mock.patch.object(M, "tocar_alarme", lambda: falas.append("SINO")), \
                mock.patch.object(M, "_clima_cambio", lambda timeout=6.0: "Clima: 24°C"):
            r = M.run({"action": "boa_noite", "acordar": "06:30"})
            self.assertIn("despertador às 06:30", r)
            e = sono.estado()
            self.assertTrue(e["dormindo"] and e["rotina"] and e["alarme"])
            d = M.dados()
            self.assertTrue(d["noite"] and d["alarme"]["hora"] == "06:30")
            # de madrugada: um aviso urgente acorda; o plugin guarda o resto e volta a dormir sozinho
            d["noite"]["deitou"] = time.time() - 3 * 3600
            d["noite"]["alarme"] = d["alarme"]["quando"] = time.time() + 4 * 3600
            M._salvar(d)
            sono.segurar("[DOWNLOAD] Diga ao usuário, em UMA frase curta e no idioma da conversa: baixou. "
                         "Não chame nenhuma ferramenta.")
            info = sono.acordar("aviso urgente")
            self.assertTrue(sono.avisar_ouvintes(info))
            d = M.dados()
            self.assertEqual(d["noite"]["acordadas"], 1)
            self.assertEqual(len(d["noite"]["recados"]), 1)
            self.assertIsNotNone(sono.estado()["retorno"])
            self.assertEqual(falas, [])                            # nada de bom dia às 3 da manhã
            # o despertador: toca UMA vez e dá bom dia com a noite e o que chegou
            sono.dormir("voltando a dormir", ate=time.time() - 1, rotina=True, alarme=True)
            info = sono.acordar(sono.motivo_da_hora())
            self.assertTrue(sono.avisar_ouvintes(info))
            t0 = time.time()
            while len(falas) < 2 and time.time() - t0 < 5:
                time.sleep(0.05)
        self.assertEqual(falas[0], "SINO")
        self.assertIn("[BOM DIA]", falas[1])
        self.assertIn("baixou", falas[1])
        self.assertIn("Clima: 24°C", falas[1])
        self.assertIn("soneca", falas[1])
        d = M.dados()
        self.assertIsNone(d["noite"])
        self.assertEqual(len(d["noites"]), 1)
        self.assertTrue(d["alarme"]["tocado"])
        self.assertIsNone(M._pegar_alarme())                       # não toca de novo

    def test_soneca_reabre_a_noite(self):
        with mock.patch.object(M, "_rotina_noite", lambda *a: None), \
                mock.patch.object(M, "falar", lambda p, t: None), mock.patch.object(M, "tocar_alarme", lambda: None):
            M.run({"action": "boa_noite", "acordar": "06:30"})
            d = M.dados()
            d["noite"]["deitou"] = time.time() - 7 * 3600
            M._salvar(d)
            sono.dormir("x", ate=time.time() - 1, rotina=True, alarme=True)
            sono.avisar_ouvintes(sono.acordar("despertador"))
            self.assertEqual(len(M.dados()["noites"]), 1)
            r = M.run({"action": "soneca", "minutos": 9})
        self.assertIn("Soneca", r)
        d = M.dados()
        self.assertEqual(d["noites"], [])
        self.assertEqual(d["noite"]["sonecas"], 1)
        self.assertFalse(d["alarme"]["tocado"])
        e = sono.estado()
        self.assertTrue(e["dormindo"] and e["alarme"])
        self.assertAlmostEqual(e["ate"], time.time() + 540, delta=5)

    def test_boa_noite_usa_o_despertador_ja_marcado(self):
        with mock.patch.object(M, "_rotina_noite", lambda *a: None):
            M.despertador("06:45")
            self.assertIn("despertador às 06:45", M.run({"action": "boa_noite"}))
            self.assertEqual(M.dados()["alarme"]["hora"], "06:45")
            self.assertIn("sem despertador", M.run({"action": "boa_noite", "acordar": "não"}))
            self.assertIsNone(M.dados()["alarme"])

    def test_vou_dormir_de_novo_de_madrugada_e_a_mesma_noite(self):
        with mock.patch.object(M, "_rotina_noite", lambda *a: None):
            M.run({"action": "boa_noite", "acordar": "06:30"})
            d = M.dados()
            d["noite"]["deitou"] = time.time() - 4 * 3600
            M._salvar(d)
            sono.acordar("comando digitado")
            M.run({"action": "boa_noite"})
        d = M.dados()
        self.assertAlmostEqual(d["noite"]["deitou"], time.time() - 4 * 3600, delta=5)
        self.assertEqual(d["alarme"]["hora"], "06:30")

    def test_cochilo_toca_e_avisa(self):
        falas = []
        with mock.patch.object(M, "falar", lambda p, t: falas.append(t)), \
                mock.patch.object(M, "tocar_alarme", lambda: falas.append("SINO")):
            self.assertIn("Cochilo de 20", M.run({"action": "cochilo", "minutos": 20}))
            self.assertTrue(sono.dormindo())
            sono.dormir("cochilo", ate=time.time() - 1, alarme=True)
            self.assertTrue(sono.avisar_ouvintes(sono.acordar(sono.motivo_da_hora())))
        self.assertEqual(falas[0], "SINO")
        self.assertIn("[DESPERTADOR]", falas[1])

    def test_acordou_de_manha_antes_do_despertador(self):
        with mock.patch.object(M, "_rotina_noite", lambda *a: None), \
                mock.patch.object(M, "falar", lambda p, t: None), mock.patch.object(M, "tocar_alarme", lambda: None):
            M.run({"action": "boa_noite", "acordar": "06:30"})
            d = M.dados()
            d["noite"]["deitou"] = time.time() - 7 * 3600
            d["noite"]["alarme"] = d["alarme"]["quando"] = time.time() + 30 * 60
            M._salvar(d)
            sono.avisar_ouvintes(sono.acordar("duas palmas"))
        d = M.dados()
        self.assertIsNone(d["alarme"])                             # acordou antes: o despertador da noite sai
        self.assertEqual(d["noites"][-1]["como"], "duas palmas")

    def test_despertador_com_o_jarvis_acordado(self):
        falas = []
        with mock.patch.object(M, "falar", lambda p, t: falas.append(t)), \
                mock.patch.object(M, "tocar_alarme", lambda: falas.append("SINO")):
            self.assertIn("Despertador às", M.run({"action": "despertador", "hora": "06:30"}))
            d = M.dados()
            d["alarme"]["quando"] = time.time() - 5
            M._salvar(d)
            M.passo()
            M.passo()
        self.assertEqual(falas.count("SINO"), 1)
        self.assertTrue(any("[DESPERTADOR]" in f for f in falas))
        self.assertTrue(M.dados()["alarme"]["tocado"])
        self.assertIn("Despertador cancelado", M.run({"action": "despertador", "cancelar": True}))
        self.assertIn("Não havia", M.run({"action": "despertador", "cancelar": True}))

    def test_despertador_atrasado_demais_nao_toca(self):
        M.despertador("06:30")
        d = M.dados()
        d["alarme"]["quando"] = time.time() - 4 * 3600
        M._salvar(d)
        with mock.patch.object(M, "tocar_alarme", lambda: self.fail("tocou atrasado")):
            M.passo()
        self.assertIsNone(M.dados()["alarme"])

    def test_lembrete_uma_vez_por_noite(self):
        self.cfg["hora_dormir"] = "23:30"
        avisos = []
        with mock.patch.object(M, "avisar", lambda p, t, e="": avisos.append((e, t))), \
                mock.patch.object(M, "_ocioso", lambda: 5.0):
            M.passo(datetime(2026, 11, 7, 23, 45).timestamp())
            M.passo(datetime(2026, 11, 8, 0, 30).timestamp())
            M.passo(datetime(2026, 11, 8, 23, 40).timestamp())
        self.assertEqual(len(avisos), 2)
        self.assertEqual(avisos[0][0], "HORA DE DORMIR")
        self.assertIn("vou dormir", avisos[0][1])

    def test_relatorio_e_registrar(self):
        self.assertIn("Ainda não tenho noites", M.run({"action": "sono"}))
        self.assertIn("Anotado", M.run({"action": "registrar", "inicio": "23h", "fim": "6h30"}))
        r = M.run({"action": "sono"})
        self.assertIn("Última noite", r)
        self.assertIn("7h30", r)

    def test_sons_sem_placa_de_som(self):
        class Laco:
            def __init__(self, audio, taxa, volume):
                self.volume, self.alvo, self.parado = volume, volume, False

            def tocar(self):
                pass

            def parar(self, fade=1.5):
                self.parado = True
        from plugins import _som
        with mock.patch.object(_som, "Laco", Laco):
            self.assertIn("Tocando ruído branco", M.run({"action": "sons", "som": "ruído branco", "minutos": 30}))
            self.assertEqual(M.som_tocando(), "ruido_branco")
            self.assertIn("desligado", M.run({"action": "sons", "som": "parar"}))
        self.assertEqual(M.som_tocando(), "")
        self.assertIn("Qual?", M.tocar_som("xyz"))

    def test_status_e_acordar(self):
        self.assertIn("Para me acordar", M.run({"action": "status"}))
        self.assertIn("Já estou acordado", M.run({"action": "acordar"}))

    def test_o_que_tem_amanha(self):
        from plugins import contas
        amanha = (datetime.now() + timedelta(days=1)).date()
        contas.ARQ.parent.mkdir(parents=True, exist_ok=True)
        antes = contas.ARQ.read_text(encoding="utf-8") if contas.ARQ.exists() else None
        try:
            contas.ARQ.write_text('{"contas": [{"id": 1, "descricao": "conta de luz", "valor": 142.0, '
                                  f'"vencimento": "{amanha.isoformat()}", "pago": false}}]}}', encoding="utf-8")
            self.assertIn("vence conta de luz (R$ 142)", M._agenda_do_dia(amanha))
            self.assertEqual(M._agenda_do_dia(amanha + timedelta(days=3)), [])
        finally:
            if antes is None:
                contas.ARQ.unlink(missing_ok=True)
            else:
                contas.ARQ.write_text(antes, encoding="utf-8")


# ── integração com o resto do JARVIS ─────────────────────────────────────────
class TestIntegracao(_Base):
    def test_estado_do_mundo_e_central_de_avisos(self):
        from core import central_avisos, estado_mundo
        e = estado_mundo.inferir(datetime(2026, 11, 8, 2, 0), "code.exe", "", 0, set(), dormindo=True)
        self.assertEqual((e["atividade"], e["fala"]), ("dormindo", "silencio"))
        self.assertFalse(estado_mundo.permite(e, "normal"))
        self.assertTrue(estado_mundo.permite(e, "urgente"))
        self.assertTrue(central_avisos.montar_resumo([{"texto": "x", "etiqueta": "A"}], "dormindo")
                        .startswith("Enquanto o senhor dormia"))

    def test_cena_nao_comeca_dormindo(self):
        from plugins import _dupla as D
        sono.dormir("teste")
        self.assertFalse(D.encenar([{"quem": "JARVIS", "texto": "oi"}], abrir_palco=False, pausar_microfone=False))

    def test_main_usa_o_modo_dormir(self):
        m = (RAIZ / "main.py").read_text(encoding="utf-8")
        for trecho in ("from core import sono as _sono", "def _dormindo(self)", "_sono.segurar(instruction)",
                       "self._palmas.bloco(indata)", "_sono.deve_acordar()", "_sono.retorno_pendente(",
                       "set_wake_callback(self._acordar_pelo_celular)", "_sono.restaurar()",
                       "self._iniciar_atalho_sono()", 'self.wake(reason="comando digitado")'):
            self.assertIn(trecho, m)
        self.assertNotIn("self._wake_enabled and not self._awake", m)       # o portão é um só: _dormindo()
        self.assertNotIn('or "1007" in err_str:', m)                         # 1007 sozinho não é chave errada
        u = (RAIZ / "ui.py").read_text(encoding="utf-8")
        self.assertIn('DORMIR AGORA  [Ctrl+Alt+D]', u)
        from core import hotkey
        self.assertIn("d", hotkey._VK)

    def test_firewall_do_linux_libera_as_portas(self):
        from dashboard import server
        chamados = []

        class R:
            def __init__(self, out="", rc=0):
                self.stdout, self.returncode = out, rc

        def falso_run(cmd, **k):
            chamados.append(cmd)
            if cmd[:2] == ["ufw", "status"]:
                return R("Status: active")
            return R()
        with mock.patch.object(sys, "platform", "linux"), mock.patch("subprocess.run", falso_run):
            server._ensure_network_access(8000, 8443)            # antes: NameError (`port` não existia)
        liberados = [c for c in chamados if "allow" in c]
        self.assertEqual([c[-1] for c in liberados], ["8000/tcp", "8443/tcp"])


class TestSintaxe311(unittest.TestCase):
    """O setup.py aceita Python 3.11: nada de f-string com barra invertida ou aspas iguais dentro (3.12+)."""

    def test_fstrings_compativeis(self):
        if sys.version_info < (3, 12):
            self.skipTest("o tokenizador antigo não separa as f-strings")
        problemas = []
        for arq in RAIZ.rglob("*.py"):
            if any(p in arq.parts for p in ("__pycache__", ".git", "ferramentas")):
                continue
            src = arq.read_text(encoding="utf-8", errors="replace")
            try:
                ast.parse(src)
                toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
            except (SyntaxError, tokenize.TokenError):
                continue
            pilha = []                                       # [delimitador, profundidade das chaves]
            for t in toks:
                dentro = bool(pilha) and pilha[-1][1] > 0
                if t.type == tokenize.FSTRING_START:
                    delim = t.string.lstrip("rRbBuUfF")
                    if dentro and pilha[-1][0] in delim:
                        problemas.append(f"{arq.relative_to(RAIZ)}:{t.start[0]} aspas iguais aninhadas")
                    pilha.append([delim, 0])
                elif t.type == tokenize.FSTRING_END:
                    if pilha:
                        pilha.pop()
                elif pilha and t.type == tokenize.OP and t.string == "{":
                    pilha[-1][1] += 1
                elif pilha and t.type == tokenize.OP and t.string == "}":
                    pilha[-1][1] = max(0, pilha[-1][1] - 1)
                elif dentro and t.type == tokenize.STRING:
                    if "\\" in t.string:
                        problemas.append(f"{arq.relative_to(RAIZ)}:{t.start[0]} barra invertida na f-string")
                    elif pilha[-1][0] in t.string:          # o 3.11 acharia que a f-string acabou ali
                        problemas.append(f"{arq.relative_to(RAIZ)}:{t.start[0]} aspas iguais aninhadas")
        self.assertEqual(problemas, [])


if __name__ == "__main__":
    unittest.main()
