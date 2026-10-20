# match_002開発成果の安全回収

2026-10-20。これはGeometry認識完成やFull E2E改善の報告ではなく、次の開発をmainから
始めるための成果選別記録。最終のCI・merge SHAは、以下の統合PRと完了時の報告を正本とする。
CI待ちの記述を成功へ読み替えない。

## 起点と保存方針

- 研究ブランチ: `work/match002-geometry-qualification`。
- 保存HEAD: `1f3edf094634037747928021c0ca9169f02928f8`。remoteと一致し、削除・resetしない。
- 分類時main: `c688206ef4b62c8f206687a1e434fe84833105df`。
- merge-base: `7e480c2f2f7f49aea73e1541d065d78881d2f11c`。
- 研究側固有54commit・70ファイル。全体mergeはしない。
- 研究側に未コミットのconvergence報告書があった。破棄せず、日付付き歴史資料として
  `docs/match_002_geometry_convergence.md`にも回収する。元のローカルファイルは変更しない。
- 元動画、anchor/reference/mask、raw観測、GT、Validation Packは移植しない。
  private outputと元ブランチの既存履歴は保持する。

全70ファイルの分類・由来commit・直接import依存・処置は
`docs/match_002_recovery_inventory.json`に記録した。**分類対象はmainとの差分部分**であり、
例えば`templates.py`の既存main部分を統合禁止とする意味ではない。

## 選別結果

| 分類 | ファイル数 | 処置 |
|---|---|---|
| A: 不具合修正／独立した検証・回帰 | 14 | 2ファイルを数値修正PR、12ファイルを検証回収PRへ |
| B: 条件付き研究／データ収集・比較 | 44 | 4ファイルのprivate-only blind reviewを回収。残る40は研究側保持（うち1ファイルの独立したA安全hunkだけ回収） |
| C: 未資格のruntime認識拡張 | 2 | `numeric_regions.py`と`templates.py`のnumeric opt-in差分を移植しない |
| D: 重複／棄却／後継の引継ぎ文書あり | 10 | 古いFull出力や冗長時系列、棄却padding、旧reader等は研究履歴として保持 |

「Bだから未使用なら安全」とは判断していない。回収する4ファイルは入力と出力、
private保存先、hash照合、無回答とunknown、モデル予測の非表示、overwrite拒否を実装と
negative testsで確認し、productionからのimportがないものに限定した。
他の研究ツールを動かすためだけの大きな依存グラフはmainへ持ち込まない。

## 小PR 1: 数値計算バグ修正

[PR #57](https://github.com/shark-man0/eval_valorant_perspective/pull/57)
`integrate/match002-spectator-precision`。
由来は`351b75c`、回収commitは`026d620005a070b264e9d0c3eaf06e9a2df654b2`。

- `src/valorant_ai_coach/hud/spectator_icon.py`と`tests/unit/test_spectator_icon.py`のみ。
- float32のpi→度変換が180度を179.99998度へ動かし、方向histogramのbinを誤る問題を修正。
- presenceとabsence crosscheckの双方をfloat64で計算。丸め・snap・threshold緩和はしない。
- 8方向・signed zero・境界の両側の2回帰テストを追加。既存期待値は変更しない。
- 関連42テスト、Ruff、production mypy133files、diff checkがローカル成功。
- 必須Linux/Windows CI、UTF-8無効、PyInstaller、packaged smoke成功後にのみmergeする。

これは既知の数値不具合修正であり、新しい観戦認識アルゴリズムやprofileではない。
実動画のidentity改善は未証明。コード変更によってglobal recognizer fingerprintは変わるので、
旧profile/codeのqualification bundleを新mainへ付け替えてはならない。

## 小PR 2: 検証・データ安全性・引継ぎ

`integrate/match002-validation-recovery`。最新mainで先行修正が統合された後に追従し、
先行PRの成果を二重移植しない。PR番号・最終検証・merge結果は実際のPRに記録する。

回収する16ファイルと、混在ファイルから切り出した安全hunk:

- `native_score_gaps.py`とテスト: source SHA/epoch/timebase/input fingerprint/整数PTS cadence/
  pixel hash形式を照合し、連続したscore変化と欠落を跨ぐ変化を区別。
  source breakで履歴をreset。**実pixelの真偽をこの集計だけで証明するものではない**。
  `continuity_proven=false`、`qualification_created=false`、`events_released=0`を保持。
- `prepare_numeric_review.py`、`freeze_numeric_review.py`、`compare_numeric_review.py`と各テスト:
  モデル予測を見せないprivate review、明示CSV回答だけのfreeze、保存観測のreduction。
  fractional timerを勝手に丸めない。無回答は未レビュー、unknownとabsentを分ける。
  元画像/ROI/HTML/回答/raw観測のhash・inventory・重複を照合し、変更時は拒否。
  採用・イベント・資格を生成せず、比較出力には正解値・OCR・path・画像を含めない。
- `prepare_pool_presence_review.py`とテスト: 保存済みpoolから既存レビューsubsetと同一hashを
  除いたgalleryを作る。数字非表示を自動推定しない。これだけでfresh/independentにはならない。
- `compare_held_banner_text.py`とテスト: 既存の盲検レビューと保存matcher出力をhash照合して
 集計。candidate再選択・recognizer/decoder呼出しなし。任意candidate IDを含み得るため、
 出力はprivateのまま扱い、共有時は別途allowlist確認する。
- `datasets/input_contracts/match_002.unedited.json`とテスト: ユーザーの「未編集」来歴を
  source SHAに限定。録画停止・frame loss・可視連続性・ownership・Round境界・資格は証明しない。
- `test_incomplete_round_fact_trace.py`: 終了証拠なしRound、独立した次開始、unknown/spectator/
  remoteでの本人値抑制、Fact confidence、exclusive membership、Schema/Trace transportの合成回帰。
- `test_map_runner_contract.py`: settings-onlyテストの`APP_ROOT`をtmp_pathへ隔離し、
  開発checkoutで実行中のE2E lockへ干渉しない。全既存assertionを維持。
- `validate_native_system_prefix.py`の既存output上書き拒否だけを回収。
  practical/UI新mode・新import・score集計配線は移植しない。新しい合成regressionで、
  Unicode名の既存receiptをAnalyzer/decoder構築前に拒否しbytesを保持することを確認。

由来commit群: `7d2050d`/`ab5c441`（gap）、`e8f7338`（numeric review）、
`1cc18d8`（freeze）、`25e8d01`（比較）、`8f913cd`（presence）、`837f712`（held text）、
`7e12aa9`（source assurance）、`9862fbf`（Fact/Trace）、`8f5552a`（lock隔離）。
最終のUTF-8対応等も含めたfile別source SHAはinventoryを参照。

reviewテストの旧fixtureだけはGeometry candidate builderへの依存を除いた。
`changing_brightness()[15]`と同じ合成rasterを直接作り、元テストの全assertionを維持する。
これにより未採用mask生成コードや追加Geometry test群を依存として持ち込まない。
ローカルの関連検証は初回88 PASS。上書き拒否の追加分とLinux/Windows必須CIは、
回収PRの実HEADで別に確認する。

## CLIの再利用範囲

以下は保存済みのprivateな開発資料を手元で扱うための入口。新動画からの自動認識や
GTの作成/変更、正式評価の開始コマンドではない。各入力JSONの由来とexposureを先に確認する。

```text
python -m scripts.diagnostics.prepare_numeric_review --help
python -m scripts.diagnostics.freeze_numeric_review --help
python -m scripts.diagnostics.compare_numeric_review --help
python -m scripts.diagnostics.prepare_pool_presence_review --help
python -m scripts.diagnostics.compare_held_banner_text --help
```

`native_score_gaps.summarize_native_score_gaps(rows, step)`は保存されたproducer-owned native rowを
集計する関数で、動画解析を起動しない。rowの実source検証は既存source preflight/native入口の責務。
生成画像・ラベル・回答・raw outputはignored private directoryから共有しない。
レビュー返信のprovenance文字列やJSON hashだけでは人間の著者性を証明できない。
信頼できる実際のユーザー返信を別に保持する。

## 保留した変更と依存

- `numeric_regions.py`/`templates.py`の新OCR runtime配線は未資格。明示opt-inでも
  production pathへ入るため採用しない。main既存readerの設定・format・fallbackは維持。
- Gradient NCC、enclosure mask、exclusions v2、candidate生成/ablation/Analyzer probeは研究のみ。
  正例12件中各3件受理、自然負例1件拒否という開発結果はqualificationでも新main性能でもない。
- v1 exclusion、棄却score-padding、旧localized readerは後継または棄却済みの履歴として保持。
- banner discovery/recapture/prospective numeric collectionは研究graphへの依存が大きく、
  next-phaseに必要な独立機能だけを再度切り出す。今回便利だからという理由で一括収容しない。
- 旧`e2e_reports/match_002`はcommit `c11ec6d`のAnalyzer中断記録。mainのlatest reportとして
  コピーしない。Geometry0/13,287、Evaluator未実行という事実はconvergence報告に残した。
- `1f3edf0`のWindows native-path修正は安全だが、対象のheld-banner review tool自体が今回保留。
  その将来回収時にはこの修正も必ず一緒に移す。成功済み旧Windows CIを新PRへ流用しない。
- PR #55のsource integrity preflightとPR #56のtemporal-data契約はmainに統合済み。
  D相当として重複実装しない。70差分の外にある既統合UTF-8/portable-path修正も再移植しない。
- open PR #42（reader/geometry initialization）、#51（sampled binding/application）、
  #54（native endpoint）、#44（snapshot transport）とは別責務。owner branchを変更しない。
  数値修正で資格fingerprintが変わることは各branchのrequalification時に考慮が必要。

## データ・認識安全性の受入確認

各PRのbaseと最終差分で以下を確認し、CI結果とともにPRへ記録する。

1. production差分はPR #57の数値修正2使用箇所のみ。回収PRはsrc変更0。
2. Geometry .90 / 3anchor / 64support、confidence、owner/identity条件、default profileを変更しない。
3. schemas、評価ルール、既存GT/assertions/manifest/canonical出力を変更しない。
4. source contractの追加は明示入力のみ。別動画への流用・連続性/本人帰属の昇格をテストで拒否。
5. private source/images/profile/Pack/GTをstageしない。比較ツールをproductionがimportしない。
6. review/input mutation、欠落・低confidence・mixed provenance・重複をnegative testsで確認。
7. 元ブランチとprivate dataのhashを保持。sealed Packを開封・再生成・初期化しない。
8. Linux、Windows、UTF-8無効、PyInstaller、packaged smokeを各PRの実HEADで確認。

既存canonical **23 PASS / 55 FAIL / 4 NE**は歴史的採用基準で、新mainのFull測定値ではない。
今回Full E2Eは開始しない。CI成功を実動画の認識精度へ換算しない。

## 次の開発への引き継ぎと残存リスク

- まず最新mainと、この回収のmerge/CI記録を取得して新branchを作る。
  研究branchをnext-phaseのbaseとして丸ごとmergeしない。
- Geometryはtimer/HPのNCC不足と描画差への弱さが残る。convergence報告のH1は計画だけで、
  mask生成・matcher変更・production採用はいずれも未承認・未実装。
- match_002のdevelopment `[0,720)`と保護holdout `[720,2214.272)`を維持。
  既存reviewed/development画像はfreshに戻らず、exposure履歴も消さない。
  privateの`validation_pack_v2`と登録manifestを保持し、recognizerへ正解時刻を注入しない。
- 個人専用動画解析の再設計では、source SHA/PTS入口、private review、欠落を跨がない集計、
  不完全Roundの保存とFact/Trace membership testsを再利用できる。
- Timer/Score reader、phase/result、Start/End、identity/ownership、Map/Visual eligibilityは
 それぞれ別の資格/観測gate。Geometry改善だけで全機能完成とはならない。
- ローカル回収テストは合成データ中心。独立した実動画qualificationと最新main Fullは未達。
  Windowsの具体結果や未解決テストはPRのterminal結果を確認してから最終報告する。
- 今回のmerge権限は安全条件を満たす回収PRだけ。他のopen PRや研究候補の採用権限ではない。
