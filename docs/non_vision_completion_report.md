# 非画像解析パイプライン 完了作業レポート

## 状態

- 作業branch: `external/non-vision-completion`
- 開始SHA: `80d0d460b8e3a76d3c181e035c72cd10026f4252`
- 開始時main: 同上（PR #8 merge commit）
- 実動画認識精度改善: 担当外
- Vision production code: 変更なし
- 現在の状態: 契約変更を要しない調査・統合テストを進行済み。Priority Aの契約判断待ち。

## 1. Phase 1: 最新mainの検証

PR #8の既存実装を一から作り直さず、現行mainを正として再確認した。

### 完了済みと確認したもの

- spectator由来player stateのmask
- `state_snapshot.source_confidence`
- Fact confidenceが参照Event confidenceを超えないvalidation
- deterministic rule authorityのlabel / fact-ref binding
- temporal scopeの基本実装
- GOOD / IMPROVE / UNSCORED
- Qt非依存result view model
- clip生成と保存済みresult表示

### 開始時CI

Windows verificationは成功。

Linux Basic CIはpytest assertion failureではなく、全test成功後のprocess teardownで失敗した。

- pytest: 1856 passed / 7 skipped
- coverage: 84.50%
- message: `QObject: shared QObject was deleted directly. The program is malformed and may crash.`
- process exit: 139
- Linuxで解決されたPySide6: 6.12.0
- 直近の成功Linux runで使われていたPySide6: 6.11.2
- Windows constraints: PySide6 6.11.2

version差は原因候補だが、先にtest側QObject lifecycleを明示cleanupして切り分ける。test skipで成功扱いにはしない。

## 2. Phase 2: Priority A再現

### A-1 evaluation confidence

現行`SchemaValidator.validate_ai_output`は次を既に検証する。

- finite number
- JSON Schema
- match / round identity
- candidate rule identity
- unknown fact reference
- duplicate evaluation / clip ID
- evidence / clipのround範囲
- evidence timestampとevidence_rangeの包含

`fact_refs`はSchema上uniqueである。

一方、次は未検証。

`evaluation.confidence <= min(confidence of referenced facts)`

MockEvaluatorはhybrid評価のconfidenceをpackage aggregateとevent confidenceから計算し、
その後にrule関連factを`fact_refs`へ付けるため、引用factより高いconfidenceになり得る。

既存調査どおりTC-014 / TC-016が代表例である。

- TC-014: evaluation 0.98に対し引用可能なvisual factに0.90が存在する
- TC-016: evaluation 0.98に対し引用可能なzone factに0.90が存在する

ただしframe-onlyの独立画像根拠まで無関係なfact confidenceで上限化するのは不適切なので、
適用範囲の契約決定が必要。

### A-2 output scope / context

Round Package自体の不正はAPI呼出し前にvalidationされる。

AI outputの通常Schema/identity違反は`OpenAICoach`内の修復loopへ入る。

一方、`validate_output_scope`は現在`RoundAnalyzer`でCoach返却後に呼ばれるため、

- rule analysis window外のevidence_range
- missing previous-round contextでのGOOD/IMPROVE

は修復loopの外で`ContractValidationError`になる。

入力不正と、正しい入力に対するAI output不正を分けた扱いが必要。

### A-3 UNSCORED duplication

MOV-02 / AIM-03のscored resultは既存dedup groupで1件へ集約される。

低confidenceで両方UNSCOREDになった場合、UNSCOREDはevidence_rangeを持たないため
`_same_scene`が成立せず2件残る。

原因・provenanceまで同一の場合だけ統合するか、rule identityを優先して2件保持するかは
契約判断待ち。

### A-4 deterministic authority

現行OpenAI pathでは`_bind_deterministic_evaluation`がdeterministic decisionについて
次をlocalでbindする。

- label
- fact_refs
- confidence
- evidence
- evidence_range
- display_clip
- rule identity

さらにOpenAICoachとRoundAnalyzerの両方にalignment/authority checkがある。

追加検証で重複実装するのではなく、この既存bindingとpost-checkを防御層として維持する。

## 3. Priority B: Temporal Context監査

44ルールのlevel内訳:

- match: 1
- micro: 7
- local: 11
- round: 14
- phase: 8
- cross_round: 3

### requires_round_timeline

- 44ルールすべてに定義
- true: 26
- UIはこの値を「ラウンド全体文脈」表示に利用
- TemporalScopeResolverはこのboolean自体を直接消費しない
- 現在はlevel / event_windowと整合する範囲でwhole-roundへfallbackする
- booleanを新たな強制scope gateとして扱う意味は正本から一意でないため、推測実装しない

### uses_whole_match_aggregation

- 44ルールすべてに定義
- true: AIM-01, AIM-02, AIM-03, AIM-04, MOV-01, MOV-02
- 現pipelineはround単位APIであり、whole-match aggregation executorは存在しない
- AIM-01のmatch-level scopeも現在は「そのround全体」まで
- 実装にはmatch単位の入力・保存・集約責務設計が必要。未実装として明示する

### display_clip_strategy

- 44ルールすべてに自然言語で定義
- 現clip範囲は主に`display_clip`、ruleの`suggested_clip_window_seconds`、Mock側の既定窓で決まる
- 自然言語strategyを自動parseしていない
- rule意味を推測して新しいclip durationへ変換しない

### temporal_tolerance_policy

全体policyとしてlevel別に定義される。

- micro: evidence 0.75s / clip 1.5s
- local: 2s / 3s
- phase: 4s / 5s
- round: 6s / 8s
- cross_round: 10s / 12s
- match: 3s / 4s

現`TemporalScopeResolver`のscope toleranceは固定0.05sであり、このglobal policyを
evaluation/clip生成へ直接適用していない。既存`event_window_seconds`とは別の概念なので、
用途を推測して適用しない。

### automation_policy

44ルールすべてにrule直下で定義。

- `llm_contextual`: 40
- `deterministic_if_confident_else_llm`: 4

RuleSelector / DeterministicRuleEngine / RoundAnalyzerの既存責務に相当する部分はあるが、
JSONのautomation_policy objectを実行時authorityとして直接dispatchする実装ではない。
現在の44ルールの意味を変えず、差分を明示する。

## 4. Priority C: 追加統合テスト

追加済み:

- post-Visionのspectator-safe synthetic Round Packageを本物の
  `RoundAnalyzer`へ通すtest
- player-owned HP / armor / weapon / utility / spike-carried factが再生成されないこと
- viewpoint-independentな`spike_planted`は保持されること
- world-level fact confidenceがsource confidenceを維持すること

Vision production codeやValidation Pack/GTは使用していない。

## 5. Priority D: Clip / Result UI

新規機能は追加していない。

実`MainWindow`を構築するtestを追加し、以下を検証対象にした。

- result pageへの遷移
- GOOD / IMPROVE / UNSCORED件数
- default filter
- UNSCORED filter
- evidence / fact refs / time range
- clip button有無
- `_play_clip`でのsource切替
- cached audio track metadata
- replay時のposition=0
- missing clipの安全なwarning
- widget teardown

### D-3 元動画の該当時刻jump案

未実装。新UIなので承認が必要。

既存の「根拠clip再生」と役割を分け、追加するなら「元動画の根拠位置を確認」にする。

推奨設計:

1. 元動画を再生する。生成clipは既存buttonが担当する。
2. target timestampはformatted textから逆算せず、保存済みraw evidence timestampをUI contractへ渡す。
3. `evidence_range`は根拠の許容範囲、`display_clip`は短尺表示範囲として分離を維持する。
4. pipelineのtimestampはsource-video absolute secondsなので、根拠なくoffsetを追加しない。
5. 元動画が無ければwarningし、clip/resultは壊さない。

## 6. Priority E: 小規模整合性

### Zone confidence

現builderはzone factを

`min(zone_resolution.zone_confidence, package observation_quality.visual_confidence)`

で保存する。

上方向の水増しは起きず保守的だが、source-specific resolver confidenceにpackage aggregateを
混ぜるためprovenanceとしては粗い。変更するとconfidenceが上がる可能性があるため、
安全条件を維持して現状を保留する。

### Same-state snapshot thinning

snapshot dedup keyにsource confidenceは含まれない。同一stateが2秒未満続く場合、
後から来た高confidence observationが保存されないことがある。

best-confidence replacement等はtimestamp/provenanceを変えるので、推測実装せず設計課題として保留。

### HP / Armor

HPには別経路`_owned_hp_facts`があり、live-first-personかつ
`roi_confidence.hp_value >= 0.90`の読みだけfact化する。

snapshotの`source_confidence`にはhp/armorが現在入らない。
armorの同等のdedicated fact経路は確認できていない。Vision/HUD側confidence contractへ
踏み込まず、非画像側で推測confidenceを付与しない。

### 古いsource_confidenceなしdata

`FactBuilder._source_confidence`はmissing/invalidを0.0にする。
過去dataへ推測confidenceを補完しない既存安全方針を維持する。

## 7. Priority F: 入力範囲効率化

現single-call設計ではcandidateの1件でもwhole-round scopeならpackage全体を送る。
既存38 fixtureではこの条件により実質的な入力削減が発生しないことが既存計測で確認されている。

windowed rule群とwhole-round rule群を別API callへ分離すれば削減可能だが、

- API call数増加
- 料金増加可能性
- repair/cache keyの複雑化
- cross-call aggregation/authorityの追加責務

が発生する。

よって今回は計測・設計までとし、承認なしにmulti-callへ変更しない。

## 8. Priority G: Linux Qt teardown

開始時mainのLinux Basic CIでは全assertion成功後にQt teardownでexit 139。

最初の切り分けとして、productionやCI dependencyを変えず、UI testのwidgetを
`deleteLater` + DeferredDelete event deliveryでQApplication生存中に明示破棄する修正を追加した。

結果はCI完了後に追記する。これで解消しない場合、PySide6 6.12.0固有回帰かを
6.11.2との比較で確認し、CI pinが必要なら最小変更案を先に報告する。

## 9. 承認待ちの契約判断

実装前にユーザー承認が必要:

1. fact-backed evaluation confidence超過の処理方式
2. AI output scope/context違反のrepair / UNSCORED / reject方針
3. 同一原因UNSCOREDのdedup方針
4. 元動画jumpの新UI
5. API call分割による入力効率化

詳細な選択肢は作業会話で提示し、承認後に回帰test → production修正へ進む。

## 10. 後方互換性

ここまでのcompletion branch追加はtest/docsのみでproduction behaviorを変更していない。
PR #8までのsource_confidence / deterministic authority / 38 fixture contractをそのまま維持する。

## 11. CI / 最終検証

最終状態で次を更新する。

- Dataset validation 38 cases
- pytest / coverage
- Ruff
- mypy
- Linux Basic CI
- Windows verification
- packaged smoke
- negative controls
