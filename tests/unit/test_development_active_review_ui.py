import json
import re
import threading
import urllib.error
import urllib.request
from copy import deepcopy

import cv2
import numpy as np
import pytest

from tests.unit.test_development_active_review import item
from valorant_ai_coach.visual.development_active_review import ReviewPolicy, select_review
from valorant_ai_coach.visual.development_active_review_ui import (
    SemanticReviewStore,
    build_manifest,
    make_review_server,
    render_review,
)
from valorant_ai_coach.visual.development_marker_features import _digest


def manifest(*, synthetic=False):
    selection = select_review([item(0)], policy=ReviewPolicy(hard_slots=1, audit_slots=0))
    ok, png = cv2.imencode(".png", np.full((25, 25, 3), 128, np.uint8))
    assert ok
    return build_manifest(
        selection, {selection["selected"][0]["item_id"]: png.tobytes()}, synthetic=synthetic
    )


def payload(m, label="UNKNOWN"):
    return {
        "manifest_fingerprint": m["manifest_fingerprint"],
        "item_id": m["items"][0]["item_id"],
        "label": label,
    }


def test_one_choice_is_saved_without_center_reclick_or_metadata_input(tmp_path):
    m = manifest()
    store = SemanticReviewStore(m, tmp_path / "review")
    result = store.save(payload(m))
    assert result["saved"] and result["saved_count"] == 1
    key = m["items"][0]["item_id"]
    row = json.loads((tmp_path / "review" / f"review_{key}_latest.json").read_bytes())
    assert row["semantic_label"] == "UNKNOWN" and row["label_origin"] == "human_confirmed"
    assert row["human_center_verified"] is False and row["ownership"] == "UNKNOWN"
    assert row["formal_outputs"] == 0 and row["frame"] == json.loads(
        json.dumps(m["items"][0]["candidate"]["frame"])
    )
    assert row["review_visibility"] == "PREDICTION_BLIND"


def test_repeated_save_is_idempotent_and_changed_choice_appends_revision(tmp_path):
    m = manifest()
    store = SemanticReviewStore(m, tmp_path / "review")
    a = store.save(payload(m, "PLAYER"))
    b = store.save(payload(m, "PLAYER"))
    assert a == b
    c = store.save(payload(m, "DEATH_MARKER"))
    assert c["revision"] == 2 and c["saved_count"] == 1
    assert len(list((tmp_path / "review").glob("*_rev*.json"))) == 2


def test_synthetic_ui_exercise_cannot_be_imported_as_human_label_evidence(tmp_path):
    from valorant_ai_coach.visual.development_learning_dataset import LabelOrigin

    m = manifest(synthetic=True)
    store = SemanticReviewStore(m, tmp_path / "synthetic")
    store.save(payload(m, "PLAYER"))
    row = json.loads(next((tmp_path / "synthetic").glob("*latest.json")).read_bytes())
    assert row["dataset_kind"] == "SYNTHETIC_TEST" and row["label_origin"] == "synthetic_test"
    with pytest.raises(ValueError):
        LabelOrigin(row["label_origin"])


def test_atomic_latest_failure_is_retryable_without_overwriting_orphan_revision(
    tmp_path, monkeypatch
):
    import valorant_ai_coach.visual.development_active_review_ui as ui

    m = manifest()
    store = SemanticReviewStore(m, tmp_path / "review")

    def fail(*args):
        raise OSError("synthetic interrupted latest commit")

    with monkeypatch.context() as patch:
        patch.setattr(ui.os, "replace", fail)
        with pytest.raises(OSError):
            store.save(payload(m))
    result = store.save(payload(m))
    assert result["revision"] == 2 and result["saved_count"] == 1
    assert len(list((tmp_path / "review").glob("*_rev*.json"))) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        {"label": "SELF"},
        {"item_id": "../escape"},
        {"manifest_fingerprint": "f" * 64},
        {"frame": {"owner": "SELF"}},
    ],
)
def test_payload_cannot_override_source_or_promote_owner(tmp_path, mutation):
    m = manifest()
    store = SemanticReviewStore(m, tmp_path / "review")
    with pytest.raises(ValueError):
        store.save(payload(m) | mutation)
    assert not store.saved()


def test_changed_manifest_asset_or_saved_bytes_are_rejected(tmp_path):
    m = manifest()
    broken = deepcopy(m)
    broken["visibility"] = "PREDICTION_EXPOSED"
    with pytest.raises(ValueError, match="manifest"):
        SemanticReviewStore(broken, tmp_path / "bad")
    store = SemanticReviewStore(m, tmp_path / "good")
    store.save(payload(m))
    p = next((tmp_path / "good").glob("*latest.json"))
    row = json.loads(p.read_bytes())
    row["semantic_label"] = "PLAYER"
    p.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        store.saved()


def test_blind_page_does_not_serialize_predictions_or_hard_audit_reasons():
    m = manifest()
    page = render_review(m, "synthetic-token", {})
    data = json.loads(re.search(r"const data=(.*?);\nconst names", page, re.S).group(1))
    assert set(data["items"][0]) == {"item_id", "image"}
    assert "teacher_labels" not in page and "raw_geometry" not in page
    exposed = deepcopy(m)
    exposed["visibility"] = "PREDICTION_EXPOSED"
    assert "predictions" in render_review(exposed, "synthetic-token", {})


def test_private_review_files_cannot_be_written_into_git(tmp_path):
    m = manifest()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: example", encoding="utf-8")
    with pytest.raises(ValueError, match="outside Git"):
        SemanticReviewStore(m, repo / "responses")


def test_fake_traversal_identifier_cannot_pass_even_with_recomputed_manifest_digest(tmp_path):
    m = manifest()
    m["items"][0]["item_id"] = "../escape"
    m["manifest_fingerprint"] = _digest({k: v for k, v in m.items() if k != "manifest_fingerprint"})
    with pytest.raises(ValueError):
        SemanticReviewStore(m, tmp_path / "review")


def test_loopback_server_rejects_forged_origin_and_accepts_bound_synthetic_choice(tmp_path):
    m = manifest()
    store = SemanticReviewStore(m, tmp_path / "review")
    server = make_review_server(store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        page = urllib.request.urlopen(origin, timeout=5).read().decode("utf-8")
        data = json.loads(re.search(r"const data=(.*?);\nconst names", page, re.S).group(1))
        content = json.dumps(payload(m, "UI")).encode("utf-8")
        bad = urllib.request.Request(
            origin + "/submit",
            content,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://not-local.invalid",
                "X-Review-Token": data["token"],
            },
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(bad, timeout=5)
        assert exc.value.code == 403 and not store.saved()
        good = urllib.request.Request(
            origin + "/submit",
            content,
            headers={
                "Content-Type": "application/json",
                "Origin": origin,
                "X-Review-Token": data["token"],
            },
        )
        result = json.loads(urllib.request.urlopen(good, timeout=5).read())
        assert result["saved"] and store.saved()[m["items"][0]["item_id"]] == "UI"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
