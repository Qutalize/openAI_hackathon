"""Write synthetic /training uploads, to check that the pipeline can learn at all.

Each phrase moves a different group of points at its own speed; people differ in face shape,
position and speed. Unknown is a slow random drift. The data says nothing about real accuracy.
"""

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def write(directory, kind, people=3, repetitions=6, seed=0):
    vocabulary = json.loads((ROOT / "config/vocabulary.ja.json").read_text(encoding="utf-8"))
    labels = [x["id"] for x in vocabulary["items"] if kind in x["modalities"]] + ["unknown"]
    points, frames = (40, 56) if kind == "lipread" else (100, 80)
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 0.3, (points, 3))
    # Sign takes show only the left hand, so move left-hand and pose points.
    movable = np.arange(points) if kind == "lipread" else np.r_[0:21, 42:75]
    groups = np.array_split(rng.permutation(movable), len(labels) - 1)
    for p in range(people):
        shape = base * rng.uniform(0.9, 1.1) + rng.normal(0, 0.02, (points, 3))
        tempo = rng.uniform(0.85, 1.15)
        for label_index, label in enumerate(labels):
            for r in range(repetitions):
                t = np.arange(frames) * 50.0
                xyz = np.repeat(shape[None], frames, 0) + rng.normal(0, 0.01, (frames, points, 3))
                if label == "unknown":
                    xyz += rng.normal(0, 0.01, (frames, 1, 3)).cumsum(0)
                else:
                    phase = np.linspace(0, np.pi * (1 + label_index % 4) * tempo, frames)
                    axis = label_index % 2
                    xyz[:, groups[label_index], axis] += 0.15 * np.sin(phase)[:, None]
                valid = np.ones((frames, points, 1))
                if kind == "sign":
                    valid[:, 21:42] = 0
                    xyz[:, 21:42] = 0
                sample = {
                    "version": 1,
                    "subject_id": f"synthetic{p:02d}",
                    "label": label,
                    "modality": kind,
                    "consent": True,
                    "created_at": "2026-11-14T00:00:00Z",
                    "preprocessing_version": "landmarks-v1",
                    "mediapipe_version": "0.10.32",
                    "frames": np.concatenate([xyz, valid], 2).round(4).tolist(),
                    "timestamps": t.tolist(),
                }
                folder = Path(directory) / kind / sample["subject_id"]
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{label}--{r}.json").write_text(json.dumps(sample), encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("modality", choices=["lipread", "sign"])
    p.add_argument("directory")
    p.add_argument("--people", type=int, default=3)
    p.add_argument("--repetitions", type=int, default=6)
    a = p.parse_args()
    write(a.directory, a.modality, a.people, a.repetitions)
