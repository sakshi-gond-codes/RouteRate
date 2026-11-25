#!/usr/bin/env bash
# RouteRate setup for macOS / Linux (same steps as setup.bat)
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for cmd in python3.13 python3.12 python3 python; do
  if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    PY="$cmd"; break
  fi
done
[ -z "$PY" ] && { echo "[ERROR] Python 3.12+ not found."; exit 1; }
echo "[1/6] Using $($PY --version)"

[ -x .venv/bin/python ] || { echo "[2/6] Creating .venv"; "$PY" -m venv .venv; }
echo "[3/6] Installing packages"
.venv/bin/python -m pip install --upgrade pip --quiet --disable-pip-version-check
.venv/bin/python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo "[4/6] MySQL database"
.venv/bin/python scripts/configure.py "$@"
echo "[5/6] Migrations"
.venv/bin/python manage.py migrate --noinput
echo "[6/6] Demo data"
.venv/bin/python manage.py seed_demo --if-empty
echo
echo "Setup complete. Run ./start.sh and log in as admin / RouteRate@123"
