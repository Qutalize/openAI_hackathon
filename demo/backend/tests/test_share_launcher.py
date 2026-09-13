import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.sharing import shared_settings

spec = importlib.util.spec_from_file_location(
    "share_launcher", Path(__file__).parents[2] / "scripts/share.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_download_is_verified_before_executable_is_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: None)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher.platform, "machine", lambda: "AMD64")
    release = {
        "tag_name": "test-version",
        "assets": [
            {
                "name": "cloudflared-windows-amd64.exe",
                "digest": "sha256:" + "0" * 64,
                "browser_download_url": "https://github.com/cloudflare/cloudflared/releases/download/test/app.exe",
            }
        ],
    }
    monkeypatch.setattr(
        launcher,
        "download",
        lambda url: io.BytesIO(
            json.dumps(release).encode() if url == launcher.RELEASE_API else b"downloaded-test-bytes"
        ),
    )
    with pytest.raises(RuntimeError, match="SHA-256"):
        launcher.find_cloudflared()
    assert not (tmp_path / ".cache/cloudflared/cloudflared.exe").exists()
    assert not list(tmp_path.rglob("*.download"))
    release["assets"][0]["digest"] = "sha256:" + hashlib.sha256(b"downloaded-test-bytes").hexdigest()
    binary = launcher.find_cloudflared()
    assert binary.read_bytes() == b"downloaded-test-bytes"
    monkeypatch.setattr(launcher, "download", lambda _: pytest.fail("Verified cache must work offline"))
    assert launcher.find_cloudflared() == binary


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    cfg = shared_settings("https://preflight.trycloudflare.com", 8765)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/index.html").write_text("app")
    cfg.server.frontend_dist = str(tmp_path / "dist")
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher, "shared_settings", lambda *args: cfg)
    monkeypatch.setattr(launcher, "find_cloudflared", lambda _: tmp_path / "cloudflared.exe")
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)
    return argparse.Namespace(port=0, skip_build=True, prepare_only=False, cloudflared=None)


def test_prepare_only_never_opens_tunnel(prepared, monkeypatch):
    prepared.prepare_only = True
    monkeypatch.setattr(launcher, "spawn", lambda *args: pytest.fail("Must not publish"))
    launcher.share(prepared)


@pytest.mark.parametrize("interrupted", [False, True])
def test_failed_or_interrupted_start_stops_both_owned_processes(prepared, monkeypatch, interrupted):
    created, stopped = [], []

    def spawn(*args):
        process = SimpleNamespace(pid=len(created) + 1)
        created.append(process)
        return process

    def wait(*args):
        if interrupted:
            raise KeyboardInterrupt
        raise RuntimeError("Backend startup failed")

    monkeypatch.setattr(launcher, "spawn", spawn)
    monkeypatch.setattr(launcher, "wait_for_tunnel", lambda *args: "https://shared.trycloudflare.com")
    monkeypatch.setattr(launcher, "wait_for_server", wait)
    monkeypatch.setattr(launcher, "stop", lambda p: stopped.append(p))
    with pytest.raises(KeyboardInterrupt if interrupted else RuntimeError):
        launcher.share(prepared)
    assert len(created) == 2 and stopped == created


def test_dead_tunnel_never_reports_a_shared_url(tmp_path):
    log = tmp_path / "tunnel.log"
    log.write_text("https://stale.trycloudflare.com")
    with pytest.raises(RuntimeError, match="発行に失敗"):
        launcher.wait_for_tunnel(SimpleNamespace(poll=lambda: 1), log)


def test_existing_named_tunnel_config_is_left_untouched(prepared, tmp_path, monkeypatch):
    config = tmp_path / ".cloudflared/config.yaml"
    config.parent.mkdir()
    config.write_text("existing-named-tunnel")
    monkeypatch.setattr(launcher, "spawn", lambda *args: pytest.fail("Must not start a tunnel"))
    with pytest.raises(RuntimeError, match="既存"):
        launcher.share(prepared)
    assert config.read_text() == "existing-named-tunnel"
