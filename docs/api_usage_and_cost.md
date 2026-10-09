# AI API使用量・推定費用

## 目的・既存機能との関係

OpenAI Coachの実際に受け取った`response.usage.input_tokens/output_tokens`を記録する。Semantic Visionの既存予算管理は変更・重複実装しない。

## 保存モデル

SQLite`api_usage_events`。記録時刻、機能名、モデル、応答状態、実usage token数（欠損はNULL）、cache hit、repair attempt、retry attempt。送信内容・APIキー・画像・モデル出力全文は保存しない。cache hitは利用した応答キャッシュであり新規請求を意味しない。通信失敗でusageが取得できないときは費用不明であり、0円と断言しない。

## GUIと価格設定

「履歴・統計ツール」→「API使用量・費用」。単価はユーザーが`api_prices.json`で明示指定する。形式:

```json
{"prices":{"モデルID":{"input_per_million":1.0,"output_per_million":2.0,"currency":"USD"}},"monthly_budget":20.0}
```

数値は**形式説明用の仮値**であり公式価格ではない。単価未設定なら推定料金「不明」。実usageと概算を区別し、通貨が異なれば合算しない。月間予算は目安の警告のみ。強制停止や請求額の保証は行わない。月の境界はUTC基準。

## テスト・制約

`test_non_video_features.py`と`test_non_video_dialog.py`。usage有無、cache hit、エラー、再起動保持、単価欠損を検証。Semantic Visionを含め全課金を網羅する台帳ではない。ツール内の予算はユーザー提示の目安に限られる。