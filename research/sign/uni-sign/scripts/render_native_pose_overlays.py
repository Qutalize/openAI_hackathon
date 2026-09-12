"""入力動画の画角・解像度で保存poseを重ねる。拡大欄なし、再推定なし。"""
import argparse
import json
from pathlib import Path
import pickle
import shlex
import sys

import cv2
import numpy as np

import render_pose_overlays as drawing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--all-variants', action='store_true', help='前処理済み条件も各入力寸法で描画')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if (drawing.MODEL_DIR / 'outputs').resolve() not in out.parents:
        parser.error('出力はUni-Sign/outputs以下の新規ディレクトリ')
    results = json.loads(args.results.read_text())
    rows = [row for row in results['rows'] if args.all_variants or row['variant'] == 'original']
    if not rows or len({(row['id'], row['variant']) for row in rows}) != len(rows):
        parser.error('重複のない入力条件が必要です')
    for row in rows:
        if row['status'] != 'success' or not all(row[key].replace('_', '').isalnum() for key in ('id', 'variant')):
            parser.error('成功した安全なsample IDの結果が必要です')
        if drawing.sha(row['input_path']) != row['input_sha256']:
            parser.error('原動画のSHA256が推論時と不一致')
        if drawing.sha(row['pose_path']) != row['pose_cache_sha256']:
            parser.error('保存poseのSHA256が推論時と不一致')
    out.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--results',
               str(args.results.resolve()), '--output-dir', str(out)]
    if args.all_variants:
        command.append('--all-variants')
    (out / 'command.txt').write_text(shlex.join(command) + '\n')
    manifest = {'status': 'running', 'results_path': str(args.results.resolve()),
                'results_sha256': drawing.sha(args.results), 'script_sha256': drawing.sha(__file__),
                'drawing_script_sha256': drawing.sha(drawing.__file__), 'opencv': cv2.__version__,
                'python': sys.version, 'codec': 'mp4v', 'audio': False,
                'new_inference': False, 'resize_crop_mirror': False, 'all_variants': args.all_variants,
                'notes': ['Saved predicted pose, not ground truth.',
                          'Same decoded width/height/frame order and average FPS as each input variant.',
                          'Uses the same colors and selected-point mask threshold as render_pose_overlays.py.',
                          'No zoom panels. Drawn anatomical lines are not the exact model graph.'],
                'rows': []}
    for row in rows:
        folder = out / row['id']
        if args.all_variants:
            folder = folder / row['variant']
        folder.mkdir(parents=True)
        with Path(row['pose_path']).open('rb') as stream:
            pose = pickle.load(stream)
        points, scores = np.asarray(pose['keypoints']), np.asarray(pose['scores'])
        frames = len(scores)
        if points.shape != (frames, 1, 133, 2) or scores.shape != (frames, 1, 133):
            raise ValueError('Expected one person, 133 points')
        cap = cv2.VideoCapture(row['input_path'])
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not cap.isOpened() or fps <= 0 or width % 2 or height % 2:
            raise ValueError('Cannot encode original dimensions/FPS')
        target = folder / ('pose_overlay.mp4' if args.all_variants else 'original_pose_overlay.mp4')
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError('mp4v unavailable')
        counts = []
        try:
            for index in range(frames):
                ok, frame = cap.read()
                if not ok or frame.shape[:2] != (height, width):
                    raise ValueError('Input frame mismatch')
                overlay, _, _, stats = drawing.draw_pose(frame, points[index, 0], scores[index, 0])
                label = (f'{row["id"].split("_")[0]} {row["variant"]} f{index}/{frames-1}' if args.all_variants
                         else f'{row["id"]} | frame {index}/{frames-1}')
                drawing.text(overlay, label, (8, 20), scale=.38 if args.all_variants else .5)
                writer.write(overlay)
                counts.append(stats)
                if index == frames // 2:
                    if not cv2.imwrite(str(folder / 'preview.jpg'), overlay):
                        raise RuntimeError('Preview write failed')
            if cap.read()[0]:
                raise ValueError('Input has extra frames')
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
            if frame.shape[:2] != (height, width):
                raise ValueError('Output dimensions changed')
            decoded += 1
        check.release()
        if decoded != frames or abs(output_fps - fps) > .01:
            raise ValueError('Output frame count/FPS mismatch')
        manifest['rows'].append({'id': row['id'], 'variant': row['variant'], 'input_path': row['input_path'],
                                 'input_sha256': row['input_sha256'], 'pose_path': row['pose_path'],
                                 'pose_sha256': row['pose_cache_sha256'], 'output_path': str(target),
                                 'output_sha256': drawing.sha(target), 'width': width, 'height': height,
                                 'frames': frames, 'verified_decoded_frames': decoded,
                                 'input_fps': fps, 'output_fps': output_fps, 'per_frame': counts})
        (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print(f'{row["id"]}: {width}x{height}, {decoded} frames verified', flush=True)
    manifest['status'] = 'complete'
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
