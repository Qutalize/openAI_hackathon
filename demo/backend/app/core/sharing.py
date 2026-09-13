"""Settings for an HTTPS tunnel to this PC, without changing local development."""

import re
import secrets
from urllib.parse import urlsplit

from app.core.config import Settings, load_settings


def shared_settings(origin: str, port: int, settings: Settings | None = None) -> Settings:
    url = urlsplit(origin)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
        or not re.fullmatch(r"[a-zA-Z0-9.-]+", url.hostname)
    ):
        raise ValueError("共有先はパスを含まないHTTPS URLで指定してください")
    # Revalidate the complete object so production checks see all changes at once.
    data = (settings or load_settings()).model_dump()
    data["app"]["environment"] = "production"
    data["public_origin"] = origin.rstrip("/")
    data["session_secret"] = secrets.token_urlsafe(48)
    data["security"]["cookie_secure"] = True
    data["security"]["cookie_name"] = "shared_conversation_session"
    data["server"].update(
        host="127.0.0.1", port=port, allowed_origins=[data["public_origin"]], serve_frontend=True
    )
    data["storage"]["room_database"] = "data/shared-rooms.sqlite3"
    if not data["rtc"]["stun_urls"]:
        data["rtc"]["stun_urls"] = ["stun:stun.l.google.com:19302"]
    if data["turn_urls"] or data["turn_secret"] or data["turn_username"] or data["turn_password"]:
        data["rtc"]["turn_enabled"] = True
    return Settings.model_validate(data)
