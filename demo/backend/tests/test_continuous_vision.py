import asyncio

import app.services.rooms as rooms_module
from app.core.config import load_settings
from app.models.session import RoomState, Session
from app.services.rooms import RoomService


class Models:
    def __init__(self, labels):
        self.labels = list(labels)
        self.capabilities = {"lipread": {"available": True, "transport": "features"}}
        self.windows = []

    async def recognize(self, participant, kind, segment):
        self.windows.append(len(segment["frames"]))
        label = self.labels.pop(0) if self.labels else None
        candidates = [{"label": label, "text": label}] if label else []
        return {"candidates": candidates, "model_version": "test"}


class Control:
    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)


def watching(models):
    service = RoomService(load_settings(), None, models)
    s = Session("person", "room", "ユーザーA", "standard", "lipread", "digest", "csrf", 1e12)
    s.control = Control()
    service.rooms["room"] = RoomState(participants={s.participant_id: s})
    service.sessions[s.token_digest] = s
    s.watch = {
        "id": "w",
        "frames": [],
        "timestamps": [],
        "busy": False,
        "next_at": 0.0,
        "quiet_until": 0.0,
        "last_label": None,
    }
    return service, s


async def feed(service, s, start, count):
    for i in range(start, start + count):
        service.watch_frames(s, [[[0.0, 0.0, 0.0, 1.0]] * 40], [i * 50.0])
        await asyncio.sleep(0)
        for task in list(s.tasks):
            await task


def offered(s):
    return [e["payload"] for e in s.control.events if e["type"] == "recognition.candidate"]


async def test_a_phrase_seen_twice_in_a_row_is_offered_once(monkeypatch):
    monkeypatch.setattr(rooms_module, "WATCH_INTERVAL", 0)
    monkeypatch.setattr(rooms_module, "WATCH_QUIET", 60)
    models = Models([None, "thanks", "thanks", "thanks", "thanks"])
    service, s = watching(models)
    await feed(service, s, 0, 40)
    payloads = offered(s)
    assert len(payloads) == 1
    assert payloads[0]["automatic"] is True
    assert payloads[0]["candidates"][0]["label"] == "thanks"
    # The window starts over after an offer, and nothing more is offered while quiet.
    assert s.watch["frames"] == [] or len(s.watch["frames"]) < 40


async def test_changing_labels_are_not_offered(monkeypatch):
    monkeypatch.setattr(rooms_module, "WATCH_INTERVAL", 0)
    models = Models(["thanks", "greeting", "thanks", "greeting", None, None])
    service, s = watching(models)
    await feed(service, s, 0, 40)
    assert offered(s) == []


async def test_window_keeps_only_the_latest_frames(monkeypatch):
    monkeypatch.setattr(rooms_module, "WATCH_INTERVAL", 0)
    models = Models([])
    service, s = watching(models)
    await feed(service, s, 0, 200)
    span = load_settings().recognition.lipread.max_frames * 50
    assert s.watch["timestamps"][-1] - s.watch["timestamps"][0] <= span
    assert max(models.windows) <= 64
    # Nothing is recognized before half a window has arrived.
    assert min(models.windows) >= 10
