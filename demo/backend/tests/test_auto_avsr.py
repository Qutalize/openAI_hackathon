import json
import subprocess
from pathlib import Path

from app.inference.auto_avsr import AutoAvsrRecognizer


def test_auto_avsr_adapter_prepares_video_and_returns_candidate(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    model = tmp_path / "research/vsr/auto_avsr"
    runner = model / "scripts/run_vsr.sh"
    python = model / ".venv/bin/python"
    ffmpeg = tmp_path / "ffmpeg"
    required = [
        model / "weights/vsr_trlrs2lrs3vox2avsp_base.pth",
        model / "auto_avsr/preparation/detectors/mediapipe/20words_mean_face.npy",
        model / "auto_avsr/spm/unigram/unigram5000.model",
    ]
    for path in [runner, python, ffmpeg, *required]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == str(python):
            return subprocess.CompletedProcess(args, 0, stdout=str(ffmpeg) + "\n", stderr="")
        if args[0] == "bash":
            output = Path(args[-1])
            output.mkdir()
            (output / "result.json").write_text(json.dumps({"transcript": "HELLO WORLD"}))
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)
    recognizer = AutoAvsrRecognizer(
        root,
        {
            "runner_path": "../research/vsr/auto_avsr/scripts/run_vsr.sh",
            "model_version": "test-auto-avsr",
        },
    )
    recognizer.warmup()
    result = recognizer.recognize({"video": b"webm", "content_type": "video/webm"})

    assert result == {
        "candidates": [{"label": "auto-avsr", "text": "HELLO WORLD"}],
        "model_version": "test-auto-avsr",
    }
    assert any("fps=25" in call for call in calls)
    assert any(call[0] == str(python) and "torch.cuda.is_available" in call[-1] for call in calls)
    assert any(call[0] == "bash" and call[1] == str(runner) for call in calls)
