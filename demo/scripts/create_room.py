import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import load_settings
from app.repositories.rooms import RoomRepository


def main():
    parser = argparse.ArgumentParser(description="会話ルームを作成します")
    parser.add_argument("room_id", nargs="?")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--max-participants", type=int, default=4)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    cfg = load_settings()
    repo = RoomRepository(cfg.path(cfg.storage.room_database))
    if args.cleanup:
        print(f"期限切れルームを{repo.cleanup()}件削除しました")
        return
    if not args.room_id:
        parser.error("room_idが必要です")
    password = getpass.getpass("ルームパスワード (8〜128文字): ")
    if password != getpass.getpass("確認: "):
        parser.error("パスワードが一致しません")
    try:
        repo.create(args.room_id, password, args.hours * 3600, args.max_participants)
    except (ValueError, sqlite3.IntegrityError) as exc:
        parser.error(
            "同じIDのルームが存在します"
            if isinstance(exc, sqlite3.IntegrityError)
            else str(exc)
        )
    print(
        f"ルーム {args.room_id.strip().lower()} を作成しました ({args.hours}時間有効)"
    )


if __name__ == "__main__":
    main()
