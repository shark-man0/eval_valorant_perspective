from valorant_ai_coach.temporal import map_view_episodes as model


def test_only_measured_samples_can_share_an_episode_through_lifecycle_boundaries(monkeypatch):
    monkeypatch.setattr(
        model, "measure_recorder_view", lambda f, _r: (f.get("measured"), False),
    )
    states = [
        ("SELF", "ALIVE", "a", None),
        ("UNKNOWN", "UNKNOWN", None, None),
        ("SELF", "ALIVE", "a", None),
        ("SPECTATOR", "DEAD", None, None),
        ("SELF", "ALIVE", "a", None),
        ("SELF", "ALIVE", "a", "r"),
        ("SELF", "ALIVE", "b", "r"),
    ]
    frames = {}
    for i, (camera, life, measured, token) in enumerate(states):
        key = str(i)
        frames[key] = {
            "sample": {"source_id": "s", "source_sha256": "s", "acquisition_id": "a",
                       "native_epoch": "e", "native_time_base": "1/5", "native_pts_tick": i,
                       "frame_size_px": [100, 100], "sample_sha256": key},
            "camera": {"value": camera}, "life": {"value": life}, "round": {"value": "UNKNOWN"},
            "observation_ids": [], "continuity": {"carry_allowed": True}, "tracking_epoch": "x",
            "measured": measured, "round_token": token,
        }
    results = model.map_view_episodes({"observations": {}, "native_frames": frames})
    assert [x.current_samples for x in results] == [("0", "2"), ("4",), ("5",), ("6",)]
    assert [x.opening_boundary for x in results] == [
        "capture_start", "other_view_state", "round_scope_changed", "current_view_gap_or_change",
    ]
    assert results[1].boundary_sample_ref == "3"
