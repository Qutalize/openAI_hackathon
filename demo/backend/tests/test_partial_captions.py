import asyncio

from conftest import join


class Events:
    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)

    async def close(self, code=1000):
        pass


class Heard:
    """Stands in for the segmenter: some speech is in progress under a given serial."""

    def __init__(self):
        self.serial = 1

    def snapshot(self):
        return self.serial, b"pcm"


def partials(observer):
    return [e["payload"] for e in observer.events if e["type"] == "utterance.partial"]


def test_speech_in_progress_is_captioned_without_entering_the_transcript(client, application):
    join(client)
    service = application.state.rooms
    service.settings.recognition.partial_results = True
    s = next(iter(service.sessions.values()))

    async def exercise():
        observer = s.control = Events()
        s.segmenter = Heard()
        release = asyncio.Event()

        async def recognize(*args):
            await release.wait()
            return {"text": "こんにちは", "model_version": "test"}

        service.inference.recognize = recognize
        service.launch_partial(s)
        service.launch_partial(s)  # one request at a time: this one is skipped
        assert len(s.tasks) == 1
        release.set()
        await asyncio.gather(*list(s.tasks))
        assert partials(observer) == [
            {"participant_id": s.participant_id, "display_name": s.display_name, "text": "こんにちは"}
        ]
        # Transient: not numbered, not replayed, and not part of the transcript.
        assert "event_id" not in observer.events[-1]
        assert service.rooms[s.room_id].utterances == []
        assert all(e["type"] != "utterance.partial" for _, e in service.rooms[s.room_id].replay)

    client.portal.call(exercise)


def test_result_for_speech_that_already_ended_is_dropped(client, application):
    join(client)
    service = application.state.rooms
    service.settings.recognition.partial_results = True
    s = next(iter(service.sessions.values()))

    async def exercise():
        observer = s.control = Events()
        s.segmenter = Heard()
        release = asyncio.Event()

        async def recognize(*args):
            await release.wait()
            return {"text": "古い結果", "model_version": "test"}

        service.inference.recognize = recognize
        service.launch_partial(s)
        s.segmenter.serial += 1  # the segment ended while the request was running
        release.set()
        await asyncio.gather(*list(s.tasks))
        assert partials(observer) == []

    client.portal.call(exercise)


def test_final_without_text_and_input_reset_clear_the_caption(client, application):
    join(client)
    service = application.state.rooms
    service.settings.recognition.partial_results = True
    s = next(iter(service.sessions.values()))

    async def exercise():
        observer = s.control = Events()

        async def recognize(*args):
            return {"text": "", "model_version": "test"}

        service.inference.recognize = recognize
        service.launch_recognition(s, "speech", {})
        await asyncio.gather(*list(s.tasks))
        assert partials(observer)[-1] == {"participant_id": s.participant_id, "text": ""}
        observer.events.clear()
        await service.reset_input(s)
        assert partials(observer) == [{"participant_id": s.participant_id, "text": ""}]

    client.portal.call(exercise)
