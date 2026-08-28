"""Media classification and playback duration detection."""

from __future__ import annotations

import json
import shutil
import subprocess
from enum import Enum
from pathlib import Path

from .config import VIDEO_EXTENSIONS

ANIMATABLE_EXTENSIONS = {".gif", ".webp"}


class MediaKind(Enum):
    IMAGE = "image"
    ANIMATED_IMAGE = "animated_image"
    VIDEO = "video"


def classify_media(path: Path) -> MediaKind:
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return MediaKind.VIDEO
    if suffix in ANIMATABLE_EXTENSIONS and _is_animated(path):
        return MediaKind.ANIMATED_IMAGE
    return MediaKind.IMAGE


def _is_animated(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return getattr(image, "n_frames", 1) > 1
    except Exception:
        return _ffprobe_frame_count(path) > 1


def _ffprobe_frame_count(path: Path) -> int:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 1
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "json", str(path)],
        text=True, capture_output=True, check=False,
    )
    try:
        frames = json.loads(result.stdout)["streams"][0].get("nb_frames", "1")
        return int(frames)
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return 1


def probe_duration_seconds(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, capture_output=True, check=False,
    )
    try:
        duration = float(result.stdout.strip())
        if duration > 0:
            return duration
    except ValueError:
        pass
    return _duration_from_stream(path, ffprobe)


def _duration_from_stream(path: Path, ffprobe: str) -> float | None:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames,avg_frame_rate,duration", "-of", "json", str(path)],
        text=True, capture_output=True, check=False,
    )
    try:
        stream = json.loads(result.stdout)["streams"][0]
    except (KeyError, IndexError, json.JSONDecodeError):
        return None
    raw_duration = stream.get("duration")
    try:
        if raw_duration not in (None, "N/A") and float(raw_duration) > 0:
            return float(raw_duration)
    except (TypeError, ValueError):
        pass
    try:
        frames = int(stream.get("nb_frames", "0"))
        numerator, _, denominator = stream.get("avg_frame_rate", "0/1").partition("/")
        fps = float(numerator) / float(denominator or 1)
        if frames > 0 and fps > 0:
            return frames / fps
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def playback_seconds(path: Path, fallback_seconds: float) -> float:
    if classify_media(path) is MediaKind.IMAGE:
        return fallback_seconds
    return probe_duration_seconds(path) or fallback_seconds
