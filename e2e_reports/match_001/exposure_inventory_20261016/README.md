# PTS・split記録の参照用コピー（2026-10-16）

ユーザーの共有依頼に基づき、ローカルの非公開作業記録からPTSと出所のメタデータだけを抽出したスナップショットです。画像、動画、正解ラベル、認識出力、認識profile、qualification bundle、認証情報、個人の絶対パスは含めません。

**完全なexposure台帳ではありません。掲載がない区間を未閲覧・未使用・新しい独立holdoutと判断しないでください。** 抽出・保存された画像の記録から、実際の閲覧時刻や開発での利用履歴を自動的に確定できません。同じ終了イベントの隣接画像も、独立した別イベントにはなりません。

## ファイル

| ファイル | 内容 |
| --- | --- |
| `sources.json` | 対象動画2本のファイル名、SHA256、timebase |
| `frames.jsonl` | 整数PTS、timebase、pixel hash、存在する場合のencoded hash・decoder epoch、記録元ID、用途の分類 |
| `artifact_index.json` | 記録元38ファイルのリポジトリ相対名とSHA256。元ファイル自体は非公開 |
| `historical_split_plans.json` | 当時の開発・geometry・評価候補・control候補等の区間割当 |
| `method_snapshots.json` | 当時のcode/profile fingerprintやcommitの記録。現在有効な資格を意味しない |
| `discovery_requests.json` | 探索画像の取得を要求した時刻。実際のdecode PTSや閲覧確認とは別 |
| `summary.json` | 件数、保証できない項目、公開データ6ファイルのSHA256 |

`frames.jsonl` は4,518レコード、sourceと正規化したtimebase・PTSの組み合わせで4,432地点です。同じPTSでもdecoder epochや画像hashの異なる記録、epoch/hashが一部省略された補助記録があり、レコード数を独立した画像・イベント数とは扱いません。

`source_identity_inherited` / `time_base_inherited` は、元レコードに値がなく動画別の既知メタデータを用いた場合にtrueです。秒からPTSを推測して補ったレコードはありません。元のファイルSHA256はサニタイズ前の非公開記録の照合用であり、画像がリポジトリに存在することは保証しません。

## 対象範囲

- `supplemental_010246`：`Valorant_10-08-2026_1-2-46-283.mp4`。初期評価、事前分割後の開発・過去の評価、保存済みgeometry記録など。
- `supplemental_001927`：`Valorant_10-08-2026_0-19-27-350.mp4`。geometry検証6地点、探索画像、E1〜E3のnative画像、開発参照や方式固定の記録など。
- match_001の全履歴、元Linux環境の完全なexposure履歴、他チャット・他担当者の履歴は網羅しません。
- **match_002の画像利用履歴を調査・証明したデータではありません。** match_002のGTは含みません。

`historical_split_plans.json` の `unused_*` や `held_*` は計画作成時の名称です。その後の利用を取り消すものではありません。当時の`viewed:false`等を現在状態として誤読しないよう、それらのフラグは抽出していません。`historical_evaluation`も当初の用途分類であり、別方式への新しい独立性を保証しません。

geometry検証も画像の参照・利用です。geometry用と値認識用の分離方針は元のsplit計画に記録されていますが、本データから「動画全体を一度も見ていない」とは主張できません。

用途分類は記録元ファイル名・配置による便宜的な分類です。初回閲覧者、実際に使用した全アルゴリズム、閲覧日時、完全なイベント単位のsplitは復元していません。すべてのframeで新しいblind holdoutの状態を`not_certified`としています。独立評価への採用には、別途イベント単位のexposure確認が必要です。

## 別環境で参照する

専用ブランチ `codex/round-boundary-requalification` を取得し、このディレクトリを開いてください。参照だけならPythonや元動画は不要です。Pythonで特定sourceのPTSを抽出する例：

```python
import json
from pathlib import Path

root = Path('e2e_reports/match_001/exposure_inventory_20261016')
for line in (root / 'frames.jsonl').read_text(encoding='utf-8').splitlines():
    row = json.loads(line)
    if row['source_id'] == 'supplemental_001927':
        print(row['pts_ticks'], row['time_base'], row['purposes'])
```

公開ファイルの照合：

```python
import hashlib
import json
from pathlib import Path

root = Path('e2e_reports/match_001/exposure_inventory_20261016')
summary = json.loads((root / 'summary.json').read_text(encoding='utf-8'))
for name, expected in summary['files_sha256'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
```

元の非公開作業記録がある環境で新しいスナップショットを生成する場合：

```bash
python scripts/diagnostics/export_pts_exposure_inventory.py \
  --repo-root . --output-dir /tmp/new-pts-inventory
```

既存の出力先は上書きせず拒否します。元動画をdecodeしたり、新しい画像を閲覧したりするコマンドではありません。Validation Packやrecognizerの入力として利用しないでください。
