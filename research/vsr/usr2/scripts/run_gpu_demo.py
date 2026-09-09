"""上流demoをCUDA必須で実行し、同一プロセスのVRAM使用量を記録する。"""
import atexit
import json
from pathlib import Path
import runpy
import sys

import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDAが利用できません。USR2のGPU環境とGPU割当を確認してください。")
torch.cuda.init()
torch.cuda.reset_peak_memory_stats()
print(f"GPU: {torch.cuda.get_device_name(0)} / torch {torch.__version__}", flush=True)


def save_gpu_metrics():
    metrics = {
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "max_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
        "max_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
    }
    Path("gpu_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print("GPU metrics: " + json.dumps(metrics), flush=True)


atexit.register(save_gpu_metrics)
upstream = Path(__file__).resolve().parents[1] / "upstream"
sys.path.insert(0, str(upstream))
runpy.run_path(str(upstream / "demo.py"), run_name="__main__")
