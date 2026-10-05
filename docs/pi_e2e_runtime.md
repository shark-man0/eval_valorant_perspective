# Raspberry Pi 実動画 E2E の runtime 修復

検証環境: Raspberry Pi 4 Model B Rev 1.5、Linux aarch64、Python 3.12.3。
この記録は認識精度や全 assertion の PASS を保証するものではない。

## 原因と共通コードの修正

- 最初の失敗 run: `outputs/e2e/match_001/20261005T112039Z-e2187acc`。
  `readers._cross_lines_score` が HoughLinesP の結果を `(N, 1, 4)` と決めつけ、
  この環境の OpenCV 5.0 が返す `(N, 4)` に対して IndexError を起こした。
  保存済み実フレームでスタックトレースを取得して再現した。
- HUD の線分利用箇所を `reshape(-1, 4)`、円の個数判定を `reshape(-1, 3)` に統一。
  座標、個数の条件、identity 条件、検出閾値は変更していない。
- 再実行では、全フレームをデコードする FFprobe の PTS 取得が固定300秒でタイムアウトした。
  `VideoService` に独立した `pts_timeout_sec`（既定1800秒）を追加した。
  メタデータ取得の既定45秒、PTS の妥当性検証、キャンセル、子プロセス終了処理は維持した。
  フレームを省略したり、FPSからPTSを代用したりしない。
- `tests/e2e/run_real_video.py` の例外処理で、private な analyzer.log に
  スタックトレースを残すようにした。

OpenCV 5.0、OpenAI SDK 3.x、古い jsonschema はこの checkout の依存指定と一致していなかった。
現在は `constraints-e2e.txt` の共通6依存に合わせている。
配列形状の修正はOS分岐を使わない。OpenCV 5全体の認識精度互換性を保証する変更ではない。

## ラウンド未検出の診断モード

最初の全動画再検証では3869フレームを解析した後、Round Package生成が
「信頼できるラウンド区間なし」で停止した。幾何校正だけのプロファイルでは
identityやラウンド境界の根拠が足りないためであり、区間を推測して補うことはしない。

共通のRoundPackageBuilderとHudVideoProcessorに `require_detected_rounds` を追加した。
既定はTrueで、通常のproduction/GUIは従来どおりラウンド未検出を拒否する。
実動画E2EランナーだけがFalseを指定し、未検出時は空のRound Packageと
`round_packages_unavailable: no reliable round boundaries` を返す。
観測とVisualの実データは保持し、校正、FPS、Schemaなど他の検証はそのまま行う。
空の区間からスナップショットやラウンドを捏造しない。
この診断モードはOS非依存で、Pi専用の検出・評価ロジックではない。

通常モードの拒否、診断モードの空の結果、校正失敗と無効FPSの拒否を回帰テストで確認した。
既存evaluatorはラウンド未検出のtraceをschema validとして評価し、未検出はassertion failureになる。
空の検出結果によるnegative assertionのPASSは検出精度の証明にはならない。

## 校正プロファイル

既定 layout には `config/hud_layout_1080p_v3.templates.json` が存在しなかった。
元動画からの自動生成では、安定した幾何アンカーが3個未満となり、引き継ぐプロファイルも
存在しないため失敗した。`outputs/hud-profile-diagnostic-pi.log` に詳細を保存した。

既存の未加工 `hud_reference.png` から標準の校正機能でローカル参照画像を生成した:

```sh
python3 -m valorant_ai_coach.hud.calibrate hud_reference.png \
  outputs/hud_profiles/reference-seed --layout config/hud_layout_1080p_v3.json
```

生成先は新しいディレクトリを指定する必要がある。
保存済み実動画17フレームで通常のアンカー照合を実行し、幾何校正が成立することを確認した。
独立したidentityの根拠は未設定なので、17フレームすべての状態判定はunknownだった。
このプロファイルは幾何校正用であり、プレイヤー帰属やHUD値の認識を許可する代用品ではない。
Validation Pack、expected result、元動画は変更していない。

無加工の参照画像を使った通常の照合と、既存のgeometry保持・identityゲートを通している。
校正失敗を無条件に無視する処理は追加していない。

`.env.local` に次を設定した（CLI/環境変数の明示設定がある場合はそちらが優先）:

```dotenv
VALORANT_E2E_HUD_LAYOUT=outputs/hud_profiles/reference-seed/hud_layout.json
```

プロファイル内の4画像参照は相対パス。Windowsへ移す場合はプロファイルディレクトリ全体を
移し、Windows側の `.env.local` で対応するパスを指定する。Pi専用production実装はない。
共通E2Eは `sys.executable`、引数配列、Path、PATHからの外部コマンド探索を使用する。

## 環境と検証

新しい環境では既存のセットアップ手順に従い、venv内で共通制約を使ってインストールする:

```sh
python3 -m pip install -c constraints-e2e.txt -e '.[dev,gui]'
python3 -m pip check
python3 scripts/e2e/run_dataset_case.py --check-environment
```

GUI依存は今回の全体テスト・mypy用。headlessなE2Eの実行には不要。
OpenCVのGUI版とheadless版を同じ環境へ重複インストールしない。
実機では既存headless版5.0を削除し、共通制約のopencv-python 4.14.0.94へ揃えた。
開発用editable installにより、テストの子プロセスからも本体をimportできるようにした。
実機の依存記録は `outputs/pi-runtime-requirements.txt` に保存した。

- `pip check` と環境チェック: 成功。
- `ruff check .`: 変更対象外の既存386件で終了コード1。
- `ruff check src tests scripts/e2e`: 成功。
- `mypy .`: `report_context` と `scripts.e2e.report_context` のモジュール名重複で停止。
- `mypy src/valorant_ai_coach`: 86ファイル成功。
- 全体pytest: 974 passed、6 skipped、失敗0、終了コード0。
  `QT_QPA_PLATFORM=offscreen` と supplied pack を指す `VALORANT_E2E_PACK` を設定して実行した。
  Windows/PowerShell、別指定の実動画、sibling pack固定参照のケースがskipされた。

## 実動画 E2E

テスト完了後、依頼されたコマンドをそのまま再実行:

```sh
python3 scripts/e2e/run_dataset_case.py \
  --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 \
  --video-id match_001 \
  --validation-pack ValorantData/valorant_e2e_validation_pack_v3
```

最終Run: `outputs/e2e/match_001/20261005T135105Z-80024d30`。
実機の実動画解析からtrace生成、evaluator、共有レポート出力まで完走した。

| 確認項目 | 実測結果 |
| --- | --- |
| 終了コード | 1（assertion FAIL、runtime failureなし） |
| raw_processing.status | complete |
| sampled_frame_count / 実HUD観測数 / 実Visual観測数 | 3869 / 3869 / 3869 |
| hud_calibration.counts.frames | 3869 |
| summary.result.schema_valid | true |
| summary.result.error_code | null |
| summary.result.status | fail |
| assertion records | 21 passed、57 failed、4 not_evaluated |
| failure_message_count | 57 |
| Round Package数 | 0 |

`raw_processing.json`、`e2e_trace.json`、`evaluation_report.json`、`analyzer.log` が
同runに生成され、`run_metadata.json` の終了コードも1。`error_code.json` は存在しない。
入力動画・Validation PackのSHA256は元のmanifestの値と一致した。

identityの根拠が全3869フレームで不足し、信頼できるラウンド境界がないため、
traceの6配列は空。rawには実際に解析した観測が3869件ずつ保存されている。
評価工程の完走を確認した結果であり、HUD認識やラウンド検出の成功とは扱わない。
20件のnegative assertionが評価されているが、空traceで禁止条件が成立しても検出精度の証明ではない。

## Windows 実機での追加確認

同じ共通依存・参照プロファイルで実動画E2Eを実行し、PTSと画像の対応、trace schema、
evaluatorへの到達、生成物を確認する。Windows/PowerShell専用のskipテスト、
GUI動画再生・音声トラック切替、同梱FFmpeg/FFprobeを使う配布物の起動も実機で確認する。
