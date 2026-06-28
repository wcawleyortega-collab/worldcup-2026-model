#!/bin/bash
# Daily automation entrypoint (called by the LaunchAgent twice a day).
# 1. Re-forecast the tournament on the latest results + snapshot Polymarket.
# 2. Regenerate the shareable HTML/Markdown report.
# Each step is independent: a failed report still leaves fresh model outputs.
set -o pipefail
cd "$(dirname "$0")" || exit 1
PY=".venv/bin/python"

echo "=== run_daily $(date) ==="
"$PY" update_predictions.py
"$PY" daily_report.py
