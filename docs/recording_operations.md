# 録画の運用手順（登録から学習・独立評価まで）

新しい録画を登録してから、開発・学習に使い、独立評価に回すまでの手順です。どの段階でも、録画カタログ（`docs/recording_data_catalog.md`）を正本とします。カタログの中身（ID、ハッシュ、パス、ファイル名）はGitに入れません。

## 準備

カタログの場所と、別の環境でマウントした保存先の読み替えを環境変数で指定します。両方とも任意ですが、指定すると旧来の割当ファイルを使う処理もカタログで照合されます。

```sh
export VALORANT_RECORDING_CATALOG="$PRIVATE_CATALOG"
# 例: Macで登録したパスを仮想環境のマウント先で読む場合
export VALORANT_RECORDING_PATH_MAP='{"/Users/USER/valorant": "/mnt/valorant"}'
alias rec='python -m valorant_ai_coach.recordings --catalog "$VALORANT_RECORDING_CATALOG"'
```

| 環境変数 | 内容 |
|---|---|
| `VALORANT_RECORDING_CATALOG` | カタログのディレクトリ。`SourcePolicy`、段階的予約、2本目の有効化、`register_private_sources.py` がこのカタログで照合する |
| `VALORANT_RECORDING_PATH_MAP` | `{"保存されたパスの先頭": "この環境のパス"}` のJSON。CLIの `--path-map` と同じ |

## 1. 新しい録画を登録する

```sh
rec register "$NEW_RECORDINGS_DIR" --physical-match-id MATCH --probe
rec verify --recordings ID
rec head        # 表示された SEQ:SHA256 をカタログの外に控える
```

- splitは指定しなければ `sha256(seed:physical_match_id)` で決まり、後から変えられません。映像を見る前に登録します。
- 前半・後半など同じ試合の複数ファイルには、同じ `--physical-match-id` を付けます。
- サイズが同じ別の録画は `--confirm-distinct` を付けるまで登録しません。
- 旧来の取り込み（`scripts/diagnostics/register_private_sources.py register`）を使う場合は `--catalog` を付けるか環境変数を設定します。割当はそのままカタログへ取り込まれ、食い違いがあれば登録を中止します。

## 2. 開発に使う

DEVELOPMENTの録画はそのまま開発に使えます。使ったことを記録します。

```sh
rec guard ID --purpose development_analysis
rec expose ID --kind development_use --note "何に使ったか"
```

既存の解析器に渡す `SourcePolicy` は、カタログから作ります。

```json
{"catalog": "<カタログ>", "allowed_recording_ids": ["<ID>"], "protected_source_sha256s": []}
```

段階的予約（`temporal/staged_validation.py`）と2本目の有効化（`temporal/second_validation.py activate --catalog`）は、カタログを指定すると割当をカタログで照合し、`development_use` を記録したうえでカタログ形式の `SourcePolicy` を返します。カタログと食い違う割当は、ファイルを書く前に拒否します。

QUALIFICATIONやFINAL_HOLDOUTの録画を開発に使うには、利用者の判断を `rec expose ID --kind user_authorized_development_use --note "理由"` で記録します。記録した録画は独立評価に使えなくなり、元に戻せません。

## 3. 学習に使う（#154の統合後）

学習用のデータ（HUD切り出しアーカイブなど）は、生成したものをartifactとして親の録画に結び付けて登録します。

```sh
rec artifact --kind frames --parent ID --producer NAME --version V --path ARCHIVE
rec plan --producer NAME --version V     # まだ処理していない録画
```

#154の継続学習登録簿へは、差分を確かめてから反映します。

```sh
rec import-learning-assignment "$WORKSPACE/dataset_registry.json"   # 既存の分割を引き継ぐ（初回のみ）
rec sync-learning --workspace "$WORKSPACE" --dry-run                  # 書き込まずに差分を表示
rec sync-learning --workspace "$WORKSPACE"                            # 反映
```

- `--dry-run` は `would_add`（追加予定）、`already_present`（登録済み）、`split_mismatch`（分割の食い違い）、`id_mismatch`（IDの食い違い）を返します。食い違いが1件でもあれば終了コード1で止まるので、反映せずに原因を確認します。
- 反映できるのはTRAIN・VALIDATION・DEV_COMPARISONだけです。QUALIFICATIONとFINAL_HOLDOUTは登録簿に入れません。
- #154が統合される前は、`sync-learning` は終了コード2で止まり、何も書きません。
- モデルを登録するときは `rec artifact --kind model --parent <学習データのartifact>` とします。祖先に学習に使えない録画があれば拒否されます。

## 4. 独立評価に使う

独立評価に使えるのは、一度も開発・学習に使っていない（露出していない）QUALIFICATIONとFINAL_HOLDOUTの録画だけです。2026-11-17時点の36試合はすべて露出済みなので、独立評価には新しく登録した録画を使います。

```sh
rec summary                                    # independent_evaluation_eligible を確認
rec open ID --purpose final_evaluation --note "承認の記録"
rec guard ID --purpose final_evaluation
```

- `open` には理由の記録が必要です。開封すると `blind` でなくなります。
- 露出済みの録画は `open` も `guard` も拒否します。
- 評価結果は `rec artifact --kind report --parent ID` で登録し、どの録画で評価したかをたどれるようにします。

## 5. 定期的な確認

```sh
rec verify --trusted-head "SEQ:SHA256"   # 全保存場所の再ハッシュと履歴末尾の削除の検出
rec leak-check docs/*.md                 # Gitに入れる文書にIDやハッシュが含まれていないか
```

`verify` が `changed_sources`、`broken_links`、`retargeted_links`、`became_links` のいずれかを報告したら、その録画は隔離されるか、保存場所の確認が必要です。ハッシュ不一致の録画はどの用途にも使えません。

## カタログを指定しない場合

カタログを指定せず、環境変数もない場合は、旧来の割当ファイルだけで判断する従来の動作のままです（他の担当の作業手順を壊さないため）。この場合は漏洩防止の照合が働かないので、正式な運用では必ずカタログを指定します。
