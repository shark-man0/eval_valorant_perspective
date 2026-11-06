from __future__ import annotations

import csv
import json
import threading
from copy import deepcopy
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from test_development_timeline_application import build

from valorant_ai_coach.temporal import comparison, comparison_viewer


def comparison_fixture(tmp_path):
    from fractions import Fraction

    from test_shared_game_timeline import obs, replay
    from test_shared_timeline_replay import policy_fixture, write

    from valorant_ai_coach.temporal.application import build_application_timeline

    policy = write(tmp_path / "policy.json", policy_fixture(tmp_path))
    bundle = build_application_timeline(
        replay([obs(0, ["buy", "owner_hud"]), obs(10, ["active", "owner_hud"])]),
        source={"video_id": "a", "source_sha256": "a" * 64, "physical_match_id": "physical1"},
        origin=Fraction(0),
        duration=Fraction(4),
    )
    path = write(tmp_path / "timeline_PRIVATE.json", bundle)
    write(
        tmp_path / "completion_PRIVATE.json",
        {"output_sha256s": {path.name: comparison.file_sha(path)}},
    )
    entry = {
        "id": "one",
        "primary": True,
        "bundle": str(path),
        "bundle_sha256": comparison.file_sha(path),
        "policy": str(policy),
        "policy_sha256": comparison.file_sha(policy),
        "conditions": {"synthetic": True},
    }
    manifest = write(
        tmp_path / "comparison_manifest.json",
        {"version": comparison.MANIFEST_VERSION, "results": [entry]},
    )
    return manifest, entry


def test_catalog_export_uses_real_admission_and_evaluation_without_opening_video(tmp_path):
    manifest, _ = comparison_fixture(tmp_path)
    output = tmp_path / "export"
    result = comparison.export_catalog(manifest, output)
    assert result["physical_matches"] == 1
    assert result["primary_rows"] == 4
    with (output / "comparison_PRIVATE.csv").open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["physical_match_id"] == "physical1"
    assert row["rows"] == "4"
    evaluation = json.loads((output / "evaluation_PRIVATE.json").read_text(encoding="utf-8"))
    assert evaluation["one"]["seconds_consumed"] == 4
    assert evaluation["one"]["deterministic_engine_decision"] is None
    assert result["formal_outputs"] == 0
    assert result["results"][0]["unobserved_seconds"] == 2


def test_catalog_does_not_count_alternate_results_as_new_physical_matches(tmp_path):
    from test_shared_timeline_replay import write

    manifest, entry = comparison_fixture(tmp_path)
    alternate = {
        **entry,
        "id": "alternate",
        "primary": False,
        "compare_to": "one",
        "conditions": {"different_sampling": True},
    }
    write(manifest, {"version": comparison.MANIFEST_VERSION, "results": [entry, alternate]})
    catalog = comparison.build_catalog(manifest)
    assert catalog["physical_matches"] == 1
    assert catalog["result_versions"] == 2
    assert catalog["primary_rows"] == 4
    assert (
        catalog["results"][0]["condition_identity"] != catalog["results"][1]["condition_identity"]
    )
    assert catalog["results"][1]["before_after"]["seconds"]["round_state"]["changed_seconds"] == 0
    alternate["primary"] = True
    write(manifest, {"version": comparison.MANIFEST_VERSION, "results": [entry, alternate]})
    with pytest.raises(ValueError, match="One primary"):
        comparison.build_catalog(manifest)


def test_exact_zone_sidecar_retains_epochs_and_never_assigns_recorder():
    from fractions import Fraction

    from test_shared_game_timeline import obs, replay
    from test_shared_zone_context import zone

    from valorant_ai_coach.temporal.application import build_application_timeline
    from valorant_ai_coach.temporal.zone_projection import attach_viewed_zones

    native = obs(0, ["owner_hud", "buy"])
    bundle = build_application_timeline(
        replay([native]),
        source={"video_id": "a", "source_sha256": "a" * 64, "physical_match_id": "physical"},
        duration=Fraction(1),
        origin=Fraction(0),
    )
    before = deepcopy(bundle)
    z = zone(epoch="different_epoch")
    attach_viewed_zones(bundle, [z])
    row = bundle["seconds"][0]
    assert row["map_observations"]["zone_candidates"][0]["label_text"] == "Bテスト"
    assert (
        row["map_observations"]["zone_candidates"][0]["zone_subject"] == "unassigned_viewed_actor"
    )
    assert row["map_observations"]["current_self_position_candidates"] == []
    assert bundle["native_frames"] == before["native_frames"]
    assert bundle["observations"][z["observation_id"]] == z
    assert bundle["HUD_zone_observation_links"][0]["independent_confirmation"] is False
    assert bundle["unmatched_HUD_zone_observation_ids"] == []
    wrong_pixel = zone(1, epoch="other")
    attach_viewed_zones(bundle, [wrong_pixel])
    assert bundle["unmatched_HUD_zone_observation_ids"] == [wrong_pixel["observation_id"]]
    assert row["map_observations"]["zone_candidates"][0]["label_text"] == "Bテスト"


def test_map_weak_highlight_is_visible_without_becoming_strict_owner():
    from valorant_ai_coach.temporal.map_correspondence import correspondence_review

    marker = {"center_frame_px": [12, 14]}
    pool = [marker]
    result = correspondence_review(pool, [], [{"candidate": marker}], [])
    assert result["status"] == "PROVISIONAL_HIGHLIGHT_WITH_WEAK_VIEW"
    assert result["provisional_highlight_indices"] == [0]
    assert result["strict_recorder_marker_count"] == 0
    assert result["ownership"] == "UNKNOWN"
    assert pool == [marker]


def test_unknown_categories_and_review_flags_never_assert_errors():
    bundle = build()
    first, missing = bundle["seconds"][:2]
    assert comparison.unknown_reason(first, "round_state") == "conflicting_candidates"
    assert comparison.unknown_reason(missing, "round_state") == "not_observed"
    first["life_state"]["hypotheses"] = ["UNKNOWN", "ALIVE"]
    first["life_state"]["value"] = "UNKNOWN"
    assert comparison.unknown_reason(first, "life_state") == "observed_unresolved"
    before = deepcopy(bundle)
    issues = comparison.review_intervals(bundle, minimum_unknown=1)
    assert any(i["kind"] == "unknown_not_observed" for i in issues)
    assert any(i["kind"] == "map_candidates_unassigned" for i in issues)
    assert any(i["kind"] == "hud_available_state_unresolved" for i in issues)
    assert all(i["is_error"] is None for i in issues)
    assert all(set(i["evidence_refs"]) <= bundle["observations"].keys() for i in issues)
    assert before == bundle


def test_summary_denominators_include_missing_and_partial_final_second():
    summary = comparison.summarize_bundle(build())
    assert summary["rows"] == 4
    assert summary["duration_seconds"] == "7/2"
    assert summary["observed_seconds"] + summary["unobserved_seconds"] == 4
    assert summary["domains"]["round_state"]["unknown_fraction"] > 0
    assert summary["hud_candidate_seconds"]["armor"] == 0
    assert summary["map_candidate_seconds"] > 0
    assert summary["map_self_candidate_seconds"] == 0
    assert summary["formal_outputs"] == 0


def test_comparison_requires_same_clock_and_separates_estimate_change_from_truth():
    before = build()
    after = deepcopy(before)
    after["seconds"][0]["round_state"]["value"] = "ACTIVE"
    frame = next(iter(after["native_frames"].values()))
    frame["round"]["value"] = "ACTIVE"
    result = comparison.compare_versions(before, after)
    assert result["seconds"]["round_state"]["changed_seconds"] == 1
    assert result["seconds"]["round_state"]["previous_correct_lost"] is None
    assert result["exact_pixel_native_state_changes"]["round"] == 1
    frame["sample"]["native_pixel_sha256"] = "changed"
    assert (
        comparison.compare_versions(before, after)["exact_pixel_native_state_changes"]["round"] == 0
    )
    after["recording"]["native_origin_seconds"] = "0"
    with pytest.raises(ValueError, match="clock"):
        comparison.compare_versions(before, after)


def test_reject_incomplete_grid_and_formal_outputs():
    for mutation in (lambda b: b.update(formal_outputs=1), lambda b: b["seconds"].pop()):
        bundle = build()
        mutation(bundle)
        with pytest.raises(ValueError):
            comparison.summarize_bundle(bundle)


def test_manifest_digest_and_result_identifier_validation(tmp_path):
    data = tmp_path / "bundle.json"
    data.write_text("{}", encoding="utf-8")
    entry = {
        "id": "one",
        "bundle": "bundle.json",
        "bundle_sha256": comparison.file_sha(data),
        "policy": "bundle.json",
        "policy_sha256": comparison.file_sha(data),
        "primary": True,
        "conditions": {},
    }
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"version": comparison.MANIFEST_VERSION, "results": [entry]}), encoding="utf-8"
    )
    assert comparison.load_manifest(path)[0]["bundle"] == str(data)
    data.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        comparison.load_manifest(path)
    entry["id"] = "../outside"
    path.write_text(
        json.dumps({"version": comparison.MANIFEST_VERSION, "results": [entry]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="identifiers"):
        comparison.load_manifest(path)


def test_local_server_token_download_query_bounds_and_lazy_drilldown(tmp_path, monkeypatch):
    bundle = build()
    entry = {"id": "one", "bundle": "/private/bundle.json", "policy": "/private/policy.json"}
    summary = comparison.summarize_bundle(bundle)
    summary.update(id="one", condition_identity="synthetic")
    catalog = {"results": [summary]}
    monkeypatch.setattr(comparison_viewer, "load_manifest", lambda p: [entry])
    monkeypatch.setattr(comparison_viewer, "build_catalog", lambda p: catalog)
    monkeypatch.setattr(comparison, "load_result", lambda e: bundle)
    calls = []

    class Child:
        viewer_url = "http://127.0.0.1:1/child/"

        def serve_forever(self):
            pass

        def shutdown(self):
            calls.append("shutdown")

        def server_close(self):
            calls.append("close")

    monkeypatch.setattr(comparison_viewer, "make_server", lambda *a: Child())
    server = comparison_viewer.make_comparison_server(tmp_path / "manifest.json")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(server.viewer_url + "api/catalog") as response:
            assert json.load(response)["results"][0]["id"] == "one"
        with urlopen(server.viewer_url + "download.csv") as response:
            assert b"physical_match" in response.read()
        for query in ("id=unknown&second=0", "id=one&second=nan", "id=one&second=4"):
            with pytest.raises(HTTPError) as exc:
                urlopen(server.viewer_url + "open?" + query)
            assert exc.value.code == 400
        with pytest.raises(HTTPError) as exc:
            urlopen(
                server.viewer_url.replace(server.viewer_url.split("/")[-2], "wrong") + "api/catalog"
            )
        assert exc.value.code == 404
        assert server.children == {}

        connection = HTTPConnection("127.0.0.1", server.server_port)
        try:
            token = server.viewer_url.split("/")[-2]
            connection.request("GET", f"/{token}/open?id=one&second=1.5")
            redirect = connection.getresponse()
            assert redirect.status == 302
            assert redirect.getheader("Location").endswith("?second=1.5")
        finally:
            connection.close()
        assert set(server.children) == {"one"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert calls == ["shutdown", "close"]


def test_original_viewer_accepts_bounded_initial_seek():
    from valorant_ai_coach.temporal.viewer import HTML

    assert "new URLSearchParams(location.search).get('second')" in HTML
    assert "Number.isFinite(requested)" in HTML
    assert "loadedmetadata" in HTML
