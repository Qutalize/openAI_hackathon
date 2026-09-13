import base64
import struct

import pytest

from conftest import join, receive_type, send

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRXsAAAAASUVORK5CYII="


def test_avatar_shared_in_session_events_and_departed_speaker_history(client, application):
    response = client.post(
        "/api/rooms/demo-room/join",
        json={
            "password": "test-password",
            "mode": "standard",
            "input": "text",
            "avatar": PNG,
        },
    )
    assert response.status_code == 200
    first = response.json()
    assert first["avatar"] == PNG
    assert client.get("/api/session").json()["avatar"] == PNG
    with client.websocket_connect("/ws/rooms/demo-room") as ws:
        assert receive_type(ws, "participant.joined")["payload"]["avatar"] == PNG
        send(ws, "utterance.submit", {"text": "Icon stays with my message"})
        utterance = receive_type(ws, "utterance.final")["payload"]
        assert "avatar" not in utterance  # Do not repeat image bytes in every message.
        client.cookies.clear()
        join(client)
        snap = client.get("/api/rooms/demo-room/snapshot").json()
        assert snap["avatars"][first["participant_id"]] == PNG
    service = application.state.rooms
    author = next(s for s in service.sessions.values() if s.participant_id == first["participant_id"])
    client.portal.call(service.remove, author)
    snap = client.get("/api/rooms/demo-room/snapshot").json()
    assert snap["avatars"][first["participant_id"]] == PNG
    assert all(p["id"] != first["participant_id"] for p in snap["participants"])
    assert client.get("/api/rooms/other-room/snapshot").status_code == 403
    state = service.rooms["demo-room"]
    state.utterances.clear()
    assert first["participant_id"] not in client.get("/api/rooms/demo-room/snapshot").json()["avatars"]


@pytest.mark.parametrize(
    "avatar",
    [
        "https://example.com/avatar.png",
        "data:image/svg+xml;base64,PHN2Zy8+",
        "data:image/png;base64,not-valid",
        "data:image/png;base64," + base64.b64encode(b"not a PNG image").decode(),
        PNG + "A" * 65536,
        "data:image/png;base64,"
        + base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 10000, 10000) + bytes(9)
        ).decode(),
    ],
    ids=["external-url", "svg", "invalid-base64", "wrong-content", "too-large", "oversize-dimensions"],
)
def test_invalid_avatar_rejected(client, avatar):
    assert (
        client.post(
            "/api/rooms/demo-room/join",
            json={
                "password": "test-password",
                "mode": "standard",
                "input": "text",
                "avatar": avatar,
            },
        ).status_code
        == 422
    )


def test_legacy_client_uses_default_avatar(client):
    assert join(client)["avatar"] == ""
