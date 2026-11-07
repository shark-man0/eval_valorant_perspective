from copy import deepcopy

import pytest
from test_development_cross_match import comparison_fixture

from valorant_ai_coach.temporal.comparison import build_catalog, load_result
from valorant_ai_coach.temporal.issue_analysis import (
    analyze_catalog,
    classify_intervals,
    prioritize,
    select_representatives,
)
from valorant_ai_coach.temporal.issue_review import (
    HISTORY_VERSION,
    context_window,
    issue_page,
    load_review_sidecars,
    presentation_catalog,
)
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def test_classification_preserves_absence_and_native_aggregation_ambiguity(tmp_path):
    _, entry = comparison_fixture(tmp_path)
    bundle = load_result(entry)
    row = bundle["seconds"][0]
    row["round_state"]["native_estimates"].append(
        deepcopy(row["round_state"]["native_estimates"][0])
    )
    row["round_state"]["native_estimates"][-1]["estimate"]["value"] = "ACTIVE"
    rows = classify_intervals(
        bundle,
        [
            {
                "start": 0,
                "end": 4,
                "kind": "unknown",
                "domain": "round_state",
                "sample_refs": [],
                "evidence_refs": [],
            }
        ],
        result_id="one",
        bundle_sha256=entry["bundle_sha256"],
    )
    codes = {c["code"] for c in rows[0]["causes"]}
    assert {"A1", "A3", "A8"} <= codes
    assert "A6" not in codes  # No Map analysis is not a negative marker observation.
    assert rows[0]["is_error"] is None
    assert len(row["round_state"]["native_estimates"]) == 2
    assert rows[0]["inspection_window"]["end"] <= 4
    with pytest.raises(ValueError, match="outside recording"):
        classify_intervals(bundle, [{"start": 0, "end": 5}], result_id="one", bundle_sha256="x")


def test_representative_selection_balances_match_domain_and_caps_overlap():
    rows = []
    for match in range(8):
        for i, domain in enumerate(["round_state", "HUD", "life_state"]):
            rows.append(
                {
                    "issue_id": f"{match}-{i}",
                    "source": {"physical_match_id": str(match)},
                    "domain": domain,
                    "cluster": str(i),
                    "start": i * 10,
                    "end": i * 10 + 5,
                    "causes": [{"code": f"A{i + 1}"}],
                    "affected_domains": [domain],
                    "duration_seconds": 5,
                    "evidence_refs": ["native"],
                }
            )
    # Distinct problem clusters within each domain permit up to the per-match quota.
    for row in rows:
        row["cluster"] += row["source"]["physical_match_id"]
    prioritize(rows)
    ids = select_representatives(rows)
    chosen = [r for r in rows if r["issue_id"] in ids]
    assert len(chosen) == 24
    assert {
        d: sum(r["domain"] == d for r in chosen) for d in ["round_state", "HUD", "life_state"]
    } == {"round_state": 8, "HUD": 8, "life_state": 8}
    assert all(r["priority"]["scope"] == "review_utility_heuristic_not_correctness" for r in rows)


def test_bound_sidecar_pagination_and_before_after_context(tmp_path):
    manifest, entry = comparison_fixture(tmp_path)
    catalog = build_catalog(manifest)
    catalog_path = tmp_path / "catalog.json"
    write_private(catalog_path, catalog)
    analysis = analyze_catalog(manifest, catalog_path)
    analysis_path = tmp_path / "analysis.json"
    write_private(analysis_path, analysis)
    history_path = tmp_path / "history.json"
    write_private(
        history_path,
        {
            "version": HISTORY_VERSION,
            "formal_outputs": 0,
            "records": [
                {
                    "id": "one",
                    "problem": "tail",
                    "cause_hypothesis": "stale display",
                    "change": "opt-in",
                    "inputs": [],
                    "gained_controls": 0,
                    "lost_controls": 0,
                    "unverified_changes": [],
                    "decision": "research_only",
                    "next": "native review",
                }
            ],
        },
    )
    data = read_json(manifest)
    data["issue_analysis"] = {"path": str(analysis_path), "sha256": file_sha(analysis_path)}
    data["improvement_history"] = {"path": str(history_path), "sha256": file_sha(history_path)}
    manifest.write_text(__import__("json").dumps(data), encoding="utf-8")
    review = load_review_sidecars(manifest, {"one": entry})
    page = issue_page(review, result_id="one", page_size=1)
    assert len(page["records"]) <= 1
    assert all("sample_refs" not in r for r in page["records"])
    assert review["history"][0]["gained_controls"] == 0
    assert context_window({"one": entry}, "one", 0)["versions"][0]["seconds"][0]["sample_refs"]
    with pytest.raises(ValueError):
        context_window({"one": entry}, "one", 4)
    with pytest.raises(ValueError):
        issue_page(review, page=-1)
    catalog["results"][0]["review_intervals"] = [{"evidence_refs": ["a"], "sample_refs": ["b"]}]
    presentation = presentation_catalog(catalog)
    assert "evidence_refs" in catalog["results"][0]["review_intervals"][0]
    assert "evidence_refs" not in presentation["results"][0]["review_intervals"][0]
    changed = deepcopy(entry)
    changed["bundle_sha256"] = "changed"
    with pytest.raises(ValueError, match="baseline changed"):
        load_review_sidecars(manifest, {"one": changed})
