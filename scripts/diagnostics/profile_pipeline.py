from __future__ import annotations

import argparse
import logging
import uuid
from pathlib import Path

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.logging_setup import configure_logging
from valorant_ai_coach.observability import (
    PerformanceRecorder,
    bind_context,
    classify_exception,
    instrument_pipeline,
    write_dependency_snapshot,
)
from valorant_ai_coach.observability.instrumentation import InstrumentationSession
from valorant_ai_coach.settings import SettingsStore, default_data_dir

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Profile one normal pipeline run without changing analyzer policy."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--match-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/diagnostics"))
    args = parser.parse_args()
    if args.resume and args.match_id is None:
        parser.error("--resume requires --match-id")

    run_id = f"D-{uuid.uuid4().hex}"
    match_id = args.match_id or f"M-{uuid.uuid4().hex}"
    run_dir = args.output_dir / run_id
    recorder = PerformanceRecorder(run_id, repository_root=ROOT)
    session: InstrumentationSession | None = None
    failure_category: str | None = None
    status = "failed"
    exit_code = 1
    try:
        with recorder.phase("bootstrap"):
            store = SettingsStore(default_data_dir() / "settings.json")
            settings = store.load()
            configure_logging(
                settings.data_dir / "logs",
                level=logging.DEBUG if settings.debug_logging else logging.INFO,
            )
            services = build_services(store, settings=settings)
            recorder.set_tool_executables(
                ffmpeg=str(getattr(services.pipeline.clips, "ffmpeg_path", "ffmpeg")),
                ffprobe=str(getattr(services.video, "ffprobe_path", "ffprobe")),
            )
        session = instrument_pipeline(services.pipeline, recorder)
        with bind_context(run_id=run_id, match_id=match_id):
            with recorder.phase("total"):
                result = services.pipeline.analyze_video(
                    args.video,
                    match_id=match_id,
                    resume=args.resume,
                )
            status = result.status
            exit_code = 0 if status in {"completed", "partial"} else 1
    except KeyboardInterrupt as exc:
        failure_category = classify_exception(exc)
        LOGGER.exception("Profiled pipeline run cancelled category=%s", failure_category)
    except Exception as exc:
        failure_category = classify_exception(exc)
        LOGGER.exception("Profiled pipeline run failed category=%s", failure_category)
    finally:
        if session is not None:
            session.close()
        recorder.finish(status, failure_category=failure_category)
        recorder.write_json(run_dir / "performance.json")
        write_dependency_snapshot(
            run_dir / "dependency_snapshot.json",
            repository_root=ROOT,
            include_pip_check=False,
            ffmpeg_executable=recorder.ffmpeg_executable,
            ffprobe_executable=recorder.ffprobe_executable,
        )
    print(run_dir)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
