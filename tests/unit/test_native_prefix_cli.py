import json
import sys
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from scripts.diagnostics import validate_native_system_prefix as subject


@pytest.mark.parametrize("include_ui", [False, True])
def test_cli_explicit_unqualified_ui_option_never_qualifies_or_releases_events(
        tmp_path, monkeypatch, include_ui):
    output = tmp_path / "diagnostic.json"
    calls = []

    class Analyzer:
        global_qualification = None
        last_calibration_diagnostics = {}

        def fingerprint(self):
            return "a" * 64

        def observe_native_system_frames(self, frames, **kwargs):
            calls.append(kwargs)
            return ()

    monkeypatch.setattr(subject, "RealHudAnalyzer", lambda *_: Analyzer())
    monkeypatch.setattr(subject, "global_recognizer_fingerprint", lambda: "b" * 64)
    monkeypatch.setattr(subject, "VideoService", lambda: SimpleNamespace(
        native_window=lambda *_, **__: nullcontext([])))
    args = ["probe", "--video", str(tmp_path / "synthetic.mp4"), "--source-sha256", "c" * 64,
            "--layout", str(tmp_path / "synthetic.json"), "--start", "1", "--end", "2",
            "--native-step-ticks", "256", "--output", str(output)]
    if include_ui:
        args.append("--include-ui-measurements")
    monkeypatch.setattr(sys, "argv", args)
    subject.main()
    assert calls == [{"native_step_ticks": 256, "include_ui_measurements": include_ui}]
    report = json.loads(output.read_text())
    assert report["unqualified_ui_measurements_requested"] is include_ui
    assert report["qualification_loaded"] is False
    assert report["qualification_created"] is False
    assert report["events_released"] == 0
