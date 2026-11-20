"""Agendador: interpretação de horários e dias, próxima execução, vencidas."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import tests  # noqa: F401
from plugins import agendador as ag

# quarta-feira, 28/10/2026, 10:00
AGORA = datetime(2026, 10, 28, 10, 0)


class TestHora(unittest.TestCase):
    def test_formatos(self):
        casos = {"8": (8, 0), "08:30": (8, 30), "8h30": (8, 30), "23h": (23, 0), "às 23h": (23, 0),
                 "20:00": (20, 0), "meio-dia": (12, 0), "meia noite": (0, 0),
                 "8 da noite": (20, 0), "3 da tarde": (15, 0), "7h05": (7, 5)}
        for texto, esperado in casos.items():
            self.assertEqual(ag.parse_hora(texto), esperado, texto)

    def test_invalidos(self):
        for texto in ("", "25h", "abc", "12:99"):
            self.assertIsNone(ag.parse_hora(texto), texto)


class TestDias(unittest.TestCase):
    def test_dias(self):
        self.assertEqual(ag.parse_dias("todo dia"), [])
        self.assertEqual(ag.parse_dias("todos os dias"), [])
        self.assertEqual(ag.parse_dias("toda sexta"), [4])
        self.assertEqual(ag.parse_dias("segunda a sexta"), [0, 1, 2, 3, 4])
        self.assertEqual(ag.parse_dias("dias úteis"), [0, 1, 2, 3, 4])
        self.assertEqual(ag.parse_dias("fim de semana"), [5, 6])
        self.assertEqual(ag.parse_dias("seg, qua, sex"), [0, 2, 4])
        self.assertEqual(ag.parse_dias("sábado e domingo"), [5, 6])
        self.assertEqual(ag.parse_dias("sexta a segunda"), [4, 5, 6, 0])


class TestQuando(unittest.TestCase):
    def test_diario(self):
        q = ag.montar_quando("8h", "todo dia", None, None, AGORA)
        self.assertEqual(q, {"tipo": "semanal", "hora": "08:00", "dias": []})
        self.assertEqual(ag.proxima_execucao(q, AGORA), datetime(2026, 10, 29, 8, 0))

    def test_semanal(self):
        q = ag.montar_quando("18h", "toda sexta", None, None, AGORA)
        self.assertEqual(ag.proxima_execucao(q, AGORA), datetime(2026, 10, 30, 18, 0))
        # depois de rodar na sexta, a próxima é a sexta seguinte
        self.assertEqual(ag.proxima_execucao(q, datetime(2026, 10, 30, 18, 0)), datetime(2026, 11, 6, 18, 0))

    def test_sem_dia_e_uma_vez_so(self):
        q = ag.montar_quando("23h", "", None, None, AGORA)
        self.assertEqual(q["tipo"], "unico")
        self.assertEqual(ag.proxima_execucao(q, AGORA), datetime(2026, 10, 28, 23, 0))
        self.assertIsNone(ag.proxima_execucao(q, datetime(2026, 10, 29, 0, 0)))
        # hora que já passou hoje → amanhã
        q2 = ag.montar_quando("9h", "", None, None, AGORA)
        self.assertEqual(ag.proxima_execucao(q2, AGORA), datetime(2026, 10, 29, 9, 0))

    def test_data(self):
        q = ag.montar_quando("14:30", "", "05/11", None, AGORA)
        self.assertEqual(ag.proxima_execucao(q, AGORA), datetime(2026, 11, 5, 14, 30))
        q = ag.montar_quando("7h", "", "amanhã", None, AGORA)
        self.assertEqual(ag.proxima_execucao(q, AGORA), datetime(2026, 10, 29, 7, 0))

    def test_intervalo(self):
        q = ag.montar_quando(None, None, None, 30, AGORA)
        self.assertEqual(q, {"tipo": "intervalo", "minutos": 30})
        self.assertEqual(ag.proxima_execucao(q, AGORA), datetime(2026, 10, 28, 10, 30))

    def test_horario_invalido(self):
        self.assertIsNone(ag.montar_quando("depois", "todo dia", None, None, AGORA))

    def test_descricao(self):
        self.assertEqual(ag.descrever_quando({"tipo": "semanal", "hora": "08:00", "dias": []}), "todo dia às 08:00")
        self.assertEqual(ag.descrever_quando({"tipo": "semanal", "hora": "09:00", "dias": [0, 1, 2, 3, 4]}),
                         "de segunda a sexta às 09:00")
        self.assertEqual(ag.descrever_quando({"tipo": "intervalo", "minutos": 60}), "a cada 60 min")


class TestArmazenamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.antigo = ag.ARQUIVO
        ag.ARQUIVO = Path(self.tmp.name) / "agendador.json"

    def tearDown(self):
        ag.ARQUIVO = self.antigo
        self.tmp.cleanup()

    def test_adicionar_e_vencidas(self):
        q = ag.montar_quando("10:05", "todo dia", None, None, AGORA)
        t = ag.adicionar("abrir_app", "WhatsApp", q, AGORA)
        self.assertEqual(t["id"], "1")
        self.assertEqual(t["proxima"], "2026-10-28T10:05:00")
        tarefas = ag.carregar()
        self.assertEqual(ag.vencidas(tarefas, AGORA), [])
        self.assertEqual(len(ag.vencidas(tarefas, datetime(2026, 10, 28, 10, 5))), 1)
        t2 = ag.adicionar("lembrete", "água", ag.montar_quando(None, None, None, 60, AGORA), AGORA)
        self.assertEqual(t2["id"], "2")

    def test_tarefa_pausada_nao_vence(self):
        q = ag.montar_quando("10:05", "todo dia", None, None, AGORA)
        ag.adicionar("abrir_app", "WhatsApp", q, AGORA)
        tarefas = ag.carregar()
        tarefas[0]["ativo"] = False
        self.assertEqual(ag.vencidas(tarefas, datetime(2026, 10, 29, 12, 0)), [])

    def test_criar_pelo_run_e_apagar(self):
        r = ag.run({"action": "criar", "acao": "abrir_app", "alvo": "WhatsApp", "hora": "8h", "dias": "todo dia"})
        self.assertIn("Agendado (#1)", r)
        self.assertIn("todo dia às 08:00", r)
        r = ag.run({"action": "apagar", "alvo": "whatsapp"})
        self.assertIn("apagada", r)
        self.assertEqual(ag.carregar(), [])

    def test_acao_perigosa_pede_confirmacao(self):
        r = ag.run({"action": "criar", "acao": "desligar", "hora": "23h", "dias": ""})
        # sem interface ligada, a confirmação recusa — e nada é agendado
        self.assertNotIn("Agendado", r)
        self.assertEqual(ag.carregar(), [])


if __name__ == "__main__":
    unittest.main()
