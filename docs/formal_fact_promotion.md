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
