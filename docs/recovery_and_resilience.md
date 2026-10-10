# 非動画領域の復旧・耐障害性

## 対象・既存機能

既存`SQLiteRepository`はWAL・外部キー・transaction・busy timeout 15秒・atomic schema migrationを備える。既存`SettingsStore.save`はfsync後に`os.replace`する。これらを再実装せず利用。

## 追加した対策

`evaluation_feedback`と`api_usage_events`をSQLiteの独立migrationとtransactionで作成。feedbackは既存評価へ外部キー参照し、Match削除時にはcascade。評価payloadを更新しない。レポート・プロファイル・単価設定は同じディレクトリ内の一時ファイルへの書込/fsync/原子的置換。GUIで保存・読取例外を表示し、失敗時に完了扱いにしない。

## 検証

I/O Error、PermissionError、破損JSON、未知評価ID、再起動相当の再初期化、外部キー整合性、元評価不変を`test_non_video_features.py`で再現。既存分析jobの中断・再開契約は変更していない。実動画へのアクセス、API再送、DB再生成・全削除を行わない。

## 既知の限界

ディスク物理破損・OS停止・電源断を完全に復旧するものではない。外部コピーとの同時変更や、他プロセスによる長時間SQLiteロックの自動解決は保証しない。バックアップ運用は引き続き必要。