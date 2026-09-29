from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.video.sampling import HudFrameSampler, SampleRequest
from valorant_ai_coach.visual import VisualAnalyzer
from valorant_ai_coach.visual.analyzer import WorldViewGate
from valorant_ai_coach.visual.fusion import EvidenceFusion
from valorant_ai_coach.visual.sampling import micro_requests


class HudVideoProcessingError(RuntimeError):
    pass


class FrameObservationAnalyzer(Protocol):
    def observe_frames(
        self,
        frames: Sequence[FrameSample],
        *,
        video_metadata: VideoMetadata,
        cancel_event: Event | None = None,
    ) -> Any: ...


class FrameExtractor(Protocol):
    def extract_frames(
        self,
        path: Path,
        timestamps_sec: Sequence[float],
        output_dir: Path,
        *,
        max_frames: int = 600,
        jpeg_quality: int = 92,
        max_dimension: int | None = 1600,
        metadata: VideoMetadata | None = None,
        cancel_event: Event | None = None,
    ) -> list[FrameSample]: ...


@dataclass(frozen=True, slots=True)
class HudVideoProcessingResult:
    round_packages: tuple[dict[str, Any], ...]
    observations: tuple[dict[str, Any], ...]
    hud_events: tuple[dict[str, Any], ...]
    visual_events: tuple[dict[str, Any], ...]
    diagnostics: tuple[str, ...]
    sampled_frame_count: int
    evidence_frames: tuple[FrameSample, ...] = ()
    visual_observations: tuple[dict[str, Any], ...] = ()
    visual_candidates: tuple[dict[str, Any], ...] = ()
    zone_resolutions: tuple[dict[str, Any], ...] = ()


class HudVideoProcessor:
    """Run native-resolution two-pass HUD analysis before AI evidence planning."""

    def __init__(
        self,
        *,
        video: FrameExtractor,
        analyzer: FrameObservationAnalyzer,
        visual_analyzer: VisualAnalyzer,
        package_builder: RoundPackageBuilder,
        validator: SchemaValidator,
        sampler: HudFrameSampler | None = None,
    ) -> None:
        self.video = video
        self.analyzer = analyzer
        self.visual_analyzer = visual_analyzer
        self.package_builder = package_builder
        self.event_contract = getattr(
            package_builder, "contract", None
        ) or EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
        self.validator = validator
        self.sampler = sampler or HudFrameSampler(
            change_fps=float(getattr(visual_analyzer, "trigger_fps", 4.0)),
            max_pass_a_frames=12_000,
            max_pass_b_frames=6_000,
        )

    def process(
        self,
        *,
        metadata: VideoMetadata,
        match_id: str,
        output_dir: Path,
        cancel_event: Event | None = None,
        progress_cb: Callable[[float, str], None] | None = None,
    ) -> HudVideoProcessingResult:
        progress = progress_cb or (lambda _value, _message: None)
        visual_cancel = getattr(self.visual_analyzer, "set_cancel_event", None)
        if callable(visual_cancel):
            visual_cancel(cancel_event)
        self._check_cancel(cancel_event)
        progress(0.0, "HUD Pass Aのフレームを抽出しています")
        pass_a_requests: list[SampleRequest] = []
        pass_a_frames: list[FrameSample] = []
        for index, requests in enumerate(self.sampler.pass_a_batches(metadata.duration_sec)):
            self._check_cancel(cancel_event)
            pass_a_requests.extend(requests)
            pass_a_frames.extend(
                self.sampler.extract_in_batches(
                    self.video.extract_frames,
                    path=metadata.path,
                    requests=requests,
                    output_dir=Path(output_dir) / "pass-a" / f"segment-{index:04d}",
                    metadata=metadata,
                    cancel_event=cancel_event,
                )
            )
            progress(
                0.35 * requests[-1].time_sec / metadata.duration_sec,
                "HUD Pass Aのフレームを抽出しています",
            )
        if not pass_a_frames:
            raise HudVideoProcessingError("HUD Pass Aでフレームを抽出できませんでした")
        progress(0.35, "HUD Pass Aを解析しています")
        pass_a = self.analyzer.observe_frames(
            pass_a_frames, video_metadata=metadata, cancel_event=cancel_event
        )
        self._check_cancel(cancel_event)
        self._raise_if_calibration_required(pass_a)
        observations_a = self._observations(pass_a)
        self._validate_observations(observations_a)

        requested_changes = tuple(getattr(pass_a, "change_times_sec", ()))
        change_times = requested_changes or self.sampler.change_times(observations_a)
        triggers = getattr(self.visual_analyzer, "trigger_windows", None)
        micro: tuple[SampleRequest, ...] = ()
        if callable(triggers):
            progress(0.45, "Visual Pass Bのammo・recoil候補を走査しています")
            micro = micro_requests(
                metadata.duration_sec,
                triggers(pass_a_frames, observations_a, video_metadata=metadata),
            )
        pass_b_requests = self._only_new_requests(
            self.sampler.merge(self.sampler.pass_b(metadata.duration_sec, change_times), micro),
            pass_a_requests,
        )
        pass_b_frames: list[FrameSample] = []
        if pass_b_requests:
            progress(0.5, "HUD変化点を高密度で再抽出しています")
            pass_b_frames = self.sampler.extract_in_batches(
                self.video.extract_frames,
                path=metadata.path,
                requests=pass_b_requests,
                output_dir=Path(output_dir) / "pass-b",
                metadata=metadata,
                cancel_event=cancel_event,
            )
        combined = self._deduplicate_frames(pass_a_frames + pass_b_frames)
        progress(0.72, "HUD時系列とイベントを確定しています")
        final = self.analyzer.observe_frames(
            combined, video_metadata=metadata, cancel_event=cancel_event
        )
        self._check_cancel(cancel_event)
        self._raise_if_calibration_required(final)
        observations = self._observations(final)
        self._validate_observations(observations)
        hud_events = tuple(dict(item) for item in getattr(final, "hud_events", ()))

        begin_match = getattr(self.visual_analyzer, "begin_match", None)
        if callable(begin_match):
            begin_match(match_id, hud_events)

        visual = self.visual_analyzer.analyze(
            combined,
            observations,
            video_metadata=metadata,
        )
        self._check_cancel(cancel_event)
        visual_events = tuple(
            dict(item)
            for item in visual.events
            if WorldViewGate.allows_event(dict(item), observations)
        )
        dropped_visual = len(visual.events) - len(visual_events)
        hud_events, visual_events, fusion_notes = EvidenceFusion(self.event_contract).events(
            hud_events, visual_events
        )
        visual_confidences = dict(visual.frame_confidences)
        for observation in observations:
            if WorldViewGate.is_trustworthy(observation):
                confidence = visual_confidences.get(float(observation["time_sec"]), 0.0)
                observation["quality"]["visual_confidence"] = confidence
        self._validate_observations(observations)
        packages = self.package_builder.build(
            match_id=match_id,
            video_metadata=metadata,
            hud_observations=observations,
            hud_events=hud_events,
            visual_events=visual_events,
            visual_observations=visual.observations,
            zone_resolutions=visual.zone_resolutions,
            map_name=getattr(self.visual_analyzer, "map_name", "unknown"),
        )
        diagnostics = (
            tuple(getattr(final, "diagnostics", ())) + tuple(visual.diagnostics) + fusion_notes
        )
        if dropped_visual:
            diagnostics += (
                f"無効なworld-view区間のVisualイベントを{dropped_visual}件抑制しました",
            )
        event_times = {float(item["time_sec"]) for item in (*hud_events, *visual_events)}
        event_times.update(
            float(proof["time_sec"])
            for candidate in visual.candidates
            if candidate["confidence"] >= 0.7
            for proof in candidate["evidence"]
        )
        evidence_by_path = {
            frame.path: frame
            for timestamp in event_times
            for frame in [min(combined, key=lambda value: abs(value.time_sec - timestamp))]
        }
        progress(1.0, "Round Packageを生成しました")
        return HudVideoProcessingResult(
            packages,
            tuple(observations),
            hud_events,
            visual_events,
            diagnostics,
            len(combined),
            tuple(sorted(evidence_by_path.values(), key=lambda frame: frame.time_sec)),
            visual.observations,
            visual.candidates,
            visual.zone_resolutions,
        )

    @staticmethod
    def _check_cancel(cancel_event: Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("HUD解析がキャンセルされました")

    def _validate_observations(self, observations: Sequence[dict[str, Any]]) -> None:
        if not observations:
            raise HudVideoProcessingError("HUD Observationが生成されませんでした")
        previous = -1.0
        for observation in observations:
            self.validator.validate_hud_observation(observation)
            timestamp = float(observation["time_sec"])
            if timestamp < previous:
                raise HudVideoProcessingError("HUD Observationの時刻が昇順ではありません")
            previous = timestamp

    @staticmethod
    def _observations(result: Any) -> list[dict[str, Any]]:
        return [dict(item) for item in getattr(result, "observations", ())]

    @staticmethod
    def _raise_if_calibration_required(result: Any) -> None:
        calibration = getattr(result, "calibration", None)
        if isinstance(calibration, dict):
            required = bool(calibration.get("calibration_required", False))
            reasons = calibration.get("reasons", ())
        else:
            required = bool(getattr(calibration, "calibration_required", False))
            reasons = getattr(calibration, "reasons", ())
        if required:
            detail = "、".join(str(item) for item in reasons) or "HUDアンカー不一致"
            raise HudVideoProcessingError(f"HUD calibration_required: {detail}")

    @staticmethod
    def _only_new_requests(
        candidates: Sequence[SampleRequest], existing: Sequence[SampleRequest]
    ) -> tuple[SampleRequest, ...]:
        existing_times = {round(item.time_sec, 6) for item in existing}
        return tuple(item for item in candidates if round(item.time_sec, 6) not in existing_times)

    @staticmethod
    def _deduplicate_frames(frames: Sequence[FrameSample]) -> list[FrameSample]:
        by_time: dict[float, FrameSample] = {}
        for frame in frames:
            by_time[round(float(frame.time_sec), 6)] = frame
        return [by_time[key] for key in sorted(by_time)]
