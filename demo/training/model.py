"""Landmark sequence classifier shared by training, export and evaluation.

The ONNX contract stays `features [1,T,K,4]` + `frame_mask [1,T]` -> `logits [1,C]`, so the
server runs any version of this model without changes.
"""

import math

import torch
from torch import nn

MODEL_ARCHITECTURE = "temporal-conv-v3"
# lip40_v1 has 40 lip points; 0 and 10 are the mouth corners (face mesh 61 and 291).
LIP_POINTS, LIP_CORNERS = 40, (0, 10)


def mouth_frame(features, frame_mask):
    """Lip points relative to the mouth centre of each frame, in units of the take's mouth width.

    The browser scales by face width, so silent mouthing moves the points by only a few hundredths;
    this makes the mouth shape itself the input and removes head motion and distance to the camera.
    """
    valid = features[..., 3:4] * frame_mask[:, :, None, None]
    xyz = features[..., :3]
    centre = (xyz * valid).sum(2, keepdim=True) / valid.sum(2, keepdim=True).clamp(min=1)
    a, b = LIP_CORNERS
    width = (xyz[:, :, a, :2] - xyz[:, :, b, :2]).norm(dim=-1)
    present = valid[:, :, a, 0] * valid[:, :, b, 0]
    take_width = ((width * present).sum(1) / present.sum(1).clamp(min=1)).clamp(min=1e-3)
    return torch.cat([(xyz - centre) / take_width[:, None, None, None], features[..., 3:4]], -1)


class Block(nn.Module):
    def __init__(self, width, dilation, dropout):
        super().__init__()
        self.conv = nn.Conv1d(width, width, 5, padding=2 * dilation, dilation=dilation)
        self.norm = nn.GroupNorm(1, width)
        self.act = nn.GELU()
        self.drop = nn.Dropout(dropout)

    def forward(self, x, mask):
        return x + self.drop(self.act(self.norm(self.conv(x * mask))))


class TemporalClassifier(nn.Module):
    def __init__(self, points, classes, width=128, dropout=0.15):
        super().__init__()
        self.embed = nn.Sequential(
            nn.Linear(points * 10, width), nn.LayerNorm(width), nn.GELU(), nn.Dropout(dropout)
        )
        self.blocks = nn.ModuleList(Block(width, d, dropout) for d in (1, 2, 4, 1))
        self.attention = nn.Linear(width, 1)
        self.head = nn.Sequential(nn.LayerNorm(width * 2), nn.Dropout(0.2), nn.Linear(width * 2, classes))

    def forward(self, features, frame_mask):
        if features.shape[2] == LIP_POINTS:
            features = mouth_frame(features, frame_mask)
        valid = features[..., 3:4] * frame_mask[:, :, None, None]
        xyz = features[..., :3] * valid
        # Velocity only where both this and the previous frame have the point.
        prev_xyz = torch.cat([xyz[:, :1], xyz[:, :-1]], 1)
        prev_valid = torch.cat([valid[:, :1], valid[:, :-1]], 1)
        velocity = (xyz - prev_xyz) * valid * prev_valid
        # Position relative to each point's mean over the take: motion, not face or body shape.
        count = valid.sum(1, keepdim=True).clamp(min=1)
        centered = (xyz - xyz.sum(1, keepdim=True) / count) * valid
        mask = frame_mask[:, :, None]
        h = torch.cat([xyz, valid, velocity, centered], -1).flatten(2)
        h = self.embed(h) * mask
        h = h.transpose(1, 2)
        m = frame_mask[:, None, :]
        for block in self.blocks:
            h = block(h, m) * m
        h = h.transpose(1, 2)
        score = self.attention(h).squeeze(-1).masked_fill(frame_mask < 0.5, -1e4)
        weights = torch.softmax(score, 1)[..., None]
        pooled = (h * weights).sum(1)
        peak = h.masked_fill(mask < 0.5, -1e4).max(1).values
        return self.head(torch.cat([pooled, peak], -1))


def augment(features, mask, generator=None):
    """Random geometric and temporal perturbations of a batch [B,T,K,4] / [B,T]."""
    b, t, k, _ = features.shape
    dev = features.device

    def rand(*shape):
        return torch.rand(*shape, device=dev, generator=generator)

    valid = features[..., 3:4]
    xyz = features[..., :3]
    angle = (rand(b) - 0.5) * 2 * math.radians(12)
    scale = 0.85 + rand(b) * 0.3
    cos, sin = torch.cos(angle) * scale, torch.sin(angle) * scale
    x, y = xyz[..., 0], xyz[..., 1]
    x2 = x * cos[:, None, None] - y * sin[:, None, None]
    y2 = x * sin[:, None, None] + y * cos[:, None, None]
    shift = (rand(b, 1, 1, 3) - 0.5) * 0.1
    xyz = torch.stack([x2, y2, xyz[..., 2] * scale[:, None, None]], -1) + shift
    xyz = xyz + torch.randn(xyz.shape, device=dev, generator=generator) * 0.008
    out = torch.cat([xyz * valid, valid], -1)
    # Time stretch and shift by resampling frame indices.
    speed = 0.8 + rand(b) * 0.45
    lengths = mask.sum(1).clamp(min=1)
    offset = (rand(b) - 0.5) * 0.2 * lengths
    positions = torch.arange(t, device=dev)[None].float() * speed[:, None] + offset[:, None]
    index = positions.round().long()
    inside = (index >= 0) & (index < lengths[:, None].long())
    index = index.clamp(0, t - 1)
    out = torch.gather(out, 1, index[:, :, None, None].expand(b, t, k, 4))
    new_mask = torch.gather(mask, 1, index) * inside.float()
    # Drop a few frames, as the browser does when it falls behind.
    new_mask = new_mask * (rand(b, t) > 0.08).float()
    out = out * new_mask[:, :, None, None]
    return out, new_mask
