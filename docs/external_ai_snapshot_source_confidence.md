# snapshot由来factのconfidence provenance（`state_snapshot.source_confidence`）

## 1. 問題

`FactBuilder` は state_snapshot から fact を作るとき、confidence に **package全体の集約値**
（`observation_quality.hud_confidence` / `visual_confidence`）を一律で使っていた。集約値は
受理されたobservation全体の統計なので、個々の観測より高くなりうる。その結果、

- 観測 `< 0.90` から作られたfactが `>= 0.90` になり、決定論 `0.90` gate を通過しうる（過大評価）
- 逆に、集約値が低いと `>= 0.90` の観測から作られたfactがgate未満になる（過小評価）

という、confidence provenance上の不整合があった。

## 2. 生成元の確認（読んだコード）

snapshotは**単一のsource confidenceを共有しない**。

| snapshotのフィールド | 観測源 | source confidence |
|---|---|---|
| `ally_alive` `enemy_alive` `weapon` `spike_state` `utility_available_count` | そのsnapshotを作ったHUD observation | observationの `hud_confidence`。ビジョン側で `min(状態分類のconfidence, 受理された全リーダーのconfidence)` として作られるため、**どのリーダーのconfidenceも超えない** |
| `round_time_remaining_sec` | 同上のタイマーリーダー | 予約済みの値レベル score `roi_confidence.round_timer_value`（受理されなければ 0.0）。`roi_confidence` の他のキーは特徴・幾何のconfidenceと同じ名前空間で混在し、値の根拠にならない（ビジョン側コメントと同じ原則） |
| `spatial_context`（cover / escape / LOS / exposed / view target） | 視覚observation | `min(spatial.confidence, quality.visual_confidence)` |
| `player_location`（zone） | map resolver | resolution の `zone_confidence` |

よって単一の `confidence` ではなく、**フィールド（源）単位**で保持する。`hp` / `armor` は
`FactBuilder` がsnapshotからfact化せず、HPは `_owned_hp_facts`（`hp_value`）で別経路のため対象外。

## 3. 変更

- **schema**（`schemas/round_package_schema_v2.json`、追加のみ・`schema_version` 据え置き）:
  `state_snapshot.source_confidence`（任意）。`additionalProperties:false`、各値は `[0,1]` の数値。
  キー: `ally_alive` `enemy_alive` `weapon` `spike_state` `round_time_remaining_sec`
  `utility_available_count` `player_location` `spatial_context`。
- **生成**（`rounds/builder.py`）: 上表の源から各snapshotに記録。不正値（真偽値・文字列・範囲外・非有限）は 0.0。
- **fact化**（`facts/builder.py`）: snapshot由来factは `source_confidence[field]` を使い、**それを超えない**。
  複数フィールドから作るfact（`numbers_state` / `clutch_state`）は最小値。エントリが無い・不正な値は **0.0**。
  package集約値は snapshot由来factの代替sourceとして一切使わない。
- `FactBuilder` の既存挙動（重複identityのスキップ、provenance付きevent由来factの扱い）は不変。

## 4. 評価不能の扱い（既存contractに従う）

source confidence が不足するfactは 0.0 または低値になり、決定論gate（`>= 0.90`）を通らない。
snapshot由来factで決定論decisionを持つのは `PEEK-04`（`exposed_directions_count`）のみで、
gate未満なら既存contractどおり `unscored`（`low_confidence`）になる。

## 5. 変更前の計測

方法: `scripts/measure_snapshot_fact_confidence.py`。本番と同じ経路
（`RoundPackageBuilder.build` → `FactBuilder.enrich`）に、決定論的な**合成**observation集合
（60秒、0.5秒間隔、50 package/分布、seed固定）を通し、各snapshot由来factを、
そのfactを作ったobservationの `hud_confidence` と比べる。

**これは実録画での頻度ではない。** リポジトリに生のobservationは無く、
`e2e_reports/match_001`（4,634 observation / 919 snapshot）のサマリには観測ごとのconfidence
分布が含まれないため、実データでの件数は計測できなかった。以下は、置いた分布の下で
欠陥がどの規模で現れるかの測定である。

| 分布 | snapshot由来fact | 過大評価（obs<0.90 → fact≥0.90） | 過小評価（obs≥0.90 → fact<0.90） | 元観測より高い | 過大評価のあるpackage | 集約値 | 最大乖離 |
|---|---:|---:|---:|---:|---:|---|---:|
| uniform 0.65–1.00 | 13,260 | 0 | 2,628（19.8%） | 6,130（46.2%） | 0/50 | 0.80–0.86 | 0.000 |
| bimodal（70%が0.90–0.99） | 14,742 | **3,405（23.1%）** | 0 | 5,453（37.0%） | **50/50** | 0.91–0.94 | **0.278** |
| mostly high（90%が0.95–0.99） | 15,453 | **1,150（7.4%）** | 0 | 5,002（32.4%） | **49/50** | 0.96–0.97 | **0.318** |
| constant 0.80 | 12,250 | 0 | 0 | 0 | 0/50 | 0.80 | 0.000 |

- 欠陥の出方は分布で決まる。集約値が個々の観測を上回る分布（高信頼な観測が多数を占めるほど）で過大評価が起き、
  下回る分布では逆に過小評価が起きる。constant 0.80 は集約値＝観測値で、どちらも起きない。
- 「元観測より高い」は、gateを超えなくても出所より高いconfidenceを持つfactの数。

## 6. 変更後の計測

同一スクリプト・同一入力。fact総数は変更前と同一（13,260 / 14,742 / 15,453 / 12,250）で、
**4分布すべてで過大評価・過小評価・「元観測より高い」が 0、最大乖離 0.000**。

生データ: `docs/external_ai_snapshot_confidence_measurement_before.json` / `..._after.json`

## 7. 後方互換性

| 対象 | 影響 |
|---|---|
| schema検証 | 任意追加のため、`source_confidence` の無い既存packageも検証を通る。`schema_version` は据え置き |
| 既存fixture（`tests/cases/TC-*/input.json`） | 38/38ケースのsnapshotが `source_confidence` を持たず、**そのままだと36ケース・56件のfactが 0.98 → 0.0** になった（ラベルは不変）。本番packageと同じ形にするため、**合成fixtureのみ明示的に移行**（`scripts/migrate_fixture_snapshot_source_confidence.py`）。旧実装がfactに与えていたpackage値をそのまま書き出す1回限りの移行で、38ファイル・57 snapshot・409行の追加のみ（削除なし）。移行後、全497factが旧実装と完全一致 |
| 保存済みの実データ（SQLite等） | **移行しない。** `source_confidence` の無い古いpackageを再解析すると、snapshot由来factは 0.0（決定論gateを通さず、`PEEK-04` は `unscored`）になる。保存済みの過去の評価結果自体は変更されない。測定されていないconfidenceを黙って付与するフォールバックは入れていない |
| 移行スクリプト | 実データへ使用不可（スクリプト冒頭に明記）。合成fixture専用 |

## 8. テスト

`tests/unit/test_snapshot_source_confidence.py`（30件）。依頼の4件を含む:

- source `0.65` → factが `0.90` 以上にならない（0.0 / 0.30 / 0.65、集約値0.99）
- source `0.89` → 決定論 `0.90` gate を通らない（`PEEK-04` が `unscored` / `low_confidence`）
- source `0.95` → 他条件を満たせばgateを通る（`PEEK-04` が `improve`、confidence 0.95。集約値0.30でも）
- package集約値が高くても（0.99 / 1.0）低くても（0.30）source confidenceを上書きしない

加えて、フィールド別の独立性と最小値、欠落・不正値（真偽値/文字列/NaN/inf/範囲外）の0.0扱い、
schemaでの不正値拒否、旧形式の検証通過、`RoundPackageBuilder` 経由（観測ごとのconfidence、タイマーの予約score、
spatialの最小値）、計測集合に過大評価が無いこと。

**ネガティブコントロール**: `facts/` と `rounds/` だけを変更前に戻して実行すると、30件中23件が失敗する
（依頼の4件はすべて失敗）。

## 9. 未解決・限界

- **評価のconfidenceが、引用factのconfidenceを超えうる。** `validate_ai_output` は評価confidenceと
  `fact_refs` のfact confidenceの関係を検証しない。fixtureの採点済み評価（`fact_refs`あり）31件中2件
  （TC-014, TC-016）で 0.98 > 引用factの最小 0.90。mockは評価confidenceの上限にpackage集約値を使い
  （`mock_evaluator._confidence`）、実モデルの宣言値には制約が無い。今回は「factのconfidence」の修正で、
  評価confidenceの上限は別のcontract変更になるため未実施（次の候補: AI出力の検証層）。
- mockおよび実モデルの非決定論ruleは、factの値をconfidenceに関係なく参照する（従来どおり）。
  決定論gateを通らないのは `0.90` gateを持つruleのみ。
- 同一状態が続くsnapshotは間引かれる（既存挙動）。最初のsnapshotのconfidenceが記録され、
  後続の同一状態でより高いconfidenceの観測は記録されない。保守側の情報欠落のみ。
- zone factは、builderが先に作る `MZ` factが `min(zone_confidence, package visual_confidence)` を持つ（既存）。
  package集約値は上限として下げる方向にのみ働き、sourceを超えない。変更していない。
- `hp` / `armor` には `source_confidence` を付けていない（fact化経路が別）。
- 画像解析側のコード（`hud/` `visual/` `maps/`）は変更していない。
