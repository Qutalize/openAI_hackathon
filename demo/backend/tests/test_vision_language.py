import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import load_settings
from app.main import create_app
from app.models.session import RoomState, Session
from app.services.rooms import RoomService


def capability(available, transport="features"):
    return {"available": available, "reason": "", "vocabulary": [], "transport": transport}


class Models:
    def __init__(self, ja=True, en=True):
        self.capabilities = {
            "speech": capability(False),
            "lipread": capability(ja),
            "sign": capability(False),
            "lipread_open": capability(en, "video"),
            "sign_open": capability(False, "video"),
        }
        self.metrics, self.pending, self.calls = {}, {}, []

    async def start(self):
        pass

    async def close(self):
        pass

    async def recognize(self, participant, kind, segment):
        self.calls.append(kind)
        return {"candidates": [], "model_version": kind}


def service_with(models):
    return RoomService(load_settings(), None, models)


def test_language_defaults_to_japanese_and_falls_back_to_english():
    assert service_with(Models()).pick_language("lipread") == "ja"
    assert service_with(Models(ja=False)).pick_language("lipread") == "en"
    assert service_with(Models(ja=False)).available("lipread")
    assert not service_with(Models(ja=False, en=False)).available("lipread")
    with pytest.raises(ValueError):
        service_with(Models(en=False)).pick_language("lipread", "en")
    with pytest.raises(ValueError):
        service_with(Models()).pick_language("lipread", "fr")


async def test_recognition_uses_the_model_of_the_selected_language():
    models = Models()
    service = service_with(models)
    s = Session("person", "room", "ユーザーA", "standard", "lipread", "digest", "csrf", 1e12, language="en")
    service.rooms["room"] = RoomState(participants={s.participant_id: s})
    service.sessions[s.token_digest] = s

    class Control:
        async def send(self, event):
            pass

    s.control = Control()
    service.launch_recognition(s, "lipread", {"frames": []}, service.model_kind("lipread", s.language))
    for task in list(s.tasks):
        await task
    assert models.calls == ["lipread_open"]


def test_join_and_input_update_carry_the_language(tmp_path):
    cfg = load_settings()
    cfg.storage.room_database = str(tmp_path / "rooms.sqlite3")
    cfg.app.environment = "test"
    app = create_app(cfg, Models())
    with TestClient(app, headers={"origin": "http://localhost:5173"}) as c:
        app.state.rooms.repo.create("lang-room", "test-password")
        body = {"password": "test-password", "mode": "standard", "input": "lipread", "language": "en"}
        joined = c.post("/api/rooms/lang-room/join", json=body).json()
        assert joined["language"] == "en"
        s = next(iter(app.state.rooms.sessions.values()))
        assert app.state.rooms.model_kind(s.input, s.language) == "lipread_open"


def test_open_slots_accept_only_video_models():
    data = load_settings().model_dump()
    data["recognition"]["lipread_open"] = {
        **data["recognition"]["lipread"],
        "provider": "onnx_temporal_classifier",
    }
    with pytest.raises(ValidationError):
        type(load_settings()).model_validate(data)
