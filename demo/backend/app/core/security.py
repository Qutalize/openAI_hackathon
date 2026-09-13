import base64
import hashlib
import hmac
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

hasher = PasswordHasher()
_dummy = hasher.hash(secrets.token_urlsafe(32))


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        return hasher.verify(encoded or _dummy, password) and encoded is not None
    except (VerificationError, InvalidHashError):
        return False


def digest(secret: str, token: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def turn_credentials(secret: str, participant: str, ttl: int) -> dict:
    expires = int(time.time()) + ttl
    username = f"{expires}:{participant}"
    credential = base64.b64encode(
        hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    ).decode()
    return {"username": username, "credential": credential, "expires_at": expires}
