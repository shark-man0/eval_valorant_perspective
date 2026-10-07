from __future__ import annotations


def classify_exception(exc: BaseException) -> str:
    if isinstance(exc, (InterruptedError, KeyboardInterrupt)):
        return "cancelled"
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "dependency"
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return "input"

    text = f"{type(exc).__name__}: {exc}".lower()
    ordered = (
        ("ffprobe", "video_probe"),
        ("ffmpeg", "ffmpeg"),
        ("frame", "frame_extraction"),
        ("hud", "hud"),
        ("visual", "visual"),
        ("map", "map"),
        ("round", "round_analysis"),
        ("openai", "ai"),
        ("coach", "ai"),
        ("clip", "clip"),
        ("sqlite", "storage"),
        ("database", "storage"),
        ("dependency", "dependency"),
        ("environment", "environment"),
    )
    for needle, category in ordered:
        if needle in text:
            return category
    if isinstance(exc, (ValueError, TypeError)):
        return "input"
    return "internal"
