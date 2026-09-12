"""全フレームで完全に黒い左右列だけを除去する診断用動画変換。"""
import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from run_online import MODEL_DIR, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--sample-ids', required=True, nargs='+')
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if (MODEL_DIR / 'outputs').resolve() not in out.parents:
        parser.error('出力はUni-Sign/outputs以下の新規ディレクトリ')
    inputs = json.loads(args.manifest.read_text())
    selected = [s for s in inputs['samples'] if s['id'] in args.sample_ids]
    if len(selected) != len(set(args.sample_ids)):
        parser.error('指定sampleがmanifestにありません')
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'planned', 'input_manifest_sha256': sha256(args.manifest),
                'script_sha256': sha256(Path(__file__)), 'python': sys.version, 'opencv': cv2.__version__,
                'policy': 'Remove only outer columns that are exactly zero in every decoded frame; even crop bounds; no resize/rotate/trim; FFV1 lossless',
                'gt_or_prediction_used': False, 'samples': []}
    for sample in selected:
        video = Path(sample['variants']['original'])
        if sha256(video) != sample['variant_sha256']['original']:
            raise ValueError('Original SHA256 mismatch')
        if not sample['id'].replace('_', '').isalnum():
            raise ValueError('Unsafe sample id')
        cap = cv2.VideoCapture(str(video))
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        column_max = np.zeros(width, dtype=np.uint8)
        frames = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            column_max = np.maximum(column_max, frame.max(axis=(0, 2)))
            frames += 1
        cap.release()
        nonzero = np.flatnonzero(column_max)
        if not frames or not len(nonzero):
            raise ValueError('Empty or entirely black input')
        left, right = int(nonzero[0]) // 2 * 2, min(width, (int(nonzero[-1]) + 2) // 2 * 2)
        if left == 0 and right == width:
            raise ValueError('No removable black columns')
        folder = out / sample['id']
        folder.mkdir()
        manifest['samples'].append({'id': sample['id'], 'frames': frames, 'fps': fps,
                                    'crop_xywh': [left, 0, right-left, height],
                                    'removed_columns_max_pixel_value': 0,
                                    'variants': {'original': str(video), 'remove_bars': str(folder / 'remove_bars.avi')},
                                    'variant_sha256': {'original': sha256(video)}})
    (out / 'planned_manifest.json').write_text(json.dumps(manifest, indent=2))
    for sample in manifest['samples']:
        x, _, width, height = sample['crop_xywh']
        source = cv2.VideoCapture(sample['variants']['original'])
        target = Path(sample['variants']['remove_bars'])
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*'FFV1'), sample['fps'], (width, height))
        if not writer.isOpened():
            raise RuntimeError('FFV1 unavailable')
        for _ in range(sample['frames']):
            ok, frame = source.read()
            if not ok:
                raise ValueError('Input frame missing')
            writer.write(frame[:, x:x+width])
        source.release()
        writer.release()
        source = cv2.VideoCapture(sample['variants']['original'])
        check = cv2.VideoCapture(str(target))
        for _ in range(sample['frames']):
            a, frame = source.read()
            b, cropped = check.read()
            if not a or not b or not np.array_equal(frame[:, x:x+width], cropped):
                raise ValueError('Lossless frame verification failed')
        if source.read()[0] or check.read()[0]:
            raise ValueError('Extra frames')
        source.release()
        check.release()
        sample['variant_sha256']['remove_bars'] = sha256(target)
        sample['verification'] = {'frames': sample['frames'], 'max_pixel_delta': 0}
        print(sample['id'], sample['crop_xywh'], 'all frames/pixels verified', flush=True)
    manifest['status'] = 'complete'
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
