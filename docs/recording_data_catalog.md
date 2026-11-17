# 録画データ管理基盤（#62）

`src/valorant_ai_coach/recordings/` は、録画とそこから作ったデータを一か所で管理する非公開カタログです。これまで録画の登録は3つの仕組みに分かれていました。9本単位の非公開取り込み（`scripts/diagnostics/register_private_sources.py`）、6本の段階的予約（`temporal/staged_validation.py`）、2本目の録画の有効化（`temporal/second_validation.py`）です。それぞれが別々のJSONとsplitの定義を持っていました。また、モデルや教師データがどの録画から作られたかをプログラムで確かめる手段がありませんでした。

既存の3つの仕組みはカタログで照合するように移行しました（下記「旧来の管理方式からの移行」）。登録から独立評価までの手順は `docs/recording_operations.md` にまとめています。

## 保存の形式

カタログはGitリポジトリの外に置きます。リポジトリの中を指定すると作成を拒否します。

| ファイル | 内容 |
|---|---|
| `journal.jsonl` | 追記専用の履歴。各行は直前の行のSHA-256を `prev` に持つ |
| `catalog.json` | 履歴を再生した結果の写し。`verify` が履歴から作り直して照合する |
| `HEAD.json` | 最後に追記した履歴の番号とハッシュ。末尾の削除を検出する |
| `.catalog.lock` | OSのファイルロック（異常終了しても残らず、削除も不要） |

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

## 2026-11-17 承認後の追加

- 正本：既存の解析器が使う `SourcePolicy` は、`{"catalog": ..., "allowed_recording_ids": [...]}` でカタログから許可リストを作る。旧来の割当で書かれた受領記録は、取り込み時に記録した割当ファイルのハッシュで引き続き検証できる。`register_private_sources.py --catalog` は登録後にカタログへ取り込む。
- 物理試合IDの継承：派生動画（`register --derived-from`）、切り出し画像（`frames`）、タイムライン、解析結果は親の物理試合IDとsplitを引き継ぐ。1試合から作る種類が複数の試合にまたがると拒否する。
- 履歴末尾の削除：`HEAD.json` と、カタログ外に保管する `SEQ:SHA256`（`head` で表示、`verify --trusted-head` で照合）で検出する。
- artifactの再登録：同じIDは同じ内容・種類・親・生成器のときだけ受け付ける。同じ内容を別の系譜で登録すると拒否する。
- 露出済み録画：独立した評価（qualification・final_evaluation）の開封も利用も拒否する。
- 別の場所にマウントした保存先：`--path-map 保存されたパス=この環境のパス` で読み替える。保存するパスは元の（Macの）パスのまま。
- 継続学習（#154）：`learning-archives` と `sync-learning` で、HUD切り出しアーカイブをTRAIN・VALIDATION・DEV_COMPARISONに登録する。INDEPENDENT_TESTには入れない。

## 実データでの検証（2026-11-17）

| 項目 | 結果 |
|---|---|
| 既存割当の移行 | 4つの登録簿（9・8・9・6本）の32本を取り込み。split変更0、衝突0、却下0 |
| 割当ファイルのハッシュ | 9ファイル（manifest/allocation）を照合用に記録 |
| 新規登録 | full_match_5の4本（11.6GB、24秒）をDEVELOPMENTとして登録 |
| 増分登録 | 36本すべて登録済みの再実行で、ハッシュ計算0本、0.3秒 |
| ハッシュ照合 | 62か所（元動画36、管理コピー26）、212.6GBを再計算。不一致0、欠落0 |
| 開発利用許可 | 36本に記録。QUALIFICATION 6本・FINAL_HOLDOUT 5本は `blind` でなくなり、splitは維持 |
| 独立評価の拒否 | 露出済みのFINAL_HOLDOUTを `final_evaluation` に使うと拒否 |
| 履歴末尾の削除 | 写しの末尾2行を削除すると読み込みで拒否 |
| 旧来の受領記録 | 既存の開発結果60フレームをカタログ由来の `SourcePolicy` で全件受理 |
| 継続学習への接続 | HUD切り出しアーカイブ36件を #154 の登録簿へ登録できることを確認（このときの分割20・6・10は、下記の「統合前の最終修正」で #154 の21・6・9に統一） |
| 系譜 | アーカイブ36件、タイムライン2件、開発用評価2件を登録。評価から録画までたどれる |

## 統合前の最終修正（2026-11-17）

| 項目 | 決定 | 対応 |
|---|---|---|
| シンボリックリンク | 正式に許容する。独立したバックアップとしては扱わない | リンクを保存場所として登録でき、リンク先（リンクの文字列）を記録する。`summary` の `recordings_with_two_regular_copies` は通常ファイルだけを数える |
| リンクの異常 | 検出する | `verify` が `broken_links`（リンク先がない）、`retargeted_links`（リンク先が変わった）、`became_links`（通常ファイルがリンクになった）、`changed_sources`（ハッシュ不一致）を報告する。ハッシュ不一致は隔離する |
| 学習データ割当の差異 | #154の割当（21・6・9）を正とする | `import-learning-assignment` で #154 の登録簿の分割とIDを引き継ぐ。引き継いだ分割は変更できず、同じ物理試合を別の分割に置けない。新しい試合だけがハッシュで分かれる |
| 独立評価 | 現在の36試合は使わない | 36試合とも露出済みで、`independent_evaluation_eligible` は0。#154のINDEPENDENT_TESTにも入れない |

管理コピー26本は、2026-11-17に利用者がシンボリックリンクに置き換えた（意図した操作）。`register <登録簿>/sources --role managed` でリンクとして登録し直した（リンク先の内容を再ハッシュして一致を確認したうえで記録）。

### 実データでの確認

| 項目 | 結果 |
|---|---|
| リンクへの置き換えの検出 | 26か所を `became_links` として検出。ハッシュ不一致0 |
| リンクとしての登録し直し | 26か所。登録後の `verify` で異常0 |
| 全件ハッシュ照合（登録し直した後） | 62か所・212.6GB。不一致0、欠落0、リンク切れ0 |
| 保存場所 | 62（うちリンク26）。通常ファイルが2つある録画は0 |
| 学習データ割当 | #154の登録簿（21・6・9）を36件すべて引き継ぎ。DEV_COMPARISONの9試合は #154 と同じ |
| #154への反映 | 既存の登録簿への同期は追加0・既存36で、登録簿は1バイトも変わらない |

## 旧来の管理方式からの移行（2026-11-17）

旧来の3つの仕組みは、それぞれの割当ファイルだけで録画の利用を判断していたため、カタログの漏洩防止を通らずに保護録画を使える経路が残っていました。カタログを指定すると、どの経路もカタログで照合します。

| 経路 | 移行前 | 移行後（カタログ指定時） |
|---|---|---|
| `SourcePolicy`（旧形式の割当ハッシュ） | 割当ファイルのハッシュだけで許可 | 許可リストの全録画をカタログで照合し、split・物理試合ID・`guard` が合わなければ拒否 |
| 段階的予約（`register_six`） | 割当ファイルだけを書く | 書く前にカタログと照合し、書いた割当をカタログへ取り込む。食い違いがあれば何も書かない |
| 1本目・2本目の有効化 | 割当ファイルから許可を作る | カタログの `guard` を通し、`development_use` を記録したうえでカタログ形式の `SourcePolicy` を返す |
| `register_private_sources.py` | 割当ファイルだけを書く | 書いた割当をカタログへ取り込み、食い違いがあれば中止する |

カタログは、引数（`--catalog`、`SourcePolicy` の `catalog_check`）か環境変数 `VALORANT_RECORDING_CATALOG` で指定します。保存先の読み替えは `VALORANT_RECORDING_PATH_MAP`（JSON）で指定できます。どれも指定しない場合は従来の動作のままで、他の担当の作業手順は変わりません。

継続学習（#154）への反映は、`sync-learning --dry-run` で差分（追加予定、登録済み、分割の食い違い、IDの食い違い）を確かめてから行います。#154が統合されていない環境では、何も書かずに終了コード2で止まります。

## 制約

- 同じ試合を別の設定で録画した場合など、内容が違う同一試合はハッシュでは見分けられません。物理試合IDの指定は利用者の申告に依存します。
- 同じ場所の写し（originalとmanaged）は災害対策のバックアップになりません。別の暗号化ディスクなどへの複製と復元確認は、引き続き運用で行います。
- 既存の解析コード（`SourcePolicy` など）はまだ旧来の割当ファイルを直接読みます。カタログからの移行は別の変更で行います。
