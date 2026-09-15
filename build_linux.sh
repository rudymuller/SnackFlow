#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python_bin=".venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
    python_bin="python3"
fi

"$python_bin" -m PyInstaller --noconfirm --clean --onedir --windowed \
    --name SnackFlow --paths src src/Main.py

mkdir -p dist/SnackFlow/data
if [[ -f data/SysDB.db ]]; then
    cp data/SysDB.db dist/SnackFlow/data/SysDB.db
fi

echo "Executavel criado em: dist/SnackFlow/SnackFlow"