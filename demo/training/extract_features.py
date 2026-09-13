"""Pack the exact browser-extracted features; never silently change detector versions."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.inference.preprocessing import PREPROCESSING_VERSION, pack_frames  # noqa: E402


def extract(manifest_path, destination):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kind = manifest["modality"]
    if kind not in ("lipread", "sign"):
        raise ValueError("modality must be lipread or sign")
    vocabulary = json.loads(
        (ROOT / "config/vocabulary.ja.json").read_text(encoding="utf-8")
    )
    labels = [x["id"] for x in vocabulary["items"] if kind in x["modalities"]] + [
        "unknown"
    ]
    subjects, seen_paths, rows = {}, set(), []
    for entry in manifest["samples"]:
        path = (manifest_path.parent / entry["path"]).resolve()
        if path in seen_paths:
            raise ValueError(f"duplicate recording: {path.name}")
        seen_paths.add(path)
        sample = json.loads(path.read_text(encoding="utf-8"))
        if (
            sample.get("consent") is not True
            or sample.get("preprocessing_version") != PREPROCESSING_VERSION
            or sample.get("mediapipe_version") != "0.10.32"
            or sample["modality"] != kind
        ):
            raise ValueError(f"missing consent or preprocessing mismatch: {path.name}")
        subject, split = sample["subject_id"], entry["split"]
        if (
            split not in ("train", "validation", "test")
            or subjects.get(subject, split) != split
        ):
            raise ValueError(
                "A person must belong to exactly one train/validation/test split"
            )
        subjects[subject] = split
        features, mask, valid_ratio = pack_frames(
            sample["frames"],
            sample["timestamps"],
            64 if kind == "lipread" else 96,
            kind,
        )
        rows.append(
            (
                features[0],
                mask[0],
                labels.index(sample["label"]),
                subject,
                split,
                valid_ratio,
            )
        )
    if not rows:
        raise ValueError("No samples supplied")
    for split in ("train", "validation", "test"):
        if {row[2] for row in rows if row[4] == split} != set(range(len(labels))):
            raise ValueError(f"Every class including unknown needs examples in {split}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        features=np.stack([r[0] for r in rows]),
        masks=np.stack([r[1] for r in rows]),
        targets=np.array([r[2] for r in rows]),
        subjects=np.array([r[3] for r in rows]),
        splits=np.array([r[4] for r in rows]),
        valid_ratios=np.array([r[5] for r in rows]),
        labels=np.array(labels),
        modality=kind,
        vocabulary_version=vocabulary["version"],
    )
    print(
        f"Packed {len(rows)} recordings from {len(subjects)} people into {destination}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("output")
    args = parser.parse_args()
    extract(args.manifest, args.output)
