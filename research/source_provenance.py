"""入れ子のGitに依存せず、取り込んだ上流の出典と当時の差分を読む。"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT_ROOT / "research/upstream-sources.json"


def upstream_source(source_dir):
    """元revisionを返す。現在のルートGitのrevisionとは区別する。"""
    key = Path(source_dir).resolve().relative_to(PROJECT_ROOT).as_posix()
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"][key]


def upstream_revision(source_dir):
    return upstream_source(source_dir)["revision"]


def upstream_patch_at_import(source_dir):
    """取り込み時点の保存差分。実行時点の未コミット差分ではない。"""
    patch = upstream_source(source_dir)["local_patch_at_import"]
    if patch is None:
        return ""
    return (PROJECT_ROOT / patch).read_text(encoding="utf-8")
