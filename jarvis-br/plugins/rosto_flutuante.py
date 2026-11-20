"""
Rosto flutuante por voz — plugin do J.A.R.V.I.S BR 1.3.

    "Jarvis, fica no canto da tela" / "mostra seu rosto flutuante"
    "Jarvis, vai para o canto esquerdo" / "fica maior" / "fica pequeno"
    "Jarvis, esconde o rosto"

A janelinha em si está em core/rosto_flutuante.py; aqui só se pede à
interface (pela ponte core/qt_bridge.py) para mostrar, mover ou esconder.
"""

from __future__ import annotations

PLUGIN = {
    "name": "rosto_flutuante",
    "brief": "Show/hide/move/resize JARVIS's floating face in a screen corner.",
    "description": (
        "JARVIS's animated face in a small always-on-top window in a corner of the screen, "
        "talking with subtitles while the user works or codes. action='mostrar' for 'fica no "
        "canto da tela', 'mostra seu rosto', 'modo flutuante'; 'esconder'; 'canto' with canto = "
        "inferior direito | inferior esquerdo | superior direito | superior esquerdo; 'tamanho' "
        "with tamanho = pequeno | médio | grande | maior | menor."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mostrar | esconder | canto | tamanho"},
            "canto": {"type": "STRING"},
            "tamanho": {"type": "STRING"},
        },
        "required": ["action"],
    },
}


def _na_interface(player, funcao) -> bool:
    from core import qt_bridge
    win = getattr(player, "_win", None)
    if win is None or not qt_bridge.disponivel():
        return False
    return qt_bridge.na_interface(lambda: funcao(win))


def _canto(texto: str) -> str | None:
    from core.rosto_flutuante import CANTOS
    t = (texto or "").lower()
    for c in CANTOS:
        if all(p[:5] in t for p in c.split()):
            return c
    if "esquerd" in t:
        return "superior esquerdo" if ("cima" in t or "superior" in t) else "inferior esquerdo"
    if "direit" in t:
        return "superior direito" if ("cima" in t or "superior" in t) else "inferior direito"
    return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    from core.rosto_flutuante import TAMANHOS
    p = parameters or {}
    a = str(p.get("action") or "mostrar").strip().lower()
    try:
        if a in ("mostrar", "ligar", "abrir"):
            ok = _na_interface(player, lambda w: w.alternar_rosto_flutuante(True))
            return ("Estou no canto da tela. Arraste para mover, use a rodinha para mudar o "
                    "tamanho e o botão direito para as opções.") if ok else \
                "O rosto flutuante precisa da interface aberta."
        if a in ("esconder", "fechar", "desligar"):
            _na_interface(player, lambda w: w.alternar_rosto_flutuante(False))
            return "Rosto flutuante escondido."
        if a == "canto":
            canto = _canto(str(p.get("canto") or ""))
            if not canto:
                return "Qual canto? Inferior direito, inferior esquerdo, superior direito ou superior esquerdo."

            def mover(w):
                w.alternar_rosto_flutuante(True)
                w._rosto().ir_para_canto(canto)
            return f"Fui para o canto {canto}." if _na_interface(player, mover) else \
                "O rosto flutuante precisa da interface aberta."
        if a == "tamanho":
            t = str(p.get("tamanho") or "").lower()

            def redimensionar(w):
                w.alternar_rosto_flutuante(True)
                rf = w._rosto()
                if t in ("maior", "aumentar", "aumenta"):
                    rf.mudar_tamanho(rf._lado + 60)
                elif t in ("menor", "diminuir", "diminui"):
                    rf.mudar_tamanho(rf._lado - 60)
                else:
                    rf.mudar_tamanho(TAMANHOS.get(t.replace("medio", "médio"), 210))
            return "Pronto." if _na_interface(player, redimensionar) else \
                "O rosto flutuante precisa da interface aberta."
        return "Use mostrar, esconder, canto ou tamanho."
    except Exception as e:
        return f"O rosto flutuante falhou: {e}"
