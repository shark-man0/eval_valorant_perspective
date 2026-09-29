from typing import Any

from .backend import BackendFacade

__all__ = ["BackendFacade", "MainWindow"]


def __getattr__(name: str) -> Any:
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    raise AttributeError(name)
