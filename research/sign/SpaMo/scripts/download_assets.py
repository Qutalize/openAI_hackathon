"""公式の固定revisionから視覚重みとT5の設定・tokenizerを取得する。"""
import hashlib
import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest_path = ROOT / "weights" / "assets.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    revisions_path = ROOT / "model-revisions.json"
    revisions = json.loads(revisions_path.read_text()) if revisions_path.exists() else {}
    models = [
        ("clip", "openai/clip-vit-large-patch14", ["*.json", "pytorch_model.bin"]),
        ("videomae", "MCG-NJU/videomae-large", ["*.json", "pytorch_model.bin"]),
        # spamo.ckptに完全なT5重みがあることを検査してから使用する。
        ("t5", "google/flan-t5-xl", ["*.json", "spiece.model"]),
    ]
    for key, repo, patterns in models:
        revision = (manifest.get(key, {}).get("revision")
                    or revisions.get(key, {}).get("revision")
                    or HfApi().model_info(repo).sha)
        print(f"Downloading {repo}@{revision}", flush=True)
        folder = ROOT / "weights" / key
        snapshot_download(repo, revision=revision, local_dir=folder,
                          allow_patterns=patterns, max_workers=2)
        files = {str(p.relative_to(folder)): sha256(p) for p in sorted(folder.rglob("*"))
                 if p.is_file() and ".cache" not in p.parts}
        manifest[key] = {"repo_id": repo, "revision": revision, "sha256": files}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
