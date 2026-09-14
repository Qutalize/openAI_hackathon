"""Adapter for kai's isolated Auto-AVSR command-line environment."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from app.inference.base import Recognizer


class AutoAvsrRecognizer(Recognizer):
    def __init__(self, root: Path, config):
        self.root = root
        self.config = config
        self.runner = self._resolve(config["runner_path"])
        if not self.runner.is_file():
            raise ValueError("Auto-AVSR runner is missing")
        self.model_dir = self.runner.parent.parent
        self.python = self.model_dir / ".venv/bin/python"
        if not self.python.is_file():
            raise ValueError("Auto-AVSR environment is missing")
        self.model_version = config.get("model_version") or "auto-avsr"
        self.ffmpeg = self._resolve_ffmpeg()

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (self.root / path).resolve()

    def _resolve_ffmpeg(self) -> Path:
        result = subprocess.run(
            [
                str(self.python),
                "-c",
                "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        path = Path(result.stdout.strip())
        if not path.is_file():
            raise ValueError("Auto-AVSR ffmpeg is missing")
        return path

    def warmup(self):
        # The upstream CLI loads the GPU model per request. Startup only verifies
        # isolated runtime assets so the app can still report an honest capability.
        required = [
            self.model_dir / "weights/vsr_trlrs2lrs3vox2avsp_base.pth",
            self.model_dir / "auto_avsr/preparation/detectors/mediapipe/20words_mean_face.npy",
            self.model_dir / "auto_avsr/spm/unigram/unigram5000.model",
        ]
        if any(not path.is_file() for path in required):
            raise ValueError("Auto-AVSR model assets are missing")
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
        with tempfile.TemporaryDirectory(prefix="kotoba-auto-avsr-") as temporary:
            work = Path(temporary)
            source = work / f"capture{suffix}"
            prepared = work / "video-25fps.mp4"
            output = work / "result"
            source.write_bytes(video)
            subprocess.run(
                [
                    str(self.ffmpeg),
                    "-nostdin",
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-vf",
                    "fps=25",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "18",
                    "-preset",
                    "fast",
                    str(prepared),
                ],
                check=True,
                capture_output=True,
                timeout=45,
            )
            subprocess.run(
                ["bash", str(self.runner), str(prepared), str(output)],
                check=True,
                capture_output=True,
                timeout=180,
            )
            result = json.loads((output / "result.json").read_text(encoding="utf-8"))
            transcript = result.get("transcript", "").strip()
            return {
                "candidates": ([{"label": "auto-avsr", "text": transcript}] if transcript else []),
                "model_version": self.model_version,
            }
