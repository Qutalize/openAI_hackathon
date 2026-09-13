import pytest
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app


class NoModels:
    capabilities = {
        k: {"available": False, "reason": "モデル未導入", "vocabulary": []}
        for k in ("speech", "lipread", "sign")
    }
    metrics = {}
    pending = {}

    async def start(self):
        pass

    async def close(self):
        pass


@pytest.fixture
def application(tmp_path):
    cfg = load_settings()
    cfg.storage.room_database = str(tmp_path / "rooms.sqlite3")
    cfg.app.environment = "test"
    cfg.security.join_attempts_per_minute = 50
    return create_app(cfg, NoModels())


@pytest.fixture
def client(application):
    with TestClient(application, headers={"origin": "http://localhost:5173"}) as c:
        application.state.rooms.repo.create("demo-room", "test-password")
        application.state.rooms.repo.create("other-room", "test-password")
        yield c


def join(client, room="demo-room"):
    response = client.post(
        f"/api/rooms/{room}/join", json={"password": "test-password", "mode": "standard", "input": "text"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def receive_type(ws, kind):
    for _ in range(30):
        event = ws.receive_json()
        if event["type"] == kind:
            return event
    raise AssertionError(f"No {kind} received")


def send(ws, kind, payload, request_id="request"):
    ws.send_json({"version": 1, "type": kind, "request_id": request_id, "payload": payload})
