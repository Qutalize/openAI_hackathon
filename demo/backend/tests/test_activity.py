import asyncio

import pytest

from app.inference.worker import InferenceBusy
from conftest import join


class Events:
    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)

    async def close(self, code=1000):
        pass


def test_speaking_status_tracks_activity_not_microphone_and_is_shared(client, application):
    join(client)
    service = application.state.rooms
    s = next(iter(service.sessions.values()))

    async def exercise():
        observer = Events()
        s.control = observer
        s.devices["microphone"] = True
        assert s.public()["speaking"] is False
        await service.activity(s, True)
        assert service.snapshot(s)["self"]["speaking"] is True
        assert any(e["type"] == "participant.activity" and e["payload"]["speaking"] for e in observer.events)
        await service.reset_input(s)
        assert s.public()["speaking"] is False
        assert s.public()["recognizing"] is False
        assert observer.events[-1]["payload"] == {
            "id": s.participant_id,
            "speaking": False,
            "recognizing": False,
        }

    client.portal.call(exercise)


@pytest.mark.parametrize("outcome", ["success", "error", "busy", "cancel"])
def test_recognition_status_clears_for_every_completion(client, application, outcome):
    join(client)
    service = application.state.rooms
    s = next(iter(service.sessions.values()))

    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        observer = Events()
        s.control = observer

        async def recognize(*args):
            entered.set()
            await release.wait()
            if outcome == "error":
                raise RuntimeError("test failure")
            if outcome == "busy":
                raise InferenceBusy()
            return {"text": "recognized", "model_version": "test"}

        service.inference.recognize = recognize
        service.launch_recognition(s, "speech", {})
        tasks = list(s.tasks)
        await asyncio.wait_for(entered.wait(), 1)
        assert service.snapshot(s)["self"]["recognizing"] is True
        if outcome == "cancel":
            await service.reset_input(s)
        else:
            release.set()
        await asyncio.gather(*tasks)
        assert s.public()["recognizing"] is False
        activity = [e["payload"] for e in observer.events if e["type"] == "participant.activity"]
        assert activity[0]["recognizing"] is True
        assert activity[-1]["recognizing"] is False

    client.portal.call(exercise)


def test_overlapping_jobs_keep_status_until_last_finishes(client, application):
    join(client)
    service = application.state.rooms
    s = next(iter(service.sessions.values()))

    async def exercise():
        s.control = Events()
        started = [asyncio.Event(), asyncio.Event()]
        release = [asyncio.Event(), asyncio.Event()]

        async def recognize(_, kind, segment):
            index = segment["index"]
            started[index].set()
            await release[index].wait()
            return {"text": "", "model_version": "test"}

        service.inference.recognize = recognize
        service.launch_recognition(s, "speech", {"index": 0})
        first = next(iter(s.tasks))
        service.launch_recognition(s, "speech", {"index": 1})
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started)), 1)
        assert s.recognition_jobs == 2
        release[0].set()
        await first
        assert s.public()["recognizing"] is True
        release[1].set()
        await asyncio.gather(*list(s.tasks))
        assert s.public()["recognizing"] is False

    client.portal.call(exercise)
