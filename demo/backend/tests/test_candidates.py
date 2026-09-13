import asyncio
import time

import pytest

from app.core.config import load_settings
from app.models.session import RoomState, Session
from app.schemas.protocol import ClientEvent
from app.services.rooms import RoomService


class CaptureConnection:
    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)


class TestVisionEngine:
    """Protocol test double, never loaded by the application."""
    async def recognize(self, *args):
        return {"candidates": [{"label": "greeting", "text": "こんにちは"}], "model_version": "test-only"}


async def prepare():
    service = RoomService(load_settings(), None, TestVisionEngine())
    s = Session("person", "room", "ユーザーA", "hearing_support", "sign", "digest", "csrf", time.time()+60)
    s.control = CaptureConnection()
    service.rooms["room"] = RoomState(participants={s.participant_id: s})
    service.sessions[s.token_digest] = s
    service.launch_recognition(s, "sign", {"frames": []})
    await asyncio.gather(*s.tasks)
    event = next(e for e in s.control.events if e["type"] == "recognition.candidate")
    return service, s, event["payload"]["candidate_id"]


async def test_recognition_candidate_is_private_until_confirmed():
    service, s, candidate = await prepare()
    assert service.rooms["room"].utterances == []
    await service.handle(s, ClientEvent(version=1, type="utterance.submit", request_id="submit",
                                       payload={"candidate_id": candidate, "text": "こんにちは、ありがとう"}))
    u = service.rooms["room"].utterances[0]
    assert u["source"] == "sign" and u["confirmed_by_user"] is True
    assert u["text"] == "こんにちは、ありがとう"


async def test_candidate_from_old_input_epoch_cannot_be_submitted():
    service, s, candidate = await prepare()
    await service.reset_input(s)
    with pytest.raises(ValueError, match="候補の期限"):
        await service.handle(s, ClientEvent(version=1, type="utterance.submit", request_id="submit",
                                           payload={"candidate_id": candidate, "text": "こんにちは"}))
    assert service.rooms["room"].utterances == []
