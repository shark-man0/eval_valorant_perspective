from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


def raspberry_pi_metrics() -> dict[str, Any]:
    """Best-effort Pi-only diagnostics. Never raises when the host lacks Pi facilities."""
    result: dict[str, Any] = {
        "available": False,
        "cpu_temperature_c": None,
        "throttling_state": None,
    }
    if platform.system() != "Linux" or platform.machine().lower() not in {"aarch64", "arm64"}:
        return result

    temperature_path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        if temperature_path.is_file():
            raw_temperature = float(temperature_path.read_text().strip())
            result["cpu_temperature_c"] = round(raw_temperature / 1000.0, 2)
            result["available"] = True
    except (OSError, ValueError):
        pass

    vcgencmd = shutil.which("vcgencmd")
    if vcgencmd is not None:
        try:
            completed = subprocess.run(
                [vcgencmd, "get_throttled"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            line = (completed.stdout or "").strip()
            if completed.returncode == 0 and line.startswith("throttled="):
                result["throttling_state"] = line.split("=", 1)[1]
                result["available"] = True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return result
