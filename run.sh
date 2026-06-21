#!/usr/bin/env bash
# One-command start. Backend is optional — the dashboard runs standalone too.
set -e
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env

echo ""
echo "ReferralGuard backend → http://localhost:8000  (health: /health)"
echo "Dashboard → open dashboard/index.html in your browser"
echo ""
uvicorn server:app --port 8000
