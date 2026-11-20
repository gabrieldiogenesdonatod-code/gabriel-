"""
Lógica pura dos jogos por voz do J.A.R.V.I.S BR (1.7). Começa com "_": não é ferramenta.

Jogo da velha (minimax: no difícil o JARVIS nunca perde), Lig 4 (alfa-beta),
forca com palavras em português por tema, adivinhe o número e
pedra-papel-tesoura com uma IA que aprende os seus padrões.
Tudo aqui é determinístico com um random.Random e está nos testes.
"""

from __future__ import annotations

import random
import re
import unicodedata
from collections import Counter


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


# ═══ jogo da velha ═════════════════════════════════════════════════════════════
LINHAS_VELHA = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def velha_vencedor(t: list[str]) -> str:
    """'X', 'O', 'empate' ou ''."""
    for a, b, c in LINHAS_VELHA:
        if t[a] and t[a] == t[b] == t[c]:
            return t[a]
    return "empate" if all(t) else ""


def _minimax(t: list[str], vez: str, eu: str) -> int:
    v = velha_vencedor(t)
    if v:
        return 0 if v == "empate" else (10 if v == eu else -10)
    outro = "O" if vez == "X" else "X"
    notas = []
    for i in range(9):
        if not t[i]:
            t[i] = vez
            notas.append(_minimax(t, outro, eu) * 0.9)
            t[i] = ""
    return max(notas) if vez == eu else min(notas)


def velha_jogada(t: list[str], eu: str, nivel: str = "dificil", rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    livres = [i for i in range(9) if not t[i]]
    if not livres:
        return -1
    if nivel == "facil" or (nivel == "medio" and rng.random() < 0.35):
        return rng.choice(livres)
    outro = "O" if eu == "X" else "X"
    notas = []
    for i in livres:
        t[i] = eu
        notas.append((_minimax(t, outro, eu), i))
        t[i] = ""
    melhor = max(n for n, _ in notas)
    return rng.choice([i for n, i in notas if n == melhor])


def velha_desenho(t: list[str]) -> str:
    c = [t[i] or str(i + 1) for i in range(9)]
    return "\n───┼───┼───\n".join(f" {c[r * 3]} │ {c[r * 3 + 1]} │ {c[r * 3 + 2]}" for r in range(3))


POSICOES_FALADAS = {
    "canto superior esquerdo": 0, "em cima no meio": 1, "meio de cima": 1, "canto superior direito": 2,
    "meio da esquerda": 3, "centro": 4, "meio": 4, "meio da direita": 5,
    "canto inferior esquerdo": 6, "embaixo no meio": 7, "meio de baixo": 7, "canto inferior direito": 8,
}
NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "nove": 9, "dez": 10}


def ler_numero(texto: str) -> int | None:
    t = dobrar(str(texto))
    m = re.search(r"-?\d+", t)
    if m:
        return int(m.group())
    for palavra, n in NUMEROS.items():
        if re.search(rf"\b{palavra}\b", t):
            return n
    return None


def velha_ler(texto: str) -> int | None:
    """'5', 'cinco', 'centro', 'canto superior direito' → índice 0..8."""
    t = dobrar(str(texto))
    for frase, i in sorted(POSICOES_FALADAS.items(), key=lambda x: -len(x[0])):
        if frase in t:
            return i
    n = ler_numero(t)
    return n - 1 if n is not None and 1 <= n <= 9 else None


# ═══ Lig 4 ═════════════════════════════════════════════════════════════════════
COLS, LINS = 7, 6


def lig4_novo() -> list[list[str]]:
    """Lista de colunas; cada coluna cresce de baixo para cima."""
    return [[] for _ in range(COLS)]


def lig4_soltar(cols: list[list[str]], c: int, peca: str) -> bool:
    if 0 <= c < COLS and len(cols[c]) < LINS:
        cols[c].append(peca)
        return True
    return False


def _em(cols, c, r):
    return cols[c][r] if 0 <= c < COLS and 0 <= r < len(cols[c]) else ""


def lig4_vencedor(cols: list[list[str]]) -> str:
    for c in range(COLS):
        for r in range(len(cols[c])):
            p = cols[c][r]
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if all(_em(cols, c + dc * k, r + dr * k) == p for k in range(1, 4)):
                    return p
    return "empate" if all(len(x) == LINS for x in cols) else ""


def _lig4_nota(cols, eu, outro) -> int:
    nota = 0
    for c in range(COLS):
        for r in range(LINS):
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                janela = [_em(cols, c + dc * k, r + dr * k) if 0 <= r + dr * k < LINS and 0 <= c + dc * k < COLS
                          else None for k in range(4)]
                if None in janela:
                    continue
                n_eu, n_ou = janela.count(eu), janela.count(outro)
                if n_eu and not n_ou:
                    nota += (1, 4, 20, 1000)[n_eu - 1]
                elif n_ou and not n_eu:
                    nota -= (1, 5, 25, 1000)[n_ou - 1]
    return nota + sum(3 for x in cols[3] if x == eu)


def _lig4_busca(cols, prof, alfa, beta, vez, eu, outro):
    v = lig4_vencedor(cols)
    if v:
        return 0 if v == "empate" else (100000 + prof if v == eu else -100000 - prof)
    if prof == 0:
        return _lig4_nota(cols, eu, outro)
    ordem = sorted(range(COLS), key=lambda c: abs(3 - c))
    if vez == eu:
        melhor = -10 ** 9
        for c in ordem:
            if len(cols[c]) < LINS:
                cols[c].append(eu)
                melhor = max(melhor, _lig4_busca(cols, prof - 1, alfa, beta, outro, eu, outro))
                cols[c].pop()
                alfa = max(alfa, melhor)
                if alfa >= beta:
                    break
        return melhor
    pior = 10 ** 9
    for c in ordem:
        if len(cols[c]) < LINS:
            cols[c].append(outro)
            pior = min(pior, _lig4_busca(cols, prof - 1, alfa, beta, eu, eu, outro))
            cols[c].pop()
            beta = min(beta, pior)
            if alfa >= beta:
                break
    return pior


def lig4_jogada(cols: list[list[str]], eu: str, nivel: str = "medio", rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    livres = [c for c in range(COLS) if len(cols[c]) < LINS]
    if not livres:
        return -1
    if nivel == "facil":
        return rng.choice(livres)
    outro = "O" if eu == "X" else "X"
    prof = 3 if nivel == "medio" else 5
    notas = []
    for c in livres:
        cols[c].append(eu)
        notas.append((_lig4_busca(cols, prof - 1, -10 ** 9, 10 ** 9, outro, eu, outro), c))
        cols[c].pop()
    melhor = max(n for n, _ in notas)
    return rng.choice([c for n, c in notas if n == melhor])


def lig4_desenho(cols: list[list[str]]) -> str:
    sim = {"X": "🔴", "O": "🟡", "": "⚪"}
    linhas = ["".join(sim[_em(cols, c, r)] for c in range(COLS)) for r in range(LINS - 1, -1, -1)]
    return "\n".join(linhas + ["1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"])


# ═══ forca ═════════════════════════════════════════════════════════════════════
PALAVRAS = {
    "animais": ["capivara", "tamandua", "jacare", "papagaio", "onca", "tucano", "golfinho", "elefante", "girafa",
                "borboleta", "tartaruga", "pinguim", "camaleao", "jabuti", "sucuri", "lobo guara", "morcego"],
    "frutas": ["jabuticaba", "acerola", "pitanga", "goiaba", "abacaxi", "maracuja", "caju", "cupuacu", "graviola",
               "melancia", "carambola", "tangerina", "pequi", "acai", "mangaba"],
    "comidas": ["feijoada", "pamonha", "coxinha", "brigadeiro", "pao de queijo", "tapioca", "moqueca", "pastel",
                "empadao", "galinhada", "quindim", "acaraje", "farofa", "churrasco"],
    "tecnologia": ["teclado", "processador", "algoritmo", "internet", "servidor", "programador", "aplicativo",
                   "computador", "impressora", "roteador", "microfone", "bateria", "robo", "inteligencia"],
    "lugares": ["goiania", "pirenopolis", "chapada", "amazonia", "pantanal", "salvador", "florianopolis",
                "fortaleza", "brasilia", "curitiba", "manaus", "recife", "caldas novas"],
    "objetos": ["guarda chuva", "travesseiro", "geladeira", "liquidificador", "ventilador", "escova", "tesoura",
                "cadeira", "espelho", "mochila", "bicicleta", "relogio"],
}
MAX_ERROS = 6


def forca_nova(tema: str = "", rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    tema = next((k for k in PALAVRAS if k.startswith(dobrar(tema)[:4])), "") if tema else ""
    tema = tema or rng.choice(list(PALAVRAS))
    return {"tema": tema, "palavra": rng.choice(PALAVRAS[tema]), "letras": [], "erros": 0}


def forca_mascara(f: dict) -> str:
    return " ".join(ch if ch == " " or ch in f["letras"] else "_" for ch in f["palavra"]).replace("   ", "  /  ")


def forca_estado(f: dict) -> str:
    if all(ch == " " or ch in f["letras"] for ch in f["palavra"]):
        return "ganhou"
    return "perdeu" if f["erros"] >= MAX_ERROS else ""


def forca_chutar(f: dict, chute: str) -> str:
    """Chute de letra ('a', 'letra a', 'é a letra e') ou palavra inteira. Muda f e devolve a resposta."""
    t = dobrar(chute).strip()
    t = re.sub(r"^(e a |eh a |a )?letra\s+", "", t).strip()
    if len(t.replace(" ", "")) > 1 and t != "":
        if t == f["palavra"]:
            f["letras"] = sorted(set(f["palavra"].replace(" ", "")))
            return "acertou a palavra"
        f["erros"] += 1
        return "palavra errada"
    letra = t[:1]
    if not letra.isalpha():
        return "diga uma letra"
    if letra in f["letras"]:
        return f"a letra {letra} já foi"
    f["letras"].append(letra)
    if letra in f["palavra"]:
        return f"tem {f['palavra'].count(letra)} {letra.upper()}"
    f["erros"] += 1
    return f"não tem {letra.upper()}"


BONECO = [" ┌──┐\n │\n │\n │\n─┴─", " ┌──┐\n │  O\n │\n │\n─┴─", " ┌──┐\n │  O\n │  |\n │\n─┴─",
          " ┌──┐\n │  O\n │ /|\n │\n─┴─", " ┌──┐\n │  O\n │ /|\\\n │\n─┴─", " ┌──┐\n │  O\n │ /|\\\n │ /\n─┴─",
          " ┌──┐\n │  O\n │ /|\\\n │ / \\\n─┴─"]


def forca_desenho(f: dict) -> str:
    erradas = [x for x in f["letras"] if x not in f["palavra"]]
    return (f"{BONECO[min(f['erros'], MAX_ERROS)]}\n\nTema: {f['tema']}\n{forca_mascara(f).upper()}\n"
            f"Erradas: {' '.join(erradas).upper() or '—'}   ({MAX_ERROS - f['erros']} vidas)")


# ═══ pedra, papel, tesoura (IA que aprende) ════════════════════════════════════
PPT = ("pedra", "papel", "tesoura")
GANHA_DE = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}
VENCE = {v: k for k, v in GANHA_DE.items()}             # quem vence cada um


def ppt_ler(texto: str) -> str | None:
    t = dobrar(texto)
    for x in PPT:
        if x in t:
            return x
    return None


def ppt_jogada(historico: list[str], rng: random.Random | None = None) -> str:
    """Olha o que você costuma jogar depois do seu último lance (cadeia de Markov) e joga o que vence isso."""
    rng = rng or random.Random()
    if len(historico) < 3:
        return rng.choice(PPT)
    ultimo = historico[-1]
    seguintes = Counter(b for a, b in zip(historico, historico[1:]) if a == ultimo)
    if not seguintes:
        seguintes = Counter(historico)
    previsto = seguintes.most_common(1)[0][0]
    return VENCE[previsto] if rng.random() < 0.85 else rng.choice(PPT)


def ppt_resultado(voce: str, eu: str) -> str:
    if voce == eu:
        return "empate"
    return "voce" if GANHA_DE[voce] == eu else "eu"
