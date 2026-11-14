"""Collect consented landmark recordings for training; video never reaches the server."""

import asyncio
import hmac
import json
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.inference.preprocessing import PREPROCESSING_VERSION, pack_frames

router = APIRouter()
SUBJECT = re.compile(r"^[a-zA-Z0-9_-]{2,40}$")
MAX_FRAMES = {"lipread": 64, "sign": 96}


class TrainingSample(BaseModel):
    version: int = 1
    subject_id: str
    label: str
    modality: str
    consent: bool
    created_at: str = Field(max_length=40)
    preprocessing_version: str
    mediapipe_version: str
    frames: list[list[list[float]]]
    timestamps: list[float]


def settings_for(request: Request):
    cfg = request.app.state.settings
    if not cfg.training.upload_enabled or not cfg.training_upload_token:
        raise HTTPException(404, "学習データの収集は有効になっていません")
    code = request.headers.get("x-training-code", "")
    if not hmac.compare_digest(code.encode(), cfg.training_upload_token.encode()):
        raise HTTPException(403, "収集コードが違います")
    return cfg


def vocabulary_for(root: Path, kind: str) -> list[dict]:
    vocabulary = json.loads((root / "config/vocabulary.ja.json").read_text(encoding="utf-8"))
    return [{"id": x["id"], "text": x["text"]} for x in vocabulary["items"] if kind in x["modalities"]]


def labels_for(root: Path, kind: str) -> list[str]:
    return [x["id"] for x in vocabulary_for(root, kind)] + ["unknown"]


def counts(root: Path, directory: Path, subject: str | None = None) -> dict:
    result = {}
    for kind in MAX_FRAMES:
        base = directory / kind
        per_label, people = {}, set()
        if base.is_dir():
            for path in base.glob("*/*.json"):
                people.add(path.parent.name)
                if subject and path.parent.name != subject:
                    continue
                label = path.name.split("--", 1)[0]
                per_label[label] = per_label.get(label, 0) + 1
        result[kind] = {
            "labels": per_label,
            "subjects": len(people),
            "vocabulary": vocabulary_for(root, kind),
        }
    return result


@router.get("/api/training/status")
async def status(request: Request, subject: str | None = None):
    cfg = settings_for(request)
    if subject is not None and not SUBJECT.match(subject):
        raise HTTPException(422, "人物IDは英数字・-・_の2〜40文字です")
    return await asyncio.to_thread(counts, cfg.root, cfg.path(cfg.training.directory), subject)


@router.post("/api/training/samples", status_code=201)
async def upload(sample: TrainingSample, request: Request):
    cfg = settings_for(request)
    kind = sample.modality
    if kind not in MAX_FRAMES:
        raise HTTPException(422, "入力方式が不正です")
    if not sample.consent:
        raise HTTPException(422, "本人の同意がない収録は保存できません")
    if not SUBJECT.match(sample.subject_id):
        raise HTTPException(422, "人物IDは英数字・-・_の2〜40文字です")
    if sample.label not in labels_for(cfg.root, kind):
        raise HTTPException(422, "語彙にない表現です")
    if sample.preprocessing_version != PREPROCESSING_VERSION:
        raise HTTPException(422, "特徴点の形式が古いです。画面を再読み込みしてください")
    try:
        _, _, ratio = pack_frames(sample.frames, sample.timestamps, MAX_FRAMES[kind], kind)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if ratio < cfg.training.min_valid_frame_ratio[kind]:
        raise HTTPException(422, "特徴点が途切れました。顔や手が映る位置で、もう一度お願いします")
    folder = cfg.path(cfg.training.directory) / kind / sample.subject_id
    if folder.is_dir() and sum(1 for _ in folder.glob("*.json")) >= cfg.training.max_samples_per_subject:
        raise HTTPException(429, "この人物IDの収録数が上限に達しました")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sample.label}--{time.time_ns()}.json"
    await asyncio.to_thread(path.write_text, sample.model_dump_json(), "utf-8")
    return {"valid_ratio": ratio, "saved": path.name}


@router.delete("/api/training/subjects/{subject}", status_code=204)
async def delete_subject(subject: str, request: Request):
    cfg = settings_for(request)
    if not SUBJECT.match(subject):
        raise HTTPException(422, "人物IDは英数字・-・_の2〜40文字です")
    for kind in MAX_FRAMES:
        folder = cfg.path(cfg.training.directory) / kind / subject
        if folder.is_dir():
            for path in folder.glob("*.json"):
                path.unlink()
            folder.rmdir()
