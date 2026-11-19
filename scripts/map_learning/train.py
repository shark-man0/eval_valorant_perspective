"""Train independent portrait/marker CNNs from synthetic and TRAIN-only native crops."""

import argparse
import hashlib
import os
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from models import MarkerCNN, PortraitCNN
from torch.nn import functional as F

from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--recording-catalog", type=Path, required=True)
parser.add_argument("--map-catalog", type=Path, required=True)
parser.add_argument("--asset-cache", type=Path, required=True)
parser.add_argument("--training-receipt", type=Path, required=True)
parser.add_argument("--output-directory", type=Path, required=True)
args = parser.parse_args()
cv2.setNumThreads(1)
torch.set_num_threads(3)
torch.manual_seed(119)
os.umask(0o077)
rng = np.random.default_rng(119)
out = args.output_directory.resolve()
if any((parent / ".git").exists() for parent in out.parents):
    raise ValueError("Private Map CNN artifacts must remain outside Git checkouts")
out.mkdir(parents=True, exist_ok=False, mode=0o700)
cat = args.map_catalog
cache = args.asset_cache
knowledge = KnowledgeRecorderMap.load(cache, cat)
assets = ReferenceAssets.load(cache)
sources = dict(knowledge.minimap_portraits)
for uid in knowledge._uuids:
    if uid not in sources:
        sources[uid] = assets.image(f"agent:{uid}:displayicon")


def silhouette(im):
    if im.shape[2] == 3:
        return np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    return im


def variants(im):
    im = silhouette(im)
    y, x = np.nonzero(im[:, :, 3] > 100)
    if len(x):
        return [im, im[y.min() : y.max() + 1, x.min() : x.max() + 1]]
    return [im]


bank = [variants(sources[u]) for u in knowledge._uuids]
catalog = RecordingCatalog(args.recording_catalog)
receipt = read_json(args.training_receipt)
if receipt.get("schema") != "map_cnn_training_receipt_v1" or not receipt.get("recordings"):
    raise ValueError("A pinned Map CNN training receipt is required")
train = []
physical = set()
for row in receipt["recordings"]:
    rid = row["recording_id"]
    rec = catalog.state.recordings[rid]
    catalog.guard([rid], "training")
    if (
        rec.split != "DEVELOPMENT"
        or rec.learning.get("split") != "TRAIN"
        or rec.physical_match_id in physical
        or row["source_sha256"] != rec.source_sha256
    ):
        raise ValueError("Training crops must belong to distinct registered TRAIN matches")
    physical.add(rec.physical_match_id)
    patch_path = Path(row["patches"])
    if file_sha(patch_path) != row["sha256"]:
        raise ValueError("Training crop archive hash mismatch")
    with np.load(patch_path, allow_pickle=False) as src:
        pos_data, neg_data = src["positive"], src["negative"]
        for data in (pos_data, neg_data):
            if not len(data) or data.dtype != np.uint8 or data.shape[1:] != (25, 25, 3):
                raise ValueError("Expected 25 by 25 uint8 BGR center crops")
        train.append(
            {
                "positive": pos_data,
                "negative": neg_data,
                "agent": knowledge._uuids.index(row["recorder_agent_uuid"]),
            }
        )
pos = np.concatenate([r["positive"] for r in train])
neg = np.concatenate([r["negative"] for r in train])
real_agent = np.concatenate([np.full(len(r["positive"]), int(r["agent"])) for r in train])


def paint(kind, agent):
    background = (
        neg[rng.integers(len(neg))].copy()
        if rng.random() < 0.85
        else np.full((25, 25, 3), rng.uniform(25, 145)).astype(np.uint8)
    )
    if rng.random() < 0.7:
        background = cv2.GaussianBlur(background, (7, 7), 2)
    if kind == "none":
        if rng.random() < 0.4:
            cv2.line(background, (2, 10), (23, 14), (120, 194, 237), int(rng.integers(1, 3)))
        return background
    x, y = 12 + rng.integers(-1, 2, 2)
    r = int(rng.integers(7, 10))
    size = 2 * r - 1
    source = bank[agent][rng.integers(len(bank[agent]))]
    avatar = cv2.resize(source, (size, size), interpolation=cv2.INTER_AREA)
    a = avatar[:, :, 3:4] / 255.0
    yy, xx = np.indices((size, size))
    a *= ((xx - size // 2) ** 2 + (yy - size // 2) ** 2 <= r * r)[:, :, None]
    z = background[y - size // 2 : y + size // 2 + 1, x - size // 2 : x + size // 2 + 1]
    z[:] = np.uint8(np.clip(z * (1 - a) + avatar[:, :, :3] * a, 0, 255))
    if kind in ("self", "other"):
        shade = int(rng.integers(-22, 23))
        ring = (155 + shade, 233 + shade // 2, 255) if kind == "self" else (221, 235, 53 + shade)
        theta = float(rng.uniform(0, 2 * np.pi))
        tip = np.array(
            [
                (x + np.cos(angle) * radius, y + np.sin(angle) * radius)
                for angle, radius in ((theta, r + 5), (theta + 0.61, r - 1), (theta - 0.61, r - 1))
            ],
            np.int32,
        )
        cv2.fillConvexPoly(background, tip, ring)
        cv2.circle(background, (x, y), r, ring, int(rng.integers(1, 3)), cv2.LINE_AA)
    if rng.random() < 0.2:
        background = cv2.GaussianBlur(background, (3, 3), rng.uniform(0.2, 1))
    return background


def input_tensor(x, size):
    half = size // 2
    images = x[:, 12 - half : 13 + half, 12 - half : 13 + half, :]
    return torch.from_numpy(images.copy()).permute(0, 3, 1, 2).float() / 255.0


def augment(x, stronger=False):
    gain = torch.rand((len(x), 3, 1, 1)) * (0.30 if stronger else 0.18) + (
        0.85 if stronger else 0.91
    )
    bias = (torch.rand((len(x), 3, 1, 1)) - 0.5) * (0.14 if stronger else 0.08)
    return (x * gain + bias + torch.randn_like(x) * (0.034 if stronger else 0.019)).clamp(0, 1)


def fit(model, size, real_x, real_y, syn_x, syn_y, name):
    start = time.monotonic()
    xr = input_tensor(real_x, size)
    xs = input_tensor(syn_x, size)
    yr = torch.from_numpy(real_y.astype(np.int64))
    ys = torch.from_numpy(syn_y.astype(np.int64))
    # Negative patches have a recorder-role label and no Agent class label.
    unlabelled = input_tensor(neg, size) if name == "portrait" else None
    classes = torch.bincount(yr)
    example_weights = 1.0 / classes[yr].float()
    axis = torch.arange(size) - size // 2
    center_mask = axis[:, None].square() + axis[None, :].square() <= 5**2
    opt = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.001)
    for epoch in range(14):
        model.train()
        tot = 0.0
        confident = 0
        pseudo_count = 0
        perm = torch.randperm(len(xs))
        choice = torch.randperm(len(xr))
        for k, batch in enumerate(perm.split(128)):
            ri = choice[(torch.arange(96) + k * 96) % len(choice)]
            if name == "portrait":
                ri[48:] = torch.multinomial(example_weights, 48, replacement=True)
            x = torch.cat([xs[batch], xr[ri]])
            y = torch.cat([ys[batch], yr[ri]])
            if name == "marker":
                # Randomize the avatar at the center while retaining its rim and direction.
                swaps = torch.rand(len(x)) < 0.4
                mask = swaps[:, None, None, None] & center_mask[None, None, :, :]
                x = torch.where(mask, x[torch.randperm(len(x))], x)
            logits = model(augment(x))
            logits = logits.flatten(1)
            if name == "marker":
                loss = F.binary_cross_entropy_with_logits(logits[:, 0], y.float())
            else:
                loss = F.cross_entropy(logits, y, label_smoothing=0.03)
            # Consistency under an independent color/noise view of real patches.
            # Only retain pseudo-labels if the weak view is confident.
            if epoch >= 5:
                with torch.no_grad():
                    soft = logits[-len(ri) :].detach()
                    q = soft[:, 0].sigmoid() if name == "marker" else F.softmax(soft, dim=-1)
                strong = model(augment(xr[ri], True)).flatten(1)
                if name == "marker":
                    agree = (q > 0.92) | (q < 0.08)
                    if agree.any():
                        loss += 0.15 * F.binary_cross_entropy_with_logits(
                            strong[agree, 0], q[agree]
                        )
                else:
                    v, _ = q.max(dim=1)
                    agree = v > 0.92
                    if agree.any():
                        loss += 0.15 * F.kl_div(
                            F.log_softmax(strong[agree], -1), q[agree], reduction="batchmean"
                        )
                confident += int(agree.sum())
                if unlabelled is not None:
                    samples = unlabelled[torch.randint(len(unlabelled), (32,))]
                    with torch.no_grad():
                        first = F.softmax(model(augment(samples)), dim=-1)
                        second = F.softmax(model(augment(samples)), dim=-1)
                        top, label = first.max(dim=1)
                        alternative, label2 = second.max(dim=1)
                        stable = (top >= 0.97) & (alternative >= 0.97) & label.eq(label2)
                    if stable.any():
                        predicted = model(augment(samples[stable], True))
                        loss += 0.10 * F.cross_entropy(predicted, label[stable])
                        pseudo_count += int(stable.sum())
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss.detach())
        if epoch in (0, 4, 9, 13):
            print(
                name,
                epoch + 1,
                round(tot / (k + 1), 4),
                confident,
                pseudo_count,
                round(time.monotonic() - start, 2),
                flush=True,
            )
    model.eval()
    arrays = {key: t.detach().numpy() for key, t in model.state_dict().items()}
    np.savez_compressed(out / f"{name}_cnn_weights_PRIVATE.npz", **arrays)
    return {
        "runtime_s": time.monotonic() - start,
        "parameters": sum(p.numel() for p in model.parameters()),
        "real": len(real_x),
        "synthetic": len(syn_x),
        "agent_pseudo_labels_last_epoch": pseudo_count,
    }


N = len(bank)
labels = np.repeat(np.arange(N), 300)
rng.shuffle(labels)
synth = np.stack([paint(("self", "other", "plain")[int(rng.integers(3))], i) for i in labels])
stats = {"portrait": fit(PortraitCNN(N), 17, pos, real_agent, synth, labels, "portrait")}
kind = ["self"] * 4500 + ["other"] * 2700 + ["none"] * 1800
rng.shuffle(kind)
synthetic = np.stack([paint(b, int(rng.integers(N))) for b in kind])
y = np.array([b == "self" for b in kind])
target = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
stats["marker"] = fit(MarkerCNN(), 19, np.concatenate([pos, neg]), target, synthetic, y, "marker")
stats["train_recordings"] = len(train)
stats["agent_uuids"] = list(knowledge._uuids)
stats["asset_sha256s"] = {
    u: hashlib.sha256(sources[u].tobytes()).hexdigest() for u in knowledge._uuids
}
stats["formal_outputs"] = 0
stats["schema"] = "map_cnn_weights_v1"
stats["training_receipt_sha256"] = file_sha(args.training_receipt)
stats["weight_sha256s"] = {
    name: file_sha(out / f"{name}_cnn_weights_PRIVATE.npz") for name in ("portrait", "marker")
}
write_private(out / "training_summary_PRIVATE.json", stats)
print(
    {k: v for k, v in stats.items() if k in ("portrait", "marker", "train_recordings")}, flush=True
)
