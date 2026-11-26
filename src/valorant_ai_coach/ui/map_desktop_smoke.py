"""Exercise the desktop Map workflow using a synthetic public fixture."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.request import urlopen

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from valorant_ai_coach.application.map_library import (
    attach_map_tracker,
    open_map_package,
    verified_map_package,
)
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.resources import resource_root
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private
from valorant_ai_coach.ui.lifecycle import release_qobject_tree
from valorant_ai_coach.ui.map_analysis_dialog import (
    MapAnalysisDialog,
    map_external_program,
    map_worker_environment,
    map_worker_root,
)

LOGGER = logging.getLogger(__name__)


def run_map_desktop_smoke(app: QApplication) -> None:
    python = os.environ["VALORANT_MAP_SMOKE_PYTHON"]
    root = resource_root()
    worker_root = map_worker_root()
    environment = map_worker_environment(worker_root)

    def run_external(command: list[str]) -> None:
        with map_external_program(), subprocess.Popen(command, cwd=root, env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
            try:
                _, errors = child.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()
                raise
            if child.returncode:
                diagnostic = errors.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"Map smoke external process failed: {diagnostic}")

    run_external([python, str(worker_root / "scripts/map_learning/workflow.py"), "--help"])
    LOGGER.info("Packaged Map worker startup passed")
    fixture = root / "smoke/map_desktop_worker.py"
    if not fixture.is_file():
        fixture = root / "tests/fixtures/map_desktop_worker.py"
    with TemporaryDirectory(prefix="valorant-map-smoke-") as temporary:
        path = Path(temporary)
        video = path / "synthetic.mp4"
        run_external(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                      "color=c=blue:s=320x240:r=10", "-t", "2", "-pix_fmt", "yuv420p",
                      str(video)])
        catalog = RecordingCatalog.create(path / "catalog")
        baseline, candidate = (path / f"{label}.json" for label in ("baseline", "candidate"))
        for setup in (baseline, candidate):
            setup.write_text("{}", encoding="utf-8")
        dialog = MapAnalysisDialog(path / "desktop", worker=fixture)
        dialog.show()

        def wait(condition: Callable[[], bool]) -> None:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                app.processEvents()
                if condition():
                    return
                time.sleep(.02)
            raise RuntimeError(f"Map GUI smoke timed out: {dialog.status.text()}")

        def stopped() -> bool:
            return (dialog.process.state() == QProcess.ProcessState.NotRunning
                    and dialog.start_button.isEnabled())

        def complete() -> None:
            wait(stopped)
            if "ローカルに保存" not in dialog.status.text():
                raise RuntimeError(dialog.comparison.toPlainText() or dialog.status.text())

        try:
            for key, value in {
                "video": video, "catalog": catalog.root, "setup": baseline, "python": python,
                "workspace": path / "work", "library": path / "library",
            }.items():
                dialog.fields[key].setText(str(value))
            dialog.distinct.setChecked(True)
            dialog.start_button.click()
            wait(lambda: "観測フレーム" in dialog.status.text() or stopped())
            dialog.pause_button.click()
            wait(stopped)
            if "中断しました" not in dialog.status.text():
                raise RuntimeError(dialog.comparison.toPlainText() or dialog.status.text())
            # Reopen the dialog to check the persistent resume state independently.
            dialog.close()
            release_qobject_tree(dialog)
            LOGGER.info("Packaged Map registration and pause passed")
            dialog = MapAnalysisDialog(path / "desktop", worker=fixture)
            dialog.show()
            dialog.resume_button.click()
            complete()
            dialog.fields["setup"].setText(str(candidate))
            dialog.distinct.setChecked(True)
            dialog.start_button.click()
            complete()
            LOGGER.info("Packaged Map persisted resume and alternate execution passed")
            if dialog.recordings.count() != 1 or dialog.after.count() != 2:
                raise RuntimeError("Both immutable recognition variants must remain available")
            dialog.compare_results()
            if "欠測回復後" not in dialog.comparison.toPlainText():
                raise RuntimeError(dialog.comparison.toPlainText())
            baseline_receipt = Path(dialog.after.currentData())
            base = verified_map_package(baseline_receipt)
            tracked = path / "tracked_PRIVATE.json"
            write_private(tracked, {
                **read_json(base["recovered"]),
                "multi_marker_replay": {
                    "method": "development_map_multi_marker_track_v1", "formal_outputs": 0,
                    "input_sha256s": {"bundle": file_sha(base["bundle"]),
                                      "incumbent": file_sha(base["recovered"])},
                },
            })
            imported = attach_map_tracker(path / "library", baseline_receipt, tracked)
            dialog.refresh_results()
            dialog.before.setCurrentIndex(dialog.before.findData(str(baseline_receipt)))
            dialog.after.setCurrentIndex(dialog.after.findData(str(imported)))
            dialog.compare_results()
            if "複数マーカー追跡" not in dialog.comparison.toPlainText():
                raise RuntimeError(dialog.comparison.toPlainText())
            for idx in range(dialog.after.count()):
                dialog.after.setCurrentIndex(idx)
                dialog.open_result()
                receipt = dialog.selected_receipt
                if receipt is None:
                    raise RuntimeError("The selected variant did not open")
                server = open_map_package(receipt)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    url = server.viewer_url  # type: ignore[attr-defined]
                    with urlopen(url, timeout=5) as response:
                        if response.status != 200:
                            raise RuntimeError("The Map viewer did not return its homepage")
                    with urlopen(url + "api/overview", timeout=5) as response:
                        modes = json.load(response)["recorder_map_presence"]
                        expected = {"standard", "recovered"}
                        if receipt == imported:
                            expected.add("tracked")
                        if modes.keys() != expected:
                            raise RuntimeError("The Map viewer exposed the wrong result modes")
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()
        finally:
            if not stopped():
                dialog.pause_job()
                wait(stopped)
            dialog.close()
            release_qobject_tree(dialog)
        LOGGER.info("Packaged Map result comparison and viewer passed")
