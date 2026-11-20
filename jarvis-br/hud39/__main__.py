"""python -m hud39 [--sem-janela] [--sem-tela-cheia] — o HUD 3.9 sem o JARVIS (só o painel e as ações locais)."""
from __future__ import annotations

import sys
import time

from .servidor import abrir

if __name__ == "__main__":
    url = abrir(tela_cheia="--sem-tela-cheia" not in sys.argv, janela="--sem-janela" not in sys.argv)
    print(f"HUD 3.9 em {url}  (Ctrl+C para sair)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
