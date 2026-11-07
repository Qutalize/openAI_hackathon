#!/bin/bash
# Builds the Uni-Sign inference environment with uv instead of conda.
# Same pinned versions as the README's conda steps; the environment goes to research/sign/uni-sign/.venv
# (override with UNI_SIGN_VENV) so the demo app can use a relative python_path.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
venv="${UNI_SIGN_VENV:-$here/.venv}"
uv_bin="${UV_BIN:-uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$HOME/.local/share/uv/python}"
cd "$here/Uni-Sign"

[ -x "$venv/bin/python" ] || "$uv_bin" venv --seed --python 3.9.25 "$venv"
[ "$venv" = "$here/.venv" ] || ln -sfn "$venv" "$here/.venv"
py="$venv/bin/python"

"$py" -m pip install torch==2.1.1+cu121 torchvision==0.16.1+cu121 torchaudio==2.1.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121
"$py" -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121
"$py" -m pip install -e ./demo/rtmlib-main coloredlogs==15.0.1 humanfriendly==10.0
"$py" -m pip install --no-deps onnxruntime-gpu==1.18.0 \
  --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/
"$py" -m pip install nvidia-curand-cu12==10.3.2.106 nvidia-cufft-cu12==11.0.2.54 \
  nvidia-cuda-runtime-cu12==12.1.105 huggingface-hub==0.36.2

"$py" -B - <<'PY'
import onnxruntime as ort
import rtmlib
import torch

print("torch:", torch.__version__, "CUDA available:", torch.cuda.is_available())
print("BF16 supported:", torch.cuda.is_available() and torch.cuda.is_bf16_supported())
print("ORT:", ort.__version__, ort.get_available_providers())
print("RTMLib source:", rtmlib.__file__)
PY
