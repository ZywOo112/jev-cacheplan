#!/usr/bin/env bash
set -euo pipefail
JEV_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${JEV_CLIENT_PYTHON:-python}" "$JEV_PROJECT_ROOT/scripts/service.py" stop
