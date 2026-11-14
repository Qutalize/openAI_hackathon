"""From /training uploads to a registered model in one command.

    python training/pipeline.py lipread --data data/training --register

1. Load every recording under data/training/{modality}/{subject}/ that matches the current vocabulary.
2. Evaluate with leave-one-subject-out cross-validation (each person is tested by a model that never
   saw them). With a single person, fall back to a held-out split of their recordings and say so.
3. Train the final model on everyone, pick the candidate threshold on a validation split, export ONNX.
4. Accept when macro-F1 over the phrases is >= 0.80 and unknown movements are accepted <= 5% of the
   time; only then copy the model to models/{modality}/ and record its hashes (with --register).
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from export_onnx import MIN_VALID_RATIO, export
from sklearn.metrics import f1_score
from train_temporal import calibrate, checkpoint, decide, fit, pick_device, probabilities

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.inference.preprocessing import PREPROCESSING_VERSION, pack_frames  # noqa: E402

MAX_FRAMES = {"lipread": 64, "sign": 96}
ACCEPT_F1, ACCEPT_FALSE_ACCEPT = 0.8, 0.05


def load(directory, kind, log=print):
    vocabulary = json.loads((ROOT / "config/vocabulary.ja.json").read_text(encoding="utf-8"))
    labels = [x["id"] for x in vocabulary["items"] if kind in x["modalities"]] + ["unknown"]
    rows, skipped = [], Counter()
    for path in sorted((Path(directory) / kind).glob("*/*.json")):
        sample = json.loads(path.read_text(encoding="utf-8"))
        if sample.get("consent") is not True or sample.get("preprocessing_version") != PREPROCESSING_VERSION:
            skipped["no consent or old preprocessing"] += 1
            continue
        if sample["label"] not in labels:
            skipped["label not in vocabulary"] += 1
            continue
        try:
            features, mask, ratio = pack_frames(
                sample["frames"], sample["timestamps"], MAX_FRAMES[kind], kind
            )
        except ValueError:
            skipped["unreadable"] += 1
            continue
        if ratio < MIN_VALID_RATIO[kind]:
            skipped["too few valid frames"] += 1
            continue
        rows.append((features[0], mask[0], labels.index(sample["label"]), sample["subject_id"]))
    if skipped and log:
        log(f"skipped: {dict(skipped)}")
    if not rows:
        raise SystemExit(f"No usable {kind} recordings under {directory}")
    x = np.stack([r[0] for r in rows])
    m = np.stack([r[1] for r in rows])
    y = np.array([r[2] for r in rows])
    subjects = np.array([r[3] for r in rows])
    return x, m, y, subjects, labels, vocabulary["version"]


def stratified_split(y, fraction, seed):
    """Indices for (rest, held) holding out `fraction` of every class (at least one when possible)."""
    rng = np.random.default_rng(seed)
    held = []
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        if len(idx) > 1:
            held.extend(idx[: max(1, int(round(len(idx) * fraction)))])
    held = np.array(sorted(held), dtype=int)
    rest = np.setdiff1d(np.arange(len(y)), held)
    return rest, held


def scores(probs, targets, unknown, threshold, classes):
    predictions, accept = decide(probs, unknown, threshold)
    known = targets != unknown
    return {
        "macro_f1_known": float(
            f1_score(
                targets[known],
                predictions[known],
                labels=[i for i in range(classes) if i != unknown],
                average="macro",
                zero_division=0,
            )
        )
        if known.any()
        else 0.0,
        "unknown_false_accept_rate": float(accept[~known].mean()) if (~known).any() else None,
        "rejection_rate": float(1 - accept.mean()),
        "samples": int(len(targets)),
    }


def train_and_calibrate(x, m, y, classes, unknown, epochs, seed, device):
    rest, val = stratified_split(y, 0.15, seed)
    model, info = fit(
        (x[rest], m[rest], y[rest]), (x[val], m[val], y[val]), classes, epochs, seed, device, log=None
    )
    threshold = calibrate(probabilities(model, x[val], m[val]), y[val], unknown)
    return model, threshold, info


def evaluate(x, m, y, subjects, labels, epochs, seed, device, log=print):
    unknown, classes = labels.index("unknown"), len(labels)
    people = sorted(set(subjects.tolist()))
    folds, all_probs, all_targets, thresholds = [], [], [], []
    if len(people) >= 2:
        method = "leave-one-subject-out"
        splits = [(np.flatnonzero(subjects != p), np.flatnonzero(subjects == p), p) for p in people]
    else:
        method = "within-subject-holdout"
        rest, held = stratified_split(y, 0.25, seed + 1)
        splits = [(rest, held, people[0])]
    for train_idx, test_idx, person in splits:
        model, threshold, _ = train_and_calibrate(
            x[train_idx], m[train_idx], y[train_idx], classes, unknown, epochs, seed, device
        )
        probs = probabilities(model, x[test_idx], m[test_idx])
        fold = {
            "subject": person,
            "threshold": threshold,
            **scores(probs, y[test_idx], unknown, threshold, classes),
        }
        if log:
            log(json.dumps(fold, ensure_ascii=False))
        folds.append(fold)
        all_probs.append(probs)
        all_targets.append(y[test_idx])
        thresholds.append(threshold)
    probs, targets = np.concatenate(all_probs), np.concatenate(all_targets)
    # Score each fold at its own threshold, then pool the decisions.
    predictions = np.concatenate(
        [decide(p, unknown, t)[0] for p, t in zip(all_probs, thresholds, strict=True)]
    )
    known = targets != unknown
    accepted_mask = predictions != unknown
    overall = {
        "macro_f1_known": float(
            f1_score(
                targets[known],
                predictions[known],
                labels=[i for i in range(classes) if i != unknown],
                average="macro",
                zero_division=0,
            )
        ),
        "unknown_false_accept_rate": float(accepted_mask[~known].mean()) if (~known).any() else 1.0,
        "rejection_rate": float(1 - accepted_mask.mean()),
        "test_samples": int(len(targets)),
        "test_subjects": len(people) if method == "leave-one-subject-out" else 1,
    }
    accepted = (
        overall["macro_f1_known"] >= ACCEPT_F1 and overall["unknown_false_accept_rate"] <= ACCEPT_FALSE_ACCEPT
    )
    return {
        "accepted": bool(accepted),
        "method": method,
        "criteria": {"macro_f1_known": ACCEPT_F1, "unknown_false_accept_rate": ACCEPT_FALSE_ACCEPT},
        **overall,
        "folds": folds,
        "note": ""
        if method == "leave-one-subject-out"
        else "Only one person recorded; accuracy for new people is unknown.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("modality", choices=["lipread", "sign"])
    p.add_argument("--data", default=str(ROOT / "data/training"))
    p.add_argument("--work", default=str(ROOT / "data/training-runs"))
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto")
    p.add_argument("--license", default="CC-BY-4.0")
    p.add_argument(
        "--register", action="store_true", help="copy an accepted model to models/ and record hashes"
    )
    args = p.parse_args()
    kind, device = args.modality, pick_device(args.device)
    x, m, y, subjects, labels, vocabulary_version = load(args.data, kind)
    counts = Counter(labels[i] for i in y)
    print(f"{kind}: {len(y)} recordings from {len(set(subjects))} people on {device}; {dict(counts)}")
    missing = [label for label in labels if counts[label] < 2]
    if missing:
        raise SystemExit(f"Every phrase and unknown needs at least 2 recordings; missing: {missing}")
    evaluation = evaluate(x, m, y, subjects, labels, args.epochs, args.seed, device)
    print(json.dumps({k: v for k, v in evaluation.items() if k != "folds"}, ensure_ascii=False))
    unknown = labels.index("unknown")
    model, threshold, info = train_and_calibrate(
        x, m, y, len(labels), unknown, args.epochs, args.seed, device
    )
    version = f"{kind}-ja-{time.strftime('%Y%m%d-%H%M%S')}"
    run = Path(args.work) / version
    c = checkpoint(
        model,
        labels,
        kind,
        vocabulary_version,
        MAX_FRAMES[kind],
        {
            "seed": args.seed,
            "best_epoch": info["best_epoch"],
            "candidate_threshold": threshold,
            "training_data_summary": {
                "subjects": len(set(subjects.tolist())),
                "samples": int(len(y)),
                "per_label": dict(counts),
                "split_by_person": evaluation["method"] == "leave-one-subject-out",
            },
        },
    )
    run.mkdir(parents=True, exist_ok=True)
    torch.save(c, run / "checkpoint.pt")
    export(c, run, version, args.license, evaluation)
    print(f"model: {run} (threshold {threshold}, accepted={evaluation['accepted']})")
    if not args.register:
        return 0 if evaluation["accepted"] else 1
    if not evaluation["accepted"]:
        print("Not registered: the model did not meet the acceptance criteria.")
        return 1
    target = ROOT / "models" / kind
    target.mkdir(parents=True, exist_ok=True)
    for name in ("model.onnx", "metadata.json", "labels.json"):
        shutil.copy2(run / name, target / name)
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_models.py"), "--register", kind], check=True)
    print(f"registered {version} in {target}; restart the server to load it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
