"""GTを使わず既存pose幾何から自前動画の固定crop/resize/pad派生を作る。"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pickle
import re
import sys

import cv2
import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[1] / "Uni-Sign"
PROJECT_DIR = Path(__file__).resolve().parents[4]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def even_size(value):
    return max(2, int(round(value / 2)) * 2)


def transform(frame, variant, spec):
    if variant == "reencode":
        return frame
    x, _, width, _ = spec["crop_xywh"]
    cropped = frame[:, x:x + width]
    if variant == "crop":
        return cropped
    if variant == "crop_pad_resize":
        cropped = cv2.copyMakeBorder(cropped, 0, spec["pad_bottom"], spec.get("pad_left", 0),
                                     spec.get("pad_right", 0),
                                     cv2.BORDER_CONSTANT, value=(114, 114, 114))
    return cv2.resize(cropped, tuple(spec["dimensions"][variant]), interpolation=cv2.INTER_AREA)


def evaluation_inputs(path):
    """推論結果からID・状態・入力/cache情報のみを使い、英文は参照しない。"""
    evaluation = json.loads(path.read_text(encoding="utf-8"))
    sign_dir = (PROJECT_DIR / "data/sign").resolve()
    outputs = (MODEL_DIR / "outputs").resolve()
    selected = []
    seen = set()
    for row in evaluation["rows"]:
        if row["variant"] != "original" or row["status"] != "success":
            continue
        name = row["id"]
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) is None:
            raise ValueError("unsafe evaluation sample id")
        if name in seen:
            raise ValueError(f"duplicate original sample: {name}")
        seen.add(name)
        sample_dir = (sign_dir / name).resolve()
        if not sample_dir.is_dir() or sample_dir.parent != sign_dir:
            raise ValueError(f"sample must exist directly under data/sign: {name}")
        video = Path(row["input_path"]).resolve()
        cached = Path(row["pose_path"]).resolve()
        if not video.is_file() or video.parent != sample_dir:
            raise ValueError(f"original input must be inside its sample directory: {video}")
        if not cached.is_file() or cached.suffix != ".pkl" or outputs not in cached.parents:
            raise ValueError(f"pose cache must be a local outputs pickle: {cached}")
        if digest(video) != row["input_sha256"]:
            raise ValueError(f"original input SHA256 mismatch: {video}")
        if digest(cached) != row["pose_cache_sha256"]:
            raise ValueError(f"pose cache SHA256 mismatch: {cached}")
        # 自分たちが保存したローカルcacheのみ。外部のpickleは読み込まない。
        with cached.open("rb") as stream:
            pose = pickle.load(stream)
        if not pose["keypoints"] or len(pose["keypoints"]) != len(pose["scores"]):
            raise ValueError(f"empty or inconsistent pose cache: {cached}")
        keypoints, scores = [], []
        for frame_kp, frame_sc in zip(pose["keypoints"], pose["scores"]):
            frame_kp, frame_sc = np.asarray(frame_kp), np.asarray(frame_sc)
            if (frame_kp.ndim != 3 or frame_kp.shape[1:] != (133, 2)
                    or frame_kp.shape[0] < 1 or frame_sc.shape != frame_kp.shape[:2]):
                raise ValueError(f"expected normalized wholebody133 pose and scores: {cached}")
            # 上流S2T_Dataset_online.load_part_kpと同じ先頭人物を使用。
            keypoints.append(frame_kp[0])
            scores.append(frame_sc[0])
        selected.append((name, video, cached, np.stack(keypoints), np.stack(scores)))
    if not selected:
        raise ValueError("evaluation results contain no successful original rows")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--pose-dir", type=Path,
                        help="従来の01/02用pose_thread16.npzディレクトリ")
    inputs.add_argument("--evaluation-results", type=Path,
                        help="original成功行の入力SHA・pose cache SHAを含む既存results.json")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if MODEL_DIR / "outputs" not in out.parents:
        parser.error("保存先はUni-Sign/outputs以下の新規ディレクトリ")
    out.mkdir(parents=True, exist_ok=False)
    # 参照manifestに英文はあるが読み出す値はposeパスのみ、GT/予測は使用しない。
    reference = json.loads(args.reference_manifest.read_text())
    sizes = []
    for sample in reference["samples"]:
        with Path(sample["pose_path"]).open("rb") as stream:
            sizes.append(pickle.load(stream)["w_h"])
    aspect = float(np.median([w / h for w, h in sizes]))
    target_height = even_size(float(np.median([h for w, h in sizes])))
    variants = ("original", "reencode", "crop", "crop_resize", "crop_pad_resize")
    manifest = {"status": "planned", "samples": [], "reference_aspect_median": aspect,
                "reference_height_median_even": target_height, "reference_sizes": sizes,
                "reference_manifest_sha256": digest(args.reference_manifest),
                "preprocessing_policy": {"crop": "score>0.3 body/face/hands x envelope across all frames, 5% margin each side; full original height; fixed per clip",
                                         "resize": "INTER_AREA, aspect-preserving intent with nearest even width rounding",
                                         "pad": "bottom only, BGR114; match reference median aspect; no synthesized body parts",
                                         "codec": "OpenCV FFV1 AVI lossless, decoded BGR pixels verified exactly against transforms",
                                         "time": "all frames in original order, constant frame rate based on original reported average fps; no trim/duplication/speed change",
                                         "mirror": False, "label_or_prediction_selection": False},
                "script_sha256": digest(Path(__file__)), "python": sys.version, "opencv": cv2.__version__}
    if args.evaluation_results:
        sources = evaluation_inputs(args.evaluation_results)
        manifest["source_evaluation_results"] = str(args.evaluation_results.resolve())
        manifest["source_evaluation_results_sha256"] = digest(args.evaluation_results)
        manifest["pose_source"] = "existing online normalized wholebody133 pickle; first person, as upstream"
        manifest["preprocessing_policy"]["pad"] = (
            "match reference median aspect by symmetric horizontal padding for narrow crops, "
            "bottom padding for wide crops; even canvas dimensions; BGR114; no synthesized body parts")
    else:
        sources = []
        for name in ("01_whats_your_name", "02_greetings"):
            video = PROJECT_DIR / "data/sign" / name / "original.mp4"
            cached = args.pose_dir / name / "pose_thread16.npz"
            with np.load(cached) as data:
                kp, sc = data["keypoints"][:, 0], data["scores"][:, 0]
            sources.append((name, video, cached, kp, sc))
        manifest["pose_source"] = "legacy 01/02 pose_thread16.npz"
    for name, video, cached, kp, sc in sources:
        cap = cv2.VideoCapture(str(video))
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps, frames = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        if width <= 0 or height <= 0 or frames <= 0 or not np.isfinite(fps) or fps <= 0:
            raise ValueError(f"invalid original video metadata: {video}")
        if len(kp) != frames:
            raise ValueError("cached pose and original video frame count mismatch")
        indices = [0] + list(range(3, 11)) + list(range(23, 133))
        points, scores = kp[:, indices], sc[:, indices]
        valid = (scores > .3) & np.isfinite(points).all(axis=-1)
        x = points[..., 0][valid] * width
        if not len(x):
            raise ValueError(f"no finite confident body/face/hand points: {name}")
        low, high = float(x.min()), float(x.max())
        margin = .05 * (high - low)
        left = max(0, int(math.floor((low - margin) / 2)) * 2)
        right = min(width, int(math.ceil((high + margin) / 2)) * 2)
        crop_width = right - left
        if crop_width <= 0:
            raise ValueError(f"invalid crop width: {name}")
        canvas_height = max(height, int(math.ceil(crop_width / aspect / 2)) * 2)
        canvas_width = crop_width
        pad_left = pad_right = 0
        if args.evaluation_results:
            if crop_width / height < aspect:
                canvas_height = int(math.ceil(height / 2)) * 2
                canvas_width = max(crop_width, int(math.ceil(canvas_height * aspect / 2)) * 2)
            else:
                canvas_width = int(math.ceil(crop_width / 2)) * 2
                canvas_height = max(height, int(math.ceil(canvas_width / aspect / 2)) * 2)
            pad_left = (canvas_width - crop_width) // 2
            pad_right = canvas_width - crop_width - pad_left
        spec = {"id": name, "input_sha256": digest(video), "pose_path": str(cached.resolve()),
                "pose_sha256": digest(cached), "frames": frames, "fps": fps,
                "valid_point_x_range": [low, high], "horizontal_margin": margin,
                "crop_xywh": [left, 0, crop_width, height], "pad_bottom": canvas_height - height,
                "pad_left": pad_left, "pad_right": pad_right,
                "canvas_dimensions": [canvas_width, canvas_height],
                "dimensions": {"reencode": [width, height], "crop": [crop_width, height],
                               "crop_resize": [even_size(crop_width * target_height / height), target_height],
                               "crop_pad_resize": [even_size(canvas_width * target_height / canvas_height), target_height]},
                "variants": {"original": str(video.resolve())}}
        folder = out / name
        folder.mkdir()
        for variant in variants[1:]:
            spec["variants"][variant] = str(folder / (variant + ".avi"))
        manifest["samples"].append(spec)
    # 全条件を描画・推論の前に固定する。条件は予測結果で変更しない。
    (out / "planned_manifest.json").write_text(json.dumps(manifest, indent=2))
    for spec in manifest["samples"]:
        writers = {variant: cv2.VideoWriter(spec["variants"][variant], cv2.VideoWriter_fourcc(*"FFV1"),
                                           spec["fps"], tuple(spec["dimensions"][variant])) for variant in variants[1:]}
        if not all(writer.isOpened() for writer in writers.values()):
            raise RuntimeError("FFV1 writer unavailable; no dependency changes attempted")
        cap = cv2.VideoCapture(spec["variants"]["original"])
        count, previews = 0, []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            for variant, writer in writers.items():
                result = transform(frame, variant, spec)
                writer.write(result)
                if count == spec["frames"] // 2:
                    preview = np.full((390, 420, 3), 245, np.uint8)
                    scale = min(400 / result.shape[1], 350 / result.shape[0])
                    small = cv2.resize(result, (int(result.shape[1] * scale), int(result.shape[0] * scale)))
                    preview[35:35 + len(small), 10:10 + small.shape[1]] = small
                    cv2.putText(preview, variant, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1)
                    previews.append(preview)
            count += 1
        cap.release()
        for writer in writers.values():
            writer.release()
        if count != spec["frames"]:
            raise ValueError("not all input frames decoded")
        cv2.imwrite(str(out / spec["id"] / "variants_contact.jpg"), np.concatenate(previews, axis=1))
        # 再デコードして、全フレームで元画像からの予定変換とbit単位で一致することを検証。
        source = cv2.VideoCapture(spec["variants"]["original"])
        captures = {key: cv2.VideoCapture(spec["variants"][key]) for key in variants[1:]}
        spec["verification"] = {key: {"decoded_frames": 0, "max_pixel_delta": 0,
                                      "decoded_fps": cap.get(cv2.CAP_PROP_FPS)} for key, cap in captures.items()}
        for index in range(count):
            ok, frame = source.read()
            assert ok
            for variant, cap in captures.items():
                ok, decoded = cap.read()
                expected = transform(frame, variant, spec)
                if not ok or decoded.shape != expected.shape:
                    raise ValueError(f"decode/shape mismatch: {variant}, frame {index}")
                delta = int(np.abs(decoded.astype(np.int16) - expected.astype(np.int16)).max())
                spec["verification"][variant]["max_pixel_delta"] = max(delta, spec["verification"][variant]["max_pixel_delta"])
                spec["verification"][variant]["decoded_frames"] += 1
        source.release()
        for variant, cap in captures.items():
            if cap.read()[0] or spec["verification"][variant]["max_pixel_delta"] != 0:
                raise ValueError("extra frames or lossless pixel check failed")
            cap.release()
        spec["variant_sha256"] = {key: digest(Path(path)) for key, path in spec["variants"].items()}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(spec["id"], spec["crop_xywh"], spec["dimensions"], "all frames/pixels verified", flush=True)
    manifest["status"] = "complete"
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
