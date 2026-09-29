# VALORANT AI Coach — Codex実装仕様（HUD座標確定前・完成版 v3）

## 1. 目的
Windows 10/11上で動作する個人利用のVALORANTプレイ分析デスクトップアプリを実装する。プレイ録画を解析し、ユーザー定義の評価基準に基づく GOOD / IMPROVE / UNSCORED を、根拠となる短いクリップと一緒に表示する。

## 2. 今回実装してよい範囲
HUDの正確なROI座標だけ未確定。それ以外は実装を開始してよい。HUD層は後から `hud_layout.json` を差し替えられる設計にし、Mock Round PackageでE2E試験できるようにする。

## 3. 技術構成
- Python 3.12系
- GUI: PySide6
- 動画: FFmpeg / FFprobe / OpenCV
- 保存: SQLite + JSON + clips/*.mp4
- AI: OpenAI Responses API（画像入力可能モデル。モデルIDは設定値）
- JSON検証: jsonschema
- Windows配布: PyInstaller onedir を正式な初期方式とする

## 4. 正式なデータ契約
### AI入力
`schemas/round_package_schema_v2.json` が唯一の正式Schema。
Video/HUD Analyzerは評価結論を生成しない。観測事実と、コードで正規化した非評価Factだけを出力する。

### AI/Rule Engine共通出力
`schemas/ai_coach_output_schema_v3.json` が唯一の正式Schema。
`decision_source` で llm / deterministic / hybrid を記録する。

### 評価対象外と通常行動
- 候補ルールにならない: 出力しない。UNSCOREDにしない。
- 明確なGOOD/IMPROVE根拠がない通常行動: 出力しない。NEUTRALを作らない。
- 候補にはなったが証拠不足/必要Fact欠落/例外曖昧: UNSCORED。

## 5. 役割分担
### コード側（決定論的）
- HUD/OCR/映像から観測値を抽出
- alive人数、Spike状態、残り時間、Weapon、Utility残数、Role、Zone等を正規化
- 明示的な数値/二値基準に必要なFactを生成
- `rule_trigger_registry_v2.json` により候補ルールを絞る
- 高信頼かつ人間基準に明示された閾値だけ deterministic/hybrid 判定可能

### AI側
- ラウンド文脈・例外条件・状況依存判断
- なぜ良い/悪いかの説明
- 具体的な改善案
- 曖昧な場合のUNSCORED判断

## 6. 空間情報
本アプリは録画映像から完全な3D座標/Z軸/真の3D Line-of-Sightを復元しない。
代わりに以下を使う。
- `player_location.zone_id / zone_name`
- 任意の正規化ミニマップ2D座標
- `spatial_context.cover_available`
- `escape_route_available`
- `line_of_sight_state`（confirmed_clear / confirmed_blocked / unknown）
- `exposed_directions_count`

確認できない空間情報を推測で埋めてはならない。

## 7. Role
`round_meta.player_role` を明示する。Role固有ルールはRole一致をcandidate gateにする。Agent→Role対応は更新可能なResolver/registryで管理し、未解決はunknown。

## 8. AI Coachパイプライン
1. Video Analyzerがラウンド境界と解析用フレームを生成。
2. HUD/Visual Analyzerがevents/state snapshotsを生成。
3. Deterministic Fact Builderが `deterministic_facts` を生成。
4. Rule Selectorが `rule_trigger_registry_v2.json` で候補を最大12件程度へ絞る。
5. ラウンド全体のsparse contextを理解。
6. 候補場面のみdense frameを追加。
7. 候補ルールのhuman_policy / human_exceptionsを最優先して評価。
8. 出力Schema v3でvalidate。失敗時は最大2回修復。
9. GOOD/IMPROVEかつconfidence条件を満たすものだけdisplay_clipを生成。
10. 同一ルールの反復指摘はaggregation_policyで集約。

## 9. 数値化方針
人間が明示した数値だけ固定閾値として扱う。例:
- AIM-02: 約0.5秒前プリエイム
- PEEK-04: 3方向露出
- 「完全停止」と明示された停止系ルール

「適切なタイミング」「無理のない詰め」等を、根拠なく2秒/4秒などへ変換してはならない。

## 10. Utility効果
`status_effect` / `utility_effect_observed` は観測できた場合だけ記録する。誰に当たったか、効果時間等を取れる場合はFactとしてAIへ渡す。取得不能なら推測しない。

## 11. confidence
- 0.75以上: 通常表示可
- 0.55〜0.7499: 要確認帯
- 0.55未満: 原則UNSCOREDまたは抑制
ルール固有policyがあればそちらを優先。

## 12. HUD未確定部分
`config/hud_layout.json` を別ファイルにし、ROIは0〜1正規化座標。`MockHudAnalyzer` と `RealHudAnalyzer` を差し替えられる構造にする。実スクショなしで架空座標を完成扱いにしない。

## 13. GUI
最低限:
1. ホーム/動画選択
2. 解析進捗
3. 試合結果
4. 評価カード一覧（GOOD/IMPROVE/要確認）
5. 評価詳細 + クリップ再生
6. 設定（APIキー、モデル、保存先、FFmpegパス）
UNSCOREDは通常一覧へ大量表示せず診断画面から確認可能にする。

## 14. テスト
`tests/` を使用する。
- 入力Schema v2検証
- Assertion Schema検証
- candidate selector契約テスト
- MVP必須ルールカバレッジ
- GOOD/IMPROVE/UNSCORED
- 同一ラウンド複数評価（GOOD+IMPROVE）
- Role gate
- 極端な残り時間
- Status effect後の判断
- 低HUD/低Visual confidence
- 評価対象外/通常区間で「出力なし」
- PEEK-02曖昧性
- 反復ミス集約

## 15. 完了条件（HUD ROI以外）
- WindowsでGUI起動
- mp4/mkv選択とffprobeメタデータ取得
- Mock Round Packageで `Fact Builder → Rule Selector → AI Coach → Schema検証 → DB保存 → clip生成 → UI表示` が通る
- API未設定時はMock AIでデモ可能
- PyInstaller onedirビルド手順/specがある
- ログ/エラー表示がある
- READMEに開発/実行/ビルド手順がある
