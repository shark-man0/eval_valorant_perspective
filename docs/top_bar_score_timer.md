# 上部バーの得点・タイマー認識（共通タイムラインへの引き継ぎ）

開発用。正式なFact/Eventは作らない。

## 何をするか

- `knowledge/score_reader.py`：上部バーの味方・敵の得点と、ラウンドタイマー（m:ss）を読む。
- `knowledge/top_bar_timeline.py`：読み取り結果を、共通タイムライン（`temporal.game.DevelopmentGameTimeline`）の `observation` 形式の行にする。既存のラウンド読み取りと同じ欄（`context.score`、`context.timer_seconds`、タイマーが45秒を超えるときの `active` シグナル）だけを埋める。
- Roundの正本は共通タイムラインのまま。この認識器はタイムラインへ証拠を渡すだけで、Roundを決めない。

```python
from valorant_ai_coach.knowledge.score_reader import ScoreReader
from valorant_ai_coach.knowledge.top_bar_timeline import top_bar_observation

reader = ScoreReader.load(cache_dir)          # 非公開キャッシュのテンプレート
row = top_bar_observation(frame_bgr, native_sample, reader)
timeline.add(row)                             # 通常の供給元の観測として受け付けられる
```

## テンプレートと系譜

- 数字のテンプレートは、Riotが画像を配布していないため、開発用録画から作る（`scripts/knowledge/build_score_templates.py`）。
- 使えるのはTRAIN分割の録画だけ。ビルダーは継続学習のデータセット登録簿と元動画のSHA-256で照合し、TRAIN以外が1本でも混ざると `TemplateSourceRefused` で止まる。
- マニフェストに系譜（登録簿のSHA-256、各録画のsource_id・物理試合ID・元動画SHA-256・切り出しアーカイブのSHA-256）を記録する。読み取り側は、TRAIN限定の系譜がないテンプレートを読み込まない。
- Tesseractは開発時のラベル付けにだけ使う。アプリ本体は使わない。

## 精度（TRAIN以外の15試合から無作為抽出し、目視でラベル付け）

整合率（読み取り同士が矛盾しない割合）と正答率（人が見た値と一致する割合）を分けて測った。

| 指標 | 結果 |
|---|---|
| 得点：1フレームの正答率 | 160/160（100％） |
| 得点：1フレームで値を返した割合 | 160/236（67.8％） |
| 得点：補完後の時系列の正答率 | 219/221（99.1％）。誤り2件はRound終了直後で、新しい得点がまだ確定していない区間 |
| 得点：補完後に値がある割合 | 221/236（93.6％） |
| 得点：整合率（確定した読み取りのうち、得点が減らない並びに残る割合） | 各試合 98〜99％ |
| タイマー：1フレームの正答率（判定規則を決めた後の新しい抽出44枚） | 23/23（100％） |
| タイマー：値を返した割合 | 23/44（52％） |

## 共通タイムラインとの比較（タイムラインの書き出しがある10試合）

| 指標 | 結果 |
|---|---|
| 得点を少なくとも片方読めた割合 | 本認識器 77〜95％（5秒ごと）、タイムライン既存 54〜85％（1秒ごと） |
| 戦闘開始時刻（タイマーから逆算）とタイムラインのBUY→ACTIVE遷移の差 | 2秒以内 139/141（98.6％） |
| タイムラインの round_start イベント | 例：fm2_3 で 17Round 中 7 件。Round番号（得点由来）は全Roundにある |

規則側は、タイムラインのRound番号とイベントからRoundを組み立てる（`TimelineView.rounds`）。タイムラインの書き出しがない試合だけ、得点による仮のRoundを使い、`provisional_score` と明記する。

## Roundの4つの時点

`rules/round_phases.py` は次を別々に出す。

- `score_update`：新しい得点が初めて確定して読めた時刻（観測時刻であり、Round終了より数秒遅れる）
- `buy_phase_start`：購入フェーズのカウントダウンから逆算（第1・13Roundと延長は45秒、それ以外は30秒）
- `combat_start`：ラウンドタイマー（100秒）から逆算
- `round_end`：上部バーでどちらかのチームが全滅した時刻、または設置なしでタイマーが尽きた時刻。どちらも見えないときは次の得点更新を上限として、`score_update_upper_bound` と明記する
