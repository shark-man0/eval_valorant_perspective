"""Diagnostic neighbors cannot cross native dimensions or timebase scopes."""

from test_conditional_state_tails import row

from valorant_ai_coach.temporal import view_ranking_experiment as experiment
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.replay import file_sha, write_private


def test_lopo_features_do_not_mix_resolution_scopes(tmp_path, monkeypatch):
    entries = []
    for match, source in enumerate(["a", "b"]):
        rows = []
        for tick in [0, 1, 4, 5]:
            positive = tick % 2 == 0
            sample = dict(row(tick, source=source)["sample"])
            sample.pop("sample_sha256")
            sample["frame_size_px"] = [1920, 1080] if positive else [1280, 720]
            sample = freeze_native_sample(sample)
            rows.append(
                observation(
                    sample=sample,
                    producer="f" * 64,
                    signals=["owner_hud"]
                    if positive
                    else ["recorder_elimination_display", "spectator"],
                    raw={
                        "classifiers": {
                            key: {"raw": "SELF" if positive else "SPECTATOR", "margin": 0.7}
                            for key in ["centroid", "three_prototypes"]
                        },
                        "view_hp": {"display": "100" if positive else None, "confidence": 0.98},
                        "current_HUD_component_supported": positive,
                        "owner_hypothesis_exclusions": [],
                    },
                    context={"unqualified_view_model": True},
                )
            )
        path = tmp_path / f"native_{match}.json"
        write_private(path, {"observations": rows})
        entries.append(
            {
                "physical_match": f"match{match}",
                "native_timeline": str(path),
                "native_sha256": file_sha(path),
            }
        )
    manifest = tmp_path / "manifest.json"
    write_private(manifest, {"records": entries})
    original = experiment.margin_features
    features = []

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        features.append(result)
        return result

    monkeypatch.setattr(experiment, "margin_features", capture)
    result = experiment.run(manifest, tmp_path / "result.json")
    assert len(features) == 8 and all(f[-1] == 0 for f in features)
    assert len(result["folds"]) == 2
    assert result["state_applied"] is False and result["human_accuracy"] is None
    assert result["pseudo_total"] == {1: 4, 0: 4}
