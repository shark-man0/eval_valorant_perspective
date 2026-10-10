from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.logging_setup import configure_logging
from valorant_ai_coach.non_video.features import NonVideoFeatures
from valorant_ai_coach.non_video.profiles import ProfileStore
from valorant_ai_coach.settings import AppSettings, SettingsStore, default_data_dir

from .contracts import (
    EvaluationView,
    MatchResultView,
    RoundObservationView,
    RoundPartitionView,
    UiSettings,
    VideoMetadataView,
)
from .view_model import parse_time_range

LOGGER = logging.getLogger(__name__)


class BackendFacade:
    """Qt-free application facade used by the desktop UI and smoke tests."""

    def __init__(self, settings_store: SettingsStore | None = None) -> None:
        self.settings_store = settings_store or SettingsStore(default_data_dir() / "settings.json")
        selected = self.settings_store.load()
        self.startup_warning: str | None = None
        try:
            self.services = build_services(self.settings_store, settings=selected)
        except Exception as exc:
            # Keep the settings screen reachable if a custom HUD path became invalid.
            LOGGER.exception("Persisted services could not be constructed; using safe session mode")
            self.startup_warning = str(exc)
            safe = AppSettings.defaults(selected.data_dir)
            self.services = build_services(self.settings_store, settings=safe)
        self.non_video = NonVideoFeatures(self.services.repository)
        self.profiles = ProfileStore(self.settings_store)
        self._refresh_rule_metadata()

    def _refresh_rule_metadata(self) -> None:
        self._rule_category = {
            rule_id: str(rule.get("category", "Other"))
            for rule_id, rule in self.services.rules_by_id.items()
        }
        self._round_context = {
            rule_id: bool(rule.get("temporal_context", {}).get("requires_round_timeline"))
            for rule_id, rule in self.services.rules_by_id.items()
        }

    def get_settings(self) -> UiSettings:
        value = self.settings_store.load()
        return UiSettings(
            data_dir=str(value.data_dir),
            ffmpeg_path=value.ffmpeg_path,
            ffprobe_path=value.ffprobe_path,
            model_id=value.model_id,
            mock_ai=value.mock_ai,
            hud_mode=value.hud_mode,
            hud_layout_path=value.hud_layout_path,
            mock_case_id=value.mock_case_id,
            delete_temp_frames=value.delete_temp_frames,
            debug_logging=value.debug_logging,
            preferred_audio_track_index=value.preferred_audio_track_index,
            visual_profile_path=value.visual_profile_path,
            manual_map_id=value.manual_map_id,
            map_client_build=value.map_client_build,
            visual_semantic_enabled=value.visual_semantic_enabled,
            visual_semantic_model=value.visual_semantic_model,
            round_boundary_mode=value.round_boundary_mode,
            unedited_input_contract_path=value.unedited_input_contract_path,
            native_png_budget_mb=value.native_png_budget_mb,
        )

    def update_settings(self, values: dict[str, Any], api_key: str | None = None) -> None:
        previous_settings = self.settings_store.load()
        previous_key = self.settings_store.get_stored_api_key()
        updated = self.settings_store.update(values, api_key=api_key)
        try:
            rebuilt = build_services(self.settings_store, settings=updated)
        except Exception:
            self.settings_store.save(previous_settings)
            if api_key and api_key.strip():
                if previous_key:
                    self.settings_store.set_api_key(previous_key)
                else:
                    self.settings_store.delete_api_key()
            raise
        self.services = rebuilt
        self.non_video = NonVideoFeatures(self.services.repository)
        self.startup_warning = None
        self._refresh_rule_metadata()
        configure_logging(
            updated.data_dir / "logs",
            level=logging.DEBUG if updated.debug_logging else logging.INFO,
        )

    def has_api_key(self) -> bool:
        return bool(self.settings_store.get_api_key())

    def set_preferred_audio_track_index(self, index: int | None) -> None:
        """Persist playback preference without rebuilding analysis services."""
        self.settings_store.update({"preferred_audio_track_index": index})

    def probe_video(
        self, video_path: Path, *, cancel_event: Event | None = None
    ) -> VideoMetadataView:
        value = self.services.video.probe(video_path, cancel_event=cancel_event)
        return VideoMetadataView(
            duration_sec=value.duration_sec,
            width=value.width,
            height=value.height,
            fps=value.fps,
            video_codec=value.video_codec,
            has_audio=value.has_audio,
            file_size=value.file_size,
            audio_tracks=value.audio_tracks,
        )

    def analyze_video(
        self,
        video_path: Path,
        progress_cb: Callable[[int, str], None],
        cancel_event: Event,
        *,
        match_id: str | None = None,
        resume: bool = False,
    ) -> str:
        # Rebuild for every run so the worker sees the latest persisted settings/key.
        selected = self.settings_store.load()
        self.services = build_services(self.settings_store, settings=selected)
        self.non_video = NonVideoFeatures(self.services.repository)
        self._refresh_rule_metadata()

        def forwarded_progress(value: float, message: str) -> None:
            progress_cb(round(value * 100), message)

        if resume:
            if not match_id:
                raise ValueError("再開にはmatch_idが必要です")
            result = self.services.pipeline.resume_analysis(
                match_id,
                video_path=video_path,
                progress_cb=forwarded_progress,
                cancel_event=cancel_event,
            )
        else:
            result = self.services.pipeline.analyze_video(
                video_path,
                progress_cb=forwarded_progress,
                cancel_event=cancel_event,
                match_id=match_id,
            )
        return result.match_id

    def can_resume(self, match_id: str) -> bool:
        match = self.services.repository.get_match(match_id)
        checkpoint = self.services.repository.get_job_checkpoint(match_id)
        if match is None or checkpoint is None:
            return False
        resumable = {"analyzing", "generating_clips", "cancelled", "failed", "partial"}
        state = checkpoint.get("checkpoint", {})
        has_resume_identity = bool(
            state.get("source_fingerprint") and state.get("config_fingerprint")
        )
        return str(match["status"]) in resumable and has_resume_identity

    def list_matches(self) -> list[dict[str, Any]]:
        return self.services.repository.list_matches()

    def delete_match(self, match_id: str) -> None:
        self.services.pipeline.delete_match(match_id)

    def get_match_result(self, match_id: str) -> MatchResultView:
        stored = self.services.repository.get_match_result(match_id)
        if stored is None:
            raise KeyError(f"解析結果がありません: {match_id}")
        match = stored["match"]
        packages = self.services.repository.list_round_packages(match_id)
        round_meta = packages[0].get("round_meta", {}) if packages else {}
        evaluations = tuple(self._evaluation_view(item) for item in stored["evaluations"])
        checkpoint = self.services.repository.get_job_checkpoint(match_id)
        diagnostics = (checkpoint or {}).get("checkpoint", {}).get("hud_diagnostics", [])
        return MatchResultView(
            match_id=match_id,
            source_video_path=str(match["source_video_path"]),
            status=str(match["status"]),
            evaluations=evaluations,
            good_count=int(stored["good_count"]),
            improve_count=int(stored["improve_count"]),
            unscored_count=int(stored["unscored_count"]),
            map_name=round_meta.get("map"),
            player_agent=round_meta.get("player_agent"),
            diagnostics=tuple(str(item) for item in diagnostics),
            round_partitions=tuple(self._round_partition_view(package) for package in packages),
        )

    @staticmethod
    def _round_partition_view(package: dict[str, Any]) -> RoundPartitionView:
        lifecycle = package.get("round_lifecycle", {})
        statuses = {}
        for name, kind in (("start", "round_start"), ("end", "round_end")):
            statuses[name] = lifecycle.get(name, {}).get("status") or (
                "confirmed" if any(e["type"] == kind for e in package["events"]) else "unknown"
            )
        return RoundPartitionView(
            round_no=int(package["round_no"]),
            start_sec=float(package["round_window"]["start_sec"]),
            end_sec=float(package["round_window"]["end_sec"]),
            start_status=statuses["start"], end_status=statuses["end"],
            observations=tuple(RoundObservationView(
                time_sec=float(row["time_sec"]),
                timer_display=row.get("round_time_remaining_display"), hp=row.get("hp"),
                score_ally=row.get("score_ally"), score_enemy=row.get("score_enemy"),
            ) for row in package["state_snapshots"]),
        )

    def search_evaluations(self, **filters: Any) -> list[dict[str, Any]]:
        return self.non_video.search(**filters)

    def get_statistics(self, **filters: Any) -> dict[str, Any]:
        return self.non_video.statistics(**filters)

    def compare_matches(self, first: str, second: str) -> dict[str, Any]:
        return self.non_video.compare(first, second)

    def export_report(self, match_id: str, destination: Path, fmt: str) -> None:
        self.non_video.export_report(
            match_id, destination, fmt, rule_categories=self._rule_category
        )

    def get_feedback(self, evaluation_id: str) -> dict[str, Any] | None:
        return self.non_video.feedback(evaluation_id)

    def save_feedback(self, evaluation_id: str, verdict: str, memo: str) -> None:
        self.non_video.save_feedback(evaluation_id, verdict, memo)

    def delete_feedback(self, evaluation_id: str) -> None:
        self.non_video.delete_feedback(evaluation_id)

    def get_api_usage(self, prices: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.non_video.usage(prices)

    def _evaluation_view(self, item: dict[str, Any]) -> EvaluationView:
        confidence = float(item.get("confidence", 0.0))
        evidence_lines = tuple(self._format_evidence(value) for value in item.get("evidence", []))
        clip = item.get("clip") or {}
        return EvaluationView(
            evaluation_id=str(item.get("evaluation_id", "")),
            label=str(item.get("label", "unscored")),
            title=str(item.get("title", item.get("primary_rule_id", "評価"))),
            rule_id=str(item.get("primary_rule_id", "")),
            related_rule_ids=tuple(str(value) for value in item.get("related_rule_ids", [])),
            situation=str(item.get("situation", "観測された場面")),
            evidence=evidence_lines,
            missing_information=tuple(str(value) for value in item.get("missing_information", [])),
            reason=str(item.get("reason", "")),
            improvement=item.get("improvement"),
            confidence=confidence,
            category=self._rule_category.get(str(item.get("primary_rule_id", "")), "Other"),
            round_no=(int(item["round_no"]) if item.get("round_no") is not None else None),
            requires_round_context=self._round_context.get(
                str(item.get("primary_rule_id", "")), False
            ),
            decision_source=str(item.get("decision_source", "llm")),
            clip_path=str(clip["file_path"]) if clip.get("file_path") else None,
            needs_review=item.get("label") in {"good", "improve"} and confidence < 0.75,
            unscored_reason_code=item.get("unscored_reason_code"),
            fact_refs=tuple(str(value) for value in item.get("fact_refs", [])),
            time_range=parse_time_range(item.get("evidence_range")),
        )

    @staticmethod
    def _format_evidence(value: Any) -> str:
        if not isinstance(value, dict):
            return str(value)
        seconds = float(value.get("time_sec", 0.0))
        minutes, remainder = divmod(max(0, round(seconds)), 60)
        fact = str(value.get("fact", "観測事実"))
        source = str(value.get("source", "unknown"))
        return f"{minutes:02d}:{remainder:02d}  {fact}（{source}）"


__all__ = ["BackendFacade"]
