"""Background wallpaper rotation loop."""

from __future__ import annotations

import random
import time
from pathlib import Path

from .config import MEDIA_EXTENSIONS, WALLPAPER_DIR
from .media import playback_seconds
from .rotation_config import read_config
from .wallpaper import HyprlandWallpaper

POLL_SECONDS = 5


def _log(message: str) -> None:
    print(message, flush=True)


def _t(key: str, **values: object) -> str:
    return key.format(**values) if values else key


def _library() -> list[Path]:
    return sorted(path for path in WALLPAPER_DIR.iterdir() if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS)


def _wait_for(seconds: float) -> None:
    remaining = seconds
    while remaining > 0:
        if not read_config()["enabled"]:
            return
        chunk = min(POLL_SECONDS, remaining)
        time.sleep(chunk)
        remaining -= chunk


def _current_candidates(current: Path | None) -> list[Path]:
    library = _library()
    if not library:
        return []
    if current is not None and not current.exists():
        current = None
    if current is not None:
        remaining = [path for path in library if path != current]
        if remaining:
            return remaining
    return library


def run_rotator() -> None:
    wallpaper = HyprlandWallpaper(_log, _t)
    current: Path | None = None
    while True:
        config = read_config()
        if not config["enabled"]:
            time.sleep(POLL_SECONDS)
            continue
        candidates = _current_candidates(current)
        if not candidates:
            time.sleep(POLL_SECONDS)
            continue
        choice = random.choice(candidates) if config["shuffle"] else candidates[0]
        try:
            wallpaper.set_wallpaper(choice)
            current = choice
        except Exception as error:
            _log(f"error: {error}")
            time.sleep(POLL_SECONDS)
            continue
        duration = playback_seconds(choice, config["fallback_minutes"] * 60)
        _wait_for(duration)