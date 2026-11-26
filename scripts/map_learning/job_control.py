"""Cooperative desktop Map job control shared by the CLI and its children."""

import os
import subprocess
from pathlib import Path

PAUSE_EXIT = 75
PAUSE_ENV = "VALORANT_MAP_PAUSE_FILE"
PHASE_PREFIX = "Map workflow phase: "


class MapPaused(InterruptedError):
    """The caller asked to keep completed files and stop this job."""


def check_pause():
    signal = os.environ.get(PAUSE_ENV)
    if signal and Path(signal).is_file():
        raise MapPaused("Map analysis paused")


def phase(name):
    check_pause()
    print(PHASE_PREFIX + name, flush=True)


def run_interruptible(command, **kwargs):
    check_pause()
    with subprocess.Popen(command, **kwargs) as child:
        try:
            while True:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    check_pause()
        finally:
            if child.poll() is None:
                child.kill()
        if code:
            raise subprocess.CalledProcessError(code, command)
