import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class TemporalClassifier(nn.Module):
    def __init__(self, points, classes):
        super().__init__()
        self.temporal = nn.Sequential(
            nn.Conv1d(points * 4, 96, 5, padding=2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Conv1d(96, 96, 5, padding=2),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(96, classes)

    def forward(self, features, frame_mask):
        masked = features * frame_mask[:, :, None, None]
        x = masked.flatten(2).transpose(1, 2)
        x = self.temporal(x) * frame_mask[:, None, :]
        pooled = x.sum(dim=2) / frame_mask.sum(dim=1, keepdim=True).clamp(min=1)
        return self.classifier(pooled)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("output")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    d = np.load(args.dataset, allow_pickle=False)
    for left, right in (
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    ):
        if set(d["subjects"][d["splits"] == left]) & set(
            d["subjects"][d["splits"] == right]
        ):
            raise ValueError("Person leakage across splits")
    features, masks, targets = (
        torch.from_numpy(d[k]) for k in ("features", "masks", "targets")
    )
    train_indices = np.flatnonzero(d["splits"] == "train")
    val_indices = np.flatnonzero(d["splits"] == "validation")
    loader = DataLoader(
        TensorDataset(
            features[train_indices], masks[train_indices], targets[train_indices]
        ),
        batch_size=16,
        shuffle=True,
    )
    model = TemporalClassifier(features.shape[2], len(d["labels"]))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    loss_fn = nn.CrossEntropyLoss()
    best, best_state, best_epoch = float("inf"), None, 0
    for epoch in range(args.epochs):
        model.train()
        for x, mask, target in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(x, mask), target.long())
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(
                loss_fn(
                    model(features[val_indices], masks[val_indices]),
                    targets[val_indices].long(),
                )
            )
        if val_loss < best:
            best, best_state, best_epoch = (
                val_loss,
                copy.deepcopy(model.state_dict()),
                epoch,
            )
        if epoch % 10 == 0:
            print(f"epoch={epoch} validation_loss={val_loss:.4f}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": best_state,
            "points": features.shape[2],
            "max_frames": features.shape[1],
            "labels": d["labels"].tolist(),
            "modality": str(d["modality"]),
            "vocabulary_version": str(d["vocabulary_version"]),
            "seed": args.seed,
            "best_epoch": best_epoch,
            "training_data_summary": {
                "subjects": len(set(d["subjects"].tolist())),
                "samples": len(targets),
                "split_by_person": True,
            },
        },
        output,
    )
    print(
        json.dumps(
            {
                "checkpoint": str(output),
                "best_epoch": best_epoch,
                "validation_loss": best,
            }
        )
    )


if __name__ == "__main__":
    main()
