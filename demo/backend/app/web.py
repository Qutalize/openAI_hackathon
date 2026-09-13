"""Serve only the built frontend alongside the API and WebSockets."""

import os
import re
from pathlib import Path

from starlette.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    def __init__(self, directory: Path):
        if not (directory / "index.html").is_file():
            raise RuntimeError("画面のビルドがありません。frontend で npm.cmd run build を実行してください")
        super().__init__(directory=directory, follow_symlink=False)

    async def get_response(self, path, scope):
        path = path.replace(os.sep, "/")
        # Only known SPA routes fall back to HTML; missing APIs/assets remain 404.
        if path in (".", "", "training") or re.fullmatch(r"rooms/[a-z0-9-]{3,32}", path):
            path = "index.html"
        response = await super().get_response(path, scope)
        if path == "index.html":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(self)"
        return response
