#!/usr/bin/env bash
set -euo pipefail
JEV_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$JEV_PROJECT_ROOT"
if [[ -e .venv-cpu ]]; then
  printf 'Existing .venv-cpu preserved. Activate it and run pip install -r requirements.txt explicitly.\n' >&2
  exit 1
fi
"${JEV_SYSTEM_PYTHON:-python3}" -m venv .venv-cpu
.venv-cpu/bin/python -m pip install -r requirements.txt
