import errno
from pathlib import Path
from unittest.mock import Mock

import pytest

from valorant_ai_coach.recordings.catalog import CatalogError


def test_map_batch_retries_only_a_busy_catalog_lock(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/map_learning"
    monkeypatch.syspath_prepend(str(scripts))
    import run_batch

    occupied = CatalogError("カタログは別の処理が使用中です")
    occupied.__cause__ = BlockingIOError(errno.EAGAIN, "busy")
    catalog = Mock()
    catalog.record_exposure.side_effect = [occupied, None]
    sleeper = Mock()
    monkeypatch.setattr(run_batch.time, "sleep", sleeper)
    run_batch.record_map_exposure(catalog, "dev")
    assert catalog.record_exposure.call_count == 2
    sleeper.assert_called_once_with(0.16)

    catalog.reset_mock()
    catalog.record_exposure.side_effect = CatalogError("catalog evidence changed")
    with pytest.raises(CatalogError, match="catalog evidence changed"):
        run_batch.record_map_exposure(catalog, "dev")
    assert catalog.record_exposure.call_count == 1
