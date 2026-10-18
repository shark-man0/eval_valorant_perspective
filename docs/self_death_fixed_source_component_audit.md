# Self Death：固定実画像によるRole・Reportの検証

判定は **B**。正しいSelf／RoleとReport fieldの実測は増えたが、独立したDeath資格付け、
正式Event、現コードによるcanonical FAIL削減は未達である。
開始mainは `7e480c2f2f7f49aea73e1541d065d78881d2f11c`、開始ブランチは
`fe772dbe321231d5b53378821a945965e1c82d68`。PR #53は引き続きPR #52上のDraft stack。
本変更は診断評価器・テスト・レポートで、production reader、profile、asset、qualification、
confidence、所有権、temporal horizon、GT、assertion、samplerは変更していない。

## 入力と分割

移行済みの第2録画から、元のnative keyframe全2,245件のindex
`floor(i * 2245 / 192), i=0..191` を固定して192件を取得した。
選択に認識の成功、名前、GT、正解時刻を使っていない。reader・profile・assetを先に固定し、
全16枚のcontact sheetを目視してsource labelを保存した後、全192入力を認識した。
元のPNGは変更していない。表示用sheetはreaderや参照画像へ渡していない。

ただし、全フレームに過去のcaption crop探索によるexposureがあり、さらに古いglobal geometry
の利用履歴は不明である。**新規blind holdoutとは呼ばない。**
既知のnative episodeや既知full-image contextから前後15秒の範囲を保守的に既知群に含めた。
既知群71件、既知episode記録なし群121件である。記録がないことは未使用の証明ではない。
途中でfull-image contextの既存記録も照合し、認識前のreviewへ追加した。
既知episode群だけを除いて都合のよい検出率を報告しない。

隔離したkeyframeは静的componentの入力であり、連続性やDeath時刻の証拠ではない。
full E2Eのsamplerやnative temporal replayを変更していない。新しい動画は転送していない。

## Self・Roleの実測

| 指標 | 実測 |
| --- | ---: |
| 評価したnative静止画 | 192 |
| 目視で確認したSelf行 | 15 |
| 正しいSelf marker / Role出力 | 11 / 11 |
| 正しいSelf Killer / Self Victim出力 | 6 / 5 |
| 目視Self行に対してmarker未検出のまま保持 | 4 |
| 誤ったSelf marker / Role出力 | 0 / 0 |
| 正しく読めた本人名 / 誤読 | 10 / 0 |
| victimのうちnumeric weapon NCCもあるもの | 2 |
| Selfがないと確認できた静止画 / 出力なし | 176 / 176 |
| 追加の描画途中行が判定不能な画像 | 2 |
| 異なるPTSでの同一full-image pixel hash | 1組 |
| 正式Death Event | 0 |

2件の描画途中行は成功した負例へ含めない。一方の画像には既知Self行もあるため、
この表の各行は排他的な画像分類ではない。名前未検出もwrongや成功へ埋めない。
正しいRoleが出た11行はmarkerの3 NCC・黄色支持を持ち、別行の同じRoleで代用していない。
victim 5行のうち3行はgeometryのみで、numeric releaseのweapon NCCを満たさない。
正しい5つのvictim静止画はすべて既知の死亡episodeであり、新規独立Death 5件ではない。

既知群では9行が正しく出力され、1行が未検出。記録なし群では2行が正しく出力され、
3行が未検出だった。後者の成功2行はいずれもSelf Killerである。
これらをSelf Victimの独立qualificationへ読み替えない。NonselfをSelfとして出力していない
という範囲の負例結果であり、Teammate／Enemyの新規意味分類を完成させたわけではない。

またcase005の事前freeze（`4e1fbe3`）と現在を照合し、source照合からmarker検出・
反転照合・黄色支持までのreader部分、`_matches` / `_iou`、全marker配列、marker設定が
byte／array単位で不変であることを確認した。case005をmarkerのcomponent試験として扱う際の
依存範囲は限定できる。一方、このcaseは後のweapon参照追加と名前layout修正にも使われたため、
その変更やreader全体の独立holdoutにはできない。部分的な不変性から全資格を付け替えない。

未検出4例では、同じ行付近を元の参照と反転参照でread-only診断した。
最大NCC候補を見ても、元の3 NCCと黄色支持をすべて満たす候補はなかった。
最大値の位置が本当の本人markerとは限らないため、その値を「本人confidence」とは呼ばない。
新しい参照の追加、閾値緩和、identity昇格は行っていない。

異なるPTSで全pixelが同じ画像1組も検出した。静止画2件から停止期間や原因は確定できない。
録画時のフレーム重複の可能性を残し、未編集契約を連続取得の保証として使わない。

## Weapon separator単体の別測定

固定192件のうち完全な2ページ、24件を選び、全行のpictogram種別を目視で保存してから、
元の `_matches` NCC 0.90とplate 0.90をそのまま使って測定した。
これはSubjectの有無から独立してweapon primitiveを調べる診断であり、正式Role producerではない。

12 weapon行中9行を検出、3行は未検出。ability行3件はweaponにしなかった。
他に部分表示で未解決の行を1件残した。追加した開発用weapon referenceは3画像で一致し、
既知Self Killer以外に新しいNonself行と別のSelf Killer行でも支持された。
新しいSelf Victim episodeや完全なqualificationの成功件数には加算しない。

初回の評価で1件の行対応エラーがあった。source reviewが「表示中の上からの順番」を
固定slot番号として記録していたが、元のfull画像には空きslotがあった。
元reviewと全測定を残し、full画像による訂正を別receiptへ保存した。
訂正後に確認した9件はすべてweapon行で、wrong-kindは0件。
**測定後のannotation訂正を含むため、完全な事前固定blind試験としては扱わない。**
runtime ROI、profile、参照、閾値は変更していない。

## Report・fatal row・killer portrait

別にsource画像をレビューした5つのReport正例と2つのReportなし負例を、
変更していない既存Report reader・OCR・fatal-row参照で測定した。

| 指標 | 実測 |
| --- | ---: |
| Report正例のdamage数値が正しい | 5 / 5 |
| fatal-rowとdamageの関連付けを受理 | 4 / 5 |
| 正しい対応クラスのkiller portrait候補 | 1 / 5 |
| 未対応portraitをunknownのまま保持 | 4 / 5 |
| 誤ったdamage / portrait候補 | 0 / 0 |
| Reportなし負例でのfield受理 | 0 / 2 |
| 正式Death属性・資格付け | 0 |

観戦中の他人のHPや、別のReport行の大きいdamageを本人のdamageへ代用していない。
複数damage行を持つ正例でも、readerは目視したfatal側の値を取得した。
これは読み取り結果であり、Reportだけで現在のSelf Deathを確定したわけではない。

fatal-row未検出例は、固定文字列「で倒された」の位置がsearch外だったわけではない。
headerによる平行移動後の正しい領域内にbest matchがあり、NCCは **0.86814773** で
既存0.90未満だった。他の4例は0.98067〜0.98315で受理された。
描画差等の具体的原因は未確定であり、閾値を下げたり新参照をこの例から作ったりしていない。
元referenceに名前やdamage数字が混入したという仮説も、参照画像の目視では支持されない。

正しく読めたportraitはRazeの1例で、Fadeの独立正例は今回得られていない。
現 `QualifiedDeathAttributeContract` は3属性の意味reviewとproducer全体を束縛し、
クラス別の許可リストを持たない。**この1例から全対応クラスの資格を発行しない。**
count資格と3属性を要求するpoint資格は分離したままにする。

## 再現用の評価器

`scripts/diagnostics/evaluate_self_subject_roles.py` は認識済みの固定出力を、
別保存のsource reviewと元decode manifestに照合するoffline evaluatorである。
runtimeへラベル・名前・GTを渡さず、候補をqualifiedへ変更せず、Eventも作らない。

```bash
PYTHONPATH=.:src python3 -m scripts.diagnostics.evaluate_self_subject_roles \
  --readings "$PRIVATE_FIXED_SET/recognition-result.json" \
  --review "$PRIVATE_FIXED_SET/source-labels-before-recognition.json" \
  --manifest "$PRIVATE_FIXED_SET/manifest.json" \
  --row-origin 113 --row-pitch 39 \
  --output "$PRIVATE_FIXED_SET/new-audit.json"
```

Windowsでは同じmoduleを既存のPython環境とリポジトリのimport設定で使う。
`--row-origin/pitch` はこの静的source reviewの評価座標だけで、productionへ渡さない。
出力ファイルの上書きを拒否する。

元decodeのsource SHA・整数PTS・time base・epoch・pixel/encoded hashを各行で照合し、
出力のcode/profile/dependency fingerprint、元reviewのhash、全件順序・件数も確認する。
同一source PTSの重複は拒否し、異なるPTSの同一pixelは別途開示する。
違う行の同じRole、未解決truth、低confidence、bool/string/NaN/Inf、誤った名前prefix、
geometryのみのvictimが成功件数やnumeric qualificationを水増ししないことをテストする。
manifestのhash一致だけで中身のsource bindingを省略しない。
ただし保存metadataの照合は再decodeや独立reviewの代わりではない。

## 処理時間と容量

| 処理 | Wall秒 | peak RSS bytes |
| --- | ---: | ---: |
| 192 native keyframe取得 | 418.078 | 80,756,736 |
| 同192画像のSelf／Role reader | 210.993 | 96,210,944 |
| 24画像のseparator primitive | 14.970 | 97,816,576 |
| 7画像のReport fields | 7.252 | 89,731,072 |

追加native PNGは259,400,435 bytesで、source動画の複製は作っていない。
分離プロセスの値なのでこれらのRSSを合算しない。Full高速化率や全体の偽陽性率へ換算しない。
固定出力のRole再集計には動画の再認識は不要。

## テスト・CI

新しいoffline auditは40ケースPASS。実測192件のCLI再評価も同じ集計で成功した。
Ruffは既存CIと同じ `src tests` と追加diagnosticがPASS、mypyは148 source filesでPASS、
text-I/O classified auditもPASS。最初に `ruff check .` を実行した結果にはprivate pack等の
既存違反も含まれたため、それを全体PASSとして報告していない。追加テストのimport整形は修正した。
追加CLIを素のPython環境で起動した一度のimport失敗も、明示的な `PYTHONPATH=.:src` で解決した。
どちらもproduction条件やテストを緩和する対応ではない。

元reader commit `fe772db` のLinux／Windows／text-I/O CIはすべてsuccessだった。
新しい診断コードを含むHEADのCI結果はPR #53の当該commitのcheckを正とし、
旧commitの成功を新HEADの成功として流用しない。

## E2E比較と未完了条件

| 指標 | 採用済みFull | 保存した未採用Strict | 今回の現コードcanonical | 差分 |
| --- | ---: | ---: | --- | --- |
| PASS | 23 | 28 | 未計測 | 未計測 |
| FAIL | 55 | 50 | 未計測 | 未計測 |
| NE | 4 | 4 | 未計測 | 未計測 |
| negative違反 | 0 | 0 | 未計測 | 未計測 |
| discontinuity assertion違反 | 0 | 0 | 未計測 | 未計測 |
| 正式Death Event | 0 | 0 | 0（静的診断は生成しない） | 0 |

新規PASS ID・現コードのPASS→FAILなしとは報告しない。別の±0.1秒評価方式も混ぜない。
独立Self Victim・episode temporal qualificationと実資格が未成立なのでFullは起動していない。
同じ旧Traceの再評価を今回の認識改善として使っていない。

次に必要なのは、現在の固定primitiveに対するcomponent別exposureの閉包と、
Source-continuousな死亡・再表示・respawn・重複の独立reviewである。
今回の追加成功はSelf Killer／Nonselfのweaponであり、独立Self Victim正例が不足していることを
曖昧な「証拠不足」で覆わない。既知のvictim画像を新しいblind画像として再利用しない。
Raze portraitの単発成功も全クラス資格へ広げない。
資格成立後に既存numeric consumerとnative Package／Trace経路を使ってtargeted→sampledを検証する。
default caller、実資格certificate、本番採用を先に有効化していない。

集約値とprivate証拠のdigestは
[機械可読レポート](../e2e_reports/match_001/self_death_fixed_source_component_audit.json) に保存した。
private画像・名前・Report値・GT・profileはGitに含めない。
