"""
Motor de xadrez próprio do J.A.R.V.I.S BR (1.7). Começa com "_": não é ferramenta.

Sem instalar nada: regras completas (roque, en passant, promoção, xeque,
xeque-mate, afogamento, material insuficiente), FEN para salvar a partida,
busca alfa-beta com ordenação de capturas e tabelas de posição.
Casas: 0 = a1 … 63 = h8 (índice = fileira × 8 + coluna).
"""

from __future__ import annotations

import random
import re

INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
VALOR = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
NOMES = {"K": "rei", "Q": "dama", "R": "torre", "B": "bispo", "N": "cavalo", "P": "peão"}
PECAS_PT = {"rei": "K", "dama": "Q", "rainha": "Q", "torre": "R", "bispo": "B", "cavalo": "N", "peao": "P"}
_N = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
_K = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
_B = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_R = [(1, 0), (-1, 0), (0, 1), (0, -1)]
# bônus de posição (do ponto de vista das brancas, a1 = índice 0)
_PST = {
    "P": [0] * 8 + [5, 10, 10, -20, -20, 10, 10, 5] + [5, -5, -10, 0, 0, -10, -5, 5] + [0, 0, 0, 20, 20, 0, 0, 0]
         + [5, 5, 10, 25, 25, 10, 5, 5] + [10, 10, 20, 30, 30, 20, 10, 10] + [50] * 8 + [0] * 8,
    "N": [-50, -40, -30, -30, -30, -30, -40, -50] + [-40, -20, 0, 5, 5, 0, -20, -40] + [-30, 5, 10, 15, 15, 10, 5, -30]
         + [-30, 0, 15, 20, 20, 15, 0, -30] * 2 + [-30, 5, 10, 15, 15, 10, 5, -30] + [-40, -20, 0, 0, 0, 0, -20, -40]
         + [-50, -40, -30, -30, -30, -30, -40, -50],
    "B": [-20, -10, -10, -10, -10, -10, -10, -20] + [-10, 5, 0, 0, 0, 0, 5, -10] + [-10, 10, 10, 10, 10, 10, 10, -10]
         + [-10, 0, 10, 10, 10, 10, 0, -10] * 2 + [-10, 0, 5, 10, 10, 5, 0, -10] + [-10, 0, 0, 0, 0, 0, 0, -10]
         + [-20, -10, -10, -10, -10, -10, -10, -20],
    "R": [0, 0, 0, 5, 5, 0, 0, 0] + [-5, 0, 0, 0, 0, 0, 0, -5] * 5 + [5, 10, 10, 10, 10, 10, 10, 5] + [0] * 8,
    "Q": [-20, -10, -10, -5, -5, -10, -10, -20] + [-10, 0, 5, 0, 0, 0, 0, -10] + [-10, 5, 5, 5, 5, 5, 0, -10]
         + [0, 0, 5, 5, 5, 5, 0, -5] + [-5, 0, 5, 5, 5, 5, 0, -5] + [-10, 0, 5, 5, 5, 5, 0, -10]
         + [-10, 0, 0, 0, 0, 0, 0, -10] + [-20, -10, -10, -5, -5, -10, -10, -20],
    "K": [20, 30, 10, 0, 0, 10, 30, 20] + [20, 20, 0, 0, 0, 0, 20, 20] + [-10, -20, -20, -20, -20, -20, -20, -10]
         + [-20, -30, -30, -40, -40, -30, -30, -20] + [-30, -40, -40, -50, -50, -40, -40, -30] * 4,
}


def nome_casa(i: int) -> str:
    return "abcdefgh"[i % 8] + str(i // 8 + 1)


def casa(nome: str) -> int:
    return (int(nome[1]) - 1) * 8 + "abcdefgh".index(nome[0])


def branca(p: str) -> bool:
    return p.isupper()


class Posicao:
    __slots__ = ("tab", "vez", "roques", "ep", "meio", "lance")

    def __init__(self, fen: str = INICIAL):
        partes = fen.split()
        self.tab = [""] * 64
        for r, linha in enumerate(partes[0].split("/")):
            f = 0
            for ch in linha:
                if ch.isdigit():
                    f += int(ch)
                else:
                    self.tab[(7 - r) * 8 + f] = ch
                    f += 1
        self.vez = partes[1] if len(partes) > 1 else "w"
        self.roques = partes[2] if len(partes) > 2 and partes[2] != "-" else ""
        self.ep = casa(partes[3]) if len(partes) > 3 and partes[3] != "-" else -1
        self.meio = int(partes[4]) if len(partes) > 4 else 0
        self.lance = int(partes[5]) if len(partes) > 5 else 1

    def fen(self) -> str:
        linhas = []
        for r in range(7, -1, -1):
            s, vazio = "", 0
            for f in range(8):
                p = self.tab[r * 8 + f]
                if p:
                    s += (str(vazio) if vazio else "") + p
                    vazio = 0
                else:
                    vazio += 1
            linhas.append(s + (str(vazio) if vazio else ""))
        return (f"{'/'.join(linhas)} {self.vez} {self.roques or '-'} {nome_casa(self.ep) if self.ep >= 0 else '-'} "
                f"{self.meio} {self.lance}")

    def copia(self) -> "Posicao":
        n = Posicao.__new__(Posicao)
        n.tab, n.vez, n.roques, n.ep, n.meio, n.lance = self.tab[:], self.vez, self.roques, self.ep, self.meio, self.lance
        return n

    # ── ataques e lances ─────────────────────────────────────────────────────
    def atacada(self, sq: int, por_brancas: bool) -> bool:
        r, f = divmod(sq, 8)
        d = -1 if por_brancas else 1                          # de onde viria o peão atacante
        for df in (-1, 1):
            rr, ff = r + d, f + df
            if 0 <= rr < 8 and 0 <= ff < 8 and self.tab[rr * 8 + ff] == ("P" if por_brancas else "p"):
                return True
        for dr, df in _N:
            rr, ff = r + dr, f + df
            if 0 <= rr < 8 and 0 <= ff < 8 and self.tab[rr * 8 + ff] == ("N" if por_brancas else "n"):
                return True
        for dr, df in _K:
            rr, ff = r + dr, f + df
            if 0 <= rr < 8 and 0 <= ff < 8 and self.tab[rr * 8 + ff] == ("K" if por_brancas else "k"):
                return True
        for dirs, alvos in ((_B, "BQ"), (_R, "RQ")):
            alvos = alvos if por_brancas else alvos.lower()
            for dr, df in dirs:
                rr, ff = r + dr, f + df
                while 0 <= rr < 8 and 0 <= ff < 8:
                    p = self.tab[rr * 8 + ff]
                    if p:
                        if p in alvos:
                            return True
                        break
                    rr, ff = rr + dr, ff + df
        return False

    def em_xeque(self, brancas: bool | None = None) -> bool:
        brancas = (self.vez == "w") if brancas is None else brancas
        rei = "K" if brancas else "k"
        try:
            return self.atacada(self.tab.index(rei), not brancas)
        except ValueError:
            return True

    def pseudo(self) -> list[tuple[int, int, str]]:
        brancas = self.vez == "w"
        lances = []
        for sq, p in enumerate(self.tab):
            if not p or branca(p) != brancas:
                continue
            r, f = divmod(sq, 8)
            t = p.upper()
            if t == "P":
                d, inicio, ultima = (1, 1, 7) if brancas else (-1, 6, 0)
                um = sq + 8 * d
                if 0 <= um < 64 and not self.tab[um]:
                    self._peao(lances, sq, um, ultima)
                    dois = sq + 16 * d
                    if r == inicio and not self.tab[dois]:
                        lances.append((sq, dois, ""))
                for df in (-1, 1):
                    ff, rr = f + df, r + d
                    if 0 <= ff < 8 and 0 <= rr < 8:
                        alvo = rr * 8 + ff
                        q = self.tab[alvo]
                        if (q and branca(q) != brancas) or alvo == self.ep:
                            self._peao(lances, sq, alvo, ultima)
            elif t in "NK":
                for dr, df in (_N if t == "N" else _K):
                    rr, ff = r + dr, f + df
                    if 0 <= rr < 8 and 0 <= ff < 8:
                        q = self.tab[rr * 8 + ff]
                        if not q or branca(q) != brancas:
                            lances.append((sq, rr * 8 + ff, ""))
                if t == "K":
                    self._roques(lances, sq, brancas)
            else:
                dirs = _B if t == "B" else _R if t == "R" else _B + _R
                for dr, df in dirs:
                    rr, ff = r + dr, f + df
                    while 0 <= rr < 8 and 0 <= ff < 8:
                        q = self.tab[rr * 8 + ff]
                        if q:
                            if branca(q) != brancas:
                                lances.append((sq, rr * 8 + ff, ""))
                            break
                        lances.append((sq, rr * 8 + ff, ""))
                        rr, ff = rr + dr, ff + df
        return lances

    @staticmethod
    def _peao(lances, de, para, ultima):
        if para // 8 == ultima:
            lances += [(de, para, x) for x in "QRBN"]
        else:
            lances.append((de, para, ""))

    def _roques(self, lances, sq, brancas):
        base = 0 if brancas else 56
        if sq != base + 4 or self.em_xeque(brancas):
            return
        k, q = ("K", "Q") if brancas else ("k", "q")
        torre = "R" if brancas else "r"
        if k in self.roques and self.tab[base + 7] == torre and not self.tab[base + 5] and not self.tab[base + 6] \
                and not self.atacada(base + 5, not brancas) and not self.atacada(base + 6, not brancas):
            lances.append((sq, base + 6, ""))
        if q in self.roques and self.tab[base] == torre and not self.tab[base + 1] and not self.tab[base + 2] \
                and not self.tab[base + 3] and not self.atacada(base + 3, not brancas) and not self.atacada(base + 2, not brancas):
            lances.append((sq, base + 2, ""))

    def jogar(self, lance: tuple[int, int, str]) -> "Posicao":
        de, para, promo = lance
        n = self.copia()
        p = n.tab[de]
        brancas = branca(p)
        capturou = bool(n.tab[para])
        n.tab[para], n.tab[de] = p, ""
        if p.upper() == "P":
            if para == self.ep:                                 # en passant: tira o peão de trás
                n.tab[para - 8 if brancas else para + 8] = ""
                capturou = True
            if promo:
                n.tab[para] = promo if brancas else promo.lower()
        if p.upper() == "K" and abs(para - de) == 2:            # roque: a torre pula
            if para % 8 == 6:
                n.tab[para - 1], n.tab[para + 1] = n.tab[para + 1], ""
            else:
                n.tab[para + 1], n.tab[para - 2] = n.tab[para - 2], ""
        n.ep = (de + para) // 2 if p.upper() == "P" and abs(para - de) == 16 else -1
        tira = {4: "KQ", 0: "Q", 7: "K", 60: "kq", 56: "q", 63: "k"}
        for sq in (de, para):
            for c in tira.get(sq, ""):
                n.roques = n.roques.replace(c, "")
        n.meio = 0 if capturou or p.upper() == "P" else n.meio + 1
        if not brancas:
            n.lance += 1
        n.vez = "b" if brancas else "w"
        return n

    def legais(self) -> list[tuple[int, int, str]]:
        brancas = self.vez == "w"
        return [m for m in self.pseudo() if not self.jogar(m).em_xeque(brancas)]

    def captura(self, lance) -> bool:
        return bool(self.tab[lance[1]]) or (self.tab[lance[0]].upper() == "P" and lance[1] == self.ep)

    def resultado(self) -> str:
        """'' em andamento; 'mate_brancas' (brancas venceram), 'mate_pretas', 'afogado', 'empate'."""
        if not self.legais():
            if self.em_xeque():
                return "mate_pretas" if self.vez == "w" else "mate_brancas"
            return "afogado"
        pecas = [p for p in self.tab if p and p.upper() != "K"]
        if not pecas or (len(pecas) == 1 and pecas[0].upper() in "NB") or self.meio >= 100:
            return "empate"
        return ""


# ── avaliação e busca ─────────────────────────────────────────────────────────
def avaliar(pos: Posicao) -> int:
    """Pontos do ponto de vista de quem joga."""
    total = 0
    for sq, p in enumerate(pos.tab):
        if not p:
            continue
        t = p.upper()
        if branca(p):
            total += VALOR[t] + _PST[t][sq]
        else:
            total -= VALOR[t] + _PST[t][(7 - sq // 8) * 8 + sq % 8]
    return total if pos.vez == "w" else -total


def _ordem(pos: Posicao, lances):
    return sorted(lances, key=lambda m: -(VALOR.get(pos.tab[m[1]].upper(), 0) if pos.tab[m[1]] else 0)
                  - (800 if m[2] == "Q" else 0))


def _busca(pos: Posicao, prof: int, alfa: int, beta: int) -> int:
    if prof == 0:
        return _quieta(pos, alfa, beta, 3)
    lances = pos.legais()
    if not lances:
        return -100000 - prof if pos.em_xeque() else 0
    for m in _ordem(pos, lances):
        v = -_busca(pos.jogar(m), prof - 1, -beta, -alfa)
        if v >= beta:
            return v
        alfa = max(alfa, v)
    return alfa


def _quieta(pos: Posicao, alfa: int, beta: int, limite: int) -> int:
    parado = avaliar(pos)
    if parado >= beta or limite == 0:
        return parado
    alfa = max(alfa, parado)
    for m in _ordem(pos, [m for m in pos.pseudo() if pos.captura(m)]):
        nova = pos.jogar(m)
        if nova.em_xeque(pos.vez == "w"):
            continue
        v = -_quieta(nova, -beta, -alfa, limite - 1)
        if v >= beta:
            return v
        alfa = max(alfa, v)
    return alfa


def melhor_lance(pos: Posicao, nivel: str = "medio", rng: random.Random | None = None):
    rng = rng or random.Random()
    lances = pos.legais()
    if not lances:
        return None
    if nivel == "facil":
        capturas = [m for m in lances if pos.captura(m)]
        return rng.choice(capturas if capturas and rng.random() < 0.6 else lances)
    prof, folga = (2, 5) if nivel == "medio" else (4, 0)
    notas = []
    alfa = -10 ** 9
    for m in _ordem(pos, lances):
        # janela: só interessa saber se o lance chega perto do melhor até agora (o resto é cortado)
        v = -_busca(pos.jogar(m), prof - 1, -10 ** 9, -(alfa - folga - 1))
        notas.append((v, m))
        alfa = max(alfa, v)
    melhor = max(v for v, _m in notas)
    return rng.choice([m for v, m in notas if v >= melhor - folga])


# ── fala ──────────────────────────────────────────────────────────────────────
def _dobrar(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def ler_lance(pos: Posicao, fala: str):
    """Texto falado ('cavalo para f3', 'e2 e4', 'roque pequeno', 'peão e8 vira dama') → (lance, '') ou (None, motivo)."""
    t = _dobrar(fala)
    legais = pos.legais()
    if "roque" in t:
        base = 0 if pos.vez == "w" else 56
        alvo = base + (2 if ("grande" in t or "longo" in t) else 6)
        m = next((x for x in legais if x[0] == base + 4 and x[1] == alvo and pos.tab[x[0]].upper() == "K"), None)
        return (m, "") if m else (None, "O roque não é possível agora.")
    casas = [casa(a + b) for a, b in re.findall(r"\b([a-h])\s*([1-8])\b", t)]
    if not casas:
        return None, "Não entendi o lance. Diga a peça e a casa, como 'cavalo para f3' ou 'e2 e4'."
    destino, origem = casas[-1], (casas[0] if len(casas) >= 2 else None)
    padrao_promo = r"(vira|promov\w*|coroa\w*|=)\s*(a |em |um |uma )?(dama|rainha|torre|bispo|cavalo)"
    achou = re.search(padrao_promo, t)
    promo = PECAS_PT[achou.group(3)] if achou else "Q"
    sem_promo = re.sub(padrao_promo, " ", t)
    tipo = next((v for k, v in PECAS_PT.items() if re.search(rf"\b{k}\b", sem_promo)), None)
    cands = [m for m in legais if m[1] == destino and (origem is None or m[0] == origem)]
    if tipo:
        cands = [m for m in cands if pos.tab[m[0]].upper() == tipo]
    elif origem is None:
        cands = [m for m in cands if pos.tab[m[0]].upper() == "P"] or cands
    if any(m[2] for m in cands):
        cands = [m for m in cands if m[2] == promo]
    if len(cands) == 1:
        return cands[0], ""
    if not cands:
        return None, "Esse lance não é permitido agora."
    return None, "Qual deles: de " + " ou ".join(sorted({nome_casa(m[0]) for m in cands})) + "?"


def falar_lance(pos: Posicao, lance) -> str:
    de, para, promo = lance
    p = pos.tab[de].upper()
    if p == "K" and abs(para - de) == 2:
        texto = "roque pequeno" if para % 8 == 6 else "roque grande"
    else:
        texto = f"{NOMES[p]} {'captura em' if pos.captura(lance) else 'para'} {nome_casa(para)}"
        if promo:
            texto += f", vira {NOMES[promo]}"
    depois = pos.jogar(lance)
    r = depois.resultado()
    if r.startswith("mate"):
        texto += ", xeque-mate"
    elif depois.em_xeque():
        texto += ", xeque"
    return texto


SIMBOLOS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
            "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}


def desenho(pos: Posicao, brancas_embaixo: bool = True) -> str:
    linhas = []
    for r in (range(7, -1, -1) if brancas_embaixo else range(8)):
        linha = f"{r + 1} "
        for f in (range(8) if brancas_embaixo else range(7, -1, -1)):
            p = pos.tab[r * 8 + f]
            linha += (SIMBOLOS[p] if p else ("·" if (r + f) % 2 else "▪")) + " "
        linhas.append(linha)
    linhas.append("  " + " ".join("abcdefgh" if brancas_embaixo else "hgfedcba"))
    return "\n".join(linhas)


def perft(pos: Posicao, prof: int) -> int:
    """Contagem de posições (confere as regras contra os números conhecidos)."""
    if prof == 0:
        return 1
    return sum(perft(pos.jogar(m), prof - 1) for m in pos.legais())
