"""追加ASL動画07/08を3モデルで直列実行し、CLI時間とGPU使用量を記録する。"""

import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time


PROJECT = Path(__file__).resolve().parents[3]
SIGN = PROJECT / "research/sign"
INPUTS = (("07_whats_your_name_pro", "whatisyourname.mp4"),
          ("08_greetings_pro", "mynameis (2).mp4"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def query_gpu():
    command = ["nvidia-smi", "--query-gpu=uuid,name,memory.used,utilization.gpu,power.draw",
               "--format=csv,noheader,nounits"]
    lines = list(csv.reader(subprocess.check_output(command, text=True, timeout=10).splitlines()))
    if len(lines) != 1:
        raise RuntimeError("比較補助はGPUが1台の環境を対象とします")
    uuid, name, memory, utilization, power = [s.strip() for s in lines[0]]
    process_text = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=pid,used_gpu_memory", "--format=csv,noheader,nounits"],
        text=True, timeout=10)
    processes = [{"pid": int(row[0]), "memory_mib": float(row[1])}
                 for row in csv.reader(process_text.splitlines()) if row]
    return {"gpu_uuid": uuid, "gpu_name": name, "memory_mib": float(memory),
            "utilization_percent": float(utilization), "power_watts": float(power),
            "compute_processes": processes}


def descendant_pids(root_pid):
    parents = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                # comm may contain spaces or parentheses; remaining fields start with state and ppid.
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                parents[int(entry.name)] = int(fields[1])
            except (OSError, IndexError, ValueError):
                continue
    descendants = {root_pid}
    while True:
        expanded = descendants | {pid for pid, ppid in parents.items() if ppid in descendants}
        if expanded == descendants:
            return descendants
        descendants = expanded


def build_command(model, sample_id, filename, run_name, folder):
    video = PROJECT / "data/sign" / sample_id / filename
    if model == "uni-sign":
        result_dir = SIGN / model / "Uni-Sign/outputs" / run_name / sample_id
        manifest = {"status": "complete", "input_language": "ASL (user confirmed)",
                    "output_language": "English", "operation": "original video; no external transformations",
                    "samples": [{"id": sample_id, "variants": {"original": str(video)},
                                 "variant_sha256": {"original": sha256(video)}}]}
        manifest_path = folder / "input_manifest.json"
        write_json(manifest_path, manifest)
        command = ["/home/kosaki/anaconda3/envs/Uni-Sign/bin/python", "-B", "-u",
                   str(SIGN / model / "scripts/evaluate_preprocessed_self.py"),
                   "--manifest", str(manifest_path), "--output-dir", str(result_dir)]
    else:
        result_dir = SIGN / model / "outputs" / run_name / sample_id
        command = [str(SIGN / model / ".venv/bin/python"), "-B", "-u",
                   str(SIGN / model / "scripts/run_video.py"), str(video), "--output", str(result_dir)]
        if model == "SpaMo":
            command += ["--variant", "sign-vla", "--languages", "English"]
    if result_dir.exists():
        raise FileExistsError(result_dir)
    return command, result_dir, video


def measure(command, folder, interval):
    baseline = query_gpu()
    if baseline["compute_processes"]:
        raise RuntimeError("既存のGPU compute processがあります。同時実行による混同を避けるため停止します")
    write_json(folder / "baseline.json", baseline)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    samples = []
    monitor_errors = []
    observed_children = set()
    unrelated_pids = set()
    with (folder / "console.log").open("w", encoding="utf-8") as log, \
            (folder / "gpu_samples.jsonl").open("w", encoding="utf-8") as trace:
        start = time.perf_counter()
        process = subprocess.Popen(command, cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT)
        next_progress = start + 30
        try:
            while True:
                if process.poll() is not None:
                    end = time.perf_counter()
                    break
                sample_started = time.perf_counter()
                observed_children.update(descendant_pids(process.pid))
                try:
                    sample = query_gpu()
                    observed_children.update(descendant_pids(process.pid))
                    sample["elapsed_seconds"] = time.perf_counter() - start
                    sample["owned_process_memory_mib"] = sum(
                        p["memory_mib"] for p in sample["compute_processes"] if p["pid"] in observed_children)
                    unrelated_pids.update(p["pid"] for p in sample["compute_processes"]
                                          if p["pid"] not in observed_children)
                    samples.append(sample)
                    trace.write(json.dumps(sample) + "\n")
                    trace.flush()
                except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as error:
                    monitor_errors.append(repr(error))
                now = time.perf_counter()
                if now >= next_progress:
                    print(f"実行中: {folder.name}; {now - start:.1f}秒", flush=True)
                    next_progress = now + 30
                time.sleep(max(0, interval - (time.perf_counter() - sample_started)))
        except BaseException:
            process.terminate()
            process.wait(timeout=15)
            raise
    elapsed = end - start
    # Sample-time weighted mean over observed samples, with first sample applied from process start.
    weighted = 0.0
    for index, sample in enumerate(samples):
        left = 0 if index == 0 else sample["elapsed_seconds"]
        right = samples[index + 1]["elapsed_seconds"] if index + 1 < len(samples) else elapsed
        weighted += sample["utilization_percent"] * max(0, right - left)
    summary = {"returncode": process.returncode, "cli_wall_seconds": elapsed,
               "requested_sampling_interval_seconds": interval, "sample_count": len(samples),
               "observed_sampling_max_gap_seconds": max(
                   (b["elapsed_seconds"] - a["elapsed_seconds"] for a, b in zip(samples, samples[1:])), default=None),
               "baseline": baseline, "monitor_errors": monitor_errors,
               "observed_descendant_pids": sorted(observed_children),
               "unrelated_compute_pids": sorted(unrelated_pids),
               "timing_scope": "new CLI process start through observed exit; model loads, preprocessing, generation, hash/provenance and output writes included; exit poll resolution approximately sample interval",
               "memory_scope": "nvidia-smi device memory and all observed process-tree compute memory; MiB; sampled, not allocator exact peak",
               "utilization_scope": "device-wide nvidia-smi utilization.gpu; time-weighted over whole CLI including CPU/model loading/recording phases",
               "status": "success" if process.returncode == 0 and samples and not monitor_errors and not unrelated_pids else "needs_review"}
    if samples:
        summary.update(peak_device_memory_mib=max(s["memory_mib"] for s in samples),
                       peak_device_memory_delta_mib=max(s["memory_mib"] for s in samples) - baseline["memory_mib"],
                       peak_owned_process_memory_mib=max(s["owned_process_memory_mib"] for s in samples),
                       peak_device_utilization_percent=max(s["utilization_percent"] for s in samples),
                       mean_device_utilization_percent=weighted / elapsed)
    write_json(folder / "measurement.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--models", nargs="+", choices=["uni-sign", "SpaMo", "ssvp_slt"],
                        default=["uni-sign", "SpaMo", "ssvp_slt"])
    parser.add_argument("--interval", type=float, default=0.2)
    args = parser.parse_args()
    if not args.run_name.replace("-", "").replace("_", "").isalnum() or args.interval < 0.1:
        parser.error("run-nameは英数字/-/_、intervalは0.1秒以上")
    output = SIGN / "outputs" / args.run_name
    output.mkdir(parents=True, exist_ok=False)
    plan = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "script_sha256": sha256(Path(__file__)), "run_name": args.run_name, "rows": [],
            "notes": ["Same two original videos; each model retains its established preprocessing and decoding.",
                      "Sequential runs, new process for each video; no OS/disk cache flushing; no warm steady-state benchmark.",
                      "References never supplied as model context. Accuracy scored separately from saved outputs."]}
    write_json(output / "benchmark.json", plan)
    for model in args.models:
        for sample_id, filename in INPUTS:
            folder = output / f"{model}-{sample_id}"
            folder.mkdir(exist_ok=False)
            command, result_dir, video = build_command(model, sample_id, filename, args.run_name, folder)
            (folder / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
            row = {"model": model, "id": sample_id, "input_path": str(video), "input_sha256": sha256(video),
                   "command": command, "model_output_dir": str(result_dir), "measurement_dir": str(folder)}
            print(f"開始: {model} / {sample_id}", flush=True)
            try:
                row["measurement"] = measure(command, folder, args.interval)
            except Exception as error:
                row["error"] = repr(error)
                plan["rows"].append(row)
                write_json(output / "benchmark.json", plan)
                raise
            plan["rows"].append(row)
            write_json(output / "benchmark.json", plan)
            print(f"完了: {model} / {sample_id}: {row['measurement']['status']}; "
                  f"{row['measurement']['cli_wall_seconds']:.2f}秒", flush=True)
            if row["measurement"]["status"] != "success":
                raise RuntimeError("実行/計測に問題があります。保存ログを確認してください")
    plan["status"] = "success"
    write_json(output / "benchmark.json", plan)


if __name__ == "__main__":
    main()
