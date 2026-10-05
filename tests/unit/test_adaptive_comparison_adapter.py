from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
adapter = importlib.import_module("compare_adaptive_regression")


class AdapterStrictnessTests(unittest.TestCase):
    def test_fact_records_cover_all_packages_and_ignore_generated_ids(self) -> None:
        old = {
            "observations": [{"time_sec": 1.0}],
            "round_packages": [
                {
                    "match_id": "m",
                    "round_no": 1,
                    "deterministic_facts": [
                        {
                            "fact_id": "old-a",
                            "key": "hp",
                            "value": None,
                            "confidence": 0.9,
                            "source": "hud",
                            "time_sec": 1.0,
                            "time_range": None,
                            "provenance_event_ids": ["old-event"],
                        }
                    ],
                },
                {
                    "match_id": "m",
                    "round_no": 2,
                    "deterministic_facts": [
                        {
                            "fact_id": "old-b",
                            "key": "hp",
                            "value": 0,
                            "confidence": 0.8,
                            "source": "hud",
                            "time_sec": 2.0,
                            "time_range": None,
                            "provenance_event_ids": ["old-event"],
                        }
                    ],
                },
            ],
        }
        new = {
            "observations": [{"time_sec": 1.0}, {"time_sec": 2.0}],
            "round_packages": [
                {
                    "match_id": "m",
                    "round_no": 1,
                    "deterministic_facts": [
                        {
                            "fact_id": "new-a",
                            "key": "hp",
                            "value": None,
                            "confidence": 0.9,
                            "source": "hud",
                            "time_sec": 1.0,
                            "time_range": None,
                            "provenance_event_ids": ["new-event"],
                        }
                    ],
                },
                {
                    "match_id": "m",
                    "round_no": 2,
                    "deterministic_facts": [
                        {
                            "fact_id": "new-b",
                            "key": "hp",
                            "value": 0,
                            "confidence": 0.8,
                            "source": "hud",
                            "time_sec": 2.0,
                            "time_range": None,
                            "provenance_event_ids": ["new-event"],
                        }
                    ],
                },
            ],
        }
        summary = adapter.fact_summary(old, new)["hp"]
        self.assertEqual(summary["baseline_count"], 2)
        self.assertEqual(summary["current_count"], 2)
        self.assertEqual(summary["semantic_records_retained_unchanged"], 2)
        self.assertEqual(summary["semantic_records_lost"], 0)
        self.assertEqual(summary["semantic_records_gained"], 0)

    def test_duplicate_fact_multiplicity_is_preserved(self) -> None:
        fact = {
            "key": "hp",
            "value": 0,
            "confidence": 1.0,
            "source": "hud",
            "time_sec": 4.0,
            "time_range": None,
        }
        old = {
            "observations": [{"time_sec": 4.0}],
            "round_packages": [
                {
                    "match_id": "m",
                    "round_no": 1,
                    "deterministic_facts": [{**fact, "fact_id": "a"}, {**fact, "fact_id": "b"}],
                }
            ],
        }
        new = {
            "observations": [{"time_sec": 4.0}],
            "round_packages": [
                {"match_id": "m", "round_no": 1, "deterministic_facts": [{**fact, "fact_id": "c"}]}
            ],
        }
        summary = adapter.fact_summary(old, new)["hp"]
        self.assertEqual(summary["semantic_records_retained_unchanged"], 1)
        self.assertEqual(summary["semantic_records_lost"], 1)
        self.assertEqual(summary["lost_at_common_observation_time"], 1)

    def test_null_value_is_distinct_from_numeric_zero(self) -> None:
        old = {
            "observations": [{"time_sec": 4.0}],
            "round_packages": [
                {
                    "match_id": "m",
                    "round_no": 1,
                    "deterministic_facts": [
                        {
                            "fact_id": "old",
                            "key": "hp",
                            "value": None,
                            "confidence": 1.0,
                            "source": "hud",
                            "time_sec": 4.0,
                            "time_range": None,
                        }
                    ],
                }
            ],
        }
        new = {
            "observations": [{"time_sec": 4.0}],
            "round_packages": [
                {
                    "match_id": "m",
                    "round_no": 1,
                    "deterministic_facts": [
                        {
                            "fact_id": "new",
                            "key": "hp",
                            "value": 0,
                            "confidence": 1.0,
                            "source": "hud",
                            "time_sec": 4.0,
                            "time_range": None,
                        }
                    ],
                }
            ],
        }
        summary = adapter.fact_summary(old, new)["hp"]
        self.assertEqual(summary["semantic_records_retained_unchanged"], 0)
        self.assertEqual(summary["semantic_records_lost"], 1)
        self.assertEqual(summary["semantic_records_gained"], 1)
        self.assertEqual(summary["semantic_slots_changed"], 1)

    def test_native_table_rejects_empty_duplicate_and_mismatched_order(self) -> None:
        base = {
            "stream_index": 0,
            "time_base_num": 1,
            "time_base_den": 60,
            "native_frames": [
                {
                    "source_frame_index": 0,
                    "pts": 0,
                    "stream_index": 0,
                    "best_effort_timestamp_time_sec": 0.0,
                },
                {
                    "source_frame_index": 1,
                    "pts": 1,
                    "stream_index": 0,
                    "best_effort_timestamp_time_sec": 1 / 60,
                },
            ],
        }
        self.assertEqual(len(adapter.native_index(base)[0]), 2)
        with self.assertRaises(ValueError):
            adapter.native_index({**base, "native_frames": []})
        duplicate = {
            **base,
            "native_frames": [base["native_frames"][0], {**base["native_frames"][1], "pts": 0}],
        }
        with self.assertRaises(ValueError):
            adapter.native_index(duplicate)
        reordered = {**base, "native_frames": list(reversed(base["native_frames"]))}
        with self.assertRaises(ValueError):
            adapter.native_index(reordered)

    def test_observation_duplicate_native_binding_rejected(self) -> None:
        table = {
            "stream_index": 0,
            "time_base_num": 1,
            "time_base_den": 60,
            "native_frames": [
                {
                    "source_frame_index": 0,
                    "pts": 10,
                    "stream_index": 0,
                    "best_effort_timestamp_time_sec": 1.0,
                }
            ],
        }
        raw = {"observations": [{"time_sec": 1.0}, {"time_sec": 1.0}]}
        with self.assertRaisesRegex(ValueError, "same native locator"):
            adapter.bind_observations(raw, table)

    def test_run_metadata_rejects_source_or_raw_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "raw.json"
            path.write_text("{}", encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            table = {"source_video_sha256": "a" * 64}
            raw = {"observations": [], "round_packages": []}
            metadata = {
                "metadata": {"source_sha256": "b" * 64, "git_is_dirty": False},
                "input_hashes": {"raw_processing.json": digest},
            }
            with self.assertRaisesRegex(ValueError, "source SHA"):
                adapter.validate_run_inputs(raw, metadata, path, table)
            metadata["metadata"]["source_sha256"] = "a" * 64
            metadata["input_hashes"]["raw_processing.json"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "raw_processing SHA"):
                adapter.validate_run_inputs(raw, metadata, path, table)

    def test_run_metadata_requires_explicit_dirty_state(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "raw.json"
            path.write_text("{}", encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            table = {"source_video_sha256": "a" * 64}
            raw = {"observations": [], "round_packages": []}
            metadata = {
                "metadata": {"source_sha256": "a" * 64},
                "input_hashes": {"raw_processing.json": digest},
            }
            with self.assertRaisesRegex(ValueError, "git_is_dirty"):
                adapter.validate_run_inputs(raw, metadata, path, table)

    def test_aggregate_guard_rejects_private_paths_and_locator_keys(self) -> None:
        adapter.assert_aggregate_only({"counts": {"matched": 2}})
        with self.assertRaisesRegex(ValueError, "private locator/path"):
            adapter.assert_aggregate_only({"records": [{"frame_key": "secret"}]})
        with self.assertRaisesRegex(ValueError, "private locator/path"):
            adapter.assert_aggregate_only({"private": {"path": r"C:\private\frame.jpg"}})

    def test_aggregate_writer_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "comparison.json"
            adapter.write_aggregate_exclusive(path, {"counts": {"common": 2}})
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"counts": {"common": 2}}
            )
            with self.assertRaises(FileExistsError):
                adapter.write_aggregate_exclusive(path, {"counts": {"common": 3}})

    @staticmethod
    def _run(
        primary: str,
        confidence: float,
        time: float,
        start: float,
        end: float,
        *,
        boundary: bool = False,
    ) -> dict:
        obs = {
            "time_sec": time,
            "primary_state": primary,
            "quality": {"hud_confidence": confidence},
            "state_flags": [],
            "values": {"buy_phase_visible": False},
        }
        package = {
            "match_id": "m",
            "round_no": 1,
            "source_video": {"duration_sec": 10.0},
            "round_window": {"start_sec": start, "end_sec": end},
        }
        events = [{"time_sec": start, "type": "round_start"}] if boundary else []
        return {"observations": [obs], "round_packages": [package], "hud_events": events}

    def test_unchanged_round_window_has_conditional_unchanged_reason(self) -> None:
        raw = self._run("live_first_person", 0.9, 1.0, 1.0, 2.0)
        comparison = adapter.round_window_summary(raw, raw)
        self.assertEqual(comparison["comparisons"][0]["measured_cause"], "window_bounds_unchanged")
        self.assertEqual(comparison["comparisons"][0]["start_delta_sec"], 0.0)

    def test_changed_boundary_window_is_not_given_fallback_causality(self) -> None:
        old = self._run("live_first_person", 0.9, 1.0, 1.0, 2.0, boundary=True)
        new = self._run("live_first_person", 0.9, 1.0, 1.5, 2.0, boundary=True)
        comparison = adapter.round_window_summary(old, new)
        self.assertEqual(
            comparison["comparisons"][0]["measured_cause"],
            "boundary_or_nonfallback_difference_requires_review",
        )

    def test_boundary_outside_window_still_blocks_fallback_causality(self) -> None:
        old = self._run("remote_control_view", 0.92, 1.0, 1.0, 2.0)
        new = self._run("live_first_person", 0.72, 2.0, 2.0, 2.5)
        old["hud_events"] = [{"time_sec": 0.5, "type": "round_start"}]
        new["hud_events"] = [{"time_sec": 0.5, "type": "round_start"}]
        comparison = adapter.round_window_summary(old, new)
        row = comparison["comparisons"][0]
        self.assertEqual(row["baseline"]["boundary_event_count"], 0)
        self.assertEqual(row["baseline"]["run_boundary_event_count"], 1)
        self.assertFalse(row["baseline"]["fallback_causality_eligible"])
        self.assertEqual(
            row["measured_cause"], "boundary_or_nonfallback_difference_requires_review"
        )

    def test_earlier_global_usable_sample_prevents_fallback_attribution(self) -> None:
        old = self._run("live_first_person", 0.9, 2.0, 2.0, 3.0)
        new = self._run("live_first_person", 0.9, 3.0, 3.0, 4.0)
        old["observations"].insert(
            0, self._run("live_first_person", 0.9, 1.0, 1.0, 2.0)["observations"][0]
        )
        new["observations"].insert(
            0, self._run("live_first_person", 0.9, 1.0, 1.0, 2.0)["observations"][0]
        )
        comparison = adapter.round_window_summary(old, new)
        row = comparison["comparisons"][0]
        self.assertTrue(row["baseline"]["start_matches_earliest_usable_sample"])
        self.assertFalse(row["baseline"]["start_matches_global_earliest_usable_sample"])
        self.assertFalse(row["baseline"]["fallback_causality_eligible"])
        self.assertEqual(
            row["measured_cause"], "boundary_or_nonfallback_difference_requires_review"
        )

    def test_multi_package_start_change_remains_unresolved(self) -> None:
        old = self._run("live_first_person", 0.9, 1.0, 1.0, 2.0)
        new = self._run("live_first_person", 0.9, 2.0, 2.0, 3.0)
        old["round_packages"].append(
            {
                "match_id": "m",
                "round_no": 2,
                "source_video": {"duration_sec": 10.0},
                "round_window": {"start_sec": 2.0, "end_sec": 3.0},
            }
        )
        new["round_packages"].append(
            {
                "match_id": "m",
                "round_no": 2,
                "source_video": {"duration_sec": 10.0},
                "round_window": {"start_sec": 3.0, "end_sec": 4.0},
            }
        )
        comparison = adapter.round_window_summary(old, new)
        first = comparison["comparisons"][0]
        self.assertFalse(first["baseline"]["fallback_causality_eligible"])
        self.assertEqual(
            first["measured_cause"], "boundary_or_nonfallback_difference_requires_review"
        )

    def test_retained_old_earliest_sample_that_loses_usability_is_explicit(self) -> None:
        old = self._run("remote_control_view", 0.92, 1.0, 1.0, 2.0)
        new = {
            **self._run("unknown", 0.45, 1.0, 2.0, 2.5),
            "observations": [
                self._run("unknown", 0.45, 1.0, 2.0, 2.5)["observations"][0],
                self._run("live_first_person", 0.72, 2.0, 2.0, 2.5)["observations"][0],
            ],
        }
        comparison = adapter.round_window_summary(old, new)
        self.assertEqual(
            comparison["comparisons"][0]["measured_cause"],
            "baseline_start_sample_retained_but_fails_current_usable_filter",
        )


if __name__ == "__main__":
    unittest.main()
