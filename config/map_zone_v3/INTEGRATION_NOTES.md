# Integration Notes

## Visual Analyzer v2
このpatch導入時は `valorant_visual_analyzer_patch_v2/config/map_zone_runtime_contract_v1.json` をruntimeでロードしてはいけない。`config/map_zone_runtime_contract_v4.json` が唯一の正本。

`integration_overrides/visual_analyzer_v2/visual_analyzer_map_contract_overrides_v1.json` を適用し、旧 `auto_site_anchor_macro_groups` / A-B-Mid前提のfallbackを廃止する。

Map ResolverはZoneResolutionのみ生成し、rotation/team-entryを直接emitしない。

## HUD Analyzer v2
HUD Scale/ROIだけでなくstatic minimap mask alignmentをMap calibrationの入力にする。Map profileを復元できない場合は`calibration_required`。

## Base v3
baseの空 `map_zone_contract_v1.json` は本patch `map_zone_contract_v4.json` にsupersedeされる。
