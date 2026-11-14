"""Retrain the Japanese phrase models when /training has new recordings.

    python training/retrain.py               # once
    python training/retrain.py --every 30    # check every 30 minutes

For each input whose recordings changed since the last attempt, run pipeline.py --register and append
the outcome to data/training-runs/history.jsonl. An accepted model is copied to models/{input}/ and
the running server swaps it in within a minute; a rejected one leaves the current model in place.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODALITIES = ("lipread", "sign")


def fingerprint(directory: Path) -> list:
    files = list(directory.glob("*/*.json")) if directory.is_dir() else []
    return [len(files), max((f.stat().st_mtime_ns for f in files), default=0)]


def run_once(data: Path, work: Path, epochs: int, log=print) -> list[dict]:
    work.mkdir(parents=True, exist_ok=True)
    state_path = work / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    outcomes = []
    for kind in MODALITIES:
        current = fingerprint(data / kind)
        if current[0] == 0 or state.get(kind) == current:
            continue
        summary = work / f"summary-{kind}.json"
        summary.unlink(missing_ok=True)
        started = time.monotonic()
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "training/pipeline.py"),
                kind,
                "--data",
                str(data),
                "--work",
                str(work),
                "--epochs",
                str(epochs),
                "--register",
                "--summary",
                str(summary),
            ],
            capture_output=True,
            text=True,
        )
        outcome = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modality": kind,
            "seconds": round(time.monotonic() - started, 1),
        }
        if summary.is_file():
            outcome.update(json.loads(summary.read_text(encoding="utf-8")))
        else:
            # Not enough recordings yet, or a failure: keep the last lines as the reason.
            outcome.update(
                {
                    "accepted": False,
                    "registered": False,
                    "error": process.stdout[-300:] + process.stderr[-300:],
                }
            )
        state[kind] = current
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with (work / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        log(json.dumps({k: v for k, v in outcome.items() if k != "error"}, ensure_ascii=False))
        outcomes.append(outcome)
    return outcomes


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default=str(ROOT / "data/training"))
    p.add_argument("--work", default=str(ROOT / "data/training-runs"))
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--every", type=float, help="repeat every N minutes")
    args = p.parse_args()
    while True:
        run_once(Path(args.data), Path(args.work), args.epochs)
        if not args.every:
            return
        time.sleep(args.every * 60)


if __name__ == "__main__":
    main()
