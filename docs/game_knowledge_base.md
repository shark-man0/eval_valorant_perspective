# 外部ゲーム知識基盤（Issue #96）

録画から一から学習しなくてよいゲーム情報（エージェント、アビリティ、武器、マップ、ルール）を、出典・版・ハッシュ付きの共通データとして持ち、HUD・Map・タイムラインの各認識器から同じAPIで参照できるようにした。

知識は「ゲームがどういうものか」を表すだけで、録画の中で何が起きたかの証拠にはしない。候補の生成・順位付け・制約に使い、正式Factは作らない。

## 構成

| 置き場所 | 内容 | Git |
|---|---|---|
| `config/game_knowledge/valorant_content_en_13.10.json` | エージェント30、アビリティ、武器21、マップ13、コールアウト300（英語） | コミット |
| `config/game_knowledge/valorant_content_ja_13.10.json` | 同じ項目の日本語名（日本語クライアントの画面文字と照合する） | コミット |
| `config/game_knowledge/game_rules_v1.json` | ラウンド時間、購入フェーズ、スパイク時間、HUDのアビリティ順など | コミット |
| `config/game_knowledge/source_ledger_v1.json` | 出典台帳（種別、利用条件、更新頻度、信頼度、ハッシュ） | コミット |
| `config/game_knowledge/reference_assets_13.10.json` | 参照画像268点の内容ダイジェスト | コミット |
| 参照画像キャッシュ（アイコン、ポートレート、ミニマップ） | Riotの画像 | **コミットしない**（非公開キャッシュ） |

ゲーム版は 13.10.00.5893614（release-13.10、2026-11-07ビルド）。

## 出典と利用条件

詳細は `source_ledger_v1.json` にある。要点は次のとおり。

- **valorant-api.com**（Riotクライアントデータの非公式ミラー）から名前・ロール・スロット・武器性能・コールアウト・座標変換を取得した。ブラウザで取得した圧縮スナップショットを、ブラウザ側とこちら側の両方でSHA-256照合した。
- **参照画像**はRiotの著作物なので、手元の非公開キャッシュにだけ置く。キャッシュは `content_digest`（全ファイルの「URL SHA-256」行の要約）が固定値と一致しないと開けない。
- **ルールの数値**は複数の二次情報で一致を確認した値で、状態は `secondary_consistent`。候補の事前分布としてだけ使う。
- **Riot公式API**は鍵が必要なので今回は使っていない（既存の `maps/public_catalog.py` で読み込める）。**Overwolf**は既存録画に使えず、**YouTube**は利用規約上使えないため、どちらも `not_usable` として理由を記録した。

## API

```python
from valorant_ai_coach.knowledge import load_game_knowledge

k = load_game_knowledge()               # 版を固定し、台帳のハッシュを検証して読む
k.agent("クローヴ").role               # "controller"（日本語・英語・UUIDで引ける）
k.agent("Fade").hud_abilities()         # C, Q, E, X の順のアビリティ
k.weapon("ヴァンダル").magazine_size     # 25
k.weapons_by_cost(2900)                 # Vandal, Phantom, Warden
k.map("Haven").sites                    # ("A", "B", "C")
k.map("Ascent").world_to_minimap(x, y)  # ミニマップ画像上の正規化座標
k.vocabulary("callout", "ja-JP")        # 画面の「Aロビー」→ "A Lobby"
k.rule("spike_detonation_sec")          # 45（出典と検証状態つき）
```

参照画像は `ReferenceAssets.load(cache_dir)` で開く。取得は次のスクリプトで行う（標準ライブラリのみ、valorant-api.comに接続できる環境で実行する）。

```sh
python3 scripts/knowledge/fetch_reference_assets.py --out ~/valorant_knowledge_cache \
  --expected-digest 8c45fc55106c2c598708514e288d55a579af016cb5125ad19edd91672b47bf84
export VALORANT_KNOWLEDGE_CACHE=~/valorant_knowledge_cache
python -m valorant_ai_coach.knowledge verify-assets
```

## 知識を使う読み取り器

- **アビリティHUD**（`knowledge/hud_abilities.py`）：画面下中央の4スロットを公式アイコンと照合し、表示中のHUDがどのエージェントかを順位付けする。アイコン下のチャージ表示から、使えるアビリティ数とアルティメットの準備状態も読む。観戦中は観戦相手のHUDが出るため、録画者のエージェントは試合全体の多数決で決め、1フレームでは決めない。
- **上部マッチバー**（`knowledge/top_bar.py`）：各チーム5枠のうち、生存者のポートレートが中央寄せで並ぶという知識を使い、生存人数と人数状況（有利・不利・同数）を読む。空き枠はチーム色の帯だけで模様がないため、ポートレートの有無はテクスチャ量で判定する。中央寄せになっていない読み取りは不整合として捨てる。
- **ロール解決**：`RoleResolver.from_game_knowledge()` で、エージェント名（日本語名を含む）からロールを返す。既存の `RoleResolver()` の既定動作は変えていない（正式パイプラインへの接続は承認後）。

## 検証

### データの整合

- スナップショットの2ファイルは台帳のハッシュと一致しないと読み込まない（単体テストで確認）。
- ミニマップ座標変換：コールアウト300点を公式ミニマップ画像に投影し、地図の描画領域に入るかを数えた。x・yを入れ替える変換で **277/300**、入れ替えない変換で **70/300** だった。入れ替える方を採用した。残りの23点は主にスポーン地点など描画領域の外縁にあたる。

### 実動画：録画者エージェントの特定

開発用録画36試合（full_match〜full_match_5 の全動画）を5秒間隔で切り出して比較した。正解は、各試合のHUDの切り出しと公式アイコンを並べた目視確認による（Claudeによるレビュー）。

| 方式 | 特定できた試合 | 正解 |
|---|---|---|
| 外部知識なし（従来） | 0/36（名前・ロールを出せない） | 0/36 |
| 公式アイコンのみ（スロット順の知識なし） | 36/36 | 36/36 |
| 公式アイコン＋スロット順（採用） | 36/36 🟢 | 36/36 🟢 |

- 36試合の録画者は16エージェントで、4ロールすべてを含む（Omen 8、Fade 5、Phoenix・Neon・Sova 各3、Reyna・Killjoy・Chamber 各2、Vyse・Jett・Cypher・Clove・Tejo・Breach・Raze・Astra 各1）。
- 試合ごとの多数決の得票率は最小0.606・中央値0.760、1位と2位の平均スコア差は最小0.133・中央値0.328で、棄権した試合はなかった。得票率が1に届かないのは、残りのフレームが観戦中の味方のHUDだからである（観戦相手も同じ方法で特定できる）。
- Chamberは、Qスロットにアイコンの代わりに残弾数（例：「8」）が出るため、そのスロットのスコアが0.27まで下がる。それでも他の3スロットで特定できた。
- スロット順の知識の有無で差は出なかった。公式アイコン同士が十分に異なるためで、スロット順は照合の計算量を4分の1にする効果のほうが大きい。
- 処理時間は1試合（約400〜600フレーム）あたり約15秒。

```sh
PYTHONPATH=src python3 scripts/knowledge/agent_identification_experiment.py \
  --cache CACHE --truth fm1_1=Fade,... CROPS/*.zip
```

## 版の更新手順

1. パッチ後に valorant-api.com から同じ形式のスナップショットを取り直す（`scripts/knowledge/fetch_reference_assets.py` と同じ選択規則）。
2. 新しい版のファイル名（例：`valorant_content_en_13.11.json`）で追加し、台帳にハッシュを登録する。古い版は残す。
3. `reference_assets_<版>.json` に新しい `content_digest` を固定する。
4. 録画のクライアント版に合わせて `load_game_knowledge(version)` を選ぶ。

## 残っている課題

- コールアウトは代表点で、領域ポリゴンではない。ゾーン判定は最寄り候補の順位付けにとどめている。
- ルールの数値は録画のタイマー読み取りと照合していない（`recording_consistent` への昇格は未実施）。
- 武器スキンでインベントリのシルエットが変わるため、武器アイコン照合は未実装。
- アビリティの最大チャージ数は取得元にないため、チャージは表示の割合として扱っている。
