import re
import sqlite3
import time
from pathlib import Path

from app.core.security import hasher


def normalize_room_id(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9-]{3,32}", value):
        raise ValueError("ルームIDは半角英数字・ハイフンの3〜32文字です")
    return value


class RoomRepository:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
                max_participants INTEGER NOT NULL, expires_at REAL NOT NULL,
                created_at REAL NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def get(self, room_id: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM rooms WHERE id=? AND expires_at>?", (room_id, time.time())
            ).fetchone()
            return dict(row) if row else None

    def create(self, room_id: str, password: str, ttl: int = 86400, maximum: int = 4):
        room_id = normalize_room_id(room_id)
        if not 8 <= len(password) <= 128:
            raise ValueError("パスワードは8〜128文字です")
        if not 1 <= maximum <= 4 or ttl < 60:
            raise ValueError("人数は1〜4人、有効期間は60秒以上です")
        created_at = time.time()
        expires_at = created_at + ttl
        password_hash = hasher.hash(password)
        with self.connect() as db:
            db.execute(
                "INSERT INTO rooms VALUES (?, ?, ?, ?, ?)",
                (room_id, password_hash, maximum, expires_at, created_at),
            )
        return {"room_id": room_id, "expires_at": expires_at, "max_participants": maximum}

    def cleanup(self):
        with self.connect() as db:
            return db.execute("DELETE FROM rooms WHERE expires_at<=?", (time.time(),)).rowcount
