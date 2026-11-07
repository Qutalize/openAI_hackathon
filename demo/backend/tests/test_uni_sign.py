import json
import subprocess
from pathlib import Path

from app.inference.uni_sign import UniSignRecognizer


def test_uni_sign_adapter_accepts_webm_and_returns_candidate(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    model = tmp_path / "research/sign/uni-sign"
    runner = model / "scripts/run_online.py"
    python = tmp_path / "env/bin/python"
    required = [
        model / "Uni-Sign/weights/how2sign_pose_only_slt.pth",
        model / "Uni-Sign/weights/mt5-base/config.json",
        model / "Uni-Sign/weights/mt5-base/pytorch_model.bin",
        model / "Uni-Sign/weights/mt5-base/spiece.model",
        model / "Uni-Sign/weights/mt5-base/tokenizer_config.json",
        model / "Uni-Sign/weights/mt5-base/special_tokens_map.json",
        model
        / "Uni-Sign/weights/torch-cache/hub/checkpoints/"
        "yolox_tiny_8xb8-300e_humanart-6f3252f9.onnx",
        model
        / "Uni-Sign/weights/torch-cache/hub/checkpoints/"
        "rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.onnx",
    ]
    for path in [runner, python, *required]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if "--output-dir" in args:
            output = Path(args[args.index("--output-dir") + 1])
            output.mkdir()
            (output / "result.json").write_text(
                json.dumps({"prediction": "WHAT IS YOUR NAME"}), encoding="utf-8"
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    recognizer = UniSignRecognizer(
        root,
        {
            "runner_path": "../research/sign/uni-sign/scripts/run_online.py",
            "python_path": str(python),
            "model_version": "test-uni-sign",
        },
    )
    recognizer.warmup()
    result = recognizer.recognize({"video": b"webm", "content_type": "video/webm"})

    assert result == {
        "candidates": [{"label": "uni-sign", "text": "WHAT IS YOUR NAME"}],
        "model_version": "test-uni-sign",
    }
    assert any(call[0] == str(python) and "torch.cuda.is_available" in call[-1] for call in calls)
    inference = next(call for call in calls if "--output-dir" in call)
    assert inference[0:3] == [str(python), "-B", str(runner)]
    assert inference[3].endswith(".webm")


def test_relative_python_path_keeps_venv_symlinks(tmp_path):
    root = tmp_path / "demo"
    model = tmp_path / "research/sign/uni-sign"
    runner = model / "scripts/run_online.py"
    base_python = tmp_path / "uv/python3.9"
    venv = tmp_path / "envs/uni-sign"
    for path in (runner, base_python):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    # Like uv and venv: .venv links to the environment, whose bin/python links to the base interpreter.
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").symlink_to(base_python)
    (model / ".venv").symlink_to(venv)

    recognizer = UniSignRecognizer(
        root,
        {
            "runner_path": "../research/sign/uni-sign/scripts/run_online.py",
            "python_path": "../research/sign/uni-sign/.venv/bin/python",
        },
    )

    assert recognizer.python == model / ".venv/bin/python"
    assert recognizer.runner == runner
