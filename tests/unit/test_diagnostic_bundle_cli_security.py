from pathlib import Path

import pytest

from scripts.diagnostics.create_bundle import _resolve_run_dir


def test_resolve_run_dir_stays_under_selected_diagnostics_root(tmp_path: Path) -> None:
    root = tmp_path / "diagnostics"
    resolved = _resolve_run_dir(root, "run-001")
    assert resolved == root.resolve() / "run-001"


def test_resolve_run_dir_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "diagnostics"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "run-001"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="symlink"):
        _resolve_run_dir(root, "run-001")


@pytest.mark.parametrize("run_id", ["../escape", "/absolute", ".", "..", "bad/name"])
def test_resolve_run_dir_rejects_unsafe_run_ids(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        _resolve_run_dir(tmp_path / "diagnostics", run_id)
