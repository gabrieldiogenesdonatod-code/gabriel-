"""
Testes da 1.8 — acesso remoto (túneis, câmeras, Central) e WhatsApp.

Nada aqui usa a internet, a câmera ou o WhatsApp de verdade: a ponte Node roda
com um whatsapp-web.js FALSO (gerado na pasta temporária) que simula as
mensagens; sem Node no PC, esse teste é pulado.
"""
import json
import shutil
import subprocess
import time
import unittest
from unittest import mock

import tests
from core import resposta_remota as rr
from plugins import _camera_remota as cr, _painel_remoto as pr, _tunel, _whatsapp as W


class TestRegrasWhatsApp(unittest.TestCase):
    def test_numeros(self):
        self.assertTrue(W.mesmo_numero("62 99999-1234", "5562999991234"))
        self.assertTrue(W.mesmo_numero("+55 (62) 9 9999-1234", "62999991234"))
        self.assertTrue(W.mesmo_numero("6299991234", "62999991234"))          # sem o 9 extra
        self.assertTrue(W.mesmo_numero("99991234", "5562999991234"))          # sem DDD
        self.assertFalse(W.mesmo_numero("11999991234", "62999991234"))        # outro DDD
        self.assertFalse(W.mesmo_numero("123", "123"))

    def test_decidir(self):
        self.assertEqual(W.decidir({"eu": True, "chat": "x@c.us"}, [], [], ""), "dono")
        self.assertEqual(W.decidir({"chat": "a@lid"}, ["a@lid"], [], ""), "dono")
        self.assertEqual(W.decidir({"chat": "b@c.us", "numero": "5562999991234"}, [], ["62999991234"], ""), "dono")
        self.assertEqual(W.decidir({"chat": "c@c.us", "texto": "oi jabc23"}, [], [], "JABC23"), "parear")
        self.assertEqual(W.decidir({"chat": "c@c.us", "texto": "oi"}, [], ["11988887777"], "JABC23"), "ignorar")

    def test_comandos_rapidos(self):
        self.assertEqual(W.comando_rapido("Foto"), ("foto", 0))
        self.assertEqual(W.comando_rapido("foto 2"), ("foto", 1))
        self.assertEqual(W.comando_rapido("manda uma foto da câmera"), ("foto", 0))
        self.assertEqual(W.comando_rapido("Tela!"), ("tela", 0))
        self.assertEqual(W.comando_rapido("como está o pc?"), ("status", 0))
        self.assertEqual(W.comando_rapido("sim, confirmar"), ("confirmar", 0))
        self.assertEqual(W.comando_rapido("cancela"), ("cancelar", 0))
        self.assertEqual(W.comando_rapido("link"), ("link", 0))
        self.assertEqual(W.comando_rapido("liga a tv da sala"), ("", 0))
        self.assertEqual(W.comando_rapido("tira uma foto minha e manda pra minha mãe agora mesmo por favor"), ("", 0))


class TestFluxoWhatsApp(unittest.TestCase):
    def setUp(self):
        self._arq = W.ARQ
        W.ARQ = tests.TMP / "whatsapp_t.json"
        W.ARQ.unlink(missing_ok=True)
        self.enviadas = []
        self.p = [mock.patch.object(W, "enviar", lambda chat, texto="", arquivo=None: self.enviadas.append((chat, texto, arquivo)) or True),
                  mock.patch.object(W, "enviar_donos_para_ponte", lambda: None),
                  mock.patch.object(W, "numeros_dono", lambda: [])]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        W.ARQ = self._arq
        rr.encerrar()

    def test_pareamento_e_pedido(self):
        W.tratar({"chat": "z@c.us", "texto": "oi"})
        self.assertEqual(self.enviadas, [])                                   # estranho: silêncio
        cod = W.novo_codigo()
        W.tratar({"chat": "z@c.us", "texto": f"meu código {cod.lower()}"})
        self.assertIn("z@c.us", W.dados()["ids"])
        self.assertIn("agora fala com o J.A.R.V.I.S", self.enviadas[-1][1])
        W.tratar({"chat": "z@c.us", "texto": "ajuda"})
        self.assertIn("Atalhos", self.enviadas[-1][1])
        pedidos = []

        def pedir(texto, responder, fonte="", silencio=True):
            pedidos.append((texto, silencio))
            responder("A TV da sala foi ligada.")
            return True
        with mock.patch.object(rr, "pedir", pedir):
            W.tratar({"chat": "z@c.us", "texto": "liga a tv da sala"})
        self.assertIn("[Mensagem do dono pelo WhatsApp] liga a tv da sala", pedidos[0][0])
        self.assertTrue(pedidos[0][1])                                         # não fala em casa
        self.assertEqual(self.enviadas[-1], ("z@c.us", "A TV da sala foi ligada.", None))

    def test_confirmar_pelo_whats(self):
        from core import confirm
        feito = []
        confirm.bind(lambda t, d: None, lambda: None)
        confirm.request("teste", "Desligar a TV?", "", lambda: feito.append(1) or "ok")
        W.tratar({"chat": "eu@c.us", "eu": True, "texto": "confirmar"})
        self.assertIn("Confirmado: Desligar a TV?", self.enviadas[-1][1])
        for _ in range(50):
            if feito:
                break
            time.sleep(0.02)
        self.assertEqual(feito, [1])
        W.tratar({"chat": "eu@c.us", "eu": True, "texto": "confirmar"})
        self.assertIn("Não há nada", self.enviadas[-1][1])
        confirm.bind(None, None)


class TestRespostaRemota(unittest.TestCase):
    def tearDown(self):
        rr.encerrar()

    def test_ida_e_volta(self):
        recebidas = []

        class App:
            def comando_remoto(self, texto, fonte):
                self.texto = texto
                return True
        app = App()
        with mock.patch("core.registro_ferramentas.app", lambda: app):
            self.assertTrue(rr.pedir("oi", recebidas.append))
        self.assertEqual(app.texto, "oi")
        self.assertTrue(rr.silenciar())
        rr.publicar("Olá!")
        for _ in range(50):
            if recebidas:
                break
            time.sleep(0.02)
        self.assertEqual(recebidas, ["Olá!"])
        rr.encerrar()
        self.assertFalse(rr.silenciar())
        rr.publicar("ninguém ouve")                                             # sem pedido: não faz nada
        with mock.patch("core.registro_ferramentas.app", lambda: None):
            self.assertFalse(rr.pedir("oi", recebidas.append))                 # sem JARVIS rodando
        self.assertFalse(rr.ativo())


class TestTunelECameras(unittest.TestCase):
    def test_tailscale(self):
        saida = json.dumps({"BackendState": "Running", "Self": {"TailscaleIPs": ["100.101.102.103", "fd7a::1"],
                                                                "DNSName": "pc-casa.tail1234.ts.net.", "UserID": 7},
                            "User": {"7": {"LoginName": "dono@exemplo.com"}}})
        s = _tunel.ler_status_tailscale(saida)
        self.assertEqual((s["estado"], s["ip"], s["nome"], s["conta"]),
                         ("Running", "100.101.102.103", "pc-casa.tail1234.ts.net", "dono@exemplo.com"))
        self.assertEqual(_tunel.ler_status_tailscale("lixo")["estado"], "erro")

    def test_cloudflare_e_link(self):
        linha = "2026-11-02 INF |  https://gato-azul-rede-xyz.trycloudflare.com                  |"
        self.assertEqual(_tunel.achar_url_cloudflare(linha), "https://gato-azul-rede-xyz.trycloudflare.com")
        self.assertEqual(_tunel.achar_url_cloudflare("nada aqui"), "")

        class Srv:
            def new_key(self, s):
                return "ABCD1234"
        self.assertEqual(_tunel.link_de_entrada("https://x.trycloudflare.com/", Srv()),
                         "https://x.trycloudflare.com/auto-login?key=ABCD1234")

    def test_cameras_ip(self):
        lista = cr.ler_cameras_ip("Garagem=rtsp://u:s@192.168.0.30/stream1; Portão = http://192.168.0.31/snap.jpg;"
                                  " ruim=ftp://x; semigual")
        self.assertEqual([c["nome"] for c in lista], ["Garagem", "Portão"])

    def test_central_so_controle(self):
        self.assertIn("não permitida", pr.acao_aparelho({"acao": "rodar", "aparelho": "PC"}))
        self.assertIn("não permitida", pr.acao_aparelho({"acao": "remover", "aparelho": "PC"}))
        with mock.patch("plugins.aparelhos.run", lambda p: f"ok {p['action']} {p['aparelho']} {p.get('tecla', '')}"):
            self.assertEqual(pr.acao_aparelho({"acao": "tecla", "aparelho": "TV", "tecla": "home"}), "ok tecla TV home")


@unittest.skipUnless(shutil.which("node"), "sem Node.js")
class TestPonteNode(unittest.TestCase):
    """Roda a ponte de verdade com um whatsapp-web.js falso."""

    FALSO = r"""
const { EventEmitter } = require("events"); const fs = require("fs");
const roteiro = JSON.parse(fs.readFileSync(process.env.ROTEIRO, "utf8"));
class Client extends EventEmitter {
  constructor() { super(); this.info = { wid: { user: "5562900000000", _serialized: "5562900000000@c.us" } }; }
  async initialize() {
    this.emit("qr", "QR-FALSO"); this.emit("authenticated"); this.emit("ready");
    for (const m of roteiro) setTimeout(() => this.emit(m.evento, Object.assign({
      isStatus: false, hasMedia: false, type: "chat", timestamp: 1,
      async getContact() { return { number: m.numero || "" }; } }, m, { id: { _serialized: m.id } })), 300);
  }
  async sendMessage(para, conteudo, op) {
    fs.appendFileSync(process.env.SAIDA, JSON.stringify({ para, conteudo: String(conteudo), op }) + "\n");
    return { id: { _serialized: "enviada-" + Date.now() } };
  }
  async destroy() {}
}
class LocalAuth { constructor() {} }
class MessageMedia { static fromFilePath(p) { return "MIDIA:" + p; } }
module.exports = { Client, LocalAuth, MessageMedia };
"""
    QR = "module.exports = { toDataURL: async () => 'data:', toFile: async () => {} };"

    def test_ponte(self):
        pasta = tests.TMP / "ponte"
        for mod, codigo in (("whatsapp-web.js", self.FALSO), ("qrcode", self.QR)):
            (pasta / "node_modules" / mod).mkdir(parents=True, exist_ok=True)
            (pasta / "node_modules" / mod / "index.js").write_text(codigo, encoding="utf-8")
        shutil.copy(tests.RAIZ / "whatsapp_ponte" / "ponte.js", pasta / "ponte.js")
        roteiro = [
            {"evento": "message", "id": "1", "from": "estranho@c.us", "to": "5562900000000@c.us", "body": "oi", "fromMe": False},
            {"evento": "message", "id": "2", "from": "grupo@g.us", "to": "x", "body": "JARVIS", "fromMe": False},
            {"evento": "message_create", "id": "3", "from": "5562900000000@c.us", "to": "5562900000000@c.us",
             "body": "status", "fromMe": True},
            {"evento": "message", "id": "3", "from": "5562900000000@c.us", "to": "5562900000000@c.us",
             "body": "status", "fromMe": True},                                     # repetida: só uma vez
            {"evento": "message_create", "id": "4", "from": "5562900000000@c.us", "to": "amigo@c.us",
             "body": "oi amigo", "fromMe": True},                                   # você falando com outra pessoa
            {"evento": "message_create", "id": "5", "from": "5562900000000@c.us", "to": "5562900000000@c.us",
             "body": "🤖 resposta do jarvis", "fromMe": True},                       # eco da própria resposta
            {"evento": "message", "id": "6", "from": "novo@lid", "to": "x", "body": "meu codigo JXYZ99", "fromMe": False,
             "numero": "5562988887777"},
        ]
        (pasta / "roteiro.json").write_text(json.dumps(roteiro), encoding="utf-8")
        saida = pasta / "saida.jsonl"
        import os
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        env = dict(os.environ, JARVIS_WA_PORTA=str(porta), JARVIS_WA_TOKEN="t" * 24, JARVIS_WA_SESSAO=str(pasta / "s"),
                   ROTEIRO=str(pasta / "roteiro.json"), SAIDA=str(saida))
        proc = subprocess.Popen(["node", "ponte.js"], cwd=pasta, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        antigo = dict(W._p)
        try:
            W._p.update(porta=porta, token="t" * 24, proc=proc)
            for _ in range(50):
                if W._http("GET", "/estado", timeout=1).get("estado") == "pronto":
                    break
                time.sleep(0.1)
            self.assertEqual(W._http("GET", "/estado")["numero"], "5562900000000")
            self.assertEqual(W._http("POST", "/donos", {"ids": [], "codigo": "JXYZ99"})["ok"], True)
            time.sleep(1.2)
            evs = W._http("GET", "/eventos?desde=0")["eventos"]
            self.assertEqual([(e["chat"], e["texto"], e["eu"]) for e in evs],
                             [("5562900000000@c.us", "status", True), ("novo@lid", "meu codigo JXYZ99", False)])
            self.assertEqual(evs[1]["numero"], "5562988887777")
            self.assertTrue(W.enviar("5562900000000@c.us", "olá"))
            self.assertFalse(W.enviar("grupo@g.us", "não"))                      # só conversas privadas
            linhas = [json.loads(x) for x in saida.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(linhas, [{"para": "5562900000000@c.us", "conteudo": "🤖 olá"}])
            self.assertEqual(_status_sem_token(porta), 403)
        finally:
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            W._p.clear()
            W._p.update(antigo)
        self.assertEqual(proc.returncode, 0)                                     # fechou sozinha com o JARVIS


def _status_sem_token(porta: int) -> int:
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{porta}/estado", timeout=3)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


if __name__ == "__main__":
    unittest.main()
