"""Spawn-safe process worker with bounded, fair scheduling and hard timeouts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import multiprocessing as mp
import queue
import sys
import time
from collections import OrderedDict, deque
from pathlib import Path


def verify_assets(root: Path, paths: list[Path]):
    records = {}
    # manifest.local.json (not in Git) holds models trained on this server.
    for name in ("manifest.json", "manifest.local.json"):
        path = root / "models" / name
        if path.is_file():
            records.update({a["path"]: a for a in json.loads(path.read_text(encoding="utf-8"))["assets"]})
    for path in paths:
        key = path.relative_to(root).as_posix()
        record = records.get(key)
        if not path.is_file() or not record or not record.get("sha256"):
            raise ValueError("model file or manifest hash missing")
        with path.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != record["sha256"]:
            raise ValueError("model checksum mismatch")


def failure_log(kind: str, exc: Exception) -> str:
    """Describe a failed job for the server log; the client only ever gets a generic message."""
    detail = getattr(exc, "stderr", None)
    if isinstance(detail, bytes):
        detail = detail.decode(errors="replace")
    # A model CLI's traceback ends with the actual cause, so keep the tail.
    tail = f"\n{detail.strip()[-2000:]}" if detail and detail.strip() else ""
    return f"recognition failed ({kind}): {exc!r}{tail}"


MODEL_KINDS = ("speech", "lipread", "sign", "lipread_open", "sign_open")
VIDEO_PROVIDERS = {"auto_avsr_cli", "uni_sign_cli"}


def unavailable(reason="モデル未導入"):
    return {"available": False, "reason": reason, "vocabulary": [], "transport": "features"}


def load_model(root: Path, kind: str, c: dict, vocabulary: dict):
    """Build, verify and warm one model; return (model, capability), or (None, capability) when absent."""
    # lipread_open / sign_open serve the same input as lipread / sign.
    base = kind.removesuffix("_open")
    if kind == "speech":
        path = root / c["model_path"]
        if not path.exists():
            return None, unavailable()
        from app.inference.speech import SpeechRecognizer

        # The vocabulary is .txt for older conversions and .json for large-v3 based ones,
        # which also ship the feature extractor settings.
        optional = [
            x
            for x in ("vocabulary.txt", "vocabulary.json", "preprocessor_config.json")
            if (path / x).is_file()
        ]
        verify_assets(root, [path / x for x in ("model.bin", "config.json", "tokenizer.json", *optional)])
        model = SpeechRecognizer(path, c)
    elif c["provider"] in VIDEO_PROVIDERS:
        if c["provider"] == "auto_avsr_cli":
            if base != "lipread":
                raise ValueError("Auto-AVSR is only available for lipread input")
            from app.inference.auto_avsr import AutoAvsrRecognizer

            model = AutoAvsrRecognizer(root, c)
        else:
            if base != "sign":
                raise ValueError("Uni-Sign is only available for sign input")
            from app.inference.uni_sign import UniSignRecognizer

            model = UniSignRecognizer(root, c)
    else:
        if kind != base:
            raise ValueError("Open-vocabulary slots take video models only")
        path = root / c["model_path"]
        if not path.exists():
            return None, unavailable()
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
    metadata = getattr(model, "metadata", {})
    return model, {
        "available": True,
        "reason": "利用可能",
        "vocabulary": (
            []
            if c["provider"] == "uni_sign_cli"
            else [x for x in vocabulary["items"] if base in x["modalities"]]
        ),
        "transport": "video" if c["provider"] in VIDEO_PROVIDERS else "features",
        "language_note": getattr(model, "language_note", ""),
        "model_version": metadata.get("model_version", c.get("model_version", "")),
    }


def process_main(root_string, config, incoming, outgoing):
    root = Path(root_string)
    models, capabilities = {}, {}
    vocabulary = json.loads((root / "config/vocabulary.ja.json").read_text(encoding="utf-8"))
    for kind in MODEL_KINDS:
        c = config.get(kind)
        if c is None:
            capabilities[kind] = unavailable("設定されていません")
            continue
        if not c["enabled"]:
            capabilities[kind] = unavailable("設定で無効になっています")
            continue
        try:
            model, capabilities[kind] = load_model(root, kind, c, vocabulary)
            if model is not None:
                models[kind] = model
        except Exception as exc:
            capabilities[kind] = unavailable(f"モデルを初期化できません ({type(exc).__name__})")
    outgoing.put({"capabilities": capabilities})
    while True:
        job = incoming.get()
        if job is None:
            break
        if job["kind"].startswith("reload:"):
            # Swap one retrained model in place; keep the old one if the new one does not load.
            kind = job["kind"].removeprefix("reload:")
            try:
                model, capability = load_model(root, kind, config[kind], vocabulary)
                if model is None:
                    raise ValueError("model file missing")
                old = models.get(kind)
                models[kind] = model
                if old is not None:
                    old.close()
                outgoing.put({"result": {"capability": capability}})
            except Exception as exc:
                print(failure_log(job["kind"], exc), file=sys.stderr, flush=True)
                outgoing.put({"error": type(exc).__name__})
            continue
        try:
            result = models[job["kind"]].recognize(job["segment"])
            outgoing.put({"result": result})
        except Exception as exc:
            print(failure_log(job["kind"], exc), file=sys.stderr, flush=True)
            outgoing.put({"error": type(exc).__name__})
    for model in models.values():
        model.close()


logger = logging.getLogger(__name__)
# Queue name for model reloads, and how often to look for retrained models.
RELOAD = "__models__"
MODEL_CHECK_SECONDS = 30


class InferenceBusy(Exception):
    pass


class InferenceService:
    def __init__(self, settings):
        self.settings = settings
        self.config = settings.recognition
        self.capabilities = {
            k: {"available": False, "reason": "モデル準備中", "vocabulary": [], "transport": "features"}
            for k in MODEL_KINDS
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
        self.watcher = asyncio.create_task(self.watch_models())

    def model_stamp(self, kind):
        """When the retrainable phrase model of an input last changed, or None."""
        c = getattr(self.config, kind)
        if not c.enabled or c.provider != "onnx_temporal_classifier":
            return None
        path = self.settings.path(c.metadata_path)
        return path.stat().st_mtime_ns if path.is_file() else None

    async def reload(self, kind):
        """Load a retrained model of one input inside the worker without stopping the others."""
        future = asyncio.get_running_loop().create_future()
        self.pending[RELOAD] = self.pending.get(RELOAD, 0) + 1
        self.queues.setdefault(RELOAD, deque()).append((f"reload:{kind}", {}, future, time.monotonic()))
        self.wake.set()
        result = await future
        self.capabilities = {**self.capabilities, kind: result["capability"]}
        return result["capability"]

    async def watch_models(self, interval=MODEL_CHECK_SECONDS):
        stamps = {k: self.model_stamp(k) for k in ("lipread", "sign")}
        while not self.closed:
            await asyncio.sleep(interval)
            for kind, before in stamps.items():
                stamp = self.model_stamp(kind)
                if stamp is None or stamp == before:
                    continue
                stamps[kind] = stamp
                try:
                    capability = await self.reload(kind)
                    logger.info("reloaded %s model %s", kind, capability.get("model_version"))
                except Exception as exc:
                    logger.warning("could not reload the %s model, keeping the previous one: %r", kind, exc)

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
        if getattr(self, "watcher", None):
            self.watcher.cancel()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for jobs in self.queues.values():
            for _, _, future, _ in jobs:
                future.cancel()
        self.queues.clear()
        self.stop_process()
