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
| `player_death` / `player_died` | 共通タイムラインの死亡仮説とキルフィードの本人強調を、Round単位で照合（タイムラインがない試合だけ、自分のHUDが味方のHUDに切り替わった時点も使う） | UTL-01, ADV-01 |
| `first_death_by_player` / `first_kill_by_player` | そのRoundの最初のキルフィード項目の被害者側／キル側に、ゲームの本人強調（黄色の枠）があるか | ADV-01, ADV-02 |
| `kill`（項目単位） | キルフィードの新しい項目（表示が続く間の重複は除く）。キルフィードを切り出していない場合だけ、上部バーの生存数の減少で代用 | INFO-03, DEC-01/02, ADV-01/02/03 |
| `spike_planted` / `objective_state` | 上部中央のタイマーが赤いスパイクアイコンに変わる（設置時に1回だけイベント） | OBJ-03, POS-04, DEC-05 |
| `spike_carried_by_player` | 録画者自身の生存中の視点で、武器一覧の上にスパイクの見出しが出ているか（テンプレート照合）。守備Roundでは常に false | OBJ-02 |
| `side` | スパイクを持てるのは攻撃側だけなので、所持を見たRoundは攻撃。上部バーの得点から求めたRound番号と、12Roundで攻守が入れ替わる知識で、同じ試合の他の規定Roundに広げる | POS-05, OBJ-02 |
| `round_start` | 得点から区切ったRoundの最初のサンプル | POS-05 |

スパイク見出しと得点の数字には、Riotが単体の画像を配布していない。そこで、開発用録画から作ったテンプレートを、公式画像と同じ非公開キャッシュに置いて使う（リポジトリには入れない）。

- スパイク見出し：目で確認した1サンプルを起点に、一致度0.9以上の切り出しを平均して作る（`scripts/knowledge/build_spike_template.py`）。表示言語やキー設定に左右されないよう、文字とキー表示は含めない。36試合で、見出しは一致度0.75以上、最も紛らわしいRound開始前の砂時計表示は0.74以下で、間がほぼ空いている。
- 得点の数字：TRAIN分割の21試合だけから、開発時にTesseractで数字を読み取ってラベルを付け、数字ごとに中央値をとって作る（`scripts/knowledge/build_score_templates.py`）。アプリ本体はTesseractを使わない。読み取った得点は、2回続けて同じ値のものだけを残し、減ることのない得点の性質に合わない値を除く。この条件で残った読み取りは各試合98〜99％。

本人視点・生存・観戦は、共通タイムラインの書き出しがある試合（10/36）ではタイムラインの SELF かつ ALIVE をそのまま使う。独自の推定で上書きはしない。書き出しがない試合だけ、表示中のアビリティHUDが録画者のエージェントと一致するかで判断する。

### 死亡のRound単位の照合（`rules/recorder_life.py`）

- Round境界は上部バーの得点で決める。どちらかのチームの得点が増えた時点が境界で、開始時刻は直後に上部バーが5対5に戻った時点に合わせる。得点と関係のない5対5への戻り（観戦中の表示の乱れなど）は境界にしない。ただし、5対5の状態が20秒以上続いた戻り（購入フェーズ）は、得点の読み取りが途切れて見落とした境界として加える。
- 前回まではタイムラインの round_start／round_end を使っていたが、タイムラインのある10試合でRound数が得点の約1.7倍（例：得点では22Roundの試合が41Round）に分かれていた。生存・本人視点・観戦は引き続きタイムラインを使う。
- 上部バーで味方5人全員の生存が、候補の時点と次のサンプルの両方で見えている死亡候補は捨てる（Round切り替え時のHUDの入れ替わりによる誤検出）。
- 死亡候補は、タイムライン → キルフィードの本人強調 → 自分のHUDの喪失（タイムラインなしの試合のみ）の順に扱い、8秒以内の同じ死亡は1件にまとめる。
- 1つのRoundの死亡は原則1回とする。2回目は、その間に本人視点で生存しているサンプルがRound途中（生存者が10人未満）で2回以上あった場合だけ「復活後の死亡」として残し、それ以外は重複として統合する。
- Round境界の外の候補は捨てる。タイムラインが観戦中としている時点のHUD由来の候補も捨てる。
- 本人強調は録画者自身のキルにも付くため、キルフィード由来の候補は、12秒以内に本人以外の視点が現れた場合だけ死亡として採用する。

## 結果

### 成立度（コードからの集計、44ルール）

| 成熟度 | 変更前 | 変更後 |
|---|---|---|
| なし | 18 | 3 🟢（前回 5） |
| 契約のみ | 25 | 24 |
| 開発観測（実動画で入力がそろう） | 1 | **17** 🟢（前回 15） |
| 認定 | 0 | 0 |

### 実動画で評価候補が出たルール（36試合）

開発用録画36試合（録画者は16エージェント、4ロールすべて）で、評価候補が1回以上出たルールは **16**（前回 14 🟢、変更前に実動画で入力がそろうのは ECO-01 の1ルールのみ）。エージェント特定は36/36のまま。

| ルール | 候補が出た試合（前回→今回） | 候補数（前回→今回） |
|---|---|---|
| INFO-03 人数状況の認識 | 36→36 | 5,525→5,525 |
| DEC-01 人数有利時の判断 | 36→36 | 1,356→1,356 |
| DEC-02 人数不利時の判断 | 36→36 | 1,260→1,260 |
| UTL-01 Utilityを残して死亡 | 36→36 | 461→454 |
| ADV-08 Ult使用判断 | 36→36 | 426→434 |
| ADV-03 クラッチ判断 | 27→27 | 90→90 |
| ROLE-03（イニシエーター） | 10→10 | 544→572 |
| ROLE-02（コントローラー） | 10→10 | 433→439 |
| ROLE-07（センチネル） | 6→6 | 316→324 |
| ADV-01 ファーストデス | 34→34 | 99→100 |
| ADV-02 ファーストキル | 22→20 | 43→40 |
| OBJ-03 設置後の行動 | 36→36 | 551→552 |
| POS-04 設置後の位置 | 36→36 | 551→552 |
| DEC-05 目標状態に応じた判断 | 36→36 | 551→552 |
| **POS-05** 守りの配置 | 0→**20** 🟢 | 0→194 |
| **OBJ-02** 設置判断 | 0→**2** 🟢 | 0→2 |

- ADV-02 が減ったのは、タイムラインのある5試合で、細かく分かれすぎていたRoundが正しい数に戻り、「Roundの最初のキル」の数が減ったため。
- OBJ-02 は「攻撃側でスパイク所持中に設置が起きた」時点が条件で、設置の瞬間に武器一覧が見えていることが少ないため、2件にとどまる。
- 候補数は5秒ごとのサンプル単位の数で、評価件数ではない。

### 攻守の推定（36試合）

| 指標 | 結果 |
|---|---|
| 攻守が決まった試合 | 21/36（残り15試合は、武器一覧にスパイクの見出しが一度も映らなかった） |
| 観測と前後半の構造の矛盾 | **0/21**（Round数の数え上げで番号を付けた版では 3/15 で矛盾） |
| 攻撃Roundを2つ以上観測した試合 | 10試合。どの試合でも、観測した攻撃Roundはすべて同じ前後半に収まった |
| 攻守が付いたサンプル | 7,847 |

- 延長戦は知識基盤に攻守の順序がないため、直接観測したRoundだけに攻守を付ける。fm3_7 では延長の第1・3・5Round（番号24・26・28）で所持を観測し、前半攻撃のチームが延長の1Round目に攻撃する並びと一致した。
- スパイク見出しの誤検出が守備側の前後半に出れば矛盾として表に出るが、447件の検出で矛盾はなかった。

### 死亡検出の照合結果（36試合）

| 指標 | 前回 | 今回 |
|---|---|---|
| Round数の合計 | 974 | **804** 🟢（得点から確実に言える下限は790） |
| 死亡の総数 | 583 | 572 |
| 死亡数がRound数を超える試合 | 0/36 | 0/36 |
| 同じRoundで2回以上の死亡がある試合 | 6/36（10件） | **4/36（5件）** 🟢 |
| 重複として統合した候補 | 81 | 81 |
| Round境界の外で捨てた候補 | 14 | 0 |
| 味方全員の生存中として捨てた候補 | — | 13 |
| 自分のキルと判断して捨てたキルフィード候補 | 76 | 76 |

- 前回は、タイムラインのある試合でRoundが細かく分かれていたため、同じRoundの2回目の死亡が別Roundに見えていた。Roundを得点で区切り直したうえで、同じRoundで2回の死亡が残ったのは5件。内訳は、間にRound途中の本人視点の生存が続くもの3件（蘇生か、1回目の死亡の誤検出かは未判別）、購入フェーズの5対5が表示の乱れで途切れて境界を見落としたもの1件、味方全滅後の表示を生存と見たもの1件。

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
| POS-04 | ポストプラント位置 | llm_contextual | 契約のみ | 開発観測 🟢 | 36 | - |
| POS-05 | 守りの配置 | llm_contextual | なし | 開発観測 🟢 | 20 | - |
| INFO-02 | 音情報の利用 | llm_contextual | なし | なし | 0 | trigger:audio_cue/position_change/peek, fact:audio_cue_observed |
| INFO-03 | 人数状況の認識 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| INFO-04 | 未確認エリアの扱い | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:enemy_spotted/enemy_lost/peek/position_change |
| DEC-01 | 人数有利時の判断 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| DEC-02 | 人数不利時の判断 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| DEC-03 | 戦闘継続/離脱 | llm_contextual | 契約のみ | 契約のみ | 0 | fact:disadvantageous_effect_active |
| DEC-04 | ローテーション判断 | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:enemy_spotted/rotation_started/position_change, fact:enemy_spotted_count |
| DEC-05 | 残り時間の使い方 | llm_contextual | 契約のみ | 開発観測 🟢 | 36 | - |
| UTL-01 | Utilityを残して死亡 | llm_contextual | なし | 開発観測 🟢 | 36 | - |
| TEAM-02 | 味方とのタイミング合わせ | llm_contextual | 契約のみ | 契約のみ | 0 | trigger:ally_entry_start/ally_enter_site/peek/engagement_start, fact:ally_entry_active |
| OBJ-02 | 設置判断 | llm_contextual | なし | 開発観測 🟢 | 2 | - |
| OBJ-03 | 設置後/解除時の時間管理 | llm_contextual | 契約のみ | 開発観測 🟢 | 36 | - |
| ECO-01 | チームBuyとの同期 | llm_contextual | 開発観測 | 開発観測 | 0 | - |
| ECO-02 | 武器回収/セーブ判断 | llm_contextual | 契約のみ | 契約のみ | 0 | fact:save_context_observed |
| ADV-01 | ファーストデス | llm_contextual | なし | 開発観測 🟢 | 34 | - |
| ADV-02 | ファーストキル後の判断 | llm_contextual | なし | 開発観測 🟢 | 20 | - |
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

変更後に開発観測に届かない27ルールの主な原因は次のとおり（阻害しているルール数の多い順）。

1. **射撃（`shot`）と移動（`movement_state`）**：AIM・MOV・WPN系。5秒間隔の切り出しでは捉えられない。交戦区間だけを高頻度で切り出し、弾数表示の減少（射撃）と画面全体の動き（移動）を読む2段構えで次に実装する。弾数の数字は、武器の知識（装弾数）で字形を自己ラベル付けする方針。
2. **ピーク（`peek` / `info_peek`）**：PEEK系。移動の検出器の上に作る。
3. **味方のエントリー・セーブ判断・音声・状態異常**：それぞれ専用の検出器が必要。

## 範囲外にしたこと

- 共通タイムライン改善、Map認識、コード品質監査の担当範囲には手を入れていない。上記の検出は開発用の経路だけで使い、`DevelopmentGameTimeline` や正式パイプラインには接続していない。
- 正式Factは生成していない。特定試合の値に合わせた閾値調整もしていない（ポートレートの有無の閾値は、5試合を通じて空き枠と在席が大きく離れていることを確認して決めた）。
