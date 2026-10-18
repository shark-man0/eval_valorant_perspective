# E2E検証の収束と次の開発サイクル（2026-10-18）

本書は認識器追加から検証結果の確定へ方針を切り替えた時点のレポートです。
調査開始HEADは `a9eca7b32e38262b041e3fbdd82f39dd87fc91d3`、fetch後mainは
`7e480c2f2f7f49aea73e1541d065d78881d2f11c` でした。
この調査ではproductionコード、profile、qualification、GT、assertion、samplerを変更していません。
開始時のHEADとmainの差分は77ファイル、19,346行追加・142行削除で、上流の未マージPRを
含みます。今回の調査による追加差分は本書、集約JSON、既存workflow文書だけです。

**1. 実行状態・有効性**

開始時の一度のプロセス調査でローカルE2Eの実行はありませんでした。
現在コマンド・mode・開始時刻・処理段階・経過時間は該当なしです。
プロセスの終了・再起動・並列Full起動は行っていません。

最新の正常完了成果物は `current-full-verified-20261015/run` のFull候補です。
元実行のmetadata開始日時は `2026-10-14T17:37:30.531948+00:00`、
commitは `46462336427149764beb8e1fdd94c554e075616e`、dirty-tree fingerprintも記録されています。
全段階が終了しているため待機やキャンセルは不要で、raw / trace / evaluation /
metadata / timing / command結果と画像を保存済みです。正確な元argvと元実行全体の
Python・OS・依存ファイルbindingはterminal metadataから完全には復元できません。
後から現在環境を元実行環境として記入しません。

analyzerはexit 0、rawは `complete`、trace schemaはvalid、evaluatorはexit 1です。
元source SHA、pack / assertion / evaluatorとterminal artifact hashesを再確認し、
既存 `load_previous()` の検証にも通過しました。現在の参照評価器で再評価した82件の状態と
99件の失敗メッセージは保存結果と完全一致しました。
**保存された過去候補の失敗分析には有効です。最新main・現コードの正式採用検証としては採用しません。**

理由は現在コードとのfingerprint差、現在コードに対するqualification不一致、および上記の
元環境記録の限界です。Full用asset profileは現在も元qualificationのprofile fingerprintと
一致しますが、資格付けされたrecognizer fingerprintは現在のrecognizerと異なります。
以前の資格を付け替えて現在の正式Death/Boundary出力を有効化していません。

別の `current-full-20261015` は `MANIFEST_METADATA_OR_PACK_MISMATCH` のpreflight失敗
（exit 2）で、raw / traceがありません。これは除外し、82 assertionの認識失敗と数えません。

**2. 実行条件とprovenance**

| 項目 | 確認結果 |
| --- | --- |
| source SHA-256 | `71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06` |
| source | 267,056,165 bytes、1920×1080、60 fps、171.019336秒 |
| Full mode | real HUD、mock coach、visual semantic off、GT未読込 |
| native entrance | origin→EOF、replay、64 MiB buffer、明示的unedited契約 |
| original runner code fingerprint | `68512af8e83031e2c278a0ac217f7a35ff029cadc4facc2d04767bf2958b700d` |
| recorded runner settings/profile fingerprint | `23fdb3a3cd1202dd0d8bf1b54994cc0e14b2ecc1367dce9dfa829fff883f64da` |
| 実asset profile fingerprint | `60b029cb987fe0d7447853e3b4cd791d5defb0918dfaa25a401bd45d2b64c813`、57 assets |
| qualification SHA-256 | `46d75286f7f525ae4dd687012f62d9bc289b72b32b0125ba70480f992d63b2a4` |
| 元qualificationのrecognizer | `ad482fe1bae0f2c4401ce0364841f749f63c6e2230ff75c49cf853962c8eb859` |
| pack SHA-256 | `71b8021e21d4796a32e7c09327c38ec83cb4645ad6d3f78a1823ecb53970359d` |
| assertions SHA-256 | `c5e242b611ce227d1d2633e5e24c00dfe65168d8124ab58fbdea84b1d7f0d820` |
| evaluator SHA-256 | `9384bcc0aab792123c724a11004e5e17bfc3360592236c1307223f192cf93f80` |
| 今回の評価環境 | Python 3.12.3、Linux aarch64、OpenCV 4.14.0、NumPy 2.5.3 |

各terminal hashと現在コードfingerprintは
[機械可読レポート](../e2e_reports/match_001/e2e_validation_convergence.json) に記録しました。
privateの実値・expected定義・source PTS・argvはignored outputs内の
`private_assertion_matrix.json` / `evaluation_execution.json` に保持します。
公開レポートにはGT定義、private画像、profile本体を含めません。

**3. 82 assertionと安全性の結果**

| Metric | 採用済み基準 | 保存Full候補 | 今回の同一Trace再評価 | 保存候補との差 |
| --- | ---: | ---: | ---: | ---: |
| PASS | 23 | 28 | 28 | 0 |
| FAIL | 55 | 50 | 50 | 0 |
| NOT_EVALUATED | 4 | 4 | 4 | 0 |
| Negative violations | 0 | 0 | 0 | 0 |
| source discontinuity assertion violations | 0 | 0 | 0 | 0 |

20件のnegativeはすべてPASS。false owner / false death / false boundaryについては、
固定negative内の違反が0という範囲の確認です。独立した全般的な誤検出率を測定したとは扱いません。
採用済み基準に対する5件の改善は以前のlifecycle候補によるもので、今回の認識改善ではありません。
`GT-R1-ROUND-START`、`GT-R2-ROUND-START`、`event_count_constraints-000/-002/-004` です。
採用済みPASSからの退行は0。NEの旧表記 `ne` は比較時だけ `not_evaluated` と正規化し、
表記差を状態変化と数えていません。別の±0.1秒評価方式による30/49/3は本比較に混ぜません。

4件のorderingは必要なDeath / End pointが未成立でNEです。R2 Endは生成されていません。
R1 Endは観測時刻を保持し、固定canonical窓への時刻補正はしていません。

**4. 50 FAILの第一・二次阻害要因**

新しい評価結果と元raw / traceからnearest snapshot、coverage、event数、package窓を再計算し、
分類した後に過去表と照合しました。過去分類のコピーを新しい認識実績とは扱っていません。
第一阻害要因は排他的で合計50件です。

| 第一阻害要因 | 件数 | FAIL中の割合 |
| --- | ---: | ---: |
| snapshot_current_state_evidence | 15 | 30.0% |
| preparation_scope | 7 | 14.0% |
| snapshot_player_life_evidence | 5 | 10.0% |
| death_event_contract | 4 | 8.0% |
| remote_state | 4 | 8.0% |
| owned_visual_evidence | 4 | 8.0% |
| self_ownership | 2 | 4.0% |
| dead_ownership | 2 | 4.0% |
| map_resolution | 2 | 4.0% |
| round_end_time | 1 | 2.0% |
| smoke_state | 1 | 2.0% |
| expanded_map_state | 1 | 2.0% |
| spectator_coverage | 1 | 2.0% |
| teammate_ownership | 1 | 2.0% |

`snapshot_hud_gate` の第一阻害要因は0件です。歴史的な17件がPASSになったという意味ではありません。
current-frame state 15件、player life 5件、preparation 7件などが残ります。
二次条件は重複があるため第一阻害要因へ加算しません。

明示的なsnapshot不一致には、第一要因以外に `player_alive` が13件、HPが4件、
ammo/reload系が各3件、観戦対象の名前・HP・ammo・weapon・location系が各2件あります。
Death point 2件はsubject/transitionに加えてvictim名・killer agent・damage属性も必要です。
Death count 2件は正しいtype/actor/round/countが必要で、3属性を追加するだけでは成立しません。
interval 16件にはcoverage/edge/continuity依存があります。これらは確定した失敗述語と
実装依存の仮説をJSON内で区別しています。

native packageはR1 `[2.502669, 81.752669]` とR2 `[110.986003, 171.019336]` の2件。
R2の上端は録画終端のsentinelであり、正式Round Endではありません。
Snap数は3054 / 2281、native Fact数は2765 / 1648、TraceのSnapshotは合計5335です。
Factはtimer 3917件・HP496件で、既存のsource/ownership条件に従います。
Traceには独立したFact一覧を追加せず、既存adapterの投影契約を維持します。
Trace eventsはstate_snapshot 211、round_start 2、round_end 1、movement_state 1。
正式player_death / shotは0です。
map-labelled resolution行は6614ありますが、全件 `unknown` scope /
`calibration_required` でzone_idは0件です。map文字列の存在を解決成功とは数えません。

**5. 性能の実測と不足計測**

Full CLI wallは37,848.922秒（約10時間30分49秒）、main観測は6614フレーム、
0.174747 frames/secです。analyzer subprocessは37,813.932秒、元evaluatorは14.486秒。
今回の同一Trace評価は11.709秒、child CPU 11.641秒、peak RSS 47,775,744 bytesでした。
後者は評価だけの再実行であり、Fullの高速化率ではありません。

Fullのprocess CPU・peak RSS・全パス合計decoded frame countは保存artifactにありません。
未計測と記録し、今回の評価プロセスの値で埋めません。source inventoryのframe数や
matcher呼出数もdecoded回数の代用にはしません。main analyzed countは6614、
保存JPEGは7160です。Full directoryは2,620,135,102 bytesで、うちJPEGが2,561,939,854 bytes。
一時native bufferのpeakや既にcleanupされた容量をこの値から推測しません。

次はexclusive stage timeです。割合の分母はanalyzer collectorの37,812.315秒で、
CLI wallとは異なります。nested stageの子時間を親から除く実装を確認しました。

| Stage | Calls | Total sec | Average sec | Wall share |
| --- | ---: | ---: | ---: | ---: |
| hud_geometry | 35805 | 11811.971 | 0.329897 | 31.24% |
| hud_spectator | 17901 | 7126.819 | 0.398124 | 18.85% |
| hud_numeric_ocr | 17901 | 7014.728 | 0.391862 | 18.55% |
| native_lifecycle | 1 | 5221.008 | 5221.008445 | 13.81% |
| hud_identity | 71604 | 1538.169 | 0.021482 | 4.07% |
| native_frame_decode | 1 | 889.375 | 889.374706 | 2.35% |
| visual_analysis | 1 | 816.321 | 816.320755 | 2.16% |
| decode | 16 | 731.168 | 45.697987 | 1.93% |
| hud_signal_templates | 35802 | 172.439 | 0.004816 | 0.46% |
| visual_trigger_scan | 1 | 126.658 | 126.658263 | 0.33% |
| hud_menu | 35802 | 54.711 | 0.001528 | 0.14% |
| round_package_build | 1 | 48.346 | 48.346357 | 0.13% |
| trace_serialization | 1 | 14.348 | 14.347560 | 0.04% |
| hud_event_detection | 2 | 0.553 | 0.276610 | 0.00% |
| metadata_open | 1 | 0.296 | 0.296184 | 0.00% |
| event_fusion | 1 | 0.000 | 0.000155 | 0.00% |
| evaluator | 0 | 0.000 | 0.000000 | 0.00% |
| report_generation | 0 | 0.000 | 0.000000 | 0.00% |

geometry / spectator / OCRで68.64%。`hud_geometry` はanchorだけでなく
feature sequence全体を含むため、現データだけでanchorが31.24%と断定できません。
計測外の残余約2245秒を特定のrecognizerへ割り当てません。
native collectorのevaluator / report_generationはcalls 0です。evaluatorは外側の
command計測14.486秒を使い、report generationは未計測とします。0秒の実処理と解釈しません。

コード監査で、native lifecycle収集、HUD Pass A、adaptive final passのそれぞれが
観測処理を実行する経路を確認しました。`observe_frames()` はfeature sequence内で画像を読み、
後のframe loopでも `load_frame()` を呼びます。ただしsequenceのflash/killfeed/anchor安定性は
隣接フレーム依存です。Pass Aの完成観測をfinal passへそのまま流用する案は採用しません。
35,805 geometry / 17,901 OCR / 71,604 identity callsは部分処理・各passを含み、
そのままunique frame数や無駄な再計算回数とは扱いません。

追加のread-only監査では、同じfilename時刻のJPEGが545組あり、全組でbytes/hashが一致。
余分な546ファイルは196,243,386 bytesです。これはファイル重複の実測であり、
独立したPTS・source continuity証明ではありません。保存ファイルは削除していません。
decode stageは731秒（1.93%）なので、保存重複だけで10時間処理が大幅短縮するとは言いません。

**6. Issue #29への具体的な引継ぎ**

[既存Issue #29](https://github.com/shark-man0/eval_valorant_perspective/issues/29) はopenです。
同じ課題の新Issueは作りません。まず次の小さなPR候補を既存課題へ引き継ぎます。

| 候補 | 実測根拠・最小変更 | 必要な同一出力回帰 | 採用判断 |
| --- | --- | --- | --- |
| geometry内訳の追加計測 | 31.24%のstageをfeature sequence / anchor match / validateへ分ける。既存collectorを使い、Fullを新しく回さず短い固定source窓で計測 | 同じPTS/pixels、anchor結果、break、raw/Trace、adaptive change_timesが一致 | 第一優先の計測PR候補。まだ実装・速度改善未証明 |
| 純粋なframe特徴の限定再利用 | 同じフレームをsequenceとframe loop、複数passで処理する経路がある。pixel/hash/profile/decoder/preprocessをキーに実測 | temporal neighbor特徴・calibration retention・owner/Eventを毎passで再計算、出力一致、bounded RSS | キャッシュ範囲を証明後のみ。完成したrecognition結果は共有しない |
| JPEGの重複生成抑制 | 545組/196MBの同一bytes。既存safe frame cacheとactual-PTS解決の再利用可能性を確認 | exact ticks/time base/decoder identity/pixels、全requestとの対応、参照path・cleanupとWindows保存互換 | decode前の同一性を証明するまで提案。Full samplerを変更しない |
| OCR / spectator前処理の内訳 | 18.55% / 18.85%。同じcurrent ROIの不変な前処理だけを計測し、lookup/asset準備の繰返しを調査 | score/unknown/method/provenanceが完全一致、NCC/acceptance/negative不変 | 現時点で実際の重複量・高速化率は未計測 |

Issue #29にある19,703秒のwhole-native実験と、本候補のnative＋adaptive Full 37,849秒は
処理範囲が異なります。性能退行率として直接比較しません。大規模refactor、FPS低下、
frame skip、複数Full並列化は行っていません。

**7. 次に直すべき機能3件**

性能計測は上記 #29 をP0依存として扱い、認識・成立条件の改修は次の順で分けます。

| 優先 | 修正対象・該当箇所 | 必要なsource evidence / 最小再現 | 期待範囲と未解決条件 |
| --- | --- | --- | --- |
| 1 | Self Deathの資格付け済みEvent・属性経路。`experimental/numeric_death_session.py` / `numeric_death_release.py`、legacy `hud/temporal.py::_player_death_event` | 既存のnative連続窓、本人marker・victim・Report初出と残存/観戦/respawn負例。既存image replayとepisode field replayを使う | 直接4 FAIL＋ordering依存が候補。現時点の正式Eventは0。7 fatal-row観測やcandidateの正例成功だけで資格を与えない。点の3属性・Round所属・重複も必要 |
| 2 | current-frame state / identity producer。`hud/analyzers.py::observe_frames`、`hud/identity.py::live_identity`、`rounds/builder.py::_state_snapshots` | 固定source PTSでHP/Ability/Weapon・spectator exclusionを分解。24点の既存診断とsource-backed frame fixtureを再利用し、新readerだけ再認識 | state 15件、life 5件は別条件。state修正だけでowner/alive/数値/観戦semanticが成立するとは限らない |
| 3 | preparation membership。`rounds/builder.py::_preparation_context_start` / `_round_windows` / `_retain_unassigned_observations` | 最初は保存raw/lifecycleとcontractテスト。同一segmentのpreparation→startが不明なら、その連続窓のみ取得 | 直接7件。早期snapshotのstate/life/mapは二次依存。81.786/81.836秒のbreakを跨がず、Practical unknownをStrictに昇格しない |

単独修正で保証できるPASS増加はすべて0です。候補件数を合算して予告しません。
必要な正例・負例、source binding、ownershipと資格の不足を個別に記録し、同じ仮説の
微調整を反復しません。追加動画のデバイス移行は要求しません。

**8. 次回の低コスト検証と所要時間の根拠**

| 変更種別 | 再利用する既存経路 | 時間の根拠・制約 |
| --- | --- | --- |
| evaluator / Traceの変更 | `tests/e2e/evaluate_saved_trace.py`。transport変更はハッシュ検証済みrawを `run_real_video.py --from-raw` でadapterへ | 今回82件評価11.709秒。認識性能の比較にはしない |
| Snapshot / Fact / Package | `scripts/diagnostics/replay_snapshot_gate.py`＋対応contract / integration | original source/code/profile/qualification contextを保持。認識器変更にはrawを新結果として再利用しない |
| Self Deathのfield transport | `scripts/diagnostics/replay_death_episode_fields.py` | 既存171フレームの37.743秒はhash/pixel検証を含み、join自体0.087秒。すべてexposed regression |
| fatal Report row | 既存Report reader＋実装済みoptional reader、private frozen replay | 13フレーム3.176秒。7値/3episode annotation、formal Event 0。独立qualificationではない |
| 新しいimage reader / temporal | `scripts/diagnostics/replay_self_death_images.py` のverified-cache / native-window入口 | 同じ窓・code/profile/dependenciesで新しく認識。273/381/393秒など既存限定窓実測があり、全機能共通の秒数は約束しない |
| primary stateの点評価 | 既存 `run_dataset_case.py --mode targeted --category ...` | 旧profile13で6点70.788秒・sampled30点326.450秒の参考実測。新profileの性能値に転用しない |

最初にunit→contract/integration→固定source fixture→targeted→固定sampled→必要な
continuous→採用候補だけFullとします。境界/Deathは孤立点の成功から連続性を作りません。
候補に差分がなく、負例回帰がある、または資格が不足する場合は高コスト段階へ進めません。
raw再利用と画像cache再認識を区別し、同じsource/PTS/window/GT/evaluator/modeで比較します。

既存Traceの再評価例（private入力を明示、既存Fullを上書きしない）:

```bash
python3 tests/e2e/evaluate_saved_trace.py \
  --pack PRIVATE_VALIDATION_PACK \
  --trace ARCHIVED_RUN/e2e_trace.json \
  --output PRIVATE_NEW_RUN/evaluation_report.json
```

保存rawのsnapshot伝達再現例:

```bash
python3 scripts/diagnostics/replay_snapshot_gate.py \
  --raw ARCHIVED_RUN/raw_processing.json \
  --raw-sha256 VERIFIED_ORIGINAL_RAW_SHA256 \
  --targets PRIVATE_FIXED_TARGETS.json \
  --output PRIVATE_NEW_RUN/snapshot_transport.json
```

新機能・同等のreplayツールは追加していません。共通Python orchestrationとWindows/Piの
共通コードを使います。Full開始時は仮説、期待差分、再利用不能な理由、fingerprints、
独立qualification、時間/容量、排他・保全方法を記録します。

**9. 証拠不足と残るリスク**

Self subject / killer-victim / temporal正例とReport残存等の負例について、現recognizerの
独立資格付けは未完了です。match_001/002の既存exposureを隠してblind holdoutと呼びません。
一方で、これを理由に全実装・全分析へ追加動画移行を必須化しません。
mapには実sourceに対応するcalibration/asset、remote等には識別可能なcurrent interface、
preparationには同一segmentの所属根拠が必要です。どの項目もunknownを値で補いません。

旧レポートには17 gate、9 preparation、720 confidence-mapエラー、片方の動画しかないという
歴史的記述があります。本書の対象Fullではそれぞれgate 0、preparation 7、confidence失敗0。
現在のsource在庫や認識候補を旧Fullの結果へ逆輸入しません。

PR #53はPR #52のブランチをbaseとするDraft stackで、main向けの単独完了PRとは扱いません。
上流のtransport・ownership・subjectモデルと、新しい認識器のreview範囲を分ける必要があります。
別担当のRound PRを変更せず、mainマージも行っていません。
source commit `a9eca7b` のLinux/Windows（push/PR）とtext-I/Oの5 runはすべてsuccessでした。
CI成功はコード・契約・package smokeの証拠であり、実動画精度やFormal Death成立の証明ではありません。
今回の変更は文書・集約JSONだけで、新しいproduction認識やテストコード変更はありません。

**10. 全82件の今回再評価一覧**

以下の状態は保存Full候補のTraceを再評価した結果です。現在ブランチの新認識結果ではありません。
expected値とprivate source PTSの詳細はignored private matrix、公開表はID・状態・阻害fieldのみです。

| Assertion | Status | First blocker | Secondary failed fields / dependencies |
| --- | --- | --- | --- |
| GT-R1-ROUND-START | pass | — | — |
| GT-R1-DEATH | fail | death_event_contract | qualified_subject; native_temporal_transition; one_event_per_episode; lifecycle_membership; event_attribute:victim_name; event_attribute:killer_agent; event_attribute:combat_report_damage_received |
| GT-R1-ROUND-END | fail | round_end_time | source_backed_timing_and_event_meaning |
| GT-R2-ROUND-START | pass | — | — |
| GT-R2-DEATH | fail | death_event_contract | qualified_subject; native_temporal_transition; one_event_per_episode; lifecycle_membership; event_attribute:victim_name; event_attribute:killer_agent; event_attribute:combat_report_damage_received |
| ordering_constraints-000 | not_evaluated | point dependency | matched_point:GT-R1-ROUND-START; matched_point:GT-R1-DEATH |
| ordering_constraints-001 | not_evaluated | point dependency | matched_point:GT-R1-ROUND-START; matched_point:GT-R1-ROUND-END |
| ordering_constraints-002 | not_evaluated | point dependency | matched_point:GT-R1-DEATH; matched_point:GT-R1-ROUND-END |
| ordering_constraints-003 | not_evaluated | point dependency | matched_point:GT-R2-ROUND-START; matched_point:GT-R2-DEATH |
| GT-R1-BUY-FLAG | fail | preparation_scope | source_continuity_and_interval_edges |
| GT-R1-ASTRAL-1 | fail | remote_state | source_continuity_and_interval_edges |
| GT-R1-ASTRAL-2 | fail | remote_state | source_continuity_and_interval_edges |
| GT-R1-SMOKE | fail | smoke_state | source_continuity_and_interval_edges |
| GT-R1-COMBAT-REPORT | pass | — | — |
| GT-R2-BUY-FLAG | fail | preparation_scope | source_continuity_and_interval_edges |
| GT-R2-BUY-MENU-1 | fail | preparation_scope | source_continuity_and_interval_edges |
| GT-R2-BUY-MENU-2 | fail | preparation_scope | source_continuity_and_interval_edges |
| GT-R2-ASTRAL-1 | fail | remote_state | source_continuity_and_interval_edges |
| GT-R2-ASTRAL-2 | fail | remote_state | source_continuity_and_interval_edges |
| GT-R2-EXPANDED-MAP | fail | expanded_map_state | source_continuity_and_interval_edges |
| GT-R2-SPECTATOR | fail | spectator_coverage | source_continuity_and_interval_edges |
| OWN-R1-SELF | fail | self_ownership | source_continuity_and_interval_edges; qualified_current_subject; current_or_qualified_temporal_life |
| OWN-R1-SELF-DEAD | fail | dead_ownership | source_continuity_and_interval_edges; qualified_current_subject; current_or_qualified_temporal_life |
| OWN-R2-SELF | fail | self_ownership | source_continuity_and_interval_edges; qualified_current_subject; current_or_qualified_temporal_life |
| OWN-R2-SELF-DEAD | fail | dead_ownership | source_continuity_and_interval_edges; qualified_current_subject; current_or_qualified_temporal_life |
| OWN-R2-TEAMMATE | fail | teammate_ownership | source_continuity_and_interval_edges; qualified_current_subject; current_or_qualified_temporal_life |
| GT-R1-SNAP-0035 | fail | snapshot_current_state_evidence | primary_state, player_alive, location_label_raw |
| GT-R1-SNAP-0415 | fail | snapshot_current_state_evidence | primary_state, player_alive, location_label_raw |
| GT-R1-SNAP-475 | fail | snapshot_current_state_evidence | primary_state, player_alive, nonself_killfeed_row_visible |
| GT-R1-SNAP-585 | fail | snapshot_current_state_evidence | primary_state |
| GT-R1-SNAP-595 | fail | snapshot_current_state_evidence | primary_state, vision_obscured_smoke |
| GT-R1-SNAP-705 | pass | — | — |
| GT-R1-SNAP-728 | fail | snapshot_current_state_evidence | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible |
| GT-R1-SNAP-733 | fail | snapshot_current_state_evidence | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible |
| GT-R1-SNAP-734 | fail | snapshot_current_state_evidence | primary_state, player_alive, ammo_mag, ammo_reserve, reload_animation_visible |
| GT-R1-SNAP-7425 | fail | snapshot_current_state_evidence | primary_state, player_alive, player_hp, muzzle_flash_visible, location_label_raw, spectator_primary_state |
| GT-R1-SNAP-7438 | fail | snapshot_current_state_evidence | primary_state, player_alive, muzzle_flash_visible |
| GT-R1-SNAP-7440 | fail | snapshot_player_life_evidence | player_alive |
| GT-R1-SNAP-7445 | fail | snapshot_player_life_evidence | player_alive, score_enemy |
| GT-R2-SNAP-820 | fail | preparation_scope | current_frame_state; player_ownership_and_life; required_fields_not_evaluable_until_membership |
| GT-R2-SNAP-1050 | fail | preparation_scope | current_frame_state; player_ownership_and_life; required_fields_not_evaluable_until_membership |
| GT-R2-SNAP-11145 | fail | snapshot_player_life_evidence | player_alive |
| GT-R2-SNAP-143 | fail | snapshot_current_state_evidence | primary_state, player_alive, player_hp |
| GT-R2-SNAP-1475 | fail | snapshot_current_state_evidence | primary_state, player_alive, player_hp |
| GT-R2-SNAP-1476 | fail | snapshot_current_state_evidence | primary_state, player_alive, player_hp |
| GT-R2-SNAP-1477 | fail | snapshot_player_life_evidence | player_alive |
| GT-R2-SNAP-149 | fail | snapshot_current_state_evidence | primary_state, player_alive |
| GT-R2-SNAP-151 | fail | snapshot_current_state_evidence | primary_state, player_alive, view_owner, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, spectated_location_label_raw |
| GT-R2-SNAP-170 | fail | snapshot_player_life_evidence | player_alive, spectated_name, spectated_hp, spectated_ammo_mag, spectated_ammo_reserve, spectated_weapon, muzzle_flash_visible, spectated_location_label_raw |
| GT-R1-SNAP-0035-DERIVED-zone_id | fail | map_resolution | zone_id |
| GT-R1-SNAP-0415-DERIVED-zone_id | fail | map_resolution | zone_id |
| GT-R2-SNAP-820-DERIVED-zone_id | fail | preparation_scope | current_frame_state; player_ownership_and_life; required_fields_not_evaluable_until_membership; map_resolution |
| GT-R1-MUZZLE-1 | fail | owned_visual_evidence | current_self_owner; qualified_visual_action; source_bound_event_export |
| GT-R1-MUZZLE-2 | fail | owned_visual_evidence | current_self_owner; qualified_visual_action; source_bound_event_export |
| GT-R1-MUZZLE-3 | fail | owned_visual_evidence | current_self_owner; qualified_visual_action; source_bound_event_export |
| event_count_constraints-000 | pass | — | — |
| event_count_constraints-001 | fail | death_event_contract | qualified_subject; native_temporal_transition; one_event_per_episode; lifecycle_membership |
| event_count_constraints-002 | pass | — | — |
| event_count_constraints-003 | fail | owned_visual_evidence | current_self_owner; qualified_visual_action; native_event_export; event_count_scope |
| event_count_constraints-004 | pass | — | — |
| event_count_constraints-005 | fail | death_event_contract | qualified_subject; native_temporal_transition; one_event_per_episode; lifecycle_membership |
| event_count_constraints-006 | pass | — | — |
| NEG-REMOTE-R1A | pass | — | — |
| NEG-REMOTE-R1B | pass | — | — |
| NEG-REMOTE-R2A | pass | — | — |
| NEG-REMOTE-R2B | pass | — | — |
| NEG-ASTRAL-NOT-SMOKE | pass | — | — |
| NEG-SMOKE-NOT-ASTRAL | pass | — | — |
| NEG-SMOKE-WORLD-SPOT | pass | — | — |
| NEG-NONSELF-KILLFEED | pass | — | — |
| NEG-RELOAD-NOT-SHOT | pass | — | — |
| NEG-BUY-MENU-1 | pass | — | — |
| NEG-BUY-MENU-2 | pass | — | — |
| NEG-SPECTATOR-COUNT-TEXT | pass | — | — |
| NEG-DEAD-PLAYER-MECHANICS | pass | — | — |
| NEG-EXPANDED-MAP-MECHANICS | pass | — | — |
| NEG-SPECTATOR-POISON-151 | pass | — | — |
| NEG-SPECTATOR-POISON-170 | pass | — | — |
| NEG-STALE-COMBAT-REPORT | pass | — | — |
| NEG-R2-NO-ROUND-END | pass | — | — |
| NEG-SAME-ZONE-CALLOUT-CHANGE | pass | — | — |
| NEG-CONTENT-JUMP-SPAN | pass | — | — |

**11. この収束Goalの確認**

現在E2Eの有無・保存候補の有効範囲を判定し、元成果物は保全しました。
82件を同じ評価基準で再評価し、50件を排他的第一要因と二次条件に分解しました。
修正可能なtransport/計測経路と独立証拠不足を分け、既存replayで再現可能な対象と
Issue #29への最小計測・改修候補を示しました。main・GT・資格・閾値は変更していません。
**これは検証の収束・修正計画の完了であり、Self Death認識器やStrict E2E精度改善の完了ではありません。**
