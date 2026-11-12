"""Client for a model process that stays loaded and answers one JSON line per request."""

from __future__ import annotations

import json
import subprocess


class ResidentProcess:
    """Runs `command`, which prints {"ready": true} once loaded and then one reply line per request line.

    The child exits when its stdin closes, so it never outlives the worker that started it.
    """

    def __init__(self, command: list[str], env: dict | None = None):
        self.command = command
        self.env = env
        self.process = None
        self.ready = False

    def start(self):
        self.stop()
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=self.env,
            )
        except OSError:
            self.process = None

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        self.process, self.ready = None, False

    def ask(self, request: dict) -> dict | None:
        """Return the reply, or None when the process cannot be reached (the caller then falls back)."""
        if self.process is None or self.process.poll() is not None:
            self.start()
        if self.process is None:
            return None
        try:
            if not self.ready:
                # Loading takes tens of seconds; the first request waits for it here.
                self.ready = bool(json.loads(self.process.stdout.readline()).get("ready"))
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            reply = json.loads(self.process.stdout.readline())
        except (OSError, ValueError):
            # A dead or garbled process: drop it so the next request starts a fresh one.
            self.stop()
            return None
        if "error" in reply:
            # The input itself was rejected; a one-shot run would fail the same way.
            raise ValueError(reply["error"])
        return reply
