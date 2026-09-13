"""The exact temporal packing used by training and serving."""

import numpy as np

LIP_INDICES = [
    61,
    146,
    91,
    181,
    84,
    17,
    314,
    405,
    321,
    375,
    291,
    308,
    324,
    318,
    402,
    317,
    14,
    87,
    178,
    88,
    95,
    78,
    191,
    80,
    81,
    82,
    13,
    312,
    311,
    310,
    415,
    409,
    270,
    269,
    267,
    0,
    37,
    39,
    40,
    185,
]
FACE_INDICES = [
    1,
    4,
    33,
    133,
    263,
    362,
    61,
    291,
    13,
    14,
    17,
    0,
    70,
    63,
    105,
    66,
    107,
    336,
    296,
    334,
    293,
    300,
    152,
    234,
    454,
]
PREPROCESSING_VERSION = "landmarks-v1"


def pack_frames(frames, timestamps, max_frames: int, kind: str):
    points = 40 if kind == "lipread" else 100
    source = np.asarray(frames, dtype=np.float32)
    times = np.asarray(timestamps, dtype=np.float64)
    if source.shape != (len(times), points, 4) or len(times) < 2:
        raise ValueError("撮影区間が短すぎます")
    if not np.isfinite(source).all() or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("特徴点または時刻が不正です")
    times = times - times[0]
    if times[-1] > max_frames * 50 + 100:
        raise ValueError("撮影時間の上限を超えました")
    data = np.zeros((1, max_frames, points, 4), dtype=np.float32)
    mask = np.zeros((1, max_frames), dtype=np.float32)
    count = min(max_frames, int(times[-1] // 50) + 1)
    for n in range(count):
        t = n * 50
        hi = int(np.searchsorted(times, t))
        if hi < len(times) and abs(times[hi] - t) < 0.001:
            frame = source[hi].copy()
        elif hi == 0 or hi == len(times) or times[hi] - times[hi - 1] > 100:
            continue
        else:
            lo = hi - 1
            alpha = (t - times[lo]) / (times[hi] - times[lo])
            frame = source[lo] * (1 - alpha) + source[hi] * alpha
            frame[:, 3] = (source[lo, :, 3] > 0.5) & (source[hi, :, 3] > 0.5)
        frame[frame[:, 3] < 0.5] = 0
        valid = frame[:, 3] > 0.5
        good = (
            valid.mean() >= 0.8
            if kind == "lipread"
            else ((valid[:21].mean() >= 0.7 or valid[21:42].mean() >= 0.7) and valid[53] and valid[54])
        )
        if good:
            data[0, n] = frame
            mask[0, n] = 1
    return data, mask, float(mask.sum() / max(count, 1))
