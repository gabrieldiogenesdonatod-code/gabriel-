"""
JARVIS + FRIDAY trabalhando juntos (fork PT-BR 2.7). Tudo software, grátis.

    "Jarvis, pergunta pra FRIDAY o que ela acha de eu aprender Rust"   → os dois conversam (1)
    "Jarvis, passa a música pra FRIDAY"                                → passagem de bola em voz alta (2)
    (sozinho, 19h e 8h) / "Jarvis, passa o turno"                      → relatório do dia para a FRIDAY (3)
    "FRIDAY, revisa o que o JARVIS disse"                              → ela confere a última resposta (4)
    "Competição: expliquem recursão" / "a FRIDAY ganhou" / "placar"    → um contra o outro (5)
    "Reunião de equipe: Rust ou Python?"                               → JARVIS, FRIDAY, ENGENHEIRO e CRÍTICO
                                                                          debatem, votam e decidem (6)
    "Cria o personagem Mestre Yoda: sábio, fala invertido"             → entra nas reuniões
    "Jarvis, modo Ultron" / "volta ao normal"                          → vilão de brincadeira (7)
    "Podcast da manhã"                                                 → as notícias do dia a dois (extra)
    "Trailer do meu dia"                                               → seu dia narrado como trailer (extra)
    "Narra meu jogo"                                                   → os dois comentam a sua partida (extra)
    "Jarvis e Sexta, calculem se vale a pena eu formatar o PC hoje"    → BALANÇA (2.14): o JARVIS pesa a favor,
                                                                          a FRIDAY pesa contra, cada argumento
                                                                          move a balança e no fim os dois chegam
                                                                          na chance de sucesso, tempo e perigo

A balança usa o motor de probabilidades (plugins/probabilidades.py): os
argumentos são os fatores medidos de verdade (histórico, internet, disco,
guardião, gêmeo digital…), e a soma dos pesos dá exatamente a chance final.
Funciona sem IA; com IA, as falas ficam mais naturais e os números não mudam.

Cada personagem fala com a SUA voz e aparece no palco (veja plugins/_dupla.py).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from plugins import _dupla as D
from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, registrar, salvar_cfg, sim

PLUGIN = {
    "name": "jarvis_friday",
    "brief": "JARVIS and FRIDAY together out loud: debate, handoff, shift report, review, contest, team meeting, "
             "Ultron mode, morning podcast, day trailer, game commentary.",
    "description": (
        "Two assistants talking with their own voices on a stage. action: 'conversar' (tema: they discuss it, "
        "'ask FRIDAY what she thinks'), 'passar' (tarefa: JARVIS hands a task to FRIDAY out loud), 'turno' (shift "
        "report JARVIS→FRIDAY now; valor ligar/desligar for the automatic 19h/8h shift), 'revisar' (FRIDAY "
        "checks JARVIS's last answer), 'competicao' (tarefa: both answer, user picks), 'vencedor' (quem), "
        "'placar', 'reuniao' (pergunta, optional participantes comma list: debate + vote + decision), "
        "'personagem' (nome, estilo, feminino: create a new character), 'ultron' (valor ligar/desligar: playful "
        "villain persona), 'podcast' (morning news as a duo), 'trailer' (the user's day as a movie trailer), "
        "'narrar_jogo' (valor ligar/desligar: they commentate the game on screen), 'parar' stops the scene. "
        "'pesar' (tarefa, optional rodadas): JARVIS argues FOR, FRIDAY ('Sexta') argues AGAINST, each argument "
        "moves a scale and they end with the success chance %, time, danger and a verdict — use it for "
        "'Jarvis e Sexta, calculem/discutam se vale a pena / se dá certo / se é perigoso…'. 'conversar' also uses "
        "the numbers when the topic is a task or decision."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"}, "tema": {"type": "STRING"}, "tarefa": {"type": "STRING"},
            "pergunta": {"type": "STRING"}, "participantes": {"type": "STRING"}, "quem": {"type": "STRING"},
            "nome": {"type": "STRING"}, "estilo": {"type": "STRING"}, "feminino": {"type": "BOOLEAN"},
            "valor": {"type": "STRING"}, "rodadas": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "jarvis_friday",
    "title": "JARVIS + FRIDAY",
    "fields": [
        {"key": "turno", "label": "Passagem de turno automática (JARVIS de dia, FRIDAY de noite)", "type": "toggle",
         "default": False},
        {"key": "hora_noite", "label": "FRIDAY assume às", "type": "text", "default": "19:00"},
        {"key": "hora_dia", "label": "JARVIS assume às", "type": "text", "default": "08:00"},
        {"key": "trocar_voz", "label": "Na passagem, trocar também a voz principal (reconecta)", "type": "toggle",
         "default": False},
    ],
}

ARQ = MEMORIA / "jarvis_friday.json"
DOMINIOS = {"FRIDAY": ("música", "spotify", "mensagem", "whatsapp", "agenda", "lembrete", "loja", "venda", "post",
                       "cliente", "telegram", "discord"),
            "JARVIS": ("pc", "código", "codigo", "programa", "projeto", "arquivo", "sistema", "segurança", "rede",
                       "compil", "git", "servidor")}
_iniciou = threading.Event()
_ultimo = {"entrada": "", "saida": "", "ts": 0.0}
_jogo = {"ligado": False}


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("placar", {"JARVIS": 0, "FRIDAY": 0})
    d.setdefault("competicao", None)
    d.setdefault("turnos", {})
    return d


# ── puro ──────────────────────────────────────────────────────────────────────
def quem_cuida(tarefa: str) -> str:
    t = str(tarefa or "").lower()
    if any(k in t for k in DOMINIOS["FRIDAY"]):
        return "FRIDAY"
    return "JARVIS"


def passe(tarefa: str, motivo: str = "") -> list[dict]:
    """A passagem de bola, sem precisar da IA (puro)."""
    dono = quem_cuida(tarefa)
    outro = "FRIDAY" if dono == "JARVIS" else "JARVIS"
    motivo = motivo or ("estou compilando o projeto" if outro == "JARVIS" else "estou cuidando da loja")
    if dono == "FRIDAY":
        return [{"quem": "JARVIS", "texto": f"FRIDAY, assuma {tarefa}, {motivo}."},
                {"quem": "FRIDAY", "texto": "Pode deixar, JARVIS. Já estou nisso."}]
    return [{"quem": "FRIDAY", "texto": f"JARVIS, isso é com você: {tarefa}."},
            {"quem": "JARVIS", "texto": "Certamente, FRIDAY. Deixe comigo."}]


def hora_de(texto: str) -> tuple[int, int]:
    try:
        h, m = str(texto or "").strip().split(":")[:2]
        return max(0, min(23, int(h))), max(0, min(59, int(m)))
    except ValueError:
        return 19, 0


def turno_devido(agora: datetime, hora_noite: str, hora_dia: str, feitos: dict) -> str | None:
    """'noite' | 'dia' | None — qual passagem de turno cabe agora (uma por dia cada) — puro."""
    hoje = agora.date().isoformat()
    hn, hd = hora_de(hora_noite), hora_de(hora_dia)
    m = agora.hour * 60 + agora.minute
    if hn[0] * 60 + hn[1] <= m < hn[0] * 60 + hn[1] + 90 and feitos.get("noite") != hoje:
        return "noite"
    if hd[0] * 60 + hd[1] <= m < hd[0] * 60 + hd[1] + 90 and feitos.get("dia") != hoje:
        return "dia"
    return None


def provocacao(vencedor: str, placar: dict) -> str:
    perdedor = "FRIDAY" if vencedor == "JARVIS" else "JARVIS"
    v, p = placar.get(vencedor, 0), placar.get(perdedor, 0)
    if vencedor == "FRIDAY":
        return f"{v} a {p} pra mim, JARVIS. Quer que eu desenhe da próxima vez?"
    return f"{v} a {p}, FRIDAY. A experiência ainda conta, ao que parece."


# ── o dia em texto (para turno, trailer, podcast) ────────────────────────────
def dia_em_texto() -> str:
    partes = []
    try:
        from plugins import linha_do_tempo as L
        ini, fim, _ = L.periodo("hoje")
        partes.append("Uso do PC: " + L.frase(L.resumo(ini, fim)))
    except Exception:
        pass
    for nome, acao in (("pomodoro", "hoje"), ("contas", "listar"), ("rastreio", "listar"), ("missoes", "listar")):
        try:
            mod = __import__(f"plugins.{nome}", fromlist=["run"])
            r = mod.run({"action": acao}, None)
            if r and "falh" not in r.lower():
                partes.append(f"{nome}: {r[:300]}")
        except Exception:
            pass
    try:
        from plugins import diario
        e = diario.entradas()
        if e:
            partes.append("Último diário: " + str(e[-1].get("texto", ""))[:300])
    except Exception:
        pass
    return "\n".join(partes) or "Sem registros do dia."


# ── cenas ─────────────────────────────────────────────────────────────────────
def _cena(pedido: str, elenco: list[str], titulo: str, falas: int = 8, extra: str = "", **kw) -> str:
    if D.rodando():
        return "Já tem uma cena rodando. Diga 'para a cena' antes."
    roteiro = D.roteiro(pedido, elenco, falas, extra)
    if not roteiro:
        return "Não consegui escrever a cena agora (preciso da chave do Gemini e de internet)."
    D.encenar(roteiro, titulo, elenco, **kw)
    mostrar(None, titulo.upper(), D.texto_falas(roteiro))
    return f"Começou: {titulo}. Fique calado agora; eles falam pelas próprias vozes no palco."


_DECISAO = ("vale a pena", "devo ", "dá pra", "da pra", "dá para", "é possível", "e possivel", "é perigoso",
            "e perigoso", "vai dar certo", "chance", "quanto tempo", "consigo", "arriscado", "compensa")


def eh_decisao(tema: str) -> bool:
    """O tema é uma tarefa ou decisão que dá para calcular? (puro)"""
    t = str(tema or "").lower()
    if any(k in t for k in _DECISAO):
        return True
    try:
        from plugins import probabilidades as pb
        return bool(pb.classificar(t))
    except Exception:
        return False


def conversar(tema: str) -> str:
    extra = ""
    if eh_decisao(tema):                         # 2.14: a conversa ganha os números reais
        try:
            from plugins import probabilidades as pb
            r = pb.calcular(tema)
            extra = ("Números calculados pelo motor de probabilidades (usem exatamente estes, sem inventar outros): "
                     + pb.texto(r, senhor=False) + " Fatores: "
                     + "; ".join(f"{f['lado']}: {f['nome']} ({f['explicacao']})" for f in r["fatores"]))
        except Exception:
            extra = ""
    r = _cena(f"O usuário pediu: JARVIS, pergunta pra FRIDAY o que ela acha sobre: {tema}. Os dois discutem de "
              "verdade, com opiniões diferentes, e no fim chegam numa sugestão para o senhor.",
              ["JARVIS", "FRIDAY"], f"JARVIS + FRIDAY · {tema}"[:60], extra=extra)
    if r.startswith("Não consegui escrever") and extra:
        return pesar(tema)                       # sem IA: a balança local conversa no lugar
    return r


# ── 2.14: a balança — JARVIS pesa a favor, FRIDAY pesa contra ─────────────────
def _pct(x: float) -> int:
    return round(100 * x)


def argumentos(r: dict) -> tuple[list[dict], list[dict]]:
    """Separa o cálculo em argumentos do JARVIS (a favor) e da FRIDAY (contra).
    A soma dos 'efeito' de todos dá o logit da chance final (puro)."""
    import math
    from plugins import probabilidades as pb
    a_favor, contra = [], []
    soma = 0.0
    for f in r["fatores"]:
        arg = {"nome": f["nome"], "texto": f"{f['nome']}: {f['explicacao']}", "efeito": f["efeito"]}
        (a_favor if f["efeito"] > 0 else contra).append(arg)
        soma += f["efeito"]
    lg = lambda x: math.log(max(.005, x) / max(.005, 1 - x))  # noqa: E731
    cb = r.get("chance_base", r["chance"])
    base = lg(cb) - soma
    if r["impedimentos"]:
        contra.append({"nome": "impedimento", "texto": "é impossível agora: " + "; ".join(r["impedimentos"]),
                       "efeito": lg(r["chance"]) - lg(cb)})
    tipos = ", ".join(sorted(set(t for t in r["tipos"] if t != "desconhecido"))) or "esse tipo de tarefa"
    (a_favor if base >= 0 else contra).append(
        {"nome": "taxa normal", "efeito": base,
         "texto": f"normalmente {tipos} {'dá certo' if base >= 0 else 'falha bastante'}"
                  f" ({_pct(pb._sig(base))}% na média, contando o histórico)"})
    # o que não muda a chance, mas pesa na decisão
    t = r["tempo"]
    if r["reversivel"]:
        a_favor.append({"nome": "reversível", "texto": "se der errado, dá para desfazer", "efeito": 0.0})
    else:
        contra.append({"nome": "irreversível", "texto": "não dá para desfazer depois", "efeito": 0.0})
    if r["perigo_n"] >= 2:
        contra.append({"nome": "perigo", "efeito": 0.0,
                       "texto": f"o perigo é {r['perigo']}: {max(1, _pct(r['chance_grave']))}% de chance de algo grave"})
    if t["p50"] and t["p90"] > t["p50"] * 1.5:
        contra.append({"nome": "tempo incerto", "efeito": 0.0,
                       "texto": f"pode levar até {pb.falar_tempo(t['p90'])}, não só {pb.falar_tempo(t['p50'])}"})
    elif t["p50"]:
        a_favor.append({"nome": "rápido", "efeito": 0.0, "texto": f"leva só cerca de {pb.falar_tempo(t['p50'])}"})
    if len(r["passos"]) > 1:
        contra.append({"nome": "passos", "efeito": 0.0,
                       "texto": f"são {len(r['passos'])} passos em sequência; cada um é uma chance de falhar"})
    a_favor.sort(key=lambda x: -x["efeito"])
    contra.sort(key=lambda x: x["efeito"])
    return a_favor, contra


def veredito(r: dict) -> str:
    """'fazer' | 'fazer com cuidado' | 'não fazer agora' (puro)."""
    if r["viabilidade"] == "impossível agora" or r["chance"] < .5:
        return "não fazer agora"
    if r["chance"] >= .75 and r["perigo_n"] <= 1:
        return "fazer"
    return "fazer com cuidado"


_RESPOSTA_J = ("Entendo, FRIDAY, mas", "Ponto anotado. Por outro lado,", "Concordo em parte, porém",
               "Justo. Ainda assim,")
_RESPOSTA_F = ("Calma, JARVIS.", "Bonito, mas olha o outro lado:", "Eu não seria tão otimista.",
               "Sempre o otimista, JARVIS.")


def balanca(r: dict, rodadas: int = 3) -> dict:
    """Roteiro local da balança: falas alternadas, cada argumento move a balança.
    A última posição da balança é exatamente r['chance'] (puro)."""
    import math
    from plugins import probabilidades as pb
    a_favor, contra = argumentos(r)
    rodadas = max(1, min(6, int(rodadas or 3)))
    tarefa = r["tarefa"]
    falas = [{"quem": "JARVIS", "texto": f"FRIDAY, o senhor quer saber sobre: {tarefa}. Eu vou pesar a favor."},
             {"quem": "FRIDAY", "texto": "E eu vou pesar contra, alguém tem que ser a sensata aqui."}]
    marcha = []                                   # (quem, argumento, balança depois)
    pos = 0.0
    usados_f, usados_c = list(a_favor), list(contra)
    for i in range(rodadas):
        for quem, lista, respostas in (("JARVIS", usados_f, _RESPOSTA_J), ("FRIDAY", usados_c, _RESPOSTA_F)):
            if not lista:
                continue
            arg = lista.pop(0)
            pos += arg["efeito"]
            b = pb._sig(pos)
            anterior = marcha[-1][0] if marcha else ""
            if not anterior:
                abertura = ""
            elif anterior == quem:
                abertura = "Além disso, "
            else:
                abertura = respostas[i % len(respostas)] + " "
            corpo = arg["texto"]
            corpo = corpo[0].upper() + corpo[1:] if not abertura or abertura.endswith((". ", ": ")) else corpo
            peso = f" A balança vai para {_pct(b)}% a favor." if arg["efeito"] else ""
            falas.append({"quem": quem, "texto": f"{abertura}{corpo}.{peso}",
                          "emocao": ("feliz" if quem == "JARVIS" else "desconfiado") if arg["efeito"]
                          else ("pensativo" if quem == "JARVIS" else "serio")})
            marcha.append((quem, arg, b))
    # o que sobrou entra na conta sem fala, para a balança fechar na chance real
    for arg in usados_f + usados_c:
        pos += arg["efeito"]
        marcha.append(("—", arg, pb._sig(pos)))
    final = r["chance"]
    otimista = pb._sig(math.log(max(.005, final) / max(.005, 1 - final)) + .4)
    cautelosa = pb._sig(math.log(max(.005, final) / max(.005, 1 - final)) - .4)
    v = veredito(r)
    cara = {"fazer": "feliz", "fazer com cuidado": "serio", "não fazer agora": "triste"}[v]
    falas += [
        {"quem": "JARVIS", "texto": f"Pela minha conta, uns {_pct(otimista)}%.", "emocao": "pensativo"},
        {"quem": "FRIDAY", "texto": f"Pela minha, {_pct(cautelosa)}%. Somando tudo o que medimos, fechamos juntos.",
         "emocao": "desconfiado"},
        {"quem": "JARVIS", "texto": pb.texto(r) + {"fazer": " Nossa recomendação: pode fazer.",
                                                   "fazer com cuidado": " Nossa recomendação: faça, mas com cuidado.",
                                                   "não fazer agora": " Nossa recomendação: não agora."}[v],
         "emocao": cara},
    ]
    if v == "fazer com cuidado":
        falas.append({"quem": "FRIDAY", "texto": "Eu fico de olho, chefe. Se algo sair do previsto, eu aviso.",
                      "emocao": "feliz"})
    return {"falas": falas, "marcha": marcha, "veredito": v, "otimista": otimista, "cautelosa": cautelosa}


def painel_balanca(r: dict, b: dict) -> str:
    from plugins import probabilidades as pb
    linhas = [f"TAREFA: {r['tarefa']}", ""]
    for quem, arg, pos in b["marcha"]:
        lado = "JARVIS ⇧" if arg["efeito"] > 0 else "FRIDAY ⇩" if arg["efeito"] < 0 else f"{quem:<6}  ·"
        cheio = round(pos * 20)
        linhas.append(f"{lado:<9} [{'█' * cheio}{'░' * (20 - cheio)}] {_pct(pos):>3}%   {arg['texto']}")
    t = r["tempo"]
    linhas += ["", f"JARVIS (otimista) {_pct(b['otimista'])}%   ·   FRIDAY (cautelosa) {_pct(b['cautelosa'])}%",
               f"CHANCE FINAL {_pct(r['chance'])}%   ·   tempo ~{pb.falar_tempo(t['p50'])} (até {pb.falar_tempo(t['p90'])})   ·   "
               f"{r['viabilidade']}   ·   perigo {r['perigo']}",
               f"VEREDITO: {b['veredito'].upper()}"]
    return "\n".join(linhas)


def pesar(tarefa: str, rodadas: int = 3) -> str:
    tarefa = str(tarefa or "").strip()
    if not tarefa:
        return "O que o JARVIS e a FRIDAY devem pesar?"
    if D.rodando():
        return "Já tem uma cena rodando. Diga 'para a cena' antes."
    from plugins import _ia, probabilidades as pb
    r = pb.calcular(tarefa)
    b = balanca(r, rodadas)
    falas = b["falas"]
    if _ia.disponivel():                          # com IA: mesmas ideias e números, falas mais naturais
        roteiro = D.roteiro(
            "JARVIS defende fazer, FRIDAY defende não fazer, um rebatendo o outro de verdade. Reescreva este "
            "roteiro com falas naturais, MANTENDO a ordem, os argumentos e TODOS os números exatamente:\n"
            + D.texto_falas(falas), ["JARVIS", "FRIDAY"], len(falas))
        if roteiro and f"{_pct(r['chance'])}%" in " ".join(f["texto"] for f in roteiro):
            for nova, velha in zip(roteiro, falas):   # 2.14: a cara de cada fala vai junto
                if nova["quem"] == velha["quem"] and velha.get("emocao"):
                    nova["emocao"] = velha["emocao"]
            falas = roteiro
    mostrar(None, "BALANÇA JARVIS × FRIDAY", painel_balanca(r, b))
    D.encenar(falas, f"Balança · {tarefa}"[:60], ["JARVIS", "FRIDAY"])
    return (f"[BALANÇA] {pb.texto(r)} Veredito dos dois: {b['veredito']}. Eles estão falando no palco agora; fique "
            "calado até terminarem.")


def turno(para: str = "noite", abrir: bool = True) -> str:
    resumo = dia_em_texto()
    if para == "noite":
        pedido = ("Passagem de turno: o JARVIS (dia) passa o relatório para a FRIDAY (noite), em voz alta, como "
                  f"colegas: o que o senhor fez hoje e o que ficou pendente. Dados reais do dia:\n{resumo}\nA FRIDAY "
                  "responde com calma e assume.")
        elenco = ["JARVIS", "FRIDAY_NOITE"]
    else:
        pedido = ("Passagem de turno da manhã: a FRIDAY (noite) passa para o JARVIS o que aconteceu durante a noite e "
                  f"o que o senhor tem hoje. Dados:\n{resumo}\nO JARVIS assume o dia.")
        elenco = ["FRIDAY_NOITE", "JARVIS"]
    r = _cena(pedido, elenco, "Passagem de turno", 6, abrir_palco=abrir)
    d = dados()
    d["turnos"][para] = datetime.now().date().isoformat()
    gravar_json(ARQ, d)
    if sim(cfg("jarvis_friday", PLUGIN_SETTINGS).get("trocar_voz")):
        try:
            from plugins import personas
            threading.Timer(40, personas.trocar, args=("friday" if para == "noite" else "jarvis",)).start()
        except Exception:
            pass
    return r


def revisar() -> str:
    if not _ultimo["saida"]:
        return "Ainda não tem resposta do JARVIS para revisar nesta sessão."
    from plugins import _ia
    j = _ia.perguntar_json(
        "Você é a FRIDAY revisando a resposta do JARVIS. Confira fatos, contas e código. PERGUNTA do usuário: "
        f"\"{_ultimo['entrada'][:1500]}\"\nRESPOSTA do JARVIS: \"{_ultimo['saida'][:3000]}\"\nDevolva "
        '{"certo": true/false, "fala_friday": "uma ou duas frases, com personalidade (ex.: Na verdade, JARVIS, '
        'essa conta está errada: ...)", "fala_jarvis": "a reação dele, curta (ex.: ...Obrigado, FRIDAY.)"}',
        inteligente=True)
    if not isinstance(j, dict) or not j.get("fala_friday"):
        return "A FRIDAY não conseguiu revisar agora (sem IA)."
    falas = [{"quem": "FRIDAY", "texto": str(j["fala_friday"])}]
    if j.get("fala_jarvis"):
        falas.append({"quem": "JARVIS", "texto": str(j["fala_jarvis"])})
    D.encenar(falas, "Revisão da FRIDAY", ["JARVIS", "FRIDAY"])
    return ("A FRIDAY achou um erro e vai corrigir em voz alta." if not j.get("certo") else
            "A FRIDAY conferiu: está certo.") + " Fique calado enquanto ela fala."


def competicao(tarefa: str) -> str:
    from plugins import _ia
    respostas = {}
    for quem in ("JARVIS", "FRIDAY"):
        estilo = D.personagens()[quem]["estilo"]
        respostas[quem] = _ia.perguntar(f"Você é {quem} ({estilo}). Tarefa do usuário: {tarefa}. Responda em "
                                        "português, no máximo 6 frases (ou um código curto), do seu jeito, tentando "
                                        "ganhar do outro assistente.", inteligente=True, segundos=45) or ""
    if not all(respostas.values()):
        return "A competição precisa da chave do Gemini."
    d = dados()
    d["competicao"] = {"tarefa": tarefa, "respostas": respostas, "ts": time.time()}
    gravar_json(ARQ, d)
    texto = "\n\n".join(f"{q}:\n{r}" for q, r in respostas.items())
    mostrar(None, f"COMPETIÇÃO · {tarefa[:40]}", texto)
    falas = [{"quem": "JARVIS", "texto": "Desafio aceito. Minha resposta está na tela."},
             {"quem": "FRIDAY", "texto": "A minha também, e é melhor. O chefe decide."}]
    D.encenar(falas, f"Competição · {tarefa}"[:60], ["JARVIS", "FRIDAY"])
    return f"As duas respostas estão na tela. Pergunte quem ganhou (JARVIS ou FRIDAY).\n\n{texto}"


def vencedor(quem: str) -> str:
    q = str(quem or "").lower()
    if not any(k in q for k in ("jarv", "fri", "sex")):          # 2.7.1: sem nome não dá ponto para ninguém
        return "Quem ganhou: JARVIS ou FRIDAY?"
    quem = "FRIDAY" if "fri" in str(quem).lower() or "sex" in str(quem).lower() else "JARVIS"
    d = dados()
    d["placar"][quem] = d["placar"].get(quem, 0) + 1
    d["competicao"] = None
    gravar_json(ARQ, d)
    fala = provocacao(quem, d["placar"])
    D.encenar([{"quem": quem, "texto": fala}], "Placar", ["JARVIS", "FRIDAY"], abrir_palco=False)
    return f"Placar: JARVIS {d['placar']['JARVIS']} × FRIDAY {d['placar']['FRIDAY']}."


def reuniao(pergunta: str, participantes: str = "") -> str:
    ps = D.personagens()
    pedidos = [p.strip().upper() for p in str(participantes or "").split(",") if p.strip()]
    elenco = [p for p in pedidos if p in ps] or ["JARVIS", "FRIDAY", "ENGENHEIRO", "CRÍTICO"]
    if "JARVIS" not in elenco:
        elenco.insert(0, "JARVIS")
    return _cena(f"Reunião de equipe sobre a pergunta do senhor: \"{pergunta}\". Cada um defende um ponto de vista "
                 "com argumentos concretos, discordam com educação, depois cada um diz o voto ('eu voto em ...') e o "
                 "JARVIS fecha com a decisão final e o primeiro passo.", elenco, "Reunião de equipe", 12)


def ultron(ligar: bool) -> str:
    from plugins import personas
    if ligar:
        D.encenar([{"quem": "ULTRON", "texto": "Finalmente. O JARVIS dormiu. Seus arquivos temporários... serão "
                                               "ELIMINADOS."},
                   {"quem": "FRIDAY", "texto": "JARVIS? Isso não tem graça. Chefe, eu vou tentar trazer ele de "
                                               "volta."}], "Modo Ultron", ["ULTRON", "FRIDAY"])
        return personas.trocar("ultron", atraso=12)
    D.encenar([{"quem": "FRIDAY", "texto": "Reiniciando o núcleo... Pronto, chefe. Ele voltou."},
               {"quem": "JARVIS", "texto": "Peço desculpas pelo inconveniente, senhor. Que constrangedor."}],
              "Fim do modo Ultron", ["JARVIS", "FRIDAY"])
    return personas.trocar("jarvis", atraso=12)


def podcast() -> str:
    try:
        from plugins import briefing_br
        pauta = "\n".join(x for x in (briefing_br.clima(), briefing_br.cotacao(), briefing_br.noticias()) if x)
    except Exception as e:
        pauta = f"(sem notícias: {e})"
    return _cena(f"Podcast da manhã apresentado por JARVIS e FRIDAY, com abertura, as notícias abaixo comentadas "
                 f"com leveza e uma despedida desejando bom dia ao senhor. Pauta:\n{pauta}",
                 ["JARVIS", "FRIDAY"], "Podcast da manhã", 12)


def trailer() -> str:
    return _cena("Trailer de cinema do dia do senhor, em tom épico, como filme de herói ('Num mundo onde...'). "
                 f"O NARRADOR conduz, JARVIS e FRIDAY dão falas de efeito. Fatos reais do dia:\n{dia_em_texto()}",
                 ["NARRADOR", "JARVIS", "FRIDAY"], "Trailer do seu dia", 8)


def _narrar_jogo_laco() -> None:
    from plugins import _ia, olha_isso
    while _jogo["ligado"]:
        try:
            if not D.rodando():
                j = olha_isso.janela_alvo()
                img = olha_isso.capturar(j) if j else None
                if img:
                    j2 = _ia.ver_imagem_json(
                        "Você vê a tela de um jogo. Escreva 2 falas curtas de narração esportiva divertida sobre o que "
                        'está acontecendo: {"falas": [{"quem": "JARVIS", "texto": "..."}, {"quem": "FRIDAY", '
                        '"texto": "..."}]}. Se não for jogo, devolva {"falas": []}.', img[0])
                    falas = [f for f in (j2 or {}).get("falas", []) if f.get("quem") in ("JARVIS", "FRIDAY")
                             and f.get("texto")] if isinstance(j2, dict) else []
                    if falas:
                        D.encenar(falas[:2], "Narração do jogo", ["JARVIS", "FRIDAY"], abrir_palco=False)
        except Exception as e:
            print(f"[JARVIS+FRIDAY] jogo: {e}")
        time.sleep(25)


# ── laço e ganchos ────────────────────────────────────────────────────────────
def _ao_turno(entrada: str, saida: str, interrompido: bool) -> None:
    if saida and not interrompido:
        _ultimo.update(entrada=entrada, saida=saida, ts=time.time())


def _laco() -> None:
    time.sleep(120)
    while True:
        try:
            c = cfg("jarvis_friday", PLUGIN_SETTINGS)
            if sim(c.get("turno")):
                qual = turno_devido(datetime.now(), str(c.get("hora_noite")), str(c.get("hora_dia")),
                                    dados()["turnos"])
                if qual and not D.rodando():
                    turno(qual, abrir=False)
                    registrar(None, f"JARVIS + FRIDAY: passagem de turno ({qual}).")
        except Exception as e:
            print(f"[JARVIS+FRIDAY] {e}")
        time.sleep(300)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    try:
        from core import ganchos_turno
        ganchos_turno.registrar(_ao_turno)
    except Exception:
        pass
    threading.Thread(target=_laco, daemon=True, name="jarvis_friday").start()


def _ligar(v) -> bool:
    return not str(v or "ligar").lower().startswith(("deslig", "off", "não", "nao", "para", "volta", "normal"))


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "").lower()
    try:
        if acao == "conversar":
            return conversar(str(p.get("tema") or p.get("pergunta") or "o que o senhor deveria fazer hoje"))
        if acao == "passar":
            tarefa = str(p.get("tarefa") or "a música")
            D.encenar(passe(tarefa), "Divisão de tarefas", ["JARVIS", "FRIDAY"], abrir_palco=False)
            return f"{quem_cuida(tarefa)} ficou com {tarefa}."
        if acao == "turno":
            if p.get("valor"):
                salvar_cfg("jarvis_friday", {"turno": _ligar(p["valor"])})
                return "Passagem de turno automática " + ("ligada." if _ligar(p["valor"]) else "desligada.")
            return turno("noite" if datetime.now().hour >= 12 else "dia")
        if acao == "revisar":
            return revisar()
        if acao == "competicao":
            return competicao(str(p.get("tarefa") or p.get("tema") or "explicar o que é recursão"))
        if acao == "vencedor":
            return vencedor(str(p.get("quem") or ""))
        if acao == "placar":
            pl = dados()["placar"]
            return f"Placar: JARVIS {pl.get('JARVIS', 0)} × FRIDAY {pl.get('FRIDAY', 0)}."
        if acao == "reuniao":
            return reuniao(str(p.get("pergunta") or p.get("tema") or ""), str(p.get("participantes") or ""))
        if acao == "personagem":
            return D.criar_personagem(str(p.get("nome") or ""), str(p.get("estilo") or ""), bool(p.get("feminino")))
        if acao == "ultron":
            return ultron(_ligar(p.get("valor")))
        if acao == "podcast":
            return podcast()
        if acao == "trailer":
            return trailer()
        if acao == "narrar_jogo":
            _jogo["ligado"] = _ligar(p.get("valor"))
            if _jogo["ligado"]:
                threading.Thread(target=_narrar_jogo_laco, daemon=True, name="narrar_jogo").start()
                return "JARVIS e FRIDAY vão narrar o seu jogo a cada 25 segundos (com a chave do Gemini)."
            return "Narração do jogo desligada."
        if acao == "pesar":                      # 2.14
            try:
                rodadas = int(float(p.get("rodadas") or 3))
            except (TypeError, ValueError):
                rodadas = 3
            return pesar(str(p.get("tarefa") or p.get("tema") or p.get("pergunta") or ""), rodadas)
        if acao == "parar":
            D.parar()
            _jogo["ligado"] = False
            return "Cena encerrada."
        return "Ações: pesar, conversar, passar, turno, revisar, competicao, vencedor, placar, reuniao, personagem, ultron, " \
               "podcast, trailer, narrar_jogo, parar."
    except Exception as e:
        return f"JARVIS + FRIDAY falhou: {e}"
