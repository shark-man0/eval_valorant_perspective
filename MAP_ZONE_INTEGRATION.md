# Map / Zone v3 統合

## 1. 変更ファイル

- `config/map_zone_v3/`: 添付ZIPを変更せず格納。設定・Schema・参照画像・原本テスト。
- `src/valorant_ai_coach/maps/{registry,resolver,calibration}.py`: データ検証、選択、画像校正、位置解決。
- `src/valorant_ai_coach/visual/{map_pipeline,map_consumer}.py`: 校正済み座標の追跡と位置解決、Visual側のイベント生成。
- `visual/{core,runtime,analyzer}.py`: 新しいタイムラインの受け渡し。旧 `visual/zones.py` は削除。
- `rounds/builder.py`, `schema_validation.py`, `application/{hud_video_processor,pipeline}.py`: 厳密な検証、v3への明示的な射影、監査JSON保存。
- `settings.py`, `bootstrap.py`, `ui/{contracts,backend,settings_dialog}.py`: Map手動選択と録画時build設定。
- `main.py`: packaged smoke testでMapリソース・Shapely読み込みを検証し、失敗時もダイアログ待ちしない。
- `pyproject.toml`, `constraints-windows.txt`: Shapely依存関係。
- `tests/unit/test_map_{resolver,calibration}_v3.py`, `tests/integration/test_map_zone_v3.py`: 単体・実CV・時系列統合テスト。
- `tests/unit/test_visual_core_v2.py`: Visualの入力境界をZoneResolutionへ移行。元の33ケースJSONは変更していない。

## 2. 統合した処理

画像 → ミニマップ校正 → ROI座標をmap-mask座標へ変換 → Map/Zone Resolver →
厳密なZoneResolutionタイムライン → Visualイベント → 既存Round Package / Rule Engine / AI Coach。

ResolverはイベントもGOOD/IMPROVE評価も生成しない。位置・ローテーション・味方サイト進入は
VisualのMapEventConsumerのみで生成する。認識不能、低confidence、未校正、特殊視点では
位置依存の確定事実を生成しない。Semantic Visionへ位置推定や隠れた射線推定を依頼しない。

## 3. 正本と旧契約

実行時の正本は `config/map_zone_v3/config/map_zone_runtime_contract_v4.json`。
同bundleのmap/callout/peek/registry Schemaとデータを使用する。
本体・Visual v2に含まれる古いMap/Zone契約は履歴と原本検証のため残すが、実行時には読み込まない。
Visual profileの旧 `map_registry` / `peek_registry` は明示的なエラーとする。
旧式geometryを自動変換して新契約扱いにしない。

## 4. Registryと選択

手動指定 → 信頼できるMapラベル → 参照画像一致（0.90以上）→ 未解決、の順。
単一Mapしか登録されていなくても自動的にそのMapを選ばない。
未解決の場合は設定画面でMapを選択する。未登録IDはエラーとなる。
テストfixtureは明示的な `allow_fixture=True` の場合だけロードでき、通常の選択画面には出さない。

カスタムデータを使う場合、Visual profileに以下を追加する。パスはprofileファイルからの相対パス。
`registry_root` 以下には、同梱bundleと同じ `config/`, `schemas/`, `assets/` 構造を用意する。

```json
{
  "map_zone": {
    "registry_root": "map_zone_bundle",
    "manual_map_id": "summit",
    "client_build": "13.06.00.5435758",
    "dynamic_rotation": false,
    "player_centered": false
  }
}
```

設定画面のMap/build指定が非空ならprofileの値より優先する。
この例のMap/buildは添付データの値であり、実装にハードコードしていない。

## 5. 校正

参照PNGと実フレームのSIFT特徴点から固定向きのsimilarity transformを推定する。
一致点数・空間分布・再投影誤差・全マップ可視性・非一様スケールを確認する。
ROIはHUDレイアウトまたはVisual profileの正規化XYXY座標から読み込む。
変換後は参照画像内のmap-mask bboxを原点・サイズとして再正規化する。
全マップを回復可能な拡大縮小・余白移動は対応し、回転、部分クロップ、非一様な歪み、
player-centered、既知のgeometry変更、version不一致は `calibration_required` とする。
未知buildは `client_build_unverified` を診断へ記録する。画像一致だけでbuild検証済みとはしない。

## 6. Resolver

日本語aliasもcalloutレコードから解決し、ラベルは時間ベースで安定性を確認する。
ラベルとpolygonは正本のfusion表で統合する。高confidence同士の不一致はunknown、
境界では最大0.6秒だけ前状態を減衰保持する。通常遷移も0.6秒持続してから採用する。
polygon confidenceは校正・marker・Map・Zoneのcapの最小値。
両providerがaccept未満の同意はdegraded contextだけとし、名前付きイベントには使用しない。
PEEK-04は人手の静的anchorとの一致だけを利用する。添付Summitのanchorは空なので常にnull。

## 7. Visualへの接続

`position_change`, `position_hold`, `rotation_started`, `rotation_completed`,
`ally_entry_start`, `ally_enter_site`をVisual側で生成する。
ローテーションは `topology_edges` 上で観測された連続経路とsite_affinityの変化から判定する。
任意のサイト数・Midなし・special linkに対応し、A/Bや特定zone名で分岐しない。
味方の短時間追跡は一意な双方向近傍対応のみ。交差・消失・曖昧な対応ではIDを引き継がず、
架空のサイト進入を抑制する。サイト進入には0.35秒、ローテーション完了には1秒の持続が必要。

## 8. Schemaと保存

Map、Registry、runtime contract、callout、mask、peek、ZoneResolutionのSchemaを実際に検証する。
参照先、geometry version、PNG SHA-256、polygon妥当性、sites[]、edge参照も確認する。
独立operational mask内のgap/overlap QAを実行し、失敗時にmaskを自動修正しない。
Round Packageへは許可されたlocation/spatial/Eventフィールドのみを射影し、
中間専用フィールドは流さない。タイムライン自体はHUD解析監査JSONの `zone_resolutions` に保存する。

## 9. テスト

2026-09-28 macOS / Python 3.12.14での初回統合結果:

- 全体: **334 passed / 1 skipped**。カバレッジ **80.03%**。
- Map正本validator: **24 cases OK**。本体正本validator: **38 cases OK**。
- Ruff: 成功。mypy: **71 source files成功**。
- 隔離した一時データディレクトリでのQt offscreen smoke test: **exit 0**。
- skipは実VALORANT連続動画が未提供のためのHUD精度確認1件。
- Mapパッチ原本30ファイル、Visualパッチ原本31ファイル、本体のconfig/Schema/ケース86ファイルはZIPとのバイト比較で不変。
- API呼び出しなし。Windows exeビルドと実機の動画認識精度はこの結果に含めない。

原本 `validate_map_zone_patch_v3.py` の24ケースをそのまま実行するpytestラッパーを追加した。
実ResolverからVisual、v3 Schema検証までの連続テスト、3サイト/no-Mid/teleporter、
ラベル競合・境界保持・degraded・校正失敗・不正データ拒否を追加。
参照PNGへの制御されたmarker重畳で、実OpenCV校正・marker検出・Resolver・Visual接続も確認する。

原本3サイトfixtureでは `tri_c_site` と `tri_hub` が重複する。
元データは変更せず、polygon入力はunknownになることを検証する。
A→C経路テストは明示的なテスト用calloutレコードによるラベル入力を使用する。
既存Visualの33ケースはconsumer境界のZoneResolution入力へ移行し、TEAM-02は
新正本の0.35秒dwellを満たす観測列にした。期待結果は削除・弱体化していない。

### 2026-09-29 レビュー指摘4点の修正

- Zone confidence: Round Packageの既存 `deterministic_facts` に `zone_id` を時刻付きで保存。
  confidenceはResolverとラウンド品質の最小値。Fact Builderの既存重複排除により、
  保存・再読み込み・再enrich後も高いラウンドconfidenceへ置換されない。Schema変更なし。
- 境界hold: 前Zoneを保持する際、新Zone候補の待ち時間をリセットする。
  曖昧区間から復帰後に、改めて0.6秒の連続した観測が必要。
- ローテーション: 同一Zone滞在中もconfidenceの最小値を更新する。
  一時的な低下後に回復しても、その経路の完了confidenceを引き上げない。
  position_holdにも保持区間の最小confidenceを使用する。
- ROI: `video/geometry.py` に正規化ROI→pixel boundsの共通処理を追加し、
  Visual画像切り出しとMinimapCalibratorが同じ丸め・検証を使用する。
- Visual実装fingerprintを4へ更新。旧実装で作成した途中解析と新処理を混在させない。
  設定指紋不一致となる旧解析については、新規解析を開始する。

修正後の検証: **347 passed / 1 skipped、coverage 79.79%**。
今回追加した回帰テストは13件。Ruff成功、mypyは72ファイル成功。
Qt offscreen smoke testも成功。スキップ理由は引き続き実録画未提供。
既存のテスト期待値・正本JSON・Schemaは、この修正では変更していない。

変更対象: `rounds/builder.py`, `maps/{resolver,calibration}.py`,
`visual/{map_consumer,pixels,runtime}.py`, 新規 `video/geometry.py`、
`tests/integration/test_map_zone_v3.py`, `tests/unit/test_map_resolver_v3.py`、
新規 `tests/unit/test_roi_geometry.py`。

## 10. Summitで確認した範囲

添付データ: 9 zones、24 callouts、14 topology edges。独立mask内gap=8.6239%、overlap=0%。
参照PNG、拡縮・移動したPNG、回転/クロップ/ノイズ/歪みの失敗ケースを確認した。
実試合の連続動画は未提供のため、実運用の位置精度・tracking精度は未検証。
参照画像＋合成markerの成功を、実録画での精度保証とは扱わない。

## 11. 未登録Map・残課題

productionとして登録されているのは添付registryにあるMapのみ。
未登録Map、未登録callout、動的回転/部分マップ、全マップを復元できない映像は未対応。
PEEK-04 anchor、人手確認済みの追加Map geometry、実動画でのmarker色/ROI校正が必要。
敵の隠れた位置、精密calloutや3D構造は推測しない。

## 12. Mapを追加する手順

1. 固定向きの参照画像とgeometry_version、確認build、SHA-256を登録する。
2. map-mask正規化座標でzones・sites・topology_edgesを作成する。
3. 別ファイルのplayable/operational maskを人手で確認する。
4. callout records/aliasesを作成し、未確認語彙のconfidenceを下げる。
5. peek registryは根拠がなければ空にする。追加するなら位置・半径・site/zone整合・人手provenanceを記録する。
6. registryの参照を追加し、Schema/coverage QAと録画解像度・HUD Scale別の校正テストを行う。

## 13. Windows起動・exe

Python 3.12、FFmpeg/FFprobeを用意してプロジェクト直下で実行する。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-windows.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe -m valorant_ai_coach
.\build_windows.ps1
```

追加依存はShapely 2.1.2。Map bundleは既存specのconfigフォルダ同梱対象に含まれる。
WindowsビルドではShapely/GEOSライブラリの同梱も必要となる。
packaged smoke testにproduction MapのSchema・参照PNG hash・Shapely geometry QAのロードを追加した。
`dist\VALORANT-AI-Coach\VALORANT-AI-Coach.exe` をフォルダごと配布する。
Windows CIはpytest/lint/mypy/build/packaged smoke testを実行する構成。
今回の作業環境はmacOSで、Windows実機起動・exeビルドは未検証。
