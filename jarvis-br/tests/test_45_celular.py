"""Testes da 2.18 — JARVIS no celular (celular/jarvis_celular.py) com um Gemini falso, sem rede."""
import json
import sys
import unittest
from unittest import mock

import tests
from tests import RAIZ

sys.path.insert(0, str(RAIZ / "celular"))
import jarvis_celular as jc  # noqa: E402


def _resp(*partes):
    return {"candidates": [{"content": {"role": "model", "parts": list(partes)}}]}


def gemini_falso(modelo, corpo, chave, t):
    ult = corpo["contents"][-1]["parts"][0]
    if "functionResponse" in ult:
        return _resp({"text": "ok: " + ult["functionResponse"]["response"]["resultado"]})
    txt = ult.get("text", "")
    if "conta" in txt:
        return _resp({"functionCall": {"name": "calculadora", "args": {"action": "conta", "expressao": "6*7"}}})
    if "juros" in txt:
        return _resp({"functionCall": {"name": "usar_ferramenta",
                                       "args": {"nome": "juros", "parametros": json.dumps({"action": "simples", "valor": "100",
                                                                                           "taxa": "1", "meses": "2"})}}})
    if "procura" in txt:
        return _resp({"functionCall": {"name": "buscar_ferramentas", "args": {"pergunta": "fase da lua"}}})
    return _resp({"text": "Às suas ordens."})


class TestCelular(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from memory import config_manager as cm
        from plugins import modos
        cls.p = [mock.patch.object(cm, "CONFIG_FILE", tests.TMP / "api_celular.json"),
                 mock.patch.object(modos, "ARQ_ESTADO", tests.TMP / "modo_cel.json"),
                 mock.patch.object(modos, "_rodar", lambda passos, player: [])]
        for x in cls.p:
            x.start()
        (tests.TMP / "api_celular.json").write_text(json.dumps({"gemini_api_key": "x"}))
        cls.motor = jc.iniciar(llm=gemini_falso)

    @classmethod
    def tearDownClass(cls):
        for x in cls.p:
            x.stop()

    def test_conversa_e_ferramentas(self):
        self.assertEqual(self.motor.conversar("oi")["resposta"], "Às suas ordens.")
        r = self.motor.conversar("faz a conta")
        self.assertEqual((r["ferramentas"], r["resposta"]), (["calculadora"], "ok: 6*7 = 42"))
        self.assertIn("R$ 2,00", self.motor.conversar("juros")["resposta"])
        self.assertIn("astronomia", self.motor.conversar("procura")["resposta"])

    def test_modo_no_sistema(self):
        from plugins import modos
        modos.entrar("pirata")
        self.assertIn("MODO PIRATA", self.motor.sistema())
        modos.sair()
        self.assertNotIn("MODO PIRATA", self.motor.sistema())

    def test_schemas_e_estado(self):
        decl = self.motor.ferramentas()
        self.assertGreaterEqual(len(decl), 20)
        json.dumps(decl)
        for d in self.motor.declaracoes():                  # nenhum schema derruba a limpeza
            jc.limpar_schema(d["parameters"])
        e = jc.estado()
        self.assertGreaterEqual(e["total_plugins"], 250)
        self.assertGreaterEqual(len(e["modos"]), 64)

    def test_falas_dos_plugins(self):
        n = jc.EVENTOS.n
        jc.PLAYER.request_say("[GUIA] Diga exatamente, sem chamar ferramenta: Inspire… 4")
        jc.PLAYER.request_say("[TIMER] Diga ao usuário, em UMA frase curta e no idioma da conversa: Timer 'bolo' acabou! "
                              "Não chame nenhuma ferramenta.")
        falas = [e["texto"] for e in jc.EVENTOS.desde(n) if e["tipo"] == "fala"]
        self.assertEqual(falas, ["Inspire… 4", "Timer 'bolo' acabou!"])

    def test_sem_chave(self):
        with mock.patch.object(self.motor, "chave_fn", lambda: ""):
            self.assertEqual(self.motor.conversar("oi")["erro"], "chave")

    def test_cliente_rest(self):
        with mock.patch.object(jc, "gemini_rest", lambda m, c, k, t: _resp({"text": c["contents"][0]["parts"][0]["text"]})):
            self.assertEqual(jc._ClienteREST("k", 1000).models.generate_content("m", "eco").text, "eco")


if __name__ == "__main__":
    unittest.main()
