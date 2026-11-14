import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch
from model import MODEL_ARCHITECTURE, TemporalClassifier, augment
from torch import nn

# Unknown-movement false accepts allowed when choosing the candidate threshold.
TARGET_FALSE_ACCEPT = 0.05


def pick_device(name="auto"):
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


def fit(train, validation, classes, epochs=150, seed=42, device="cpu", batch_size=32, log=print):
    """Train on (features, masks, targets) arrays; keep the state with the lowest validation loss."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    generator = torch.Generator(device=device).manual_seed(seed)
    x, m, y = (torch.as_tensor(a).to(device) for a in train)
    vx, vm, vy = (torch.as_tensor(a).to(device) for a in validation)
    y, vy = y.long(), vy.long()
    model = TemporalClassifier(x.shape[2], classes).to(device)
    counts = torch.bincount(y, minlength=classes).float().clamp(min=1)
    loss_fn = nn.CrossEntropyLoss(weight=(counts.sum() / counts / classes), label_smoothing=0.1)
    plain_loss = nn.CrossEntropyLoss()
    steps = max(1, int(np.ceil(len(y) / batch_size)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=0.05)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, 2e-3, total_steps=epochs * steps)
    best, best_state, best_epoch = float("inf"), copy.deepcopy(model.state_dict()), 0
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(y), device=device, generator=generator)
        for i in range(steps):
            idx = order[i * batch_size : (i + 1) * batch_size]
            bx, bm = augment(x[idx], m[idx], generator)
            optimizer.zero_grad()
            loss = loss_fn(model(bx, bm), y[idx])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(plain_loss(model(vx, vm), vy)) if len(vy) else float(loss)
        if val_loss < best:
            best, best_state, best_epoch = val_loss, copy.deepcopy(model.state_dict()), epoch
        if log and (epoch % 25 == 0 or epoch == epochs - 1):
            log(f"epoch={epoch} validation_loss={val_loss:.4f}")
    model.load_state_dict(best_state)
    return model.cpu().eval(), {"best_epoch": best_epoch, "validation_loss": best}


def probabilities(model, features, masks):
    with torch.no_grad():
        logits = model(torch.as_tensor(features), torch.as_tensor(masks))
    return torch.softmax(logits, -1).numpy()


def decide(probs, unknown, threshold):
    """Top class, or unknown when it is unknown or below the threshold."""
    top = probs.argmax(1)
    accept = (top != unknown) & (probs.max(1) >= threshold)
    return np.where(accept, top, unknown), accept


def calibrate(probs, targets, unknown, floor=0.5):
    """Lowest threshold whose unknown false accept rate stays within the target."""
    known = targets != unknown
    for threshold in np.arange(floor, 0.991, 0.01):
        _, accept = decide(probs, unknown, threshold)
        if not (~known).any() or accept[~known].mean() <= TARGET_FALSE_ACCEPT:
            return float(round(threshold, 2))
    return 0.99


def checkpoint(model, labels, modality, vocabulary_version, max_frames, extra):
    return {
        "state_dict": model.state_dict(),
        "architecture": MODEL_ARCHITECTURE,
        "points": model.embed[0].in_features // 7,
        "max_frames": max_frames,
        "labels": list(labels),
        "modality": modality,
        "vocabulary_version": vocabulary_version,
        **extra,
    }


def main():
    """Train from a packed .npz with explicit person splits (see extract_features.py)."""
    p = argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("output")
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto")
    args = p.parse_args()
    d = np.load(args.dataset, allow_pickle=False)
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if set(d["subjects"][d["splits"] == left]) & set(d["subjects"][d["splits"] == right]):
            raise ValueError("Person leakage across splits")
    part = {s: np.flatnonzero(d["splits"] == s) for s in ("train", "validation")}
    data = {s: (d["features"][i], d["masks"][i], d["targets"][i]) for s, i in part.items()}
    labels = d["labels"].tolist()
    model, info = fit(
        data["train"], data["validation"], len(labels), args.epochs, args.seed, pick_device(args.device)
    )
    threshold = calibrate(
        probabilities(model, *data["validation"][:2]), data["validation"][2], labels.index("unknown")
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        checkpoint(
            model,
            labels,
            str(d["modality"]),
            str(d["vocabulary_version"]),
            d["features"].shape[1],
            {
                "seed": args.seed,
                "best_epoch": info["best_epoch"],
                "candidate_threshold": threshold,
                "training_data_summary": {
                    "subjects": len(set(d["subjects"].tolist())),
                    "samples": len(d["targets"]),
                    "split_by_person": True,
                },
            },
        ),
        output,
    )
    print(json.dumps({"checkpoint": str(output), **info, "candidate_threshold": threshold}))


if __name__ == "__main__":
    main()
