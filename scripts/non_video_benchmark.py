"""Reproducible synthetic benchmark for non-video read/search/statistics/export.

Execute: python scripts/non_video_benchmark.py
No video data, image data, paid API or performance gate.
"""

from __future__ import annotations

import json
import statistics
import tempfile
import time
import tracemalloc
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from valorant_ai_coach.non_video.features import NonVideoFeatures
from valorant_ai_coach.storage.repository import SQLiteRepository


def measure(func: Callable[[], Any], repeats: int = 3) -> dict[str, Any]:
    durations = []
    peak = 0
    value: Any = None
    for _ in range(repeats):
        tracemalloc.start()
        start = time.perf_counter()
        value = func()
        elapsed = time.perf_counter() - start
        _, used = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak = max(peak, used)
        durations.append(elapsed * 1000)
    return {
        "median_ms": round(statistics.median(durations), 3),
        "peak_traced_bytes": peak,
        "result_count": len(value) if isinstance(value, list) else None,
    }


def make_data(root: Path, matches: int, per_match: int = 5) -> tuple[SQLiteRepository, NonVideoFeatures]:
    repo = SQLiteRepository(root / "app.db")
    for i in range(matches):
        match_id = f"bench-{i:05d}"
        repo.create_match(match_id, root / f"{match_id}.mp4",
                          status="partial" if i % 10 == 0 else "completed")
        repo.save_analysis_result({
            "match_id": match_id,
            "round_no": 1,
            "evaluations": [
                {"evaluation_id": f"ev-{i:05d}-{j:03d}",
                 "primary_rule_id": ("AIM-02" if j % 2 == 0 else "MOV-02"),
                 "label": ("good", "improve", "unscored")[j % 3],
                 "confidence": 0.8,
                 "reason": f"合成評価 {i} - {j}",
                 "improvement": "次回確認" if j % 3 == 1 else None}
                for j in range(per_match)
            ],
        })
    return repo, NonVideoFeatures(repo)


def old_search(repo: SQLiteRepository) -> list[str]:
    ids = []
    for match in repo.list_matches():
        for evaluation in repo.list_evaluations(match["match_id"]):
            if evaluation.get("primary_rule_id") == "AIM-02":
                ids.append(str(evaluation["evaluation_id"]))
    return sorted(ids)


def new_search(features: NonVideoFeatures) -> list[str]:
    ids = []
    offset = 0
    while True:
        page = features.search(rule="AIM-02", offset=offset, limit=500)
        ids.extend(str(item["evaluation_id"]) for item in page)
        if len(page) < 500:
            break
        offset += len(page)
    return sorted(ids)


def old_statistics(repo: SQLiteRepository) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for match in repo.list_matches():
        counts.update(row["label"] for row in repo.list_evaluations(match["match_id"]))
    return dict(counts)


def main() -> int:
    observations = []
    with tempfile.TemporaryDirectory(prefix="valorant-nonvideo-bench-") as temporary:
        for matches in (10, 100, 1000):
            root = Path(temporary) / str(matches)
            root.mkdir()
            repo, features = make_data(root, matches)
            expected = old_search(repo)
            actual = new_search(features)
            if expected != actual:
                raise AssertionError("Optimized search changed the result set")
            legacy_counts = old_statistics(repo)
            optimized_counts = features.statistics()["counts"]
            if any(legacy_counts.get(k, 0) != optimized_counts[k] for k in optimized_counts):
                raise AssertionError("Optimized statistics changed the counts")
            destination = root / "report.json"
            summary = {
                "match_count": matches,
                "evaluation_count": matches * 5,
                "matches_incomplete": (matches + 9) // 10,
                "legacy_search": measure(lambda: old_search(repo)),
                "indexed_search": measure(lambda: new_search(features)),
                "legacy_statistics": measure(lambda: old_statistics(repo)),
                "sql_statistics": measure(lambda: features.statistics()),
                "json_export": measure(
                    lambda: features.export_report("bench-00000", destination, "json")
                ),
                "csv_export": measure(
                    lambda: features.export_report("bench-00000", destination, "csv")
                ),
                "consistency": "passed",
            }
            observations.append(summary)
    print(json.dumps({"benchmark_version": 1, "synthetic_only": True,
                      "results": observations}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
