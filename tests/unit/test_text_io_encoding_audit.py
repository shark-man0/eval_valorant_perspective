"""Cross-platform evidence for UTF-8, cp1252, BOM and I/O classification."""

import codecs
import json
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
    original = codecs.BOM_UTF8 + "日本語\r\nsecond\r\n".encode("utf-8")
    path.write_bytes(original)
    assert path.read_text(encoding="utf-8-sig").splitlines() == ["日本語", "second"]
    assert path.read_bytes() == original
    assert path.read_text(encoding="utf-8").startswith("\ufeff")
