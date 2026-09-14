import asyncio
import json
import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import load_settings, merge
from app.inference.preprocessing import pack_frames
from app.schemas.protocol import parse_media
from app.models.session import RoomState, Session
from app.services.rooms import RoomService
from app.main import create_app


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


def test_video_recognition_upload_requires_active_matching_segment(tmp_path):
    class VideoModels:
        capabilities = {
            "speech": {"available": False, "reason": "モデル未導入", "vocabulary": []},
            "lipread": {
                "available": True,
                "reason": "利用可能",
                "vocabulary": [],
                "transport": "video",
            },
            "sign": {"available": False, "reason": "モデル未導入", "vocabulary": []},
        }
        metrics = {}
        pending = {}

        async def start(self):
            pass

        async def close(self):
            pass

    cfg = load_settings()
    cfg.storage.room_database = str(tmp_path / "rooms.sqlite3")
    cfg.app.environment = "test"
    cfg.recognition.lipread.provider = "auto_avsr_cli"
    application = create_app(cfg, VideoModels())
    with TestClient(application, headers={"origin": "http://localhost:5173"}) as client:
        application.state.rooms.repo.create("demo-room", "test-password")
        joined = client.post(
            "/api/rooms/demo-room/join",
            json={"password": "test-password", "mode": "standard", "input": "lipread"},
        ).json()
        session = next(iter(application.state.rooms.sessions.values()))
        session.devices["camera"] = True
        session.segment = {"id": "clip", "started_at": 0, "frames": [], "timestamps": []}
        url = "/api/rooms/demo-room/recognition/video?kind=lipread&segment_id=clip"
        assert client.post(url, content=b"video", headers={"content-type": "video/webm"}).status_code == 403
        response = client.post(
            url,
            content=b"video",
            headers={"content-type": "video/webm", "x-csrf-token": joined["csrf_token"]},
        )
        assert response.status_code == 204
        assert session.segment["video"] == b"video"
        assert session.segment["content_type"] == "video/webm"
