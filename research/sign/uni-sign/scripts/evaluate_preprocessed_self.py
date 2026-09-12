"""自前ASLの前処理条件を、同一のHow2Signモデルで直列推論・採点する。"""

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import pickle
import random
import re
import shlex
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision, upstream_patch_at_import
import time
import traceback

from run_online import CHECKPOINT, EXPECTED_CHECKPOINT_SHA256, MODEL_DIR, MT5_REVISION, sha256

PROJECT_DIR = Path(__file__).resolve().parents[4]
PARTS = ("body", "left", "right", "face_all")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError("入力準備が完了したmanifestが必要です")
    samples = manifest.get("samples", [])
    if not samples or len({s["id"] for s in samples}) != len(samples):
        raise ValueError("manifestのsampleが空、またはidが重複しています")
    variants = list(samples[0]["variants"])
    if "original" not in variants:
        raise ValueError("original条件が必要です")
    if any(not name.replace("_", "").isalnum() for name in variants):
        raise ValueError("variant名には英数字とunderscoreを使ってください")
    sign_dir = (PROJECT_DIR / "data/sign").resolve()
    for sample in samples:
        sample_id = sample["id"]
        if not isinstance(sample_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", sample_id) is None:
            raise ValueError("sample idには英数字・underscore・hyphenのみを使ってください")
        sample_dir = (sign_dir / sample_id).resolve()
        if not sample_dir.is_dir() or sample_dir.parent != sign_dir:
            raise ValueError(f"data/sign直下の既存sampleディレクトリが必要です: {sample_id}")
        if list(sample["variants"]) != variants:
            raise ValueError(f"全sampleで同じ条件と順序が必要です: {sample['id']}")
        for variant, path_string in sample["variants"].items():
            video = Path(path_string)
            if not video.is_absolute() or not video.is_file():
                raise ValueError(f"動画は存在する絶対パスで指定してください: {video}")
            if sha256(video) != sample["variant_sha256"][variant]:
                raise ValueError(f"manifestの動画SHA256と一致しません: {video}")
        label = (sample_dir / "script.txt").resolve()
        if not label.is_file() or label.parent != sample_dir:
            raise ValueError(f"採点用ラベルがありません: {label}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    cli = parser.parse_args()
    cli.manifest = cli.manifest.resolve()
    out = cli.output_dir.resolve()
    if (MODEL_DIR / "outputs").resolve() not in out.parents:
        parser.error("保存先はUni-Sign/outputs以下の新規ディレクトリに限定します")
    if cli.worker:
        return worker(cli, out)
    manifest = validate_manifest(cli.manifest)
    variants = list(manifest["samples"][0]["variants"])
    digest = sha256(CHECKPOINT)
    if digest != EXPECTED_CHECKPOINT_SHA256:
        parser.error("checkpoint SHA256が公式配布値と一致しません")
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    torch_package = Path(importlib.util.find_spec("torch").origin).parent
    libraries = [torch_package / "lib"] + sorted((torch_package.parent / "nvidia").glob("*/lib"))
    env.update(UNI_SIGN_INFERENCE_ONLY="1", PYTHONDONTWRITEBYTECODE="1",
               TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TORCH_HOME=str(MODEL_DIR / "weights/torch-cache"),
               HF_HOME=str(MODEL_DIR / "weights/hf-cache"), TRITON_CACHE_DIR=str(out / "triton-cache"))
    env["LD_LIBRARY_PATH"] = os.pathsep.join([str(p) for p in libraries if p.is_dir()] +
                                             ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else []))
    command = [sys.executable, "-B", "-u", str(Path(__file__).resolve()),
               "--manifest", str(cli.manifest), "--output-dir", str(out), "--worker"]
    metadata = {
        "status": "running", "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "input_manifest": str(cli.manifest), "input_manifest_sha256": sha256(cli.manifest),
        "source_manifest": manifest, "checkpoint_sha256": digest, "mt5_revision": MT5_REVISION,
        "working_directory": str(MODEL_DIR), "command": command,
        "upstream_revision": upstream_revision(MODEL_DIR),
        "upstream_local_patch_at_import": upstream_patch_at_import(MODEL_DIR),
        "script_sha256": sha256(Path(__file__)), "python": sys.version,
        "environment": {k: env[k] for k in ("LD_LIBRARY_PATH", "TORCH_HOME", "HF_HOME", "HF_HUB_OFFLINE",
                                             "TRANSFORMERS_OFFLINE", "UNI_SIGN_INFERENCE_ONLY", "TRITON_CACHE_DIR")},
        "settings": {"dataset": "How2Sign", "task": "SLT", "rgb_support": False, "dtype": "bfloat16",
                     "batch_size": 1, "max_length": 256, "seed": 42, "reset_seed_per_sample_and_variant": True,
                     "max_new_tokens": 100, "num_beams": 4, "training": False,
                     "generation_target": "empty string; labels read only after all generation for scoring",
                     "postprocessing": "tokenizer.batch_decode(skip_special_tokens=True) only",
                     "variants": variants},
    }
    write_json(out / "manifest.json", metadata)
    (out / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
    (out / "environment.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    print(f"保存先: {out}", flush=True)
    started = time.perf_counter()
    providers = []
    with (out / "inference.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen(command, cwd=MODEL_DIR, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
                if line.startswith("ONNX Runtime providers: "):
                    providers.append(json.loads(line.removeprefix("ONNX Runtime providers: ")))
            exit_code = process.wait()
    metadata.update(status="success" if exit_code == 0 else "failed", exit_code=exit_code,
                    elapsed_seconds=time.perf_counter() - started, ort_session_providers=providers,
                    timing_scope="worker startup, model loading, pose extraction, generation and scoring")
    metadata["artifacts_sha256"] = {
        str(p.relative_to(MODEL_DIR)): sha256(p)
        for p in list((MODEL_DIR / "weights/mt5-base").glob("*")) +
        list((MODEL_DIR / "weights/torch-cache/hub/checkpoints").glob("*.onnx")) if p.is_file()
    }
    write_json(out / "manifest.json", metadata)
    return exit_code


def worker(cli, out):
    import cv2
    import torch
    sys.path.insert(0, str(MODEL_DIR))
    import utils
    from datasets import S2T_Dataset_online
    from demo.online_inference import pose_extraction
    from models import Uni_Sign
    from score_saved_results import score

    if not torch.cuda.is_available():
        raise RuntimeError("CUDAが利用できません。CPUへ自動切替しません")
    manifest = validate_manifest(cli.manifest)
    variants = list(manifest["samples"][0]["variants"])
    args = utils.get_args_parser().parse_args(["--dataset", "How2Sign", "--task", "SLT",
                                               "--max_length", "256", "--seed", "42"])
    utils.set_seed(42)
    results = {"rows": [], "scores": {}, "gpu": torch.cuda.get_device_name(0),
               "variants": variants, "translation_confidence": None,
               "notes": ["全入力を同じコード・seed・実行環境で測定。originalのみの評価にも対応。",
                         "正解ラベルは全推論の完了後、採点にのみ読み込む。",
                         "上流pose_extractionは内部で16thread。GPU推論条件は外側で直列実行。",
                         f"検出confidence・mask率は翻訳信頼度ではない。{len(manifest['samples'])}本の診断値。"]}
    started = time.perf_counter()
    model = Uni_Sign(args)
    state = torch.load(CHECKPOINT, map_location="cpu")["model"]
    loaded = model.load_state_dict(state, strict=True)
    del state
    model.cuda().eval().to(torch.bfloat16)
    torch.cuda.synchronize()
    results["model_loading_seconds"] = time.perf_counter() - started
    results["checkpoint_keys"] = {"missing": loaded.missing_keys, "unexpected": loaded.unexpected_keys}
    for sample in manifest["samples"]:
        for variant in variants:
            video = Path(sample["variants"][variant])
            folder = out / sample["id"] / variant
            folder.mkdir(parents=True, exist_ok=False)
            row = {"id": sample["id"], "variant": variant, "status": "running",
                   "input_path": str(video), "input_sha256": sha256(video),
                   "translation_confidence": None, "output_directory": str(folder)}
            try:
                utils.set_seed(42)
                started = time.perf_counter()
                cap = cv2.VideoCapture(str(video))
                if not cap.isOpened():
                    raise ValueError(f"動画を開けません: {video}")
                row["video_metadata"] = {"width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                                         "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                         "fps": cap.get(cv2.CAP_PROP_FPS),
                                         "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
                cap.release()
                pose = pose_extraction(str(video))
                torch.cuda.synchronize()
                row["pose_extraction_seconds"] = time.perf_counter() - started
                if not pose or not pose["scores"]:
                    raise ValueError("姿勢抽出結果が空です")
                pose_path = folder / "online_pose.pkl"
                with pose_path.open("wb") as stream:
                    pickle.dump(pose, stream, protocol=4)
                row.update(pose_path=str(pose_path), pose_cache_sha256=sha256(pose_path))
                row["pose_people_counts"] = sorted(set(len(frame) for frame in pose["keypoints"]))
                online = S2T_Dataset_online(args)
                online.pose_data, online.rgb_data = pose, str(video)
                utils.set_seed(42)
                frames = len(pose["scores"])
                rng = random.Random()
                rng.setstate(random.getstate())
                # 上流online.load_poseの直前状態を複製し、乱数状態を進めず同じindexを記録する。
                selected = (sorted(rng.sample(range(frames), k=online.max_length))
                            if frames > online.max_length else list(range(frames)))
                row["frames"] = {"stored_frames": frames, "used_frames": len(selected),
                                 "selected_absolute_indices": selected}
                source, _ = online.collate_fn([online[0]])
                row["normalized_pose"] = {
                    part: {"shape": list(source[part].shape), "finite": bool(torch.isfinite(source[part]).all()),
                           "all_zero_fraction": float((source[part] == 0).all(dim=-1).float().mean()),
                           "masked_joint_count": int((source[part] == 0).all(dim=-1).sum()),
                           "joint_count": source[part][..., 2].numel()}
                    for part in PARTS
                }
                if not all(value["finite"] for value in row["normalized_pose"].values()):
                    raise ValueError("正規化姿勢に非有限値があります")
                row["preprocessing_seconds"] = time.perf_counter() - started
                source = {key: value.to(torch.bfloat16).cuda() if isinstance(value, torch.Tensor) else value
                          for key, value in source.items()}
                target = {"gt_sentence": [""], "gt_gloss": [""]}
                utils.set_seed(42)
                torch.cuda.synchronize()
                started = time.perf_counter()
                with torch.no_grad():
                    stack = model(source, target)
                    tokens = model.generate(stack, max_new_tokens=100, num_beams=4)
                torch.cuda.synchronize()
                row.update(status="success", generation_seconds=time.perf_counter() - started,
                           tokens=tokens.cpu().tolist()[0],
                           prediction=model.mt5_tokenizer.batch_decode(tokens, skip_special_tokens=True)[0],
                           embedding_finite=bool(torch.isfinite(stack["inputs_embeds"]).all()))
                if not row["embedding_finite"]:
                    raise ValueError("モデル埋め込みに非有限値があります")
                (folder / "prediction.txt").write_text(row["prediction"] + "\n", encoding="utf-8")
            except Exception as error:
                row.update(status="failed", error=repr(error), traceback=traceback.format_exc())
                print(row["traceback"], flush=True)
            finally:
                results["rows"].append(row)
                write_json(folder / "result.json", row)
                write_json(out / "results.json", results)
                print(json.dumps({k: row[k] for k in ("id", "variant", "status", "prediction") if k in row}), flush=True)
    # 全条件の生成が確定した後でのみ、GTを読み込んで採点する。
    for row in results["rows"]:
        label = PROJECT_DIR / "data/sign" / row["id"] / "script.txt"
        row.update(reference=label.read_text(encoding="utf-8").strip(),
                   label_path=str(label), label_sha256=sha256(label))
        if row["status"] == "success":
            row["scores"] = score([row])
        write_json(Path(row["output_directory"]) / "result.json", row)
    for variant in variants:
        rows = [row for row in results["rows"] if row["variant"] == variant and row["status"] == "success"]
        results["scores"][variant] = score(rows) if rows else {"count": 0}
    matched = set.intersection(*[{row["id"] for row in results["rows"]
                                 if row["variant"] == variant and row["status"] == "success"}
                                for variant in variants])
    results["paired_ids"] = sorted(matched)
    results["paired_scores"] = {
        variant: score([row for row in results["rows"] if row["variant"] == variant and row["id"] in matched])
        if matched else {"count": 0} for variant in variants
    }
    results["metric_definitions"] = {
        "bleu": "upstream corpus BLEU1-4; mixed case, 13a tokenization, exp smoothing; 0-100 higher better",
        "rouge": "upstream rouge package ROUGE-L F average * 100; higher better",
        "wer": "lowercase regex words retaining internal apostrophes; word edit distance / GT words * 100; lower better",
        "mask": "upstream normalized [x,y,confidence] all zero joint fraction; not translation confidence",
    }
    write_json(out / "results.json", results)
    print(json.dumps(results["scores"], ensure_ascii=False, indent=2), flush=True)
    return 1 if any(row["status"] != "success" for row in results["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main())
