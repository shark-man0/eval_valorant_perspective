# Ability identity review

## Decision

**NEED MORE EVIDENCE**。production detector・threshold・全identity gateを変更しない。今回の診断で位置ずれは回収要因にならず、75件中63件は下部Ability HUDが視認できるにもかかわらず固定pixel matcherがrejectしていた。うち42件は独立した4つのpedestal輪郭が同時に一致した。これは固定pixel representationの限界を示すが、「Abilityの動的状態だけが主因」とは証明していない。候補は既存positiveを24件失い、contextual negativeのraw受理も増えるため採用しない。

## Reproducibility

| 項目 | 検証値 |
| --- | --- |
| Starting main | e38ad8a829d8509ec5a418e64ca6734a8ad40aaf |
| Current analyzer source | e38ad8a829d8509ec5a418e64ca6734a8ad40aaf（production差分なし） |
| Last clean E2E analyzer | 2650d09b90df50d6a004dbe5d849fc60432af33b |
| Video SHA256 | 71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06 |
| Profile fingerprint | 372bf43ab9c443e3d54bd46b3b5d51626aa1ebf0f8d8a68edeb76e5aff826453 |
| Layout SHA256 | a3678bcd9df35d0932ae0e69495eb5b87a3ab40e9c988560d502a9507d59eef1 |
| Templates sidecar SHA256 | 9e9ad3c4a74583f8792a6e56256fb1828cc36a5991dc31bcee2942ce80b6f2d7 |
| Ability PNG SHA256 | d83617acdc2ec7bc72cf103393463276710f2882047dbb6ae30a6bcaa6d5fc1f |
| Decoded grayscale SHA256 | 54f25aa94bc2a1bb5c92d21a02518b389122f12e9d54de960cba8d188cee3202 |
| Worktree at diagnostic start | clean |
| E2E metadata | git_is_dirty=false |
| Samples | 258 canonical frames; 75 missing /183 accepted; C27; unresolved3; uniform64 training32/holdout32 |

Profileは `outputs/hud_profiles/weapon_observability_v1_run1`。直近Clean E2Eのraw processing内にAbility referenceのgenerated status・content hash・100×67寸法が記録され、profile assetと一致する。E2E metadataのlayout hashも実ファイルと一致する。fingerprintはlayout/sidecar bytesおよび参照assetのpath/bytesから計算したもの。現在diskのreferenceを見ただけの推測ではない。

258枚は前回Weapon診断と同じ、元の4451-observation runから固定したSpectator-excluded cohortである。直近4730-observation runに258枚すべてが出力されたという主張はしない。private native timestamp照合では242件が共通、16件は直近streamにない。現在mainのprofile/runtimeを元の258 JPEGへ再適用した比較であり、全roleとlive reasonを前回のcurrent-profile比較に対して確認した。frame番号・timestamps・manifest・画像・詳細dumpはprivateに保持した。

実videoからVideoServiceを再実行し、generatorと同じ `linspace(0,duration,66)[1:-1]` の64 requested samplesを抽出した。full-resolution BGR JPEG→gray、even32 training/odd32 holdoutで `structure_reference()` を再生成した結果、referenceは全pixel一致（差分0、max error0）、bounds・155 candidates・training21/holdout24も一致。以前のfresh64 cacheとのJPEG hash比較も64/64一致した。

診断の再現手順: (1)上記source/profile/video hashesを確認、(2)private canonical manifestから同じ258 BGR JPEGを読み、loaded profileの `detect_signals()` をtrace、(3)実際に渡されたAbility cropに独立OpenCV NCCを適用、(4)pass/failとscore一致をassertしてから25 bounded offsetsを測定、(5)fresh64を再抽出しtrainingだけで候補を固定、(6)holdout・A/B・C27に固定candidateを適用する。GT、OCR、expected ability values、agent/event labelsは診断featureやcandidate学習にも使用していない。

## Current implementation

| 確認項目 | 実測・コード契約 |
| --- | --- |
| Generation | calibrate_profile.create_profile → generic structure_reference（Ability専用identity_structure_regionsなし） |
| Reference | ROIを5×5の固定candidate位置へ区切り、各100×67patchのtraining seed NCC>=.90 clusterを作る。3 members以上のmedian referenceからtraining support最大の1候補を選択 |
| Structural validation | Canny60/150 edge density .015–.25; std>=8; Hough line>=2; member edge coverage>=.90 |
| Training/holdout | even32 /odd32。holdoutで再選択しない。holdout support>=3かつtraining cluster prevalence予測の80%以上 |
| ROI | abilities [710,855,1210,1078] /500×223 |
| Subregion | normalized [0.2,0.6995515695,0.4,1.0] /full-frame [810,1011,910,1078] /100×67 |
| Runtime | HudTemplateProfile.detect_signals → _best_template_match → BGR2GRAY → TM_CCOEFF_NORMED → minMaxLoc |
| Threshold | 0.90（変更なし） |
| Alignment | same-size 100×67 response1×1、centerのみ。runtimeのbounded offset searchはない |
| Mask /support /dynamic exclusion | いずれもなし |
| Representation | unmasked raw grayscale pixels。値・world背景・fill・glyphの局所変化に不変ではない |
| Score meaning | mean-centered normalized correlationをfinite checkし[0,1]へclamp。確率、semantic ability availability、absence証明ではない |
| Inheritance | 有効なindependent identity assetがgeometry asset/hashと重複せず同じrole/ROI等の検査に通るとinherit可能。今回はgeometry inherited、Ability identity generated |
| Generation diagnostics | 155 candidates; structural_rejected112; support_rejected546; holdout_rejected0; train21/32; holdout24/32; accepted-holdout median0.9800663 |

Runtimeにはgeneratorのstd<5 guardはない。generatorの `_score()` とruntime `_best_template_match()` の相違を独立再実装へ混入させない。Ability PNGは100×67のpixel referenceで、4-slot全体を表すreferenceではない。部分icon、pedestal/fill、固定keybind glyph、透明HUD越しの背景を含む。

## Runtime reproduction

Actual loaded runtimeと独立NCCは258/258でscore完全一致（max error0）、pass/fail完全一致。欠落75/75にも一致した。初期診断集計のWeapon用score混入を修正し、Ability専用のcheckpointが通るまで下流分析を再開しなかった。最終aggregateは修正済みartifactのみから作成した。

Private per-frame dumpはindex/internal id、private timestamp、image/ref hashes、Ability NCC/pass、ROI/bounds/crop dimensions、各25 dx/dy score、luminance std/mean/range、edge count/density、actual detector path、geometry、current HP/Weapon outcomes、Spectator exclusion、frozen-original blocker contextを使ったcurrent live reasonを含む。original gate結果とcurrent比較結果を別フィールドで保存した。

再現baseline: HP missing18、Weapon missing142、Ability missing75、live86、structure insufficiency158、competing-view blockers14。geometryは258/258 valid、crop寸法100×67で一致。

## Cohorts

A=75 runtime Ability rejects。B=183同じ258枚中のAbility accepts（semantic liveをGTで保証した集団ではなく、検出器positive control）。C=27 distinct contextual/observable negative controls。32 stratum slotsを30 unique imagesへdedupし、明瞭なAbility HUDがあるUNKNOWN3件をnegativeと断定せずunresolved補助群へ除いた。UNKNOWNをpositiveに変更していない。

CにはSpectator8、remote6、buy4、combat-report6のstratum observations（Spectatorとcombat-reportの重複1）および4追加controlsがある。追加はcombat-report blocker付き2件と、非黒のgameplay frameで下部Ability HUDが実際に視認できない2件。C27内の17件はAbility-like下部HUDが見え、8件は見えず、2件はoverlayで曖昧。単なる黒画面controlではない。expanded tactical map /recent-death-only controlsは選択元から確証ある例を取得できず、未カバーとして明示する。

## Score distributions

| Cohort | n | min | p10 | p25 | median | p75 | p90 | max | >=.90 | .88 | .85 | .80 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 75 | 0.167293 | 0.190207 | 0.708892 | 0.811464 | 0.839492 | 0.880063 | 0.898976 | 0 | 8 | 17 | 38 |
| B | 183 | 0.901557 | 0.918594 | 0.926975 | 0.948433 | 0.981007 | 0.993643 | 0.996276 | 183 | 183 | 183 | 183 |
| C | 27 | 0.000000 | 0.133473 | 0.211786 | 0.884263 | 0.954355 | 0.977503 | 0.995969 | 13 | 15 | 19 | 19 |

## Threshold simulations

| Diagnostic threshold | Recovered A75 | C raw accepts | New C accepts vs.90 | C accept rate |
| --- | --- | --- | --- | --- |
| 0.90 | 0 | 13 | 0 | 48.1% |
| 0.88 | 8 | 15 | 2 | 55.6% |
| 0.85 | 17 | 19 | 6 | 70.4% |
| 0.80 | 38 | 19 | 6 | 70.4% |

Precision-risk: .88は8件回収に対しcontextual negativeを2件、.85は17件に対し6件、.80は38件に対し6件追加受理する。A/B/C scoreは重なり、単純な閾値変更ではSelf-view separationを改善しない。case-control抽出とcontextual role sharingのため、この率はdeployment precisionの推定値ではない。既存Spectator/remote等のgateがfalse-liveを防ぐことと、Ability patchがnegativeでもmatchすることを区別する。production thresholdは.90のまま。

## Alignment results

| Search | A recovered at.90 | B retained | C raw accepts |
| --- | --- | --- | --- |
| center | 0 | 183 | 13 |
| ±1px diagnostic | 0 | 183 | 13 |
| ±2px diagnostic | 0 | 183 | 13 |

各missingでcenter score、best score、best dx/dy、pass flipをprivate保存した。A75の63件はbest offsetもcenter、12件の低score群だけに小さな感度があり、gain>.01は2件。258全体のmax gainは±1=.0082083、±2=.0188650、判定flipは0。alignment aloneで0/75回収。large search/自由transformなし。

## Visual-state analysis

All75のcropと500×223 wider contextを視覚確認した。63件は下部pedestal/key structureが期待ROIに見える。12件は対象HUDが見えない。visible63のcontext observationsはbright/colored scene-effect25、手・equipment等が近接/背景に現れる27、これらのcoarse flagなし11。これらは観察であり、animation、cooldown、agent identity、因果ラベルではない。特にworld/foreground imageryはneighboring HUD contaminationとは区別した。

64 chronological samplesのper-pixel temporal varianceとCanny edge/brightness persistenceを計算した。raw reference patchのtemporal std中央値35.703、p90=45.303、std>20は100%だった。一方7×7 top-hat ridge patchではstd中央値2.600、p90=10.432、std>20は6.03%。raw変動にはworld背景とHUD有無のmode変化が混在するため、100%を「iconが動的」と解釈しない。

Reference Canny edges459のうちtraining edge recurrence>=.50は414（90.20%）。64全体では411/459（89.54%）。patch全pixelのedge persistence>=.50は6.40%、brightness>=160のpersistence>=.50は9.64%。構造輪郭はかなり安定しているが、matcherは6700 pixel全部を比較する。training-persistent edgeを1px膨張したbandは1278 pixel（19.07%）で、reference centered energyの34.96%を占める。残る80.93%のpixelもNCCへ寄与する。

A75のnormalized reference残差はstatic band外の割合中央値80.15%（p10=70.14%、p90=88.33%）。single-patch masked NCC ablationでは23/75回収するが、Bを19件失い、C raw accepts14。したがって背景/非persistent pixelの影響は支持されるが、その除去だけで安全なvalue-invariant detectorが完成するという証拠ではない。

Icon brightness/fill/count/upper-slot accents等はwider HUD内で視覚変化する。現在の小patchへのscore低下がその変化だけから起きたとは証明できない。Agent/ability-specific shapeやavailability labelを使わずに同定したのは、下部pedestal輪郭の反復性とraw appearanceの変動である。

## Visual clustering

A75だけでstandardizeした84D features（16-bin grayscale histogram +global mean/std/p10/p50/p90・mean abs Sobel gx/gy・gradient occupancyの8値 +4×5 cellそれぞれmean intensity/mean abs gradient/occupancyの60値）へcustom deterministic Lloyd k-means k=5をfitし、B183/C27は凍結centroidへ割当てた。GT/state/agent/timestampsはfeaturesに使用しない。

| Cluster | A missing | B accepted | A median/min/max NCC | B median/min/max NCC | B/(A+B) | C count/raw accepts | Visual feature |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 40 | 76 | .817679 /.706152 /.898556 | .985300 /.904436 /.996276 | 65.52% | 13 /9 | variable scene texture, strong histogram/spatial background changes |
| 1 | 1 | 0 | .549366 /same /same | — | 0% | 1 /0 | single high-contrast appearance outlier |
| 2 | 21 | 107 | .862961 /.625114 /.898976 | .937162 /.901557 /.989376 | 83.59% | 5 /4 | more uniform/bright pedestal crop, appearance overlap |
| 3 | 12 | 0 | .189153 /.167293 /.220974 | — | 0% | 8 /0 | target lower HUD not visibly rendered |
| 4 | 1 | 0 | .583087 /same /same | — | 0% | 0 /0 | single appearance outlier |

Clusteringはexploratoryで、そのidにgameplay semanticsはない。 Major clusters0/2 include both A and B. A/B centroid-distance medians are42.5/38.7 and16.4/14.7 respectively. Only the visually absent12 form a clean appearance cohort without B. This does not establish a particular Ability visual mode as the cause. Singleton clusters are retained rather than forced into a semantic class. Referenceとの差は上表のNCC（1-scoreでappearance disagreement）として示し、descriptor距離をidentity confidenceへ読み替えない。

Initializationはfirst A rowとfarthest-first、distanceはsquared Euclidean、argmin/argmaxはfirst-index tie、empty clusterは旧center保持、max100 iterations、numpy allclose defaultで停止（今回は2 iterations）。ScalingはA75 mean/population stdのみ、std floor1e-8。RNG/sklearnは使用しない。private replayでA75 labelsとB183 assignmentsが完全一致、84D featuresもatol1e-5で一致した。recipeと1−NCCのcluster別aggregateはJSONに保存した。

## Observability analysis

Current raw-pixel contract: 63 observable + reference-pixel contradictory, 12 unobservable/insufficient target structure, 0 current matching among A. Under the independent four-pedestal diagnostic, the same A splits into42 observable + matching scaffold,21 visible + remaining contradiction,12 target-unobservable. Visibility comes from crop/context inspection, not variance alone; low-NCC visible cases remain contradictions, and sufficiently structured world texture is not target-HUD visibility.

Candidate internal edge-population flags alone would label12 insufficient and30 with some edge-populated failing group, overlapping in9 cases. Those are operational feature flags, not physical observability ground truth. The exclusive physical classification above takes precedence and does not misclassify a visible contradiction as unobservable. No temporal positive persistence is used.

## Cause breakdown

| Cause candidate | Overlap n/% | Primary n/% | Evidence status |
| --- | --- | --- | --- |
| alignment mismatch | 0 /0.0% | 0 /0.0% | ruled out by bounded recovery |
| ROI / geometry mismatch | 0 /0.0% | 0 /0.0% | valid geometry and identical crop size |
| low observability | 12 /16.0% | 12 /16.0% | visual absence, not low variance alone |
| dynamic visual state change | 0 /0.0% | 0 /0.0% | not established; zero confirmed is not zero occurrence |
| fixed-reference shape contradiction | 63 /84.0% | 42 /56.0% | raw pixel-pattern contradiction; not proof of different Ability icon shape |
| transient animation | 0 /0.0% | 0 /0.0% | not established from snapshots |
| neighboring HUD contamination | 0 /0.0% | 0 /0.0% | not confirmed; underlying world/foreground is separate |
| reference-generation bias | 42 /56.0% | 0 /0.0% | plausible candidate: single appearance cluster misses matching scaffold; not independently proven causal |
| insufficient training representation | 0 /0.0% | 0 /0.0% | not established; same64 supports alternative scaffold |
| other | 63 /84.0% | 21 /28.0% | changing scene imagery observed in visible misses; mechanism unresolved in21 |

Primaryはmechanismを証明した範囲の排他的なevidence classificationである。42件はfixed referenceがrejectする一方、4 scaffold groupsがmatchするrepresentation disagreement（56%）。12件はtarget structureがない（16%）。21件はHUD visibleだが、具体的なpixel failure mechanismを確定できないother（28%）。合計75。

“fixed-reference shape contradiction”はこの報告ではreference pixel-patternとのcontradictionを指し、Ability icon自体のshapeが違うという断定ではない。Overlap欄のreference-generation bias42は単一appearance clusterに限定する設計との整合性がある候補で、独立した因果証明ではない。他の未確定カテゴリの0は「確認済み0」で、現象が絶対に存在しないという意味ではない。63件の背景差とsingle-mode learningが共起するだけではdynamic ability state、training insufficiency、animationの件数を捏造できない。

## Representation comparison

| Representation | B retained/183 | A recovered/75 | C raw accepts/27 | A unobservable | A visible remaining contradiction | Train/32 | Holdout/32 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A fixed pixel NCC | 183 | 0 | 13 | 12 | 63 | 21 | 24 |
| B fixed NCC + diagnostic bounded2px | 183 | 0 | 13 | 12 | 63 | 21 | 24 |
| C independent pedestal edges | 159 | 42 | 17 | 12 | 21 | 26 | 24 |
| D single-patch masked NCC ablation | 164 | 23 | 14 | 12 | 40 | 21 | 23 |

全候補はdiagnostic-only。A/B/DのscoreはNCC、Cはreference/current双方のedge coverageの最小値で、.90という数字を同じ意味のprobabilityに読み替えない。Cは4 groups全passを要求する。Dはsingle patchかつglyph/fillの残存を許すablationなのでproduction identity contractの候補ではない。Train/holdoutは録画のmixed modes全32枚に対するrecurrenceで、GT live recallではない。

B183同士の16653 pixel NCC pairsはmin .767016、p10=.884959、median=.955241、2402 pairs（14.42%）が.90未満。現在のreferenceにacceptedであっても相互pixel appearanceは一定ではない。4 scaffold groupsが一致したA42とB183の7686 cross pairsはmedian .811378、6115 pairs（79.56%）が.90未満。共有structural familyに対するraw appearance mismatchを支持するが、Ability状態だけに限定したcontrolled interventionではない。

## Static scaffold and support groups

Training32のみからCanny60/150 edgesを1px膨張したper-pixel recurrence>=.60を作り、24px horizontal opening、component width/height>=4、height<=12でcompact icons/glyphsを除外した。population順に最大4 groupを選び、x-center間距離>=35pxを要求した。holdoutやnegativeでROI/featureを再選択・調整していない。下部pedestal/border/diamond contoursを視覚確認した。

学習されたgroupのboundsは500×223 Ability ROI内のnormalized coordinatesであり、productionの固定座標設定ではない。現在frameのedgeとreference edgeを独立box内で比較し、1px toleranceのbidirectional coverage>=.90、reference/current各8 edges以上、2–4 independent groups、全group passを要求する。bright textureによるfeature-populationをHUD存在と誤同一視しない。

| Group | Normalized [x1,y1,x2,y2] | Reference edges | Components | Train support/obs | Hold support/obs | C support/obs | Train recurrence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.080000,0.860987,0.242000,0.923767 | 227 | 4 | 28/29 | 28/28 | 17/20 | 0.875757 |
| 2 | 0.306000,0.860987,0.470000,0.923767 | 226 | 3 | 27/29 | 28/28 | 17/19 | 0.875460 |
| 3 | 0.534000,0.860987,0.696000,0.923767 | 228 | 5 | 27/29 | 27/28 | 17/19 | 0.862547 |
| 4 | 0.758000,0.860987,0.922000,0.923767 | 235 | 4 | 28/30 | 25/28 | 17/20 | 0.891544 |

Independent all-group support: training26/32、holdout24/32。group edges合計916、component数4/3/5/4、各edge populationのspreadはROI幅の.156、高さの.049327。隣接group中心距離113.5/113.5/112.5px。geometric area exclusion95.91%。7×7 top-hat temporal std>20をoperational dynamic pixelとした17671 pixels中17307（97.94%）をbox外へ除外した。ただし364 variable pixelsがbox内に残る。これはsemantic dynamic-value exclusionの証明ではなく、HUD absence/global effectsも含む尺度である。

Icon interiorとkeybind glyphの主要領域はgroup box外だが、charge-fill由来のcontour変化が完全に排除されたとは未証明。Cをvalue-invariantと認証するには、dynamic-fill-onlyのcounterexamplesでもidentityが変化しないことを確認する必要がある。

## Negative separation

C27でraw Ability patchはA13、B13、C17、D14件受理する。contextually似たHUDを持つ負例に対してreference/scaffoldだけではSelf-viewを識別できない。13や17を最終live false positivesと呼ばない。元のanalyzer-derived Spectator exclusion/blocker contextを凍結したcurrent-profile live_identity replayは0/27 liveであり、最新Clean E2Eもnegative assertions20/0。ただしcandidateの新しいfull E2Eが20/0と検証されたわけではない。

C27の8件のvisually absent controlsと2件のambiguous controlsはscaffold候補でも受理されなかった。17 matching controlsはHUDが見える別contextである。UNKNOWNでHUDが見える3件はnegative計数から除外し、candidateが3/3一致してもfalse acceptとも新しいpositive truthとも扱っていない。expanded-map/death-only hard negatives、independent recordings、およびvalue-only changesに対する分離が未確認であり、recall上昇を安全性の証拠に置き換えない。

## Adoption gates and loader contract

| Gate | Result |
| --- | --- |
| Fixed representation is main cause | Partial evidence42/75; exact dynamic-state-only causal claim unproven |
| Independent training recurrence | Yes26/32 overall; separate4 groups |
| Holdout recurrence | Yes24/32; interleaved same-video holdout, not held-out recording |
| Clear negative separation | No at role-only level; contextual gates still necessary, broader coverage missing |
| No recording timing/agent knowledge | Yes; image-only training, private timestamps only for alignment with source |
| No dynamic values as identity | Not certified; operational mask excludes most variable pixels but fill contour remains possible |
| Threshold safety | Production.90 unchanged; candidate coverage.90 not equivalent NCC safety certification |
| No UNKNOWN coercion | Yes; U3 remain unresolved and production states unchanged |

`templates.py` loaderはmasked rolesをHP/Weaponに限定し、Weapon consensusをWeapon roleだけに制限する。mask binary+shape+>=32 pixels、2–4 support labels、maskはsupport内、各group>=32 masked pixels等を検証する。Abilityへvalue_identityをそのまま設定するとrole validationでrejectされる。今回matcher/loader/contractを変更していない。将来はAbility固有contractとdynamic/neighbor exclusion、independent-group observability、observable contradiction rejectionを明示して検証する必要がある。

## Verification

pytest: **717 passed /2 skipped**,259.67s。skipはsibling trace-adapter pack未配置とreal-video-anchor integrationのsource env未設定。診断自体は実videoでgenerator/runtimeを検証している。Ruff `src tests scripts`: passed。mypy `src`: passed（83 source files）。`git diff --check`: passed。既存Weapon/HP/Spectator testsを変更していない。production変更がないため新matcherの条件付きtestsは追加せず、full E2Eも再実行しない。

Reused clean E2E: analyzer2650d09b90df50d6a004dbe5d849fc60432af33b、dirty=false、21 passed/57 failed/4 not evaluated、negative20 passed/0 failed。4730 observations: live146 /spectator519 /remote39 /buy3 /unknown4023。今回この数値が改善したとは報告しない。production-source diffは空。診断aggregate/docsのみを独立commitし、private images/crops/assetsは共有しない。

## Evidence needed next

同じROI geometryと明瞭なpedestalを保った観測frame間で、background-onlyとfill/glyph-onlyの変化を分離した比較が必要である。次の候補は静的pedestal contoursから動的fillを明示的に除外し、既存positive24件のlost-support機序、expanded-map/remote/deathのhard negatives、独立録画holdoutを確認する。現時点ではproduction変更条件を満たさないため、結論は **NEED MORE EVIDENCE**。
