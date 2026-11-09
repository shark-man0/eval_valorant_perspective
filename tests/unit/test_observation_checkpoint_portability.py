from valorant_ai_coach.temporal import checkpoint as module


def test_checkpoint_does_not_require_unix_only_fchmod(tmp_path, monkeypatch):
    monkeypatch.delattr(module.os, "fchmod", raising=False)
    directory = tmp_path / "cache_PRIVATE"
    cache = module.ObservationCheckpoint(directory, {"source": "synthetic"})
    rows = [{"measurement": {"label": "合成観測"}}]
    cache.save("coarse", {"start": 0}, rows, complete=False)
    reloaded = module.ObservationCheckpoint(directory, {"source": "synthetic"})
    assert reloaded.load("coarse", {"start": 0}) == (rows, False)
