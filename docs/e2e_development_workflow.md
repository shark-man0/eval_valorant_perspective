# 実動画E2Eの開発フロー

## モードと互換性

共通の `scripts/e2e/run_dataset_case.py` に `--mode targeted|sampled|full` を追加しました。指定を省略した既存コマンドは引き続きfullです。WindowsとRaspberry Piで同じPython orchestration、profile形式、production recognizerを使用します。

| モード | 入力 | 用途 |
| --- | --- | --- |
| targeted | 固定PTSから変更対象のカテゴリを明示選択 | 個別reader、既知の誤検出、回帰保護 |
| sampled | 動画全体から選んだ固定30フレーム | candidateの一次比較 |
| full | 既存の動画全体に対する2-pass解析 | 最終候補の採用前検証 |

fullのサンプリング、実PTSの扱い、連続性、NCC 0.90などの閾値、profile、validation pack、assertion semanticsを高速化目的で変更していません。既存のfull report/historyのschemaも維持しています。`processed frames` は従来のsamplerが実際に解析したフレーム数であり、動画の全コンテナフレーム数ではありません。

部分評価はisolated pointの評価です。各queryは実画像のcalibration prefixと現在フレームを使い、独立した時系列コンテキストでproduction analyzerを実行します。過去のアンカー検出結果やidentity判定を注入しません。HP / Ability / Weapon-Ammo / spectator exclusionの条件を維持します。prefixの観測値・イベントは評価対象に含めません。

部分評価では連続するイベント、round boundary、map trajectoryを検証したとは扱いません。traceの時間区間やイベントを疎な点から作らず、full packの評価も実行しません。現在のCLIは固定PTS方式です。連続区間に依存する変更は、部分評価の結果だけでは採用せずfullの検証を必要とします。

## 推奨手順

1. 変更箇所のunit testを実行する。
2. 関連カテゴリのtargeted E2Eを実行する。
3. 改善候補だけを固定sampled E2Eでbaselineと比較する。
4. production全体への影響がある変更、または採用候補に全回帰テストを実行する。
5. 最終候補だけにfull E2Eを実行する。

全candidateに4・5を必須にしません。targeted／sampledで改善がなく、または新たな回帰があるcandidateはそこで止めます。件数だけでなく `evaluation_report.json` のPTS・fieldごとのFAILも比較してください。既存FAILがあるbaselineでは、exit code 1だけから「新たな回帰」と断定しません。

以下はこのPiで検証したprofile13を使う具体例です。candidate評価では `--hud-layout` を候補の完全なprofileに置き換え、layout、templates sidecar、参照画像、maskを一式で用意します。`.env.local` のprofileは変更していません。Pythonは3.12を使用します。Windowsでは先頭の `python3` を `py -3.12` に置き換え、動画・pack・profileの所在を明示してください。Windows実機での実行は今回未検証です。

```bash
# 変更箇所のunit test（例：E2E runner）
python3 -m pytest -q tests/unit/test_e2e_dataset_runner.py

# live HUD変更の短い評価（今回6フレーム、約71秒）
python3 scripts/e2e/run_dataset_case.py --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 --video-id match_001 --validation-pack ValorantData/valorant_e2e_validation_pack_v3 --hud-layout outputs/hud_profiles/pi-structural-20261007-13/hud_layout.json --mode targeted --category live

# 固定sampled評価（カテゴリを絞らず代表30フレームを使う）
python3 scripts/e2e/run_dataset_case.py --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 --video-id match_001 --validation-pack ValorantData/valorant_e2e_validation_pack_v3 --hud-layout outputs/hud_profiles/pi-structural-20261007-13/hud_layout.json --mode sampled

# 比較時は同じmode・PTSセットの完了runを追加指定する
# --previous outputs/e2e/match_001/<前回run>

# 採用前の全回帰テスト。外部pack連携も有効にする
VALORANT_E2E_PACK="$PWD/ValorantData/valorant_e2e_validation_pack_v3" python3 -m pytest -q tests
python3 -m ruff check src tests scripts/e2e
python3 -m mypy src/valorant_ai_coach

# 最終full。--modeを省略した従来コマンドも同じ挙動
python3 scripts/e2e/run_dataset_case.py --video ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4 --video-id match_001 --validation-pack ValorantData/valorant_e2e_validation_pack_v3 --hud-layout outputs/hud_profiles/pi-structural-20261007-13/hud_layout.json --mode full
```

numeric OCRを使うprofileでは、そのOSで通常のproduction OCR依存を用意します。今回の計測は既存のPiローカルOCR runtimeをPATH等で指定しました。これは検証環境の指定であり、Pi専用の認識分岐ではありません。

`--frame-suite` を省略すると `datasets/e2e_suites/<video-id>/<mode>.json` を使用します。`--category` は繰り返し指定でき、カテゴリの和集合をPTS順に評価します。`--cache-dir` の既定値は `outputs/e2e_cache` です。fullで部分入力のオプションを指定すると解析前に拒否します。

## 固定PTSと期待値

`datasets/e2e_suites/match_001/targeted.json` は37フレーム、`sampled.json` は固定30フレームです。乱数は使用しません。以下のカテゴリを管理します。

- live、spectator、combat_report、buy_menu、unknown
- hp_numeric、timer_score
- known_false_positive、regression_protection、round_boundary

各行にPTS、category、source video SHA256へのbinding、review provenance、optional noteを保持します。確定している場合だけexpected state／numeric値を付けます。レビュー済みフレームにはdecoded pixel SHA256も保持し、実際にdecodeした画像との一致をevaluator側で確認します。

元データは既存のsemantic review、blind scene review、HPレビュー、validation packのsync anchors／frame PTS sidecar／timelineです。数値の期待値には元のannotation JSONと画像のhashを付けています。画像のファイル名だけから状態を推測しません。combat reportや外部cameraの一部にはprimary-stateの独立した正解labelがなく、カテゴリのみで未評価として残しています。

期待値があるのに観測・値が欠落した場合はFAILです。期待値自体が未確定の行はNOT_EVALUATEDです。partialはフレーム単位で数え、複数fieldの不一致も1フレームのFAILとします。fullの件数は既存のassertion record単位です。両者を同じ分母の精度として比較しません。

productionに渡す `frame_input.json` はPTS、calibration prefix、source hash、modeだけです。category、review、期待値は渡しません。training／holdoutや既存のground truthは変更していません。`build_frame_suites.py` は既存の証拠から固定manifestを再構成するツールであり、新しい正解を生成しません。

## キャッシュと排他

再利用するものはdecoded JPEG、immutable probe metadata、実際のcontainer PTSです。認識結果、identity、calibration判定、OCR結果、temporal featuresはキャッシュしません。

- 画像のキー：source SHA256、厳密なPTS、前処理version、native JPEG条件、decode policy、OpenCV build/version/native binary hash、backend preference。
- probe／PTSのキー：source SHA256、ffprobe binaryとpolicyのfingerprint。
- 画像・metadataのchecksumを検証し、破損・symlink・不正なkeyは再利用しない。
- native extractorが要求したPTSと完全一致するフレームを返さなければ失敗する。
- profile／recognizer変更時も画像は共有できるが、認識は毎回やり直す。code/profileのfingerprintは別途runに記録する。

fullは既存のextractorと処理順序を維持し、今回はpersistent cacheによるfullの変更を導入していません。前処理や認識の安全な追加キャッシュは別途実測・正当性の確認が必要です。

fullには共通runnerとnative子プロセスのOS advisory lockを設けました。親の異常終了時も子のfullがロックを保持します。Windowsはmsvcrt、POSIXはflockを用いるorchestration上の排他であり、recognizerのOS分岐ではありません。Pi上でfullを複数同時実行しません。フレーム並列化も採用していません。

## 結果・時間・比較

各runの `runtime_summary.json` と `runtime_summary.md` にmode、processed frames、wall-clock、frames/sec、前回比較、runtime deltaと百分率を保存します。`stage_timings.json` はnative処理の集計です。call countは2-passや内部の複数matcherを含むため、unique frame countとは異なります。

最低限、metadata/open、decode、geometry、identity、spectator、menu、numeric/OCR、event detection、trace serialization、evaluator、report generationを分離し、total／calls／average／wall shareを出力します。visual trigger scan、visual analysis、round package buildも分離しました。nested stageは子の時間を親から引いたexclusive timeです。計測外のsetup、画像読み込みの一部、検証などの残余を特定のrecognizerの時間とみなしません。

部分評価でfull pack/schema評価は未実施です。partialの `schema_valid` 診断列をfull packのPASS/FAILと読み替えないでください。

前回比較には同じmode、video SHA、pack/assertions、suite hash、選択カテゴリ、PTS、prefixを要求します。recognizerやprofileの違いはcandidate比較に必要なため、比較拒否の理由にはしません。ただし各runのfingerprintは記録します。前回runがterminalであり、raw／trace／evaluation／timing／frame input等の宣言されたhashが一致することを検証してから使います。終了結果がないrunや破損したrunは比較対象になりません。

Current／Previous／Deltaは変動値です。改善の判定には独立した正解とfieldごとの回帰確認が必要です。初回のcache missとwarm runのruntime差をrecognizerの高速化と断定しません。

verbose logはrun directoryに保存し、実行中にログ・PID・生成物を繰り返し読みません。commandの終了コードは比較処理より先に `command_results.json` へ保存します。長時間実行は一度だけ開始して終了まで待ち、terminal結果だけを確認します。

## Raspberry Pi実測（2026-10-07）

動画SHA256：`71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06`。同じ171秒の動画とprofile13を使用しました。実測artifactは `outputs/recognition-investigation/e2e-tiered-benchmark/` と `e2e-tiered-final-verification/` にあります。

| 検証 | フレーム | runner wall | frames/sec | PASS / FAIL / NE |
| --- | ---: | ---: | ---: | --- |
| 変更前full | 4634 | 約3時間37分28秒※ | 約0.355※ | 23 / 55 / 4 |
| targeted：live | 6 | 70.788秒 | 0.08476 | 6 / 0 / 0 |
| targeted：全固定セット、初回cold | 37 | 710.903秒（11分51秒） | 0.05205 | 12 / 13 / 12 |
| sampled：全固定セット、warm | 30 | 326.450秒（5分26秒） | 0.09190 | 7 / 12 / 11 |
| 変更後full | 4634 | 12995.973秒（3時間36分36秒） | 0.35657 | 23 / 55 / 4 |

※変更前にはstopwatchのruntime artifactがありません。過去の完了run `20261006T224429Z-e77952e0` の開始日時とterminal metadata保存mtimeの差13047.818秒による参考値です。厳密な性能改善率として扱いません。今回のouter process wallはtargeted-live 71.619秒、full 12997.096秒で、CLI初期化・終了等を含みます。

変更後fullと変更前fullは、4634フレームの順序付きPTS、全observation（認識値・状態・confidence等）、HUD／visual eventsが完全一致しました。82 assertionのstatusも一致し、回帰・改善とも0、negative assertion失敗0、discontinuity違反0です。安全性・精度を緩めた高速化ではありません。fullは最終検証能力と所要時間を維持し、日常の入力を明示的に限定することで待ち時間を減らしています。

| fullの主要処理 | total秒 | calls | average秒 | wall割合 |
| --- | ---: | ---: | ---: | ---: |
| HUD geometry※ | 6205.481 | 11326 | 0.547897 | 47.75% |
| spectator detection | 2227.892 | 5662 | 0.393481 | 17.14% |
| numeric readers / OCR | 2022.642 | 5662 | 0.357231 | 15.56% |
| visual analysis | 642.106 | 1 | 642.106 | 4.94% |
| frame decode | 559.756 | 11 | 50.886897 | 4.31% |
| identity detection | 461.971 | 22648 | 0.020398 | 3.55% |

※geometry stageはanchor探索・calibration検証に加え、feature sequenceの準備を含みます。identity／spectator／menuの子stage時間は差し引いています。未計測の処理を含めて「純粋なanchor探索だけの時間」とはしません。

候補14も同じ固定セットで比較しました。

| sampled metric | Current：14 | Previous：13 | Delta |
| --- | ---: | ---: | ---: |
| PASS | 7 | 7 | 0 |
| FAIL | 12 | 12 | 0 |
| NOT_EVALUATED | 11 | 11 | 0 |
| unknown | 20 | 20 | 0 |
| live | 3 | 3 | 0 |
| spectator | 5 | 5 | 0 |
| buy menu | 2 | 2 | 0 |
| wall秒 | 401.398 | 326.450 | +74.948（+22.96%） |

両sampled runは32画像すべてcache hitでした。targeted全セットも判定件数は同じで、候補14は472.610秒でしたが、profile13側はcoldで39画像missのためruntimeの単純比較から認識高速化を主張しません。固定セットで改善の証拠がない候補14に追加fullを実行せず、今回のfull互換性検証は最後の正常完了baseline profile13だけで行いました。

部分評価のFAILは既存のtimer／score readerの未認識です。fullの55 FAILも既知の認識課題として残っています。高速化作業が認識改善の完了を意味するものではありません。過去のprofile14 fullはterminal raw／trace／evaluationなしで終了しており、正常fullの時間・精度として数えていません。その終了原因は未確定です。

全回帰は1096 PASS／9 SKIPでした。外部packの指定を補った3 testを含む5 testが追加でPASSし、未実行は従来のWindows依存4件、任意の別動画anchor test、sibling pack配置依存testの6件です。RuffとmypyもPASSしました。現在の実動画fullと指定packのvalidation／evaluatorは実行済みです。

## 追加candidateの段階評価（2026-10-08）

同じ構造的profile13を基に、timerのみの明示OCRを候補15、さらに既存shared-timer fact基準と同じ `minimum_confidence: 0.90` を候補16として検証しました。scoreの暗黙OCRは無効のままです。optional reader設定 `minimum_confidence` はdigits／fieldsに使用でき、0.85〜1.0の数値のみを受理します。省略時は従来の挙動を維持します。不正な明示設定はreaderをunavailableとして残し、暗黙OCRへの置き換えを防ぎます。

| 候補16の検証 | 入力 | wall | 結果 |
| --- | ---: | ---: | --- |
| targeted：timer_score | 13フレーム | 約152秒 | timer field failure 13→4。frame FAILはscore未認識により13のまま |
| sampled | 固定30フレーム | 約331秒（5分31秒） | timer正解23、未認識7、誤読0。frame件数7 / 12 / 11は不変 |
| 全回帰 | tests全体 | 1344秒 | 1109 PASS、6 SKIP |
| full | 4661フレーム | 15149.129秒（4時間12分29秒） | 23 PASS / 55 FAIL / 4 NE、候補却下 |

候補15は独立画像レビューでtimer誤読2件があり、full前に却下しました。候補16は既存の独立holdout64件で正解48・未認識16・誤読0、sampledも誤読0だったためfullに進めました。しかしfullの画像確認で、PTS 124.486003の1:26を4:26、135.802669の1:15を4:15、156.002669の0:55を10:55と誤読しました。confidenceはそれぞれ0.93834、0.95371、0.92050です。閾値のみでは安全性を保証できません。候補16は採用せず、`.env.local` も変更していません。fullで受理されたtimer3411件全体の正確性は未検証です。誤読を発見した後に全件を正解と主張しません。

fullのnegative assertion失敗とdiscontinuity違反は0、82 assertionのstatusは前回と一致しました。baselineの4634 PTSはすべて残り、同じPTSのtimerとframe_index以外のobservationは一致しました。timer変更を既存のchange-point samplerが拾い27 PTSを追加したため、状態の単純件数も変動しています（spectator +11、unknown +16）。認識の改善とは扱いません。fullの入力範囲・sampler・連続性は変更していません。

候補16のボトルネックはgeometry 6244.055秒（41.22%）、numeric/OCR 4132.396秒（27.28%）、spectator 2237.387秒（14.77%）です。full wallは前回より2153.156秒（16.57%）増えています。認識条件を変えずに短い段階で不適格候補を除外する意義が確認できました。

`e2e_reports/match_001/profile16_diagnostic_assessment.json` にterminal hash確認、入力fingerprint、誤読画像のSHA256とPTS、却下理由を記録しました。通常のreport/historyは最後の診断runの結果であり、profileの採用宣言ではありません。raw／trace／evaluationのterminal hash一致、source/profile/code fingerprint、schemaを確認済みです。Ruff／mypyもPASS、Windows実行は未検証です。

## main統合後の検証

2026-10-08、リモートmainのCI／observability更新（`27e668c`）を競合なく統合しました。統合後にRuff（src／tests／E2E・diagnostics scripts）、mypy（96 source files）、変更関連のunit test165件がPASSしました。対象にはobservability、HUD profile生成、spectator icon、numeric confidence、E2E runner／cache／replay／manifest／metrics／timingを含みます。実動画fullの上記計測は統合前のfingerprintに対応し、統合後に再実行したfullと偽って扱いません。
