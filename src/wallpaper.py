"""Hyprland and mpvpaper wallpaper integration."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Callable

from .config import HYPRLAND_CONFIG, MARKER_END, MARKER_START, MEDIA_EXTENSIONS, STATE_FILE
from .dependencies import DesktopLiveLinuxError


class HyprlandWallpaper:

    def __init__(self, log: Callable[[str], None], t: Callable[..., str]) -> None:
        self.log = log
        self.t = t

    @staticmethod
    def in_hyprland() -> bool:
        desktop = (
            os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
            or os.environ.get("XDG_CURRENT_DESKTOP")
            or os.environ.get("XDG_SESSION_DESKTOP")
            or os.environ.get("DESKTOP_SESSION")
            or ""
        )
        if "hyprland" in desktop.lower():
            return True
        return bool(os.environ.get("WAYLAND_DISPLAY")) and shutil.which("hyprctl") is not None

    @staticmethod
    def _command(path: Path) -> list[str]:
        return ["mpvpaper", "-o", "--no-audio --panscan=1.0 --loop-file=inf", "*", str(path)]

    @staticmethod
    def _load_state() -> dict[str, object]:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _stop_previous(self) -> None:
        pid = self._load_state().get("pid")
        if isinstance(pid, int):
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        pkill = shutil.which("pkill")
        if pkill:
            subprocess.run([pkill, "-x", "mpvpaper"], check=False, capture_output=True)
        self.log(self.t("stopped"))

    def _write_hyprland_config(self, path: Path) -> None:
        HYPRLAND_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        original = HYPRLAND_CONFIG.read_text(encoding="utf-8") if HYPRLAND_CONFIG.exists() else ""

        # Always replace all prior DesktopLiveLinux blocks. If we append forever,
        # Hyprland will launch a fresh mpvpaper instance on every boot and grow RAM.
        if MARKER_START in original and MARKER_END in original:
            original = re.sub(
                rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\s*",
                "",
                original,
                flags=re.DOTALL,
            )

        cleaned = original.rstrip() + "\n"
        if HYPRLAND_CONFIG.exists():
            backup = HYPRLAND_CONFIG.with_suffix(HYPRLAND_CONFIG.suffix + ".desktop-live-linux.bak")
            backup.write_text(HYPRLAND_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
            self.log(self.t("backup", file=backup.name))
        command = " ".join(shlex.quote(part) for part in self._command(path))
        block = f"\n{MARKER_START}\nexec-once = {command}\n{MARKER_END}\n"
        HYPRLAND_CONFIG.write_text(cleaned + block, encoding="utf-8")

    def set_wallpaper(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise DesktopLiveLinuxError(self.t("file_missing"))
        if path.suffix.lower() not in MEDIA_EXTENSIONS:
            raise DesktopLiveLinuxError(self.t("unsupported_media"))
        if not self.in_hyprland():
            raise DesktopLiveLinuxError(self.t("hyprland_only"))
        if not shutil.which("hyprctl"):
            raise DesktopLiveLinuxError(self.t("hyprctl_missing"))
        if not shutil.which("mpvpaper"):
            raise DesktopLiveLinuxError(self.t("mpvpaper_missing"))
        self._write_hyprland_config(path)
        self._stop_previous()
        process = subprocess.Popen(self._command(path), start_new_session=True)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"pid": process.pid, "path": str(path)}), encoding="utf-8")
        subprocess.run(["hyprctl", "reload"], text=True, capture_output=True, check=False)
        self.log(self.t("wallpaper_set", file=path.name))
