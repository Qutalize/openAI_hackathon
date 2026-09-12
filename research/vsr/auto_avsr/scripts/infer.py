"""上流tutorials/inference.ipynbの映像経路をCUDAで実行する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "auto_avsr"))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/auto-avsr-matplotlib")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path, help="音声トラックのない25 fps動画")
    parser.add_argument("output", type=Path)
    parser.add_argument("--weights", type=Path, default=ROOT / "weights/vsr_trlrs2lrs3vox2avsp_base.pth")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    import av
    import numpy as np
    import torch
    import torchvision
    from lightning import ModelModule
    from datamodule.transforms import VideoTransform
    from preparation.detectors.mediapipe.detector import LandmarksDetector
    from preparation.detectors.mediapipe.video_process import VideoProcess

    if not torch.cuda.is_available():
        raise RuntimeError("CUDAが利用できません。GPUアクセス可能な環境で実行してください。")
    torch.set_num_threads(8)
    torch.cuda.reset_peak_memory_stats()
    with av.open(str(args.video)) as container:
        if container.streams.audio:
            raise ValueError("VSR入力から音声トラックを除去してください。")
        fps = float(container.streams.video[0].average_rate)
        if abs(fps - 25) > 0.01:
            raise ValueError(f"25 fpsへ変換してください: {fps}")
        video = np.stack([frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)])
    detector = LandmarksDetector()
    landmarks = detector(video)
    detected = sum(item is not None for item in landmarks)
    mouth = VideoProcess(convert_gray=False)(video, landmarks)
    torchvision.io.write_video(str(args.output / "mouth_crop.mp4"), torch.from_numpy(mouth), round(fps))
    sample = VideoTransform(subset="test")(torch.from_numpy(mouth).permute(0, 3, 1, 2)).to("cuda")
    torch.cuda.synchronize()
    preprocessed = time.perf_counter()
    model = ModelModule(argparse.Namespace(modality="video"))
    model.model.load_state_dict(torch.load(args.weights, map_location="cpu", weights_only=True), strict=True)
    model = model.eval().to("cuda")
    assert next(model.parameters()).is_cuda and sample.is_cuda
    torch.cuda.synchronize()
    loaded = time.perf_counter()
    with torch.inference_mode():
        transcript = model(sample)
    torch.cuda.synchronize()
    ended = time.perf_counter()
    result = {
        "transcript": transcript,
        "input_language": "en", "output_language": "en", "modality": "video",
        "video": str(args.video.resolve()),
        "input_sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
        "weights": str(args.weights.resolve()),
        "frames": len(video), "fps": fps, "duration_seconds": len(video) / fps,
        "detected_frames": detected, "input_shape": list(sample.shape),
        "detector": "mediapipe (CPU)", "model_device": str(next(model.parameters()).device),
        "gpu": torch.cuda.get_device_name(), "torch": torch.__version__, "cuda": torch.version.cuda,
        "beam_size": 40, "ctc_weight": 0.1, "confidence": None,
        "import_and_preprocess_seconds": preprocessed - started,
        "model_load_seconds": loaded - preprocessed,
        "inference_seconds": ended - loaded,
        "total_seconds": ended - started,
        "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
        "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "transcript.txt").write_text(transcript + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
