# 評価フィードバック

## 目的

AIによる元評価と利用者の主観的意見を分離する。`evaluation_feedback`は独立SQLiteテーブルであり、正本`evaluations.payload_json`を一切更新しない。

## データモデル・GUI

`evaluation_id`で外部キー関連付け。保存項目はMatch ID、verdict（`valid`＝妥当、`inappropriate`＝不適切、`pending`＝判断保留）、メモ、created_at、updated_at。結果画面の各評価カードに選択欄、メモ欄、「意見を保存」を追加。未登録・削除に戻して保存すればfeedbackのみ削除する。元のGOOD/IMPROVE/UNSCORED、根拠・confidence・クリップは変更しない。

## 安全性・テスト

存在しない評価IDを拒否。重複登録は更新として保持。Match削除時は外部キーcascade。メモ4000文字以内。`test_non_video_features.py`で登録、更新、削除、再起動、評価不変、日本語を確認する。

## 制約

主観的feedbackはGround Truthではない。自動再学習・プロンプト変更・評価ラベル変換には使用しない。