"""Scoring protocol of the independent evaluation, fixed before any hold-out is opened.

The analysis run (``independent_evaluation``) never scores. This module holds the
whole protocol that does, so that it is bound by the same code digest as the
recogniser and cannot change after a plan is frozen:

* ``frame-kit`` draws the frames a person labels. The seconds are a deterministic
  function of the recording id and its duration only (never of a prediction), and
  the kit shows no prediction.
* ``boundary-kit`` lists, per recording, the round numbers whose start and end a
  person times, again from the recording id only. After the person gives an
  approximate time, ``boundary-frames`` cuts one frame per second around it so the
  person can pick the exact second.
* ``score`` compares the person's labels with the frozen run and reports, per
  domain (Round, Life, Camera), accuracy, coverage (acquisition rate), error rate,
  abstention, and the boundary time error. It changes nothing in the run.

Usage::

    python -m valorant_ai_coach.temporal.independent_scoring frame-kit \\
        --run RUN_DIR --kit KIT_DIR
    python -m valorant_ai_coach.temporal.independent_scoring boundary-kit \\
        --run RUN_DIR --kit KIT_DIR
    python -m valorant_ai_coach.temporal.independent_scoring boundary-frames \\
        --run RUN_DIR --kit KIT_DIR --approximate approx.csv
    python -m valorant_ai_coach.temporal.independent_scoring score \\
        --run RUN_DIR --kit KIT_DIR --frame-labels frames.csv \\
        --boundary-labels boundaries.csv --output report_PRIVATE.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import Any

from .replay import file_sha, read_json, write_private

VERSION = "independent_scoring_v1"
# The protocol. Every constant here is bound by the plan's code digest.
PROTOCOL: dict[str, Any] = {
    "version": VERSION,
    "seed": "valorant-independent-scoring-v1",
    "frames_per_recording": 30,
    "frame_offset_seconds": "1/2",
    "boundary_rounds_per_recording": 6,
    "round_order_max": 40,
    "boundary_window_seconds": 6,
    "boundary_association_seconds": 15,
    "confidence_interval": "wilson_95",
}
DOMAINS: dict[str, str] = {
    "round": "round_state", "life": "life_state", "camera": "camera_state",
}
# Labels a person may give. UNSURE is excluded from scoring. OUT_OF_ROUND / NA mark
# frames where the state is not defined (loading, agent select, menus, the final
# scoreboard); there, any definite prediction is counted as a false claim.
LABELS: dict[str, tuple[str, ...]] = {
    "round": ("BUY", "ACTIVE", "ENDED", "INTERMISSION", "OUT_OF_ROUND", "UNSURE"),
    "life": ("ALIVE", "DOWNED", "DEAD", "NA", "UNSURE"),
    "camera": ("SELF", "SPECTATOR", "REMOTE", "NA", "UNSURE"),
}
UNDEFINED = {"round": "OUT_OF_ROUND", "life": "NA", "camera": "NA"}
BOUNDARY_KINDS = {"start": "round_start", "end": "round_end"}


# ---------------------------------------------------------------- sampling


def _rng(*parts: str) -> random.Random:
    key = "|".join((PROTOCOL["seed"], *parts)).encode("utf-8")
    return random.Random(int.from_bytes(hashlib.sha256(key).digest(), "big"))


def frame_seconds(recording_id: str, duration_seconds: Fraction) -> list[int]:
    """Distinct whole recording seconds to label; depends on id and duration only."""
    whole = math.floor(duration_seconds - Fraction(PROTOCOL["frame_offset_seconds"]))
    count = min(PROTOCOL["frames_per_recording"], max(whole, 0))
    return sorted(_rng("frames", recording_id).sample(range(whole), count))


def round_order(recording_id: str) -> list[int]:
    """Order in which round numbers are timed; the first N actually played are used."""
    order = list(range(1, PROTOCOL["round_order_max"] + 1))
    _rng("rounds", recording_id).shuffle(order)
    return order


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (
        1 + z * z / total
    )
    return [round(centre - half, 4), round(centre + half, 4)]


# ---------------------------------------------------------------- run access


def _run_recordings(run: Path) -> list[dict[str, Any]]:
    receipt = read_json(run / "independent_evaluation_receipt_PRIVATE.json")
    if receipt.get("formal_qualification") != "NOT_GRANTED":
        raise ValueError("Independent evaluation receipt required")
    return list(receipt["results"])


def _duration(run: Path, recording_id: str) -> Fraction:
    receipt = read_json(run / recording_id / "acquisition" / "completion_PRIVATE.json")
    return Fraction(receipt["duration_seconds"])


def _video(run: Path, recording_id: str) -> Path:
    from valorant_ai_coach.recordings.catalog import RecordingCatalog

    policy = read_json(run / recording_id / "policy_PRIVATE.json")
    catalog = RecordingCatalog(Path(policy["catalog"]), path_map=policy.get("path_map") or {})
    record = catalog.state.recordings[recording_id]
    location = record.locations.get("managed") or record.locations.get("original")
    if location is None:
        raise ValueError(f"No location for {recording_id}")
    return catalog.local_path(location["path"])


def _cut(video: Path, at_seconds: Fraction, target: Path) -> None:
    """One frame at ``at_seconds`` after the first frame (the timeline's origin)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("ffmpeg required")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{float(at_seconds):.3f}",
         "-i", str(video), "-frames:v", "1", "-q:v", "3", "-n", str(target)],
        check=True, timeout=600,
    )
    if not target.exists():
        raise ValueError(f"No frame at {float(at_seconds):.3f}s in {video.name}")


def _letters(results: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {row["recording_id"]: chr(ord("A") + i) for i, row in enumerate(results)}


# ---------------------------------------------------------------- kits


def frame_kit(run: Path, kit: Path) -> dict[str, Any]:
    results = _run_recordings(run)
    kit.mkdir(parents=True, exist_ok=True)
    (kit / "frames").mkdir()
    letters = _letters(results)
    items = [
        (row["recording_id"], second)
        for row in results
        for second in frame_seconds(row["recording_id"], _duration(run, row["recording_id"]))
    ]
    _rng("kit-order", *sorted(letters)).shuffle(items)
    offset = Fraction(PROTOCOL["frame_offset_seconds"])
    key = []
    for number, (rid, second) in enumerate(items, start=1):
        name = f"{number:03d}.jpg"
        _cut(_video(run, rid), second + offset, kit / "frames" / name)
        key.append({"no": f"{number:03d}", "recording_id": rid, "recording": letters[rid],
                    "second": second, "file": name,
                    "sha256": file_sha(kit / "frames" / name)})
    with (kit / "frame_labels_TEMPLATE.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["no", "round", "life", "camera", "note"])
        for row in key:
            writer.writerow([row["no"], "", "", "", ""])
    manifest = {"version": VERSION, "protocol": PROTOCOL, "frames": key}
    write_private(kit / "frame_key_PRIVATE.json", manifest)
    (kit / "label_frames.html").write_text(_label_page([r["no"] for r in key]),
                                          encoding="utf-8")
    return manifest


def _label_page(numbers: Sequence[str]) -> str:
    """A local page to label the frames; it saves frame_labels.csv in the browser."""
    groups = {d: list(LABELS[d]) for d in DOMAINS}
    rows = []
    for no in numbers:
        cells = []
        for domain, values in groups.items():
            options = "".join(
                f'<label><input type="radio" name="{domain}{no}" value="{v}">{v}</label> '
                for v in values)
            cells.append(f"<div><b>{domain}</b> {options}</div>")
        rows.append(f'<section id="f{no}"><h3>{no}</h3>'
                    f'<img src="frames/{no}.jpg" loading="lazy" width="960">'
                    f'{"".join(cells)}<input name="note{no}" placeholder="note"></section>')
    script = (
        "function save(){const n=__NUMBERS__;let t='no,round,life,camera,note\\n';"
        "for(const no of n){const g=d=>{const e=document.querySelector("
        "`input[name=${d}${no}]:checked`);return e?e.value:''};"
        "const note=document.querySelector(`input[name=note${no}]`).value.replace(/[,\\n]/g,' ');"
        "t+=[no,g('round'),g('life'),g('camera'),note].join(',')+'\\n'}"
        "const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],"
        "{type:'text/csv'}));a.download='frame_labels.csv';a.click()}"
    ).replace("__NUMBERS__", json.dumps(list(numbers)))
    return ("<!doctype html><meta charset='utf-8'><title>frame labels</title>"
            "<style>body{font-family:sans-serif;margin:16px}section{margin:24px 0;"
            "border-top:1px solid #ccc}label{margin-right:10px}</style>"
            "<button onclick='save()'>frame_labels.csv を保存</button>"
            + "".join(rows) + "<button onclick='save()'>frame_labels.csv を保存</button>"
            f"<script>{script}</script>")


def boundary_kit(run: Path, kit: Path) -> dict[str, Any]:
    results = _run_recordings(run)
    kit.mkdir(parents=True, exist_ok=True)
    letters = _letters(results)
    rows = []
    for row in results:
        rid = row["recording_id"]
        rows.append({"recording_id": rid, "recording": letters[rid],
                     "video": _video(run, rid).name, "round_order": round_order(rid)})
    with (kit / "boundary_approx_TEMPLATE.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["recording", "rounds_played", "round", "start_approx", "end_approx"])
        for row in rows:
            for number in row["round_order"][:12]:
                writer.writerow([row["recording"], "", number, "", ""])
    manifest = {"version": VERSION, "protocol": PROTOCOL, "recordings": rows}
    write_private(kit / "boundary_order_PRIVATE.json", manifest)
    return manifest


def _clock(text: str) -> int:
    parts = [int(p) for p in text.strip().split(":")]
    total = 0
    for part in parts:
        total = total * 60 + part
    return total


def selected_rounds(order: Sequence[int], played: int) -> list[int]:
    return [n for n in order if n <= played][: PROTOCOL["boundary_rounds_per_recording"]]


def boundary_frames(run: Path, kit: Path, approximate: Path) -> dict[str, Any]:
    orders = {r["recording"]: r for r in read_json(kit / "boundary_order_PRIVATE.json")[
        "recordings"]}
    with approximate.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    played: dict[str, int] = {}
    for row in rows:
        if row["rounds_played"].strip():
            played[row["recording"]] = int(row["rounds_played"])
    out = kit / "boundary_frames"
    out.mkdir(exist_ok=False)
    window = PROTOCOL["boundary_window_seconds"]
    offset = Fraction(PROTOCOL["frame_offset_seconds"])
    items = []
    for letter, info in sorted(orders.items()):
        if letter not in played:
            raise ValueError(f"rounds_played missing for recording {letter}")
        wanted = selected_rounds(info["round_order"], played[letter])
        duration = _duration(run, info["recording_id"])
        video = _video(run, info["recording_id"])
        for number in wanted:
            match = [r for r in rows if r["recording"] == letter and int(r["round"]) == number]
            if len(match) != 1:
                raise ValueError(f"Approximate times for {letter} round {number} required")
            for kind, column in (("start", "start_approx"), ("end", "end_approx")):
                if not match[0][column].strip():
                    raise ValueError(f"{letter} round {number} {kind} time missing")
                centre = _clock(match[0][column])
                ident = f"{letter}{number:02d}{kind[0].upper()}"
                folder = out / ident
                folder.mkdir()
                seconds = [s for s in range(centre - window, centre + window + 1)
                           if s >= 0 and s + offset < duration]
                for s in seconds:
                    _cut(video, s + offset, folder / f"{s:05d}.jpg")
                items.append({"id": ident, "recording_id": info["recording_id"],
                              "recording": letter, "round": number, "kind": kind,
                              "seconds": seconds})
    with (kit / "boundary_labels_TEMPLATE.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "first_second", "note"])
        for item in items:
            writer.writerow([item["id"], "", ""])
    manifest = {"version": VERSION, "protocol": PROTOCOL, "rounds_played": played,
                "items": items}
    write_private(kit / "boundary_key_PRIVATE.json", manifest)
    return manifest


# ---------------------------------------------------------------- scoring


def _states(run: Path, recording_id: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    csv.field_size_limit(2**31 - 1)
    timeline = run / recording_id / "timeline"
    path = timeline / "timeline_1s_PRIVATE.csv"
    states = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            states.append({d: json.loads(row[col])["value"] for d, col in DOMAINS.items()})
    return states, read_json(timeline / "evaluation_PRIVATE.json")


def score_frames(
    key: Iterable[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, str]],
    predictions: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    """Correct / wrong / abstain per domain against a person's labels."""
    tallies: dict[str, dict[str, Any]] = {}
    for domain in DOMAINS:
        total = {"correct": 0, "wrong": 0, "abstain": 0, "unsure": 0,
                 "undefined_frames": 0, "undefined_false_claims": 0, "unlabelled": 0}
        per: dict[str, dict[str, int]] = {}
        for item in key:
            label = (labels.get(item["no"], {}).get(domain) or "").strip().upper()
            bucket = per.setdefault(item["recording_id"], {"correct": 0, "wrong": 0,
                                                           "abstain": 0})
            if not label:
                total["unlabelled"] += 1
                continue
            if label not in LABELS[domain]:
                raise ValueError(f"Unknown {domain} label {label!r} for frame {item['no']}")
            predicted = predictions[item["recording_id"]][item["second"]][domain]
            if label == "UNSURE":
                total["unsure"] += 1
            elif label == UNDEFINED[domain]:
                total["undefined_frames"] += 1
                total["undefined_false_claims"] += predicted != "UNKNOWN"
            else:
                outcome = ("abstain" if predicted == "UNKNOWN"
                           else "correct" if predicted == label else "wrong")
                total[outcome] += 1
                bucket[outcome] += 1
        n = total["correct"] + total["wrong"] + total["abstain"]
        answered = total["correct"] + total["wrong"]
        tallies[domain] = {
            **total,
            "scored_frames": n,
            "accuracy": round(total["correct"] / n, 4) if n else None,
            "accuracy_ci95": wilson(total["correct"], n),
            "error_rate": round(total["wrong"] / n, 4) if n else None,
            "error_rate_ci95": wilson(total["wrong"], n),
            "coverage": round(answered / n, 4) if n else None,
            "precision_when_answered": round(total["correct"] / answered, 4)
            if answered else None,
            "per_recording": per,
        }
    return tallies


def score_boundaries(
    items: Iterable[Mapping[str, Any]],
    labels: Mapping[str, str],
    candidates: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Time error of predicted round start/end brackets against a person's seconds.

    The person's ``first_second`` g is the first labelled frame (taken at g + 1/2 s)
    showing the new state, so the true transition lies in [g - 1/2, g + 1/2]. A
    predicted bracket [lower, upper] has error 0 when it overlaps that interval,
    otherwise the gap. The nearest bracket whose centre is within the association
    window is used; none is a missed boundary.
    """
    reach = PROTOCOL["boundary_association_seconds"]
    out: dict[str, Any] = {}
    for kind, event_kind in BOUNDARY_KINDS.items():
        errors: list[float] = []
        centre_errors: list[float] = []
        widths: list[float] = []
        missed = unsure = unlabelled = 0
        rows = []
        for item in items:
            if item["kind"] != kind:
                continue
            answer = (labels.get(item["id"]) or "").strip().upper()
            if not answer:
                unlabelled += 1
                continue
            if answer == "UNSURE":
                unsure += 1
                continue
            g = int(answer)
            low, high = g - 0.5, g + 0.5
            near = [c for c in candidates[item["recording_id"]]
                    if c["kind"] == event_kind
                    and abs((c["lower_timestamp"] + c["upper_timestamp"]) / 2 - g) <= reach]
            if not near:
                missed += 1
                rows.append({"id": item["id"], "first_second": g, "candidate": None})
                continue
            best = min(near, key=lambda c: abs(
                (c["lower_timestamp"] + c["upper_timestamp"]) / 2 - g))
            lower, upper = best["lower_timestamp"], best["upper_timestamp"]
            error = 0.0 if upper >= low and lower <= high else (
                low - upper if upper < low else lower - high)
            errors.append(error)
            centre_errors.append(abs((lower + upper) / 2 - g))
            widths.append(upper - lower)
            rows.append({"id": item["id"], "first_second": g,
                         "candidate": [lower, upper], "error_seconds": error})
        n = len(errors) + missed
        out[kind] = {
            "labelled": n, "unsure": unsure, "unlabelled": unlabelled,
            "detected": len(errors), "missed": missed,
            "detection_rate": round(len(errors) / n, 4) if n else None,
            "within_bracket": sum(e == 0 for e in errors),
            "within_1s": sum(e <= 1 for e in errors),
            "within_2s": sum(e <= 2 for e in errors),
            "error_median_seconds": median(errors) if errors else None,
            "error_max_seconds": max(errors) if errors else None,
            "centre_error_median_seconds": median(centre_errors) if centre_errors else None,
            "bracket_width_median_seconds": median(widths) if widths else None,
            "items": rows,
        }
    return out


def _read_labels(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig") as f:
        return {row[key_column].strip(): row for row in csv.DictReader(f)}


def score(run: Path, kit: Path, frame_labels: Path, boundary_labels: Path | None,
          output: Path) -> dict[str, Any]:
    results = _run_recordings(run)
    key = read_json(kit / "frame_key_PRIVATE.json")
    if key["protocol"] != PROTOCOL:
        raise ValueError("Kit was drawn under a different protocol")
    predictions: dict[str, list[dict[str, str]]] = {}
    candidates: dict[str, list[dict[str, Any]]] = {}
    timeline_coverage: dict[str, Any] = {}
    for row in results:
        rid = row["recording_id"]
        states, review = _states(run, rid)
        predictions[rid] = states
        candidates[rid] = review["candidate_review_queue"]
        timeline_coverage[rid] = {
            "seconds": len(states),
            **{d: round(sum(s[d] != "UNKNOWN" for s in states) / len(states), 4)
               for d in DOMAINS},
        }
    for item in key["frames"]:
        if file_sha(kit / "frames" / item["file"]) != item["sha256"]:
            raise ValueError(f"Labelled frame {item['file']} changed")
    frames = score_frames(key["frames"], _read_labels(frame_labels, "no"), predictions)
    boundaries = None
    if boundary_labels is not None:
        bkey = read_json(kit / "boundary_key_PRIVATE.json")
        if bkey["protocol"] != PROTOCOL:
            raise ValueError("Boundary kit was drawn under a different protocol")
        labels = {k: v["first_second"] for k, v in
                  _read_labels(boundary_labels, "id").items()}
        boundaries = score_boundaries(bkey["items"], labels, candidates)
    total_seconds = sum(c["seconds"] for c in timeline_coverage.values())
    report = {
        "version": VERSION,
        "protocol": PROTOCOL,
        "run_receipt_sha256": file_sha(run / "independent_evaluation_receipt_PRIVATE.json"),
        "frame_labels_sha256": file_sha(frame_labels),
        "boundary_labels_sha256": file_sha(boundary_labels) if boundary_labels else None,
        "frames": frames,
        "boundaries": boundaries,
        "timeline_coverage": {
            "per_recording": timeline_coverage,
            "all": {d: round(sum(c[d] * c["seconds"] for c in timeline_coverage.values())
                             / total_seconds, 4) for d in DOMAINS},
            "seconds": total_seconds,
        },
        "reference_labels": "human labels on frames drawn by the frozen protocol",
        "formal_qualification": "NOT_GRANTED",
        "formal_outputs": 0,
    }
    write_private(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("frame-kit", "boundary-kit"):
        p = sub.add_parser(name)
        p.add_argument("--run", type=Path, required=True)
        p.add_argument("--kit", type=Path, required=True)
    p = sub.add_parser("boundary-frames")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--kit", type=Path, required=True)
    p.add_argument("--approximate", type=Path, required=True)
    p = sub.add_parser("score")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--kit", type=Path, required=True)
    p.add_argument("--frame-labels", type=Path, required=True)
    p.add_argument("--boundary-labels", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "frame-kit":
        manifest = frame_kit(args.run, args.kit)
        print(json.dumps({"frames": len(manifest["frames"])}))
    elif args.command == "boundary-kit":
        manifest = boundary_kit(args.run, args.kit)
        print(json.dumps({"recordings": len(manifest["recordings"])}))
    elif args.command == "boundary-frames":
        manifest = boundary_frames(args.run, args.kit, args.approximate)
        print(json.dumps({"boundaries": len(manifest["items"])}))
    else:
        report = score(args.run, args.kit, args.frame_labels, args.boundary_labels,
                       args.output)
        print(json.dumps({d: {k: report["frames"][d][k] for k in
                              ("accuracy", "coverage", "error_rate")}
                          for d in DOMAINS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
