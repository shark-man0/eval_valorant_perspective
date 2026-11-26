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

撃破の有無と順序は上部バーで決める。上部バーは本人視点でも観戦中でも見え、人数は撃破でしか減らない。キルフィードは撃破を増やしも消しもせず、上部バーの減少に割り当てられた項目だけを、本人の帰属と同じ秒の中の順序に使う。

- 戦闘中の上部バーが90%以上の秒で安定して読め、開始時に5対5であるRoundだけを対象にする。
- 片方のチームの人数が1人減るごとに1件の撃破とする。本人死亡に対応しない撃破は `kill` Eventにする（証拠種別 `top_bar_alive_counts`）。
- 本人死亡は、タイムラインの死亡時刻の前4秒から後2秒までにある味方側の減少と対応付ける。観戦表示はデスカメラの後に始まるため、キルフィードが本人の被撃破として示した減少は、10秒前まで遡って対応付ける。その場合は、減少の後に共通タイムラインが本人視点・生存を観測していないことを条件にする。
- 同じ区間に別の減少がある場合は、双方に割り当てたキルフィード項目の出現時刻が異なるときだけ順序を決める。決まらなければ順序不明として撃破順の証拠を付けない。
- 本人死亡を減少に対応付けられなかったRoundでは、撃破の一覧が完全とは言えないため、`kill` Eventの証拠種別を `top_bar_partial` にする。
- FactBuilder は、撃破順の証拠を持つRoundで最初の撃破が本人以外なら `first_death_by_player=false` を導出する。順序不明（`order_ambiguous`）の撃破からは `first_death_by_player` も `first_kill_by_player` も導出しない。

### キルフィードと上部バーの不一致の原因と対策

開発用録画の生の読み取りを並べて確認した。不一致の原因は次の4つだった。

- 上部バーが変わらない秒に、同じチーム同士の項目（例：味方→味方）が数秒間出る（誤読）。
- 本人強調の付いた行で、被撃破側のチーム色が秒ごとに入れ替わる。
- 項目が1回の読み取りだけ抜ける。被撃破者の名前も秒ごとに変わる。
- 本人強調の有無そのものも、同じ行で秒ごとに変わる。

#155 の数え方は、チーム色・名前・強調の組み合わせで新しい項目を判定するため、上記の揺れを別の撃破として数えていた。そこで次のように変えた。

- 新しい項目は、キラー側のチームだけで数える。同じキラー側の項目数が直前2秒間の最大値を超えたときに、超えた数を新規とする。本人強調は別の系列として同じ方法で数える。
- 撃破（上部バーの減少）を時刻順に並べ、それぞれに被撃破側が一致する最も早い未使用の項目を1件だけ割り当てる（減少区間の前後3秒以内）。本人強調も同じ方法で別に割り当てる。
- 1件の項目は1件の撃破にしか使わない。割り当てられなかった項目は誤読として数え（`feed_phantom`）、誰の撃破の根拠にもしない。
- 本人のキルは、本人強調（キラー側）が割り当てられた敵の減少で、本人が生存していた場合だけ `player` とする。

### 同じ証拠の重複利用の防止

- 1件のキルフィード項目と1件の本人強調は、それぞれ1件の撃破にだけ割り当てる。
- 上部バーの減少1人分は、本人死亡1件か `kill` Event 1件のどちらかにだけ使う。
- 取得フレームのSHA-256が、それより前の時刻ですでに使われている読み取りは捨てる（静止フレームの重複、`reused_frame_readings_dropped`）。同じ画像が前後の秒の安定性の確認を自分で支えないようにするため。

### `enemy_eco_likely`

敵チームの所持クレジットの上限を、得点の推移とゲームの経済規則から計算する。経済規則は知識基盤の `game_rules_v1.json` に出典（`community_economy_references`、複数の二次資料で一致）と検証状態を付けて追加した。

- 各前半・後半の最初のRoundの開始時、全員の所持額は800である。
- 録画者のチームがそのRoundに勝った場合、次のRoundの敵1人あたりの平均所持額は、多くても「800＋1敗目の敗北ボーナス1900＋スパイク設置300＋そのRoundの味方側の撃破数×200÷5」である。支出はなかったものとして上限を取る。撃破数は上部バーから読めた場合はその値、読めない場合は10とする。
- この上限が最も安い標準のフルバイ（ライフルの最高額2900＋ヘビーシールド1000＝3900）を下回れば、敵はフルバイできない。そのRoundの購入フェーズのEventに `enemy_economy` を付け、FactBuilder が `enemy_eco_likely=true`（信頼度0.8）を導出する。
- 拾った武器、所持額の偏り、生存者の持ち越しがあるため、フルバイできることは証明できない。そのため `false` は出さない。最初のRound（ピストルRound）自体には付けない。
- 得点は共通タイムラインの得点の多数決（#164 の `round_meta.score_before`）を優先し、ない場合は上部バーの得点読み取りを使う。読み取りは次の秒と同じ値で、合計がRound番号−1になるものだけを票にし、3票以上かつ60%以上を必要とする。両方がある場合に食い違えば使わない。

### 射撃（#169）

射撃は、共通タイムラインの `hud_observations` にある弾数（`ammo_current`）と予備弾数（`ammo_reserve`）から作ります。この2つは #169 がタイムラインの行に加えた読み取りで、`viewed_HUD; recorder_ownership_unresolved` のまま届きます。本人の弾数かどうかは、タイムラインの観測で決めます。

- 対象は確定したRoundの中で、`camera_state=SELF` と `life_state=ALIVE` がどちらも観測（OBSERVED）の秒だけです。特徴量のHUDエージェントが読めていて本人と違う秒は除きます。
- 1秒の中で値が1つに決まり、確信度が `ammo_min_confidence`（0.9）以上の読み取りだけを使います。
- タイムラインが弾数を読めていない秒は、同じ #169 の読み取り器がその秒のキーフレームで読んだ値（特徴量と `--ammo-only` の予備弾数）で補います。補うのは、特徴量のHUDエージェントが本人と一致する秒だけです。どちらの読み取りを使ったかは `ammo_sources` に記録します。
- 隣り合う読み取りの変化を #169 の `classify_ammo_change` で分けます。弾数が減って予備弾数が変わらなければ射撃です。予備弾数が減って弾数が増えればリロード、それ以外に予備弾数が変われば持ち替えです。リロードと持ち替えは射撃にしません。発射速度の上限より速い減少は誤読とします。
- 読み取りの間隔が3.5秒を超える場合や、本人視点が途切れた場合は比べません。
- 予備弾数が片方の端で読めていないと、別の武器の弾倉への持ち替えが射撃に見えることがあります。両端（または1秒外側）の武器名が違う場合と、両端から3秒以内で最も近い予備弾数の読み取りが違う場合は、射撃にしません（`shot_weapon_changed`、`shot_reserve_changed`）。
- Round最初の射撃と、3秒以上空いた後の射撃を `first_shot` とします。#169 の60fps交戦区間フレームがある場合は、初弾をフレーム単位で特定して `first_shot_frame_sec` に記録します。
- 武器名は、同じ秒のタイムラインの武器読み取りが1つに決まり、知識基盤の武器名に対応する場合だけ付けます。
- `shot` Event（actor は本人、信頼度0.8）から、FactBuilder が `first_shot_detected` と `weapon` を作ります。移動の判定は #169 の目視確認を通っていないため、`shot_while_moving` と `first_shot_stationary` は作りません。
- Event Source Contract の `shot` は、HUDの弾数の減少を認めるように `hud_or_visual_analyzer` に変えました。

検算は2つです。`shot_vs_feature_ammo` は、タイムラインの読み取りだけで作った射撃について、特徴量の弾数も減っているかを見ます。タイムラインの秒は1秒の中のどこかで読まれるため、前後1秒を含む区間で減っていれば一致とします。区間の中で減っていない場合は、射撃より確実に前（開始の秒以前）と確実に後（終了の秒の1秒後以降）の読み取りを比べ、同じ値なら不一致、増えていれば（リロードや持ち替えを挟むため）判定しません。特徴量で補った射撃は同じ読み取りどうしになるため `feature_sourced` として数えません。`recorder_kill_has_shot` は、キルフィードが本人のキルとした撃破の区間に射撃があるかを見ます。

### 交戦開始とスキル使用

- `engagement_start`：昇格した射撃のうち初弾（Round最初、または3秒以上空いた後）ごとに1件作ります。時刻は初弾の秒で、60fpsフレームで特定できた時刻を `start_sec` に記録します。分かるのは「本人が撃ち始めた」ことだけです。属性 `observed` は `recorder_started_firing` で、`not_inferred` に敵の視認、ピーク、プリエイム、交戦終了、相手を挙げます。敵の人数や味方のトレード距離の属性は持たないため、FactBuilder は `tradeable_ally_nearby` や `preaim_lead_sec` を作りません。
- `utility_used`：確定Roundの交戦中、本人視点・本人のHUDの秒で、スキル枠（C・Q・E・X）の #155 の充填の読み取りが変わったときに作ります。条件は次のとおりです。
  - 直前の2回の読み取りがはっきり使用可能（0.6以上、Xはさらに `ultimate_ready_charge` 以上）。
  - その後 `utility_spent_hold_sec`（8秒）のすべての読み取り（4回以上）がはっきり使用済み（0.1以下）。
  - 使用可能の最初の読み取りから保持の終わりまで、すべての秒を `hold_trace` に記録します。各秒は秒、状態（available・spent・missing）、充填値、根拠フレームを持ちます。
  - 読み取りのない秒は `missing` として記録し、`missing_seconds` に並べます。値は補いません。2秒続けて欠けたら証明できないとして見送ります（`utility_hold_missing_readings`）。
  - 途中で本人視点でなくなった秒（ドローン、観戦など）があれば見送ります（`utility_hold_view_interrupted`）。本人以外のHUD（`utility_hold_hud_not_recorder`）、Round終了をまたぐ保持（`utility_hold_past_round_end`）、使用済みの読み取りが4回未満（`utility_hold_too_few_readings`）も同じです。
  - Event の根拠参照は、`hold_trace` のすべての根拠フレームです。
  - 8秒以内に戻るアイコン（強調表示、HUDの減光、誤読）は使用にしません（`utility_use_not_held`）。2回使えるスキルの2回目のように中間の値になるものは、推測せず見送ります。
  - 購入フェーズはRound開始より前なので、購入や売却は使用に数えません。
- スキル使用ごとに、直前のアルティメットの状態を `ability_state`（スロット3）として記録し、FactBuilder が `ultimate_available` を作ります。
- Event Source Contract の `engagement_start` と `utility_used` を、上記のHUD由来でも作れるように `hud_or_visual_analyzer` に変えました。敵・味方のスキルとその効果範囲は対象外です。

### 本人死亡の見落とし補完

観戦への切り替えで判定できない本人死亡を、次の条件をすべて満たす場合に限って昇格する。そうした死亡は2つの場面で起きる。本人が最後の生存者でRoundがすぐ終わる場面と、観戦表示が数秒遅れる場面である。

- 共通タイムラインで本人視点・生存が最後に観測された秒 L の後、Round終了まで本人視点・生存が観測されない。
- [L−1, L+3] に上部バーの味方側の減少がちょうど1回ある。
- L の後に観戦視点が観測されているか、その減少で味方が0人になっている。
- そのRoundにまだ本人死亡がない。

### DOWNED・復活

- 生存状態の DOWNED は死亡として扱わず、秒数だけを数える。
- 本人死亡の後、同じRound内で本人視点・生存が5秒以上続いた場合は、死亡Eventに `revived_at_sec` を記録する。上部バーで味方数の増加が3秒以上続いた場合も、復活として数える。

復活の後に本人視点のHUDが生存を示すのは当然なので、上部バーの味方人数が死亡から復活までの間に増えた場合だけ、復活として裏付けがあるとします（`revive_corroborated_by_top_bar`）。共通タイムラインの検算（`verify_promotion`）は、裏付けのある復活を `revived` と数え、裏付けのない場合は従来どおり死亡の誤りとして数えます。

### APIなしでの採点可能性

- レポートの `scorability` で、確定Roundの候補ルールごとに次の4区分を数える。`deterministic_decided`（決定論エンジンが判定済み）、`ready_for_api`（必要Factがすべて0.55以上でそろい、AIコーチの判定を待つ）、`low_confidence`、`missing_facts`。`ready_for_api` はラベルではない。
- AIコーチ（API）を使わない経路では、決定論エンジンが同じラベルを出したもの以外の GOOD/IMPROVE をすべて UNSCORED（`other`、「AIコーチ（API）を実行していないため採点していません」）に変える。モックの判定を正式な採点として保存しない。

### 読み取り器どうしの検算

人手の正解ではなく、別の読み取り器との整合で検算する（`cross_reader_checks`）。

- `first_death_vs_kill_feed`：上部バーから導いたファーストデスと、割り当てたキルフィード項目のうち本人の被撃破が最も早いかどうかが一致するか。
- `recorder_death_vs_kill_feed`：本人死亡に対応付けた減少に、本人強調（被撃破側）が割り当てられているか。別の減少に割り当てられていれば `disagree` とし、撃破順の証拠を付けない。
- `recorder_death_recall`：上部バーで味方が0人になったRoundに、本人死亡が昇格されているか。
- `side_defense`：守備と判定したRoundに、本人視点のスパイク所持表示がないか。
- `top_bar_vs_kill_feed`：上部バーの撃破すべてにキルフィード項目が割り当てられ、余った項目がないRoundを `agree` とする。合計は `feed_assigned`、`eliminations_without_feed`、`feed_phantom` に出す。
- `score_timeline_reader_agree`：共通タイムラインの得点と上部バーの得点読み取りが両方あるRoundで、一致した数。食い違いは `score_timeline_reader_conflict` に数える。

### 計測時の重複防止

`scripts/measure_formal_promotion.py` は、同じ元動画（SHA-256）の入力を1件だけ数える。HUD値つきのフル版をreplay版より優先し、除外した入力は `duplicates_skipped` に記録する。特徴量ファイルは中のSHA-256で入力と自動的に対応付ける。`--catalog` を渡すと、共通タイムラインのない録画を `recordings_without_timeline` に列挙する。

### 開発用の昇格と独立資格付けの区別

結果は3段階で区別する（`docs/rule44_coverage.md` と同じ分類）。

| 段階 | 印 | 採点・保存 |
|---|---|---|
| 開発候補 | `dev-` 接頭辞、`development_only` | 採点と保存から除外 |
| 共通タイムラインからの昇格 | `tl-` 接頭辞、`qualification: promoted_from_shared_timeline` | 開発用の評価経路で使う。閾値は開発用36試合で較正した運用値 |
| 独立資格付け | `independently_qualified` | 未露出の独立評価用録画での合格が必要。該当録画がないため現在0件 |

ここで使う信頼度は、開発用録画で整合性の条件を通った読み取りに付ける運用値である。レポートには `independent_qualification: not_met_development_only` と記録し、独立資格付けの結果としては扱わない。評価レポートの `result_tiers` に3段階それぞれの件数を出す。`tl-` のEventがすべて `promoted_from_shared_timeline` の印を持つことも数えて確かめる。
