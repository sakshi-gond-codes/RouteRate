#!/usr/bin/env bash
# Start RouteRate on macOS / Linux
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run ./setup.sh first."; exit 1; }
.venv/bin/python manage.py migrate --noinput >/dev/null
echo "RouteRate running at http://127.0.0.1:${PORT:-8000}/  (Ctrl+C to stop)"
exec .venv/bin/python manage.py runserver "127.0.0.1:${PORT:-8000}"
