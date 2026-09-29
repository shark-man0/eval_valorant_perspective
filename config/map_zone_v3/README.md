# VALORANT Map / Zone Patch v3

Map/Zone Patch v2 の精査反映版。Summit geometry自体はv2を維持し、runtime契約・検証・拡張性を強化した。

## v3の主変更

- Map runtime contractを `map_zone_runtime_contract_v4.json` に一本化し、Visual Analyzer v2の旧runtime contractを明示的にsupersede。
- Provider IDを `location_label / polygon / coarse_fallback` に統一。
- label vs polygon のFusionを決定表化。高confidence同士の不一致は推測せずambiguous。
- JSON Schemaをstrict化し、validatorが `jsonschema` で実データを検証。
- Map Registryを追加。自動判別不能時は手動Map選択を要求。
- Minimap Rotate / dynamic centered crop はMVP非対応。安定したfull-map transformを回復できなければ `calibration_required`。
- geometry version / observed client build / invalidation policyを追加。
- `topology_edges` を唯一の接続情報の正本とし、重複`adjacency`を削除。
- 境界はambiguous扱い＋previous-zone hold/debounce。
- polygon confidenceにgeometry confidence capを追加。
- Coverage MaskをZone polygonから独立ファイルへ分離し、overlap計算はMask内へclip。
- Callout mappingを`records`一系統へ統合。日本語aliasも各record内へ保持。
- sample countではなく秒ベースのlabel stabilityへ変更。
- 実際のZone sequence + topologyを使うruntimeテスト、3-site fixture、no-mid/special-link fixtureを追加。
- `ZoneResolution`へ`time_sec/frame_index/boundary_state/candidate_zone_ids`を追加。

PEEK-04 exposure registryは引き続き空。VLMによる潜在射線推測は禁止。
