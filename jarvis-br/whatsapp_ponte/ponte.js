// Ponte WhatsApp Web ↔ J.A.R.V.I.S BR (fork PT-BR 1.8).
//
// Quem liga é o próprio JARVIS (plugins/_whatsapp.py). Usa o whatsapp-web.js:
// um WhatsApp Web de verdade rodando escondido, logado pelo QR code. NÃO é a
// API oficial: a Meta pode limitar ou banir o número. Prefira um chip só para o
// JARVIS; com o seu número, converse com ele no chat "Você" (mensagem para mim).
//
// Privacidade: só passa para o JARVIS as mensagens (1) do chat "para mim",
// (2) dos donos que o JARVIS autorizou e (3) o código de pareamento. O resto
// das suas conversas não sai daqui — a não ser que você ligue o modo loja
// (1.9), o modo pessoal (2.3: o JARVIS lê as conversas privadas para avisar e
// fazer rascunho) ou a secretária (2.3: recusa ligações e anota o recado).
// Grupos e status: nunca.
//
// API local (127.0.0.1, cabeçalho X-Token obrigatório):
//   GET  /estado                 → {estado, numero, qr}
//   GET  /eventos?desde=N        → {eventos:[…], ultimo}
//   POST /donos   {ids:[…], codigo, numeros, loja, pessoal, secretaria}
//   POST /enviar  {para, texto} | {para, arquivo, legenda}
//   GET  /chats?n=20             → conversas privadas recentes (2.3; não marca como lida)
//   GET  /mensagens?chat=ID&n=15 → últimas mensagens de uma conversa (2.3)
//   GET  /contatos?q=ana         → contatos salvos que batem com o nome (2.3)
//   POST /sair
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORTA = Number(process.env.JARVIS_WA_PORTA || 0);
const TOKEN = process.env.JARVIS_WA_TOKEN || "";
const SESSAO = process.env.JARVIS_WA_SESSAO || path.join(__dirname, ".sessao");
const MIDIA = process.env.JARVIS_WA_MIDIA || path.join(SESSAO, "midia");
const PREFIXO = "🤖 ";
if (!PORTA || TOKEN.length < 16) { console.error("faltam JARVIS_WA_PORTA/JARVIS_WA_TOKEN"); process.exit(2); }
fs.mkdirSync(MIDIA, { recursive: true });

let wa, MessageMedia, QRCode;
try {
  wa = require("whatsapp-web.js"); MessageMedia = wa.MessageMedia; QRCode = require("qrcode");
} catch (e) {
  console.error("PACOTES_FALTANDO " + e.message); process.exit(3);
}

const estado = { estado: "iniciando", numero: "", qr: "", erro: "" };
const eventos = []; let seq = 0;
let donos = new Set(); let codigo = ""; let loja = false; let numeros = [];   // 1.9: modo loja (clientes viram rascunho)
let pessoal = false; let secretaria = false;    // 2.3: modo pessoal e secretária de ligações
const recado = new Map();                       // 2.3: chat → até quando aceita o recado (depois de recusar a ligação)
const enviadas = new Set();                    // ids que a ponte mandou (não voltam como pedido)
const vistas = new Set();                      // "message" e "message_create" podem trazer a mesma

function evento(e) { e.n = ++seq; eventos.push(e); if (eventos.length > 200) eventos.shift(); }
function log(m) { console.log(new Date().toISOString().slice(11, 19) + " " + m); }

const cliente = new wa.Client({
  authStrategy: new wa.LocalAuth({ clientId: "jarvis", dataPath: SESSAO }),
  // 2.2: usa o Edge/Chrome que já está no PC (o JARVIS passa o caminho) — sem baixar navegador nenhum.
  puppeteer: Object.assign({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] },
    process.env.JARVIS_WA_NAVEGADOR ? { executablePath: process.env.JARVIS_WA_NAVEGADOR } : {}),
});

cliente.on("qr", async qr => {
  estado.estado = "qr";
  try {
    const url = await QRCode.toDataURL(qr, { margin: 1, width: 360 });
    if (estado.estado !== "qr") return;                     // já entrou enquanto o QR era gerado
    estado.qr = url; await QRCode.toFile(path.join(SESSAO, "qr.png"), qr, { margin: 1, width: 360 }); }
  catch (e) { estado.qr = ""; }
  log("QR pronto: leia no WhatsApp do celular (Aparelhos conectados → Conectar aparelho)");
});
cliente.on("authenticated", () => { estado.estado = "autenticado"; estado.qr = ""; log("autenticado"); });
cliente.on("auth_failure", m => { estado.estado = "falha"; estado.erro = String(m); log("falha no login: " + m); });
cliente.on("ready", () => {
  estado.estado = "pronto"; estado.qr = "";
  estado.numero = (cliente.info && cliente.info.wid && cliente.info.wid.user) || "";
  try { fs.unlinkSync(path.join(SESSAO, "qr.png")); } catch (e) {}
  log("pronto: " + estado.numero);
});
cliente.on("disconnected", m => { estado.estado = "desconectado"; estado.erro = String(m); log("desconectado: " + m); });

function norm(n) { n = String(n || "").replace(/\D/g, ""); return n.startsWith("55") && n.length >= 12 ? n.slice(2) : n; }
function mesmoNumero(a, b) {          // igual ao mesmo_numero() do plugins/_whatsapp.py
  a = norm(a); b = norm(b);
  if (a.length < 8 || b.length < 8 || a.slice(-8) !== b.slice(-8)) return false;
  return a.length >= 10 && b.length >= 10 ? a.slice(0, 2) === b.slice(0, 2) : true;
}
function paraMim(msg) { return msg.fromMe && msg.to && msg.from === msg.to; }

function semAcento(t) { return String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
async function baixarMidia(msg, ev) {
  if (!msg.hasMedia || !["ptt", "audio", "image"].includes(msg.type)) return;
  try {
    const m = await msg.downloadMedia();
    if (m && m.data) {
      const ext = msg.type === "image" ? (m.mimetype.includes("png") ? ".png" : ".jpg") : ".ogg";
      const arq = path.join(MIDIA, Date.now() + "_" + Math.floor(Math.random() * 1e6) + ext);
      fs.writeFileSync(arq, Buffer.from(m.data, "base64"));
      ev.arquivo = arq;
    }
  } catch (e) { ev.erro_midia = String(e.message || e); }
}

async function tratar(msg) {
  try {
    if (!msg || msg.isStatus) return;
    const id = msg.id && msg.id._serialized;
    if (id && (enviadas.has(id) || vistas.has(id))) return;
    if (id) { vistas.add(id); if (vistas.size > 500) vistas.delete(vistas.values().next().value); }
    const chat = msg.fromMe ? msg.to : msg.from;
    if (!chat || chat.endsWith("@g.us") || chat === "status@broadcast") return;   // grupos e status: nunca
    const texto = String(msg.body || "");
    if (msg.fromMe && texto.startsWith(PREFIXO)) return;
    const eu = paraMim(msg);
    if (msg.fromMe && !eu) return;                                  // você falando com outra pessoa: não é com o JARVIS
    const pareando = codigo && texto.toUpperCase().includes(codigo);
    let numero = ""; let contato = null;
    if (!eu) { try { contato = await msg.getContact(); numero = (contato && contato.number) || ""; } catch (e) {} }
    const numeroDono = numero && numeros.some(n => mesmoNumero(n, numero));
    const ev = { chat, numero, texto, tipo: msg.type, eu, ts: msg.timestamp, nome: (msg._data && msg._data.notifyName) || "" };
    if (!eu && !donos.has(chat) && !pareando && !numeroDono) {
      const esperandoRecado = (recado.get(chat) || 0) > Date.now();
      if (msg.fromMe || (!loja && !pessoal && !esperandoRecado)) return;   // conversa de outra pessoa: fica aqui
      // 1.9 loja: vira RASCUNHO. 2.3 pessoal/recado: o JARVIS avisa, faz rascunho ou responde se você liberou.
      ev.cliente = loja; ev.outro = pessoal || esperandoRecado; ev.recado = esperandoRecado;
      ev.contato = !!(contato && contato.isMyContact);
      if (contato && (contato.name || contato.pushname)) ev.nome = contato.name || contato.pushname;
      if (ev.outro) await baixarMidia(msg, ev);                     // áudio e foto de quem você liberou
      else if (!texto.trim()) return;                               // modo loja: mídia de cliente não é baixada
      evento(ev); return;
    }
    await baixarMidia(msg, ev);
    evento(ev);
  } catch (e) { log("erro ao tratar mensagem: " + e.message); }
}

// 2.3: ligações pelo WhatsApp. O WhatsApp Web não deixa ATENDER (não tem áudio);
// a secretária recusa e o JARVIS pede um recado por mensagem.
cliente.on("call", async call => {
  try {
    if (!call || call.fromMe || call.isGroup) return;
    const chat = String(call.from || "");
    if (!chat || chat.endsWith("@g.us")) return;
    let numero = ""; let nome = "";
    try { const c = await cliente.getContactById(chat); numero = (c && c.number) || ""; nome = (c && (c.name || c.pushname)) || ""; } catch (e) {}
    const dono = donos.has(chat) || (numero && numeros.some(n => mesmoNumero(n, numero)));
    let rejeitada = false;
    if (secretaria || dono) {
      try { await call.reject(); rejeitada = true; } catch (e) { log("não recusei a ligação: " + e.message); }
    }
    if (!dono && !secretaria && !pessoal) return;                    // ninguém pediu para saber
    if (rejeitada && !dono) recado.set(chat, Date.now() + 10 * 60 * 1000);
    evento({ ligacao: true, chat, numero, nome, video: !!call.isVideo, rejeitada, dono: !!dono, ts: Math.floor(Date.now() / 1000) });
  } catch (e) { log("erro na ligação: " + e.message); }
});

// 2.3: leitura das conversas (só quando o JARVIS pede: "o que me mandaram?")
function resumoMsg(m) {
  return { deMim: !!m.fromMe, texto: String(m.body || "").slice(0, 1500), tipo: m.type, ts: m.timestamp,
           midia: !!m.hasMedia, id: m.id && m.id._serialized };
}
async function listarChats(n) {
  const chats = await cliente.getChats();
  return chats.filter(c => !c.isGroup && c.id && !String(c.id._serialized).endsWith("@g.us") && c.id._serialized !== "status@broadcast")
    .slice(0, n).map(c => ({ id: c.id._serialized, nome: c.name || "", naoLidas: c.unreadCount || 0,
      ultima: c.lastMessage ? resumoMsg(c.lastMessage) : null }));
}
async function lerMensagens(id, n) {
  if (!/@(c\.us|lid)$/.test(id)) throw new Error("conversa inválida");
  const chat = await cliente.getChatById(id);
  const ms = await chat.fetchMessages({ limit: n });
  return { id, nome: chat.name || "", mensagens: ms.map(resumoMsg) };
}
// 2.16: baixa a mídia (áudio, foto, documento) de uma mensagem já existente, para o JARVIS ouvir/ver
async function baixarMidiaPorId(id) {
  const m = await cliente.getMessageById(String(id || ""));
  if (!m || !m.hasMedia) throw new Error("essa mensagem não tem mídia");
  const d = await m.downloadMedia();
  if (!d || !d.data) throw new Error("não consegui baixar");
  const ext = { "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf", "video/mp4": ".mp4" }[d.mimetype]
    || (String(d.mimetype).startsWith("image/") ? ".jpg" : String(d.mimetype).startsWith("audio/") ? ".ogg" : ".bin");
  const arq = path.join(MIDIA, Date.now() + "_" + Math.floor(Math.random() * 1e6) + ext);
  fs.writeFileSync(arq, Buffer.from(d.data, "base64"));
  return { arquivo: arq, tipo: m.type, mime: d.mimetype, nome: d.filename || "" };
}
async function buscarContatos(q) {
  const alvo = semAcento(q).trim();
  if (!alvo) return [];
  const todos = await cliente.getContacts();
  return todos.filter(c => c && c.isMyContact && !c.isGroup && c.id && /@(c\.us|lid)$/.test(c.id._serialized))
    .filter(c => semAcento(c.name || c.pushname).includes(alvo) || (c.number && alvo.replace(/\D/g, "").length >= 8 && c.number.endsWith(alvo.replace(/\D/g, ""))))
    .slice(0, 8).map(c => ({ id: c.id._serialized, nome: c.name || c.pushname || "", numero: c.number || "" }));
}

cliente.on("message", tratar);
cliente.on("message_create", m => { if (m.fromMe) tratar(m); });

async function enviar(corpo) {
  const para = String(corpo.para || "");
  if (!/@(c\.us|lid)$/.test(para)) throw new Error("destino inválido");
  let r;
  if (corpo.arquivo) {
    const media = MessageMedia.fromFilePath(String(corpo.arquivo));
    r = await cliente.sendMessage(para, media, { caption: corpo.legenda ? PREFIXO + corpo.legenda : undefined });
  } else {
    r = await cliente.sendMessage(para, (corpo.sem_prefixo ? "" : PREFIXO) + String(corpo.texto || ""));
  }
  if (r && r.id) { enviadas.add(r.id._serialized); if (enviadas.size > 500) enviadas.delete(enviadas.values().next().value); }
  return true;
}

function responder(res, cod, obj) {
  const b = Buffer.from(JSON.stringify(obj));
  res.writeHead(cod, { "Content-Type": "application/json; charset=utf-8", "Content-Length": b.length });
  res.end(b);
}
http.createServer((req, res) => {
  if (req.headers["x-token"] !== TOKEN) return responder(res, 403, { erro: "token" });
  const u = new URL(req.url, "http://127.0.0.1");
  if (req.method === "GET" && u.pathname === "/estado") return responder(res, 200, estado);
  if (req.method === "GET" && u.pathname === "/eventos") {
    const desde = Number(u.searchParams.get("desde") || 0);
    return responder(res, 200, { eventos: eventos.filter(e => e.n > desde), ultimo: seq });
  }
  if (req.method === "GET" && ["/chats", "/mensagens", "/contatos", "/midia"].includes(u.pathname)) {
    if (estado.estado !== "pronto") return responder(res, 409, { erro: "WhatsApp não está pronto" });
    const n = Math.max(1, Math.min(50, Number(u.searchParams.get("n") || 15)));
    const tarefa = u.pathname === "/chats" ? listarChats(n).then(chats => ({ chats }))
      : u.pathname === "/mensagens" ? lerMensagens(String(u.searchParams.get("chat") || ""), n)
      : u.pathname === "/midia" ? baixarMidiaPorId(u.searchParams.get("id"))
      : buscarContatos(String(u.searchParams.get("q") || "")).then(contatos => ({ contatos }));
    tarefa.then(r => responder(res, 200, r)).catch(e => responder(res, 500, { erro: String(e.message || e) }));
    return;
  }
  let dados = "";
  req.on("data", c => { dados += c; if (dados.length > 1e6) req.destroy(); });
  req.on("end", async () => {
    let corpo = {};
    try { corpo = JSON.parse(dados || "{}"); } catch (e) { return responder(res, 400, { erro: "json" }); }
    try {
      if (u.pathname === "/donos") { donos = new Set((corpo.ids || []).map(String)); codigo = String(corpo.codigo || "").toUpperCase(); loja = !!corpo.loja; numeros = (corpo.numeros || []).map(String); pessoal = !!corpo.pessoal; secretaria = !!corpo.secretaria; return responder(res, 200, { ok: true }); }
      if (u.pathname === "/enviar") { if (estado.estado !== "pronto") return responder(res, 409, { erro: "WhatsApp não está pronto" }); await enviar(corpo); return responder(res, 200, { ok: true }); }
      if (u.pathname === "/sair") { responder(res, 200, { ok: true }); try { await cliente.destroy(); } catch (e) {} process.exit(0); }
    } catch (e) { return responder(res, 500, { erro: String(e.message || e) }); }
    responder(res, 404, { erro: "rota" });
  });
}).listen(PORTA, "127.0.0.1", () => log("ponte ouvindo em 127.0.0.1:" + PORTA));

process.stdin.on("end", () => process.exit(0));      // o JARVIS fechou: a ponte fecha junto
process.stdin.resume();
cliente.initialize().catch(e => { estado.estado = "falha"; estado.erro = String(e.message || e); log("não iniciou: " + estado.erro); });
