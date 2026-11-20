"""
Campanha de herói (fork PT-BR 2.7). Tudo software, grátis.

O seu dia real vira missões de uma história no estilo Homem de Ferro:
limpar o disco é "derrotar o vírus Hydra", terminar um Pomodoro é "recarregar
o reator", pagar uma conta é "proteger o cofre". Cada semana tem um vilão com
pontos de vida; cada missão tira vida dele. No domingo sai o capítulo da
semana, narrado por JARVIS, FRIDAY, o narrador e o próprio vilão.

    "Jarvis, minhas missões de hoje"     → o que você já cumpriu
    "Como está o vilão?"                 → vida do vilão da semana
    "Capítulo da semana"                 → a história da semana, encenada no palco
As missões vêm do que você já faz com o JARVIS (registro de uso) e dos commits
(gamificação). Estado em memory/campanha_heroi.json.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, num, sim

PLUGIN = {
    "name": "campanha_heroi",
    "brief": "Hero campaign: the user's real day becomes Iron-Man-style missions, a weekly villain with HP and a "
             "narrated weekly chapter.",
    "description": (
        "Gamified hero story. action: 'missoes' (missions completed today), 'vilao' (this week's villain and its "
        "HP), 'capitulo' (narrate this week's chapter on stage with JARVIS, FRIDAY, narrator and villain), "
        "'semana' (missions this week)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "campanha_heroi",
    "title": "Campanha de herói",
    "fields": [
        {"key": "domingo", "label": "Avisar do capítulo no domingo à noite", "type": "toggle", "default": True},
        {"key": "vida", "label": "Vida do vilão da semana", "type": "text", "default": "300"},
    ],
}

ARQ = MEMORIA / "campanha_heroi.json"

# (ferramenta, ação ou None) → (missão, dano)
MISSOES = {
    ("limpeza", None): ("Derrotar o vírus Hydra no disco", 30),
    ("pomodoro", None): ("Recarregar o reator arc", 20),
    ("contas", None): ("Proteger o cofre da Stark Industries", 15),
    ("rastreio", None): ("Rastrear o carregamento da S.H.I.E.L.D.", 8),
    ("garantias", None): ("Arquivar as plantas da armadura", 8),
    ("saude_pc", None): ("Diagnóstico completo da armadura", 15),
    ("snapshots", None): ("Selar o backup no bunker", 20),
    ("guarda_seguranca", None): ("Erguer o escudo contra a A.I.M.", 20),
    ("senha_vazada", None): ("Trocar os códigos de acesso", 15),
    ("detector_golpe", None): ("Desmascarar um agente infiltrado", 20),
    ("diario", None): ("Relatório para o diretor da S.H.I.E.L.D.", 10),
    ("professor_ingles", None): ("Treino de idiomas com a agente secreta", 15),
    ("modo_professor", None): ("Estudar os arquivos secretos", 15),
    ("gerador_projetos", None): ("Forjar uma nova tecnologia", 25),
    ("ditado_codigo", None): ("Programar o novo módulo da armadura", 15),
    ("painel_dev", None): ("Calibrar os sistemas da oficina", 10),
    ("cristal_malhas", None): ("Abastecer o QG da Cristal", 15),
    ("relatorio_loja", None): ("Relatório de suprimentos do QG", 10),
    ("ideias", None): ("Esboçar um protótipo no guardanapo", 5),
    ("musica", None): ("Escolher a trilha da batalha", 3),
    ("jarvis_dj", None): ("Escolher a trilha da batalha", 3),
    ("cinema", "sessao"): ("Noite de folga na Torre", 5),
    ("commit", None): ("Atualizar o firmware da armadura (commit)", 10),
}
VILOES = [("Hydra Digital", "um vírus que se multiplica nos arquivos temporários"),
          ("Ultron", "uma IA rebelde que quer dominar o seu PC"),
          ("O Mandarim do Spam", "o mestre das notificações inúteis"),
          ("Chicote Elétrico", "um sobrecarregador de processadores"),
          ("Doutor Procrastinação", "o vilão que rouba o tempo dos heróis"),
          ("A.I.M. Malware", "cientistas do mal atrás dos seus dados"),
          ("Monge de Ferro", "uma armadura rival copiada às pressas"),
          ("Barão do Bug", "o colecionador de bugs pendentes")]
_iniciou = threading.Event()


def missao_de(ferramenta: str, acao: str = "") -> tuple[str, int] | None:
    """Pura: a missão que corresponde ao uso de uma ferramenta."""
    acao = (acao or "").lower()
    return MISSOES.get((ferramenta, acao)) or MISSOES.get((ferramenta, None))


def semana_de(d: date) -> str:
    a, s, _ = d.isocalendar()
    return f"{a}-S{s:02d}"


def vilao_da_semana(d: date) -> tuple[str, str]:
    """Pura: o vilão muda toda semana (mesma semana → mesmo vilão)."""
    a, s, _ = d.isocalendar()
    return VILOES[(a * 53 + s) % len(VILOES)]


def missoes_entre(chamadas: list[dict], extras: list[dict] | None = None) -> list[dict]:
    """Pura: junta chamadas OK + extras (commits) em missões, no máximo 3 iguais por dia."""
    saida, por_dia = [], {}
    for c in list(chamadas) + list(extras or []):
        if not c.get("ok", 1):
            continue
        m = missao_de(c.get("ferramenta", ""), c.get("acao", ""))
        if not m:
            continue
        dia = datetime.fromtimestamp(c["ts"]).date().isoformat()
        k = (dia, m[0])
        por_dia[k] = por_dia.get(k, 0) + 1
        if por_dia[k] > 3:
            continue
        saida.append({"ts": c["ts"], "dia": dia, "missao": m[0], "dano": m[1]})
    return saida


def barra(vida: int, total: int, n: int = 10) -> str:
    cheio = max(0, min(n, round(n * vida / max(1, total))))
    return "█" * cheio + "░" * (n - cheio)


def _coletar(desde: float) -> list[dict]:
    chamadas = []
    try:
        from core import registro_uso
        chamadas = registro_uso.chamadas(desde)
    except Exception:
        pass
    extras = []
    try:
        from plugins import gamificacao
        extras = [{"ts": h["ts"], "ferramenta": "commit", "ok": 1} for h in gamificacao.estado().get("historico", [])
                  if str(h.get("motivo", "")).startswith("commit") and h["ts"] >= desde]
    except Exception:
        pass
    return missoes_entre(chamadas, extras)


def inicio_semana(d: date) -> float:
    return datetime.combine(d - timedelta(days=d.weekday()), datetime.min.time()).timestamp()


def status(hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    total = max(1, int(num(cfg("campanha_heroi", PLUGIN_SETTINGS).get("vida"), 300) or 300))
    ms = _coletar(inicio_semana(hoje))
    dano = sum(m["dano"] for m in ms)
    nome, descr = vilao_da_semana(hoje)
    return {"vilao": nome, "descricao": descr, "vida": max(0, total - dano), "total": total, "missoes": ms,
            "derrotado": dano >= total, "semana": semana_de(hoje)}


def texto_missoes(dia: date | None = None) -> str:
    dia = dia or date.today()
    ini = datetime.combine(dia, datetime.min.time()).timestamp()
    ms = [m for m in _coletar(ini) if m["dia"] == dia.isoformat()]
    if not ms:
        return "Nenhuma missão cumprida hoje ainda, senhor. O vilão agradece."
    return f"{len(ms)} missões hoje: " + "; ".join(f"{m['missao']} (−{m['dano']})" for m in ms[-10:]) + "."


def texto_vilao() -> str:
    s = status()
    if s["derrotado"]:
        return f"{s['vilao']} foi DERROTADO nesta semana! Parabéns, senhor. Peça o capítulo da semana."
    return (f"Vilão da semana: {s['vilao']}, {s['descricao']}. Vida {s['vida']}/{s['total']} "
            f"{barra(s['vida'], s['total'])}. {len(s['missoes'])} missões cumpridas até agora.")


def capitulo() -> str:
    from plugins import _dupla as D
    if D.rodando():
        return "Já tem uma cena rodando."
    s = status()
    resumo = "; ".join(f"{m['dia']}: {m['missao']}" for m in s["missoes"][-25:]) or "nenhuma missão ainda"
    d = ler_json(ARQ, {}) or {}
    caps = d.setdefault("capitulos", [])
    n = len(caps) + 1
    falas = D.roteiro(
        f"Capítulo {n} da campanha de herói do usuário (ele é o herói de armadura, chamado de 'senhor'). Vilão "
        f"da semana: {s['vilao']}, {s['descricao']}. Missões reais que ele cumpriu: {resumo}. Vida do vilão: "
        f"{s['vida']} de {s['total']} ({'DERROTADO' if s['derrotado'] else 'ainda de pé'}). O NARRADOR abre, "
        "JARVIS e FRIDAY relatam as missões como batalhas épicas, o VILAO ameaça (ou cai, se derrotado) e no fim "
        "anunciam o desafio da próxima semana.", ["NARRADOR", "JARVIS", "FRIDAY", "VILAO"], 10)
    if not falas:
        return "Não consegui escrever o capítulo agora (preciso da chave do Gemini). " + texto_vilao()
    caps.append({"semana": s["semana"], "vilao": s["vilao"], "derrotado": s["derrotado"],
                 "missoes": len(s["missoes"]), "data": date.today().isoformat()})
    gravar_json(ARQ, d)
    falas[0]["efeito"] = "vinheta"
    D.encenar(falas, f"Campanha de herói · Capítulo {n}", ["NARRADOR", "JARVIS", "FRIDAY", "VILAO"],
              rodape=f"{s['vilao']} · vida {s['vida']}/{s['total']}")
    mostrar(None, f"CAPÍTULO {n}", D.texto_falas(falas))
    return f"Capítulo {n} no palco. Fique em silêncio até a cena terminar."


def _laco(player) -> None:
    time.sleep(240)
    while True:
        try:
            agora = datetime.now()
            d = ler_json(ARQ, {}) or {}
            if sim(cfg("campanha_heroi", PLUGIN_SETTINGS).get("domingo", True)) and agora.weekday() == 6 \
                    and agora.hour >= 19 and d.get("aviso") != semana_de(agora.date()):
                d["aviso"] = semana_de(agora.date())
                gravar_json(ARQ, d)
                from plugins._notificar import notificar
                notificar(player, "O capítulo da semana da sua campanha de herói está pronto. " + texto_vilao(),
                          titulo="Campanha de herói", etiqueta="campanha", prioridade="baixa")
        except Exception as e:
            print(f"[Campanha] {e}")
        time.sleep(1200)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="campanha_heroi").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "vilao").lower()
    try:
        if acao == "missoes":
            return texto_missoes()
        if acao == "capitulo":
            return capitulo()
        if acao == "semana":
            ms = status()["missoes"]
            return f"{len(ms)} missões nesta semana: " + "; ".join(m["missao"] for m in ms[-15:]) if ms else \
                "Nenhuma missão nesta semana ainda."
        return texto_vilao()
    except Exception as e:
        return f"Campanha falhou: {e}"
