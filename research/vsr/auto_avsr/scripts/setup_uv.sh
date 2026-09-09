#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
uv_bin="${UV_BIN:-uv}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/auto-avsr-uv-cache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$UV_CACHE_DIR/python}"
export UV_LINK_MODE=copy
if [[ ! -x "$model_dir/.venv/bin/python" ]]; then
    "$uv_bin" venv --python 3.10 "$model_dir/.venv"
fi
"$uv_bin" pip sync --python "$model_dir/.venv/bin/python" "$model_dir/requirements-uv.lock" \
    --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match
"$uv_bin" pip check --python "$model_dir/.venv/bin/python"
