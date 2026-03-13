#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${SCRIPT_DIR}/probe_status_summary.py" \
  --healthcheck-path "${SCRIPT_DIR}/probe_healthcheck.py" \
  "$@"
