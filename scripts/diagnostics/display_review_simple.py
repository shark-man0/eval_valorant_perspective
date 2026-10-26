"""Render an opt-in private three-question UI; never acquire sources or save GT."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.diagnostics.display_review_scope import validate_display_review

ASSETS = Path(__file__).with_name("display_review_assets")


def render_simple_display_review(
    packet: dict[str, Any], unanswered_template: dict[str, Any], *, trusted_packet_sha256: str
) -> str:
    """Return local HTML for two bounded acquisitions of one episode target.

    Callers must admit DEVELOPMENT sources, verify actual source/frame bytes,
    freeze the packet externally, save HTML privately, and preserve exposure and
    actual raw responses. This function reads repository UI assets only. It
    cannot establish human attention, visual continuity, semantic correctness or
    independent qualification. It has no production caller or event writer.
    """
    validate_display_review(
        packet, unanswered_template, trusted_packet_sha256=trusted_packet_sha256
    )
    cases = packet["cases"]
    if len(cases) != 2:
        raise ValueError("two source-bound acquisition cases required")
    if any(
        a[k]
        for a in unanswered_template["cases"]
        for k in ("points", "scopes", "boundaries", "interval_claims")
    ):
        raise ValueError("use an unanswered template, never existing labels")
    identity = set()
    for case in cases:
        episode = case.get("physical_episode_plan_id")
        if not isinstance(episode, str) or not episode:
            raise ValueError("explicit episode plan identity required, not inferred truth")
        by_id = {f["id"]: f for f in case["frames"]}
        order = list(by_id)
        native = next(
            (v for v in case.get("views", []) if v.get("all_native_images") is True), None
        )
        if native is None or not isinstance(native.get("frame_ids"), list):
            raise ValueError("an explicit all-native-images review view is required")
        ids = native["frame_ids"]
        if len(ids) < 2 or any(not isinstance(i, str) or i not in by_id for i in ids):
            raise ValueError("prepared review frames required")
        lo, hi = order.index(ids[0]), order.index(ids[-1])
        if ids != order[lo : hi + 1]:
            raise ValueError("sparse preview cannot stand in for all Native images")
        frames = [by_id[i] for i in ids]
        for a, b in zip(frames, frames[1:], strict=False):
            if (
                a["epoch"] != b["epoch"]
                or b.get("discontinuity", False)
                or b["tick"] - a["tick"] != b["expected_step_ticks"]
            ):
                raise ValueError("continuous Native view required; keep cuts UNKNOWN separately")
        width = (frames[-1]["tick"] - frames[0]["tick"]) * Fraction(frames[0]["time_base"])
        if not 0 < width <= 2:
            raise ValueError("Native review view must be bounded to two seconds")
        for f in frames:
            uri = urlsplit(f.get("uri") or "")
            if uri.scheme != "file" or uri.netloc not in ("", "localhost") or not uri.path:
                raise ValueError("verified local file images only; no network image URLs")
        identity.add(
            (episode, frames[0]["source_id"], frames[0]["source_sha256"], frames[0]["time_base"])
        )
    if len(identity) != 1:
        raise ValueError("one source and episode target across both acquisitions required")
    payload = json.dumps(
        {"packet": packet, "template": unanswered_template}, ensure_ascii=False
    ).replace("</", "<\\/")
    scripts = "\n".join(
        (ASSETS / name).read_text(encoding="utf-8")
        for name in ("frame_gate.js", "simple_model.js", "simple_ui.js")
    )
    html = (ASSETS / "simple_review.html").read_text(encoding="utf-8")
    return html.replace("__REVIEW_PAYLOAD__", payload).replace("__REVIEW_SCRIPTS__", scripts)
