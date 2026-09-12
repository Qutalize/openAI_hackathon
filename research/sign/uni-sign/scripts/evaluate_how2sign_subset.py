"""How2Sign test の固定少数組を配布poseとオンライン抽出poseで比較する。"""

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import pickle
import random
import shlex
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision
import time
import traceback

from run_online import CHECKPOINT, EXPECTED_CHECKPOINT_SHA256, MODEL_DIR, MT5_REVISION, sha256


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("author", "online", "both"), default="both")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    cli = parser.parse_args()
    cli.manifest = cli.manifest.resolve()
    out = cli.output_dir.resolve()
    if (MODEL_DIR / "outputs").resolve() not in out.parents:
        parser.error("保存先は Uni-Sign/outputs 以下の新規ディレクトリに限定します")
    if cli.worker:
        return worker(cli, out)
    manifest = json.loads(cli.manifest.read_text())
    if not manifest.get("samples"):
        parser.error("manifest.samples が空です")
    if len({sample["id"] for sample in manifest["samples"]}) != len(manifest["samples"]):
        parser.error("sample id が重複しています")
    digest = sha256(CHECKPOINT)
    if digest != EXPECTED_CHECKPOINT_SHA256:
        parser.error("checkpoint SHA256 が公式配布値と一致しません")
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    torch_dir = Path(importlib.util.find_spec("torch").origin).parent
    library_dirs = [torch_dir / "lib"] + sorted((torch_dir.parent / "nvidia").glob("*/lib"))
    env.update(UNI_SIGN_INFERENCE_ONLY="1", PYTHONDONTWRITEBYTECODE="1",
               TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TORCH_HOME=str(MODEL_DIR / "weights/torch-cache"),
               HF_HOME=str(MODEL_DIR / "weights/hf-cache"), TRITON_CACHE_DIR=str(out / "triton-cache"))
    env["LD_LIBRARY_PATH"] = os.pathsep.join([str(p) for p in library_dirs if p.is_dir()] +
                                            ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else []))
    command = [sys.executable, "-B", "-u", str(Path(__file__).resolve()), str(cli.manifest),
               "--output-dir", str(out), "--mode", cli.mode, "--worker"]
    metadata = {
        "status": "running", "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "input_manifest": str(cli.manifest), "input_manifest_sha256": sha256(cli.manifest),
        "source_manifest": manifest, "checkpoint_sha256": digest, "mt5_revision": MT5_REVISION,
        "working_directory": str(MODEL_DIR), "command": command,
        "upstream_revision": upstream_revision(MODEL_DIR),
        "environment": {k: env[k] for k in ("LD_LIBRARY_PATH", "TORCH_HOME", "HF_HOME", "HF_HUB_OFFLINE",
                                               "TRANSFORMERS_OFFLINE", "UNI_SIGN_INFERENCE_ONLY")},
        "settings": {"dataset": "How2Sign", "task": "SLT", "rgb_support": False,
                     "dtype": "bfloat16", "batch_size": 1, "max_length": 256,
                     "seed": 42, "reset_seed_per_sample_and_mode": True,
                     "max_new_tokens": 100, "num_beams": 4, "training": False,
                     "generation_target": "empty string; references used only for scoring",
                     "postprocessing": "tokenizer.batch_decode(skip_special_tokens=True) only"},
        "python": sys.version,
    }
    write_json(out / "manifest.json", metadata)
    (out / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
    (out / "environment.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    print(f"保存先: {out}", flush=True)
    started = time.perf_counter()
    with (out / "inference.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=MODEL_DIR, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        exit_code = process.wait()
    metadata.update(status="success" if exit_code == 0 else "failed", exit_code=exit_code,
                    elapsed_seconds=time.perf_counter() - started,
                    timing_scope="worker startup, model loading, pose extraction, generation and scoring")
    metadata["artifacts_sha256"] = {
        str(p.relative_to(MODEL_DIR)): sha256(p)
        for p in list((MODEL_DIR / "weights/mt5-base").glob("*")) +
        list((MODEL_DIR / "weights/torch-cache/hub/checkpoints").glob("*.onnx")) if p.is_file()
    }
    write_json(out / "manifest.json", metadata)
    return exit_code


def frame_info(pose, respect_boundaries):
    start = int(pose.get("start", 0)) if respect_boundaries else 0
    end = int(pose.get("end", len(pose["scores"]))) if respect_boundaries else len(pose["scores"])
    if not 0 <= start < end <= len(pose["scores"]):
        raise ValueError(f"invalid pose boundaries: {start}:{end}, available={len(pose['scores'])}")
    duration = end - start
    # S2T_Dataset の random.sample と同じ乱数状態から、実際の使用indexを記録する。
    rng = random.Random()
    rng.setstate(random.getstate())
    indices = sorted(rng.sample(range(duration), 256)) if duration > 256 else list(range(duration))
    return {"stored_frames": len(pose["scores"]), "start": start, "end_exclusive": end,
            "segment_frames": duration, "used_frames": len(indices),
            "selected_absolute_indices": [i + start for i in indices]}


def score_rows(rows):
    from SLRT_metrics import sableu, translation_performance
    if not rows:
        return {"count": 0}
    refs = [row["reference"] for row in rows]
    preds = [row["prediction"] for row in rows]
    if all(refs) and all(preds):
        bleu, rouge = translation_performance(refs, preds)
    else:
        bleu, rouge = sableu(refs, preds, "13a"), None
    return {"count": len(rows), "bleu": bleu, "rouge_l_f_percent": rouge,
            "exact_match_count": sum(ref == pred for ref, pred in zip(refs, preds)),
            "metric_definition": "upstream translation_performance: mixed case corpus BLEU1-4, 13a, exp smoothing; rouge package average ROUGE-L F * 100",
            "note": "少数組の診断値。論文の全testスコアを再現した結果ではない。空文字がある場合ROUGEは未計算。"}


def worker(cli, out):
    import cv2
    import torch
    sys.path.insert(0, str(MODEL_DIR))
    import utils
    from datasets import S2T_Dataset, S2T_Dataset_online
    from models import Uni_Sign

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA が利用できません。CPUへ自動切替しません")
    manifest = json.loads(cli.manifest.read_text())
    args = utils.get_args_parser().parse_args(["--dataset", "How2Sign", "--task", "SLT",
                                               "--max_length", "256", "--seed", "42"])
    utils.set_seed(42)
    dataset = S2T_Dataset(str(MODEL_DIR / "data/How2Sign/labels.test"), args, "test")
    # 配布ラベルとの対応を確認し、誤った動画と正解の組を採点しない。
    for sample in manifest["samples"]:
        if sample["id"] not in dataset.raw_data:
            raise ValueError(f"not in official test labels: {sample['id']}")
        if sample["reference"] != dataset.raw_data[sample["id"]]["text"]:
            raise ValueError(f"reference mismatch: {sample['id']}")
    results = {"rows": [], "scores": {}, "gpu": torch.cuda.get_device_name(0),
               "notes": ["配布poseとオンラインpose抽出を同じ学習済みモデル・生成設定で比較。",
                         "評価CLI全体のDeepSpeed/BLEURT経路は実行せず、上流dataset/model/generate/metricsを再利用。",
                         "公式evalの全件処理と異なり、batch1・各sampleのseed42再設定。長系列の選択indexを保存。",
                         "翻訳信頼度は未提供。検出confidenceを翻訳信頼度として扱わない。"]}
    started = time.perf_counter()
    model = Uni_Sign(args)
    state = torch.load(CHECKPOINT, map_location="cpu")["model"]
    loaded = model.load_state_dict(state, strict=True)
    del state
    model.cuda().eval().to(torch.bfloat16)
    torch.cuda.synchronize()
    results["model_loading_seconds"] = time.perf_counter() - started
    results["checkpoint_keys"] = {"missing": loaded.missing_keys, "unexpected": loaded.unexpected_keys}
    modes = ["author", "online"] if cli.mode == "both" else [cli.mode]
    parts = ("body", "left", "right", "face_all")
    for mode in modes:
        for index, sample in enumerate(manifest["samples"]):
            row = {"id": sample["id"], "reference": sample["reference"], "mode": mode,
                   "status": "running", "translation_confidence": None}
            folder = out / mode / f"{index:03d}"
            folder.mkdir(parents=True, exist_ok=False)
            try:
                source_path = sample.get("pose_path" if mode == "author" else "video_path")
                if not source_path or not Path(source_path).is_file():
                    row.update(status="skipped", reason="必要な入力ファイルがmanifestにない、または未取得")
                    continue
                source_path = Path(source_path)
                row.update(input_path=str(source_path), input_sha256=sha256(source_path))
                started = time.perf_counter()
                if mode == "author":
                    with source_path.open("rb") as stream:
                        pose = pickle.load(stream)
                    dataset.pose_dir = str(source_path.parent)
                    utils.set_seed(42)
                    row["frames"] = frame_info(pose, True)
                    normalized, support = dataset.load_pose(source_path.name)
                    source, _ = dataset.collate_fn([(sample["id"], normalized, "", "", support)])
                else:
                    from demo.online_inference import pose_extraction
                    cap = cv2.VideoCapture(str(source_path))
                    row["video_metadata"] = {"width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                                             "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                             "fps": cap.get(cv2.CAP_PROP_FPS),
                                             "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
                    cap.release()
                    pose = pose_extraction(str(source_path))
                    torch.cuda.synchronize()
                    row["pose_extraction_seconds"] = time.perf_counter() - started
                    # 再抽出なしの追試に使うローカル診断cache。元動画・配布poseは変更しない。
                    with (folder / "online_pose.pkl").open("wb") as stream:
                        pickle.dump(pose, stream, protocol=4)
                    row["pose_cache_sha256"] = sha256(folder / "online_pose.pkl")
                    online = S2T_Dataset_online(args)
                    online.pose_data, online.rgb_data = pose, str(source_path)
                    utils.set_seed(42)
                    row["frames"] = frame_info(pose, False)
                    source, _ = online.collate_fn([online[0]])
                row["pose_people_counts"] = sorted(set(len(frame) for frame in pose["keypoints"]))
                row["normalized_pose"] = {
                    part: {"shape": list(source[part].shape), "finite": bool(torch.isfinite(source[part]).all()),
                           "all_zero_fraction": float((source[part] == 0).all(dim=-1).float().mean())}
                    for part in parts
                }
                if not all(value["finite"] for value in row["normalized_pose"].values()):
                    raise ValueError("normalized pose contains nonfinite values")
                row["preprocessing_seconds"] = time.perf_counter() - started
                source = {key: value.to(torch.bfloat16).cuda() if isinstance(value, torch.Tensor) else value
                          for key, value in source.items()}
                # 正解文はモデルforwardにも渡さない。上流のloss計算用targetは空文字のみ。
                target = {"gt_sentence": [""], "gt_gloss": [""]}
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
                (folder / "prediction.txt").write_text(row["prediction"] + "\n", encoding="utf-8")
            except Exception as error:
                row.update(status="failed", error=repr(error), traceback=traceback.format_exc())
                print(row["traceback"], flush=True)
            finally:
                results["rows"].append(row)
                write_json(folder / "result.json", row)
                write_json(out / "results.json", results)
                print(json.dumps({k: row[k] for k in ("id", "mode", "status", "prediction") if k in row}), flush=True)
    for mode in modes:
        results["scores"][mode] = score_rows([row for row in results["rows"] if row["mode"] == mode and row["status"] == "success"])
    if len(modes) == 2:
        matched = set.intersection(*[{row["id"] for row in results["rows"] if row["mode"] == mode and row["status"] == "success"} for mode in modes])
        results["paired_scores"] = {mode: score_rows([row for row in results["rows"] if row["mode"] == mode and row["id"] in matched]) for mode in modes}
        results["paired_ids"] = [sample["id"] for sample in manifest["samples"] if sample["id"] in matched]
    write_json(out / "results.json", results)
    return 1 if (any(row["status"] == "failed" for row in results["rows"]) or
                 any(results["scores"][mode]["count"] == 0 for mode in modes)) else 0


if __name__ == "__main__":
    sys.exit(main())
