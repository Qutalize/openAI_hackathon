import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from train_temporal import TemporalClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.inference.preprocessing import FACE_INDICES, LIP_INDICES, PREPROCESSING_VERSION


def main():
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument("output_directory")
    p.add_argument("--version", required=True)
    p.add_argument("--license", required=True)
    args = p.parse_args()
    c = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = TemporalClassifier(c["points"], len(c["labels"]))
    model.load_state_dict(c["state_dict"])
    model.eval()
    directory = Path(args.output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    features = torch.randn(1, c["max_frames"], c["points"], 4)
    mask = torch.ones(1, c["max_frames"])
    torch.onnx.export(
        model,
        (features, mask),
        str(directory / "model.onnx"),
        input_names=["features", "frame_mask"],
        output_names=["logits"],
        opset_version=17,
        dynamo=False,
    )
    session = ort.InferenceSession(
        str(directory / "model.onnx"), providers=["CPUExecutionProvider"]
    )
    with torch.no_grad():
        expected = model(features, mask).numpy()
    actual = session.run(
        None, {"features": features.numpy(), "frame_mask": mask.numpy()}
    )[0]
    np.testing.assert_allclose(expected, actual, atol=1e-5, rtol=1e-4)
    kind = c["modality"]
    metadata = {
        "model_version": args.version,
        "modality": kind,
        "language": "ja",
        "vocabulary_version": c["vocabulary_version"],
        "feature_schema": "lip40_v1" if kind == "lipread" else "sign100_v1",
        "landmark_indices": LIP_INDICES if kind == "lipread" else FACE_INDICES,
        "preprocessing_version": PREPROCESSING_VERSION,
        "sample_fps": 20,
        "max_frames": c["max_frames"],
        "input_names": ["features", "frame_mask"],
        "input_shapes": [list(features.shape), list(mask.shape)],
        "output_names": ["logits"],
        "labels": c["labels"],
        "thresholds": {"candidate": 0.8 if kind == "lipread" else 0.85},
        "required_points": "lip-valid-80pct"
        if kind == "lipread"
        else "one-hand-70pct-and-both-shoulders",
        "training_data_summary": c["training_data_summary"],
        "evaluation_summary": {"accepted": False},
        "license": args.license,
    }
    (directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (directory / "labels.json").write_text(
        json.dumps(c["labels"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("ONNX parity passed. Run evaluate.py before registering this model.")


if __name__ == "__main__":
    main()
