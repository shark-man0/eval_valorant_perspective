from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from valorant_ai_coach.diagnostics.runtime_timing import timing_stage
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification
from valorant_ai_coach.hud.native_assured_start import current_assured_qualification
from valorant_ai_coach.hud.native_event_merge import (
    merge_native_boundaries,
    merge_native_timer_displays,
    native_source_breaks,
    validate_sampled_source_images,
    validated_native_boundaries,
)
from valorant_ai_coach.hud.native_lifecycle import NativeLifecycleAnalysis
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.video.native import NativeSourceFrame
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
class NativeLifecycleOptions:
    """Explicit whole-source processing with a mandatory PNG storage ceiling."""

    max_png_bytes: int
    png_prediction: str = "up"
    unedited_input_contract_path: Path | None = None

    def __post_init__(self) -> None:
        if type(self.max_png_bytes) is not int or self.max_png_bytes <= 0:
            raise ValueError("native PNG budget must be a positive integer")
        if self.png_prediction not in {"none", "up"}:
            raise ValueError("unsupported native PNG prediction")


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
    calibration_diagnostics: dict[str, Any] = field(default_factory=dict)


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
        require_detected_rounds: bool = True,
        native_lifecycle: NativeLifecycleAnalysis | None = None,
        native_lifecycle_options: NativeLifecycleOptions | None = None,
    ) -> HudVideoProcessingResult:
        if native_lifecycle_options is not None:
            if native_lifecycle is not None:
                raise HudVideoProcessingError("choose native result or native collection")
            native_lifecycle = self.collect_native_lifecycle(
                metadata, native_lifecycle_options, cancel_event=cancel_event,
            )
        initial_native_events = (
            self._native_boundaries(metadata, native_lifecycle) if native_lifecycle else ()
        )
        source_breaks = native_source_breaks(native_lifecycle) if native_lifecycle else ()
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
            pass_a_frames, video_metadata=metadata, cancel_event=cancel_event,
            **self._hud_break_inputs(pass_a_frames, source_breaks),
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
            with timing_stage("visual_trigger_scan"):
                trigger_windows = triggers(
                    pass_a_frames, observations_a, video_metadata=metadata,
                    **({'continuity_breaks': source_breaks} if source_breaks else {}),
                )
                micro = micro_requests(metadata.duration_sec, trigger_windows)
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
        result = self._process_frames(
            metadata=metadata,
            match_id=match_id,
            frames=combined,
            cancel_event=cancel_event,
            progress=progress,
            require_detected_rounds=require_detected_rounds,
            native_lifecycle=native_lifecycle,
        )
        if native_lifecycle is not None and (
            self._native_boundaries(metadata, native_lifecycle) != initial_native_events
            or native_source_breaks(native_lifecycle) != source_breaks
        ):
            raise HudVideoProcessingError('native inputs changed after Pass A preflight')
        return result

    def process_frames(
        self,
        metadata: VideoMetadata,
        match_id: str,
        frames: Sequence[FrameSample],
        cancel_event: Event | None = None,
        progress_cb: Callable[[float, str], None] | None = None,
        require_detected_rounds: bool = True,
        native_lifecycle: NativeLifecycleAnalysis | None = None,
    ) -> HudVideoProcessingResult:
        """Run the production final-processing stages over an exact ordered frame set."""
        self._validate_fixed_frames(frames)
        progress = progress_cb or (lambda _value, _message: None)
        visual_cancel = getattr(self.visual_analyzer, "set_cancel_event", None)
        if callable(visual_cancel):
            visual_cancel(cancel_event)
        return self._process_frames(
            metadata=metadata,
            match_id=match_id,
            frames=frames,
            cancel_event=cancel_event,
            progress=progress,
            require_detected_rounds=require_detected_rounds,
            native_lifecycle=native_lifecycle,
        )

    def _process_frames(
        self,
        *,
        metadata: VideoMetadata,
        match_id: str,
        frames: Sequence[FrameSample],
        cancel_event: Event | None,
        progress: Callable[[float, str], None],
        require_detected_rounds: bool = True,
        native_lifecycle: NativeLifecycleAnalysis | None = None,
    ) -> HudVideoProcessingResult:
        combined = list(frames)
        native_events = (
            self._native_boundaries(metadata, native_lifecycle)
            if native_lifecycle is not None else ()
        )
        source_breaks = native_source_breaks(native_lifecycle) if native_lifecycle else ()
        self._check_cancel(cancel_event)
        progress(0.72, "HUD時系列とイベントを確定しています")
        final = self.analyzer.observe_frames(
            combined, video_metadata=metadata, cancel_event=cancel_event,
            **self._hud_break_inputs(combined, source_breaks),
        )
        self._check_cancel(cancel_event)
        self._raise_if_calibration_required(final)
        observations = self._observations(final)
        self._validate_observations(observations)
        hud_events = tuple(dict(item) for item in getattr(final, "hud_events", ()))
        if native_lifecycle is not None:
            hud_events = merge_native_boundaries(hud_events, native_events)
            observations = merge_native_timer_displays(
                observations, native_lifecycle, frames=combined,
            )

        begin_match = getattr(self.visual_analyzer, "begin_match", None)
        if callable(begin_match):
            begin_match(match_id, hud_events)

        with timing_stage("visual_analysis"):
            visual = self.visual_analyzer.analyze(
                combined,
                observations,
                video_metadata=metadata,
                **({'continuity_breaks': source_breaks} if source_breaks else {}),
            )
        self._check_cancel(cancel_event)
        visual_events = tuple(
            dict(item)
            for item in visual.events
            if WorldViewGate.allows_event(dict(item), observations)
        )
        dropped_visual = len(visual.events) - len(visual_events)
        with timing_stage("event_fusion"):
            hud_events, visual_events, fusion_notes = EvidenceFusion(self.event_contract).events(
                hud_events, visual_events
            )
        visual_confidences = dict(visual.frame_confidences)
        for observation in observations:
            if WorldViewGate.is_trustworthy(observation):
                confidence = visual_confidences.get(float(observation["time_sec"]), 0.0)
                observation["quality"]["visual_confidence"] = confidence
        self._validate_observations(observations)
        with timing_stage("round_package_build"):
            packages = self.package_builder.build(
                match_id=match_id,
                video_metadata=metadata,
                hud_observations=observations,
                hud_events=hud_events,
                visual_events=visual_events,
                visual_observations=visual.observations,
                zone_resolutions=visual.zone_resolutions,
                map_name=getattr(self.visual_analyzer, "map_name", "unknown"),
                require_detected_rounds=require_detected_rounds,
                continuity_breaks=source_breaks,
            )
        diagnostics = (
            tuple(getattr(final, "diagnostics", ())) + tuple(visual.diagnostics) + fusion_notes
        )
        if not packages:
            diagnostics += ("round_packages_unavailable: no reliable round boundaries",)
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
        progress(1.0, "Round Packageを生成しました" if packages
                 else "観測解析が完了しました（信頼できるラウンド区間なし）")
        # Source/report/profile changes invalidate even constructed packages.
        if native_lifecycle is not None:
            validate_sampled_source_images(combined)
        if (
            native_lifecycle is not None
            and (self._native_boundaries(metadata, native_lifecycle) != native_events
                 or native_source_breaks(native_lifecycle) != source_breaks)
        ):
            raise HudVideoProcessingError('native boundary inputs changed during processing')
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
            getattr(final, "calibration_diagnostics", {}),
        )

    def collect_native_lifecycle(
        self, metadata: VideoMetadata, options: NativeLifecycleOptions,
        *, cancel_event: Event | None = None,
    ) -> NativeLifecycleAnalysis:
        """Collect one complete source epoch; reject before sampling on failure."""
        self._check_cancel(cancel_event)
        contract = None
        if options.unedited_input_contract_path is None:
            qualification = self._current_native_qualification()
            binding = getattr(self.analyzer, "scene_source_binding", None)
            verify = getattr(binding, "verify", None)
            observe = getattr(self.analyzer, "observe_qualified_native_lifecycle_frames", None)
            if (not {"scene_continuity", "ui_transition"} <= qualification.components
                    or not callable(verify) or not callable(observe)):
                raise HudVideoProcessingError("paired qualified native producer required")
            verify()
        digest = hashlib.sha256()
        with metadata.path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if options.unedited_input_contract_path is not None:
            contract_path = options.unedited_input_contract_path
            contract = UneditedInputContract.load(
                contract_path, source_video_sha256=digest.hexdigest(),
            )
            qualification = current_assured_qualification(self.analyzer, contract)
            observe = getattr(self.analyzer, "observe_qualified_unedited_native_start_frames", None)
            if not callable(observe):
                raise HudVideoProcessingError("qualified assured native producer required")

            def verify() -> None:
                if (UneditedInputContract.load(contract_path,
                                              source_video_sha256=digest.hexdigest()) != contract
                        or current_assured_qualification(self.analyzer, contract) != qualification):
                    raise HudVideoProcessingError("native assured inputs changed")

        if not callable(verify) or not callable(observe):
            raise HudVideoProcessingError("qualified native provider required")
        decode = getattr(self.video, "native_window", None)
        if not callable(decode):
            raise HudVideoProcessingError("verified native decoder required")
        with ExitStack() as stack:
            with timing_stage("native_frame_decode"):
                frames = stack.enter_context(decode(
                    metadata.path, start_sec=0, end_sec=None,
                    source_video_sha256=digest.hexdigest(),
                    max_png_bytes=options.max_png_bytes,
                    png_prediction=options.png_prediction,
                ))
            self._check_cancel(cancel_event)
            if len(frames) < 2:
                raise HudVideoProcessingError("native source requires continuous frames")
            if any(not isinstance(frame, NativeSourceFrame) for frame in frames):
                raise HudVideoProcessingError("verified native source frames required")
            step = frames[1].pts_ticks - frames[0].pts_ticks
            if step <= 0 or any(
                frame.width != metadata.width or frame.height != metadata.height
                or frame.time_base != frames[0].time_base
                or frame.source_epoch != frames[0].source_epoch
                or frame.source_video_sha256 != digest.hexdigest()
                or (index and frame.pts_ticks - frames[index - 1].pts_ticks != step)
                for index, frame in enumerate(frames)
            ):
                raise HudVideoProcessingError("native source metadata/cadence mismatch")
            with timing_stage("native_lifecycle"):
                arguments = ({"input_contract_path": options.unedited_input_contract_path}
                             if contract is not None else {})
                analysis = observe(
                    frames, native_step_ticks=step, video_metadata=metadata, **arguments,
                )
            self._check_cancel(cancel_event)
            if not isinstance(analysis, NativeLifecycleAnalysis):
                raise HudVideoProcessingError("native lifecycle result required")
            if len(analysis.source_rows) != len(frames):
                raise HudVideoProcessingError("native producer coverage mismatch")
            for frame, row in zip(frames, analysis.source_rows, strict=True):
                expected = {
                    "source_video_sha256": frame.source_video_sha256,
                    "source_epoch": frame.source_epoch,
                    "source_pts_ticks": frame.pts_ticks,
                    "source_time_base": str(frame.time_base),
                    "source_pts_sec": frame.time_sec,
                    "source_pixel_sha256": frame.pixel_sha256,
                }
                if any(row.get(key) != value for key, value in expected.items()):
                    raise HudVideoProcessingError("native producer source binding mismatch")
                frame.read_image()
            verify()
        # Decoder exit performs terminal source verification before publication.
        self._check_cancel(cancel_event)
        self._native_boundaries(metadata, analysis)
        return analysis

    def _current_native_qualification(self) -> GlobalLifecycleQualification:
        base_fingerprint = getattr(self.analyzer, '_base_fingerprint', None)
        path = getattr(self.analyzer, 'global_qualification_path', None)
        loaded = getattr(self.analyzer, 'global_qualification', None)
        if not callable(base_fingerprint) or path is None or loaded is None:
            raise HudVideoProcessingError('qualified native analyzer required')
        base = base_fingerprint()
        if base != getattr(self.analyzer, '_native_loaded_base_fingerprint', base):
            raise HudVideoProcessingError('native analyzer profile changed; reload analyzer')
        qualification = GlobalLifecycleQualification.load(Path(path), base)
        if qualification != loaded:
            raise HudVideoProcessingError('native qualification changed; reload analyzer')
        return qualification

    def _native_boundaries(
        self, metadata: VideoMetadata, analysis: NativeLifecycleAnalysis,
    ) -> tuple[dict[str, Any], ...]:
        qualification = (self._current_native_qualification()
                         if analysis.unedited_input_contract is None else
                         current_assured_qualification(
                             self.analyzer, analysis.unedited_input_contract,
                         ))
        digest = hashlib.sha256()
        with metadata.path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        cuts = native_source_breaks(analysis)
        if cuts and not all(
            getattr(consumer, 'supports_native_source_breaks', False) is True
            for consumer in (self.analyzer, self.visual_analyzer, self.package_builder)
        ):
            raise HudVideoProcessingError('native source breaks require compatible consumers')
        return validated_native_boundaries(
            analysis, qualification, digest.hexdigest(),
            continuity_breaks=cuts if cuts else None,
        )

    @staticmethod
    def _hud_break_inputs(
        frames: Sequence[FrameSample], cuts: Sequence[float],
    ) -> dict[str, Any]:
        if not cuts:
            return {}
        signals: list[dict[str, Any]] = [{} for _ in frames]
        ordered = sorted(enumerate(frames), key=lambda item: item[1].time_sec)
        for cut in cuts:
            following = next((index for index, frame in ordered if frame.time_sec >= cut), None)
            if following is not None:
                signals[following]['discontinuity'] = True
        return {'additional_signals': signals}

    @staticmethod
    def _validate_fixed_frames(frames: Sequence[FrameSample]) -> None:
        if not frames:
            raise HudVideoProcessingError("fixed frame set must not be empty")
        previous = -math.inf
        for frame in frames:
            timestamp = float(frame.time_sec)
            if not math.isfinite(timestamp):
                raise HudVideoProcessingError("fixed frame timestamps must be finite")
            if timestamp == previous:
                raise HudVideoProcessingError("fixed frame timestamps must be unique")
            if timestamp < previous:
                raise HudVideoProcessingError("fixed frames must be in ascending time order")
            previous = timestamp

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
