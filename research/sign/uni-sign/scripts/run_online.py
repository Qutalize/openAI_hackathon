"""上流のHow2Sign pose-only推論を実行し、未補正の英文とログを保存する。"""

import argparse
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision, upstream_patch_at_import
import tempfile
import time


MODEL_DIR = Path(__file__).resolve().parents[1] / "Uni-Sign"
CHECKPOINT = MODEL_DIR / "weights/how2sign_pose_only_slt.pth"
EXPECTED_CHECKPOINT_SHA256 = (
    "1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d"
)
MT5_REVISION = "2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    video = args.video.resolve()
    if not video.is_file():
        parser.error("入力動画が存在しません")
    required = [CHECKPOINT] + [
        MODEL_DIR / "weights/mt5-base" / name
        for name in (
            "config.json", "pytorch_model.bin", "spiece.model",
            "tokenizer_config.json", "special_tokens_map.json",
        )
    ]
    for path in required:
        if not path.is_file():
            parser.error(f"必要なファイルがありません: {path}")
    checkpoint_sha256 = sha256(CHECKPOINT)
    if checkpoint_sha256 != EXPECTED_CHECKPOINT_SHA256:
        parser.error("How2Signの重みのSHA256が公式配布ファイルと一致しません")

    # ターゲット原稿・正解文は読み込まず、映像だけを上流に渡す。
    import cv2

    cap = cv2.VideoCapture(str(video))
    opened = cap.isOpened()
    decoded, _ = cap.read()
    video_metadata = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    if not opened or not decoded:
        parser.error("動画の最初のフレームをデコードできません")

    if args.output_dir:
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
    else:
        outputs = MODEL_DIR / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path(tempfile.mkdtemp(prefix=f"how2sign-{stamp}-", dir=outputs))

    env = os.environ.copy()
    env["TORCH_HOME"] = str(MODEL_DIR / "weights/torch-cache")
    env["HF_HOME"] = str(MODEL_DIR / "weights/hf-cache")
    env["TRITON_CACHE_DIR"] = str(MODEL_DIR / "outputs/triton-cache")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["UNI_SIGN_INFERENCE_ONLY"] = "1"
    torch_package = Path(importlib.util.find_spec("torch").origin).parent
    library_dirs = [torch_package / "lib"] + sorted(
        (torch_package.parent / "nvidia").glob("*/lib")
    )
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        [str(path) for path in library_dirs if path.is_dir()]
        + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
    )
    command = [
        sys.executable, "-B", "-u", "-m", "demo.online_inference",
        "--online_video", str(video),
        "--finetune", "./weights/how2sign_pose_only_slt.pth",
        "--dataset", "How2Sign", "--task", "SLT",
        "--max_length", "256", "--seed", "42",
    ]
    metadata = {
        "status": "running",
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "working_directory": str(MODEL_DIR),
        "command": command,
        "upstream_revision": upstream_revision(MODEL_DIR),
        "upstream_local_patch_at_import": upstream_patch_at_import(MODEL_DIR),
        "mt5_revision": MT5_REVISION,
        "input_video": str(video),
        "input_sha256": sha256(video),
        "input_sign_language": "unconfirmed; checkpoint is trained for ASL",
        "output_language": "English",
        "video": video_metadata,
        "training": False,
        "postprocessing": "only removes stdout marker; no sentence correction",
        "translation_confidence": None,
        "preprocessing": {
            "pose_model": "RTMLib Wholebody lightweight; COCO wholebody 133 keypoints",
            "backend": "onnxruntime; requests CUDAExecutionProvider",
            "normalization": "x/width, y/height; upstream per-part normalization",
            "max_length": 256,
            "seed": 42,
            "frame_subsampling": video_metadata["frame_count"] > 256,
            "rgb_support": False,
            "dtype": "bfloat16",
            "num_beams": 4,
            "max_new_tokens": 100,
        },
        "cache_environment": {key: env[key] for key in (
            "TORCH_HOME", "HF_HOME", "TRITON_CACHE_DIR", "PYTHONDONTWRITEBYTECODE",
            "UNI_SIGN_INFERENCE_ONLY", "LD_LIBRARY_PATH"
        )},
        "python": sys.version,
        "packages": {
            dist.metadata["Name"]: dist.version
            for dist in importlib.metadata.distributions()
            if dist.metadata["Name"]
        },
        "artifacts_sha256": {"weights/how2sign_pose_only_slt.pth": checkpoint_sha256},
    }
    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    (output_dir / "command.txt").write_text(shlex.join(command) + "\n")
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (output_dir / "environment.txt").write_text(freeze)

    print(f"保存先: {output_dir}", flush=True)
    predictions = []
    ort_providers = []
    start = time.perf_counter()
    with (output_dir / "inference.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen(
            command, cwd=MODEL_DIR, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        ) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
                if line.startswith("Prediction result is: "):
                    predictions.append(line.removeprefix("Prediction result is: ").rstrip("\r\n"))
                if line.startswith("ONNX Runtime providers: "):
                    ort_providers.append(json.loads(line.removeprefix("ONNX Runtime providers: ")))
            exit_code = process.wait()
    metadata["elapsed_seconds"] = time.perf_counter() - start
    metadata["timing_scope"] = "upstream subprocess startup through exit, including pose extraction and model loading"
    metadata["exit_code"] = exit_code
    metadata["ort_session_providers"] = ort_providers
    metadata["status"] = "success" if exit_code == 0 and len(predictions) == 1 and predictions[0].strip() else "failed"
    metadata["prediction"] = predictions[0] if len(predictions) == 1 else None
    if metadata["status"] == "success":
        (output_dir / "prediction.txt").write_text(predictions[0] + "\n", encoding="utf-8")
    for artifact in sorted((MODEL_DIR / "weights/mt5-base").glob("*")):
        if artifact.is_file():
            metadata["artifacts_sha256"][str(artifact.relative_to(MODEL_DIR))] = sha256(artifact)
    for artifact in sorted((MODEL_DIR / "weights/torch-cache/hub/checkpoints").glob("*.onnx")):
        metadata["artifacts_sha256"][str(artifact.relative_to(MODEL_DIR))] = sha256(artifact)
    result_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"実行状態: {metadata['status']}; 保存先: {output_dir}")
    return 0 if metadata["status"] == "success" else (exit_code or 1)


if __name__ == "__main__":
    sys.exit(main())
