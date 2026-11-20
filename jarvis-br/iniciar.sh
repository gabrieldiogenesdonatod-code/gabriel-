#!/usr/bin/env bash
# J.A.R.V.I.S BR - abre o assistente (macOS / Linux)
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    exec python3 main.py
elif command -v python >/dev/null 2>&1; then
    exec python main.py
else
    echo "Python não foi encontrado. Instale o Python 3.11 ou mais novo."
    exit 1
fi
