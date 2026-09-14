import asyncio
import hmac
import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.security import digest, turn_credentials, verify_password
from app.repositories.rooms import normalize_room_id
from app.schemas.protocol import CreateRoomRequest, JoinRequest, RenameRequest

router = APIRouter()


def session_for(request):
    cfg = request.app.state.settings
    return request.app.state.rooms.authenticate(request.cookies.get(cfg.security.cookie_name))


def check_origin(request):
    cfg = request.app.state.settings
    if request.headers.get("origin") not in {*cfg.server.allowed_origins, cfg.public_origin}:
        raise HTTPException(403, "許可されていない接続元です")


def check_csrf(request, session):
    cfg = request.app.state.settings
    actual = digest(cfg.session_secret, request.headers.get("x-csrf-token", ""))
    if not hmac.compare_digest(actual, session.csrf_digest):
        raise HTTPException(403, "操作トークンが一致しません。画面を再読み込みしてください")


@router.get("/api/config")
async def public_config(request: Request):
    cfg = request.app.state.settings
    return {
        "name": cfg.app.name,
        "locale": cfg.app.locale,
        "modes": {k: v.model_dump() for k, v in cfg.modes.items()},
        "capabilities": request.app.state.inference.capabilities,
        "media": cfg.media.model_dump(),
        "output": cfg.output.model_dump(),
        "max_text_chars": cfg.room.max_text_chars,
        "heartbeat_seconds": cfg.server.heartbeat_seconds,
        "reconnect_grace_seconds": cfg.room.reconnect_grace_seconds,
        "recognition": {
            k: {"max_frames": getattr(cfg.recognition, k).max_frames} for k in ("lipread", "sign")
        },
    }


@router.post("/api/rooms", status_code=201)
async def create_room(body: CreateRoomRequest, request: Request):
    check_origin(request)
    cfg, service = request.app.state.settings, request.app.state.rooms
    # A fixed bucket prevents bypassing the creation limit by changing room IDs.
    service.rate_limit(request.client.host if request.client else "unknown", "__create__")
    try:
        return await asyncio.to_thread(
            service.repo.create,
            body.room_id,
            body.password,
            cfg.room.creation_ttl_seconds,
            cfg.room.max_participants,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, "このルームIDは既に使われています。別のIDで作成するか、既存ルームに参加してください"
        ) from None


@router.post("/api/rooms/{room_id}/join")
async def join(room_id: str, body: JoinRequest, request: Request, response: Response):
    check_origin(request)
    cfg, service = request.app.state.settings, request.app.state.rooms
    try:
        room_id = normalize_room_id(room_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    service.rate_limit(request.client.host if request.client else "unknown", room_id)
    room = service.repo.get(room_id)
    valid = await asyncio.to_thread(verify_password, body.password, room["password_hash"] if room else None)
    if not valid:
        raise HTTPException(401, cfg.security.join_failure_message)
    existing = request.cookies.get(cfg.security.cookie_name)
    if existing:
        try:
            old = service.authenticate(existing)
        except HTTPException:
            old = None
        if old:
            raise HTTPException(409, "このブラウザは既に参加しています。会話へ戻るか退出してください")
    await service.cleanup()
    s, token, csrf = service.join(room, body.mode, body.input, body.display_name, body.avatar)
    response.set_cookie(
        cfg.security.cookie_name,
        token,
        httponly=True,
        secure=cfg.security.cookie_secure,
        samesite="strict",
        path="/",
        max_age=cfg.room.session_ttl_seconds,
    )
    return {
        "participant_id": s.participant_id,
        "display_name": s.display_name,
        "avatar": s.avatar,
        "room_id": s.room_id,
        "mode": s.mode,
        "expires_at": s.expires_at,
        "csrf_token": csrf,
        **s.stream(),
    }


@router.get("/api/session")
async def session(request: Request):
    s = session_for(request)
    # Rotate CSRF on reload; only its digest is retained server-side.
    import secrets

    token = secrets.token_urlsafe(32)
    s.csrf_digest = digest(request.app.state.settings.session_secret, token)
    return {
        "participant_id": s.participant_id,
        "display_name": s.display_name,
        "avatar": s.avatar,
        "room_id": s.room_id,
        "mode": s.mode,
        "expires_at": s.expires_at,
        "csrf_token": token,
        **s.stream(),
    }


@router.patch("/api/session")
async def rename(body: RenameRequest, request: Request):
    check_origin(request)
    s = session_for(request)
    check_csrf(request, s)
    await request.app.state.rooms.rename(s, body.display_name)
    return {"display_name": s.display_name}


@router.delete("/api/session", status_code=204)
async def leave(request: Request):
    check_origin(request)
    cfg = request.app.state.settings
    try:
        s = session_for(request)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
    else:
        check_csrf(request, s)
        await request.app.state.rooms.remove(s)
    response = Response(status_code=204)
    response.delete_cookie(
        cfg.security.cookie_name,
        path="/",
        secure=cfg.security.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.post("/api/rooms/{room_id}/recognition/video", status_code=204)
async def upload_recognition_video(room_id: str, kind: str, segment_id: str, request: Request):
    """Attach a short camera clip to an active manual-recognition segment."""
    check_origin(request)
    s, cfg = session_for(request), request.app.state.settings
    check_csrf(request, s)
    if s.room_id != room_id or kind not in {"lipread", "sign"} or s.input != kind:
        raise HTTPException(403, "この認識入力は利用できません")
    recognition = getattr(cfg.recognition, kind)
    expected_provider = "auto_avsr_cli" if kind == "lipread" else "uni_sign_cli"
    if recognition.provider != expected_provider:
        raise HTTPException(409, "このモデルは動画アップロード方式ではありません")
    if not s.devices["camera"] or not s.segment or s.segment["id"] != segment_id:
        raise HTTPException(409, "撮影区間が見つかりません")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in {"video/webm", "video/mp4", "video/quicktime"}:
        raise HTTPException(415, "WebMまたはMP4動画を送信してください")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > recognition.max_upload_bytes:
            raise HTTPException(413, "撮影動画のサイズが上限を超えています")
        chunks.append(chunk)
    if not size:
        raise HTTPException(422, "撮影動画が空です")
    s.segment["video"] = b"".join(chunks)
    s.segment["content_type"] = content_type
    return Response(status_code=204)


@router.get("/api/rooms/{room_id}/snapshot")
async def snapshot(room_id: str, request: Request):
    s = session_for(request)
    if s.room_id != room_id:
        raise HTTPException(403, "このルームには参加していません")
    return request.app.state.rooms.snapshot(s)


@router.get("/api/rtc-config")
async def rtc_config(request: Request):
    s, cfg = session_for(request), request.app.state.settings
    servers = [{"urls": cfg.rtc.stun_urls}] if cfg.rtc.stun_urls else []
    expires = None
    if cfg.rtc.turn_enabled:
        if cfg.turn_username and cfg.turn_password:
            credentials = {"username": cfg.turn_username, "credential": cfg.turn_password}
        else:
            credentials = turn_credentials(
                cfg.turn_secret, s.participant_id, cfg.rtc.turn_credential_ttl_seconds
            )
            expires = credentials.pop("expires_at")
        servers.append({"urls": cfg.turn_urls, **credentials})
    return {"iceServers": servers, "iceTransportPolicy": cfg.rtc.ice_transport_policy, "expires_at": expires}


@router.get("/health/live")
async def live():
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request):
    with request.app.state.rooms.repo.connect() as db:
        db.execute("SELECT 1")
    return {"status": "ready", "capabilities": request.app.state.inference.capabilities}


@router.get("/api/metrics")
async def metrics(request: Request):
    session_for(request)
    if not request.app.state.settings.observability.metrics_enabled:
        raise HTTPException(404)
    service = request.app.state.inference
    return {**service.metrics, "pending_jobs": sum(service.pending.values())}
