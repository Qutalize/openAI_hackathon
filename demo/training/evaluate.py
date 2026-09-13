import argparse
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from sklearn.metrics import classification_report, f1_score


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("model_directory")
    args = p.parse_args()
    directory = Path(args.model_directory)
    metadata_path = directory / "metadata.json"
    m = json.loads(metadata_path.read_text(encoding="utf-8"))
    d = np.load(args.dataset, allow_pickle=False)
    if d["labels"].tolist() != m["labels"]:
        raise ValueError("Dataset/model labels differ")
    session = ort.InferenceSession(
        str(directory / "model.onnx"), providers=["CPUExecutionProvider"]
    )
    indices = np.flatnonzero(d["splits"] == "test")
    unknown = m["labels"].index("unknown")
    targets, predictions, accepted = [], [], []
    for i in indices:
        logits = session.run(
            None,
            {"features": d["features"][i : i + 1], "frame_mask": d["masks"][i : i + 1]},
        )[0][0]
        scores = np.exp(logits - logits.max())
        scores /= scores.sum()
        predicted = int(scores.argmax())
        accept = (
            predicted != unknown
            and scores[predicted] >= m["thresholds"]["candidate"]
            and d["valid_ratios"][i] >= 0.8
        )
        targets.append(int(d["targets"][i]))
        predictions.append(predicted if accept else unknown)
        accepted.append(bool(accept))
    targets, predictions, accepted = (
        np.array(targets),
        np.array(predictions),
        np.array(accepted),
    )
    if not len(targets) or set(targets) != set(range(len(m["labels"]))):
        raise ValueError(
            "The held-out test split must contain all classes including unknown"
        )
    known = targets != unknown
    macro = f1_score(
        targets[known],
        predictions[known],
        labels=[i for i in range(len(m["labels"])) if i != unknown],
        average="macro",
        zero_division=0,
    )
    false_accept = float(accepted[~known].mean())
    report = {
        "accepted": bool(macro >= 0.8 and false_accept <= 0.05),
        "macro_f1_known": float(macro),
        "unknown_false_accept_rate": false_accept,
        "rejection_rate": float(1 - accepted.mean()),
        "test_samples": len(targets),
        "test_subjects": len(set(d["subjects"][indices].tolist())),
        "class_report": classification_report(
            targets,
            predictions,
            labels=list(range(len(m["labels"]))),
            target_names=m["labels"],
            output_dict=True,
            zero_division=0,
        ),
    }
    m["evaluation_summary"] = report
    metadata_path.write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
