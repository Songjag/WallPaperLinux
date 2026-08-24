#!/usr/bin/env python3
"""DesktopLiveLinux application launcher."""

from src.bootstrap import load_customtkinter
from src.config import LANGUAGES_FILE
from src.i18n import Translator


def main() -> None:
    ctk = load_customtkinter()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    from src.app import WallpaperApp

    WallpaperApp(ctk, Translator(LANGUAGES_FILE)).run()


if __name__ == "__main__":
    main()
