from __future__ import annotations

import logging
import os
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from .observability.context import DiagnosticContextFilter
from .observability.sanitize import sanitize_text
from .settings import default_data_dir


class _PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self) -> TextIO:
        stream = super()._open()
        if os.name != "nt":
            with suppress(OSError):
                Path(self.baseFilename).chmod(0o600)
        return stream


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return sanitize_text(super().format(record))


def configure_logging(
    data_dir: Path | None = None,
    *,
    level: int = logging.INFO,
    max_bytes: int = 2_000_000,
    backup_count: int = 3,
) -> Path:
    """Configure bounded UTF-8 file logging and return the log path."""
    root = logging.getLogger()
    target_dir = Path(data_dir) if data_dir else default_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "valorant-ai-coach.log"

    for handler in tuple(root.handlers):
        root.removeHandler(handler)
        handler.close()

    handler = _PrivateRotatingFileHandler(
        log_path,
        maxBytes=max(1024, int(max_bytes)),
        backupCount=max(0, int(backup_count)),
        encoding="utf-8",
    )
    handler.addFilter(DiagnosticContextFilter())
    handler.setFormatter(
        _RedactingFormatter(
            (
                "%(asctime)s %(levelname)s %(name)s "
                "[run=%(run_id)s match=%(match_id)s round=%(round_no)s phase=%(phase)s]: "
                "%(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
    return log_path
