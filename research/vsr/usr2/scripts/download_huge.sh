#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env_dir="${USR2_VENV:-$HOME/.virtualenvs/usr2-vsr-gpu}"
checkpoint="$model_dir/weights/usr2_huge_high_resource.pth"
mkdir -p "$model_dir/weights"
if [[ ! -f "$checkpoint" ]]; then
    "$env_dir/bin/gdown" 1LzFOTYu45zCLOHGVLQt7pMGjw6jmmo9Y \
        -O "$checkpoint" --no-cookies --quiet
fi
cd "$model_dir"
awk '/  weights\/usr2_huge_high_resource.pth$/ {print}' artifacts.sha256 | sha256sum -c -
