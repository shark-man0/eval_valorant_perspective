# Map / Zone Resolver Specification v3

## 1. Responsibility
Map Zone Resolverは map selection / calibration / callout+polygon fusion / ZoneResolution timelineだけを担当する。Gameplay eventをemitしない。

Visual Analyzer v2の`minimap_spatial_tracker`が position_change / rotation_*、`team_entry_analyzer`が ally_entry_* をemitする。

## 2. Canonical contracts
`config/map_zone_runtime_contract_v4.json`を唯一のruntime正本とする。base v3の`map_zone_contract_v1.json`、Visual Analyzer v2同梱`map_zone_runtime_contract_v1.json`、Map Patch v2 runtimeはsuperseded。

## 3. Map selection
Map Registry順序: explicit user selection > trusted map label > minimap template match > unresolved。UnresolvedのままZone依存解析を続行しない。

## 4. Minimap profile
MVPはfixed orientationかつfull static map maskを安定復元できる設定のみ。dynamic rotation/centered crop/zoom mismatchを検出し、transform回復不能なら`calibration_required`。

## 5. Fusion
location labelとpolygonの競合はruntimeの決定表に従う。両方high confidenceで異なる場合、境界hold条件を満たさなければunknownへ落とす。

## 6. Boundary
共有境界近傍/複数polygon candidateはambiguous。previous stable zoneを最大0.60秒保持可能。previousがなければcandidateが0.60秒安定するまでzone_id=null。

## 7. Geometry confidence
polygon confidence = min(calibration, self-marker, map geometry cap, matched-zone geometry cap)。coarse authored geometryが0.99などの過剰confidenceを出さない。

## 8. Topology
`topology_edges`が唯一の正本。adjacencyはruntime派生。3-siteやteleporter/special-linkはfixtureで統合テストする。

## 9. Coverage QA
Operational maskはZone authoringとは別ファイル。overlap/gapはZone polygonsをmask内へclipして計算する。mask自体はofficial geometryではなくQA用。

## 10. Callout
`callout_registry.records`だけが正本。aliasesはlocale別にrecordへ保持。未観測alias/calloutはpolygon fallbackへ落とす。

## 11. Versioning
Mapごとにgeometry_versionとobserved_client_buildを保持。alignment不一致や既知のgeometry change時は再authoringが完了するまでcalibration_required。

## 12. PEEK-04
Static human-authored anchorのみ。現時点0件。VLM禁止。
