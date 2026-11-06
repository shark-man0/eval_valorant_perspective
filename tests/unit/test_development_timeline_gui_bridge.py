"""The desktop entry points only launch validated development viewer servers."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from valorant_ai_coach.settings import AppSettings, SettingsStore  # noqa: E402
from valorant_ai_coach.temporal import viewer  # noqa: E402
from valorant_ai_coach.ui.backend import BackendFacade  # noqa: E402
from valorant_ai_coach.ui.main_window import MainWindow  # noqa: E402


class MemoryCredentials:
    def get_password(self, _service: str, _username: str) -> None:
        return None

    def set_password(self, _service: str, _username: str, _password: str) -> None:
        return None


class FakeServer:
    viewer_url = "http://127.0.0.1:1234/local/"

    def __init__(self) -> None:
        self.shutdown_count = 0
        self.close_count = 0

    def serve_forever(self) -> None:
        return None

    def shutdown(self) -> None:
        self.shutdown_count += 1

    def server_close(self) -> None:
        self.close_count += 1


@pytest.mark.parametrize("comparison", [False, True])
def test_desktop_opens_development_viewer_and_closes_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, comparison: bool
) -> None:
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))
    server = FakeServer()
    selected = iter([("/private/manifest.json", ""), ("/private/policy.json", "")])
    calls: list[tuple[Path, ...]] = []
    urls: list[str] = []

    def factory(*paths: Path) -> FakeServer:
        calls.append(paths)
        return server

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: next(selected))
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: urls.append(url.toString()) or True
    )
    if comparison:
        monkeypatch.setitem(
            sys.modules,
            "valorant_ai_coach.temporal.comparison_viewer",
            SimpleNamespace(make_comparison_server=factory),
        )
    else:
        monkeypatch.setattr(viewer, "make_server", factory)

    try:
        if comparison:
            window._open_development_comparison()
            assert calls == [(Path("/private/manifest.json"),)]
        else:
            window._open_development_timeline()
            assert calls == [(Path("/private/manifest.json"), Path("/private/policy.json"))]
        assert urls == [server.viewer_url]
        assert server.close_count == 0
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    assert server.shutdown_count == 1
    assert server.close_count == 1


def test_desktop_comparison_uses_real_validated_catalog_factory(tmp_path, monkeypatch):
    from test_development_cross_match import comparison_fixture

    app = QApplication.instance() or QApplication([])
    manifest, _ = comparison_fixture(tmp_path)
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    window = MainWindow(BackendFacade(store))
    urls = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(manifest), ""))
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda u: urls.append(u.toString()) or True)
    try:
        window._open_development_comparison()
        assert len(urls) == 1 and urls[0].startswith("http://127.0.0.1:")
        with urlopen(urls[0] + "api/catalog") as response:
            catalog = json.load(response)
        assert catalog["physical_matches"] == 1
        assert catalog["primary_rows"] == 4
        assert catalog["formal_outputs"] == 0
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
