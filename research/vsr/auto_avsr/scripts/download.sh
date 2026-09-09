#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$model_dir/weights" "$model_dir/outputs/setup"
weight="$model_dir/weights/vsr_trlrs2lrs3vox2avsp_base.pth"
if [[ ! -f "$weight" ]]; then
    "$model_dir/.venv/bin/gdown" 1r1kx7l9sWnDOCnaFHIGvOtzuhFyFA88_ -O "$weight.part" --no-cookies
    mv "$weight.part" "$weight"
fi
archive="$model_dir/outputs/setup/LRS3.zip"
if [[ ! -f "$archive" ]]; then
    curl -fL --retry 2 --max-time 120 \
        https://raw.githubusercontent.com/LipVoicer/LipVoicer.github.io/1b39eaf451ea7b076d9d73f5739ec9c8bb42f5a9/data/LRS3.zip \
        -o "$archive.part"
    mv "$archive.part" "$archive"
fi
cd "$model_dir"
sha256sum -c downloads.sha256
exec "$model_dir/.venv/bin/python" "$model_dir/scripts/prepare_sample.py"
