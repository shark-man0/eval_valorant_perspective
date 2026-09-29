from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .resources import resource_path


class ContractValidationError(ValueError):
    """Raised when data violates a canonical schema or cross-field contract."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"JSONを読み込めません: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractValidationError(f"JSON objectが必要です: {path}")
    return value


@dataclass(frozen=True, slots=True)
class ContractSchemas:
    round_package: dict[str, Any]
    ai_output: dict[str, Any]
    assertions: dict[str, Any]
    hud_observation: dict[str, Any]

    @classmethod
    def load_canonical(cls) -> ContractSchemas:
        return cls(
            round_package=_load_json(resource_path("schemas/round_package_schema_v2.json")),
            ai_output=_load_json(resource_path("schemas/ai_coach_output_schema_v3.json")),
            assertions=_load_json(resource_path("schemas/test_assertion_schema_v1.json")),
            hud_observation=_load_json(resource_path("schemas/hud_observation_schema_v2.json")),
        )


class SchemaValidator:
    """Validate JSON plus invariants that JSON Schema cannot express safely."""

    def __init__(self, schemas: ContractSchemas | None = None) -> None:
        self.schemas = schemas or ContractSchemas.load_canonical()
        for schema in (
            self.schemas.round_package,
            self.schemas.ai_output,
            self.schemas.assertions,
            self.schemas.hud_observation,
        ):
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                raise ContractValidationError(f"正本Schema自体が不正です: {exc.message}") from exc
        self._round = Draft202012Validator(
            self.schemas.round_package, format_checker=FormatChecker()
        )
        self._output = Draft202012Validator(self.schemas.ai_output, format_checker=FormatChecker())
        self._assertions = Draft202012Validator(
            self.schemas.assertions, format_checker=FormatChecker()
        )
        self._hud_observation = Draft202012Validator(
            self.schemas.hud_observation, format_checker=FormatChecker()
        )
        self._visual = {
            name: Draft202012Validator(
                _load_json(resource_path(f"config/visual_v2/schemas/visual_{name}_schema_v2.json"))
            )
            for name in ("observation", "event_candidate")
        }
        self._zone = Draft202012Validator(
            _load_json(resource_path("config/map_zone_v3/schemas/zone_resolution_schema_v2.json"))
        )

    def validate_zone_resolution(self, value: dict[str, Any]) -> dict[str, Any]:
        self._validate_finite_numbers(value, "Zone Resolution")
        self._raise_errors(self._zone, value, "Zone Resolution")
        return value

    def validate_visual_observation(self, value: dict[str, Any]) -> dict[str, Any]:
        self._validate_finite_numbers(value, "Visual Observation")
        self._raise_errors(self._visual["observation"], value, "Visual Observation")
        if (
            value["analysis_eligibility"]["player_mechanics"]
            and value["hud_primary_state"] != "live_first_person"
        ):
            raise ContractValidationError("特殊視点でplayer mechanicsを許可できません")
        target = value["aiming"]["primary_target_ref"]
        if value["aiming"]["head_alignment_error_norm"] is not None and target is None:
            raise ContractValidationError("head alignmentにはprimary targetが必要です")
        spatial = value["spatial"]
        if (
            spatial["exposed_directions_count"] is not None
            and spatial["exposed_directions_source"] != "static_peek_registry"
        ):
            raise ContractValidationError("exposure countには静的registryが必要です")
        return value

    def validate_visual_candidate(self, value: dict[str, Any]) -> dict[str, Any]:
        self._validate_finite_numbers(value, "Visual Candidate")
        self._raise_errors(self._visual["event_candidate"], value, "Visual Candidate")
        if value["end_sec"] < value["start_sec"]:
            raise ContractValidationError("Visual Candidateの終了時刻が開始より前です")
        return value

    @staticmethod
    def _raise_errors(validator: Draft202012Validator, value: object, label: str) -> None:
        errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
        if not errors:
            return
        formatted = []
        for error in errors[:12]:
            location = "/".join(str(part) for part in error.absolute_path) or "<root>"
            formatted.append(f"{location}: {error.message}")
        suffix = f" (+{len(errors) - 12}件)" if len(errors) > 12 else ""
        details = "; ".join(formatted)
        raise ContractValidationError(f"{label}がSchemaに違反しています: {details}{suffix}")

    @staticmethod
    def _validate_finite_numbers(value: object, label: str, path: str = "<root>") -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ContractValidationError(f"{label}.{path} は有限値である必要があります")
        if isinstance(value, dict):
            for key, item in value.items():
                SchemaValidator._validate_finite_numbers(item, label, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                SchemaValidator._validate_finite_numbers(item, label, f"{path}[{index}]")

    def validate_round_package(self, value: dict[str, Any]) -> dict[str, Any]:
        self._validate_finite_numbers(value, "Round Package")
        self._raise_errors(self._round, value, "Round Package")
        start = float(value["round_window"]["start_sec"])
        end = float(value["round_window"]["end_sec"])
        duration = float(value["source_video"]["duration_sec"])
        if not all(math.isfinite(number) for number in (start, end, duration)):
            raise ContractValidationError("動画時刻は有限値である必要があります")
        if end <= start or end > duration + 0.05:
            raise ContractValidationError("round_windowが動画範囲外、または終了<=開始です")
        event_ids: set[str] = set()
        for event in value["events"]:
            event_id = str(event["event_id"])
            if event_id in event_ids:
                raise ContractValidationError(f"event_idが重複しています: {event_id}")
            event_ids.add(event_id)
            if not start <= float(event["time_sec"]) <= end:
                raise ContractValidationError(f"イベントがラウンド範囲外です: {event_id}")
        for index, snapshot in enumerate(value["state_snapshots"]):
            snapshot_time = float(snapshot["time_sec"])
            if not math.isfinite(snapshot_time):
                raise ContractValidationError(
                    f"state_snapshots[{index}].time_sec は有限値である必要があります"
                )
            if not start <= snapshot_time <= end:
                raise ContractValidationError(
                    f"state_snapshots[{index}].time_sec がラウンド範囲外です"
                )
        fact_ids: set[str] = set()
        for fact in value["deterministic_facts"]:
            fact_id = str(fact["fact_id"])
            if fact_id in fact_ids:
                raise ContractValidationError(f"fact_idが重複しています: {fact_id}")
            fact_ids.add(fact_id)
            unknown = set(fact["provenance_event_ids"]) - event_ids
            if unknown:
                raise ContractValidationError(
                    f"{fact_id} が未知のevent_idを参照しています: {sorted(unknown)}"
                )
            fact_time = fact.get("time_sec")
            if fact_time is not None:
                fact_time = float(fact_time)
                if not math.isfinite(fact_time):
                    raise ContractValidationError(
                        f"{fact_id}.time_sec は有限値である必要があります"
                    )
                if not start <= fact_time <= end:
                    raise ContractValidationError(f"{fact_id}.time_sec がラウンド範囲外です")
            fact_range = fact.get("time_range")
            if fact_range is not None:
                fact_start = float(fact_range["start_sec"])
                fact_end = float(fact_range["end_sec"])
                if not math.isfinite(fact_start) or not math.isfinite(fact_end):
                    raise ContractValidationError(
                        f"{fact_id}.time_range は有限値である必要があります"
                    )
                if fact_end <= fact_start:
                    raise ContractValidationError(f"{fact_id}.time_range の終了<=開始です")
                if fact_start < start or fact_end > end:
                    raise ContractValidationError(f"{fact_id}.time_range がラウンド範囲外です")
                if fact_time is not None and not fact_start <= fact_time <= fact_end:
                    raise ContractValidationError(f"{fact_id}.time_sec がtime_range外です")
        for index, frame in enumerate(value["frames"]):
            frame_time = float(frame["time_sec"])
            if not math.isfinite(frame_time):
                raise ContractValidationError(
                    f"frames[{index}].time_sec は有限値である必要があります"
                )
            if not start <= frame_time <= end:
                raise ContractValidationError(f"frames[{index}].time_sec がラウンド範囲外です")
        return value

    def validate_hud_observation(self, value: dict[str, Any]) -> dict[str, Any]:
        """Validate the patch intermediate without changing Round Package v2."""

        self._validate_finite_numbers(value, "HUD Observation")
        self._raise_errors(self._hud_observation, value, "HUD Observation")
        if value["primary_state"] != "remote_control_view":
            remote_type = value["view_context"]["remote_view_type"]
            if remote_type != "none":
                raise ContractValidationError(
                    "remote_control_view以外ではremote_view_type=noneが必要です"
                )
        blocked_view = value["primary_state"] != "live_first_person" or bool(
            set(value["state_flags"])
            & {"vision_obscured_smoke", "vision_obscured_flash", "visual_transition"}
        )
        if blocked_view and value["view_context"]["is_player_world_view_trustworthy"]:
            raise ContractValidationError(
                "特殊画面をplayer world viewとして信頼することはできません"
            )
        player_valid = value["values"].get("player_specific_hud_valid", True)
        if value["primary_state"] == "spectator_first_person" and player_valid:
            raise ContractValidationError(
                "spectator_first_personではplayer_specific_hud_valid=falseが必要です"
            )
        if not player_valid:
            for key in ("hp", "armor", "ammo_current", "ammo_reserve", "weapon_text"):
                if value["values"].get(key) is not None:
                    raise ContractValidationError(
                        f"player_specific_hud_valid=falseでは{key}=nullが必要です"
                    )
            for slot in value["values"].get("ability_slots", []):
                if slot.get("available") is not None or slot.get("charges") is not None:
                    raise ContractValidationError(
                        "player_specific_hud_valid=falseではability値を確定できません"
                    )
        return value

    def validate_ai_output(
        self,
        value: dict[str, Any],
        *,
        round_package: dict[str, Any] | None = None,
        candidate_rule_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        self._validate_finite_numbers(value, "AI Coach出力")
        self._raise_errors(self._output, value, "AI Coach出力")
        if round_package is None:
            return value
        self._validate_finite_numbers(round_package, "Round Package")
        if value["match_id"] != round_package["match_id"]:
            raise ContractValidationError("AI出力のmatch_idが入力と一致しません")
        if value["round_no"] != round_package["round_no"]:
            raise ContractValidationError("AI出力のround_noが入力と一致しません")
        fact_ids = {str(item["fact_id"]) for item in round_package["deterministic_facts"]}
        round_start = float(round_package["round_window"]["start_sec"])
        round_end = float(round_package["round_window"]["end_sec"])
        seen_evaluation_ids: set[str] = set()
        seen_clip_ids: set[str] = set()
        for evaluation in value["evaluations"]:
            evaluation_id = str(evaluation["evaluation_id"])
            if evaluation_id in seen_evaluation_ids:
                raise ContractValidationError(f"evaluation_idが重複しています: {evaluation_id}")
            seen_evaluation_ids.add(evaluation_id)
            primary = str(evaluation["primary_rule_id"])
            if candidate_rule_ids is not None and primary not in candidate_rule_ids:
                raise ContractValidationError(f"候補外ルールが出力されました: {primary}")
            if candidate_rule_ids is not None:
                unknown_related = set(evaluation["related_rule_ids"]) - candidate_rule_ids
                if unknown_related:
                    raise ContractValidationError(
                        f"候補外related_rule_idsが出力されました: {sorted(unknown_related)}"
                    )
            unknown_facts = set(evaluation["fact_refs"]) - fact_ids
            if unknown_facts:
                raise ContractValidationError(
                    f"{evaluation_id} が未知のfact_idを参照しています: {sorted(unknown_facts)}"
                )
            for key in ("evidence_range", "display_clip"):
                interval = evaluation[key]
                if interval is None:
                    continue
                interval_start = float(interval["start_sec"])
                interval_end = float(interval["end_sec"])
                if not math.isfinite(interval_start) or not math.isfinite(interval_end):
                    raise ContractValidationError(
                        f"{evaluation_id}.{key} は有限値である必要があります"
                    )
                if interval_end <= interval_start:
                    raise ContractValidationError(f"{evaluation_id}.{key} の終了<=開始です")
                if interval_start < round_start - 0.05 or interval_end > round_end + 0.05:
                    raise ContractValidationError(f"{evaluation_id}.{key} がラウンド範囲外です")
            evidence_range = evaluation["evidence_range"]
            display_clip = evaluation["display_clip"]
            if evaluation["label"] in {"good", "improve"}:
                if evidence_range is None or display_clip is None:
                    raise ContractValidationError(
                        f"{evaluation_id} の採点済み評価にはevidence_rangeとdisplay_clipが必要です"
                    )
                if (
                    float(display_clip["start_sec"]) > float(evidence_range["start_sec"]) + 0.05
                    or float(display_clip["end_sec"]) < float(evidence_range["end_sec"]) - 0.05
                ):
                    raise ContractValidationError(
                        f"{evaluation_id}.evidence_range がdisplay_clipに含まれていません"
                    )
            for evidence in evaluation["evidence"]:
                evidence_time = float(evidence["time_sec"])
                if not math.isfinite(evidence_time):
                    raise ContractValidationError(
                        f"{evaluation_id}.evidence.time_sec は有限値である必要があります"
                    )
                if not round_start <= evidence_time <= round_end:
                    raise ContractValidationError(
                        f"{evaluation_id}.evidence.time_sec がラウンド範囲外です"
                    )
                if evidence_range is None or not (
                    float(evidence_range["start_sec"])
                    <= evidence_time
                    <= float(evidence_range["end_sec"])
                ):
                    raise ContractValidationError(
                        f"{evaluation_id}.evidence.time_sec がevidence_range外です"
                    )
            clip_id = evaluation["clip_id"]
            if clip_id is not None:
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", str(clip_id)):
                    raise ContractValidationError(
                        f"{evaluation_id}.clip_id に使用できない文字が含まれています"
                    )
                if clip_id in seen_clip_ids:
                    raise ContractValidationError(f"clip_idが重複しています: {clip_id}")
                seen_clip_ids.add(clip_id)
        return value

    def validate_assertions(self, value: dict[str, Any]) -> dict[str, Any]:
        self._validate_finite_numbers(value, "Test Assertion")
        self._raise_errors(self._assertions, value, "Test Assertion")
        return value
