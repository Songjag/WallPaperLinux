"""Detection and installation of required system and Python dependencies."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


class DesktopLiveLinuxError(RuntimeError):
    """An error suitable for displaying in the application."""


@dataclass(frozen=True)
class Distribution:
    name: str
    package_manager: str
    packages: tuple[str, ...]
    requires_root: bool = True


class LinuxDependencies:
    """Detect a package manager and install mpvpaper prerequisites."""

    DISTRIBUTIONS = {
        "apt": Distribution("Debian/Ubuntu", "apt", ("mpvpaper", "mpv", "ffmpeg", "python3-pip")),
        "dnf": Distribution("Fedora", "dnf", ("mpvpaper", "mpv", "ffmpeg", "python3-pip")),
        "pacman": Distribution("Arch Linux", "pacman", ("mpvpaper", "mpv", "ffmpeg", "python-pip")),
        "zypper": Distribution("openSUSE", "zypper", ("mpvpaper", "mpv", "ffmpeg", "python3-pip")),
        "apk": Distribution("Alpine", "apk", ("mpvpaper", "mpv", "ffmpeg", "py3-pip")),
        "xbps-install": Distribution("Void Linux", "xbps-install", ("mpvpaper", "mpv", "ffmpeg", "python3-pip")),
        "eopkg": Distribution("Solus", "eopkg", ("mpvpaper", "mpv", "ffmpeg", "python3-pip")),
        "nix": Distribution("NixOS", "nix", ("mpvpaper", "mpv", "ffmpeg"), requires_root=False),
    }

    def __init__(self, log: Callable[[str], None], t: Callable[..., str]) -> None:
        self.log = log
        self.t = t

    @staticmethod
    def command_exists(command: str) -> bool:
        return shutil.which(command) is not None

    def detect(self) -> Distribution:
        for manager, distribution in self.DISTRIBUTIONS.items():
            if self.command_exists(manager):
                return distribution
        raise DesktopLiveLinuxError(self.t("no_package_manager"))

    @staticmethod
    def _run(command: list[str]) -> None:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise DesktopLiveLinuxError(result.stderr.strip() or result.stdout.strip() or "unknown error")

    def _privileged(self, command: list[str]) -> list[str]:
        executable = shutil.which(command[0])
        if executable is None:
            raise DesktopLiveLinuxError(self.t("command_missing", command=command[0]))
        command[0] = executable
        if os.geteuid() == 0:
            return command
        if self.command_exists("pkexec"):
            return ["pkexec", *command]
        if self.command_exists("sudo"):
            return ["sudo", *command]
        raise DesktopLiveLinuxError(self.t("needs_admin"))

    def install_system_dependencies(self) -> None:
        missing = [item for item in ("mpvpaper", "mpv", "ffmpeg") if not self.command_exists(item)]
        if missing:
            distro = self.detect()
            self.log(self.t("installing_system", items=", ".join(missing), distro=distro.name))
            packages = list(distro.packages)
            if distro.package_manager == "apt":
                self._run(self._privileged(["apt-get", "update"]))
                command = ["apt-get", "install", "-y", *packages]
            elif distro.package_manager == "dnf":
                command = ["dnf", "install", "-y", *packages]
            elif distro.package_manager == "pacman":
                command = ["pacman", "-S", "--needed", "--noconfirm", *packages]
            elif distro.package_manager == "zypper":
                command = ["zypper", "--non-interactive", "install", *packages]
            elif distro.package_manager == "apk":
                command = ["apk", "add", *packages]
            elif distro.package_manager == "xbps-install":
                command = ["xbps-install", "-y", *packages]
            elif distro.package_manager == "eopkg":
                command = ["eopkg", "install", "-y", *packages]
            else:
                command = ["nix", "profile", "install", *[f"nixpkgs#{item}" for item in packages]]
            if distro.requires_root:
                command = self._privileged(command)
            self._run(command)
            still_missing = [item for item in missing if not self.command_exists(item)]
            if still_missing:
                raise DesktopLiveLinuxError(self.t("still_missing", items=", ".join(still_missing)))
            self.log(self.t("dependencies_installed"))
        self.log(self.t("dependencies_ready"))

    def install_all_dependencies(self) -> None:
        self.install_system_dependencies()
        self.install_ytdlp()

    def install_ytdlp(self) -> None:
        try:
            importlib.import_module("yt_dlp")
            self.log(self.t("ytdlp_ready"))
            return
        except ImportError:
            pass
        self.log(self.t("installing_python", package="yt-dlp"))
        python = shutil.which("python3") or shutil.which("python") or sys.executable
        result = subprocess.run(
            [python, "-m", "pip", "install", "--user", "--upgrade", "yt-dlp"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise DesktopLiveLinuxError(self.t("python_install_failed", package="yt-dlp", details=details))
        importlib.invalidate_caches()
        try:
            importlib.import_module("yt_dlp")
        except ImportError as error:
            raise DesktopLiveLinuxError(self.t("python_import_failed", package="yt-dlp")) from error
        self.log(self.t("ytdlp_ready"))

    def get_ytdlp(self) -> object:
        try:
            return importlib.import_module("yt_dlp")
        except ImportError:
            raise DesktopLiveLinuxError(self.t("ytdlp_missing"))
