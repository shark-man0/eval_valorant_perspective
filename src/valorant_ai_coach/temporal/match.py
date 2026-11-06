"""Development-only whole-recording timeline CLI with adaptive native sampling.

Source identity is used for admission/provenance only. The observer sees pixels
without timestamps, Source identity, labels, roster, or an initialized state.
Frames stream through a bounded buffer; original PTS and pixel hashes survive.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import struct
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import IO, Any, Protocol, cast

import cv2
import numpy as np

from valorant_ai_coach.video.native import _sha256, decoded_source_ticks
from valorant_ai_coach.video.service import _subprocess_environment

from .evidence import digest, freeze_native_sample, is_sha, native_time
from .game import DevelopmentGameTimeline, observation, round_number_summary
from .match_observer import ProfileHudObserver
from .replay import SourcePolicy, file_sha, peak_rss_mib, read_json, write_private


class PixelObserver(Protocol):
    """Deterministic image-only supplier; no acquisition identity is passed in."""

    fingerprint: str
    bindings: dict[str, Any]

    def inspect(self, image: np.typing.NDArray[np.uint8]) -> dict[str, Any]: ...


def _pts_expression(ticks: list[int]) -> str:
    """Balanced expression avoids FFmpeg's linear expression-depth limit."""
    if not ticks:
        raise ValueError("Native audit points required")
    if len(ticks) == 1:
        return f"eq(pts\\,{ticks[0]})"
    middle = len(ticks) // 2
    return f"({_pts_expression(ticks[:middle])}+{_pts_expression(ticks[middle:])})"


def _native_audit_batches(ticks: list[int], base: Fraction) -> Iterator[list[int]]:
    """Bound both expression size and intervening decoding for sparse audits."""
    if (
        base <= 0
        or any(type(tick) is not int for tick in ticks)
        or any(right <= left for left, right in zip(ticks, ticks[1:], strict=False))
    ):
        raise ValueError("Increasing native audit ticks and positive time base required")
    batch: list[int] = []
    for tick in ticks:
        if batch and (len(batch) >= 512 or (tick - batch[0]) * base > 6):
            yield batch
            batch = []
        batch.append(tick)
    if batch:
        yield batch


def frame_observations(
    measurement: dict[str, Any], sample: dict[str, Any], producer: str
) -> list[dict[str, Any]]:
    """Attach the verified native sample to separately fingerprinted suppliers.

    A composite observer may expose supplier_observations. Their Source/PTS
    cannot override the transport's sample. The summary drives sampling only;
    the shared engine consumes the original supplier claims, once each.
    """
    suppliers = measurement.get("supplier_observations")
    if suppliers is None:
        suppliers = [{**measurement, "producer_fingerprint": producer}]
    elif not isinstance(suppliers, list) or not suppliers:
        raise ValueError("Nonempty supplier observations required")
    allowed = {"producer_fingerprint", "signals", "raw", "context", "map_candidates"}
    rows = []
    for item in suppliers:
        if not isinstance(item, dict) or (
            "supplier_observations" in measurement and set(item) - allowed
        ):
            raise ValueError("Supplier cannot override acquisition or continuity")
        rows.append(
            observation(
                sample=sample,
                producer=item["producer_fingerprint"],
                signals=item["signals"],
                raw=item["raw"],
                context=item.get("context", {}),
                map_candidates=item.get("map_candidates", []),
                continuity={"decode_ok": True},
            )
        )
    if len({r["observation_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate supplier observation is not independent evidence")
    return rows


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        part = stream.read(size - len(result))
        if not part:
            raise ValueError("Truncated native PNG stream")
        result.extend(part)
    return bytes(result)


def png_frames(stream: IO[bytes], *, max_frame_bytes: int = 64 * 1024**2) -> Iterator[bytes]:
    """Bound each encoded native frame independently; never buffer a movie."""
    while True:
        first = stream.read(1)
        if not first:
            return
        signature = first + _read_exact(stream, 7)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Expected native PNG framing")
        encoded = bytearray(signature)
        while True:
            header = _read_exact(stream, 8)
            size = struct.unpack(">I", header[:4])[0]
            if len(encoded) + size + 12 > max_frame_bytes:
                raise ValueError("Native frame exceeds memory budget")
            encoded.extend(header)
            encoded.extend(_read_exact(stream, size + 4))
            if header[4:] == b"IEND":
                yield bytes(encoded)
                break


def refinement_windows(
    records: list[dict[str, Any]],
    *,
    max_windows: int,
    padding: Fraction = Fraction(1),
    max_total_seconds: Fraction = Fraction(240),
    origin: Fraction = Fraction(0),
    selection_policy: str = "chronological",
) -> tuple[list[tuple[Fraction, Fraction]], int]:
    """Select from observed changes only; no known Round times or Source cases."""
    if type(padding) is not Fraction or not 0 <= padding <= 10:
        raise ValueError("Exact refinement padding between zero and ten seconds required")
    if selection_policy not in {"chronological", "balanced"}:
        raise ValueError("Known development refinement selection policy required")
    windows: list[tuple[Fraction, Fraction]] = []
    candidates: list[tuple[Fraction, Fraction, Fraction, int]] = []
    for before, after in zip(records, records[1:], strict=False):
        a, b = before["measurement"], after["measurement"]
        clocks = [v["context"].get("timer_seconds") for v in (a, b)]
        changed = (
            a["signals"] != b["signals"]
            or a["context"].get("score") != b["context"].get("score")
            or bool(a.get("map_candidates")) != bool(b.get("map_candidates"))
            or all(v is not None for v in clocks)
            and abs(clocks[1] - clocks[0]) > 2
        )
        if not changed:
            continue
        lower = max(origin, native_time(before["sample"]) - padding)
        upper = native_time(after["sample"]) + padding
        candidates.append((lower, upper, native_time(after["sample"]), _change_priority(a, b)))
        if windows and lower <= windows[-1][1]:
            windows[-1] = windows[-1][0], max(upper, windows[-1][1])
        else:
            windows.append((lower, upper))
    if selection_policy == "balanced":
        return _balanced_refinement(
            candidates, windows, max_windows=max_windows,
            max_total_seconds=max_total_seconds, origin=origin,
            end=native_time(records[-1]["sample"]) if records else origin,
            proposal_seconds=max(Fraction(6), padding * 2 + 2),
        )
    chosen = []
    remaining = max_total_seconds
    deferred = max(0, len(windows) - max_windows)
    for lower, upper in windows[:max_windows]:
        if remaining <= 0:
            deferred += 1
            continue
        end = min(upper, lower + remaining)
        chosen.append((lower, end))
        remaining -= end - lower
        deferred += int(end < upper)
    return chosen, deferred


def _change_priority(before: dict[str, Any], after: dict[str, Any]) -> int:
    """Rank measured changes for acquisition, without interpreting an event."""
    left, right = set(before["signals"]), set(after["signals"])
    for vocabulary, rank in [
        ({"buy", "active", "result", "intermission"}, 4),
        ({"owner_hud", "spectator", "remote", "death", "downed"}, 3),
    ]:
        a, b = left & vocabulary, right & vocabulary
        if len(a) == len(b) == 1 and a != b:
            return rank
    scores = [row["context"].get("score") for row in (before, after)]
    if all(score is not None for score in scores) and scores[0] != scores[1]:
        return 3
    return 1


def _balanced_refinement(
    candidates: list[tuple[Fraction, Fraction, Fraction, int]],
    regions: list[tuple[Fraction, Fraction]],
    *,
    max_windows: int,
    max_total_seconds: Fraction,
    origin: Fraction,
    end: Fraction,
    proposal_seconds: Fraction = Fraction(6),
) -> tuple[list[tuple[Fraction, Fraction]], int]:
    """Cover temporal strata before spending unused slots on further changes.

    Each proposal has a bounded configured width, preventing merged OCR flicker from
    spending the entire budget in one prefix. The returned deferred count keeps
    the legacy unit: original merged regions not fully refined, including
    partially refined regions. Neither a selection nor its priority is an event.
    """
    if max_windows <= 0 or max_total_seconds <= 0 or not candidates:
        return [], len(regions)
    width = min(proposal_seconds, max_total_seconds)
    slots = min(max_windows, max(1, int(max_total_seconds // width)), len(candidates))
    span = max(end - origin, Fraction(1))
    strata: dict[int, list[int]] = {}
    for i, (_, _, anchor, _) in enumerate(candidates):
        bucket = max(0, min(slots - 1, int((anchor - origin) * slots / span)))
        strata.setdefault(bucket, []).append(i)
    selected: set[int] = set()
    for bucket, indices in strata.items():
        center = origin + span * Fraction(2 * bucket + 1, 2 * slots)
        selected.add(max(indices, key=lambda i: (
            candidates[i][3], -abs(candidates[i][2] - center), -candidates[i][2]
        )))
    while len(selected) < slots:
        remaining = set(range(len(candidates))) - selected
        selected.add(max(remaining, key=lambda i: (
            candidates[i][3],
            min(abs(candidates[i][2] - candidates[j][2]) for j in selected),
            -candidates[i][2],
        )))
    chosen: list[tuple[Fraction, Fraction]] = []
    proposals = []
    for i in selected:
        lower, upper, anchor, _ = candidates[i]
        if upper - lower > width:
            lower = max(lower, min(anchor - width / 2, upper - width))
            upper = lower + width
        proposals.append((lower, upper))
    for lower, upper in sorted(proposals):
        if chosen and lower <= chosen[-1][1]:
            chosen[-1] = chosen[-1][0], max(upper, chosen[-1][1])
        else:
            chosen.append((lower, upper))
    deferred = sum(not any(a <= lower and upper <= b for a, b in chosen)
                   for lower, upper in regions)
    return chosen, deferred


def run_match(
    *,
    policy_path: Path,
    source_id: str,
    reader_config: Path,
    output: Path,
    coarse_seconds: Fraction = Fraction(1),
    dense_seconds: Fraction = Fraction(1, 5),
    max_refinement_windows: int = 40,
    stop_after: int | None = None,
    retain_frames: bool = False,
    observer_factory: Callable[[Path], PixelObserver] | None = None,
    audit_sample_plan: Path | None = None,
    refinement_selection_policy: str = "chronological",
    refinement_padding_seconds: Fraction = Fraction(1),
    report_view_bridge: bool = False,
    buy_clock_expiry: bool = False,
    provisional_map_roles: bool = False,
    active_clock_bridge: bool = False,
) -> dict[str, Any]:
    began = time.perf_counter()
    implementation_sha = file_sha(Path(__file__))
    engine_sha = file_sha(Path(__file__).with_name("game.py"))
    map_role_sha = file_sha(Path(__file__).with_name("map_roles.py"))
    if not 0 < dense_seconds < coarse_seconds <= 2 or max_refinement_windows < 0:
        raise ValueError("Bounded coarse/dense observation cadence required")
    if refinement_selection_policy not in {"chronological", "balanced"}:
        raise ValueError("Known development refinement selection policy required")
    if (type(refinement_padding_seconds) is not Fraction
            or not 0 <= refinement_padding_seconds <= 10):
        raise ValueError("Exact refinement padding between zero and ten seconds required")
    if type(report_view_bridge) is not bool:
        raise ValueError("Explicit development report-view reconciliation boolean required")
    if type(provisional_map_roles) is not bool:
        raise ValueError("Explicit development provisional Map role boolean required")
    if type(active_clock_bridge) is not bool:
        raise ValueError("Explicit development ACTIVE clock bridge boolean required")
    if stop_after is not None and (type(stop_after) is not int or not 0 < stop_after <= 180):
        raise ValueError("Pilot limit must be at most 180 seconds")
    output = output.expanduser().resolve()
    if output.exists() or any((p / ".git").exists() for p in output.parents):
        raise ValueError("New private output directory outside Git required")
    policy_data = read_json(policy_path)
    policy = SourcePolicy(policy_data)
    candidates = [v for v in policy.allowed.values() if v["video_id"] == source_id]
    if len(candidates) != 1:
        raise ValueError("Registered, explicitly admitted DEVELOPMENT source required")
    source = candidates[0]
    video = Path(source["managed_path"])
    if _sha256(video) != source["source_sha256"]:
        raise ValueError("Source bytes changed")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("FFmpeg and ffprobe required")
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=time_base,width,height,duration,duration_ts,start_pts",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        env=_subprocess_environment(),
    )
    stream = json.loads(proc.stdout)["streams"][0]
    base = Fraction(stream["time_base"])
    duration = int(stream["duration_ts"]) * base
    native_start = int(stream["start_pts"]) * base
    if base <= 0 or duration <= 0:
        raise ValueError("Native stream timing required")
    limit = min(duration, Fraction(stop_after)) if stop_after is not None else duration
    audit_requests: dict[int, list[dict[str, Any]]] = {}
    deferred_audits = 0
    audit_plan_sha = None if audit_sample_plan is None else file_sha(audit_sample_plan)
    if audit_sample_plan is not None:
        plan = read_json(audit_sample_plan)
        if set(plan) != {"schema", "samples"} or plan["schema"] != "development_native_audit_v1":
            raise ValueError("Native-sample-only audit plan required")
        if not isinstance(plan["samples"], list):
            raise ValueError("Native sample list required")
        for reference in plan["samples"]:
            if not isinstance(reference, dict):
                raise ValueError("Native sample record required")
            sample = freeze_native_sample(reference)
            if set(reference) - set(sample):
                raise ValueError("Audit sample cannot carry labels or initialization")
            policy.admit(sample)
            if sample["source_sha256"] != source["source_sha256"]:
                continue
            if (
                Fraction(sample["native_time_base"]) != base
                or sample["frame_size_px"] != [int(stream["width"]), int(stream["height"])]
                or not native_start <= native_time(sample) < native_start + duration
            ):
                raise ValueError("Audit sample outside the admitted native stream")
            if native_time(sample) >= native_start + limit:
                deferred_audits += 1
                continue
            audit_requests.setdefault(sample["native_pts_tick"], []).append(sample)
    make_observer: Callable[[Path], PixelObserver] = observer_factory or ProfileHudObserver
    observer = make_observer(reader_config)
    if not is_sha(observer.fingerprint):
        raise ValueError("Bound pixel observer fingerprint required")
    bindings_sha = digest(observer.bindings)
    baseline_producers: list[str] = observer.bindings.get("baseline_producer_fingerprints", [])
    if (
        not isinstance(baseline_producers, list)
        or not all(is_sha(p) for p in baseline_producers)
        or len(set(baseline_producers)) != len(baseline_producers)
    ):
        raise ValueError("Explicit baseline supplier fingerprints required")
    permitted_producers: list[str] = observer.bindings.get(
        "supplier_producer_fingerprints", [observer.fingerprint]
    )
    if (
        not isinstance(permitted_producers, list)
        or not permitted_producers
        or not all(is_sha(p) for p in permitted_producers)
        or len(set(permitted_producers)) != len(permitted_producers)
    ):
        raise ValueError("Bound supplier fingerprints required")
    decoder_shas = {"ffmpeg": file_sha(Path(ffmpeg)), "ffprobe": file_sha(Path(ffprobe))}
    epoch = uuid.uuid4().hex
    output.mkdir(parents=True, mode=0o700)
    records: dict[int, dict[str, Any]] = {}

    def decode(
        lower: Fraction,
        upper: Fraction,
        step: Fraction,
        name: str,
        expected: dict[int, list[dict[str, Any]]] | None = None,
    ) -> None:
        tick_lower, tick_upper = math.ceil(lower / base), math.floor(upper / base)
        filters = (
            f"trim=end_pts={tick_upper + 1},select=between(pts\\,{tick_lower}\\,{tick_upper}),"
            f"select=isnan(prev_selected_pts)+gte(t-prev_selected_t\\,{float(step)}),"
            "showinfo"
        )
        if expected is not None:
            filters = (
                f"trim=end_pts={tick_upper + 1},select={_pts_expression(sorted(expected))},showinfo"
            )
        command = [ffmpeg, "-hide_banner", "-loglevel", "info", "-threads", "1"]
        if lower > 0:
            command += ["-noaccurate_seek", "-seek_timestamp", "1", "-ss", str(float(lower))]
        command += [
            "-copyts",
            "-i",
            str(video),
            "-an",
            "-sn",
            "-dn",
            "-map",
            "0:v:0",
            "-t",
            str(float(upper + 1)),
            "-vf",
            filters,
            "-fps_mode",
            "passthrough",
            "-threads",
            "1",
            "-c:v",
            "png",
            "-compression_level",
            "1",
            "-pred",
            "up",
            "-f",
            "image2pipe",
            "pipe:1",
        ]
        log_path = output / f"{name}_decode.log"
        pending: list[dict[str, Any]] = []
        with log_path.open("x", encoding="utf-8") as log:
            child = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=log, env=_subprocess_environment()
            )
            assert child.stdout is not None
            try:
                for encoded in png_frames(child.stdout):
                    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None or [image.shape[1], image.shape[0]] != [
                        int(stream["width"]),
                        int(stream["height"]),
                    ]:
                        raise ValueError("Native decoded geometry mismatch")
                    # Bind the decoded native pixels, before any supplier's
                    # in-place preprocessing can alter its analysis buffer.
                    native_pixel_sha = hashlib.sha256(image.tobytes()).hexdigest()
                    measurement = deepcopy(observer.inspect(
                        cast(np.typing.NDArray[np.uint8], image)))
                    item = {
                        "encoded_sha": hashlib.sha256(encoded).hexdigest(),
                        "pixel_sha": native_pixel_sha,
                        "measurement": measurement,
                    }
                    if retain_frames:
                        path = output / f"{name}_{len(pending):06d}.png"
                        path.write_bytes(encoded)
                        path.chmod(0o600)
                        item["path"] = str(path)
                    pending.append(item)
                    if len(pending) % 60 == 0:
                        print(
                            json.dumps(
                                {
                                    "pass": name,
                                    "observed": len(pending),
                                    "elapsed_sec": time.perf_counter() - began,
                                }
                            ),
                            flush=True,
                        )
                if child.wait(timeout=60) != 0:
                    raise ValueError("Decoder did not complete successfully; inspect private log")
            finally:
                child.stdout.close()
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=60)
        ticks = decoded_source_ticks(log_path.read_text(encoding="utf-8"), base)
        if (
            len(ticks) != len(pending)
            or not ticks
            or any(not tick_lower <= t <= tick_upper for t in ticks)
            or any(b <= a for a, b in zip(ticks, ticks[1:], strict=False))
        ):
            raise ValueError("Decoder output/native PTS correspondence failed")
        if expected is not None and list(ticks) != sorted(expected):
            raise ValueError("Audit native PTS missing or changed")
        for tick, item in zip(ticks, pending, strict=True):
            if expected is not None and any(
                s["native_pixel_sha256"] != item["pixel_sha"] for s in expected[tick]
            ):
                raise ValueError("Audit native pixels changed")
            if tick in records:
                if records[tick]["sample"]["native_pixel_sha256"] != item["pixel_sha"]:
                    raise ValueError("Repeated decoding changed native pixels")
                continue
            sample = freeze_native_sample(
                {
                    "source_id": source_id,
                    "source_sha256": source["source_sha256"],
                    "acquisition_id": epoch,
                    "native_epoch": epoch,
                    "native_pts_tick": tick,
                    "native_time_base": str(base),
                    "frame_size_px": [int(stream["width"]), int(stream["height"])],
                    "acquired_frame_sha256": item.pop("encoded_sha"),
                    "native_pixel_sha256": item.pop("pixel_sha"),
                }
            )
            records[tick] = {"sample": sample, "pass": name, **item}

    exclusive_end = native_start + limit - base
    decode(native_start, exclusive_end, coarse_seconds, "coarse")
    coarse = [records[k] for k in sorted(records)]
    windows, deferred = refinement_windows(
        coarse, max_windows=max_refinement_windows, origin=native_start,
        selection_policy=refinement_selection_policy,
        padding=refinement_padding_seconds,
    )
    for index, (lower, upper) in enumerate(windows):
        decode(lower, min(upper, exclusive_end), dense_seconds, f"dense_{index:04d}")
    # Evaluation references never change automatic acquisition or inference.
    # Keep their extra observations, exact PTS and pixels in a separate sidecar.
    automatic_ticks = set(records)
    needed = sorted(set(audit_requests) - set(records))
    audit_batches = list(_native_audit_batches(needed, base))
    for index, batch in enumerate(audit_batches):
        decode(
            batch[0] * base,
            batch[-1] * base,
            dense_seconds,
            f"audit_{index:04d}",
            {t: audit_requests[t] for t in batch},
        )
    aliases = []
    for tick, references in sorted(audit_requests.items()):
        actual = records[tick]["sample"]
        for reference in references:
            if actual["native_pixel_sha256"] != reference["native_pixel_sha256"]:
                raise ValueError("Audit native pixels changed")
            aliases.append(
                {
                    "reference_sample": reference,
                    "observed_sample": actual,
                    "criterion": "same_Source_native_PTS_timebase_size_pixels",
                    "independent_confirmation": False,
                    "already_automatically_observed": tick in automatic_ticks,
                }
            )
    if _sha256(video) != source["source_sha256"]:
        raise ValueError("Source bytes changed during processing")
    if audit_sample_plan is not None and file_sha(audit_sample_plan) != audit_plan_sha:
        raise ValueError("Native audit plan changed during execution")
    if file_sha(Path(__file__)) != implementation_sha:
        raise ValueError("Acquisition implementation changed during execution")
    if (file_sha(Path(__file__).with_name("game.py")) != engine_sha
            or file_sha(Path(__file__).with_name("map_roles.py")) != map_role_sha):
        raise ValueError("Shared engine changed during execution")
    if (
        digest(observer.bindings) != bindings_sha
        or make_observer(reader_config).fingerprint != observer.fingerprint
    ):
        raise ValueError("Pixel observer bindings changed during execution")
    if decoder_shas != {"ffmpeg": file_sha(Path(ffmpeg)), "ffprobe": file_sha(Path(ffprobe))}:
        raise ValueError("Native decoder binaries changed during execution")
    engine = DevelopmentGameTimeline(
        fuse_exact_native_evidence=True, report_view_bridge=report_view_bridge,
        buy_clock_expiry=buy_clock_expiry,
        provisional_map_roles=provisional_map_roles,
        active_clock_bridge=active_clock_bridge,
    )
    baseline_engine = (
        DevelopmentGameTimeline(
            fuse_exact_native_evidence=True, report_view_bridge=report_view_bridge,
            buy_clock_expiry=buy_clock_expiry,
            provisional_map_roles=provisional_map_roles,
            active_clock_bridge=active_clock_bridge,
        )
        if baseline_producers else None
    )
    for tick in sorted(records):
        r = records[tick]
        m = r["measurement"]
        suppliers = frame_observations(m, r["sample"], observer.fingerprint)
        if {s["producer_fingerprint"] for s in suppliers} - set(permitted_producers):
            raise ValueError("Unbound supplier fingerprint at native frame")
        if set(baseline_producers) - {s["producer_fingerprint"] for s in suppliers}:
            raise ValueError("Baseline supplier missing at an observed native frame")
        if tick not in automatic_ticks:
            continue
        for supplied in suppliers:
            engine.add(supplied)
            if (
                baseline_engine is not None
                and supplied["producer_fingerprint"] in baseline_producers
            ):
                baseline_engine.add(supplied)
    timeline = engine.rebuild()
    write_private(
        output / "observations_PRIVATE.json",
        {
            "records": [records[t] for t in sorted(automatic_ticks)],
            "reader_bindings": observer.bindings,
            "reader_fingerprint": observer.fingerprint,
        },
    )
    write_private(output / "timeline_PRIVATE.json", timeline)
    if baseline_engine is not None:
        write_private(output / "baseline_timeline_PRIVATE.json", baseline_engine.rebuild())
    if audit_sample_plan is not None:
        write_private(output / "native_audit_aliases_PRIVATE.json", {"records": aliases})
        write_private(output / "audit_observations_PRIVATE.json", {
            "schema": "development_native_audit_sidecar_v1",
            "records": [records[t] for t in sorted(set(records) - automatic_ticks)],
            "reader_bindings": observer.bindings,
            "reader_fingerprint": observer.fingerprint,
            "recognition_or_initialization_input": False,
            "qualified_facts": [], "qualified_events": [],
        })
    # Seconds outside observed endpoints remain explicit unobserved rows.
    relative_bins: dict[int, list[dict[str, Any]]] = {}
    for frame in timeline["frames"]:
        second = int((native_time(frame["sample"]) - native_start) // 1)
        relative_bins.setdefault(second, []).append(frame)
    with (output / "timeline_1s_PRIVATE.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "source_id",
                "recording_second",
                "observation_present",
                "round",
                "life",
                "camera",
                "round_hypotheses",
                "round_uncertainty",
                "life_hypotheses",
                "life_uncertainty",
                "camera_hypotheses",
                "camera_uncertainty",
                "qualification",
                "round_number",
                "round_number_candidates",
                "round_number_uncertainty",
            ]
        )
        for second in range(math.ceil(limit)):
            rows = relative_bins.get(second, [])
            number = round_number_summary([r["round_number"] for r in rows])
            writer.writerow(
                [
                    source_id,
                    second,
                    bool(rows),
                    *(
                        next(iter(values)) if len(values) == 1 else "UNKNOWN"
                        for d in ("round", "life", "camera")
                        for values in [{r[d]["value"] for r in rows}]
                    ),
                    *(
                        "|".join(
                            sorted(
                                {
                                    v
                                    for r in rows
                                    for v in (
                                        r[d]["hypotheses"]
                                        if field == "hypotheses"
                                        else [r[d]["uncertainty"]]
                                    )
                                }
                            )
                        )
                        or "UNKNOWN"
                        for d in ("round", "life", "camera")
                        for field in ("hypotheses", "uncertainty")
                    ),
                    "development_only",
                    number["value"] if number["value"] is not None else "UNKNOWN",
                    "|".join(str(n) for n in number["candidates"]) or "UNKNOWN",
                    number["uncertainty"],
                ]
            )
    receipt = {
        "version": "development_full_match_v2",
        "source_id": source_id,
        "source_sha256": source["source_sha256"],
        "physical_match_id": source["physical_match_id"],
        "duration_seconds": str(duration),
        "native_start_pts_tick": int(stream["start_pts"]),
        "sampling": {
            "coarse_seconds": str(coarse_seconds),
            "dense_seconds": str(dense_seconds),
            "max_refinement_windows": max_refinement_windows,
            "max_refinement_seconds": 240,
            "selection_policy": refinement_selection_policy,
            "refinement_padding_seconds": str(refinement_padding_seconds),
            "balanced_proposal_seconds": str(max(Fraction(6), refinement_padding_seconds * 2 + 2)),
            "deferred_unit": "original_merged_regions_not_fully_refined",
        },
        "processed_limit_seconds": str(limit),
        "whole_file_completed": stop_after is None,
        "source_bytes_verified_before_and_after": True,
        "policy_sha256": file_sha(policy_path),
        "reader_fingerprint": observer.fingerprint,
        "implementation_sha256": implementation_sha,
        "shared_engine_sha256": engine_sha,
        "shared_engine_configuration": timeline["configuration"],
        "state_reconstruction_fingerprint": digest({
            "pixel_observer_fingerprint": observer.fingerprint,
            "shared_engine_sha256": engine_sha,
            "configuration": timeline["configuration"],
        }),
        "decoder_binary_sha256s": decoder_shas,
        "same_native_baseline_producers": baseline_producers,
        "native_audit": {
            "plan_sha256": audit_plan_sha,
            "decode_batches": len(audit_batches),
            "max_decode_batch_span_seconds": 6,
            "max_decode_batch_points": 512,
            "matched_references": len(aliases),
            "additional_native_points": len(needed),
            "deferred_outside_pilot_limit": deferred_audits,
            "recognition_or_initialization_input": False,
        },
        "all_decoded_frame_PTS_audited": False,
        "epoch": epoch,
        "coarse_points": len(coarse),
        "observed_native_points": len(automatic_ticks),
        "audit_only_native_points": len(set(records) - automatic_ticks),
        "total_decoded_native_points": len(records),
        "refinement_windows": [[str(a), str(b)] for a, b in windows],
        "deferred_refinement_windows": deferred,
        "elapsed_seconds": time.perf_counter() - began,
        "python_peak_RSS_MiB": peak_rss_mib(),
        "semantic_continuity": "UNKNOWN",
        "native_frame_PTS_retained": True,
        "formal_outputs": 0,
        "map_reader_status": "UNCONFIGURED",
        "recognition_accuracy": None,
        "artifact_sha256s": {
            name: file_sha(output / name)
            for name in (
                "observations_PRIVATE.json",
                "timeline_PRIVATE.json",
                "timeline_1s_PRIVATE.csv",
            )
        },
    }
    if baseline_engine is not None:
        receipt["artifact_sha256s"]["baseline_timeline_PRIVATE.json"] = file_sha(
            output / "baseline_timeline_PRIVATE.json"
        )
    if audit_sample_plan is not None:
        receipt["artifact_sha256s"]["native_audit_aliases_PRIVATE.json"] = file_sha(
            output / "native_audit_aliases_PRIVATE.json"
        )
        receipt["artifact_sha256s"]["audit_observations_PRIVATE.json"] = file_sha(
            output / "audit_observations_PRIVATE.json"
        )
    receipt["receipt_id"] = digest(receipt)
    write_private(output / "completion_PRIVATE.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--reader-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-refinement-windows", type=int, default=40)
    parser.add_argument(
        "--refinement-policy", choices=["chronological", "balanced"], default="chronological"
    )
    parser.add_argument("--refinement-padding-seconds", type=Fraction, default=Fraction(1))
    parser.add_argument("--pilot-seconds", type=int)
    parser.add_argument("--retain-frames", action="store_true")
    parser.add_argument("--audit-sample-plan", type=Path)
    parser.add_argument("--report-view-bridge", action="store_true")
    parser.add_argument("--buy-clock-expiry", action="store_true")
    parser.add_argument("--provisional-map-roles", action="store_true")
    parser.add_argument("--active-clock-bridge", action="store_true")
    args = parser.parse_args()
    result = run_match(
        policy_path=args.policy,
        source_id=args.source_id,
        reader_config=args.reader_config,
        output=args.output,
        max_refinement_windows=args.max_refinement_windows,
        refinement_selection_policy=args.refinement_policy,
        refinement_padding_seconds=args.refinement_padding_seconds,
        stop_after=args.pilot_seconds,
        retain_frames=args.retain_frames,
        audit_sample_plan=args.audit_sample_plan,
        report_view_bridge=args.report_view_bridge,
        buy_clock_expiry=args.buy_clock_expiry,
        provisional_map_roles=args.provisional_map_roles,
        active_clock_bridge=args.active_clock_bridge,
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
