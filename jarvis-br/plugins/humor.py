"""
Humor interno (fork PT-BR 1.5).

O JARVIS tem um "estado" que muda com o seu dia — e isso muda o JEITO de
falar, não o que ele sabe nem as regras de segurança:

    manhã (até 11h)            formal e cerimonioso
    dia normal                 o J.A.R.V.I.S de sempre
    6 h+ programando hoje      sarcástico e seco ("mais um bug, senhor?")
    dia de vendas boas         animado
    muitos erros/anomalias     cuidadoso e direto
    madrugada                  calmo, preocupado com o seu sono

O estado entra nas instruções da sessão com o modelo. Quando muda, ele
reconecta (mantendo a conversa) só num momento em que você não está falando
com ele, e no máximo a cada 2 horas.

    "Jarvis, como você está hoje?"     "Jarvis, fica sempre formal"
    "Jarvis, volta o humor automático"
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from plugins._comum import MEMORIA, gravar_json, ler_json, plugin_ligado

PLUGIN = {
    "name": "humor",
    "brief": "JARVIS's internal mood (formal morning, sarcastic after long coding, cheerful on good sales...).",
    "description": (
        "Internal mood that shapes JARVIS's speaking style through the day (formal in the morning, dry sarcasm after "
        "6+ hours of coding, cheerful on a good sales day, careful when many errors, calm late at night). "
        "action='status' ('how are you today?'), 'fixar' with humor (formal|normal|sarcastico|animado|cuidadoso|calmo) "
        "to keep one, 'automatico' to go back to automatic."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "status | fixar | automatico"},
                       "humor": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "humor.json"
HUMORES = {
    "formal": "Seu humor agora é FORMAL: cerimonioso, frases completas e educadas, como um mordomo de manhã cedo.",
    "normal": "",
    "sarcastico": ("Seu humor agora é SARCÁSTICO: o usuário está programando há horas. Use ironia seca e leve, à moda "
                   "do J.A.R.V.I.S, sem ser grosseiro e sem atrapalhar a ajuda."),
    "animado": "Seu humor agora é ANIMADO: o dia está indo bem. Seja caloroso e entusiasmado, sem exagero.",
    "cuidadoso": ("Seu humor agora é CUIDADOSO: houve vários erros hoje. Seja direto, confirme os detalhes e evite "
                  "piadas."),
    "calmo": ("Seu humor agora é CALMO: é madrugada. Fale baixo e pouco, e se fizer sentido lembre o usuário de "
              "descansar."),
}
_NOME_HUMOR = {"sarcastico": "sarcástico"}
_iniciado = threading.Event()


def calcular(agora: datetime, horas_codigo: float, erros_hoje: int, vendas_hoje: float) -> tuple[str, str]:
    """(humor, motivo) — pura."""
    h = agora.hour
    if 1 <= h < 5:
        return "calmo", "é madrugada"
    if erros_hoje >= 5:
        return "cuidadoso", f"{erros_hoje} erros/anomalias hoje"
    if horas_codigo >= 6:
        return "sarcastico", f"{horas_codigo:.0f} h programando hoje"
    if vendas_hoje >= 3:
        return "animado", f"{vendas_hoje:.0f} vendas na loja hoje"
    if 5 <= h < 11:
        return "formal", "é de manhã"
    if h >= 23:
        return "calmo", "já é tarde"
    return "normal", "dia comum"


def _dados_de_hoje() -> tuple[float, int, float]:
    hoje0 = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    horas = 0.0
    try:
        from plugins import _monitor_db
        horas = sum(f["fim"] - f["inicio"] for f in _monitor_db.focos(hoje0)
                    if f.get("app") in ("VS Code", "PyCharm", "Terminal", "PowerShell")) / 3600
    except Exception:
        pass
    erros = 0
    try:
        from core import registro_uso
        erros = len(registro_uso.erros(hoje0))
        radar = (ler_json(MEMORIA / "radar.json", {}) or {}).get("historico", [])
        erros += sum(1 for a in radar if a.get("quando", 0) >= hoje0)
    except Exception:
        pass
    vendas = 0.0
    try:
        from plugins._dados_br import ler
        hoje = datetime.now().strftime("%Y-%m-%d")
        vendas = sum(1 for v in ler("cristal_vendas.csv") if str(v.get("data", "")).startswith(hoje))
    except Exception:
        pass
    return horas, erros, vendas


def atual() -> tuple[str, str]:
    e = ler_json(_ARQ, {}) or {}
    if e.get("fixo"):
        return e["fixo"], "fixado por você"
    return calcular(datetime.now(), *_dados_de_hoje())


def estilo_atual() -> str:
    """Chamado pelo main.py ao montar a sessão. '' = sem mudança de estilo."""
    try:
        if not plugin_ligado("humor"):
            return ""
        humor, motivo = atual()
        texto = HUMORES.get(humor, "")
        return f"[HUMOR INTERNO]\n{texto} (Motivo: {motivo}. Não comente isto, só deixe transparecer.)" if texto else ""
    except Exception:
        return ""


def _laco(player) -> None:
    aplicado, ultima_troca = atual()[0], time.time()
    while True:
        time.sleep(600)
        try:
            novo = atual()[0]
            if novo == aplicado or time.time() - ultima_troca < 2 * 3600:
                continue
            from core import registro_ferramentas, registro_uso
            ocupado = registro_uso.chamadas(time.time() - 300)
            falando = getattr(getattr(getattr(player, "_win", None), "hud", None), "speaking", False)
            if ocupado or falando:
                continue
            if registro_ferramentas.reconectar(f"humor: {novo}", manter_conversa=True):
                aplicado, ultima_troca = novo, time.time()
        except Exception as e:
            print(f"[Humor] {e}")


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="humor").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        e = ler_json(_ARQ, {}) or {}
        if acao == "fixar":
            humor = str(p.get("humor") or "").lower().replace("á", "a")
            humor = next((h for h in HUMORES if h.startswith(humor[:5])), "")
            if not humor:
                return "Humores: formal, normal, sarcástico, animado, cuidadoso ou calmo."
            e["fixo"] = humor
            gravar_json(_ARQ, e)
            return (f"Combinado: fico {_NOME_HUMOR.get(humor, humor)} até você mandar voltar ao automático. "
                    "Vale na próxima conexão.")
        if acao == "automatico":
            e.pop("fixo", None)
            gravar_json(_ARQ, e)
            return "Voltei ao humor automático."
        humor, motivo = atual()
        return (f"[HUMOR] Meu humor agora: {_NOME_HUMOR.get(humor, humor)} ({motivo}). Responda ao usuário nesse tom, "
                "numa frase.")
    except Exception as ex:
        return f"O humor falhou: {ex}"
