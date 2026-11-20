"""
JARVIS que evolui sozinho (fork PT-BR 2.4).

Ele testa, discretamente, jeitos diferentes de fazer a mesma coisa:

    tamanho   resposta curta  × resposta mais completa
    tom       formal          × descontraído
    ordem     resposta antes  × passos antes

A cada período de uso (uns 40 minutos de conversa) ele sorteia uma
combinação e põe nas instruções da sessão. Depois OBSERVA como você reage à
resposta seguinte:

    você interrompeu ele falando ................ ruim
    "não, não foi isso" / "tá errado" ........... ruim (corrigiu)
    "repete" / "o quê?" / "não entendi" ......... ruim (pediu de novo)
    "resume" / "mais curto" ..................... ruim para a resposta longa
    "explica melhor" / "mais detalhes" .......... ruim para a resposta curta
    "valeu" / "perfeito" / "isso mesmo" ......... bom
    seguiu a conversa normalmente ............... um pouco bom

Cada jeito tem uma nota (distribuição Beta) e o sorteio é por amostragem de
Thompson: quem funciona aparece cada vez mais e quem não funciona some
sozinho — evolução por seleção natural, sem você configurar nada.

Fica em memory/evolucao.json. "Jarvis, o que você aprendeu sobre o meu jeito?"
mostra o placar. Nunca mexe em regra de segurança: só no JEITO de falar.
"""

from __future__ import annotations

import random
import re
import threading
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json

ARQ = MEMORIA / "evolucao.json"
PERIODO_S = 40 * 60

DIMENSOES: dict[str, dict[str, str]] = {
    "tamanho": {
        "curta": "Prefira respostas CURTAS: uma ou duas frases, só o essencial; ofereça detalhes se ele quiser.",
        "completa": "Prefira respostas um pouco mais COMPLETAS: responda e dê o contexto útil em poucas frases.",
    },
    "tom": {
        "formal": "Tom formal e cerimonioso, como um mordomo britânico ('senhor').",
        "descontraido": "Tom descontraído e próximo, como um amigo que sabe muito, sem perder o respeito.",
    },
    "ordem": {
        "resposta_antes": "Comece SEMPRE pela resposta ou conclusão; o porquê e os passos vêm depois.",
        "passos_antes": "Quando houver passos, diga os passos em ordem primeiro e a conclusão no final.",
    },
    # Fork PT-BR 2.21: genes novos — humor e fechamento também evoluem com você.
    "humor": {
        "com_tirada": "Quando couber, solte UMA tirada leve ou referência geek por resposta (nunca em assunto sério).",
        "sem_tirada": "Sem piadas nem tiradas: humor só se ele puxar.",
    },
    "fechamento": {
        "proximo_passo": "Termine sugerindo, em poucas palavras, o próximo passo útil.",
        "so_resposta": "Termine na resposta, sem oferecer mais nada.",
    },
}
NOMES = {"curta": "respostas curtas", "completa": "respostas mais completas", "formal": "tom formal",
         "descontraido": "tom descontraído", "resposta_antes": "a resposta primeiro",
         "passos_antes": "os passos primeiro", "com_tirada": "uma tirada de humor", "sem_tirada": "sem piadas",
         "proximo_passo": "sugerir o próximo passo", "so_resposta": "só a resposta"}

_lock = threading.Lock()
_mem: dict = {"pendente": None}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── regras (puras, nos testes) ───────────────────────────────────────────────
SINAIS = [
    ("repetir", r"\b(repete|repita|fala de novo|fala outra vez|nao entendi|o que voce disse|hein|como e que e)\b|^(o que|oi|ha|que)\??$"),
    ("corrigir", r"^(nao|errado)\b(?!$)(?! (obrigad|precis|quero|valeu|pode|agora|tudo|sei))|\b(ta errado|esta errado|nao foi isso|nao e isso|nao era isso|entendeu errado|"
                 r"voce errou|nao foi o que eu pedi)\b"),
    ("mais_curto", r"\b(resume|resumindo|mais curto|menos texto|direto ao ponto|fala menos|so a resposta|para de falar|"
                   r"chega|ja entendi)\b"),
    ("mais_longo", r"\b(explica melhor|mais detalhes|detalha|explica mais|aprofunda|me explica direito|so isso\?)\b"),
    ("elogio", r"\b(valeu|obrigad[oa]|perfeito|show|isso mesmo|exatamente|top|boa jarvis|muito bom|otimo)\b"),
    ("riso", r"\b(k{3,}|(ha){2,}|rsrs|kkk\w*)\b"),
    ("aceitou", r"^(sim|pode|faz|bora|manda ver|pode fazer|faz isso|isso ai)\b"),
]


def sinal(texto: str) -> str:
    """Como você reagiu à resposta anterior: 'repetir', 'corrigir', 'mais_curto', 'mais_longo', 'elogio' ou '' (pura)."""
    t = re.sub(r"[!.,]+", " ", _dobrar(texto)).strip()
    t = re.sub(r"\s+", " ", t)
    for nome, padrao in SINAIS:
        if re.search(padrao, t):
            return nome
    return ""


def recompensas(sig: str, atual: dict[str, str], interrompido: bool = False) -> dict[str, tuple[float, float]]:
    """{dimensão: (recompensa 0..1, peso)} para a combinação que estava valendo (pura)."""
    dims = list(atual)
    if interrompido:
        r = {d: (0.0, 0.6) for d in dims}
        if atual.get("tamanho") == "completa":
            r["tamanho"] = (0.0, 1.0)
        return r
    if sig in ("repetir", "corrigir"):
        return {d: (0.0, 1.0) for d in dims}
    if sig == "mais_curto":
        return {"tamanho": (0.0, 1.0)} if atual.get("tamanho") == "completa" else {"tamanho": (0.3, 0.5)}
    if sig == "mais_longo":
        return {"tamanho": (0.0, 1.0)} if atual.get("tamanho") == "curta" else {"tamanho": (0.3, 0.5)}
    if sig == "elogio":
        return {d: (1.0, 1.0) for d in dims}
    if sig == "riso":                                         # 2.21: riu → a tirada funcionou; sem tirada, riu de outra coisa
        return {"humor": (1.0, 1.0) if atual.get("humor") == "com_tirada" else (0.6, 0.3)}
    if sig == "aceitou":                                      # 2.21: aceitou a sugestão do próximo passo
        return {"fechamento": (1.0, 1.0) if atual.get("fechamento") == "proximo_passo" else (0.6, 0.3)}
    return {d: (1.0, 0.3) for d in dims}                      # seguiu normalmente: um pouco bom


def nota(p: dict) -> float:
    return (p["a"]) / (p["a"] + p["b"])


def sortear(placar: dict, rng: random.Random | None = None) -> dict[str, str]:
    """Amostragem de Thompson em cada dimensão (pura com rng)."""
    rng = rng or random.Random()
    escolha = {}
    for dim, vars_ in DIMENSOES.items():
        p = placar.get(dim, {})
        escolha[dim] = max(vars_, key=lambda v: rng.betavariate(p.get(v, {}).get("a", 1.0),
                                                                 p.get(v, {}).get("b", 1.0)))
    return escolha


def melhores(placar: dict) -> dict[str, str]:
    return {dim: max(vars_, key=lambda v: nota(placar.get(dim, {}).get(v, {"a": 1, "b": 1})))
            for dim, vars_ in DIMENSOES.items()}


def aplicar(placar: dict, atual: dict[str, str], rec: dict[str, tuple[float, float]]) -> None:
    for dim, (r, peso) in rec.items():
        v = atual.get(dim)
        if not v:
            continue
        p = placar.setdefault(dim, {}).setdefault(v, {"a": 1.0, "b": 1.0, "n": 0})
        p["a"] += r * peso
        p["b"] += (1 - r) * peso
        p["n"] = p.get("n", 0) + 1


# ── estado ───────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("ativo", True)
    d.setdefault("placar", {})
    d.setdefault("atual", {})
    d.setdefault("desde", 0.0)
    d.setdefault("fixo", {})
    d.setdefault("turnos", 0)
    return d


def _salvar(d: dict) -> None:
    gravar_json(ARQ, d)


def combinacao_atual(agora: float | None = None) -> dict[str, str]:
    """Troca a combinação a cada período de uso (ou mantém as fixadas)."""
    agora = agora or time.time()
    with _lock:
        d = dados()
        if not d["atual"] or agora - d["desde"] > PERIODO_S or set(d["atual"]) != set(DIMENSOES):
            d["atual"] = sortear(d["placar"]) if d["ativo"] else melhores(d["placar"])
            d["desde"] = agora
        d["atual"].update({k: v for k, v in d["fixo"].items() if k in DIMENSOES and v in DIMENSOES[k]})
        _salvar(d)
        return dict(d["atual"])


def instrucao() -> str:
    """Entra nas instruções da sessão (main.py)."""
    try:
        atual = combinacao_atual()
    except Exception:
        return ""
    return "[ESTILO DESTA CONVERSA] " + " ".join(DIMENSOES[d][v] for d, v in atual.items())


def turno(entrada: str, saida: str, interrompido: bool = False) -> None:
    """Chamado a cada fim de turno (core/ganchos_turno.py)."""
    with _lock:
        d = dados()
        atual = d["atual"]
        if not atual:
            return
        pend = _mem["pendente"]
        mudou = False
        if interrompido and saida:
            aplicar(d["placar"], atual, recompensas("", atual, True))
            _mem["pendente"] = None
            mudou = True
        else:
            if pend and entrada:
                aplicar(d["placar"], pend, recompensas(sinal(entrada), pend))
                mudou = True
            if saida:
                _mem["pendente"] = dict(atual)
        if mudou:
            d["turnos"] = d.get("turnos", 0) + 1
            _salvar(d)


def relatorio() -> str:
    d = dados()
    linhas = []
    for dim, vars_ in DIMENSOES.items():
        p = d["placar"].get(dim, {})
        usos = sum(p.get(v, {}).get("n", 0) for v in vars_)
        if usos < 3:
            linhas.append(f"{dim}: ainda testando (poucas conversas)")
            continue
        melhor = max(vars_, key=lambda v: nota(p.get(v, {"a": 1, "b": 1})))
        pct = round(100 * nota(p.get(melhor, {"a": 1, "b": 1})))
        linhas.append(f"{dim}: {NOMES[melhor]} funcionam melhor ({pct}% de aprovação em {usos} respostas)")
    fixos = ", ".join(NOMES.get(v, v) for v in d["fixo"].values())
    return ("; ".join(linhas) + "." + (f" Fixado por você: {fixos}." if fixos else "")
            + ("" if d["ativo"] else " Os testes estão pausados (uso só o que já funcionou)."))


def ligar(ativo: bool) -> None:
    with _lock:
        d = dados()
        d["ativo"] = bool(ativo)
        d["desde"] = 0.0
        _salvar(d)


def fixar(variante: str) -> str:
    alvo = _dobrar(variante)
    for dim, vars_ in DIMENSOES.items():
        for v in vars_:
            if alvo and (alvo in _dobrar(v) or alvo in _dobrar(NOMES[v])):
                with _lock:
                    d = dados()
                    d["fixo"][dim] = v
                    d["desde"] = 0.0
                    _salvar(d)
                return f"Fixado: {NOMES[v]}."
    return "Não entendi qual jeito fixar (curta, completa, formal, descontraído, resposta antes, passos antes)."


def zerar() -> None:
    with _lock:
        _salvar({"ativo": True, "placar": {}, "atual": {}, "desde": 0.0, "fixo": {}, "turnos": 0})
        _mem["pendente"] = None
