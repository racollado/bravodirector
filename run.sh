#!/usr/bin/env bash
# Rebuild the Vite frontend, then start the Bravo Director server.
# Usage: ./run.sh [--script path.json] [--port N] [--debug]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT}/venv/bin/activate"
fi

echo "==> Building web (npm run build)…"
(cd "${ROOT}/web" && npm run build)

echo "==> Starting main.py…"
if command -v python >/dev/null 2>&1; then
  exec python "${ROOT}/main.py" "$@"
fi
exec python3 "${ROOT}/main.py" "$@"
