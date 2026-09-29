from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from valorant_ai_coach.logging_setup import configure_logging
from valorant_ai_coach.settings import SettingsStore, default_data_dir
from valorant_ai_coach.ui.backend import BackendFacade
from valorant_ai_coach.ui.main_window import MainWindow

LOGGER = logging.getLogger(__name__)


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv
    qt_arguments = [argument for argument in sys.argv if argument != "--smoke-test"]
    app = QApplication(qt_arguments)
    app.setApplicationName("VALORANT AI Coach")
    app.setOrganizationName("ValorantAICoach")
    store = SettingsStore(default_data_dir() / "settings.json")
    try:
        settings = store.load()
        configure_logging(
            settings.data_dir / "logs",
            level=logging.DEBUG if settings.debug_logging else logging.INFO,
        )
        backend = BackendFacade(store)
        window = MainWindow(backend)
        if smoke_test:
            from valorant_ai_coach.maps.registry import MapRegistry

            registry = MapRegistry()
            for map_id, entry in registry.data["maps"].items():
                if entry.get("production", False):
                    registry.load(map_id)
            # Exercise the packaged composition root and widget construction without
            # leaving a GUI process running in Windows CI.
            window.close()
            app.processEvents()
            return 0
        window.show()
    except Exception as exc:
        LOGGER.exception("Application startup failed")
        if smoke_test:
            return 1
        QMessageBox.critical(
            None,
            "起動できません",
            f"アプリの初期化に失敗しました。\n\n{exc}",
        )
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
