"""
Coach de decisões grandes (fork PT-BR 2.10).

Pra quando você tem uma escolha difícil. Você diz as opções, vai jogando os prós
e os contras (com um peso de 1 a 5 que você mesmo ajusta), e o JARVIS soma e mostra
qual está na frente — e o ponto mais forte de cada lado. A conta é sua ferramenta,
não a decisão: no fim quem decide é você.

    "Jarvis, me ajuda a decidir entre aceitar o SENAI ou continuar freelancer."
    "Jarvis, ponto a favor do SENAI: salário fixo, peso 5."
    "Jarvis, contra do SENAI: tenho menos tempo livre, peso 3."
    "Jarvis, muda o peso do salário fixo pra 4."
    "Jarvis, como tá a decisão?"      "Jarvis, decidi pelo SENAI."

Tudo em memory/decisoes.json. Os pesos e a soma são só pra organizar o seu
pensamento; ele não escolhe por você.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "coach_decisao",
    "brief": "Big-decision coach: options with weighted pros/cons you adjust; tallies and shows the leader (you decide).",
    "description": (
        "Helps the user think through a big decision with options and weighted pros/cons (weight 1-5 the user sets). "
        "It tallies and shows which option leads and the strongest point on each side — but the user decides. Use "
        "for 'me ajuda a decidir entre X e Y', 'ponto a favor/contra de X', 'muda o peso de...', 'como está a "
        "decisão?', 'decidi por X'. action: 'nova' (titulo + opcoes, comma-separated); 'pro' / 'contra' (opcao + "
        "texto + optional peso 1-5); 'peso' (opcao + fator words + peso); 'ver' (optional titulo); 'decidir' (opcao); "
        "'listar'; 'remover' (titulo). Never tell the user which option to pick as if it were certain; present the "
        "tally and let them choose."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "nova | pro | contra | peso | ver | decidir | listar | remover"},
            "titulo": {"type": "STRING", "description": "what the decision is about"},
            "opcoes": {"type": "STRING", "description": "options, comma-separated (for 'nova')"},
            "opcao": {"type": "STRING", "description": "which option"},
            "texto": {"type": "STRING", "description": "the pro/con, in the user's words"},
            "fator": {"type": "STRING", "description": "which pro/con to re-weight (for 'peso')"},
            "peso": {"type": "NUMBER", "description": "1 (weak) to 5 (decisive)"},
        },
        "required": ["action"],
    },
}

ARQ = MEMORIA / "decisoes.json"          # o carregador dos testes troca este caminho
_lock = threading.RLock()
PESO_PADRAO = 3


# ── texto (puro) ───────────────────────────────────────────────────────────────
def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def ler_peso(valor, padrao: int = PESO_PADRAO) -> int:
    t = dobrar(valor)
    palavras = {"decisiv": 5, "muito important": 5, "important": 4, "medio": 3, "mais ou menos": 3, "pouco": 2,
                "fraco": 1, "detalhe": 1}
    for p, n in palavras.items():
        if p in t:
            return n
    m = re.search(r"\b([1-5])\b", t)
    return int(m.group(1)) if m else padrao


def achar_opcao(opcoes: list[dict], termo: str) -> dict | None:
    """A opção que combina com o termo (pura)."""
    t = dobrar(termo).strip()
    if not t:
        return None
    for o in opcoes:
        if dobrar(o["nome"]) == t:
            return o
    palavras = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2]
    melhor, ponto = None, 0
    for o in opcoes:
        alvo = dobrar(o["nome"])
        n = sum(1 for w in palavras if w in alvo)
        if n > ponto:
            melhor, ponto = o, n
    return melhor


def achar_fator(opcao: dict, termo: str):
    t = dobrar(termo)
    palavras = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2]
    melhor, ponto = None, 0
    for f in opcao.get("fatores", []):
        alvo = dobrar(f["texto"])
        n = sum(1 for w in palavras if w in alvo)
        if n > ponto:
            melhor, ponto = f, n
    return melhor


def pontuar(opcao: dict) -> int:
    """Σ(prós·peso) − Σ(contras·peso) (pura)."""
    return sum((f["peso"] if f["lado"] == "pro" else -f["peso"]) for f in opcao.get("fatores", []))


def ranquear(decisao: dict) -> list[tuple[dict, int]]:
    return sorted(((o, pontuar(o)) for o in decisao.get("opcoes", [])), key=lambda x: x[1], reverse=True)


def _mais_forte(opcao: dict, lado: str):
    cands = [f for f in opcao.get("fatores", []) if f["lado"] == lado]
    return max(cands, key=lambda f: f["peso"]) if cands else None


def resumo(decisao: dict) -> str:
    rank = ranquear(decisao)
    if not rank:
        return f"A decisão “{decisao['titulo']}” ainda não tem opções."
    linhas = []
    for pos, (o, s) in enumerate(rank, 1):
        pro = _mais_forte(o, "pro")
        contra = _mais_forte(o, "contra")
        detalhe = []
        if pro:
            detalhe.append(f"+{pro['texto']}({pro['peso']})")
        if contra:
            detalhe.append(f"−{contra['texto']}({contra['peso']})")
        np = sum(1 for f in o["fatores"] if f["lado"] == "pro")
        nc = len(o["fatores"]) - np
        linhas.append(f"{pos}. {o['nome']}: {s:+d}  ({np} prós, {nc} contras)" +
                      ("  " + ", ".join(detalhe) if detalhe else ""))
    return "\n".join(linhas)


def frase_coach(decisao: dict) -> str:
    """O que o JARVIS fala (pura): mostra o placar sem decidir pela pessoa."""
    rank = ranquear(decisao)
    if not rank:
        return f"Ainda não temos opções em “{decisao['titulo']}”. Quais são as escolhas?"
    if len(rank) == 1:
        o, s = rank[0]
        return f"“{o['nome']}” está com saldo {s:+d}. Me diga a outra opção pra comparar, ou mais prós e contras."
    (o1, s1), (o2, s2) = rank[0], rank[1]
    if s1 == s2:
        return (f"Empate entre “{o1['nome']}” e “{o2['nome']}” ({s1:+d}). Pelo visto estão parelhas — talvez falte "
                "um ponto que pese de verdade pra você. O que mais importa aqui?")
    dif = s1 - s2
    forca = "bem na frente" if dif >= 4 else "na frente" if dif >= 2 else "um pouquinho à frente"
    pro = _mais_forte(o1, "pro")
    motivo = f", puxada por “{pro['texto']}”" if pro else ""
    return (f"Pela sua conta, “{o1['nome']}” está {forca} ({s1:+d} contra {s2:+d}){motivo}. Mas a decisão é sua — "
            "quer ajustar algum peso ou falta algum ponto?")


# ── dados ──────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("decisoes", [])
    d.setdefault("proximo_id", 1)
    return d


def _gravar(d: dict) -> None:
    with _lock:
        gravar_json(ARQ, d)


def _atual(d: dict, titulo: str = "") -> dict | None:
    abertas = [x for x in d["decisoes"] if not x.get("decidida")]
    if titulo:
        t = dobrar(titulo)
        achada = next((x for x in d["decisoes"] if t in dobrar(x["titulo"]) or dobrar(x["titulo"]) in t), None)
        if achada:
            return achada
    return abertas[-1] if abertas else (d["decisoes"][-1] if d["decisoes"] else None)


# ── ações ──────────────────────────────────────────────────────────────────────
def _opcoes_de(texto: str) -> list[str]:
    bruto = re.split(r"\s*(?:,|;| ou | e | versus | vs\.? | x )\s*", str(texto or "").strip())
    vistos, saida = set(), []
    for o in bruto:
        o = o.strip(" .")
        if o and dobrar(o) not in vistos:
            vistos.add(dobrar(o))
            saida.append(o[:60])
    return saida


def nova(titulo: str, opcoes: str) -> str:
    titulo = " ".join(str(titulo or "").split()).strip(" .?") or "minha decisão"
    nomes = _opcoes_de(opcoes)
    with _lock:
        d = dados()
        dec = {"id": d["proximo_id"], "titulo": titulo, "criada": time.time(), "decidida": "",
               "opcoes": [{"nome": n, "fatores": []} for n in nomes]}
        d["decisoes"].append(dec)
        d["proximo_id"] += 1
        _gravar(d)
    registrar(None, f"⚖️ Decisão aberta: {titulo}")
    if len(nomes) < 2:
        return (f"Abri a decisão “{titulo}”. Quais são as opções? (ex.: 'as opções são aceitar o SENAI ou continuar "
                "freelancer')")
    return (f"Decisão “{titulo}” com {len(nomes)} opções: {', '.join(nomes)}. Agora me diga os prós e contras de "
            "cada uma, com um peso de 1 a 5. Pode começar.")


def fator(opcao: str, texto: str, peso, lado: str, titulo: str = "") -> str:
    texto = " ".join(str(texto or "").split()).strip(" .")
    if not texto:
        return "Qual é o ponto?"
    with _lock:
        d = dados()
        dec = _atual(d, titulo)
        if not dec:
            return "Não temos nenhuma decisão aberta. Diga 'me ajuda a decidir entre X e Y'."
        alvo = achar_opcao(dec["opcoes"], opcao)
        if alvo is None:
            if len(dec["opcoes"]) == 1:
                alvo = dec["opcoes"][0]
            else:
                return (f"De qual opção é esse ponto? As opções são: {', '.join(o['nome'] for o in dec['opcoes'])}.")
        p = ler_peso(peso)
        alvo.setdefault("fatores", []).append({"texto": texto, "peso": p, "lado": lado})
        _gravar(d)
        placar = pontuar(alvo)
    nome = "ponto a favor" if lado == "pro" else "ponto contra"
    return (f"Anotei o {nome} de “{alvo['nome']}”: {texto} (peso {p}). Essa opção está com saldo {placar:+d}. "
            f"{frase_coach(dec)}")


def mudar_peso(opcao: str, fator_txt: str, peso, titulo: str = "") -> str:
    with _lock:
        d = dados()
        dec = _atual(d, titulo)
        if not dec:
            return "Não temos nenhuma decisão aberta."
        termo = f"{opcao} {fator_txt}".strip()
        alvo = achar_opcao(dec["opcoes"], opcao) if opcao else None
        candidatos = [alvo] if alvo else dec["opcoes"]
        achado_f, achado_o = None, None
        for o in candidatos:
            f = achar_fator(o, fator_txt or termo)
            if f is not None:
                achado_f, achado_o = f, o
                break
        if achado_f is None:
            return "Não achei esse ponto pra mudar o peso. Qual ponto, e de qual opção?"
        achado_f["peso"] = ler_peso(peso)
        _gravar(d)
    return (f"Pronto: “{achado_f['texto']}” agora pesa {achado_f['peso']} em “{achado_o['nome']}”. {frase_coach(dec)}")


def ver(titulo: str = "", player=None) -> str:
    with _lock:
        d = dados()
        dec = _atual(d, titulo)
    if not dec:
        return "Você não tem nenhuma decisão registrada. Diga 'me ajuda a decidir entre X e Y'."
    mostrar(player, f"DECISÃO · {dec['titulo']}", resumo(dec))
    if dec.get("decidida"):
        return f"Essa decisão você já fechou: escolheu “{dec['decidida']}”."
    return frase_coach(dec)


def decidir(opcao: str, titulo: str = "") -> str:
    with _lock:
        d = dados()
        dec = _atual(d, titulo)
        if not dec:
            return "Qual decisão? Não achei nenhuma aberta."
        alvo = achar_opcao(dec["opcoes"], opcao)
        if alvo is None:
            return f"Por qual opção você decidiu? ({', '.join(o['nome'] for o in dec['opcoes'])})"
        dec["decidida"] = alvo["nome"]
        dec["quando_decidiu"] = time.time()
        _gravar(d)
        placar = pontuar(alvo)
        venceu = ranquear(dec)[0][0]["nome"] == alvo["nome"]
    registrar(None, f"⚖️ Decidido: {dec['titulo']} → {alvo['nome']}")
    fecho = "Era a que estava na frente na sua conta também." if venceu else ("A conta apontava outra, mas quem sente "
            "o peso de verdade é você — boa escolha se é o que o seu coração pede.")
    return f"Fechado: “{alvo['nome']}” (saldo {placar:+d}). {fecho}"


def listar(player=None) -> str:
    with _lock:
        decisoes = dados()["decisoes"]
    if not decisoes:
        return "Você não tem decisões registradas."
    linhas = []
    for x in decisoes[-15:]:
        st = f"→ {x['decidida']}" if x.get("decidida") else f"em aberto ({len(x['opcoes'])} opções)"
        linhas.append(f"#{x['id']} {x['titulo']} — {st}")
    mostrar(player, "DECISÕES", "\n".join(linhas))
    abertas = [x for x in decisoes if not x.get("decidida")]
    return f"Você tem {len(decisoes)} decisão(ões), {len(abertas)} em aberto. Mostrei na tela; resuma em 2 frases."


def remover(titulo: str) -> str:
    with _lock:
        d = dados()
        dec = _atual(d, titulo)
        if not dec:
            return f"Não achei a decisão “{titulo}”."
        d["decisoes"] = [x for x in d["decisoes"] if x.get("id") != dec["id"]]
        _gravar(d)
    return f"Apaguei a decisão “{dec['titulo']}”."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "ver").strip()
    titulo = str(p.get("titulo") or "")
    try:
        if acao in ("nova", "criar", "decisao", "decidir_entre", "ajudar"):
            return nova(titulo, str(p.get("opcoes") or ""))
        if acao in ("pro", "favor", "a_favor", "vantagem"):
            return fator(str(p.get("opcao") or ""), str(p.get("texto") or ""), p.get("peso"), "pro", titulo)
        if acao in ("contra", "desvantagem", "ponto_contra"):
            return fator(str(p.get("opcao") or ""), str(p.get("texto") or ""), p.get("peso"), "contra", titulo)
        if acao in ("peso", "mudar_peso", "ajustar"):
            return mudar_peso(str(p.get("opcao") or ""), str(p.get("fator") or p.get("texto") or ""), p.get("peso"),
                              titulo)
        if acao in ("ver", "analisar", "como_esta", "placar", "mostrar"):
            return ver(titulo, player)
        if acao in ("decidir", "escolhi", "escolher", "fechar"):
            return decidir(str(p.get("opcao") or ""), titulo)
        if acao in ("listar", "lista"):
            return listar(player)
        if acao in ("remover", "apagar", "excluir"):
            return remover(titulo or str(p.get("opcao") or ""))
        return ver(titulo, player)
    except Exception as e:
        return f"O coach de decisões falhou: {e}"
