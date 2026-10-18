# Self Death資格付け：容量を限定したnative検証

判定は **B**。正式Deathと現コードのcanonical FAIL削減は未達である。
開始mainは `7e480c2f2f7f49aea73e1541d065d78881d2f11c`、開始ブランチは
`053dcc1ced18807a88dc9e503e336c3158b24f38`。mainへマージしていない。

## 資格条件の判定

| 条件 | 現在の証拠 | 判定 |
| --- | --- | --- |
| Recorder markerの意味 | 黄色枠のsource-owner reviewと実画像 | 意味reviewあり。認識器全体の資格とは別 |
| Markerの画像認識 | 固定192画像で正しい11行、未検出4行、誤Self出力0。case005以前からのmarker code／asset不変性 | component証拠あり。whole-modelの独立資格は未成立 |
| Numeric victim role | 実際のR1／R2は既存reference000を使用。別録画の旧NCC探索31画像を再検証し、全31画像のweapon pictogramにNCC／plate支持 | outcome選択を受けた6 graphic episode。Self Victimの5画像は既知episode。31独立Death／blind holdoutではない |
| 新しいDeathの時間的根拠 | case005のnative可視遷移と元onset、未変更temporalコード | 既知1例を支持。Report不在と遮蔽・再表示の独立資格は未成立 |
| Report再表示の拒否 | case006は121連続frameで候補0 | current victimなしで拒否。不在reader全体の資格とは見なさない |
| Native source入口 | 既存の明示的source-assured／qualified scene入口 | SelfやDeathの意味を付与しない |
| Name／killer／damage属性 | 個別source-backed測定、fatal-row guard、クラス制限付き内部v2 | 実資格certificateなし。Fadeの独立positive等も不足 |
| Event→Package→Trace→SQLite | 既存の合成契約試験 | 実資格付きの実動画出力・canonical比較は未検証 |

現時点で実資格certificateを発行せず、`CANDIDATE` を `SOURCE_REVIEWED` に書き換えない。
componentが不変だったことだけでwhole-modelの独立性を証明したことにしない。
同時に、一般のgeometry画像利用履歴が不明なことと、確認できたcomponentのfit履歴は区別する。

未検証のweapon参照を単に除けば無変更で資格を移せる、とは扱わない。
現readerには「separatorが一意でなければunknown」という条件があるため、参照を除くと
以前のambiguous行がknownに変わる可能性もある。その場合は別profileとしてfreeze・再認識・
独立検証が必要で、R1／R2が通りやすいsubsetを選んで資格に代えることはしない。
NCC 0.868のfatal-row未検出も、0.90を下げて解消しない。

## 検証経路の実装上の問題

既存 `scripts/diagnostics/replay_self_death_images.py --native-window` は、
動画全体のnative PTS／pixel列をdecode・検証した後で認識区間を選ぶ方式だった。
長い原動画から数秒のholdoutを確認する場合にも、全体decodeの費用が発生する。
容量の小さい端末へ原動画を移すことを前提にせず、原動画がある環境で限定検証できる経路が必要だった。

既存runnerに明示的な `--bounded-native-window START:END` を追加した。
既存 `VideoService.native_window` を再利用し、別decoder／recognizerは作っていない。

- source video SHA-256を確認し、区間内の全native PTS・encoded／pixel hash・geometryを検証する。
- requested interval内でFPS変換、Nフレーム間引き、resize、timestamp補正をしない。
- 各区間はdecoderの元epochと独立したdetectorを持ち、区間を跨ぐstateやcontinuityを作らない。
- 浮動小数点decoder境界を外側へguardし、最終入力は元PTSの有理数比較で厳密に選ぶ。
  guardで取得した区間外frameは認識入力に加えない。時刻自体は丸めない。
- `--native-max-window-png-bytes` が一時PNGのhard limit。既定256 MiBで、区間終了時に消去する。
  上限超過やsource変更はエラーとなり、成功したnegativeとして保存しない。
- metadataは `whole_source_pts_pixels_verified=false`、
  `cross_window_continuity_asserted=false` とし、動画全体の時系列検証をしたように表示しない。

旧 `--native-window`、cache replay、full E2E、GT／evaluator／sampler／production readerは変更しない。
新modeも診断専用で `qualified=false`、`formal_events=[]` を維持する。
動画のbyte hash一致は全frame正常取得や編集のないことの証明ではなく、別動画への入力保証も継承しない。

## 実動画での等価性確認

現在のsource1原動画から既知の2死亡区間とReport残存controlを新たにdecodeした。
新しい画像をblind holdoutとは扱わず、入力・判定等価性の確認として使った。

| 指標 | 検証済み既存cache | 新しいbounded decode | Delta |
| --- | ---: | ---: | ---: |
| 処理frame | 84 | 84 | 0 |
| R1 diagnostic candidate | 1 | 1 | 0 |
| Report残存control candidate | 0 | 0 | 0 |
| R2 diagnostic candidate | 1 | 1 | 0 |
| source-blocked frame | 0 | 0 | 0 |
| 正式Death | 0 | 0 | 0 |

全84件の元PTS／pixel hash、status／reason、onset／confirmation、support／Report supportが一致した。
image code、profile、dependency fingerprintも一致した。旧rawを新しい認識として流用せず、
実際に新たに原動画をdecodeして認識した結果を比較した。

実測wallは182.475秒、認識95.257秒、Python peak RSSは100,872,192 bytes。
一度に保持したPNGの最大は85,502,305 bytesで、256 MiBの上限内だった。
原動画のコピーや永続的な全frame cacheは作っていない。
これは異なるscopeのFull E2Eに対する速度比ではない。
Fullは今回起動せず、独立資格の成立後に判断する。

計測は最終的なpreflight関数抽出前の作業ツリーで行った。実行時のrunner bytesを
元記録SHA-256 `f012d1e350f582d319cfc365687b158b21d74fe3bdc593b625ef55dfaf865b32`
と一致させてprivateに保存した。最終版の追加は、同じ引数検査を高コスト処理より前にも呼ぶ変更。
元manifest、実行argv、terminal hashes、reader結果、等価性receiptはignored outputsに保持する。

## Windows／Pi共通コマンド

既存環境を使い、同じGit commit・profile・assetsを先にfreezeする。
動画とprofileのsource SHA／画像寸法は一致が必要である。
別動画の資格や旧certificateを付け替えない。追加sourceのprofileが必要なら、診断用の
source bindingとcalibrationを明示して準備し、holdout画像を見て調整しない。

PowerShellの例。変数は原動画が存在する環境のパスと事前固定区間で設定する。
profile・owner review・画像・動画・詳細結果はprivateのまま扱う。

```powershell
$env:PYTHONPATH = ".;src"
python -m scripts.diagnostics.replay_self_death_images `
  --source $SourceVideo --profile $FrozenProfile --owner-review $OwnerReview `
  --tesseract $TesseractLauncher --engine-binary $TesseractEngineBinary `
  --tessdata $TessdataDirectory --dependency-root $TesseractDirectory `
  --native-step-ticks $VerifiedNativeStepTicks `
  --bounded-native-window $PositiveWindow `
  --bounded-native-window $NegativeWindow `
  --native-max-window-png-bytes 268435456 `
  --output $NewPrivateResult
```

Linux／Piでは `PYTHONPATH=.:src python3 -m scripts.diagnostics.replay_self_death_images` を使い、
同じ引数を渡す。step ticksを動画名やFPSだけから推測しない。
2秒以上の区間でPNG上限に達する場合は、利用可能容量に合わせて上限を明示する。
上限内に収めるために連続区間内のframeを飛ばさない。

development／holdout／negativeをepisode単位で事前固定し、認識後に都合のよい画像だけを選ばない。
元の動画を移す代わりに、元環境でこの固定検証を実施できる。
接続先・原動画保存先は現時点で未提示で、他環境での実行結果はまだない。
異なるOSのdependency fingerprintも記録し、Windowsの結果をPiの資格へ自動流用しない。

## テストと残る作業

lossless動画を実際にencode／decodeする契約試験で、旧modeと新modeのPTS／pixel／status一致、
別区間でのstate非結合、有理数境界、PNG上限、区間終了時の一時画像消去、認識中source改変の
terminal拒否を検証する。重複・逆順・接触／重複区間・不正予算はdecode前に拒否する。
新modeの試験ではwhole-source decoderの呼び出し自体を禁止し、限定decodeを使うことも確認する。
関連replay契約60ケースが15.97秒でPASS。Ruff（既存CI scopeと変更diagnostic）、
mypy（148 source files）、classified text-I/O auditもPASSした。
新HEADのLinux／Windows CIはPR #53の当該commitの結果を正とする。

正式基準23/55/4、保存した未採用Strict 28/50/4、新コードtargeted／sampled／Full未計測を維持する。
追加candidate 2件を新規canonical PASSとして数えず、現コードの20 negativeや全82件の回帰未計測を
「違反0」と埋めない。次は不足する独立Self Victim／Report不在・遮蔽／episode証拠を固定条件で
取得・判定し、資格が成立した後に既存Event→Package→Traceを通じてcanonical差分を実測する。

集約値とprivate実行証拠のdigestは
[機械可読レポート](../e2e_reports/match_001/self_death_bounded_native_validation.json) に保存した。
