"""Local E2E fixture with isolated room storage and a public test-only password."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.rooms import RoomRepository  # noqa: E402

if __name__ == "__main__":
    import uvicorn

    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="e2e-", dir=cache) as directory:
        cfg = load_settings()
        cfg.storage.room_database = str(Path(directory) / "rooms.sqlite3")
        cfg.security.join_attempts_per_minute = 100
        repository = RoomRepository(Path(cfg.storage.room_database))
        for room_id in ("e2e-room", "mobile-room", "voice-room", "four-room"):
            repository.create(room_id, "e2e-password", ttl=3600)
        # Full real server and real adapters; unavailable models remain unavailable.
        uvicorn.run(create_app(cfg), host="127.0.0.1", port=8000, access_log=False)
