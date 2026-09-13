import base64
import binascii
import json
import math
import struct
import unicodedata
from typing import Any, Literal

import numpy as np
from pydantic import Field, field_validator

from app.core.config import Input, Mode, StrictModel


class JoinRequest(StrictModel):
    password: str = Field(min_length=1, max_length=128)
    mode: Mode
    input: Input
    display_name: str = Field(default="", max_length=40)
    avatar: str = Field(default="", max_length=65536)

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value):
        if not value:
            return value
        try:
            if not value.startswith("data:image/png;base64,"):
                raise ValueError()
            data = base64.b64decode(value.split(",", 1)[1], validate=True)
            if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[8:16] != b"\x00\x00\x00\rIHDR":
                raise ValueError()
            width, height = struct.unpack(">II", data[16:24])
            if not 1 <= width <= 96 or not 1 <= height <= 96:
                raise ValueError()
        except (ValueError, binascii.Error):
            raise ValueError("アイコン画像が不正です。画像を選び直してください") from None
        return value

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value):
        return validate_display_name(value) if value.strip() else ""


def validate_display_name(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 40 or any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("名前は制御文字を含まない1〜40文字で入力してください")
    return value


class RenameRequest(StrictModel):
    display_name: str = Field(min_length=1, max_length=40)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value):
        return validate_display_name(value)


class CreateRoomRequest(StrictModel):
    room_id: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class ClientEvent(StrictModel):
    version: Literal[1]
    type: str = Field(max_length=64)
    request_id: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = {}


def parse_media(data: bytes, limit: int):
    if len(data) < 5 or len(data) > limit:
        raise ValueError("メディアメッセージのサイズが不正です")
    header_size = struct.unpack_from("<I", data)[0]
    if not 1 <= header_size <= 2048 or header_size + 4 > len(data):
        raise ValueError("メディアヘッダーが不正です")
    h = json.loads(data[4 : 4 + header_size])
    if not isinstance(h, dict) or h.get("version") != 1:
        raise ValueError("メディアバージョンが不正です")
    for key in ("input_epoch", "seq"):
        if type(h.get(key)) is not int or not 0 <= h[key] <= 2**32 - 1:
            raise ValueError("メディア連番が不正です")
    if not isinstance(h.get("stream_id"), str) or len(h["stream_id"]) > 100:
        raise ValueError("ストリームIDが不正です")
    t = h.get("capture_ms")
    if type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t < 2**53:
        raise ValueError("メディア時刻が不正です")
    body = data[4 + header_size :]
    if h.get("kind") == "audio.pcm":
        if len(body) != 6400:
            raise ValueError("PCMは16kHz mono 200msで送信してください")
        return h, body
    if h.get("kind") != "vision.features":
        raise ValueError("入力方式が不正です")
    shape = h.get("shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 3
        or any(type(n) is not int for n in shape)
        or not 1 <= shape[0] <= 5
        or shape[1] not in (40, 100)
        or shape[2] != 4
    ):
        raise ValueError("特徴点shapeが不正です")
    if len(body) != math.prod(shape) * 4:
        raise ValueError("特徴点データ長が不正です")
    times = h.get("frame_timestamps_ms")
    if (
        not isinstance(times, list)
        or len(times) != shape[0]
        or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times)
        or any(a >= b for a, b in zip(times, times[1:]))
    ):
        raise ValueError("フレーム時刻が不正です")
    a = np.frombuffer(body, dtype="<f4").reshape(shape)
    if (
        not np.isfinite(a).all()
        or np.any(np.abs(a[:, :, :3]) > 100)
        or np.any((a[:, :, 3] != 0) & (a[:, :, 3] != 1))
    ):
        raise ValueError("特徴点値が不正です")
    return h, a.copy()
