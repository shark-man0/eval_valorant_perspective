# Review Fixes - HUD Analyzer Patch v2

外部レビューで指摘された高優先度項目を反映した差分記録。

- HUD/Visual Analyzerのイベント責務境界を明文化
- spectator検出を実装契約化
- buy/round-end banner分類を文脈ベース化
- Agent非依存Ultimate slot contract追加
- HUD confidence / final evaluation confidenceの意味を分離
- kill side判定をalive count差分中心に規定
- remote control viewをAgent横断で一般化
- round observation quality集約式を追加
- spike stateのMVPサポート範囲を明示
- smoke/flash/state transition/calibrationの誤検出対策を追加
- weapon識別・複数audio stream UI方針を追加

未検証のAgent/画面については「契約のみ」であり、実測済みとは表現しない。
