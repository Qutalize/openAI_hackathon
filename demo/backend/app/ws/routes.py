import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.schemas.protocol import ClientEvent, parse_media
from app.services.rooms import Connection

router = APIRouter()


async def authenticate(ws, room_id):
    cfg = ws.app.state.settings
    if ws.headers.get("origin") not in {*cfg.server.allowed_origins, cfg.public_origin}:
        await ws.close(code=4403)
        return None
    try:
        return ws.app.state.rooms.authenticate(ws.cookies.get(cfg.security.cookie_name), room_id)
    except HTTPException:
        await ws.close(code=4401)
        return None


@router.websocket("/ws/rooms/{room_id}")
async def control(ws: WebSocket, room_id: str):
    s = await authenticate(ws, room_id)
    if s is None:
        return
    service = ws.app.state.rooms
    await ws.accept()
    connection = Connection(ws)
    if s.control:
        await s.control.close(4001)
    s.control = connection
    s.disconnected_at = None
    s.last_seen = time.time()
    await service.publish(room_id, "participant.joined", s.public(), s.participant_id)
    recent = []
    try:
        while s.control is connection:
            text = await ws.receive_text()
            service.authenticate(ws.cookies.get(ws.app.state.settings.security.cookie_name), room_id)
            if len(text.encode()) > 16384:
                await connection.close(1009)
                break
            now = time.time()
            recent = [t for t in recent if now - t < 1]
            if len(recent) >= 60:
                await connection.close(4429)
                break
            recent.append(now)
            request_id = None
            try:
                event = ClientEvent.model_validate_json(text)
                request_id = event.request_id
                await service.handle(s, event)
            except (ValueError, TypeError, KeyError, ValidationError) as exc:
                message = str(exc) if type(exc) is ValueError else "操作データが不正です"
                await service.private(s, "error", {"message": message, "retryable": True}, request_id)
    except (WebSocketDisconnect, RuntimeError, HTTPException):
        pass
    finally:
        if s.control is connection:
            s.control = None
            s.disconnected_at = time.time()
            await service.reset_input(s)
            if s.media:
                await s.media.close(4000)
            s.media = None
            await service.publish(room_id, "participant.updated", s.public(), s.participant_id)


@router.websocket("/ws/rooms/{room_id}/media")
async def media(ws: WebSocket, room_id: str):
    s = await authenticate(ws, room_id)
    if s is None or not s.control:
        if s is not None:
            await ws.close(code=4401)
        return
    await ws.accept()
    connection = Connection(ws)
    if s.media:
        await s.media.close(4001)
    s.media = connection
    service, cfg = ws.app.state.rooms, ws.app.state.settings
    try:
        while s.media is connection:
            data = await ws.receive_bytes()
            service.authenticate(ws.cookies.get(cfg.security.cookie_name), room_id)
            try:
                h, body = parse_media(data, cfg.server.websocket_max_message_bytes)
                if h["input_epoch"] != s.input_epoch or h["stream_id"] != s.stream_id:
                    continue
                if h["seq"] <= s.media_seq:
                    continue
                if h["seq"] != s.media_seq + 1 or h["capture_ms"] <= s.capture_ms:
                    raise ValueError("入力データが欠落しました。認識を再開してください")
                s.media_seq, s.capture_ms = h["seq"], h["capture_ms"]
                if h["kind"] == "audio.pcm":
                    if s.input != "speech" or not s.devices["microphone"]:
                        raise ValueError("発声入力が停止しています")
                    if not s.segmenter:
                        from app.inference.speech import SpeechSegmenter

                        s.segmenter = await asyncio.to_thread(
                            SpeechSegmenter, cfg.recognition.speech.model_dump()
                        )
                    epoch = s.input_epoch
                    completed, active, changed = await asyncio.to_thread(s.segmenter.feed, body)
                    if epoch != s.input_epoch:
                        continue
                    if changed:
                        await service.activity(s, active)
                    for pcm in completed:
                        service.launch_recognition(s, "speech", {"pcm": pcm})
                else:
                    if s.input not in ("lipread", "sign") or not s.devices["camera"] or not s.segment:
                        raise ValueError("撮影を開始してください")
                    c = getattr(cfg.recognition, s.input)
                    if h.get("schema") != c.feature_schema or h.get("segment_id") != s.segment["id"]:
                        raise ValueError("特徴点の方式または撮影区間が一致しません")
                    expected_k = 40 if s.input == "lipread" else 100
                    if body.shape[1] != expected_k:
                        raise ValueError("特徴点の数が一致しません")
                    times = h["frame_timestamps_ms"]
                    if s.segment["timestamps"] and times[0] <= s.segment["timestamps"][-1]:
                        raise ValueError("フレームの順序が不正です")
                    if len(s.segment["frames"]) + len(body) > c.max_frames:
                        raise ValueError("撮影時間の上限です")
                    s.segment["frames"].extend(body.tolist())
                    s.segment["timestamps"].extend(times)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                await service.reset_input(s)
                await service.private(
                    s,
                    "recognition.state",
                    {
                        "state": "error",
                        **s.stream(),
                        "message": "入力データを受け取れませんでした。撮影・マイクを再開してください",
                    },
                )
    except (WebSocketDisconnect, RuntimeError, HTTPException):
        pass
    except Exception:
        await service.private(
            s, "recognition.state", {"state": "error", "message": "音声認識の前処理を開始できません"}
        )
    finally:
        if s.media is connection:
            s.media = None
            await service.reset_input(s)
            await service.private(
                s, "recognition.state", {"state": "error", **s.stream(), "message": "認識接続が切れました"}
            )
