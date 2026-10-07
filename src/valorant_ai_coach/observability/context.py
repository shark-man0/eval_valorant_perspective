from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

_RUN_ID: ContextVar[str] = ContextVar("valorant_run_id", default="-")
_MATCH_ID: ContextVar[str] = ContextVar("valorant_match_id", default="-")
_ROUND_NO: ContextVar[str] = ContextVar("valorant_round_no", default="-")
_PHASE: ContextVar[str] = ContextVar("valorant_phase", default="-")


@dataclass(frozen=True, slots=True)
class DiagnosticContext:
    run_id: str = "-"
    match_id: str = "-"
    round_no: str = "-"
    phase: str = "-"


def current_context() -> DiagnosticContext:
    return DiagnosticContext(
        run_id=_RUN_ID.get(),
        match_id=_MATCH_ID.get(),
        round_no=_ROUND_NO.get(),
        phase=_PHASE.get(),
    )


@contextmanager
def bind_context(
    *,
    run_id: str | None = None,
    match_id: str | None = None,
    round_no: int | str | None = None,
    phase: str | None = None,
) -> Iterator[None]:
    tokens: list[tuple[ContextVar[str], Token[str]]] = []
    if run_id is not None:
        tokens.append((_RUN_ID, _RUN_ID.set(str(run_id))))
    if match_id is not None:
        tokens.append((_MATCH_ID, _MATCH_ID.set(str(match_id))))
    if round_no is not None:
        tokens.append((_ROUND_NO, _ROUND_NO.set(str(round_no))))
    if phase is not None:
        tokens.append((_PHASE, _PHASE.set(str(phase))))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


class DiagnosticContextFilter(logging.Filter):
    """Inject contextvars into LogRecord without any process-global mutable run state."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = current_context()
        setattr(record, "run_id", context.run_id)
        setattr(record, "match_id", context.match_id)
        setattr(record, "round_no", context.round_no)
        setattr(record, "phase", context.phase)
        return True
