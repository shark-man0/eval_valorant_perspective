# Round lifecycle prerequisite audit

## Scope and evidence

2026-10-08、main `ae43a77ad2c553445c316caa2d940994085467f7`で実施。55 FAIL分類後の次段階はround lifecycleの入力を揃えることであり、新しいnumeric candidateを追加することではない。production、profile、threshold、pack、GT、assertion、samplerは変更していない。full E2Eも起動していない。

保存済みfull16の実画像6枚を目視し、同じ画像を現在のRealHudAnalyzerと安全側profile13で再診断した。full16のtimer profileは既に却下済みで、数値は原因調査だけに使用する。安全なprofile13のtimerは未構成であり、今回numeric認識の採用判断はしていない。

各点は独立に、保存fullの先頭3フレームPTS `[0.036003, 0.202669, 0.402669]`から校正した。通常targeted runnerのprefixとは異なる。anchor/signalの注入はしていない。点間の連続性、temporal event、round packageは証明しない。診断sinkは既存のものを利用した。画像・完全診断はPiローカル `outputs/recognition-investigation/round-lifecycle-prerequisites/` に保存した。

## Current-frame prerequisites

各構造列はsignal/confidence。unconfirmedは診断に肯定signalがないことを示し、構造が画像内に存在しないという意味ではない。NCC/identity条件は維持している。

| PTS | HP | Ability | Weapon | Spectator checked | Shared banner/confidence | Identity reason |
| --- | --- | --- | --- | --- | --- | --- |
| 3.919336 | True/0.9412 | unconfirmed | unconfirmed | True | False/0.6744 | structure_evidence_insufficient |
| 4.152669 | True/0.9661 | unconfirmed | unconfirmed | True | False/0.0581 | structure_evidence_insufficient |
| 74.319336 | True/0.9602 | unconfirmed | True/0.9471 | True | True/1.0000 | structure_evidence_insufficient |
| 74.486003 | unconfirmed | unconfirmed | unconfirmed | False | True/0.9764 | spectator_exclusion_unverified |
| 111.352669 | True/0.9930 | True/0.9886 | unconfirmed | True | False/0.7790 | structure_evidence_insufficient |
| 111.436003 | True/0.9779 | True/0.9929 | unconfirmed | True | False/0.0955 | structure_evidence_insufficient |

全6点でeffective geometryは成立したが、identity.liveはfalse、primary stateはunknown、hud_confidenceは0。開始直前・直後で不足する入力は異なる。

- R1開始前後：HPは成立するがAbility/Weaponは未確認。実画像にはknifeを持つself HUDが見える。knifeの動的形状をidentity根拠に追加することはせず、既存value-invariant weapon/inventory証拠の適用範囲を調査する。
- R2開始前後：HP/Abilityは成立、Weaponが未確認。紫色背景だけをremote/unknown→liveへの変換根拠にしない。
- R1終了後：spectator detectorはchecked=false、reason=panel_structure_mismatch。HP等を読んでplayer ownershipを補完しない。combat reportフラグだけで死亡やround終了を確定しない。

## Phase evidence is a separate missing input

目視した3.919336、111.352669には「購入フェーズ」があり、4.152669、111.436003にはその表示がなくtimerが開始値へ切り替わる。これは保存画像のレビュー結果であり、新たなGTや採用済みphase detectorではない。

現在のOpenCvHudFeatureReaderはcenter_phase_bannerのtextureをshared_banner候補に使う。購入表示がある2点はshared_banner=false（confidence 0.6744/0.7790）。一方74.319336の戦闘背景、74.486003の死亡直後画像はshared_banner=true（1.0/0.9764）。**texture候補だけではsemanticな購入/終了表示を証明できない**。表示がある2枚に閾値を合わせて下げる変更は採用しない。

profile13にはbuy_phase_template / round_end_template、ally/enemy score readerがない。_enrich_temporal_evidenceは、両scoreが前後で既知ならscore_stable/changedを作り、buy_phase_templateとscore_stableが揃えばpre_round_contextを作る。今回の6点にはpre_round_context、next_stable_state、score_changed、timer_stoppedがない。shared_bannerだけをtrueにしても、classifierのphase契約を満たさない。

## Saved temporal observations

保存full16の連続観測を変更せず、明示した診断範囲で確認した。これはsource動画の全フレームを新たに解析したものではない。非公開のtemporal evidenceを再構成していない。

| Diagnostic range | Observations | Unknown | Buy/end flags | Both scores known | Observed numeric reset pair |
| --- | ---: | ---: | --- | ---: | --- |
| R1 start 3.8–4.3 | 13 | 13 | 0/0 | 0 | 4.086003 → 4.152669 |
| R1 end 74.2–74.7 | 9 | 9 | 0/0 | 0 | none |
| R2 start 111.2–111.7 | 10 | 10 | 0/0 | 0 | 111.402669 → 111.436003 |

この32観測でHUD confidenceは全て0。保存timer数値のresetがある開始2箇所でも、実装済み_round_start_confirmedのlive遷移とbuy証拠がないためpredicateはfalse。安全なprofile13のtimerを置換すれば境界が出る、という仮説は成立しない。round endはscore、phase、confidenceの独立証拠が欠ける。private evidenceなしのend predicate=falseから、native timeline joinの全挙動を証明したとは扱わない。

## Next implementation prerequisites

1. 開始時のAbility/Weapon identity不足を現在のvalue-invariant reference診断で分解する。画像にknife/紫背景があること自体をstate肯定証拠にしない。training/holdoutを分離しminimum support/NCC 0.90とspectator exclusionを維持する。
2. semantic phase表示と両scoreのsource証拠を用意する。既存template/reader形式を利用し、phase表示なしの背景、menu、combat report、spectatorをnegative cohortに含める。texture候補の高confidenceを認識正解と扱わない。
3. 開始/終了のproducer→trace actorとpre-round package所属の契約を決める。team/systemを評価の都合だけで置換しない。
4. 以上を満たすcandidateだけで、連続実PTSの境界区間を検証する。既存3つの境界窓とR2終了非検出、discontinuity、negativeを確認し、採用候補のみ全回帰/fullへ進む。

現段階では、33 FAILに影響する上流原因の修正を開始するための入力資格を満たしていない。PASS増加は0件確認、保証増加も0件。phase/identity両方を含む縦断featureとして扱う。新しいrecognizer candidateは生成していない。

## Verification and provenance

既存production diagnostic hookで6点のobserve_frames完走を確認。raw/画像のhashとprofile hashをJSONに記録。documentationとPiローカル診断のみで、production code差分0。新規codeをproductionに追加していないためunit/Ruff/mypyの再実行は不要。E2Eの23 PASS / 55 FAIL / 4 NEを更新する新runはない。

Local diagnostic SHA256:
- `safe-profile13-replay.json`: `edc7ac827022279f5cba99cd60684a2f30bec81d96ee2a6ee191392b2a0c9c24`
- `saved-boundary-predicates.json`: `3b291252e8ae1bb9339b4950ad93d389a78c5e7f3cbb2cd8bc8aba5ecfda4e04`
- `boundary-context.json`: `5e421fc05cb7d378d48cab5d69a1915d8dfaa677bf0d366bea51fce06a3c6245`
