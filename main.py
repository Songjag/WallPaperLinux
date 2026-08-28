#!/usr/bin/env python3
"""HyprWall application launcher."""

import sys

from src.bootstrap import load_customtkinter
from src.config import LANGUAGES_FILE
from src.i18n import Translator


def main() -> None:
    if "--rotator" in sys.argv:
        from src.rotator import run_rotator

        run_rotator()
        return

    ctk = load_customtkinter()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    from src.app import WallpaperApp

    WallpaperApp(ctk, Translator(LANGUAGES_FILE)).run()


if __name__ == "__main__":
    main()
