from __future__ import annotations

import threading
import traceback
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class AnalysisSignals(QObject):
    progress = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str, str)
    cancelled = Signal()


class ProbeSignals(QObject):
    completed = Signal(str, str, object)
    failed = Signal(str, str, str)
    cancelled = Signal(str)


class VideoProbeWorker(QRunnable):
    """Read video metadata without blocking the Qt GUI thread."""

    def __init__(self, backend: Any, video_path: Path, request_id: str) -> None:
        super().__init__()
        self.backend = backend
        self.video_path = Path(video_path)
        self.request_id = str(request_id)
        self.cancel_event = threading.Event()
        self.signals = ProbeSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            metadata = self.backend.probe_video(
                self.video_path,
                cancel_event=self.cancel_event,
            )
            if self.cancel_event.is_set():
                self.signals.cancelled.emit(self.request_id)
            else:
                self.signals.completed.emit(
                    self.request_id,
                    str(self.video_path),
                    metadata,
                )
        except InterruptedError:
            self.signals.cancelled.emit(self.request_id)
        except Exception as exc:
            if self.cancel_event.is_set():
                self.signals.cancelled.emit(self.request_id)
            else:
                self.signals.failed.emit(
                    self.request_id,
                    str(exc),
                    traceback.format_exc(),
                )


class AnalysisWorker(QRunnable):
    """Run the blocking video/AI pipeline outside the GUI thread."""

    def __init__(
        self,
        backend: Any,
        video_path: Path,
        *,
        match_id: str | None = None,
        resume: bool = False,
    ) -> None:
        super().__init__()
        self.backend = backend
        self.video_path = Path(video_path)
        self.match_id = match_id
        self.resume = resume
        self.cancel_event = threading.Event()
        self.signals = AnalysisSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            match_id = self.backend.analyze_video(
                self.video_path,
                progress_cb=lambda value, text: self.signals.progress.emit(value, text),
                cancel_event=self.cancel_event,
                match_id=self.match_id,
                resume=self.resume,
            )
            if self.cancel_event.is_set():
                self.signals.cancelled.emit()
            else:
                self.signals.completed.emit(str(match_id))
        except InterruptedError:
            self.signals.cancelled.emit()
        except Exception as exc:  # GUI boundary must surface every backend failure.
            if self.cancel_event.is_set():
                self.signals.cancelled.emit()
            else:
                self.signals.failed.emit(str(exc), traceback.format_exc())


__all__ = ["AnalysisSignals", "AnalysisWorker", "ProbeSignals", "VideoProbeWorker"]
