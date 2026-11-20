"""Testes da 2.21 — ideias "impossíveis": conselho do multiverso, eu do passado, palavras secretas,
sentido de aranha e os genes novos do Darwin (core/evolucao.py)."""
import json
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from plugins import _lote2, eu_do_passado, multiverso, palavras_secretas, sentido_aranha

HOJE = date(2026, 11, 13)
DEBATE = {"rodada1": [{"quem": n, "fala": f"fala do {n}"} for n, _ in multiverso.MEMBROS],
          "rodada2": [{"quem": "Empresário", "responde_a": "Stark", "fala": "e o caixa?"}],
          "votos": [{"quem": "Stark", "voto": "sim", "porque": "x"}, {"quem": "Empresário", "voto": "não", "porque": "x"},
                    {"quem": "Sábio", "voto": "testar antes", "porque": "x"}, {"quem": "Rapper", "voto": "Sim!", "porque": "x"},
                    {"quem": "Cientista", "voto": "testar", "porque": "x"}],
          "veredito": "Testar por um mês.", "primeiro_passo": "Postar três peças."}


class TestMultiverso(unittest.TestCase):
    def test_apuracao(self):
        self.assertEqual(multiverso.apurar(DEBATE["votos"]), ("empate", {"sim": 2, "não": 1, "testar antes": 2}))
        self.assertEqual(multiverso.apurar([{"voto": "não"}, {"voto": "nao"}, {"voto": "sim"}])[0], "não")
        self.assertIn("Placar: sim 2", multiverso.roteiro(DEBATE))
        self.assertTrue(all(n in multiverso.montar_prompt("abrir loja?") for n, _ in multiverso.MEMBROS))

    def test_reuniao(self):
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), \
                mock.patch("core.gemini.as_json", lambda *a, **k: DEBATE):
            self.assertIn("Qual é a decisão", multiverso.run({"action": "convocar", "pergunta": "e aí"}))
            r = multiverso.run({"action": "convocar", "pergunta": "Abro uma segunda loja ou invisto na online?"})
            self.assertIn("sim 2, não 1, testar antes 2", r)
            self.assertIn("O Rapper mandou: fala do Rapper", r)
            self.assertIn("Testar por um mês", multiverso.run({"action": "ultima"}))
            self.assertIn("empate", multiverso.run({"action": "historico"}))
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), mock.patch("core.gemini.as_json", lambda *a, **k: None):
            self.assertIn("não respondeu", multiverso.run({"action": "convocar", "pergunta": "Abro uma segunda loja?"}))


class TestEuDoPassado(unittest.TestCase):
    def test_fotografias(self):
        fotos = [{"dia": "2026-05-10", "partes": {}}, {"dia": "2026-08-12", "partes": {}}, {"dia": "2026-11-01", "partes": {}}]
        self.assertEqual(eu_do_passado.mais_perto(fotos, 6, HOJE)["dia"], "2026-05-10")
        self.assertEqual(eu_do_passado.mais_perto(fotos, 3, HOJE)["dia"], "2026-08-12")
        self.assertIsNone(eu_do_passado.mais_perto(fotos[2:], 6, HOJE))           # 12 dias não conta
        foto = eu_do_passado.tirar_foto(lambda n, a: {"metas_pessoais": "Abrir loja online: 40%", "ideias": "Nenhuma ideia."}.get(n, "Ação 'x' não existe."))
        self.assertEqual(foto["partes"].get("metas"), "Abrir loja online: 40%")
        self.assertNotIn("ideias", foto["partes"])

    def test_conversa(self):
        pasta = Path(tempfile.mkdtemp())
        pedidos = []
        with mock.patch.object(_lote2, "PASTA", pasta), mock.patch("core.registro_ferramentas.executar", lambda *a, **k: "Meta: aprender IA 10%"), \
                mock.patch("core.gemini.text", lambda pedido, **k: pedidos.append(pedido) or "Eu queria terminar a IA do zero."):
            self.assertIn("Ainda não tenho uma fotografia", eu_do_passado.run({"action": "conversar", "pergunta": "oi"}))
            fotos = _lote2.carregar("eu_do_passado", [])
            self.assertEqual(len(fotos), 1)                                          # tirou a de hoje
            fotos.insert(0, {"dia": (date.today() - timedelta(180)).isoformat(), "partes": {"metas": "Abrir a loja online"}})
            _lote2.guardar("eu_do_passado", fotos)
            r = eu_do_passado.run({"action": "conversar", "pergunta": "o que você queria?", "meses": "6"})
            self.assertIn("Eu queria terminar a IA do zero.", r)
            self.assertIn("Abrir a loja online", pedidos[-1])
            self.assertIn("Não invente", pedidos[-1])
            self.assertIn("ANTES", (eu_do_passado.run({"action": "mudou", "meses": "6"}), pedidos[-1])[1])


def chamada(ts, ferramenta, acao="", params=None, ok=1):
    return {"ts": ts, "ferramenta": ferramenta, "acao": acao, "params": json.dumps(params or {"action": acao}), "ok": ok}


class TestPalavrasSecretas(unittest.TestCase):
    def diario(self):
        out, base = [], time.mktime((2026, 11, 2, 8, 0, 0, 0, 0, -1))
        for d in range(4):                                       # 4 manhãs: caixa → meta → música
            t = base + d * 86400
            out += [chamada(t, "caixa_loja", "abrir", {"action": "abrir", "valor": "100"}), chamada(t + 60, "meta_vendas", "status"),
                    chamada(t + 120, "musica", "tocar", {"action": "tocar", "pedido": "rap"}), chamada(t + 3000, "piadas", "contar")]
        out.append(chamada(base + 5 * 86400, "caixa_loja", "abrir", ok=0))
        return out

    def test_padroes(self):
        blocos = palavras_secretas.sessoes(self.diario())
        self.assertEqual(len(blocos), 8)                         # a piada 50 min depois é outra sessão
        achou = palavras_secretas.padroes(blocos)
        self.assertEqual(achou[0], ((("caixa_loja", "abrir"), ("meta_vendas", "status"), ("musica", "tocar")), 4))
        self.assertEqual(len(achou), 1)                          # não sugere pedaços da mesma sequência
        self.assertNotEqual(palavras_secretas.inventar_nome(achou[0][0], {"pequi"}), "Pequi")

    def test_aceitar_vira_protocolo(self):
        pasta = Path(tempfile.mkdtemp())
        from plugins import protocolos
        with mock.patch.object(_lote2, "PASTA", pasta), mock.patch.object(protocolos, "ARQUIVO", pasta / "protocolos.json"), \
                mock.patch("core.registro_uso.chamadas", lambda **k: self.diario()):
            r = palavras_secretas.run({"action": "descobrir"})
            self.assertIn("Em 4 dias diferentes", r)
            nome = list(_lote2.carregar("palavras_secretas", {})["sugestoes"])[0]
            self.assertIn(f"protocolo {nome}", palavras_secretas.run({"action": "aceitar", "nome": nome}))
            passos = protocolos._load()[_lote2.norm(nome)]["passos"]
            self.assertEqual(passos[0], {"tipo": "ferramenta", "nome": "caixa_loja", "params": {"action": "abrir", "valor": "100"}})
            self.assertIn(nome, palavras_secretas.run({"action": "minhas"}))
            self.assertIn("Ainda não achei", palavras_secretas.run({"action": "descobrir"}))   # não sugere de novo


class TestSentidoAranha(unittest.TestCase):
    def test_disco(self):
        total = 500e9
        enchendo = [(i, 400e9 + i * 2e9) for i in range(10)]
        self.assertAlmostEqual(sentido_aranha.dias_ate_encher(enchendo, total), 41, 0)
        self.assertIsNone(sentido_aranha.dias_ate_encher([(i, 400e9) for i in range(10)], total))
        self.assertIsNone(sentido_aranha.dias_ate_encher(enchendo[:3], total))

    def test_tendencias(self):
        semana = {0: 550, 1: 700, 2: 850, 3: 1000}               # 0 = semana mais recente
        vendas = {(HOJE - timedelta(k)).isoformat(): semana[(k - 1) // 7] for k in range(1, 29)}
        self.assertEqual(len(sentido_aranha.semanas_caindo(vendas, HOJE)), 4)
        estavel = {(HOJE - timedelta(k)).isoformat(): 500 for k in range(1, 29)}
        self.assertIsNone(sentido_aranha.semanas_caindo(estavel, HOJE))
        agua = {(HOJE - timedelta(k)).isoformat(): (1000 if k <= 7 else 2500) for k in range(1, 29)}
        self.assertAlmostEqual(sentido_aranha.queda_recente(agua, HOJE), 60)
        self.assertIsNone(sentido_aranha.queda_recente({k: 2000 for k in agua}, HOJE))

    def test_sentir(self):
        habito = {(HOJE - timedelta(k)).isoformat(): (1.0 if k > 7 else (1.0 if k == 1 else 0.0)) for k in range(1, 29)}
        s = {"hábito ler": habito, "horas trabalhadas": {(HOJE - timedelta(k)).isoformat(): 11.5 for k in range(1, 8)}}
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), mock.patch("plugins.sonhos.series", lambda: s):
            av = sentido_aranha.sentir(HOJE)
        self.assertTrue(any("hábito ler está escapando: só 1" in a for a in av), av)
        self.assertTrue(any("11.5 horas" in a for a in av), av)
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())):
            self.assertIn("medindo (1 de 5 dias)", sentido_aranha.run({"action": "disco"}))
            self.assertIn("Nenhum aviso", sentido_aranha.run({"action": "historico"}))


class TestDarwinGenesNovos(unittest.TestCase):
    def test_humor_e_fechamento(self):
        from core import evolucao as EV
        self.assertIn("humor", EV.DIMENSOES)
        self.assertEqual(EV.sinal("kkkkk boa"), "riso")
        self.assertEqual(EV.sinal("pode fazer"), "aceitou")
        atual = {"tamanho": "curta", "tom": "formal", "ordem": "resposta_antes", "humor": "com_tirada", "fechamento": "proximo_passo"}
        self.assertEqual(EV.recompensas("riso", atual), {"humor": (1.0, 1.0)})
        self.assertEqual(EV.recompensas("aceitou", atual), {"fechamento": (1.0, 1.0)})


if __name__ == "__main__":
    unittest.main()
