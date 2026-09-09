#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env_dir="${USR2_VENV:-$HOME/.virtualenvs/usr2-vsr}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/usr2-uv-cache}"
export UV_LINK_MODE=copy
if [[ ! -x "$env_dir/bin/python" ]]; then
    uv venv --python 3.10 "$env_dir"
fi
uv pip sync --python "$env_dir/bin/python" "$model_dir/requirements-uv.lock" \
    --index pytorch=https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match
uv pip check --python "$env_dir/bin/python"
