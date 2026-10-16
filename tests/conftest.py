import sys

import cv2
import numpy as np
import pytest
from _pytest.reports import TestReport


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Remember each phase's report so the Qt guard knows whether the test body passed."""
    outcome = yield
    setattr(item, f"_report_{call.when}", outcome.get_result())


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Fail a passing test that leaves a top-level Qt widget alive after it is torn down.

    A widget such as ``MainWindow`` is kept alive by its own signal closures, so it is not
    freed when the test function returns.  If it is still alive at interpreter shutdown,
    PySide6 deletes its C++ tree while visiting the child wrappers, which corrupts the heap
    and aborts the process *after* every test has passed (exit code 134 / 139).  Tests must
    delete what they create while the QApplication is alive.

    The check runs after pytest has released the test's fixtures and arguments, so plain
    Python-owned widgets that are freed by reference counting at that point (for example
    parentless helper widgets held by a fixture object) are not reported; only widgets that
    genuinely survive are.  Whatever is found is deleted here, then reported as an error.
    """
    result = yield
    widgets = sys.modules.get("PySide6.QtWidgets")
    if widgets is None or widgets.QApplication.instance() is None:
        return result
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent

    from valorant_ai_coach.ui.lifecycle import release_qobject_tree

    # Let ``deleteLater()`` calls made by the test finish; whatever remains is really alive.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    leaked = [w for w in widgets.QApplication.topLevelWidgets() if shiboken6.isValid(w)]
    names = sorted(type(widget).__name__ for widget in leaked)
    for widget in leaked:
        if shiboken6.isValid(widget):
            release_qobject_tree(widget)
    call = getattr(item, "_report_call", None)
    if names and call is not None and call.passed:
        message = (
            f"test left top-level Qt widgets alive: {names}; delete them before the test "
            "ends (deleteLater + DeferredDelete) so they are not destroyed during "
            "interpreter shutdown"
        )
        item.ihook.pytest_runtest_logreport(
            report=TestReport(
                nodeid=item.nodeid,
                location=item.location,
                keywords={name: 1 for name in item.keywords},
                outcome="failed",
                longrepr=message,
                when="teardown",
            )
        )
    return result


@pytest.fixture
def panel_images():
    """Synthetic positive UI and changing scene; not real VALORANT samples."""

    def make(width, height, offset=0):
        panel = np.full((126, 160), 60, np.uint8)
        cv2.line(panel, (5, 8), (155, 8), 230, 2)
        cv2.rectangle(panel, (10, 30), (45, 85), 200, 2)
        cv2.putText(panel, "AAA", (55, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 230, 1)
        scene = np.tile(np.linspace(25 + offset, 100 + offset, 160, dtype=np.uint8), (126, 1))
        cv2.circle(scene, (140, 110), 8, 230, 2)
        return tuple(
            cv2.cvtColor(
                cv2.resize(p, (width, height), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR
            )
            for p in (panel, scene)
        )

    return make


@pytest.fixture
def live_identity_signals():
    """Independent measured UI structures; never inferred from geometry fixtures."""
    return {
        "hp_hud_structure": True,
        "hp_hud_structure_confidence": 0.97,
        "ability_bar_structure": True,
        "ability_bar_structure_confidence": 0.97,
        "weapon_ammo_structure": True,
        "weapon_ammo_structure_confidence": 0.97,
        "spectator_panel_absent": True,
        "spectator_detector_checked": True,
        "spectator_panel_present": False,
    }
