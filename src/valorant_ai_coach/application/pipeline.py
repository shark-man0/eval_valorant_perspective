from __future__ import annotations

import hashlib
import inspect
import json
import logging
import shutil
import uuid
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event as ThreadEvent
from typing import Any, Protocol

from valorant_ai_coach.clips import ClipArtifact, ClipGenerationError
from valorant_ai_coach.hud import HudAnalyzer, HudObservations
from valorant_ai_coach.rules import EvaluationAggregator
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.video import FrameSample, VideoMetadata

from .frame_planner import FramePlanner, PlannedFrame
from .hud_video_processor import HudVideoProcessingResult, HudVideoProcessor, NativeLifecycleOptions
from .round_analyzer import RoundAnalysis, RoundAnalyzer

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[float, str], None]


class AnalysisCancelled(InterruptedError):
    pass


class VideoReader(Protocol):
    def probe(self, path: Path, *, cancel_event: ThreadEvent | None = None) -> VideoMetadata: ...

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
        cancel_event: ThreadEvent | None = None,
    ) -> list[FrameSample]: ...


class ClipWriter(Protocol):
    def create_clip(
        self,
        video_path: Path,
        start_sec: float,
        end_sec: float,
        source_duration_sec: float | None = None,
        clip_id: str | None = None,
        *,
        cancel_event: ThreadEvent | None = None,
    ) -> ClipArtifact: ...


@dataclass(frozen=True, slots=True)
class MatchAnalysisResult:
    match_id: str
    status: str
    rounds: tuple[RoundAnalysis, ...]
    clips: tuple[ClipArtifact, ...]
    errors: tuple[str, ...]
    analysis_json: Path


class MatchAnalysisPipeline:
    """Run the production-shaped VOD pipeline one Round Package at a time."""

    def __init__(
        self,
        *,
        data_dir: Path,
        repository: SQLiteRepository,
        video: VideoReader,
        clips: ClipWriter,
        hud: HudAnalyzer,
        round_analyzer: RoundAnalyzer,
        frame_planner: FramePlanner,
        aggregator: EvaluationAggregator,
        validator: SchemaValidator,
        delete_temp_frames: bool = True,
        hud_video_processor: HudVideoProcessor | None = None,
        round_boundary_mode: str = "strict",
        native_lifecycle_options: NativeLifecycleOptions | None = None,
    ) -> None:
        if round_boundary_mode not in {"strict", "practical"}:
            raise ValueError("unsupported boundary mode")
        if round_boundary_mode == "practical" and (
            hud_video_processor is None or native_lifecycle_options is None
            or native_lifecycle_options.unedited_input_contract_path is None
        ):
            raise ValueError(
                "Practical Mode requires a video processor and explicit input contract"
            )
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.repository = repository
        self.video = video
        self.clips = clips
        self.hud = hud
        self.round_analyzer = round_analyzer
        self.frame_planner = frame_planner
        self.aggregator = aggregator
        self.validator = validator
        self.delete_temp_frames = delete_temp_frames
        self.hud_video_processor = hud_video_processor
        self.round_boundary_mode = round_boundary_mode
        self.native_lifecycle_options = native_lifecycle_options

    def analyze_video(
        self,
        video_path: Path,
        progress_cb: ProgressCallback | None = None,
        cancel_event: ThreadEvent | None = None,
        *,
        match_id: str | None = None,
        resume: bool = False,
    ) -> MatchAnalysisResult:
        progress = progress_cb or (lambda _value, _message: None)
        cancel = cancel_event or ThreadEvent()
        identifier = match_id or f"M-{uuid.uuid4().hex}"
        if resume and match_id is None:
            raise ValueError("再開にはmatch_idが必要です")
        if not identifier.replace("-", "").replace("_", "").isalnum():
            raise ValueError("match_idには英数字・ハイフン・アンダースコアだけを使用できます")
        # Probe precedes durable match creation because its validated metadata is part
        # of the match record, but it must still be interruptible when the user closes
        # the application or cancels a newly selected video.
        try:
            metadata = self.video.probe(Path(video_path), cancel_event=cancel)
        except InterruptedError as exc:
            raise AnalysisCancelled("動画メタデータ取得がキャンセルされました") from exc
        source_fingerprint = self._source_fingerprint(metadata.path)
        config_fingerprint = self._config_fingerprint()
        completed: list[int] = []
        failed_rounds: list[int] = []
        round_diagnostics: dict[str, str] = {}
        expected_package_fingerprints: dict[str, str] = {}
        if resume:
            checkpoint_row = self.repository.get_job_checkpoint(identifier)
            match = self.repository.get_match(identifier)
            if match is None or checkpoint_row is None:
                raise KeyError(f"再開可能な解析ジョブがありません: {identifier}")
            checkpoint = checkpoint_row["checkpoint"]
            self._validate_resume_fingerprints(
                match,
                checkpoint,
                metadata.path,
                source_fingerprint,
                config_fingerprint,
            )
            completed = [int(value) for value in checkpoint.get("completed_rounds", [])]
            failed_rounds = [int(value) for value in checkpoint.get("failed_rounds", [])]
            round_diagnostics = {
                str(key): str(value)
                for key, value in checkpoint.get("round_diagnostics", {}).items()
            }
            expected_package_fingerprints = {
                str(key): str(value)
                for key, value in checkpoint.get("round_package_fingerprints", {}).items()
            }
            self.repository.update_match_status(identifier, "analyzing")
        else:
            self.repository.create_match(
                identifier,
                metadata.path,
                metadata={
                    **asdict(metadata),
                    "path": str(metadata.path),
                    "source_fingerprint": source_fingerprint,
                    "config_fingerprint": config_fingerprint,
                },
                status="analyzing",
            )
            self.repository.reset_match_analysis(identifier)
            self._clear_match_evidence(identifier)
        checkpoint_state: dict[str, Any] = {
            "source_fingerprint": source_fingerprint,
            "config_fingerprint": config_fingerprint,
            "completed_rounds": completed,
            "failed_rounds": failed_rounds,
            "round_diagnostics": round_diagnostics,
            "round_package_fingerprints": expected_package_fingerprints,
        }
        self.repository.save_job_checkpoint(identifier, "analyzing", checkpoint_state)
        progress(0.03, "動画メタデータを取得しました")
        errors: list[str] = []
        clip_errors: list[str] = []
        round_results: list[RoundAnalysis] = []
        clip_artifacts: list[ClipArtifact] = []
        temp_root = (self.data_dir / "temp" / identifier).resolve()
        try:
            self._check_cancel(cancel)
            observations: HudVideoProcessingResult | HudObservations
            if self.hud_video_processor is not None:
                lifecycle_arguments: dict[str, Any] = {}
                if self.round_boundary_mode == "practical":
                    lifecycle_arguments = {
                        "boundary_mode": "practical",
                        "native_lifecycle_options": self.native_lifecycle_options,
                    }
                observations = self.hud_video_processor.process(
                    metadata=metadata,
                    match_id=identifier,
                    output_dir=temp_root / "hud",
                    cancel_event=cancel,
                    progress_cb=lambda value, message: progress(0.03 + 0.22 * value, message),
                    **lifecycle_arguments,
                )
                self._persist_hud_report(identifier, observations)
            else:
                observations = self.hud.analyze([], video_metadata=metadata, match_id=identifier)
            packages = list(observations.round_packages)
            if not packages:
                raise RuntimeError("HUD解析からRound Packageが生成されませんでした")
            for diagnostic in observations.diagnostics:
                LOGGER.info("HUD diagnostic: %s", diagnostic)
            checkpoint_state["hud_diagnostics"] = list(dict.fromkeys(observations.diagnostics))[:64]
            if any(
                float(package["observation_quality"]["timeline_completeness"]) == 0
                for package in packages
            ):
                checkpoint_state["hud_diagnostics"].append(
                    "ラウンド全体を観測できていない区間があります。完全なラウンド文脈として扱いません"
                )
            round_numbers = [int(package["round_no"]) for package in packages]
            if len(round_numbers) != len(set(round_numbers)):
                raise RuntimeError("HUD解析結果のround_noが重複しています")
            if any(str(package.get("match_id")) != identifier for package in packages):
                raise RuntimeError("HUD解析結果のmatch_idが解析ジョブと一致しません")
            actual_package_fingerprints = {
                str(package["round_no"]): self._round_package_fingerprint(package)
                for package in packages
            }
            if (
                resume
                and expected_package_fingerprints
                and actual_package_fingerprints != expected_package_fingerprints
            ):
                raise RuntimeError(
                    "再開できません: Round Package入力が前回実行時から変更されています"
                )
            expected_package_fingerprints = actual_package_fingerprints
            checkpoint_state["round_package_fingerprints"] = expected_package_fingerprints
            self.repository.save_job_checkpoint(identifier, "analyzing", checkpoint_state)
            total = len(packages)
            round_progress_start = 0.25 if self.hud_video_processor else 0.08
            round_progress_span = 0.70 - round_progress_start
            for index, raw_package in enumerate(packages):
                self._check_cancel(cancel)
                round_no = int(raw_package["round_no"])
                if round_no in completed:
                    restored = self._restore_round(identifier, round_no)
                    if restored is not None:
                        round_results.append(restored)
                        progress(
                            round_progress_start + round_progress_span * (index + 1) / total,
                            f"区間 {round_no} の保存済み観測を復元しました（採点保留）"
                            if RoundAnalyzer.boundary_context_is_uncertain(restored.round_package)
                            else f"ラウンド {round_no} は保存済み結果を使用しました",
                        )
                        continue
                    completed.remove(round_no)
                round_temp = temp_root / f"round-{round_no:03d}"
                try:
                    package = self._attach_evidence_frames(
                        deepcopy(raw_package), metadata, round_temp, cancel
                    )
                    result = self.round_analyzer.analyze(package, cancel_event=cancel)
                    result = self._persist_round_evidence(result, identifier, round_no)
                    self.repository.save_round_package(result.round_package)
                    # Persist raw per-round output before advancing the checkpoint. This is the
                    # durable recovery source; match aggregation may replace it later.
                    self.repository.save_analysis_result(result.output)
                    round_results.append(result)
                    completed.append(round_no)
                    failed_rounds = [value for value in failed_rounds if value != round_no]
                    round_diagnostics.pop(str(round_no), None)
                    progress(
                        round_progress_start + round_progress_span * (index + 1) / total,
                        f"区間 {round_no} の観測を保存しました（境界未確定・採点保留）"
                        if RoundAnalyzer.boundary_context_is_uncertain(result.round_package)
                        else f"ラウンド {round_no} を評価しました",
                    )
                except AnalysisCancelled:
                    raise
                except InterruptedError as exc:
                    raise AnalysisCancelled("解析がキャンセルされました") from exc
                except Exception as exc:
                    LOGGER.exception("Round %s analysis failed", round_no)
                    if round_no not in failed_rounds:
                        failed_rounds.append(round_no)
                    round_diagnostics[str(round_no)] = f"{type(exc).__name__}: {exc}"
                    errors.append(f"round {round_no}: {exc}")
                    progress(
                        round_progress_start + round_progress_span * (index + 1) / total,
                        f"ラウンド {round_no} は失敗しました。後続ラウンドを継続します",
                    )
                finally:
                    checkpoint_state.update(
                        {
                            "completed_rounds": sorted(set(completed)),
                            "failed_rounds": sorted(set(failed_rounds)),
                            "round_diagnostics": round_diagnostics,
                            "current_round": round_no,
                        }
                    )
                    self.repository.save_job_checkpoint(identifier, "analyzing", checkpoint_state)
                    if self.delete_temp_frames:
                        self._safe_remove_tree(round_temp, temp_root)

            aggregated = self.aggregator.aggregate(
                [
                    {
                        **deepcopy(evaluation),
                        "_aggregation_scope": int(result.output["round_no"]),
                    }
                    for result in round_results
                    for evaluation in result.output["evaluations"]
                ]
            )
            by_round: dict[int, list[dict[str, Any]]] = {
                int(result.output["round_no"]): [] for result in round_results
            }
            for evaluation in aggregated:
                aggregation_scope = int(evaluation.pop("_aggregation_scope"))
                by_round[aggregation_scope].append(self._enforce_confidence_policy(evaluation))

            for result in round_results:
                round_no = int(result.output["round_no"])
                payload = {
                    "schema_version": "3.0",
                    "analysis_id": str(result.output["analysis_id"]),
                    "match_id": identifier,
                    "round_no": round_no,
                    "evaluations": by_round[round_no],
                }
                self.validator.validate_ai_output(
                    payload,
                    round_package=result.round_package,
                    candidate_rule_ids={candidate.rule_id for candidate in result.candidates},
                )
                self.repository.save_analysis_result(payload)

            checkpoint_state.update({"completed_rounds": sorted(set(completed))})
            self.repository.save_job_checkpoint(identifier, "generating_clips", checkpoint_state)
            reusable: dict[tuple[float, float], ClipArtifact] = {}
            scored = [
                item
                for evaluations in by_round.values()
                for item in evaluations
                if item["label"] in {"good", "improve"}
            ]
            for index, evaluation in enumerate(scored):
                self._check_cancel(cancel)
                interval = evaluation["display_clip"]
                assert interval is not None
                key = (round(float(interval["start_sec"]), 3), round(float(interval["end_sec"]), 3))
                try:
                    clip_id = str(evaluation["clip_id"])
                    self.repository.assert_clip_id_available(
                        clip_id, str(evaluation["evaluation_id"])
                    )
                    artifact = reusable.get(key) or self._stored_clip(clip_id, metadata.path)
                    if artifact is None:
                        artifact = self._create_clip(metadata, key, clip_id, cancel)
                        reusable[key] = artifact
                    stored_artifact = ClipArtifact(
                        clip_id=str(evaluation["clip_id"]),
                        path=artifact.path,
                        start_sec=artifact.start_sec,
                        end_sec=artifact.end_sec,
                        duration_sec=artifact.duration_sec,
                        source_path=artifact.source_path,
                    )
                    self.repository.save_clip(
                        stored_artifact.clip_id,
                        str(evaluation["evaluation_id"]),
                        stored_artifact.path,
                        stored_artifact.start_sec,
                        stored_artifact.end_sec,
                        stored_artifact.duration_sec,
                    )
                    clip_artifacts.append(stored_artifact)
                except InterruptedError as exc:
                    raise AnalysisCancelled("解析がキャンセルされました") from exc
                except (ClipGenerationError, OSError, ValueError) as exc:
                    LOGGER.exception("Clip generation failed for %s", evaluation["evaluation_id"])
                    diagnostic = f"{evaluation['evaluation_id']}: {exc}"
                    clip_errors.append(diagnostic)
                    errors.append(diagnostic)
                progress(
                    0.72 + 0.25 * (index + 1) / max(1, len(scored)),
                    "根拠クリップを生成しています",
                )

            status = "failed" if not round_results else "partial" if errors else "completed"
            self.repository.update_match_status(identifier, status)
            self.repository.save_job_checkpoint(
                identifier,
                status,
                {
                    **checkpoint_state,
                    "completed_rounds": sorted(set(completed)),
                    "failed_rounds": sorted(set(failed_rounds)),
                    "round_diagnostics": round_diagnostics,
                    "clip_errors": clip_errors,
                    "processing_errors": errors,
                },
            )
            analysis_json = self._write_analysis_json(identifier, errors, clip_errors)
            progress(
                1.0,
                "解析が完了しました"
                if not errors
                else "一部のラウンドまたはクリップで失敗しました",
            )
            return MatchAnalysisResult(
                identifier,
                status,
                tuple(round_results),
                tuple(clip_artifacts),
                tuple(errors),
                analysis_json,
            )
        except InterruptedError as exc:
            self.repository.update_match_status(identifier, "cancelled")
            self.repository.save_job_checkpoint(identifier, "cancelled", checkpoint_state)
            raise AnalysisCancelled("解析がキャンセルされました") from exc
        except Exception as exc:
            self.repository.update_match_status(identifier, "failed")
            self.repository.save_job_checkpoint(
                identifier, "failed", {**checkpoint_state, "error": str(exc)}
            )
            raise
        finally:
            # Full HUD sampling is transient, even when AI debug frames are kept.
            self._safe_remove_tree(temp_root / "hud", temp_root)
            if self.delete_temp_frames:
                self._safe_remove_tree(temp_root, self.data_dir / "temp")

    def resume_analysis(
        self,
        match_id: str,
        video_path: Path | None = None,
        progress_cb: ProgressCallback | None = None,
        cancel_event: ThreadEvent | None = None,
    ) -> MatchAnalysisResult:
        """Explicit public resume entry point with source/config fingerprint validation."""
        match = self.repository.get_match(match_id)
        if match is None:
            raise KeyError(f"再開可能なmatchがありません: {match_id}")
        source = Path(video_path or match["source_video_path"])
        return self.analyze_video(
            source,
            progress_cb=progress_cb,
            cancel_event=cancel_event,
            match_id=match_id,
            resume=True,
        )

    def delete_match(self, match_id: str) -> None:
        """Remove a completed/cancelled match and its private evidence safely."""

        identifier = str(match_id)
        if not identifier.replace("-", "").replace("_", "").isalnum():
            raise ValueError("match_idには英数字・ハイフン・アンダースコアだけを使用できます")
        # This is the logical commit (including FK cascade).  A locked frame or
        # analysis.json is only a post-commit cleanup diagnostic, never a reason to
        # resurrect a deleted database record.
        self.repository.delete_match(identifier)
        matches_root = (self.data_dir / "matches").resolve()
        self._safe_remove_tree(matches_root / identifier, matches_root)

    def _attach_evidence_frames(
        self,
        package: dict[str, Any],
        metadata: VideoMetadata,
        output_dir: Path,
        cancel_event: ThreadEvent,
    ) -> dict[str, Any]:
        if RoundAnalyzer.boundary_context_is_uncertain(package):
            package["frames"] = []
            return package
        prepared = self.round_analyzer.fact_builder.enrich(package)
        candidates = self.round_analyzer.selector.select(prepared)
        plan = self.frame_planner.plan(prepared, candidates)
        samples = self.video.extract_frames(
            metadata.path,
            [frame.time_sec for frame in plan],
            output_dir,
            max_frames=len(plan),
            jpeg_quality=88,
            max_dimension=1600,
            metadata=metadata,
            cancel_event=cancel_event,
        )
        package["frames"] = [
            {
                "time_sec": sample.time_sec,
                "path": str(sample.path),
                "purpose": self._nearest_purpose(sample.time_sec, plan),
            }
            for sample in samples
        ]
        return package

    def _persist_round_evidence(
        self, result: RoundAnalysis, match_id: str, round_no: int
    ) -> RoundAnalysis:
        """Stage, validate, then publish durable evidence without losing prior files."""

        package = deepcopy(result.round_package)
        match_root = (self.data_dir / "matches" / match_id).resolve()
        evidence_root = (match_root / "evidence").resolve()
        round_root = (evidence_root / f"round-{round_no:03d}").resolve()
        if not round_root.is_relative_to(evidence_root):
            raise ValueError("根拠フレーム保存先がmatchディレクトリ外です")
        evidence_root.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        staging_root = evidence_root / f".{round_root.name}.{token}.staging"
        backup_root = evidence_root / f".{round_root.name}.{token}.backup"
        staging_root.mkdir(parents=False, exist_ok=False)
        staged: list[dict[str, Any]] = []
        try:
            for index, frame in enumerate(package.get("frames", [])):
                source = Path(str(frame["path"])).expanduser().resolve()
                if not source.is_file() or source.stat().st_size <= 0:
                    raise FileNotFoundError(f"保存する根拠フレームがありません: {source}")
                suffix = source.suffix.lower()
                if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                    raise ValueError(f"未対応の根拠フレーム形式です: {suffix}")
                target = staging_root / (
                    f"frame-{index:03d}-{float(frame['time_sec']):010.3f}{suffix}"
                )
                temporary = staging_root / f".{target.name}.{uuid.uuid4().hex}.tmp"
                shutil.copy2(source, temporary)
                temporary.replace(target)
                staged.append({**frame, "path": str(target)})
            package["frames"] = staged
            self.validator.validate_round_package(package)
        except BaseException:
            self._safe_remove_tree(staging_root, evidence_root)
            raise
        had_previous = round_root.exists()
        try:
            if had_previous:
                round_root.replace(backup_root)
            try:
                staging_root.replace(round_root)
            except BaseException:
                # A failed publish must leave the prior evidence addressable by the
                # persisted round package.  Remove only the newly published tree, then
                # restore the old tree from its private backup.
                self._safe_remove_tree(round_root, evidence_root)
                if had_previous and backup_root.exists():
                    backup_root.replace(round_root)
                raise
        except BaseException:
            self._safe_remove_tree(staging_root, evidence_root)
            raise
        finally:
            # Superseded evidence is physical cleanup only.  A locked file on Windows
            # cannot invalidate the DB state or the newly published round.
            if backup_root.exists():
                self._safe_remove_tree(backup_root, evidence_root)
        package["frames"] = [
            {
                **frame,
                "path": str(round_root / Path(str(frame["path"])).name),
            }
            for frame in staged
        ]
        return RoundAnalysis(
            package,
            result.candidates,
            result.deterministic_decisions,
            result.output,
        )

    def _restore_round(self, match_id: str, round_no: int) -> RoundAnalysis | None:
        package = self.repository.get_round_package(match_id, round_no)
        if package is None:
            return None
        evidence_root = (self.data_dir / "matches" / match_id / "evidence").resolve()
        for frame in package.get("frames", []):
            path = Path(str(frame.get("path", ""))).expanduser().resolve()
            if not path.is_file() or not path.is_relative_to(evidence_root):
                LOGGER.warning("保存済み根拠フレームを復元できません: %s", path)
                return None
        try:
            self.validator.validate_round_package(package)
            if RoundAnalyzer.boundary_context_is_uncertain(package):
                if self.repository.list_round_evaluations(match_id, round_no):
                    LOGGER.warning("暫定境界の保存済み採点を再利用しません: %s", round_no)
                    return None
                output = {
                    "schema_version": "3.0", "analysis_id": f"RESTORED-{match_id}-R{round_no}",
                    "match_id": match_id, "round_no": round_no, "evaluations": [],
                }
                self.validator.validate_ai_output(output, round_package=package)
                return RoundAnalysis(package, (), {}, output, {})
            candidates = self.round_analyzer.selector.select(package)
            output = {
                "schema_version": "3.0",
                "analysis_id": f"RESTORED-{match_id}-R{round_no}",
                "match_id": match_id,
                "round_no": round_no,
                "evaluations": self.repository.list_round_evaluations(match_id, round_no),
            }
            self.validator.validate_ai_output(
                output,
                round_package=package,
                candidate_rule_ids={candidate.rule_id for candidate in candidates},
            )
        except Exception:
            LOGGER.exception("保存済みラウンドを復元できません: %s R%s", match_id, round_no)
            return None
        return RoundAnalysis(package, tuple(candidates), {}, output)

    def _create_clip(
        self,
        metadata: VideoMetadata,
        interval: tuple[float, float],
        clip_id: str,
        cancel_event: ThreadEvent,
    ) -> ClipArtifact:
        return self.clips.create_clip(
            metadata.path,
            interval[0],
            interval[1],
            metadata.duration_sec,
            clip_id,
            cancel_event=cancel_event,
        )

    def _stored_clip(self, clip_id: str, source_path: Path) -> ClipArtifact | None:
        stored = self.repository.get_clip(clip_id)
        if stored is None:
            return None
        path = Path(str(stored["file_path"])).expanduser().resolve()
        if not path.is_file() or path.stat().st_size <= 0:
            return None
        return ClipArtifact(
            clip_id=clip_id,
            path=path,
            start_sec=float(stored["start_sec"]),
            end_sec=float(stored["end_sec"]),
            duration_sec=float(stored["duration_sec"]),
            source_path=source_path,
        )

    def _clear_match_evidence(self, match_id: str) -> None:
        match_root = (self.data_dir / "matches" / match_id).resolve()
        self._safe_remove_tree(match_root / "evidence", match_root)

    @staticmethod
    def _source_fingerprint(path: Path) -> str:
        """Hash identity plus bounded content without rereading a multi-gigabyte VOD."""

        source = Path(path).expanduser().resolve()
        stat = source.stat()
        digest = hashlib.sha256()
        digest.update(f"{source}|{stat.st_size}|{stat.st_mtime_ns}".encode())
        chunk_size = 1024 * 1024
        with source.open("rb") as stream:
            digest.update(stream.read(chunk_size))
            if stat.st_size > chunk_size:
                stream.seek(max(0, stat.st_size - chunk_size))
                digest.update(stream.read(chunk_size))
        return digest.hexdigest()

    def _config_fingerprint(self) -> str:
        components = (
            self.round_analyzer.fact_builder,
            self.round_analyzer.selector,
            self.round_analyzer.rule_engine,
            self.round_analyzer.coach,
            self.aggregator,
            self.frame_planner,
            self.hud,
        )

        def implementation_token(component: object) -> str:
            component_type = type(component)
            try:
                return inspect.getsource(component_type)
            except (OSError, TypeError):
                return f"{component_type.__module__}.{component_type.__qualname__}"

        payload = {
            "resume_contract_version": 16,
            "implementations": [implementation_token(component) for component in components],
            "selector_registry": self.round_analyzer.selector.registry,
            "rule_engine_contract": self.round_analyzer.rule_engine.contract,
            "aggregation_rules": self.aggregator.rules,
            "aggregation_groups": self.aggregator.groups,
            "model": getattr(self.round_analyzer.coach, "model", None),
            "frame_limits": {
                "sparse": self.frame_planner.max_sparse,
                "dense": self.frame_planner.max_dense,
            },
            "schemas": {
                "round": self.validator.schemas.round_package,
                "output": self.validator.schemas.ai_output,
                "hud": self.validator.schemas.hud_observation,
            },
        }
        if self.round_boundary_mode == "practical":
            assert self.native_lifecycle_options is not None
            contract_path = self.native_lifecycle_options.unedited_input_contract_path
            assert contract_path is not None
            payload["round_partition"] = {
                "mode": self.round_boundary_mode,
                "native_options": asdict(self.native_lifecycle_options),
                "input_contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
            }
            from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint

            payload["round_partition"]["recognizer_fingerprint"] = global_recognizer_fingerprint()
        if self.hud_video_processor is not None:
            processor = self.hud_video_processor
            payload["hud_processing"] = {
                "implementation": [
                    implementation_token(component)
                    for component in (
                        processor,
                        processor.analyzer,
                        processor.sampler,
                        processor.visual_analyzer,
                        processor.package_builder,
                    )
                ],
                "sampler": vars(processor.sampler),
                "sources": {
                    key: asdict(value)
                    for key, value in processor.package_builder.contract.rules.items()
                },
            }
        hud_fingerprint = getattr(self.hud, "fingerprint", None)
        if callable(hud_fingerprint):
            payload["hud_resources"] = hud_fingerprint()
        if self.hud_video_processor is not None:
            visual_fingerprint = getattr(
                self.hud_video_processor.visual_analyzer, "fingerprint", None
            )
            if callable(visual_fingerprint):
                payload["visual_resources"] = visual_fingerprint()
        return self._json_fingerprint(payload)

    def _persist_hud_report(self, match_id: str, result: HudVideoProcessingResult) -> None:
        """Keep observed facts and adopted frame references, never all sampled pixels."""
        root = self.data_dir / "matches" / match_id
        root.mkdir(parents=True, exist_ok=True)
        evidence_root = root / "hud-evidence"
        evidence_root.mkdir(exist_ok=True)
        refs = []
        retained_paths: dict[str, str] = {}
        for frame in result.evidence_frames:
            target = evidence_root / f"frame-{round(frame.time_sec * 1000000):012d}.jpg"
            if frame.path.is_file():
                shutil.copy2(frame.path, target)
                retained_paths[str(frame.path)] = str(target)
                refs.append({"time_sec": frame.time_sec, "path": str(target)})
        visual_candidates = deepcopy(result.visual_candidates)
        for candidate in visual_candidates:
            for evidence in candidate["evidence"]:
                evidence["frame_ref"] = retained_paths.get(str(evidence["frame_ref"]), "")
        payload = {
            "observations": result.observations,
            "hud_events": result.hud_events,
            "visual_events": result.visual_events,
            "visual_observations": result.visual_observations,
            "visual_candidates": visual_candidates,
            "zone_resolutions": result.zone_resolutions,
            "diagnostics": result.diagnostics,
            "sampled_frame_count": result.sampled_frame_count,
            "adopted_frames": refs,
        }
        target = root / "hud-analysis.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    @classmethod
    def _round_package_fingerprint(cls, package: dict[str, Any]) -> str:
        stable = deepcopy(package)
        stable["frames"] = []
        return cls._json_fingerprint(stable)

    @staticmethod
    def _json_fingerprint(value: Any) -> str:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_resume_fingerprints(
        match: dict[str, Any],
        checkpoint: dict[str, Any],
        source_path: Path,
        source_fingerprint: str,
        config_fingerprint: str,
    ) -> None:
        stored_source = Path(str(match["source_video_path"])).expanduser().resolve()
        if stored_source != Path(source_path).expanduser().resolve():
            raise RuntimeError("再開できません: 元動画のパスが前回実行時と異なります")
        metadata = match.get("metadata", {})
        expected_source = checkpoint.get("source_fingerprint") or metadata.get("source_fingerprint")
        expected_config = checkpoint.get("config_fingerprint") or metadata.get("config_fingerprint")
        if not expected_source or expected_source != source_fingerprint:
            raise RuntimeError("再開できません: 元動画が前回実行時から変更されています")
        if not expected_config or expected_config != config_fingerprint:
            raise RuntimeError("再開できません: 解析設定または実装が前回実行時から変更されています")

    @staticmethod
    def _nearest_purpose(timestamp: float, plan: list[PlannedFrame]) -> str:
        if not plan:
            return "sparse_round_context"
        return min(plan, key=lambda frame: abs(frame.time_sec - timestamp)).purpose

    @staticmethod
    def _enforce_confidence_policy(evaluation: dict[str, Any]) -> dict[str, Any]:
        item = deepcopy(evaluation)
        confidence = float(item["confidence"])
        if item["label"] in {"good", "improve"} and confidence < 0.55:
            item.update(
                {
                    "label": "unscored",
                    "clip_id": None,
                    "display_clip": None,
                    "improvement": None,
                    "missing_information": list(item["missing_information"])
                    or ["評価信頼度が0.55未満です"],
                    "unscored_reason_code": "low_confidence",
                }
            )
        return item

    def _write_analysis_json(
        self, match_id: str, errors: list[str], clip_errors: list[str]
    ) -> Path:
        result = self.repository.get_match_result(match_id)
        if result is None:
            raise RuntimeError(f"保存済みmatchを読み出せません: {match_id}")
        output = self.data_dir / "matches" / match_id / "analysis.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **result,
            "processing_errors": errors,
            "clip_errors": clip_errors,
        }
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output)
        return output

    @staticmethod
    def _safe_remove_tree(path: Path, allowed_root: Path) -> None:
        target = Path(path).resolve()
        root = Path(allowed_root).resolve()
        if target == root or not target.is_relative_to(root):
            return
        if target.is_dir():
            try:
                shutil.rmtree(target)
            except OSError as exc:
                LOGGER.warning("Best-effort cleanup failed for %s: %s", target, exc)

    @staticmethod
    def _check_cancel(cancel_event: ThreadEvent) -> None:
        if cancel_event.is_set():
            raise AnalysisCancelled("解析がキャンセルされました")
