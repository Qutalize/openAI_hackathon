import time
from dataclasses import dataclass, field
from uuid import uuid4


def uid():
    return str(uuid4())


@dataclass
class Session:
    participant_id: str
    room_id: str
    display_name: str
    mode: str
    input: str
    token_digest: str
    csrf_digest: str
    expires_at: float
    avatar: str = ""
    input_epoch: int = 0
    stream_id: str = field(default_factory=uid)
    devices: dict = field(default_factory=lambda: {"microphone": False, "camera": False})
    output: list = field(default_factory=lambda: ["audio", "text"])
    last_seen: float = field(default_factory=time.time)
    disconnected_at: float | None = field(default_factory=time.time)
    active_since: float | None = None
    recognition_jobs: int = 0
    control: object = None
    media: object = None
    media_seq: int = -1
    capture_ms: float = -1
    segment: dict | None = None
    candidates: dict = field(default_factory=dict)
    requests: dict = field(default_factory=dict)
    segmenter: object = None
    tasks: set = field(default_factory=set)

    def public(self):
        return {
            "id": self.participant_id,
            "display_name": self.display_name,
            "avatar": self.avatar,
            "mode": self.mode,
            "input": self.input,
            "devices": self.devices.copy(),
            "speaking": self.active_since is not None,
            "recognizing": self.recognition_jobs > 0,
            "connection_state": "connected" if self.control else "reconnecting",
        }

    def stream(self):
        return {"input": self.input, "input_epoch": self.input_epoch, "stream_id": self.stream_id}


@dataclass
class RoomState:
    participants: dict = field(default_factory=dict)
    avatars: dict = field(default_factory=dict)
    utterances: list = field(default_factory=list)
    replay: list = field(default_factory=list)
    seq: int = 0
    empty_since: float | None = None
    speaker: str | None = None
    speaker_since: float = 0
