#!/usr/bin/env bash
set -euo pipefail
ILL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ILL_WORKSPACE="${ILLUSTRIOUS_WORKSPACE:-/workspace}"
mkdir -p "$ILL_WORKSPACE/illustrious-runtime"
exec 9>"$ILL_WORKSPACE/illustrious-runtime/studio.lock"
flock -n 9 || { echo "Illustrious Studio is already running."; exit 1; }
if [[ -n "${ILLUSTRIOUS_PYTHON:-}" ]]; then
  ILL_PYTHON="$ILLUSTRIOUS_PYTHON"
elif [[ -x /opt/venvs/core/bin/python ]]; then
  ILL_PYTHON=/opt/venvs/core/bin/python
else
  ILL_PYTHON=python3
fi
export PYTHONPATH="$ILL_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$ILL_PYTHON" "$ILL_ROOT/scripts/bootstrap.py" "$@"
