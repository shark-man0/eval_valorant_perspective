# Windows E2E 上流診断（2026-10-01）

## 2026-10-02: 回収report 3f005a0を基準とするidentity限定修正

この節が最新。基準実装はde46747。旧runからの回収metadataのnullを性能比較に使わない。
Macではunit/integration/syntheticのみ検証し、Windows実動画改善は未確認。

### Weapon

Candidate Bはedge人口・方向一致・train/holdout支持があっても、旧gateの
「少なくとも2本の非平行線」が成立せず `edge_arrangement_invalid` になった。
これは強い構造一致とorientation diversityが別条件だったため。旧共有診断には
全lineの向きがないので、実画像の具体的な線配置は断定しない。

新gateは十分な二次元spreadに加え、非平行線、または離れた短いedge群の配置を要求する。
後者は3つ以上の局所connected components、二次元のcentroid spread、4x4 gridの
5cell以上のedge occupancyを要求する。全幅の平行stripeや一本線は通らない。
line support、density、edge similarity >=.90、最低3支持、80%支持、holdout条件は維持。

Candidate Aのmembershipはseed scaffoldの片方向recallで作られる一方、最終支持は
recall/precisionの両方向。clutterを含むmemberは最終支持から落ち得る。
12/16=75%の棄却は正常であり80%条件を下げない。holdoutを使った候補再選択もしない。
新共有診断はgates、line count、8-bin orientation histogram、spread、component count、
4x4 occupancy、training/holdout分布を含む。全candidateはローカルに残し共有は最大6代表例。

### Spectator

pairwise countsは要素の共存（一部は相対配置）であり、同一panel構造成立数ではない。
最終成立にはportraitと3つ以上のaligned text群、両者を覆うboundary、各label>=12pxが必要。
前回のpairwise6 / all1だけでは残り5件の最終棄却理由は特定できない。
今回、text alignment / boundary span / relative position / component pixel不足を記録する。
`final_rejection_counts` は候補box試行の集計でありframe数とは限らない。

boundaryはportrait/text spanの90%以上の被覆を要求し、endpointの完全包含への依存を除く。
training/holdout/runtime presenceの一致は全3componentを共通の最大±2px rigid offsetで
検証する。個別componentの移動やROI全域のpositive探索はしない。端の欠損は分母から除かない。
部分一致、blur、低contrast、reference unavailableはunknownのまま。
absenceは従来の固定位置scoreとdisplaced-component vetoを維持し、positiveの位置許容を
absenceへ転用しない。portrait単独やpairwise共存だけでpositiveへ昇格させない。

HP/Ability/Weapon/spectator exclusion全4条件、geometry/identity分離、GT不使用は維持。
Visual/Map/Round処理は変更しない。旧解析cacheを使わないためresume contractのみ15へ更新。
新profile生成が必要。Windowsコマンドは `WINDOWS_E2E.md` のAutomatic local profile節を参照。

次回はidentity readiness、Weapon rejection/gates/support分布、spectator final rejectionと
training/holdout support、live/unknown、Visual eligibilityを比較する。
Map/Visual改善やE2E PASSは今回のMac検証から主張しない。

Mac検証: pytest 525 passed / 3 skipped（実録画未提供1、PowerShell未導入2）。
`ruff check src tests scripts`、変更4Pythonファイルのformat check、mypy（78 source files）、
git diff --check成功。`ruff check .` は同梱の未変更validation pack/config検証コードの
386件で失敗するため、リポジトリ全域のlint成功とは報告しない。
追加回帰: 非平行線なしの豊富な構造、一本線/平行stripe/compact/textureの棄却、
共通位置差付きpanel生成、部分panel unknown、pairwise共存と最終geometryの区別、
理由診断、共有privacy/128 KiB境界。既存negativeテストは変更していない。

## 2026-10-02: shared export容量超過の回収

Analyzer/Evaluator完了後の共有export失敗は、詳細candidate/sample診断でsummaryが
128 KiBを超えたため。旧fallbackはfailuresしか縮めず、HUD arraysには効かなかった。
今回の修正では上限を増やさず、共有allowlist適用後に最大6代表例へ縮約する。
Weaponの選択候補・支持/棄却件数・similarity分布、Spectatorのevidence/rejection countsと
portrait統計を維持。省略件数とdetail_truncatedを共有する。raw/local詳細は変更しない。

容量fallbackはfailures短縮→HUD詳細arrays削除の二段階。summaryとhud_calibration両方を
書き込み前にサイズ検査する。それでも超える場合だけエラーにする。

`scripts.e2e.reexport_report` は完了済みrunの3JSONから、解析・評価を実行せず再共有できる。
今後はrun_metadata.jsonにsanitized metadataと3JSONのhashを保存し、再exportで同一性を検証。
旧runは登録manifestでpackを確認できる場合のみ回収し、歴史的commit/dirty/time/settingsを
推測せずnullにする。現在のgit状態や指定layoutで過去metadataを作り直さない。
実行コマンドと旧runでの制限は `WINDOWS_E2E.md` のRecovery節を参照。
Windows実動画の改善をMacで検証したものではない。
Mac検証: pytest 517 passed / 3 skipped（実録画未提供1、PowerShell未導入2）。
Ruff・mypy（78 source files）・git diff --check成功。容量fallback、privacy、raw不変、
解析/評価再実行なし、通常exportとの一致、入力/pack改変拒否、旧metadata不明をテストした。

## 2026-10-02: report 83a36df / analyzer 20346ac の再検証と構造検出修正

この節が最新。Windows実行metadataは `20346ac` / dirty=false、実動画改善はMacでは未確認。
HUD unknown3892 / live0、Weapon missing3929、spectator reference_unavailable3929のまま。

### 確定した原因と未確定部分

- Weaponは46候補が全構造棄却：固定edge不足21、方向配置不足17、mask contrast不足8。
  46件全部をvariance問題と断定しない。旧固定edgeは同一pixelに90%以上出現する必要があり、
  圧縮・AAでedge位置が揺れる場合にも消える。方向配置不足は別のgeometry条件の棄却である。
- `variance<=4` は8bit画素で標準偏差<=2階調。輝度だけが動く固定UIでもmaskから除外される。
  最新のstable_pixel_ratio≒0 / mask_population≒0と整合する。圧縮/輝度揺れの各寄与は
  原画像なしでは確定できないが、輝度変動・ノイズ・JPEGの合成回帰で問題を再現した。
- Spectatorはobservable/textlike64、boundary6、portrait2、all_components0。観測性の失敗では
  ない。閉じたconvex四角contourが必要な旧priorが欠損や装飾に弱いことは合成回帰で確認。
  実際の残り62枚の内訳（本当のpanel不在、輪郭欠損、geometry条件違反）は画像なしでは不明。

### 新しいWeapon方式

`oriented_edges_v1`: local contrastを正規化し、長い線のscaffoldからtraining clusterを作る。
1px以内の位置差と20度以内のunsigned gradient方向差を許容し、clusterの90%以上で
同じ構造を支持するedgeだけをidentity maskへ残す。画素varianceは比較用診断のみ。

類似度は `min(oriented edge recall, neighbourhood precision)`。両方向90%以上を要求する。
内容部分から離れた数字/iconは比較しないが、枠近傍の余分なedgeはprecisionで減点する。
ROI全体を滑らせる探索はしない。位置ずれ、遮蔽、強いblur、平行線だけ、world textureは
合成negativeで棄却。固定線の異方向配置と十分なedge人口は維持する。

これはNCCでもAI Coach confidenceでもなく、identity構造の一致率である。.90の意味と
1px/20度の許容は合成回帰で検証した設計値であり、実動画の誤検出率保証ではない。
trainingだけで候補を凍結し、holdout最低3件・training prevalenceの80%以上を維持する。
旧masked NCC profileはruntime互換を維持するが、再生成時はWeaponを新方式で生成し直す。

### 新しいportrait方式と安全条件

輪郭のbounding regionとHough水平/垂直線ペアから枠候補を作る。convex/4頂点/閉輪郭は
不要。distance transformで4辺のedge occupancyを測り、3辺>=.55、残り辺>=.25、平均>=.70を
要求する。寸法/縦横比priorは維持し、同時にboundaryと隣接する整列text-like構造を要求する。
欠けたAA枠のpositive、単独要素やnormal/buy/remote/map背景のnegativeを追加した。
portrait単独ではpanelにしない。既存の現在frameチェック・部分一致/blur/低contrast unknown・
移動したcomponentの全ROI探索・template missだけでabsenceにしない条件は維持する。

HP/Ability/Weapon/spectator exclusionの4条件は変更しない。geometry asset/hash照合と
GT/expected state不使用も維持。Visual/Map/Roundロジックは変更しない。
検出結果キャッシュの互換性を切るためresume contractだけ14へ更新した。

### 次回共有診断

Weaponのselected_candidateにはedge_count、stable_edge_ratio、orientation_consistency、
mask_population、training_similarity/holdout_similarityのcount/min/median/maxを追加。
全候補棄却でも、training支持に基づく最良の診断候補を保存する（採用の意味ではない）。
matcherと新edge_support_insufficient理由も共有。stable_pixel_ratioは旧画素統計であり、
新方式ではこの値が低いことだけで失敗と解釈しない。

Spectatorはsampleごとのportrait候補数、geometry成立数、occupancy棄却数、支持数、
最良のframe score/4辺scoreを追加。画像/path/OCR文字列は共有allowlistから除外する。
Windowsでは `WINDOWS_E2E.md` の単一CLI→E2E手順で新profileを生成する。JSON/画像手編集不要。

### Mac検証

pytest: 507 passed / 3 skipped（実録画未提供1、PowerShell未導入2）。
Ruff: All checks passed。mypy: 78 source files、問題なし。git diff --check: 成功。
新規回帰はJPEG/輝度変動/ノイズ、1px jitter、clutter、位置ずれ/遮蔽/blur、欠損AA枠、
三要素不足、normal/buy/remote/map背景、診断の共有境界。既存テストは変更していない。
合成動画→生成profile→Round Package/SQLiteの既存integrationも成功。実動画改善は未検証。

## 2026-10-02: Weapon/Ammo・spectator限定の追加修正（Mac検証）

以下が今回の変更であり、下記の過去経緯より優先する。Windows実動画の改善は未確認。

### 原因と変更

- 旧Weapon生成は生pixel NCCでclusterを形成し、選んだ1候補のtraining支持16に対して
  holdout支持9だった。必要支持12.8を下回ったため棄却された。数字・weapon表示の変動が
  原因という仮説はあるが、旧共有情報だけでは変動箇所は確定できない。
- Weaponのみ、trainingのedge支持でclusterを形成し、低分散（画素分散<=4）かつ
  edge persistence>=.90の領域周辺から専用maskを生成する。固定位置masked NCC>=.90、
  独立holdout最低3件・training prevalenceの80%以上を維持する。trainingだけで候補を
  1個選ぶ。複数reference ORは今回導入しない。holdout失敗時に別候補へ逃げない。
  平行線だけの背景は採用せず、異なる方向の持続edgeを要求する。
- geometryの元/新assetとidentity template/maskをpath・hashで照合し、コピーも継承拒否。
  HP/Ability生成・4条件のlive policy・competing evidence抑止は変更しない。
- 旧spectatorは左側portrait、ROI上/下端の長い線、固定pxで整列した文字状成分という
  priorで32 training frame全部が構造棄却された。どの要素が不足したかは旧診断では不明。
  今回はportraitと隣接text-like成分をまたぐ外側boundaryという相対配置を要求する。
  portrait閉枠・3個以上の整列した文字状成分・boundaryの三要素は依然必須。
- spectatorのtraining支持集合をclusterとして重複排除し、選択後holdoutで確認する。
  背景clear画像は使わない。実行済みdetectorで全mandatory componentが強く否定され、
  ROIが観測可能で、移動したcomponent/別panel候補も残らない場合のみabsenceとする。
  blur・低contrast・部分一致・位置不一致はunknownのまま。
- Map/Visual CVは変更しない。resume contractは13へ更新し、旧キャッシュを再利用しない。

### 共有診断

`automatic_identity_generation.references.weapon_ammo_structure` に候補/cluster件数、
支持件数、棄却件数を保存。`weapon_ammo_generation` に各候補のtraining cluster size、
holdout支持/prevalence、ROI内normalized bounds、dimensions、正規化temporal variance、
edge persistence、dynamic/stable/mask pixel ratio、棄却理由と選択候補を保存する。
候補一覧は先頭64件で上限を設け、除外件数は `omitted_candidate_count` で明示する。
選択候補は一覧外でも別途保存する。候補のholdout数は診断専用で選択に利用しない。

`automatic_identity_generation.references.spectator_panel.spectator_generation` に全sample
（最大64）のobservability、各要素・pairwise evidence、all components、training/holdout区分、
blur/contrast/geometry/structural棄却理由、要素別集計を保存する。sample indexは抽出順序のみで
動画時刻や正解labelではない。cluster/support/holdout/statusは親参照rowに保存する。
画像、path、OCR文字列は共有allowlistから除外。生成assetはWindowsローカルのみ。

### 次回Windows比較

必ず新しい出力先へprofileを再生成する。コマンドは `WINDOWS_E2E.md` の
Automatic local profile節。生成後の画像/JSON手編集は不要。元layout/隣接profile/assetは保持。
以下を旧baselineと比較する。

- Weapon status・training/holdout支持・stable/dynamic比率・棄却内訳。
- Spectator status・三要素/pairwise/observability・cluster/holdout支持。
- identity_reference_ready、reference_unavailable（旧3929）、present/excluded/ambiguous/mismatch。
- HUD live（旧0）、unknown（旧3892）、HP/Ability/Weapon missing（旧1277/1409/3929）。
- Visual eligibility（旧0/0）、Map calibration attempted/accepted、skipped（旧3929）、resolved。
- Round count（旧1）、E2E failed（旧57）、negative failures=0を維持。

Mac最終確認: pytest 495 passed / 3 skipped。skipは実録画未提供1件とPowerShell未導入2件。
Ruff: All checks passed。mypy: 78 source files、問題なし。git diff --checkも成功。
unit/integration/syntheticのみの結果であり、Windows実動画精度の証明ではない。

## 2026-10-02: 精査で再現した3件の修正

- `hud/spectator.py`: 固定位置で3要素が不一致でも、ROI全体でpanel候補と移動した特徴を
  探索する。候補・特徴が残っていれば `panel_structure_mismatch` として未確認に戻す。
  合成panelの5px/10px移動でabsence→liveになる再現を回帰テスト化。
- `hud/calibrate_profile.py`: 新positive clusterが生成できない場合、既存の検証済み
  component detectorをdimensions・形式・assetに基づいて継承し、新出力先へコピーする。
  観戦場面なしで再生成するテストでも、前回の参照を保持して現在frameを検査できる。
- 同生成器で元profileのgeometry asset provenanceを保持し、生成後anchorとの両方を
  path/hashで照合する。古いanchorが置き換わった場合と別名コピーの場合の流用を拒否。
- `scripts/e2e/calibration_report.py`: 新しいmismatch理由を画像なしで共有。
  `application/pipeline.py`: resume contractを12へ更新。

Windows実測JSONは変更していない。CLIと再実行コマンドは `WINDOWS_E2E.md` に記載。
Mac検証: **489 passed / 3 skipped**、Ruff成功、mypy77ファイル成功。
今回の回帰テストは位置移動3ケース、参照継承1ケース、geometry流用2ケース。
skipは実録画1件・PowerShell2件。実動画精度やWindows動作は未検証。

## 2026-10-02: 34dc48a Windows再検証後の修正（現在の手順）

正本 `summary.json` / `hud_calibration.json` を確認。実行元99d7d1a、geometry有効3929、
geometry有効下unknown3892、spectator_exclusion_unverified3929、独立参照4件不足。
Visual eligibilityは両方0、Map definition未解決は解消、57 failed / negative failures 0。
今回のMac作業ではこのWindows結果JSONを変更していない。

### 確認できた原因と限界

- 旧structure_referenceは全training中央値から一つの参照を作り、全trainingと全holdoutの
  各80%以上でNCC >= .90を要求していた。異なるHUDモードが混在する場合、十分に一貫した
  minority modeまで不採用になる。固定cropの形状フィルタでも棄却され得る。
- 旧clear生成はpanel ROI全体がほぼ一様（max-min <= 8）で、固定背景と全holdoutの80%以上
  一致することを要求した。変化する3D背景には不適切。
- 旧共有JSONは棄却時のtraining/holdout値が全てnull。実画像もMacにないので、各roleが
  最初に落ちたフィルタや画素を特定したとは言えない。構造上の欠陥と実測棄却を区別する。
- live_identityの早期returnはspectatorの不足しか報告せず、同時に起きる3構造不足を隠した。

### 修正

1. Training frame内でNCC >= .90のcandidate clusterを作り、cluster内の固定edge整合性を
   検査。trainingだけで候補を選び、未使用holdoutで一度検証する。各splitで3件以上の支持と
   training比率に対して80%以上のholdout支持を要求。全動画の80%一致ではない。
   最良training候補がholdout不合格なら、holdoutを使って別候補へ乗り換えない。
2. Geometry asset/maskを使わずidentity ROIから別参照を生成。継承時もpathとhashでgeometry
   assetの流用を拒否する。cluster自体をlive/spectator等の正解stateとはラベル付けしない。
3. `hud/spectator.py` を追加。panel ROI内の長い境界、portrait状の閉じた枠、横に整列する
   文字要素というUI形状条件からpositive候補を抽出し、training/holdout支持を検証。
   既存の明示的positive panel templateがある場合は、同じ形状条件で参照を継承可能。
4. Runtimeでは背景NCCではなく3要素のedge被覆を測る。観測可能性（contrast、明度、blur）
   とサイズを確認し、全要素 >= .90なら存在、全要素 <= .10なら構造の不在を確認する。
   中間値・部分隠れ・参照不足は未確認。`checked=true && panel_present=false` の時のみ
   absentを設定。旧clear assetとlegacy pixel templateの非検出はabsenceに利用しない。
5. 自動CLIの入力・出力先・E2E呼出方法は維持。新profileの生成が必要。JSON手編集なし。
   現在frameの証拠だけを使い、remote/spectator/menu/map/死亡UIの抑止とunknownを維持。
   resume contractを11へ更新。

このpanel形状条件は未検証のUI variantには対応しない。観戦画面がサンプルに存在しない、
portrait枠等が条件を満たさない、holdout支持不足ならdetectorは未確認のままになる。
任意の背景クラスタをpanelと呼んで埋め合わせることはしない。実動画改善は未確認。

### Mapの次のgate

`visual/runtime.py` はHUD live + player_specific_hud_valid + 禁止flagなしでのみ
`timeline.calibrate(image)` を呼ぶ。live=0の今回の実行経路では、その前で全件停止する。
従来のmap_selection_or_calibration_requiredはNoneをまとめた理由なので、markerやlocation
の故障を意味しない。新しい共有診断は以下を区別する。

- `map_calibration_skipped_hud_eligibility` / `map_ownership_blocked`
- 校正を試した場合: `map_calibration_failed` + 個別理由（asset不足、特徴不足、alignment等）
- `map_calibration_accepted` 後: `map_marker_missing` / `map_marker_available`
- `map_location_not_evaluated` / `map_location_unresolved` / `map_location_resolved`

### 次回の比較指標

- `automatic_identity_generation.references`: 各roleのcandidate_count、structural_rejected、
  support_rejected、holdout_rejected、training/holdout支持件数。新しいroleはspectator_panel。
  `*_rejected`は候補検査件数でありframe件数ではない。identity_reference_readyは参照の
  構成可否であって精度PASSではない。
- `identity_missing`: 各構造の不足frame数（早期returnとは独立）。
- `spectator_checks`: reference_unavailable、roi_unobservable、geometry_mismatch、
  panel_structure_present/excluded/ambiguous（およびROI不足・未評価）。
- geometry成功保持率、HUD unknown/live、Visual eligibility/events、Map各gate件数、
  E2E failedとnegative failures。live増加だけで改善判定せず、誤liveとnegativeも比較。

Windowsコマンド全文は `WINDOWS_E2E.md` のAutomatic local profile節。今回は前回使用した
Windows-local layout/profileをbaseにし、64サンプルで新しい出力先へ生成する。
古い画像やJSONの目視修正は不要。GTはE2E評価だけに使い、生成器は参照しない。

### 変更ファイルとMac検証

- `src/valorant_ai_coach/hud/calibrate_profile.py`: cluster生成、生成診断、旧clear参照除外。
- `src/valorant_ai_coach/hud/spectator.py`（新規）: positive UI形状抽出・三値検査。
- `src/valorant_ai_coach/hud/{templates,identity,analyzers,diagnostics}.py`: 実行接続、
  checked/present条件、同時不足の集計。
- `src/valorant_ai_coach/visual/{runtime,map_pipeline}.py`: Mapの試行/未試行・gate診断。
- `src/valorant_ai_coach/application/pipeline.py`: resume contract更新。
- `scripts/e2e/{calibration_report,share_report}.py`: 新統計のallowlist共有。
- `tests/unit/test_hud_cluster_spectator.py`（新規）、既存HUD/profile/diagnostics/Map/report
  テスト、`tests/conftest.py`、`tests/integration/test_hud_pixels_e2e.py`: 回帰・合成検証。
- 本文書、`WINDOWS_E2E.md`、`E2E_VALIDATION_STATUS.md`: 手順と検証限界。

Mac全体テスト **483 passed / 3 skipped**。Ruff成功、mypy77ファイル成功。
skipは実録画1件とPowerShell2件。合成動画→profile→Round Package→SQLiteを含むが、
Windows実動画改善やUI形状の適合を検証した結果ではない。
既存テストの変更は、旧「背景が一致すれば不在」fixtureを明示的positive panel構造へ置換し、
黒画面で証拠を出さない検証を維持したもの。GTや期待イベントを検出器へ注入していない。

## 2026-10-02: 手編集不要の自動生成経路

下記の旧「Windows側profile作業」は `hud.calibrate_profile` に置き換えた。
実行コマンド全文は `WINDOWS_E2E.md` の Automatic local profile 節。
geometryとは別に未ラベルROIから固定矩形のidentity参照を選び、未使用holdout frameで
一致を確認。geometry maskをidentityへ流用せず、閾値.90も維持する。
観戦presenceの意味ラベルは自動捏造しない。既存detectorを保持し、条件が成立する場合に
限り全領域clear参照を生成する。不成立はunknownのまま。API・GTは生成に使用しない。
生成統計はallowlist経由で共有し、参照画像・mask・profile本体はローカルに保持する。
resume contractは10へ更新。Windows実動画改善は未検証。

## 最新診断06f981bに基づくgeometry / identity分離

正本は最新summary / hud_calibration。Windows実行commit `f301aeb`、dirty=false。
3929 frame中、fresh geometry成功1、保持込み成功3929、保持3928。
geometry無効によるunknownは0、有効下unknownは3891、identity証拠不足3928。
全anchorはmaskなし。medianはtimer .772、match bar .444、HP .502、abilities .418。
これはgeometryの失効ではなく、内容が変化する大きなROIを毎フレームのidentity確認にも
使っていた経路が主問題であることを示す。画素未確認なので、各ROIのどの画素が変動したか
までは断定しない。

### 設計変更

- `hud/identity.py`で本人視点証拠をgeometryから完全に分離。anchorの個数・スコアは
  live判定へ渡さない。masked/unmaskedのどちらもgeometry専用。
- 現在frameの独立した `hp_hud_structure` / `ability_bar_structure` /
  `weapon_ammo_structure` の3検出（各confidence >= .90）と、実行済みの観戦パネル
  detectorによる不在確認を必要とする。既存signal template readerを利用する。
- 観戦パネルの中間スコア(.20超〜threshold未満)、未設定、サイズ不一致、黒画面、
  読み取り不成立は不在とみなさない。陰性結果だけでliveにすることもない。
- remote、観戦、buy menu、expanded map、死亡UI等の証拠がある場合はliveを抑止。
  過去liveを持ち越すpersistenceは採用せず、毎frameで独立証拠を要求する。
  geometryの保持とletterbox等による失効は従来どおり。
- geometryだけのprofileでは、引き続きunknownになる。これは未検証の本人視点を
  自動承認しないためであり、閾値緩和は行っていない。resume contractは9。

### Windows側profile作業（必要）

既存profileがanchorのみの場合は独立したsignalの追加が必要。
`config/hud_templates.example.json` の3構造signalと `spectated_player_panel` を参考に、
Windowsローカルで各ROI内の小さな固定UI形状を参照画像として用意する。
HPの数字・timer・abilityのready状態・実キー文字・プレイヤー名・背景は含めない。
ROI全体やgeometry用maskをそのままidentityへ流用しない。通常/特殊視点で検証し、
不確かな検出は有効化しない。Macには素材がないため、これらの実画像は作成・検証していない。

`hud.calibrate_temporal` は未ラベル動画から8〜64枚（標準24）を等間隔抽出し、
低時間分散と持続するエッジからgeometry用のmask候補を作る。GT時刻・stateは使わない。
情報不足なら失敗し、3個未満のanchorを無理に補完しない。既存thresholdを下げず、
reader/signalは保持する。新規フォルダへのみ出力し、Git内ではignored先に限定する。
生成画像・mask・元profileへの絶対参照はWindowsローカルだけに保持する。
静止背景や一定の数字が残る可能性があるので、候補は完成済み校正の保証ではない。
このツールはidentity画像を自動生成・承認しない。

### Visual / Map

Visual eligibilityはplayer_mechanics/world_semanticsとも1。現在のevents=0だけでは
独立したCVバグと断定できない。HUD identity設定後、同じCV条件で再評価する。

Mapの `map_definition_unresolved=3929` は、resolverがdefinition=Noneのまま呼ばれたことを
明確に示す。これはresolverの校正・ownership判定より前に発生する。
ただし自動選択を試すminimap校正は上流でHUD eligibilityに制限されるので、
HUDと完全に無関係な故障と断定もできない。

runner → run_real_video → AppSettings → bootstrap → MapTimelineのmanual ID伝達は正常。
登録された正確なIDは `summit`。自動選択はtrusted labelまたはminimap照合の十分な
confidenceを必要とし、登録mapが1個という理由で決めない。前回のflag値はhashから
復元できない。今回は共有metadataに登録済みmanual_map_idだけを記録するよう追加。
明示的 `-ManualMapId summit` によりGTではなくユーザー設定として選択できる。
選択後も位置・所有者・minimap校正に失敗すればzoneはunknown。これを迂回しない。
`-MapClientBuild`は実際のclient buildが分かる場合のみ指定する。参照版を憶測で指定しない。

### Windows再実行

変更をcommit/push後にWindowsでpullする。前回のVisualProfile等の設定も維持する。

```powershell
git pull
$video = Read-Host '元動画の絶対パス'
$oldLayout = Read-Host '現在使用中のlayout JSONの絶対パス'
# geometry候補の生成は任意。出力先は未使用のignoredフォルダ。
$newLayout = & .\.venv\Scripts\python.exe -m valorant_ai_coach.hud.calibrate_temporal `
  --video $video --layout $oldLayout --output .\outputs\hud_temporal_v1 --samples 24
if ($LASTEXITCODE -ne 0) { throw '候補生成失敗。閾値を下げず診断してください' }
```

生成されたprofileのgeometry候補を確認し、同じprofileのsignalsに独立したidentity参照を
追加・検証してから実行する（既存profileにこれらがあれば保持される）。

```powershell
.\run_e2e_windows.ps1 -Video $video -VideoId match_001 `
  -ValidationPack '.\ValorantData\valorant_e2e_validation_pack_v3' `
  -HudLayout $newLayout -ManualMapId summit
```

マスク生成を省略するなら、identity signalを追加した `$oldLayout` を指定する。
`-IncludeEvidence`は不要。共有対象はe2e_reportsのみ。画像/profileはgit addしない。

次回比較: geometry保持率、unknown3891、`identity_reasons`の内訳、独立構造成立数、
Visual eligibility1/events0、map_definition_unresolved3929、Map resolved0、Round1→期待2、
E2E failed57、negative failures0維持。`live_identity_evidence_insufficient`は今後geometry
anchor数ではなく独立構造数に基づくため、policy名と合わせて比較する。
temporal_generationは選択画素数/率とhashだけ共有し、画像/パス/自由文はexportしない。

### 修正ファイルと検証範囲

新規: `hud/identity.py`、`hud/calibrate_temporal.py`、対応unit tests、Map経路テスト、
独立したidentity証拠を供給するtests/conftest.py。
変更: `hud/analyzers.py`、`hud/templates.py`、`hud/diagnostics.py`、application/pipeline.py、
`scripts/e2e/{calibration_report,run_dataset_case,share_report}.py`、profile設定例、
HUD境界/letterbox/診断テスト、実ピクセル→SQLite統合テスト。
runtimeパスは `src/valorant_ai_coach/` 以下。
Mac全体テスト: **464 passed / 3 skipped**（32.33秒）、Ruff成功、mypy 75ファイル成功。
skipは実動画アンカー1件とPowerShell未導入による2件。新規31ケースは独立identity、
geometry欠落時のlive成立、モード遷移即時抑止、非有限/低confidence抑止、画素template、
temporal候補生成/情報不足/非上書き/既存設定維持、Map選択経路、sanitizationを検証。
既存テストの期待結果は維持し、旧「geometry一致だけでlive」という入力前提に
独立したidentity検出fixtureを追加した。GT/付属Schema/評価基準は変更していない。
実動画・Windows profileは未使用。以下の旧レビューにある「mask不明」等は当時の状況。

---

## 正本と検証限界

取得commit: `a880518`。最新 `e2e_reports/match_001/summary.json` の実行コードは
`65d0ca83a01d5af9990b948f283b520b3814d4cf`、dirty=true。
Schema適合、Exit 1、21 passed / 57 failed / 4 not evaluated、失敗メッセージ58件。
Macでは今回、実動画・Windowsの校正profile・raw anchor画像を使っていない。
最新summary/historyは過去実測の正本として変更せず保持した。

## 58 failureの分類

|分類|カテゴリ|件数|判断|
|---|---|---:|---|
|root-cause調査対象|state_coverage、state_start_edge|12+1|HUDの状態成立が不足。geometry不足かidentity不足かは従来reportから確定不可|
|cascading failureの有力候補|missing_point|5|round開始・終了・死亡の観測不足|
|cascading failureの有力候補|ownership_coverage|5|本人・死亡UI・観戦状態への帰属が不足|
|cascading failureの有力候補|missing_snapshot|23|unknownでは本人HP/ammo等を消去する安全処理の影響もある|
|cascading failureの有力候補|count|6|上流イベント未検出・round分割不足に伴う件数不足|
|独立原因も調査が必要|missing_visual_observation|3|HUD gateの影響に加えCV検出器・profile不足の可能性|
|独立原因も調査が必要|missing_derived_snapshot|3|Map未解決。map選択・校正・所有者・label/markerのどこかは従来reportでは不明|

合計58。これはコードと観測結果からの因果仮説分類であり、58件すべての原因を
実証したという意味ではない。判定結果をGTから補完していない。

## HUD unknown大量発生

3891 / 3929 = 約99.0%がunknown。`RealHudAnalyzer.observe_frames`では、
幾何校正成立後も、独立した通常視点の証拠がなければunknownとなる。
masked anchorは形状が特殊視点でも残るため、幾何校正専用で本人視点の証拠には使わない。
全anchorをmask化したprofileでは、それだけでlive判定を回復できない。
今回のWindows profileのmask有無は不明であり、該当すると断定していない。

anchor不足だけなら過去の有効なgeometryを保持する既存実装がある。
letterbox/位置/scale等の不整合では失効する。この安全条件を維持した。
state分類器自体にはunknownを時間方向へ増幅させる平滑化はない。
snapshot/ownership/roundにある保守的な条件まで一律緩和する修正はしない。

確認された不整合: profileのthresholdで棄却されたスコアでも0.90以上なら
本人視点の証拠に使われ得た。現在は当該フレームで受理されたanchorだけを使う。
閾値を下げる修正ではなく、誤ったlive判定を防ぐ修正である。

## Round / Visual / Map

- Round境界はbuy→live、timer/score/banner等の時系列証拠を使う。
  liveが1件しかない今回の出力では境界証拠不足が強く疑われる。Round Builder独自の
  不具合を証明できたわけではない。前ラウンドcombat reportの死亡再発行防止は維持。
- Visual player mechanicsはliveかつ本人HUD有効を必要とする。大部分unknownなので
  対象フレームがほぼない。muzzle flashのCV感度自体は共有結果だけでは評価できない。
  smoke中shot継続・観戦shot非本人扱い・reload抑制は変更していない。
- Mapでは未選択、minimap校正、ownership、location label/marker等の各gateがある。
  resolved=0だけから特定のgateを原因と断定できない。次回は許可された診断コードの
  件数とVisual eligibilityを共有する。GTのzoneや時刻を本番へ追加しない。

## 新しい画像なし診断

自動生成先: `e2e_reports/<id>/hud_calibration.json`。
同じデータをsummaryの `hud_calibration` に含め、commit等はmetadataで関連付ける。
Schemaを持つHUD observationやRound Packageには診断専用フィールドを混ぜない。

各既知anchor（round_timer/top_match_bar/player_hp_armor/abilities）について:

- threshold、mask presence、画像dimensions（width,height）、画像/マスクのSHA-256
- accepted/rejected/unscored counts（rejectedは未設定/未読込も含む）
- match confidence min/median/max（有限の実測だけ。未測定はnull）
- `missing_during_insufficient_anchors`: anchor不足フレームでこのrequired anchorが
  欠けていた件数。重複する共同不足であり、因果の寄与率ではない
- `geometry_success_rate_when_accepted`: 当該anchor受理時に全体の新規校正も成立した率

全体の `fresh_geometry_success_rate` はそのフレーム単独で成立した率、
`effective_geometry_success_rate` は保持済み校正を含め使用可能だった率。
分母は実際に解析したsample frame数で、動画の全フレーム数や時間加重率ではない。
最終passだけを集計し、Pass A/Bの二重加算をしない。途中の校正エラー時は
完了した直近passの診断を保存し、レポート全体はFAILのままにする。

`geometry_valid_state_unknown` が多ければstate/ownership証拠を調べ、
`geometry_invalid_unknown` が多ければgeometry/asset/anchorを先に調べる。
古いrawや前処理失敗では `available=false`。過去実行の統計を捏造・流用しない。
画像・profile本体・パス・例外文字列は共有せず、固定名と数値をexport時にも再検査する。
追加依存や有料APIはない。exeの起動方法は変更なし。

## Fingerprint / dirty

Windows側のrelative POSIX path文字列ソートを保持し、Posix/Windowsの列挙順が
異なっても同じhashになるテストを追加。入力JSONや改行自体が異なる場合は別hashになる。
今回のdirty fingerprintは一方向hashしか残っておらず、実行時の未commit差分を
復元できない。後続commitは共有reportと `hud_reference.png` を追加しているが、
当時のdirtyがそれだけだったとは断定できない。現在の取得直後のworktreeはcleanだった。

既にリモート履歴にrawに近い `hud_reference.png` とValidation Pack画像がある。
今回それらは参照・追加・削除していない。公開範囲の見直しや履歴削除は別途判断が必要。

## 変更ファイルとMacテスト

新規: `hud/diagnostics.py`（runtime統計）、`scripts/e2e/calibration_report.py`
（共有境界の再sanitization）、`tests/unit/test_calibration_diagnostics.py`、本書。
変更: `hud/analyzers.py`、`application/hud_video_processor.py`、`application/pipeline.py`、
`tests/e2e/run_real_video.py`、`scripts/e2e/run_dataset_case.py`、`scripts/e2e/share_report.py`、
`tests/unit/test_e2e_dataset_runner.py`、`tests/unit/test_e2e_share_report.py`、
`tests/unit/test_hud_calibration_export.py`、`WINDOWS_E2E.md`、`E2E_VALIDATION_STATUS.md`。
runtimeの各パスは `src/valorant_ai_coach/` 以下。

追加検証: anchor metadata/hash/score中央値、geometryとstateの分離、missing寄与、
非有限値・パス・秘密文字列除去、受理閾値とidentityの一貫性、異常終了時の統計保持、
POSIX/Windows列挙順に依存しないpack hash。既存masked anchor/letterboxテストも通過。
**全体433 passed / 3 skipped、Ruff成功、mypy 73ファイル成功**。
skipは実動画アンカー1件とPowerShell実行2件。実動画PASS/Windows再実行は未確認。

## 次のWindows実行手順

この変更をcommit/pushしてWindowsへ反映後、**前回と同じ校正profileと他の設定**を使用する。
`-IncludeEvidence` は指定しない。profileを新規生成し直す必要はない。

```powershell
git pull
$video = Read-Host '前回と同じ元動画の絶対パス'
$hudLayout = Read-Host '前回と同じ校正profile内のlayout JSONの絶対パス'
.\run_e2e_windows.ps1 -Video $video -VideoId match_001 `
  -ValidationPack '.\ValorantData\valorant_e2e_validation_pack_v3' -HudLayout $hudLayout
```

前回VisualProfile/ManualMapId/MapClientBuild等を指定した場合は同じ指定を追加する。
終了後、summaryとhud_calibrationを確認し、軽量reportだけを手動commit/pushする。
profileフォルダ・画像・動画は追加しない。

比較指標: unknown 3891/3929、Visual events 0、Map resolved 0、Round count 1（期待2）、
E2E failed 57、negative failures 0。加えて新規/保持込みgeometry成功率、
geometry有効下unknown、anchor別棄却率・score中央値・mask有無、Visual eligibility、
Map診断件数を確認する。今回のMac修正だけで認識精度改善や実動画PASSは主張しない。
