"""Static private source-only frame viewer; only the human exports observations."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any


def write_page(session: Path, folder: Path, plan: dict[str, Any], acq: dict[str, Any]) -> None:
    from scripts.temporal_gt.review_session import response_defaults

    data = {
        "frames": [dict(f, uri=Path(f["path"]).as_uri()) for f in acq["frames"]],
        "response": response_defaults(acq),
        "acquisition_id": acq["acquisition_id"],
        "schedule": plan["planned_windows"],
        "time_base": plan["time_base"],
        "video_uri": Path(acq["video_path"]).as_uri(),
    }
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("source_review.html").read_text(encoding="utf-8")
    page = template.replace("__PAYLOAD__", payload)
    # A private HTML contains native PTS and absolute local evidence URIs. Never commit it.
    page = page.replace("<title>", "<!-- " + html.escape(session.name) + " -->\n<title>", 1)
    target = folder / "review.html"
    with target.open("x", encoding="utf-8") as stream:
        stream.write(page)
    os.chmod(target, 0o600)
