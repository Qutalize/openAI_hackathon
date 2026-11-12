"""Short-lived ICE servers from Cloudflare Realtime TURN.

The TURN key and its API token stay on the server; browsers only receive credentials that expire.
"""

from __future__ import annotations

import asyncio
import time

import httpx

ENDPOINT = "https://rtc.live.cloudflare.com/v1/turn/keys/{key_id}/credentials/generate-ice-servers"


class CloudflareTurn:
    def __init__(self, key_id: str, api_token: str, ttl: int):
        self.key_id, self.api_token, self.ttl = key_id, api_token, ttl
        self.servers: list[dict] = []
        self.expires = 0
        self.lock = asyncio.Lock()

    async def ice_servers(self) -> tuple[list[dict], int]:
        """Return (iceServers, expires_at). Credentials are shared and renewed at half their lifetime."""
        async with self.lock:
            if self.expires - time.time() < self.ttl / 2:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        ENDPOINT.format(key_id=self.key_id),
                        headers={"Authorization": f"Bearer {self.api_token}"},
                        json={"ttl": self.ttl},
                    )
                response.raise_for_status()
                self.servers = response.json()["iceServers"]
                self.expires = int(time.time()) + self.ttl
            return self.servers, self.expires
