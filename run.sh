#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

if [ ! -d .venv/.playwright ]; then
  python -m playwright install --with-deps chromium
fi

pytest -q
