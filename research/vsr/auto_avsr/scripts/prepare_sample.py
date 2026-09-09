"""取得した公開LRS3サンプルを展開し、音声トラックを除去する。"""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import imageio_ffmpeg

root = Path(__file__).resolve().parents[1]
output = root / "outputs/setup"
member = "LRS3/good/NqOjj1FCcVY_00007_gt.mp4"
with zipfile.ZipFile(output / "LRS3.zip") as archive:
    (output / "original.mp4").write_bytes(archive.read(member))
subprocess.run([
    imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-i", str(output / "original.mp4"),
    "-map", "0:v:0", "-c:v", "copy", "-an", str(output / "video_only.mp4"),
], check=True)
manifest = {
    "id": "NqOjj1FCcVY_00007", "archive_member": member,
    "source": "https://raw.githubusercontent.com/LipVoicer/LipVoicer.github.io/1b39eaf451ea7b076d9d73f5739ec9c8bb42f5a9/data/LRS3.zip",
    "sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
               for name in ("LRS3.zip", "original.mp4", "video_only.mp4")},
}
(output / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
