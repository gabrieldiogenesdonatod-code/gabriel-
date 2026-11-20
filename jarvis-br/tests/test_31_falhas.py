"""
Testes da 2.6.1 — o JARVIS não fecha mais sozinho: erro em janela/thread vira
registro em memory/erros.log, a sessão sobe de novo se cair, e o "shutdown"
só fecha o programa com um pedido claro ("fecha o Jarvis").
"""
import sys
import threading
import time
import unittest

from core import protecao_falhas as P
from tests import RAIZ, TMP


class TestFalhas(unittest.TestCase):
    def setUp(self):
        P.ARQ = TMP / "erros.log"
        P.ARQ.unlink(missing_ok=True)
        P._estado["ultimos"].clear()

    def test_erro_vira_registro(self):
        try:
            1 / 0
        except ZeroDivisionError:
            P._hook(*sys.exc_info())                                   # o que o PyQt chamaria
        self.assertIn("ZeroDivisionError", P.ARQ.read_text(encoding="utf-8"))

    def test_erro_em_thread(self):
        antigo = threading.excepthook
        threading.excepthook = P._hook_thread
        try:
            t = threading.Thread(target=lambda: [][1], name="teste_quebra")
            t.start()
            t.join()
        finally:
            threading.excepthook = antigo
        self.assertIn("teste_quebra", P.ARQ.read_text(encoding="utf-8"))

    def test_protegido_tenta_de_novo(self):
        chamadas = []

        def instavel():
            chamadas.append(1)
            if len(chamadas) < 3:
                raise RuntimeError("caiu")
            return "ok"
        self.assertEqual(P.protegido("teste", instavel, espera_s=0), "ok")
        self.assertEqual(len(chamadas), 3)
        self.assertIsNone(P.protegido("sempre", lambda: 1 / 0, tentativas=2, espera_s=0))

    def test_so_fecha_com_pedido_claro(self):
        for t in ("Jarvis, fecha o programa", "desliga o jarvis", "pode fechar", "Jarvis, desliga", "fecha o Jarvis",
                  "Jarvis, pode se desligar? não, pode desligar você", "encerra o programa por favor"):
            self.assertTrue(P.pedido_de_fechar(t), t)
        for t in ("tchau", "para", "chega por hoje", "desliga o intérprete", "para a vitrine", "desliga a luz",
                  "tchau Maria, até amanhã", "",
                  # 2.7.2: o nome "Jarvis" no começo não é o alvo
                  "Jarvis, fecha o Discord", "Jarvis, fecha essa pasta", "Jarvis, sai do jogo",
                  "Jarvis, encerra o processo do Chrome", "Jarvis, fecha tudo", "Jarvis, desliga o PC daqui a pouco",
                  "Jarvis, finaliza a tarefa", "fecha o bloco de notas, Jarvis"):
            self.assertFalse(P.pedido_de_fechar(t), t)

    def test_queda_anterior(self):
        P.ARQ.write_text("=== x · JARVIS iniciado ===\nFatal Python error: Segmentation fault\nThread 0x1\n",
                         encoding="utf-8")
        self.assertIn("Segmentation fault", P.queda_anterior())
        P.ARQ.write_text("=== y · JARVIS iniciado ===\ntudo certo\n", encoding="utf-8")
        self.assertEqual(P.queda_anterior(), "")

    def test_versao_da_pasta(self):
        self.assertRegex(P.versao(), r"^\d+\.\d+")

    def test_motivo_da_ultima_saida(self):
        P.ARQ.write_text("=== a · JARVIS iniciado ===\n=== b · JARVIS fechado: pedido de fechar: \"fecha o jarvis\" ===\n",
                         encoding="utf-8")
        self.assertIn("fecha o jarvis", P.como_fechou_da_ultima_vez())
        P.ARQ.write_text("=== a · JARVIS iniciado ===\nnada\n", encoding="utf-8")
        self.assertEqual(P.como_fechou_da_ultima_vez(), "sem registro")     # morto de fora
        P.ARQ.write_text("=== a · JARVIS iniciado ===\nWindows fatal exception: access violation\n", encoding="utf-8")
        self.assertEqual(P.como_fechou_da_ultima_vez(), "queda")
        self.assertIn("access violation", P.queda_anterior())
        P._estado.pop("saida", None)
        P.ARQ.write_text("=== c · JARVIS iniciado ===\n", encoding="utf-8")
        P.registrar_saida("teste")
        P.registrar_saida("outro")                                            # só o primeiro motivo vale
        self.assertEqual(P.como_fechou_da_ultima_vez(), "teste")
        P._estado.pop("saida", None)

    def test_interromper_nao_mexe_na_placa(self):
        """A 2.6.2 tirou o abort()+start() da placa de som, que derrubava o Python no Windows."""
        codigo = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("descartar_saida, stream", codigo)
        # 2.7.3: nenhum arquivo do projeto chama abort() em stream de áudio (fechava o JARVIS no INTERROMPER)
        for arq in list(RAIZ.glob("*.py")) + list((RAIZ / "core").glob("*.py")) + list((RAIZ / "plugins").glob("*.py")):
            texto = arq.read_text(encoding="utf-8", errors="ignore")
            self.assertNotRegex(texto, r"(stream|st|saida|placa|_out)\w*\.abort\(\)", arq.name)

    def test_placa_nao_fecha_no_meio_da_escrita(self):
        """2.7.4: ao reconectar (sessão caiu), fechar a saída de som enquanto a thread ainda escrevia
        derrubava o Python. A escrita e o fechamento passam pela mesma trava."""
        codigo = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn("_escrever_placa, bytes(batch)", codigo)
        self.assertNotIn("escrever_cortavel, stream.write", codigo)
        self.assertNotRegex(codigo, r"finally:\s+self\.set_speaking\(False\)\s+stream\.stop\(\)")
        self.assertIn('target=_fechar_placa', codigo)

    def test_keepalive_da_sessao(self):
        """2.7.4: sem nada para enviar, o Gemini fechava a sessão (1008 client inactivity)."""
        codigo = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn("wait_for(self.out_queue.get(), timeout=_KEEPALIVE_S)", codigo)
        self.assertIn("_SILENCIO_KEEPALIVE = bytes(int(SEND_SAMPLE_RATE * 0.1) * 2)", codigo)

    def test_trava_simulada(self):
        """A mesma trava do main.py: o fechamento espera a escrita em andamento e depois nada mais escreve."""
        import threading
        eventos, trava, fechada = [], threading.Lock(), [False]
        escrevendo = threading.Event()

        def escrever(_d):
            with trava:
                if not fechada[0]:
                    escrevendo.set()
                    time.sleep(0.05)
                    eventos.append("escreveu")

        def fechar():
            with trava:
                fechada[0] = True
                eventos.append("fechou")
        t = threading.Thread(target=escrever, args=(b"x",))
        t.start()
        escrevendo.wait(1)
        fechar()
        escrever(b"y")
        t.join()
        self.assertEqual(eventos, ["escreveu", "fechou"])

    def test_main_usa_a_protecao(self):
        codigo = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn("_pf.instalar()", codigo)
        self.assertIn("_pf.pedido_de_fechar", codigo)
        self.assertIn("_pf.protegido(", codigo)


if __name__ == "__main__":
    unittest.main()
