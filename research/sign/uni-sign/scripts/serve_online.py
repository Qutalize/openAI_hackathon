"""モデルを読み込んだまま待機し、標準入力の依頼ごとに手話動画を英文へ翻訳する。

推論の設定と手順はrun_online.pyが起動する上流のdemo.online_inferenceと同じ。
依頼は1行1件のJSON {"video": "動画のパス"}、応答も1行1件のJSON。
標準入力が閉じたら終了するので、起動元が止まれば一緒に止まる。
重みのSHA256検査と実行記録の保存は行わない（検証用の記録はrun_online.pyで取る）。
"""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_online import MODEL_DIR, inference_env


def main():
    if os.environ.get("UNI_SIGN_SERVER") != "1":
        # GPUライブラリの場所はプロセスの開始時に決まるので、環境を整えて自分を起動し直す。
        env = inference_env()
        env["UNI_SIGN_SERVER"] = "1"
        env["TOKENIZERS_PARALLELISM"] = "false"
        os.chdir(MODEL_DIR)
        os.execve(sys.executable, [sys.executable, "-B", "-u", str(Path(__file__).resolve())], env)

    # ライブラリが標準出力へ書いても応答の行が壊れないよう、応答専用の出力を分けておく。
    replies = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)

    def reply(message):
        replies.write(json.dumps(message, ensure_ascii=False) + "\n")
        replies.flush()

    started = time.perf_counter()
    sys.path.insert(0, str(MODEL_DIR))
    import argparse
    from concurrent.futures import ThreadPoolExecutor

    import cv2
    import numpy as np
    import torch
    from torch.utils.data import DataLoader

    import utils
    from datasets import S2T_Dataset_online
    from demo import online_inference as upstream
    from models import Uni_Sign
    from rtmlib import Wholebody

    args = argparse.ArgumentParser(parents=[utils.get_args_parser()]).parse_args([
        "--finetune", "./weights/how2sign_pose_only_slt.pth",
        "--dataset", "How2Sign", "--task", "SLT",
        "--max_length", "256", "--seed", "42",
    ])
    utils.set_seed(args.seed)
    # 以下は上流のmain()と同じ順序でモデルを用意する。
    model = Uni_Sign(args=args)
    model.cuda()
    model.train()
    for _, param in model.named_parameters():
        if param.requires_grad:
            param.data = param.data.to(torch.float32)
    state = torch.load(args.finetune, map_location="cpu")["model"]
    model.load_state_dict(state, strict=True)
    model.eval()
    model.to(torch.bfloat16)
    wholebody = Wholebody(to_openpose=False, mode="lightweight", backend="onnxruntime", device="cuda")
    reply({"ready": True, "load_seconds": time.perf_counter() - started})

    def extract_pose(video):
        """上流のpose_extraction()と同じ計算を、読み込み済みの姿勢モデルで行う。"""
        capture = cv2.VideoCapture(video)
        if not capture.isOpened():
            raise ValueError("動画を開けません")
        frames = []
        while True:
            decoded, frame = capture.read()
            if not decoded:
                break
            frames.append(frame)
        capture.release()
        if not frames:
            raise ValueError("動画のフレームをデコードできません")
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(lambda frame: upstream.process_frame(frame, wholebody), frames))
        data = {"keypoints": [], "scores": []}
        for keypoints, scores, size in results:
            data["keypoints"].append(keypoints / np.array(size)[None, None])
            data["scores"].append(scores)
        return data, len(frames)

    for line in sys.stdin:
        if not line.strip():
            continue
        began = time.perf_counter()
        try:
            video = json.loads(line)["video"]
            utils.set_seed(args.seed)
            pose, frames = extract_pose(video)
            posed = time.perf_counter()
            data = S2T_Dataset_online(args=args)
            data.rgb_data = video
            data.pose_data = pose
            loader = DataLoader(
                data, batch_size=1, collate_fn=data.collate_fn,
                sampler=torch.utils.data.SequentialSampler(data),
            )
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                upstream.inference(loader, model)
            marker = "Prediction result is: "
            predictions = [
                text.removeprefix(marker) for text in printed.getvalue().splitlines() if text.startswith(marker)
            ]
            if len(predictions) != 1:
                raise RuntimeError("翻訳結果を取得できません")
            reply({
                "prediction": predictions[0], "frames": frames,
                "pose_seconds": posed - began, "seconds": time.perf_counter() - began,
            })
        except Exception as exc:
            reply({"error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
