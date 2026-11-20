"""
Cérebro local de comandos (fork PT-BR 3.4) — uma IA pequena que aprende COMO VOCÊ FALA, no seu PC.

O Gemini continua sendo quem conversa. O cérebro cuida dos comandos do dia a dia:

  • APRENDE sozinho: a cada pedido seu que terminou em UMA ferramenta que deu certo, ele guarda a
    frase e o que foi feito ("abre a loja" → cristal_malhas, ação abrir). Correção sua ("não, não
    foi isso") marca aquele aprendizado como errado. Você também pode ensinar direto.
  • Já nasce sabendo um pouco: lê as frases de exemplo ("Jarvis, …") que estão em cada plugin.
  • REFLEXO: comando que você já usou do mesmo jeito e deu certo pelo menos 2 vezes (ou que você
    ensinou) roda na hora, sem passar pelo Gemini — no celular, no comando digitado sem internet e
    quando o Gemini está fora. Mais rápido, sem gastar a cota e funcionando sem rede.
  • SEM INTERNET: mesmo para frase nova, ele tenta entender (Naive Bayes sobre raízes de palavras
    e pares de palavras + vizinho mais parecido) e, se não tiver certeza, sugere em vez de fazer.
  • AJUDA A BUSCA: as ferramentas que ele aprendeu com você entram primeiro na busca de ferramentas.

Regras de segurança: nunca faz reflexo de ferramenta CRÍTICA, tudo passa pelo mesmo caminho de
sempre (verificação do dono, sistema imune, diário), e no modo anônimo/convidado ele não aprende.
É estatística honesta, não mágica: frase muito diferente de tudo que ele viu vai para o Gemini.
Arquivo: memory/cerebro.json (até 3.000 exemplos).

3.9.4 — CÉREBRO PRONTO: ele já vem treinado. core/cerebro_base.json (gerado por core/cerebro_treino.py)
traz centenas de comandos do dia a dia COM a ação certa ("aumenta o som" → computer_settings volume_up,
"pula essa" → musica proxima…) e padrões com lacuna ("abre <app>", "toca <música>", "volume 40",
"timer de 10 minutos", "tempo em <cidade>"…). Sem o Gemini, ele já faz esses comandos no primeiro dia;
com o Gemini no ar, a base só ajuda a adivinhar e a achar a ferramenta. O que você ensina ou corrige
sempre vence a base, e ferramenta crítica continua nunca virando reflexo.
"""

from __future__ import annotations

import ast
import contextlib
import json
import math
import re
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "memory" / "cerebro.json"
ARQ_BASE = RAIZ / "core" / "cerebro_base.json"          # 3.9.4: o cérebro pronto (core/cerebro_treino.py)
MAX_EXEMPLOS = 3000
MIN_REFLEXO = 2                       # vezes que deu certo do mesmo jeito para virar reflexo
PESO = {"semente": 1.0, "base": 2.0, "uso": 3.0, "ensinado": 5.0}
PARADAS = set("""a o as os um uma uns umas de da do das dos em no na nos nas por pelo pela para pra pro com
e ou que se me te mim meu minha seu sua isso esse essa este esta ai la aqui agora ja so tambem ei oi ola
jarvis jarvas por favor favor pf pfv senhor ae entao vai vou quero queria preciso pode poderia consegue da""".split())
_PALAVRAS_LIVRES = {"action", "acao"}  # parâmetros que não carregam texto do usuário

_lock = threading.Lock()
_turno: list[tuple[float, str, dict, bool, bool]] = []
_anterior: dict = {"chave": None, "propria": False}
_cache: dict = {}


# ─────────────────────────────────────────────────────────── texto (puras) ───
def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9%$ ]+", " ", t)
    t = re.sub(r"^\s*(ei|oi|ola|e ai)?\s*jarv[ia]s\b", " ", t)
    return " ".join(t.split())


def chave(t: str) -> str:
    """A frase como 'mesmo pedido': normalizada e sem palavras vazias, na ordem. Pura."""
    return " ".join(w for w in normalizar(t).split() if w not in PARADAS)


# 3.9.4: jeitos diferentes de dizer a mesma coisa ("abre", "inicia", "executa"…) ganham um atributo em comum
# ("~abrir"), para o modelo reconhecer frase nova. Só o modelo usa; a semelhança (que decide reflexo) não.
_SINONIMOS = {
    "abrir": "abre abra abrir abrindo inicia inicie iniciar executa execute executar roda rodar carrega",
    "fechar": "fecha feche fechar encerra encerre encerrar finaliza finalizar mata",
    "aumentar": "aumenta aumente aumentar sobe suba subir levanta",
    "diminuir": "abaixa abaixe abaixar diminui diminua diminuir baixa baixe reduz reduza",
    "ligar": "liga ligue ligar ativa ative ativar acende acenda acender",
    "desligar": "desliga desligue desligar desativa desative desativar apaga apague apagar",
    "colocar": "bota bote coloca coloque poe ponha solta manda",
    "tocar": "toca toque tocar",
    "parar": "para pare parar pausa pause pausar segura chega",
    "mostrar": "mostra mostre mostrar exibe le leia ler ver lista listar",
    "pc": "pc computador notebook maquina note",
    "som": "som volume audio",
    "musica": "musica musicas cancao faixa musiquinha",
    "tela": "tela monitor",
    "limpar": "limpa limpe limpar faxina esvazia",
    "organizar": "organiza organize organizar arruma arrumar",
    "proximo": "proxima proximo pula pule pular passa",
    "lento": "lento travando pesado pesando",
}
_CANON = {w: c for c, ws in _SINONIMOS.items() for w in ws.split()}


def atributos(t: str) -> list[str]:
    """Raízes (5 letras) + pares de raízes vizinhas + números (+ 3.9.4: sinônimos '~'). Pura."""
    ws = [w for w in normalizar(t).split() if w not in PARADAS]
    rz = [w[:5] for w in ws]
    out = rz + [f"{a}_{b}" for a, b in zip(rz, rz[1:])]
    cn = ["~" + _CANON[w] if w in _CANON else r for w, r in zip(ws, rz)]
    if cn != rz:
        out += [c for c in cn if c[0] == "~"] + [f"~{a.lstrip('~')}_{b.lstrip('~')}" for a, b in zip(cn, cn[1:])
                                                 if a[0] == "~" or b[0] == "~"]
    return out


def parecido(a: list[str], b: list[str]) -> float:
    sa, sb = {x for x in a if x[0] != "~"}, {x for x in b if x[0] != "~"}
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def args_simples(args: dict) -> bool:
    """Só 'action' (sem texto livre do usuário): dá para repetir em frase parecida. Pura."""
    return all(k in _PALAVRAS_LIVRES for k in (args or {}))


# ─────────────────────────────────────────────────────────── memória ───
def _ler() -> dict:
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _gravar(d: dict) -> None:
    try:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        tmp = ARQ.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ARQ)
    except OSError:
        pass
    _cache.pop("modelo", None)


def _desligado() -> bool:
    """Modo anônimo ou convidado: não aprende."""
    try:
        from core import anonimo
        if anonimo.ativo():
            return True
    except Exception:
        pass
    try:
        from plugins import modo_convidado
        return modo_convidado.ativo()
    except Exception:
        return False


def reflexos_ligados() -> bool:
    return bool(_ler().get("reflexos", True))


def ligar_reflexos(sim: bool) -> None:
    with _lock:
        d = _ler()
        d["reflexos"] = bool(sim)
        _gravar(d)


def semelhanca_ligada() -> bool:
    return bool(_ler().get("semelhanca", False))


def ligar_semelhanca(sim: bool) -> None:
    """Reflexo por semelhança com o Gemini no ar. Só a metacognição liga, e só com a sua aprovação."""
    with _lock:
        d = _ler()
        d["semelhanca"] = bool(sim)
        _gravar(d)


# ─────────────────────────────────────────────────── 3.9.4: cérebro pronto ───
_base_override: dict | None = None


def base() -> dict:
    """A base pré-treinada (core/cerebro_base.json): {'exemplos': [{k, f, a}], 'padroes': [...]}. Vazia se faltar."""
    if not _cache.get("base"):
        try:
            d = _base_override if _base_override is not None else json.loads(ARQ_BASE.read_text(encoding="utf-8"))
            d = dict(d)
            d = d if isinstance(d, dict) else {}
        except Exception:
            d = {}
        d.setdefault("exemplos", [])
        d.setdefault("padroes", [])
        d["_mapa"] = {e["k"]: e for e in d["exemplos"] if isinstance(e, dict) and e.get("k") and e.get("f")}
        d["_re"] = []
        for p in d["padroes"]:
            try:
                d["_re"].append((re.compile(p["re"]), p))
            except (re.error, KeyError, TypeError):
                pass
        _cache["base"] = d
    return _cache["base"]


@contextlib.contextmanager
def base_temporaria(d: dict):
    """Usa outra base enquanto dura (o treino mede a base nova antes de gravar). Não grava nada."""
    global _base_override
    antes = _base_override
    _base_override = d
    _cache.pop("base", None)
    _cache.pop("modelo", None)
    try:
        yield
    finally:
        _base_override = antes
        _cache.pop("base", None)
        _cache.pop("modelo", None)


_EDUCADO_INI = re.compile(r"^(?:(?:por favor|pf|voce pode|vc pode|pode|consegue|da pra|quero que voce|preciso que voce|me|ai)\s+)+")
_EDUCADO_FIM = re.compile(r"(?:\s+(?:por favor|pra mim|para mim|agora|ai|rapidinho|ja|obrigado|valeu|pf))+$")


def por_padrao(texto: str) -> tuple[str, dict] | None:
    """3.9.4: comando com lacuna da base ("abre o obs studio" → open_app {app_name: 'obs studio'}). Pura (lê a base)."""
    t = _EDUCADO_FIM.sub("", _EDUCADO_INI.sub("", normalizar(texto))).strip()
    if not t:
        return None
    for rx, p in base()["_re"]:
        m = rx.match(t)
        if not m:
            continue
        grupos = {k: " ".join((v or "").split()) for k, v in m.groupdict().items()}
        nao = set(p.get("nao") or [])
        if any(v in nao or re.sub(r"^(?:o|a|os|as) ", "", v) in nao for v in grupos.values() if v):
            continue
        proibidas = set(p.get("nao_contem") or [])
        if proibidas and any(proibidas & set(v.split()) for v in grupos.values() if v):
            continue
        args = {}
        for nome, valor in (p.get("a") or {}).items():
            if isinstance(valor, str) and re.fullmatch(r"\{\w+\}", valor):
                v = grupos.get(valor[1:-1]) or ""
                if v:
                    args[nome] = v
            else:
                args[nome] = valor
        if any(grupos.values()):
            return p["f"], args
    return None


def exemplos() -> list[dict]:
    return list(_ler().get("exemplos", []))


def _guardar_exemplo(texto: str, ferramenta: str, args: dict, origem: str, bom: bool = True) -> dict | None:
    k = chave(texto)
    if not k or not ferramenta:
        return None
    args = {a: v for a, v in (args or {}).items() if v not in (None, "")}
    with _lock:
        d = _ler()
        ex = d.setdefault("exemplos", [])
        alvo = next((e for e in ex if e["k"] == k and e["f"] == ferramenta and e.get("a") == args), None)
        if alvo is None:
            alvo = {"k": k, "f": ferramenta, "a": args, "ok": 0, "ruim": 0, "origem": origem, "ts": time.time()}
            ex.append(alvo)
        alvo["ok" if bom else "ruim"] += 1
        alvo["ts"] = time.time()
        if origem == "ensinado":
            alvo["origem"] = "ensinado"
        if len(ex) > MAX_EXEMPLOS:
            ex.sort(key=lambda e: (e.get("origem") == "ensinado", e["ok"] - 2 * e["ruim"], e["ts"]))
            del ex[:len(ex) - MAX_EXEMPLOS]
        _gravar(d)
        return dict(alvo)


# ─────────────────────────────────────────────────────────── aprender ───
def anotar_chamada(ferramenta: str, args: dict, resultado: str, proprio: bool = False) -> None:
    """Toda ferramenta chamada por um pedido (PC e celular). Barato; nunca levanta exceção.
    proprio=True: foi o próprio cérebro que decidiu (reflexo) — não conta na medição da 3.6."""
    try:
        from core.registro_uso import parece_falha
        ok = not parece_falha(resultado)
    except Exception:
        ok = True
    with _lock:
        agora = time.time()
        _turno[:] = [c for c in _turno if agora - c[0] < 180] + [(agora, ferramenta, dict(args or {}), ok, bool(proprio))]


def turno(entrada: str, saida: str = "") -> dict | None:
    """Fim de um pedido: se teve UMA ferramenta e deu certo, aprende 'esta frase → isto'.
    Se o pedido é uma correção, o aprendizado anterior vira erro."""
    with _lock:
        chamadas = list(_turno)
        _turno.clear()
    entrada = str(entrada or "").strip()
    if not entrada or _desligado():
        return None
    try:
        from core import evolucao
        corrigiu = evolucao.sinal(entrada) == "corrigir"
    except Exception:
        corrigiu = False
    if corrigiu and _anterior.get("chave"):
        k, f, a = _anterior["chave"]
        _guardar_exemplo(k, f, a, "uso", bom=False)
        if _anterior.get("propria"):                       # 3.6: ele tinha feito sozinho, por semelhança, e você corrigiu
            try:
                from core import metacognicao
                metacognicao.reflexo_corrigido()
            except Exception as erro:
                print(f"[Cérebro] medição: {erro}")
        _anterior.update(chave=None, propria=False)
        return None
    if len(chamadas) != 1 or not chamadas[0][3]:
        _anterior.update(chave=None, propria=False)
        return None
    _, f, a, _, proprio = chamadas[0]
    if f in ("cerebro", "catalogo", "outras_ferramentas", "buscar_ferramentas", "usar_ferramenta", "pesquisar_web"):
        return None
    propria = False
    try:
        # Fork PT-BR 3.6 (metacognição): ANTES de aprender com este pedido, o cérebro é medido.
        from core import metacognicao
        if proprio:
            # Foi ele mesmo que fez. Se foi por semelhança (a evolução que você aprovou), fica anotado como acerto
            # até você corrigir; reflexo de frase conhecida não entra na conta (ninguém conferiu).
            propria = metacognicao.reflexo_proprio(entender(entrada))
        else:
            # O Gemini resolveu: o que o cérebro teria feito sozinho, comparado com o que foi feito de verdade.
            metacognicao.sombra_cerebro(f, {x: v for x, v in a.items() if v not in (None, "")},
                                        entender(entrada), entender(entrada, _simular=True))
    except Exception as erro:
        print(f"[Cérebro] medição: {erro}")
    e = _guardar_exemplo(entrada, f, a, "uso")
    _anterior.update(chave=(entrada, f, a) if e else None, propria=bool(e) and bool(propria))
    return e


def ensinar(frase: str, ferramenta: str, args: dict | None = None) -> dict | None:
    return _guardar_exemplo(frase, ferramenta, args or {}, "ensinado")


def esquecer(frase: str) -> int:
    k = chave(frase)
    with _lock:
        d = _ler()
        antes = len(d.get("exemplos", []))
        d["exemplos"] = [e for e in d.get("exemplos", []) if e["k"] != k]
        _gravar(d)
        return antes - len(d["exemplos"])


# ─────────────────────────────────────────────────────────── sementes ───
_FRASE = re.compile(r"[\"“]\s*Jarvis,?\s+([^\"”]{3,140}?)[\"”]")


def sementes(pasta: Path | None = None) -> list[tuple[str, str]]:
    """(frase, ferramenta) das frases de exemplo escritas nos próprios plugins."""
    pasta = pasta or RAIZ / "plugins"
    out = []
    for arq in sorted(pasta.glob("*.py")):
        if arq.name.startswith("_"):
            continue
        try:
            doc = ast.get_docstring(ast.parse(arq.read_text(encoding="utf-8", errors="replace"))) or ""
        except (SyntaxError, ValueError, OSError):
            continue
        for frase in _FRASE.findall(doc):
            frase = frase.split("→")[0].strip(" .")
            if chave(frase):
                out.append((frase, arq.stem))
    return out


# ─────────────────────────────────────────────────────────── modelo ───
class Modelo:
    """Naive Bayes multinomial sobre atributos + vizinho mais parecido. Treina em milissegundos."""

    def __init__(self, dados: list[tuple[str, str, dict, str, float]]):
        self.cont: dict[str, Counter] = defaultdict(Counter)
        self.total: Counter = Counter()
        self.docs: Counter = Counter()
        self.vocab: set[str] = set()
        self.itens = []
        self.variantes: dict[str, dict[str, Counter]] = defaultdict(dict)   # 3.9.4: ferramenta → parâmetros → atributos
        for texto, f, a, origem, peso in dados:
            at = atributos(texto)
            if not at or peso <= 0:
                continue
            if origem != "semente" and (origem == "base" or args_simples(a)):
                aj = json.dumps(a or {}, sort_keys=True, ensure_ascii=False)
                self.variantes[f].setdefault(aj, Counter()).update({x: peso for x in at})
            for x in at:
                self.cont[f][x] += peso
            self.total[f] += peso * len(at)
            self.docs[f] += peso
            self.vocab.update(at)
            self.itens.append((at, f, a, origem, texto))

    def probabilidades(self, texto: str) -> list[tuple[str, float]]:
        at = [x for x in atributos(texto) if x in self.vocab]
        if not at or not self.docs:
            return []
        v, n = len(self.vocab), sum(self.docs.values())
        notas = {}
        for f in self.docs:
            lp = math.log(self.docs[f] / n) * 0.3
            for x in at:
                lp += math.log((self.cont[f][x] + 0.1) / (self.total[f] + 0.1 * v))
            notas[f] = lp
        t = max(1.0, len(at) / 2)                      # temperatura: NB costuma ter certeza demais
        m = max(notas.values())
        exps = {f: math.exp((lp - m) / t) for f, lp in notas.items()}
        soma = sum(exps.values())
        return sorted(((f, e / soma) for f, e in exps.items()), key=lambda x: -x[1])

    def melhores_args(self, texto: str, ferramenta: str) -> dict | None:
        """3.9.4: entre os jeitos de usar a ferramenta (ex.: musica pausar/proxima/tocar), o mais provável. Pura."""
        vs = self.variantes.get(ferramenta)
        if not vs:
            return None
        at = atributos(texto)
        v = len(self.vocab) or 1
        melhor, nota = None, -1e18
        for aj, cont in vs.items():
            total = sum(cont.values())
            lp = sum(math.log((cont[x] + 0.1) / (total + 0.1 * v)) for x in at)
            if lp > nota:
                melhor, nota = aj, lp
        return json.loads(melhor) if melhor else None

    def vizinho(self, texto: str, ferramenta: str | None = None, sem_semente: bool = False) -> tuple[float, tuple | None]:
        at = atributos(texto)
        melhor = (0.0, None)
        for item in self.itens:
            if ferramenta and item[1] != ferramenta:
                continue
            if sem_semente and item[3] == "semente":
                continue
            s = parecido(at, item[0])
            if s > melhor[0]:
                melhor = (s, item)
        return melhor


def modelo() -> Modelo:
    d = _ler()
    b = base()
    assinatura = (len(d.get("exemplos", [])), sum(e["ok"] + e["ruim"] for e in d.get("exemplos", [])), id(b))
    m = _cache.get("modelo")
    if m and _cache.get("assinatura") == assinatura:
        return m
    if "sementes" not in _cache:
        _cache["sementes"] = sementes()
    dados = [(t, f, {}, "semente", PESO["semente"]) for t, f in _cache["sementes"]]
    dados += [(e["k"], e["f"], e.get("a") or {}, "base", PESO["base"]) for e in b["_mapa"].values()]
    for e in d.get("exemplos", []):
        peso = PESO.get(e.get("origem"), 3.0) * max(0, e["ok"] - 2 * e["ruim"])
        dados.append((e["k"], e["f"], e.get("a") or {}, e.get("origem", "uso"), peso))
    m = Modelo(dados)
    _cache.update(modelo=m, assinatura=assinatura)
    return m


def _nivel(ferramenta: str, args: dict) -> str:
    try:
        from core import verificacao
        return verificacao.nivel_de(ferramenta, args)
    except Exception:
        return "livre"


def entender(texto: str, sem_ia: bool = False, _simular: bool = False) -> dict:
    """O que o cérebro faria com o pedido.
    reflexo=True: pode executar já (frase conhecida, deu certo ≥2×, nunca corrigida, não é crítica).
    sem_ia=True (Gemini fora): aceita frase parecida com certeza alta, se a ação não precisa de texto livre.
    3.6: com a evolução "por semelhança" APROVADA por você (core/metacognicao.py), frase parecida também vira
    reflexo com o Gemini no ar — só para ferramentas livres (nunca sensíveis nem críticas).
    _simular=True: responde como se essa evolução estivesse ligada (é como ela é medida antes de ser proposta)."""
    r = {"texto": texto, "ferramenta": None, "args": {}, "confianca": 0.0, "reflexo": False, "semelhanca": False, "motivo": "",
         "sugestoes": []}
    k = chave(texto)
    if not k:
        r["motivo"] = "pedido vazio"
        return r
    d = _ler()
    conhecidos = [e for e in d.get("exemplos", []) if e["k"] == k and e["ok"] > 0 and e["ruim"] == 0]
    if conhecidos:
        e = max(conhecidos, key=lambda x: (x.get("origem") == "ensinado", x["ok"]))
        r.update(ferramenta=e["f"], args=dict(e.get("a") or {}), confianca=1.0)
        firme = e.get("origem") == "ensinado" or e["ok"] >= (1 if sem_ia else MIN_REFLEXO)   # sem Gemini, 1 acerto basta
        if not firme:
            r["motivo"] = f"já fiz isso {e['ok']} vez(es); vira reflexo na {MIN_REFLEXO}ª"
        elif _nivel(e["f"], r["args"]) == "critico":
            r["motivo"] = "ferramenta crítica nunca vira reflexo"
        elif not d.get("reflexos", True):
            r["motivo"] = "reflexos desligados"
        else:
            r.update(reflexo=True, motivo="frase conhecida")
        r["sugestoes"] = [(e["f"], 1.0)]
        return r
    corrigida = any(e["k"] == k and e["ruim"] > 0 for e in d.get("exemplos", []))
    # 3.9.4: frase que o cérebro pronto já conhece (e que você nunca corrigiu).
    eb = base()["_mapa"].get(k)
    if eb and not corrigida:
        r.update(ferramenta=eb["f"], args=dict(eb.get("a") or {}), confianca=0.95, sugestoes=[(eb["f"], 0.95)])
        if not sem_ia:
            r["motivo"] = "frase do cérebro pronto (o Gemini decide)"
        elif _nivel(eb["f"], r["args"]) == "critico":
            r["motivo"] = "ferramenta crítica nunca vira reflexo"
        elif not d.get("reflexos", True):
            r["motivo"] = "reflexos desligados"
        else:
            r.update(reflexo=True, motivo="frase do cérebro pronto")
        return r
    m = modelo()
    probs = m.probabilidades(texto)
    r["sugestoes"] = probs[:3]
    if not probs:
        r["motivo"] = "não conheço nada parecido"
        return r
    f, p = probs[0]
    sim, item = m.vizinho(texto, f)
    r.update(ferramenta=f, confianca=round(p * (0.5 + 0.5 * sim), 3))
    if item and item[3] != "semente" and (sim >= 0.5 or item[3] != "base"):
        r["args"] = dict(item[2] or {})
    else:                                   # 3.9.4: semente não tem parâmetros; o modelo escolhe o jeito mais provável
        r["args"] = m.melhores_args(texto, f) or (dict(item[2] or {}) if item and item[3] != "semente" else {})
    # Sem o Gemini: frase bem parecida (≥ 60% das raízes) com um pedido SEU que deu certo, cuja ferramenta também
    # está entre as 3 que o modelo acha, e que não leva texto livre seu nos parâmetros.
    meu = max(((parecido(atributos(texto), it[0]) - (0.001 if it[3] == "base" else 0), it) for it in m.itens if it[3] != "semente"),
              key=lambda x: x[0], default=(0.0, None))
    top3 = {x for x, _ in probs[:3]}
    nivel = _nivel(meu[1][1], meu[1][2]) if meu[1] else "critico"
    pode = (sem_ia and nivel != "critico") or ((_simular or d.get("semelhanca")) and nivel == "livre")
    # 3.6: frase em que você JÁ me corrigiu nunca mais é feita "por parecer" (antes ele repetia o mesmo engano).
    # 3.9.4: os parâmetros da base são fixos (nunca texto seu), então valem como "simples".
    padrao = por_padrao(texto) if not corrigida else None
    if pode and not corrigida and d.get("reflexos", True) and meu[1] and meu[0] >= 0.6 and meu[1][1] in top3 \
            and (args_simples(meu[1][2]) or meu[1][3] == "base"):
        r.update(ferramenta=meu[1][1], args=dict(meu[1][2] or {}), confianca=round(meu[0], 3), reflexo=True, semelhanca=True,
                 motivo="parecido com um pedido que você já fez")
    elif corrigida and pode:
        r["motivo"] = "você já me corrigiu nessa frase; não faço sozinho"
    elif padrao:
        # 3.9.4: comando com lacuna ("abre <app>", "toca <música>", "volume 40"…). Sem o Gemini, faz; com ele, sugere.
        f2, a2 = padrao
        r.update(ferramenta=f2, args=a2, confianca=max(r["confianca"], 0.8))
        r["sugestoes"] = [(f2, 0.8)] + [x for x in r["sugestoes"] if x[0] != f2][:2]
        if not sem_ia:
            r["motivo"] = "comando do cérebro pronto (o Gemini decide)"
        elif _nivel(f2, a2) == "critico":
            r["motivo"] = "ferramenta crítica nunca vira reflexo"
        elif not d.get("reflexos", True):
            r["motivo"] = "reflexos desligados"
        else:
            r.update(reflexo=True, motivo="comando do cérebro pronto")
    else:
        r["motivo"] = "palpite (o Gemini decide)" if not sem_ia else "não tenho certeza suficiente para fazer sozinho"
    return r


def sugerir(texto: str, n: int = 3, minimo: float = 0.5) -> list[str]:
    """Ferramentas que o cérebro aprendeu COM VOCÊ para essa frase (para a busca de ferramentas)."""
    r = entender(texto)
    pessoais = {e["f"] for e in exemplos() if e.get("origem") in ("uso", "ensinado") and e["ok"] > e["ruim"]}
    out = [f for f, p in r["sugestoes"] if f in pessoais and p >= minimo]
    # 3.9.4: depois das suas, as que o cérebro pronto tem certeza (frase conhecida ou comando com lacuna).
    if r["ferramenta"] and r["ferramenta"] not in out and r["confianca"] >= 0.8 and \
            (base()["_mapa"].get(chave(texto)) or por_padrao(texto)):
        out.append(r["ferramenta"])
    return out[:n]


def estado() -> dict:
    d = _ler()
    ex = d.get("exemplos", [])
    if "sementes" not in _cache:
        _cache["sementes"] = sementes()
    firmes = [e for e in ex if e["ruim"] == 0 and (e.get("origem") == "ensinado" or e["ok"] >= MIN_REFLEXO)]
    return {"sementes": len(_cache["sementes"]), "base": len(base()["_mapa"]), "padroes": len(base()["_re"]),
            "aprendidos": len(ex), "reflexos": len(firmes),
            "corrigidos": sum(1 for e in ex if e["ruim"]), "ligado": d.get("reflexos", True),
            "ferramentas": len({e["f"] for e in ex}),
            "mais_usados": sorted(ex, key=lambda e: -e["ok"])[:8], "firmes": firmes}


def resposta_curta(resultado: str, limite: int = 600) -> str:
    """Resultado de ferramenta pronto para mostrar/falar sem o Gemini (tira marcas internas). Pura."""
    t = str(resultado or "")
    try:
        from core import outcome
        t = outcome.unwrap(t)
    except Exception:
        pass
    m = re.match(r"\s*status=(\w+)\b(.*)", t, re.S)
    if m:
        t = {"done": "Feito.", "ask": "Preciso de mais detalhes.", "failed": "Não deu certo."}.get(m.group(1), "") + \
            (" " + re.sub(r"\b\w+=", "", m.group(2)).strip() if m.group(1) != "done" else "")
    t = " ".join(t.split())
    return t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "…"
