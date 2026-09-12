"""作者配布の分割ZIPから固定したHow2Sign test少数組だけをHTTP Rangeで取得。"""
import argparse
import bisect
import gzip
import hashlib
import io
import json
from pathlib import Path
import pickle
import random
import urllib.request
import zipfile

MODEL_DIR = Path(__file__).resolve().parents[1] / "Uni-Sign"
REPO = "https://huggingface.co/ZechengLi19/Uni-Sign"


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


class MultipartHTTP(io.RawIOBase):
    """連結ZIPをseek可能な読取専用streamとして扱い、CRC検査はzipfileへ委譲。"""
    def __init__(self, revision, parts):
        self.revision, self.parts = revision, parts
        self.ends = []
        for part in parts:
            self.ends.append((self.ends[-1] if self.ends else 0) + part["size"])
        self.position = 0
        self.cache = {}
        self.transferred = 0
        self.requests = []

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (0 if whence == 0 else self.position if whence == 1 else self.ends[-1])
        if self.position < 0:
            raise ValueError("negative seek")
        return self.position

    def read(self, size=-1):
        if size < 0:
            size = self.ends[-1] - self.position
        size = min(size, self.ends[-1] - self.position)
        if size > 32 * 1024 * 1024:
            raise ValueError("one ZIP read exceeds 32 MiB; refusing full archive transfer")
        output = bytearray()
        while size > 0:
            part_idx = bisect.bisect_right(self.ends, self.position)
            start = self.ends[part_idx - 1] if part_idx else 0
            local = self.position - start
            block = local // (1024 * 1024)
            cache_key = (part_idx, block)
            if cache_key not in self.cache:
                first = block * 1024 * 1024
                last = min(first + 1024 * 1024, self.parts[part_idx]["size"]) - 1
                path = self.parts[part_idx]["path"]
                url = f"{REPO}/resolve/{self.revision}/{path}?subset_range={first}-{last}"
                request = urllib.request.Request(url, headers={"Range": f"bytes={first}-{last}"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status != 206:
                        raise RuntimeError(f"Range unsupported: HTTP {response.status}")
                    expected = f"bytes {first}-{last}/{self.parts[part_idx]['size']}"
                    if response.headers.get("Content-Range") != expected:
                        raise RuntimeError("Content-Range mismatch")
                    data = response.read(last - first + 2)
                if len(data) != last - first + 1:
                    raise RuntimeError("Range response size mismatch")
                self.cache[cache_key] = data
                self.transferred += len(data)
                self.requests.append({"part": path, "first": first, "last": last, "bytes": len(data)})
            data = self.cache[cache_key]
            within = local % (1024 * 1024)
            chunk = data[within:within + size]
            output.extend(chunk)
            self.position += len(chunk)
            size -= len(chunk)
        return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--revision", help="再現時にmanifestのHugging Face revisionを指定")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if MODEL_DIR / "outputs" not in out.parents:
        parser.error("保存先はUni-Sign/outputs以下に限定")
    out.mkdir(parents=True, exist_ok=False)
    revision = args.revision or get_json("https://huggingface.co/api/models/ZechengLi19/Uni-Sign")["sha"]
    tree = get_json(f"https://huggingface.co/api/models/ZechengLi19/Uni-Sign/tree/{revision}?recursive=false&expand=false")
    label_path = MODEL_DIR / "data/How2Sign/labels.test"
    labels = pickle.loads(gzip.decompress(label_path.read_bytes()))
    selected = random.Random(args.seed).sample(list(labels), args.count)
    manifest = {"dataset": "How2Sign", "split": "test", "reference_source": str(label_path),
                "label_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest(),
                "revision": revision, "repository": REPO, "seed": args.seed,
                "selection": "random.Random(seed).sample(list(upstream_test_labels), count); before any prediction",
                "samples": [{"id": key, "reference": labels[key]["text"]} for key in selected], "archives": {}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "hf_tree.json").write_text(json.dumps(tree, indent=2))
    for kind, suffix in (("pose", ".pkl"), ("rgb", ".mp4")):
        parts = sorted([p for p in tree if p["path"].startswith(f"how2sign_{kind}_format.zip.")], key=lambda p: p["path"])
        stream = MultipartHTTP(revision, parts)
        folder = out / kind
        folder.mkdir()
        with zipfile.ZipFile(stream) as archive:
            names = archive.namelist()
            (out / f"{kind}_members.txt").write_text("\n".join(names))
            for sample in manifest["samples"]:
                basename = Path(sample["id"]).with_suffix(suffix).name
                matches = [name for name in names if Path(name).name == basename]
                if len(matches) != 1:
                    raise RuntimeError(f"expected one archive member for {basename}; got {matches}")
                member = archive.getinfo(matches[0])
                if member.file_size > 100 * 1024 * 1024:
                    raise RuntimeError("sample exceeds 100 MiB")
                data = archive.read(member)  # Decompression and CRC32 verification.
                target = folder / basename
                with target.open("xb") as file:
                    file.write(data)
                key = "pose_path" if kind == "pose" else "video_path"
                sample[key] = str(target)
                sample[f"{kind}_sha256"] = hashlib.sha256(data).hexdigest()
                sample[f"{kind}_member"] = member.filename
                sample[f"{kind}_bytes"] = len(data)
                sample[f"{kind}_crc32"] = member.CRC
                print(kind, basename, len(data), flush=True)
                (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        manifest["archives"][kind] = {"parts": parts, "total_archive_bytes": stream.ends[-1],
                                          "transferred_bytes": stream.transferred, "range_requests": stream.requests}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    manifest["status"] = "complete"
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Download complete", out, flush=True)


if __name__ == "__main__":
    main()
