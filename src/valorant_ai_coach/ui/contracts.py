from __future__ import annotations

from dataclasses import dataclass

from valorant_ai_coach.video import AudioTrackMetadata


@dataclass(frozen=True, slots=True)
class UiSettings:
    data_dir: str
    ffmpeg_path: str
    ffprobe_path: str
    model_id: str
    mock_ai: bool
    hud_mode: str
    hud_layout_path: str
    mock_case_id: str
    delete_temp_frames: bool
    debug_logging: bool
    preferred_audio_track_index: int | None = None
    visual_profile_path: str = ""
    manual_map_id: str = ""
    map_client_build: str = ""
    visual_semantic_enabled: bool = False
    visual_semantic_model: str = ""


@dataclass(frozen=True, slots=True)
class VideoMetadataView:
    duration_sec: float
    width: int
    height: int
    fps: float
    video_codec: str
    has_audio: bool
    file_size: int
    audio_tracks: tuple[AudioTrackMetadata, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationView:
    evaluation_id: str
    label: str
    title: str
    rule_id: str
    related_rule_ids: tuple[str, ...]
    situation: str
    evidence: tuple[str, ...]
    missing_information: tuple[str, ...]
    reason: str
    improvement: str | None
    confidence: float
    category: str
    round_no: int | None
    requires_round_context: bool
    decision_source: str
    clip_path: str | None
    needs_review: bool
    unscored_reason_code: str | None


@dataclass(frozen=True, slots=True)
class MatchResultView:
    match_id: str
    source_video_path: str
    status: str
    evaluations: tuple[EvaluationView, ...]
    good_count: int
    improve_count: int
    unscored_count: int
    map_name: str | None = None
    player_agent: str | None = None
    diagnostics: tuple[str, ...] = ()


__all__ = [
    "EvaluationView",
    "MatchResultView",
    "UiSettings",
    "VideoMetadataView",
]
