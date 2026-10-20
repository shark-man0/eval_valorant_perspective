> Historical investigation snapshot: 2026-10-19, before safe recovery PRs. HEADs, CI states and planned dispositions below are historical, not the final integration status. See `match_002_recovery.md` and its linked PRs for adoption status. H1 remains an unapproved, unimplemented experiment.

# match_002 Geometry調査の収束報告

調査日: 2026-10-19。対象は既存失敗の原因分類と、次の実験1件の計画まで。
新しいmask/template/matcherは実装・生成していない。正式qualification、認識改善、
Full E2E成功、本番採用を宣言する報告ではない。

## 1. 現在のHEADとCI

- 作業HEAD: `1f3edf094634037747928021c0ca9169f02928f8`、
  `work/match002-geometry-qualification`。調査開始時clean、originと一致。
- fetch後のmain: `ba90c0ba05185642265d269979d7a0cb25c9e517`。
  main固有2commit／作業ブランチ固有54commit。mainを変更・mergeしていない。
  mainの追加はPR #55のsource integrity preflight（3ファイル）で、認識変更ではない。
- 作業HEADの[Linux CI](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/38862849747)
  と[Windows CI](https://github.com/shark-man0/eval_valorant_perspective/actions/runs/38862849722)
  はGETで`completed/success`を確認。Windowsはpytest、UTF-8無効テスト、Ruff、mypy、
  PyInstaller、packaged smokeまで成功。過去のpath fixture失敗は解決済み。
- 最新mainのCIは確認時点ではLinux `39191641470`／Windows `39191641568`が実行中。
  作業HEADの成功を新mainの結果には転用しない。
- プロセス一覧で実行中のE2E/Analyzer/Evaluatorなし（確認コマンド自身を除く）。
  今回も新しいFull E2E・動画decode・matcher replayを起動していない。
- 元動画の実SHAを再計算し、下記source SHAと一致。base profile全23asset、
  candidate全6asset、combined profile全36assetが存在し、candidate凍結hashも一致。

今回のMac確認: 関連pytest **131 PASS**、CIと同じ範囲のRuff PASS、
production mypy **134 files PASS**。既存テスト・threshold・assertionは変更なし。
これはunit/integration/synthetic確認であり、Windows実動画の改善検証ではない。

## 2. Geometry認識の現状と証拠の結び付け

主問題は、正しい固定形状が見える画像でも3つのanchorが同時にNCCを超えないこと。
ただし旧Fullは別profile・別codeであり、現在の候補の認識率とは比較しない。
Geometryが成立しても本人identity、reader qualification、Round境界成立は別条件である。

主要なbinding:

| 記号 | 意味 | SHA-256 |
|---|---|---|
| S | 元動画 | `55d909c2d6a5f38575d1cb6c249ddfa7e2a48b96535841317adcae704c6f63b6` |
| P | candidate-only profile | `61f9ffe367e0544c00eebf536c5ca0c589e7bf4b046b3be5299ec7444dc882e2` |
| PA | Aの別Analyzer試行profile（identity等を含む） | `e45416816dca2f269ce6b748697f3e5e8b218c5d23369b844e7f1484858c1562` |
| PD | Dのcombined Analyzer profile | `b751fb55c8f7995107c5554787f41daf63f9634dc60dd9935db3ea03e324efe5` |
| PB | 現在も読める元base profile | `253a571ecff51dd1043ef9469af27df2644f3bc7647581b7919af4e559183511` |
| PE | 旧Fullの記録されたrun/settings binding（PBと別のhash方式） | `2611cfecc2b148e381d760290c14d70a060efcea2bd837657fe55627ef75554b` |
| G | 現在のglobal recognizer | `7c3654fc4f34b46633c01d61017458c959e5b5cae13b4d5915937f16c2467381` |
| GD | Dの歴史的global recognizer | `87f4bcea8b1699dbad965b634b06ebd4095dbb4519bd55ac4b8495b1d486e008` |
| RA | Aの別Analyzer試行／旧Fullの歴史的runtime-code hash | `211864cb232a1c26d661229c09ffe8c7f350151d6ab7485ce9db66a9f8d7f3bf` |
| Asset P | candidate asset manifest | `2d49ff3e049b7ff8203e2cb5cbb3ad8c2012a322f5a0d107e81a3b97e74cc669` |

各hash方式のscopeは異なる。RAをGと同じ方式と扱わず、旧結果をGで再実行したとはしない。
Aの生成codeはcandidate_report内のbuilder hash
`e3d1a4ed1d7ecc498e2bbcdaba658baf3a464928f8614a60ab2a94415d9561d5`で記録。
Bの凍結計画には**global recognizer hashが保存されていない**。
matcher script hash `d9357b07039f60a21f49f71ff53ea6bea6550372bc73b3cdbb02ce4e5ec1ec51`
と凍結計画hashで結び付け、GDやGを事後注入しない。

ローカルの新規調査記録:
`outputs/match_002/geometry_convergence_20261019_v1/evidence.json`
（SHA `d3c66cb93162cab967d6191e3417e02cc51fde690c88b0a2a3f70a540cf0b4fc`）。
元の観測、入力hash、全sample PTS、score集計、nullの未記録項目を保持する。
保存結果のreductionと既存trainingの構造測定であり、新しい認識実行ではない。
画像・詳細PTS・ラベル・ローカルpathはGit共有しない。

## 3. 評価集合別の認識結果

| 集合 | 画像数／unique | 独立Geometryラベル | Raw fresh | Gradient fresh | Retained / Effective |
|---|---|---|---|---|---|
| A: Candidate v3 | 24 / 22 encoded | positive24（unique22）、negative0 | 3/24 | 未測定（B参照） | 別Analyzer試行PAでretained10 / effective13、fresh3 |
| B: 固定Gradient比較 | Aと同じ24 / 22 | Aと同じ。追加標本ではない | 3/24 | 12/24（unique12/22） | 未実行 |
| C: 別の人間レビュー | 13 / 13 encoded | positive12、negative1、unknown0 | positive3/12 | positive3/12 | 未実行 |
| D: native区間 | 205 / 205 pixel hash | 未レビュー205。positive/negative不明 | 7/205 | 83/205 | Raw combined PDでretained24 / effective31。Gradientは未実行 |
| E: 旧Full | 13,287 JPEG / 13,166 encoded | Geometryラベルなし | 0/13,287 | 未実行 | retained0 / effective0 |

全てsource S。A/BはP、CはP/G、Dのmatcher比較はP/GD、別AnalyzerはPD/GD。
Eはcommit `c11ec6d333957cccb270417bc95a8a57f433e6ad`、RA、PEを保持する。
A/B/Cは孤立sample点でsource連続性を証明しない。Dはsource所有の整数PTS・timebase・
全205pixel hash一致と隣接cadenceを確認した区間だが、scene continuityの正式資格ではない。
Eは全体の疎なsample scanで、native連続性検証ではない。ユーザーの「未編集」来歴は別証拠。
private記録にはA/B/Cの全PTS、Dの全整数PTSとtimebase、Eのファイル名由来の丸めPTSを区別して保存。
Eのencoded unique数は今回ファイルbytesをhashした数で、decoded raster unique数は不明。

False reject: A Raw21/24（unique19/22）、B Gradient12/24（unique10/22）、
Cは各9/12。Cの自然負例は両方0/1 false accept。
A/Bに自然負例がないため自然false acceptは未測定。Bのanchor ablationは0/72受理
（unique source+removed-anchorは66）で、自然負例の代用ではない。
D/Eはラベルがないためacceptanceをaccuracy/false rejectに変換しない。
EはAnalyzer exit2で中断、Visual・Round Package・Evaluator未実行。E2E PASS数は存在しない。

計測可能性とlayout:

- Aの3anchorはscore取得不能0、3scoreが閾値以上なのにlayoutがrejectした件数0。
- Bの3anchorはscore取得不能0、3score受理後layout reject0。
- CのGradientはscore取得不能0、3score受理後layout reject0。
  Rawのanchor別score分布・取得不能数は保存されておらずnull。再計測で補わず欠落を明示。
- Dの設定済み3anchorはRaw/Gradientとも取得不能0、Gradientの3score受理後layout reject0。
  未設定top_match_barの205 unscoredを、設定済み3anchorの失敗へ加算しない。
- Eの4anchorのscore取得不能0、HP/abilitiesは受理0で3anchor段階へ到達しない。

保存scoreはNCC similarityでありAI confidenceではない。下表はmin / median / max、丸め表示。

| 条件 | timer（受理数） | HP/armor（受理数） | abilities（受理数） |
|---|---|---|---|
| A Raw24 | .3051 / .8427 / .9871（9） | .6198 / .9041 / .9879（16） | .8270 / .9666 / .9976（21） |
| B Gradient24 | .4196 / .9150 / .9957（12） | .8445 / .9464 / .9731（23） | .9036 / .9534 / .9780（24） |
| C Gradient positive12 | .6009 / .8268 / .9915（5） | .8470 / .9476 / .9727（10） | .9187 / .9574 / .9764（12） |
| D Raw205 | .3604 / .6593 / .9797（54） | .4188 / .8578 / .9850（51） | .7630 / .8227 / .9970（38） |
| D Gradient205 | .4725 / .9651 / .9964（177） | .7048 / .9039 / .9663（107） | .9115 / .9526 / .9778（205） |
| E Raw13,287 | .0000 / .7694 / .9181（32） | .0000 / .5014 / .7580（0） | .0000 / .2929 / .6048（0） |

Eのtop_match_barも.0000 / .3262 / .5071、受理0。元baseのgeneration時にtop barが
独立supportを得ていても、別動画Sの実行時に一致する証明ではない。

## 4. 主要アンカー別の阻害要因

- **timer:** Bではtimer単独不足11件、timer+HP不足1件。CではGradientのtimer単独不足7件。
  正しい固定構造が見えることは人間確認済みで、数字非表示を「正しいabstention」と再解釈しない。
  現在のGradient supportは139pxと小さく、微小補間で失敗する。
- **HP/armor:** Bの不足1件に対しDでは単独94件、timerとの併発4件。
  Cでも単独2件。不十分なsample一般化は確認済みだが、その全てが同じ物理原因とは未証明。
- **abilities:** B/C/DのGradientでは全件anchor受理。ただしtraining参照の微小移動には弱い。
  現在の集合で受理できたことを未知場面の安全性には転用しない。

要求された9分類:

| 原因候補 | 現時点の判定と証拠 | 次の扱い |
|---|---|---|
| 1. 見える固定構造でもNCC不足 | **確認済み**。AとCの人間確認正例でfalse reject | 特徴・supportの実験対象 |
| 2. maskが動的内容へ依存 | **未証明**。既存exclusion違反0、Aのmask固定形状レビュー承認済み。輝度変動だけで数字混入とは断定不可 | training構造統計と将来の追加bandレビューを分離 |
| 3. サブピクセル／補間感度 | **syntheticで確認済み**。実動画の全失敗原因であるとは未証明 | 既存stressを最初の安価なgateへ |
| 4. 参照と実画像の描画差 | trainingの輝度変動とsynthetic感度が仮説を支持。実映像の因果・圧縮/描画/透明背景の内訳は未確定 | 1候補だけで反証可能に試す |
| 5. support不足 | 現在は139/872/597で全て64以上、B/Dでunscorable0。平滑化を足すとtimer8で**確実に不足** | 無根拠な平滑化を却下 |
| 6. 探索範囲不適合 | Aでは設定位置scoreと探索maxが概ね一致、画像上の位置もレビュー済み。Dでも不適合の証拠なし | 拡張しない。将来wrong-locationを検査 |
| 7. anchor間layout不一致 | B/C/Dの3score受理後reject0。現在の主要因ではない | 3-inlier/位置/scale条件を維持 |
| 8. 実際に固定構造がない | **Cの1枚だけ人間確認**。D/Eのrejectから欠落を推測しない | 未ラベルはunknown |
| 9. source/配置/profile不一致 | 現在のsource/凍結candidate hash一致。Eは別profile由来の失敗で、A/Bと同条件ではない | 歴史的bindingを保持、付け替え禁止 |

## 5. 改善すべき特徴表現の問題

生成側は28枚のCanny edgeの位置persistence >=.65、unsigned orientation一致 >=.90を使い、
1px膨張してraw maskを作る。一方、診断matcherはsigned Sobel方向をNCC比較し、
除外領域を畳み込まないよう1px erosionする。このため**安定edgeを見つける条件と、
実際に比較する信号が同じではない**。raw NCCは輝度を比較し、signed Gradientも
薄いsupport上での方向変動・補間に敏感。極性だけをunsigned化すれば解決とも言えない。

今回、新しい候補を作らず既存training28枚だけを読んだ追加測定:

| 指標 | timer | HP/armor | abilities |
|---|---|---|---|
| raw mask / Gradient support | 387 / 139 | 1640 / 872 | 1023 / 597 |
| raw mask内の同一点Canny persistence>=.65 | 32.56% | 33.60% | 34.31% |
| support内のstrongかつunsigned方向安定 | 82.73% | 82.57% | 69.35% |
| raw mask内輝度の時間std中央値（8bit） | 57.85 | 32.36 | 41.41 |
| unsigned安定だがsigned不一致のsupport画素 | 7 | 2 | 18 |

strongはSobel magnitude>=16、28枚の65%以上でstrong、unsigned coherence>=.90。
signed不一致はcoherence<.90。画像選別・stateラベル・GT・reviewed画素は使っていない。
膨張maskにはedge両側が含まれるので32〜34%を「残りは動的内容」と解釈しない。
これらは時間的一貫性のproxyであり、**意味的な固定UI比率そのものは未測定/null**。
極性だけの不一致は少数で、unsigned化単独を次の実験にしない。

既存trainingのscore分布も保持する。Rawはcandidate生成時の**設定位置**NCC、
GradientはBの**検索後max**であり、同一score方式・同一分布とは扱わない。

| training28、min / median / max（閾値通過数） | timer | HP/armor | abilities |
|---|---|---|---|
| Raw設定位置 | .0000 / .8464 / .9880（13） | .1684 / .9178 / .9883（18） | .5297 / .9837 / .9974（22） |
| Gradient検索max | .4766 / .9717 / .9963（21） | .4392 / .9396 / .9800（25） | .4566 / .9583 / .9782（24） |

Bのtraining検索＋layoutまでの全体受理はRaw8/28、Gradient20/28。
この28枚は学習に使った画像であり、独立positive accuracyではない。

保存済みstress（参照だけ、各15変換）ではRawは全anchor12/15、Gradientは9/15、6/15、6/15。
JPEGなしでもtimerは.5/.75px、HP/abilitiesは.25/.5/.75pxの線形補間移動でNCC<.90。
探索は整数座標であり、薄いedge supportと離散微分が描画位相に弱い、という具体的失敗形。
実動画に同じ変換が起きたという証明ではない。

3x3平滑化+3x3 Sobelなら依存半径2が必要で、現在maskの安全supportは8/220/239。
除外後の空間的上限は半径2で1408/239/26792だが、背景も含む上限であって固定UIではない。
この上限を新しいmaskとして採用することは禁止する。

## 6. 推奨する単一の改善実験（承認待ち、未実装）

**仮説H1: 既存固定edgeの周囲に、除外規則と時間的一貫性を保つ最小1pxの余裕を
追加できれば、同じsigned Gradient NCCの描画位相への感度を低減できる。**

実験名: `training_fixed_edge_band_plus1_v1`。新matcher、平滑化、template変更、
検索範囲拡張、reference bank、Raw/Gradient ORは行わない。変えるものはmaskの幅1項目だけ。

承認後に限る手順:

1. 現在のS/P/asset manifest/exclusion/code/28枚のhash、順番、実験定数を新規計画へ凍結。
   読込可能な画像入力をこの28枚と既存3参照だけに制限する。
2. 各既存maskを3x3全1kernelで**1回だけ**膨張（既存edge-bandから外へ最大1px）。
   `content_mask`を既存v2 exclusion・元reader field・padding4・HP enclosureのまま再適用。
   digits/iconを使えるようexclusionを変更しない。元templateは完全に同じbytes。
3. 今と同じ1px erosionで3x3 Sobel依存を完全にmask内へ閉じ、同じfixed matcherを使用。
   64px未満、定数/非有限値、どれか1anchorでsupportが増えない場合はこの候補を打ち切る。
4. 新supportの上記strong/unsigned安定比率が、各anchorで今回のbaseline以上であること。
   追加bandの動的content混入を独立レビューで否定できない場合も不採用。
   空間的に許容されるだけの画素を安定と呼ばない。
5. 既存15変換/anchorの固定stressでGradientが各12/15以上、JPEGなしの全5移動が受理されること。
   現在のtraining20/28の受理集合を全て保持し、少なくとも1枚増えること。
   28枚は未ラベルなので「training positive recall」とは呼ばない。
6. 全training画像のanchor別NCC min/median/max・support・推定位置・layout判定を保存。
   各anchorを消す84件のsource-derived ablation、flat/noise、既存許容誤差外のshift、
   decoy位置、除外領域だけを変えるcontrolで誤受理・除外漏れ0を要求。

どれか不成立なら**1候補で終了**し、幅2px/別kernel/別thresholdの探索へ進まない。
上記数値は実験を続けるための事前gateであり、productionの受理基準変更ではない。
通過しても追加bandの意味的な固定構造の確認と独立negative検証までは本番不採用。

## 7. 実験の安全条件

NCC>=.90、最低3anchor、最低64 support、現行位置/scale/3-inlier validationを維持。
3anchor全て受理しない限りgeometry成功にしない。GT、Validation Pack、期待state、
最終holdout、A/B/C/Dの評価画素で候補生成・parameter選択しない。
source/profile/code/hashは前後照合し、不一致なら中止。新候補には新fingerprintを発行し、
旧結果はそのまま保存。geometryからidentityへ証拠を流さず、remote/spectator/menu/map
抑制、unknown処理、ownership、temporal continuity条件は変更しない。
実験承認はproduction採用承認ではない。現時点では実験自体も未承認・未着手。

## 8. 必要な独立Positive/Negative

training gate通過後にのみ、凍結済みのdevelopment A/B/Cを**regression**として1回比較。
改善を確認できなければ停止。A/Bは同じ22uniqueであり二重加算しない。
Cのpositive12でGradientの既存3件を失わず1件以上改善し、negative1の誤受理0を維持すること。
A/Bでも既存Gradient受理12件を失わず1件以上改善すること。結果を見てmaskを直さない。

さらに新しい独立検証が必要。今回その画像は取得も選別もしていない。
final holdoutをdevelopmentへ移動せず、未使用developmentの可用性とexposure履歴を先に点検。
不足なら別の連続録画を使い、失敗matcherからpositive/negativeを選ばない。

- Positive: 最低12unique、3つ以上の独立episodeで固定UIと位置を盲検確認。
  背景明暗・動く3D背景・timer数字非表示を含む。画面stateではなくgeometryをラベルする。
- Natural negative: 最低12unique、各3例以上の4条件を事前登録:
  固定HUD全体がない、timer固定構造がない、HP固定構造がない、abilities固定構造がない。
  実際の表示が存在する場合はnegativeにしない。不足する条件をsyntheticで水増ししない。
- 別枠で実captureのcrop/letterbox/HUD-scaleずれ、類似形状decoy・他位置を検査。
  定量的に許容範囲外と確認した配置だけをmisalignment negativeとする。
  spectator/remoteや数字非表示は、固定UIが残る限りgeometry negativeではない。
- 人間確認は予測・score非表示、元source/画像hashと返信をbinding。unknownは分母から区別。
  全natural negativeでfalse accept0、未ラベルを正解扱いしない。

この最低数は小実験の工学的go/no-goであって、安全率やformal qualificationを保証しない。
既存qualification loaderの全split/unique/hash/reader/temporal要件は別途満たす必要がある。

## 9. Expected improvementと検証方法

期待するのは「小さな描画位相差を吸収し、timer/HPの同時受理を増やすこと」で、
予測認識率・Full PASS増加は提示できない。改善しない可能性を含む仮説である。
評価順は Unit → frozen training/stress → static development → independent natural negative
→ fixed targeted native → 必要な連続source → formal qualification → Full E2E。
training/staticで改善がなければ高コスト段階へ進まず、Fullを回さない。
Dの将来再比較では205個のPTS/pixel binding、3score後layout、fresh/retained/effective、
unknown原因を別々に記録し、83/205をaccuracyとして改善判定しない。
資格がない段階のgeometry改善だけでformal Start/Endを出さない。

## 10. コスト・処理時間の削減策

既存固定画像replay、`diagnose_geometry_gradient_ncc`のRaw/Gradient比較、
`summarize_anchor_scores`、`compare_geometry_controls`のレビュー照合、
`VideoService.native_window`/`native_replay`のsource入口とsynthetic stressを再利用可能。
今回の新しい汎用診断ツール追加は0。privateの一回限りの集計だけを実行した。

- matcher不変ならsaved score/observationをreductionし、video decodeやOCRを再実行しない。
- 24entry/22uniqueなどの重複はunique計算で重複加算せず、元entry集計も保持。
- 既存JPEGはstatic診断に再利用できるがnative source所有証拠へ格上げしない。
  native pixelが保存されていなければ、変更matcherのnative評価時だけbounded decodeする。
- 既存cacheはsource/probe/decoder fingerprintをキーにmetadata/PTSを再利用。
  native再生のメモリcacheは有界で、動画全体を保持する仕組みではない。
- 旧Fullは1975.64秒、decode720.24秒・Geometry1177.42秒を消費。今回同一条件の再実行0。
  Dの旧matcher比較38.92秒も再実行せず保存値を集計。候補失敗を静止画段階で止める。
- code/profileが変わったら旧数値はbaselineとしてのみ利用し、新codeの測定へ付け替えない。

## 11. PRへ統合できる変更と研究履歴の分離

70ファイル・54commitを一括認識リリースとしてmainへ入れない。履歴を削除・resetせず、
次の小PR候補に分ける。今回PR作成やmain mergeは行っていない。

| 分類 | 具体的な対象 | 方針 |
|---|---|---|
| A 独立安全修正 | `351b75c` spectator角度をfloat64で正確に計算する修正＋境界regression2件 | threshold/policy無変更の小PR候補。main起点で再テスト・own-HEAD CIが必要 |
| A test portability | `1f3edf0` held-review fixtureのnative Path選択 | そのtest/toolを移すPRに含める。単独mainには対象testがない |
| B 再利用検証 | `compare_geometry_controls`、`summarize_geometry_review`、blind review/hash照合、`9862fbf`不完全Round Fact/Trace integration tests | 既存mainのcontractに合わせて依存を最小化し、研究profileを同梱しない |
| C Candidate実験 | `build_geometry_candidate`追加、`geometry_enclosure_mask`、exclusions v1/v2、challenge | diagnosticsに隔離。productionへ配線しない |
| D 未採用Matcher | `diagnose_geometry_gradient_ncc`、soft-edge比較prototype | reference用途。factory/default profileへ登録しない |
| E 開発/失敗履歴 | 大きいqualification時系列doc、旧Full summary、棄却padding等 | 証拠として維持。認識成功・main必須機能とは扱わない |
| F 資格待ち | `numeric_regions.py`とtemplatesの明示opt-in、phase/result参照、native provisional証拠 | 自動採用しない。reader/temporal/negativeの独立資格が必要 |

PR責務はGitHubの最新body/filesを照合した:

- [#42](https://github.com/shark-man0/eval_valorant_perspective/pull/42) はopen、
  HEAD `d457d96ce1f1815ae6f9f0807c68d2852e2918ad`。match_001のsource-bound geometry初期化、
  reader/End条件、資格待ち研究を含む。別sourceの証拠をmatch_002へ転用しない。
- [#51](https://github.com/shark-man0/eval_valorant_perspective/pull/51) はopen、
  HEAD `5347f9a010e429d693e55966810ee83778676966`。sampled-frame prefix/binding/application、
  `analyzers.py`・`hud_video_processor.py`・`native_system_input.py`を担当。重複実装しない。
- source integrity preflightは[#55](https://github.com/shark-man0/eval_valorant_perspective/pull/55)
  でmainへ統合済み。新ツールを重複追加しない。
- 作業branchのproduction差分はspectator修正とnumeric opt-in（3ファイル）に限定。
  Gradientはdiagnosticsのみ。#42のtemplates変更とnumeric opt-inは同じfileなので、
  将来統合時に明示的なconflict確認と資格hash更新が必要。

## 12. 残存するRound lifecycle阻害要因

| 独立gate | 現在の証拠と未達 | 次の担当/条件 |
|---|---|---|
| Timer/Score設定 | 元profileではglobal取得不可。明示numeric opt-inで取得例あり | reader設定をGeometryと別に固定 |
| Numeric localization | bright_components_v1はopt-in、.90未満/不明文字はunknown | independent値/非表示レビュー、別ruleのscore研究と責務確認 |
| Reader資格 | 文字が読めることとcurrent profile/code資格は別 | disjoint train/held/negative、既存loaderの>=3unique等を全て満たす |
| Phase/Result | 購入/WON/LOSTの意味付け・bounded検出あり。独立temporal資格なし | native内の表示有無・時間遷移を証拠化 |
| Start | 最初の開始のprovisional例あり、次開始はgeometryによるprepare観測不足 | 既存安全条件、source continuity、reader/UI資格を保持 |
| End | paired scoreが3frame欠ける例、ally confidence .82476738<.90 | 欠落をbridgeしない。score/result/timer連続入力と資格が必要 |
| Identity/ownership | geometry成功でもHP/Ability/Weapon＋spectator exclusionが別gate | geometry証拠を本人証拠へ流用しない |
| Membership | 1つのprefixで不完全Package→Fact/Trace接続を検証、全23Round認識ではない | formal境界からmembershipを再検証。GTでRound ID/時刻を注入しない |
| Fact/Trace | synthetic integration9件を含む関連131件PASS | 認識された全試合Packageの保証ではない |

map calibration、Visual eligibilityも別gate。Eの未実行をCV独立故障と解釈しない。
Validation Pack、threshold、negative contractは今回一切変更していない。
**調査Goalは原因分類と単一実験計画の確定で収束する。H1の実装承認・本番採用・
formal qualification・Full E2Eは別の判断事項であり、今回の完了を認識改善と読み替えない。**
