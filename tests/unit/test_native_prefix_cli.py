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
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["unqualified_ui_measurements_requested"] is include_ui
    assert report["qualification_loaded"] is False
    assert report["qualification_created"] is False
    assert report["events_released"] == 0
    before = output.read_bytes()
    with pytest.raises(FileExistsError, match='preserve existing'):
        subject.main()
    assert output.read_bytes() == before
    assert len(calls) == 1


@pytest.mark.parametrize('confirmed', [False, True])
def test_practical_cli_delegates_to_producer_and_never_releases_confirmed_events(
        tmp_path, monkeypatch, confirmed):
    analyzer = SimpleNamespace(fingerprint=lambda: 'a' * 64, global_qualification=None,
                               last_calibration_diagnostics={})
    calls = []

    def collect(actual, frames, **kwargs):
        assert actual is analyzer and frames == []
        calls.append(kwargs)
        boundary = SimpleNamespace(boundary_status='provisional', to_dict=lambda: {
            'boundary_status': 'provisional', 'kind': 'round_start'})
        return SimpleNamespace(source_rows=[], boundaries=[boundary], diagnostics=[],
                               confirmed_lifecycle=object() if confirmed else None)

    monkeypatch.setattr(subject, 'RealHudAnalyzer', lambda _: analyzer)
    monkeypatch.setattr(subject, 'collect_practical_lifecycle', collect)
    monkeypatch.setattr(subject, 'global_recognizer_fingerprint', lambda: 'b' * 64)
    monkeypatch.setattr(subject, 'VideoService', lambda: SimpleNamespace(
        native_window=lambda *_, **__: nullcontext([])))
    output, contract = tmp_path / 'out.json', tmp_path / 'contract.json'
    monkeypatch.setattr(sys, 'argv', [
        'probe', '--video', 'synthetic.mp4', '--source-sha256', 'c' * 64,
        '--layout', 'synthetic.json', '--start', '1', '--end', '2',
        '--native-step-ticks', '256', '--output', str(output),
        '--practical-input-contract', str(contract),
    ])
    if confirmed:
        with pytest.raises(ValueError, match='unqualified profile'):
            subject.main()
        assert not output.exists()
    else:
        subject.main()
        report = json.loads(output.read_text(encoding='utf-8'))
        assert report['practical_candidate_mode'] is True
        assert report['provisional_boundaries'][0]['boundary_status'] == 'provisional'
        assert report['events_released'] == 0
        assert report['qualification_created'] is False
    assert calls == [{'native_step_ticks': 256, 'input_contract_path': contract}]
