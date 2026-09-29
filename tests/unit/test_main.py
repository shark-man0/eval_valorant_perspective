from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from valorant_ai_coach import main as app_main  # noqa: E402


class FakeApplication:
    def __init__(self, arguments: list[str]) -> None:
        self.arguments = arguments
        self.processed = False

    def setApplicationName(self, _name: str) -> None:  # noqa: N802 - Qt-compatible fake
        return None

    def setOrganizationName(self, _name: str) -> None:  # noqa: N802 - Qt-compatible fake
        return None

    def processEvents(self) -> None:  # noqa: N802 - Qt-compatible fake
        self.processed = True

    def exec(self) -> int:
        raise AssertionError("smoke test must not enter the GUI event loop")


def test_smoke_flag_builds_and_closes_window_without_event_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    application: FakeApplication | None = None
    window_closed = False

    def build_application(arguments: list[str]) -> FakeApplication:
        nonlocal application
        application = FakeApplication(arguments)
        return application

    class FakeStore:
        def __init__(self, _path: object) -> None:
            pass

        @staticmethod
        def load() -> object:
            return type(
                "Settings",
                (),
                {"data_dir": tmp_path, "debug_logging": False},
            )()

    class FakeWindow:
        def __init__(self, _backend: object) -> None:
            pass

        def close(self) -> None:
            nonlocal window_closed
            window_closed = True

    monkeypatch.setattr(app_main, "QApplication", build_application)
    monkeypatch.setattr(app_main, "SettingsStore", FakeStore)
    monkeypatch.setattr(app_main, "BackendFacade", lambda _store: object())
    monkeypatch.setattr(app_main, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_main, "configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_main, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr(app_main.sys, "argv", ["valorant-ai-coach", "--smoke-test"])

    assert app_main.main() == 0
    assert application is not None
    assert application.arguments == ["valorant-ai-coach"]
    assert application.processed is True
    assert window_closed is True
