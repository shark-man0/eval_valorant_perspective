"""Cross-platform evidence for UTF-8, cp1252, BOM and I/O classification."""

import codecs
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.audit_text_io import scan_source


def test_inventory_distinguishes_explicit_utf8_binary_and_unknown() -> None:
    source = """
from pathlib import Path
import subprocess
a = Path('a').read_text(encoding='utf-8')
b = Path('b').read_text()
c = Path('c').open('rb')
d = open('d', 'w', encoding='utf-8-sig')
e = subprocess.run(['git', 'status'], text=True, capture_output=True)
f = Path('e').write_bytes(b'123')
"""
    result = scan_source(source, "synthetic.py")
    assert [item["category"] for item in result] == [
        "UTF-8明示", "要調査", "Binary I/O",
        "UTF-8明示", "要調査", "Binary I/O",
    ]


def test_japanese_json_round_trip_when_cp1252_cannot_decode(tmp_path: Path) -> None:
    path = tmp_path / "日本語 テスト #.json"
    payload = {"録画": "試合と戦術", "count": 2}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
    raw = path.read_bytes()
    assert codecs.decode(raw, "utf-8") == path.read_text(encoding="utf-8")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("cp1252")
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert path.read_bytes() == raw


def test_bom_and_crlf_are_not_silently_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "bom-data.txt"
    original = codecs.BOM_UTF8 + "日本語\r\nsecond\r\n".encode()
    path.write_bytes(original)
    assert path.read_text(encoding="utf-8-sig").splitlines() == ["日本語", "second"]
    assert path.read_bytes() == original
    assert path.read_text(encoding="utf-8").startswith("\ufeff")


def test_diagnostic_json_writes_are_explicitly_utf8() -> None:
    """Protect application-owned diagnostic JSON from Windows locale drift."""
    root = Path(__file__).resolve().parents[2]
    audited = (
        "assemble_source_review_plan.py",
        "audit_assured_start_evidence.py",
        "audit_client_graph_history.py",
        "audit_descriptor_competitors.py",
        "audit_descriptor_photometry.py",
        "audit_native_adjacent_regions.py",
        "audit_native_png_storage.py",
        "audit_native_seed_failure.py",
        "audit_corner_crop_context.py",
        "audit_fixed_camera_domains.py",
        "compare_native_foreground.py",
        "validate_fixed_shared_score_source.py",
        "validate_frozen_result_feature.py",
        "validate_native_system_prefix.py",
        "validate_scene_chain_cohort.py",
        "validate_scene_world_holdout.py",
        "validate_unedited_native_start.py",
    )
    for filename in audited:
        path = root / "scripts" / "diagnostics" / filename
        findings = scan_source(path.read_text(encoding="utf-8"), str(path))
        writers = [site for site in findings if site["operation"] == "write_text"]
        assert writers, filename
        assert all(site["category"] == "UTF-8明示" for site in writers), filename


def test_frame_suite_json_writes_are_explicitly_utf8() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "e2e" / "build_frame_suites.py"
    findings = scan_source(path.read_text(encoding="utf-8"), str(path))
    writers = [site for site in findings if site["operation"] == "write_text"]
    assert writers
    assert all(site["category"] == "UTF-8明示" for site in writers)


def test_ffprobe_json_subprocess_calls_use_explicit_utf8() -> None:
    root = Path(__file__).resolve().parents[2]
    audited = (
        "src/valorant_ai_coach/video/native.py",
        "src/valorant_ai_coach/video/native_replay.py",
        "scripts/diagnostics/diagnose_native_global_lifecycle.py",
        "scripts/diagnostics/diagnose_roster_window.py",
        "scripts/diagnostics/intake_recording.py",
        "scripts/e2e/prepare_pack_source.py",
        "scripts/e2e/validate_fixture.py",
    )
    for filename in audited:
        path = root / filename
        findings = scan_source(path.read_text(encoding="utf-8"), str(path))
        text_processes = [
            site for site in findings
            if site["operation"] == "subprocess" and site["category"] != "Binary I/O"
        ]
        assert text_processes, filename
        assert all(site["category"] == "UTF-8明示" for site in text_processes), filename


def test_utf8_subprocess_json_survives_cp1252_host() -> None:
    code = "import sys; sys.stdout.buffer.write('日本語'.encode())"
    raw = subprocess.run([sys.executable, "-c", code], capture_output=True, check=True).stdout
    with pytest.raises(UnicodeDecodeError):
        raw.decode("cp1252")
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, check=True,
        text=True, encoding="utf-8",
    )
    assert result.stdout == "日本語"
