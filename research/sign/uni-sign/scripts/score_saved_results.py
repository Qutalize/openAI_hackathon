"""保存済みHow2Sign/自前ASL出力を同じ指標で採点する。推論・文章補正なし。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MODEL_DIR = Path(__file__).resolve().parents[1] / "Uni-Sign"
PROJECT_DIR = Path(__file__).resolve().parents[4]


def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())


def edit_distance(reference, prediction):
    previous = list(range(len(prediction) + 1))
    for index, token in enumerate(reference, 1):
        current = [index]
        for column, other in enumerate(prediction, 1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (token != other)))
        previous = current
    return previous[-1]


def score(rows):
    from SLRT_metrics import translation_performance
    refs = [row["reference"] for row in rows]
    preds = [row["prediction"] for row in rows]
    bleu, rouge = translation_performance(refs, preds)
    errors = sum(edit_distance(words(ref), words(pred)) for ref, pred in zip(refs, preds))
    length = sum(len(words(ref)) for ref in refs)
    return {"count": len(rows), "bleu": bleu, "rouge_l_f_percent": rouge,
            "wer_percent": errors / length * 100, "word_errors": errors, "reference_words": length,
            "exact_match_count": sum(ref == pred for ref, pred in zip(refs, preds))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-results", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if MODEL_DIR / "outputs" not in out.parents:
        parser.error("保存先はUni-Sign/outputs以下")
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(MODEL_DIR))
    benchmark = json.loads(args.benchmark_results.read_text())
    groups = {mode: [r for r in benchmark["rows"] if r["mode"] == mode and r["status"] == "success"]
              for mode in ("author", "online")}
    groups["self"] = []
    for name, run in (("01_whats_your_name", "20260912-how2sign-01-whats-your-name-gpu"),
                      ("02_greetings", "20260912-how2sign-02-greetings-gpu")):
        label = PROJECT_DIR / "data/sign" / name / "script.txt"
        result_path = MODEL_DIR / "outputs" / run / "result.json"
        result = json.loads(result_path.read_text())
        if result["status"] != "success":
            raise ValueError("saved self inference failed")
        groups["self"].append({"id": name, "reference": label.read_text().strip(),
                               "prediction": result["prediction"], "result_path": str(result_path),
                               "label_path": str(label), "label_sha256": hashlib.sha256(label.read_bytes()).hexdigest(),
                               "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()})
    scores = {name: score(rows) for name, rows in groups.items()}
    individual = [{**row, "scores": score([row])} for row in groups["self"]]
    examples = [{"id": r["id"], "reference": r["reference"], "prediction": r["prediction"]}
                for r in groups["online"] if r["id"] in ("g3X3XE6M2_A_15-3-rgb_front.mp4",
                                                          "g0iNy-yPisM_17-8-rgb_front.mp4",
                                                          "FZCF7kPIyOk_10-1-rgb_front.mp4")]
    result = {"scores": scores, "self_samples": individual, "how2sign_online_examples": examples,
              "source_benchmark": str(args.benchmark_results.resolve()),
              "source_benchmark_sha256": hashlib.sha256(args.benchmark_results.read_bytes()).hexdigest(),
              "metric_definitions": {"bleu": "upstream corpus BLEU1-4; case mixed, tokenization 13a, exp smoothing; 0-100 higher better",
                                     "rouge": "upstream rouge package ROUGE-L F average * 100; higher better",
                                     "wer": "sum uniform-cost word Levenshtein distances / sum reference words * 100; lowercase; regex words retain internal apostrophes, drop punctuation; lower better; may exceed 100",
                                     "exact_match": "case/space/punctuation sensitive full string equality"},
              "notes": ["Scores use saved original GPU self predictions, not later FP32/static/zero controls.",
                        "No new inference, training, or sentence correction.",
                        "Small different datasets; no statistical/generalization claim.",
                        "WER is supplementary: valid translation paraphrases may be penalized."]}
    (out / "scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(scores, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
