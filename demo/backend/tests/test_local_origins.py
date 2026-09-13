import pytest

from conftest import receive_type, send


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_local_origin_create_join_websocket_and_leave(client, origin):
    client.headers["origin"] = origin
    creation = client.post("/api/rooms", json={"room_id": "origin-room", "password": "test-password"})
    assert creation.status_code == 201
    assert creation.headers["access-control-allow-origin"] == origin
    joined = client.post(
        "/api/rooms/origin-room/join",
        json={
            "password": "test-password",
            "mode": "standard",
            "input": "text",
        },
    )
    assert joined.status_code == 200
    with client.websocket_connect("/ws/rooms/origin-room") as ws:
        receive_type(ws, "participant.joined")
        send(ws, "utterance.submit", {"text": "ローカルURLから接続できました"}, "origin")
        assert receive_type(ws, "utterance.final")["payload"]["text"] == "ローカルURLから接続できました"
    assert (
        client.delete(
            "/api/session",
            headers={
                "x-csrf-token": joined.json()["csrf_token"],
            },
        ).status_code
        == 204
    )


@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "http://127.0.0.1:9999",
        "http://127.0.0.1.evil.example:5173",
        "https://evil.example",
    ],
)
def test_other_origins_still_cannot_create_rooms(client, application, origin):
    response = client.post(
        "/api/rooms", json={"room_id": "origin-room", "password": "test-password"}, headers={"origin": origin}
    )
    assert response.status_code == 403
    assert application.state.rooms.repo.get("origin-room") is None
