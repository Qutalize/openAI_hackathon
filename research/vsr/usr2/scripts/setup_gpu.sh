#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env_dir="${USR2_VENV:-$HOME/.virtualenvs/usr2-vsr-gpu}"
uv_bin="${UV_BIN:-uv}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/usr2-uv-cache}"
export UV_LINK_MODE=copy
if [[ ! -x "$env_dir/bin/python" ]]; then
    "$uv_bin" venv --python 3.10 "$env_dir"
fi
"$uv_bin" pip sync --python "$env_dir/bin/python" "$model_dir/requirements-gpu.lock" \
    --index pytorch=https://download.pytorch.org/whl/cu124 \
    --index-strategy unsafe-best-match
"$uv_bin" pip check --python "$env_dir/bin/python"
"$env_dir/bin/python" -c 'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.__version__, torch.cuda.get_device_name(0))'
