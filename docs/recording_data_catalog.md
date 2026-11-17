# 録画データ管理基盤（#62）

`src/valorant_ai_coach/recordings/` は、録画とそこから作ったデータを一か所で管理する非公開カタログです。これまで録画の登録は3つの仕組みに分かれていました。9本単位の非公開取り込み（`scripts/diagnostics/register_private_sources.py`）、6本の段階的予約（`temporal/staged_validation.py`）、2本目の録画の有効化（`temporal/second_validation.py`）です。それぞれが別々のJSONとsplitの定義を持っていました。また、モデルや教師データがどの録画から作られたかをプログラムで確かめる手段がありませんでした。

既存の3つの仕組みは変更していません。カタログはその割当を読み込んで引き継ぎます。

## 保存の形式

カタログはGitリポジトリの外に置きます。リポジトリの中を指定すると作成を拒否します。

| ファイル | 内容 |
|---|---|
| `journal.jsonl` | 追記専用の履歴。各行は直前の行のSHA-256を `prev` に持つ |
| `catalog.json` | 履歴を再生した結果の写し。`verify` が履歴から作り直して照合する |
| `.catalog.lock` | 書き込み中の排他ロック |

現在の状態は履歴の再生でだけ決まります。行を書き換えたり消したりすると連鎖が切れ、読み込み時に `CatalogIntegrityError` になります。ファイルの権限はPOSIXで0600、ディレクトリは0700です。Windowsでは所有者だけが読めるNTFS ACLを別途設定してください。

## 登録・検証・重複排除

- 登録した録画のsplitは変えられません。splitを変える操作自体がありません。
- 同じ物理試合は1つのsplitにだけ属します。前半と後半のように複数のファイルがあっても同じsplitです。
- splitを指定しない場合は、`sha256(seed:physical_match_id)` で決めます。比率はカタログ作成時に固定します（既定はDEVELOPMENT 0.6、QUALIFICATION 0.2、FINAL_HOLDOUT 0.2）。メタデータや映像を見る前に決まります。
- 同じ内容（SHA-256が同じ）の再登録は何もしません。別の場所にある同じ内容は、保存場所として追加します。
- 同じ内容を別の物理試合として登録しようとすると拒否します。
- サイズが同じ別の録画は、別の試合であることを利用者が確認するまで登録しません（`--confirm-distinct`）。
- `verify` は全保存場所を再ハッシュします。内容が変わった録画は隔離（quarantined）にし、学習・解析の対象から外します。登録済みのハッシュを書き換えることはしません。
- ディレクトリ単位の登録は増分処理です。パス・サイズ・更新時刻が登録済みと同じファイルはハッシュを計算しません。新しいファイルは並列にハッシュします。

## Exposure（視聴・利用の履歴）

Exposureはsplitとは別に記録します。

| 種別 | 意味 |
|---|---|
| `development_use` / `source_viewed` / `annotation` / `prediction_opened` / `tuning` | 開発で見た・使った |
| `user_authorized_development_use` | 保護録画を開発に使うことを利用者が決めた |
| `qualification_opened` / `final_evaluation_opened` | 評価のために開封した（理由の記録が必須） |
| `unknown_prior_exposure` | 過去の利用状況が分からない |

QUALIFICATIONとFINAL_HOLDOUTの録画は、Exposureが1件でもあれば `blind = False` になり、元に戻りません。splitの表示は残すので、履歴は後から確認できます。

## 系譜の追跡と漏洩防止

抽出画像（`frames`）、特徴量（`features`）、教師データ（`labels`）、タイムライン（`timeline`）、解析結果（`analysis_result`）、モデル（`model`）、レポート（`report`）を、親（録画または別のartifact）と生成器（名前・版・設定のハッシュ）つきで登録します。`lineage` で、あるモデルがどの録画から作られたかと、ある録画から作られたものの一覧を出せます。

`guard` は用途ごとに次を確かめます。

| 用途 | 許可する録画 |
|---|---|
| `training` / `tuning` / `development_analysis` | DEVELOPMENT、または `user_authorized_development_use` のある録画 |
| `qualification` | 開封済みのQUALIFICATION |
| `final_evaluation` | 開封済みのFINAL_HOLDOUT |

隔離中の録画はどの用途にも使えません。モデルを登録するときは、祖先にtrainingで使えない録画があれば登録を拒否します。

## 継続学習基盤との接続

`learning_view()` は、継続学習の登録簿（#105・PR #154の `DatasetRegistry`）と同じ項目（`source_id`、`physical_match_id`、`archive`、`archive_sha256`、`archive_bytes`、`split`）を返します。TRAIN・VALIDATION・DEV_COMPARISONは、開発に使える録画の中で物理試合単位に分けます。QUALIFICATIONとFINAL_HOLDOUTは、学習側の非回帰ゲートで繰り返し使うと漏洩になるため、このビューには入れません。利用者が開発利用を認めた録画は、`include_authorised_exposed=True` のときだけ `exposed_holdout: true` を付けて入れます。

`plan(producer)` は、指定した生成器（名前・版・設定）でまだ処理していない録画を返します。処理後に結果をartifactとして登録すると、次の `plan` から外れます。

## 既存の割当の引き継ぎ

`import-legacy` は既存の `manifest.json` / `allocation.json` を読み込みます。

- `QUALIFICATION_CANDIDATE` はQUALIFICATION、`FINAL_HOLDOUT_CANDIDATE` はFINAL_HOLDOUTとして引き継ぎます。splitは決め直しません。
- `exposure` が `DEVELOPMENT` なら `development_use`、`UNKNOWN_EXPOSURE` なら `unknown_prior_exposure` を記録します。
- `rejected` の録画は取り込みません。
- カタログと食い違う行（同じ内容でsplitが違う等）は変更せず、`conflicts` に報告します。

2026-11-15に利用者が決めた「full_match〜full_match_5の全動画を開発に使ってよい」は、割当の変更ではなく `expose --kind user_authorized_development_use` で記録します。

## 公開してよい出力

`summary` は件数だけを返します（ID、ハッシュ、パス、ファイル名、日時を含みません）。`leak-check` は、Gitへ入れる予定のファイルにカタログのハッシュ・ID・パス・ファイル名が含まれていないかを調べ、見つかった種類だけを報告します。

## コマンド

```sh
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" init
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" import-legacy "$REGISTRY/personal_20261108/manifest.json"
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" register "$NEW_RECORDINGS_DIR" --probe
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" expose ID --kind user_authorized_development_use --note "理由"
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" open ID --purpose qualification --note "承認の記録"
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" artifact --kind labels --parent ID --producer NAME --version V --path FILE
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" guard ARTIFACT_ID --purpose training
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" plan --producer NAME --version V
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" verify
python -m valorant_ai_coach.recordings --catalog "$PRIVATE_CATALOG" leak-check docs/*.md
```

## 制約

- 同じ試合を別の設定で録画した場合など、内容が違う同一試合はハッシュでは見分けられません。物理試合IDの指定は利用者の申告に依存します。
- 同じ場所の写し（originalとmanaged）は災害対策のバックアップになりません。別の暗号化ディスクなどへの複製と復元確認は、引き続き運用で行います。
- 既存の解析コード（`SourcePolicy` など）はまだ旧来の割当ファイルを直接読みます。カタログからの移行は別の変更で行います。
