"""Human whole-window coverage receipts and discovery cues, never event GT."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from scripts.diagnostics.register_private_sources import write_private
from scripts.e2e.run_dataset_case import read_json, sha256_file, valid_id
from scripts.temporal_gt.contract import canonical_hash, require
from scripts.temporal_gt.review_session import (
    append_exposure,
    exclusive_operation,
    load_plan,
    private_directory,
    registry_source,
)

VERSION = "human-source-window-review-v1"
STATUSES = {"COMPLETE", "INCOMPLETE", "NEEDS_RECHECK"}
KINDS = {
    "round_start",
    "round_end",
    "next_round",
    "score_change",
    "clock_change",
    "self_death",
    "self_killer",
    "nonself_death",
    "spectator",
    "combat_report_first",
    "report_persistence",
    "report_redisplay",
    "respawn",
    "natural_negative",
    "unknown",
    "source_discontinuity",
}


def defaults(session: Path, index: int) -> dict[str, Any]:
    plan = load_plan(session)
    require(type(index) is int and 1 <= index <= len(plan["planned_windows"]), "window_index")
    return {
        "version": VERSION,
        "plan_sha256": sha256_file(session / "plan.json"),
        "source_sha256": plan["source_sha256"],
        "window_index": index,
        "reviewer_id": "user",
        "human_source_review_confirmed": False,
        "predictions_consulted": False,
        "status": "INCOMPLETE",
        "full_interval_reviewed": False,
        "round_searched": False,
        "death_searched": False,
        "notes": "",
        "cues": [],
    }


def validate_response(session: Path, response: dict[str, Any]) -> None:
    plan = load_plan(session)
    index = response["window_index"]
    expected = defaults(session, index)
    require(set(response) == set(expected), "window_response_keys")
    for key in ("version", "plan_sha256", "source_sha256", "reviewer_id"):
        require(response[key] == expected[key], "window_source_plan_binding")
    for key in (
        "human_source_review_confirmed",
        "predictions_consulted",
        "full_interval_reviewed",
        "round_searched",
        "death_searched",
    ):
        require(type(response[key]) is bool, "window_explicit_boolean")
    require(response["human_source_review_confirmed"] is True, "window_human_confirmation")
    require(response["predictions_consulted"] is False, "window_prediction_blind")
    require(response["status"] in STATUSES, "window_status")
    require(isinstance(response["notes"], str), "window_notes")
    if response["status"] == "COMPLETE":
        require(
            all(
                response[k] for k in ("full_interval_reviewed", "round_searched", "death_searched")
            ),
            "whole_window_human_review_required",
        )
    if response["status"] == "NEEDS_RECHECK":
        require(bool(response["notes"].strip()), "recheck_reason_required")
    window = plan["planned_windows"][index - 1]
    begin = window["start_tick"] * Fraction(plan["time_base"])
    end = window["end_tick"] * Fraction(plan["time_base"])
    require(isinstance(response["cues"], list), "window_cues")
    for cue in response["cues"]:
        require(
            isinstance(cue, dict) and set(cue) == {"kind", "approx_source_sec", "note"}, "cue_keys"
        )
        require(cue["kind"] in KINDS and isinstance(cue["approx_source_sec"], str), "cue_kind")
        require(begin <= Fraction(cue["approx_source_sec"]) <= end, "cue_inside_planned_window")
        require(isinstance(cue["note"], str), "cue_note")
        if cue["kind"] in {"unknown", "source_discontinuity"}:
            require(bool(cue["note"].strip()), "cue_unknown_reason_required")


def journal(session: Path) -> dict[int, dict[str, Any]]:
    plan = load_plan(session)
    path = Path(plan["batch"]) / "exposure_journal.jsonl"
    previous = None
    entries: dict[int, dict[str, Any]] = {}
    if path.exists():
        for order, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            entry = json.loads(text)
            require(
                entry["previous_sha256"] == previous and entry["event"]["order"] == order,
                "exposure_chain",
            )
            previous = canonical_hash(entry)
            entries[order] = entry
    return entries


def progress(session: Path) -> dict[str, Any]:
    plan = load_plan(session)
    states = ["UNREVIEWED"] * len(plan["planned_windows"])
    # Legacy bounded reviews establish partial coverage only, never a full60-second review.
    for path in session.glob("*/human_receipt.json"):
        receipt = read_json(path)
        response_path = path.parent / "human_response.json"
        require(sha256_file(response_path) == receipt["response_sha256"], "legacy_response_hash")
        acq = read_json(path.parent / "acquisition.json")
        require(canonical_hash(acq) == receipt["acquisition_sha256"], "legacy_acquisition_hash")
        require(acq["source_sha256"] == plan["source_sha256"], "legacy_source")
        response = read_json(response_path)
        if not (response["round"]["reviewed"] or response["death"]["reviewed"]):
            continue
        first, last = acq["frames"][0]["tick"], acq["frames"][-1]["tick"]
        for i, window in enumerate(plan["planned_windows"]):
            if first < window["end_tick"] and window["start_tick"] < last:
                states[i] = "INCOMPLETE"
    entries = journal(session)
    accepted = []
    for path in (session / "window_reviews").glob("*/receipt.json"):
        receipt = read_json(path)
        response_path = path.parent / "response.json"
        raw = path.parent / "response.raw.json"
        require(sha256_file(raw) == receipt["raw_sha256"], "window_raw_hash")
        require(sha256_file(response_path) == receipt["response_sha256"], "window_response_hash")
        entry = entries[receipt["exposure_order"]]
        require(
            entry["event"]["source_id"] == plan["video_id"]
            and entry["event"]["kind"] == "source_only_view"
            and Path(entry["evidence_path"]).resolve() == response_path.resolve()
            and entry["evidence_sha256"] == receipt["response_sha256"],
            "window_exposure_binding",
        )
        response = read_json(response_path)
        validate_response(session, response)
        accepted.append((receipt["exposure_order"], response))
    cues: list[dict[str, Any]] = []
    for _, response in sorted(accepted):
        states[response["window_index"] - 1] = response["status"]
    # A progress correction must not silently discard earlier discovery notes.
    for order, response in sorted(accepted):
        for index, cue in enumerate(response["cues"], 1):
            cues.append(
                dict(
                    cue,
                    window_index=response["window_index"],
                    cue_id=f"journal_{order}_cue_{index}",
                    status="PENDING_NATIVE_HUMAN_REVIEW",
                )
            )
    counts = Counter(states)
    return {
        "total_windows": len(states),
        "complete_windows": counts["COMPLETE"],
        "unreviewed_windows": counts["UNREVIEWED"],
        "incomplete_windows": counts["INCOMPLETE"],
        "needs_recheck_windows": counts["NEEDS_RECHECK"],
        "full_match_review_complete": all(s == "COMPLETE" for s in states),
        "window_statuses": states,
        "pending_evidence_cues": cues,
        "cues_are_gt": False,
        "unreviewed_is_negative": False,
        "source_continuity": "UNVERIFIED",
        "recognition_executed": False,
    }


def prepare(session: Path, output: Path, index: int) -> None:
    plan = load_plan(session)
    row = registry_source(plan)
    summary = progress(session)
    next_index = next(
        (i + 1 for i, s in enumerate(summary["window_statuses"]) if s != "COMPLETE"),
        len(plan["planned_windows"]),
    )
    require(type(index) is int and 1 <= index <= next_index, "review_in_timeline_order")
    require(sha256_file(Path(row["managed_path"])) == plan["source_sha256"], "source_integrity")
    response = defaults(session, index)
    private_directory(output)
    window = plan["planned_windows"][index - 1]
    payload = {
        "response": response,
        "window_count": len(plan["planned_windows"]),
        "begin": float(window["start_tick"] * Fraction(plan["time_base"])),
        "end": float(window["end_tick"] * Fraction(plan["time_base"])),
        "video_uri": Path(row["managed_path"]).as_uri(),
        "progress": summary["window_statuses"],
    }
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("window_review.html").read_text(encoding="utf-8")
    target = output / "review.html"
    with target.open("x", encoding="utf-8") as stream:
        stream.write(template.replace("__PAYLOAD__", text))
    os.chmod(target, 0o600)
    append_exposure(
        session,
        "source_only_view",
        target,
        "Prediction-blind DEVELOPMENT planned-window source player prepared. "
        "No completed review or GT inferred from page creation/playback.",
    )


def record(session: Path, response_path: Path, receipt_id: str) -> dict[str, Any]:
    plan = load_plan(session)
    with exclusive_operation(Path(plan["batch"]) / ".window-review-lock"):
        raw = response_path.read_bytes()
        response = read_json(response_path)
        require(json.loads(raw.decode("utf-8")) == response, "response_changed_during_read")
        expected = defaults(session, response["window_index"])
        require(
            all(
                response.get(k) == expected[k]
                for k in ("version", "plan_sha256", "source_sha256", "reviewer_id")
            ),
            "window_source_plan_binding",
        )
        if response.get("predictions_consulted") is True:
            rejected = session / "window_reviews" / valid_id(receipt_id)
            private_directory(rejected)
            proof = rejected / "rejected_prediction_response.json"
            with proof.open("xb") as stream:
                stream.write(raw)
            os.chmod(proof, 0o600)
            append_exposure(
                session,
                "prediction_review",
                proof,
                "Human reports prediction viewing; window coverage import rejected.",
            )
        validate_response(session, response)
        entries = journal(session)
        require(
            not any(
                e["event"]["source_id"] == plan["video_id"]
                and e["event"]["kind"] in {"prediction", "prediction_review"}
                for e in entries.values()
            ),
            "prediction_exposure_requires_separate_workflow",
        )
        prior = progress(session)
        index = response["window_index"]
        next_index = next(
            (i + 1 for i, s in enumerate(prior["window_statuses"]) if s != "COMPLETE"),
            len(prior["window_statuses"]),
        )
        require(index <= next_index, "review_in_timeline_order")
        if response["status"] == "COMPLETE":
            require(
                all(s == "COMPLETE" for s in prior["window_statuses"][: index - 1]),
                "review_in_timeline_order",
            )
        require(
            sha256_file(Path(registry_source(plan)["managed_path"])) == plan["source_sha256"],
            "source_integrity",
        )
        folder = session / "window_reviews" / valid_id(receipt_id)
        private_directory(folder)
        with (folder / "response.raw.json").open("xb") as stream:
            stream.write(raw)
        os.chmod(folder / "response.raw.json", 0o600)
        write_private(folder / "response.json", response)
        order = append_exposure(
            session,
            "source_only_view",
            folder / "response.json",
            "Human source-only planned-window review; discovery cues are "
            "unconfirmed and do not change event GT or continuity qualification.",
        )
        write_private(
            folder / "receipt.json",
            {
                "response_sha256": sha256_file(folder / "response.json"),
                "raw_sha256": sha256_file(folder / "response.raw.json"),
                "exposure_order": order,
            },
        )
        return progress(session)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "record", "summary"])
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--window-index", type=int)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--receipt-id")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            require(args.output is not None and args.window_index is not None, "prepare_arguments")
            prepare(args.session, args.output, args.window_index)
        elif args.command == "record":
            require(args.response is not None and args.receipt_id is not None, "record_arguments")
            record(args.session, args.response, args.receipt_id)
        report = progress(args.session)
        # Cues contain private timing/notes; stdout is anonymous counts only.
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in {"pending_evidence_cues", "window_statuses"}
                }
            )
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ZeroDivisionError):
        parser.exit(2, "WINDOW_REVIEW_CONTRACT_REJECTED\n")


if __name__ == "__main__":
    main()
