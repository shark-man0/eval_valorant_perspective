"""Camera evidence from two fixed HUD displays, bound to exact native samples.

* The spectator panel in the lower left carries a fixed "switch player" label
  while the recorder views another player. A normalized cross-correlation with a
  reference crop of that label measures it; between the presence and absence
  thresholds the label is undecided.
* Astra's astral form replaces the recorder's view with a purple starfield over
  a bright magenta floor plan of the map while the body stays in place: the
  recorder controls something else, as with a drone (REMOTE). It is measured
  from the colour composition of the central screen: a purple share, a bright
  magenta share (the floor plan) and the brightness spread (its sharp edges).
  A uniformly purple smoke is darker and has no bright plan; a single bright
  wall lacks the spread. The form is held for a while, so only a run of such
  frames spanning a second or more counts; shorter runs stay undecided.
* A placed camera (Cypher's spycam) is viewed from the ability's own key hint:
  a two-cell box with the aiming crosshair and the exit key. Both the whole box
  and its crosshair cell must match the reference, which separates it from the
  single "view camera" hint and from bow aiming hints of the same box style.
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
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from ..video.native import decoded_source_ticks
from ..video.service import _subprocess_environment
from .evidence import digest, freeze_native_sample
from .game import observation
from .match import _native_audit_batches, _pts_expression, png_frames

VERSION = "development_camera_panel_v1"
REFERENCE_SIZE = (1920, 1080)
# Native 1080p geometry: label box (x, y, w, h), search margin, ability bar box.
LABEL_BOX = (112, 852, 158, 28)
LABEL_MARGIN = 6
BAR_BOX = (700, 975, 520, 85)
BAR_SLOTS = ((55, 125), (170, 240), (285, 355), (400, 470))
BAR_ROWS = (0, 56)
SLOT_MARGIN = 4
# Remote control hint band above the ability bar and the control duration icon.
REMOTE_BAND = (640, 850, 650, 125)
DURATION_BOX = (930, 850, 60, 50)
REMOTE_HINT_MATCH = 0.60
REMOTE_DURATION_MATCH = 0.60
# Own health digits left of the ability bar: only a living player's HUD shows them.
HEALTH_BOX = (575, 1000, 105, 58)
HEALTH_DIGIT_HEIGHT = (28, 40)
HEALTH_DIGIT_WIDTH = (6, 26)
HEALTH_DIGIT_AREA = 120
# Astral form: central region of a 320x180 reduction (rows, columns) and thresholds.
ASTRAL_SIZE = (320, 180)
ASTRAL_REGION = (30, 140, 70, 300)
ASTRAL_PURPLE = 0.80
ASTRAL_BRIGHT = 0.10
ASTRAL_SPREAD = 25.0
# The astral form is held: a run of measured frames (gaps of at most ASTRAL_GAP
# seconds) spanning at least ASTRAL_MIN_SPAN. A shorter run (e.g. the purple wash
# of the Round transition) is left undecided.
ASTRAL_GAP = 1.5
ASTRAL_MIN_SPAN = 1.0
# Camera view hint: whole box and crosshair cell (rows, columns of the reference).
CAMERA_HINT_MATCH = 0.90
CAMERA_HINT_CELL = (8, 40, 4, 44)
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


@dataclass(frozen=True)
class CameraHintReference:
    """Key hint shown while a placed camera is viewed (crosshair and exit key)."""

    hint: NDArray[np.float32]
    cell: NDArray[np.float32]
    sha256: str

    @classmethod
    def load(cls, path: Path) -> CameraHintReference:
        data = path.read_bytes()
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
        top, bottom, left, right = CAMERA_HINT_CELL
        if (
            image is None
            or image.shape[0] > REMOTE_BAND[3] or image.shape[1] > REMOTE_BAND[2]
            or image.shape[0] < bottom or image.shape[1] < right
        ):
            raise ValueError("Readable camera hint reference within the remote band required")
        hint = image.astype(np.float32)
        return cls(hint, hint[top:bottom, left:right], hashlib.sha256(data).hexdigest())


def measure_camera_hint(
    image: NDArray[np.uint8], reference: CameraHintReference
) -> dict[str, Any]:
    native = _native(image)
    if native is None:
        return {"checked": False, "present": None}
    x, y, w, h = REMOTE_BAND
    band = _gray(native[y : y + h, x : x + w])
    hint, cell = _ncc(band, reference.hint), _ncc(band, reference.cell)
    return {
        "checked": True,
        "hint_score": round(hint, 6),
        "cell_score": round(cell, 6),
        "present": hint >= CAMERA_HINT_MATCH and cell >= CAMERA_HINT_MATCH,
    }


@dataclass(frozen=True)
class RemoteReference:
    """Remote-control key hint and duration icon shown while steering an ability."""

    hint: NDArray[np.float32]
    duration: NDArray[np.float32]
    sha256: str

    @classmethod
    def load(cls, hint_path: Path, duration_path: Path) -> RemoteReference:
        images = []
        digest_input = b""
        for path in (hint_path, duration_path):
            data = path.read_bytes()
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError("Readable remote reference required")
            images.append(image.astype(np.float32))
            digest_input += hashlib.sha256(data).digest()
        hint, duration = images
        if (
            hint.shape[0] > REMOTE_BAND[3] or hint.shape[1] > REMOTE_BAND[2]
            or duration.shape[0] > DURATION_BOX[3] or duration.shape[1] > DURATION_BOX[2]
        ):
            raise ValueError("Remote references exceed their search regions")
        return cls(hint, duration, hashlib.sha256(digest_input).hexdigest())


def measure_remote(image: NDArray[np.uint8], reference: RemoteReference) -> dict[str, Any]:
    native = _native(image)
    if native is None:
        return {"checked": False, "present": None}
    x, y, w, h = REMOTE_BAND
    hint = _ncc(_gray(native[y : y + h, x : x + w]), reference.hint)
    x, y, w, h = DURATION_BOX
    duration = _ncc(_gray(native[y : y + h, x : x + w]), reference.duration)
    return {
        "checked": True,
        "hint_score": round(hint, 6),
        "duration_score": round(duration, 6),
        "present": hint >= REMOTE_HINT_MATCH and duration >= REMOTE_DURATION_MATCH,
    }


def measure_astral(image: NDArray[np.uint8]) -> dict[str, Any]:
    """Colour composition of the central screen; ``present`` for the astral form."""
    native = _native(image)
    if native is None:
        return {"checked": False, "present": None}
    small = cv2.resize(native, ASTRAL_SIZE, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    top, bottom, left, right = ASTRAL_REGION
    region = hsv[top:bottom, left:right].astype(np.int32)
    hue, sat, val = region[..., 0], region[..., 1], region[..., 2]
    purple = float(((hue >= 130) & (hue <= 165) & (sat >= 90) & (val >= 70)).mean())
    bright = float(((hue >= 135) & (hue <= 170) & (sat >= 100) & (val >= 220)).mean())
    spread = float(val.std())
    return {
        "checked": True,
        "purple_share": round(purple, 6),
        "bright_magenta_share": round(bright, 6),
        "brightness_spread": round(spread, 6),
        "present": purple >= ASTRAL_PURPLE and bright >= ASTRAL_BRIGHT
        and spread >= ASTRAL_SPREAD,
    }


def health_digits(image: NDArray[np.uint8]) -> int | None:
    """Number of digit-shaped bright glyphs in the health box (None if unchecked).

    A dead recorder's camera can keep the recorder's ability bar (for example the
    view that follows the planted spike) but shows no health value.
    """
    native = _native(image)
    if native is None or native.ndim != 3:
        return None
    x, y, w, h = HEALTH_BOX
    hsv = cv2.cvtColor(native[y : y + h, x : x + w], cv2.COLOR_BGR2HSV)
    mask = ((hsv[..., 2] > 200) & (hsv[..., 1] < 90)).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    return sum(
        1
        for _, _, width, height, area in stats[1:]
        if HEALTH_DIGIT_HEIGHT[0] <= height <= HEALTH_DIGIT_HEIGHT[1]
        and HEALTH_DIGIT_WIDTH[0] <= width <= HEALTH_DIGIT_WIDTH[1]
        and area >= HEALTH_DIGIT_AREA
    )


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


def measure_frame(
    image: NDArray[np.uint8],
    reference: LabelReference,
    remote: RemoteReference | None = None,
    camera: CameraHintReference | None = None,
) -> dict[str, Any]:
    """Per-frame measurements; only small crops are kept."""
    return {
        "label": measure_label(image, reference),
        "slots": bar_slots(image),
        "health_digits": health_digits(image),
        "remote": None if remote is None else measure_remote(image, remote),
        "camera_hint": None if camera is None else measure_camera_hint(image, camera),
        "astral": measure_astral(image),
    }


def _held_astral(measured: list[tuple[dict[str, Any], dict[str, Any]]]) -> set[str]:
    """Samples of astral-form runs spanning at least ``ASTRAL_MIN_SPAN`` seconds."""
    times = sorted(
        (int(sample["native_pts_tick"]) / 15360, sample["sample_sha256"])
        for sample, m in measured if (m.get("astral") or {}).get("present")
    )
    held: set[str] = set()
    run: list[tuple[float, str]] = []
    for item in [*times, (float("inf"), "")]:
        if run and item[0] - run[-1][0] > ASTRAL_GAP:
            if run[-1][0] - run[0][0] >= ASTRAL_MIN_SPAN:
                held.update(sha for _, sha in run)
            run = []
        run.append(item)
    return held


def camera_rows(
    measured: list[tuple[dict[str, Any], dict[str, Any]]],
    reference: LabelReference,
    remote: RemoteReference | None = None,
    camera: CameraHintReference | None = None,
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
        "remote_reference_sha256": None if remote is None else remote.sha256,
        "camera_hint_reference_sha256": None if camera is None else camera.sha256,
        "label_box": LABEL_BOX,
        "bar_box": BAR_BOX,
        "health_box": HEALTH_BOX,
        "thresholds": {"label_present": LABEL_PRESENT, "label_absent": LABEL_ABSENT,
                       "own_bar": OWN_BAR_MATCH, "remote_hint": REMOTE_HINT_MATCH,
                       "remote_duration": REMOTE_DURATION_MATCH,
                       "astral_purple": ASTRAL_PURPLE, "astral_bright": ASTRAL_BRIGHT,
                       "astral_spread": ASTRAL_SPREAD, "astral_gap": ASTRAL_GAP,
                       "astral_min_span": ASTRAL_MIN_SPAN,
                       "camera_hint": CAMERA_HINT_MATCH},
        "own_bar_prototype_sha256": own.get("prototype_sha256"),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    producer = digest(bindings)
    held = _held_astral(measured)
    rows = []
    counts = {"spectator_label": 0, "remote_control": 0, "camera_view": 0, "astral_view": 0,
              "own_ability_bar": 0, "undecided": 0}
    for sample, m in measured:
        label, slot = m["label"], m["slots"]
        own_score = (
            _slot_similarity(slot, own["prototype"])
            if own["available"] and slot is not None else None
        )
        signals: list[str] = []
        remote_cue = m.get("remote")
        camera_cue = m.get("camera_hint")
        steering = bool(remote_cue and remote_cue["present"])
        viewing = bool(camera_cue and camera_cue["present"])
        if label["state"] == "PRESENT" and not (steering or viewing):
            signals = ["spectator"]
            counts["spectator_label"] += 1
        elif steering and label["state"] != "PRESENT":
            signals = ["remote"]
            counts["remote_control"] += 1
        elif viewing and label["state"] != "PRESENT":
            signals = ["remote"]
            counts["camera_view"] += 1
        elif (m.get("astral") or {}).get("present"):
            if (
                sample["sample_sha256"] in held
                and label["state"] == "ABSENT"
                and (m.get("health_digits") or 0) > 0
            ):
                # The recorder's own living HUD with the held astral form: remote view.
                signals = ["remote"]
                counts["astral_view"] += 1
            else:
                counts["undecided"] += 1
                continue
        elif (
            label["state"] == "ABSENT"
            and own_score is not None and own_score >= OWN_BAR_MATCH
            and (m.get("health_digits") or 0) > 0
        ):
            signals = ["owner_hud"]
            counts["own_ability_bar"] += 1
        else:
            counts["undecided"] += 1
            continue
        rows.append(observation(
            sample=freeze_native_sample(sample),
            producer=producer,
            signals=signals,
            raw={"camera_panel": {"label": label, "remote": remote_cue,
                                  "camera_hint": camera_cue,
                                  "astral": m.get("astral"),
                                  "health_digits": m.get("health_digits"),
                                  "own_ability_bar_score": None if own_score is None
                                  else round(own_score, 6)},
                 "qualified": False, "formal_outputs": 0},
            context={"stream_kind": "camera_panel"},
        ))
    summary = {k: v for k, v in own.items() if k != "prototype"}
    return {"version": VERSION, "bindings": bindings, "own_ability_bar": summary,
            "counts": counts, "observations": rows, "qualified": False,
            "formal_outputs": 0}


NATIVE_TIME_BASE = Fraction(1, 15360)


def native_decode_command(ffmpeg: str, batch: list[int]) -> list[str]:
    """The acquisition's native decode, restricted to the listed source PTS.

    Same binary, seek, filters, pixel transport and PNG encoding as the native
    audit decode in ``match``, so the pixels are those the samples were bound to.
    """
    lower, upper = batch[0] * NATIVE_TIME_BASE, batch[-1] * NATIVE_TIME_BASE
    command = [ffmpeg, "-hide_banner", "-loglevel", "info", "-threads", "1"]
    if lower > 0:
        command += ["-noaccurate_seek", "-seek_timestamp", "1", "-ss", str(float(lower))]
    return command + [
        "-copyts", "-i", "{video}", "-an", "-sn", "-dn", "-map", "0:v:0",
        "-t", str(float(upper + 1)),
        "-vf", f"trim=end_pts={batch[-1] + 1},select={_pts_expression(batch)},showinfo",
        "-fps_mode", "passthrough", "-threads", "1",
        "-c:v", "png", "-compression_level", "1", "-pred", "up",
        "-f", "image2pipe", "pipe:1",
    ]


def decode_samples(
    video: Path, samples: list[dict[str, Any]], missing: list[dict[str, Any]]
) -> Iterator[tuple[dict[str, Any], NDArray[np.uint8]]]:
    """Yield samples decoded by native timestamp whose pixels are identical.

    Frames are decoded with the same native FFmpeg decode the acquisition used
    (not OpenCV's own decoder, whose pixels can differ by platform and build).
    Samples that are not found or differ in pixels are appended to ``missing``.
    """
    wanted: dict[int, list[dict[str, Any]]] = {}
    for sample in samples:
        if sample["native_time_base"] != "1/15360":
            raise ValueError("Native 1/15360 time base required")
        wanted.setdefault(int(sample["native_pts_tick"]), []).append(sample)
    if not wanted:
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("FFmpeg required for the native decode")
    for batch in _native_audit_batches(sorted(wanted), NATIVE_TIME_BASE):
        command = [str(video) if part == "{video}" else part
                   for part in native_decode_command(ffmpeg, batch)]
        with tempfile.TemporaryFile() as log:
            child = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=log, env=_subprocess_environment()
            )
            assert child.stdout is not None
            try:
                frames = list(png_frames(child.stdout))
            finally:
                child.stdout.close()
                code = child.wait()
            if code != 0:
                raise ValueError(f"Native decode failed ({code})")
            log.seek(0)
            ticks = decoded_source_ticks(log.read().decode("utf-8", "replace"),
                                         NATIVE_TIME_BASE)
        if len(ticks) != len(frames):
            raise ValueError("Native decode frame and PTS counts differ")
        for tick, encoded in zip(ticks, frames, strict=True):
            if tick not in wanted:
                continue
            image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Native PNG frame cannot be decoded")
            pixel = hashlib.sha256(image.tobytes()).hexdigest()
            for sample in wanted.pop(tick):
                if sample["native_pixel_sha256"] == pixel:
                    yield sample, np.asarray(image, dtype=np.uint8)
                else:
                    missing.append(sample)
    missing.extend(s for group in wanted.values() for s in group)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--timeline", type=Path, required=True,
                        help="Timeline or observation JSON whose samples are measured")
    parser.add_argument("--label-reference", type=Path, required=True)
    parser.add_argument("--remote-hint", type=Path)
    parser.add_argument("--remote-duration", type=Path)
    parser.add_argument("--camera-hint", type=Path,
                        help="Key hint shown while a placed camera is viewed")
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
    if (args.remote_hint is None) != (args.remote_duration is None):
        raise SystemExit("Both remote references or neither required")
    remote = (
        RemoteReference.load(args.remote_hint, args.remote_duration)
        if args.remote_hint is not None and args.remote_duration is not None else None
    )
    camera = None if args.camera_hint is None else CameraHintReference.load(args.camera_hint)
    missing: list[dict[str, Any]] = []
    measured = [
        (sample, measure_frame(image, reference, remote, camera))
        for sample, image in decode_samples(args.video, list(samples.values()), missing)
    ]
    result = camera_rows(measured, reference, remote, camera)
    result["samples_requested"] = len(samples)
    result["samples_not_pixel_identical"] = len(missing)
    args.output.write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps({"rows": len(result["observations"]), "counts": result["counts"],
                      "own_ability_bar": result["own_ability_bar"],
                      "samples_not_pixel_identical": len(missing)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
