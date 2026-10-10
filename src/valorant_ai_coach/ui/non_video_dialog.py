"""Windows desktop UI for stored-result features; no video decoding or paid API calls."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from valorant_ai_coach.non_video.features import _atomic_write
from valorant_ai_coach.observability.sanitize import sanitize_text


class NonVideoDialog(QDialog):
    def __init__(self, backend: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.backend = backend
        self.setWindowTitle("履歴・統計・レポート・設定ツール")
        self.setMinimumSize(850, 640)
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.rules = backend.services.rules_by_id
        self.matches = backend.list_matches()
        self._history_tab()
        self._statistics_tab()
        self._report_tab()
        self._profiles_tab()
        self._usage_tab()

    def _execute(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:
            QMessageBox.warning(self, "操作を完了できません", sanitize_text(str(exc)))

    def _select_match(self) -> QComboBox:
        combo = QComboBox()
        for item in self.matches:
            combo.addItem(str(item["match_id"]), str(item["match_id"]))
        return combo

    def _rule_selector(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem("全ルール", "")
        for rule in sorted(self.rules):
            combo.addItem(rule, rule)
        return combo

    def _category_selector(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem("全カテゴリ", "")
        for category in sorted({
            str(r.get("category", "Other")) for r in self.rules.values()
        }):
            combo.addItem(category, category)
        return combo

    def _category_rules(self, selected: str) -> tuple[str, ...]:
        return tuple(sorted(
            rule_id for rule_id, info in self.rules.items()
            if info.get("category", "Other") == selected
        )) if selected else ()

    @staticmethod
    def _grid(columns: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(list(columns))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    @staticmethod
    def _fill(table: QTableWidget, records: list[tuple[Any, ...]]) -> None:
        table.setRowCount(len(records))
        for i, record in enumerate(records):
            for j, value in enumerate(record):
                item = QTableWidgetItem("" if value is None else str(value))
                table.setItem(i, j, item)

    def _history_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        form = QFormLayout()
        self.query_match = QLineEdit()
        self.query_match.setPlaceholderText("Match ID（完全一致）")
        self.query_rule = self._rule_selector()
        self.query_category = self._category_selector()
        self.query_label = QComboBox()
        for title, value in (("すべて", ""), ("GOOD", "good"),
                             ("IMPROVE", "improve"), ("UNSCORED", "unscored")):
            self.query_label.addItem(title, value)
        self.query_word = QLineEdit()
        self.query_word.setPlaceholderText("理由・改善提案などのキーワード")
        self.query_start = QLineEdit()
        self.query_start.setPlaceholderText("開始日 YYYY-MM-DD")
        self.query_end = QLineEdit()
        self.query_end.setPlaceholderText("終了日 YYYY-MM-DD（当日を含む）")
        for text, widget in (
            ("Match", self.query_match), ("Rule", self.query_rule),
            ("Category", self.query_category), ("Label", self.query_label),
            ("キーワード", self.query_word), ("開始日", self.query_start),
            ("終了日", self.query_end),
        ):
            form.addRow(text, widget)
        root.addLayout(form)
        controls = QHBoxLayout()
        self.query_page = QSpinBox()
        self.query_page.setMinimum(1)
        self.query_page.setMaximum(100000)
        search = QPushButton("検索")
        search.clicked.connect(lambda: self._execute(self._search))
        controls.addWidget(QLabel("ページ（50件/ページ）"))
        controls.addWidget(self.query_page)
        controls.addWidget(search)
        controls.addStretch()
        root.addLayout(controls)
        self.query_table = self._grid(("日時", "Match", "Round", "Rule", "Label", "理由"))
        root.addWidget(self.query_table, 1)
        compare_row = QHBoxLayout()
        self.compare_left = self._select_match()
        self.compare_right = self._select_match()
        if self.compare_right.count() > 1:
            self.compare_right.setCurrentIndex(1)
        compare_button = QPushButton("2試合を比較")
        compare_button.clicked.connect(lambda: self._execute(self._compare))
        for compare_widget in (self.compare_left, self.compare_right, compare_button):
            compare_row.addWidget(compare_widget)
        root.addLayout(compare_row)
        self.compare_text = QPlainTextEdit()
        self.compare_text.setReadOnly(True)
        self.compare_text.setMaximumHeight(115)
        root.addWidget(self.compare_text)
        self.tabs.addTab(page, "検索・比較")
        self._execute(self._search)

    @staticmethod
    def _end_exclusive(text: str) -> str:
        if not text:
            return ""
        from datetime import timedelta
        return (datetime.strptime(text, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    def _search(self) -> None:
        rows = self.backend.search_evaluations(
            match_id=self.query_match.text().strip(),
            rule=str(self.query_rule.currentData()),
            category_rules=self._category_rules(str(self.query_category.currentData())),
            label=str(self.query_label.currentData()),
            keyword=self.query_word.text(),
            start=self.query_start.text().strip(),
            end=self._end_exclusive(self.query_end.text().strip()),
            limit=50,
            offset=(self.query_page.value() - 1) * 50,
        )
        self._fill(self.query_table, [
            (item["created_at"], item["match_id"], item["round_no"],
             item["primary_rule_id"], item["label"], item["payload"].get("reason", "")[:120])
            for item in rows
        ])

    def _compare(self) -> None:
        first, second = str(self.compare_left.currentData()), str(self.compare_right.currentData())
        result = self.backend.compare_matches(first, second)
        lines = []
        for match_id, info in result.items():
            categories: dict[str, int] = {}
            for rule, count in info["by_rule"].items():
                category = str(self.rules.get(rule, {}).get("category", "Other"))
                categories[category] = categories.get(category, 0) + count
            lines.append(
                f"{match_id} [{info['status']}]: GOOD {info['counts']['good']} / "
                f"IMPROVE {info['counts']['improve']} / UNSCORED {info['counts']['unscored']}"
                f" / カテゴリ {categories} / Rule {info['by_rule']}"
            )
        lines.append("※ 観測量・不完全Matchの差を考慮。総合的な優劣は判定しません。")
        self.compare_text.setPlainText("\n".join(lines))

    def _statistics_tab(self) -> None:
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        form = QHBoxLayout()
        self.stat_start = QLineEdit()
        self.stat_start.setPlaceholderText("開始日 YYYY-MM-DD")
        self.stat_end = QLineEdit()
        self.stat_end.setPlaceholderText("終了日 YYYY-MM-DD")
        self.stat_category = self._category_selector()
        self.stat_rule = self._rule_selector()
        button = QPushButton("統計更新")
        button.clicked.connect(lambda: self._execute(self._refresh_stats))
        for w in (self.stat_start, self.stat_end, self.stat_category, self.stat_rule, button):
            form.addWidget(w)
        root.addLayout(form)
        self.stat_summary = QLabel()
        self.stat_summary.setWordWrap(True)
        root.addWidget(self.stat_summary)
        root.addWidget(QLabel("評価ラベル別分布"))
        self.stat_bars = QVBoxLayout()
        root.addLayout(self.stat_bars)
        root.addWidget(QLabel("カテゴリ別評価件数（上位8件）"))
        self.stat_category_bars = QVBoxLayout()
        root.addLayout(self.stat_category_bars)
        root.addWidget(QLabel("日付別評価件数（直近14日分の観測日）"))
        self.stat_day_bars = QVBoxLayout()
        root.addLayout(self.stat_day_bars)
        root.addWidget(QLabel("頻出する改善ルール（上位8件）"))
        self.stat_improve_bars = QVBoxLayout()
        root.addLayout(self.stat_improve_bars)
        root.addWidget(QLabel("カテゴリ・ルール・日付の全件表"))
        self.stat_category_table = self._grid(("カテゴリ", "評価件数"))
        root.addWidget(self.stat_category_table)
        self.stat_table = self._grid(("ルール", "件数", "カテゴリ"))
        root.addWidget(self.stat_table)
        self.stat_timeline = self._grid(("日付", "評価件数"))
        root.addWidget(self.stat_timeline)
        root.addWidget(QLabel(
            "GOOD率 = GOOD / (GOOD + IMPROVE)。スキルの絶対評価ではありません。"
        ))
        self.tabs.addTab(page, "統計")
        self._execute(self._refresh_stats)

    @staticmethod
    def _render_chart(layout: QVBoxLayout, entries: list[tuple[str, int]]) -> None:
        while layout.count():
            entry = layout.takeAt(0)
            old_widget = entry.widget() if entry is not None else None
            if old_widget is not None:
                old_widget.deleteLater()
        if not entries:
            layout.addWidget(QLabel("該当データなし"))
            return
        maximum = max(1, *(count for _, count in entries))
        for name, count in entries:
            bar = QProgressBar()
            bar.setRange(0, maximum)
            bar.setValue(count)
            bar.setFormat(f"{name}: {count}")
            bar.setTextVisible(True)
            layout.addWidget(bar)

    def _refresh_stats(self) -> None:
        stats = self.backend.get_statistics(
            start=self.stat_start.text().strip(),
            end=self._end_exclusive(self.stat_end.text().strip()),
            rule=str(self.stat_rule.currentData()),
            category_rules=self._category_rules(str(self.stat_category.currentData())),
        )
        counts = stats["counts"]
        share = stats["good_share_of_scored"]
        self.stat_summary.setText(
            f"Match {stats['match_count']}件 / 評価可能 {stats['evaluable_match_count']}件 "
            f"/ 不完全 {stats['incomplete_match_count']}件 "
            f"/ 評価0件Match {stats['matches_without_evaluations']}件\n"
            f"GOOD {counts['good']} / IMPROVE {counts['improve']} / "
            f"UNSCORED {counts['unscored']} / 採点済みGOOD割合 "
            f"{share:.1%}" if share is not None else
            f"Match {stats['match_count']}件 / GOOD {counts['good']} / "
            f"IMPROVE {counts['improve']} / UNSCORED {counts['unscored']} "
            "/ 採点済みGOOD割合: 分母なし"
        )
        self._render_chart(
            self.stat_bars,
            [(label.upper(), counts[label]) for label in ("good", "improve", "unscored")],
        )
        by_rule = stats["by_rule"]
        categories: dict[str, int] = {}
        for rule, count in by_rule.items():
            category = str(self.rules.get(rule, {}).get("category", "Other"))
            categories[category] = categories.get(category, 0) + count
        category_items = sorted(categories.items(), key=lambda item: (-item[1], item[0]))
        self._fill(self.stat_category_table, category_items)
        self._render_chart(self.stat_category_bars, category_items[:8])
        self._fill(self.stat_table, [
            (rule, count, self.rules.get(rule, {}).get("category", "Other"))
            for rule, count in sorted(by_rule.items(), key=lambda it: (-it[1], it[0]))
        ])
        day_items = list(stats["by_day"].items())
        self._fill(self.stat_timeline, day_items)
        self._render_chart(self.stat_day_bars, day_items[-14:])
        frequent = stats["by_improve_rule"]
        frequent_items = sorted(frequent.items(), key=lambda item: (-item[1], item[0]))
        self._render_chart(self.stat_improve_bars, frequent_items[:8])
        if frequent:
            self.stat_summary.setText(
                self.stat_summary.text() + "\n頻出改善ルール: " +
                ", ".join(f"{rule}={count}" for rule, count in
                          sorted(frequent.items(), key=lambda item: (-item[1], item[0]))[:5])
            )

    def _report_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.export_match = self._select_match()
        self.export_format = QComboBox()
        for fmt in ("html", "csv", "json"):
            self.export_format.addItem(fmt.upper(), fmt)
        button = QPushButton("保存先を選んでエクスポート")
        button.clicked.connect(lambda: self._execute(self._export))
        form.addRow("Match", self.export_match)
        form.addRow("形式", self.export_format)
        form.addRow(button)
        form.addRow(QLabel(
            "元動画・画像・APIキーは含めません。絶対パスは伏せ、CSV式を無害化します。"
        ))
        self.tabs.addTab(page, "レポート出力")

    def _export(self) -> None:
        match = self.export_match.currentData()
        if not match:
            raise ValueError("Matchがありません")
        fmt = str(self.export_format.currentData())
        path, _ = QFileDialog.getSaveFileName(
            self, "評価レポートを保存", f"valorant-report.{fmt}",
            f"{fmt.upper()} (*.{fmt})"
        )
        if path:
            self.backend.export_report(str(match), Path(path), fmt)
            QMessageBox.information(self, "保存完了", "レポートを保存しました。")

    def _profiles_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.profile_names = QComboBox()
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("新しい名前")
        root.addWidget(self.profile_names)
        root.addWidget(self.profile_name)
        actions = (
            ("現在の設定を保存", self._profile_create),
            ("選択した設定を適用", self._profile_activate),
            ("名前を変更", self._profile_rename),
            ("選択を削除", self._profile_delete),
            ("初期設定に戻す", self._profile_reset),
            ("JSONに出力", self._profile_export),
            ("JSONから読込", self._profile_import),
        )
        for title, method in actions:
            button = QPushButton(title)
            button.clicked.connect(lambda _checked=False, fn=method: self._execute(fn))
            root.addWidget(button)
        root.addWidget(QLabel(
            "APIキー・資格情報・データ保存先はプロファイルに含みません。"
            "切替・初期化でもMatch履歴は消しません。"
        ))
        root.addStretch()
        self.tabs.addTab(page, "設定プロファイル")
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        self.profile_names.clear()
        for name in self.backend.profiles.list_names():
            self.profile_names.addItem(name, name)

    def _selected_profile(self) -> str:
        value = self.profile_names.currentData()
        if not value:
            raise ValueError("プロファイルを選択してください")
        return str(value)

    def _profile_create(self) -> None:
        self.backend.profiles.create(self.profile_name.text())
        self._refresh_profiles()

    def _profile_activate(self) -> None:
        self.backend.profiles.activate(self._selected_profile(), self.backend)
        QMessageBox.information(self, "適用しました", "設定プロファイルを適用しました。")

    def _profile_rename(self) -> None:
        self.backend.profiles.rename(self._selected_profile(), self.profile_name.text())
        self._refresh_profiles()

    def _profile_delete(self) -> None:
        self.backend.profiles.delete(self._selected_profile())
        self._refresh_profiles()

    def _profile_reset(self) -> None:
        self.backend.profiles.reset_settings(self.backend)
        QMessageBox.information(self, "初期化しました", "履歴を保持したまま設定を初期化しました。")

    def _profile_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "プロファイルを書き出し", "profile.json", "JSON (*.json)"
        )
        if path:
            self.backend.profiles.export_file(self._selected_profile(), Path(path))

    def _profile_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "プロファイルを読込", "", "JSON (*.json)")
        if path:
            self.backend.profiles.import_file(Path(path), self.profile_name.text())
            self._refresh_profiles()

    def _usage_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.usage_summary = QLabel()
        root.addWidget(self.usage_summary)
        self.usage_table = self._grid(
            ("日時", "機能", "モデル", "状態", "Input", "Output", "Total", "Cache", "推定料金")
        )
        root.addWidget(self.usage_table)
        self.price_path = self.backend.settings_store.path.parent / "api_prices.json"
        self.price_editor = QPlainTextEdit()
        self.price_editor.setMaximumHeight(130)
        self.price_editor.setPlaceholderText(
            '{"prices":{"model-id":{"input_per_million":0,"output_per_million":0,'
            '"currency":"USD"}},"monthly_budget":null}'
        )
        self.price_editor.setPlainText(
            self.price_path.read_text(encoding="utf-8") if self.price_path.exists()
            else '{"prices": {}, "monthly_budget": null}'
        )
        root.addWidget(QLabel("モデル別単価（100万tokenあたり、手動設定）と月間予算目安"))
        root.addWidget(self.price_editor)
        actions = QHBoxLayout()
        save = QPushButton("単価設定を保存")
        save.clicked.connect(lambda: self._execute(self._save_prices))
        refresh = QPushButton("使用量を更新")
        refresh.clicked.connect(lambda: self._execute(self._refresh_usage))
        actions.addWidget(save)
        actions.addWidget(refresh)
        root.addLayout(actions)
        root.addWidget(QLabel(
            "請求額ではなく概算です。usage欠損・通信失敗・価格未設定は不明。"
            "強制停止や自動課金の制御は行いません。"
        ))
        self.tabs.addTab(page, "API使用量・費用")
        self._execute(self._refresh_usage)

    def _parsed_prices(self) -> dict[str, Any]:
        data = json.loads(self.price_editor.toPlainText())
        if not isinstance(data, dict) or not isinstance(data.get("prices"), dict):
            raise ValueError("pricesはJSON objectで指定してください")
        for model, price in data["prices"].items():
            if not isinstance(model, str) or not isinstance(price, dict):
                raise ValueError("モデル別単価の形式が不正です")
            for key in ("input_per_million", "output_per_million"):
                value = price.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("単価は0以上の有限な数値で指定してください")
                if not math.isfinite(float(value)) or not 0 <= float(value) < 1e9:
                    raise ValueError("単価は0以上の有限な数値で指定してください")
            if not isinstance(price.get("currency"), str) or not price["currency"].strip():
                raise ValueError("通貨を指定してください")
        budget = data.get("monthly_budget")
        if budget is not None and (
            isinstance(budget, bool)
            or not isinstance(budget, (int, float))
            or not 0 <= float(budget) < 1e9
        ):
            raise ValueError("月間予算は0以上またはnullで指定してください")
        return data

    def _save_prices(self) -> None:
        values = self._parsed_prices()
        values["configured_at_utc"] = datetime.now(UTC).isoformat()
        _atomic_write(self.price_path, json.dumps(
            values, ensure_ascii=False, indent=2
        ) + "\n")
        self._refresh_usage()

    def _refresh_usage(self) -> None:
        prices = self._parsed_prices()
        events = self.backend.get_api_usage(prices["prices"])
        self._fill(self.usage_table, [
            (x["recorded_at"], x["feature"], x["model"], x["status"],
             x["input_tokens"] if x["input_tokens"] is not None else "不明",
             x["output_tokens"] if x["output_tokens"] is not None else "不明",
             x["total_tokens"] if x["total_tokens"] is not None else "不明",
             "HIT" if x["cache_hit"] else "-",
             f"{x['estimated_cost']:.6f} {x.get('currency', '')}"
             if x["estimated_cost"] is not None else "不明")
            for x in events[:250]
        ])
        now_month = datetime.now(UTC).strftime("%Y-%m")
        current = [x for x in events if x["recorded_at"].startswith(now_month)]
        amounts = [x["estimated_cost"] for x in current]
        known = [v for v in amounts if v is not None]
        budget = prices.get("monthly_budget")
        totals: dict[str, float] = {}
        for item in current:
            if item["estimated_cost"] is not None:
                currency = str(item.get("currency", ""))
                totals[currency] = totals.get(currency, 0.0) + float(item["estimated_cost"])
        one_currency = len(totals) == 1
        exceeds = one_currency and budget is not None and (
            next(iter(totals.values())) >= budget
        )
        total_text = ", ".join(
            f"{amount:.6f} {currency}" for currency, amount in sorted(totals.items())
        ) or "不明"
        self.usage_summary.setText(
            f"当月記録（直近2000件中）: {len(current)}件 / "
            f"推定額が計算可能: {len(known)}件"
            f" / 合計（通貨別・既知分のみ） {total_text}"
            + (" / 予算目安へ到達（参考警告）" if exceeds else "")
        )
