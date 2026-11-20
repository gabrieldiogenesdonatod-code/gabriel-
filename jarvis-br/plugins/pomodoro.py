"""
Foco / Pomodoro — plugin do J.A.R.V.I.S BR.

    "Jarvis, começa um pomodoro"            → 25 min de foco, 5 de pausa
    "Jarvis, pomodoro de 50 minutos"        → foco de 50
    "Jarvis, quanto falta?" / "pausa o pomodoro" / "para o pomodoro"
    "Jarvis, quantos pomodoros eu fiz hoje?"

Durante o FOCO
    * apps da lista de distração são fechados se abrirem (do jeito educado, e
      respeitando a lista de proteção);
    * se a janela da frente for um navegador num site da lista (YouTube,
      Instagram, TikTok…), ela é minimizada e o JARVIS lembra que é hora de
      foco. Opcionalmente fecha a aba (Ctrl+W). Sem mexer no arquivo hosts, então
      não precisa de administrador;
    * pode rodar o protocolo Foco no começo (fecha jogos, abre o VS Code etc.).
Na PAUSA tudo é liberado. A cada 4 focos, a pausa é longa (15 min).

Fork PT-BR 2.5
    * "celular na mão": com a webcam ligada para isso (⚙ → Foco), ele percebe o
      celular na sua mão durante o foco (visão no próprio PC, MediaPipe) e
      fala "Senhor, o celular pode esperar mais 12 minutos.";
    * negociação: "Jarvis, me dá 5 minutos de YouTube?" → "Libero 5 se você
      terminar essa função primeiro." Terminou? Ele libera e avisa quando
      acabar. Quer agora? Fica devendo: ele cobra os minutos no fim do foco.
"""

from __future__ import annotations

import threading
import time
from datetime import date

from plugins import _negociacao as _neg                       # Fork PT-BR 2.5
from plugins._comum import (MEMORIA, avisar, cfg, gravar_json, ler_json, num,
                            registrar, sim)

PLUGIN = {
    "name": "pomodoro",
    "brief": "Pomodoro focus timer blocking distracting apps/sites: start, pause, resume, stop, status, today.",
    "description": (
        "Focus timer (Pomodoro) that blocks distracting apps and sites during focus. "
        "action='iniciar' (foco = minutes, default 25; pausa = minutes), 'pausar', 'retomar', "
        "'parar', 'status' ('quanto falta'), 'hoje' (how many pomodoros today). "
        "Negotiation when the user asks for a break from focus ('me dá 5 minutos de YouTube?'): "
        "action='negociar' with o_que and minutos — say JARVIS's answer; 'cumpri' when the user did the deal; "
        "'fiado' when the user wants it NOW (released now, extra focus minutes later). "
        "'vigiar' with valor ligar/desligar: webcam notices the phone in hand during focus."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "iniciar | pausar | retomar | parar | status | hoje | "
                                                        "negociar | cumpri | fiado | vigiar"},
            "foco": {"type": "NUMBER"}, "pausa": {"type": "NUMBER"},
            "o_que": {"type": "STRING"}, "minutos": {"type": "NUMBER"}, "valor": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "pomodoro",
    "title": "Foco / Pomodoro",
    "fields": [
        {"key": "foco", "label": "Minutos de foco", "type": "text", "default": "25"},
        {"key": "pausa", "label": "Minutos de pausa", "type": "text", "default": "5"},
        {"key": "pausa_longa", "label": "Minutos da pausa longa", "type": "text", "default": "15"},
        {"key": "ciclos", "label": "Focos até a pausa longa", "type": "text", "default": "4"},
        {"key": "apps", "label": "Apps bloqueados no foco", "type": "text",
         "default": "steam, epicgameslauncher, riotclientservices, leagueclient, valorant, discord"},
        {"key": "sites", "label": "Sites bloqueados (palavras do título)", "type": "text",
         "default": "YouTube, Instagram, TikTok, Facebook, Netflix, Twitch, Twitter, / X"},
        {"key": "fechar_aba", "label": "Fechar a aba do site (Ctrl+W) em vez de só minimizar",
         "type": "toggle", "default": False},
        {"key": "protocolo_foco", "label": "Rodar o protocolo Foco ao começar", "type": "toggle", "default": True},
        # Fork PT-BR 2.5
        {"key": "celular", "label": "Avisar se eu pegar o celular no foco (webcam; a imagem não sai do PC)",
         "type": "toggle", "default": False},
    ],
}

NAVEGADORES = ("chrome", "msedge", "firefox", "opera", "brave", "vivaldi", "safari", "chromium")
ARQUIVO = MEMORIA / "pomodoro.json"

_estado: dict = {"fase": None}
_lock = threading.Lock()
_parar = threading.Event()


def _cfg() -> dict:
    return cfg("pomodoro", PLUGIN_SETTINGS)


def lista(texto) -> list[str]:
    return [x.strip() for x in str(texto or "").split(",") if x.strip()]


def site_bloqueado(titulo: str, termos: list[str]) -> str | None:
    t = (titulo or "").lower()
    for termo in termos:
        if termo.strip().lower() and termo.strip().lower() in t:
            return termo.strip().lstrip("/ ").strip() or termo
    return None


def _registrar_foco(minutos: float) -> None:
    dados = ler_json(ARQUIVO, {}) or {}
    hoje = dados.setdefault(date.today().isoformat(), {"pomodoros": 0, "minutos": 0})
    hoje["pomodoros"] += 1
    hoje["minutos"] += int(minutos)
    gravar_json(ARQUIVO, dados)


# ── bloqueios ──────────────────────────────────────────────────────────────────
def _bloquear(player, c: dict, avisados: dict):
    import psutil

    from plugins._protecao import nome_base, proteger_processo
    apps = {nome_base(a) for a in lista(c.get("apps"))}
    lib = _estado.get("liberado")                              # Fork PT-BR 2.5: minutos negociados
    for p in psutil.process_iter(["name"]):
        n = nome_base(p.info.get("name") or "")
        if n in apps and not _neg.liberado(lib, n, time.time()) and not proteger_processo(p):
            try:
                p.terminate()
            except Exception:
                continue
            if time.time() - avisados.get(n, 0) > 300:
                avisados[n] = time.time()
                avisar(player, f"{p.info.get('name')} está bloqueado durante o foco; fica para a pausa.",
                       "POMODORO")
    try:
        from plugins import _janelas
        j = _janelas.ativa()
    except Exception:
        j = None
    if not j or nome_base(j.get("processo", "")) not in NAVEGADORES:
        return
    site = site_bloqueado(j.get("titulo", ""), lista(c.get("sites")))
    if not site or _neg.liberado(lib, site, time.time()):
        return
    if sim(c.get("fechar_aba")):
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "w")
        except Exception:
            _janelas.estado(j, "minimizar")
    else:
        _janelas.estado(j, "minimizar")
    if time.time() - avisados.get("site:" + site, 0) > 120:
        avisados["site:" + site] = time.time()
        avisar(player, f"Hora de foco: {site} fica para a pausa.", "POMODORO")


# ── o relógio ──────────────────────────────────────────────────────────────────
def _laco(player):
    avisados: dict = {}
    while not _parar.wait(5):
        with _lock:
            e = dict(_estado)
        if not e.get("fase") or e.get("pausado"):
            continue
        c = _cfg()
        restante = e["fim"] - time.time()
        if e["fase"] == "foco":
            _acordos_no_tempo(player)                          # Fork PT-BR 2.5
            try:
                _bloquear(player, c, avisados)
            except Exception as ex:
                print(f"[Pomodoro] bloqueio: {ex}")
            if sim(c.get("celular")):
                _vigiar_celular(player, restante, avisados)
        if restante > 0:
            continue
        with _lock:
            if _estado["fase"] == "foco" and _estado.get("divida_s", 0) > 0:      # Fork PT-BR 2.5: cobra o fiado
                divida = _estado.pop("divida_s")
                _estado["fim"] = time.time() + divida
                msg = (f"Antes da pausa, a dívida: mais {_neg.minutos_txt(divida / 60)} de foco pelos minutos "
                       f"que eu liberei. Depois é pausa.")
            else:
                msg = ""
        if msg:
            avisar(player, msg, "POMODORO")
            continue
        with _lock:
            if _estado["fase"] == "foco":
                _registrar_foco(_estado["duracao_foco"] / 60)
                _estado["ciclo"] += 1
                longa = _estado["ciclo"] % max(1, int(num(c.get("ciclos"), 4))) == 0
                minutos = num(c.get("pausa_longa"), 15) if longa else _estado["duracao_pausa"] / 60
                _estado.update({"fase": "pausa", "fim": time.time() + minutos * 60, "acordos": 0,
                                "acordo": None, "liberado": None})
                msg = (f"Foco {_estado['ciclo']} concluído! Pausa {'longa ' if longa else ''}de "
                       f"{int(minutos)} minutos: levanta, bebe uma água.")
            else:
                _estado.update({"fase": "foco", "fim": time.time() + _estado["duracao_foco"]})
                msg = f"Fim da pausa. Foco {_estado['ciclo'] + 1} começando: {int(_estado['duracao_foco'] / 60)} minutos."
        avisar(player, msg, "POMODORO")


# ── Fork PT-BR 2.5: negociação e celular na mão ───────────────────────────────
def _acordos_no_tempo(player) -> None:
    agora = time.time()
    fala = ""
    with _lock:
        lib, ac = _estado.get("liberado"), _estado.get("acordo")
        if lib and agora >= lib["ate"]:
            _estado["liberado"] = None
            fala = (f"Acabaram os {lib['minutos']} minutos de {lib['termo']}. Combinado é combinado: "
                    f"de volta ao foco!")
        elif ac and ac.get("condicao") == "tempo" and agora >= ac.get("libera_em", agora + 1):
            _texto, lib = _neg.cumprir(ac, agora)
            _estado.update(acordo=None, liberado=lib, acordos=_estado.get("acordos", 0) + 1)
            fala = f"Combinado cumprido: {lib['minutos']} minutos de {lib['termo']} liberados agora."
    if fala:
        avisar(player, fala, "POMODORO")


def _vigiar_celular(player, restante: float, avisados: dict) -> None:
    agora = time.time()
    if agora - avisados.get("cel_check", 0) < 15 or _estado.get("liberado"):
        return
    avisados["cel_check"] = agora
    try:
        from plugins import _visao_local
        from plugins._camera_remota import quadro
        img, _erro = quadro(0, espera_s=3)
        na_mao = _visao_local.celular_na_mao(img) if img is not None else None
    except Exception as ex:
        print(f"[Pomodoro] celular: {ex}")
        na_mao = None
    avisados["cel_seguidos"] = avisados.get("cel_seguidos", 0) + 1 if na_mao else 0
    if avisados["cel_seguidos"] >= 2 and agora - avisados.get("cel_aviso", 0) > 240:
        avisados["cel_aviso"] = agora
        avisar(player, _neg.frase_celular(restante), "POMODORO")


def negociar(acao: str, o_que: str = "", minutos=None) -> str:
    agora = time.time()
    with _lock:
        e = dict(_estado)
        em_foco = e.get("fase") == "foco" and not e.get("pausado")
        if acao == "negociar":
            atividade = ""
            try:
                from core import estado_mundo
                atividade = estado_mundo.agora().get("atividade", "")
            except Exception:
                pass
            r = _neg.propor(num(minutos, 5), o_que, (e["fim"] - agora) if em_foco else None, atividade,
                            e.get("acordos", 0), e.get("duracao_pausa", 300) / 60, agora)
            if r["acordo"]:
                _estado["acordo"] = r["acordo"]
            extra = "" if not r["acordo"] else (" [Para o modelo: quando ele cumprir, action='cumpri'. Se ele "
                                                "insistir em agora, action='fiado'.]")
            return r["resposta"] + extra
        if not em_foco:
            return "Não tem foco rolando agora: pode ir."
        if acao == "cumpri":
            texto, lib = _neg.cumprir(e.get("acordo"), agora)
            if lib:
                _estado.update(acordo=None, liberado=lib, acordos=e.get("acordos", 0) + 1)
            return texto
        texto, lib, divida = _neg.fiado(e.get("acordo"), o_que, num(minutos, 5), agora)
        _estado.update(acordo=None, liberado=lib, acordos=e.get("acordos", 0) + 1,
                       divida_s=e.get("divida_s", 0) + divida)
        return texto


def iniciar(player, foco=None, pausa=None) -> str:
    c = _cfg()
    f = max(1.0, num(foco, 0) or num(c.get("foco"), 25))
    p = max(1.0, num(pausa, 0) or num(c.get("pausa"), 5))
    with _lock:
        if _estado.get("fase"):
            return "Já tem um pomodoro rodando. Diga 'para o pomodoro' para recomeçar."
        _estado.clear()
        _estado.update({"fase": "foco", "fim": time.time() + f * 60, "duracao_foco": f * 60,
                        "duracao_pausa": p * 60, "ciclo": 0, "pausado": False})
    _parar.clear()
    if not any(t.name == "pomodoro" and t.is_alive() for t in threading.enumerate()):
        threading.Thread(target=_laco, args=(player,), daemon=True, name="pomodoro").start()
    extra = ""
    if sim(c.get("protocolo_foco", True)):
        try:
            from plugins.protocolos import _load
            if "foco" in _load():
                from plugins.protocolos import _executar
                threading.Thread(target=_executar, args=("foco", player, True), daemon=True).start()
                extra = " Rodei o protocolo Foco."
        except Exception as e:
            registrar(player, f"Pomodoro: protocolo foco não rodou ({e})")
    return (f"Pomodoro começou: {int(f)} minutos de foco e {int(p)} de pausa. "
            f"Apps e sites de distração ficam bloqueados até a pausa.{extra}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "status").strip().lower()
    try:
        if a in ("iniciar", "comecar", "começar"):
            return iniciar(player, p.get("foco"), p.get("pausa"))
        if a == "parar":
            with _lock:
                if not _estado.get("fase"):
                    return "Nenhum pomodoro rodando."
                ciclos = _estado.get("ciclo", 0)
                _estado.clear()
                _estado["fase"] = None
            _parar.set()
            return f"Pomodoro encerrado depois de {ciclos} foco(s). Bloqueios liberados."
        if a in ("pausar", "retomar"):
            with _lock:
                if not _estado.get("fase"):
                    return "Nenhum pomodoro rodando."
                if a == "pausar" and not _estado.get("pausado"):
                    _estado["pausado"] = True
                    _estado["restante"] = _estado["fim"] - time.time()
                    return "Pomodoro pausado. Bloqueios suspensos."
                if a == "retomar" and _estado.get("pausado"):
                    _estado["pausado"] = False
                    _estado["fim"] = time.time() + _estado.pop("restante", 0)
                    return "Pomodoro retomado."
            return "Nada a mudar."
        if a == "status":
            with _lock:
                e = dict(_estado)
            if not e.get("fase"):
                return "Nenhum pomodoro rodando."
            restante = e.get("restante") if e.get("pausado") else e["fim"] - time.time()
            m, s = divmod(int(max(0, restante)), 60)
            return (f"{'Foco' if e['fase'] == 'foco' else 'Pausa'}: faltam {m} min {s:02d} s"
                    f"{' (pausado)' if e.get('pausado') else ''}. Focos concluídos: {e.get('ciclo', 0)}.")
        if a in ("negociar", "cumpri", "fiado"):                # Fork PT-BR 2.5
            return negociar(a, str(p.get("o_que") or ""), p.get("minutos"))
        if a == "vigiar":
            from plugins._comum import salvar_cfg
            ligar = not str(p.get("valor") or "ligar").lower().startswith(("deslig", "off", "não", "nao", "para"))
            salvar_cfg("pomodoro", {"celular": ligar})
            if not ligar:
                return "Parei de olhar o celular no foco."
            from plugins import _visao_local
            if not _visao_local.disponivel():
                return ("Para eu ver o celular na sua mão preciso do MediaPipe: python -m pip install mediapipe. "
                        "Deixei ligado para quando ele estiver instalado.")
            return "Combinado: no foco eu fico de olho no celular pela webcam (a imagem não sai do PC)."
        if a == "hoje":
            d = (ler_json(ARQUIVO, {}) or {}).get(date.today().isoformat())
            if not d:
                return "Nenhum pomodoro hoje ainda."
            return f"Hoje: {d['pomodoros']} pomodoro(s), {d['minutos']} minutos de foco."
        return "Use iniciar, pausar, retomar, parar, status, hoje, negociar, cumpri, fiado ou vigiar."
    except Exception as e:
        return f"O pomodoro falhou: {e}"
