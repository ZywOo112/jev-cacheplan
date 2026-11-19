#!/usr/bin/env bash
set -euo pipefail
JEV_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$JEV_PROJECT_ROOT"
if [[ -e .venv-gpu ]]; then
  printf 'Existing .venv-gpu preserved; no installation performed.\n' >&2
  exit 1
fi
"${JEV_SYSTEM_PYTHON:-python3}" -m venv .venv-gpu
.venv-gpu/bin/python -m pip install -r requirements/gpu.txt
