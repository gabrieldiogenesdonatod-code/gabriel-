"""
WhatsApp pessoal e secretária (fork PT-BR 2.3). Começa com "_": não é ferramenta.

Com o modo pessoal ligado (⚙ → WhatsApp do JARVIS), a ponte passa para cá as
mensagens que OUTRAS pessoas te mandam em conversa privada (grupos nunca):

  • por padrão o JARVIS só avisa e prepara um RASCUNHO escrito como se fosse
    você — nada é enviado sem você aprovar ("aprovar 3", por voz ou pelo whats);
  • resposta AUTOMÁTICA só para os contatos que você liberou, ou para todo
    mundo enquanto o "modo ausente" estiver ligado. Ela sempre começa com
    "🤖 Assistente de <seu nome>:", não inventa compromisso nem conta nada
    pessoal, e tem freio (no máximo 1 a cada 20 s e 6 por hora por conversa;
    nunca responde outro robô).

Secretária: o WhatsApp Web não tem áudio, então ninguém consegue "atender" uma
ligação por ele. A secretária RECUSA a ligação, manda "não pode atender agora,
quer deixar recado?" e anota o que a pessoa mandar (texto ou áudio, que vira
texto) em memory/recados.json, avisando você.
"""

from __future__ import annotations

import re
import time

from plugins import _recados
from plugins import _whatsapp as W
from plugins._comum import nome_usuario, registrar

RESPIRO_S = 20            # resposta automática: no mínimo 20 s entre uma e outra na mesma conversa
MAX_POR_HORA = 6
RECADO_S = 600            # depois de recusar a ligação, aceita o recado por 10 minutos
PREFIXO_ROBO = "🤖"


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def nome_dono() -> str:
    return str(W.config().get("nome_dono") or "").strip() or nome_usuario()


def assinatura(nome: str) -> str:
    return f"Assistente de {nome}" if nome else "Assistente virtual"


def liberado(ev: dict, lista: str) -> bool:
    """O contato está na lista de resposta automática? ('Ana, 62 99999-1234, mãe') (pura)."""
    nome = W._dobrar(ev.get("nome") or "")
    for item in re.split(r"[,;\n]", str(lista or "")):
        item = item.strip()
        if not item:
            continue
        if len(W.so_digitos(item)) >= 8:
            if ev.get("numero") and W.mesmo_numero(item, ev["numero"]):
                return True
        elif nome and W._dobrar(item) and (nome == W._dobrar(item) or nome.split()[0] == W._dobrar(item)):
            return True
    return False


def pode_auto(historico: list[float], agora: float) -> bool:
    """Freio da resposta automática (pura)."""
    recentes = [t for t in historico if agora - t < 3600]
    if recentes and agora - max(recentes) < RESPIRO_S:
        return False
    return len(recentes) < MAX_POR_HORA


def eh_robo(texto: str) -> bool:
    t = str(texto or "").lstrip()
    return t.startswith(PREFIXO_ROBO) or bool(re.match(r"(?i)^(assistente (virtual|de)|mensagem autom[aá]tica)", t))


def prompt_auto(dono: str, nome: str, historico: str, mensagem: str) -> str:
    quem = dono or "o dono deste WhatsApp"
    return (f"Você é o assistente virtual de {quem} e está respondendo no WhatsApp dele porque ele não pode responder "
            f"agora. Quem escreveu: {nome or 'um contato'}.\n"
            "Regras: responda curto (1 ou 2 frases), educado, em português do Brasil. Sua mensagem já começa com "
            f"\"Assistente de {quem}:\", então não se apresente de novo. NÃO invente nem confirme compromissos, horários, "
            "valores ou decisões em nome dele. NÃO conte nada pessoal (onde ele está, endereço, agenda, saúde, dinheiro, "
            "senhas, códigos). Se pedirem algo, pedirem decisão ou for urgente, diga que vai avisar ele. Se for só um "
            "oi, cumprimente e pergunte se quer deixar recado. Responda só o texto.\n\n"
            f"CONVERSA RECENTE:\n{historico or '(sem histórico)'}\n\nMENSAGEM NOVA: {mensagem}")


def prompt_rascunho(dono: str, nome: str, historico: str, mensagem: str, pedido: str = "") -> str:
    return (f"Escreva UM rascunho de resposta de WhatsApp, em primeira pessoa, como se fosse {dono or 'o dono do celular'} "
            f"respondendo {nome or 'o contato'}. Curto, natural, em português do Brasil, no tom da conversa. Não invente "
            "fatos, horários nem compromissos; se não der para saber, faça uma resposta neutra (ex.: 'Oi! Vi agora, "
            "já te respondo direitinho'). Sem assinatura. Responda só o texto."
            + (f"\nO QUE ELE QUER DIZER: {pedido}" if pedido else "")
            + f"\n\nCONVERSA RECENTE:\n{historico or '(sem histórico)'}\n\nÚLTIMA MENSAGEM: {mensagem}")


def formatar_conversa(nome: str, msgs: list[dict], dono: str = "") -> str:
    """Mensagens da ponte → texto 'Ana: oi / Você: …' (pura)."""
    linhas = []
    for m in msgs[-30:]:
        texto = str(m.get("texto") or "").strip()
        if not texto:
            texto = {"ptt": "[áudio]", "audio": "[áudio]", "image": "[foto]", "video": "[vídeo]", "sticker": "[figurinha]",
                     "document": "[arquivo]", "call_log": "[ligação]"}.get(m.get("tipo"), "[mídia]")
        quem = (dono or "Você") if m.get("deMim") else (nome or "Contato")
        linhas.append(f"{quem}: {texto[:500]}")
    return "\n".join(linhas)


def resumo_chats(chats: list[dict], so_nao_lidas: bool = True) -> str:
    """'Ana (3 novas): chega que horas?' (pura)."""
    linhas = []
    for c in chats:
        if so_nao_lidas and not c.get("naoLidas"):
            continue
        u = c.get("ultima") or {}
        texto = str(u.get("texto") or "").strip() or ("[áudio]" if u.get("tipo") in ("ptt", "audio") else "[mídia]")
        novas = f" ({c['naoLidas']} nova{'s' if c['naoLidas'] > 1 else ''})" if c.get("naoLidas") else ""
        linhas.append(f"• {c.get('nome') or c.get('id', '').split('@')[0]}{novas}: {'Você: ' if u.get('deMim') else ''}"
                      f"{texto[:160]}")
    return "\n".join(linhas)


# ── estado (memory/whatsapp.json, junto do resto do WhatsApp) ────────────────
def ausente_ate() -> float:
    return float(W.dados().get("ausente_ate") or 0)


def ausente(agora: float | None = None) -> bool:
    return ausente_ate() > (agora or time.time())


def definir_ausente(ligar: bool, minutos: float = 0) -> str:
    d = W.dados()
    d["ausente_ate"] = (time.time() + minutos * 60 if minutos > 0 else time.time() + 10 * 365 * 86400) if ligar else 0
    W.gravar_json(W.ARQ, d)
    if not ligar:
        return "Modo ausente desligado: voltei a só fazer rascunhos."
    return ("Modo ausente ligado" + (f" por {minutos:g} minutos" if minutos > 0 else " até você desligar")
            + ": eu respondo as conversas privadas como seu assistente, sem prometer nada por você.")


def _abrir_recado(chat: str) -> None:
    d = W.dados()
    abertos = {k: v for k, v in (d.get("recado_aberto") or {}).items() if v > time.time()}
    abertos[chat] = time.time() + RECADO_S
    d["recado_aberto"] = abertos
    W.gravar_json(W.ARQ, d)


def _recado_aberto(chat: str) -> bool:
    return float((W.dados().get("recado_aberto") or {}).get(chat) or 0) > time.time()


def _anotar_auto(chat: str) -> list[float]:
    d = W.dados()
    log = d.get("auto_log") or {}
    agora = time.time()
    lista = [t for t in log.get(chat, []) if agora - t < 3600]
    log = {k: v for k, v in log.items() if v and agora - max(v) < 3600}
    log[chat] = lista + [agora]
    d["auto_log"] = log
    W.gravar_json(W.ARQ, d)
    return lista


def _historico_auto(chat: str) -> list[float]:
    return list((W.dados().get("auto_log") or {}).get(chat, []))


# ── ler conversas (pela ponte) ────────────────────────────────────────────────
def conversas(n: int = 20) -> list[dict]:
    r = W._http("GET", f"/chats?n={int(n)}", timeout=40)
    if r.get("erro"):
        raise RuntimeError(r["erro"])
    return r.get("chats") or []


def mensagens(chat: str, n: int = 15) -> list[dict]:
    from urllib.parse import quote
    r = W._http("GET", f"/mensagens?chat={quote(chat)}&n={int(n)}", timeout=40)
    if r.get("erro"):
        raise RuntimeError(r["erro"])
    return r.get("mensagens") or []


def historico_texto(chat: str, n: int = 10) -> str:
    try:
        return formatar_conversa("Contato", mensagens(chat, n), nome_dono() or "Dono")
    except Exception:
        return ""


def achar(nome: str) -> list[dict]:
    """Contatos/conversas com esse nome ou número: [{id, nome, numero}]."""
    nome = str(nome or "").strip()
    if not nome:
        return []
    from urllib.parse import quote
    r = W._http("GET", f"/contatos?q={quote(nome)}", timeout=40)
    achados = list(r.get("contatos") or [])
    if not achados:                                            # conversa com quem não está salvo
        try:
            alvo = W._dobrar(nome)
            achados = [{"id": c["id"], "nome": c.get("nome", ""), "numero": c["id"].split("@")[0]}
                       for c in conversas(50) if alvo and alvo in W._dobrar(c.get("nome", ""))]
        except Exception:
            pass
    exato = [c for c in achados if W._dobrar(c.get("nome")) == W._dobrar(nome)]
    return exato or achados


# ── eventos da ponte ─────────────────────────────────────────────────────────
def _texto_do_evento(ev: dict) -> str:
    texto = str(ev.get("texto") or "").strip()
    arq, tipo = ev.get("arquivo"), str(ev.get("tipo") or "")
    if arq and tipo in ("ptt", "audio", "image"):              # 2.16: entende, resume e guarda
        from plugins import _mensagens_midia as MM
        quem = str(ev.get("nome") or ev.get("numero") or "")
        info = MM.entender(arq, tipo, quem)
        MM.guardar(str(ev.get("chat") or ""), quem, info, arq)
        ev["_midia"] = info
        if info["tipo"] == "áudio":
            if not info["texto"]:
                return "[áudio que não consegui transcrever]"
            if info["resumo"] != info["texto"]:
                return f"[áudio, resumo: {info['resumo']}] {info['texto']}"
            return f"[áudio] {info['texto']}"
        return f"[foto: {info['texto'] or 'sem descrição'}] {texto}".strip()
    return texto


def avisar_em_voz(ev: dict, texto: str) -> None:
    """2.16: com 'ler em voz alta' ligado, o JARVIS fala quem mandou e o essencial
    (o resumo, para áudio longo). Nunca no meio de uma chamada/jogo: passa pela central de avisos."""
    if not W.config().get("ler_em_voz"):
        return
    quem = ev.get("nome") or ev.get("numero") or "alguém"
    info = ev.get("_midia") or {}
    if info.get("tipo") == "áudio":
        conteudo = f"mandou um áudio: {info.get('resumo') or info.get('texto')}"
    elif info.get("tipo") == "foto":
        conteudo = f"mandou uma foto: {info.get('resumo')}"
    else:
        conteudo = f"disse: {texto[:220]}"
    try:
        from plugins._notificar import notificar
        notificar(None, f"Mensagem de {quem}, que {conteudo}", "WhatsApp", etiqueta="MENSAGEM",
                  chave=f"wa_voz_{ev.get('chat')}", intervalo_s=20)
    except Exception as e:
        print(f"[WhatsApp] voz: {e}")


def tratar_ligacao(ev: dict) -> None:
    chat = str(ev.get("chat") or "")
    quem = ev.get("nome") or ev.get("numero") or "Alguém"
    tipo = "de vídeo" if ev.get("video") else ""
    if ev.get("dono"):
        extra = ""
        try:
            from plugins import _atendente_voz as A
            if A.ligado():
                extra = f" Para falar comigo por voz, ligue no número do JARVIS: {A.numero_publico()}."
        except Exception:
            pass
        W.enviar(chat, "Vi sua ligação 📞 Pelo WhatsApp eu não consigo atender voz (o WhatsApp Web não tem áudio). "
                       "Mande um *áudio* aqui que eu escuto e respondo." + extra)
        return
    if ev.get("rejeitada"):
        _abrir_recado(chat)
        dono = nome_dono()
        W.enviar(chat, f"{assinatura(dono)}: Oi{(', ' + ev['nome'].split()[0]) if ev.get('nome') else ''}! "
                       f"{dono or 'Ele'} não pode atender agora. Quer deixar um recado? Pode mandar por texto ou áudio "
                       "que eu passo para ele.")
        _recados.adicionar("whatsapp", ev.get("nome") or "", ev.get("numero") or "", "", chat)
    aviso = f"📞 {quem} te ligou {tipo} no WhatsApp".replace("  ", " ") + \
        (" — recusei e pedi um recado." if ev.get("rejeitada") else ".")
    registrar(None, aviso)
    if W.config().get("avisos", True):
        W.para_donos(aviso)


def anotar_recado(ev: dict, texto: str) -> None:
    chat = str(ev.get("chat") or "")
    r = _recados.adicionar("whatsapp", ev.get("nome") or "", ev.get("numero") or "", texto, chat)
    primeira = r["texto"].strip() == texto.strip()
    if primeira:
        W.enviar(chat, f"{assinatura(nome_dono())}: Anotado! ✅ Vou passar o recado.")
    quem = ev.get("nome") or ev.get("numero") or "alguém"
    registrar(None, f"📝 Recado de {quem} (WhatsApp): {texto[:200]}")
    W.para_donos(f"📝 Recado de *{quem}*: {texto[:1500]}")


def responder_automatico(ev: dict, texto: str) -> bool:
    from plugins import _ia
    chat = str(ev.get("chat") or "")
    if not _ia.disponivel() or eh_robo(texto) or not pode_auto(_historico_auto(chat), time.time()):
        return False
    dono = nome_dono()
    resp = _ia.perguntar(prompt_auto(dono, str(ev.get("nome") or ""), historico_texto(chat), texto), False, 30)
    if not resp:
        return False
    resp = resp.strip().strip('"').strip()
    if not W.enviar(chat, f"{assinatura(dono)}: {resp}"):
        return False
    _anotar_auto(chat)
    quem = ev.get("nome") or ev.get("numero") or "contato"
    registrar(None, f"🤖 Respondi {quem} por você no WhatsApp: {resp[:160]}")
    if W.config().get("avisos", True):
        W.para_donos(f"🤖 Respondi *{quem}* por você:\n“{texto[:300]}”\n→ {resp[:600]}")
    return True


def tratar_outro(ev: dict) -> None:
    chat = str(ev.get("chat") or "")
    texto = _texto_do_evento(ev)
    if not texto:
        return
    if ev.get("recado") or _recado_aberto(chat):
        anotar_recado(ev, texto)
        return
    c = W.config()
    if not c.get("modo_pessoal"):
        return
    if (ausente() or liberado(ev, c.get("auto_contatos") or "")) and responder_automatico(ev, texto):
        return
    quem = ev.get("nome") or ev.get("numero") or "contato"
    avisar_em_voz(ev, texto)                                   # 2.16
    if c.get("rascunho_pessoal", True) and not eh_robo(texto):
        W.rascunho_cliente(dict(ev, texto=texto), pessoal=True)
    else:
        registrar(None, f"💬 WhatsApp de {quem}: {texto[:160]}")


# ── pedidos por voz ──────────────────────────────────────────────────────────
def mandar_como_dono(chat: str, texto: str) -> bool:
    """Manda com as SUAS palavras, sem o 🤖 (só depois da sua confirmação)."""
    return W.enviar(chat, texto, sem_prefixo=True)


def rascunho_para(contato: dict, pedido: str) -> dict:
    """Rascunho de resposta para uma conversa (você aprova com 'aprovar N')."""
    from plugins import _ia
    msgs = mensagens(contato["id"], 12)
    ultima = next((m.get("texto") for m in reversed(msgs) if not m.get("deMim") and m.get("texto")), "")
    hist = formatar_conversa(contato.get("nome") or "Contato", msgs, nome_dono() or "Dono")
    texto = ""
    if _ia.disponivel():
        texto = (_ia.perguntar(prompt_rascunho(nome_dono(), contato.get("nome", ""), hist, ultima, pedido), False, 40)
                 or "").strip()
    if not texto and pedido:
        texto = pedido
    d = W.dados()
    rs = d.setdefault("rascunhos", [])
    r = {"id": (max([x["id"] for x in rs], default=0) % 999) + 1, "chat": contato["id"], "nome": contato.get("nome", ""),
         "numero": contato.get("numero", ""), "pergunta": ultima or "(você pediu)", "texto": texto, "ts": time.time(),
         "status": "pendente", "tipo": "pessoal"}
    rs.append(r)
    d["rascunhos"] = rs[-50:]
    W.gravar_json(W.ARQ, d)
    return r
