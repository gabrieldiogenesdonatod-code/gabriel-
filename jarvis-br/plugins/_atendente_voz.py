"""
Atendente de voz no número da Twilio (fork PT-BR 2.3). Começa com "_": não é ferramenta.

Quando alguém liga para o número da Twilio (o mesmo da "Ligação de alerta"),
a Twilio pergunta ao painel do JARVIS o que fazer (rotas /twilio/… em
plugins/_painel_remoto.py, pela internet através do túnel Cloudflare):

  • VOCÊ (número = "Seu número" da configuração) + PIN falado ou digitado →
    conversa com o JARVIS de verdade, com as mesmas ferramentas da voz
    ("liga a TV", "como está o PC?"). O PIN existe porque número de quem liga
    dá para falsificar.
  • QUALQUER OUTRA PESSOA → a secretária: diz que você não pode atender, anota
    nome e recado, não conta nada sobre você e não promete nada. No fim, o
    recado vai para memory/recados.json e para você (WhatsApp/Telegram/Discord).

Toda chamada da Twilio é conferida pela assinatura (X-Twilio-Signature,
HMAC-SHA1 com o seu Auth Token); sem ela, 403.

Custos: a Twilio cobra o número por mês e os minutos recebidos; número
brasileiro exige cadastro regulatório (documentos) na Twilio. Um número dos EUA
funciona, mas quem liga do Brasil paga ligação internacional.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import re
import threading
import time

from plugins._comum import cfg, registrar, salvar_cfg

VOZ = "Polly.Camila-Neural"
ESPERA_POR_RODADA_S = 9.0           # a Twilio desiste depois de 15 s sem resposta
RODADAS_MAX = 5                     # ~45 s esperando o JARVIS; depois a resposta vai por mensagem
TURNOS_VISITANTE = 4

_lock = threading.Lock()
SESSOES: dict[str, dict] = {}


def _c() -> dict:
    from plugins.ligacao import PLUGIN_SETTINGS
    return cfg("ligacao", PLUGIN_SETTINGS)


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def assinatura_twilio(url: str, params: dict, token: str) -> str:
    """Como a Twilio assina: URL + cada chave e valor dos parâmetros em ordem alfabética, HMAC-SHA1, base64."""
    dados = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(token.encode(), dados.encode("utf-8"), hashlib.sha1).digest()).decode()


def assinatura_valida(urls: list[str], params: dict, recebida: str, token: str) -> bool:
    if not token or not recebida:
        return False
    return any(hmac.compare_digest(assinatura_twilio(u, params, token), recebida) for u in urls if u)


def urls_candidatas(base_salva: str, caminho: str, consulta: str, host: str) -> list[str]:
    q = f"?{consulta}" if consulta else ""
    saida = []
    if base_salva:
        saida.append(base_salva.rstrip("/") + caminho + q)
    if host:
        saida.append(f"https://{host}{caminho}{q}")
    return saida


def limpar_fala(texto: str, limite: int = 700) -> str:
    """Texto do JARVIS → frase boa de falar no telefone (sem markdown, emoji e links) (pura)."""
    t = re.sub(r"https?://\S+", "o link", str(texto or ""))
    t = re.sub(r"[*_`#>|~]", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = "".join(ch for ch in t if ord(ch) < 0x2190 or ch in "–—…“”‘’")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limite:
        corte = t[:limite]
        t = corte[:max(corte.rfind(". "), corte.rfind("? "), limite // 2) + 1].strip()
    return t


def despedida(texto: str) -> bool:
    t = re.sub(r"[^a-z ]", "", _dobrar(texto)).strip()
    return bool(re.fullmatch(r"(e |entao )?(so isso|era so isso|tchau|ate mais|ate logo|pode desligar|desliga|"
                             r"valeu tchau|obrigad[oa] tchau|tchau obrigad[oa]|nao obrigad[oa]|tudo certo tchau)( jarvis)?",
                             t))


def _dobrar(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def _say(texto: str) -> str:
    return f'<Say language="pt-BR" voice="{VOZ}">{html.escape(texto)}</Say>'


def twiml_ouvir(fala: str, acao: str, digitos: int = 0, tempo: int = 5) -> str:
    """Fala e escuta a resposta (voz; com digitos>0 também aceita o teclado) (pura)."""
    entrada = "dtmf speech" if digitos else "speech"
    extra = f' numDigits="{digitos}"' if digitos else ""
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather input="{entrada}" language="pt-BR" speechTimeout="auto" timeout="{tempo}"{extra} '
            f'action="{acao}" method="POST" actionOnEmptyResult="true">{_say(fala) if fala else ""}</Gather>'
            '</Response>')


def twiml_dizer(fala: str, desligar: bool = True) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>' + _say(fala)
            + ('<Hangup/>' if desligar else '') + '</Response>')


def twiml_esperar(fala: str = "") -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>' + (_say(fala) if fala else '<Pause length="1"/>')
            + '<Redirect method="POST">/twilio/aguardar</Redirect></Response>')


def mesmo_numero(a: str, b: str) -> bool:
    from plugins._whatsapp import mesmo_numero as mn
    return mn(a, b)


def prompt_secretaria(dono: str, conversa: list[tuple[str, str]]) -> str:
    hist = "\n".join(f"{'Pessoa' if q == 'p' else 'Você'}: {t}" for q, t in conversa)
    return (f"Você é a secretária virtual de {dono or 'o dono deste número'} atendendo uma LIGAÇÃO telefônica. Ele não "
            "pode atender agora. Objetivo: saber o nome de quem liga, o recado e se é urgente. Regras: fale UMA ou duas "
            "frases curtas por vez, em português do Brasil, sem emojis nem listas. NÃO conte nada sobre ele (onde está, "
            "agenda, telefone, endereço, dinheiro) e NÃO prometa nada (horário de retorno, preço, decisão) — diga só que "
            "vai passar o recado. Quando já tiver o recado, ou a pessoa se despedir, agradeça, despeça-se e termine a "
            "resposta com [FIM].\n\nCONVERSA ATÉ AGORA:\n" + hist + "\n\nSua próxima fala:")


# ── estado ───────────────────────────────────────────────────────────────────
def ligado() -> bool:
    c = _c()
    return bool(c.get("atender")) and bool(str(c.get("url_publica") or "").strip())


def numero_publico() -> str:
    return str(_c().get("de") or "").strip()


def _dono_nome() -> str:
    try:
        from plugins import _whatsapp_pessoal as P
        return P.nome_dono()
    except Exception:
        return ""


def _sessao(params: dict) -> dict:
    sid = str(params.get("CallSid") or "")
    agora = time.time()
    with _lock:
        for k in [k for k, v in SESSOES.items() if agora - v["inicio"] > 3600]:
            SESSOES.pop(k, None)
        s = SESSOES.get(sid)
        if s is None:
            s = {"sid": sid, "de": str(params.get("From") or ""), "inicio": agora, "dono": False, "autorizado": False,
                 "pin_erros": 0, "vazias": 0, "conversa": [], "respostas": [], "esperando": False, "rodadas": 0,
                 "fim": False, "avisado": False, "desde_resposta": 0.0}
            SESSOES[sid] = s
        return s


# ── etapas (cada uma devolve o TwiML) ────────────────────────────────────────
def tratar(etapa: str, params: dict) -> str:
    try:
        if etapa == "voz":
            return _voz(params)
        if etapa == "pin":
            return _pin(params)
        if etapa == "fala":
            return _fala(params)
        if etapa == "aguardar":
            return _aguardar(params)
        if etapa == "fim":
            _fim(params)
            return '<?xml version="1.0" encoding="UTF-8"?><Response/>'
    except Exception as e:
        print(f"[Atendente] {etapa}: {e}")
        return twiml_dizer("Desculpe, tive um problema aqui. Tente de novo daqui a pouco.")
    return twiml_dizer("Desculpe, não entendi.")


def _voz(params: dict) -> str:
    if not _c().get("atender"):
        return twiml_dizer("Este número não está atendendo agora. Tchau!")
    s = _sessao(params)
    c = _c()
    s["dono"] = bool(c.get("para")) and mesmo_numero(s["de"], str(c.get("para")))
    if s["dono"]:
        pin = re.sub(r"\D", "", str(c.get("pin") or ""))
        if not pin:
            return twiml_dizer("Oi! Para falar comigo por telefone, cadastre um PIN em Configurações, Plugins, Ligação "
                               "de alerta. Até já!")
        return twiml_ouvir("Oi! Diga ou digite o seu PIN.", "/twilio/pin", digitos=len(pin), tempo=8)
    dono = _dono_nome()
    fala = (f"Olá! Aqui é a assistente virtual de {dono}. " if dono else "Olá! Aqui é a assistente virtual. ") + \
        "Ele não pode atender agora. Qual é o seu nome e o recado?"
    s["conversa"].append(("a", fala))
    return twiml_ouvir(fala, "/twilio/fala", tempo=6)


def _pin(params: dict) -> str:
    s = _sessao(params)
    if not s["dono"]:
        return twiml_dizer("Desculpe, não entendi.")
    certo = re.sub(r"\D", "", str(_c().get("pin") or ""))
    dito = re.sub(r"\D", "", str(params.get("Digits") or "")) or re.sub(r"\D", "", str(params.get("SpeechResult") or ""))
    if certo and hmac.compare_digest(dito, certo):
        s["autorizado"] = True
        registrar(None, "📞 Você ligou no número do JARVIS (PIN certo).")
        return twiml_ouvir("Pronto, senhor. Pode falar.", "/twilio/fala", tempo=8)
    s["pin_erros"] += 1
    if s["pin_erros"] >= 2:
        registrar(None, f"📞 Ligação com PIN errado do número {s['de'][-4:].rjust(8, '•')}.")
        return twiml_dizer("PIN errado. Tchau.")
    return twiml_ouvir("PIN errado. Tente de novo.", "/twilio/pin", digitos=len(certo), tempo=8)


def _fala(params: dict) -> str:
    s = _sessao(params)
    texto = str(params.get("SpeechResult") or "").strip()
    if s["dono"] and not s["autorizado"]:
        return twiml_dizer("Desculpe, não entendi.")
    if not texto:
        s["vazias"] += 1
        if s["vazias"] >= 2:
            _fim(params)
            return twiml_dizer("Não estou te ouvindo. Tchau!")
        return twiml_ouvir("Não ouvi. Pode repetir?", "/twilio/fala", tempo=6)
    s["vazias"] = 0
    s["conversa"].append(("p", texto))
    if s["dono"]:
        if despedida(texto):
            s["fim"] = True
            return twiml_dizer("Até mais, senhor.")
        _pedir_ao_jarvis(s, texto)
    else:
        turnos = sum(1 for q, _t in s["conversa"] if q == "p")
        if despedida(texto) or turnos >= TURNOS_VISITANTE:
            s["fim"] = True
            _fim(params)
            return twiml_dizer("Certo, vou passar o seu recado. Obrigada e até logo!")
        _pedir_secretaria(s)
    return _esperar_resposta(s, primeira=True)


def _aguardar(params: dict) -> str:
    return _esperar_resposta(_sessao(params), primeira=False)


def _esperar_resposta(s: dict, primeira: bool) -> str:
    fim = time.time() + ESPERA_POR_RODADA_S
    while time.time() < fim:
        with _lock:
            pronto = s["respostas"] and (not s["dono"] or time.time() - s["desde_resposta"] > 1.5 or not s["esperando"])
        if pronto:
            break
        time.sleep(0.25)
    with _lock:
        respostas, s["respostas"] = s["respostas"], []
    if respostas:
        s["esperando"], s["rodadas"] = False, 0
        fala = limpar_fala(" ".join(respostas))
        if not s["dono"]:
            terminou = "[FIM]" in fala
            fala = fala.replace("[FIM]", "").strip()
            s["conversa"].append(("a", fala))
            if terminou:
                s["fim"] = True
                _fim({"CallSid": s["sid"]})
                return twiml_dizer(fala or "Obrigada, vou passar o recado. Tchau!")
            return twiml_ouvir(fala, "/twilio/fala", tempo=6)
        return twiml_ouvir(fala or "Feito.", "/twilio/fala", tempo=8)
    s["rodadas"] += 1
    if s["rodadas"] >= RODADAS_MAX:
        s["rodadas"], s["tarde"] = 0, True
        return twiml_ouvir("Isso está demorando. Te mando a resposta por mensagem. Quer mais alguma coisa?",
                           "/twilio/fala", tempo=6)
    return twiml_esperar("Só um instante." if primeira else "")


def _pedir_ao_jarvis(s: dict, texto: str) -> None:
    with _lock:
        s["esperando"], s["tarde"], s["respostas"] = True, False, []

    def responder(t: str) -> None:
        with _lock:
            s["respostas"].append(t)
            s["desde_resposta"] = time.time()
        if s.get("tarde") or s.get("fim"):                    # a ligação já seguiu: manda por mensagem
            try:
                from plugins import _canais
                _canais.mandar(f"📞 Resposta do seu pedido por telefone (“{texto[:80]}”):\n{t}")
            except Exception:
                pass
    from core import resposta_remota
    pedido = (f"[Ligação do dono por telefone] {texto}\n(Ele está OUVINDO pelo telefone: responda curto, falado, sem "
              "listas, links, emojis nem markdown. Ações com confirmação: diga que precisa confirmar no PC ou pelo "
              "WhatsApp.)")
    if not resposta_remota.pedir(pedido, responder, fonte="telefone", silencio=True):
        from plugins import _ia
        r = _ia.perguntar(f"Você é o J.A.R.V.I.S falando por telefone com o seu dono. O PC está sem a sessão de voz, "
                          f"então você não consegue usar ferramentas; diga isso se ele pedir uma ação. Responda em 1 ou "
                          f"2 frases faladas. Ele disse: {texto}", False, 10) if _ia.disponivel() else None
        responder(r or "O Jarvis está sem conexão no PC agora. Tente de novo daqui a pouco.")


def _pedir_secretaria(s: dict) -> None:
    conversa = list(s["conversa"])

    def tarefa():
        r = None
        try:
            from plugins import _ia
            if _ia.disponivel():
                r = _ia.perguntar(prompt_secretaria(_dono_nome(), conversa), False, 10)
        except Exception:
            r = None
        if not r:                                              # sem IA: roteiro fixo
            turnos = sum(1 for q, _t in conversa if q == "p")
            r = "Anotado. Quer acrescentar mais alguma coisa?" if turnos < 2 else \
                "Certo, vou passar o seu recado. Obrigada e até logo! [FIM]"
        with _lock:
            s["respostas"].append(r)
            s["desde_resposta"] = time.time()
    threading.Thread(target=tarefa, daemon=True).start()


def _fim(params: dict) -> None:
    sid = str(params.get("CallSid") or "")
    with _lock:
        s = SESSOES.get(sid)
        if s is None or s["avisado"]:
            return
        s["avisado"] = True
    if s["dono"]:
        return
    falas = [t for q, t in s["conversa"] if q == "p"]
    texto = " / ".join(falas)
    from plugins import _recados
    _recados.adicionar("telefone", "", s["de"], texto)
    aviso = (f"📞 {s['de'] or 'Número oculto'} ligou no número do JARVIS"
             + (f" e deixou recado: {texto[:1500]}" if texto else " e não deixou recado."))
    registrar(None, aviso)
    try:
        from plugins import _canais
        _canais.mandar(aviso)
    except Exception:
        pass


# ── configurar o número na Twilio ────────────────────────────────────────────
def configurar_twilio(base: str) -> str:
    """Aponta o número da Twilio para este PC (VoiceUrl). '' = deu certo."""
    c = _c()
    sid, token, de = (str(c.get(k) or "").strip() for k in ("sid", "token", "de"))
    if not (sid and token and de):
        return "Falta configurar a Twilio (Account SID, Auth Token e o número) em Ligação de alerta."
    base = base.rstrip("/")
    try:
        import requests
        api = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers"
        r = requests.get(f"{api}.json", params={"PhoneNumber": de}, auth=(sid, token), timeout=20)
        if r.status_code >= 300:
            return f"A Twilio recusou: {r.text[:160]}"
        numeros = r.json().get("incoming_phone_numbers") or []
        if not numeros:
            return f"Não achei o número {de} na sua conta Twilio."
        r = requests.post(f"{api}/{numeros[0]['sid']}.json", auth=(sid, token), timeout=20,
                          data={"VoiceUrl": f"{base}/twilio/voz", "VoiceMethod": "POST",
                                "StatusCallback": f"{base}/twilio/fim", "StatusCallbackMethod": "POST"})
        if r.status_code >= 300:
            return f"A Twilio recusou: {r.text[:160]}"
    except Exception as e:
        return f"Não consegui falar com a Twilio: {e}"
    salvar_cfg("ligacao", {"url_publica": base})
    return ""


def url_mudou(url: str) -> None:
    """Chamado pelo _tunel quando o endereço do Cloudflare muda: reaponta o número."""
    c = _c()
    if not c.get("atender") or not url or url.rstrip("/") == str(c.get("url_publica") or "").rstrip("/"):
        return
    erro = configurar_twilio(url)
    print(f"[Atendente] {'número da Twilio apontado para ' + url if not erro else erro}")


def ligar_atendimento() -> str:
    from plugins import _tunel
    c = _c()
    if not all(str(c.get(k) or "").strip() for k in ("sid", "token", "de")):
        return "Primeiro configure a Twilio em Configurações, Plugins, Ligação de alerta (SID, Token e o número)."
    if _tunel.painel() is None:
        return "O painel do JARVIS precisa estar ligado (ele recebe a ligação)."
    local, https = _tunel.endereco_local()
    url, erro = _tunel.cloudflare_ligar(local, sem_verificar_tls=https)
    if not url:
        return f"Não consegui abrir o endereço público: {erro}"
    salvar_cfg("ligacao", {"atender": True})
    erro = configurar_twilio(url)
    if erro:
        return erro
    aviso = "" if re.sub(r"\D", "", str(c.get("pin") or "")) else \
        " Cadastre um PIN em Ligação de alerta para VOCÊ poder falar comigo pelo telefone."
    return f"Pronto: o número {c['de']} agora atende. Quem ligar fala com a secretária e deixa recado.{aviso}"


def desligar_atendimento() -> str:
    salvar_cfg("ligacao", {"atender": False})
    return "Atendimento desligado: quem ligar ouve que o número não está atendendo."
