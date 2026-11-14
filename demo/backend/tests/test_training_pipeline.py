"""The training pipeline learns separable synthetic motions across people and exports a model the
server accepts. Needs the training extra (torch); skipped otherwise."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("sklearn")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "training"))

import pipeline  # noqa: E402
import synthetic  # noqa: E402
from export_onnx import export  # noqa: E402
from train_temporal import checkpoint, pick_device  # noqa: E402

from app.inference.lipread import TemporalRecognizer  # noqa: E402

DEVICE = pick_device()


@pytest.mark.parametrize("kind", ["lipread", "sign"])
def test_pipeline_generalises_to_an_unseen_person_and_exports(tmp_path, kind):
    synthetic.write(tmp_path / "data", kind, people=3, repetitions=4)
    x, m, y, subjects, labels, version = pipeline.load(tmp_path / "data", kind, log=None)
    evaluation = pipeline.evaluate(x, m, y, subjects, labels, epochs=40, seed=0, device=DEVICE, log=None)
    assert evaluation["method"] == "leave-one-subject-out"
    assert evaluation["accepted"], evaluation
    unknown = labels.index("unknown")
    model, threshold, info = pipeline.train_and_calibrate(x, m, y, len(labels), unknown, 40, 0, DEVICE)
    c = checkpoint(
        model,
        labels,
        kind,
        version,
        pipeline.MAX_FRAMES[kind],
        {"candidate_threshold": threshold, "training_data_summary": {"subjects": 3, "samples": len(y)}},
    )
    export(c, tmp_path / "run", "test-model", "test-license", evaluation)
    vocabulary = json.loads((ROOT / "config/vocabulary.ja.json").read_text(encoding="utf-8"))
    config = {
        "feature_schema": "lip40_v1" if kind == "lipread" else "sign100_v1",
        "max_frames": pipeline.MAX_FRAMES[kind],
        "min_valid_frame_ratio": 0.8 if kind == "lipread" else 0.5,
        "candidate_threshold": 0.5,
        "top_k": 3,
    }
    recognizer = TemporalRecognizer(
        tmp_path / "run/model.onnx", tmp_path / "run/metadata.json", config, kind, vocabulary
    )
    sample = json.loads(next((tmp_path / "data" / kind).glob("*/thanks--0.json")).read_text())
    result = recognizer.recognize({"frames": sample["frames"], "timestamps": sample["timestamps"]})
    assert result["candidates"][0]["label"] == "thanks"


def test_single_person_is_flagged_as_within_subject(tmp_path):
    synthetic.write(tmp_path / "data", "lipread", people=1, repetitions=4)
    x, m, y, subjects, labels, _ = pipeline.load(tmp_path / "data", "lipread", log=None)
    evaluation = pipeline.evaluate(x, m, y, subjects, labels, epochs=5, seed=0, device=DEVICE, log=None)
    assert evaluation["method"] == "within-subject-holdout"
    assert evaluation["note"]
