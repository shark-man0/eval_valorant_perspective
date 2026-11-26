from pathlib import Path


def test_gap_summary_counts_eligible_seconds_and_shared_rejections(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/map_learning"))
    from summarize_runs import _position_gap_seconds

    seconds = [
        {"timestamp": second, "sample_refs": refs}
        for second, refs in enumerate([["a", "b"], ["c"], ["d", "e"], ["outside"], ["f"]])
    ]
    eligible = ["a", "b", "c", "d", "e", "f"]
    reference = {"comparison_evidence": {
        "operable_sample_refs": eligible, "unresolved_portrait_sample_refs": ["a", "b", "d", "e"],
    }}
    adaptive = {"comparison_evidence": {
        "operable_sample_refs": eligible, "unresolved_portrait_sample_refs": ["a", "b", "d"],
    }}

    def report(found):
        return {
            "operable_coverage": {
                "operable_seconds_with_current_evidence": 4,
                "operable_seconds_with_position": 1,
            },
            "second_rows": [
                {
                    "timestamp": row["timestamp"],
                    "recorder_map_observations": [row] if i in found else [],
                }
                for i, row in enumerate(seconds)
            ],
        }

    assert _position_gap_seconds(seconds, reference, adaptive, report({4}), report({1, 3})) == {
        "remaining": 3,
        "both_portrait_stages_rejected_all": 1,
        "added_in_recovery": 1,
        "lost_in_recovery": 1,
    }
