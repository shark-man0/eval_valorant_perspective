# Visual Analyzer v2 統合記録

2026-09-28。Visual v2を既存v3/HUD v2へ追加しました。これは実装とテストの記録です。
**実VALORANT録画での認識精度を保証するものではありません。**

## 1. 変更したファイル

`src/valorant_ai_coach/` 以下の主な追加・変更:

| ファイル | 責務 |
| --- | --- |
| `visual/models.py` | 正本形式のVisualObservation / EventCandidate / EvidencePoint |
| `visual/pixels.py` | OpenCV特徴、テンプレート、短時間tracking、minimap、固定論理slot差分 |
| `visual/remote.py` | 汎用remote fallback、特殊視点の優先順位 |
| `visual/core.py` | 時系列の事実抽出、burst/engagement FSM、イベント候補 |
| `visual/policy.py` | Visual専用confidence、独立証拠、明示的v3投影 |
| `visual/zones.py` | 静的polygon/site/peek anchor解決 |
| `visual/semantic.py` | 独立した事実確認API、永続予算・結果再利用 |
| `visual/fusion.py` | producer契約とconfidenceに基づく競合解決 |
| `visual/sampling.py` | 正本設定による候補窓と15fps抽出計画 |
| `visual/runtime.py`, `visual/analyzer.py` | 実フレーム処理、状態/鮮度ゲート、観測・候補の返却 |
| `application/hud_video_processor.py` | HUD readerの5fps監視、CV候補→密解析→fusion→Round Package |
| `rounds/builder.py`, `schema_validation.py` | strict Schema検証、Visual空間/Zoneをsnapshotへ投影 |
| `application/pipeline.py` | Visual監査JSON・採用証拠画像保存、再開fingerprint更新 |
| `bootstrap.py`, `settings.py`, `ui/{backend,contracts,settings_dialog}.py` | 本体への組込みとVisual設定UI |

追加テストは `tests/unit/test_visual_{core,pixels,semantic}_v2.py`、
`tests/integration/test_visual_runtime_v2.py` です。

Visual ZIP全体は `config/visual_v2/` に元のディレクトリ構造・内容のまま保持しました。
同名のAbility Slot契約はHUD版とVisual版で内容が異なるため、上書きしていません。
実装用の任意profile例は `config/visual_runtime.example.json` です。

## 2. 実装したVisual機能

- VisualObservation生成・検証と、candidate / confirmed / suppressedの保存。
- ammo差分と低コストrecoil/muzzle特徴による独立した候補起動。reload・武器変更を除外し、full-autoをburst開始としてまとめます。
- マクロminimap変位と、shot直前のoptical flow/weapon bobを分離。camera motionとtranslationが解けなければshot時のmovingはnullです。
- 校正した色/テンプレートによる可視entity候補、短時間の一対一tracking、primary target選択、head alignment。頭部を検出できなければnullです。
- enemy_spotted/lost、engagement開始/終了、再交戦のhysteresisとdebounce。
- stationary/安定view/既知cornerまたは可視headでのみpreaimの観測leadを測定。移動preaimは低confidence候補に限定し、homography逆投影はありません。
- cover/revealテンプレートとtranslationからpeek候補。info_peekは新情報・射撃なし・re-coverの列を要求し、semantic確認なしではconfirmedになりません。
- position change/hold、hold_angle、粗いZone間rotation、校正した味方markerのsite境界通過によるally entry。
- HUD ability差分とcast cueによるutility_used、可視人数中心のsite_state、確認済み対象陣営に限るutility_effect_observed。

これらは**観測値が揃った場合の検出・変換経路**です。全Agent・全Mapで必要な認識profileが同梱されているわけではありません。

## 3. HUDとの統合

本体の実HUDモードは `RealVisualAnalyzer` を使用します。従来のNull実装は差し替え・テスト用途として残しています。

HUDの同じROI readerを常時5fpsで実行し、広域2fpsサンプルと統合します。Visual triggerから必要な窓のみ15fpsへ昇格します。元動画全体をVision APIへ送りません。

- 観戦、remote、buy menu、tactical overlay、unknownでは本人mechanicsを生成しません。
- smoke/flash中もHUDの本人帰属が安全ならshot候補を扱います。Aim/Peek等はworld-viewゲートを通しません。
- remoteはAgent専用テンプレート以外にも、通常HUD/手元の消失・ability遷移・remote overlayの組合せを利用可能です。OCRの失敗だけを「HUD消失」とは扱いません。
- C/Q/E/XはHUDの固定slot indexから変換し、キー文字をOCR比較しません。
- 同一事実の競合はconfidenceと許可producerを照合します。近いconfidenceで内容が対立した場合は未解決として抑制します。
- candidate専用fieldをv3 Eventへ流しません。空間snapshotも許可された5fieldだけを明示的にコピーします。
- JSON監査結果は `matches/<id>/hud-analysis.json` の `visual_observations` / `visual_candidates` / `visual_events` に保存。証拠画像は同階層の `hud-evidence/` に保存します。

## 4. 未実装・低confidence扱い

- 本番Map用のpolygon/正規化minimap変換/peek anchorデータは未提供です。テスト用 `TEST_MAP` を本番データとして自動採用しません。
- 未校正のoutline色、明滅、画像差分だけでは敵・射撃等の高confidence事実にしません。profileなしでも候補監視は動きますが、多くの項目はunknownになります。
- 遮蔽、camera turn、weapon bobの競合、高速移動中のpreaim、Agent別effect識別は保守的に扱い、実録画での調整が必要です。
- info_peek、utility対象陣営、crossfire/riskなどsemantic確認が必要なfieldは、未確認ならcandidate/nullのままです。
- オプションのnative-fps Pass D、auto site-anchor fallback、音声解析、3D再構成、hidden enemy推測、全弾カウントは実装していません。
- Minimapの回転/ズームを自動で全Mapへ校正する機能はありません。north-upの正規化対応を校正したprofileが必要です。
- 1時間以上の実録画での処理時間・ディスク/メモリ消費は未測定です。計画・抽出は分割していますが、観測JSON全体はメモリに保持します。

## 5. テスト結果

最終結果は末尾に記録しています。

- 添付 `validate_visual_patch.py` を無改変で実行: 成功（25契約、33ケース、8参照窓）。
- 添付33ケースを実装コンポーネントへ入力する回帰テスト: **33件成功**。元JSONの期待値は変更していません。
- 既存本体dataset: **38 cases OK**。
- 元ZIPとのbyte比較: 本体 **87件**、HUD **8件**、Visual **31件**が一致。
- 既存・追加テストの全体結果、coverage、静的検査は末尾の最終検証欄を参照してください。

## 6. 実動画で確認できた範囲

元の `Valorant_09-25-2026_0-37-29-379.mp4` は今回も未提供です。
添付の8枚の静止画（960×540）は実際にOpenCVで読み込み、正本VisualObservationを生成して検証しました。
ただし疎な静止画からshot/peek/movementの精度を検証したとは扱いません。

合成動画では、実FFmpeg encode/decode→校正HUD→Visual処理→Round Package→SQLiteの既存E2Eを実行し、成功しました。
別の統合試験では、実画像CVとHUD ammo時系列を使用してburst eventを生成し、strict Round PackageとSQLite保存まで検証しました。
**これらは実ゲーム映像の適合率・再現率の証明ではありません。**

## 7. Semantic Vision AI

既定OFFです。設定画面で専用モデルと有効化を選び、Mock AIもOFFにした場合のみ呼び出します。
Mock AIがONなら、有効化チェックが残っていても外部へ送信しません。

用途は候補窓のcover/re-cover、可視utility対象、可視crossfire/risk、低confidenceのcorner alignment補助などです。
Coachのルール・評価結果・会話履歴は入力しません。露出方向数を返せるfieldもAPI Schemaにありません。
画像と時刻だけを独立したResponses APIリクエストへ送り、strict factual Schemaで検証します。

API形式は公式の [画像入力](https://developers.openai.com/api/docs/guides/images-vision) と
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) に沿っています。
この作業では有料API呼び出しを行っていません。接続層はモック応答で検証しました。

## 8. API上限

- **1 round 8回 / 1 match 96回**。境界不明区間は1つのpartial予算にまとめます。
- **micro窓12枚 / round context 24枚**。超過時は時系列から均等選択します。
- SQLiteのトランザクションで送信前に枠を確保。失敗・拒否も消費し、SDKの自動retryは無効です。
- `visual-semantic-budget.sqlite` に試行を永続化。成功した事実JSONを再開時に再利用し、同じ窓への追加呼び出しを避けます。
- 上限到達はunknown/candidateへ戻し、自動で予算を増やしません。既定timeoutは1リクエスト60秒です。

## 9. 今後必要なMap/Zone・認識profile

最低限、Mapごとに正規化minimapのA/B Site、Mid、Spawn、Main、Link等の粗いpolygonとsite境界を作成してください。
PEEK-04には、人が登録したpeek anchor・半径・露出方向数が必要です。位置/Zoneが一致し、confidenceが0.9以上の場合だけ使用します。

任意のVisual profileの主なfield:

- `validated`: 実データで調整後にのみtrue。
- `rois`: `world` / `weapon` / `minimap`を `[x0,y0,x1,y1]` の正規化座標で指定。minimapは既存HUD ROIを既定として再利用します。
- `minimap_north_up_calibrated`: 静的Mapとの向き・範囲が一致する場合のみtrue。
- `outline_colors_hsv`, `minimap_colors_hsv`: sideごとの `lower` / `upper` / `min_area_px`。色のみのentity候補は低confidenceです。
- `crosshair_template`, `corner_template`, `enemy_body_template`, `enemy_head_template`, `ally_body_template`, `muzzle_template`, `cast_template`, `world_effect_template`, `cover_template`, `revealed_region_template`: 必要なものだけ画像を指定。
- `normal_weapon_hud_template`, `normal_hands_template`, `remote_templates`: 通常表示の消失と特殊interfaceの確認用。
- `map_registry`, `peek_registry`: 契約形式のJSON objectまたはprofile基準の相対JSONパス。

画像パスもprofile基準の相対パスで指定できます。空欄・未登録なら捏造せず未観測になります。
Cypher Camera / Sova Drone / Skye Trailblazer、HUD Scale差、smoke/flash、武器変更を含む連続した実映像で検証が必要です。

## 10. Windows実行・exeへの影響

Python依存の追加はありません。既存のPython 3.12 / PySide6 / OpenCV / FFmpeg手順を使用します。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-windows.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe -m valorant_ai_coach
.\.venv\Scripts\python.exe config\visual_v2\tests\validate_visual_patch.py
.\build_windows.ps1
```

設定画面で「実HUD」、校正済みHUD JSON、必要ならVisual profileを選択してください。
最初はMock AIをON、Visual SemanticをOFFで観測を確認してください。
PyInstallerはconfig全体を収録するためVisual契約・Schemaも同梱されます。
利用者固有のprofile・テンプレート・Map JSONは外部フォルダとして一緒に配布します。
出力は `dist\VALORANT-AI-Coach\VALORANT-AI-Coach.exe`、フォルダごと配布します。
Windows実機での起動・`.exe`生成はこのmacOS環境では未確認です。

## 最終検証

- レビュー修正後の全体テスト: **296 passed / 1 skipped**（19.61秒）。coverage **79.46%**、必要値75%を満たしています。
- Ruff: 成功。mypy: 66 source filesでエラーなし。
- 正本Visual validator: 成功（25 event contracts / 33 logic cases / 8 reference windows）。本体dataset validator: 38 cases成功。
- 元ZIPとのバイト比較: 本体config/schemas/testsの87ファイル、HUDの同範囲8ファイル、Visualパッチ全31ファイルが一致しています。
- GUI offscreen smoke test: 終了コード0。macOSの音声デバイス・代替フォント警告は発生しました。
- skip 1件は元のVALORANT録画が未提供の実動画anchorテストです。添付8静止画のデコード確認は、連続した実プレイでの検出精度検証とは区別しています。
- 実OpenAI API呼び出し、Windows実機起動、Windows `.exe` ビルドは未確認です。

## レビュー指摘6件の修正（2026-09-28）

- **停止判定**: smoke/flash等でworldが観測不能、またはcamera rotationを除外できない場合、shotのmovingをnullにします。ammoに基づくshotは維持します。v3の単一confidenceを使うため、movingを含める場合は移動証拠のconfidenceを上限とし、弱い移動証拠が強いammo証拠で昇格しないようにしました。
- **Preaim**: 敵出現時の明確なprimary headとの位置整合を要求します。頭部未検出・複数対象の曖昧さ・照準から離れた出現では確定leadを出しません。出現前の静的cornerによる観測は利用できますが、それだけでは出現後の対象への照準を保証しません。lead区間中の弱いconfidenceも保持します。
- **Info peek**: 既知の敵と新規に観測された敵を区別します。Semanticによる「新情報なし」はピーク途中のフレームでも保持し、後の復帰フレームで消えないようにしました。
- **Primary target**: 各フレームで頭部参照と照準距離を再確認し、対象変更・頭部追跡喪失・曖昧な同距離を扱います。
- **World ROI**: entity検出を設定済みworld領域に限定し、既知のminimap/weapon ROIを除外します。検出box/head座標は元画面の正規化座標へ戻します。
- **Semantic入力失敗**: 画像の読み込み失敗は診断ログ付きの棄権とし、API送信・予算消費をせず解析を継続します。

変更コードは `visual/core.py`, `visual/pixels.py`, `visual/semantic.py`, `visual/runtime.py`。
Visual実装fingerprintを2へ更新し、旧解析の再開結果をそのまま再利用しないようにしました。
正本Schema・設定JSON・添付テストデータは変更していません。依存関係・Windowsビルド手順の変更もありません。

新規回帰テストは `tests/integration/test_visual_review_regressions.py` と
`tests/unit/test_visual_io_regressions.py` の計15ケースです。
否定ケースだけでなく、信頼できる停止・正しい照準・新情報のあるpeek・有効な画像入力が引き続き通ることも確認しています。
独立レビューで見つかった頭部不明時とピーク途中の否定証拠の境界ケースも含めています。
実ゲーム連続動画での認識精度とWindows実機確認は、前述のとおり別途必要です。
