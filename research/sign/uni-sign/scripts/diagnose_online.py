"""既存のHow2Sign重みで姿勢・実行精度・時間系列への反応を診断する。"""

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision

from run_online import MODEL_DIR, CHECKPOINT, EXPECTED_CHECKPOINT_SHA256, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cached-poses", type=Path, help="既存診断の並列/逐次poseを固定して生成だけ比較")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.videos = [p.resolve() for p in args.videos]
    if args.cached_poses:
        args.cached_poses = args.cached_poses.resolve()
    out = args.output_dir.resolve()
    if MODEL_DIR / "outputs" not in out.parents:
        parser.error("保存先はUni-Sign/outputsの新規ディレクトリに限定します")
    if not args.worker:
        if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
            parser.error("checkpoint SHA256が一致しません")
        out.mkdir(parents=True, exist_ok=False)
        env = os.environ.copy()
        torch_dir = Path(importlib.util.find_spec("torch").origin).parent
        libs = [torch_dir / "lib"] + sorted((torch_dir.parent / "nvidia").glob("*/lib"))
        env.update(UNI_SIGN_INFERENCE_ONLY="1", PYTHONDONTWRITEBYTECODE="1",
                   TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1",
                   TRANSFORMERS_OFFLINE="1", TORCH_HOME=str(MODEL_DIR / "weights/torch-cache"))
        env["LD_LIBRARY_PATH"] = os.pathsep.join([str(p) for p in libs if p.is_dir()] +
                                                ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else []))
        command = [sys.executable, "-B", str(Path(__file__).resolve()), *map(str, args.videos),
                   "--output-dir", str(out), "--worker"]
        if args.cached_poses:
            command += ["--cached-poses", str(args.cached_poses)]
        (out / "command.txt").write_text(shlex.join(command) + "\n")
        (out / "environment.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
        metadata = {"inputs": {str(p): sha256(p) for p in args.videos},
                    "checkpoint_sha256": sha256(CHECKPOINT), "command": command,
                    "environment": {k: env[k] for k in ("LD_LIBRARY_PATH", "TORCH_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")},
                    "revision": upstream_revision(MODEL_DIR)}
        metadata["cached_pose_hashes"] = ({str(p): sha256(p) for p in args.cached_poses.glob("*/pose_*.npz")}
                                          if args.cached_poses else {})
        (out / "manifest.json").write_text(json.dumps(metadata, indent=2))
        with (out / "diagnostic.log").open("w") as log:
            result = subprocess.run(command, cwd=MODEL_DIR, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f"exit_code={result.returncode}; outputs={out}")
        return result.returncode
    worker(args, out)
    return 0


def worker(cli, out):
    import cv2
    import numpy as np
    import torch
    sys.path.insert(0, str(MODEL_DIR))
    import utils
    from datasets import S2T_Dataset_online
    from demo.online_inference import pose_extraction
    from models import Uni_Sign
    from rtmlib import Wholebody, draw_skeleton

    args = utils.get_args_parser().parse_args(["--dataset", "How2Sign", "--task", "SLT", "--max_length", "256", "--seed", "42"])
    utils.set_seed(42)
    sources, results = {}, {"pose": {}, "generation": []}
    parts = {"body": [0] + list(range(3, 11)), "left": list(range(91, 112)),
             "right": list(range(112, 133)), "face_all": list(range(23, 40, 2)) + list(range(83, 91)) + [53]}
    # 上流そのものの16-thread抽出を保存し、逐次抽出と比較する。
    for video in cli.videos:
        key = video.parent.name
        if cli.cached_poses:
            for mode in ("thread16", "sequential"):
                with np.load(cli.cached_poses / key / f"pose_{mode}.npz") as cached:
                    dataset = S2T_Dataset_online(args)
                    dataset.pose_data = {k: list(cached[k]) for k in ("keypoints", "scores")}
                    dataset.rgb_data = str(video)
                    sources[f"{key}/{mode}"] = dataset.collate_fn([dataset[0]])
            continue
        folder = out / key
        folder.mkdir(exist_ok=False)
        pose = pose_extraction(str(video))
        np.savez_compressed(folder / "pose_thread16.npz", keypoints=np.stack(pose["keypoints"]), scores=np.stack(pose["scores"]))
        sequential = Wholebody(to_openpose=False, mode="lightweight", backend="onnxruntime", device="cuda")
        cap = cv2.VideoCapture(str(video))
        coords, scores, boxes, panels = [], [], [], []
        selected = set(np.linspace(0, len(pose["scores"]) - 1, 12, dtype=int).tolist())
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            bbox = sequential.det_model(frame)
            kp, sc = sequential.pose_model(frame, bboxes=bbox)
            boxes.append(len(bbox))
            coords.append(kp / np.array([w, h])[None, None])
            scores.append(sc)
            if index in selected:
                # 上流並列抽出の骨格を元フレームに描く。顔/骨格はローカルのみ。
                overlay = draw_skeleton(frame.copy(), pose["keypoints"][index] * np.array([w, h])[None, None],
                                        pose["scores"][index], openpose_skeleton=False, kpt_thr=0.3)
                cv2.putText(overlay, f"frame {index}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                panels.append(cv2.resize(overlay, (640, 360)))
            index += 1
        cap.release()
        cv2.imwrite(str(folder / "skeleton_contact_sheet.jpg"), np.concatenate([np.concatenate(panels[i:i+3], axis=1) for i in range(0, 12, 3)], axis=0))
        seq = {"keypoints": coords, "scores": scores}
        np.savez_compressed(folder / "pose_sequential.npz", keypoints=np.stack(coords), scores=np.stack(scores))
        kp, sc = np.stack(pose["keypoints"]), np.stack(pose["scores"])
        stats = {"frames": len(kp), "pose_people_counts": [len(p) for p in pose["keypoints"]],
                 "sequential_detector_box_counts": boxes,
                 "coordinates_finite": bool(np.isfinite(kp).all()), "scores_finite": bool(np.isfinite(sc).all()),
                 "thread_vs_sequential_max_coordinate_delta": float(np.abs(kp - np.stack(coords)).max()),
                 "thread_vs_sequential_max_score_delta": float(np.abs(sc - np.stack(scores)).max()), "parts": {}}
        for part, indices in parts.items():
            values = sc[:, 0, indices]
            stats["parts"][part] = {"score_mean": float(values.mean()), "score_quantiles": np.quantile(values, [0, .1, .5, .9, 1]).tolist(),
                                    "masked_fraction_le_0_3": float((values <= .3).mean()),
                                    "per_frame_masked_fraction": (values <= .3).mean(axis=1).tolist()}
        dataset = S2T_Dataset_online(args)
        dataset.pose_data, dataset.rgb_data = pose, str(video)
        source, target = dataset.collate_fn([dataset[0]])
        stats["normalized_parts"] = {part: {"shape": list(source[part].shape), "finite": bool(torch.isfinite(source[part]).all()),
                                                   "all_zero_fraction": float((source[part] == 0).all(dim=-1).float().mean())} for part in parts}
        sources[key] = (source, target)
        results["pose"][key] = stats
        del sequential
        (out / "results.json").write_text(json.dumps(results, indent=2))

    model = Uni_Sign(args)
    state = torch.load(CHECKPOINT, map_location="cpu")["model"]
    keys = model.load_state_dict(state, strict=True)
    results["checkpoint_keys"] = {"missing": keys.missing_keys, "unexpected": keys.unexpected_keys}
    model.cuda().eval()
    # 各精度の前に配布重みから再読込。checkpoint保存時の丸めは復元しない。
    for dtype in (torch.bfloat16, torch.float32):
        model.to(dtype)
        model.load_state_dict(state, strict=True)
        for key, (original, target) in sources.items():
            variants = ["baseline", "repeat", "reverse", "static_middle", "zero"] if dtype == torch.bfloat16 else ["baseline"]
            if cli.cached_poses:
                variants = ["baseline", "repeat"]
            for variant in variants:
                source = copy.deepcopy(original)
                for part in parts:
                    if variant == "reverse":
                        source[part] = source[part].flip(1)
                    elif variant == "static_middle":
                        source[part] = source[part][:, source[part].shape[1] // 2:source[part].shape[1] // 2 + 1].expand_as(source[part]).clone()
                    elif variant == "zero":
                        source[part] = torch.zeros_like(source[part])
                source = {k: v.to(dtype).cuda() if isinstance(v, torch.Tensor) else v for k, v in source.items()}
                with torch.no_grad():
                    computed = model(source, target)
                    tokens = model.generate(computed, max_new_tokens=100, num_beams=4)
                row = {"input": key, "dtype": str(dtype), "variant": variant,
                       "tokens": tokens.cpu().tolist(), "prediction": model.mt5_tokenizer.batch_decode(tokens, skip_special_tokens=True)[0],
                       "embedding_finite": bool(torch.isfinite(computed["inputs_embeds"]).all())}
                results["generation"].append(row)
                print(json.dumps(row), flush=True)
                (out / "results.json").write_text(json.dumps(results, indent=2))
    results["notes"] = ["scores are pose detection scores, not translation confidence", "static/zero/reverse are synthetic negative controls, not valid ASL", "FP32 changes arithmetic only; distributed checkpoint is already BF16"]
    (out / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    sys.exit(main())
