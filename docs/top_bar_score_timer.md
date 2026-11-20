# 上部バーの得点・タイマー認識（共通タイムラインへの引き継ぎ）

開発用。正式なFact/Eventは作らない。

## 何をするか

- `knowledge/score_reader.py`：上部バーの味方・敵の得点と、ラウンドタイマー（m:ss）を読む。
- `knowledge/top_bar_timeline.py`：読み取り結果を、共通タイムライン（`temporal.game.DevelopmentGameTimeline`）の `observation` 形式の行にする。既存のラウンド読み取りと同じ欄（`context.score`、`context.timer_seconds`、タイマーが45秒を超えるときの `active` シグナル）を埋める。
- 同じ行の `raw["values"]` に、読み取り値と確信度を入れる（`ally_score`、`enemy_score`、`timer`（m:ss））。`temporal.application` がこれを `hud_observations` の候補に変える。#164 の昇格器（`facts.timeline_promotion`）が読むのはこの欄で、Fact供給の窓口はここに一本化した。
- `knowledge/own_view_timeline.py`：表示中の視点の弾倉数（`ammo_current`）とスパイク所持（`spike_carried`）を、同じ形の行で渡す。どちらも表示中の視点の値なので、件名は `viewed_HUD; recorder_ownership_unresolved` のまま。録画者本人の値かどうかはタイムラインの視点判定が決める。
- 確信度は、各数字のテンプレート照合（正規化相関）の最小値。確率として較正した値ではない。昇格の閾値は #164 の `config/timeline_promotion_v1.json` だけが持つ。
- Roundの正本は共通タイムラインのまま。この認識器はタイムラインへ証拠を渡すだけで、Roundも状態も持たず、Factへの昇格もしない。

```python
from valorant_ai_coach.knowledge.score_reader import ScoreReader
from valorant_ai_coach.knowledge.top_bar_timeline import top_bar_observation

reader = ScoreReader.load(cache_dir)          # 非公開キャッシュのテンプレート
row = top_bar_observation(frame_bgr, native_sample, reader)
timeline.add(row)                             # 通常の供給元の観測として受け付けられる
```

## テンプレートと系譜

- 数字のテンプレートは、Riotが画像を配布していないため、開発用録画から作る（`scripts/knowledge/build_score_templates.py`）。
- 使えるのはTRAIN分割の録画だけ。ビルダー（`--registry` と `--catalog` が必須）は、切り出しアーカイブごとに次の4つを照合し、1つでも合わなければ `TemplateSourceRefused` で止まる（`knowledge/template_lineage.py`）。
  1. データセット登録簿：アーカイブの `video_id` が登録済みで、分割がTRAIN
  2. アーカイブのハッシュ：ファイルのSHA-256とサイズが登録簿の `archive_sha256` / `archive_bytes` と一致する。同じ録画から作り直したアーカイブや、項目を足したアーカイブは通らない
  3. 録画カタログ（`recordings.catalog`、ジャーナルを再生して整合性を確かめる）：登録簿の元動画SHA-256の録画があり、開発利用が許可され、独立評価用に保留されておらず、学習用の小分割（`learning.split`）がTRAINで、登録簿の同じsource_id・物理試合IDに結び付いている
  4. 元動画：アーカイブの切り出し元のファイル名とサイズがカタログの原本の記録と一致する。`--video-hashes` を渡すと、別に計算した元動画のSHA-256とも照合する
- マニフェストに系譜（登録簿のSHA-256、カタログのジャーナル先頭ハッシュ、各録画のsource_id・物理試合ID・元動画SHA-256・アーカイブSHA-256・カタログの録画ID・学習分割の由来・原本のファイル名とサイズ）を記録する。読み取り側は、TRAIN限定の系譜がないテンプレートを読み込まない。
- この照合を入れたところ、以前のテンプレートは21本のTRAIN録画のうち5本（fm3_9、fm4_3、fm4_4、fm4_5、fm5_3）で、登録簿と異なるアーカイブ（キルフィードの切り出しを足した作り直し版）から作られていたことが分かった。登録済みのアーカイブから作り直した結果、得点と弾倉の数字テンプレートはバイト単位で同一、スパイクの見出しテンプレートは平均した枚数が341枚から200枚に減り、画素値が最大3階調変わった。
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
