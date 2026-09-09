#!/usr/bin/env bash
set -euo pipefail
model_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env_dir="${USR2_VENV:-$HOME/.virtualenvs/usr2-vsr-gpu}"
if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 VIDEO [OUTPUT_DIR]" >&2
    exit 2
fi
video_path="$(realpath -- "$1")"
output_dir="${2:-$model_dir/outputs/$(date +%Y%m%d-%H%M%S)-vsr}"
model_size="${USR2_MODEL_SIZE:-huge}"
case "$model_size" in
    huge|baseplus) ;;
    *) echo "USR2_MODEL_SIZE must be huge or baseplus" >&2; exit 2 ;;
esac
checkpoint="$model_dir/weights/usr2_${model_size}_high_resource.pth"
[[ -f "$video_path" && -f "$checkpoint" && -x "$env_dir/bin/python" ]]
"$env_dir/bin/python" - "$video_path" <<'CHECK_VIDEO'
import av
import sys
with av.open(sys.argv[1]) as container:
    if container.streams.audio:
        raise SystemExit("VSR入力には音声トラックを除去した動画を指定してください。")
    if not container.streams.video:
        raise SystemExit("映像ストリームがありません。")
CHECK_VIDEO
mkdir -p -- "$output_dir"
output_dir="$(realpath -- "$output_dir")"
export OMP_NUM_THREADS="${USR2_NUM_THREADS:-8}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
beam_size="${USR2_BEAM_SIZE:-20}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/usr2-matplotlib-cache}"
export PYTHONUNBUFFERED=1
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
cd -- "$output_dir"
/usr/bin/time -v -o time.txt "$env_dir/bin/python" "$model_dir/scripts/run_gpu_demo.py" \
    "video=$video_path" "model.pretrained_model_path=$checkpoint" \
    "model/backbone=resnet_transformer_$model_size" modality=v detector=mediapipe \
    "decode.beam_size=$beam_size" decode.ctc_weight=0.1 \
    "hydra.run.dir=$output_dir" hydra.output_subdir=.hydra \
    2>&1 | tee console.log
