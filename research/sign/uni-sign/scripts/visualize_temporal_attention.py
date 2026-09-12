"""Uni-Sign時間診断の保存量から図・CSV・ローカル閲覧HTMLを作成する（CPUのみ）。"""

import argparse
import csv
import html
import json
import hashlib
import shlex
import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_rows(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def word_groups(rows):
    """SentencePieceの▁は後続語に付属。apostrophe/継続subwordは結合。句点/EOSは別。"""
    groups = []
    for row in rows:
        t, piece = row["position"], row["subword"]
        if piece in ("</s>", "<pad>", ".", ",", "!", "?"):
            groups.append({"word": piece, "positions": [t]})
        elif piece.startswith("▁"):
            groups.append({"word": piece[1:], "positions": [t]})
        else:
            if not groups:
                groups.append({"word": "", "positions": []})
            groups[-1]["word"] += piece
            groups[-1]["positions"].append(t)
    assert all(g["word"] for g in groups)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    cli = parser.parse_args()
    out = cli.analysis_dir.resolve()
    figures = out / "figures"
    figures.mkdir(exist_ok=False)
    write_json(out / "visualization_manifest.json", {"command": shlex.join([sys.executable, *sys.argv]),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "overlay_path": str(cli.overlay.resolve()), "overlay_sha256": hashlib.sha256(cli.overlay.read_bytes()).hexdigest()})
    (out / "visualization_script.py.txt").write_text(Path(__file__).read_text(), encoding="utf-8")
    summary = json.loads((out / "summary.json").read_text())
    record = json.loads(cli.result.read_text())
    prefix = summary["prefix"]["length"]
    fps, n = record["video_metadata"]["fps"], record["video_metadata"]["frames"]
    times = np.arange(n) / fps
    windows = [(12, 36, "A: chest"), (36, 62, "B: both hands"), (62, 99, "C: near mouth")]
    observations = [
        {"start_frame": 0, "end_frame_exclusive": 12, "observation_ja": "両手を膝付近に置いた開始姿勢", "gt_candidate": None},
        {"start_frame": 12, "end_frame_exclusive": 36, "observation_ja": "画面左側の手を上げ、胸元を指すような動き。18〜30付近で胸への接近が明瞭", "gt_candidate": "I（未確認候補）"},
        {"start_frame": 36, "end_frame_exclusive": 62, "observation_ja": "両手を前方に上げ、掌を上に向けて指を曲げながら下方・体側へ引くように見える", "gt_candidate": "want（未確認候補）"},
        {"start_frame": 62, "end_frame_exclusive": 99, "observation_ja": "画面左側の手を口元へ上げ、複数の指を伸ばした形で保持・小さく動かす。口元位置は66〜96付近", "gt_candidate": "water（未確認候補）"},
        {"start_frame": 99, "end_frame_exclusive": 109, "observation_ja": "手を下げて膝付近の姿勢へ戻る", "gt_candidate": None},
    ]
    write_json(out / "observations.json", {"method": "入力・保存overlayから抽出した時系列画像を目視。語の意味や厳密な境界をASL専門家が確認した値ではない", "intervals": observations})

    # 全フレームをデコードして動画の時間・寸法整合を検証し、代表画像を保存。
    decoded = []
    for path in (Path(record["input_path"]), cli.overlay):
        cap = cv2.VideoCapture(str(path))
        assert cap.get(cv2.CAP_PROP_FPS) == fps
        frames = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()
        assert len(frames) == n
        decoded.append(frames)
    frame_indices = list(range(0, n, 6))
    fig, axes = plt.subplots(4, 5, figsize=(12, 13))
    for ax, index in zip(axes.flat, frame_indices):
        ax.imshow(decoded[0][index]); ax.set_title(f"f{index} / {index/fps:.2f} s"); ax.axis("off")
    for ax in list(axes.flat)[len(frame_indices):]:
        ax.axis("off")
    fig.suptitle("Actual preprocessed input: chronological observations (not word timestamps)")
    fig.tight_layout(); fig.savefig(figures / "input_contact_sheet.png", dpi=140); plt.close(fig)
    fig, axes = plt.subplots(2, 9, figsize=(18, 6))
    samples = [0, 18, 30, 42, 54, 66, 78, 90, 108]
    for r in range(2):
        for ax, index in zip(axes[r], samples):
            ax.imshow(decoded[r][index]); ax.set_title(f"f{index} / {index/fps:.2f}s"); ax.axis("off")
    fig.suptitle("Input (top) / saved pose overlay (bottom); no pose re-extraction")
    fig.tight_layout(); fig.savefig(figures / "input_and_pose.png", dpi=160); plt.close(fig)
    # 指と手首の重なりを確認するため、元画素から手・顔周辺を拡大。
    fig, axes = plt.subplots(2, 5, figsize=(14, 7))
    for c, index in enumerate([24, 42, 54, 78, 90]):
        for r in range(2):
            frame = decoded[r][index]
            axes[r, c].imshow(frame[90:390, 95:345]); axes[r, c].axis("off")
            axes[r, c].set_title(f"f{index} / {index/fps:.2f}s")
    fig.suptitle("Hand / face detail: original and saved overlay (same pixel crop)")
    fig.tight_layout(); fig.savefig(figures / "hands_detail.png", dpi=180); plt.close(fig)

    token_rows, stat_rows, head_rows, layer_rows, groups_dict = [], [], [], [], {}
    matrices = {}
    for name in ("prediction", "gt"):
        data = json.loads((out / f"{name}_tokens.json").read_text())
        groups = word_groups(data["tokens"])
        groups_dict[name] = groups
        path = "generation_attention.npz" if name == "prediction" else "gt_teacher_forced.npz"
        cross = np.load(out / path)["cross"]
        matrices[name] = cross
        mean = cross.mean(axis=(0, 1))
        for row in data["tokens"]:
            token_rows.append({"condition": name, **{k: v for k, v in row.items() if k != "top5"}})
        for level, units in [("token", [{"word": r["subword"], "positions": [r["position"]]} for r in data["tokens"]]), ("word", groups)]:
            values = np.stack([mean[g["positions"]].mean(axis=0) for g in units])
            # prefixは独立した位置として可視化。動画だけにrenormalizeした図としない。
            fig, axes = plt.subplots(1, 2, figsize=(15, max(3, .33 * len(units) + 1.8)), gridspec_kw={"width_ratios": [2.4, 10.9]}, sharey=True)
            vmax = max(.015, float(np.quantile(values, .995)))
            axes[0].imshow(values[:, :prefix], aspect="auto", vmin=0, vmax=vmax, cmap="magma")
            axes[0].set_xticks(range(prefix)); axes[0].set_xticklabels(summary["prefix"]["tokens"], rotation=70, fontsize=8)
            axes[0].set_yticks(range(len(units))); axes[0].set_yticklabels([g["word"] for g in units])
            im = axes[1].imshow(values[:, prefix:], aspect="auto", vmin=0, vmax=vmax, cmap="magma", extent=[-.5/fps, (n-.5)/fps, len(units)-.5, -.5])
            for start, end, label in windows:
                axes[1].axvline(start/fps, color="cyan", lw=.6, alpha=.6)
            axes[1].set_xlabel("Video position anchor (s); encoder states have global context")
            axes[0].set_xlabel("Prompt positions")
            title = "Generated beam path" if name == "prediction" else "GT teacher forcing"
            fig.suptitle(f"{title}: {level} cross-attention, mean of 12 layers x 12 heads")
            fig.colorbar(im, ax=axes, shrink=.7, pad=.02, label="Raw attention per source position (clipped color scale)")
            fig.subplots_adjust(bottom=.25, top=.88, left=.11, right=.88, wspace=.08)
            fig.savefig(figures / f"{name}_{level}_heatmap.png", dpi=160); plt.close(fig)
            for unit, vector in zip(units, values):
                visual = vector[prefix:]
                visual = visual / visual.sum()
                cdf = visual.cumsum()
                entry = {"condition": name, "level": level, "unit": unit["word"], "token_positions": ",".join(map(str, unit["positions"])),
                         "prefix_mass": float(vector[:prefix].sum()), "visual_mass": float(vector[prefix:].sum()),
                         "visual_peak_seconds": float(times[visual.argmax()]), "visual_centroid_seconds": float(visual @ times),
                         "visual_q10_seconds": float(times[min(n-1, np.searchsorted(cdf, .1))]),
                         "visual_q90_seconds": float(times[min(n-1, np.searchsorted(cdf, .9))]),
                         "visual_entropy_normalized": float(-(visual * np.log(visual + 1e-30)).sum() / np.log(n))}
                for start, end, label in windows:
                    entry[label.split(":")[0] + "_conditional_visual_mass"] = float(visual[start:end].sum())
                stat_rows.append(entry)
        # 層・head平均に隠れる差を保存。単語ごとに各headのピーク・重心・prompt質量。
        word_cross = np.stack([cross[:, :, g["positions"], :].mean(axis=2) for g in groups], axis=2)
        layer_visual = word_cross.mean(axis=1)[:, :, prefix:]
        fig, axes = plt.subplots(4, 3, figsize=(16, 12), sharex=True, sharey=True)
        vmax = float(np.quantile(layer_visual, .995))
        for layer, ax in enumerate(axes.flat):
            ax.imshow(layer_visual[layer], aspect="auto", vmin=0, vmax=vmax, cmap="magma", extent=[-.5/fps,(n-.5)/fps,len(groups)-.5,-.5])
            ax.set_title(f"Decoder layer {layer+1}"); ax.set_yticks(range(len(groups))); ax.set_yticklabels([g["word"] for g in groups], fontsize=8)
            for start, end, label in windows:
                ax.axvline(start/fps, color="cyan", lw=.5)
        fig.suptitle(f"{name}: cross-attention by layer, mean over 12 heads (shared color scale)")
        fig.tight_layout(); fig.savefig(figures / f"{name}_layers.png", dpi=140); plt.close(fig)
        for layer in range(cross.shape[0]):
            for w, group in enumerate(groups):
                value = layer_visual[layer, w]
                layer_rows.append({"condition": name, "layer": layer+1, "word": group["word"],
                                   "peak_frame": int(value.argmax()), "centroid_seconds": float(value @ times / value.sum())})
        for l in range(cross.shape[0]):
            for h in range(cross.shape[1]):
                for w, group in enumerate(groups):
                    value = word_cross[l, h, w]
                    visual = value[prefix:] / value[prefix:].sum()
                    head_rows.append({"condition": name, "layer": l+1, "head": h+1, "word": group["word"],
                                      "prefix_mass": float(value[:prefix].sum()), "peak_seconds": float(times[visual.argmax()]),
                                      "centroid_seconds": float(visual @ times), "entropy_normalized": float(-(visual*np.log(visual+1e-30)).sum()/np.log(n))})
        key_words = ["I", "want", "water"] if name == "gt" else ["They're", "heavy", "thirsty"]
        fig, axes = plt.subplots(1, len(key_words), figsize=(13, 4))
        for ax, word in zip(axes, key_words):
            w = [g["word"] for g in groups].index(word)
            visual = word_cross[:, :, w, prefix:]
            centroids = (visual * times).sum(-1) / visual.sum(-1)
            im = ax.imshow(centroids, vmin=0, vmax=n/fps, cmap="viridis", aspect="auto")
            ax.set_title(word); ax.set_xlabel("Head"); ax.set_ylabel("Layer")
            ax.set_xticks(range(12)); ax.set_xticklabels(range(1,13)); ax.set_yticks(range(12)); ax.set_yticklabels(range(1,13))
        fig.suptitle(f"{name}: visual attention centroid (s), each of 144 layer/head pairs")
        fig.colorbar(im, ax=axes, shrink=.8); fig.savefig(figures / f"{name}_head_centroids.png", dpi=140); plt.close(fig)

    csv_rows(out / "token_probabilities.csv", token_rows)
    csv_rows(out / "attention_time_statistics.csv", stat_rows)
    csv_rows(out / "layer_head_statistics.csv", head_rows)
    csv_rows(out / "layer_statistics.csv", layer_rows)
    write_json(out / "word_mapping.json", {"groups": groups_dict, "method": "単独▁は次語、continuationは前語に結合。単語Attentionは構成tokenの算術平均。句読点・EOSは独立。decoder-start0は予測対象から除外。確率はtoken単位のまま。"})
    # 同一秒軸の動作画像と、予測/GTの単語Attention。
    fig = plt.figure(figsize=(16, 10))
    grid = fig.add_gridspec(4, 1, height_ratios=[2, .4, 3, 2], hspace=.3)
    ax = fig.add_subplot(grid[0])
    strip = np.hstack([cv2.resize(decoded[1][i], (145,190)) for i in [6,18,30,42,54,66,78,90,102]])
    ax.imshow(strip, extent=[0,108/fps,0,1], aspect="auto"); ax.set_xlim(0,n/fps); ax.set_yticks([])
    ax.set_title("Saved pose frames centered at 0.2, 0.6, ..., 3.4 s; image widths are display bins")
    ax = fig.add_subplot(grid[1]); ax.set_xlim(0,n/fps); ax.set_ylim(0,1); ax.set_yticks([])
    for start, end, label in windows:
        ax.axvspan(start/fps,end/fps,alpha=.25); ax.text((start+end)/2/fps,.5,label,ha="center",va="center")
    ax.set_title("Observed movements; ASL meanings and exact boundaries are unconfirmed", fontsize=10)
    for index, name in enumerate(("prediction", "gt")):
        ax = fig.add_subplot(grid[index+2]); cross = matrices[name].mean((0,1))
        groups = groups_dict[name]
        values = np.stack([cross[g["positions"], prefix:].mean(0) for g in groups])
        # 条件付き形状の比較用。prompt質量は別図・CSVに保持。
        values /= values.sum(-1, keepdims=True)
        im = ax.imshow(values, aspect="auto", cmap="magma", vmin=0, vmax=.035, extent=[-.5/fps,(n-.5)/fps,len(groups)-.5,-.5])
        ax.set_yticks(range(len(groups))); ax.set_yticklabels([g["word"] for g in groups]); ax.set_xlim(0,n/fps)
        for start,end,label in windows:
            ax.axvline(start/fps,color="cyan",lw=.8)
        ax.set_title(f"{name}: word attention conditional on visual positions (different text prefixes)")
    ax.set_xlabel("Video time anchor (s), not a word timestamp")
    fig.colorbar(im, ax=fig.axes, fraction=.015, pad=.02, label="Visual-conditional attention per position (0–0.035; clipped)")
    fig.savefig(figures / "aligned_timeline.png", dpi=170, bbox_inches="tight"); plt.close(fig)

    # 特徴の時間的相違とencoderの文脈混合を別量として観測する。
    feats = np.load(out / "intermediate_features.npz")
    enc = np.load(out / "prediction_teacher_forced.npz")
    pose_proj = feats["pose_proj_0"][0]
    last = enc["encoder_hidden"][-1, prefix:]
    def cosine(x):
        unit = x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)
        return unit @ unit.T
    before, after = cosine(pose_proj), cosine(last)
    fig, axes = plt.subplots(1,3,figsize=(15,4))
    for ax,x,title in [(axes[0], before, "Projected pose features"), (axes[1], after, "Final mT5 encoder states")]:
        im=ax.imshow(x,origin="lower",extent=[-.5/fps,(n-.5)/fps,-.5/fps,(n-.5)/fps],vmin=-1,vmax=1,cmap="coolwarm");ax.set_title(title);ax.set_xlabel("s");ax.set_ylabel("s")
    for key in ("temporal_body_0", "temporal_hands_0", "temporal_hands_1", "temporal_face_0"):
        x=feats[key][0].mean(-1).T
        speed=np.linalg.norm(np.diff(x,axis=0),axis=-1)
        axes[2].plot(times[1:],speed/(np.linalg.norm(x,axis=-1).mean()+1e-12),label=key.replace("temporal_", ""))
    axes[2].set_title("Relative adjacent feature change");axes[2].set_xlabel("s");axes[2].legend(fontsize=8)
    fig.tight_layout();fig.savefig(figures / "feature_diagnostics.png",dpi=160);plt.close(fig)
    feature_stats = {"projected_pose_adjacent_cosine_mean": float(np.diag(before,1).mean()),
                     "encoder_adjacent_cosine_mean": float(np.diag(after,1).mean()),
                     "projected_pose_all_offdiagonal_cosine_mean": float(before[~np.eye(n,dtype=bool)].mean()),
                     "encoder_all_offdiagonal_cosine_mean": float(after[~np.eye(n,dtype=bool)].mean())}
    feature_stats["encoder_state_l2_norm_by_frame"] = np.linalg.norm(last, axis=-1).tolist()
    # encoder各layer/headにおけるj±6外へのattention。因果寄与量ではない。
    ea=enc["encoder_self"][:,:,prefix:,prefix:]
    far=np.abs(np.arange(n)[:,None]-np.arange(n)[None,:])>6
    feature_stats["encoder_visual_query_attention_to_far_visual_by_layer"]=(ea*far).sum(-1).mean((1,2)).tolist()
    write_json(out / "feature_statistics.json",feature_stats)
    # 介入固定文スコア差。異なる長さの文同士のsum比較は行わない。
    intervention_rows, detail_rows = [], []
    for experiment in summary["interventions"]:
        row={"intervention":experiment["name"],"free_generation":experiment["prediction"],"generated_tokens_excluding_start":len(experiment["tokens"])-1,
             "mask_changed":experiment["mask_changed"],"embedding_relative_l2":experiment["embedding_relative_l2"]}
        for name, stats in experiment["scores"].items():
            row[name+"_delta_mean_logprob"]=stats["delta_mean_logprob"]
            row[name+"_delta_sum_logprob"]=stats["delta_sum_logprob"]
            for token in stats["tokens"]:
                base=summary["baseline_scores"][name]["tokens"][token["position"]]
                detail_rows.append({"intervention":experiment["name"],"fixed_text":name,"position":token["position"],"subword":token["subword"],
                                    "log_probability":token["log_probability"],"delta_log_probability":token["log_probability"]-base["log_probability"],
                                    "probability":token["probability"],"eos_probability":token["eos_probability"]})
        intervention_rows.append(row)
    csv_rows(out / "interventions.csv",intervention_rows);csv_rows(out / "intervention_token_probabilities.csv",detail_rows)
    fig,axes=plt.subplots(1,2,figsize=(15,5))
    y=np.arange(len(intervention_rows))
    for offset,name in [(-.18,"prediction"),(.18,"gt")]:
        axes[0].barh(y+offset,[r[name+"_delta_mean_logprob"] for r in intervention_rows],height=.35,label=name)
    axes[0].set_yticks(y);axes[0].set_yticklabels([r["intervention"] for r in intervention_rows]);axes[0].axvline(0,color="black",lw=.6)
    axes[0].set_xlabel("Change in mean log P(token | fixed preceding tokens), including EOS");axes[0].legend();axes[0].set_title("Input interventions: fixed-text score changes")
    pred=summary["baseline_scores"]["prediction"]["tokens"]
    axes[1].plot([r["probability"] for r in pred],label="chosen token");axes[1].plot([r["eos_probability"] for r in pred],label="EOS")
    axes[1].set_yscale("log");axes[1].set_xticks(range(len(pred)));axes[1].set_xticklabels([r["subword"] for r in pred],rotation=70)
    axes[1].set_title("Recorded prediction prefixes (teacher forced)");axes[1].set_ylabel("Conditional probability");axes[1].legend()
    fig.tight_layout();fig.savefig(figures / "interventions_and_eos.png",dpi=160);plt.close(fig)
    html_text='<!doctype html><meta charset="utf-8"><title>Uni-Sign 時間診断</title><style>body{max-width:1400px;margin:30px auto;font-family:sans-serif}img{max-width:100%}section{margin:3em 0}code{white-space:pre-wrap}</style><h1>Uni-Sign：I want water. の時間診断</h1><p>ローカル専用。図中の秒はencoder位置のアンカーで、確定したASL単語時刻ではありません。予測は実生成beam、GTはteacher forcingです。</p>'
    for image_path in sorted(figures.glob("*.png")):
        html_text+=f'<section><h2>{html.escape(image_path.stem)}</h2><a href="figures/{image_path.name}"><img src="figures/{image_path.name}"></a></section>'
    (out / "index.html").write_text(html_text,encoding="utf-8")
    print(figures)


if __name__ == "__main__":
    main()
