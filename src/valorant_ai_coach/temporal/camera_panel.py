"""Camera evidence from two fixed HUD displays, bound to exact native samples.

* The spectator panel in the lower left carries a fixed "switch player" label
  while the recorder views another player. A normalized cross-correlation with a
  reference crop of that label measures it; between the presence and absence
  thresholds the label is undecided.
* The ability bar shows the abilities of the player whose HUD is displayed. A
  team never fields the same agent twice and only teammates can be spectated,
  so the recorder's own ability icons identify the recorder's HUD. The icons are
  learned per recording from frames without the spectator label (the dominant
  cluster) and are rejected if any frame with the label also matches them.

Rows are development supplements (``export --supplement``). They are never
qualified Facts/Events and carry their measurements in ``raw``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, freeze_native_sample
from .game import observation

VERSION = "development_camera_panel_v1"
REFERENCE_SIZE = (1920, 1080)
# Native 1080p geometry: label box (x, y, w, h), search margin, ability bar box.
LABEL_BOX = (112, 852, 158, 28)
LABEL_MARGIN = 6
BAR_BOX = (700, 975, 520, 85)
BAR_SLOTS = ((55, 125), (170, 240), (285, 355), (400, 470))
BAR_ROWS = (0, 56)
SLOT_MARGIN = 4
LABEL_PRESENT = 0.55
LABEL_ABSENT = 0.30
OWN_BAR_MATCH = 0.60
CLUSTER_SIMILARITY = 0.60
CLUSTER_SAMPLE = 300
MIN_CLUSTER_SHARE = 0.5
MIN_CLUSTER_SIZE = 30


def _gray(image: NDArray[np.uint8]) -> NDArray[np.float32]:
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return image.astype(np.float32)


def _ncc(region: NDArray[np.float32], template: NDArray[np.float32]) -> float:
    if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
        return -1.0
    if float(template.std()) == 0.0:
        return -1.0
    score = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    value = float(np.nan_to_num(score, nan=-1.0).max())
    return max(-1.0, min(1.0, value))


def _native(image: NDArray[np.uint8]) -> NDArray[np.uint8] | None:
    """Return the frame at reference geometry, or None for other aspect ratios."""
    height, width = image.shape[:2]
    if width * REFERENCE_SIZE[1] != height * REFERENCE_SIZE[0]:
        return None
    if (width, height) == REFERENCE_SIZE:
        return image
    return np.asarray(
        cv2.resize(image, REFERENCE_SIZE, interpolation=cv2.INTER_AREA), dtype=np.uint8
    )


@dataclass(frozen=True)
class LabelReference:
    template: NDArray[np.float32]
    sha256: str

    @classmethod
    def load(cls, path: Path) -> LabelReference:
        data = path.read_bytes()
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None or image.shape != (LABEL_BOX[3], LABEL_BOX[2]):
            raise ValueError(f"Spectator label reference must be {LABEL_BOX[2]}x{LABEL_BOX[3]}")
        return cls(image.astype(np.float32), hashlib.sha256(data).hexdigest())


def bar_slots(image: NDArray[np.uint8]) -> list[NDArray[np.float32]] | None:
    """Ability icon slots of a full frame, with the search margin."""
    native = _native(image)
    if native is None:
        return None
    x, y, w, h = BAR_BOX
    bar = _gray(native[y : y + h, x : x + w])
    return [
        bar[BAR_ROWS[0] : BAR_ROWS[1], a - SLOT_MARGIN : b + SLOT_MARGIN] for a, b in BAR_SLOTS
    ]


def measure_label(image: NDArray[np.uint8], reference: LabelReference) -> dict[str, Any]:
    native = _native(image)
    if native is None:
        return {"checked": False, "score": None, "state": "UNCHECKED",
                "reason": "unsupported_aspect_ratio"}
    x, y, w, h = LABEL_BOX
    m = LABEL_MARGIN
    region = _gray(native[y - m : y + h + m, x - m : x + w + m])
    score = _ncc(region, reference.template)
    state = (
        "PRESENT" if score >= LABEL_PRESENT else "ABSENT" if score <= LABEL_ABSENT else "UNDECIDED"
    )
    return {"checked": True, "score": round(score, 6), "state": state}


def _slot_similarity(
    slots: list[NDArray[np.float32]], prototype: list[NDArray[np.float32]]
) -> float:
    """Second-lowest slot score: three of four icons must agree."""
    values = sorted(_ncc(s, t) for s, t in zip(slots, prototype, strict=True))
    return values[1]


def _core(slots: list[NDArray[np.float32]]) -> list[NDArray[np.float32]]:
    m = SLOT_MARGIN
    return [s[m:-m, m:-m] for s in slots]


def learn_own_bar(
    absent: list[list[NDArray[np.float32]]],
    present: list[list[NDArray[np.float32]]],
) -> dict[str, Any]:
    """Learn the recorder's ability icons from frames without the label.

    The sample is evenly spaced, so the result is deterministic. The prototype
    is rejected unless one cluster holds most sampled frames and no frame with
    the spectator label matches it.
    """
    if len(absent) < MIN_CLUSTER_SIZE:
        return {"available": False, "reason": "too_few_label_absent_frames"}
    step = max(1, len(absent) // CLUSTER_SAMPLE)
    sample = absent[::step][:CLUSTER_SAMPLE]
    cores = [_core(s) for s in sample]
    n = len(sample)
    neighbours = [
        [j for j in range(n) if j != i and _slot_similarity(sample[j], cores[i])
         > CLUSTER_SIMILARITY]
        for i in range(n)
    ]
    centre = max(range(n), key=lambda i: (len(neighbours[i]), -i))
    members = [centre, *neighbours[centre]]
    if len(members) < max(MIN_CLUSTER_SIZE, MIN_CLUSTER_SHARE * n):
        return {"available": False, "reason": "no_dominant_ability_cluster",
                "cluster_size": len(members), "sampled": n}
    prototype = [
        np.median(np.stack([cores[j][k] for j in members]), axis=0).astype(np.float32)
        for k in range(len(BAR_SLOTS))
    ]
    leaks = sum(_slot_similarity(s, prototype) >= OWN_BAR_MATCH for s in present)
    if leaks:
        return {"available": False, "reason": "prototype_matches_spectated_hud",
                "spectator_matches": leaks}
    return {
        "available": True,
        "prototype": prototype,
        "cluster_size": len(members),
        "sampled": n,
        "spectator_frames_checked": len(present),
        "prototype_sha256": hashlib.sha256(
            b"".join(np.ascontiguousarray(p).tobytes() for p in prototype)
        ).hexdigest(),
    }


def measure_frame(image: NDArray[np.uint8], reference: LabelReference) -> dict[str, Any]:
    """Per-frame measurements; only small crops are kept."""
    return {"label": measure_label(image, reference), "slots": bar_slots(image)}


def camera_rows(
    measured: list[tuple[dict[str, Any], dict[str, Any]]],
    reference: LabelReference,
) -> dict[str, Any]:
    """Return a supplement with one row per frame decided by the two displays."""
    absent = [m["slots"] for _, m in measured
              if m["slots"] is not None and m["label"]["state"] == "ABSENT"]
    present = [m["slots"] for _, m in measured
               if m["slots"] is not None and m["label"]["state"] == "PRESENT"]
    own = learn_own_bar(absent, present)
    bindings = {
        "version": VERSION,
        "label_reference_sha256": reference.sha256,
        "label_box": LABEL_BOX,
        "bar_box": BAR_BOX,
        "thresholds": {"label_present": LABEL_PRESENT, "label_absent": LABEL_ABSENT,
                       "own_bar": OWN_BAR_MATCH},
        "own_bar_prototype_sha256": own.get("prototype_sha256"),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    producer = digest(bindings)
    rows = []
    counts = {"spectator_label": 0, "own_ability_bar": 0, "undecided": 0}
    for sample, m in measured:
        label, slot = m["label"], m["slots"]
        own_score = (
            _slot_similarity(slot, own["prototype"])
            if own["available"] and slot is not None else None
        )
        signals: list[str] = []
        if label["state"] == "PRESENT":
            signals = ["spectator"]
            counts["spectator_label"] += 1
        elif label["state"] == "ABSENT" and own_score is not None and own_score >= OWN_BAR_MATCH:
            signals = ["owner_hud"]
            counts["own_ability_bar"] += 1
        else:
            counts["undecided"] += 1
            continue
        rows.append(observation(
            sample=freeze_native_sample(sample),
            producer=producer,
            signals=signals,
            raw={"camera_panel": {"label": label,
                                  "own_ability_bar_score": None if own_score is None
                                  else round(own_score, 6)},
                 "qualified": False, "formal_outputs": 0},
            context={"stream_kind": "camera_panel"},
        ))
    summary = {k: v for k, v in own.items() if k != "prototype"}
    return {"version": VERSION, "bindings": bindings, "own_ability_bar": summary,
            "counts": counts, "observations": rows, "qualified": False,
            "formal_outputs": 0}


def decode_samples(
    video: Path, samples: list[dict[str, Any]], missing: list[dict[str, Any]]
) -> Iterator[tuple[dict[str, Any], NDArray[np.uint8]]]:
    """Yield samples decoded by native timestamp whose pixels are identical.

    Samples that are not found or differ in pixels are appended to ``missing``.
    """
    wanted: dict[int, list[dict[str, Any]]] = {}
    for sample in samples:
        if sample["native_time_base"] != "1/15360":
            raise ValueError("Native 1/15360 time base required")
        wanted.setdefault(int(sample["native_pts_tick"]), []).append(sample)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("Recording cannot be opened")
    last = max(wanted, default=-1)
    try:
        while wanted and capture.grab():
            tick = round(capture.get(cv2.CAP_PROP_POS_MSEC) * 15.36)
            if tick > last:
                break
            if tick not in wanted:
                continue
            ok, image = capture.retrieve()
            if not ok:
                break
            pixel = hashlib.sha256(image.tobytes()).hexdigest()
            for sample in wanted.pop(tick):
                if sample["native_pixel_sha256"] == pixel:
                    yield sample, np.asarray(image, dtype=np.uint8)
                else:
                    missing.append(sample)
    finally:
        capture.release()
    missing.extend(s for group in wanted.values() for s in group)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--timeline", type=Path, required=True,
                        help="Timeline or observation JSON whose samples are measured")
    parser.add_argument("--label-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise SystemExit("New output path required")
    data = json.loads(args.timeline.read_text(encoding="utf-8"))
    hasher = hashlib.sha256()
    with args.video.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    source = hasher.hexdigest()
    samples = {
        row["sample"]["sample_sha256"]: row["sample"]
        for row in data["observations"]
        if row["sample"]["source_sha256"] == source
    }
    reference = LabelReference.load(args.label_reference)
    missing: list[dict[str, Any]] = []
    measured = [
        (sample, measure_frame(image, reference))
        for sample, image in decode_samples(args.video, list(samples.values()), missing)
    ]
    result = camera_rows(measured, reference)
    result["samples_requested"] = len(samples)
    result["samples_not_pixel_identical"] = len(missing)
    args.output.write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps({"rows": len(result["observations"]), **result["counts"],
                      "own_ability_bar": result["own_ability_bar"],
                      "samples_not_pixel_identical": len(missing)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
