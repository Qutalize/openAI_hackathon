"""モデルを読み込んだまま待機し、標準入力の依頼ごとに読唇する。

処理はinfer.pyの映像経路と同じ（口元の切り出し動画の保存だけ省く）。
依頼は1行1件のJSON {"video": "25 fpsで音声なしの動画"}、応答も1行1件のJSON。
標準入力が閉じたら終了するので、起動元が止まれば一緒に止まる。
"""
import argparse
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
    parser.add_argument("--weights", type=Path, default=ROOT / "weights/vsr_trlrs2lrs3vox2avsp_base.pth")
    args = parser.parse_args()
    # ライブラリが標準出力へ書いても応答の行が壊れないよう、応答専用の出力を分けておく。
    replies = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)

    def reply(message):
        replies.write(json.dumps(message, ensure_ascii=False) + "\n")
        replies.flush()

    started = time.perf_counter()
    import av
    import numpy as np
    import torch
    from lightning import ModelModule
    from datamodule.transforms import VideoTransform
    from preparation.detectors.mediapipe.detector import LandmarksDetector
    from preparation.detectors.mediapipe.video_process import VideoProcess

    if not torch.cuda.is_available():
        raise RuntimeError("CUDAが利用できません。GPUアクセス可能な環境で実行してください。")
    torch.set_num_threads(8)
    model = ModelModule(argparse.Namespace(modality="video"))
    model.model.load_state_dict(torch.load(args.weights, map_location="cpu", weights_only=True), strict=True)
    model = model.eval().to("cuda")
    detector = LandmarksDetector()
    crop = VideoProcess(convert_gray=False)
    transform = VideoTransform(subset="test")
    torch.cuda.synchronize()
    reply({"ready": True, "load_seconds": time.perf_counter() - started})

    for line in sys.stdin:
        if not line.strip():
            continue
        began = time.perf_counter()
        try:
            with av.open(json.loads(line)["video"]) as container:
                if container.streams.audio:
                    raise ValueError("VSR入力から音声トラックを除去してください。")
                fps = float(container.streams.video[0].average_rate)
                if abs(fps - 25) > 0.01:
                    raise ValueError(f"25 fpsへ変換してください: {fps}")
                video = np.stack([frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)])
            mouth = crop(video, detector(video))
            sample = transform(torch.from_numpy(mouth).permute(0, 3, 1, 2)).to("cuda")
            with torch.inference_mode():
                transcript = model(sample)
            torch.cuda.synchronize()
            reply({"transcript": transcript, "frames": len(video), "seconds": time.perf_counter() - began})
        except Exception as exc:
            reply({"error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
