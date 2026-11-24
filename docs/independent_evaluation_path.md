# 独立評価専用の実行経路

QUALIFICATION と FINAL_HOLDOUT の録画を解析できるのは、この経路だけです。開発用のコマンドは、これまでどおり `development_analysis` の用途でしか録画を受け付けません。

モジュール：`valorant_ai_coach.temporal.independent_evaluation`

## 手順

1. 開封（この経路の外）：統括の承認を得て、`python -m valorant_ai_coach.recordings open` で録画を評価用に開封します。開封の記録はカタログに残ります。
2. 計画の凍結（`prepare`）：録画、用途、解析オプション、参照画像、読み取り設定、解析コードのダイジェストを計画ファイルに固定します。カタログ上でその用途に開封済みで、ほかの露出がない録画だけを受け付けます。`prepare` はカタログに書き込みません。
3. 実行（`execute`）：承認の記録（`--approval-note`）を必須とします。計画の作成後にコード、参照画像、読み取り設定、カタログの受け入れ条件のどれかが変わっていれば実行しません。

```
python -m valorant_ai_coach.temporal.independent_evaluation prepare \
    --catalog CATALOG --purpose qualification --recording REC_ID \
    --reader-config screen_PRIVATE.json --label-reference label.png \
    --remote-hint hint.png --remote-duration bat.png --camera-hint camera.png \
    --plan plan_PRIVATE.json
python -m valorant_ai_coach.temporal.independent_evaluation execute \
    --plan plan_PRIVATE.json --approval-note "承認者と日時" --output OUT
```

## 守っていること

- 用途は呼び出し側が決めます。`SourcePolicy` は用途を引数で受け取り、ポリシーファイルに書かれた用途と一致しなければ拒否します。評価用のポリシーを開発用のコマンドに渡すことも、その逆もできません。
- 評価用途では、録画カタログ経由の受け入れだけを認めます。旧方式の割当ファイルでは受け付けません。
- 解析オプションは、承認済みの共通タイムライン（#150・#151）の設定に固定しています。補助入力や上書き、調整用の入力は受け付けません。
- 出力は新しい非公開ディレクトリにだけ書き、受領ファイルに計画のハッシュ、承認の記録、計画時点と実行時点のカタログの先頭を残します。
- 中断した実行は `--resume` で、同じ計画と承認の記録のまま同じ出力先から続けられます。終わった録画はそのまま使い、途中の録画は出力を別名に退避してチェックポイントから解析し直します。
- 64MB 以上の JSON 出力は、伸張して同じハッシュになることを確かめてから gzip に置き換えます。元のハッシュは各録画の完了記録に残します。
- この経路では採点も正式な資格付けもしません。受領ファイルには `scoring: NOT_PERFORMED`、`formal_qualification: NOT_GRANTED`、`formal_outputs: 0` を記録します。採点は `independent_scoring` が、事前に固定した基準（`docs/independent_evaluation_protocol.md`）で行います。

## まだしていないこと

- full_match_6 の8本は未開封のままです。この経路で解析したことはありません。
- 独立評価の実行と正式な資格付けには、別途承認が必要です。
