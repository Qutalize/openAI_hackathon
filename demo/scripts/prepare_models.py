"""Fetch pinned public assets, or register locally trained ONNX models."""

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEECH_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
VISION_ASSETS = {
    "face_landmarker.task": "face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "hand_landmarker.task": "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "pose_landmarker.task": "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
}


def record(manifest, path, source, revision, license_name):
    key = path.relative_to(ROOT).as_posix()
    with path.open("rb") as f:
        checksum = hashlib.file_digest(f, "sha256").hexdigest()
    entry = {
        "path": key,
        "sha256": checksum,
        "source": source,
        "revision": revision,
        "license": license_name,
    }
    manifest["assets"] = [x for x in manifest["assets"] if x["path"] != key] + [entry]


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".partial")
    request = urllib.request.Request(
        url, headers={"User-Agent": "kotoba-link-model-preparation/0.1"}
    )
    with (
        urllib.request.urlopen(request, timeout=120) as response,
        temp.open("wb") as target,
    ):
        shutil.copyfileobj(response, target, length=1024 * 1024)
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(
        description="モデルを取得・登録しSHA-256 manifestを作成"
    )
    parser.add_argument("--speech", action="store_true")
    parser.add_argument("--vision-assets", action="store_true")
    parser.add_argument("--register", choices=["lipread", "sign"])
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--verify-speech",
        action="store_true",
        help="音声モデル資産だけをmanifestのSHA-256で検証",
    )
    args = parser.parse_args()
    manifest_path = ROOT / "models/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.speech:
        for filename in (
            "model.bin",
            "config.json",
            "tokenizer.json",
            "vocabulary.txt",
            "README.md",
        ):
            url = f"https://huggingface.co/Systran/faster-whisper-small/resolve/{SPEECH_REVISION}/{filename}"
            path = ROOT / "models/speech/whisper-small" / filename
            print(f"Downloading speech/{filename}", flush=True)
            existing = next(
                (
                    x
                    for x in manifest["assets"]
                    if x["path"] == path.relative_to(ROOT).as_posix()
                ),
                None,
            )
            if not path.exists() or not existing:
                download(url, path)
            record(manifest, path, url, SPEECH_REVISION, "MIT")
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    if args.vision_assets:
        for filename, relative in VISION_ASSETS.items():
            url = "https://storage.googleapis.com/mediapipe-models/" + relative
            path = ROOT / "frontend/public/models/mediapipe" / filename
            print(f"Downloading {filename}", flush=True)
            download(url, path)
            record(manifest, path, url, "1", "See MediaPipe model distribution terms")
        wasm = ROOT / "frontend/public/models/mediapipe/wasm"
        if wasm.exists():
            for path in wasm.iterdir():
                if path.is_file():
                    record(
                        manifest,
                        path,
                        "npm:@mediapipe/tasks-vision",
                        "0.10.32",
                        "Apache-2.0",
                    )
    if args.register:
        directory = ROOT / "models" / args.register
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        if not metadata.get("evaluation_summary", {}).get("accepted"):
            parser.error("テストデータでの受入評価に合格したモデルのみ登録できます")
        for filename in ("model.onnx", "metadata.json", "labels.json"):
            record(
                manifest,
                directory / filename,
                "local-training",
                metadata["model_version"],
                metadata["license"],
            )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.verify or args.verify_speech:
        sys.path.insert(0, str(ROOT / "backend"))
        from app.inference.worker import verify_assets

        assets = manifest["assets"]
        if args.verify_speech and not args.verify:
            assets = [a for a in assets if a["path"].startswith("models/speech/")]
            if not assets:
                parser.error("manifestに音声モデル資産がありません")
        verify_assets(ROOT, [ROOT / a["path"] for a in assets])
        scope = "speech " if args.verify_speech and not args.verify else ""
        print(f"Verified {len(assets)} {scope}assets")
    if not any(vars(args).values()):
        parser.print_help()


if __name__ == "__main__":
    main()
