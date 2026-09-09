#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/auto-avsr-matplotlib}"
export OMP_NUM_THREADS=8
export OPENBLAS_NUM_THREADS=8
exec "$model_dir/.venv/bin/python" "$model_dir/scripts/infer.py" "$@"
