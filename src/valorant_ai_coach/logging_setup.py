from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import default_data_dir


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

    handler = RotatingFileHandler(
        log_path,
        maxBytes=max(1024, int(max_bytes)),
        backupCount=max(0, int(backup_count)),
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
    return log_path
