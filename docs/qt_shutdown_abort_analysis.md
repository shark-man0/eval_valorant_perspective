# Qt終了時abort（Linux CI）の原因分析と修正

対象: 全テスト成功後に発生していたLinux上のプロセスabort（exit code 134）。
開始時のmain: `c11ec6d333957cccb270417bc95a8a57f433e6ad`（PR #15マージ後）。

## 1. 結論

`MainWindow`を**明示的に破棄しないまま**インタプリタが終了処理に入ると、PySide6のfinalize（`destroyQCoreApplication`）が
C++側のツリーを破棄する際にヒープを破壊し、`malloc_consolidate(): unaligned fastbin chunk detected`でabortする
（サンドボックスではSIGSEGVになることもある）。

`MainWindow`は`lambda`でselfを捕捉するシグナル接続を多数持ち、これらのクロージャが参照を保持するため、
最後のローカル変数が消えても参照カウントが0にならない（診断: `refcount=5`、`del`と`gc.collect()`後も生存）。
そのため、明示的に破棄しない限り終了処理まで生き残る。

発生源は2系統あった。

| 系統 | 内容 |
|---|---|
| テスト | `tests/unit/test_ui_smoke.py::test_close_waits_until_analysis_worker_has_stopped`だけが、他の全GUIテストが呼ぶ`_destroy_widget`を呼ばずに`MainWindow`を残していた |
| 実アプリ | `valorant_ai_coach.main.main()`が`MainWindow`を破棄せずに戻っていた（`--smoke-test`と、`app.exec()`終了後の通常終了の両方） |

## 2. 再現条件と切り分け

固定条件: Python 3.12.3 / PySide6 6.12.0 / `QT_QPA_PLATFORM=offscreen` / 各試行は独立したプロセス。
サンドボックスにはPipeWireが無く、`QAudioOutput`生成で別件のsegfaultが出るため、診断では
`PIPEWIRE_CONFIG_DIR`と`XDG_RUNTIME_DIR`をスクラッチに向けて回避した（リポジトリの変更ではない）。

| 条件 | 試行 | 正常終了 | abort(134) | segv(139) |
|---|---|---|---|---|
| QApplication生成・終了のみ | 100 | 100 | 0 | 0 |
| 親なしのQAudioOutputを明示破棄せず終了 | 100 | 100 | 0 | 0 |
| QWidget親のQAudioOutput+QMediaPlayerを明示破棄（1試行内で3回繰り返し） | 100 | 100 | 0 | 0 |
| MainWindow生成・明示破棄（1試行内で3回繰り返し） | 100 | 100 | 0 | 0 |
| SettingsDialog生成・明示破棄（1試行内で3回繰り返し） | 100 | 100 | 0 | 0 |
| `test_ui_smoke.py`の1〜8番 | 60 | 60 | 0 | 0 |
| `test_ui_smoke.py`の9〜17番 | 60 | 51 | 9 | 0 |
| 9〜12番 | 60 | 18 | 5 | 37 |
| 13〜17番 | 60 | 60 | 0 | 0 |
| 12番のみ | 60 | 14 | 3 | 43 |
| `test_ui_smoke.py`全体 | 150 | 125 | 25 | 0 |
| `test_ui_smoke.py`全体から12番を除外（診断のみ） | 150 | 150 | 0 | 0 |
| 最小再現: MainWindowを関数内で作り放置（`exp2 fn_release`） | 40 | 19 | 21 | 0 |
| 同上、モジュール変数に保持（`exp2 global_keep`） | 40 | 40 | 0 | 0 |
| 実エントリポイント`main --smoke-test` | 40 | 5 | 2 | 33 |
| 実`main()`（`app.exec()`を即時復帰に差し替え） | 40 | 25 | 1 | 14 |

QApplication単体、QAudioOutput/QMediaPlayer、SettingsDialogは、この条件では原因ではなかった。
`MainWindow`もそれ自体は明示破棄すれば100試行で発生しない。QVideoWidgetは単独の最小実験を行っておらず、
`MainWindow`の一部として上記の結果に含まれる。

## 3. 直接原因と根拠

- gdb（`exp2 fn_release`）: `[diag] ATEXIT handler running` → `MainWindow C++ DESTROYED` → `QAudioOutput DESTROYED` →
  `QMediaPlayer DESTROYED`の直後に`malloc_consolidate(): unaligned fastbin chunk detected`でSIGABRT。
  バックトレースは`~QStatusBar` → `~QWidget` → `QObject::destroyed` → `free`、さらに上位は
  `libpyside6`の`destroyQCoreApplication`と`libshiboken6`のバインディング走査。
- valgrind（同条件）: 解放済み領域への`Invalid write of size 8`が`QObject::~QObject()`で発生。呼び出し元は
  `Shiboken::BindingManager::visitAllPyObjects` → `PySide::destroyQCoreApplication`。
  つまりインタプリタ終了処理中にwrapperを走査しながらC++ツリーを破棄していて、解放済みメモリを触っている。
- 破棄順序: `QApplication`が生きている間に破棄されるべき`MainWindow`ツリーが、終了処理で初めて破棄される。
  明示破棄（`deleteLater()`+`DeferredDelete`送出）では発生しない。

### 未解明の点（断定しない）

- 同じ「終了処理中に破棄される」条件でも、モジュール変数が`MainWindow`を直接保持する場合は40試行で発生せず（`global_keep` 0/40）、
  クロージャだけが保持する場合は発生した（21/40）。finalizeの走査順がこの差を生むと考えているが、
  Shiboken側の走査順そのものは確認していない。この点は原因の記述に含めていない。
- CIの実ログにあった`QObject: shared QObject was deleted directly.`は、ローカルの1,000回超の試行では一度も出ていない
  （`malloc_consolidate`のabortのみ）。同じ「二重破棄/解放済み領域の再利用」の症状と考えられるが、ローカルでは再現できていない。
  CIのログ本体はダウンロードできず（403）、ユーザー提供の抜粋でのみ確認している。

## 4. 修正

| ファイル | 内容 |
|---|---|
| `src/valorant_ai_coach/ui/lifecycle.py`（新規） | `release_qobject_tree()`: `deleteLater()`→`DeferredDelete`を明示送出→`processEvents()`。`QApplication`が生きている間に破棄する |
| `src/valorant_ai_coach/main.py` | `main()`の全経路（`--smoke-test`・通常終了・起動失敗）で`finally`内に`release_qobject_tree(window)`。`exec()`の位置と起動失敗時の挙動は従来どおり |
| `tests/unit/test_ui_smoke.py` | 12番のテスト末尾に、他の全テストと同じ`_destroy_widget(window, app)`を追加（1行） |
| `tests/conftest.py` | リーク検出: 成功したテストがトップレベルのQtウィジェットを残した場合、そのテストをteardownで失敗させる（残ったものは破棄する） |
| `tests/unit/test_main.py` | `--smoke-test`で`window.deleteLater()`が呼ばれることを検証 |
| `tests/unit/test_qt_shutdown_lifecycle.py`（新規） | 下記の回帰テスト |

`os._exit`、sleep、グローバルGC、skip、終了コード判定の緩和は使っていない。GUI機能は変更していない
（破棄のタイミングのみ。`closeEvent`・ワーカー管理・メディア再生の処理は変更なし）。

## 5. 回帰テスト（修正前に失敗することを確認）

`tests/unit/test_qt_shutdown_lifecycle.py`（22件）:

- 進行中: QApplication生成・終了、MainWindow生成・破棄、SettingsDialog生成・破棄、QMediaPlayer/QAudioOutputの停止と解放、
  親子関係、実行中ワーカーのキャンセルとウィンドウ終了、ワーカー完了後のウィンドウ破棄
- プロセスレベル（子プロセスの**実際の終了コード**を検証）: 実`main --smoke-test`を独立プロセスで8回、
  5種類の最小シナリオ、GUIテスト連続実行のpytestプロセス3回

修正前に失敗する証拠:

- `main.py`だけ修正前に戻すと、`test_application_entry_point_exits_with_code_zero`（8パラメータ）が3回の実行でそれぞれ
  5/8、7/8、8/8失敗した（計20/24）。内訳はSegmentation fault 19回・Aborted 1回。
  確認後、`main.py`は修正版に戻してある。
- 修正前の`test_ui_smoke.py`をそのまま流すと、リーク検出が12番で`MainWindow`の生存を毎回検出して失敗する（3/3）。

## 6. 修正前後の比較

| 指標 | 修正前 | 修正後 |
|---|---|---|
| `test_ui_smoke.py`全体 150回: 正常終了 / abort | 125 / 25 | 150 / 0 |
| 12番のみ 60回: 正常終了 / abort / segv | 14 / 3 / 43 | 60 / 0 / 0 |
| 9〜12番 60回: 正常終了 / abort / segv | 18 / 5 / 37 | 60 / 0 / 0 |
| 実`main --smoke-test` 40回: 正常終了 / 異常終了 | 5 / 35 | 40 / 0 |
| 実`main()`（exec即時復帰） 40回: 正常終了 / 異常終了 | 25 / 15 | 40 / 0 |
| Qt関連テストPASS/FAIL | 17 passed（終了時に異常終了あり） | 17 passed |
| `QObject: shared QObject was deleted`の出力 | 0（ローカルでは未再現） | 0 |
| 全pytest（Linux、ローカル） | — | 3651 passed / 9 skipped、exit 0、coverage 86.55% |

0回は「発生しない」ことを意味しない。上記の試行回数の範囲で観測されなかった、という意味である。
CIの発生率は低く（数回に1回未満）、少数回のCI成功では修正の十分な証拠にならない。
