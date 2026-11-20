"""Testes da 3.9.4 — cérebro pronto (core/cerebro_base.json + core/cerebro_treino.py). Sem Gemini e sem os seus dados."""
import importlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests.test_52_v33 import trocar


class Base(unittest.TestCase):
    def setUp(self):
        global C
        C = importlib.import_module("core.cerebro")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        trocar(self, "core.cerebro", "ARQ", self.tmp / "cerebro.json")     # nada aprendido do usuário
        C._cache.pop("modelo", None)
        C._turno.clear()
        C._anterior["chave"] = None

    def faz(self, frase, ferramenta, args=None, action=None):
        r = C.entender(frase, sem_ia=True)
        self.assertEqual(r["ferramenta"], ferramenta, (frase, r))
        if args is not None:
            self.assertEqual(r["args"], args, (frase, r))
        if action is not None:
            self.assertEqual(r["args"].get("action"), action, (frase, r))
        self.assertTrue(r["reflexo"], (frase, r))
        return r


class TestArquivo(Base):
    def test_base_existe_e_e_grande(self):
        b = C.base()
        self.assertGreater(len(b["_mapa"]), 3000)
        self.assertGreaterEqual(len(b["_re"]), 10)
        self.assertGreater(C.estado()["base"], 3000)

    def test_treino_valida_e_passa_na_prova(self):
        T = importlib.import_module("core.cerebro_treino")
        exemplos, _ = T.gerar()
        self.assertEqual(T.validar(exemplos), [])
        nota, falhas = T.prova(T.montar(exemplos))
        self.assertGreaterEqual(nota, T.NOTA_MINIMA, falhas)

    def test_base_sem_nada_perigoso(self):
        perigosos = {"shutdown", "restart", "desligar_pc", "formatar", "delete", "apagar"}
        for e in C.base()["exemplos"]:
            self.assertNotIn(str(e["a"].get("action")), perigosos, e)
        self.assertNotIn("file_controller", {e["f"] for e in C.base()["exemplos"]})

    def test_expandir(self):
        T = importlib.import_module("core.cerebro_treino")
        self.assertEqual(sorted(T.expandir("(a|b) [c] d")), ["a c d", "a d", "b c d", "b d"])
        self.assertEqual(sorted(T.expandir("x (y|(z|w) k)")), ["x w k", "x y", "x z k"])


class TestPrimeiroDia(Base):
    def test_comandos_sem_gemini(self):
        self.faz("Jarvis, aumenta o som", "computer_settings", action="volume_up")
        self.faz("não tô ouvindo nada", "computer_settings", action="volume_up")
        self.faz("pula essa música", "musica", action="proxima")
        self.faz("por que o meu notebook tá travando tanto?", "monitor_sistema", action="pesando")
        self.faz("acende a luz do quarto", "casa_inteligente", {"action": "ligar", "aparelho": "luz do quarto"})
        self.faz("abre o spotify", "open_app", {"app_name": "spotify"})

    def test_padroes_com_lacuna(self):
        self.faz("abre o davinci resolve", "open_app", {"app_name": "davinci resolve"})
        self.faz("toca Legião Urbana por favor", "musica", {"action": "tocar", "pedido": "legiao urbana"})
        self.faz("volume em 40%", "controle_audio_video", {"action": "volume", "nivel": "40"})
        self.faz("põe um timer de 10 minutos pro bolo", "cronometros", {"action": "timer", "tempo": "10 minutos", "nome": "bolo"})
        self.faz("gastei 40 no almoço", "gastos", {"action": "registrar", "valor": "40", "descricao": "almoco", "categoria": "outros"})

    def test_nao_faz_o_que_nao_deve(self):
        for frase in ("qual a capital da França", "fecha o jarvis", "fecha a janela da cozinha", "abre a porta",
                      "desliga o computador", "formata o pc", "reinicia o pc", "liga o modo leitura", "quero desligar tudo",
                      "apaga o arquivo relatorio", "toca o telefone"):
            self.assertFalse(C.entender(frase, sem_ia=True)["reflexo"], frase)

    def test_com_gemini_a_base_so_sugere(self):
        r = C.entender("aumenta o som")
        self.assertEqual(r["ferramenta"], "computer_settings")
        self.assertFalse(r["reflexo"])
        self.assertFalse(C.entender("abre o davinci resolve")["reflexo"])
        self.assertIn("computer_settings", C.sugerir("aumenta o som"))

    def test_critico_e_reflexo_desligado(self):
        with mock.patch("core.verificacao.nivel_de", return_value="critico"):
            self.assertFalse(C.entender("aumenta o som", sem_ia=True)["reflexo"])
            self.assertFalse(C.entender("abre o davinci resolve", sem_ia=True)["reflexo"])
        C.ligar_reflexos(False)
        self.assertFalse(C.entender("aumenta o som", sem_ia=True)["reflexo"])
        C.ligar_reflexos(True)


class TestVoceVence(Base):
    def test_o_que_voce_ensina_vence_a_base(self):
        C.ensinar("aumenta o som", "controle_audio_video", {"action": "volume", "nivel": "mais"})
        r = C.entender("aumenta o som", sem_ia=True)
        self.assertEqual((r["ferramenta"], r["args"]), ("controle_audio_video", {"action": "volume", "nivel": "mais"}))

    def test_correcao_desliga_a_base_naquela_frase(self):
        C.anotar_chamada("computer_settings", {"action": "volume_up"}, "Feito.")
        C.turno("aumenta o som")
        C.turno("não, não foi isso")
        self.assertFalse(C.entender("aumenta o som", sem_ia=True)["reflexo"])

    def test_base_temporaria_nao_vaza(self):
        n = len(C.base()["_mapa"])
        with C.base_temporaria({"exemplos": [{"k": "frase unica teste", "f": "musica", "a": {"action": "tocar"}}], "padroes": []}):
            self.assertEqual(len(C.base()["_mapa"]), 1)
        self.assertEqual(len(C.base()["_mapa"]), n)


if __name__ == "__main__":
    unittest.main()
