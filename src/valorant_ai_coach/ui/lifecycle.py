"""Deterministic teardown of Qt object trees.

PySide6 keeps a Python wrapper alive for every ``QObject`` that is still referenced
from Python, and signal connections made with closures (``lambda: self.method()``) keep
their receiver alive as well.  A top-level widget such as ``MainWindow`` therefore never
reaches refcount zero on its own and is *not* collected when the last local name goes
away.  If it is still alive when the interpreter finalises, PySide6 deletes the C++ tree
from inside ``PySide::destroyQCoreApplication`` while the wrappers of its children are
being visited, which destroys objects twice and corrupts the heap (observed as
``malloc_consolidate(): unaligned fastbin chunk detected``, ``double free or corruption``
or a segmentation fault *after* every test or the whole application run has finished).

The only safe point to delete such a tree is while the ``QApplication`` and its event
dispatcher are still alive, so owners release it explicitly with
:func:`release_qobject_tree` before returning to the interpreter.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QObject


def release_qobject_tree(obj: QObject) -> None:
    """Delete ``obj`` and all of its Qt children now, while the application is alive.

    ``deleteLater`` is used (rather than a direct delete) so that Qt finishes any event
    that is currently being delivered to the object.  ``DeferredDelete`` events are then
    delivered explicitly: they are not processed by a plain ``processEvents`` once the
    event loop has exited or when called outside of a running loop.
    """

    obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


__all__ = ["release_qobject_tree"]
