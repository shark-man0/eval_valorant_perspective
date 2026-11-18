# 共通タイムラインからの正式Fact/Event昇格

関連Issue：#16・#20・#21・#32・#138

## 背景と阻害要因

PR #158 で、共通タイムライン（`development_application_timeline_v1`）は Round Package・RoundAnalyzer・保存・GUIまでつながった。しかし正式Fact/Eventは0件のままで、評価も0件だった。原因は次の2点である。

1. 共通タイムラインのRound境界は常に `provisional` で、`formal_event_id` を持つ `round_start` / `round_end` を作る経路がなかった。RoundAnalyzerは境界未確定のRoundの採点を保留するため、全Roundが `provisional_withheld` になっていた。
2. Factの供給元は #155 の開発用候補（`dev-` 接頭辞、`development_only`）だけだった。開発用候補は採点と保存から除外されるため、正式Factに相当する入力が存在しなかった。

## 追加したもの

`src/valorant_ai_coach/facts/timeline_promotion.py` の `TimelinePromoter` が、共通タイムラインの候補を証拠条件つきで正式Event・state_snapshot・Round境界へ昇格させる。認識処理は持たず、共通タイムラインの秒ごとの状態、Round番号候補、HUD値候補、遷移候補だけを読む。閾値は `config/timeline_promotion_v1.json` にまとめた。

| 正式Event | 昇格条件 |
|---|---|
| `round_start` | BUY→ACTIVE の遷移候補で、境界幅6秒以内。直前の最初の観測が BUY、直後の最初の観測が ACTIVE。開始後10秒以内に BUY の観測がない。Round番号が矛盾しない。3秒を超えて離れた有効候補が複数あれば棄権する。遷移候補が1件もない場合に限り、両端とも観測済みの BUY→ACTIVE 状態ペア（6秒以内）を使う。 |
| `round_end` | ENDED への遷移候補で、境界幅6秒以内。直後に ENDED を確認でき、それ以前にそのRoundの ACTIVE がある。探索上限は昇格済み開始から149秒（知識基盤 #96 の Round時間100秒＋スパイク45秒＋設置4秒）に境界幅を足した値。Round区切りの終わりから終了表示までの間に、別Roundの番号や BUY の観測がない。 |
| `buy_phase` | 確定Round窓の開始前に、BUY の観測が3秒以上ある。 |
| `player_death`（本人） | SELF→SPECTATOR の遷移候補。直前10秒以内に本人視点かつ生存の観測がある。さらに、DEAD の観測、共通タイムラインの死亡仮説、または観戦の観測が6秒中3秒以上続き途中で本人視点に戻らないこと、のいずれかで裏付けられる。同じRoundで復帰がなければ2件目は作らない。 |
| `state_snapshot` | 本人視点かつ生存が観測された秒だけを使う。信頼度0.9以上で値が一致したHUD値だけを採用する。HP 0〜100、アーマー 0〜50、武器名は知識基盤 #96 で解決できたもの、タイマーは戦闘中のみ。スコアは合計が「Round番号−1」と一致する場合だけ採用する。 |

Round の勝敗（`round_meta.round_result`）は、開始前と終了後のスコア表示がそれぞれ1通りに定まり、どちらか一方だけが1増えた場合に限って `win` / `loss` にする。それ以外は `unknown` のままにする。

すべての昇格Eventは `tl-` 接頭辞のIDを持ち、`attributes.qualification = promoted_from_shared_timeline` と、昇格に使った証拠（evidence_refs、共通タイムラインの候補ID、境界幅）を記録する。条件を満たさなかった候補は、理由コードつきで `formal_promotion.abstentions` / `rejected_candidates` に数える。

## 評価経路への接続

- 両境界を昇格できたRoundだけ `round_lifecycle` を `confirmed` にし、`formal_event_id` を付ける。Round窓は購入フェーズから終了表示までの正式窓に置き換える。
- 昇格できなかったRoundは従来どおり `provisional` のままで、採点を保留する。
- 確定Roundの `observation_quality` は、タイムラインから測った観測率と、採用したHUD値の信頼度から求める。映像系の producer はないため `visual_confidence` は0とする。
- 保存前に、動画パイプラインと同じ0.55下限（D-1b）をかける（`policy_runtime.enforce_confidence_floor` に共通化）。
- オフラインのモックコーチでは、必要Factが欠けて選ばれたルール（`allow_unscored`）を、不足Factを明示した UNSCORED（`missing_required_fact`）として出力する。2026-10-07 の決定「評価0件ではなく unscored を明示する」に合わせた。APIコーチの前段には挟まない。
- `--coach openai` で本番のAIコーチを使える（OpenAI APIキーが必要）。

## 修正した潜在不具合

保存済みデータからの再集計（`aggregate_saved_match`）がルール候補を渡していなかったため、各評価の `time_scope` が `unknown` になり、ライブ集計と食い違っていた。確定Roundの評価が0件だったため、これまでは表に出ていなかった。保存済みパッケージから候補を再選択し、動画パイプラインの復元処理と同じ結果になるよう直した。

## 使い方

```
python -m valorant_ai_coach.application.timeline_evaluation evaluate \
  --timeline timeline_PRIVATE.json.gz --output out_dir --match-id DEV-xxx --database app.db
python -m valorant_ai_coach.application.timeline_evaluation evaluate \
  --replay events_and_states_PRIVATE.json --output out_dir --match-id DEV-xxx
python scripts/measure_formal_promotion.py --timeline NAME=PATH --replay NAME=PATH --output dir
```

`--no-promotion` を付けると従来の挙動（全Round暫定）になる。`--replay` は replay 出力を秒単位へ射影する。HUD値を含まないため、state_snapshot は作られない。

## 検算方法

開発用36試合には人手の正解ラベルがない。そのため、昇格条件に使っていないHUD信号との整合で検算する（`verify_promotion`）。人手の正解に代わる独立評価ではない。

- Round開始：昇格した開始から5秒以内のRoundタイマーに1:35以上の読みがあれば正、すべて1:30未満なら誤。
- Round終了：終了より後に、同じRound番号の ACTIVE が観測されれば誤。
- 勝敗：次Roundの区間で読めたスコアが「開始前スコア＋勝敗」と一致すれば正。
- 本人死亡：死亡の3秒後からRound終了までに、本人視点・生存・HP>0 の観測があれば誤。HUD値のない replay では保留にする。

## 残る課題

- 発火したルールは POS-05・INFO-03・UTL-01・ECO-01・ECO-02・ADV-01・ADV-06 の7件で、いずれも `llm_contextual`。決定論エンジンが扱う4ルール（AIM-02・AIM-03・MOV-02・PEEK-04）は映像系Factが必要で、まだ発火しない。GOOD/IMPROVE の判定にはAIコーチの実行が必要になる。
- INFO-03 の `numbers_state`、UTL-01 の `utility_available_count`、ADV-01 の `first_death_by_player`、ADV-06 の `enemy_eco_likely`、POS-05 の `side` は、まだ共通タイムラインに供給元がない。#153 の生存人数・アビリティ・キルフィードの読み取りが共通タイムラインへ接続されれば、同じ昇格の枠組みで正式Fact化できる。
- 境界の棄権は、購入フェーズが観測されない、粗いサンプリングで購入→戦闘の間が6秒を超える、共通タイムラインが遷移候補を出さない、のいずれかで起きる。条件は緩めず、共通タイムライン側の改善を待つ。

## 読み取り器の値による拡張（#153・#155）

`facts/second_feature_promotion.py` の `SecondFeaturePromoter` は、`TimelinePromoter` が確定したRoundに、#155 の `extract_second_features.py` が出す1秒ごとの読み取り値を載せる。読み取り値の中身は、上部バーの生存人数、アビリティHUDの残量、キルフィード、スパイク所持表示である。独自の認識処理や状態管理は持たない。条件は `config/timeline_promotion_v1.json` の `second_features` にまとめた。

### 共通タイムラインを正本とする条件

- 特徴量の元動画（SHA-256）が共通タイムラインと一致しない場合は、何も昇格しない。
- 特徴量の秒は共通タイムラインの秒 `s` の区間 [s, s+1) に割り当てる。キーフレームの位置は秒の途中にずれるため。
- 値を使うのは確定Round窓の中だけ。本人視点の値（アビリティ残量・スパイク所持）は、共通タイムラインが本人視点かつ生存を観測した秒だけで使う。
- 本人死亡は共通タイムラインの判定を基本とする。読み取り値は撃破順の証拠を付けるためと、後述の見落とし補完にだけ使う。

### 生成するFact

| Fact | 根拠 | 条件 |
|---|---|---|
| `numbers_state`（`ally_alive`/`enemy_alive`） | 上部バー | 前後どちらかの秒と同じ読みであること。Round中に人数が増えた読みは3秒続いた場合だけ採用する。信頼度0.9。 |
| `utility_available_count` | アビリティHUD（C・Q・E） | HUDのエージェントが本人のエージェントと一致し、前後の秒と同じ個数であること。信頼度0.85。 |
| `first_death_by_player` / `first_kill_by_player` | 上部バーの減少、キルフィード | 下記の撃破順を参照。 |
| `side` | 本人視点のスパイク所持表示、前後半の入れ替わり（#155 `side.py`） | 矛盾があれば付けない。延長戦は付けない。 |
| `player_role` | 本人エージェント（知識基盤 #96） | 本人のエージェントは、共通タイムラインの本人視点の秒でHUDのエージェントを多数決して決める。60フレーム以上かつ60%以上の一致が必要。 |

### 撃破順

キルフィードは本人強調の判定とチーム色が秒ごとにぶれるため、撃破順には上部バーを使う。上部バーは本人視点でも観戦中でも見える。

- 戦闘中の上部バーが90%以上の秒で安定して読め、開始時に5対5であるRoundだけを対象にする。
- 片方のチームの人数が減るごとに1件の `kill` Eventにする（証拠種別 `top_bar_alive_counts`）。キラーは、キルフィードの本人強調（キラー側）が減少と同じ区間にあり、本人が生存していた場合だけ `player` とする。それ以外の敵の減少では `unknown` とする。
- 本人死亡は、その前4秒から後2秒までにある味方側の減少1件と対応付け、その減少の位置に並べる。同じ区間に別の減少がある場合や、最初の減少が同時に2人だった場合は、順序不明として撃破順の証拠を付けない。
- FactBuilder は、撃破順の証拠を持つRoundで最初の撃破が本人以外なら `first_death_by_player=false` を導出する。キラーが確定している場合は `first_kill_by_player` も導出する。

### 本人死亡の見落とし補完

観戦への切り替えで判定できない本人死亡を、次の条件をすべて満たす場合に限って昇格する。そうした死亡は2つの場面で起きる。本人が最後の生存者でRoundがすぐ終わる場面と、観戦表示が数秒遅れる場面である。

- 共通タイムラインで本人視点・生存が最後に観測された秒 L の後、Round終了まで本人視点・生存が観測されない。
- [L−1, L+3] に上部バーの味方側の減少がちょうど1回ある。
- L の後に観戦視点が観測されているか、その減少で味方が0人になっている。
- そのRoundにまだ本人死亡がない。

### DOWNED・復活

- 生存状態の DOWNED は死亡として扱わず、秒数だけを数える。
- 本人死亡の後、同じRound内で本人視点・生存が5秒以上続いた場合は、死亡Eventに `revived_at_sec` を記録する。上部バーで味方数の増加が3秒以上続いた場合も、復活として数える。

### APIなしでの採点可能性

- レポートの `scorability` で、確定Roundの候補ルールごとに次の4区分を数える。`deterministic_decided`（決定論エンジンが判定済み）、`ready_for_api`（必要Factがすべて0.55以上でそろい、AIコーチの判定を待つ）、`low_confidence`、`missing_facts`。`ready_for_api` はラベルではない。
- AIコーチ（API）を使わない経路では、決定論エンジンが同じラベルを出したもの以外の GOOD/IMPROVE をすべて UNSCORED（`other`、「AIコーチ（API）を実行していないため採点していません」）に変える。モックの判定を正式な採点として保存しない。

### 読み取り器どうしの検算

人手の正解ではなく、別の読み取り器との整合で検算する（`cross_reader_checks`）。

- `first_death_vs_kill_feed`：上部バーから導いたファーストデスと、キルフィードの最初の項目が本人の被撃破かどうかが一致するか。
- `recorder_death_recall`：上部バーで味方が0人になったRoundに、本人死亡が昇格されているか。
- `side_defense`：守備と判定したRoundに、本人視点のスパイク所持表示がないか。
- `top_bar_vs_kill_feed`：上部バーの撃破数と、#155 の数え方によるキルフィードの新規項目数が一致するか。キルフィード側が多く数える傾向があるため、現状は読み取り器の品質の指標として扱う。

### 計測時の重複防止

`scripts/measure_formal_promotion.py` は、同じ元動画（SHA-256）の入力を1件だけ数える。HUD値つきのフル版をreplay版より優先し、除外した入力は `duplicates_skipped` に記録する。特徴量ファイルは中のSHA-256で入力と自動的に対応付ける。`--catalog` を渡すと、共通タイムラインのない録画を `recordings_without_timeline` に列挙する。

### 独立資格との関係

ここで使う信頼度は、開発用録画で整合性の条件を通った読み取りに付ける運用値である。#155 の生成器資格（`config/producer_qualification_v1.json`）は、目視確認と未露出録画での独立評価を求める。この資格は満たしていないため、レポートには `independent_qualification: not_met_development_only` と記録する。
