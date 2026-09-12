#!/usr/bin/env python3
"""上流SONAR推論でASL動画1本を英文に変換し、未補正出力と再現情報を保存する。"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision, upstream_source
import time
from datetime import datetime, timezone
from uuid import uuid4


MODEL_ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def override(key, value):
    # Hydraのoverride文法でも空白・カンマ等をパスの一部として扱う。
    return key + "=" + json.dumps(str(value), ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="ASL映像の入力動画（正解文は読み込まない）")
    parser.add_argument("--output", type=Path, help="新規出力ディレクトリ。既存の場所は拒否")
    arguments = parser.parse_args()
    video = arguments.video.expanduser().resolve()
    if not video.is_file():
        parser.error(f"入力動画が見つかりません: {video}")
    upstream = MODEL_ROOT / "upstream"
    weights = MODEL_ROOT / "weights"
    assets = {
        "signhiera": weights / "dm_70h_ub_signhiera.pth",
        "sonar_asl_encoder": weights / "dm_70h_ub_sonar_encoder.pth",
        "dlib_face_detector": weights / "mmod_human_face_detector.dat",
        "t5_config": weights / "t5-v1_1-large/config.json",
    }
    for path in [upstream / "examples/sonar/run.py", *assets.values()]:
        if not path.is_file():
            parser.error(f"必要なファイルが見つかりません: {path}")
    default_name = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    output = (arguments.output or MODEL_ROOT / "outputs" / default_name).expanduser().resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f"既存の出力ディレクトリは使用できません: {output}")

    child_environment = os.environ.copy()
    # venv を使うため、親の Conda 設定による fairseq2n の探索先制限を解除。
    child_environment.pop("CONDA_PREFIX", None)
    settings = {
        "PYTHONPATH": str(upstream / "src"),
        "TORCH_HOME": str(weights / "torch-cache"),
        "HF_HOME": str(weights / "hf-cache"),
        "XDG_CACHE_HOME": str(weights / "cache"),
        "PYTHONUNBUFFERED": "1",
        "HYDRA_FULL_ERROR": "1",
    }
    child_environment.update(settings)
    command = [
        sys.executable, "-u", str(upstream / "examples/sonar/run.py"),
        override("video_path", video),
        override("preprocessing.detector_path", assets["dlib_face_detector"]),
        override("feature_extraction.pretrained_model_path", assets["signhiera"]),
        override("translation.pretrained_model_path", assets["sonar_asl_encoder"]),
        override("translation.base_model_name", assets["t5_config"].parent),
        "translation.tgt_langs=[eng_Latn]",
        "verbose=true", "preprocessing.verbose=true",
        "feature_extraction.verbose=true", "translation.verbose=true",
        override("hydra.run.dir", output / "hydra"), "hydra.output_subdir=.hydra",
    ]
    command_text = "cd " + shlex.quote(str(upstream / "examples/sonar")) + "\n"
    command_text += shlex.join(["env", "-u", "CONDA_PREFIX", *(f"{key}={value}" for key, value in settings.items()), *command])
    (output / "command.txt").write_text(command_text + "\n", encoding="utf-8")
    (output / "inference.log").touch()
    started = time.perf_counter()
    result = {
        "status": "preparing",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_language": "ASL（米国手話）",
        "output_language": "English", "target_language_code": "eng_Latn",
        "prediction": None, "output_kind": "モデルが生成した未補正の英文",
        "postprocessing": "上流stdoutの表示ラベルと外側の引用符のみ除去。文章補正なし",
        "confidence": None, "confidence_scale": "上流の推論経路は信頼度を返さない",
        "semantic_correctness": "未確認", "training_performed": False,
        "command": command, "child_environment_overrides": settings,
        "child_environment_removed": ["CONDA_PREFIX"],
        "subprocess_wall_seconds": None, "subprocess_returncode": None,
        "upstream_reported_seconds": {},
        "timing_note": "subprocess全体はimport・モデル読込・初回ダウンロード・推論を含む。上流内訳はログ記載値で、CUDA同期を追加していない。",
    }
    environment = {
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "packages": sorted(
            f"{package.metadata['Name']}=={package.version}"
            for package in importlib.metadata.distributions() if package.metadata.get("Name")
        ),
        "child_environment_overrides": settings,
    }
    try:
        import torch
        import dlib

        environment.update({
            "torch_version": torch.__version__, "torch_cuda_version": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "dlib_version": getattr(dlib, "__version__", None),
            "dlib_use_cuda": bool(dlib.DLIB_USE_CUDA),
            "dlib_cuda_devices": dlib.cuda.get_num_devices(),
        })
        if not torch.cuda.is_available():
            raise RuntimeError("CUDAが利用できません。CPU推論への自動切替は行いません。")
        torch.cuda.init()
        device_index = torch.cuda.current_device()
        properties = torch.cuda.get_device_properties(device_index)
        environment["gpu"] = {
            "device_index": device_index, "name": properties.name,
            "total_memory_bytes": properties.total_memory,
        }
        result["model_device"] = "cuda"
        result["face_detection_device"] = "cuda" if dlib.DLIB_USE_CUDA else "cpu"
        result["input"] = file_record(video)
        result["weights"] = {name: file_record(path) for name, path in assets.items()}
        result["upstream_revision"] = upstream_revision(upstream)
        result["upstream_source_at_import"] = upstream_source(upstream)
        result["wrapper"] = file_record(Path(__file__).resolve())
        write_json(output / "environment.txt", environment)
        result["status"] = "running"
        write_json(output / "result.json", result)
        print(f"出力先: {output}", flush=True)
        process_started = time.perf_counter()
        with (output / "inference.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command, cwd=upstream / "examples/sonar", env=child_environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            try:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    print(line, end="", flush=True)
                result["subprocess_returncode"] = process.wait()
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                result["subprocess_returncode"] = process.returncode
                raise
            finally:
                process.stdout.close()
                result["subprocess_wall_seconds"] = time.perf_counter() - process_started
        log_text = (output / "inference.log").read_text(encoding="utf-8")
        result["upstream_reported_seconds"] = {
            match.group(1).strip(): float(match.group(2))
            for match in re.finditer(r"(?m)^\s*(?:- )?([A-Za-z][A-Za-z ]+): ([0-9.]+)\s*s\s*$", log_text)
        }
        if result["subprocess_returncode"] != 0:
            raise RuntimeError(f"上流推論が終了コード {result['subprocess_returncode']} で失敗しました。inference.logを確認してください。")
        matches = re.findall(
            r'Translations:\s*\n-{50}\s*\neng_Latn: "(.*?)"\r?\n-{50}', log_text, re.DOTALL
        )
        if len(matches) != 1 or not matches[0].strip():
            raise RuntimeError("上流stdoutから英文を一意に抽出できませんでした。inference.logを確認してください。")
        result["prediction"] = matches[0]
        (output / "prediction.txt").write_text(matches[0] + "\n", encoding="utf-8")
        result["status"] = "success"
    except (Exception, KeyboardInterrupt) as error:
        result["status"] = "failed"
        result["error"] = f"{type(error).__name__}: {error}"
        print(result["error"], file=sys.stderr)
    finally:
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        result["wrapper_wall_seconds"] = time.perf_counter() - started
        write_json(output / "environment.txt", environment)
        write_json(output / "result.json", result)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
