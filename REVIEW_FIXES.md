# 外部レビュー反映内容（Claude + Gemini）

## Claudeレビューで反映済み
1. 入出力Schemaを単一の正式契約へ統一。
2. Round Package正式Schemaを作成。
3. テスト入力から評価結論の先出しを除去。
4. 44ルールを毎回LLMへ渡さず候補選定Registryを導入。
5. MVP必須ルールのテストカバレッジを追加。
6. concept_tags、label条件制約、confidence帯、temporal tolerance、dedup policyを明文化。
7. PEEK-02の曖昧性を仕様化。

## Geminiレビューから採用した修正
1. 3D復元は採用せず、Zone + 観測可能なSpatial Contextへ整理。
2. RoleをRound Packageへ追加し、Role固有ルールをcandidate gate化。
3. `required_state_predicates` を構造化し、明確な条件を候補選定へ利用。
4. Deterministic Fact Builder / Rule Engine契約を追加。LLMは文脈・例外・説明へ集中。
5. Utilityの効果/状態異常を扱える `status_effect` / `utility_effect_observed` を追加（観測できる場合のみ）。
6. 同一ラウンドでGOODとIMPROVEが同時に成立する複合テストを追加。
7. Role gateテスト、極端な残り時間、状態効果後の離脱、評価出力なしケースを追加。
8. UNSCOREDを「候補だが判断不能」に限定。候補外/通常行動はevaluationを生成しない。
9. 出力に `decision_source` / `fact_refs` / `unscored_reason_code` を追加。

## 採用しなかった/修正して採用した内容
- Z座標/Yaw/Pitch/完全3D LOS復元: 個人用録画解析として過剰。推測誤りを避けるため採用しない。
- 全ての定性的基準を秒数/距離へ強制変換: 人間基準を歪めるため採用しない。明示された閾値のみ数値化。
- NEUTRAL / NOT_APPLICABLEラベル追加: UI/APIを増やさず、出力自体を生成しない方式にする。
