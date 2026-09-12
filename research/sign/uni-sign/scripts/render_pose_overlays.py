"""保存済み推論poseを対応動画へ重ねる。CPUのみ、pose再推定なし。"""
import argparse
import hashlib
import json
from pathlib import Path
import pickle
import shlex
import sys

import cv2
import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[1] / "Uni-Sign"
BODY = [0] + list(range(3, 11))
FACE = list(range(23, 40, 2)) + list(range(83, 91)) + [53]
LEFT = list(range(91, 112))
RIGHT = list(range(112, 133))
USED = BODY + FACE + LEFT + RIGHT
COLORS = {"body": (80, 230, 80), "face": (220, 110, 255),
          "left": (255, 220, 40), "right": (30, 210, 255),
          "unused": (160, 160, 160), "masked": (40, 40, 255)}
SIZE = (1536, 864)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text(frame, label, position, color=(240, 240, 240), scale=.55):
    cv2.putText(frame, label, position, cv2.FONT_HERSHEY_SIMPLEX, scale,
                (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, label, position, cv2.FONT_HERSHEY_SIMPLEX, scale,
                color, 1, cv2.LINE_AA)


def draw_pose(frame, normalized, scores):
    height, width = frame.shape[:2]
    points = normalized * np.array([width, height])
    finite = np.isfinite(points).all(axis=1) & np.isfinite(scores)
    inside = finite & (points[:, 0] >= 0) & (points[:, 0] < width) & (points[:, 1] >= 0) & (points[:, 1] < height)
    valid = inside & (scores > .3)
    radius = max(2, int(round(min(width, height) / 260)))
    thickness = max(1, radius // 2)
    output = frame.copy()

    def line(a, b, color):
        if valid[a] and valid[b]:
            cv2.line(output, tuple(np.rint(points[a]).astype(int)),
                     tuple(np.rint(points[b]).astype(int)), color, thickness, cv2.LINE_AA)

    for a, b in [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (0, 3), (0, 4)]:
        line(a, b, COLORS["body"])
    for base, color in [(91, COLORS["left"]), (112, COLORS["right"])]:
        for start in (1, 5, 9, 13, 17):
            chain = [base] + list(range(base + start, base + start + 4))
            for a, b in zip(chain, chain[1:]):
                line(a, b, color)
    for chain in [list(range(23, 40, 2)), list(range(83, 91)) + [83]]:
        for a, b in zip(chain, chain[1:]):
            line(a, b, COLORS["face"])
    for index in set(range(133)) - set(USED):
        if valid[index]:
            cv2.circle(output, tuple(np.rint(points[index]).astype(int)), max(1, radius // 2),
                       COLORS["unused"], -1, cv2.LINE_AA)
    for indices, name in [(BODY, "body"), (FACE, "face"), (LEFT, "left"), (RIGHT, "right")]:
        for index in indices:
            if not inside[index]:
                continue  # 画外点を境界へclampしない。
            point = tuple(np.rint(points[index]).astype(int))
            if valid[index]:
                cv2.circle(output, point, radius, COLORS[name], -1, cv2.LINE_AA)
            else:
                cv2.drawMarker(output, point, COLORS["masked"], cv2.MARKER_TILTED_CROSS,
                               radius * 3, thickness, cv2.LINE_AA)
    counts = {"masked_selected": int((scores[USED] <= .3).sum()),
              "outside_selected": int((finite & ~inside)[USED].sum()),
              "nonfinite_selected": int((~finite)[USED].sum())}
    return output, points, valid, counts


def fit(frame, size):
    width, height = size
    canvas = np.full((height, width, 3), 22, np.uint8)
    scale = min(width / frame.shape[1], height / frame.shape[0])
    new_width = max(1, min(width, int(round(frame.shape[1] * scale))))
    new_height = max(1, min(height, int(round(frame.shape[0] * scale))))
    resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    x, y = (width - new_width) // 2, (height - new_height) // 2
    canvas[y:y + new_height, x:x + new_width] = resized
    return canvas


def hand_panel(raw, overlay, points, valid, scores, indices, name):
    panel = np.full((384, 512, 3), 22, np.uint8)
    text(panel, name + ' hand (signer side)', (12, 24), COLORS[name])
    text(panel, 'Video', (12, 53))
    text(panel, 'Pose overlay', (268, 53))
    good = np.array(indices)[valid[indices]]
    count = int((scores[indices] <= .3).sum())
    text(panel, f'score <= 0.3: {count}/21 points', (12, 350))
    if len(good) < 3:
        text(panel, 'Too few reliable in-frame points', (12, 185))
        return panel
    low, high = points[good].min(axis=0), points[good].max(axis=0)
    center = (low + high) / 2
    side = max(float((high - low).max()) * 1.6, min(raw.shape[:2]) * .075)
    scale = 256 / side
    matrix = np.array([[scale, 0, 128 - center[0] * scale],
                       [0, scale, 128 - center[1] * scale]], dtype=np.float32)
    for x, frame in [(0, raw), (256, overlay)]:
        panel[66:322, x:x + 256] = cv2.warpAffine(frame, matrix, (256, 256), flags=cv2.INTER_LINEAR,
                                                borderMode=cv2.BORDER_CONSTANT, borderValue=(22, 22, 22))
    return panel


def render_frame(frame, keypoints, scores, row, index, total, fps):
    overlay, points, valid, counts = draw_pose(frame, keypoints, scores)
    canvas = np.full((SIZE[1], SIZE[0], 3), 22, np.uint8)
    text(canvas, f'{row["id"]} / {row["variant"]}  |  frame {index}/{total-1}  ~{index/fps:.2f}s', (16, 25), scale=.65)
    legend = [(16, 'Body', 'body'), (116, 'Face', 'face'), (218, 'Left hand', 'left'),
              (385, 'Right hand', 'right'), (570, 'Gray: unused by translator', 'unused'),
              (905, 'Red X: score <= 0.3 (masked)', 'masked')]
    for x, label, color in legend:
        text(canvas, label, (x, 53), COLORS[color], .52)
    canvas[64:832, :1024] = fit(overlay, (1024, 768))
    canvas[64:448, 1024:] = hand_panel(frame, overlay, points, valid, scores, LEFT, 'left')
    canvas[448:832, 1024:] = hand_panel(frame, overlay, points, valid, scores, RIGHT, 'right')
    text(canvas, f'Selected points: 69 | masked: {counts["masked_selected"]} | outside image: {counts["outside_selected"]} | Saved pose; no new inference',
         (16, 854), scale=.56)
    return canvas, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    args.results = args.results.resolve()
    out = args.output_dir.resolve()
    if (MODEL_DIR / 'outputs').resolve() not in out.parents:
        parser.error('保存先はUni-Sign/outputs以下の新規ディレクトリ')
    results = json.loads(args.results.read_text())
    rows = results['rows']
    if not rows or any(row['status'] != 'success' for row in rows):
        parser.error('成功した保存済み推論結果が必要です')
    for row in rows:
        if not all(value.replace('_', '').isalnum() for value in (row['id'], row['variant'])):
            parser.error('安全なid/variant名が必要です')
        if sha(row['input_path']) != row['input_sha256'] or sha(row['pose_path']) != row['pose_cache_sha256']:
            parser.error('入力動画または保存poseのSHA256が不一致です')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'command.txt').write_text(shlex.join([sys.executable, '-B', str(Path(__file__).resolve()),
                                               '--results', str(args.results), '--output-dir', str(out)]) + '\n')
    manifest = {'status': 'running', 'results_path': str(args.results), 'results_sha256': sha(args.results),
                'script_sha256': sha(__file__), 'python': sys.version, 'opencv': cv2.__version__,
                'codec': 'mp4v (MPEG-4 Part 2)', 'output_dimensions': list(SIZE),
                'coordinates': 'saved normalized xy multiplied by corresponding video W,H; before model part normalization',
                'selected_indices': USED, 'threshold': .3, 'new_pose_or_translation_inference': False,
                'time': 'all frames, input average fps, no audio; displayed time is frame index / fps',
                'notes': ['Drawn lines visualize anatomy, not the exact internal model graph.',
                          'Low-score in-frame selected points are red X; outside points counted, never clamped.',
                          'Hand zoom is an adaptive display crop only; does not change model input.',
                          'Gray dots: high-score points not selected by translator. Score is not correctness probability.'],
                'rows': []}
    for row in rows:
        folder = out / row['id'] / row['variant']
        folder.mkdir(parents=True)
        with Path(row['pose_path']).open('rb') as stream:
            pose = pickle.load(stream)
        keypoints, scores = np.asarray(pose['keypoints']), np.asarray(pose['scores'])
        count = len(scores)
        if keypoints.shape != (count, 1, 133, 2) or scores.shape != (count, 1, 133):
            raise ValueError('Expected one person and 133 points per frame')
        cap = cv2.VideoCapture(row['input_path'])
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not cap.isOpened() or fps <= 0:
            raise ValueError('Cannot read input video/FPS')
        target = folder / 'pose_overlay.mp4'
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*'mp4v'), fps, SIZE)
        if not writer.isOpened():
            raise RuntimeError('mp4v writer unavailable; no dependencies changed')
        per_frame = []
        try:
            for index in range(count):
                ok, frame = cap.read()
                if not ok:
                    raise ValueError('Video shorter than pose sequence')
                expected = row['video_metadata']
                if frame.shape[:2] != (expected['height'], expected['width']):
                    raise ValueError('Input dimensions changed')
                canvas, stats = render_frame(frame, keypoints[index, 0], scores[index, 0], row, index, count, fps)
                writer.write(canvas)
                per_frame.append(stats)
                if index == count // 2:
                    if not cv2.imwrite(str(folder / 'preview.jpg'), canvas):
                        raise RuntimeError('Preview write failed')
            if cap.read()[0]:
                raise ValueError('Video longer than pose sequence')
        finally:
            cap.release()
            writer.release()
        check = cv2.VideoCapture(str(target))
        decoded = 0
        output_fps = check.get(cv2.CAP_PROP_FPS)
        while True:
            ok, frame = check.read()
            if not ok:
                break
            if frame.shape[:2] != (SIZE[1], SIZE[0]):
                raise ValueError('Output shape mismatch')
            decoded += 1
        check.release()
        if decoded != count or abs(output_fps - fps) > .01:
            raise ValueError('Output frame count/FPS mismatch')
        artifact = {'id': row['id'], 'variant': row['variant'], 'input_path': row['input_path'],
                    'input_sha256': row['input_sha256'], 'pose_path': row['pose_path'],
                    'pose_sha256': row['pose_cache_sha256'], 'output_path': str(target),
                    'output_sha256': sha(target), 'frames': count, 'decoded_frames_verified': decoded,
                    'input_fps': fps, 'output_fps': output_fps, 'per_frame': per_frame}
        manifest['rows'].append(artifact)
        (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        print(f'{row["id"]}/{row["variant"]}: {decoded} frames verified', flush=True)
    manifest['status'] = 'complete'
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {len(rows)} videos to {out}', flush=True)


if __name__ == '__main__':
    main()
