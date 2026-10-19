# Self Death：独立qualificationの引き渡しとPR #53の収束

本書の完了は**検証準備とblocked handoffの完了**を意味する。Self Death認識の完成、
独立qualification、正式Event、Canonical改善を意味しない。認識機能の判定は引き続き **B**。
新たな画像認識実験・閾値調整・Full E2Eは行わない。

## 1. 現在の統合状態

調査開始時のmainは `7e480c2f2f7f49aea73e1541d065d78881d2f11c`、
PR #53のHEADは `ca4b975a439fbf028e646125e3f27b0acd60ad87`。
[PR #53](https://github.com/shark-man0/eval_valorant_perspective/pull/53) はDraftのまま、
[PR #52](https://github.com/shark-man0/eval_valorant_perspective/pull/52) の
`codex/self-subject-source-continuity`（`ffdf41fd1ea8b1239891e7476512693056106962`）をbaseとする。
どちらも未マージである。調査時点ではstacked baseに対してmergeable／cleanだが、
mainへの単独統合や本番採用の承認ではない。#44／#46／#47／#50／#52の変更を本PR単独の成果と扱わない。

このhandoffではproduction、profile、asset、confidence、owner、公開Schema、GT、assertion、
samplerを変更しない。PR #42等の他担当ブランチも変更しない。

## 2. 成立した成果と測定範囲

既存の実装・実画像測定は再利用し、同じ画像を再認識しない。

| 成果 | 根拠と限界 |
| --- | --- |
| Recorder marker／killer-victim role | 固定192静止画で正しいSelf行11、未検出4、誤Self出力0。5つのvictim静止画は既知episode。独立Death 5件ではない |
| 名前ROIの実装修正 | padded templateの範囲と実pictogramを分離し、同時に残る別行から名前を借りない。source-backed regressionで本人名の伝達を改善 |
| Episode候補と時刻 | 元onsetと後続confirmationを保持し、source context変更と重複を拒否。候補を正式Deathと扱わない |
| 属性の内部契約 | victim名、fatal received damage、portraitを別source evidenceに束縛。内部v2はreview済みagent classだけを許可。実資格certificateなし |
| 限定decode | 原動画から84 native framesを再decodeし、既存cacheのPTS／pixels／判定と一致。候補R1／残存control／R2は1／0／1、正式Deathは0 |
| 資源制限 | 上記限定decodeは182.475秒、Python peak RSS 100,872,192 bytes、一時PNG peak 85,502,305 bytes。異なるscopeのFullとの速度比ではない |
| Native transport | 合成契約試験でEvent→Package→Fact→Trace→SQLiteを確認。実資格付き実動画の通過実績ではない |

`ca4b975` のLinux CIは4,357 PASS／既存7 skip、coverage 87.22%、Ruff／mypy成功。
Windows CIはtests、UTF-8-disabled checks、build、packaged smoke成功。
これらを後続の別認識コードや実動画の精度として流用しない。

## 3. Phase A：独立した資格条件

### A-1 Self Victimと物理episode

source-only reviewerが、認識結果を見る前に以下を記録する。

- source SHA、native PTS整数とtime base、decoder epoch、encoded／pixel hash。
- 録画者を示す黄色枠等の現在画像上の独立証拠、そのROIと意味のreview。
- killerとvictimの位置・対応。Self Killer、Nonself Victim、同agentの別人を分離する。
- 死亡前の状態、最初の死亡表示、後続確認を含む同一source segmentの連続入力。
- 最後に明確に死亡前と分かるnative PTSと、最初に死亡表示を確認できるnative PTSによるonset bracket。
  初出が遮蔽されていれば区間を狭く捏造せずunknownとする。表示の時刻をserver時刻と断定しない。
- code／profile／assetのfit履歴と物理episodeの独立性。

episode IDはsource SHAとsource reviewで確認した物理イベントへ付ける。
同じDeathの別window、別ROI、連続100 frame、再表示を別の正例へ数えない。
review前に固定した全episodeを評価し、失敗例を除外しない。今回、最低件数や許容誤検出率を
便宜的に新設してqualificationの代わりにはしない。1成功だけで全般性能を証明しない。

### A-2 Reportの時間的意味

| source上の状況 | 必要なreview／期待する扱い |
| --- | --- |
| 新しいSelf DeathでReportが初出 | 独立Self Victim、死亡遷移、遮蔽されていない前状態と時系列を照合する |
| 同じReportの継続 | 同じepisode。追加Deathを発行しない |
| menu等で隠れている | Reportのabsenceを証明しない。visibilityはoccluded／unknown |
| 遮蔽解除で再表示 | captionの再検出だけでfreshへ昇格しない |
| Reportのみ、現在victimなし | Subject／新規Deathはunknownのまま |
| spectator／respawn／preparation | 状態遷移だけでSelf Deathを生成しない。既存Reportの残存を別記する |
| source break後のReport | 新しいepoch。前の不在・victim・候補を持ち越さない |

Report absenceには、対象領域が観測可能で、遮蔽・別画面・reader failureではないと分かる
独立したcurrent-frame evidenceが必要である。単にNCCが0.90未満というだけでは不在をqualifiedにしない。
現行の `ReportVictimEpisodeProbe` はこれを明記した**未資格の診断**である。
case006で候補0だった事実も、absence reader全体の資格にはならない。

負例は上記に加え、Self Killer、Nonself victim、victim部分表示／OCR不明、残存killfeed、
同一pixelの繰り返し、PTS欠落・source breakを含める。caption探索で見つからなかった区間を
reviewせず完全なnegativeにしない。各controlの前後履歴が足りなければ未判定として残す。

### A-3 Countと属性を分離する

| 判定 | 必要な意味・証拠 |
| --- | --- |
| Death count | qualified Self Subject＋victim role＋新規Death＋temporal/source整合性、type／actor／round／重複排除 |
| victim_name | 同一victim行の元pixel・ROI・OCR confidence・source review。他行やGTの名前を借りない |
| killer_agent | そのDeathのkiller側またはfatal Reportの適切なportraitと、当該classの独立review |
| combat_report_damage_received | 同一Deathのfatal received rowに対応する実数値とconfidence。与ダメージ・過去Reportと区別 |
| Death point | count相当の資格に加え、そのassertionに必要な属性と時刻条件 |

属性ごとの元source PTS・ROI・confidence・qualification／reviewを保持する。
未認識属性はunknown。未知のagent classを既知classへ置換しない。
属性不足だけで独立成立したcountの資格を無条件に取り消さず、pointとの結果を分ける。
一方、Subject／victim／新規Deathが未qualifiedなら、count用も含め正式Eventを生成しない。

## 4. Phase B：Exposure Ledgerの監査

privateのtraining plans、native manifests、source-only reviews、固定静止画plan、後続fit履歴を照合した。
元記録は修正しない。追加のepisode対応表と証拠digestはprivateに保存し、公開集約は
[handoff JSON](../e2e_reports/match_001/self_death_qualification_handoff.json) に記録する。

| 分類 | 意味・扱い |
| --- | --- |
| TRAINING | reference／mask等へ画像を使用。holdoutへ戻さない |
| DEVELOPMENT | ROI／profile／実装の調整、失敗原因調査に使用。現モデルの独立評価へ戻さない |
| EXPOSED_REGRESSION | 出力を閲覧した既存検証context。固定回帰には使用可能。新しいblindとは呼ばない |
| PROSPECTIVE_HELD_OUT | model・episode割当を先にfreezeし、fitとの分離が裏付けられた未評価episode |
| UNKNOWN_EXPOSURE | 未登録、履歴不明、他担当での利用が未確認。未使用の証明ではない |

今回のwhole-model評価用に確認できた `PROSPECTIVE_HELD_OUT` は**0件**。
Mac上に未評価episodeが「おそらくある」との情報は候補であり、この件数へ加えない。

match_001のR1／R2は開発・回帰に使用済み。match_002の既知contextには次の履歴がある。
下表はepisode／fit-contextの重複を束ねた対応表で、15件のqualified Deathや新しいpositive数ではない。
元のexact PTS・pixel hash・レビュー時刻順はprivate台帳から追跡できる。

| 台帳ID | 現在の分類 | 主な根拠 |
| --- | --- | --- |
| M2-C01／role-case-002 | TRAINING | 最初のcross-source構造fitと、後の同時killer/victim名前ROI調査 |
| M2-C02／compact-fit | TRAINING | compact separatorの実pixelを抽出。短いfit画像だけで新規死亡は証明しない |
| M2-C03／role-case-001 | TRAINING | 後に追加weapon referenceのfit元へ使用。最初のprospective表記を保持しても現在のholdoutではない |
| M2-C04／role-case-003 | EXPOSED_REGRESSION | 既存強いglyph・role試験と名前回帰の出力閲覧済み |
| M2-C05／transition-fit | TRAINING | 既存weapon reference拡張の開発context |
| M2-C06／panel-a | EXPOSED_REGRESSION | source reviewとnative replay済み |
| M2-C07／cross-context-a | EXPOSED_REGRESSION | native reader比較済み |
| M2-C08／reserved | EXPOSED_REGRESSION | 当初reservedだったが、その後source reviewと出力閲覧済み |
| M2-C09／shared-prospective | EXPOSED_REGRESSION | 当初prospectiveだったが、その後source reviewと出力閲覧済み |
| M2-C10／panel-b | EXPOSED_REGRESSION | source review、native replay、後のreference000静止画review済み |
| M2-C11／panel-c | EXPOSED_REGRESSION | source reviewとnative replay済み |
| M2-C12／next | EXPOSED_REGRESSION | source reviewとnative replay済み |
| M2-C13／role-case-005 | DEVELOPMENT | 認識前reviewは残存するが、後のweapon coverage／name修正の調査に使用 |
| M2-C14／cross-context-b | EXPOSED_REGRESSION | native replay・既知episode残存controlとして確認済み |
| M2-C15／marker-ability-fit | TRAINING | luminance marker／ability参照の開発画像を使用 |

role-case-004／006等のReport再表示、既知spectator／nonself／Self Killer controlは
`EXPOSED_REGRESSION`。別windowが同じ元Death／Reportを扱う場合、新しい独立episodeに増やさない。
孤立した192画像、NCC-positive選択31画像も回帰／component材料であり、時間的なDeath cohortではない。

match_002には全2,245 keyframeに対するcaption／NCC探索履歴があり、古いgeometry利用履歴は不明。
固定192画像のうち「既知episode記録なし」121件も未使用とは断定しない。
一方、componentの不変性と全modelの独立性は別に監査する。geometry履歴不明だけで、
確認できたmarker componentのfit分離まで自動的に否定することもしない。

`codex/round-boundary-requalification` の既存台帳は別の補助source 2本が対象で、
match_002の画像利用履歴を証明していない。台帳にないsource／episodeはまず
`UNKNOWN_EXPOSURE` とし、使用担当・fit／出力閲覧・splitを確認してから分類する。
追加動画の移行や新規撮影を一律の条件にはしない。

## 5. Phase C：Macへの最小引き渡し

ユーザー確認：**実行ホストはMac、Git経由で結果を受け渡し可能**。
原動画パスと利用可能なProfile／Assetは未確認。未評価episodeは「おそらくある」で、独立性未確認。
SSH等の接続先は提供されておらず、CodexからMacで実行した事実はない。

### C-1 場所と実行環境を確認する

Macの既存checkoutを上書きせず、以下を実行する。動画や検索結果をそのまま公開Gitへ追加しない。

```bash
git fetch origin
git status --short
git rev-parse HEAD origin/main origin/codex/self-death-positive-recognition
command -v python3 ffmpeg ffprobe tesseract
find "$HOME/Movies" "$HOME/Downloads" -type f \
  \( -iname '*.mp4' -o -iname '*.mkv' -o -iname '*.mov' \) -print 2>/dev/null
find outputs -type f \
  \( -iname '*profile*.json' -o -iname '*.npz' -o -iname '*owner*review*.json' \) \
  -print 2>/dev/null
```

既存checkoutが別branch／dirtyならそこでcheckout／resetせず、認識用の別worktreeを作る。
作成先が存在しないことを確認し、以後のPythonコマンドはそのworktreeで実行する。

```bash
git worktree add --detach ../s01-qualification-mac origin/codex/self-death-positive-recognition
cd ../s01-qualification-mac
git rev-parse HEAD
```

profileと動画は既存のprivate保存場所を絶対pathで参照し、新worktreeへ動画をcopyしない。
Gitに含まれないassetsが新worktreeへ現れないことは正常で、下記の所在確認が別途必要である。

戻す情報は、実行方法、原動画のlocal path、Profile／Asset／owner-reviewの所在、未評価episodeの候補だけ。
local pathはprivateな受け渡しでよく、公開Gitへ記載する必要はない。
AssetはこのGitに含まれない。Macで見つからない場合、探索手順だけで認識可能になったとは報告しない。
既存private profileを使えるか確認し、source SHA・寸法・校正が合わなければそこで止める。
新sourceへの校正が必要ならdevelopmentを先に分離し、holdoutを見て調整しない。

Macでは既存の依存環境を使う。必要なbinary／Python packageがなければ不足を記録する。
PiのOCR runtimeやLinux依存binaryをMacの依存と偽装しない。

### C-2 実行前に固定するもの

private `freeze.json` に、source SHA／size、Git SHAとdirty状態、runtime・reader code SHA、
profile／asset／owner-reviewのSHA、decoder／OCR binaryと関連dependency rootのSHA・version、
Python／OpenCV／NumPy／thread数、native time base／step ticks、各windowの有理数PTS範囲を保存する。
runnerの `dependencies_fingerprint` は実際のMac依存から認識前に生成され、終了時にも照合される。
Piと異なるfingerprintを既存certificateへ付け替えない。

さらに、物理episode ID、Exposure分類と根拠、positive／negative割当、review担当、成功／失敗／
中断条件、PNG上限を先に固定する。認識結果による区間選び直しをしない。
source-only reviewのファイルを先に保存してdigestを固定し、readerには渡さない。

source reviewは既存 `VideoService.native_window` が返す全native frameを対象とする。
単発画像や通常playerの表示時刻だけでnative onset bracketを記入しない。
既存decoderを再実装せず、review担当は同APIのcontext内でpixelを確認し、
`NativeSourceFrame` のPTS／time base／epoch／hashをannotationに転記する。
decoderの一時画像はcontext終了時に消えるため、reviewとbindingの保存を終えてから閉じる。
必要なsource-only抽出は認識前に行い、出力を見た後のreviewならその事実を明示する。

次は既存APIを使うsource-only review用の短い呼出例で、readerを起動しない。
`S01_REVIEW_WINDOW` は事前固定した1区間、`S01_REVIEW_BINDINGS` は新しいprivate JSONのpath、
`S01_SOURCE_SHA256` は事前計算した原動画のSHA。ほかの変数も下記runnerと同じものを用意する。
reviewerは表示された一時folder内の全frameをnative順で確認し、別のannotation JSONへ意味・
onset bracketを保存してからEnterを押す。Enterだけでは意味的資格を付与しない。
予算外へ画像をcopyせず、PNGが消えることを前提に元動画とhash bindingを保存する。

```bash
PYTHONPATH=.:src python3 - <<'PY'
import json
import os
from dataclasses import asdict
from pathlib import Path
from scripts.diagnostics.replay_self_death_images import parse_native_window
from valorant_ai_coach.video import VideoService

begin, end = parse_native_window(os.environ['S01_REVIEW_WINDOW'])
output = Path(os.environ['S01_REVIEW_BINDINGS'])
if output.exists():
    raise ValueError('preserve existing review bindings')
with VideoService().native_window(
    Path(os.environ['S01_SOURCE_VIDEO']), start_sec=float(begin), end_sec=float(end),
    source_video_sha256=os.environ['S01_SOURCE_SHA256'], png_prediction='up',
    max_png_bytes=int(os.environ['S01_PNG_CAP']),
) as frames:
    if not frames:
        raise ValueError('source-only review has no native frames')
    rows = []
    for frame in frames:
        frame.read_image()
        row = asdict(frame)
        row['path'] = str(frame.path)
        row['time_base'] = str(frame.time_base)
        rows.append(row)
    print('Private source-only review folder:', frames[0].path.parent)
    input('Save source-only annotations separately before pressing Enter: ')
with output.open('x', encoding='utf-8') as stream:
    json.dump({'kind': 'source_only_native_review_bindings_not_qualification',
               'source_terminal_verified': True, 'frames': rows}, stream, indent=2)
PY
```

これはsource-only reviewの取得範囲を記録する呼出で、bounded runnerと別のdecode epochを持つ。
後の認識出力との照合はsource SHA・元PTS／time base・pixel hashで行い、別epochを継ぎ合わせない。
decode境界付近のguard frameもreviewした場合はその範囲を明示する。厳密な認識入力選択は
既存bounded runnerの有理数PTS比較を使い、annotationの時刻を丸めない。

reviewには `self_relation`／`killer_role`／`victim_role`、Reportの
`absent_visible`／`present_same`／`occluded`／`reappeared`／`unknown`、
死亡前後のnative onset bracket、各属性の読取可否とROI、矛盾、reviewer／時刻を記録する。
これらはannotation例であり、production Schemaやqualification certificateではない。

### C-3 既存runnerを実行する

変数は確認済みのMac上の実在pathと、事前固定したwindowで設定する。以下を未設定のまま実行しない。
`S01_PNG_CAP` は最初に256 MiBとし、source-only reviewでも同じ上限を適用する。
native stepは元PTSで確認し、60fpsという表示だけから256等をコピーしない。

```bash
export PYTHONPATH=.:src
python3 -m scripts.diagnostics.replay_self_death_images --help
python3 -m scripts.diagnostics.replay_self_death_images \
  --source "$S01_SOURCE_VIDEO" --profile "$S01_FROZEN_PROFILE" \
  --owner-review "$S01_OWNER_REVIEW" \
  --tesseract "$S01_TESSERACT" --engine-binary "$S01_TESSERACT_ENGINE" \
  --tessdata "$S01_TESSDATA" --dependency-root "$S01_OCR_ROOT" \
  --native-step-ticks "$S01_NATIVE_STEP" \
  --bounded-native-window "$S01_POSITIVE_WINDOW" \
  --bounded-native-window "$S01_NEGATIVE_WINDOW" \
  --native-max-window-png-bytes "$S01_PNG_CAP" \
  --output "$S01_NEW_PRIVATE_RESULT" > "$S01_NEW_PRIVATE_LOG" 2>&1
```

全変数は実行shellへexportする。`S01_PNG_CAP=268435456` を設定し、output／logには未使用pathを使う。
source-only Python例にも同じexport済み変数を使う。既存logを上書きしないよう、必要なら
実行shellで `set -C` を先に設定する。

window引数はsource時刻順、互いに非接触・非重複とする。positiveが後なら引数も順に並べ替える。
source breakを跨ぐ連続証拠を作らず、各windowは独立context。必要な前履歴が収まらなければ
qualification未判定とする。`--native-window` は全動画decodeを先行する旧modeなので、ここでは選ばない。
Macではlauncherと実engineが同じ実行ファイルなら両引数へ同じpathを指定できる。
tessdataは実際の `eng.traineddata` を含む場所、dependency rootは使用したOCR関連依存を記録する。

一時PNGは既定256 MiB／window。上限超過、hash変更、PTS／decode異常、不正設定、必要証拠不足は
成功negativeに数えない。中断後にFPSを下げたりframeを捨てたりしない。
予算や区間の変更が必要なら元失敗を保持し、新しいfreezeとrun IDで明示する。
source-only reviewで画像を別保存する場合は、その保存容量も含めて予算化する。
動画本体は複製しない。長い実行は1回起動して終了まで待ち、成長中logを定期確認しない。

### C-4 戻す結果

詳細の生JSONはlocal path、OCRした名前、ROI等を含むためprivateのまま保持する。
Git経由では、明示的に選んだ集約項目だけを新しいbranchへcommitする。
`git add .`、動画・画像・GT・profile・assetsの公開は行わない。

戻す集約はsource／code／profile／asset／dependencyとfreeze／review／rawのdigest、episode別の
TP／FP／FN／Unknown、誤Self帰属、重複、source rejection、未判定件数、
native frame数、onset bracket／confirmationの妥当性、wall／RSS／一時保存量、exit status。
player名や私的なpathは含めない。reviewされていない区間のFPを0で埋めない。
候補が出なかっただけのsource errorをTNへ混ぜない。元結果と集約の対応はprivate receiptで保持する。

## 6. Phase D：判定を段階化する

| Level | 成立条件 | 現在の状態 |
| --- | --- | --- |
| 1 | 正しいsource frameとnative PTS／pixelを取得 | 既知Pi入力で成立。Mac未実行 |
| 2 | source reviewと照合した診断candidate | 既知Pi episodeで成立。Mac未実行 |
| 3 | 独立positive／negativeでSubject・victim・Report transition資格 | 未成立 |
| 4 | 現fingerprint、外部review、qualification loader等のrelease条件 | 未成立。Level 3前の有効化禁止 |
| 5 | 実資格Event→Package→Fact→Trace | 合成契約のみ。実動画未検証 |
| 6 | 同じCanonical evaluator／GTでassertion改善 | 未計測 |

countを満たしてpoint属性が不足する場合も段階を分ける。
正式なrelease可否はfreezeと独立reviewの妥当性を確認して判断し、JSONのhash一致だけでは決めない。
Level 3を満たすまでdefault callerを有効化しない。GT時刻やexpected属性をruntimeへ渡さない。

## 7. PR #53の変更分類と分離判断

| 分類 | 主な対象 | 統合条件 |
| --- | --- | --- |
| 安全な実装上の修正 | `killfeed_subject.py` の名前ROI分離、`facts/builder.py` の不完全なSelf Deathからelimination順を推論しないguard | qualificationを付与しない。親stackと実験readerへの依存、既存回帰を含めてreview |
| 実験的認識器 | `self_death_image.py`、`killfeed_subject.py`、`report_victim_episode.py`、`report_fatal_row.py` | 未資格・default無効を維持。診断candidateは正式Eventではない |
| qualification待ちの機能 | `numeric_subject_provider.py`、`numeric_death_session.py`、`numeric_death_release.py`、`qualified_death_attributes.py` | 独立reviewと正しいcertificateなしでは実releaseしない |
| 診断・検証ツール | bounded/cache replay、role evaluator、関連tests／reports | reader資格と別にorchestrationの正当性・資源上限をreview可能 |
| 未採用prototype | private weapon参照拡張・開発profile、過去の失敗変種 | Gitへ公開しない。既存qualified profileへの自動差替えをしない |

bounded replayは全体のDeath資格とは独立に、exact PTS選択・hash検証・資源制限として安全性を
reviewできる。ただし `ca4b975` をそのままmainやPR #52へcherry-pickできるとは判定しない。
**mainとPR #52には既存replay runnerも `SelfDeathImageRecognizer`／`KillfeedSubjectProfile` も存在しない。**
runnerとtestsはこれらへimport依存する。一方 `VideoService.native_window`／native decoder本体は
既にmainにあり、本PRとの差分がない。新しい汎用decoderを作る必要はない。

分離する場合は、まず実験reader＋共通診断runnerの最小依存範囲を独立reviewし、そのbase上へ
bounded runner／testsを小PRとして分ける案が妥当。現時点では提案に留め、既存PRをrewriteしたり、
他担当branchへcommitしたりしない。main単独適用可能なpatchと誤表示しない。

## 8. 次の担当と完了範囲

Codexだけで実施できる今回の残作業は、台帳の対応付け、資格条件・Mac引き渡し・stack依存の整理、
資料の整合性確認とPR更新である。新しい認識実験は追加しない。
外部入力が必要なのはMacのsource／private assets所在、未評価episodeの履歴確認、
source-only人間review、実行結果の返却。接続権限やpathを推測して実行しない。

次の採用判断は、固定modelと独立episodeの実資格が成立し、属性別の未知を保持しながら、
正式Eventと既存transportを実動画で検証し、targeted→sampledで同一条件のcanonical差分を測定した時点。
Fullはその条件と明確な新仮説が揃った後だけ実行する。

採用済み23/55/4、保存した未採用Strict 28/50/4、別時刻仕様30/49/3は分けて保持する。
現コードのcanonical targeted／sampled／Full、新規PASS／回帰FAIL、negative／discontinuity assertionの
変化は未計測。正式Deathは0。今回のhandoff完了をこれらの改善として報告しない。
