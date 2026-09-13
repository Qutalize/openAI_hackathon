import pytest

from conftest import join, receive_type, send


def test_automatic_name_does_not_collide_with_custom_name(client):
    response = client.post(
        "/api/rooms/demo-room/join",
        json={
            "password": "test-password",
            "mode": "standard",
            "input": "text",
            "display_name": "ユーザーa",
        },
    )
    assert response.status_code == 200
    client.cookies.clear()
    assert join(client)["display_name"] == "ユーザーB"


def test_rename_broadcasts_and_preserves_utterance_owner(client):
    first = join(client)
    with client.websocket_connect("/ws/rooms/demo-room") as author:
        receive_type(author, "participant.joined")
        send(author, "utterance.submit", {"text": "before rename"})
        utterance = receive_type(author, "utterance.final")["payload"]
        client.cookies.clear()
        second = join(client)
        with client.websocket_connect("/ws/rooms/demo-room") as observer:
            receive_type(observer, "participant.joined")
            response = client.patch(
                "/api/session",
                json={"display_name": "  花子  "},
                headers={"x-csrf-token": second["csrf_token"]},
            )
            assert response.status_code == 200
            assert response.json()["display_name"] == "花子"
            for socket in (author, observer):
                event = receive_type(socket, "participant.updated")["payload"]
                assert event["id"] == second["participant_id"]
                assert event["display_name"] == "花子"
            send(
                observer,
                "utterance.correct",
                {"utterance_id": utterance["utterance_id"], "revision": 1, "text": "not mine"},
            )
            assert "自分の発言" in receive_type(observer, "error")["payload"]["message"]
            send(observer, "utterance.submit", {"text": "my message"}, "submit")
            mine = receive_type(observer, "utterance.final")["payload"]
            assert mine["display_name"] == "花子"
            assert (
                client.patch(
                    "/api/session",
                    json={"display_name": "Hanako"},
                    headers={"x-csrf-token": second["csrf_token"]},
                ).status_code
                == 200
            )
            snapshot = client.get("/api/rooms/demo-room/snapshot").json()
            assert snapshot["utterances"][0]["participant_id"] == first["participant_id"]
            assert snapshot["utterances"][1]["display_name"] == "Hanako"
            assert snapshot["utterances"][1]["participant_id"] == second["participant_id"]


def test_name_auth_csrf_and_duplicates(client):
    assert client.patch("/api/session", json={"display_name": "Name"}).status_code == 401
    first = join(client)
    assert client.patch("/api/session", json={"display_name": "Name"}).status_code == 403
    headers = {"x-csrf-token": first["csrf_token"]}
    assert (
        client.patch(
            "/api/session",
            json={"display_name": "Name"},
            headers={**headers, "origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert client.patch("/api/session", json={"display_name": "Name"}, headers=headers).status_code == 200
    client.cookies.clear()
    body = {"password": "test-password", "mode": "standard", "input": "text", "display_name": "name"}
    assert client.post("/api/rooms/demo-room/join", json=body).status_code == 409
    body["display_name"] = "  Other  "
    second = client.post("/api/rooms/demo-room/join", json=body).json()
    assert second["display_name"] == "Other"
    headers = {"x-csrf-token": second["csrf_token"]}
    assert client.patch("/api/session", json={"display_name": "NAME"}, headers=headers).status_code == 409
    assert (
        client.patch(
            "/api/session",
            json={"display_name": "Other", "participant_id": first["participant_id"]},
            headers=headers,
        ).status_code
        == 422
    )


@pytest.mark.parametrize("name", ["", "   ", "x" * 41, "a\nb", "a\u202eb"])
def test_invalid_rename(client, name):
    session = join(client)
    assert (
        client.patch(
            "/api/session", json={"display_name": name}, headers={"x-csrf-token": session["csrf_token"]}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("name", ["x" * 41, "a\nb", "a\u202eb"])
def test_invalid_name_on_join(client, name):
    assert (
        client.post(
            "/api/rooms/demo-room/join",
            json={
                "password": "test-password",
                "mode": "standard",
                "input": "text",
                "display_name": name,
            },
        ).status_code
        == 422
    )
