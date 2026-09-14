"""Adapter for kai's isolated Uni-Sign command-line environment."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from app.inference.base import Recognizer


class UniSignRecognizer(Recognizer):
    language_note = (
        "ASL（米国手話）の動画を英語字幕へ変換する検証版です。"
        "日本手話には対応していません。"
    )

    def __init__(self, root: Path, config):
        self.root = root
        self.config = config
        self.runner = self._resolve(config["runner_path"])
        self.python = self._resolve(config["python_path"])
        if not self.runner.is_file():
            raise ValueError("Uni-Sign runner is missing")
        if not self.python.is_file():
            raise ValueError("Uni-Sign environment is missing")
        self.model_dir = self.runner.parent.parent / "Uni-Sign"
        self.model_version = config.get("model_version") or "uni-sign-how2sign"

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (self.root / path).resolve()

    def warmup(self):
        required = [
            self.model_dir / "weights/how2sign_pose_only_slt.pth",
            self.model_dir / "weights/mt5-base/config.json",
            self.model_dir / "weights/mt5-base/pytorch_model.bin",
            self.model_dir / "weights/mt5-base/spiece.model",
            self.model_dir / "weights/mt5-base/tokenizer_config.json",
            self.model_dir / "weights/mt5-base/special_tokens_map.json",
            self.model_dir
            / "weights/torch-cache/hub/checkpoints/yolox_tiny_8xb8-300e_humanart-6f3252f9.onnx",
            self.model_dir
            / "weights/torch-cache/hub/checkpoints/rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.onnx",
        ]
        if any(not path.is_file() for path in required):
            raise ValueError("Uni-Sign model assets are missing")
        subprocess.run(
            [
                str(self.python),
                "-c",
                "import torch; assert torch.cuda.is_available(), 'CUDA is unavailable'",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )

    def recognize(self, segment):
        video = segment.get("video")
        content_type = segment.get("content_type", "")
        if not isinstance(video, bytes) or not video:
            raise ValueError("video clip is missing")
        suffix = ".mp4" if content_type in {"video/mp4", "video/quicktime"} else ".webm"
        with tempfile.TemporaryDirectory(prefix="kotoba-uni-sign-") as temporary:
            work = Path(temporary)
            source = work / f"capture{suffix}"
            output = work / "result"
            source.write_bytes(video)
            subprocess.run(
                [
                    str(self.python),
                    "-B",
                    str(self.runner),
                    str(source),
                    "--output-dir",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            result = json.loads((output / "result.json").read_text(encoding="utf-8"))
            prediction = (result.get("prediction") or "").strip()
            return {
                "candidates": ([{"label": "uni-sign", "text": prediction}] if prediction else []),
                "model_version": self.model_version,
            }
