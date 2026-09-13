from __future__ import annotations

import asyncio
import secrets
import time
from datetime import datetime, timezone

from fastapi import HTTPException, WebSocketDisconnect

from app.core.security import digest
from app.inference.worker import InferenceBusy
from app.models.session import RoomState, Session, uid


class Connection:
    def __init__(self, ws):
        self.ws = ws
        self.lock = asyncio.Lock()

    async def send(self, event):
        try:
            async with self.lock:
                await asyncio.wait_for(self.ws.send_json(event), timeout=2)
        except (RuntimeError, OSError, TimeoutError, WebSocketDisconnect):
            pass

    async def close(self, code=1000):
        try:
            await self.ws.close(code=code)
        except (RuntimeError, OSError, WebSocketDisconnect):
            pass


class RoomService:
    def __init__(self, settings, repo, inference):
        self.settings, self.repo, self.inference = settings, repo, inference
        self.rooms: dict[str, RoomState] = {}
        self.sessions: dict[str, Session] = {}
        self.attempts = {}

    def rate_limit(self, ip, room_id):
        now = time.time()
        for key, limit in (
            (f"ip:{ip}", self.settings.security.join_attempts_per_minute * 4),
            (f"room:{ip}:{room_id}", self.settings.security.join_attempts_per_minute),
        ):
            entries = [t for t in self.attempts.get(key, []) if now - t < 60]
            self.attempts[key] = entries
            if len(entries) >= limit:
                raise HTTPException(429, "試行回数が多いため、1分後に再試行してください")
            entries.append(now)

    def authenticate(self, token, room_id=None):
        session = self.sessions.get(digest(self.settings.session_secret, token or ""))
        if (
            not session
            or session.expires_at <= time.time()
            or (
                session.disconnected_at is not None
                and time.time() - session.disconnected_at > self.settings.room.reconnect_grace_seconds
            )
        ):
            raise HTTPException(401, "セッションが切れました。再入室してください")
        if room_id and session.room_id != room_id:
            raise HTTPException(403, "このルームには参加していません")
        return session

    def join(self, room, mode, input_kind, display_name="", avatar=""):
        allowed = self.settings.modes[mode].allowed_inputs
        if input_kind not in allowed:
            raise HTTPException(422, "このモードでは利用できない入力方式です")
        if input_kind != "text" and not self.inference.capabilities[input_kind]["available"]:
            raise HTTPException(409, "選択したモデルは未導入です。文字入力を選択してください")
        state = self.rooms.setdefault(room["id"], RoomState())
        if len(state.participants) >= min(room["max_participants"], self.settings.room.max_participants):
            raise HTTPException(409, "ルームが満員です")
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        used = {s.display_name.casefold() for s in state.participants.values()}
        if display_name and display_name.casefold() in used:
            raise HTTPException(409, "その名前は参加者が使用しています。別の名前を入力してください")
        name = display_name or next(
            f"ユーザー{chr(65 + n)}" for n in range(4) if f"ユーザー{chr(65 + n)}".casefold() not in used
        )
        s = Session(
            participant_id=uid(),
            room_id=room["id"],
            display_name=name,
            avatar=avatar,
            mode=mode,
            input=input_kind,
            token_digest=digest(self.settings.session_secret, token),
            csrf_digest=digest(self.settings.session_secret, csrf),
            expires_at=min(room["expires_at"], time.time() + self.settings.room.session_ttl_seconds),
            output=list(self.settings.modes[mode].output),
        )
        state.participants[s.participant_id] = s
        if avatar:
            state.avatars[s.participant_id] = avatar
        state.empty_since = None
        self.sessions[s.token_digest] = s
        return s, token, csrf

    async def rename(self, session, display_name):
        state = self.rooms[session.room_id]
        if any(
            p is not session and p.display_name.casefold() == display_name.casefold()
            for p in state.participants.values()
        ):
            raise HTTPException(409, "その名前は参加者が使用しています。別の名前を入力してください")
        session.display_name = display_name
        for utterance in state.utterances:
            if utterance["participant_id"] == session.participant_id:
                utterance["display_name"] = display_name
        await self.publish(session.room_id, "participant.updated", session.public(), session.participant_id)

    def snapshot(self, s):
        state = self.rooms[s.room_id]
        self.prune_avatars(state)
        return {
            "participants": [p.public() for p in state.participants.values()],
            "avatars": dict(state.avatars),
            "utterances": list(state.utterances),
            "last_server_seq": state.seq,
            "speaker_id": state.speaker,
            "self": {**s.public(), **s.stream(), "output": s.output},
        }

    def prune_avatars(self, state):
        # Keep departed speakers' icons only while their messages remain in history.
        visible = set(state.participants) | {u["participant_id"] for u in state.utterances}
        state.avatars = {key: value for key, value in state.avatars.items() if key in visible}

    async def private(self, s, kind, payload, request_id=None):
        if s.control:
            await s.control.send({"version": 1, "type": kind, "payload": payload, "request_id": request_id})

    async def publish(self, room_id, kind, payload, participant_id=None):
        state = self.rooms.get(room_id)
        if not state:
            return
        state.seq += 1
        now = time.time()
        event = {
            "version": 1,
            "type": kind,
            "event_id": uid(),
            "server_seq": state.seq,
            "room_id": room_id,
            "participant_id": participant_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        state.replay = [(t, e) for t, e in state.replay if now - t < self.settings.room.event_replay_seconds]
        state.replay.append((now, event))
        state.replay = state.replay[-2000:]
        await asyncio.gather(*(s.control.send(event) for s in list(state.participants.values()) if s.control))

    async def reset_input(self, s):
        s.input_epoch += 1
        s.stream_id = uid()
        s.media_seq, s.capture_ms = -1, -1
        s.segment, s.segmenter = None, None
        s.candidates.clear()
        for task in list(s.tasks):
            task.cancel()
        s.recognition_jobs = 0
        await self.activity(s, False)
        await self.publish_activity(s)

    async def publish_activity(self, s):
        await self.publish(
            s.room_id,
            "participant.activity",
            {
                "id": s.participant_id,
                "speaking": s.active_since is not None,
                "recognizing": s.recognition_jobs > 0,
            },
            s.participant_id,
        )

    async def activity(self, s, active):
        changed = active != (s.active_since is not None)
        if active and s.active_since is None:
            s.active_since = time.time()
        if not active:
            s.active_since = None
        if changed:
            await self.publish_activity(s)
        await self.choose_speaker(s.room_id)

    async def choose_speaker(self, room_id):
        state = self.rooms.get(room_id)
        if not state:
            return
        old = state.participants.get(state.speaker)
        if old and (old.active_since is not None or time.time() - state.speaker_since < 2):
            return
        candidates = [s for s in state.participants.values() if s.active_since is not None]
        speaker = min(candidates, key=lambda s: s.active_since).participant_id if candidates else None
        if speaker != state.speaker:
            state.speaker, state.speaker_since = speaker, time.time()
            await self.publish(room_id, "speaker.changed", {"participant_id": speaker})

    async def remove(self, s):
        if s.token_digest not in self.sessions:
            return
        self.sessions.pop(s.token_digest, None)
        await self.reset_input(s)
        for connection in (s.control, s.media):
            if connection:
                await connection.close()
        s.control = s.media = None
        state = self.rooms.get(s.room_id)
        if state:
            state.participants.pop(s.participant_id, None)
            self.prune_avatars(state)
            if not state.participants:
                state.empty_since = time.time()
            await self.publish(
                s.room_id,
                "participant.left",
                {"participant_id": s.participant_id, "display_name": s.display_name},
            )
            await self.choose_speaker(s.room_id)

    async def cleanup(self):
        now = time.time()
        for s in list(self.sessions.values()):
            if s.expires_at <= now or (
                s.disconnected_at is not None
                and now - s.disconnected_at >= self.settings.room.reconnect_grace_seconds
            ):
                await self.remove(s)
            elif s.control and now - s.last_seen > self.settings.server.disconnect_timeout_seconds:
                await s.control.close(4000)
            s.candidates = {k: v for k, v in s.candidates.items() if v["expires_at"] > now}
            s.requests = {k: v for k, v in s.requests.items() if now - v[0] < 60}
            if s.segment and now - s.segment["started_at"] > 7:
                await self.reset_input(s)
                await self.private(
                    s,
                    "recognition.state",
                    {"state": "error", "message": "撮影区間が期限切れです", **s.stream()},
                )
        for room_id, state in list(self.rooms.items()):
            state.replay = [
                (t, e) for t, e in state.replay if now - t < self.settings.room.event_replay_seconds
            ]
            if state.empty_since and now - state.empty_since >= self.settings.room.empty_room_cleanup_seconds:
                del self.rooms[room_id]
            else:
                await self.choose_speaker(room_id)
        self.attempts = {
            k: [t for t in v if now - t < 60] for k, v in self.attempts.items() if v and now - v[-1] < 60
        }

    async def finalize(self, s, text, source, confirmed, model_version=None):
        text = self.validate_text(text)
        u = {
            "utterance_id": uid(),
            "participant_id": s.participant_id,
            "display_name": s.display_name,
            "revision": 1,
            "source": source,
            "text": text,
            "confirmed_by_user": confirmed,
            "model_version": model_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "replayed": False,
        }
        state = self.rooms[s.room_id]
        state.utterances.append(u)
        state.utterances = state.utterances[-self.settings.room.max_transcript_entries :]
        self.prune_avatars(state)
        await self.publish(s.room_id, "utterance.final", u.copy(), s.participant_id)
        return {"utterance_id": u["utterance_id"]}

    def validate_text(self, text):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= self.settings.room.max_text_chars:
            raise ValueError("本文は1〜500文字で入力してください")
        return text.strip()

    def launch_recognition(self, s, kind, segment):
        epoch = s.input_epoch

        async def run():
            if s.input_epoch != epoch or s.token_digest not in self.sessions or not s.control:
                return
            s.recognition_jobs += 1
            try:
                await self.publish_activity(s)
                await self.private(s, "recognition.state", {"state": "processing", "input": kind})
                result = await self.inference.recognize(s.participant_id, kind, segment)
                if s.input_epoch != epoch or s.token_digest not in self.sessions or not s.control:
                    return
                if kind == "speech":
                    if result.get("text"):
                        await self.finalize(
                            s,
                            result["text"][: self.settings.room.max_text_chars],
                            kind,
                            False,
                            result["model_version"],
                        )
                    await self.private(s, "recognition.state", {"state": "idle"})
                else:
                    candidate_id = uid()
                    candidates = result.get("candidates", [])
                    s.candidates[candidate_id] = {
                        **result,
                        "source": kind,
                        "epoch": epoch,
                        "expires_at": time.time() + 60,
                    }
                    await self.private(
                        s,
                        "recognition.candidate",
                        {
                            "candidate_id": candidate_id,
                            "candidates": candidates,
                            "input": kind,
                            "expires_in": 60,
                            "message": "候補を確認して送信してください"
                            if candidates
                            else "認識できませんでした",
                        },
                    )
            except InferenceBusy:
                await self.private(
                    s, "recognition.busy", {"message": "認識が混み合っています。区間をやり直してください"}
                )
            except asyncio.CancelledError:
                pass
            except Exception:
                await self.private(
                    s,
                    "recognition.state",
                    {"state": "error", "message": "認識できませんでした。再試行してください"},
                )
            finally:
                if s.input_epoch == epoch:
                    s.recognition_jobs = max(0, s.recognition_jobs - 1)
                    await self.publish_activity(s)

        task = asyncio.create_task(run())
        s.tasks.add(task)
        task.add_done_callback(s.tasks.discard)

    async def handle(self, s, event):
        p, kind = event.payload, event.type
        cached = s.requests.get(event.request_id)
        if cached and time.time() - cached[0] < 60:
            await self.private(s, "ack", cached[1], event.request_id)
            return
        result = {}
        if kind in ("ping", "pong"):
            s.last_seen = time.time()
            await self.private(s, "pong", {}, event.request_id)
            return
        if kind == "session.resume":
            last = p.get("last_server_seq", 0)
            if type(last) is not int or last < 0:
                raise ValueError("再接続位置が不正です")
            state = self.rooms[s.room_id]
            if last and state.replay and state.replay[0][1]["server_seq"] <= last + 1 <= state.seq + 1:
                for _, replay in state.replay:
                    if replay["server_seq"] > last:
                        await s.control.send({**replay, "payload": {**replay["payload"], "replayed": True}})
            # Snapshot is authoritative for devices, identities, and expired history.
            await self.private(s, "room.snapshot", self.snapshot(s))
            result = s.stream()
        elif kind == "device.update":
            if set(p) - {"microphone", "camera"} or any(type(v) is not bool for v in p.values()):
                raise ValueError("デバイス状態が不正です")
            if p.get("microphone") and s.input != "speech":
                raise ValueError("発声入力を選択してください")
            s.devices.update(p)
            await self.reset_input(s)
            await self.publish(s.room_id, "participant.updated", s.public(), s.participant_id)
            result = s.stream()
        elif kind == "input.update":
            selected = p.get("input")
            if selected not in self.settings.modes[s.mode].allowed_inputs:
                raise ValueError("このモードでは利用できない入力方式です")
            if selected != "text" and not self.inference.capabilities[selected]["available"]:
                raise ValueError("認識モデルが利用できません")
            s.input = selected
            if selected != "speech":
                s.devices["microphone"] = False
            await self.reset_input(s)
            await self.publish(s.room_id, "participant.updated", s.public(), s.participant_id)
            result = s.stream()
        elif kind == "preferences.update":
            output = p.get("output")
            if not isinstance(output, list) or not output or set(output) - {"audio", "text"}:
                raise ValueError("出力方式が不正です")
            s.output = list(dict.fromkeys(output))
        elif kind.startswith("rtc."):
            if kind not in ("rtc.offer", "rtc.answer", "rtc.ice"):
                raise ValueError("シグナリング方式が不正です")
            target = self.rooms[s.room_id].participants.get(p.get("target_id"))
            if not target or target is s or not target.control:
                raise ValueError("接続先が見つかりません")
            signal = p.get("description") if kind != "rtc.ice" else p.get("candidate")
            if not isinstance(signal, dict):
                raise ValueError("シグナリングデータが不正です")
            await self.private(target, kind, {**p, "from_id": s.participant_id})
        elif kind == "segment.start":
            if s.input not in ("lipread", "sign") or not s.devices["camera"] or not s.media:
                raise ValueError("カメラと認識接続を確認してください")
            if s.segment:
                raise ValueError("既に撮影中です")
            segment_id = p.get("segment_id")
            if not isinstance(segment_id, str) or not 1 <= len(segment_id) <= 100:
                raise ValueError("撮影区間IDが不正です")
            s.segment = {"id": segment_id, "started_at": time.time(), "frames": [], "timestamps": []}
            s.candidates.clear()
            await self.activity(s, True)
            result = {"segment_id": segment_id}
        elif kind == "segment.cancel":
            await self.reset_input(s)
            result = s.stream()
        elif kind == "segment.end":
            segment = s.segment
            if (
                not segment
                or segment["id"] != p.get("segment_id")
                or type(p.get("last_media_seq")) is not int
            ):
                raise ValueError("撮影区間が見つかりません")
            deadline = time.monotonic() + 1
            epoch = s.input_epoch
            while (
                s.media_seq < p["last_media_seq"] and time.monotonic() < deadline and epoch == s.input_epoch
            ):
                await asyncio.sleep(0.01)
            if s.segment is not segment or s.media_seq != p["last_media_seq"]:
                await self.reset_input(s)
                raise ValueError("撮影データが不足しています。撮り直してください")
            s.segment = None
            await self.activity(s, False)
            self.launch_recognition(s, s.input, segment)
        elif kind == "utterance.submit":
            text = self.validate_text(p.get("text"))
            source, version = "text", None
            candidate_id = p.get("candidate_id")
            if candidate_id:
                candidate = s.candidates.get(candidate_id)
                if (
                    not candidate
                    or candidate["expires_at"] <= time.time()
                    or candidate["epoch"] != s.input_epoch
                ):
                    raise ValueError("候補の期限が切れました。文字入力として送信するか再認識してください")
                source, version = candidate["source"], candidate["model_version"]
                s.candidates.pop(candidate_id)
            result = await self.finalize(s, text, source, True, version)
        elif kind == "utterance.correct":
            text = self.validate_text(p.get("text"))
            utterance = next(
                (u for u in self.rooms[s.room_id].utterances if u["utterance_id"] == p.get("utterance_id")),
                None,
            )
            if not utterance or utterance["participant_id"] != s.participant_id:
                raise ValueError("自分の発言だけ修正できます")
            if p.get("revision") != utterance["revision"]:
                raise ValueError("発言が更新されています。最新の内容を確認してください")
            utterance.update(text=text, revision=utterance["revision"] + 1, confirmed_by_user=True)
            await self.publish(s.room_id, "utterance.corrected", utterance.copy(), s.participant_id)
        else:
            raise ValueError("未対応の操作です")
        s.requests[event.request_id] = (time.time(), result)
        # Bound idempotency memory even if a client sends many unique commands.
        if len(s.requests) > 1000:
            del s.requests[next(iter(s.requests))]
        await self.private(s, "ack", result, event.request_id)
