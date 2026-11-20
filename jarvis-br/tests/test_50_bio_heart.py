"""Biological Core (3.1) — sistema nervoso, circulação, coração, saúde e painel."""
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

import tests  # noqa: F401
from tests.bio_comum import organismo, projeto, vitais

from biological_core.circulation.data_flow import Circulacao
from biological_core.circulation.task_queue import FilaPrioridade
from biological_core.heart.health_monitor import MonitorSaude
from biological_core.nervous_system.communication import Orgao
from biological_core.nervous_system.event_bus import ALTA, BAIXA, CRITICA, NORMAL, Barramento
from core import relogio


class TestSistemaNervoso(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jarvis_bio_"))
        self.bus = Barramento(log=self.tmp / "nervos.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_comunicacao_entre_orgaos(self):
        recebidos = []
        a, b = Orgao(self.bus, "alfa"), Orgao(self.bus, "beta")
        b.ouvir("incidente.*", lambda ev: recebidos.append((ev.topico, ev.origem, ev.dados["x"])))
        b.oferecer_ajuda("somar", lambda d: d["a"] + d["b"])
        a.enviar("incidente.novo", {"x": 1}, ALTA)
        a.enviar("outra.coisa", {"x": 2})
        self.assertEqual(recebidos, [("incidente.novo", "alfa", 1)])
        self.assertEqual(a.pedir_ajuda("somar", {"a": 2, "b": 3}), [5])
        ordens = []
        b.receber_ordem = lambda ordem, dados: ordens.append(ordem)
        a.enviar("ordem.beta", {"ordem": "reparar"})
        self.assertEqual(ordens, ["reparar"])
        erros = []
        self.bus.assinar("orgao.erro", lambda ev: erros.append(ev.dados["orgao"]))
        a.relatar_erro(ValueError("x"))
        self.assertEqual(erros, ["alfa"])
        self.assertTrue(self.bus.historico("incidente.*"))
        log = self.bus.ler_log()
        self.assertTrue(all(e["prioridade"] <= ALTA for e in log))       # só o importante vai para o disco
        self.assertIn("incidente.novo", [e["topico"] for e in log])

    def test_nervo_inflamado_nao_derruba_os_outros(self):
        ok, alertas = [], []
        self.bus.assinar("t", lambda ev: 1 / 0, "quebrado")
        self.bus.assinar("t", lambda ev: ok.append(1), "bom")
        self.bus.assinar("nervo.inflamado", lambda ev: alertas.append(ev.dados["assinante"]))
        for _ in range(6):
            self.bus.publicar("t")
        self.assertEqual(len(ok), 6)
        self.assertEqual(alertas, ["quebrado"])
        self.assertEqual(self.bus.estado()["inflamados"], ["quebrado"])
        self.assertTrue(self.bus.reanimar("quebrado"))


class TestCirculacao(unittest.TestCase):
    def test_prioridade_e_sem_duplicar(self):
        f = FilaPrioridade(limite=3)
        f.colocar("baixa", BAIXA)
        f.colocar("critica", CRITICA)
        self.assertTrue(f.colocar("bat", NORMAL, chave="batimento"))
        self.assertFalse(f.colocar("bat", NORMAL, chave="batimento"))      # juntou com o que esperava
        self.assertTrue(f.colocar("alta", ALTA))                            # cheia: sai a baixa, não a crítica
        saida = []
        while (x := f.tirar(timeout=0)) is not None:
            saida.append((x[0], x[1]))
        self.assertEqual(saida, [("critica", 1), ("alta", 1), ("bat", 2)])
        self.assertEqual((f.coalescidos, f.descartados), (1, 1))

    def test_entrega_em_segundo_plano_e_congestionamento(self):
        bus = Barramento()
        circ = Circulacao(bus, congestao=5)
        chegou = threading.Event()
        bus.assinar("x", lambda ev: chegou.set())
        circ.iniciar()
        try:
            bus.publicar("x")
            self.assertTrue(chegou.wait(2))
        finally:
            circ.parar()
        alertas = []
        bus.assinar("circulacao.congestionada", lambda ev: alertas.append(ev.dados))
        circ.ativa = True                                                   # sem thread: tudo fica na fila
        for i in range(8):
            bus.publicar("lixo", prioridade=BAIXA)
        circ.ativa = False
        self.assertTrue(alertas)
        self.assertLessEqual(len(circ.fila), 5)


class TestCoracao(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jarvis_bio_"))
        self.raiz = projeto(self.tmp)

    def tearDown(self):
        relogio.pausar_nao_essenciais(False)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_batimento_vitais_cores_e_reflexo(self):
        org = organismo(self.raiz)
        try:
            s = org.coracao.bater()
            self.assertEqual((s["nota"], s["cor"]), (100, "azul"))
            self.assertEqual(set(s["orgaos"]), {"cerebro", "coracao", "nervos", "imune", "dna", "circulacao", "regeneracao", "celulas"})
            limpou = []
            org.coracao.caches.append(lambda: limpou.append(1))
            org.coracao.fonte_vitais = vitais(ram_pc=95.0)
            s = org.coracao.bater()
            self.assertLess(s["nota"], 90)
            self.assertTrue(any("RAM do PC em 95%" in p for p in s["problemas"]))
            self.assertEqual(limpou, [1])                                   # reflexo: limpou caches na hora
        finally:
            org.encerrar()

    def test_febre_pausa_o_que_nao_e_essencial(self):
        org = organismo(self.raiz)
        try:
            org.coracao.fonte_vitais = vitais(ram_pc=97.0, disco_livre_pct=2.0, temp_cpu=92.0, ram_jarvis_mb=2600.0)
            for _ in range(3):
                org.coracao.bater()
            self.assertTrue(org.coracao.febre)
            self.assertTrue(relogio._pausa_nao_essenciais)
            org.coracao.fonte_vitais = vitais()
            for _ in range(3):
                org.coracao.bater()
            self.assertFalse(org.coracao.febre)
            self.assertFalse(relogio._pausa_nao_essenciais)
        finally:
            org.encerrar()

    def test_detecta_travado_e_ciclo_de_vida(self):
        org = organismo(self.raiz)
        try:
            boot = org.coracao.inicializacao
            self.assertEqual([e["etapa"] for e in boot][:3], ["DNA", "memória imunológica", "sistema nervoso e circulação"])
            self.assertTrue(all(e["ok"] for e in boot))
            tok = org.sentinela.inicio("bioteste_clima", {"action": "agora"})
            nome, acao, t0, th = org.sentinela.em_voo[tok]
            org.sentinela.em_voo[tok] = (nome, acao, t0 - 120, th)          # "está rodando há 2 minutos"
            self.assertEqual([(t[0], t[1]) for t in org.coracao.travados()], [("bioteste_clima", "agora")])
            org.sentinela.fim(tok)
            self.assertEqual(org.coracao.travados(), [])
            rel = org.coracao.ciclo_inicializacao([("ok", lambda: 1), ("quebra", lambda: 1 / 0), ("depois", lambda: 2)])
            self.assertEqual([e["ok"] for e in rel], [True, False, True])   # uma etapa ruim não impede as outras
        finally:
            fim = org.encerrar()
        self.assertTrue(all(e["ok"] for e in fim))


class TestSaude(unittest.TestCase):
    def test_cores_e_motivos(self):
        m = MonitorSaude()
        self.assertEqual(m.avaliar({}, {}, [], [], 0)["cor"], "azul")
        s = m.avaliar({"ram_pc": 92}, {}, [], [{"gravidade": "alta"}], 1)
        self.assertEqual(s["cor"], "amarelo")
        self.assertTrue(any("RAM" in p for p in s["problemas"]))
        s = m.avaliar({"ram_pc": 95, "disco_livre_pct": 2}, {"cerebro": {"cor": "vermelho", "titulo": "Cérebro"}}, [], [], 0)
        self.assertEqual(s["cor"], "vermelho")
        m.registrar_recuperacao()
        self.assertEqual(m.avaliar({}, {}, [], [], 0)["cor"], "verde")


class TestPainel(unittest.TestCase):
    def test_pagina_e_svg(self):
        tmp = Path(tempfile.mkdtemp(prefix="jarvis_bio_"))
        org = organismo(projeto(tmp))
        try:
            from biological_core.dashboard.biological_dashboard import dados, escrever, pagina, svg
            org.coracao.bater()
            d = dados(org)
            self.assertEqual(len(d["camadas"]), 8)
            self.assertEqual(svg(d).count("<g transform="), 8)                # os 8 órgãos desenhados
            html = pagina(d)
            for t in ("BIOLOGICAL CORE", "Sistema imunológico", "Esperando o seu sim", "Decisões do cérebro", "Sinais vitais"):
                self.assertIn(t, html)
            self.assertNotIn("{d[", html)
            self.assertTrue(escrever(org).is_file())
        finally:
            org.encerrar()
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
