"""
Caixa-preta (fork PT-BR 3.3): os erros que o JARVIS já cometeu com VOCÊ — para não repetir.

Igual à de avião: tudo que dá errado fica registrado. Quando você corrige o JARVIS ("não, não foi
isso", "tá errado", "entendeu errado"…), ele guarda três coisas: o que você tinha pedido, o que ele
respondeu e a sua correção. Erro parecido com um que já existe soma no mesmo registro (2×, 3×…).

No começo de cada sessão, os erros mais repetidos e mais recentes entram nas instruções do JARVIS
("não repita: quando ele pediu X, você respondeu Y e ele corrigiu Z"). Com o tempo ele erra menos
com você — e você vê tudo: "Jarvis, mostra a caixa-preta".

Quem percebe a correção é o mesmo detector do core/evolucao.py (que até a 3.2 só usava isso para
ajustar o estilo). No modo anônimo e no modo convidado nada é registrado nem usado.
Arquivo: memory/caixa_preta.json (no máximo 60 registros).
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / "memory" / "caixa_preta.json"
MAXIMO = 60
PARADAS = {"para", "pelo", "pela", "como", "isso", "esse", "essa", "este", "esta", "qual", "quais", "quero", "queria",
           "voce", "jarvis", "sobre", "mais", "menos", "muito", "agora", "entao", "porque", "nada", "tudo", "minha", "meu",
           "foi", "nao", "sim", "tava", "estava", "errado", "certo", "falei", "pedi", "disse", "entendeu", "fala", "falou"}
_lock = threading.Lock()
_anterior: dict = {"entrada": "", "saida": ""}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def chaves(texto: str) -> set[str]:
    """Palavras que dizem do que se trata (raiz de 5 letras, sem as palavras vazias). Pura."""
    return {w[:5] for w in re.findall(r"[a-z0-9]{4,}", _dobrar(texto)) if w not in PARADAS}


def parecido(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _ler() -> dict:
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"erros": []}
    except Exception:
        return {"erros": []}


def _gravar(d: dict) -> None:
    try:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        tmp = ARQ.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(ARQ)
    except OSError:
        pass


def _anonimo() -> bool:
    """Modo anônimo ou modo convidado: não registra nada e não põe nada pessoal nas instruções."""
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


def registrar(pergunta: str, resposta: str, correcao: str, origem: str = "conversa") -> dict | None:
    """Guarda um erro. Se já existe um parecido (mesmo assunto), soma nele."""
    pergunta, correcao = str(pergunta or "").strip(), str(correcao or "").strip()
    if not pergunta or not correcao or _anonimo():
        return None
    ch = chaves(pergunta) | chaves(correcao)
    with _lock:
        d = _ler()
        erros = d.setdefault("erros", [])
        alvo = max(erros, key=lambda e: parecido(set(e.get("chaves", [])), ch), default=None)
        if alvo and parecido(set(alvo.get("chaves", [])), ch) >= 0.5:
            alvo.update(vezes=alvo.get("vezes", 1) + 1, ts=time.time(), correcao=correcao[:220],
                        resposta=str(resposta or "")[:220] or alvo.get("resposta", ""))
            alvo["chaves"] = sorted(set(alvo.get("chaves", [])) | ch)[:30]
            e = alvo
        else:
            d["seq"] = int(d.get("seq", 0)) + 1
            e = {"id": d["seq"], "ts": time.time(), "pergunta": pergunta[:220], "resposta": str(resposta or "")[:220],
                 "correcao": correcao[:220], "vezes": 1, "origem": origem, "chaves": sorted(ch)[:30]}
            erros.append(e)
        if len(erros) > MAXIMO:
            erros.sort(key=lambda x: _peso(x))
            del erros[:len(erros) - MAXIMO]
        _gravar(d)
        return dict(e)


def turno(entrada: str, saida: str) -> dict | None:
    """Chamado a cada troca (ganchos de fim de turno no PC; motor no celular)."""
    from core import evolucao
    entrada, saida = str(entrada or "").strip(), str(saida or "").strip()
    anterior = dict(_anterior)
    if entrada or saida:
        _anterior.update(entrada=entrada, saida=saida)
    if entrada and anterior["entrada"] and evolucao.sinal(entrada) == "corrigir":
        return registrar(anterior["entrada"], anterior["saida"], entrada)
    return None


def _peso(e: dict, agora: float | None = None) -> float:
    """Mais repetido e mais recente pesa mais (meia-vida de 30 dias)."""
    idade_dias = max(0.0, ((agora or time.time()) - e.get("ts", 0)) / 86400)
    return e.get("vezes", 1) * 0.5 ** (idade_dias / 30)


def erros() -> list[dict]:
    return sorted(_ler().get("erros", []), key=_peso, reverse=True)


def licoes(n: int = 6) -> list[dict]:
    return erros()[:n]


def instrucao(n: int = 6, limite: int = 900) -> str:
    """O trecho que entra nas instruções da sessão. Vazio sem erros ou no modo anônimo."""
    if _anonimo():
        return ""
    ls = licoes(n)
    if not ls:
        return ""
    linhas = ["[CAIXA-PRETA] Erros que você já cometeu com este usuário. Não repita:"]
    for e in ls:
        linha = (f"- Ele pediu \"{e['pergunta'][:90]}\"" + (f"; você respondeu \"{e['resposta'][:70]}\"" if e.get("resposta") else "")
                 + f"; ele corrigiu: \"{e['correcao'][:110]}\"" + (f" ({e['vezes']}×)" if e.get("vezes", 1) > 1 else "") + ".")
        if sum(len(x) + 1 for x in linhas) + len(linha) > limite:
            break
        linhas.append(linha)
    return "\n".join(linhas) if len(linhas) > 1 else ""


def parecidos(texto: str, n: int = 3) -> list[dict]:
    ch = chaves(texto)
    achados = [(parecido(set(e.get("chaves", [])), ch), e) for e in _ler().get("erros", [])]
    return [e for s, e in sorted(achados, key=lambda x: -x[0]) if s > 0.15][:n]


def esquecer(eid: int) -> bool:
    with _lock:
        d = _ler()
        antes = len(d.get("erros", []))
        d["erros"] = [e for e in d.get("erros", []) if e.get("id") != eid]
        _gravar(d)
        return len(d["erros"]) < antes


def limpar() -> int:
    with _lock:
        d = _ler()
        n = len(d.get("erros", []))
        d["erros"] = []
        _gravar(d)
        return n
