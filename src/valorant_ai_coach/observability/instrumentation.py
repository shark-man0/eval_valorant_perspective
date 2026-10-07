from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from .profiling import PerformanceRecorder


@dataclass(slots=True)
class InstrumentationSession:
    recorder: PerformanceRecorder
    _restore: list[tuple[object, str, Any]] = field(default_factory=list)

    def _wrap(
        self,
        target: object,
        method_name: str,
        phase_name: str,
        *,
        round_from_first_arg: bool = False,
    ) -> None:
        original = getattr(target, method_name, None)
        if not callable(original):
            return

        def timed(*args: Any, **kwargs: Any) -> Any:
            round_no: int | str | None = None
            if round_from_first_arg and args and isinstance(args[0], dict):
                raw_round = args[0].get("round_no")
                if isinstance(raw_round, (int, str)):
                    round_no = raw_round
            with self.recorder.phase(phase_name, round_no=round_no):
                return original(*args, **kwargs)

        try:
            setattr(target, method_name, timed)
        except (AttributeError, TypeError):
            return
        self._restore.append((target, method_name, original))

    def install_pipeline(self, pipeline: object) -> None:
        video = getattr(pipeline, "video", None)
        if video is not None:
            self._wrap(video, "probe", "video_probe")
            self._wrap(video, "extract_frames", "frame_extraction")

        hud_processor = getattr(pipeline, "hud_video_processor", None)
        if hud_processor is not None:
            self._wrap(hud_processor, "process", "hud_observation_processing")

        round_analyzer = getattr(pipeline, "round_analyzer", None)
        if round_analyzer is not None:
            self._wrap(
                round_analyzer,
                "analyze",
                "round_analysis",
                round_from_first_arg=True,
            )
            rule_engine = getattr(round_analyzer, "rule_engine", None)
            if rule_engine is not None:
                self._wrap(rule_engine, "evaluate", "rule_coach_processing")
            coach = getattr(round_analyzer, "coach", None)
            if coach is not None:
                self._wrap(coach, "evaluate", "rule_coach_processing")

        clips = getattr(pipeline, "clips", None)
        if clips is not None:
            self._wrap(clips, "create_clip", "clip_generation")

        repository = getattr(pipeline, "repository", None)
        if repository is not None:
            for name in (
                "create_match",
                "update_match_status",
                "reset_match_analysis",
                "save_job_checkpoint",
                "save_round_package",
                "save_analysis_result",
                "save_clip",
            ):
                self._wrap(repository, name, "persistence_report_generation")

        self._wrap(pipeline, "_write_analysis_json", "persistence_report_generation")

    def close(self) -> None:
        for target, method_name, original in reversed(self._restore):
            with suppress(AttributeError, TypeError):
                setattr(target, method_name, original)
        self._restore.clear()

    def __enter__(self) -> InstrumentationSession:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


def instrument_pipeline(pipeline: object, recorder: PerformanceRecorder) -> InstrumentationSession:
    session = InstrumentationSession(recorder)
    session.install_pipeline(pipeline)
    return session
