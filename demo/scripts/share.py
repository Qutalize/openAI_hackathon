"""Build and share this PC through a temporary HTTPS Cloudflare Quick Tunnel."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.sharing import shared_settings  # noqa: E402

TUNNEL_URL = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b")
RELEASE_API = "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"


def download(url):
    return urlopen(Request(url, headers={"User-Agent": "kotoba-link-share"}), timeout=60)


def find_cloudflared(explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise RuntimeError("--cloudflared に指定した実行ファイルがありません")
        return path
    installed = shutil.which("cloudflared")
    if installed:
        return Path(installed)
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("cloudflared をインストールするか、--cloudflared で実行ファイルを指定してください")
    cache = ROOT / ".cache" / "cloudflared"
    cache.mkdir(parents=True, exist_ok=True)
    binary, manifest = cache / "cloudflared.exe", cache / "release.json"
    if binary.is_file() and manifest.is_file():
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        if hashlib.sha256(binary.read_bytes()).hexdigest() == metadata.get("sha256"):
            return binary
    print("初回のみ、Cloudflare公式GitHubから cloudflared を取得します。", flush=True)
    with download(RELEASE_API) as response:
        release = json.load(response)
    asset = next((a for a in release["assets"] if a["name"] == "cloudflared-windows-amd64.exe"), None)
    if not asset or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
        raise RuntimeError("公式のSHA-256を確認できません。cloudflared を手動でインストールしてください")
    url = asset["browser_download_url"]
    if not url.startswith("https://github.com/cloudflare/cloudflared/releases/download/"):
        raise RuntimeError("cloudflared の公式ダウンロードURLを確認できません")
    expected = asset["digest"].removeprefix("sha256:")
    # Stage downloads so interruption never leaves an executable-looking partial file.
    with tempfile.NamedTemporaryFile(dir=cache, suffix=".download", delete=False) as staged:
        staged_path = Path(staged.name)
        try:
            with download(url) as response:
                shutil.copyfileobj(response, staged)
        except BaseException:
            staged.close()
            staged_path.unlink(missing_ok=True)
            raise
    try:
        if hashlib.sha256(staged_path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("cloudflared のSHA-256が一致しません。取得を中止しました")
        staged_path.replace(binary)
        manifest.write_text(
            json.dumps({"version": release["tag_name"], "sha256": expected}), encoding="utf-8"
        )
    finally:
        staged_path.unlink(missing_ok=True)
    return binary


def spawn(command, log, cwd=ROOT):
    return subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"},
    )


def stop(process):
    if process is not None and process.poll() is None:
        if os.name == "nt":
            # Include the inference workers created by this server, not other app instances.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        else:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_for_tunnel(process, log, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"共有URLの発行に失敗しました。ログ: {log}")
        match = TUNNEL_URL.search(log.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group()
        time.sleep(0.3)
    raise RuntimeError(f"共有URLの発行がタイムアウトしました。ネットワークとログを確認してください: {log}")


def wait_for_server(process, port, log, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"アプリの起動に失敗しました。ログ: {log}")
        try:
            with urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
                if json.load(response).get("status") == "ready":
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"アプリの起動がタイムアウトしました。ログ: {log}")


def serve(origin, port):
    import uvicorn
    from app.main import create_app

    cfg = shared_settings(origin, port)
    uvicorn.run(
        create_app(cfg),
        host="127.0.0.1",
        port=port,
        ws_max_size=cfg.server.websocket_max_message_bytes,
        access_log=False,
        # Only the local cloudflared process can reach this loopback listener.
        forwarded_allow_ips="127.0.0.1",
        proxy_headers=True,
    )


def share(args):
    # Catch invalid TURN settings and occupied ports before opening any tunnel.
    cfg = shared_settings("https://preflight.trycloudflare.com", args.port)
    with socket.socket() as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            raise RuntimeError(
                f"ポート {args.port} は使用中です。--port 8766 など別の番号を指定してください"
            ) from None
    if not args.skip_build:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise RuntimeError("Node.js / npm が見つかりません")
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    if not cfg.path(cfg.server.frontend_dist).joinpath("index.html").is_file():
        raise RuntimeError("画面のビルドがありません。--skip-build を外して実行してください")
    tunnel_exe = find_cloudflared(args.cloudflared)
    if args.prepare_only:
        print("共有の準備が完了しました。まだインターネットには公開していません。", flush=True)
        return

    # Quick Tunnels cannot use an existing named-tunnel config. Leave that file intact.
    for name in ("config.yml", "config.yaml"):
        if (Path.home() / ".cloudflared" / name).exists():
            raise RuntimeError(
                "既存の .cloudflared/config.yml または config.yaml があるためQuick Tunnelを起動できません。"
                "既存設定を別名で退避してから再実行してください。"
            )
    cache = ROOT / ".cache" / "share"
    cache.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=cache))
    tunnel_log, server_log = run / "tunnel.log", run / "server.log"
    tunnel = server = None
    try:
        with tunnel_log.open("w", encoding="utf-8") as out:
            tunnel = spawn(
                [str(tunnel_exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{args.port}"],
                out,
            )
        print("共有用のHTTPS URLを発行しています…", flush=True)
        origin = wait_for_tunnel(tunnel, tunnel_log)
        with server_log.open("w", encoding="utf-8") as out:
            server = spawn(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--serve",
                    "--origin",
                    origin,
                    "--port",
                    str(args.port),
                ],
                out,
            )
        wait_for_server(server, args.port, server_log)
        print(f"\n共有URL: {origin}\n自分も相手も、このURLをブラウザで開いてください。", flush=True)
        print("新規ルームを作成し、同じURL・ルームID・パスワードを相手に伝えてください。", flush=True)
        if not cfg.rtc.turn_enabled:
            print(
                "映像・音声がつながらない回線ではTURN設定が必要です。文字入力はそのまま使えます。", flush=True
            )
        print(f"このPCとターミナルを起動したままにしてください。終了: Ctrl+C\nログ: {run}", flush=True)
        while True:
            if tunnel.poll() is not None or server.poll() is not None:
                raise RuntimeError(
                    f"共有プロセスが停止しました。再実行して新しいURLを共有してください。ログ: {run}"
                )
            time.sleep(1)
    finally:
        stop(tunnel)
        stop(server)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="ローカル待受ポート（既定8765）")
    parser.add_argument("--skip-build", action="store_true", help="ビルド済み画面を使う")
    parser.add_argument("--prepare-only", action="store_true", help="ビルドとツール取得のみ。公開しない")
    parser.add_argument("--cloudflared", help="既存のcloudflared実行ファイルのパス")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--origin", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.serve:
            serve(args.origin, args.port)
        else:
            share(args)
        return 0
    except KeyboardInterrupt:
        print("\n共有を終了しました。", flush=True)
        return 0
    except ValidationError as exc:
        messages = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors(include_input=False)]
        print("設定を確認してください: " + "; ".join(messages), file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, URLError) as exc:
        print(f"起動できませんでした: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
