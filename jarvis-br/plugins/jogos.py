"""
Modo diversão / Arcade J.A.R.V.I.S (fork PT-BR 1.7).

    "Jarvis, abre os jogos"            → janela do Arcade com 14 jogos clicáveis
    "Jarvis, abre o campo minado"      → já abre no jogo
    Por voz, sem janela:
    "Jarvis, jogo da velha"  → "no centro" / "posição 3"
    "Jarvis, lig 4"          → "coluna 4"
    "Jarvis, forca"          → "letra a" / "é capivara"
    "Jarvis, adivinha o número" → "50"
    "Jarvis, pedra papel tesoura" → "pedra"
    "Jarvis, meu placar"

Xadrez e damas do Arcade são a mesma partida da ferramenta xadrez (clicar e
falar mexem no mesmo jogo). Nada aqui precisa de pacote extra.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess

from plugins import _jogos as J
from plugins._comum import CNW, MEMORIA, WIN, abrir_no_sistema, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "jogos",
    "brief": "Arcade window with 14 games (chess, checkers, tic-tac-toe, connect 4, minesweeper, 2048, snake, "
             "blocks, breakout, memory, hangman, simon, rock-paper-scissors, reflex) plus voice games.",
    "description": (
        "Fun mode. action='abrir' opens the Arcade window (optional jogo: xadrez, damas, velha, lig4, minas, 2048, "
        "cobrinha, tetris, breakout, memoria, forca, genius, ppt, reflexo, cacapalavras, meteoros, labirinto, sudoku, "
        "pong; 'pac man' opens labirinto, an original maze game). Voice games without a window: "
        "action='velha' with posicao (1-9 or words like 'centro'); action='lig4' with coluna (1-7); action='forca' "
        "with chute (letter or whole word); action='adivinha' with numero; action='ppt' with escolha "
        "(pedra|papel|tesoura); start any of them fresh with action='novo' + jogo (+ optional nivel facil|medio|dificil, "
        "tema for forca); action='placar' reads the scores. Read the reply as returned."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "abrir | novo | velha | lig4 | forca | adivinha | ppt | placar"},
            "jogo": {"type": "STRING"}, "nivel": {"type": "STRING"}, "tema": {"type": "STRING"},
            "posicao": {"type": "STRING"}, "coluna": {"type": "STRING"}, "chute": {"type": "STRING"},
            "numero": {"type": "STRING"}, "escolha": {"type": "STRING"},
        },
        "required": [],
    },
}

ARQ = MEMORIA / "jogos_voz.json"
JOGOS_ARCADE = {"caca": "cacapalavras", "palavras": "cacapalavras",                       # 2.5 (antes da forca)
                "meteor": "meteoros", "asteroid": "meteoros", "nave": "meteoros", "labirint": "labirinto",
                "pac": "labirinto", "bitinho": "labirinto", "sudoku": "sudoku", "pong": "pong", "ping": "pong",
                "raquete": "pong",
                "xadrez": "xadrez", "damas": "damas", "velha": "velha", "lig": "lig4", "minad": "minas",
                "minas": "minas", "2048": "2048", "cobr": "cobrinha", "snake": "cobrinha", "tetris": "tetris",
                "bloco": "tetris", "breakout": "breakout", "tijolo": "breakout", "memoria": "memoria",
                "forca": "forca", "genius": "genius", "simon": "genius", "pedra": "ppt", "ppt": "ppt",
                "reflexo": "reflexo", "alvo": "reflexo"}
NOMES_PLACAR = {"xadrez": "Xadrez", "damas": "Damas", "velha": "Jogo da velha", "lig4": "Lig 4", "minas": "Campo minado",
                "2048": "2048", "cobrinha": "Cobrinha", "tetris": "Blocos", "breakout": "Quebra-tijolos",
                "memoria": "Memória", "forca": "Forca", "genius": "Genius", "ppt": "Pedra, papel, tesoura",
                "reflexo": "Reflexo", "adivinha": "Adivinha o número",
                "cacapalavras": "Caça-palavras", "meteoros": "Meteoros", "labirinto": "Labirinto do Bitinho",
                "sudoku": "Sudoku", "pong": "Pong"}


def qual_jogo(texto: str) -> str:
    t = J.dobrar(texto)
    return next((v for k, v in JOGOS_ARCADE.items() if k in t), "")


# ── janela ───────────────────────────────────────────────────────────────────
def _abrir_janela(url: str) -> bool:
    """Edge/Chrome em modo app (janela própria, sem abas); senão o navegador padrão."""
    if WIN:
        for exe in ("msedge", "chrome"):
            caminho = shutil.which(exe)
            if not caminho:
                for base in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                             r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
                    if exe in base.lower() and os.path.exists(base):
                        caminho = base
            if caminho:
                try:
                    subprocess.Popen([caminho, f"--app={url}", "--window-size=1180,860"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **CNW)
                    return True
                except OSError:
                    pass
    return abrir_no_sistema(url)


def abrir(jogo: str = "", player=None) -> str:
    from plugins import _arcade
    url = _arcade.iniciar()
    if player is not None and _arcade._ao_jogar is None:
        _arcade._ao_jogar = lambda fala: mostrar(player, "ARCADE", fala)
    jogo = qual_jogo(jogo) if jogo else ""
    if not _abrir_janela(url + (f"#{jogo}" if jogo else "")):
        return f"Não consegui abrir a janela. Abra no navegador: {url}"
    nome = NOMES_PLACAR.get(jogo, "")
    return (f"Arcade aberto no {nome}." if nome else
            "Arcade aberto: xadrez, damas, jogo da velha, lig 4, campo minado, 2048, cobrinha, blocos, "
            "quebra-tijolos, memória, forca, genius, pedra-papel-tesoura, reflexo, caça-palavras, meteoros, "
            "labirinto do Bitinho, sudoku e pong.")


# ── jogos por voz ────────────────────────────────────────────────────────────
def _nivel(p) -> str:
    return next((n for n in ("facil", "medio", "dificil") if n in J.dobrar(str(p.get("nivel") or ""))), "medio")


def _placar(jogo: str, resultado: str) -> None:
    try:
        from plugins import _arcade
        _arcade.registrar(jogo, resultado)
    except Exception:
        pass


def novo(jogo: str, p: dict, d: dict, rng: random.Random, player=None) -> str:
    if jogo == "velha":
        d["velha"] = {"t": [""] * 9, "nivel": _nivel(p) if p.get("nivel") else "dificil"}
        mostrar(player, "JOGO DA VELHA", J.velha_desenho(d["velha"]["t"]))
        return "Jogo da velha: você é o X. Diga a posição de 1 a 9 (1 é o canto de cima à esquerda) ou 'centro'."
    if jogo == "lig4":
        d["lig4"] = {"cols": J.lig4_novo(), "nivel": _nivel(p)}
        mostrar(player, "LIG 4", J.lig4_desenho(d["lig4"]["cols"]))
        return "Lig 4: você é o vermelho. Diga a coluna, de 1 a 7."
    if jogo == "forca":
        d["forca"] = J.forca_nova(str(p.get("tema") or ""), rng)
        f = d["forca"]
        mostrar(player, "FORCA", J.forca_desenho(f))
        return f"Forca, tema {f['tema']}: {len(f['palavra'].replace(' ', ''))} letras. Diga uma letra."
    if jogo == "adivinha":
        maximo = {"facil": 50, "medio": 100, "dificil": 1000}[_nivel(p)]
        d["adivinha"] = {"alvo": rng.randint(1, maximo), "max": maximo, "tentativas": 0}
        return f"Pensei num número de 1 a {maximo}. Chute!"
    if jogo == "ppt":
        d["ppt"] = {"hist": [], "voce": 0, "eu": 0, "empates": 0}
        return "Pedra, papel ou tesoura? Eu aprendo seus padrões, cuidado."
    return "Jogos por voz: velha, lig 4, forca, adivinha o número e pedra-papel-tesoura. Os outros estão no Arcade."


def jogar_velha(d: dict, texto: str, rng: random.Random, player=None) -> str:
    v = d.get("velha") or {}
    t = v.get("t")
    if not t or J.velha_vencedor(t):
        return "Comece com 'jogo da velha'."
    i = J.velha_ler(texto)
    if i is None:
        return "Diga a posição de 1 a 9, ou 'centro', 'canto superior direito'…"
    if t[i]:
        return f"A posição {i + 1} já está ocupada."
    t[i] = "X"
    fim = J.velha_vencedor(t)
    meu = ""
    if not fim:
        j = J.velha_jogada(t, "O", v.get("nivel", "dificil"), rng)
        t[j] = "O"
        meu = f"Eu joguei na {j + 1}. "
        fim = J.velha_vencedor(t)
    mostrar(player, "JOGO DA VELHA", J.velha_desenho(t))
    if fim == "X":
        _placar("velha", "vitoria")
        return "Você venceu! Bem jogado."
    if fim == "O":
        _placar("velha", "derrota")
        return meu + "E fechei a linha: eu venci."
    if fim == "empate":
        _placar("velha", "empate")
        return meu + "Deu velha: empate."
    return meu + "Sua vez."


def jogar_lig4(d: dict, texto: str, rng: random.Random, player=None) -> str:
    g = d.get("lig4") or {}
    cols = g.get("cols")
    if not cols or J.lig4_vencedor(cols):
        return "Comece com 'lig 4'."
    n = J.ler_numero(texto)
    if n is None or not 1 <= n <= 7:
        return "Diga a coluna, de 1 a 7."
    if not J.lig4_soltar(cols, n - 1, "X"):
        return f"A coluna {n} está cheia."
    fim = J.lig4_vencedor(cols)
    meu = ""
    if not fim:
        c = J.lig4_jogada(cols, "O", g.get("nivel", "medio"), rng)
        J.lig4_soltar(cols, c, "O")
        meu = f"Joguei na coluna {c + 1}. "
        fim = J.lig4_vencedor(cols)
    mostrar(player, "LIG 4", J.lig4_desenho(cols))
    if fim == "X":
        _placar("lig4", "vitoria")
        return "Quatro em linha: você venceu!"
    if fim == "O":
        _placar("lig4", "derrota")
        return meu + "Quatro em linha: eu venci."
    if fim == "empate":
        _placar("lig4", "empate")
        return meu + "Tabuleiro cheio: empate."
    return meu + "Sua vez."


def jogar_forca(d: dict, texto: str, player=None) -> str:
    f = d.get("forca")
    if not f or J.forca_estado(f):
        return "Comece com 'forca'."
    r = J.forca_chutar(f, texto)
    mostrar(player, "FORCA", J.forca_desenho(f))
    e = J.forca_estado(f)
    if e == "ganhou":
        _placar("forca", "vitoria")
        return f"{r.capitalize()}! A palavra era {f['palavra']}. Você ganhou!"
    if e == "perdeu":
        _placar("forca", "derrota")
        return f"{r.capitalize()}. Enforcado! A palavra era {f['palavra']}."
    return f"{r.capitalize()}. {J.forca_mascara(f)}. Restam {J.MAX_ERROS - f['erros']} vidas."


def jogar_adivinha(d: dict, texto: str) -> str:
    a = d.get("adivinha")
    if not a or a.get("acertou"):
        return "Comece com 'adivinha o número'."
    n = J.ler_numero(texto)
    if n is None:
        return "Diga um número."
    a["tentativas"] += 1
    if n == a["alvo"]:
        a["acertou"] = True
        _placar("adivinha", "vitoria")
        return f"Acertou! Era {n}, em {a['tentativas']} tentativa{'s' if a['tentativas'] > 1 else ''}."
    perto = abs(n - a["alvo"]) <= max(2, a["max"] // 20)
    return ("Maior" if n < a["alvo"] else "Menor") + (", e está perto!" if perto else ".")


def jogar_ppt(d: dict, texto: str, rng: random.Random) -> str:
    g = d.setdefault("ppt", {"hist": [], "voce": 0, "eu": 0, "empates": 0})
    x = J.ppt_ler(texto)
    if not x:
        return "Diga pedra, papel ou tesoura."
    eu = J.ppt_jogada(g["hist"], rng)
    g["hist"] = (g["hist"] + [x])[-60:]
    r = J.ppt_resultado(x, eu)
    g[{"voce": "voce", "eu": "eu", "empate": "empates"}[r]] += 1
    frase = {"voce": "você ganhou essa", "eu": "ganhei essa", "empate": "empate"}[r]
    return f"Eu joguei {eu}: {frase}. Placar: você {g['voce']}, eu {g['eu']}."


def texto_placar() -> str:
    try:
        from plugins import _arcade
        p = _arcade.placar()
    except Exception:
        p = {}
    if not p:
        return "Ainda não há placar. Bora jogar?"
    partes = []
    for k, j in sorted(p.items(), key=lambda x: -x[1].get("partidas", 0))[:8]:
        nome = NOMES_PLACAR.get(k, k)
        if j.get("recorde"):
            partes.append(f"{nome}: recorde {j['recorde']}")
        else:
            partes.append(f"{nome}: {j.get('vitorias', 0)} vitórias, {j.get('derrotas', 0)} derrotas")
    return "Placar. " + "; ".join(partes) + "."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = J.dobrar(str(p.get("action") or "abrir"))
    rng = random.Random()
    try:
        if acao in ("abrir", "arcade", "menu"):
            return abrir(str(p.get("jogo") or ""), player)
        if acao == "placar":
            return texto_placar()
        d = ler_json(ARQ, {}) or {}
        if acao == "novo":
            jogo = qual_jogo(str(p.get("jogo") or "")) or ("adivinha" if "adivinh" in J.dobrar(str(p.get("jogo"))) else "")
            if jogo in ("xadrez", "damas"):
                return "Para xadrez e damas por voz, use a ferramenta xadrez; ou diga 'abre os jogos'."
            if jogo not in ("velha", "lig4", "forca", "adivinha", "ppt"):
                return abrir(jogo, player) if jogo else novo("", p, d, rng)
            r = novo(jogo, p, d, rng, player)
        elif acao == "velha":
            r = jogar_velha(d, str(p.get("posicao") or p.get("chute") or ""), rng, player) if d.get("velha") and \
                (p.get("posicao") or p.get("chute")) else novo("velha", p, d, rng, player)
        elif acao == "lig4":
            r = jogar_lig4(d, str(p.get("coluna") or p.get("posicao") or ""), rng, player) if d.get("lig4") and \
                (p.get("coluna") or p.get("posicao")) else novo("lig4", p, d, rng, player)
        elif acao == "forca":
            r = jogar_forca(d, str(p.get("chute")), player) if d.get("forca") and p.get("chute") else novo("forca", p, d, rng, player)
        elif acao == "adivinha":
            r = jogar_adivinha(d, str(p.get("numero") or p.get("chute"))) if d.get("adivinha") and \
                (p.get("numero") or p.get("chute")) else novo("adivinha", p, d, rng)
        elif acao == "ppt":
            r = jogar_ppt(d, str(p.get("escolha") or p.get("chute") or ""), rng) if (p.get("escolha") or p.get("chute")) \
                else novo("ppt", p, d, rng)
        else:
            return abrir(acao, player) if qual_jogo(acao) else "Ações: abrir, novo, velha, lig4, forca, adivinha, ppt, placar."
        gravar_json(ARQ, d)
        return r
    except Exception as e:
        return f"O jogo falhou: {e}"
