import numpy as np

from app.inference.base import Recognizer


class SpeechRecognizer(Recognizer):
    def __init__(self, path, config):
        from faster_whisper import WhisperModel

        self.config = config
        self.model = WhisperModel(
            str(path), device=config["device"], compute_type=config["compute_type"], local_files_only=True
        )

    def warmup(self):
        list(self.model.transcribe(np.zeros(16000, dtype=np.float32), language="ja", vad_filter=True)[0])

    def recognize(self, segment):
        pcm = np.frombuffer(segment["pcm"], dtype="<i2").astype(np.float32) / 32768
        segments, _ = self.model.transcribe(
            pcm,
            language="ja",
            task="transcribe",
            beam_size=self.config["beam_size"],
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return {"text": "".join(s.text for s in segments).strip(), "model_version": "whisper-small"}


class SpeechSegmenter:
    """Per-participant Silero state. Never share recurrent state between speakers."""

    def __init__(self, config):
        from faster_whisper.vad import get_vad_model

        self.model = get_vad_model()
        self.config = config
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)
        self.remainder = np.empty(0, dtype=np.float32)
        self.pre = np.empty(0, dtype=np.float32)
        self.segment = []
        self.silence = 0
        self.voiced = 0
        self.active = False

    def feed(self, pcm: bytes):
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        self.remainder = np.concatenate([self.remainder, audio])
        completed = []
        activity_before = self.active
        while len(self.remainder) >= 512:
            chunk, self.remainder = self.remainder[:512], self.remainder[512:]
            # faster-whisper Silero model has an explicit recurrent state API.
            combined = np.concatenate([self.context, chunk[None, :]], axis=1)
            probability, self.h, self.c = self.model.session.run(
                None, {"input": combined, "h": self.h, "c": self.c}
            )
            self.context = chunk[None, -64:]
            voice = float(np.asarray(probability).reshape(-1)[0]) >= 0.5
            if voice and not self.active:
                self.active = True
                self.segment = [self.pre.copy()]
            if self.active:
                self.segment.append(chunk.copy())
                self.voiced += 512 if voice else 0
                self.silence = 0 if voice else self.silence + 512
                total = sum(len(x) for x in self.segment)
                if (
                    self.silence >= self.config["vad_silence_ms"] * 16
                    or total >= self.config["max_segment_ms"] * 16
                ):
                    if self.voiced >= self.config["min_segment_ms"] * 16:
                        samples = np.concatenate(self.segment)
                        completed.append((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
                    self.active, self.segment, self.silence, self.voiced = False, [], 0, 0
            self.pre = np.concatenate([self.pre, chunk])[-3200:]
        return completed, self.active, activity_before != self.active
