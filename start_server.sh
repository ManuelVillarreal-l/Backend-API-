#!/usr/bin/env bash
# Start the RutaSegura API on http://127.0.0.1:8000 (Linux / macOS). Windows: start_server.bat
set -e
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
python -m uvicorn app.main:app --reload
