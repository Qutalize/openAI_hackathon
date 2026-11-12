import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.inference.auto_avsr import AutoAvsrRecognizer

SERVER = """
import json, sys
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    if MODE == "crash":
        sys.exit(1)
    if MODE == "reject":
        print(json.dumps({"error": "ValueError: no face"}), flush=True)
    else:
        print(json.dumps({"transcript": " FROM SERVER "}), flush=True)
"""


@pytest.fixture
def recognizer(tmp_path, monkeypatch):
    """An adapter whose model tree holds a stand-in resident server and one-shot runner."""
    model = tmp_path / "research/vsr/auto_avsr"
    runner = model / "scripts/run_vsr.sh"
    python = model / ".venv/bin/python"
    ffmpeg = tmp_path / "ffmpeg"
    for path in [
        runner,
        ffmpeg,
        model / "weights/vsr_trlrs2lrs3vox2avsp_base.pth",
        model / "auto_avsr/preparation/detectors/mediapipe/20words_mean_face.npy",
        model / "auto_avsr/spm/unigram/unigram5000.model",
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    python.parent.mkdir(parents=True)
    os.symlink(sys.executable, python)
    runs = []

    def run(args, **kwargs):
        runs.append(args)
        if args[0] == str(python):
            return subprocess.CompletedProcess(args, 0, stdout=str(ffmpeg) + "\n", stderr="")
        if args[0] == "bash":
            output = Path(args[-1])
            output.mkdir()
            (output / "result.json").write_text(json.dumps({"transcript": "FROM RUNNER"}))
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)

    def build(mode):
        (model / "scripts/serve.py").write_text(f"MODE = {mode!r}\n{SERVER}")
        built = AutoAvsrRecognizer(
            tmp_path / "demo", {"runner_path": "../research/vsr/auto_avsr/scripts/run_vsr.sh"}
        )
        built.warmup()
        built.runs = runs
        return built

    built = []
    yield lambda mode: built.append(build(mode)) or built[-1]
    for item in built:
        item.close()


CLIP = {"video": b"webm", "content_type": "video/webm"}


def test_resident_server_answers_without_the_one_shot_runner(recognizer):
    model = recognizer("answer")
    assert model.recognize(CLIP)["candidates"] == [{"label": "auto-avsr", "text": "FROM SERVER"}]
    assert model.recognize(CLIP)["candidates"][0]["text"] == "FROM SERVER"
    assert not any(call[0] == "bash" for call in model.runs)


def test_crashed_server_falls_back_to_the_one_shot_runner(recognizer):
    model = recognizer("crash")
    assert model.recognize(CLIP)["candidates"][0]["text"] == "FROM RUNNER"
    assert any(call[0] == "bash" for call in model.runs)


def test_clip_rejected_by_the_server_fails_without_retrying(recognizer):
    model = recognizer("reject")
    with pytest.raises(ValueError, match="no face"):
        model.recognize(CLIP)
    assert not any(call[0] == "bash" for call in model.runs)


def test_closing_stops_the_server(recognizer):
    model = recognizer("answer")
    process = model.server.process
    model.close()
    assert process.poll() is not None
