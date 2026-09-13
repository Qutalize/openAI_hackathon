import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings, load_settings
from app.core.sharing import shared_settings
from app.main import create_app
from conftest import NoModels, receive_type, send

ORIGIN = "https://meeting-demo.trycloudflare.com"
WS_ORIGIN = ORIGIN.replace("https://", "wss://")


@pytest.fixture
def shared_app(tmp_path):
    cfg = shared_settings(ORIGIN, 8765)
    cfg.storage.room_database = str(tmp_path / "rooms.sqlite3")
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<html><div id="root"></div></html>', encoding="utf-8")
    (dist / "assets" / "app.js").write_text('console.log("app")', encoding="utf-8")
    (tmp_path / "private.txt").write_text("do not expose", encoding="utf-8")
    cfg.server.frontend_dist = str(dist)
    return create_app(cfg, NoModels())


def test_shared_settings_are_isolated_from_local_settings():
    original = load_settings()
    before = original.model_dump()
    cfg = shared_settings(ORIGIN, 8765, original)
    assert original.model_dump() == before
    assert cfg.app.environment == "production"
    assert cfg.server.host == "127.0.0.1"
    assert cfg.server.allowed_origins == [ORIGIN]
    assert cfg.security.cookie_secure and cfg.server.serve_frontend
    assert cfg.storage.room_database == "data/shared-rooms.sqlite3"
    assert cfg.session_secret != original.session_secret
    assert cfg.rtc.stun_urls


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.com",
        "https://example.com/path",
        "https://u:p@host",
        "https://host?query=1",
        "https://host#fragment",
        "https://",
    ],
)
def test_invalid_public_origin_is_rejected(origin):
    with pytest.raises(ValueError):
        shared_settings(origin, 8765)


def test_https_join_sets_secure_host_only_cookie(shared_app):
    with TestClient(shared_app, base_url=ORIGIN, headers={"origin": ORIGIN}) as first:
        assert (
            first.post("/api/rooms", json={"room_id": "shared-room", "password": "test-password"}).status_code
            == 201
        )
        payload = {"password": "test-password", "mode": "standard", "input": "text"}
        joined = first.post("/api/rooms/shared-room/join", json=payload)
        assert joined.status_code == 200
        cookie = joined.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        assert "domain=" not in cookie
        assert first.get("/api/session").status_code == 200


def test_https_websocket_caption_flow(shared_app):
    with TestClient(shared_app, base_url=ORIGIN, headers={"origin": ORIGIN}) as first:
        second = TestClient(shared_app, base_url=ORIGIN, headers={"origin": ORIGIN})
        try:
            first.post("/api/rooms", json={"room_id": "shared-room", "password": "test-password"})
            body = {"password": "test-password", "mode": "standard", "input": "text"}
            for client in (first, second):
                assert client.post("/api/rooms/shared-room/join", json=body).status_code == 200
            with first.websocket_connect(f"{WS_ORIGIN}/ws/rooms/shared-room") as wa:
                receive_type(wa, "participant.joined")
                with second.websocket_connect(f"{WS_ORIGIN}/ws/rooms/shared-room") as wb:
                    receive_type(wb, "participant.joined")
                    send(wa, "utterance.submit", {"text": "HTTPS経由で会話"})
                    assert receive_type(wb, "utterance.final")["payload"]["text"] == "HTTPS経由で会話"
            assert first.get("/rooms/shared-room").status_code == 200
            session = first.get("/api/session").json()
            assert (
                first.delete("/api/session", headers={"x-csrf-token": session["csrf_token"]}).status_code
                == 204
            )
            assert first.get("/api/session").status_code == 401
        finally:
            second.close()


def test_shared_origin_is_exact_and_ws_requires_session(shared_app):
    with TestClient(shared_app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        for origin in (
            "http://localhost:5173",
            "https://another.trycloudflare.com",
            ORIGIN + ".evil.example",
        ):
            response = client.post(
                "/api/rooms",
                json={"room_id": "bad-room", "password": "test-password"},
                headers={"origin": origin},
            )
            assert response.status_code == 403
            with pytest.raises(WebSocketDisconnect) as error:
                with client.websocket_connect("/ws/rooms/demo-room", headers={"origin": origin}):
                    pass
            assert error.value.code == 4403
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/ws/rooms/demo-room"):
                pass
        assert error.value.code == 4401


def test_only_built_frontend_and_known_spa_routes_are_served(shared_app):
    with TestClient(shared_app, base_url=ORIGIN) as client:
        for path in ("/", "/training", "/rooms/demo-room?layout=vision"):
            response = client.get(path)
            assert response.status_code == 200
            assert 'id="root"' in response.text
            assert response.headers["cache-control"] == "no-store"
        asset = client.get("/assets/app.js")
        assert asset.status_code == 200 and "javascript" in asset.headers["content-type"]
        for path in (
            "/api/missing",
            "/assets/missing.js",
            "/.env",
            "/backend/app/main.py",
            "/%2e%2e/private.txt",
            "/docs",
            "/openapi.json",
            "/unknown-route",
        ):
            assert client.get(path).status_code == 404
        assert client.get("/health/ready").json()["status"] == "ready"


def test_missing_build_fails_before_startup(tmp_path):
    cfg = shared_settings(ORIGIN, 8765)
    cfg.server.frontend_dist = str(tmp_path)
    with pytest.raises(RuntimeError, match="ビルド"):
        create_app(cfg, NoModels())


@pytest.mark.parametrize("service_auth", [True, False])
def test_turn_credentials_are_authenticated_and_not_in_public_config(shared_app, service_auth):
    data = shared_app.state.settings.model_dump()
    data.update(
        turn_urls=["turns:relay.example:443?transport=tcp"],
        turn_secret="",
        turn_username="",
        turn_password="",
    )
    if service_auth:
        data.update(turn_username="service-user", turn_password="service-password")
    else:
        data["turn_secret"] = "turn-shared-secret-" * 3
    data["rtc"]["turn_enabled"] = True
    shared_app.state.settings = Settings.model_validate(data)
    with TestClient(shared_app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
        assert client.get("/api/rtc-config").status_code == 401
        assert "service-password" not in client.get("/api/config").text
        assert "turn-shared-secret" not in client.get("/api/config").text
        client.post("/api/rooms", json={"room_id": "turn-room", "password": "test-password"})
        client.post(
            "/api/rooms/turn-room/join",
            json={"password": "test-password", "mode": "standard", "input": "text"},
        )
        result = client.get("/api/rtc-config").json()
        relay = result["iceServers"][-1]
        assert relay["urls"] == data["turn_urls"]
        if service_auth:
            assert relay["username"] == "service-user" and relay["credential"] == "service-password"
            assert result["expires_at"] is None
        else:
            expected = base64.b64encode(
                hmac.new(data["turn_secret"].encode(), relay["username"].encode(), hashlib.sha1).digest()
            ).decode()
            assert relay["credential"] == expected and result["expires_at"] > 0


def test_partial_turn_config_fails_preflight():
    cfg = load_settings()
    cfg.turn_urls = ["turn:relay.example:3478"]
    cfg.turn_username = "user"
    with pytest.raises(ValidationError, match="TURN requires"):
        shared_settings(ORIGIN, 8765, cfg)
