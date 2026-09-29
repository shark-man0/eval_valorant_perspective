# HUD実データ検証レポート v2

## 検証対象

- 1920x1080スクリーンショット: 12枚
- 動画: `Valorant_09-25-2026_0-37-29-379.mp4`
- 約171.02秒 / 1920x1080 / 60 fps / H.264
- AAC 48kHz stereo: 3 streams

## 実データで確認できた状態

- 通常一人称
- 購入フェーズbanner
- 購入menu
- Astra astral form
- smoke等の視界遮蔽
- round end banner
- combat report
- death/spectator
- expanded tactical map

## v1レビュー反映

1. HUD AnalyzerとVisual Analyzerの責務を分離し、全eventのproducerを `event_source_contract_v1.json` に定義。
2. `spectator_first_person` の検出条件を追加。
3. buy-phase / round-endの重複ROIを前提に、score/timer/state sequenceで分類する契約へ変更。
4. Agent metadataなしでもX logical slotからUltimate availabilityを扱えるcontractを追加。
5. HUD confidenceとAI Coach final confidenceを別レイヤーとして明文化。
6. kill sideをalive-count差分 + kill-feed補助で決定する規則を追加。
7. Astra専用primary stateを廃止し、汎用 `remote_control_view` + subtypeへ変更。
8. flash detection / tactical-map transition / HUD-scale calibrationを追加。
9. Round `observation_quality` 集約式を定義。
10. Spike 8状態のうち、MVPで高信頼に直接判定する範囲を明示。
11. weapon識別と複数audio track再生の契約を明示。

## 注意

今回の実動画にはFlashやCypher/Sova/Skye remote-view、HUD Scale変更は十分な検証例がない。これらはsynthetic contract testのみであり、実動画検証済みとは扱わない。

また、HUD Analyzerだけではshot/peek/movement/engagement/rotation等は生成できない。これらはVisual Analyzer実装が必要である。
