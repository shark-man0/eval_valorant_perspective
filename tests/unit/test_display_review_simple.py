from copy import deepcopy

import pytest

from scripts.diagnostics.display_review_simple import render_simple_display_review
from scripts.temporal_gt.contract import canonical_hash


def fixture():
    cases = []
    for j in range(2):
        frames = [
            {
                "id": f"f{j}_{i}",
                "source_id": "development-fixture",
                "source_sha256": "a" * 64,
                "tick": j * 600 + i,
                "time_base": "1/60",
                "epoch": f"acquisition{j}",
                "expected_step_ticks": 1,
                "encoded_sha256": f"{i + 1:064x}",
                "pixel_sha256": f"{i + 11:064x}",
                "uri": f"file:///synthetic/frame{j}_{i}.png",
            }
            for i in range(4)
        ]
        cases.append(
            {
                "id": f"c{j}",
                "frames": frames,
                "physical_episode_plan_id": "development-review-target",
                "views": [
                    {
                        "id": "native",
                        "all_native_images": True,
                        "frame_ids": [f["id"] for f in frames],
                    }
                ],
            }
        )
    packet = {"kind": "development_display_review_packet_v2_1", "cases": cases}
    response = {
        "kind": "development_display_review_response_v2_1",
        "origin": "human",
        "reviewer": "fixture-only",
        "packet_sha256": canonical_hash(packet),
        "internal_End_tick": None,
        "formal_events": [],
        "cases": [
            {"id": c["id"], "points": [], "scopes": [], "boundaries": [], "interval_claims": []}
            for c in cases
        ],
    }
    return packet, response


def render(p, r):
    return render_simple_display_review(p, r, trusted_packet_sha256=canonical_hash(p))


def test_renders_three_question_local_page_without_mutating_inputs():
    p, r = fixture()
    before = deepcopy((p, r))
    html = render(p, r)
    assert "3つの質問" in html and "simple_pair_review_v2_wait_decode" in html
    assert "decodeFrameReady" in html and "canRecordFrame" in html
    assert "__REVIEW_PAYLOAD__" not in html and "__REVIEW_SCRIPTS__" not in html
    assert (p, r) == before


@pytest.mark.parametrize(
    "mutation",
    [
        "network",
        "remote_file_host",
        "sparse",
        "epoch_cut",
        "missing_native_tick",
        "source",
        "episode",
        "wide",
    ],
)
def test_invalid_or_unsafe_native_material_is_rejected(mutation):
    p, r = fixture()
    c = p["cases"][1]
    if mutation == "network":
        c["frames"][0]["uri"] = "https://example.invalid/private.png"
    elif mutation == "remote_file_host":
        c["frames"][0]["uri"] = "file://remote-machine/private.png"
    elif mutation == "sparse":
        c["views"][0]["frame_ids"].pop(1)
    elif mutation == "epoch_cut":
        c["frames"][1]["epoch"] = "foreign-acquisition"
    elif mutation == "missing_native_tick":
        c["frames"][1]["tick"] += 1
        c["frames"][2]["tick"] += 1
        c["frames"][3]["tick"] += 1
    elif mutation == "source":
        for f in c["frames"]:
            f["source_sha256"] = "b" * 64
    elif mutation == "episode":
        c["physical_episode_plan_id"] = "different-episode"
    else:
        for f in c["frames"]:
            f["time_base"] = "1/1"
    r["packet_sha256"] = canonical_hash(p)
    with pytest.raises(ValueError):
        render(p, r)


def test_existing_answers_are_never_prefilled_as_an_unanswered_template():
    p, r = fixture()
    r["cases"][0]["points"] = [
        {"id": "p", "frame_id": "f0_0", "reviewed": True, "result_state": "PRESENT", "score": None}
    ]
    with pytest.raises(ValueError, match="unanswered template"):
        render(p, r)


def test_external_packet_anchor_cannot_be_replaced_by_response():
    p, r = fixture()
    with pytest.raises(ValueError, match="trusted packet"):
        render_simple_display_review(p, r, trusted_packet_sha256="b" * 64)


def test_metadata_closing_script_tags_are_data_not_executable_markup():
    p, r = fixture()
    for c in p["cases"]:
        c["physical_episode_plan_id"] = "</script><script>unsafe()</script>"
    r["packet_sha256"] = canonical_hash(p)
    html = render(p, r)
    assert "</script><script>unsafe()" not in html
    assert "<\\/script><script>unsafe()" in html
