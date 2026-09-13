import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import join, receive_type, send


def test_public_config_hides_secrets(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    text = response.text
    assert "session_secret" not in text and "model_path" not in text
    assert response.json()["capabilities"]["sign"]["available"] is False


def test_join_auth_and_origin(client):
    body = {"password": "wrong", "mode": "standard", "input": "text"}
    a = client.post("/api/rooms/demo-room/join", json=body)
    b = client.post("/api/rooms/missing-room/join", json=body)
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    assert (
        client.post(
            "/api/rooms/demo-room/join", json=body, headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_cookie_and_leave_csrf(client):
    s = join(client)
    assert client.get("/api/session").status_code == 200
    # /api/session rotates CSRF; use the latest token.
    csrf = client.get("/api/session").json()["csrf_token"]
    assert client.delete("/api/session").status_code == 403
    assert client.delete("/api/session", headers={"x-csrf-token": csrf}).status_code == 204
    assert client.get("/api/session").status_code == 401
    assert client.delete("/api/session").status_code == 204
    assert s["participant_id"]


def test_capacity_and_names(client, application):
    names = []
    for _ in range(4):
        client.cookies.clear()
        names.append(join(client)["display_name"])
    assert len(set(names)) == 4
    client.cookies.clear()
    assert (
        client.post(
            "/api/rooms/demo-room/join",
            json={"password": "test-password", "mode": "standard", "input": "text"},
        ).status_code
        == 409
    )


def test_unavailable_model_is_not_faked(client):
    response = client.post(
        "/api/rooms/demo-room/join",
        json={"password": "test-password", "mode": "standard", "input": "lipread"},
    )
    assert response.status_code == 409


def test_room_isolation(client):
    join(client)
    assert client.get("/api/rooms/other-room/snapshot").status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/rooms/other-room"):
            pass


def test_websocket_origin(client):
    join(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/rooms/demo-room", headers={"origin": "https://evil.example"}):
            pass


def test_text_correction_and_idempotency(client):
    join(client)
    with client.websocket_connect("/ws/rooms/demo-room") as ws:
        receive_type(ws, "participant.joined")
        send(ws, "utterance.submit", {"text": "こんにちは"}, "first")
        u = receive_type(ws, "utterance.final")["payload"]
        receive_type(ws, "ack")
        send(ws, "utterance.submit", {"text": "こんにちは"}, "first")
        receive_type(ws, "ack")
        send(
            ws,
            "utterance.correct",
            {"utterance_id": u["utterance_id"], "revision": 1, "text": "こんばんは"},
            "fix",
        )
        updated = receive_type(ws, "utterance.corrected")["payload"]
        assert updated["revision"] == 2 and updated["text"] == "こんばんは"
        assert len(client.get("/api/rooms/demo-room/snapshot").json()["utterances"]) == 1


def test_cannot_correct_other_participant(client, application):
    a = join(client)
    with client.websocket_connect("/ws/rooms/demo-room") as wa:
        receive_type(wa, "participant.joined")
        send(wa, "utterance.submit", {"text": "Aの発言"}, "create")
        u = receive_type(wa, "utterance.final")["payload"]
        client.cookies.clear()
        b = join(client)
        assert a["participant_id"] != b["participant_id"]
        with client.websocket_connect("/ws/rooms/demo-room") as wb:
            receive_type(wb, "participant.joined")
            send(wb, "utterance.correct", {"utterance_id": u["utterance_id"], "revision": 1, "text": "偽装"})
            assert "自分の発言" in receive_type(wb, "error")["payload"]["message"]
            send(
                wb,
                "rtc.offer",
                {"target_id": "not-in-room", "description": {"type": "offer", "sdp": "x"}},
                "rtc",
            )
            assert receive_type(wb, "error")


def test_resume_snapshot_and_input_epoch(client):
    join(client)
    with client.websocket_connect("/ws/rooms/demo-room") as ws:
        receive_type(ws, "participant.joined")
        send(ws, "device.update", {"camera": False, "microphone": False}, "device")
        epoch = receive_type(ws, "ack")["payload"]["input_epoch"]
        assert epoch > 0
        send(ws, "session.resume", {"last_server_seq": 0}, "resume")
        snap = receive_type(ws, "room.snapshot")["payload"]
        assert snap["self"]["input_epoch"] == epoch
        send(ws, "utterance.submit", {"text": "x" * 501}, "long")
        assert receive_type(ws, "error")


def test_expired_session_rejected(client, application):
    join(client)
    next(iter(application.state.rooms.sessions.values())).expires_at = 0
    assert client.get("/api/session").status_code == 401
