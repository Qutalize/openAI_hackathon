import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app
from tests.conftest import NoModels

CODE = "collect-code-for-tests"


@pytest.fixture
def collector(tmp_path):
    cfg = load_settings()
    cfg.storage.room_database = str(tmp_path / "rooms.sqlite3")
    cfg.app.environment = "test"
    cfg.training.upload_enabled = True
    cfg.training.directory = str(tmp_path / "training")
    cfg.training.max_samples_per_subject = 3
    cfg.training_upload_token = CODE
    with TestClient(create_app(cfg, NoModels()), headers={"origin": "http://localhost:5173"}) as c:
        yield c, tmp_path / "training"


def sample(label="greeting", subject="p01", consent=True, frames=30, valid=1.0):
    return {
        "subject_id": subject,
        "label": label,
        "modality": "lipread",
        "consent": consent,
        "created_at": "2026-11-14T00:00:00Z",
        "preprocessing_version": "landmarks-v1",
        "mediapipe_version": "0.10.32",
        "frames": [[[0.5, 0.5, 0.0, valid]] * 40] * frames,
        "timestamps": [i * 50.0 for i in range(frames)],
    }


def test_collection_is_off_without_a_code(client):
    assert client.post("/api/training/samples", json=sample()).status_code == 404


def test_upload_requires_the_collection_code(collector):
    c, _ = collector
    assert c.post("/api/training/samples", json=sample()).status_code == 403
    assert c.post("/api/training/samples", json=sample(), headers={"x-training-code": "wrong"}).status_code == 403


def test_upload_saves_landmarks_and_reports_counts(collector):
    c, directory = collector
    h = {"x-training-code": CODE}
    r = c.post("/api/training/samples", json=sample(), headers=h)
    assert r.status_code == 201, r.text
    c.post("/api/training/samples", json=sample("unknown"), headers=h)
    saved = list((directory / "lipread/p01").glob("*.json"))
    assert len(saved) == 2
    assert json.loads(saved[0].read_text())["consent"] is True
    status = c.get("/api/training/status?subject=p01", headers=h).json()
    assert status["lipread"]["labels"] == {"greeting": 1, "unknown": 1}
    assert status["lipread"]["subjects"] == 1
    assert {"id": "thanks", "text": "ありがとう"} in status["lipread"]["vocabulary"]


@pytest.mark.parametrize(
    "body",
    [
        sample(consent=False),
        sample(label="not-in-vocabulary"),
        sample(subject="../escape"),
        sample(frames=1),
        sample(valid=0.0),
    ],
)
def test_upload_rejects_invalid_recordings(collector, body):
    c, directory = collector
    r = c.post("/api/training/samples", json=body, headers={"x-training-code": CODE})
    assert r.status_code == 422
    assert not directory.exists()


def test_subject_limit_and_deletion(collector):
    c, directory = collector
    h = {"x-training-code": CODE}
    for _ in range(3):
        assert c.post("/api/training/samples", json=sample(), headers=h).status_code == 201
    assert c.post("/api/training/samples", json=sample(), headers=h).status_code == 429
    assert c.delete("/api/training/subjects/p01", headers=h).status_code == 204
    assert not (directory / "lipread/p01").exists()
