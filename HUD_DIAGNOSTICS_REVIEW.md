# Windows E2E 上流診断（2026-10-01）

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
