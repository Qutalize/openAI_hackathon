"""Spawn-safe process worker with bounded, fair scheduling and hard timeouts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing as mp
import queue
import time
from collections import OrderedDict, deque
from pathlib import Path


def verify_assets(root: Path, paths: list[Path]):
    manifest = json.loads((root / "models/manifest.json").read_text(encoding="utf-8"))
    records = {a["path"]: a for a in manifest["assets"]}
    for path in paths:
        key = path.relative_to(root).as_posix()
        record = records.get(key)
        if not path.is_file() or not record or not record.get("sha256"):
            raise ValueError("model file or manifest hash missing")
        with path.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != record["sha256"]:
            raise ValueError("model checksum mismatch")


def process_main(root_string, config, incoming, outgoing):
    root = Path(root_string)
    models, capabilities = {}, {}
    vocabulary = json.loads((root / "config/vocabulary.ja.json").read_text(encoding="utf-8"))
    for kind in ("speech", "lipread", "sign"):
        c = config[kind]
        capabilities[kind] = {
            "available": False,
            "reason": "モデル未導入",
            "vocabulary": [],
            "transport": "features",
        }
        if not c["enabled"]:
            capabilities[kind]["reason"] = "設定で無効になっています"
            continue
        try:
            if kind == "speech":
                path = root / c["model_path"]
                if not path.exists():
                    continue
                from app.inference.speech import SpeechRecognizer

                verify_assets(
                    root, [path / x for x in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")]
                )
                model = SpeechRecognizer(path, c)
            elif c["provider"] in {"auto_avsr_cli", "uni_sign_cli"}:
                if c["provider"] == "auto_avsr_cli":
                    if kind != "lipread":
                        raise ValueError("Auto-AVSR is only available for lipread input")
                    from app.inference.auto_avsr import AutoAvsrRecognizer

                    model = AutoAvsrRecognizer(root, c)
                else:
                    if kind != "sign":
                        raise ValueError("Uni-Sign is only available for sign input")
                    from app.inference.uni_sign import UniSignRecognizer

                    model = UniSignRecognizer(root, c)
                capabilities[kind]["transport"] = "video"
            else:
                path = root / c["model_path"]
                if not path.exists():
                    continue
                from app.inference.lipread import TemporalRecognizer

                meta = root / c["metadata_path"]
                assets = root / "frontend/public/models/mediapipe"
                needed = [assets / "face_landmarker.task"]
                wasm_files = list((assets / "wasm").glob("*.wasm"))
                if not wasm_files:
                    raise ValueError("MediaPipe WASM assets missing")
                needed.extend(wasm_files)
                if kind == "sign":
                    needed += [assets / "hand_landmarker.task", assets / "pose_landmarker.task"]
                verify_assets(root, [path, meta, meta.parent / "labels.json", *needed])
                model = TemporalRecognizer(path, meta, c, kind, vocabulary)
            model.warmup()
            models[kind] = model
            capabilities[kind] = {
                "available": True,
                "reason": "利用可能",
                "vocabulary": (
                    []
                    if c["provider"] == "uni_sign_cli"
                    else [x for x in vocabulary["items"] if kind in x["modalities"]]
                ),
                "transport": (
                    "video" if c["provider"] in {"auto_avsr_cli", "uni_sign_cli"} else "features"
                ),
                "language_note": getattr(model, "language_note", ""),
            }
        except Exception as exc:
            capabilities[kind]["reason"] = f"モデルを初期化できません ({type(exc).__name__})"
    outgoing.put({"capabilities": capabilities})
    while True:
        job = incoming.get()
        if job is None:
            break
        try:
            result = models[job["kind"]].recognize(job["segment"])
            outgoing.put({"result": result})
        except Exception as exc:
            outgoing.put({"error": type(exc).__name__})
    for model in models.values():
        model.close()


class InferenceBusy(Exception):
    pass


class InferenceService:
    def __init__(self, settings):
        self.settings = settings
        self.config = settings.recognition
        self.capabilities = {
            k: {"available": False, "reason": "モデル準備中", "vocabulary": [], "transport": "features"}
            for k in ("speech", "lipread", "sign")
        }
        self.queues = OrderedDict()
        self.pending = {}
        self.wake = asyncio.Event()
        self.process = None
        self.task = None
        self.closed = False
        self.metrics = {"completed": 0, "failed": 0, "busy": 0, "total_seconds": 0.0}

    async def start(self):
        await self.spawn()
        self.task = asyncio.create_task(self.consume())

    async def spawn(self):
        context = mp.get_context("spawn")
        self.incoming, self.outgoing = context.Queue(1), context.Queue(1)
        self.process = context.Process(
            target=process_main,
            args=(str(self.settings.root), self.config.model_dump(), self.incoming, self.outgoing),
            daemon=True,
        )
        self.process.start()
        try:
            ready = await asyncio.to_thread(self.outgoing.get, True, 120)
            self.capabilities = ready["capabilities"]
        except queue.Empty:
            self.stop_process()
            self.capabilities = {
                k: {
                    "available": False,
                    "reason": "モデル初期化がタイムアウトしました",
                    "vocabulary": [],
                    "transport": "features",
                }
                for k in self.capabilities
            }

    def stop_process(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
        for name in ("incoming", "outgoing"):
            q = getattr(self, name, None)
            if q is not None:
                q.cancel_join_thread()
                q.close()

    async def recognize(self, participant: str, kind: str, segment: dict):
        if not self.capabilities[kind]["available"]:
            raise ValueError("認識モデルが利用できません")
        if (
            self.pending.get(participant, 0) >= self.config.max_pending_jobs_per_participant
            or sum(self.pending.values()) >= self.config.max_pending_jobs_total
        ):
            self.metrics["busy"] += 1
            raise InferenceBusy()
        future = asyncio.get_running_loop().create_future()
        self.pending[participant] = self.pending.get(participant, 0) + 1
        self.queues.setdefault(participant, deque()).append((kind, segment, future, time.monotonic()))
        self.wake.set()
        return await future

    async def consume(self):
        while not self.closed:
            await self.wake.wait()
            if not self.queues:
                self.wake.clear()
                continue
            participant, jobs = self.queues.popitem(last=False)
            kind, segment, future, enqueued = jobs.popleft()
            if jobs:
                self.queues[participant] = jobs
            started = time.monotonic()
            try:
                if future.cancelled():
                    continue
                remaining = self.config.job_timeout_seconds - (started - enqueued)
                if remaining <= 0:
                    raise TimeoutError("認識の待ち時間を超えました")
                if self.process is None or not self.process.is_alive():
                    raise RuntimeError("推論ワーカーが停止しています")
                self.incoming.put_nowait({"kind": kind, "segment": segment})
                try:
                    reply = await asyncio.to_thread(self.outgoing.get, True, remaining)
                except queue.Empty:
                    self.stop_process()
                    await self.spawn()
                    raise TimeoutError("認識がタイムアウトしました") from None
                if "error" in reply:
                    raise ValueError("認識できませんでした。撮影位置を確認して再試行してください")
                if not future.done():
                    future.set_result(reply["result"])
                self.metrics["completed"] += 1
            except Exception as exc:
                self.metrics["failed"] += 1
                if not future.done():
                    future.set_exception(exc)
            finally:
                self.pending[participant] -= 1
                if self.pending[participant] == 0:
                    del self.pending[participant]
                self.metrics["total_seconds"] += time.monotonic() - started

    async def close(self):
        self.closed = True
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for jobs in self.queues.values():
            for _, _, future, _ in jobs:
                future.cancel()
        self.queues.clear()
        self.stop_process()
