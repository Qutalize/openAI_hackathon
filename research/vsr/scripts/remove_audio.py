#!/usr/bin/env python3
"""FFmpegで原本を再エンコードせず、音声なしのMP4を作成する。"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="音声付き撮影原本（MP4）")
    parser.add_argument("-o", "--output", type=Path, help="既定: 入力と同じ場所のvideo_only.mp4")
    args = parser.parse_args()
    source = args.input.resolve()
    output = (args.output or source.with_name("video_only.mp4")).resolve()
    if not source.is_file():
        parser.error(f"入力ファイルがありません: {source}")
    if source == output:
        parser.error("入力と出力は別のファイルにしてください")
    if output.exists():
        parser.error(f"出力が既にあります（上書きしません）: {output}")
    if output.suffix.lower() != ".mp4":
        parser.error("出力の拡張子は.mp4にしてください")
    if not output.parent.is_dir():
        parser.error(f"出力先ディレクトリがありません: {output.parent}")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        parser.error("FFmpegが必要です。ffmpegをインストールしてPATHに追加してください")

    # 完成したファイルだけを公開し、失敗時は一時ファイルを削除する。
    try:
        with tempfile.TemporaryDirectory(prefix=".remove_audio_", dir=output.parent) as directory:
            temporary = Path(directory) / "video_only.mp4"
            subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                 "-i", str(source), "-map", "0:v:0", "-c:v", "copy", "-an",
                 "-map_metadata", "-1", "-map_chapters", "-1",
                 "-movflags", "+faststart", str(temporary)],
                check=True,
            )
            # 変換中に同名ファイルが作られても上書きしない。
            os.link(temporary, output)
    except (OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"音声除去に失敗しました: {exc}\n")
    print(f"音声なし動画を保存しました: {output}")


if __name__ == "__main__":
    main()
