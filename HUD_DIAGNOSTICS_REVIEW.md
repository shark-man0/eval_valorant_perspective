# Windows E2E 上流診断（2026-10-01）

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
