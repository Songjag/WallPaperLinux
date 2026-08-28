"""Persisted settings shared by the GUI and background rotator."""

from __future__ import annotations

import configparser

from .config import DEFAULT_ROTATION_MINUTES, MIN_ROTATION_MINUTES, WALLPAPER_DIR

CONFIG_FILE = WALLPAPER_DIR / ".config.cfg"


def read_config() -> dict[str, object]:
    parser = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        parser.read(CONFIG_FILE, encoding="utf-8")
    section = parser["rotation"] if parser.has_section("rotation") else {}
    try:
        fallback = int(section.get("fallback_minutes", DEFAULT_ROTATION_MINUTES))
    except ValueError:
        fallback = DEFAULT_ROTATION_MINUTES
    return {
        "enabled": str(section.get("enabled", "false")).lower() == "true",
        "fallback_minutes": max(MIN_ROTATION_MINUTES, fallback),
        "shuffle": str(section.get("shuffle", "true")).lower() == "true",
    }


def write_config(*, enabled: bool, fallback_minutes: int, shuffle: bool = True) -> None:
    parser = configparser.ConfigParser()
    parser["rotation"] = {
        "enabled": "true" if enabled else "false",
        "fallback_minutes": str(max(MIN_ROTATION_MINUTES, fallback_minutes)),
        "shuffle": "true" if shuffle else "false",
    }
    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        parser.write(handle)