"""Install the background rotator as a systemd user service."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

SERVICE_NAME = "hyprwall-rotator.service"
INSTALL_DIR = Path.home() / ".local" / "bin"
BINARY_NAME = "hyprwall"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


def _current_binary() -> Path:
    return Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).resolve()


def install_and_enable(log: Callable[[str], None]) -> None:
    if not shutil.which("systemctl"):
        log("systemd not available - skipping autostart setup.")
        return
    source = _current_binary()
    if getattr(sys, "frozen", False):
        target = INSTALL_DIR / BINARY_NAME
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
            shutil.copy2(source, target)
            target.chmod(0o755)
        exec_start = f"{target} --rotator"
    else:
        target = source
        exec_start = f"{sys.executable} {source} --rotator"
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    (UNIT_DIR / SERVICE_NAME).write_text(
        "[Unit]\nDescription=HyprWall wallpaper rotator\nAfter=graphical-session.target\n\n"
        "[Service]\n"
        f"ExecStart={exec_start}\nRestart=on-failure\nRestartSec=5\n\n"
        "[Install]\nWantedBy=default.target\n",
        encoding="utf-8",
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", SERVICE_NAME], check=False, capture_output=True)
    log(f"Background rotator installed and enabled ({SERVICE_NAME}).")


def disable(log: Callable[[str], None]) -> None:
    """Stop the rotator service without affecting the GUI."""
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "disable", "--now", SERVICE_NAME], check=False, capture_output=True)
    log("Background rotator disabled.")


def cleanup_legacy_service(log: Callable[[str], None]) -> None:
    old_names = ("desktop-live-linux-rotator.service", "wallpaper-rotator.service")
    for old_name in old_names:
        old_unit = UNIT_DIR / old_name
        if old_unit.exists() and shutil.which("systemctl"):
            subprocess.run(["systemctl", "--user", "disable", "--now", old_name], check=False, capture_output=True)
        if old_unit.exists():
            old_unit.unlink()
    old_binary = INSTALL_DIR / "desktop-live-linux"
    if old_binary.exists():
        old_binary.unlink()
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)