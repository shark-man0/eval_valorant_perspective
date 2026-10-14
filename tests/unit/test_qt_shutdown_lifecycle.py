"""Regression tests for the intermittent Qt abort that happened *after* all tests passed.

Root cause: ``MainWindow`` is kept alive by signal closures that capture ``self``, so it is
not freed when its last local name goes away.  When it was still alive at interpreter
shutdown, PySide6 deleted the C++ tree while visiting the child wrappers (use-after-free,
seen as ``malloc_consolidate(): unaligned fastbin chunk detected`` / ``double free`` /
SIGSEGV, exit code 134 or 139).  Owners must delete the tree while the ``QApplication`` is
alive; ``valorant_ai_coach.ui.lifecycle.release_qobject_tree`` does that.

The abort is probabilistic, so the process-level tests below run several independent
interpreters and assert the real exit code, not just pytest assertions.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from valorant_ai_coach.settings import AppSettings, SettingsStore  # noqa: E402
from valorant_ai_coach.ui.backend import BackendFacade  # noqa: E402
from valorant_ai_coach.ui.lifecycle import release_qobject_tree  # noqa: E402
from valorant_ai_coach.ui.main_window import MainWindow  # noqa: E402
from valorant_ai_coach.ui.settings_dialog import SettingsDialog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESS_TIMEOUT_SECONDS = 180


class MemoryCredentials:
    def get_password(self, _service: str, _username: str) -> str | None:
        return None

    def set_password(self, _service: str, _username: str, _password: str) -> None:
        return None


def _backend(tmp_path: Path) -> BackendFacade:
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    return BackendFacade(store)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])  # type: ignore[return-value]


# --------------------------------------------------------------------------------------
# In-process lifecycle contracts (the conftest guard also fails any test that leaks a
# top-level widget, so each test must release what it builds).
# --------------------------------------------------------------------------------------


def test_release_deletes_parent_and_children_while_application_stays_alive() -> None:
    app = _application()
    parent = QWidget()
    child = QLabel("child", parent)
    grandchild = QPushButton("grandchild", child)

    release_qobject_tree(parent)

    assert not shiboken6.isValid(parent)
    assert not shiboken6.isValid(child)
    assert not shiboken6.isValid(grandchild)
    assert QApplication.instance() is app


def test_release_deletes_main_window_and_its_multimedia_children(tmp_path: Path) -> None:
    app = _application()
    window = MainWindow(_backend(tmp_path))
    player, audio = window.player, window.audio
    assert shiboken6.isValid(player) and shiboken6.isValid(audio)

    window.close()
    release_qobject_tree(window)

    assert not shiboken6.isValid(window)
    assert not shiboken6.isValid(player)
    assert not shiboken6.isValid(audio)
    assert QApplication.instance() is app


def test_release_deletes_settings_dialog(tmp_path: Path) -> None:
    _application()
    dialog = SettingsDialog(_backend(tmp_path))
    assert shiboken6.isValid(dialog)

    release_qobject_tree(dialog)

    assert not shiboken6.isValid(dialog)


def test_media_player_and_audio_output_are_stopped_detached_and_released() -> None:
    _application()
    owner = QWidget()
    audio = QAudioOutput(owner)
    player = QMediaPlayer(owner)
    player.setAudioOutput(audio)
    player.stop()
    player.setSource(QUrl())
    assert player.playbackState() == QMediaPlayer.PlaybackState.StoppedState

    release_qobject_tree(owner)

    assert not shiboken6.isValid(player)
    assert not shiboken6.isValid(audio)
    assert not shiboken6.isValid(owner)


def _blocking_backend_call(started: threading.Event) -> Any:
    """``analyze_video`` stand-in that runs until the cancel event is set."""

    def analyze_video(_path: Path, **kwargs: Any) -> str:
        started.set()
        assert kwargs["cancel_event"].wait(10), "worker was never cancelled"
        raise InterruptedError

    return analyze_video


def test_running_worker_is_cancelled_and_window_closes_after_it_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _application()
    backend = _backend(tmp_path)
    started = threading.Event()
    monkeypatch.setattr(backend, "analyze_video", _blocking_backend_call(started))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes
    )
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"video")
    window = MainWindow(backend)
    try:
        window._launch_analysis(video)
        assert started.wait(10), "analysis worker did not start"
        assert window.worker is not None

        # Closing while the worker runs must cancel it and defer the close.
        window.close()
        assert window._close_after_worker is True
        assert window.isHidden() or window.worker is not None

        assert window.pool.waitForDone(10_000)
        QCoreApplication.processEvents()  # deliver the queued ``cancelled`` signal
        QCoreApplication.processEvents()  # run the ``QTimer.singleShot(0, close)``

        assert window.worker is None
        assert window._allow_close is True
    finally:
        release_qobject_tree(window)
    assert not shiboken6.isValid(window)


def test_window_is_released_after_worker_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _application()
    backend = _backend(tmp_path)
    monkeypatch.setattr(backend, "analyze_video", lambda _path, **_kwargs: "M-DONE")
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"video")
    shown: list[str] = []
    window = MainWindow(backend)
    monkeypatch.setattr(window, "_show_results", shown.append)
    try:
        window._launch_analysis(video)
        assert window.pool.waitForDone(10_000)
        QCoreApplication.processEvents()  # deliver the queued ``completed`` signal

        assert shown == ["M-DONE"]
        assert window.worker is None
    finally:
        release_qobject_tree(window)
    assert not shiboken6.isValid(window)


# --------------------------------------------------------------------------------------
# Process-level checks: the interpreter must exit with code 0, which is where the heap
# corruption used to surface.
# --------------------------------------------------------------------------------------


def _isolated_environment(tmp_path: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COV_CORE_", "COVERAGE_"))
    }
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    src = str(REPO_ROOT / "src")
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(home),
            "LOCALAPPDATA": str(home),
            "XDG_DATA_HOME": str(home),
            "XDG_CONFIG_HOME": str(home),
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONUTF8": "1",
            "PYTHONFAULTHANDLER": "1",
            "PYTHONPATH": os.pathsep.join(filter(None, [src, env.get("PYTHONPATH", "")])),
        }
    )
    return env


def _run(command: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=_isolated_environment(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=PROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _assert_clean_exit(result: subprocess.CompletedProcess[str]) -> None:
    detail = (
        f"exit code {result.returncode} (-6 = SIGABRT, -11 = SIGSEGV when killed by a signal)\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n--- stderr ---\n{result.stderr[-4000:]}"
    )
    assert result.returncode == 0, detail
    assert "QObject: shared QObject was deleted directly" not in result.stderr, detail
    assert "malloc" not in result.stderr and "double free" not in result.stderr, detail


@pytest.mark.parametrize("attempt", range(8))
def test_application_entry_point_exits_with_code_zero(attempt: int, tmp_path: Path) -> None:
    """The real ``main()`` (``--smoke-test``) must not corrupt the heap at shutdown.

    Before the fix ``main()`` returned with ``MainWindow`` still alive, and a large share
    of runs aborted or crashed while the interpreter finalised, so repeated independent
    runs are used (each attempt is a fresh interpreter).
    """
    result = _run([sys.executable, "-m", "valorant_ai_coach.main", "--smoke-test"], tmp_path)

    _assert_clean_exit(result)


_PREAMBLE = textwrap.dedent(
    """
    import os, sys
    from pathlib import Path
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from valorant_ai_coach.settings import AppSettings, SettingsStore
    from valorant_ai_coach.ui.backend import BackendFacade
    from valorant_ai_coach.ui.lifecycle import release_qobject_tree

    class Credentials:
        def get_password(self, *_args): return None
        def set_password(self, *_args): return None

    tmp = Path(sys.argv[1])
    def backend():
        store = SettingsStore(tmp / "settings.json", credential_backend=Credentials())
        store.save(AppSettings.defaults(tmp))
        return BackendFacade(store)

    app = QApplication([])
    """
)

_SCENARIOS = {
    "application_create_and_exit": "",
    "main_window_create_close_release": """
        from valorant_ai_coach.ui.main_window import MainWindow
        window = MainWindow(backend())
        window.show()
        window.close()
        release_qobject_tree(window)
    """,
    "settings_dialog_create_release": """
        from valorant_ai_coach.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(backend())
        release_qobject_tree(dialog)
    """,
    "media_player_and_audio_output_release": """
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtWidgets import QWidget
        owner = QWidget()
        audio = QAudioOutput(owner)
        player = QMediaPlayer(owner)
        player.setAudioOutput(audio)
        player.stop()
        player.setSource(QUrl())
        release_qobject_tree(owner)
    """,
    "consecutive_windows_and_dialogs": """
        from valorant_ai_coach.ui.main_window import MainWindow
        from valorant_ai_coach.ui.settings_dialog import SettingsDialog
        for _ in range(3):
            window = MainWindow(backend())
            dialog = SettingsDialog(backend())
            window.close()
            release_qobject_tree(dialog)
            release_qobject_tree(window)
    """,
}


@pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
def test_qt_lifecycle_scenario_exits_with_code_zero(scenario: str, tmp_path: Path) -> None:
    script = _PREAMBLE + textwrap.dedent(_SCENARIOS[scenario]) + '\nprint("scenario-complete")\n'
    work = tmp_path / "work"
    work.mkdir()

    result = _run([sys.executable, "-c", script, str(work)], tmp_path)

    assert "scenario-complete" in result.stdout, result.stderr[-4000:]
    _assert_clean_exit(result)


@pytest.mark.parametrize("attempt", range(3))
def test_pytest_process_exits_with_code_zero_after_consecutive_gui_tests(
    attempt: int, tmp_path: Path
) -> None:
    """A whole pytest process over the GUI tests must also exit cleanly (not only pass)."""
    result = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/test_ui_smoke.py",
            "tests/unit/test_main.py",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--basetemp",
            str(tmp_path / "basetemp"),
        ],
        tmp_path,
    )

    assert " passed" in result.stdout, result.stdout[-2000:]
    _assert_clean_exit(result)
