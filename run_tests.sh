#!/usr/bin/env bash
# Run the automated tests (Linux / macOS). Windows: run_tests.bat
set -e
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
python -m pytest -v "$@"
