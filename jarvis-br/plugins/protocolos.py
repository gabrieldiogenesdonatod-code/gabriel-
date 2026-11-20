"""
Protocolos nomeados — plugin do J.A.R.V.I.S BR (versão 1.2: passos em ordem).

Uma frase dispara uma sequência de passos, EXECUTADOS NA ORDEM em que estão:

    "Jarvis, protocolo foco"  → fecha jogos e Discord, plano de energia
                                equilibrado, abre o VS Code, espera, abre uma
                                playlist para programar.
    "Jarvis, protocolo casa"  → fecha o VS Code e abre o Spotify.
    "Jarvis, protocolo loja"  → abre WhatsApp, CapCut e o Instagram.

TIPOS DE PASSO (config/protocolos.json, campo "passos")
    abrir          alvo: apps separados por vírgula (aceita apelidos e nomes
                   aproximados: "zap", "vs code", "lol")
    fechar         alvo: apps separados por vírgula
    site           alvo: endereços separados por vírgula
    esperar        segundos
    volume         nivel (0–100, "mais", "menos")
    mudo           ligar (sim/nao)
    plano_energia  plano ("economia", "equilibrado", "alto desempenho")
    modo_jogo      ligar (sim/nao)
    modo_escuro    ligar (sim/nao)
    macro          nome, velocidade
    pomodoro       foco (minutos)
    minimizar_tudo
    bloquear
    mensagem       texto (o JARVIS fala)
    comando        texto (um pedido para o JARVIS fazer, como se você falasse)
    persona        nome (troca JARVIS ↔ FRIDAY: nome, voz e estilo)       [1.4]
    casa           texto ("desligar luz do quarto", "cena dormir")          [1.4]
    energia        operacao (desligar|reiniciar|suspender|hibernar; com
                   confirmação na tela)                                     [1.4]
    ferramenta     nome + params (qualquer ferramenta do JARVIS, em JSON)   [1.4]

Protocolos do formato antigo (abrir/fechar/sites soltos) continuam valendo:
são convertidos para passos na ordem antiga (fechar → abrir → sites).

Progresso: protocolos curtos respondem de uma vez; os que têm esperas,
macros ou mais de 4 passos rodam em segundo plano, com o progresso no registro
e um resumo falado no fim.

Segurança: fechar respeita a lista de proteção compartilhada
(plugins/_protecao.py) — o JARVIS, o Python e os processos do sistema nunca
são fechados, mesmo que estejam no JSON.
"""

from __future__ import annotations

import json
import threading
import time
import webbrowser

from plugins._comum import CONFIG, falar, gravar_json, ler_json, mostrar, num, registrar, sim
from plugins._protecao import filtrar_nomes, nome_base, proteger_processo

PLUGIN = {
    "name": "protocolos",
    "brief": "Run, list, view, create, extend or delete named routines ('protocolo X').",
    "description": (
        "Named routines ('protocols') that run ordered steps from one phrase. "
        "action='executar' with nome when the user says 'protocolo X', 'ativa o protocolo X' "
        "or 'modo X' (e.g. foco, casa, loja). action='listar'; 'ver' (nome) shows the steps; "
        "'criar' (nome plus any of abrir, fechar, sites, volume, plano, mensagem — lists comma "
        "separated) makes or replaces one; 'adicionar_passo' (nome, tipo, valor) appends a step: "
        "tipo = abrir | fechar | site | esperar | volume | mudo | plano_energia | modo_jogo | "
        "modo_escuro | macro | pomodoro | minimizar_tudo | bloquear | mensagem | comando; "
        "'apagar' (nome). Do NOT call open_app or other tools for a protocol's steps."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "executar | listar | ver | criar | adicionar_passo | apagar"},
            "nome": {"type": "STRING", "description": "Protocol name, e.g. 'foco'"},
            "abrir": {"type": "STRING", "description": "criar: apps to open, comma separated"},
            "fechar": {"type": "STRING", "description": "criar: apps to close, comma separated"},
            "sites": {"type": "STRING", "description": "criar: URLs, comma separated"},
            "volume": {"type": "STRING", "description": "criar: volume level"},
            "plano": {"type": "STRING", "description": "criar: power plan"},
            "mensagem": {"type": "STRING", "description": "criar: sentence said when it runs"},
            "tipo": {"type": "STRING", "description": "adicionar_passo: step type"},
            "valor": {"type": "STRING", "description": "adicionar_passo: the step's value"},
        },
        "required": ["action"],
    },
}

ARQUIVO = CONFIG / "protocolos.json"

_PADRAO = {
    "foco": {
        "mensagem": "Protocolo Foco ativado. Distrações fechadas, ambiente pronto.",
        "passos": [
            {"tipo": "fechar", "alvo": "steam, epicgameslauncher, discord, riotclientservices, "
                                       "leagueclient, valorant"},
            {"tipo": "abrir", "alvo": "Visual Studio Code"},
            {"tipo": "esperar", "segundos": 2},
            {"tipo": "site", "alvo": "https://music.youtube.com/search?q=lofi+para+programar"},
        ],
    },
    "casa": {
        "mensagem": "Protocolo Casa ativado. Hora de descansar, senhor.",
        "passos": [
            {"tipo": "fechar", "alvo": "code"},
            {"tipo": "abrir", "alvo": "Spotify"},
        ],
    },
    "loja": {
        "mensagem": "Protocolo Loja ativado. Tudo pronto para a Cristal Malhas.",
        "passos": [
            {"tipo": "abrir", "alvo": "WhatsApp, CapCut"},
            {"tipo": "site", "alvo": "https://www.instagram.com/"},
        ],
    },
}

TIPOS = ("abrir", "fechar", "site", "esperar", "volume", "mudo", "plano_energia", "modo_jogo",
         "modo_escuro", "macro", "pomodoro", "minimizar_tudo", "bloquear", "mensagem", "comando",
         "persona", "casa", "energia", "ferramenta")          # os 4 últimos: fork PT-BR 1.4
_EM_SEGUNDO_PLANO = ("esperar", "macro", "pomodoro", "modo_jogo")


# ── armazenamento e migração ───────────────────────────────────────────────────
def _split(texto) -> list[str]:
    if isinstance(texto, list):
        return [str(t).strip() for t in texto if str(t).strip()]
    return [t.strip() for t in str(texto or "").split(",") if t.strip()]


def migrar(proto: dict) -> dict:
    """Formato antigo (abrir/fechar/sites) → passos, na ordem antiga."""
    if isinstance(proto.get("passos"), list):
        return proto
    passos = []
    if _split(proto.get("fechar")):
        passos.append({"tipo": "fechar", "alvo": ", ".join(_split(proto["fechar"]))})
    if _split(proto.get("abrir")):
        passos.append({"tipo": "abrir", "alvo": ", ".join(_split(proto["abrir"]))})
    if _split(proto.get("sites")):
        passos.append({"tipo": "site", "alvo": ", ".join(_split(proto["sites"]))})
    return {"mensagem": proto.get("mensagem", ""), "passos": passos}


def _load() -> dict:
    dados = ler_json(ARQUIVO, None)
    if not isinstance(dados, dict):
        dados = {k: dict(v) for k, v in _PADRAO.items()}
        _save(dados)
        return dados
    migrados = {k: migrar(v) for k, v in dados.items() if isinstance(v, dict)}
    if migrados != dados:
        _save(migrados)
    return migrados


def _save(dados: dict) -> None:
    gravar_json(ARQUIVO, dados)


def _norm(nome: str) -> str:
    n = (nome or "").strip().lower()
    for prefixo in ("protocolo ", "protocol ", "modo "):
        if n.startswith(prefixo):
            n = n[len(prefixo):]
    return n.strip()


def descrever_passo(p: dict) -> str:
    t = p.get("tipo", "?")
    alvo = p.get("alvo") or p.get("texto") or p.get("nome") or ""
    extra = {"esperar": f"{p.get('segundos', 0)} s", "volume": f"{p.get('nivel', '')}%",
             "plano_energia": p.get("plano", ""), "pomodoro": f"{p.get('foco', 25)} min",
             "modo_jogo": "ligar" if sim(p.get("ligar", True)) else "desligar",
             "modo_escuro": "ligar" if sim(p.get("ligar", True)) else "desligar",
             "mudo": "ligar" if sim(p.get("ligar", True)) else "desligar",
             "energia": p.get("operacao", "desligar")}.get(t, alvo)
    return f"{t} {extra}".strip()


# ── execução de cada passo ─────────────────────────────────────────────────────
def _fechar(nomes: list[str]) -> str:
    import psutil

    from plugins._indice_apps import resolver_apelido
    permitidos, bloqueados = filtrar_nomes([resolver_apelido(n) for n in nomes])
    alvos = {nome_base(n).replace(" ", "") for n in permitidos} | {nome_base(n) for n in permitidos}
    # "Visual Studio Code" é o Code.exe: o appidentity casa nome e título da
    # janela, então pedidos com o nome "bonito" também acham o processo.
    try:
        from core import appidentity
        for n in permitidos:
            for m in appidentity.running(n)[:10]:
                if m.score >= 60:
                    alvos.add(nome_base(m.name))
    except Exception:
        pass
    fechados, procs = set(), []
    for p in psutil.process_iter(["name"]):
        n = nome_base(p.info.get("name") or "")
        if n in alvos and not proteger_processo(p):
            procs.append(p)
            fechados.add(p.info.get("name") or n)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    psutil.wait_procs(procs, timeout=3)
    partes = []
    if fechados:
        partes.append("fechei " + ", ".join(sorted(f.rsplit(".", 1)[0] for f in fechados)))
    if bloqueados:
        partes.append("não fecho " + ", ".join(bloqueados) + " (sistema)")
    return "; ".join(partes)


def _abrir(nomes: list[str], player) -> str:
    from actions.open_app import open_app
    abertos = []
    for n in nomes:
        try:
            open_app({"app_name": n}, player=player)
            abertos.append(n)
            time.sleep(0.6)
        except Exception as e:
            registrar(player, f"Protocolo: não abri {n} ({e})")
    return ("abrindo " + ", ".join(abertos)) if abertos else ""


def executar_passo(p: dict, player, silencioso: bool = False) -> str:
    t = str(p.get("tipo") or "").lower()
    if t == "abrir":
        return _abrir(_split(p.get("alvo")), player)
    if t == "fechar":
        return _fechar(_split(p.get("alvo")))
    if t == "site":
        urls = [u for u in _split(p.get("alvo")) if u.lower().startswith(("http://", "https://"))]
        for u in urls:
            webbrowser.open(u, new=2)
        return f"{len(urls)} página(s) abertas" if urls else ""
    if t == "esperar":
        time.sleep(max(0.0, min(300.0, num(p.get("segundos"), 1))))
        return ""
    if t == "volume":
        from plugins.controle_audio_video import _volume
        return _volume(p.get("nivel", 50))
    if t == "mudo":
        from plugins.controle_audio_video import _mudo
        return _mudo(p.get("ligar", "sim"))
    if t == "plano_energia":
        from plugins.controle_sistema import _plano
        return _plano(str(p.get("plano") or "equilibrado"))
    if t == "modo_jogo":
        from plugins import modo_jogo
        return modo_jogo.ligar(player) if sim(p.get("ligar", True)) else modo_jogo.desligar(player)
    if t == "modo_escuro":
        from plugins.controle_audio_video import _modo_escuro
        return _modo_escuro(p.get("ligar", "sim"))
    if t == "macro":
        from plugins.macros import rodar
        return rodar(str(p.get("nome") or p.get("alvo") or ""), p.get("velocidade"), p.get("repeticoes"), player)
    if t == "pomodoro":
        if silencioso:                      # o próprio pomodoro chamou o protocolo
            return ""
        from plugins.pomodoro import iniciar
        return iniciar(player, p.get("foco"), p.get("pausa"))
    if t == "minimizar_tudo":
        from plugins._janelas import minimizar_tudo
        return minimizar_tudo() or "janelas minimizadas"
    if t == "bloquear":
        from plugins.controle_pc import bloquear_tela
        return bloquear_tela()
    if t == "mensagem":
        texto = str(p.get("texto") or p.get("alvo") or "")
        if texto:
            falar(player, f"[PROTOCOLO] Diga ao usuário, em uma frase: {texto}")
        return ""
    if t == "comando":
        texto = str(p.get("texto") or p.get("alvo") or "")
        if texto:
            falar(player, f"[PROTOCOLO] Faça agora este pedido do usuário, usando as ferramentas "
                          f"necessárias: \"{texto}\"")
        return ""
    # ── fork PT-BR 1.4 ──
    if t == "persona":
        from plugins.personas import trocar
        return trocar(str(p.get("nome") or p.get("alvo") or ""), atraso=8.0).split(".")[0]
    if t == "casa":
        from plugins import casa_inteligente as casa
        texto = str(p.get("texto") or p.get("alvo") or "").strip()
        if texto.lower().startswith("cena "):
            return casa.rodar_cena(texto[5:])
        passo = casa.passo_de_texto(texto)
        return casa.executar(passo[1], passo[0], passo[2]) if passo else f"falhou: não entendi '{texto}'"
    if t == "energia":
        from plugins.controle_pc import _energia
        return _energia(str(p.get("operacao") or p.get("alvo") or "desligar").lower())
    if t == "ferramenta":
        from core import registro_ferramentas
        params = p.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        return registro_ferramentas.executar(str(p.get("nome") or p.get("alvo") or ""), params, player)
    return f"passo desconhecido '{t}'"


_PARALELIZAVEIS = ("abrir", "site", "fechar")


def _grupos(passos: list[dict], paralelo: bool) -> list[list[dict]]:
    """Com 'paralelo' ligado (sugestão da memória contrafactual), passos
    seguidos de abrir/site/fechar viram um grupo que roda ao mesmo tempo.
    Os outros passos continuam um de cada vez, na ordem."""
    grupos: list[list[dict]] = []
    for passo in passos:
        if paralelo and grupos and passo.get("tipo") in _PARALELIZAVEIS \
                and all(x.get("tipo") in _PARALELIZAVEIS for x in grupos[-1]):
            grupos[-1].append(passo)
        else:
            grupos.append([passo])
    return grupos


def _um_passo(passo, player, silencioso) -> dict:
    t0 = time.perf_counter()
    try:
        r = executar_passo(passo, player, silencioso)
        ok = not str(r).lower().startswith(("falhou", "passo desconhecido"))
    except Exception as e:
        r, ok = f"falhou ({e})", False
    return {"descricao": descrever_passo(passo), "tipo": passo.get("tipo"),
            "ms": round((time.perf_counter() - t0) * 1000), "ok": ok, "resultado": str(r or "")[:160]}


def _rodar(chave: str, proto: dict, player, silencioso: bool) -> list[str]:
    passos = proto.get("passos", [])
    paralelo = bool(proto.get("paralelo"))
    registros, feitos, n = [], [], 0
    t0 = time.perf_counter()
    for grupo in _grupos(passos, paralelo):
        if len(grupo) == 1:
            n += 1
            registrar(player, f"Protocolo {chave}: passo {n}/{len(passos)} — {descrever_passo(grupo[0])}")
            resultados = [_um_passo(grupo[0], player, silencioso)]
        else:
            registrar(player, f"Protocolo {chave}: passos {n + 1}–{n + len(grupo)} juntos — "
                              + ", ".join(descrever_passo(x) for x in grupo))
            n += len(grupo)
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=len(grupo)) as ex:
                resultados = list(ex.map(lambda x: _um_passo(x, player, silencioso), grupo))
        for r in resultados:
            registros.append(r)
            if r["resultado"]:
                feitos.append(r["resultado"])
    total = (time.perf_counter() - t0) * 1000
    # Fork PT-BR 1.4: duração de cada passo vai para o diário; a memória
    # contrafactual lê daqui e sugere melhorias (ex.: abrir em paralelo).
    try:
        from core import registro_uso
        registro_uso.registrar_tarefa("protocolo", chave, registros, total, all(r["ok"] for r in registros))
    except Exception:
        pass
    registrar(player, f"Protocolo {chave} concluído em {total / 1000:.1f} s.")
    return feitos


def _executar(nome: str, player, silencioso: bool = False) -> str:
    dados = _load()
    chave = _norm(nome)
    proto = dados.get(chave)
    if not proto:
        from plugins._indice_apps import pontuar
        parecido = max(dados, key=lambda k: pontuar(chave, k), default=None)
        if parecido and pontuar(chave, parecido) >= 65:
            chave, proto = parecido, dados[parecido]
        else:
            return f"Não existe o protocolo '{nome}'. Disponíveis: {', '.join(sorted(dados)) or 'nenhum'}."
    passos = proto.get("passos", [])
    mensagem = proto.get("mensagem") or f"Protocolo {chave} ativado."
    longo = len(passos) > 4 or any(p.get("tipo") in _EM_SEGUNDO_PLANO for p in passos)
    if longo and not silencioso:
        def em_fundo():
            feitos = _rodar(chave, proto, player, silencioso)
            falar(player, f"[PROTOCOLO] O protocolo {chave} terminou. Resuma em UMA frase: "
                          + ("; ".join(feitos) if feitos else "tudo pronto") + ". Não chame ferramentas.")
        threading.Thread(target=em_fundo, daemon=True, name=f"protocolo-{chave}").start()
        return f"{mensagem} Executando {len(passos)} passos; aviso quando terminar."
    feitos = _rodar(chave, proto, player, silencioso)
    return mensagem + (" " + "; ".join(feitos).capitalize() + "." if feitos else "")


# ── criar e editar ─────────────────────────────────────────────────────────────
def _criar(p: dict) -> str:
    chave = _norm(p.get("nome", ""))
    if not chave:
        return "Preciso de um nome para o protocolo."
    passos = []
    fechar_ok, bloqueados = filtrar_nomes(_split(p.get("fechar")))
    if fechar_ok:
        passos.append({"tipo": "fechar", "alvo": ", ".join(fechar_ok)})
    if p.get("plano"):
        passos.append({"tipo": "plano_energia", "plano": str(p["plano"])})
    if _split(p.get("abrir")):
        passos.append({"tipo": "abrir", "alvo": ", ".join(_split(p.get("abrir")))})
    sites = [u for u in _split(p.get("sites")) if u.lower().startswith(("http://", "https://"))]
    if sites:
        passos.append({"tipo": "site", "alvo": ", ".join(sites)})
    if p.get("volume") not in (None, ""):
        passos.append({"tipo": "volume", "nivel": str(p["volume"])})
    if not passos:
        return "O protocolo precisa de pelo menos um passo (abrir, fechar, sites, volume ou plano)."
    dados = _load()
    novo = chave not in dados
    dados[chave] = {"mensagem": (p.get("mensagem") or f"Protocolo {chave} ativado.").strip(), "passos": passos}
    _save(dados)
    aviso = ""
    if bloqueados:
        verbo = "é um programa" if len(bloqueados) == 1 else "são programas"
        aviso = f" Ignorei {', '.join(bloqueados)}, que {verbo} do sistema."
    return f"Protocolo {chave} {'criado' if novo else 'atualizado'} com {len(passos)} passo(s).{aviso}"


def passo_de(tipo: str, valor: str) -> dict | None:
    t = str(tipo or "").strip().lower().replace(" ", "_")
    if t not in TIPOS:
        return None
    v = str(valor or "").strip()
    if t in ("abrir", "fechar", "site"):
        if t == "fechar":
            ok, bloqueados = filtrar_nomes(_split(v))
            if bloqueados and not ok:
                return {"erro": f"{', '.join(bloqueados)} são do sistema e nunca são fechados."}
            v = ", ".join(ok)
        return {"tipo": t, "alvo": v} if v else None
    if t == "esperar":
        return {"tipo": t, "segundos": max(1, min(300, int(num(v, 3))))}
    if t == "volume":
        return {"tipo": t, "nivel": v or "50"}
    if t in ("mudo", "modo_jogo", "modo_escuro"):
        return {"tipo": t, "ligar": "nao" if v.lower() in ("nao", "não", "desligar", "off") else "sim"}
    if t == "plano_energia":
        return {"tipo": t, "plano": v or "equilibrado"}
    if t == "macro":
        return {"tipo": t, "nome": v} if v else None
    if t == "pomodoro":
        return {"tipo": t, "foco": int(num(v, 25)) or 25}
    if t in ("mensagem", "comando", "casa"):
        return {"tipo": t, "texto": v} if v else None
    if t == "persona":
        return {"tipo": t, "nome": v} if v else None
    if t == "energia":
        op = v.lower() or "desligar"
        return {"tipo": t, "operacao": op} if op in ("desligar", "reiniciar", "suspender", "hibernar") else None
    if t == "ferramenta":
        nome, _sep, resto = v.partition(" ")
        return {"tipo": t, "nome": nome, "params": resto.strip() or "{}"} if nome else None
    return {"tipo": t}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action", "")).strip().lower()
    try:
        if a in ("executar", "rodar", "ativar"):
            return _executar(p.get("nome", ""), player)
        if a == "listar":
            dados = _load()
            if not dados:
                return "Nenhum protocolo criado."
            return "Protocolos: " + " | ".join(
                f"{k}: " + ", ".join(descrever_passo(x) for x in v.get("passos", [])[:4])
                + ("…" if len(v.get("passos", [])) > 4 else "") for k, v in sorted(dados.items()))
        if a == "ver":
            chave = _norm(p.get("nome", ""))
            proto = _load().get(chave)
            if not proto:
                return f"Não existe o protocolo '{chave}'."
            mostrar(player, f"PROTOCOLO {chave.upper()}", "\n".join(
                f"{i}. {descrever_passo(x)}" for i, x in enumerate(proto.get("passos", []), 1))
                + f"\n\nMensagem: {proto.get('mensagem', '')}")
            return f"O protocolo {chave} tem {len(proto.get('passos', []))} passos; estão no painel."
        if a == "criar":
            return _criar(p)
        if a == "adicionar_passo":
            chave = _norm(p.get("nome", ""))
            dados = _load()
            if chave not in dados:
                return f"Não existe o protocolo '{chave}'. Crie primeiro."
            passo = passo_de(p.get("tipo"), p.get("valor"))
            if passo and passo.get("erro"):
                return passo["erro"]
            if not passo:
                return ("Passo inválido (tipo desconhecido ou sem valor). Tipos: "
                        + ", ".join(TIPOS) + ".")
            dados[chave].setdefault("passos", []).append(passo)
            _save(dados)
            return f"Adicionei '{descrever_passo(passo)}' ao protocolo {chave}."
        if a == "apagar":
            chave = _norm(p.get("nome", ""))
            dados = _load()
            if chave not in dados:
                return f"Não existe o protocolo '{chave}'."
            del dados[chave]
            _save(dados)
            return f"Protocolo {chave} apagado."
        return "Ação desconhecida. Use executar, listar, ver, criar, adicionar_passo ou apagar."
    except Exception as e:
        return f"O protocolo falhou: {e}"
