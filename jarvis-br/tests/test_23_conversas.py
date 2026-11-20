"""
Testes da 2.3 — WhatsApp pessoal (ler, mandar, rascunho, resposta automática,
modo ausente), secretária de ligações do WhatsApp, recados e o atendente de
voz da Twilio. Nada usa o WhatsApp, a Twilio ou a internet de verdade.
"""
import json
import shutil
import subprocess
import time
import unittest
from unittest import mock

import tests
from plugins import _atendente_voz as A
from plugins import _recados as R
from plugins import _whatsapp as W
from plugins import _whatsapp_pessoal as P
from plugins import whatsapp_conversas as WC


class Base(unittest.TestCase):
    """Arquivos de dados vão para a pasta temporária; o WhatsApp e a IA são falsos."""

    CONFIG = {"modo_pessoal": True, "rascunho_pessoal": True, "auto_contatos": "Mãe, 62 98888-1111",
              "secretaria": True, "nome_dono": "Rafael", "avisos": True}

    def setUp(self):
        self.enviadas, self.donos, self.rascunhos = [], [], []
        self._arqs = (W.ARQ, R.ARQ)
        W.ARQ = tests.TMP / f"wa_{self.id()}.json"
        R.ARQ = tests.TMP / f"rec_{self.id()}.json"
        self.cfg = dict(self.CONFIG)
        self.p = [mock.patch.object(W, "config", lambda: self.cfg),
                  mock.patch.object(W, "enviar", lambda chat, texto="", arquivo=None, sem_prefixo=False:
                                    self.enviadas.append((chat, texto, sem_prefixo)) or True),
                  mock.patch.object(W, "para_donos", lambda texto, arquivo=None: self.donos.append(texto) or 1),
                  mock.patch.object(W, "rascunho_cliente", lambda ev, pessoal=False: self.rascunhos.append((ev, pessoal))),
                  mock.patch.object(P, "registrar", lambda *a: None),
                  mock.patch.object(P, "historico_texto", lambda chat, n=10: "Ana: oi")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        W.ARQ, R.ARQ = self._arqs


class TestRegras(unittest.TestCase):
    def test_decidir(self):
        self.assertEqual(W.decidir({"ligacao": True, "chat": "x"}, [], [], ""), "ligacao")
        self.assertEqual(W.decidir({"outro": True, "chat": "a@c.us"}, [], [], ""), "outro")
        self.assertEqual(W.decidir({"outro": True, "cliente": True, "contato": False, "chat": "a"}, [], [], ""), "cliente")
        self.assertEqual(W.decidir({"outro": True, "cliente": True, "contato": True, "chat": "a"}, [], [], ""), "outro")
        self.assertEqual(W.decidir({"outro": True, "cliente": True, "recado": True, "chat": "a"}, [], [], ""), "outro")
        self.assertEqual(W.decidir({"outro": True, "chat": "dono@c.us"}, ["dono@c.us"], [], ""), "dono")
        self.assertEqual(W.decidir({"chat": "a"}, [], [], ""), "ignorar")

    def test_liberado_freio_robo(self):
        lista = "Mãe, 62 98888-1111, joao"
        self.assertTrue(P.liberado({"nome": "Mae"}, lista))
        self.assertTrue(P.liberado({"nome": "João Silva"}, lista))
        self.assertTrue(P.liberado({"nome": "", "numero": "5562988881111"}, lista))
        self.assertFalse(P.liberado({"nome": "Ana", "numero": "5562977770000"}, lista))
        self.assertFalse(P.liberado({"nome": "Ana"}, ""))
        agora = 10_000.0
        self.assertTrue(P.pode_auto([], agora))
        self.assertFalse(P.pode_auto([agora - 5], agora))                   # respiro de 20 s
        self.assertFalse(P.pode_auto([agora - 100 * i - 30 for i in range(6)], agora))   # 6 por hora
        self.assertTrue(P.pode_auto([agora - 4000] * 10, agora))
        self.assertTrue(P.eh_robo("🤖 Assistente de Ana: oi"))
        self.assertTrue(P.eh_robo("Mensagem automática: estou fora"))
        self.assertFalse(P.eh_robo("oi, tudo bem?"))

    def test_textos(self):
        msgs = [{"deMim": False, "texto": "chega que horas?"}, {"deMim": True, "texto": "8h"},
                {"deMim": False, "texto": "", "tipo": "ptt"}]
        self.assertEqual(P.formatar_conversa("Ana", msgs, "Rafael"), "Ana: chega que horas?\nRafael: 8h\nAna: [áudio]")
        chats = [{"id": "a@c.us", "nome": "Ana", "naoLidas": 2, "ultima": {"texto": "e aí?"}},
                 {"id": "b@c.us", "nome": "Bia", "naoLidas": 0, "ultima": {"texto": "ok"}},
                 {"id": "556299@c.us", "nome": "", "naoLidas": 1, "ultima": {"tipo": "ptt", "texto": ""}}]
        self.assertEqual(P.resumo_chats(chats), "• Ana (2 novas): e aí?\n• 556299 (1 nova): [áudio]")
        self.assertIn("Assistente de Rafael", P.prompt_auto("Rafael", "Ana", "", "oi"))
        self.assertIn("NÃO invente", P.prompt_auto("Rafael", "Ana", "", "oi"))
        self.assertIn("O QUE ELE QUER DIZER: chego às 8", P.prompt_rascunho("Rafael", "Ana", "", "oi", "chego às 8"))
        self.assertEqual(P.assinatura(""), "Assistente virtual")


class TestRecados(unittest.TestCase):
    def setUp(self):
        self._a = R.ARQ
        R.ARQ = tests.TMP / "recados_t.json"
        R.limpar()

    def tearDown(self):
        R.ARQ = self._a

    def test_junta_e_lista(self):
        R.adicionar("whatsapp", "Ana", "5562977770000", "", "ana@c.us")
        R.adicionar("whatsapp", "Ana", "5562977770000", "me liga", "ana@c.us")
        R.adicionar("whatsapp", "Ana", "5562977770000", "é sobre a festa", "ana@c.us")
        R.adicionar("telefone", "", "+5511911112222", "aqui é o Zé")
        rs = R.todos()
        self.assertEqual(len(rs), 2)
        self.assertEqual(rs[0]["texto"], "me liga\né sobre a festa")
        t = R.texto_lista(rs, agora=rs[0]["ts"] + 30)
        self.assertIn("#1 Ana (WhatsApp, agora há pouco): me liga", t)
        self.assertIn("+5511911112222 (telefone", t)
        self.assertEqual(R.marcar_lidos(), 2)
        self.assertEqual(R.novos(), [])
        self.assertEqual(R.texto_lista([]), "Nenhum recado.")


class TestFluxoPessoal(Base):
    def test_ligacao_recusada_e_recado(self):
        P.tratar_ligacao({"ligacao": True, "chat": "ana@c.us", "numero": "5562977770000", "nome": "Ana Souza",
                          "rejeitada": True})
        self.assertEqual(self.enviadas[0][0], "ana@c.us")
        self.assertIn("Assistente de Rafael: Oi, Ana! Rafael não pode atender agora", self.enviadas[0][1])
        self.assertFalse(self.enviadas[0][2])                               # vai com o 🤖 da ponte
        self.assertIn("Ana Souza te ligou no WhatsApp — recusei", self.donos[0])
        # a pessoa responde com o recado (mesmo sem modo pessoal)
        self.cfg["modo_pessoal"] = False
        P.tratar_outro({"outro": True, "chat": "ana@c.us", "numero": "5562977770000", "nome": "Ana Souza",
                        "texto": "me liga quando puder"})
        self.assertIn("Anotado!", self.enviadas[-1][1])
        self.assertIn("Recado de *Ana Souza*: me liga quando puder", self.donos[-1])
        self.assertEqual(R.novos()[0]["texto"], "me liga quando puder")
        P.tratar_outro({"outro": True, "chat": "ana@c.us", "numero": "5562977770000", "nome": "Ana Souza",
                        "texto": "é urgente"})
        self.assertEqual(sum("Anotado" in t for _c, t, _s in self.enviadas), 1)   # agradece uma vez só
        self.assertEqual(R.novos()[0]["texto"], "me liga quando puder\né urgente")

    def test_ligacao_do_dono(self):
        P.tratar_ligacao({"ligacao": True, "dono": True, "chat": "eu@c.us", "rejeitada": True})
        self.assertIn("Mande um *áudio*", self.enviadas[0][1])
        self.assertEqual(self.donos, [])

    def test_rascunho_por_padrao(self):
        P.tratar_outro({"outro": True, "chat": "ana@c.us", "nome": "Ana", "numero": "5562977770000", "texto": "vem hoje?"})
        self.assertEqual(self.enviadas, [])                                   # nada enviado sozinho
        self.assertEqual((self.rascunhos[0][0]["texto"], self.rascunhos[0][1]), ("vem hoje?", True))

    def test_automatico_liberado_e_ausente(self):
        from plugins import _ia
        with mock.patch.object(_ia, "disponivel", lambda: True), \
                mock.patch.object(_ia, "perguntar", lambda *a, **k: "Oi! Ele não pode responder agora, eu aviso."):
            P.tratar_outro({"outro": True, "chat": "mae@c.us", "nome": "Mãe", "numero": "5562900000001", "texto": "filho?"})
            self.assertEqual(self.enviadas[-1], ("mae@c.us", "Assistente de Rafael: Oi! Ele não pode responder agora, "
                                                             "eu aviso.", False))
            P.tratar_outro({"outro": True, "chat": "mae@c.us", "nome": "Mãe", "texto": "e aí?"})   # freio: 20 s
            self.assertEqual(len(self.enviadas), 1)
            self.assertEqual(len(self.rascunhos), 1)                              # vira rascunho
            P.tratar_outro({"outro": True, "chat": "ana@c.us", "nome": "Ana", "texto": "oi"})       # Ana não liberada
            self.assertEqual(len(self.enviadas), 1)
            self.assertIn("Modo ausente ligado por 30", P.definir_ausente(True, 30))
            P.tratar_outro({"outro": True, "chat": "ana@c.us", "nome": "Ana", "texto": "oi"})
            self.assertEqual(self.enviadas[-1][0], "ana@c.us")
            P.tratar_outro({"outro": True, "chat": "bot@c.us", "nome": "Loja X", "texto": "🤖 Assistente de X: oi"})
            self.assertEqual(self.enviadas[-1][0], "ana@c.us")                     # nunca responde robô
            P.definir_ausente(False)
            self.assertFalse(P.ausente())

    def test_tratar_encaminha(self):
        chamados = []
        with mock.patch.object(P, "tratar_outro", lambda ev: chamados.append("outro")), \
                mock.patch.object(P, "tratar_ligacao", lambda ev: chamados.append("ligacao")):
            W.tratar({"chat": "a@c.us", "outro": True, "texto": "oi"})
            W.tratar({"chat": "a@c.us", "ligacao": True})
        self.assertEqual(chamados, ["outro", "ligacao"])


class TestFerramenta(Base):
    def test_ligar_modos(self):
        salvos = []
        with mock.patch.object(WC, "salvar_cfg", lambda ns, v: salvos.append((ns, v))), \
                mock.patch.object(W, "enviar_donos_para_ponte", lambda: None):
            self.assertIn("Secretária ligada", WC.run({"action": "secretaria", "valor": "ligar"}))
            self.assertIn("Modo pessoal desligado", WC.run({"action": "pessoal", "valor": "desliga"}))
            self.assertIn("Ana liberado", WC.run({"action": "liberar", "contato": "Ana"}))
            self.assertIn("fora da resposta", WC.run({"action": "bloquear", "contato": "mãe"}))
        self.assertEqual(salvos, [("whatsapp", {"secretaria": True}), ("whatsapp", {"modo_pessoal": False}),
                                  ("whatsapp", {"auto_contatos": "Mãe, 62 98888-1111, Ana"}),
                                  ("whatsapp", {"auto_contatos": "62 98888-1111"})])
        self.assertIn("secretária ligada", WC.run({"action": "status"}))

    def test_mandar_com_confirmacao(self):
        pedidos = []

        def confirmar(chave, titulo, detalhe, acao):
            pedidos.append((titulo, detalhe))
            return acao()
        with mock.patch.object(W, "pronto", lambda: True), mock.patch.object(WC, "confirmar", confirmar), \
                mock.patch.object(WC, "registrar", lambda *a: None), \
                mock.patch.object(P, "achar", lambda nome: [{"id": "ana@c.us", "nome": "Ana", "numero": "55"}]):
            self.assertEqual(WC.run({"action": "mandar", "contato": "ana", "texto": "chego às 8"}), "Mandei para Ana.")
        self.assertEqual(pedidos, [("Mandar para Ana", "“chego às 8”")])
        self.assertEqual(self.enviadas, [("ana@c.us", "chego às 8", True)])     # com as SUAS palavras, sem 🤖

    def test_ambiguo_e_ler(self):
        with mock.patch.object(W, "pronto", lambda: True), \
                mock.patch.object(P, "achar", lambda nome: [{"id": "1@c.us", "nome": "Ana Souza"},
                                                            {"id": "2@c.us", "nome": "Ana Lima"}]):
            self.assertIn("Ana Souza, Ana Lima. Qual deles?", WC.run({"action": "ler", "contato": "ana"}))
        with mock.patch.object(W, "pronto", lambda: True), \
                mock.patch.object(P, "achar", lambda nome: [{"id": "1@c.us", "nome": "Ana"}]), \
                mock.patch.object(P, "mensagens", lambda chat, n=15: [{"deMim": False, "texto": "bora?"}]):
            self.assertIn("Ana: bora?", WC.run({"action": "ler", "contato": "ana"}))
        with mock.patch.object(W, "pronto", lambda: False):
            self.assertIn("não está conectado", WC.run({"action": "novas"}))

    def test_rascunho_por_voz(self):
        with mock.patch.object(W, "pronto", lambda: True), \
                mock.patch.object(P, "achar", lambda nome: [{"id": "1@c.us", "nome": "Ana", "numero": "55"}]), \
                mock.patch.object(P, "mensagens", lambda chat, n=15: [{"deMim": False, "texto": "vem?"}]), \
                mock.patch("plugins._ia.disponivel", lambda: False):
            r = WC.run({"action": "rascunho", "contato": "ana", "texto": "vou sim, às 8"})
        self.assertIn("Rascunho #1 para Ana: “vou sim, às 8”", r)
        self.assertEqual(W.dados()["rascunhos"][0]["tipo"], "pessoal")


class TestAtendente(unittest.TestCase):
    CFG = {"sid": "AC1", "token": "segredo", "de": "+15550001111", "para": "+55 62 98888-7777", "pin": "4321",
           "atender": True, "url_publica": "https://x.trycloudflare.com"}

    def setUp(self):
        A.SESSOES.clear()
        self.avisos, self.recados = [], []
        self.cfg = dict(self.CFG)
        self.p = [mock.patch.object(A, "_c", lambda: self.cfg), mock.patch.object(A, "registrar", lambda *a: None),
                  mock.patch.object(A, "_dono_nome", lambda: "Rafael"),
                  mock.patch("plugins._canais.mandar", lambda t, *a, **k: self.avisos.append(t) or ["whatsapp"]),
                  mock.patch("plugins._recados.adicionar", lambda *a, **k: self.recados.append(a) or {}),
                  mock.patch("plugins._ia.disponivel", lambda: False)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_assinatura(self):
        params = {"CallSid": "CA1", "From": "+1", "SpeechResult": "oi"}
        url = "https://x.trycloudflare.com/twilio/fala"
        a = A.assinatura_twilio(url, params, "segredo")
        urls = A.urls_candidatas("https://x.trycloudflare.com/", "/twilio/fala", "", "outro.host")
        self.assertEqual(urls, [url, "https://outro.host/twilio/fala"])
        self.assertTrue(A.assinatura_valida(urls, params, a, "segredo"))
        self.assertFalse(A.assinatura_valida(urls, dict(params, SpeechResult="desliga o pc"), a, "segredo"))
        self.assertFalse(A.assinatura_valida(urls, params, a, "outro-token"))
        self.assertFalse(A.assinatura_valida(urls, params, "", "segredo"))

    def test_textos(self):
        self.assertEqual(A.limpar_fala("**Pronto!** Veja https://a.b/c 🚀 ok"), "Pronto! Veja o link ok")
        self.assertTrue(A.despedida("Tchau, Jarvis!"))
        self.assertTrue(A.despedida("só isso"))
        self.assertFalse(A.despedida("liga a tv"))
        x = A.twiml_ouvir("Diga & fale", "/twilio/pin", digitos=4)
        self.assertIn('input="dtmf speech"', x)
        self.assertIn('numDigits="4"', x)
        self.assertIn("Diga &amp; fale", x)
        self.assertIn('voice="Polly.Camila-Neural"', A.twiml_dizer("oi"))

    def test_visitante_deixa_recado(self):
        x = A.tratar("voz", {"CallSid": "C1", "From": "+5511911112222"})
        self.assertIn("assistente virtual de Rafael", x)
        self.assertIn('action="/twilio/fala"', x)
        x = A.tratar("fala", {"CallSid": "C1", "SpeechResult": "Aqui é o Zé, sobre o orçamento"})
        self.assertIn("Anotado. Quer acrescentar", x)                        # sem IA: roteiro fixo
        x = A.tratar("fala", {"CallSid": "C1", "SpeechResult": "é urgente"})
        self.assertIn("<Hangup/>", x)
        self.assertEqual(self.recados, [("telefone", "", "+5511911112222", "Aqui é o Zé, sobre o orçamento / é urgente")])
        self.assertIn("deixou recado: Aqui é o Zé", self.avisos[0])
        A.tratar("fim", {"CallSid": "C1", "CallStatus": "completed"})
        self.assertEqual(len(self.avisos), 1)                                 # avisa uma vez só

    def test_dono_precisa_de_pin(self):
        x = A.tratar("voz", {"CallSid": "D1", "From": "+5562988887777"})
        self.assertIn("PIN", x)
        self.assertIn('action="/twilio/pin"', x)
        self.assertIn("Desculpe", A.tratar("fala", {"CallSid": "D1", "SpeechResult": "desliga o pc"}))  # sem PIN: nada
        self.assertIn("PIN errado. Tente", A.tratar("pin", {"CallSid": "D1", "Digits": "1111"}))
        self.assertIn("<Hangup/>", A.tratar("pin", {"CallSid": "D1", "SpeechResult": "um dois"}))
        A.tratar("voz", {"CallSid": "D2", "From": "+5562988887777"})
        self.assertIn("Pode falar", A.tratar("pin", {"CallSid": "D2", "SpeechResult": "4 3 2 1"}))
        pedidos = []

        def pedir(texto, responder, fonte="", silencio=True):
            pedidos.append((texto, fonte, silencio))
            responder("**Feito**, TV ligada.")
            return True
        with mock.patch("core.resposta_remota.pedir", pedir):
            x = A.tratar("fala", {"CallSid": "D2", "SpeechResult": "liga a tv"})
        self.assertIn("Feito, TV ligada.", x)
        self.assertEqual(pedidos[0][1:], ("telefone", True))
        self.assertIn("[Ligação do dono por telefone] liga a tv", pedidos[0][0])
        self.assertIn("Até mais", A.tratar("fala", {"CallSid": "D2", "SpeechResult": "tchau"}))
        # sem PIN cadastrado o dono não controla nada
        self.cfg["pin"] = ""
        self.assertIn("cadastre um PIN", A.tratar("voz", {"CallSid": "D3", "From": "+5562988887777"}))

    def test_demora_vira_mensagem(self):
        A.tratar("voz", {"CallSid": "D4", "From": "+5562988887777"})
        A.tratar("pin", {"CallSid": "D4", "Digits": "4321"})
        guardado = {}
        with mock.patch("core.resposta_remota.pedir", lambda t, r, **k: guardado.setdefault("r", r) and True), \
                mock.patch.object(A, "ESPERA_POR_RODADA_S", 0.05):
            x = A.tratar("fala", {"CallSid": "D4", "SpeechResult": "faz um relatório"})
            self.assertIn("Só um instante", x)
            self.assertIn("<Redirect", x)
            for _ in range(A.RODADAS_MAX - 1):
                x = A.tratar("aguardar", {"CallSid": "D4"})
        self.assertIn("Te mando a resposta por mensagem", x)
        guardado["r"]("Relatório pronto.")
        self.assertTrue(any("Relatório pronto." in a for a in self.avisos))

    def test_desligado(self):
        self.cfg["atender"] = False
        self.assertIn("não está atendendo", A.tratar("voz", {"CallSid": "Z", "From": "+1"}))

    def test_configurar_numero(self):
        chamadas = []

        class Resp:
            def __init__(self, dados, cod=200):
                self.status_code, self._d, self.text = cod, dados, json.dumps(dados)

            def json(self):
                return self._d
        import requests
        with mock.patch.object(requests, "get", lambda url, **k: chamadas.append(("GET", url, k.get("params"))) or
                               Resp({"incoming_phone_numbers": [{"sid": "PN9"}]})), \
                mock.patch.object(requests, "post", lambda url, **k: chamadas.append(("POST", url, k.get("data"))) or
                                  Resp({})), \
                mock.patch.object(A, "salvar_cfg", lambda ns, v: self.cfg.update(v)):
            self.assertEqual(A.configurar_twilio("https://novo.trycloudflare.com/"), "")
            A.url_mudou("https://novo.trycloudflare.com")                    # mesma URL: não mexe
        self.assertEqual(chamadas[0][2], {"PhoneNumber": "+15550001111"})
        self.assertTrue(chamadas[1][1].endswith("/IncomingPhoneNumbers/PN9.json"))
        self.assertEqual(chamadas[1][2]["VoiceUrl"], "https://novo.trycloudflare.com/twilio/voz")
        self.assertEqual(chamadas[1][2]["StatusCallback"], "https://novo.trycloudflare.com/twilio/fim")
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(self.cfg["url_publica"], "https://novo.trycloudflare.com")


@unittest.skipUnless(shutil.which("node"), "sem Node.js")
class TestPontePessoal(unittest.TestCase):
    """Ponte de verdade com um whatsapp-web.js falso: modo pessoal, ligação e leitura."""

    FALSO = r"""
const { EventEmitter } = require("events"); const fs = require("fs");
const roteiro = JSON.parse(fs.readFileSync(process.env.ROTEIRO, "utf8"));
const CONTATOS = [{ id: { _serialized: "ana@c.us" }, name: "Ana Souza", number: "5562977770000", isMyContact: true },
                  { id: { _serialized: "joao@c.us" }, name: "João", number: "5562966660000", isMyContact: true },
                  { id: { _serialized: "grupo@g.us" }, name: "Ana grupo", isMyContact: true, isGroup: true }];
function saida(o) { fs.appendFileSync(process.env.SAIDA, JSON.stringify(o) + "\n"); }
class Client extends EventEmitter {
  constructor() { super(); this.info = { wid: { user: "5562900000000" } }; }
  async initialize() {
    this.emit("qr", "Q"); this.emit("authenticated"); this.emit("ready");
    for (const m of roteiro) setTimeout(() => {
      if (m.evento === "call") return this.emit("call", Object.assign({ async reject() { saida({ recusou: m.from }); } }, m));
      const c = CONTATOS.find(x => x.id._serialized === m.from) || { number: m.numero || "", isMyContact: false };
      this.emit(m.evento, Object.assign({ isStatus: false, hasMedia: false, type: "chat", timestamp: 1,
        async getContact() { return c; } }, m, { id: { _serialized: m.id } }));
    }, 400);
  }
  async getContactById(id) { return CONTATOS.find(x => x.id._serialized === id) || { number: "" }; }
  async getContacts() { return CONTATOS; }
  async getChats() { return [{ id: { _serialized: "ana@c.us" }, name: "Ana Souza", unreadCount: 2,
                               lastMessage: { body: "vem hoje?", type: "chat", fromMe: false, timestamp: 5 } },
                             { id: { _serialized: "grupo@g.us" }, name: "Grupo", isGroup: true, unreadCount: 9 }]; }
  async getChatById(id) { return { name: "Ana Souza", async fetchMessages(o) {
    return [{ body: "oi", fromMe: false, type: "chat", timestamp: 1 }, { body: "oi Ana", fromMe: true, type: "chat", timestamp: 2 }]
      .slice(-o.limit); } }; }
  async sendMessage(para, conteudo) { saida({ para, conteudo: String(conteudo) }); return { id: { _serialized: "e" + Date.now() } }; }
  async destroy() {}
}
module.exports = { Client, LocalAuth: class {}, MessageMedia: class {} };
"""

    def test_ponte(self):
        from tests.test_18_remoto import TestPonteNode
        pasta = tests.TMP / "ponte_pessoal"
        for mod, codigo in (("whatsapp-web.js", self.FALSO), ("qrcode", TestPonteNode.QR)):
            (pasta / "node_modules" / mod).mkdir(parents=True, exist_ok=True)
            (pasta / "node_modules" / mod / "index.js").write_text(codigo, encoding="utf-8")
        shutil.copy(tests.RAIZ / "whatsapp_ponte" / "ponte.js", pasta / "ponte.js")
        roteiro = [
            {"evento": "message", "id": "1", "from": "ana@c.us", "to": "x", "body": "vem hoje?", "fromMe": False},
            {"evento": "message", "id": "2", "from": "grupo@g.us", "to": "x", "body": "oi", "fromMe": False},
            {"evento": "call", "from": "joao@c.us", "isVideo": False, "fromMe": False, "isGroup": False},
            {"evento": "call", "from": "dono@c.us", "isVideo": True, "fromMe": False, "isGroup": False},
        ]
        (pasta / "roteiro.json").write_text(json.dumps(roteiro), encoding="utf-8")
        import os
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        saida = pasta / "saida.jsonl"
        env = dict(os.environ, JARVIS_WA_PORTA=str(porta), JARVIS_WA_TOKEN="t" * 24, JARVIS_WA_SESSAO=str(pasta / "s"),
                   ROTEIRO=str(pasta / "roteiro.json"), SAIDA=str(saida))
        proc = subprocess.Popen(["node", "ponte.js"], cwd=pasta, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        antigo = dict(W._p)
        try:
            W._p.update(porta=porta, token="t" * 24, proc=proc)
            for _ in range(100):
                if W._http("POST", "/donos", {"ids": ["dono@c.us"], "codigo": "", "pessoal": True, "secretaria": True},
                           timeout=1).get("ok"):
                    break
                time.sleep(0.02)
            time.sleep(1.2)
            evs = W._http("GET", "/eventos?desde=0")["eventos"]
            self.assertEqual(len(evs), 3)
            self.assertEqual((evs[0]["chat"], evs[0]["nome"], evs[0]["outro"], evs[0]["contato"]),
                             ("ana@c.us", "Ana Souza", True, True))
            self.assertEqual((evs[1]["chat"], evs[1]["ligacao"], evs[1]["rejeitada"], evs[1]["nome"], evs[1]["dono"]),
                             ("joao@c.us", True, True, "João", False))
            self.assertEqual((evs[2]["chat"], evs[2]["dono"], evs[2]["video"]), ("dono@c.us", True, True))
            recusadas = [json.loads(x).get("recusou") for x in saida.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sorted(r for r in recusadas if r), ["dono@c.us", "joao@c.us"])
            chats = P.conversas()
            self.assertEqual([(c["nome"], c["naoLidas"]) for c in chats], [("Ana Souza", 2)])   # grupo fora
            self.assertEqual(P.resumo_chats(chats), "• Ana Souza (2 novas): vem hoje?")
            self.assertEqual([m["texto"] for m in P.mensagens("ana@c.us", 5)], ["oi", "oi Ana"])
            self.assertEqual([c["id"] for c in P.achar("ana")], ["ana@c.us"])                    # sem acento, sem grupo
            self.assertEqual([c["nome"] for c in P.achar("joao")], ["João"])
            self.assertIn("erro", W._http("GET", "/mensagens?chat=grupo@g.us&n=5"))
            self.assertTrue(W.enviar("ana@c.us", "chego às 8", sem_prefixo=True))
            ultima = json.loads(saida.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(ultima, {"para": "ana@c.us", "conteudo": "chego às 8"})
        finally:
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            W._p.clear()
            W._p.update(antigo)


if __name__ == "__main__":
    unittest.main()
