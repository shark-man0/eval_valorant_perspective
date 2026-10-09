# 評価基準Excelと `valorant_evaluation_rules_v4.json` の差分整理

対象:
- `valorant_evaluation_criteria_structured.xlsx`
- `valorant_evaluation_criteria_temporal_v2.xlsx`
- `config/valorant_evaluation_rules_v4.json`

方針（依頼書どおり）: 差異は**統合せず**記録のみ。production rule（JSON）は変更していない。

## 1. 結論

- 44ルールすべてで、ExcelとJSONの**文面・優先度・判定難易度・クリップ秒数・時間文脈は一致**する。ID集合も一致（Excelの採用=はい 44件 = JSON 44件）。
- Excel 2本は「AI生成_構造化ルール」シートが同一。`temporal_v2` は `structured` に「時間文脈分類」シートを加えたもの。
- 差異は「表記の違い」と「JSONにあるがコードが読んでいない方針」に限られる。いずれもrule変更は不要と判断した。

## 2. 照合方法と範囲

| 比較 | 結果 |
|---|---|
| 構造化ルールシート vs JSON（大分類・評価項目・優先度・難易度・評価単位・確認情報・人間方針・例外・クリップ条件・AI指示・クリップ前後秒） | 差分なし |
| 人間入力シート（入力_必須 + 入力_追加）の「あなたの基準」「例外・補足」 vs JSON `human_policy` / `human_exceptions` | 差分なし |
| 人間入力シートの優先度・難易度 vs JSON | 日英表記のみ（MVP必須→mvp_required、重要→important、追加→additional、中→medium、難→hard） |
| 時間文脈分類シート vs JSON `temporal_context`（文脈レベル・映像範囲・ユーザー表示・分類理由・全体集計の要否） | 差分なし（「原則不要」と「不使用」の表記違いのみ） |

未照合: 「書き方例」「使い方」シート（ルール定義を含まない）。ExcelのセルをJSONへ機械的に再生成する検証は行っていない。

## 3. 記録すべき差異

### 3.1 Excelにあって採用されていない14項目（JSONに無い）

入力シートの `採用=いいえ`: AIM-05, INFO-01, MAP-01, OBJ-01, PEEK-03, POS-02, ROLE-01, ROLE-04, ROLE-05, TEAM-01, TEAM-03, UTL-02, UTL-03, UTL-04。意図どおりの除外で、JSONに無いのは正しい。

### 3.2 `temporal_context.event_window_seconds` と `suggested_clip_window_seconds` が13ルールで異なる

MOV-03, MOV-04, PEEK-02, PEEK-04, PEEK-05, POS-01, POS-03, INFO-02, INFO-04, DEC-03, UTL-01, ROLE-02, WPN-01。

- 前者は時間文脈シートの「AIが見る映像範囲」（イベント前後秒）、後者は構造化シートの「クリップ前秒/後秒」で、**ExcelとJSONの両方で別の値として定義されている**。JSONだけの食い違いではない。
- 意図的な区別と解釈できるが、確認はしていない（要確認）。

### 3.3 JSONにあるがコードが読んでいない方針

`src` 内の参照を検索した結果（hud / visual を除く）:

| JSONの項目 | コード側 |
|---|---|
| `temporal_context`（`requires_round_timeline` のみ） | `ui/backend.py` が表示用に参照 |
| `temporal_context.event_window_seconds` / `requires_previous_round_context` / `uses_whole_match_aggregation` | 参照なし |
| `temporal_tolerance_policy` / `automation_policy` | 参照なし |
| `confidence_policy`（0.75 / 0.55） | **コードに直書き**。`pipeline.py` の `_enforce_confidence_policy`（0.55未満の good/improve を `unscored` へ降格）、`ui/backend.py`（0.75未満で `needs_review`） |
| `aggregation_policy` | `rules/aggregator.py` が参照 |

- 時間文脈の「AIが見る範囲」は、現状ドキュメントとして存在し、評価ロジックには効いていない。クリップ窓は `suggested_clip_window_seconds`（`ai/coach.py`）のみ使用。
- 直書きの閾値はconfig値（0.55 / 0.75）と一致している。ドリフト防止として一致を固定するテストを `tests/unit/test_downstream_contract.py` に追加した。configを読む実装への変更は行っていない。

### 3.4 JSON `global_evaluation_principles` の記述

- Excel「AI共通評価方針」は10項目、JSONは17項目。JSONはExcelの内容を含み、コード側の設計原則（concept_tags、NOT_APPLICABLE/NEUTRAL禁止、Z座標を推測しない等）が加わっている。矛盾はない。
- 17項目中の1つが `rule_trigger_registry_v1.json` を参照しているが、実際に使われているのは `config/rule_trigger_registry_v2.json`。**記述が古かった**。ユーザー承認のうえ、誤記修正として `rule_trigger_registry_v2.json` に修正済み（1行のみ。registry・schema・評価ロジックなど他のconfig semanticsは未変更）。

## 4. 対応状況

1. 3.4の `v1` → `v2`: **修正済み**（誤記修正のみ）
2. 3.3の「AIが見る範囲」: **評価ロジックへ反映済み**（`rules/temporal_scope.py`、`docs/external_ai_non_vision_report.md` §6 参照）。`temporal_tolerance_policy` / `automation_policy` / `requires_round_timeline` などは引き続き未使用。
