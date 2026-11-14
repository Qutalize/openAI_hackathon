import asyncio
import json
import queue
import threading

import app.inference.worker as worker
from app.core.config import load_settings


class Fake:
    def __init__(self, version):
        self.version, self.closed = version, False

    def recognize(self, segment):
        return {"candidates": [], "model_version": self.version}

    def close(self):
        self.closed = True


def test_reload_swaps_one_model_and_keeps_it_when_the_new_one_fails(monkeypatch):
    built = {"lipread": 0}
    loaded = []

    def fake_load(root, kind, c, vocabulary):
        if kind != "lipread":
            return None, worker.unavailable()
        built["lipread"] += 1
        if built["lipread"] == 3:
            raise ValueError("broken model")
        model = Fake(f"v{built['lipread']}")
        loaded.append(model)
        return model, {"available": True, "model_version": model.version}

    monkeypatch.setattr(worker, "load_model", fake_load)
    incoming, outgoing = queue.Queue(), queue.Queue()
    config = load_settings().recognition.model_dump()
    thread = threading.Thread(
        target=worker.process_main, args=(str(load_settings().root), config, incoming, outgoing)
    )
    thread.start()
    assert outgoing.get(timeout=5)["capabilities"]["lipread"]["model_version"] == "v1"

    def ask(kind, segment=None):
        incoming.put({"kind": kind, "segment": segment or {}})
        return outgoing.get(timeout=5)

    assert ask("lipread")["result"]["model_version"] == "v1"
    assert ask("reload:lipread")["result"]["capability"]["model_version"] == "v2"
    assert loaded[0].closed
    assert ask("lipread")["result"]["model_version"] == "v2"
    assert "error" in ask("reload:lipread")
    assert ask("lipread")["result"]["model_version"] == "v2"
    incoming.put(None)
    thread.join(timeout=5)


async def test_watcher_reloads_when_metadata_changes(tmp_path, monkeypatch):
    cfg = load_settings()
    meta = tmp_path / "metadata.json"
    cfg.recognition.lipread.metadata_path = str(meta)
    cfg.recognition.sign.enabled = False
    service = worker.InferenceService(cfg)
    reloads = []

    async def fake_reload(kind):
        reloads.append(kind)
        return {"model_version": "new"}

    monkeypatch.setattr(service, "reload", fake_reload)
    task = asyncio.create_task(service.watch_models(interval=0.01))
    await asyncio.sleep(0.05)
    assert reloads == []
    meta.write_text(json.dumps({"model_version": "new"}))
    await asyncio.sleep(0.05)
    assert reloads == ["lipread"]
    await asyncio.sleep(0.05)
    assert reloads == ["lipread"]
    service.closed = True
    task.cancel()
