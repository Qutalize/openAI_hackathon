import asyncio
import json
import struct

import numpy as np
import pytest

from app.core.config import load_settings, merge
from app.inference.preprocessing import pack_frames
from app.schemas.protocol import parse_media
from app.models.session import RoomState, Session
from app.services.rooms import RoomService


def test_merge_replaces_arrays():
    assert merge({"a": {"b": 1, "c": [1]}}, {"a": {"c": [2]}}) == {"a": {"b": 1, "c": [2]}}


def test_configuration_rejects_unknown_and_unsafe_production():
    from pydantic import ValidationError

    cfg = load_settings()
    data = cfg.model_dump()
    data["media"]["invented"] = 2
    with pytest.raises(ValidationError):
        type(cfg).model_validate(data)
    data = cfg.model_dump()
    data["app"]["environment"] = "production"
    with pytest.raises(ValidationError):
        type(cfg).model_validate(data)


def packet(header, body):
    h = json.dumps(header).encode()
    return struct.pack("<I", len(h)) + h + body


def test_media_rejects_nan_and_shape():
    h = {
        "version": 1,
        "kind": "vision.features",
        "stream_id": "test",
        "input_epoch": 0,
        "seq": 0,
        "capture_ms": 10,
        "shape": [1, 40, 4],
        "frame_timestamps_ms": [10],
    }
    array = np.zeros((1, 40, 4), dtype="<f4")
    assert parse_media(packet(h, array.tobytes()), 65536)[1].shape == (1, 40, 4)
    array[0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        parse_media(packet(h, array.tobytes()), 65536)
    h["shape"] = [1000000, 40, 4]
    with pytest.raises(ValueError):
        parse_media(packet(h, b""), 65536)


def test_temporal_masks_long_gaps_and_rejects_overlong():
    frames = np.ones((3, 40, 4), np.float32)
    _, mask, _ = pack_frames(frames, [0, 50, 400], 64, "lipread")
    assert mask[0, 0] == 1 and mask[0, 2] == 0
    with pytest.raises(ValueError):
        pack_frames(frames, [0, 50, 5000], 64, "lipread")


async def test_late_recognition_is_cancelled_after_input_change(tmp_path):
    class Delayed:
        capabilities = {"speech": {"available": True}}

        async def recognize(self, *args):
            await asyncio.sleep(0.1)
            return {"text": "古い結果", "model_version": "test"}

    cfg = load_settings()
    service = RoomService(cfg, None, Delayed())
    s = Session("person", "room", "ユーザーA", "standard", "speech", "digest", "csrf", 1e12)
    service.rooms["room"] = RoomState(participants={s.participant_id: s})
    service.sessions[s.token_digest] = s
    service.launch_recognition(s, "speech", {"pcm": b""})
    await asyncio.sleep(0.01)
    await service.reset_input(s)
    await asyncio.sleep(0.15)
    assert service.rooms["room"].utterances == []


def test_silero_silent_audio_produces_no_segment():
    pytest.importorskip("faster_whisper")
    from app.inference.speech import SpeechSegmenter

    segmenter = SpeechSegmenter(load_settings().recognition.speech.model_dump())
    for _ in range(10):
        completed, active, _ = segmenter.feed(bytes(6400))
        assert completed == [] and not active
