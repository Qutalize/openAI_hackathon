import json

import numpy as np

from app.inference.base import Recognizer
from app.inference.preprocessing import FACE_INDICES, LIP_INDICES, PREPROCESSING_VERSION, pack_frames


class TemporalRecognizer(Recognizer):
    def __init__(self, path, metadata_path, config, kind, vocabulary):
        import onnxruntime as ort

        self.kind, self.config = kind, config
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        m = self.metadata
        required = {
            "model_version",
            "modality",
            "language",
            "vocabulary_version",
            "feature_schema",
            "landmark_indices",
            "preprocessing_version",
            "sample_fps",
            "max_frames",
            "input_names",
            "input_shapes",
            "output_names",
            "labels",
            "thresholds",
            "training_data_summary",
            "evaluation_summary",
            "license",
        }
        if not required <= m.keys():
            raise ValueError("metadata fields missing")
        if not m["evaluation_summary"].get("accepted"):
            raise ValueError("model has not passed held-out evaluation")
        expected_indices = LIP_INDICES if kind == "lipread" else FACE_INDICES
        if (
            m["modality"] != kind
            or m["language"] != "ja"
            or m["landmark_indices"] != expected_indices
            or m["preprocessing_version"] != PREPROCESSING_VERSION
            or m["sample_fps"] != 20
            or m["feature_schema"] != config["feature_schema"]
            or m["max_frames"] != config["max_frames"]
            or m["vocabulary_version"] != vocabulary["version"]
        ):
            raise ValueError("metadata and preprocessing mismatch")
        self.labels = json.loads((metadata_path.parent / "labels.json").read_text(encoding="utf-8"))
        if (
            self.labels != m["labels"]
            or "unknown" not in self.labels
            or len(set(self.labels)) != len(self.labels)
        ):
            raise ValueError("invalid labels")
        self.texts = {x["id"]: x["text"] for x in vocabulary["items"] if kind in x["modalities"]}
        if set(self.labels) - {"unknown"} - self.texts.keys():
            raise ValueError("unknown vocabulary labels")
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        k = 40 if kind == "lipread" else 100
        expected_shapes = [[1, config["max_frames"], k, 4], [1, config["max_frames"]]]
        if (
            [i.name for i in self.session.get_inputs()] != ["features", "frame_mask"]
            or [i.shape for i in self.session.get_inputs()] != expected_shapes
            or [o.name for o in self.session.get_outputs()] != ["logits"]
            or self.session.get_outputs()[0].shape != [1, len(self.labels)]
        ):
            raise ValueError("ONNX input/output contract mismatch")

    def warmup(self):
        k = 40 if self.kind == "lipread" else 100
        self.session.run(
            None,
            {
                "features": np.zeros((1, self.config["max_frames"], k, 4), np.float32),
                "frame_mask": np.ones((1, self.config["max_frames"]), np.float32),
            },
        )

    def recognize(self, segment):
        features, mask, ratio = pack_frames(
            segment["frames"], segment["timestamps"], self.config["max_frames"], self.kind
        )
        result = {"candidates": [], "model_version": self.metadata["model_version"]}
        if ratio < self.config["min_valid_frame_ratio"]:
            return result
        logits = self.session.run(None, {"features": features, "frame_mask": mask})[0][0]
        if not np.isfinite(logits).all():
            raise ValueError("nonfinite model output")
        scores = np.exp(logits - logits.max())
        scores /= scores.sum()
        order = np.argsort(scores)[::-1]
        threshold = max(self.config["candidate_threshold"], self.metadata["thresholds"]["candidate"])
        if self.labels[order[0]] == "unknown" or float(scores[order[0]]) < threshold:
            return result
        for i in order[: self.config["top_k"]]:
            label = self.labels[i]
            if label != "unknown":
                result["candidates"].append({"label": label, "text": self.texts[label]})
        return result
