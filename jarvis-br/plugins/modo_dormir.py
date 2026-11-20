"""
Modo dormir (fork PT-BR 2.8): o JARVIS dorme — e cuida do seu sono.

    "Jarvis, vai dormir" / "dorme 30 minutos" / "fica quieto até as 15h"
        → o JARVIS para de ouvir (nada vai para a internet) até alguém acordar ele
    "Jarvis, vou dormir, me acorda às 6h30"
        → boa noite: não perturbe até de manhã, luzes (cena da casa), som para dormir,
          tela apagada, música abaixando sozinha, PC suspenso quando ficar parado (se quiser)
          e o despertador. De manhã: bom dia com quanto você dormiu, o clima, o que vence
          hoje e o que chegou enquanto você dormia
    "Vou tirar um cochilo de 20 minutos"          → cochilo com despertador
    "Mais 10 minutos" (com o despertador tocando)  → soneca
    "Que horas eu acordo se dormir agora?" / "Que horas durmo para acordar às 6?"
                                                   → ciclos de sono de 90 minutos
    "Como foi meu sono?" / "dormi das 23h às 7h"   → diário do sono: noite passada, média da
                                                     semana, dívida de sono e regularidade
    "Toca chuva para dormir" / "ruído branco por 40 minutos" / "ventilador"
                                                   → sons gerados no próprio PC, somem devagar
    "Me ajuda a relaxar" / "respiração 4-7-8"      → respiração guiada por sons
    ⚙ "Lembrete da hora de dormir"                 → "Senhor, são 23h30, sua hora de dormir…"

Acordar o JARVIS: duas palmas, "Hey Jarvis" (se baixado), "Jarvis, acorda" (com o
faster-whisper), Ctrl+Alt+D, o botão ACORDAR AGORA, digitar, o celular — ou sozinho na
hora marcada. O estado de dormir mora em core/sono.py; aqui ficam a rotina, o
despertador e o diário do sono (memory/modo_dormir.json).
"""

from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timedelta

from core import sono
from plugins._comum import (LINUX, MAC, MEMORIA, WIN, avisar, cfg, confirmar, falar, gravar_json, ler_json,
                            mostrar, num, plugin_ligado, registrar, rodar, sim, tem)

PLUGIN = {
    "name": "modo_dormir",
    "brief": "Sleep: JARVIS sleeps/wakes (timer), goodnight routine, alarm+snooze, nap, sleep cycles, "
             "sleep log, sleep sounds (rain, white noise, fan), guided breathing.",
    "description": (
        "Sleep. action: 'dormir' (JARVIS ITSELF goes to sleep/standby and stops listening until woken; "
        "optional minutos, or ate 'HH:MM' — 'Jarvis, vai dormir', 'dorme 30 minutos', 'fica quieto até as 15h'), "
        "'boa_noite' (the USER is going to bed — 'vou dormir', 'boa noite, vou deitar', 'modo noite'; NOT a plain "
        "'boa noite' greeting: do not disturb until morning, lights scene, sleep sound, screen off, optional PC "
        "suspend; acordar='HH:MM' sets the alarm or 'nao' for none; pc='suspender|hibernar|desligar|nao'; "
        "som=sound name), 'cochilo' (minutos: power nap with alarm), 'despertador' (hora 'HH:MM' sets an alarm, "
        "cancelar=true removes it, no args = status), 'soneca' (minutos: snooze while the alarm rings), "
        "'ciclos' (dormir_as or acordar_as 'HH:MM': best times by 90-min sleep cycles), 'sono' (sleep report: "
        "last night, week average, sleep debt), 'registrar' (inicio and fim 'HH:MM': log a night by hand), "
        "'sons' (som: chuva|mar|ruido_branco|ruido_rosa|ruido_marrom|ventilador|lareira|floresta|noite|vento, "
        "minutos; som='parar' stops), 'respirar' (tecnica '478' or 'caixa', ciclos, dormir_depois=true), "
        "'acordar', 'status'. Use this — NEVER shutdown_jarvis — for 'vai dormir', 'dorme', 'modo dormir', "
        "'boa noite, vou dormir'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "dormir | boa_noite | cochilo | despertador | soneca | "
                                                        "ciclos | sono | registrar | sons | respirar | acordar | "
                                                        "status"},
            "minutos": {"type": "NUMBER"}, "ate": {"type": "STRING", "description": "HH:MM"},
            "acordar": {"type": "STRING", "description": "alarm time HH:MM, or 'nao'"},
            "pc": {"type": "STRING", "description": "suspender | hibernar | desligar | nao"},
            "som": {"type": "STRING"}, "hora": {"type": "STRING", "description": "HH:MM"},
            "cancelar": {"type": "BOOLEAN"}, "dormir_as": {"type": "STRING"}, "acordar_as": {"type": "STRING"},
            "inicio": {"type": "STRING"}, "fim": {"type": "STRING"}, "tecnica": {"type": "STRING"},
            "ciclos": {"type": "NUMBER"}, "dormir_depois": {"type": "BOOLEAN"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "modo_dormir",
    "title": "Modo dormir e sono",
    "fields": [
        {"key": "palmas", "label": "Duas palmas acordam o JARVIS", "type": "toggle", "default": True},
        {"key": "sensibilidade_palmas", "label": "Sensibilidade das palmas", "type": "choice",
         "options": ["baixa", "media", "alta"], "default": "media"},
        {"key": "voz_local", "label": "\"Jarvis, acorda\" sem internet (precisa do pacote faster-whisper)",
         "type": "toggle", "default": True},
        {"key": "atalho", "label": "Ctrl+Alt+D dorme/acorda de qualquer janela (vale ao reabrir)", "type": "toggle",
         "default": True},
        {"key": "despertador_padrao", "label": "Despertador do boa noite quando você não disser a hora (HH:MM; "
                                               "vazio = sem)", "type": "text", "default": ""},
        {"key": "so_dias_uteis", "label": "Esse despertador só de segunda a sexta", "type": "toggle", "default": False},
        {"key": "som_despertador", "label": "Despertador toca", "type": "choice", "options": ["sino", "musica"],
         "default": "sino"},
        {"key": "musica_despertador", "label": "Música do despertador (vazio = o que você mais ouve)", "type": "text",
         "default": ""},
        {"key": "som_dormir", "label": "Som no boa noite (chuva, mar, ruido_branco, ruido_rosa, ruido_marrom, "
                                       "ventilador… vazio = nenhum)", "type": "text", "default": ""},
        {"key": "minutos_som", "label": "Minutos do som para dormir", "type": "text", "default": "45"},
        {"key": "volume_som", "label": "Volume do som para dormir (0-100)", "type": "text", "default": "22"},
        {"key": "cena_casa", "label": "Cena da casa no boa noite (ex.: dormir; vazio = não mexe)", "type": "text",
         "default": ""},
        {"key": "apagar_tela", "label": "Apagar a tela no boa noite", "type": "toggle", "default": True},
        {"key": "pc_ao_dormir", "label": "Depois do boa noite, o PC", "type": "choice",
         "options": ["nao", "suspender", "hibernar"], "default": "nao"},
        {"key": "minutos_pc", "label": "…quando ficar parado por (minutos)", "type": "text", "default": "30"},
        {"key": "meta_horas", "label": "Meta de sono (horas)", "type": "text", "default": "8"},
        {"key": "hora_dormir", "label": "Lembrete da hora de dormir (HH:MM; vazio = sem)", "type": "text",
         "default": ""},
        {"key": "bom_dia", "label": "Bom dia com o resumo da noite ao acordar", "type": "toggle", "default": True},
    ],
}

ARQ = MEMORIA / "modo_dormir.json"
CICLO_MIN = 90                 # um ciclo de sono
ADORMECER_MIN = 15             # tempo médio para pegar no sono
SONECA_MIN = 9
VOLTA_A_DORMIR_S = 120         # acordou de madrugada: volta a dormir depois de 2 min sem conversa
_lock = threading.RLock()
_som = {"laco": None, "nome": "", "ate": 0.0, "vez": 0}
_iniciou = threading.Event()

NOMES_SOM = {
    "chuva": "chuva", "temporal": "chuva", "mar": "mar", "ondas": "mar", "praia": "mar", "oceano": "mar",
    "ruido branco": "ruido_branco", "ruido_branco": "ruido_branco", "branco": "ruido_branco",
    "white noise": "ruido_branco", "ruido rosa": "ruido_rosa", "ruido_rosa": "ruido_rosa", "rosa": "ruido_rosa",
    "ruido marrom": "ruido_marrom", "ruido_marrom": "ruido_marrom", "marrom": "ruido_marrom",
    "brown noise": "ruido_marrom", "ventilador": "ventilador", "ventinha": "ventilador", "lareira": "lareira",
    "fogueira": "lareira", "floresta": "floresta", "passaros": "floresta", "noite": "noite", "grilos": "noite",
    "vento": "vento", "ruido": "ruido_rosa",
}
ROTULO_SOM = {"chuva": "chuva", "mar": "mar", "ruido_branco": "ruído branco", "ruido_rosa": "ruído rosa",
              "ruido_marrom": "ruído marrom", "ventilador": "ventilador", "lareira": "lareira",
              "floresta": "floresta", "noite": "noite com grilos", "vento": "vento"}
TECNICAS = {"478": ("4-7-8", [("inspira", 4), ("segura", 7), ("solta", 8)], 4),
            "caixa": ("respiração caixa", [("inspira", 4), ("segura", 4), ("solta", 4), ("segura", 4)], 5)}


# ── dados ─────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("noites", [])
    d.setdefault("noite", None)          # a noite em andamento {"deitou", "alarme", "sonecas", "acordadas", "recados"}
    d.setdefault("alarme", None)         # {"quando", "hora", "tocado", "noite", "cochilo"}
    d.setdefault("lembrete", "")         # a noite (data) do último lembrete da hora de dormir
    d.setdefault("reabrir", None)        # a noite fechada há pouco (a soneca reabre)
    return d


def _salvar(d: dict) -> None:
    with _lock:
        d["noites"] = (d.get("noites") or [])[-180:]
        gravar_json(ARQ, d)


def _c() -> dict:
    return cfg("modo_dormir", PLUGIN_SETTINGS)


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def duracao_txt(segundos: float) -> str:
    """26_100 → '7h15'; 2_700 → '45 min' (pura)."""
    m = int(round(max(0.0, float(segundos)) / 60))
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}" if h else f"{m} min"


def ciclos_para_acordar(deitar: datetime, ciclos=(4, 5, 6), adormecer_min: int = ADORMECER_MIN) -> list[tuple[int, datetime]]:
    """Deitando agora, os horários bons para acordar (fim de um ciclo) (pura)."""
    return [(n, deitar + timedelta(minutes=adormecer_min + n * CICLO_MIN)) for n in ciclos]


def ciclos_para_deitar(acordar: datetime, ciclos=(6, 5, 4), adormecer_min: int = ADORMECER_MIN) -> list[tuple[int, datetime]]:
    """Para acordar nesse horário no fim de um ciclo, a hora de deitar (pura)."""
    return [(n, acordar - timedelta(minutes=adormecer_min + n * CICLO_MIN)) for n in ciclos]


def ciclos_dormidos(segundos: float, adormecer_min: int = ADORMECER_MIN) -> float:
    return max(0.0, (segundos / 60 - adormecer_min) / CICLO_MIN)


def frase_ciclos(dormir_as: str = "", acordar_as: str = "", agora: datetime | None = None) -> str:
    """Pura: 'Se deitar às 23:40, acorde às 05:55 (4 ciclos, 6h), 07:25 (5 ciclos, 7h30) ou 08:55…'"""
    agora = agora or datetime.now()
    if acordar_as:
        alvo = sono.interpretar_hora(acordar_as, agora)
        if alvo is None:
            return "Que horas o senhor quer acordar? (ex.: 06:30)"
        op = [f"{d:%H:%M} ({n} ciclos, {duracao_txt(n * CICLO_MIN * 60)} de sono)"
              for n, d in ciclos_para_deitar(alvo) if d > agora - timedelta(minutes=5)]
        if not op:
            return (f"Para acordar às {alvo:%H:%M} já não dá para completar 4 ciclos; deite agora e durma o "
                    "que der, ou escolha um horário mais tarde.")
        return (f"Para acordar às {alvo:%H:%M} no fim de um ciclo, deite às " + _lista(op) +
                f" (já contando uns {ADORMECER_MIN} minutos para pegar no sono).")
    base = sono.interpretar_hora(dormir_as, agora - timedelta(minutes=1)) if dormir_as else agora
    if base is None:
        return "Que horas o senhor vai deitar? (ex.: 23:30)"
    op = [f"{d:%H:%M} ({n} ciclos, {duracao_txt(n * CICLO_MIN * 60)})" for n, d in ciclos_para_acordar(base)]
    quando = "agora" if not dormir_as else f"às {base:%H:%M}"
    return (f"Se deitar {quando}, os melhores horários para acordar são " + _lista(op) +
            f" (com uns {ADORMECER_MIN} minutos para pegar no sono). Acordar no fim de um ciclo dá menos "
            "sensação de ressaca de sono.")


def _lista(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " ou " + itens[-1]


def eh_manha(deitou: float, agora: float, alarme: float = 0.0) -> bool:
    """Acordou de manhã (fecha a noite) ou no meio da noite (volta a dormir)? (pura)
    Manhã: até 2 h antes do despertador; sem despertador, depois de 4 h na cama entre 4h e 14h,
    ou depois de 7 h na cama a qualquer hora."""
    dormiu_h = (agora - deitou) / 3600
    if alarme:
        return agora >= alarme - 2 * 3600 or dormiu_h >= 9
    h = datetime.fromtimestamp(agora).hour
    return (dormiu_h >= 4 and 4 <= h < 14) or dormiu_h >= 7


def despertador_padrao(hora: str, so_uteis: bool, agora: datetime | None = None) -> float:
    """O despertador do boa noite quando ninguém disse a hora (pura). 0 = sem."""
    agora = agora or datetime.now()
    if not str(hora or "").strip():
        return 0.0
    alvo = sono.interpretar_hora(hora, agora)
    if alvo is None:
        return 0.0
    if so_uteis and alvo.weekday() >= 5:
        return 0.0
    return alvo.timestamp()


def estatisticas(noites: list[dict], agora: float | None = None, meta_h: float = 8.0, dias: int = 7) -> dict:
    """Média, dívida de sono e regularidade das últimas `dias` noites (pura)."""
    agora = time.time() if agora is None else agora
    recentes = [n for n in noites if n.get("acordou") and agora - float(n["acordou"]) <= dias * 86400 + 3600]
    durs = [max(0.0, float(n["acordou"]) - float(n["deitou"])) for n in recentes]
    if not durs:
        return {"n": 0}
    media = sum(durs) / len(durs)
    # regularidade: quanto o horário de deitar varia (minutos; perto da meia-noite não "quebra" a conta)
    minutos = []
    for n in recentes:
        d = datetime.fromtimestamp(float(n["deitou"]))
        m = d.hour * 60 + d.minute
        minutos.append(m + 1440 if m < 12 * 60 else m)
    mm = sum(minutos) / len(minutos)
    desvio = math.sqrt(sum((m - mm) ** 2 for m in minutos) / len(minutos))
    media_deitar = int(mm) % 1440
    divida = max(0.0, meta_h * 3600 * len(durs) - sum(durs))
    return {"n": len(durs), "media_s": media, "menor_s": min(durs), "maior_s": max(durs), "divida_s": divida,
            "desvio_min": desvio, "deitar_medio": f"{media_deitar // 60:02d}:{media_deitar % 60:02d}",
            "ultima_s": durs[-1]}


def noite_manual(inicio: str, fim: str, agora: datetime | None = None) -> tuple[float, float] | None:
    """'dormi das 23h às 7h' → (deitou, acordou) da última vez que isso aconteceu (pura)."""
    agora = agora or datetime.now()
    hi, hf = sono.ler_hora(inicio), sono.ler_hora(fim)
    if hi is None or hf is None:
        return None
    acordou = agora.replace(hour=hf[0], minute=hf[1], second=0, microsecond=0)
    if acordou > agora:
        acordou -= timedelta(days=1)
    deitou = acordou.replace(hour=hi[0], minute=hi[1])
    if deitou >= acordou:
        deitou -= timedelta(days=1)
    if (acordou - deitou) > timedelta(hours=16):
        return None
    return deitou.timestamp(), acordou.timestamp()


def chave_noite(agora: datetime) -> str:
    """A 'noite' a que um horário pertence (00:30 ainda é a noite de ontem) (pura)."""
    return (agora - timedelta(hours=12)).date().isoformat()


def hora_de_dormir_vencida(hora: str, agora: datetime, janela_h: float = 3.0) -> str | None:
    """Já passou da hora de dormir (dentro da janela)? Devolve a chave da noite, ou None (pura)."""
    hm = sono.ler_hora(hora)
    if hm is None:
        return None
    alvo = agora.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
    if alvo > agora:
        alvo -= timedelta(days=1)
    if agora - alvo > timedelta(hours=janela_h):
        return None
    return chave_noite(alvo)


def nome_som(texto: str) -> str:
    t = sono.sem_acento(str(texto or "")).lower().replace("-", " ").strip()
    if t in NOMES_SOM:
        return NOMES_SOM[t]
    for k, v in NOMES_SOM.items():
        if k in t:
            return v
    return ""


def op_pc(texto) -> str:
    t = sono.sem_acento(str(texto or "")).lower()
    if t.startswith("susp") or "dormir" in t:
        return "suspender"
    if t.startswith("hiber"):
        return "hibernar"
    if t.startswith("deslig"):
        return "desligar"
    return ""


def _nao(texto) -> bool:
    return sono.sem_acento(str(texto or "")).strip().lower() in ("nao", "sem", "nenhum", "sem despertador", "no",
                                                                  "false", "0")


# ── o JARVIS (main.py) ────────────────────────────────────────────────────────
def _app():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.app()
    except Exception:
        return None


def _player():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.player()
    except Exception:
        return None


def jarvis_dormir(motivo: str, ate: float = 0.0, rotina: bool = False, alarme: bool = False) -> None:
    a = _app()
    if a is not None and hasattr(a, "sleep"):
        try:
            a.sleep(reason=motivo, manual=True, ate=ate, rotina=rotina, alarme=alarme)
            return
        except TypeError:                                   # main.py antigo (sem o modo dormir)
            pass
    sono.dormir(motivo, ate=ate, rotina=rotina, alarme=alarme)


def jarvis_acordar(motivo: str) -> None:
    a = _app()
    if a is not None and hasattr(a, "wake"):
        a.wake(reason=motivo)
    else:
        info = sono.acordar(motivo)
        if info:
            _ao_acordar(info)


def _como_acordar() -> str:
    a = _app()
    if a is not None and hasattr(a, "_como_acordar"):
        try:
            return a._como_acordar()
        except Exception:
            pass
    return sono.como_acordar(palmas=sono.config_bool("palmas", True))


def _esperar_calar(maximo_s: float = 45.0) -> None:
    """Espera o JARVIS terminar de responder (o bom dia não corta a resposta de um pedido)."""
    a = _app()
    fim = time.time() + maximo_s
    if a is None:
        return
    time.sleep(2.0)
    quieto = 0.0
    while time.time() < fim and a is not None:
        if getattr(a, "_is_speaking", False):
            quieto = 0.0
        else:
            quieto += 0.25
            if quieto >= 2.0:
                return
        time.sleep(0.25)


# ── sons para dormir ──────────────────────────────────────────────────────────
def tocar_som(som: str, minutos: float = 45, volume: float | None = None) -> str:
    nome = nome_som(som)
    if not nome:
        return ("Tenho chuva, mar, ruído branco, rosa e marrom, ventilador, lareira, floresta, noite com grilos e "
                "vento. Qual?")
    minutos = max(1.0, min(600.0, num(minutos, 45) or 45))
    vol = volume if volume is not None else max(0.02, min(1.0, num(_c().get("volume_som"), 22) / 100))
    parar_som(fade=1.0)
    try:
        from plugins import _som as S
        laco = S.Laco(S.ambiente(nome, segundos=20.0), 22050, volume=vol)
        laco.tocar()
    except Exception as e:
        return f"Não consegui tocar o som agora ({e})."
    with _lock:
        _som["vez"] += 1
        vez = _som["vez"]
        _som.update(laco=laco, nome=nome, ate=time.time() + minutos * 60)
    threading.Thread(target=_sumir_som, args=(vez, minutos), daemon=True, name="sono_som").start()
    return f"Tocando {ROTULO_SOM[nome]} por {minutos:g} minutos; no fim ele some devagar."


def _sumir_som(vez: int, minutos: float) -> None:
    """Some devagar nos últimos 3 minutos e para."""
    fim = time.time() + minutos * 60
    while time.time() < fim - 180:
        if _som["vez"] != vez:
            return
        time.sleep(5)
    laco = _som["laco"]
    if laco is None or _som["vez"] != vez:
        return
    inicio = laco.volume
    for i in range(36):
        if _som["vez"] != vez:
            return
        laco.alvo = inicio * (1 - (i + 1) / 36)
        time.sleep(max(0.5, (fim - time.time()) / max(1, 36 - i)))
    if _som["vez"] == vez:
        parar_som(fade=1.0)


def parar_som(fade: float = 1.5) -> bool:
    with _lock:
        laco = _som["laco"]
        _som.update(laco=None, nome="", ate=0.0)
        _som["vez"] += 1
    if laco is None:
        return False
    try:
        laco.parar(fade=fade)
    except Exception as e:
        print(f"[Sono] parar som: {e}")
    return True


def som_tocando() -> str:
    return _som["nome"] if _som["laco"] is not None else ""


# ── respiração guiada ────────────────────────────────────────────────────────
def audio_respiracao(fases: list[tuple[str, int]], ciclos: int, taxa: int = 22050):
    """Sobe = inspira, fica = segura, desce = solta. Um sino suave marca cada ciclo (pura)."""
    import numpy as np
    partes = []
    for c in range(ciclos):
        for i, (fase, seg) in enumerate(fases):
            t = np.arange(int(seg * taxa)) / taxa
            env = np.minimum(1.0, np.minimum(t / 0.4, (seg - t) / 0.4)).clip(0, 1)
            if fase == "inspira":
                f = 220 + 110 * (t / seg)
            elif fase == "solta":
                f = 330 - 134 * (t / seg)
            else:
                f = np.full_like(t, 330.0 if (i and fases[i - 1][0] == "inspira") else 196.0)
            vol = 0.18 if fase != "segura" else 0.07
            onda = np.sin(2 * np.pi * np.cumsum(f) / taxa) + 0.25 * np.sin(4 * np.pi * np.cumsum(f) / taxa)
            if c == 0 and i == 0:
                onda[: int(0.25 * taxa)] += np.sin(2 * np.pi * 880 * t[: int(0.25 * taxa)]) * 0.5
            partes.append((onda * env * vol).astype("float32"))
    return np.concatenate(partes) if partes else np.zeros(1, "float32")


def respirar(tecnica: str = "478", ciclos=None, dormir_depois: bool = False) -> str:
    chave = "caixa" if "caix" in sono.sem_acento(str(tecnica or "")).lower() or "box" in str(tecnica).lower() else "478"
    nome, fases, padrao = TECNICAS[chave]
    n = int(max(1, min(12, num(ciclos, padrao) or padrao)))
    total = n * sum(s for _f, s in fases)

    def rodar_():
        from core import microfone
        try:
            _esperar_calar(maximo_s=20)
            microfone.reservar("respiração", total + 5)     # a respiração não vai para o modelo
            from plugins import _som as S
            S.tocar_uma(audio_respiracao(fases, n), 22050, 1.0)
            time.sleep(total + 0.5)
        except Exception as e:
            print(f"[Sono] respiração: {e}")
        finally:
            microfone.liberar()
        if dormir_depois:
            jarvis_dormir("depois da respiração")
    threading.Thread(target=rodar_, daemon=True, name="sono_respirar").start()
    passos = ", ".join(f"{f} {s}" for f, s in fases)
    return (f"Respiração {nome}: {n} ciclos ({passos} segundos), uns {duracao_txt(total)}. Explique em UMA frase "
            "calma: acompanhe o som — subindo, inspire pelo nariz; parado, segure; descendo, solte devagar pela "
            "boca. Depois fique em silêncio até o fim." + (" No fim eu entro no modo dormir." if dormir_depois else ""))


# ── tela, casa, música e PC ───────────────────────────────────────────────────
def apagar_tela() -> bool:
    try:
        if WIN:
            import ctypes
            # PostMessage (não SendMessage): um programa travado não segura o JARVIS
            return bool(ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2))
        if MAC:
            return rodar(["pmset", "displaysleepnow"], timeout=5)[0] == 0
        if LINUX and tem("xset"):
            return rodar(["xset", "dpms", "force", "off"], timeout=5)[0] == 0
    except Exception as e:
        print(f"[Sono] apagar a tela: {e}")
    return False


def _cena_casa(nome: str) -> str:
    try:
        from plugins import casa_inteligente
        return casa_inteligente.rodar_cena(nome)
    except Exception as e:
        return f"cena '{nome}' falhou: {e}"


def _musica_tocando() -> bool:
    try:
        from plugins import _midia
        return bool(_midia.tocando())
    except Exception:
        return False


def _timer_musica(minutos: float) -> None:
    try:
        from plugins import musica
        musica.dormir(float(minutos))
    except Exception as e:
        print(f"[Sono] timer da música: {e}")


def _ocioso() -> float | None:
    try:
        from plugins.linha_do_tempo import ocioso_segundos
        v = ocioso_segundos()
        return v if (WIN or v > 0) else None
    except Exception:
        return None


def _executar_energia(op: str) -> str:
    try:
        from plugins import controle_pc
        fn = controle_pc._cmd_energia(op)
    except Exception as e:
        return f"sem controle de energia ({e})"
    if fn is None:
        return "não disponível neste sistema"
    parar_som(fade=1.0)
    registrar(None, f"😴 Boa noite: {op} o PC agora.")
    fn()
    return "ok"


def _vigiar_pc(op: str, minutos: float, deitou: float) -> None:
    """Suspende/hiberna/desliga quando o PC ficou parado `minutos` depois do boa noite (até 3 h)."""
    limite = deitou + 3 * 3600
    while time.time() < limite:
        time.sleep(30)
        d = dados()
        if not d.get("noite") or abs(float(d["noite"].get("deitou") or 0) - deitou) > 1:
            return                                          # acordou ou começou outra noite
        if time.time() - deitou < minutos * 60:
            continue
        ocioso = _ocioso()
        if ocioso is None:
            registrar(None, "😴 Não sei se o PC está parado neste sistema; não vou desligar sozinho.")
            return
        if ocioso < minutos * 60:
            continue
        if not som_tocando() and _musica_tocando():
            continue                                        # ainda tem filme/música (que não é o nosso som)
        _executar_energia(op)
        return
    registrar(None, "😴 O PC não ficou parado depois do boa noite; deixei ligado.")


def agendar_pc(op: str, minutos: float, deitou: float) -> None:
    threading.Thread(target=_vigiar_pc, args=(op, minutos, deitou), daemon=True, name="sono_pc").start()


# ── amanhã / hoje ─────────────────────────────────────────────────────────────
def _agenda_do_dia(dia) -> list[str]:
    itens = []
    try:
        from plugins import contas
        for c in contas.dados().get("contas", []):
            if not c.get("pago") and c.get("vencimento") == dia.isoformat():
                valor = ""
                try:
                    valor = f" ({contas.B.reais(float(c['valor']))})" if c.get("valor") not in (None, "") else ""
                except Exception:
                    pass
                itens.append(f"vence {c.get('descricao') or 'uma conta'}{valor}")
    except Exception:
        pass
    try:
        from plugins import aniversarios
        for a, quando in aniversarios.proximos(aniversarios.carregar(), dia, 0):
            if quando == dia:
                itens.append(f"aniversário de {a.get('nome', 'alguém')}")
    except Exception:
        pass
    return itens[:4]


def _clima_cambio(timeout: float = 6.0) -> str:
    import sys
    mod = sys.modules.get("plugins.briefing_br")
    fn = getattr(mod, "coletar_extras", None)
    if not callable(fn) or not plugin_ligado("briefing_br"):
        return ""
    caixa = {"t": ""}

    def ir():
        try:
            caixa["t"] = fn() or ""
        except Exception:
            pass
    t = threading.Thread(target=ir, daemon=True)
    t.start()
    t.join(timeout)
    return caixa["t"]


# ── ações ─────────────────────────────────────────────────────────────────────
def acao_dormir(minutos=None, ate: str = "") -> str:
    agora = time.time()
    fim = 0.0
    if minutos not in (None, "") and num(minutos) > 0:
        fim = agora + max(1.0, min(24 * 60.0, num(minutos))) * 60
    elif str(ate or "").strip():
        alvo = sono.interpretar_hora(ate)
        if alvo is None:
            return "Até que horas? (ex.: 15:00)"
        fim = alvo.timestamp()
    jarvis_dormir("pedido", ate=fim)
    quando = f" até as {sono.hora_txt(fim)}" if fim else ""
    return (f"Modo dormir ligado{quando}: não ouço mais nada até acordar, e os avisos ficam guardados. "
            f"{_como_acordar()} Responda só com uma despedida curta (ex.: 'Modo de espera, senhor.') e não "
            "chame nenhuma ferramenta.")


def boa_noite(acordar: str = "", pc: str = "", som: str = "", minutos=None) -> str:
    c = _c()
    agora = datetime.now()
    # despertador
    if _nao(acordar):
        alarme = 0.0
    elif str(acordar or "").strip():
        alvo = sono.interpretar_hora(acordar, agora)
        if alvo is None:
            return "Que horas o senhor quer acordar? (ex.: 06:30)"
        alarme = alvo.timestamp()
    else:
        marcado = dados().get("alarme")                     # "me acorda às 6h30" dito antes vale
        if marcado and not marcado.get("tocado") and float(marcado.get("quando") or 0) > time.time():
            alarme = float(marcado["quando"])
        else:
            alarme = despertador_padrao(c.get("despertador_padrao"), sim(c.get("so_dias_uteis")), agora)
    d = dados()
    anterior = d.get("noite")
    if anterior and time.time() - float(anterior.get("deitou") or 0) < 12 * 3600:
        # "vou dormir" de novo de madrugada: é a mesma noite (não perde a primeira parte)
        deitou = float(anterior["deitou"])
        d["noite"] = dict(anterior, alarme=alarme)
    else:
        deitou = time.time()
        d["noite"] = {"deitou": deitou, "alarme": alarme, "sonecas": 0, "acordadas": 0, "recados": []}
    d["alarme"] = ({"quando": alarme, "hora": sono.hora_txt(alarme), "tocado": False, "noite": True}
                   if alarme else None)
    d["reabrir"] = None
    _salvar(d)
    # o que fazer com o PC
    pedido_pc = op_pc(pc)
    op = pedido_pc or ("" if _nao(pc) else op_pc(c.get("pc_ao_dormir")))
    min_pc = max(5.0, num(c.get("minutos_pc"), 30) or 30)
    aviso_pc = ""
    if op and alarme and not pedido_pc:
        aviso_pc = (f"não vou {('suspender' if op == 'suspender' else 'hibernar')} o PC porque o despertador "
                    "precisa dele ligado (a tela fica apagada)")
        op = ""
    elif op and alarme:
        aviso_pc = "com o PC desligado ou suspenso o despertador do PC NÃO toca: use o do celular também"
    # som
    nome = nome_som(som) if som else nome_som(c.get("som_dormir") or "")
    min_som = num(minutos, 0) or num(c.get("minutos_som"), 45) or 45
    cena = str(c.get("cena_casa") or "").strip()
    # o JARVIS dorme até o despertador
    jarvis_dormir("boa noite", ate=alarme, rotina=True, alarme=bool(alarme))
    threading.Thread(target=_rotina_noite, args=(nome, min_som, cena, sim(c.get("apagar_tela", True))),
                     daemon=True, name="sono_boa_noite").start()
    partes = ["Não perturbe até de manhã (os avisos ficam guardados para o bom dia)"]
    if alarme:
        dur = alarme - time.time()
        partes.append(f"despertador às {sono.hora_txt(alarme)} — uns {duracao_txt(dur - ADORMECER_MIN * 60)} de "
                      f"sono, {ciclos_dormidos(dur):.1f} ciclos")
    else:
        partes.append("sem despertador")
    if nome:
        partes.append(f"som de {ROTULO_SOM[nome]} por {min_som:g} min")
    if cena:
        partes.append(f"cena '{cena}' da casa")
    if op == "desligar":
        partes.append(confirmar("sono-desligar", "Desligar o PC depois do boa noite",
                                f"Quando o PC ficar {min_pc:g} minutos parado, ele desliga (salve o que estiver "
                                "aberto).", lambda: (agendar_pc("desligar", min_pc, deitou),
                                                     "Combinado: desligo o PC quando ele ficar parado.")[1]))
    elif op:
        agendar_pc(op, min_pc, deitou)
        partes.append(f"o PC {'suspende' if op == 'suspender' else 'hiberna'} quando ficar {min_pc:g} minutos parado")
    if aviso_pc:
        partes.append(aviso_pc)
    amanha = _agenda_do_dia((agora + timedelta(hours=10)).date())
    texto = "; ".join(partes) + "."
    if amanha:
        texto += " Amanhã: " + "; ".join(amanha) + "."
    registrar(None, f"😴 Boa noite — {texto}")
    return (texto + " Dê boa noite ao usuário em até 2 frases curtas e calmas, citando o despertador (e o que tem "
            "amanhã, se houver). Não chame nenhuma ferramenta.")


def _rotina_noite(som: str, minutos_som: float, cena: str, apagar: bool) -> None:
    """O resto do boa noite, depois que o JARVIS termina de falar."""
    _esperar_calar(maximo_s=25)
    if _musica_tocando():
        _timer_musica(min(30.0, minutos_som or 30.0))
    if cena:
        registrar(None, f"😴 Casa: {_cena_casa(cena)}")
    if som:
        registrar(None, f"😴 {tocar_som(som, minutos_som)}")
    if apagar:
        time.sleep(4)
        apagar_tela()


def cochilo(minutos=None, som: str = "") -> str:
    m = max(5.0, min(180.0, num(minutos, 20) or 20))
    quando = time.time() + m * 60
    d = dados()
    d["alarme"] = {"quando": quando, "hora": sono.hora_txt(quando), "tocado": False, "noite": False, "cochilo": True}
    _salvar(d)
    jarvis_dormir("cochilo", ate=quando, alarme=True)
    extra = ""
    if som:
        extra = " " + tocar_som(som, m)
    return (f"Cochilo de {m:g} minutos: não perturbe até as {sono.hora_txt(quando)}, aí eu toco o despertador."
            f"{extra} Responda só 'Bom cochilo, senhor.'")


def despertador(hora: str = "", cancelar: bool = False) -> str:
    d = dados()
    if cancelar or _nao(hora) or sono.sem_acento(str(hora)).lower().startswith("cancel"):
        tinha = d.get("alarme")
        d["alarme"] = None
        if d.get("noite"):
            d["noite"]["alarme"] = 0.0
        _salvar(d)
        return "Despertador cancelado." if tinha else "Não havia despertador."
    if not str(hora or "").strip():
        a = d.get("alarme")
        if a and not a.get("tocado"):
            return (f"Despertador às {a['hora']} (daqui a {duracao_txt(float(a['quando']) - time.time())}).")
        return "Nenhum despertador marcado. Diga, por exemplo, 'me acorda às 6h30'."
    alvo = sono.interpretar_hora(hora)
    if alvo is None:
        return "Que horas? (ex.: 06:30)"
    q = alvo.timestamp()
    d["alarme"] = {"quando": q, "hora": f"{alvo:%H:%M}", "tocado": False, "noite": bool(d.get("noite"))}
    if d.get("noite"):
        d["noite"]["alarme"] = q
    _salvar(d)
    return (f"Despertador às {alvo:%H:%M} (daqui a {duracao_txt(q - time.time())}). Na hora de dormir, diga "
            "'Jarvis, vou dormir' que eu cuido do resto. O PC precisa ficar ligado (a tela pode apagar).")


def soneca(minutos=None) -> str:
    m = max(1.0, min(60.0, num(minutos, SONECA_MIN) or SONECA_MIN))
    d = dados()
    agora = time.time()
    r = d.get("reabrir")
    if r and agora - float(r.get("fechou") or 0) < 30 * 60:     # reabre a noite que o despertador fechou
        noite = r["noite"]
        noite["sonecas"] = int(noite.get("sonecas") or 0) + 1
        d["noites"] = [n for n in d["noites"] if abs(float(n.get("deitou") or 0) - float(noite["deitou"])) > 1]
        d["noite"], d["reabrir"] = noite, None
    quando = agora + m * 60
    d["alarme"] = {"quando": quando, "hora": sono.hora_txt(quando), "tocado": False, "noite": bool(d.get("noite"))}
    if d.get("noite"):
        d["noite"]["alarme"] = quando
    _salvar(d)
    if str(_c().get("som_despertador")).startswith("mus"):
        try:
            from core import registro_ferramentas
            registro_ferramentas.executar("musica", {"action": "pausar"})
        except Exception:
            pass
    jarvis_dormir("soneca", ate=quando, rotina=bool(d.get("noite")), alarme=True)
    return f"Soneca: toco de novo às {sono.hora_txt(quando)}. Responda só 'Mais {m:g} minutos, senhor.'"


def relatorio(player=None) -> str:
    d = dados()
    c = _c()
    meta = num(c.get("meta_horas"), 8) or 8
    e = estatisticas(d["noites"], meta_h=meta)
    if not e.get("n"):
        return ("Ainda não tenho noites registradas. À noite diga 'Jarvis, vou dormir' que eu anoto sozinho, ou "
                "conte: 'dormi das 23h às 7h'.")
    ult = d["noites"][-1]
    linhas = [f"Última noite: {sono.hora_txt(ult['deitou'])} → {sono.hora_txt(ult['acordou'])} "
              f"({duracao_txt(float(ult['acordou']) - float(ult['deitou']))}"
              + (f", {ult['sonecas']} soneca(s)" if ult.get("sonecas") else "")
              + (f", acordou {ult['acordadas']}x de madrugada" if ult.get("acordadas") else "") + ")",
              f"Média de {e['n']} noite(s): {duracao_txt(e['media_s'])} (meta {meta:g}h)",
              f"Menor {duracao_txt(e['menor_s'])} · maior {duracao_txt(e['maior_s'])}",
              f"Deita em média às {e['deitar_medio']} (varia ±{e['desvio_min']:.0f} min)"]
    if e["divida_s"] >= 1800:
        linhas.append(f"Dívida de sono na semana: {duracao_txt(e['divida_s'])}")
    mostrar(player, "SONO", "\n".join(linhas))
    dica = ""
    if e["divida_s"] >= 3 * 3600:
        dica = " Dica: deitar uns 30 minutos mais cedo esta semana já ajuda."
    elif e["desvio_min"] >= 60:
        dica = " Dica: o horário de deitar está variando muito; um horário fixo ajuda a dormir melhor."
    return "; ".join(linhas) + "." + dica


def registrar_noite(inicio: str, fim: str) -> str:
    r = noite_manual(inicio, fim)
    if r is None:
        return "Não entendi os horários. Exemplo: 'dormi das 23h30 às 7h'."
    d = dados()
    d["noites"].append({"deitou": r[0], "acordou": r[1], "como": "anotado", "sonecas": 0})
    d["noites"].sort(key=lambda n: float(n.get("deitou") or 0))
    _salvar(d)
    return f"Anotado: {sono.hora_txt(r[0])} às {sono.hora_txt(r[1])}, {duracao_txt(r[1] - r[0])} de sono."


def status() -> str:
    d = dados()
    partes = []
    a = d.get("alarme")
    if a and not a.get("tocado"):
        partes.append(f"despertador às {a['hora']}")
    if d.get("noite"):
        partes.append(f"noite começou às {sono.hora_txt(d['noite']['deitou'])}")
    if som_tocando():
        partes.append(f"tocando {ROTULO_SOM.get(_som['nome'], _som['nome'])} até {sono.hora_txt(_som['ate'])}")
    hd = str(_c().get("hora_dormir") or "").strip()
    if hd:
        partes.append(f"lembrete da hora de dormir às {hd}")
    partes.append(_como_acordar())
    return "Modo dormir: " + "; ".join(partes)


# ── acordar: despertador e bom dia ───────────────────────────────────────────
def _pegar_alarme() -> dict | None:
    """Marca o despertador como tocado — uma vez só, mesmo com duas threads chegando juntas."""
    with _lock:
        d = dados()
        a = d.get("alarme")
        if not a or a.get("tocado"):
            return None
        a["tocado"] = True
        a["tocou_em"] = time.time()
        _salvar(d)
        return dict(a)


def tocar_alarme() -> None:
    c = _c()
    if str(c.get("som_despertador")).startswith("mus"):
        try:
            from core import registro_ferramentas
            registro_ferramentas.executar("musica", {"action": "tocar", "pedido":
                                                     str(c.get("musica_despertador") or "músicas para acordar")})
            return
        except Exception as e:
            print(f"[Sono] música do despertador: {e}")
    try:
        from plugins import _som as S
        sino = S.efeito("sino")
        for v in (0.25, 0.4, 0.6):                                  # volume subindo devagar
            S.tocar_uma(sino, 22050, v)
            time.sleep(4.2)
    except Exception as e:
        print(f"[Sono] sino do despertador: {e}")


def _bom_dia(noite_reg: dict | None, recados: list[dict], pelo_alarme: bool, depois_de_pedido: bool) -> None:
    if depois_de_pedido:
        _esperar_calar()
    perdi = ""
    try:
        from core import central_avisos
        p = central_avisos.pendentes()
        if p["fila"] or p["resumo"]:
            perdi = central_avisos.o_que_perdi(limpar=True)
    except Exception:
        pass
    c = _c()
    meta = num(c.get("meta_horas"), 8) or 8
    linhas = [f"Agora: {datetime.now():%H:%M}."]
    if noite_reg:
        dur = float(noite_reg["acordou"]) - float(noite_reg["deitou"])
        linhas.append(f"Noite: deitou {sono.hora_txt(noite_reg['deitou'])}, {duracao_txt(dur)} de sono (meta "
                      f"{meta:g}h)" + (f", {noite_reg['sonecas']} soneca(s)" if noite_reg.get("sonecas") else ""))
        e = estatisticas(dados()["noites"], meta_h=meta)
        if e.get("n", 0) >= 3:
            linhas.append(f"Média da semana: {duracao_txt(e['media_s'])}")
    extras = _clima_cambio()
    if extras:
        linhas.append(extras)
    hoje = _agenda_do_dia(datetime.now().date())
    if hoje:
        linhas.append("Hoje: " + "; ".join(hoje))
    if recados:
        linhas.append("Avisos que chegaram durante a noite:\n" + sono.lista_recados(recados))
    if perdi:
        linhas.append(perdi)
    instr = ("[BOM DIA] Você acabou de acordar" + (" o usuário com o despertador" if pelo_alarme else "") +
             ". Dados:\n" + "\n".join(linhas) + "\nDê bom dia em até 4 frases curtas, animado mas sem gritar: "
             "quanto ele dormiu (se ficou bem abaixo da meta, UMA dica curta), o clima (se tiver), o que tem hoje e "
             "o que chegou durante a noite." +
             (" Termine dizendo que 'mais 10 minutos' liga a soneca." if pelo_alarme else "") +
             (" Seja breve: ele acabou de te pedir outra coisa." if depois_de_pedido else "") +
             " Não chame nenhuma ferramenta.")
    falar(_player(), instr)


_PEDIDOS = ("comando digitado", "remote", "celular", "tecla de falar", "aviso urgente")


def _ao_acordar(info: dict) -> bool:
    """Chamado pelo core/sono quando o JARVIS sai do modo dormir. True = já falei com o usuário."""
    if not plugin_ligado("modo_dormir"):
        return False
    motivo = str(info.get("motivo") or "")
    agora = float(info.get("agora") or time.time())
    pelo_alarme = bool(info.get("alarme"))
    depois_de_pedido = any(motivo.startswith(p) for p in _PEDIDOS)
    reg, recados = None, list(info.get("recados") or [])
    with _lock:
        d = dados()
        noite = d.get("noite")
        if noite and info.get("rotina"):
            manha = pelo_alarme or (motivo != "aviso urgente" and eh_manha(float(noite["deitou"]), agora,
                                                                          float(noite.get("alarme") or 0)))
            if not manha:
                # meio da noite: guarda os avisos para o bom dia e volta a dormir sozinho
                noite.setdefault("recados", []).extend(recados)
                noite["acordadas"] = int(noite.get("acordadas") or 0) + 1
                _salvar(d)
                sono.voltar_a_dormir(VOLTA_A_DORMIR_S, ate=float(noite.get("alarme") or 0.0), rotina=True,
                                     alarme=bool(noite.get("alarme")))
                registrar(None, "😴 Acordei no meio da noite; volto a dormir em 2 min se ninguém falar comigo.")
                return True
            reg = {"deitou": float(noite["deitou"]), "acordou": agora,
                   "como": "despertador" if pelo_alarme else motivo,
                   "sonecas": int(noite.get("sonecas") or 0), "acordadas": int(noite.get("acordadas") or 0)}
            d["noites"].append(reg)
            d["noite"] = None
            d["reabrir"] = {"fechou": agora, "noite": noite}
            recados = list(noite.get("recados") or []) + recados
            if d.get("alarme") and d["alarme"].get("noite") and not pelo_alarme:
                d["alarme"] = None                          # acordou antes: o despertador da noite sai
            _salvar(d)
    tocou = pelo_alarme and _pegar_alarme() is not None     # uma vez só por despertador
    if tocou:
        parar_som(fade=2.0)
        tocar_alarme()
    if reg is not None:
        if sim(_c().get("bom_dia", True)):
            threading.Thread(target=_bom_dia, args=(reg, recados, tocou, depois_de_pedido), daemon=True,
                             name="sono_bom_dia").start()
            return True
        return False
    if pelo_alarme:                                         # cochilo / despertador sem noite
        falar(_player(), "[DESPERTADOR] Hora de levantar" + (" do cochilo" if motivo != "despertador" else "") +
              ". Avise o usuário em UMA frase animada e diga que 'mais 10 minutos' liga a soneca." +
              (" Depois conte, em até 2 frases, estes avisos que chegaram:\n" + sono.lista_recados(recados)
               if recados else "") + " Não chame nenhuma ferramenta.")
        return True
    return False


sono.ao_acordar(_ao_acordar, chave="modo_dormir")


# ── laço: despertador com o JARVIS acordado e o lembrete da hora de dormir ────
def passo(agora: float | None = None) -> None:
    agora = time.time() if agora is None else agora
    d = dados()
    a = d.get("alarme")
    if a and not a.get("tocado") and agora >= float(a["quando"]):
        if agora - float(a["quando"]) > 3 * 3600:          # o PC ficou desligado: não toca atrasado
            d["alarme"] = None
            _salvar(d)
        elif sono.dormindo():
            jarvis_acordar("despertador")                    # _ao_acordar toca e dá bom dia
        elif agora - sono.ultimo_acordar()["acordou"] > 30:   # acordado (não acabou de acordar): toca aqui
            noite = d.get("noite")
            jarvis_acordar_info = {"motivo": "despertador", "agora": agora, "alarme": True,
                                   "rotina": bool(noite), "recados": []}
            _ao_acordar(jarvis_acordar_info)
    # lembrete da hora de dormir (uma vez por noite, pela central de avisos: espera o fim do jogo/chamada)
    hd = str(_c().get("hora_dormir") or "").strip()
    if hd and not sono.dormindo() and not d.get("noite"):
        agora_dt = datetime.fromtimestamp(agora)
        chave = hora_de_dormir_vencida(hd, agora_dt)
        if chave and d.get("lembrete") != chave:
            ocioso = _ocioso()
            if ocioso is None or ocioso < 600:               # está no PC
                d["lembrete"] = chave
                _salvar(d)
                avisar(_player(), lembrete_texto(agora_dt), "HORA DE DORMIR")
    r = d.get("reabrir")
    if r and agora - float(r.get("fechou") or 0) > 30 * 60:
        d["reabrir"] = None
        _salvar(d)
    n = d.get("noite")
    if n and not sono.dormindo() and agora - float(n.get("deitou") or 0) > 16 * 3600:
        d["noite"] = None                                   # noite esquecida (JARVIS fechado de manhã): descarta
        _salvar(d)


def lembrete_texto(agora: datetime) -> str:
    """Pura (menos o despertador padrão do ⚙)."""
    c = _c()
    alarme = despertador_padrao(c.get("despertador_padrao"), sim(c.get("so_dias_uteis")), agora)
    if alarme:
        dur = alarme - agora.timestamp() - ADORMECER_MIN * 60
        return (f"Senhor, são {agora:%H:%M}, a sua hora de dormir. Deitando agora, dá {duracao_txt(dur)} de sono "
                f"até o despertador das {sono.hora_txt(alarme)}. Quando for, diga 'Jarvis, vou dormir'.")
    _n, acorda = ciclos_para_acordar(agora)[1]
    return (f"Senhor, são {agora:%H:%M}, a sua hora de dormir. Deitando agora, o melhor horário para acordar é "
            f"{acorda:%H:%M} (5 ciclos). Quando for, diga 'Jarvis, vou dormir'.")


def _laco() -> None:
    while True:
        time.sleep(15)
        try:
            passo()
        except Exception as e:
            print(f"[Sono] {e}")


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="sono_laco").start()


# ── ferramenta ───────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = sono.sem_acento(str(p.get("action") or "status")).strip().lower().replace(" ", "_")
    try:
        if a in ("dormir", "standby", "espera", "dorme"):
            return acao_dormir(p.get("minutos"), str(p.get("ate") or ""))
        if a in ("boa_noite", "vou_dormir", "noite", "deitar"):
            return boa_noite(str(p.get("acordar") or p.get("hora") or ""), str(p.get("pc") or ""),
                             str(p.get("som") or ""), p.get("minutos"))
        if a == "cochilo":
            return cochilo(p.get("minutos"), str(p.get("som") or ""))
        if a in ("despertador", "alarme"):
            return despertador(str(p.get("hora") or p.get("acordar") or ""), bool(p.get("cancelar")))
        if a == "soneca":
            return soneca(p.get("minutos"))
        if a in ("ciclos", "calcular"):
            return frase_ciclos(str(p.get("dormir_as") or ""), str(p.get("acordar_as") or ""))
        if a in ("sono", "relatorio", "como_dormi"):
            return relatorio(player)
        if a in ("registrar", "anotar"):
            return registrar_noite(str(p.get("inicio") or ""), str(p.get("fim") or ""))
        if a in ("sons", "som"):
            s = str(p.get("som") or "")
            if sono.sem_acento(s).lower().startswith(("parar", "para", "desliga", "stop")):
                return "Som desligado." if parar_som() else "Não estava tocando nenhum som."
            return tocar_som(s or "chuva", p.get("minutos") or 45)
        if a in ("parar_som", "parar"):
            return "Som desligado." if parar_som() else "Não estava tocando nenhum som."
        if a in ("respirar", "respiracao", "relaxar"):
            return respirar(str(p.get("tecnica") or "478"), p.get("ciclos"), bool(p.get("dormir_depois")))
        if a == "acordar":
            if sono.dormindo():
                jarvis_acordar("pedido")
                return "Acordei."
            return "Já estou acordado, senhor."
        return status()
    except Exception as e:
        return f"O modo dormir falhou: {e}"
