# VALORANT Video / HUD Analyzer 実装仕様 v2

## 1. 目的

ユーザー提供の 1920x1080 / 60 fps VALORANT 録画から、AI Coach前段の**観測事実**を抽出する。HUD Analyzerはプレイの良し悪しを判断しない。

本仕様は `valorant_codex_ready_bundle_v3` を変更せず追加するパッチであり、`round_package_schema_v2.json` / `event_type_registry_v2.json` / Rule Engineとの接続境界を明示する。

検証データ:
- 1920x1080スクリーンショット 12枚
- `Valorant_09-25-2026_0-37-29-379.mp4`
- H.264 / 1920x1080 / 60 fps / 約171秒
- AAC stereo × 3 tracks

## 2. 最重要: HUD Analyzer と Visual Analyzer の責務

実動画から31種類超のイベントをHUDだけで生成することはしない。

```text
VideoProbe
  -> FrameSampler
       ├-> HudStateClassifier -> ROI Readers -> HudObservation[]
       └-> VisualAnalyzer ----------------------> VisualObservation/Event candidates
                         ↓
                DerivedEventBuilder
                         ↓
                  RoundPackageBuilder
```

### HUD AnalyzerがMVPで直接生成するイベント

- `round_start`
- `round_end`
- `kill`
- `player_death`
- `spike_planted`
- `ability_state`
- `buy_phase`
- `status_effect`（映像/HUDで確実に観測できるもののみ）

### HUD Analyzer単独では生成しない主なイベント

`shot / movement_state / preaim_started / peek / info_peek / engagement_start / engagement_end / position_change / position_hold / rotation_started / rotation_completed / enemy_spotted / enemy_lost / utility_used / ally_entry_start / ally_enter_site / enemy_reengage / hold_angle / site_state / utility_effect_observed` 等。

これらは **Visual Analyzer** の責務である。全イベントの正式な生産元は `config/event_source_contract_v1.json` を正とする。

したがって、HUDパッチだけの完成を「全評価ルールが実動画で動作可能」とみなしてはならない。Mock Round Packageによる本体E2Eと、実動画から全評価イベントを生成する機能は別の完了条件とする。

## 3. 入力・Calibration

正式対応:
- 16:9
- 1920x1080基準
- 30/60 fps
- 標準HUD位置

ROIはnormalized座標で保存するが、**解像度比例だけで利用しない**。開始時に `round_timer / top_match_bar / player_hp_armor / abilities` のアンカーを検出し、3個以上が基準位置・サイズと整合するときのみROIを有効化する。

`hud_layout_1080p_v3.json` の許容範囲を超える場合は `calibration_required`。同じ1920x1080でもゲーム内HUD Scaleが異なる場合を検出対象に含める。

## 4. 2-pass sampling

### Pass A
- 2 fps: timer / score / roster / HP / state / spike
- 4 fps: kill feed / banner / status change

### Pass B
以下の周辺を10-15 fpsで再解析:
- kill feed差分
- HP急変
- alive count変化
- spike変化
- score/timer reset
- combat report出現
- banner出現
- primary_state遷移

Aim/peek/movement/engagementの高密度解析はVisual Analyzerが担当する。

## 5. Screen State Classifier

### primary_state
- `live_first_person`
- `spectator_first_person`
- `remote_control_view`
- `buy_menu_open`
- `expanded_tactical_map`
- `unknown`

### remote_view_type
- `none`
- `astra_astral`
- `cypher_camera`
- `sova_drone`
- `skye_trailblazer`
- `other`
- `unknown`

Astraだけを特別なprimary stateにしない。Cypher/Sova/Skye等の「本人の通常一人称ではない視点」を共通の `remote_control_view` として扱う。未実装のAgent固有判定は `remote_view_type=unknown` でよい。

### state_flags
- `buy_phase_banner`
- `combat_report_visible`
- `round_end_banner`
- `vision_obscured_smoke`
- `vision_obscured_flash`
- `visual_transition`

### spectator_first_person

最低2シグナルで確定:
1. `spectated_player_panel` の存在
2. self HUD identityの消失/不一致、または直前のplayer_death候補

観戦中のHP/ammo/abilityを対象プレイヤー自身の値として保存しない。`player_specific_hud_valid=false` とする。

### remote_control_view

色相だけで確定しない。Astraは少なくとも astral-map geometry / hand-interface / palette の複合特徴で判定する。他Agentの特殊視点は専用templateがない限り subtype unknown を許容する。

### smoke / flash

Smokeは「低エッジ密度・低空間情報量・色の広域均一性・HUD anchor安定」を組み合わせる。壁接近や暗所だけでsmokeにしない。

Flashは「急激な全画面輝度/彩度変化・scene detail collapse・短い立上がり/減衰・HUD anchor安定」を利用し、smokeとは別flagにする。

## 6. Buy Phase Banner と Round End Banner

2つのROIがほぼ同じ位置にあるのは正常であり、**ROI presenceだけで分類禁止**。

Buy Phaseを支持:
- score変化なし
- sequenceがlive stateへ遷移
- timer/phase contextがpre-roundとして整合
- text hint `購入フェーズ` は補助

Round Endを支持:
- ±3秒程度でscore更新
- timer停止/消失やcombat reportとの相関
- 次stateがbuy phaseへ遷移
- 勝敗/TEAM ACE系textは補助

分類不能なら両flagを出さずconfidenceを下げる。

## 7. HUD Readers

### Timer / Score
数字templateを第一候補、digits-only OCRをfallback。両者が食い違う場合は時系列整合性を優先しconfidenceを下げる。

### Alive Count
roster portrait livenessを2サンプル以上で確定。kill feedと一致するとconfidenceを上げる。

### Kill Feed / kill side
名前OCRはMVP必須ではない。

Kill rowが出た時刻の前後でalive countを比較する。
- allyだけ 1 減少 -> `victim_side=ally`
- enemyだけ 1 減少 -> `victim_side=enemy`
- kill-feed色/配置が一致し、通常キルであることが確認できる場合のみ killer_side を反対側として確定
- 両方減少、差分なし、環境死/自滅等が疑われる -> sideは`unknown`

名前やsideを推測で埋めない。

### HP / Armor / Ammo
spectator/remote view等で帰属不能ならnullまたは `player_specific_hud_valid=false`。

### Spike
MVPで直接高信頼に扱う:
- `carried_by_player`
- `planted`
- `unknown`

`carried_by_ally / dropped / defusing / resolved` は、追加の明確なUI/visual evidenceがある場合のみ生成する。取得できない状態を無理に8値へ分類しない。

### Abilities / Ultimate
Agent名対応表をMVP必須にしない。標準HUDの4 logical slotsを `C/Q/E/X` として扱い、X slotを `semantic_role=ultimate` とする。`config/ability_slot_contract_v1.json` を正とする。

これによりAgent metadataがなくても、ultimate slotのavailable stateが高confidenceで読めれば `ultimate_available` Factを生成できる。ability_nameはnull可。

### Weapon
ammo数だけから武器名を推測しない。inventory icon template registryをprimary、実際に文字ラベルが見える場合だけOCRをfallbackとする。`weapon_visual_registry_contract_v1.json` に従いunknownを許容する。

## 8. Observation -> Event / Derived Event

HUD event生成とVisual event生成を分離する。HUD eventは2節の一覧に限定する。

### player_death
原則2ソース:
- combat report appearance
- spectator transition / self HUD identity loss / roster death state

### round boundary
単一シグナルに依存しない。banner、score、timer/state transitionを統合する。

### spike_planted
spike HUD state + timer/top-center state等、可能なら2ソース一致。

Derived Event Builderは`state_snapshot / save_decision / objective_state`などをHUD/Visual eventsから構成する。評価語をattributesへ入れない。

## 9. Confidence: 2つのレイヤーを混同しない

### HUD Observation acceptance
- >=0.85: HUD observationを直接採用可
- 0.65〜0.8499: second-source / temporal cross-check後に採用
- <0.65: null/unknown

### AI Coach final evaluation
本体v3の閾値を維持:
- >=0.75: 通常表示
- 0.55〜0.7499: 要確認
- <0.55: 原則UNSCORED/抑制

前者は**入力事実の信頼度**、後者は**最終評価の信頼度**であり別物。

Deterministic Factのconfidenceは、必要観測ソースconfidenceの最小値（cross-check後）を基本とし、final evaluation scaleへの再マッピングはしない。

## 10. Round observation_quality 集約

フレーム単位 `quality` からRound Packageへ以下で集約する。

- `timeline_completeness = valid_observed_duration / round_duration`
- `hud_confidence = median(valid frame hud_confidence) * timeline_completeness`
- `visual_confidence = median(valid visual_confidence) * visual_timeline_completeness`
- `missing_intervals`: 1.0秒以上連続して必要観測が得られない区間を列挙

primary_stateがspectator/remote_control/buy_menu等の場合、player-specific HUDやworld-view visualの「意図的に無効な区間」は該当readerのcompletenessには含めない。ただしRound全体の状態遷移履歴には残す。

## 11. Expanded Map Transition

fade-in/outや半透明途中フレームは `visual_transition`。0.25秒の保護窓ではworld-view/minimap由来のsensitive visual inferenceを停止する。安定state確定まで無理にlive/mapへ二値分類しない。

## 12. Audio

MVP評価では音声解析しない。clip生成では全audio streamを保持。

Playback UI:
- container default flagがあればそのtrackを初期選択
- 無ければ先頭track
- 複数track時はユーザーが切替可能
- 選択をsettingsへ保存
- game/mic/mixの自動同定はMVP外

## 13. OCR / Template priority

数字HUD: template matching -> digits-only OCR fallback。

両者が不一致:
1. 前後フレームとの時系列整合性
2. 各backend confidence
3. それでも解消不可 -> null

日本語location / player namesはMVP必須ではない。

## 14. Storage

全フレーム保存は禁止。保存:
- observation/eventに採用したframe refs
- dense-analysis候補周辺
- 最終クリップ
- debug mode時のみROI crop（容量上限付き）

## 15. 実動画で確認済み / 未確認

確認済み:
- live first person
- buy phase/banner/menu
- Astra astral form（remote_control_viewとして扱う）
- smoke obstruction
- round-end/combat report
- expanded map
- spectator

未確認のためsynthetic testで契約のみ定義:
- flash
- Cypher/Sova/Skye remote control views
- HUD Scale変更
- ally-carried/dropped/defusing spike

未確認状態は「実動画で動いた」と主張してはならない。

## 16. テスト

- `tests/hud_state_samples_v2.json`: 実動画アンカー
- `tests/hud_logic_cases_v1.json`: synthetic logic cases

最低限、banner disambiguation / spectator / remote view / kill side / flash-vs-smoke / transition / ultimate slot / confidence aggregation / calibration_requiredをテストする。
