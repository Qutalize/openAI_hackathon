"""保存poseによるUni-Sign時間診断。学習・pose再抽出・ネットワーク接続は行わない。"""

import argparse
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import pickle
import shlex
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision
import time

from run_online import CHECKPOINT, EXPECTED_CHECKPOINT_SHA256, MODEL_DIR, MT5_REVISION, sha256

PARTS = ("body", "left", "right", "face_all")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    cli = parser.parse_args()
    cli.result = cli.result.resolve()
    out = cli.output_dir.resolve()
    if (MODEL_DIR / "outputs").resolve() not in out.parents:
        parser.error("保存先はUni-Sign/outputs以下の新規ディレクトリに限定します")
    if cli.worker:
        return worker(cli, out)
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError("checkpoint hash mismatch")
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    torch_dir = Path(importlib.util.find_spec("torch").origin).parent
    libs = [torch_dir / "lib"] + sorted((torch_dir.parent / "nvidia").glob("*/lib"))
    env.update(UNI_SIGN_INFERENCE_ONLY="1", PYTHONDONTWRITEBYTECODE="1",
               TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TORCH_HOME=str(MODEL_DIR / "weights/torch-cache"),
               HF_HOME=str(MODEL_DIR / "weights/hf-cache"), TRITON_CACHE_DIR=str(out / "triton-cache"))
    env["LD_LIBRARY_PATH"] = os.pathsep.join([str(p) for p in libs if p.is_dir()] +
                                            ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else []))
    command = [sys.executable, "-B", "-u", str(Path(__file__).resolve()), "--result", str(cli.result),
               "--output-dir", str(out), "--worker"]
    metadata = {
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "running", "command": command, "cwd": str(MODEL_DIR),
        "script_sha256": sha256(Path(__file__)), "result_sha256": sha256(cli.result),
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256, "mt5_revision": MT5_REVISION,
        "upstream_revision": upstream_revision(MODEL_DIR),
        "python": sys.version,
        "environment": {k: env[k] for k in ("LD_LIBRARY_PATH", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "UNI_SIGN_INFERENCE_ONLY")},
    }
    metadata["source_hashes"] = {str(p.relative_to(MODEL_DIR)): sha256(p) for p in
                                  [MODEL_DIR / "models.py", MODEL_DIR / "datasets.py", MODEL_DIR / "utils.py"] +
                                  sorted((MODEL_DIR / "stgcn_layers").glob("*.py"))}
    metadata["mt5_file_hashes"] = {p.name: sha256(p) for p in (MODEL_DIR / "weights/mt5-base").iterdir() if p.is_file()}
    write_json(out / "manifest.json", metadata)
    (out / "analysis_script.py.txt").write_text(Path(__file__).read_text(), encoding="utf-8")
    (out / "command.txt").write_text(shlex.join(command) + "\n")
    (out / "environment.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    with (out / "analysis.log").open("w") as log:
        rc = subprocess.run(command, cwd=MODEL_DIR, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    metadata.update(status="complete" if rc == 0 else "failed", returncode=rc,
                    finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write_json(out / "manifest.json", metadata)
    print(f"exit_code={rc}; outputs={out}")
    return rc


def worker(cli, out):
    import cv2
    import numpy as np
    import torch
    import torch.nn.functional as F
    sys.path.insert(0, str(MODEL_DIR))
    import utils
    from datasets import S2T_Dataset_online
    from models import Uni_Sign

    if not torch.cuda.is_available():
        raise RuntimeError("CUDAが必要です。共有GPUへアクセス可能な実行環境を使用してください")
    record = json.loads(cli.result.read_text())
    integrity = {}
    for field, hash_field in [("input_path", "input_sha256"), ("pose_path", "pose_cache_sha256"), ("label_path", "label_sha256")]:
        digest = sha256(Path(record[field]))
        integrity[field] = {"path": record[field], "actual_sha256": digest, "matches": digest == record[hash_field]}
        assert integrity[field]["matches"], field
    assert (cli.result.parent / "prediction.txt").read_text().strip() == record["prediction"]
    cap = cv2.VideoCapture(record["input_path"])
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames, size = 0, None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        size = list(frame.shape[:2][::-1])
        frames += 1
    cap.release()
    assert frames == record["video_metadata"]["frames"] == 109
    assert fps == record["video_metadata"]["fps"] == 30
    assert size == [record["video_metadata"]["width"], record["video_metadata"]["height"]]
    selected = record["frames"]["selected_absolute_indices"]
    assert selected == list(range(frames)), "この診断の介入窓は109フレーム・間引きなしを前提とします"
    integrity.update(decoded_frames=frames, size=size, fps=fps, prediction_text_matches=True)
    write_json(out / "integrity.json", integrity)
    with Path(record["pose_path"]).open("rb") as stream:
        pose = pickle.load(stream)  # hash照合済みのワークスペース内キャッシュに限定
    assert len(pose["keypoints"]) == len(pose["scores"]) == frames
    args = utils.get_args_parser().parse_args(["--dataset", "How2Sign", "--task", "SLT", "--max_length", "256", "--seed", "42"])
    utils.set_seed(42)
    dataset = S2T_Dataset_online(args)
    dataset.pose_data, dataset.rgb_data = pose, record["input_path"]
    original, target = dataset.collate_fn([dataset[0]])
    np.savez_compressed(out / "normalized_pose.npz", **{p: original[p].numpy() for p in PARTS})
    source = {k: v.to(torch.bfloat16).cuda() if isinstance(v, torch.Tensor) else v for k, v in original.items()}
    model = Uni_Sign(args)
    state = torch.load(CHECKPOINT, map_location="cpu")["model"]
    checkpoint_dtypes = sorted({str(x.dtype) for x in state.values()})
    loaded = model.load_state_dict(state, strict=True)
    del state
    model.cuda().eval().to(torch.bfloat16)
    tokenizer, lm = model.mt5_tokenizer, model.mt5_model
    summary = {"recorded_prediction": record["prediction"], "recorded_tokens": record["tokens"],
               "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "cuda": torch.version.cuda,
               "cudnn": torch.backends.cudnn.version(), "args": vars(args),
               "checkpoint_dtypes": checkpoint_dtypes, "missing_keys": loaded.missing_keys, "unexpected_keys": loaded.unexpected_keys,
               "dtype": "bfloat16", "seed": 42, "eval": True, "training": False,
               "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
               "cudnn_deterministic": torch.backends.cudnn.deterministic, "cudnn_benchmark": torch.backends.cudnn.benchmark,
               "allow_tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
               "generation_config": lm.generation_config.to_dict(), "generation_overrides": {"max_new_tokens": 100, "num_beams": 4},
               "model_config": lm.config.to_dict(), "tokenizer_class": type(tokenizer).__name__,
               "interventions": []}

    def cpu(x):
        return x.detach().float().cpu().numpy()

    def generate(stack, **kwargs):
        utils.set_seed(42)
        return lm.generate(inputs_embeds=stack["inputs_embeds"], attention_mask=stack["attention_mask"],
                           max_new_tokens=100, num_beams=4, **kwargs)

    with torch.no_grad():
        utils.set_seed(42)
        stack = model(source, target)
        baseline = model.generate(stack, max_new_tokens=100, num_beams=4)
        repeat = generate(stack)
        summary["baseline_tokens"] = baseline[0].tolist()
        summary["baseline_prediction"] = tokenizer.decode(baseline[0], skip_special_tokens=True)
        summary["baseline_matches_record"] = baseline[0].tolist() == record["tokens"]
        summary["repeat_matches"] = torch.equal(baseline, repeat)
        print("BASELINE", summary["baseline_prediction"], summary["baseline_matches_record"], flush=True)
        write_json(out / "summary.json", summary)

        # 計測hookは出力を書き換えない。共有された左右moduleは呼び出し順で記録する。
        captured, calls = {}, {}
        def hook(name):
            def callback(module, inputs, output):
                index = calls.get(name, 0)
                calls[name] = index + 1
                captured[f"{name}_{index}"] = cpu(output)
            return callback
        handles = [model.pose_proj.register_forward_hook(hook("pose_proj"))]
        for name, module in [("spatial_body", model.gcn_modules["body"]), ("spatial_hands", model.gcn_modules["right"]),
                             ("spatial_face", model.gcn_modules["face_all"]),
                             ("temporal_body", model.fusion_gcn_modules["body"]), ("temporal_hands", model.fusion_gcn_modules["right"]),
                             ("temporal_face", model.fusion_gcn_modules["face_all"])]:
            handles.append(module.register_forward_hook(hook(name)))
        observed_stack = model(source, target)
        for handle in handles:
            handle.remove()
        summary["hook_embedding_max_abs_delta"] = float((stack["inputs_embeds"] - observed_stack["inputs_embeds"]).abs().max())
        observed = generate(observed_stack, output_attentions=True, output_scores=True, return_dict_in_generate=True)
        summary["attention_generation_tokens"] = observed.sequences[0].tolist()
        summary["attention_generation_matches"] = torch.equal(baseline, observed.sequences)
        assert summary["hook_embedding_max_abs_delta"] == 0
        assert summary["attention_generation_matches"]
        prefix_length = stack["inputs_embeds"].shape[1] - frames
        prefix = tokenizer("Translate sign language video to English: ", return_tensors="pt")["input_ids"][0].tolist()
        assert len(prefix) == prefix_length
        summary["prefix"] = {"length": prefix_length, "ids": prefix, "tokens": tokenizer.convert_ids_to_tokens(prefix)}
        summary["shapes"] = {k: list(v.shape) for k, v in source.items() if isinstance(v, torch.Tensor)}
        summary["shapes"]["inputs_embeds"] = list(stack["inputs_embeds"].shape)
        summary["attention_mask"] = cpu(stack["attention_mask"])[0].tolist()
        summary["feature_shapes"] = {k: list(v.shape) for k, v in captured.items()}
        captured.update(inputs_embeds=cpu(stack["inputs_embeds"]), attention_mask=cpu(stack["attention_mask"]))
        np.savez_compressed(out / "intermediate_features.npz", **captured)
        mapping = [{"encoder_position": prefix_length + j, "pose_index": j, "frame": f, "seconds": f / fps,
                    "normalized_pose_rf_start_frame": max(0, f - 6), "normalized_pose_rf_end_frame": min(frames - 1, f + 6),
                    "zero_padded_left": max(0, 6 - j), "zero_padded_right": max(0, j + 6 - frames + 1)} for j, f in enumerate(selected)]
        write_json(out / "time_mapping.json", {"prefix": summary["prefix"], "video_positions": mapping,
                   "caveat": "時刻は位置アンカー。正規化は全系列のextrema、mT5 encoderは全系列を混合する。RFは正規化後poseに対する3段k5/s1/p2の構造的範囲。"})

        # generateが実際に通った最終beamの祖先からcross-attentionを回収する。
        count = baseline.shape[1] - 1
        ancestry = observed.beam_indices[0, :count].tolist()
        assert len(ancestry) == count and min(ancestry) >= 0
        generation_cross = np.stack([np.stack([cpu(layer[b, :, -1, :]) for layer in observed.cross_attentions[t]])
                                     for t, b in enumerate(ancestry)], axis=2)
        transition = lm.compute_transition_scores(observed.sequences, observed.scores, observed.beam_indices, normalize_logits=True)[0]
        np.savez_compressed(out / "generation_attention.npz", cross=generation_cross,
                            encoder=np.stack([cpu(x[0]) for x in observed.encoder_attentions]),
                            beam_indices=np.array(ancestry), transition_logprobs=cpu(transition))
        summary["generation_beam_score"] = float(observed.sequences_scores[0])

        fixed = {"prediction": baseline[0, 1:].clone(),
                 "gt": tokenizer(record["reference"], return_tensors="pt")["input_ids"][0].cuda()}

        def diagnose(current, name, keep=False):
            labels = fixed[name].unsqueeze(0)
            result = lm(inputs_embeds=current["inputs_embeds"], attention_mask=current["attention_mask"], labels=labels,
                        output_attentions=keep, output_hidden_states=keep, return_dict=True, use_cache=False)
            log_probs = F.log_softmax(result.logits[0].float(), dim=-1)
            chosen = log_probs.gather(1, labels[0, :, None]).squeeze(1)
            ids = labels[0].tolist()
            rows = []
            for t, token_id in enumerate(ids):
                top = torch.topk(log_probs[t], 5)
                rows.append({"position": t, "token_id": token_id, "subword": tokenizer.convert_ids_to_tokens(token_id),
                             "decoded_prefix": tokenizer.decode(ids[:t], skip_special_tokens=False),
                             "probability": float(chosen[t].exp()), "log_probability": float(chosen[t]),
                             "eos_probability": float(log_probs[t, tokenizer.eos_token_id].exp()),
                             "eos_rank": int((log_probs[t] > log_probs[t, tokenizer.eos_token_id]).sum()) + 1,
                             "target_rank": int((log_probs[t] > chosen[t]).sum()) + 1,
                             "top5": [{"id": int(i), "subword": tokenizer.convert_ids_to_tokens(int(i)), "probability": float(p.exp())}
                                      for p, i in zip(top.values, top.indices)]})
            stats = {"text": tokenizer.decode(ids, skip_special_tokens=True), "tokens": rows,
                     "token_count_with_eos": len(ids), "sum_logprob_with_eos": float(chosen.sum()),
                     "mean_logprob_with_eos": float(chosen.mean()),
                     "sum_logprob_without_eos": float(chosen[labels[0] != tokenizer.eos_token_id].sum()),
                     "mean_logprob_without_eos": float(chosen[labels[0] != tokenizer.eos_token_id].mean())}
            if keep:
                arrays = {"cross": np.stack([cpu(x[0]) for x in result.cross_attentions]),
                          "encoder_self": np.stack([cpu(x[0]) for x in result.encoder_attentions]),
                          "decoder_self": np.stack([cpu(x[0]) for x in result.decoder_attentions]),
                          "encoder_hidden": np.stack([cpu(x[0]) for x in result.encoder_hidden_states]),
                          "decoder_hidden": np.stack([cpu(x[0]) for x in result.decoder_hidden_states]),
                          "token_ids": np.array(ids)}
                np.savez_compressed(out / f"{name}_teacher_forced.npz", **arrays)
                write_json(out / f"{name}_tokens.json", stats)
                if name == "prediction":
                    summary["generation_vs_teacher_cross_mean_abs_delta"] = float(np.abs(generation_cross - arrays["cross"]).mean())
                    summary["generation_vs_teacher_cross_max_abs_delta"] = float(np.abs(generation_cross - arrays["cross"]).max())
                    summary["generation_vs_teacher_logprob_max_abs_delta"] = float(np.abs(cpu(transition) - cpu(chosen)).max())
            return stats

        summary["baseline_scores"] = {name: diagnose(stack, name, True) for name in fixed}
        # 第1prefixは共通だが、予測第1tokenは単独▁、GTは▁I。Theyは予測第2token。
        # 正規化後に置換し、全系列scale変化を交絡させない。長さとmaskは維持する。
        windows = [("freeze_012_035", 12, 36), ("freeze_036_061", 36, 62), ("freeze_062_098", 62, 99),
                   ("freeze_052_061", 52, 62), ("freeze_099_108", 99, 109)]
        variants = ["static_middle", "reverse", "left_static", "right_static"] + [w[0] for w in windows] + ["zero_visual_embedding", "prefix_only_masked"]
        for variant in variants:
            current_source = {k: v.clone() if isinstance(v, torch.Tensor) else copy.deepcopy(v) for k, v in source.items()}
            details = {"name": variant, "stage": "normalized_pose", "mask_changed": False}
            if variant == "static_middle":
                for p in PARTS:
                    current_source[p] = source[p][:, frames // 2:frames // 2 + 1].expand_as(source[p]).clone()
                details["replacement_frame"] = frames // 2
            elif variant == "reverse":
                for p in PARTS:
                    current_source[p] = source[p].flip(1)
            elif variant in ("left_static", "right_static"):
                p = variant.split("_")[0]
                current_source[p] = source[p][:, :1].expand_as(source[p]).clone()
                details.update(part=p, replacement_frame=0, caveat="手の局所座標/scoreだけ固定。bodyの手首位置は残る")
            elif variant.startswith("freeze_"):
                _, start, end = next(w for w in windows if w[0] == variant)
                for p in PARTS:
                    current_source[p][:, start:end] = source[p][:, start - 1:start]
                details.update(start_frame=start, end_frame_exclusive=end, replacement_frame=start - 1)
            if variant in ("zero_visual_embedding", "prefix_only_masked"):
                current = {"inputs_embeds": stack["inputs_embeds"].clone(), "attention_mask": stack["attention_mask"].clone()}
                current["inputs_embeds"][:, prefix_length:] = 0
                details["stage"] = "before_mt5_encoder"
                if variant == "prefix_only_masked":
                    current["attention_mask"][:, prefix_length:] = 0
                    details["mask_changed"] = True
            else:
                current = model(current_source, target)
            assert current["inputs_embeds"].shape == stack["inputs_embeds"].shape
            if not details["mask_changed"]:
                assert torch.equal(current["attention_mask"], stack["attention_mask"])
            tokens = generate(current)
            details.update(tokens=tokens[0].tolist(), prediction=tokenizer.decode(tokens[0], skip_special_tokens=True),
                           scores={name: diagnose(current, name) for name in fixed})
            details["embedding_relative_l2"] = float((current["inputs_embeds"].float() - stack["inputs_embeds"].float()).norm() / stack["inputs_embeds"].float().norm())
            for name in fixed:
                base = summary["baseline_scores"][name]
                details["scores"][name]["delta_mean_logprob"] = details["scores"][name]["mean_logprob_with_eos"] - base["mean_logprob_with_eos"]
                details["scores"][name]["delta_sum_logprob"] = details["scores"][name]["sum_logprob_with_eos"] - base["sum_logprob_with_eos"]
            summary["interventions"].append(details)
            print("INTERVENTION", variant, details["prediction"], flush=True)
            write_json(out / "summary.json", summary)
        # beam length penaltyの影響を同じ入力で調べる。GTによる長さ制約は使用しない。
        controlled = generate(stack, length_penalty=0.0)
        greedy = lm.generate(inputs_embeds=stack["inputs_embeds"], attention_mask=stack["attention_mask"], max_new_tokens=100, num_beams=1)
        summary["decoding_controls"] = {
            "beam4_length_penalty0": {"tokens": controlled[0].tolist(), "prediction": tokenizer.decode(controlled[0], skip_special_tokens=True)},
            "greedy": {"tokens": greedy[0].tolist(), "prediction": tokenizer.decode(greedy[0], skip_special_tokens=True)}}
        summary["max_gpu_memory_allocated_bytes"] = torch.cuda.max_memory_allocated()
        summary["notes"] = ["teacher forcingは固定prefix下の診断で自由生成成功ではない", "固定文のスコアはEOS込み/除外を両記録、介入差は同じtoken列同士で比較",
                            "Attentionは寄与や因果効果の直接測定ではない", "静止・逆順・ゼロ・置換は自然なASL分布外となる", "この診断は109フレームの指定入力に限定"]
        write_json(out / "summary.json", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
