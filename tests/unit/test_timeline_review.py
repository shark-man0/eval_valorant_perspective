import json

import pytest

from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.replay import file_sha
from valorant_ai_coach.temporal.timeline_review import PACKET_VERSION, ReviewSession


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_review_requires_exact_image_and_explicit_confirmation_and_preserves_revisions(tmp_path):
    sample = obs(10)["sample"]
    key = sample["source_sha256"]
    manifest = write(tmp_path / "manifest.json", {"records": [{
        "source_sha256": key, "video_id": sample["source_id"], "physical_match_id": "synthetic",
        "status": "accepted", "split": "DEVELOPMENT", "exposure": "DEVELOPMENT",
    }]})
    allocation = write(tmp_path / "allocation.json", {})
    policy = write(tmp_path / "policy.json", {
        "manifest": str(manifest), "allocation": str(allocation),
        "manifest_sha256": file_sha(manifest), "allocation_sha256": file_sha(allocation),
        "allowed_source_sha256s": [key],
    })
    packet = write(tmp_path / "packet.json", {
        "version": PACKET_VERSION, "formal_outputs": 0,
        "sources": {key: {"policy_path": str(policy), "native_origin_seconds": "0"}},
        "items": [{
            "review_id": "case", "source_sha256": key, "sample": sample,
            "physical_match_id": "synthetic", "source_alias": "synthetic",
            "source_video_time": 1, "context_start_seconds": 0, "context_end_seconds": 4,
            "comparison_split": "DEVELOPMENT_COMPARISON_EXPOSED", "label_scope": "test",
            "review_fields": ["round_state"], "current_prediction": {}, "event_candidates": [],
        }],
    })
    path = tmp_path / "answers.jsonl"
    session = ReviewSession(packet, path)
    assert session.overview()["reviewed"] == 0
    answer = {"review_id": "case", "reviewer": "synthetic", "labels": {"round_state": "ACTIVE"}}
    with pytest.raises(ValueError, match="confirmation"):
        session.save(answer)
    answer["confirmed"] = True
    with pytest.raises(ValueError, match="verified"):
        session.save(answer)
    session.image_hashes["case"] = "c" * 64
    session.save(answer)
    answer["labels"] = {"round_state": "UNKNOWN"}
    session.save(answer)
    lines = path.read_text(encoding="utf-8").splitlines()
    original, revision = [json.loads(line) for line in lines]
    assert revision["supersedes"] == original["answer_sha256"]
    assert revision["sample"] == sample and revision["image_sha256"] == "c" * 64
    assert original["labels"]["round_state"] == "ACTIVE"
    assert ReviewSession(packet, path).item(0)["labels"] == {"round_state": "UNKNOWN"}
