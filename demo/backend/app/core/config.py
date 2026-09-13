from __future__ import annotations

import copy
import os
import secrets
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[3]
Input = Literal["speech", "lipread", "sign", "text"]
Mode = Literal["standard", "vision_support", "hearing_support"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AppConfig(StrictModel):
    name: str
    locale: str = "ja-JP"
    environment: Literal["development", "production", "test"] = "development"


class ServerConfig(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)
    workers: Literal[1] = 1
    allowed_origins: list[str]
    websocket_max_message_bytes: int = Field(65536, ge=8192, le=65536)
    heartbeat_seconds: int = Field(15, ge=1)
    disconnect_timeout_seconds: int = Field(45, ge=2)
    serve_frontend: bool = False
    frontend_dist: str = "frontend/dist"


class RoomConfig(StrictModel):
    max_participants: int = Field(4, ge=1, le=4)
    creation_ttl_seconds: int = Field(86400, ge=60)
    session_ttl_seconds: int = Field(7200, ge=60)
    reconnect_grace_seconds: int = Field(60, ge=1)
    event_replay_seconds: int = Field(60, ge=1)
    max_transcript_entries: int = Field(500, ge=1, le=10000)
    empty_room_cleanup_seconds: int = Field(60, ge=1)
    max_text_chars: int = Field(500, ge=1, le=500)


class SecurityConfig(StrictModel):
    cookie_name: str = "conversation_session"
    cookie_secure: bool = False
    cookie_samesite: Literal["strict"] = "strict"
    join_attempts_per_minute: int = Field(5, ge=1)
    join_failure_message: str = "ルームIDまたはパスワードを確認してください"


class MediaConfig(StrictModel):
    video_width: int = Field(1280, ge=320)
    video_height: int = Field(720, ge=240)
    video_fps: int = Field(30, ge=1, le=60)
    audio_sample_rate: Literal[16000] = 16000
    audio_channels: Literal[1] = 1
    audio_chunk_ms: Literal[200] = 200
    echo_cancellation: bool = True
    noise_suppression: bool = True
    vision_fps: Literal[20] = 20
    feature_batch_frames: int = Field(5, ge=1, le=5)
    camera_off_stops_capture: Literal[True] = True


class RTCConfig(StrictModel):
    topology: Literal["mesh"] = "mesh"
    ice_transport_policy: Literal["all", "relay"] = "all"
    stun_urls: list[str] = []
    turn_enabled: bool = False
    turn_credential_ttl_seconds: int = Field(600, ge=60)


class SpeechConfig(StrictModel):
    enabled: bool = True
    provider: Literal["faster_whisper"] = "faster_whisper"
    model_path: str
    device: Literal["cpu", "cuda"] = "cpu"
    compute_type: str = "int8"
    beam_size: int = Field(1, ge=1, le=10)
    vad_silence_ms: int = Field(600, ge=200)
    min_segment_ms: int = Field(300, ge=100)
    max_segment_ms: int = Field(10000, ge=1000, le=10000)


class VisionConfig(StrictModel):
    enabled: bool = True
    provider: Literal["onnx_temporal_classifier"] = "onnx_temporal_classifier"
    model_path: str
    metadata_path: str
    feature_schema: Literal["lip40_v1", "sign100_v1"]
    max_frames: int = Field(64, ge=20, le=96)
    min_valid_frame_ratio: float = Field(0.8, ge=0, le=1)
    candidate_threshold: float = Field(0.8, ge=0, le=1)
    top_k: int = Field(3, ge=1, le=3)
    require_confirmation: Literal[True] = True


class RecognitionConfig(StrictModel):
    language: Literal["ja"] = "ja"
    max_pending_jobs_per_participant: int = Field(2, ge=1, le=4)
    max_pending_jobs_total: int = Field(8, ge=1, le=32)
    worker_processes: Literal[1] = 1
    job_timeout_seconds: int = Field(10, ge=1, le=60)
    partial_results: Literal[False] = False
    speech: SpeechConfig
    lipread: VisionConfig
    sign: VisionConfig


class OutputConfig(StrictModel):
    tts_provider: Literal["browser_speech_synthesis"] = "browser_speech_synthesis"
    tts_lang: str = "ja-JP"
    tts_rate: float = Field(1, ge=0.5, le=2)
    tts_queue_limit: int = Field(10, ge=1, le=50)
    tts_skip_own_utterances: bool = True
    tts_skip_replayed_events: bool = True
    speak_participant_changes_in_vision_mode: bool = True


class ModeConfig(StrictModel):
    input: Input
    allowed_inputs: list[Input]
    output: list[Literal["audio", "text"]]
    camera_on: bool
    microphone_on: bool
    layout: Literal["talk", "vision_support"]


class StorageConfig(StrictModel):
    room_database: str
    persist_transcripts: Literal[False] = False
    persist_media: Literal[False] = False


class ObservabilityConfig(StrictModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_transcript_text: Literal[False] = False
    metrics_enabled: bool = True


class Settings(StrictModel):
    app: AppConfig
    server: ServerConfig
    room: RoomConfig
    security: SecurityConfig
    media: MediaConfig
    rtc: RTCConfig
    recognition: RecognitionConfig
    output: OutputConfig
    modes: dict[Mode, ModeConfig]
    storage: StorageConfig
    observability: ObservabilityConfig
    root: Path = ROOT
    session_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48), repr=False)
    public_origin: str = "http://localhost:5173"
    turn_secret: str = Field("", repr=False)
    turn_urls: list[str] = []
    turn_username: str = Field("", repr=False)
    turn_password: str = Field("", repr=False)

    @model_validator(mode="after")
    def check_deployment(self):
        if set(self.modes) != {"standard", "vision_support", "hearing_support"}:
            raise ValueError("Three modes must be defined")
        for mode in self.modes.values():
            if mode.input not in mode.allowed_inputs or "text" not in mode.allowed_inputs:
                raise ValueError("Mode input and text fallback must be allowed")
        if self.app.environment == "production":
            if not self.security.cookie_secure or not self.public_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS and secure cookies")
            if len(self.session_secret) < 32 or "replace" in self.session_secret:
                raise ValueError("Production requires a generated session secret")
        if self.rtc.turn_enabled:
            shared_auth = len(self.turn_secret) >= 32
            service_auth = bool(self.turn_username and self.turn_password)
            if not self.turn_urls or not (shared_auth or service_auth):
                raise ValueError("TURN requires URLs and a shared secret or service username/password")
            if self.turn_secret and (self.turn_username or self.turn_password):
                raise ValueError("Choose either TURN shared-secret or service username/password authentication")
        if self.rtc.ice_transport_policy == "relay" and not self.rtc.turn_enabled:
            raise ValueError("Relay-only connections require TURN")
        return self

    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else self.root / p


def merge(base: dict, overrides: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        result[key] = (
            merge(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else value
        )
    return result


def load_settings(root: Path = ROOT) -> Settings:
    load_dotenv(root / ".env", override=False)
    path = Path(os.getenv("APP_CONFIG", "config/app.yaml"))
    if not path.is_absolute():
        path = root / path
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    local = root / "config/app.local.yaml"
    if local.exists():
        data = merge(data, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    for key, value in os.environ.items():
        if key.startswith("APP__"):
            parts = key[5:].lower().split("__")
            node = data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = yaml.safe_load(value)
    data["root"] = root
    data["app"]["environment"] = os.getenv("APP_ENV", data["app"]["environment"])
    data["public_origin"] = os.getenv("APP_PUBLIC_ORIGIN", "http://localhost:5173")
    secret = os.getenv("APP_SESSION_SECRET", "")
    if data["app"]["environment"] == "production" and not secret:
        raise ValueError("APP_SESSION_SECRET is required in production")
    if secret and "replace" not in secret:
        data["session_secret"] = secret
    elif data["app"]["environment"] == "production":
        raise ValueError("Replace APP_SESSION_SECRET")
    data["turn_secret"] = os.getenv("APP_TURN_SHARED_SECRET", "")
    data["turn_urls"] = [x.strip() for x in os.getenv("APP_TURN_URLS", "").split(",") if x.strip()]
    data["turn_username"] = os.getenv("APP_TURN_USERNAME", "")
    data["turn_password"] = os.getenv("APP_TURN_PASSWORD", "")
    return Settings.model_validate(data)
