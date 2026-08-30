"""Hyprland wallpaper integration.

Backend selection
-----------------
Static images (.jpg, .png, .webp, .bmp, .gif single-frame, …)
  1. swww img          – preferred, smooth transitions
  2. hyprpaper         – fallback if swww is absent
  3. mpvpaper          – last resort (works but no native image loop)

Animated / video media (.mp4, .webm, .mkv, animated .gif / .webp, …)
  → mpvpaper (only option)

The hyprland.conf exec-once block is rewritten on every change so the
correct command runs automatically on the next login.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable

from .config import HYPRLAND_CONFIG, MARKER_END, MARKER_START, MEDIA_EXTENSIONS, STATE_FILE
from .dependencies import DesktopLiveLinuxError
from .media import MediaKind, classify_media

# How long (seconds) to wait for swww-daemon to become ready.
_SWWW_DAEMON_TIMEOUT = 5.0
_SWWW_DAEMON_POLL = 0.3


class HyprlandWallpaper:

    def __init__(self, log: Callable[[str], None], t: Callable[..., str]) -> None:
        self.log = log
        self.t = t

    # ------------------------------------------------------------------
    # Environment detection
    # ------------------------------------------------------------------

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
        if shutil.which("hyprctl") is not None:
            return True
        return bool(os.environ.get("WAYLAND_DISPLAY")) and shutil.which("hyprctl") is not None

    # ------------------------------------------------------------------
    # Command builders
    # ------------------------------------------------------------------

    @staticmethod
    def _mpvpaper_command(path: Path) -> list[str]:
        return ["mpvpaper", "-o", "--no-audio --panscan=1.0 --loop-file=inf", "*", str(path)]

    @staticmethod
    def _mpvpaper_config_command(path: Path) -> str:
        option = "--no-audio --panscan=1.0 --loop-file=inf"
        return f'mpvpaper -o "{option}" \'*\' {shlex.quote(str(path))}'

    @staticmethod
    def _swww_command(path: Path) -> list[str]:
        return [
            "swww", "img",
            "--transition-type", "fade",
            "--transition-duration", "1",
            str(path),
        ]

    @staticmethod
    def _swww_config_command(path: Path) -> str:
        return f"swww img --transition-type fade --transition-duration 1 {shlex.quote(str(path))}"

    @staticmethod
    def _hyprpaper_config_text(path: Path) -> str:
        p = str(path)
        return f"preload = {p}\nwallpaper = ,{p}\n"

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_state() -> dict[str, object]:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_state(self, pid: int, path: Path, backend: str) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps({"pid": pid, "path": str(path), "backend": backend}),
            encoding="utf-8",
        )

    def _stop_previous(self) -> None:
        """Terminate any previously launched wallpaper process (all backends)."""
        state = self._load_state()
        pid = state.get("pid")
        if isinstance(pid, int) and pid > 0:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        pkill = shutil.which("pkill")
        if pkill:
            subprocess.run([pkill, "-x", "mpvpaper"],  check=False, capture_output=True)
            subprocess.run([pkill, "-x", "hyprpaper"], check=False, capture_output=True)
        self.log(self.t("stopped"))

    # ------------------------------------------------------------------
    # Hyprland config writer
    # ------------------------------------------------------------------

    def _write_hyprland_config(self, exec_lines: str | Path) -> None:
        """Overwrite the HyprWall exec-once block in hyprland.conf."""
        if isinstance(exec_lines, Path):
            path = exec_lines.expanduser().resolve()
            exec_lines = (
                'exec-once = mpvpaper -o "--no-audio --panscan=1.0 --loop-file=inf" \'*\' '
                f"{shlex.quote(str(path))}"
            )
        self.log(f"[wallpaper] updating Hyprland config: {exec_lines}")
        HYPRLAND_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        original = HYPRLAND_CONFIG.read_text(encoding="utf-8") if HYPRLAND_CONFIG.exists() else ""

        # Strip all stale HyprWall / mpvpaper / swww / hyprpaper lines.
        patterns = [
            r"(?m)^\s*exec-once\s*=\s*.*mpvpaper.*$\n?",
            r"(?m)^\s*exec-once\s*=\s*.*swww.*$\n?",
            r"(?m)^\s*exec-once\s*=\s*.*hyprpaper.*$\n?",
            r"(?m)^\s*#\s*.*DesktopLiveLinux.*$\n?",
            r"(?m)^\s*#\s*>>>\s*DesktopLiveLinux mpvpaper\s*>>>\s*$\n?",
            r"(?m)^\s*#\s*<<<\s*DesktopLiveLinux mpvpaper\s*<<<\s*$\n?",
        ]
        for pattern in patterns:
            original = re.sub(pattern, "", original)

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

        block = f"\n{MARKER_START}\n{exec_lines}\n{MARKER_END}\n"
        HYPRLAND_CONFIG.write_text(cleaned + block, encoding="utf-8")
        self.log(f"[wallpaper] config written to {HYPRLAND_CONFIG}")

    # ------------------------------------------------------------------
    # swww helpers
    # ------------------------------------------------------------------

    def _ensure_swww_daemon(self) -> bool:
        """Ensure swww-daemon is running. Returns True when ready."""
        # Check if already running.
        result = subprocess.run(["swww", "query"], capture_output=True, check=False)
        if result.returncode == 0:
            return True

        # Start the daemon.
        subprocess.Popen(
            ["swww-daemon"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Poll until ready (up to _SWWW_DAEMON_TIMEOUT seconds).
        deadline = time.monotonic() + _SWWW_DAEMON_TIMEOUT
        while time.monotonic() < deadline:
            time.sleep(_SWWW_DAEMON_POLL)
            probe = subprocess.run(["swww", "query"], capture_output=True, check=False)
            if probe.returncode == 0:
                return True

        return False  # daemon did not become ready in time

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_wallpaper(self, path: Path) -> None:
        path = path.expanduser().resolve()
        self.log(f"[wallpaper] setting wallpaper: {path}")
        if not path.is_file():
            self.log(f"[wallpaper] file missing: {path}")
            raise DesktopLiveLinuxError(self.t("file_missing"))
        if path.suffix.lower() not in MEDIA_EXTENSIONS:
            self.log(f"[wallpaper] unsupported media type: {path.suffix}")
            raise DesktopLiveLinuxError(self.t("unsupported_media"))
        if not self.in_hyprland():
            self.log("[wallpaper] current session is not Hyprland")
            raise DesktopLiveLinuxError(self.t("hyprland_only"))
        if not shutil.which("hyprctl"):
            self.log("[wallpaper] hyprctl is not installed or not on PATH")
            raise DesktopLiveLinuxError(self.t("hyprctl_missing"))

        kind = classify_media(path)
        self.log(f"[wallpaper] detected media kind: {kind}")

        if kind is MediaKind.IMAGE:
            self._set_image(path)
        else:
            self._set_video(path, kind)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _set_image(self, path: Path) -> None:
        """Set a static image wallpaper using the best available backend."""

        # --- Backend 1: swww ---
        if shutil.which("swww"):
            self._write_hyprland_config(
                "exec-once = swww-daemon\n"
                f"exec-once = {self._swww_config_command(path)}"
            )
            self._stop_previous()

            daemon_ready = self._ensure_swww_daemon()
            if daemon_ready:
                result = subprocess.run(
                    self._swww_command(path),
                    capture_output=True, text=True, check=False,
                )
                if result.returncode == 0:
                    self._save_state(0, path, "swww")
                    subprocess.run(["hyprctl", "reload"], capture_output=True, check=False)
                    self.log(self.t("wallpaper_set", file=path.name))
                    return
                # swww ran but failed — fall through to next backend.
                self.log(f"swww img error: {(result.stderr or result.stdout).strip()}")
            else:
                self.log("swww-daemon did not start in time, trying next backend.")

        # --- Backend 2: hyprpaper ---
        if shutil.which("hyprpaper"):
            cfg_dir = Path.home() / ".config" / "hypr"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / "hyprpaper.conf"
            cfg_file.write_text(self._hyprpaper_config_text(path), encoding="utf-8")

            self._write_hyprland_config(f"exec-once = hyprpaper")
            self._stop_previous()

            proc = subprocess.Popen(
                ["hyprpaper"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._save_state(proc.pid, path, "hyprpaper")
            subprocess.run(["hyprctl", "reload"], capture_output=True, check=False)
            self.log(self.t("wallpaper_set", file=path.name))
            return

        # --- Backend 3: mpvpaper (last resort for images) ---
        if shutil.which("mpvpaper"):
            self._write_hyprland_config(
                f"exec-once = {self._mpvpaper_config_command(path)}"
            )
            self._stop_previous()
            proc = subprocess.Popen(
                self._mpvpaper_command(path),
                start_new_session=True,
            )
            self._save_state(proc.pid, path, "mpvpaper")
            subprocess.run(["hyprctl", "reload"], capture_output=True, check=False)
            self.log(self.t("wallpaper_set", file=path.name))
            return

        raise DesktopLiveLinuxError(self.t("swww_missing"))

    def _set_video(self, path: Path, kind: MediaKind) -> None:
        """Use mpvpaper to display a video or animated image."""
        if not shutil.which("mpvpaper"):
            raise DesktopLiveLinuxError(self.t("mpvpaper_missing"))

        self._write_hyprland_config(
            f"exec-once = {self._mpvpaper_config_command(path)}"
        )
        self._stop_previous()
        proc = subprocess.Popen(
            self._mpvpaper_command(path),
            start_new_session=True,
        )
        self._save_state(proc.pid, path, "mpvpaper")
        subprocess.run(["hyprctl", "reload"], capture_output=True, check=False)
        self.log(self.t("wallpaper_set", file=path.name))
