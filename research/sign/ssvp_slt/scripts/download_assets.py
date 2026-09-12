#!/usr/bin/env python3
"""公式 SONAR ASL デモの重み・設定・サンプルをローカルへ取得する。"""
import bz2
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
T5_REVISION = "a98b0fcd0b8137ded40cdf0c0cf0ee884e7c9726"
ASSETS = {
    "weights/dm_70h_ub_signhiera.pth": "https://dl.fbaipublicfiles.com/SONAR/asl/dm_70h_ub_signhiera.pth",
    "weights/dm_70h_ub_sonar_encoder.pth": "https://dl.fbaipublicfiles.com/SONAR/asl/dm_70h_ub_sonar_encoder.pth",
    "weights/mmod_human_face_detector.dat.bz2": "https://raw.githubusercontent.com/davisking/dlib-models/master/mmod_human_face_detector.dat.bz2",
    "weights/t5-v1_1-large/config.json": f"https://huggingface.co/google/t5-v1_1-large/resolve/{T5_REVISION}/config.json",
    "outputs/public-sample/0043626-2023.1.4.mp4": "https://dl.fbaipublicfiles.com/SONAR/asl/0043626-2023.1.4.mp4",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    records = []
    for relative, url in ASSETS.items():
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            partial = destination.with_name(destination.name + ".partial")
            print(f"Downloading {url}", flush=True)
            urllib.request.urlretrieve(url, partial)
            partial.replace(destination)
        records.append({"path": relative, "url": url, "sha256": sha256(destination), "bytes": destination.stat().st_size})
    detector = ROOT / "weights/mmod_human_face_detector.dat"
    if not detector.exists():
        detector.write_bytes(bz2.decompress(detector.with_suffix(".dat.bz2").read_bytes()))
    records.append({"path": str(detector.relative_to(ROOT)), "sha256": sha256(detector), "bytes": detector.stat().st_size})
    for filename in ("sonar_text_decoder.pt", "sentencepiece.source.256000.model"):
        for path in (ROOT / "weights/cache/fairseq2/assets").glob(f"*/{filename}"):
            records.append({"path": str(path.relative_to(ROOT)), "url": f"https://dl.fbaipublicfiles.com/SONAR/{filename}", "sha256": sha256(path), "bytes": path.stat().st_size})
    (ROOT / "weights/assets.json").write_text(json.dumps({"t5_revision": T5_REVISION, "assets": records}, indent=2) + "\n")
    print("取得済みファイルを含めSHA256をweights/assets.jsonへ記録しました。")
    print("SONAR decoder/tokenizer は公式推論の初回実行時に追加取得されます。")


if __name__ == "__main__":
    main()
