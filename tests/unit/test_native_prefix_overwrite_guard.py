"""An existing diagnostic receipt must survive without running recognition."""
import sys

import pytest

from scripts.diagnostics import validate_native_system_prefix as subject


def test_existing_receipt_is_rejected_before_analyzer_or_decoder(tmp_path, monkeypatch):
    output = tmp_path / '診断.json'
    output.write_text('{"receipt": "既存の証拠"}\n', encoding='utf-8')
    before = output.read_bytes()

    def forbidden(*_args, **_kwargs):
        pytest.fail('existing receipt must reject before Analyzer/VideoService construction')

    monkeypatch.setattr(subject, 'RealHudAnalyzer', forbidden)
    monkeypatch.setattr(subject, 'VideoService', forbidden)
    monkeypatch.setattr(sys, 'argv', [
        'diagnostic', '--video', 'synthetic.mp4', '--source-sha256', 'a' * 64,
        '--layout', 'synthetic.json', '--start', '1', '--end', '2',
        '--native-step-ticks', '256', '--output', str(output),
    ])
    with pytest.raises(FileExistsError, match='preserve existing'):
        subject.main()
    assert output.read_bytes() == before
