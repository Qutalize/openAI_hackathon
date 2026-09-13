import time

import pytest

from app.core.security import verify_password
from app.repositories.rooms import RoomRepository


def test_created_room_persists_and_accepts_multiple_participants(client, application):
    cfg = application.state.settings
    cfg.room.creation_ttl_seconds = 3600
    start = time.time()
    response = client.post("/api/rooms", json={"room_id": "New-Room", "password": "new-password"})
    assert response.status_code == 201
    body = response.json()
    assert body["room_id"] == "new-room" and body["max_participants"] == 4
    assert start + 3600 <= body["expires_at"] <= time.time() + 3600
    assert "password" not in response.text
    # Reopening SQLite proves the room is persisted independently of the request.
    saved = RoomRepository(application.state.rooms.repo.path).get("new-room")
    assert saved["password_hash"] != "new-password"
    assert verify_password("new-password", saved["password_hash"])
    participants = []
    for _ in range(2):
        client.cookies.clear()
        joined = client.post(
            "/api/rooms/new-room/join",
            json={
                "password": "new-password",
                "mode": "standard",
                "input": "text",
            },
        )
        assert joined.status_code == 200
        participants.append(joined.json()["participant_id"])
    assert len(set(participants)) == 2


def test_duplicate_creation_does_not_replace_password(client):
    response = client.post("/api/rooms", json={"room_id": "DEMO-ROOM", "password": "replacement"})
    assert response.status_code == 409
    for password, expected in [("replacement", 401), ("test-password", 200)]:
        response = client.post(
            "/api/rooms/demo-room/join",
            json={
                "password": password,
                "mode": "standard",
                "input": "text",
            },
        )
        assert response.status_code == expected


@pytest.mark.parametrize(
    "room_id,password",
    [
        ("ab", "valid-password"),
        ("invalid/room", "valid-password"),
        ("new-room", "short"),
        ("new-room", "x" * 129),
    ],
)
def test_invalid_creation_is_not_persisted(client, application, room_id, password):
    response = client.post("/api/rooms", json={"room_id": room_id, "password": password})
    assert response.status_code == 422
    assert application.state.rooms.repo.get(room_id) is None


def test_creation_requires_allowed_origin(client, application):
    response = client.post(
        "/api/rooms",
        json={"room_id": "new-room", "password": "new-password"},
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert application.state.rooms.repo.get("new-room") is None


def test_creation_rate_limit_covers_different_room_ids(client, application):
    application.state.settings.security.join_attempts_per_minute = 1
    assert (
        client.post(
            "/api/rooms",
            json={
                "room_id": "first-room",
                "password": "new-password",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/rooms",
            json={
                "room_id": "second-room",
                "password": "new-password",
            },
        ).status_code
        == 429
    )
    assert application.state.rooms.repo.get("second-room") is None
