"""Result card rendering (needs PySide6; offscreen)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from valorant_ai_coach.ui.contracts import EvaluationView  # noqa: E402
from valorant_ai_coach.ui.main_window import MainWindow  # noqa: E402


def evaluation(label: str, evaluation_id: str, **overrides: object) -> EvaluationView:
    values: dict[str, object] = {
        "evaluation_id": evaluation_id,
        "label": label,
        "title": f"title-{evaluation_id}",
        "rule_id": "AIM-02",
        "related_rule_ids": (),
        "situation": "場面",
        "evidence": ("00:30  観測事実（hud）",),
        "missing_information": ("不足A",) if label == "unscored" else (),
        "reason": "理由",
        "improvement": "次回" if label == "improve" else None,
        "confidence": 0.9,
        "category": "Aim",
        "round_no": 1,
        "requires_round_context": False,
        "decision_source": "deterministic",
        "clip_path": None,
        "needs_review": False,
        "unscored_reason_code": "low_confidence" if label == "unscored" else None,
        "fact_refs": ("F010", "F011") if label != "unscored" else (),
        "time_range": (30.0, 31.5) if label != "unscored" else None,
    }
    values.update(overrides)
    return EvaluationView(**values)  # type: ignore[arg-type]


class Harness:
    """The real card-rendering methods of MainWindow, without building the whole window.

    MainWindow() creates a QAudioOutput, which aborts in containers with no audio server
    (and is irrelevant to card rendering). The filter combo boxes mirror MainWindow's.
    """

    _render_cards = MainWindow._render_cards
    _evaluation_card = MainWindow._evaluation_card

    def __init__(self) -> None:
        QApplication.instance() or QApplication([])
        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.addStretch()
        self.label_filter = QComboBox()
        for text, data in (
            ("評価（GOOD / 改善）", "scored"),
            ("GOOD", "good"),
            ("改善", "improve"),
            ("要確認（低信頼）", "review"),
            ("診断: UNSCORED", "unscored"),
            ("すべて", "all"),
        ):
            self.label_filter.addItem(text, data)
        self.category_filter = QComboBox()
        self.category_filter.addItem("すべてのカテゴリ", "all")
        self.round_filter = QComboBox()
        self.round_filter.addItem("すべてのラウンド", -1)
        self.current_evaluations: tuple[EvaluationView, ...] = (
            evaluation("good", "g1", clip_path="/clips/g1.mp4"),
            evaluation("improve", "i1"),
            evaluation("unscored", "u1"),
        )

    def _play_clip(self, _path: str) -> None:
        return None


@pytest.fixture
def window() -> Harness:
    return Harness()


def card_texts(main: Harness) -> list[str]:
    texts = []
    for index in range(main.cards_layout.count()):
        widget = main.cards_layout.itemAt(index).widget()
        if widget is not None and widget.objectName() == "evaluationCard":
            texts.append("\n".join(label.text() for label in widget.findChildren(QLabel)))
    return texts


def select_label(main: Harness, value: str) -> None:
    main.label_filter.setCurrentIndex(main.label_filter.findData(value))
    main._render_cards()


def test_default_view_shows_scored_cards_only(window: Harness) -> None:
    select_label(window, "scored")
    texts = card_texts(window)
    assert len(texts) == 2
    assert not any("UNSCORED" in text for text in texts)


def test_unscored_filter_shows_only_unscored_with_missing_information(window: Harness) -> None:
    select_label(window, "unscored")
    (text,) = card_texts(window)
    assert "UNSCORED" in text
    assert "不足A" in text
    assert "low_confidence" in text


def test_card_shows_time_range_facts_and_clip_status(window: Harness) -> None:
    select_label(window, "good")
    (text,) = card_texts(window)
    assert "該当時刻: 00:30–00:32（30.0–31.5秒）" in text
    assert "使用したfact: F010, F011" in text
    assert "クリップあり" in text
    select_label(window, "improve")
    (text,) = card_texts(window)
    assert "クリップなし" in text


def test_clip_button_exists_only_when_a_clip_is_stored(window: Harness) -> None:
    def buttons(label: str) -> int:
        select_label(window, label)
        widget = window.cards_layout.itemAt(0).widget()
        return len(widget.findChildren(QPushButton)) if widget is not None else -1

    assert buttons("good") == 1
    assert buttons("improve") == 0
    assert buttons("unscored") == 0


def test_no_match_shows_the_empty_message(window: Harness) -> None:
    window.category_filter.addItem("Other", "Other")
    window.category_filter.setCurrentIndex(window.category_filter.findData("Other"))
    window._render_cards()
    assert card_texts(window) == []
    first = window.cards_layout.itemAt(0).widget()
    assert isinstance(first, QLabel)
    assert "一致する評価はありません" in first.text()
