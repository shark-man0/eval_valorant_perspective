"""Tiny generated containers test transport, not unseen VALORANT recognition."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from valorant_ai_coach.temporal import validation as v
from valorant_ai_coach.temporal.replay import read_json, write_private


def test_two_synthetic_inputs_enroll_generate_compare_and_repeat(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe") or not shutil.which("git"):
        pytest.skip("Native container tools and Git unavailable")
    repository = tmp_path / "frozen-repository"
    repository.mkdir()
    subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Synthetic Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "Synthetic runtime anchor",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    module = tmp_path / "synthetic_pixel_supplier.py"
    module.write_text(
        """from pathlib import Path
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.replay import file_sha

class Reader:
    def __init__(self, config):
        self.bindings = {"synthetic_test_only": True, "code_sha": file_sha(Path(__file__))}
        self.fingerprint = digest(self.bindings)

    def inspect(self, image):
        # A pixel-derived test payload. This is not a VALORANT recognizer.
        return {"signals": ["active", "owner_hud"],
                "raw": {"view_hp": {"display": str(int(image.mean()))}},
                "context": {}}
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([str(tmp_path), str(root), str(root / "src")]))
    config = tmp_path / "config.json"
    write_private(config, {"synthetic_test_only": True})
    protocol = tmp_path / "protocol_PRIVATE.json"
    v.freeze_protocol(
        config=config,
        observer="synthetic_pixel_supplier:Reader",
        output=protocol,
        runtime_files=[module],
        repository=repository,
    )
    records = []
    for i in range(2):
        source = tmp_path / f"synthetic-{i}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x{(i + 1) * 0x333333:06x}:size=96x64:rate=10",
                "-t",
                "2.4",
                "-c:v",
                "libx264",
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        records.append(
            {
                "source_id": f"synthetic-{i}",
                "physical_match_id": f"synthetic-{i}",
                "path": str(source),
            }
        )
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a container")
    records.append({"source_id": "broken", "physical_match_id": "broken", "path": str(broken)})
    declaration = tmp_path / "declaration.json"
    write_private(
        declaration,
        {
            "purpose": "frozen_timeline_comparison",
            "content_kind": "SYNTHETIC_TEST",
            "declarations": {
                "permission": True,
                "unused_for_development": True,
                "distinct_physical_matches": True,
                "unedited_full_matches": True,
            },
            "records": records,
        },
    )
    registry = tmp_path / "private"
    manifest = v.enroll_sources(
        declaration=declaration,
        protocol=protocol,
        registry=registry,
        batch_id="synthetic",
        prior_registries=[],
    )
    assert [r["status"] for r in manifest["records"]] == ["accepted", "accepted", "rejected"]
    output = tmp_path / "comparison"
    # Exercise the actual public module entry point and its fresh worker processes.
    proc = subprocess.run(
        [
            os.sys.executable,
            "-m",
            "valorant_ai_coach.temporal.validation",
            "run",
            "--protocol",
            str(protocol),
            "--batch",
            str(registry / "synthetic"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    report = read_json(output / "comparison_PRIVATE.json")
    assert [r["processing"] for r in report["results"]] == [
        "COMPLETE_WITH_INFORMATION",
        "COMPLETE_WITH_INFORMATION",
        "REGISTRATION_REJECTED",
    ]
    assert report["real_first_attempt_matches"] == 0
    assert report["successful_informative_first_matches"] == 0
    assert all(
        r["one_second_rows"] == 3 and r["observed_seconds"] == 3 and r["evaluation_handoff"]
        for r in report["results"][:2]
    )
    # Deliberately damage an accepted managed copy. Retain its failure and process
    # the other source, without ever claiming the repeat was an unseen attempt.
    damaged = Path(manifest["records"][0]["managed_path"])
    damaged.chmod(0o600)
    damaged.write_bytes(b"changed after registration")
    repeated = v.run_enrollment(protocol, registry / "synthetic", tmp_path / "repeat")
    assert [r["processing"] for r in repeated["results"]] == [
        "FAILED",
        "COMPLETE_WITH_INFORMATION",
        "REGISTRATION_REJECTED",
    ]
    assert repeated["results"][0]["last_observed_native_PTS"] is None
    assert not any(r["first_attempt"] for r in repeated["results"])
    assert (tmp_path / "repeat/matches_PRIVATE.csv").is_file()
