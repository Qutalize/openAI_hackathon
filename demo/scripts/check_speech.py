"""Exercise PCM conversion, per-speaker VAD, and the real spawned ASR worker."""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import load_settings  # noqa: E402
from app.inference.speech import SpeechSegmenter  # noqa: E402
from app.inference.worker import InferenceService  # noqa: E402


async def main():
    from faster_whisper.audio import decode_audio

    parser = argparse.ArgumentParser()
    parser.add_argument("audio_file")
    args = parser.parse_args()
    cfg = load_settings()
    worker = InferenceService(cfg)
    try:
        await worker.start()
        audio = decode_audio(args.audio_file, sampling_rate=16000)
        audio = np.concatenate([audio, np.zeros(16000, np.float32)])
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        pcm += bytes((-len(pcm)) % 6400)
        segmenter = SpeechSegmenter(cfg.recognition.speech.model_dump())
        count = 0
        for offset in range(0, len(pcm), 6400):
            completed, _, _ = segmenter.feed(pcm[offset : offset + 6400])
            for data in completed:
                started = time.monotonic()
                result = await worker.recognize(
                    "local-smoke-test", "speech", {"pcm": data}
                )
                print(f"{time.monotonic() - started:.2f}s: {result['text']}")
                count += bool(result["text"])
        return 0 if count else 1
    finally:
        await worker.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
