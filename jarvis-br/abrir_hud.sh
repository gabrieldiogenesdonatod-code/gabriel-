#!/usr/bin/env bash
# J.A.R.V.I.S BR - abre só o HUD 3.9 (macOS / Linux). Ctrl+C fecha.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 -m hud39 "$@"
elif command -v python >/dev/null 2>&1; then
    exec python -m hud39 "$@"
else
    echo "Python não foi encontrado. Instale o Python 3.11 ou mais novo."
    exit 1
fi
