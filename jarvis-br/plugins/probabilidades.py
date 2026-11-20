"""
Motor de probabilidades — fork PT-BR 1.6.

"Senhor, as chances de sucesso são de 14%."

Para QUALQUER tarefa, o JARVIS calcula quatro coisas antes de agir:

    chance      probabilidade de dar certo (0–100%)
    tempo       quanto deve levar: provável (P50) e pior caso razoável (P90),
                por simulação Monte Carlo (2000 cenários por tarefa)
    possível?   "possível", "possível com condições" ou "impossível agora",
                com o motivo (sem internet, sem espaço, bloqueado, PC não aguenta…)
    perigo      nenhum · baixo · médio · alto, e a chance de algo GRAVE acontecer
                (perder arquivo, travar o PC, ação irreversível)

    "Jarvis, quanto tempo leva para instalar o Android Studio?"
    "Jarvis, dá para baixar 20 GB e jogar ao mesmo tempo?"
    "Jarvis, quais as chances de compilar o projeto sem erro?"
    "Jarvis, é perigoso apagar a pasta Temp?"
    "Jarvis, compara copiar para o pendrive vs mandar pela nuvem"
    "Jarvis, deu certo" / "deu errado, levou 10 minutos"   → ele aprende

De onde vêm os números (cada fator aparece no painel, a favor ou contra):
    1. o histórico real: quantas vezes aquela ferramenta/tipo de tarefa deu
       certo no diário (core/registro_uso.py) e nos resultados que você
       informou aqui (memory/probabilidades.json);
    2. o guardião de decisões: risco, reversível, administrador, bloqueio;
    3. o gêmeo digital: se o PC aguenta (RAM/CPU depois da tarefa);
    4. o estado agora: internet, ping, espaço em disco, temperatura;
    5. a complexidade: cada passo a mais multiplica a chance de falhar;
    6. com IA disponível, uma estimativa extra para tarefas que as regras não
       reconhecem — sempre marcada como "estimativa da IA".

A conta é em log-odds (cada fator soma ou subtrai), então dá para ver
exatamente quanto cada coisa pesou. As funções `combinar`, `monte_carlo`,
`classificar` e `extrair_tamanho` são puras (testadas).
"""

from __future__ import annotations

import math
import random
import re
import threading
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "probabilidades",
    "brief": "Chance of success (%), time estimate, feasibility and danger of any task, before doing it.",
    "description": (
        "Probability engine. action='calcular' with tarefa = the user's words (optional ferramenta and "
        "params of the tool that would run) for 'quanto tempo leva', 'é possível?', 'dá para…?', 'vai dar "
        "certo?', 'é perigoso?', 'quais as chances', and BEFORE any risky or long action. ALWAYS tell the "
        "user the success chance as a percentage ('Senhor, as chances de sucesso são de X%'), the time, "
        "whether it is possible and the danger. action='comparar' with planos separated by ' vs '. "
        "action='resultado' with deu_certo (true/false) and optional tempo_real (seconds) and id, for "
        "'deu certo', 'deu errado', 'levou X minutos' — it learns from that. action='historico' shows "
        "how accurate past predictions were."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "calcular | comparar | resultado | historico"},
            "tarefa": {"type": "STRING"}, "ferramenta": {"type": "STRING"},
            "params": {"type": "OBJECT"}, "planos": {"type": "STRING"},
            "deu_certo": {"type": "BOOLEAN"}, "tempo_real": {"type": "NUMBER"}, "id": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}

ARQUIVO = MEMORIA / "probabilidades.json"
_lock = threading.Lock()
GB = 1024 ** 3
MB = 1024 ** 2


def _d(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


# ── tipos de tarefa ───────────────────────────────────────────────────────────
# chave → (palavras, chance base, tempo (mín, provável, máx) em segundos, precisa internet,
#          precisa espaço, perigo base 0-3, rótulo)
TIPOS = {
    "abrir":      (r"\b(abr|inici|execut|rodar o|liga o)", .95, (1, 4, 20), False, False, 0, "abrir programa/site"),
    "fechar":     (r"\b(fech|encerr|finaliz|mat[ae]r? o)", .93, (1, 2, 10), False, False, 1, "fechar programa"),
    "baixar":     (r"\b(baix|download)", .88, (20, 120, 900), True, True, 0, "baixar"),
    "instalar":   (r"\b(instal|setup)", .82, (60, 240, 1200), True, True, 1, "instalar"),
    "atualizar":  (r"\b(atualiz|update|upgrade)", .85, (60, 300, 1800), True, True, 1, "atualizar"),
    "copiar":     (r"\b(copi|backup|pendrive|transfer)", .92, (5, 60, 600), False, True, 0, "copiar/backup"),
    "mover":      (r"\b(mov|renome|organiz)", .93, (2, 20, 300), False, False, 1, "mover/organizar"),
    "apagar":     (r"\b(apag|delet|exclu|remov|limp)", .95, (2, 30, 300), False, False, 2, "apagar/limpar"),
    "compilar":   (r"\b(compil|build|buildar|gerar o exe|pyinstaller)", .72, (20, 120, 900), False, True, 0,
                   "compilar"),
    "testar":     (r"\b(test|pytest|unittest)", .75, (5, 60, 600), False, False, 0, "rodar testes"),
    "renderizar": (r"\b(render|exportar o video|exportar video|codific)", .85, (120, 900, 5400), False, True, 0,
                   "renderizar vídeo"),
    "enviar":     (r"\b(envi|mand|post|public|upload)", .9, (3, 20, 300), True, False, 2, "enviar/publicar"),
    "pesquisar":  (r"\b(pesquis|procur|busc|google)", .93, (3, 10, 60), True, False, 0, "pesquisar"),
    "desligar":   (r"\b(deslig|reinici|shutdown|reboot)", .97, (10, 40, 180), False, False, 2, "desligar/reiniciar"),
    "formatar":   (r"\bformat", .9, (300, 1800, 7200), False, False, 3, "formatar"),
    "jogar":      (r"\b(jog(ar|a|ue|uei)\b|partida|game)", .9, (20, 60, 240), False, False, 0, "abrir jogo"),
    "esp32":      (r"\b(esp32|arduino|gravar o firmware|upload do sketch|\.ino)", .7, (20, 60, 300), False, False, 1,
                   "gravar no ESP32"),
    "programar":  (r"\b(program|codar|criar (um|o) (app|site|sistema|plugin)|desenvolv)", .65,
                   (1800, 4 * 3600, 20 * 3600), False, False, 0, "programar algo novo"),
}

# Velocidades de partida (bytes/s) até o diário ter medidas reais.
VEL_INTERNET = 5 * MB
VEL_DISCO_MESMO = 400 * MB
VEL_DISCO_OUTRO = 80 * MB


def classificar(tarefa: str) -> list[str]:
    """Tipos de tarefa reconhecidos, na ordem em que aparecem. Pura."""
    t = _d(tarefa)
    achados = []
    for chave, (padrao, *_r) in TIPOS.items():
        m = re.search(padrao, t)
        if m:
            achados.append((m.start(), chave))
    return [k for _p, k in sorted(achados)]


def dividir_passos(tarefa: str) -> list[str]:
    """'baixar o jogo e depois instalar, e abrir' → 3 passos. Pura."""
    partes = re.split(r",|;|\be depois\b|\bdepois\b|\be ent[aã]o\b|\be em seguida\b|\be\b(?= (?:abr|baix|instal|"
                      r"copi|mov|apag|compil|test|render|envi|pesquis|deslig|reinic|jog|grav|atualiz|fech))",
                      tarefa or "", flags=re.I)
    return [p.strip() for p in partes if p and p.strip()] or [tarefa]


def extrair_tamanho(texto: str) -> float | None:
    """'20 GB' → bytes. Pura."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(tb|gb|g|mb|m|kb)\b", _d(texto))
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    return n * {"tb": 1024 ** 4, "gb": GB, "g": GB, "mb": MB, "m": MB, "kb": 1024}[m.group(2)]


# ── matemática ────────────────────────────────────────────────────────────────
def _logit(p: float) -> float:
    p = min(.995, max(.005, p))
    return math.log(p / (1 - p))


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def combinar(base: float, fatores: list[dict]) -> float:
    """Chance final = base em log-odds + soma dos efeitos dos fatores. Pura."""
    return _sig(_logit(base) + sum(f["efeito"] for f in fatores))


def monte_carlo(passos: list[tuple[float, float, float]], n: int = 2000, semente: int = 7) -> dict:
    """Soma de durações triangulares por passo → P10/P50/P90 em segundos. Pura."""
    if not passos:
        return {"p10": 0, "p50": 0, "p90": 0}
    rnd = random.Random(semente)
    totais = sorted(sum(rnd.triangular(a, c, b) for a, b, c in passos) for _ in range(n))
    return {"p10": totais[int(.1 * n)], "p50": totais[int(.5 * n)], "p90": totais[int(.9 * n)]}


def falar_tempo(seg: float) -> str:
    seg = max(0, float(seg))
    if seg < 60:
        return f"{max(1, round(seg))} segundo{'s' if round(seg) != 1 else ''}"
    if seg < 3600:
        m = round(seg / 60)
        return f"{m} minuto{'s' if m != 1 else ''}"
    if seg < 86400:
        h = seg / 3600
        return f"{h:.1f} horas".replace(".0 ", " ").replace(".", ",")
    return f"{seg / 86400:.1f} dias".replace(".", ",")


# ── aprendizado ───────────────────────────────────────────────────────────────
def _dados() -> dict:
    d = ler_json(ARQUIVO, None)
    return d if isinstance(d, dict) else {"tipos": {}, "previsoes": []}


def _historico_tipo(chave: str) -> tuple[int, int, list[float]]:
    """(acertos, falhas, durações reais) do que você informou + do diário."""
    ok = falha = 0
    tempos: list[float] = []
    t = _dados()["tipos"].get(chave) or {}
    ok += int(t.get("ok", 0))
    falha += int(t.get("falha", 0))
    tempos += [float(x) for x in t.get("tempos", [])][-30:]
    return ok, falha, tempos


def _historico_ferramenta(ferramenta: str) -> tuple[int, int, list[float]]:
    if not ferramenta:
        return 0, 0, []
    try:
        from core import registro_uso
        ch = registro_uso.chamadas(time.time() - 60 * 86400, ferramenta=ferramenta)
    except Exception:
        return 0, 0, []
    ok = sum(1 for c in ch if c.get("ok"))
    return ok, len(ch) - ok, [c["ms"] / 1000 for c in ch if c.get("ms")][-50:]


def _quantis(vals: list[float]) -> tuple[float, float, float] | None:
    if len(vals) < 3:
        return None
    v = sorted(vals)
    return v[0], v[len(v) // 2], v[min(len(v) - 1, int(.9 * len(v)))]


# ── estado do PC ──────────────────────────────────────────────────────────────
def _estado() -> dict:
    try:
        from core import telemetria
        s = telemetria.get().snapshot()
    except Exception:
        return {}
    return {
        "internet": s.get("internet"),
        "ping": ((s.get("ping") or {}).get("8.8.8.8") or {}).get("ms"),
        "livre_min": min((100 - p["pct"] for p in s.get("particoes") or []), default=None),
        "livre_bytes": min((p.get("livre") or 0 for p in s.get("particoes") or [] if p.get("livre")), default=None),
        "temp": s.get("cpu_temp"), "ram_pct": (s.get("ram") or {}).get("pct"), "_snap": s,
    }


# ── cálculo ───────────────────────────────────────────────────────────────────
def _fator(nome: str, efeito: float, explicacao: str) -> dict:
    return {"nome": nome, "efeito": round(efeito, 3), "lado": "a favor" if efeito > 0 else "contra",
            "explicacao": explicacao}


def calcular(tarefa: str, ferramenta: str = "", params: dict | None = None, estado: dict | None = None,
             usar_ia: bool = True) -> dict:
    tarefa = str(tarefa or "").strip()
    params = params or {}
    e = _estado() if estado is None else estado
    passos_txt = dividir_passos(tarefa)
    fatores: list[dict] = []
    impedimentos: list[str] = []
    condicoes: list[str] = []
    duracoes: list[tuple[float, float, float]] = []
    tipos_todos: list[str] = []
    chance_passos: list[float] = []
    perigo = 0
    reconhecido = False
    tamanho = extrair_tamanho(tarefa)

    for passo in passos_txt:
        tipos = classificar(passo) or (classificar(ferramenta) if ferramenta else [])
        chave = tipos[0] if tipos else "desconhecido"
        tipos_todos.append(chave)
        if chave == "desconhecido":
            base, dur, net, espaco, pg, rot = .7, (10, 60, 600), False, False, 1, "tarefa desconhecida"
        else:
            reconhecido = True
            _pad, base, dur, net, espaco, pg, rot = TIPOS[chave]
        perigo = max(perigo, pg)

        # 1) histórico: Beta(base*4 + acertos, (1-base)*4 + falhas)
        ok, falha, tempos = _historico_tipo(chave)
        ok2, falha2, tempos2 = _historico_ferramenta(ferramenta) if len(passos_txt) == 1 else (0, 0, [])
        ok, falha, tempos = ok + ok2, falha + falha2, tempos + tempos2
        p_passo = (base * 4 + ok) / (4 + ok + falha)
        if ok + falha:
            fatores.append(_fator(f"histórico de '{rot}'", _logit(p_passo) - _logit(base),
                                  f"{ok} de {ok + falha} vezes deu certo"))
        chance_passos.append(p_passo)

        # 2) duração: medida real > tamanho informado > tabela
        q = _quantis(tempos)
        if q:
            dur = q
        elif tamanho and chave in ("baixar", "instalar", "atualizar", "copiar", "enviar"):
            vel = VEL_INTERNET if chave in ("baixar", "instalar", "atualizar", "enviar") else VEL_DISCO_OUTRO
            prov = tamanho / vel
            dur = (prov * .6, prov, prov * 2.5)
        duracoes.append(dur)

        # 3) internet
        if net:
            if e.get("internet") is False:
                impedimentos.append(f"'{rot}' precisa de internet e a internet está fora")
            elif e.get("ping") and e["ping"] > 150:
                fatores.append(_fator("internet lenta", -.5, f"ping de {round(e['ping'])} ms"))
            elif e.get("internet"):
                fatores.append(_fator("internet ok", .15, "conexão funcionando agora"))

        # 4) espaço em disco
        if espaco and e.get("livre_bytes") is not None:
            if tamanho and e["livre_bytes"] < tamanho * 1.1:
                impedimentos.append(f"falta espaço: precisa de ~{tamanho / GB:.1f} GB e o disco mais cheio "
                                    f"tem {e['livre_bytes'] / GB:.1f} GB livres".replace(".", ","))
            elif e.get("livre_min") is not None and e["livre_min"] < 8:
                fatores.append(_fator("disco quase cheio", -.8, f"só {round(e['livre_min'])}% livre"))

    # 5) complexidade: a chance da tarefa toda é o produto dos passos
    base_total = math.prod(chance_passos) if chance_passos else .7
    if len(passos_txt) > 1:
        condicoes.append(f"{len(passos_txt)} passos em sequência; se um falhar, os seguintes esperam")

    # 6) guardião de decisões
    guardiao_txt = ""
    reversivel = True
    try:
        from plugins import _guardiao
        av = _guardiao.avaliar(ferramenta, params, tarefa)
        guardiao_txt = av.texto()
        reversivel = av.reversivel
        perigo = max(perigo, av.risco)
        if av.decisao == "bloquear":
            impedimentos.append("o guardião bloqueia: " + ("; ".join(av.motivos) or "ação protegida"))
        elif av.decisao == "confirmar":
            condicoes.append("precisa da sua confirmação antes")
        if av.admin:
            fatores.append(_fator("precisa de administrador", -.3, "pode falhar sem permissão de administrador"))
    except Exception:
        pass

    # 7) gêmeo digital: o PC aguenta?
    apps = [p for p, t in zip(passos_txt, tipos_todos) if t in ("abrir", "jogar", "renderizar", "compilar")]
    if apps and e.get("_snap"):
        try:
            from plugins import gemeo_digital as gd
            alvos = []
            for p in apps:
                alvos += gd.dividir(re.sub(r"^\s*(abrir|abre|jogar|joga|renderizar|compilar)\s+", "", p, flags=re.I))
            r = gd.prever(alvos, e["_snap"], gd.carregar())
            if r["risco"] == "alto":
                fatores.append(_fator("PC no limite", -1.3, f"RAM iria a {round(r['ram_pct'])}%, CPU a "
                                                            f"{round(r['cpu_pct'])}%"))
                if r["ram_pct"] > 130:
                    impedimentos.append("o PC não tem RAM para isso tudo junto")
                elif r["fechar"]:
                    condicoes.append("fechar " + ", ".join(f["nome"] for f in r["fechar"][:3]))
            elif r["risco"] == "médio":
                fatores.append(_fator("PC apertado", -.5, f"RAM iria a {round(r['ram_pct'])}%"))
            else:
                fatores.append(_fator("PC folgado", .3, f"RAM iria a {round(r['ram_pct'])}%"))
        except Exception:
            pass

    # 8) temperatura em tarefa pesada
    if e.get("temp") and e["temp"] >= 88 and any(t in ("renderizar", "compilar", "jogar") for t in tipos_todos):
        fatores.append(_fator("PC quente", -.6, f"CPU a {round(e['temp'])} °C"))
        perigo = max(perigo, 1)

    # 9) IA para o que as regras não reconhecem
    fonte = "regras + histórico medido"
    ia_info = None
    if usar_ia and not reconhecido:
        try:
            from plugins import _ia
            r = _ia.perguntar_json(
                "Estime de forma realista para um usuário de PC Windows a tarefa: \"" + tarefa + "\". Responda SÓ "
                "JSON: {\"chance\": 0-100, \"tempo_min_s\": n, \"tempo_provavel_s\": n, \"tempo_max_s\": n, "
                "\"possivel\": true/false, \"perigo\": 0-3, \"motivos\": [\"...\"]} em português do Brasil.",
                False, 30)
            if isinstance(r, dict) and r.get("chance") is not None:
                ia_info = r
                base_total = (base_total + float(r["chance"]) / 100) / 2
                duracoes = [(float(r.get("tempo_min_s") or 10), float(r.get("tempo_max_s") or 600),
                             float(r.get("tempo_provavel_s") or 60))]
                duracoes = [(a, c, b) for a, b, c in duracoes]   # (mín, provável, máx)
                perigo = max(perigo, int(r.get("perigo") or 0))
                if r.get("possivel") is False:
                    condicoes.append("a IA acha que não é possível do jeito pedido")
                fonte = "estimativa da IA + regras (tarefa fora do catálogo)"
        except Exception:
            pass

    vistos: set = set()                       # o mesmo fator em vários passos conta uma vez só
    fatores = [f for f in fatores if not (f["nome"] in vistos or vistos.add(f["nome"]))]
    chance = combinar(base_total, fatores)
    chance_base = chance
    if impedimentos:
        chance = min(chance, .03)
    # (mín, provável, máx) → monte_carlo recebe (a, b, c) = (mín, máx, provável)
    tempo = monte_carlo([(a, c, b) for a, b, c in duracoes])

    if impedimentos:
        viab = "impossível agora"
    elif condicoes:
        viab = "possível com condições"
    else:
        viab = "possível"

    sev = {0: .0, 1: .15, 2: .45, 3: .9}[min(3, perigo)] * (1.0 if not reversivel else .5)
    grave = (1 - chance) * sev
    nivel = ("nenhum", "baixo", "médio", "alto")[min(3, perigo)]

    return {
        "tarefa": tarefa, "passos": passos_txt, "tipos": tipos_todos, "chance": chance, "chance_base": chance_base,
        "tempo": tempo, "viabilidade": viab, "impedimentos": impedimentos, "condicoes": condicoes,
        "perigo": nivel, "perigo_n": min(3, perigo), "chance_grave": grave, "reversivel": reversivel,
        "fatores": fatores, "fonte": fonte, "guardiao": guardiao_txt, "ia": ia_info,
    }


def texto(r: dict, senhor: bool = True) -> str:
    pct = round(100 * r["chance"])
    abertura = "Senhor, as" if senhor else "As"
    if r["viabilidade"] == "impossível agora":
        return (f"{abertura} chances de sucesso são de {pct}%: é impossível agora, porque "
                + "; ".join(r["impedimentos"]) + ".")
    t = r["tempo"]
    partes = [f"{abertura} chances de sucesso são de {pct}%."]
    if t["p50"]:
        partes.append(f"Deve levar uns {falar_tempo(t['p50'])}" +
                      (f", até {falar_tempo(t['p90'])} no pior caso." if t["p90"] > t["p50"] * 1.3 else "."))
    partes.append(f"É {r['viabilidade']}" + (f": {'; '.join(r['condicoes'])}." if r["condicoes"] else "."))
    if r["perigo_n"] == 0:
        partes.append("Sem perigo.")
    else:
        partes.append(f"Perigo {r['perigo']}; chance de algo grave: {max(1, round(100 * r['chance_grave']))}%"
                      + ("" if r["reversivel"] else ", e não dá para desfazer") + ".")
    contra = sorted((f for f in r["fatores"] if f["efeito"] < 0), key=lambda f: f["efeito"])
    if contra:
        partes.append(f"O que mais pesa contra: {contra[0]['nome']} ({contra[0]['explicacao']}).")
    return " ".join(partes)


def painel(r: dict) -> str:
    t = r["tempo"]
    linhas = [f"CHANCE DE SUCESSO   {round(100 * r['chance'])}%",
              f"TEMPO               provável {falar_tempo(t['p50'])} · melhor {falar_tempo(t['p10'])} · "
              f"pior {falar_tempo(t['p90'])}",
              f"VIABILIDADE         {r['viabilidade']}",
              f"PERIGO              {r['perigo']} · algo grave: {round(100 * r['chance_grave'])}% · "
              f"{'reversível' if r['reversivel'] else 'IRREVERSÍVEL'}",
              f"FONTE               {r['fonte']}", "",
              "PASSOS"] + [f"  {i}. {p}  [{k}]" for i, (p, k) in enumerate(zip(r["passos"], r["tipos"]), 1)]
    if r["fatores"]:
        linhas += ["", "FATORES (peso em log-odds)"]
        for f in sorted(r["fatores"], key=lambda f: -abs(f["efeito"])):
            barra = ("+" if f["efeito"] > 0 else "-") * max(1, min(10, round(abs(f["efeito"]) * 4)))
            linhas.append(f"  {f['lado']:<8} {barra:<10} {f['nome']}: {f['explicacao']}")
    if r["impedimentos"]:
        linhas += ["", "IMPEDIMENTOS"] + [f"  ✖ {x}" for x in r["impedimentos"]]
    if r["condicoes"]:
        linhas += ["", "CONDIÇÕES"] + [f"  • {x}" for x in r["condicoes"]]
    if r["guardiao"]:
        linhas += ["", "GUARDIÃO: " + r["guardiao"]]
    return "\n".join(linhas)


def _registrar_previsao(r: dict) -> int:
    with _lock:
        d = _dados()
        nid = (max((p["id"] for p in d["previsoes"]), default=0) + 1)
        d["previsoes"].append({"id": nid, "ts": time.time(), "tarefa": r["tarefa"][:200], "tipos": r["tipos"],
                               "chance": round(r["chance"], 3), "p50": round(r["tempo"]["p50"], 1),
                               "resultado": None, "tempo_real": None})
        d["previsoes"] = d["previsoes"][-300:]
        gravar_json(ARQUIVO, d)
    return nid


def registrar_resultado(deu_certo: bool, tempo_real: float | None = None, pid: int | None = None) -> str:
    with _lock:
        d = _dados()
        pendentes = [p for p in d["previsoes"] if p["resultado"] is None]
        alvo = next((p for p in d["previsoes"] if p["id"] == pid), None) if pid else \
            (pendentes[-1] if pendentes else None)
        if not alvo:
            return "Não tenho nenhuma previsão pendente para anotar."
        alvo["resultado"] = bool(deu_certo)
        alvo["tempo_real"] = float(tempo_real) if tempo_real else None
        for k in alvo["tipos"]:
            t = d["tipos"].setdefault(k, {"ok": 0, "falha": 0, "tempos": []})
            t["ok" if deu_certo else "falha"] += 1
            if tempo_real and len(alvo["tipos"]) == 1:
                t["tempos"] = (t["tempos"] + [float(tempo_real)])[-30:]
        gravar_json(ARQUIVO, d)
    previsto = round(100 * alvo["chance"])
    msg = f"Anotado: '{alvo['tarefa'][:60]}' {'deu certo' if deu_certo else 'deu errado'} (eu tinha previsto {previsto}%)."
    if tempo_real and alvo.get("p50"):
        msg += f" Levou {falar_tempo(tempo_real)}; eu tinha estimado {falar_tempo(alvo['p50'])}."
    return msg + " Vou usar isso nas próximas contas."


def precisao() -> dict:
    d = _dados()
    feitas = [p for p in d["previsoes"] if p["resultado"] is not None]
    if not feitas:
        return {"n": 0}
    brier = sum((p["chance"] - (1 if p["resultado"] else 0)) ** 2 for p in feitas) / len(feitas)
    acertos = sum(1 for p in feitas if (p["chance"] >= .5) == p["resultado"])
    return {"n": len(feitas), "brier": brier, "acerto": acertos / len(feitas)}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = _d(p.get("action") or "calcular")
    try:
        if a == "calcular":
            tarefa = str(p.get("tarefa") or "").strip()
            if not tarefa:
                return "Qual tarefa devo calcular?"
            r = calcular(tarefa, str(p.get("ferramenta") or ""), p.get("params") or {})
            nid = _registrar_previsao(r)
            mostrar(player, f"PROBABILIDADES #{nid} — {tarefa[:36].upper()}", painel(r))
            return texto(r)
        if a == "comparar":
            planos = [x.strip() for x in re.split(r"\bvs\.?\b|\bversus\b|\bou\b", str(p.get("planos") or ""))
                      if x.strip()]
            if len(planos) < 2:
                return "Diga dois planos para comparar, separados por 'vs'."
            rs = [calcular(x) for x in planos]
            mostrar(player, "PROBABILIDADES — COMPARAÇÃO",
                    "\n\n".join(f"### {r['tarefa']}\n{painel(r)}" for r in rs))

            def nota(r):  # chance alta, pouco tempo e pouco perigo
                return r["chance"] - .25 * r["chance_grave"] - .02 * math.log1p(r["tempo"]["p50"] / 60)
            melhor = max(rs, key=nota)
            resumo = " | ".join(f"{r['tarefa']}: {round(100 * r['chance'])}%, ~{falar_tempo(r['tempo']['p50'])}, "
                                f"perigo {r['perigo']}" for r in rs)
            return f"{resumo}. Senhor, eu iria de '{melhor['tarefa']}'."
        if a == "resultado":
            if p.get("deu_certo") is None:
                return "Deu certo ou deu errado?"
            pid = int(float(p["id"])) if p.get("id") not in (None, "") else None
            return registrar_resultado(bool(p["deu_certo"]), p.get("tempo_real"), pid)
        if a == "historico":
            pr = precisao()
            if not pr["n"]:
                return "Ainda não tenho resultados para medir minha precisão. Me diga 'deu certo' ou 'deu errado' depois das tarefas."
            return (f"Em {pr['n']} previsões com resultado, acertei o lado em {round(100 * pr['acerto'])}% "
                    f"(erro de Brier {pr['brier']:.2f}; quanto mais perto de 0, melhor).")
        return "Use calcular, comparar, resultado ou historico."
    except Exception as e:
        return f"O motor de probabilidades falhou: {e}"
