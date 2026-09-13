import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import load_settings
from app.inference.worker import InferenceService


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    service = InferenceService(load_settings())
    try:
        await service.start()
        print(json.dumps(service.capabilities, ensure_ascii=False, indent=2))
        if args.require_all and not all(
            c["available"] for c in service.capabilities.values()
        ):
            return 1
        return 0
    finally:
        await service.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
