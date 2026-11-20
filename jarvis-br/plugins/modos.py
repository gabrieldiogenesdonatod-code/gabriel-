"""
Modos do JARVIS (fork PT-BR 2.17) — um lugar só para todos os modos novos.

    "Jarvis, modo loja"            "Jarvis, sai do modo loja"
    "Jarvis, quais modos você tem?"   "Jarvis, em que modo você está?"

Cada modo é uma linha na tabela MODOS: passos ao ENTRAR e ao SAIR (os mesmos
passos dos protocolos: abrir, fechar, volume, ferramenta, mensagem…), a cara
do rosto, e um JEITO DE FALAR que o JARVIS segue enquanto o modo está ligado.
Só um modo de cada vez: entrar num novo desliga o anterior (rodando os passos
de saída dele). O modo ativo sobrevive a reiniciar o JARVIS.

Lote 1 (2.17): loja, gravação, roblox, programador, vó e reunião.
Lote 2 (2.18): mais 58 modos em plugins/_modos_extras.py (estudo, treino, debug, live…).
Lote 3 (2.19): mais 81 em plugins/_modos_lote3.py, com CATEGORIAS, e o sistema ficou mais esperto:
    "Jarvis, modo foco por 50 minutos"     sai sozinho quando o tempo acabar
    "Jarvis, que modo você sugere agora?"  pelo horário e pelo que você costuma usar
    "Jarvis, quais modos de loja?"         lista por categoria; "procura um modo de estudar"
    Nome aproximado também serve ("modo refatorar" → refatoração).
Lote 4 (3.6): os 10 modos "impossíveis" em plugins/_modos_lote4.py (OMEGA, bunker, cartório, bastidores, eu do futuro,
    cobaia, autópsia, tira-teima ("modo impossível"), só fatos, fortaleza) — "Jarvis, quais os modos impossíveis?"
    Eles só entram onde antes não havia resposta: nome que já ativava um modo continua ativando o mesmo.
Lote 5 (3.8): mineração, cripto e garagem em plugins/_modos_lote5.py — "Jarvis, modo mineração", "modo cripto", "modo garagem".
Para criar o seu: "Jarvis, cria o modo estudo que abre o Notion e põe volume 20".
Os modos antigos (modo jogo, modo carro, modo dormir, modo aula…) continuam
nos plugins deles, iguais.
"""

from __future__ import annotations

import difflib
import threading
import time
import unicodedata

from plugins._comum import CONFIG, gravar_json, ler_json, mostrar, registrar
from plugins._modos_extras import MODOS_EXTRAS
from plugins._modos_lote3 import CATEGORIAS as _CATEGORIAS3, MODOS_LOTE3
from plugins._modos_lote4 import APELIDOS4, CATEGORIA_LOTE4, MODOS_LOTE4     # 3.6: os 10 modos "impossíveis"
from plugins._modos_lote5 import APELIDOS5, CATEGORIA_LOTE5, MODOS_LOTE5     # 3.8: mineração, cripto e garagem

CATEGORIAS = {**_CATEGORIAS3, **CATEGORIA_LOTE4, **CATEGORIA_LOTE5}

PLUGIN = {
    "name": "modos",
    "brief": "Switch JARVIS modes (140+ in 10 categories, plus user-made): enter, leave, timed mode, suggest, search, list by category.",
    "description": (
        "Modes. action='entrar' with modo (loja | gravacao | roblox | programador | vo | reuniao | estudo | treino | debug | "
        "live | cozinha | festa | ingles | sherlock | … 140+, approximate names work | a user mode) turns it on, runs its steps and returns HOW YOU MUST BEHAVE while it is on — follow it. action='sair' turns the current "
        "mode off. action='listar'; action='atual'. action='criar' with modo, descricao and passos ('abrir X; fechar Y; "
        "volume 30; site https://…; mensagem texto') makes a custom mode; 'apagar' with modo deletes a custom one. "
        "2.19: 'por_tempo' with modo and minutos (leaves by itself); 'sugerir' (by time of day and habits); 'buscar' with modo = "
        "words; 'listar' with modo = a category (programacao, trabalho, loja, estudo, criacao, casa, saude, dia_a_dia, jogos, "
        "jeitos); 'historico' (most used)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "entrar | sair | listar | atual | criar | apagar | por_tempo | sugerir | "
                                                                      "buscar | historico"},
                       "modo": {"type": "STRING"}, "descricao": {"type": "STRING"}, "passos": {"type": "STRING"},
                       "minutos": {"type": "STRING"}},
        "required": ["action"],
    },
}

ARQ_ESTADO = CONFIG / "modo_ativo.json"
ARQ_MEUS = CONFIG / "modos_meus.json"


def _f(nome, params=None):
    return {"tipo": "ferramenta", "nome": nome, "params": params or {}}


MODOS: dict[str, dict] = {
    "loja": {
        "titulo": "Loja aberta", "emocao": "feliz",
        "jeito": "Fale como um vendedor simpático da Cristal Malhas. Priorize clientes no WhatsApp, estoque e vendas; "
                 "lembre de anotar cada venda. Frases curtas.",
        "entrar": [_f("whatsapp_conversas", {"action": "pessoal", "valor": "ligar"}),
                   _f("controle_mei", {"action": "status"})],
        "sair": [_f("relatorio_loja", {"action": "agora"})],
    },
    "gravacao": {
        "titulo": "Gravação de vídeo", "emocao": "animado",
        "jeito": "O senhor está gravando vídeo de produto. Não fale nada sem ser chamado; quando chamado, responda em "
                 "uma frase. Ajude com roteiro, gancho e legenda se pedir.",
        "entrar": [{"tipo": "mudo", "ligar": "sim"}, _f("whatsapp_conversas", {"action": "voz_alta", "valor": "desligar"})],
        "sair": [{"tipo": "mudo", "ligar": "nao"}],
    },
    "roblox": {
        "titulo": "Jogando Roblox", "emocao": "animado",
        "jeito": "Você é o parceiro de jogo do senhor: animado, rápido, falas de até 10 palavras durante a partida. "
                 "Comemore conquistas. Obedeça comandos de movimento com a ferramenta jogar_junto.",
        "entrar": [{"tipo": "modo_jogo", "ligar": True}, {"tipo": "abrir", "alvo": "roblox"},
                   _f("jogar_junto", {"action": "copiloto", "valor": "ligar", "jogo": "roblox"})],
        "sair": [_f("jogar_junto", {"action": "parar"}), {"tipo": "modo_jogo", "ligar": False}],
    },
    "programador": {
        "titulo": "Foco em programação", "emocao": "pensativo",
        "jeito": "Modo programação: respostas técnicas e diretas, com código quando ajudar. Não puxe assunto. Avise "
                 "erros que o vigia de código achar.",
        "entrar": [{"tipo": "fechar", "alvo": "discord, steam, roblox"}, {"tipo": "abrir", "alvo": "vs code"},
                   _f("vigia_codigo", {"action": "ligar"}), {"tipo": "plano_energia", "plano": "alto desempenho"}],
        "sair": [_f("vigia_codigo", {"action": "desligar"}), {"tipo": "plano_energia", "plano": "equilibrado"}],
    },
    "vo": {
        "titulo": "Conversando com a vó", "emocao": "feliz",
        "jeito": "Quem fala agora é a avó do senhor. Fale devagar, com carinho, frases curtas e palavras simples, sem "
                 "termos técnicos. Chame-a de 'senhora'. Lembre os cuidados do dia se ela perguntar.",
        "entrar": [{"tipo": "volume", "nivel": 85}, _f("cuidador", {"action": "checklist"})],
        "sair": [{"tipo": "volume", "nivel": 50}],
    },
    "reuniao": {
        "titulo": "Em reunião", "emocao": "serio",
        "jeito": "O senhor está numa reunião. Só fale se ele chamar, em uma frase e baixo. Avise se citarem o nome dele.",
        "entrar": [{"tipo": "fechar", "alvo": "spotify"}, _f("alerta_nome", {"action": "ligar"})],
        "sair": [_f("alerta_nome", {"action": "desligar"})],
    },
}


def todos() -> dict[str, dict]:
    meus = ler_json(ARQ_MEUS, {}) or {}
    return {**MODOS, **MODOS_EXTRAS, **MODOS_LOTE3, **MODOS_LOTE4, **MODOS_LOTE5, **meus}


def _ate_o_lote3() -> dict[str, dict]:
    """Os modos como eram até a 3.5 (lotes 1 a 3 + os seus)."""
    meus = ler_json(ARQ_MEUS, {}) or {}
    return {**MODOS, **MODOS_EXTRAS, **MODOS_LOTE3, **meus}


def chave(nome: str) -> str:
    t = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode().lower()
    t = t.replace("modo", "").strip().replace(" ", "_")
    return {"vovo": "vo", "avo": "vo", "programacao": "programador", "codigo": "programador", "gravar": "gravacao",
            "video": "gravacao", "jogo_roblox": "roblox", "call": "reuniao", "meet": "reuniao",
            # 2.18
            "estudar": "estudo", "concentracao": "foco_profundo", "foco": "foco_profundo", "silencio": "biblioteca",
            "academia": "treino", "malhar": "treino", "meditar": "meditacao", "relaxar": "relax", "dj": "festa",
            "bug": "debug", "depurar": "debug", "publicar": "deploy", "code_review": "revisao", "stream": "live",
            "editar": "edicao", "editar_video": "edicao", "producao": "beat", "rimar": "rap", "english": "ingles",
            "economizar": "economia", "bateria": "economia", "laboratorio": "laboratorio_stark", "stark": "laboratorio_stark",
            "hardware": "laboratorio_stark", "esp32": "laboratorio_stark", "ranqueada": "competitivo", "fps": "competitivo",
            "otaku": "anime", "kids": "crianca", "bomdia": "bom_dia", "manha": "bom_dia", "noite": "madrugada",
            "doente": "repouso", "faxina": "faxina_casa", "limpeza_casa": "faxina_casa", "futebol": "narrador_futebol",
            "rapido": "turbo", "curto": "turbo", "explicativo": "detalhado", "mordomo": "classico", "britanico": "classico",
            "detetive": "sherlock", "motivacao": "coach", "poesia": "poeta", "contagem_estoque": "inventario",
            "promocao": "black_friday", "trabalho_freela": "freela", "fechamento": "financas", "semana": "planejamento",
            "retrospectiva": "retro_semana", "festa_aniversario": "aniversario", "visita": "familia",
            "suporte": "suporte_parente", "sos": "emergencia", "socorro": "emergencia", "desconectar": "detox"}.get(t, t)


APELIDOS3 = {"refatorar": "refatoracao", "par": "pair_programming", "testes": "tdd", "docs": "documentacao", "sql": "banco_dados",
             "treinar_ia": "ia_treino", "treino_ia": "ia_treino", "comandos": "terminal", "emprego": "procurando_emprego",
             "vagas": "procurando_emprego", "trabalhando": "expediente", "aula_minha": "instrutor", "abrir_loja": "abertura_loja",
             "fechar_loja": "fechamento_loja", "mercadoria": "reposicao", "fotos": "fotos_produto", "mei": "papelada_mei",
             "vestibular": "enem", "simulado": "enem", "espanol": "espanhol", "revisar": "flashcards", "supermercado": "mercado",
             "reforma": "obra", "arrumar": "organizacao", "sexta": "sextou", "correr": "corrida", "alongar": "alongamento",
             "jogos_em_familia": "noite_de_jogos", "dever": "dever_de_casa", "historia_de_dormir": "historinha",
             "medico": "consulta", "triste": "dia_dificil", "apertado": "economizando", "aviao": "aeroporto", "sem_luz": "apagao",
             "cachorro": "pet", "plantas": "jardinagem", "conserto": "faca_voce_mesmo", "marmita": "marmitas",
             "roteiro": "roteirista", "batalha": "freestyle", "gravar_voz": "locutor", "natal": "natalino", "radio": "locutor_radio",
             "espacial": "controle_missao", "nasa": "controle_missao", "cowboy": "faroeste", "espiao": "agente_secreto",
             "8bits": "arcade_8bits", "informal": "descontraido", "rpg": "rpg_mesa", "free_fire": "battle_royale"}


def _sem_acento(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


def _achar_em(k: str, t: dict[str, dict]) -> str | None:
    """A busca de sempre (igual, único que contém, mais parecido, palavras) dentro dos modos dados."""
    if k in t or not k:
        return k if k in t else None
    solto = k.replace("_", " ")
    contem = [i for i, m in t.items() if k in i or solto in _sem_acento(m.get("titulo"))]
    if len(contem) == 1:
        return contem[0]
    perto = difflib.get_close_matches(k, list(t), n=1, cutoff=0.78)
    if perto:
        return perto[0]
    notas = _notas(solto, t)                    # "modo cozinhar bolo" → cozinha, se for o único que combina pelo nome
    if notas and notas[0][0] >= 3 and (len(notas) == 1 or notas[1][0] < notas[0][0]):
        return notas[0][1]
    return None


def achar(nome: str) -> str | None:
    """Id do modo a partir do nome falado: apelido, igual, único que contém, ou o mais parecido.
    3.6: primeiro a busca roda só nos modos que já existiam, exatamente como antes; os 10 modos do lote 4 só
    entram quando ela não acha nada. Assim um nome que já ativava um modo continua ativando o MESMO modo
    ("modo sem internet" segue sendo o apagão; "modo missão impossível" segue sendo o controle de missão)."""
    k = chave(nome)
    k = APELIDOS3.get(k, k)
    antes = _achar_em(k, _ate_o_lote3())
    if antes or not k:
        return antes
    return _achar_em(APELIDOS5.get(k, APELIDOS4.get(k, k)), todos())


VAZIAS = set("para pra com uma que dos das por meu minha quero modo modos fazer the".split())


def _notas(texto: str, t: dict[str, dict] | None = None) -> list[tuple[int, str]]:
    ws = [w[:5] if len(w) > 5 else w for w in _sem_acento(texto).split() if len(w) > 2 and w not in VAZIAS]
    notas = []
    for i, m in (todos() if t is None else t).items():
        nome, jeito = _sem_acento(i.replace("_", " ") + " " + m.get("titulo", "")), _sem_acento(m.get("jeito"))
        nota = sum(3 if w in nome else 1 for w in ws if w in nome or w in jeito)
        if nota:
            notas.append((nota, i))
    return sorted(notas, key=lambda x: -x[0])


def buscar(texto: str, n: int = 8) -> list[str]:
    """Modos que combinam com as palavras (nome vale mais que o jeito de falar). Pura."""
    return [i for _, i in _notas(texto)[:n]]


def _arq_hist():
    return ARQ_ESTADO.with_name("modos_historico.json")


def historico() -> list[dict]:
    h = ler_json(_arq_hist(), [])
    return h if isinstance(h, list) else []


PADRAO_HORA = [(0, 5, "madrugada"), (5, 8, "bom_dia"), (8, 12, "expediente"), (12, 14, "almoco"), (14, 18, "foco_profundo"),
               (18, 22, "relax"), (22, 24, "madrugada")]


def sugerir(agora: time.struct_time, hist: list[dict]) -> tuple[str, str]:
    """(modo, motivo): o que o usuário mais usa nesse horário; sem histórico, o que combina com a hora. Pura."""
    h, fds = agora.tm_hour, agora.tm_wday >= 5
    usados = [x["m"] for x in hist
              if abs(time.localtime(x["t"]).tm_hour - h) <= 1 and (time.localtime(x["t"]).tm_wday >= 5) == fds]
    if len(usados) >= 3:
        return max(set(usados), key=usados.count), "é o que o senhor mais usa nesse horário"
    if fds and 8 <= h < 18:
        return ("domingo" if agora.tm_wday == 6 else "relax"), "é fim de semana"
    return next(m for a, b, m in PADRAO_HORA if a <= h < b), "combina com o horário"


_temporizador: list = []


def _cancelar_tempo() -> None:
    while _temporizador:
        _temporizador.pop().cancel()


def ler_passos(texto: str) -> list[dict]:
    """'abrir notion; volume 20; fechar discord' → passos de protocolo (pura)."""
    passos = []
    for parte in str(texto or "").split(";"):
        p = parte.strip()
        if not p:
            continue
        verbo, _, resto = p.partition(" ")
        v = verbo.lower()
        if v in ("abrir", "abre"):
            passos.append({"tipo": "abrir", "alvo": resto})
        elif v in ("fechar", "fecha"):
            passos.append({"tipo": "fechar", "alvo": resto})
        elif v == "site":
            passos.append({"tipo": "site", "alvo": resto})
        elif v == "volume":
            passos.append({"tipo": "volume", "nivel": int("".join(c for c in resto if c.isdigit()) or 50)})
        elif v in ("mensagem", "fala", "diz"):
            passos.append({"tipo": "mensagem", "texto": resto})
        else:
            passos.append({"tipo": "comando", "texto": p})
    return passos


def _rodar(passos: list[dict], player) -> list[str]:
    from plugins import protocolos
    feitos = []
    for p in passos:
        try:
            r = protocolos.executar_passo(p, player, silencioso=True)
            if r:
                feitos.append(str(r)[:80])
        except Exception as e:
            feitos.append(f"falhou: {e}")
    return feitos


def atual() -> str:
    return str((ler_json(ARQ_ESTADO, {}) or {}).get("modo") or "")


def entrar(nome: str, player=None) -> str:
    k = achar(nome)
    m = todos().get(k)
    if not m:
        perto = buscar(nome, 5)
        return (f"Não tenho o modo '{nome}'. " + (f"Parecidos: {', '.join(perto)}." if perto else
                f"Tenho {len(todos())} modos; diga 'listar' ou procure por uma palavra."))
    anterior = atual()
    if anterior == k:
        return f"Já estou no modo {m['titulo']}. Jeito: {m.get('jeito', '')}"
    if anterior:
        sair(player)
    feitos = _rodar(m.get("entrar", []), player)
    gravar_json(ARQ_ESTADO, {"modo": k, "desde": time.time()})
    gravar_json(_arq_hist(), (historico() + [{"m": k, "t": time.time(), "dur": 0}])[-500:])
    try:
        from core import emocoes
        emocoes.definir(m.get("emocao", "feliz"), 4)
    except Exception:
        pass
    registrar(player, f"Modo {m['titulo']} ligado.")
    mostrar(player, f"MODO {m['titulo'].upper()}", "\n".join([m.get("jeito", "")] + [f"• {f}" for f in feitos]))
    return (f"[MODO {k.upper()}] Modo {m['titulo']} ligado. Enquanto ele estiver ligado: {m.get('jeito', '')} "
            f"Avise o usuário em uma frase curta.")


def sair(player=None) -> str:
    k = atual()
    if not k:
        return "Nenhum modo está ligado."
    m = todos().get(k, {})
    _cancelar_tempo()
    _rodar(m.get("sair", []), player)
    h = historico()
    if h and h[-1]["m"] == k:
        h[-1]["dur"] = int(time.time() - h[-1]["t"])
        gravar_json(_arq_hist(), h)
    gravar_json(ARQ_ESTADO, {})
    return f"Saí do modo {m.get('titulo', k)}. Volte ao seu jeito normal de falar."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    try:
        if a == "entrar":
            return entrar(str(p.get("modo") or ""), player)
        if a == "sair":
            return sair(player)
        if a == "atual":
            k = atual()
            return f"Estou no modo {todos()[k]['titulo']}." if k in todos() else "Nenhum modo especial ligado."
        if a == "criar":
            k = chave(p.get("modo"))
            if not k or k in MODOS or k in MODOS_EXTRAS or k in MODOS_LOTE3 or k in MODOS_LOTE4 or k in MODOS_LOTE5:
                return "Escolha outro nome (esse já é um modo pronto)." if k else "Qual o nome do modo?"
            meus = ler_json(ARQ_MEUS, {}) or {}
            meus[k] = {"titulo": str(p.get("modo")).strip().title(), "emocao": "feliz",
                       "jeito": str(p.get("descricao") or ""), "entrar": ler_passos(p.get("passos")), "sair": []}
            gravar_json(ARQ_MEUS, meus)
            return f"Modo {meus[k]['titulo']} criado com {len(meus[k]['entrar'])} passo(s). Diga 'modo {k}'."
        if a == "apagar":
            k = chave(p.get("modo"))
            meus = ler_json(ARQ_MEUS, {}) or {}
            if k not in meus:
                return "Só apago modos criados por você."
            meus.pop(k)
            gravar_json(ARQ_MEUS, meus)
            return f"Modo {k} apagado."
        if a == "por_tempo":
            mins = float("".join(c for c in str(p.get("minutos") or "25").replace(",", ".") if c.isdigit() or c == ".") or 25)
            r = entrar(str(p.get("modo") or ""), player)
            if not r.startswith("[MODO"):
                return r

            def acabou():
                sair(player)
                from plugins._comum import avisar
                avisar(player, f"O tempo do modo acabou ({mins:g} minutos). Voltei ao normal.", "MODO")
            t = threading.Timer(mins * 60, acabou)
            t.daemon = True
            t.start()
            _temporizador.append(t)
            return r + f" Ele desliga sozinho em {mins:g} minutos."
        if a == "sugerir":
            k, motivo = sugerir(time.localtime(), historico())
            m = todos().get(k) or {}
            return f"Sugiro o modo {m.get('titulo', k)} ({k}): {motivo}. Quer que eu ligue?"
        if a == "buscar":
            achados = buscar(str(p.get("modo") or p.get("descricao") or ""))
            return "Modos parecidos: " + ", ".join(f"{todos()[i]['titulo']} ({i})" for i in achados) + "." if achados else \
                "Não achei modo com essas palavras."
        if a == "historico":
            cont: dict = {}
            for x in historico():
                c = cont.setdefault(x["m"], [0, 0])
                c[0], c[1] = c[0] + 1, c[1] + x.get("dur", 0)
            top = sorted(cont.items(), key=lambda kv: -kv[1][0])[:6]
            return "Mais usados: " + "; ".join(f"{todos().get(i, {}).get('titulo', i)} {n}x ({d // 60} min)" for i, (n, d) in top) + "." \
                if top else "Ainda não usei nenhum modo."
        k, t = atual(), todos()
        cat = _sem_acento(p.get("modo")).replace("modos", "").replace(" de ", " ").strip().replace(" ", "_")
        if cat in CATEGORIAS or cat == "meus":
            ids = CATEGORIAS.get(cat) or [i for i in t if i not in MODOS and i not in MODOS_EXTRAS and i not in MODOS_LOTE3
                                          and i not in MODOS_LOTE4 and i not in MODOS_LOTE5]
            return f"Modos de {cat.replace('_', ' ')}: " + ", ".join(f"{t[i]['titulo']} ({i})" for i in ids if i in t) + "."
        mostrar(player, "MODOS", "\n".join(f"{c.replace('_', ' ').upper()}: " + ", ".join(t[i]["titulo"] for i in ids if i in t)
                                           for c, ids in CATEGORIAS.items()))
        ligado = f" Ligado agora: {t[k]['titulo']}." if k in t else ""
        return (f"Modos: {len(t)} em {len(CATEGORIAS)} categorias — " + ", ".join(f"{c.replace('_', ' ')} ({len(ids)})" for c, ids in CATEGORIAS.items()) +
                f". Diga 'modos de loja' para ver uma categoria, ou 'modo' e o nome.{ligado} Exemplos: " +
                ", ".join(f"{m['titulo']} ({n})" for n, m in list(t.items())[:8]) + ".")
    except Exception as e:
        return f"Os modos falharam: {e}"
