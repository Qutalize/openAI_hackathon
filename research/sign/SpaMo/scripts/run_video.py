"""自前動画を上流の特徴抽出・SpaMo生成へ渡す推論専用CLI。"""
import argparse
import gc
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys

# 各モデルの配置を維持したまま、保存した上流出典を参照する。
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from source_provenance import upstream_revision
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / "weights" / "hf-cache"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, str(ROOT / "SpaMo"))

import av
import numpy as np
import torch
from download_assets import sha256


def read_frames(path):
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        metadata = {
            "width": stream.width, "height": stream.height,
            "fps": float(stream.average_rate) if stream.average_rate else None,
            "audio_streams_ignored": len(container.streams.audio),
        }
        frames = [frame.to_image().convert("RGB") for frame in container.decode(stream)]
    if not frames:
        raise ValueError("動画をデコードできませんでした。")
    if len(frames) > 512:
        raise ValueError("512フレームを超えています。意味のある短区間に分割してください。")
    metadata["decoded_frames"] = len(frames)
    return frames, metadata


@torch.inference_mode()
def extract(frames, device, batch_size):
    from scripts.vit_extract_feature import ViTFeatureReader
    from scripts.mae_extract_feature import VideoMAEFeatureReader
    from utils.helpers import sliding_window_for_list

    reader = ViTFeatureReader(str(ROOT / "weights/clip"), device=device,
                              s2_mode="s2wrapping", scales=[1, 2])
    spatial = np.concatenate([reader.get_feats(frames[i:i + batch_size]).cpu().numpy()
                              for i in range(0, len(frames), batch_size)])
    del reader
    gc.collect()
    torch.cuda.empty_cache()
    reader = VideoMAEFeatureReader(str(ROOT / "weights/videomae"), device=device,
                                   overlap_size=8)
    padded = frames + [frames[-1]] * max(0, 16 - len(frames))
    windows = sliding_window_for_list(padded, 16, 8)
    motion = np.concatenate([reader.get_feats(windows[i:i + batch_size]).cpu().numpy()
                             for i in range(0, len(windows), batch_size)])
    del reader
    gc.collect()
    torch.cuda.empty_cache()
    return spatial, motion


def load_model(checkpoint, device, variant="original"):
    from accelerate import init_empty_weights
    from transformers import AutoTokenizer, T5Config, T5ForConditionalGeneration
    from spamo.t5_slt import FlanT5SLT
    from spamo.mm_projector import build_vision_projector
    from spamo.tconv import TemporalConv

    if variant == "sign-vla":
        model_path = ROOT / "upstream/sign-vla/spamo/t5_slt.py"
        spec = importlib.util.spec_from_file_location("sign_vla_t5_slt", model_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        FlanT5SLT = module.FlanT5SLT

    class CheckpointSLT(FlanT5SLT):
        def prepare_models(self, model_name):
            # 完全なstate_dictを厳格ロードするため、T5の重複ダウンロードを避ける。
            config = T5Config.from_pretrained(model_name, local_files_only=True)
            with init_empty_weights():
                self.t5_model = T5ForConditionalGeneration(config).to(torch.bfloat16)
            self.t5_model.to_empty(device="cpu")
            self.t5_model.tie_weights()
            self.t5_tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            self.spatio_proj = build_vision_projector("linear", self.input_size, self.inter_hidden)
            self.spatiotemp_proj = build_vision_projector("linear", 1024, self.inter_hidden)
            self.fusion_proj = build_vision_projector("mlp2x_gelu", self.inter_hidden,
                                                      config.hidden_size)
            self.temporal_encoder = TemporalConv(self.inter_hidden, self.inter_hidden)
            self.logit_scale = torch.nn.Parameter(torch.tensor(2.6592))

    model = CheckpointSLT(
        model_name=str(ROOT / "weights/t5"), input_size=2048, inter_hidden=768,
        fusion_mode="joint", tuning_type="lora", lora_r=16, lora_alpha=32,
        lora_dropout=0.1, prompt="Translate the given sentence into {}.",
        max_frame_len=512, max_txt_len=64, use_in_context=False, num_in_context=0,
    )
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    result = model.load_state_dict(ckpt["state_dict"], strict=True)
    info = {"strict_load": str(result), "state_dict_keys": len(ckpt["state_dict"]),
            "epoch": ckpt.get("epoch"), "global_step": ckpt.get("global_step"),
            "checkpoint_training_language": (
                "ASL/How2Sign, provider declaration" if variant == "sign-vla" else "unconfirmed")}
    del ckpt
    model.requires_grad_(False).eval().to(device)
    return model, info


@torch.inference_mode()
def generate(model, spatial, motion, device, language, seed, do_sample=True):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    samples = {"pixel_values": [torch.from_numpy(spatial).to(device)],
               "glor_values": [torch.from_numpy(motion).to(device)],
               "num_frames": [len(spatial)], "glor_lengths": [len(motion)]}
    # get_inputs/prepare_inputsの正解文・derangement経路を使用しない。
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        visual, mask = model.prepare_visual_inputs(samples)
        visual = model.fusion_proj(visual)
        tokens = model.t5_tokenizer(model.prompt.format(language), return_tensors="pt").to(device)
        prompt_embeds = model.t5_model.encoder.embed_tokens(tokens.input_ids)
        embeds = torch.cat([visual, prompt_embeds], dim=1)
        mask = torch.cat([mask, tokens.attention_mask.bool()], dim=1)
        options = {"top_p": 0.9} if do_sample else {"length_penalty": 1.0}
        output = model.t5_model.generate(inputs_embeds=embeds, attention_mask=mask,
                                        num_beams=5, max_length=64, do_sample=do_sample, **options)
    return model.t5_tokenizer.batch_decode(output, skip_special_tokens=True)[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--variant", choices=["original", "sign-vla"], default="original")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--languages", nargs="+", default=["English"])
    p.add_argument("--features-only", action="store_true")
    args = p.parse_args()
    if args.checkpoint is None:
        name = "spamo_how2sign_sign_vla.ckpt" if args.variant == "sign-vla" else "spamo.ckpt"
        args.checkpoint = ROOT / "weights" / name
    if args.batch_size < 1:
        p.error("--batch-size must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDAを利用できません。GPUへアクセスできる環境で実行してください。")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    frames, video_info = read_frames(args.video)
    if args.variant == "sign-vla":
        import cv2
        from PIL import Image
        cropped_frames = []
        for frame in frames:
            array = np.asarray(frame)
            h, w = array.shape[:2]
            aspect = 210 / 260
            if abs(w / h - aspect) > 0.01:
                if w / h > aspect:
                    new_w = int(h * aspect)
                    left = (w - new_w) // 2
                    array = array[:, left:left + new_w]
                else:
                    new_h = int(w / aspect)
                    top = (h - new_h) // 2
                    array = array[top:top + new_h]
            cropped_frames.append(Image.fromarray(cv2.resize(array, (210, 260))))
        frames = cropped_frames
    result = {"input": str(args.video.resolve()), "input_sha256": sha256(args.video),
              "input_sign_language": "ASL (user confirmed)", "video": video_info,
              "upstream_revision": upstream_revision(ROOT / "SpaMo"),
              "status": "started", "confidence": None, "accuracy": "not evaluated",
              "seed": args.seed, "use_in_context": False,
              "torch": torch.__version__, "cuda": torch.version.cuda,
              "gpu": torch.cuda.get_device_name(),
              "preprocessing": "native FPS; RGB; upstream CLIP S2 [1,2]; VideoMAE 16-frame windows, stride 8, last incomplete window dropped; first token as upstream"}
    result["variant"] = args.variant
    if args.variant == "sign-vla":
        result["feature_upstream_revision"] = result["upstream_revision"]
        result["upstream_revision"] = upstream_revision(ROOT / "upstream/sign-vla")
        result["preprocessing"] += "; Sign-VLA center crop aspect 210:260 then cv2 resize 210x260"
        result["fusion"] = "Sign-VLA interleaving: 8 spatial tokens then 1 motion token"
        result["decoding"] = "beam=5, do_sample=False, length_penalty=1.0"
    path = args.output / "result.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    t = time.perf_counter()
    spatial, motion = extract(frames, args.device, args.batch_size)
    torch.cuda.synchronize()
    result["feature_seconds"] = time.perf_counter() - t
    result["spatial_shape"] = list(spatial.shape)
    result["motion_shape"] = list(motion.shape)
    np.save(args.output / "spatial.npy", spatial)
    np.save(args.output / "motion.npy", motion)
    result["status"] = "features_complete"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if not args.features_only:
        t = time.perf_counter()
        model, info = load_model(args.checkpoint, args.device, args.variant)
        torch.cuda.synchronize()
        result["model_load_seconds"] = time.perf_counter() - t
        result["checkpoint"] = info
        result["checkpoint_sha256"] = sha256(args.checkpoint)
        result["outputs"] = []
        for language in args.languages:
            t = time.perf_counter()
            raw = generate(model, spatial, motion, args.device, language, args.seed,
                           do_sample=args.variant == "original")
            torch.cuda.synchronize()
            result["outputs"].append({"requested_output_language": language, "raw_text": raw,
                                      "generation_seconds": time.perf_counter() - t})
            print(f"{language}: {raw}", flush=True)
        result["status"] = "generation_complete_checkpoint_language_unconfirmed"
        if args.variant == "sign-vla":
            result["status"] = "generation_complete_provider_declared_asl_checkpoint"
    result["wall_seconds"] = time.perf_counter() - started
    result["peak_allocated_gpu_gib"] = torch.cuda.max_memory_allocated() / 1024**3
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(path, flush=True)


if __name__ == "__main__":
    main()
