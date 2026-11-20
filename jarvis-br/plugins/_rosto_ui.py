"""
Ajudante: escrever no balão do rosto flutuante a partir de um plugin
(fork PT-BR 1.4). Começa com "_": não é ferramenta.

Usado pelo "olha isso" (pergunta baixinho se quer explicar um erro) e pela
legenda ao vivo (tradução aparece no balão).
"""

from __future__ import annotations


def frase(player, quem: str, texto: str, mostrar_rosto: bool = False) -> bool:
    """Mostra "quem: texto" no balão. Com mostrar_rosto, liga o rosto antes."""
    try:
        from core import qt_bridge
    except Exception:
        return False
    win = getattr(player, "_win", None)
    if win is None or not qt_bridge.disponivel():
        return False

    def fazer():
        try:
            if mostrar_rosto and hasattr(win, "alternar_rosto_flutuante"):
                rf = win._rosto() if hasattr(win, "_rosto") else None
                if rf is None or not rf.isVisible():
                    win.alternar_rosto_flutuante(True)
            rf = win._rosto() if hasattr(win, "_rosto") else None
            if rf is not None and rf.isVisible():
                rf.mostrar_frase(f"{quem}: {texto}")
        except Exception as e:
            print(f"[RostoUI] {e}")

    return qt_bridge.na_interface(fazer)
