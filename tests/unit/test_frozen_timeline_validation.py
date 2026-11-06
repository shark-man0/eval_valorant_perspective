"""Admission, frozen protocol and output checks; no private data or labels."""

import csv
import json
from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace

import pytest

from valorant_ai_coach.rules.development_timeline import review_timeline
from valorant_ai_coach.temporal import validation as v
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation
from valorant_ai_coach.temporal.replay import read_json, write_private


def application():
    engine = DevelopmentGameTimeline()
    for tick, signals in [(0, ["buy", "owner_hud"]), (20, ["active", "owner_hud"])]:
        sample = freeze_native_sample(
            {
                "source_id": "synthetic",
                "source_sha256": "a" * 64,
                "acquisition_id": "e",
                "native_epoch": "e",
                "native_pts_tick": tick,
                "native_time_base": "1/10",
                "frame_size_px": [32, 32],
                "acquired_frame_sha256": digest([tick]),
                "native_pixel_sha256": digest([tick, 1]),
            }
        )
        engine.add(
            observation(
                sample=sample,
                producer="b" * 64,
                signals=signals,
                raw={"view_hp": {"display": "100"}},
                context={"score": [0, 0]},
            )
        )
    return build_application_timeline(
        engine.rebuild(),
        duration=Fraction(5, 2),
        origin=Fraction(0),
        source={
            "video_id": "synthetic",
            "source_sha256": "a" * 64,
            "physical_match_id": "physical",
        },
    )


@pytest.fixture
def admission(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "ROOT", tmp_path / "empty_repository")
    monkeypatch.setattr(v, "verify_protocol", lambda _: {})
    protocol = tmp_path / "protocol.json"
    write_private(protocol, {"synthetic": True})
    registry = tmp_path / "registry"
    request = {
        "purpose": "frozen_timeline_comparison",
        "content_kind": "SYNTHETIC_TEST",
        "declarations": {
            "permission": True,
            "unused_for_development": True,
            "distinct_physical_matches": True,
            "unedited_full_matches": True,
        },
        "records": [
            {
                "source_id": "new",
                "physical_match_id": "physical_new",
                "path": str(tmp_path / "new.mp4"),
            }
        ],
    }

    def run(request, batch="one"):
        path = tmp_path / (batch + ".json")
        write_private(path, request)
        return v.enroll_sources(
            declaration=path,
            protocol=protocol,
            registry=registry,
            batch_id=batch,
            prior_registries=[],
        )

    return request, registry, run


@pytest.mark.parametrize("fault", ["permission", "numeric_bool", "initial_state", "same_match"])
def test_declarations_and_identity_rejected_before_media(admission, monkeypatch, fault):
    request, _, run = admission
    monkeypatch.setattr(v, "_inspect", lambda *a: pytest.fail("must not inspect media"))
    if fault == "permission":
        request["declarations"]["permission"] = False
    elif fault == "numeric_bool":
        request["declarations"]["permission"] = 1
    elif fault == "initial_state":
        request["records"][0]["life_state"] = "ALIVE"
    else:
        request["records"].append({**request["records"][0], "source_id": "second"})
    with pytest.raises(ValueError):
        run(request)


def test_protected_known_path_is_not_even_hashed(admission, tmp_path, monkeypatch):
    request, registry, run = admission
    source = tmp_path / "new.mp4"
    source.write_bytes(b"do not read this reserved source")
    write_private(
        registry / "old/allocation.json",
        {
            "records": [
                {
                    "video_id": "reserved",
                    "physical_match_id": "old",
                    "original_path": str(source),
                    "source_sha256": "c" * 64,
                    "exposure": "UNKNOWN_EXPOSURE",
                }
            ]
        },
    )
    original_sha = v.file_sha

    def no_media_sha(path):
        assert path != source
        return original_sha(path)

    monkeypatch.setattr(v, "file_sha", no_media_sha)
    result = run(request)
    assert result["records"][0]["failure_rule"] == "PRIOR_PATH_OR_INVALID_SOURCE"
    assert not (registry / "one/policy_PRIVATE.json").exists()


def test_duplicate_bytes_rejected_before_probe_and_reservations_survive(
    admission, tmp_path, monkeypatch
):
    request, registry, run = admission
    (tmp_path / "new.mp4").write_bytes(b"duplicate")
    second = tmp_path / "second.mp4"
    second.write_bytes(b"duplicate")
    request["records"].append(
        {"source_id": "second", "physical_match_id": "other", "path": str(second)}
    )
    monkeypatch.setattr(v, "_inspect", lambda *a: pytest.fail("must not probe duplicate"))
    result = run(request)
    assert {r["failure_rule"] for r in result["records"]} == {"PRIOR_OR_DUPLICATE_SOURCE_BYTES"}
    assert len(read_json(registry / "one/allocation.json")["records"]) == 2
    with pytest.raises(ValueError, match="reserved"):
        run(request, "retry")


@pytest.mark.parametrize("drift", ["config", "binding", "commit", "runtime"])
def test_frozen_protocol_detects_drift(tmp_path, monkeypatch, drift):
    config, runtime, output = (tmp_path / name for name in ("config.json", "extra.py", "plan.json"))
    config.write_text("{}", encoding="utf-8")
    runtime.write_text("# fixed runtime\n", encoding="utf-8")
    observer = SimpleNamespace(fingerprint="a" * 64, bindings={"weights_sha": "b" * 64})
    monkeypatch.setattr(v, "_observer", lambda *a: observer)
    monkeypatch.setattr(v, "_git", lambda repo, *args: "c" * 40 if args[0] == "rev-parse" else "")
    # Binaries may be absent on a developer machine; real decoding is tested separately.
    monkeypatch.setattr(v.shutil, "which", lambda _: str(runtime))
    v.freeze_protocol(
        config=config,
        observer="synthetic:Reader",
        output=output,
        runtime_files=[runtime],
        repository=tmp_path,
    )
    assert v.verify_protocol(output)["human_labels_or_initial_states"] is False
    if drift == "config":
        config.write_text('{"changed":true}', encoding="utf-8")
    elif drift == "binding":
        observer.bindings["weights_sha"] = "d" * 64
    elif drift == "runtime":
        runtime.write_text("# changed\n", encoding="utf-8")
    else:
        monkeypatch.setattr(v, "_git", lambda repo, *args: "d" * 40)
    with pytest.raises(ValueError, match="changed"):
        v.verify_protocol(output)


def test_complete_grid_does_not_imply_accuracy_or_observed_seconds():
    result = v.inspect_bundle(application())
    assert result["processing"] == "COMPLETE_WITH_INFORMATION"
    assert result["one_second_rows"] == 3
    assert result["observed_seconds"] == 2
    assert result["unobserved_seconds"] == 1
    assert result["domain_seconds"]["round_state"]["UNKNOWN"] == 1
    assert result["accuracy"] is None and result["formal_outputs"] == 0


def test_all_unknown_is_structurally_complete_but_uninformative():
    bundle = application()
    bundle["events"] = {}
    for row in bundle["seconds"]:
        row["event_candidates"] = []
        for domain in ("round_state", "life_state", "camera_state"):
            row[domain]["value"] = "UNKNOWN"
        for value in row["hud_observations"].values():
            value["candidates"] = []
    result = v.inspect_bundle(bundle)
    assert result["structural_pass"]
    assert result["processing"] == "COMPLETE_UNINFORMATIVE"


def test_optional_hud_fields_need_not_exist_in_every_second():
    bundle = application()
    bundle["seconds"][0]["hud_observations"]["ally_score"] = {
        "status": "CANDIDATES",
        "candidates": [{"value": "0"}],
    }
    result = v.inspect_bundle(bundle)
    assert result["hud_candidate_seconds"]["ally_score"] == 1


@pytest.mark.parametrize("fault", ["missing", "duplicate", "end", "native", "sample", "event"])
def test_corrupt_timeline_rejected(fault):
    bundle = deepcopy(application())
    if fault == "missing":
        bundle["seconds"].pop(1)
    elif fault == "duplicate":
        bundle["seconds"][1]["timestamp"] = 0
    elif fault == "end":
        bundle["seconds"][-1]["end_timestamp"] = 3
    elif fault == "native":
        bundle["seconds"][0]["native_start_seconds"] = "1/5"
    elif fault == "sample":
        bundle["seconds"][0]["sample_refs"] = []
    else:
        next(iter(bundle["events"].values()))["qualified"] = True
    with pytest.raises(ValueError):
        v.inspect_bundle(bundle)


def test_decoder_failure_position_is_not_a_recognized_event_time(tmp_path):
    path = tmp_path / "acquisition/coarse_decode.log"
    path.parent.mkdir()
    path.write_text("[showinfo] n: 0 pts: 900 pts_time:0.9 pos: 4\n", encoding="utf-8")
    result = v._decoded_progress(tmp_path)
    assert result[0]["last_logged_decoded_frame"] == {"pts_tick": 900, "pts_time_text": "0.9"}
    assert "not last recognized frame" in result[0]["scope"]


@pytest.mark.parametrize("corrupt_csv", [False, True])
def test_json_csv_full_content_and_large_evidence_cells(tmp_path, corrupt_csv):
    bundle = application()
    bundle["seconds"][0]["hud_observations"]["hp"]["candidates"][0]["value"] = "x" * 140000
    write_private(tmp_path / "timeline_PRIVATE.json", bundle)
    write_private(tmp_path / "evaluation_PRIVATE.json", review_timeline(bundle))
    rows = deepcopy(bundle["seconds"])
    if corrupt_csv:
        rows[0]["hud_observations"]["hp"]["candidates"] = []
    with (tmp_path / "timeline_1s_PRIVATE.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(value) if isinstance(value, (dict, list)) else value
                    for k, value in row.items()
                }
            )
    write_private(
        tmp_path / "completion_PRIVATE.json",
        {"output_sha256s": {path.name: v.file_sha(path) for path in tmp_path.iterdir()}},
    )
    if corrupt_csv:
        with pytest.raises(ValueError, match="CSV candidate/evidence"):
            v.check_output(tmp_path)
    else:
        previous = csv.field_size_limit()
        assert v.check_output(tmp_path)["JSON_CSV_content_equal"]
        assert csv.field_size_limit() == previous
