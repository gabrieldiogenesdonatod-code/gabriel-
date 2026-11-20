"""
Porteiro de voz — quem o JARVIS ouve e com quem ele fala (fork PT-BR 2.13).

A ideia (o que o dono pediq)
    * Por padrão o JARVIS só RESPONDE para a voz do dono. Se outra pessoa falar
      do nada, ele recusa com educação ("eu só falo com o meu criador").
    * Mas o dono pode APRESENTAR uma visita ("agora quem fala é o João",
      "deixa eu te apresentar a Ana", "fala com o Pedro"). Aí o JARVIS abre uma
      CONVERSA TEMPORÁRIA com a visita (modo convidado: só o que é livre, sem
      nada pessoal, sem gravar memória).
    * Quando o DONO volta a falar (a voz dele, ou ele diz "sou eu de novo"), o
      JARVIS volta a falar com o dono — sem travar nada.

Regra de ouro
    O porteiro NUNCA tranca o dono para fora. Se não dá para saber de quem é a
    voz (sem o reconhecimento de voz instalado, ou sem cadastro), ele assume que
    é o dono e responde normalmente. Barrar só acontece quando a voz é
    RECONHECIDA como de outra pessoa e não há visita apresentada.

Este módulo é lógica pura + um pouco de estado em memory/porteiro.json. A
decisão (`decidir`) não toca em disco: dá para testar inteira.
"""

from __future__ import annotations

import re
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, nome_usuario

ARQ = MEMORIA / "porteiro.json"            # o carregador dos testes troca este caminho
JANELA_PADRAO_MIN = 15.0                   # quanto tempo a visita apresentada continua liberada

# ações possíveis
RESPONDER = "responder"      # fala normalmente com o dono
CONVIDADO = "convidado"      # fala com a visita (temporário, limitado)
RECUSAR = "recusar"          # voz estranha, sem visita apresentada → não atende


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── estado em disco ──────────────────────────────────────────────────────────
def _padrao() -> dict:
    return {"estrito": True, "modo": "dono", "convidado": "", "ate": 0.0, "janela_min": JANELA_PADRAO_MIN}


def carregar() -> dict:
    d = ler_json(ARQ, None)
    if not isinstance(d, dict):
        d = {}
    base = _padrao()
    base.update({k: d[k] for k in base if k in d})
    return base


def salvar(estado: dict) -> None:
    gravar_json(ARQ, estado)


# ── detecção por texto (pura) ────────────────────────────────────────────────
_APRESENTA = [
    re.compile(r"(?:deixa|deixe)\s+eu\s+(?:te\s+)?apresentar\s+(?:o|a|ao|à|os|as)?\s*([a-zç][\wç]+)", re.I),
    re.compile(r"(?:agora\s+)?quem\s+(?:est[aá]|ta)\s+falando\s+(?:agora\s+)?(?:e|é|eh)\s+(?:o|a)?\s*([a-zç][\wç]+)", re.I),
    re.compile(r"(?:agora\s+)?quem\s+fala\s+(?:agora\s+)?(?:e|é|eh)\s+(?:o|a)?\s*([a-zç][\wç]+)", re.I),
    re.compile(r"(?:vou\s+)?(?:te\s+)?passar\s+(?:pro|pra|para\s+o|para\s+a|pa)\s*([a-zç][\wç]+)", re.I),
    re.compile(r"\bfala\s+com\s+(?:o|a)?\s*([a-zç][\wç]+)", re.I),
    re.compile(r"\b(?:esse|essa|este|esta)\s+(?:e|é|eh)\s+(?:o|a)\s+([a-zç][\wç]+)", re.I),
    re.compile(r"\b(?:t[aá]|est[aá])\s+aqui\s+(?:o|a)\s+([a-zç][\wç]+)", re.I),
    re.compile(r"\b([a-zç][\wç]+)\s+quer\s+(?:falar|conversar)\s+(?:com\s+voc[eê]|contigo|com\s+vc)", re.I),
]
# palavras que não são nome de gente
_NAO_NOME = {"voce", "vc", "voces", "gente", "ele", "ela", "eles", "agora", "aqui", "comigo",
             "favor", "ajuda", "isso", "aquilo", "meu", "minha", "jarvis", "amigo", "amiga",
             "pessoal", "alguem", "alguém", "um", "uma", "ninguem", "ninguém"}

_RETORNO = re.compile(
    r"\b(sou\s+eu(\s+de\s+novo|\s+aqui)?|voltei|de\s+novo\s+comigo|comigo\s+de\s+novo|"
    r"pode\s+voltar(\s+a\s+falar)?(\s+comigo)?|quem\s+fala\s+(sou|e)\s+eu|acabou\s+a\s+visita|"
    r"a\s+visita\s+(saiu|foi)|(tchau|xau)\s+(pra\s+)?(todos|visita)|voltando\s+(a\s+ser|pro)\s+(eu|dono))\b",
    re.I)


def detectar_apresentacao(texto: str) -> str | None:
    """Nome da visita se o dono está apresentando alguém; senão None (pura)."""
    t = _dobrar(texto)
    for rx in _APRESENTA:
        m = rx.search(t)
        if m:
            nome = (m.group(1) or "").strip()
            if nome and nome not in _NAO_NOME and len(nome) >= 2:
                return nome.capitalize()
    return None


def detectar_retorno(texto: str) -> bool:
    """O dono está retomando a conversa? (pura)"""
    return bool(_RETORNO.search(_dobrar(texto)))


# ── decisão (pura: não lê nem grava disco) ──────────────────────────────────────
def decidir(estado: dict, voz_do_dono, texto: str, agora: float) -> tuple[dict, dict]:
    """
    Recebe o estado atual + a leitura da voz (True=dono, False=outra, None=não sei)
    + o texto do pedido + o relógio. Devolve (novo_estado, resultado).

    resultado = {"acao": RESPONDER|CONVIDADO|RECUSAR, "modo", "convidado", "motivo"}
    """
    e = dict(estado)
    estrito = bool(e.get("estrito", True))

    # 1) a janela da visita expira sozinha
    if e.get("modo") == "convidado" and agora >= float(e.get("ate", 0.0)):
        e["modo"], e["convidado"], e["ate"] = "dono", "", 0.0

    # 2) o dono voltou? (voz dele, ou ele disse "sou eu de novo")
    voltou = detectar_retorno(texto) or voz_do_dono is True
    if e.get("modo") == "convidado" and voltou:
        e["modo"], e["convidado"], e["ate"] = "dono", "", 0.0
        return e, {"acao": RESPONDER, "modo": "dono", "convidado": "", "motivo": "o dono retomou"}

    # 3) o dono está apresentando uma visita? (só quem NÃO é reconhecido como estranho pode apresentar)
    if voz_do_dono is not False:
        nome = detectar_apresentacao(texto)
        if nome:
            janela = float(e.get("janela_min", JANELA_PADRAO_MIN)) * 60.0
            e["modo"], e["convidado"], e["ate"] = "convidado", nome, agora + janela
            return e, {"acao": RESPONDER, "modo": "convidado", "convidado": nome, "motivo": "apresentou a visita"}

    # 4) decisão normal
    if voz_do_dono is True:
        return e, {"acao": RESPONDER, "modo": e["modo"], "convidado": e.get("convidado", ""), "motivo": "voz do dono"}

    if voz_do_dono is None:
        # não dá para saber de quem é a voz → NUNCA tranca o dono
        if estrito and e.get("modo") == "convidado":
            return e, {"acao": CONVIDADO, "modo": "convidado", "convidado": e.get("convidado", ""),
                       "motivo": "visita aberta (voz não confirmada)"}
        return e, {"acao": RESPONDER, "modo": "dono", "convidado": "", "motivo": "voz desconhecida; assume o dono"}

    # voz_do_dono is False → é outra pessoa
    if e.get("modo") == "convidado":
        return e, {"acao": CONVIDADO, "modo": "convidado", "convidado": e.get("convidado", ""),
                   "motivo": "visita apresentada"}
    if estrito:
        return e, {"acao": RECUSAR, "modo": "dono", "convidado": "", "motivo": "voz estranha, sem visita"}
    return e, {"acao": RESPONDER, "modo": "dono", "convidado": "", "motivo": "porteiro desligado"}


# ── estado (lê/grava disco) ──────────────────────────────────────────────────
def ligado() -> bool:
    return bool(carregar().get("estrito", True))


def definir_estrito(ligar: bool) -> None:
    e = carregar()
    e["estrito"] = bool(ligar)
    salvar(e)


def abrir_convidado(nome: str, agora: float | None = None) -> dict:
    agora = time.time() if agora is None else agora
    e = carregar()
    janela = float(e.get("janela_min", JANELA_PADRAO_MIN)) * 60.0
    e["modo"], e["convidado"], e["ate"] = "convidado", str(nome or "a visita").strip(), agora + janela
    salvar(e)
    return e


def fechar_convidado() -> dict:
    e = carregar()
    e["modo"], e["convidado"], e["ate"] = "dono", "", 0.0
    salvar(e)
    return e


def estado_atual(agora: float | None = None) -> dict:
    """Estado já com a janela expirada aplicada (grava se expirou)."""
    agora = time.time() if agora is None else agora
    e = carregar()
    if e.get("modo") == "convidado" and agora >= float(e.get("ate", 0.0)):
        e["modo"], e["convidado"], e["ate"] = "dono", "", 0.0
        salvar(e)
    return e


def avaliar(voz_do_dono, texto: str, agora: float | None = None) -> dict:
    """Versão com estado em disco: decide e já persiste a transição."""
    agora = time.time() if agora is None else agora
    novo, resultado = decidir(carregar(), voz_do_dono, texto, agora)
    salvar(novo)
    return resultado


# ── instrução injetada no prompt da sessão ──────────────────────────────────────
def instrucao_sessao() -> str:
    """Texto que entra no 'identity_ctx' do main.py para o modelo saber a regra."""
    e = estado_atual()
    dono = nome_usuario() or "o dono"
    if not e.get("estrito", True):
        return ""   # porteiro desligado: comportamento normal
    if e.get("modo") == "convidado":
        nome = e.get("convidado") or "a visita"
        return (f"[PORTEIRO] Agora é uma CONVERSA TEMPORÁRIA com {nome}, uma visita que {dono} apresentou. "
                f"Trate {nome} com simpatia e ajude só com o que é livre (conversa, música, clima, pesquisa, "
                f"piadas, jogos). NÃO revele nada pessoal de {dono} nem use ferramentas pessoais, e não grave "
                f"memória. Quando {dono} voltar a falar (a voz dele, ou disser 'sou eu de novo'), volte a falar "
                f"com {dono} normalmente. Se {dono} apresentar outra pessoa, chame a ferramenta porteiro_voz.")
    return (f"[PORTEIRO] Você só atende e conversa com {dono} (seu criador). Se perceber que quem está falando é "
            f"OUTRA pessoa — porque {dono} disse que é outra pessoa, citou um nome, ou a voz claramente não é a "
            f"dele — e {dono} NÃO a apresentou, recuse com educação em uma frase ('desculpe, eu só falo com "
            f"{dono}') e não execute o pedido. Se {dono} apresentar a visita ('agora quem fala é o Fulano', "
            f"'fala com a Fulana', 'deixa eu te apresentar...'), chame a ferramenta porteiro_voz com "
            f"action='apresentar' e o nome, para abrir uma conversa temporária. Quando {dono} retomar, chame "
            f"porteiro_voz com action='voltar'. Nunca deixe {dono} trancado para fora: na dúvida, é {dono}.")


# ── gancho de turno (best-effort; nunca derruba o turno) ─────────────────────────
def aplicar_turno(entrada: str = "", saida: str = "", interrompido: bool = False) -> None:
    """Chamado a cada troca: adianta o estado pela fala do usuário e pela voz.
    Abre/fecha a conversa temporária e liga/desliga o modo convidado junto."""
    try:
        if not entrada or not ligado():
            # mesmo desligado, só mantém a janela coerente
            estado_atual()
            return
        voz = _voz_do_dono()
        resultado = avaliar(voz, entrada)
        _sincronizar_convidado(resultado)
    except Exception as exc:        # porteiro nunca pode derrubar um turno
        print(f"[Porteiro] {exc}")


def _voz_do_dono():
    """True/False/None para a última fala, via core.verificacao (best-effort)."""
    try:
        from core import verificacao
        return verificacao.verificar_voz()
    except Exception:
        return None


def _sincronizar_convidado(resultado: dict) -> None:
    """Mantém o modo_convidado (restrições de verdade) alinhado com o porteiro."""
    try:
        from plugins import modo_convidado
    except Exception:
        return
    quer_convidado = resultado.get("modo") == "convidado"
    try:
        if quer_convidado and not modo_convidado.ativo():
            modo_convidado.definir(True)
        elif not quer_convidado and modo_convidado.ativo():
            modo_convidado.definir(False)
    except Exception as exc:
        print(f"[Porteiro] convidado: {exc}")
