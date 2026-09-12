"""保存済み英文を正解原稿と比較する。モデル推論・学習は行わない。"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", nargs=2, action="append", required=True,
                        metavar=("RESULT_JSON", "REFERENCE_TXT"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    for result_name, reference_name in args.pair:
        result_path, reference_path = Path(result_name), Path(reference_name)
        result = json.loads(result_path.read_text())
        outputs = [item for item in result["outputs"]
                   if item["requested_output_language"] == "English"]
        if len(outputs) != 1:
            raise ValueError(f"Expected one English output: {result_path}")
        prediction = outputs[0]["raw_text"].strip()
        reference = reference_path.read_text().strip()
        rows.append({
            "result_path": str(result_path), "reference_path": str(reference_path),
            "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
            "variant": result["variant"],
            "checkpoint_sha256": result["checkpoint_sha256"],
            "reference": reference, "prediction": prediction,
            "exact_match": prediction == reference,
            "rougeL_f1_100": scorer.score(reference, prediction)["rougeL"].fmeasure * 100,
        })
    predictions = [row["prediction"] for row in rows]
    references = [row["reference"] for row in rows]
    metrics, signatures = {}, {}
    for order in range(1, 5):
        bleu = BLEU(max_ngram_order=order, tokenize="13a")
        metrics[f"bleu{order}"] = bleu.corpus_score(predictions, [references]).score
        signatures[f"bleu{order}"] = str(bleu.get_signature())
    metrics["rougeL_f1_100"] = sum(row["rougeL_f1_100"] for row in rows) / len(rows)
    metrics["exact_match_count"] = sum(row["exact_match"] for row in rows)
    metrics["sample_count"] = len(rows)
    report = {
        "method": "SpaMo utils/evaluate.py conventions: corpus BLEU 13a; mean stemmed ROUGE-L F1 x100; exact match strips outer whitespace only",
        "versions": {name: importlib.metadata.version(name)
                     for name in ("sacrebleu", "rouge-score")},
        "bleu_signatures": signatures, "metrics": metrics, "samples": rows,
        "limitations": "Two local videos only; text overlap is not semantic accuracy or a How2Sign benchmark result.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
