"""Banner ASCII (2.19): escreve um texto em letras grandes para o topo do README, do terminal ou de um comentário; e faz molduras."""
from __future__ import annotations

from plugins._lote2 import P, norm, rodar

PLUGIN = P("banner_ascii", "Big ASCII-art text banner for READMEs/terminals and a box frame around text; copies the result to the clipboard.",
           "gerar | moldura", "texto (A-Z, 0-9; up to ~14 chars for gerar), caractere (default #).", "texto caractere")

F = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !.-?", (
    " ### /#   #/#####/#   #/#   #|#### /#   #/#### /#   #/#### | ####/#    /#    /#    / ####|#### /#   #/#   #/#   #/#### |"
    "#####/#    /###  /#    /#####|#####/#    /###  /#    /#    | ####/#    /#  ##/#   #/ ####|#   #/#   #/#####/#   #/#   #|"
    "###/ # / # / # /###|    #/    #/    #/#   #/ ### |#   #/#  # /###  /#  # /#   #|#    /#    /#    /#    /#####|"
    "#   #/## ##/# # #/#   #/#   #|#   #/##  #/# # #/#  ##/#   #| ### /#   #/#   #/#   #/ ### |#### /#   #/#### /#    /#    |"
    " ### /#   #/# # #/#  # / ## #|#### /#   #/#### /#  # /#   #| ####/#    / ### /    #/#### |#####/  #  /  #  /  #  /  #  |"
    "#   #/#   #/#   #/#   #/ ### |#   #/#   #/#   #/ # # /  #  |#   #/#   #/# # #/## ##/#   #|#   #/ # # /  #  / # # /#   #|"
    "#   #/ # # /  #  /  #  /  #  |#####/   # /  #  / #   /#####| ### /#  ##/# # #/##  #/ ### |  #  / ##  /  #  /  #  / ### |"
    " ### /#   #/  ## / #   /#####|#### /    #/ ### /    #/#### |#   #/#   #/#####/    #/    #|#####/#    /#### /    #/#### |"
    " ### /#    /#### /#   #/ ### |#####/    #/   # /  #  /  #  | ### /#   #/ ### /#   #/ ### | ### /#   #/ ####/    #/ ### |"
    "   /   /   /   /   |#/#/#/ /#| / / / /#|    /    /####/    /    | ### /#   #/  ## /     /  #  ").split("|")))


def banner(texto: str, ch: str = "#") -> str:
    letras = [F[c].split("/") for c in norm(texto).upper() if c in F]
    if not letras:
        raise ValueError("só letras, números e ! . - ?")
    return "\n".join("  ".join(l[i] for l in letras).replace("#", ch).rstrip() for i in range(5))


def moldura(texto: str) -> str:
    linhas = str(texto).splitlines() or [""]
    w = max(map(len, linhas))
    return "\n".join(["╔" + "═" * (w + 2) + "╗"] + [f"║ {l:<{w}} ║" for l in linhas] + ["╚" + "═" * (w + 2) + "╝"])


def _go(p, pl):
    t = str(p.get("texto") or "JARVIS")
    r = moldura(t) if p["action"] == "moldura" else banner(t, (str(p.get("caractere") or "#") or "#")[0])
    try:
        import pyperclip
        pyperclip.copy(r)
    except Exception:
        pass
    return r


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"gerar": _go, "moldura": _go}, player, "Banner")
