"""保存済みASL動画07/08の3モデル結果を同一定義で採点・集計する。推論は行わない。"""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys

from benchmark_pro_videos import INPUTS, PROJECT, SIGN


MODELS = ("uni-sign", "SpaMo", "ssvp_slt")
UNI_ROOT = SIGN / "uni-sign"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_prediction(entry):
    model = entry["model"]
    folder = Path(entry["model_output_dir"])
    raw_path = folder / ("results.json" if model == "uni-sign" else "result.json")
    raw = read_json(raw_path)
    if model == "uni-sign":
        require(len(raw["rows"]) == 1, f"Uni-Signは1入力ずつの結果が必要です: {raw_path}")
        result = raw["rows"][0]
        require(result["status"] == "success" and result["id"] == entry["id"]
                and result["variant"] == "original", f"Uni-Sign結果が不一致です: {raw_path}")
        prediction = result["prediction"]
        input_path, input_hash = result["input_path"], result["input_sha256"]
        timings = {key: raw[key] for key in ("model_loading_seconds",) if key in raw}
        timings.update({key: result[key] for key in
                        ("pose_extraction_seconds", "preprocessing_seconds", "generation_seconds")
                        if key in result})
        prediction_path = Path(result["output_directory"]) / "prediction.txt"
        timing_note = ("preprocessing_secondsはpose抽出・姿勢モデル初期化・pose保存/hash・正規化を含む。"
                       "pose_extraction_secondsはその内数。generation_secondsはCUDA同期ありの"
                       "pose encoder forwardと英文生成で、前処理後の入力GPU転送は区間外。")
    elif model == "SpaMo":
        result = raw
        require(raw["status"] == "generation_complete_provider_declared_asl_checkpoint"
                and raw["variant"] == "sign-vla", f"SpaMoのASL派生版結果が必要です: {raw_path}")
        require(len(raw["outputs"]) == 1 and
                raw["outputs"][0]["requested_output_language"] == "English",
                f"SpaMoの英語1出力が必要です: {raw_path}")
        prediction = raw["outputs"][0]["raw_text"]
        input_path, input_hash = raw["input"], raw["input_sha256"]
        timings = {key: raw[key] for key in
                   ("feature_seconds", "model_load_seconds", "wall_seconds") if key in raw}
        timings["outputs"] = [{key: item[key] for key in
                               ("requested_output_language", "generation_seconds") if key in item}
                              for item in raw["outputs"]]
        prediction_path = None
        timing_note = ("feature_secondsはCLIP/VideoMAEのロード・特徴抽出・解放を含む。"
                       "model_load_secondsは翻訳モデルのみ。各計測末尾はCUDA同期あり。"
                       "デコードとcropはfeature_seconds区間外。")
    else:
        result = raw
        require(raw["status"] == "success", f"SSVP-SLT結果が成功していません: {raw_path}")
        prediction = raw["prediction"]
        input_path, input_hash = raw["input"]["path"], raw["input"]["sha256"]
        timings = {key: raw[key] for key in
                   ("subprocess_wall_seconds", "wrapper_wall_seconds", "upstream_reported_seconds")
                   if key in raw}
        prediction_path = folder / "prediction.txt"
        timing_note = ("upstream_reported_secondsは上流のtime.time()によるCUDA同期なしの参考値。"
                       "顔検出はこの環境ではCPU実行。subprocess/wrapper/CLIの計測境界は異なる。")
    require(isinstance(prediction, str) and prediction.strip(), f"英文出力が空です: {raw_path}")
    require(Path(input_path).resolve() == Path(entry["input_path"]).resolve()
            and input_hash == entry["input_sha256"], f"モデル入力がbenchmarkと不一致です: {raw_path}")
    if prediction_path is not None:
        require(prediction_path.read_text(encoding="utf-8").strip() == prediction,
                f"prediction.txtとJSONの出力が不一致です: {prediction_path}")
    return {"prediction": prediction, "model_reported_timing": timings,
            "model_timing_note": timing_note,
            "model_reported_peak_allocated_gpu_gib": raw.get("peak_allocated_gpu_gib"),
            "source_result_path": str(raw_path.resolve()), "source_result_sha256": sha256(raw_path)}, result


def aggregate(rows, score):
    measurements = [row["measurement"] for row in rows]
    elapsed = sum(value["cli_wall_seconds"] for value in measurements)
    return {
        "count": len(rows), "scores": score(rows),
        "cli_wall_seconds_total": elapsed,
        "cli_wall_seconds_mean": elapsed / len(rows),
        "cli_wall_seconds_min": min(value["cli_wall_seconds"] for value in measurements),
        "cli_wall_seconds_max": max(value["cli_wall_seconds"] for value in measurements),
        **{key: max(value[key] for value in measurements) for key in
           ("peak_device_memory_mib", "peak_device_memory_delta_mib",
            "peak_owned_process_memory_mib", "peak_device_utilization_percent")},
        "mean_device_utilization_percent_time_weighted": sum(
            value["mean_device_utilization_percent"] * value["cli_wall_seconds"]
            for value in measurements) / elapsed,
        "peak_aggregation": "各動画のサンプリングピークの最大値。2本同時実行の消費量ではない。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    benchmark_path, output_path = args.benchmark.resolve(), args.output.resolve()
    require(not output_path.exists(), f"新規の出力JSONを指定してください: {output_path}")
    require(SIGN / "outputs" in output_path.parents,
            "参照原稿を含む生の集計JSONはresearch/sign/outputs以下に保存してください")
    benchmark = read_json(benchmark_path)
    require(benchmark.get("status") == "success", "全モデルのbenchmark完了後に採点してください")
    expected = {(model, sample_id) for model in MODELS for sample_id, _ in INPUTS}
    entries = benchmark["rows"]
    require(len(entries) == len(expected) and
            {(row["model"], row["id"]) for row in entries} == expected,
            "3モデル×同じ2動画の成功結果が各1件ずつ必要です")
    sys.path.insert(0, str(UNI_ROOT / "Uni-Sign"))
    sys.path.insert(0, str(UNI_ROOT / "scripts"))
    from score_saved_results import score

    originals = {sample_id: PROJECT / "data/sign" / sample_id / filename
                 for sample_id, filename in INPUTS}
    input_hashes = {sample_id: sha256(path) for sample_id, path in originals.items()}
    rows = []
    gpu_uuids = set()
    for entry in entries:
        model, sample_id = entry["model"], entry["id"]
        measurement = entry["measurement"]
        require(measurement["status"] == "success" and measurement["returncode"] == 0
                and measurement["sample_count"] > 0 and not measurement["monitor_errors"]
                and not measurement["unrelated_compute_pids"],
                f"推論またはGPU計測が正常完了していません: {model}/{sample_id}")
        gpu_uuids.add(measurement["baseline"]["gpu_uuid"])
        measurement_path = Path(entry["measurement_dir"]) / "measurement.json"
        require(read_json(measurement_path) == measurement,
                f"measurement.jsonとbenchmark記録が不一致です: {measurement_path}")
        require(Path(entry["input_path"]).resolve() == originals[sample_id].resolve()
                and entry["input_sha256"] == input_hashes[sample_id],
                f"現在の原動画とbenchmark入力が不一致です: {model}/{sample_id}")
        prediction, raw_row = load_prediction(entry)
        label = originals[sample_id].parent / "script.txt"
        reference = label.read_text(encoding="utf-8").strip()
        label_hash = sha256(label)
        require(bool(reference), f"参照原稿が空です: {label}")
        if model == "uni-sign":
            require(raw_row["reference"] == reference and raw_row["label_sha256"] == label_hash,
                    f"Uni-Sign実行時と現在の参照原稿が不一致です: {label}")
        row = {"model": model, "id": sample_id, **prediction,
               "reference": reference, "label_path": str(label.resolve()), "label_sha256": label_hash,
               "input_path": str(originals[sample_id].resolve()), "input_sha256": input_hashes[sample_id],
               "measurement": measurement, "measurement_path": str(measurement_path.resolve()),
               "measurement_sha256": sha256(measurement_path)}
        row["scores"] = score([row])
        rows.append(row)
    require(len(gpu_uuids) == 1, "全結果が同一GPUで測定されていません")
    result = {
        "status": "success", "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "input_language": "ASL (user confirmed)", "output_language": "English",
        "source_benchmark": str(benchmark_path), "source_benchmark_sha256": sha256(benchmark_path),
        "scoring_script_sha256": sha256(Path(__file__)),
        "shared_score_function_sha256": sha256(UNI_ROOT / "scripts/score_saved_results.py"),
        "rows": rows, "models": {model: aggregate([row for row in rows if row["model"] == model], score)
                                  for model in MODELS},
        "verification": {"all_six_results_success": True, "same_current_originals_all_models": True,
                         "labels_match_uni_sign_saved_labels": True, "gpu_uuids": sorted(gpu_uuids),
                         "saved_measurements_match_benchmark": True},
        "metric_definitions": {
            "bleu": "既存Uni-Sign上流corpus BLEU1-4。mixed case、13a tokenization、exp smoothing、0-100。文別平均ではない。",
            "rouge": "既存上流rouge packageによるROUGE-L F値の文平均×100。",
            "wer": "小文字化・句読点除去・語中apostrophe保持。全単語編集数/全原稿語数×100。100%超過もある。",
            "exact_match": "大小文字・空白・句読点を区別する文字列完全一致。",
            "cli_wall_seconds": "新規CLI起動から終了検出まで。モデルロード・前処理・生成・hash/記録処理を含む。",
            "memory": "nvidia-smiのMiB単位サンプリング。device全体、baseline差、対象process群合算を区別。",
            "utilization": "device全体のGPU利用率。モデル別平均は各CLI時間で加重し、CPU処理・ロード・記録時間も含む。",
        },
        "notes": [
            "全6件の保存英文を無補正で採点。推論・学習・正解を使うプロンプト処理は行わない。",
            "参照原稿は各script.txt。映像の手話をASL話者が独立確認した正解ではない。",
            "短文2本の診断。BLEU/ROUGEは正答率ではなく、WERは妥当な言い換えも罰する。意味と固有名詞の一致は別途評価する。",
            "各動画1回の新規プロセス実行。OSファイルキャッシュ未消去。定常推論の平均/p95や一般的なモデル順位ではない。",
            "モデル固有タイマーは名称を維持。範囲が異なるため直接同一条件の速度指標として扱わない。",
            "GPUピークはサンプリングで取りこぼし得る。device baseline差は参考。PyTorch allocatedとは計測範囲が異なる。",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result["models"], ensure_ascii=False, indent=2))
    print(f"保存先: {output_path}")


if __name__ == "__main__":
    main()
