# プレイ評価44ルールの成立状況（Issue #32）

44ルールそれぞれについて、トリガーとなるイベントと必須の状態（Fact）が実動画で観測できるかを、コードから機械的に集計できるようにした。あわせて、外部知識（#96）を使う読み取り器で不足していた入力を増やし、実動画で評価候補が出るルールを増やした。

ここでいう「評価候補」は開発用の観測で、正式なFact・Event・評価ではない（`formal_outputs = 0`）。

## 判定の仕組み

- `config/rule_producer_status_v1.json`：イベント31種・Fact37種ごとに、生成器と成熟度（`none` / `contract` / `development` / `qualified`）を変更前と変更後で記録する。
  - `contract`：生成器はあるが、スキーマと合成テストだけで実録画での観測がない
  - `development`：開発用の経路で実録画から観測している
  - `qualified`：独立した実動画検証に合格（現時点ではゼロ）
- `rules/coverage.py`：ルールの成立度を「トリガーのうち最も成熟したもの」と「必須Factのうち最も弱いもの」の低い方で決める。`allow_unscored` の必須Factも、ないと `unscored` にしかならないので必須として数える。
- `rules/development_readiness.py`：実録画から得た観測列から候補Fact・候補イベントを作り、ルールの述語（eq / in / gt / gte）を満たす回数を数える。

```sh
PYTHONPATH=src python3 scripts/rules/rule_coverage_report.py [--occurrences REPORT.json]
PYTHONPATH=src python3 scripts/rules/rule_readiness_real_video.py --cache ASSETS --out PRIVATE.json CROPS/*.zip
```

## 追加した検出

すべて #96 の知識基盤の上に作った。

| 入力 | 方法 | 主に効くルール |
|---|---|---|
| `player_role` | 録画者のエージェントをアビリティHUDの多数決で特定し、知識のロール表で変換 | ROLE-02/03/07（ROLE-06/08 はトリガー側が未整備） |
| `ability_state` / `utility_available_count` / `ultimate_available` | 録画者自身のHUD（表示中のHUDが録画者のエージェントのとき）のチャージ表示 | UTL-01, ADV-08 |
| `utility_used` | 自分のHUDでのチャージの減少（5秒間隔なので時刻は±5秒） | ADV-08, ROLE-02, ROLE-03 |
| `numbers_state` | 上部バーの生存ポートレート数 | INFO-03, DEC-01, DEC-02 |
| `clutch_state` | 味方の生存が1人で、表示中のHUDが録画者のもの | ADV-03 |
| `kill`（チーム単位） | 上部バーの生存数の減少（ラウンドの切り替わりで増える場合は除く）。キルした人は特定しない | INFO-03, DEC-01, DEC-02, ADV-03 |
| `player_death` / `player_died` | 自分のHUDが味方のHUDに切り替わった時点 | UTL-01 |

自分のHUDかどうかは、表示中のアビリティHUDが試合全体で特定した録画者のエージェントと一致するかで判断する。観戦中は味方のHUDが出るので、自分のチャージや死亡と混同しない。

## 結果

### 成立度（コードからの集計、44ルール）

| 成熟度 | 変更前 | 変更後 |
|---|---|---|
| なし | 18 | 7 🟢 |
| 契約のみ | 25 | 27 |
| 開発観測（実動画で入力がそろう） | 1 | **10** 🟢 |
| 認定 | 0 | 0 |

### 実動画で評価候補が出たルール（36試合）

開発用録画36試合（録画者は16エージェント、4ロールすべて）で、評価候補が1回以上出たルールは **9**（変更前に実動画で入力がそろうのは ECO-01 の1ルールのみ）。

| ルール | 候補が出た試合 | 候補数（合計） |
|---|---|---|
| INFO-03 人数状況の認識 | 36/36 | 5,525 |
| DEC-01 人数有利時の判断 | 36/36 | 1,394 |
| DEC-02 人数不利時の判断 | 36/36 | 1,298 |
| UTL-01 Utilityを残して死亡 | 36/36 | 486 |
| ADV-08 Ult使用判断 | 36/36 | 393 |
| ADV-03 クラッチ判断 | 27/36 | 83 |
| ROLE-03（イニシエーター） | 10/36 | 606 |
| ROLE-02 Smokeタイミング（コントローラー） | 10/36 | 472 |
| ROLE-07（センチネル） | 6/36 | 348 |

- ROLE系は、録画者のロールに合うルールだけに候補が出ている（イニシエーター10試合、コントローラー10試合、センチネル6試合）。デュエリストのROLE-06/08はトリガー側が未整備。
- 1試合あたりの録画者の死亡検出は8〜24回。ラウンド数との照合はまだしていないため、上限側（24回）には誤検出が含まれている可能性がある。
- 候補数は5秒ごとのサンプル単位の数で、評価件数ではない。ラウンド単位への集約と正式Fact化は別工程である。

## 全ルールの表

| ルール | 項目 | 判定方式 | 変更前 | 変更後 | 実動画の候補（試合数） | 残る阻害要因 |
|---|---|---|---|---|---|---|
| AIM-01 | ヘッドライン維持 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:engagement_start/shot |
| AIM-02 | プリエイム | deterministic_if_confident_else_llm | 契約のみ | 契約のみ | 0 | trigger:preaim_started/peek/engagement_start |
| AIM-03 | 初弾の撃ち方 | deterministic_if_confident_else_llm | 契約のみ | 契約のみ | 0 | trigger:shot |
| AIM-04 | 射撃方法の選択 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:shot |
| MOV-01 | 移動撃ち | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:shot/movement_state, fact:shot_while_moving |
| MOV-02 | ストッピング | deterministic_if_confident_else_llm | 契約のみ | 契約のみ | 0 | trigger:shot/movement_state, fact:first_shot_detected |
| MOV-03 | 不要な露出 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:peek/position_change |
| MOV-04 | 交戦後のリポジション | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:engagement_end/position_change/enemy_reengage |
| PEEK-01 | 単独ピーク | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:peek/info_peek |
| PEEK-02 | ピーク方法の選択 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:peek/info_peek |
| PEEK-04 | 複数射線への露出 | deterministic_if_confident_else_llm | 契約のみ | 契約のみ | 0 | trigger:peek, fact:exposed_directions_count |
| PEEK-05 | リピーク | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:peek/enemy_reengage |
| POS-01 | 遮蔽と退路 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:engagement_start/position_hold/position_change, fact:spatial_context_available |
| POS-03 | オフアングル | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:hold_angle/position_hold |
| POS-04 | ポストプラント位置 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:spike_planted/position_change/position_hold, fact:spike_planted |
| POS-05 | 守りの配置 | llm_contextual | なし | なし | 0 | fact:side |
| INFO-02 | 音情報の利用 | llm_contextual | なし | なし | 0 | trigger:audio_cue/position_change/peek, fact:audio_cue_observed |
| INFO-03 | 人数状況の認識 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| INFO-04 | 未確認エリアの扱い | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:enemy_spotted/enemy_lost/peek/position_change |
| DEC-01 | 人数有利時の判断 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| DEC-02 | 人数不利時の判断 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| DEC-03 | 戦闘継続/離脱 | llm_contextual | 契約のみ | 契約のみ | 0 | fact:disadvantageous_effect_active |
| DEC-04 | ローテーション判断 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:enemy_spotted/rotation_started/position_change, fact:enemy_spotted_count |
| DEC-05 | 残り時間の使い方 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:objective_state/spike_planted/rotation_started/position_change, fact:objective_state_observed |
| UTL-01 | Utilityを残して死亡 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| TEAM-02 | 味方とのタイミング合わせ | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:ally_entry_start/ally_enter_site/peek/engagement_start, fact:ally_entry_active |
| OBJ-02 | 設置判断 | llm_contextual | なし | なし | 0 | trigger:objective_state/site_state/spike_planted/engagement_start, fact:side, fact:spike_carried_by_player |
| OBJ-03 | 設置後/解除時の時間管理 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:spike_planted/spike_defuse_started/position_change/peek/engagement_start, fact:spike_planted |
| ECO-01 | チームBuyとの同期 | llm_contextual | 開発観測 | 開発観測 | 0 | - |
| ECO-02 | 武器回収/セーブ判断 | llm_contextual | 契約のみ | 契約のみ | 0 | fact:save_context_observed |
| ADV-01 | ファーストデス | llm_contextual | なし | なし | 0 | fact:first_death_by_player |
| ADV-02 | ファーストキル後の判断 | llm_contextual | なし | なし | 0 | fact:first_kill_by_player |
| ADV-03 | クラッチ判断 | llm_contextual | なし | 開発観測 🟢 | 27 | - |
| ADV-04 | ラーク | llm_contextual | なし | なし | 0 | trigger:position_change/position_hold/enemy_spotted, fact:lurk_context_observed |
| ADV-05 | エントリー役との連携 | llm_contextual | 契約のみ | 契約のみ | 0 | fact:ally_entry_active |
| ADV-06 | アンチエコ | llm_contextual | なし | なし | 0 | fact:enemy_eco_likely |
| ADV-07 | セーブ | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:save_decision/weapon_pickup/position_change, fact:save_context_observed |
| ADV-08 | Ult使用判断 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| ROLE-02 | Smokeタイミング | llm_contextual | なし | 開発観測 🟢 | 10 | - |
| ROLE-03 | 索敵Utility | llm_contextual | なし | 開発観測 🟢 | 10 | - |
| ROLE-06 | Space獲得後の生存 | llm_contextual | なし | 契約のみ 🟢 | 0 | trigger:ally_enter_site/engagement_end/position_change |
| ROLE-07 | サイト保持 | llm_contextual | なし | 開発観測 🟢 | 6 | - |
| ROLE-08 | Flank管理 | llm_contextual | なし | 契約のみ 🟢 | 0 | trigger:position_hold/enemy_spotted/enemy_lost |
| WPN-01 | Operator使用 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:hold_angle/shot/position_change, fact:weapon |

「残る阻害要因」は、開発観測に届いていない入力（`trigger:` はトリガー、`fact:` は必須Fact）。

## 残る主な阻害要因

変更後に開発観測に届かないルールを、阻害している入力の多い順に並べると次のとおり。

1. **射撃（`shot`）と移動（`movement_state`）**：AIM・MOV・WPN系の6ルール。弾数表示の減少で射撃を拾う方式が有力だが、5秒間隔では足りず、交戦区間だけを高頻度で切り出す2段構えが必要。数字の読み取りは、武器の知識（装弾数）を使って弾数表示の字形を自己ラベル付けする方法を考えている。
2. **ピーク（`peek` / `info_peek`）**：PEEK系。視点映像からの検出器が実録画で未検証。
3. **攻守（`side`）**：OBJ・ECO系。上部バーやスパイクの表示、ラウンド番号と前後半の知識から推定できる見込み。
4. **キルの当事者（`first_kill_by_player` など）**：キルフィードの照合が必要。キルフィードの顔画像は #105 のポートレート学習を流用できる。
5. **スパイク設置（`spike_planted`）**：上部中央のスパイク表示（今回の切り出しにも映っている）で検出できる見込み。

## 範囲外にしたこと

- 共通タイムライン改善、Map認識、コード品質監査の担当範囲には手を入れていない。上記の検出は開発用の経路だけで使い、`DevelopmentGameTimeline` や正式パイプラインには接続していない。
- 正式Factは生成していない。特定試合の値に合わせた閾値調整もしていない（ポートレートの有無の閾値は、5試合を通じて空き枠と在席が大きく離れていることを確認して決めた）。
