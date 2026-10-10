from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from valorant_ai_coach.ai import FileResultCache, OpenAICoach
from valorant_ai_coach.application import (
    FramePlanner,
    HudVideoProcessor,
    MatchAnalysisPipeline,
    MockCoachAdapter,
    RoundAnalyzer,
)
from valorant_ai_coach.clips import ClipService
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.hud import HudAnalyzer, MockHudAnalyzer, RealHudAnalyzer
from valorant_ai_coach.models import RoleResolver
from valorant_ai_coach.non_video.features import NonVideoFeatures
from valorant_ai_coach.resources import executable_path, resource_path, resource_root
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.rules import (
    DeterministicRuleEngine,
    EvaluationAggregator,
    RuleSelector,
)
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.visual.runtime import RealVisualAnalyzer, load_visual_profile
from valorant_ai_coach.visual.semantic import (
    OpenAIVisualTransport,
    SemanticBudget,
    SemanticVisualAdapter,
)

from .application.round_analyzer import RoundCoach


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON objectが必要です: {path}")
    return value


@dataclass(frozen=True, slots=True)
class Services:
    settings: AppSettings
    settings_store: SettingsStore
    repository: SQLiteRepository
    video: VideoService
    pipeline: MatchAnalysisPipeline
    rules_by_id: dict[str, dict[str, Any]]
    role_resolver: RoleResolver


def build_services(
    settings_store: SettingsStore,
    *,
    settings: AppSettings | None = None,
) -> Services:
    """Construct the replaceable production services from persisted settings."""

    selected = settings or settings_store.load()
    data_dir = selected.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    validator = SchemaValidator()
    registry = _load_json(resource_path("config/rule_trigger_registry_v2.json"))
    rule_config = _load_json(resource_path("config/valorant_evaluation_rules_v4.json"))
    rules_by_id = {
        str(rule["id"]): dict(rule)
        for rule in rule_config.get("rules", [])
        if isinstance(rule, dict) and "id" in rule
    }
    if not rules_by_id:
        raise RuntimeError("評価ルールを読み込めませんでした")
    role_resolver = RoleResolver()

    repository = SQLiteRepository(data_dir / "app.db", clips_dir=data_dir / "clips")
    ffmpeg_path = executable_path(selected.ffmpeg_path, "ffmpeg")
    ffprobe_path = executable_path(selected.ffprobe_path, "ffprobe")
    video = VideoService(ffprobe_path, ffmpeg_path=ffmpeg_path)
    clips = ClipService(
        ffmpeg_path,
        ffprobe_path,
        data_dir / "clips",
        video_service=video,
    )

    hud_processor = None
    if selected.hud_mode == "mock":
        packaged_fixture = (
            resource_root() / "runtime" / "mock_cases" / selected.mock_case_id / "input.json"
        )
        fixture = (
            packaged_fixture
            if packaged_fixture.is_file()
            else resource_path(f"tests/cases/{selected.mock_case_id}/input.json")
        )
        hud: HudAnalyzer = MockHudAnalyzer(fixture)
    elif selected.hud_mode == "real":
        layout_path = (
            Path(selected.hud_layout_path).expanduser()
            if selected.hud_layout_path.strip()
            else (
                data_dir / "hud_layout.json"
                if (data_dir / "hud_layout.json").is_file()
                else resource_path("config/hud_layout_1080p_v3.json")
            )
        )
        if not layout_path.is_file():
            raise RuntimeError(
                "実HUDモードには校正済みhud_layout.jsonが必要です。設定画面で選択してください"
            )
        real_hud = RealHudAnalyzer(
            layout_path, role_resolver=role_resolver,
            scene_reference_profile_path=(
                Path(selected.scene_reference_profile_path).expanduser()
                if selected.scene_reference_profile_path else None
            ),
        )
        hud = real_hud
        event_contract = EventSourceContract.load(
            resource_path("config/event_source_contract_v1.json")
        )
        event_contract.validate_registry(
            _load_json(resource_path("schemas/event_type_registry_v2.json"))
        )
        visual_profile = load_visual_profile(selected.visual_profile_path)
        map_options = visual_profile.setdefault("map_zone", {})
        if selected.manual_map_id:
            map_options["manual_map_id"] = selected.manual_map_id
        if selected.map_client_build:
            map_options["client_build"] = selected.map_client_build
        rois = visual_profile.setdefault("rois", {})
        if "minimap_normal" in real_hud.layout.regions:
            roi = real_hud.layout.normalized_roi("minimap_normal")
            rois.setdefault("minimap", [roi.x, roi.y, roi.right, roi.bottom])
        semantic = None
        if selected.visual_semantic_enabled is True and selected.mock_ai is False:
            key = settings_store.get_api_key()
            if not key or not selected.visual_semantic_model.strip():
                raise ValueError("Visual SemanticにはAPIキーと専用モデル名が必要です")
            semantic = SemanticVisualAdapter(
                transport=OpenAIVisualTransport(api_key=key, model=selected.visual_semantic_model),
                budget=SemanticBudget(data_dir / "visual-semantic-budget.sqlite"),
            )
        hud_processor = HudVideoProcessor(
            video=video,
            analyzer=real_hud,
            visual_analyzer=RealVisualAnalyzer(
                event_contract, profile=visual_profile, semantic=semantic
            ),
            package_builder=RoundPackageBuilder(contract=event_contract, validator=validator),
            validator=validator,
        )
    else:
        raise ValueError(f"未対応のHUDモードです: {selected.hud_mode}")

    if selected.mock_ai:
        coach: RoundCoach = MockCoachAdapter()
    else:
        api_key = settings_store.get_api_key()
        if not api_key:
            raise RuntimeError("実APIモードにはOpenAI APIキーが必要です")
        coach = OpenAICoach(
            api_key=api_key,
            model=selected.model_id,
            rules_by_id=rules_by_id,
            validator=validator,
            cache=FileResultCache(data_dir / "cache" / "ai"),
            usage_recorder=NonVideoFeatures(repository),
        )

    analyzer = RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(registry),
        rule_engine=DeterministicRuleEngine(),
        coach=coach,
        validator=validator,
    )
    pipeline = MatchAnalysisPipeline(
        data_dir=data_dir,
        repository=repository,
        video=video,
        clips=clips,
        hud=hud,
        round_analyzer=analyzer,
        frame_planner=FramePlanner(),
        aggregator=EvaluationAggregator(rule_config, registry),
        validator=validator,
        delete_temp_frames=selected.delete_temp_frames,
        hud_video_processor=hud_processor,
    )
    return Services(
        selected,
        settings_store,
        repository,
        video,
        pipeline,
        rules_by_id,
        role_resolver,
    )


__all__ = ["Services", "build_services"]
