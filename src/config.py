"""Application paths and media settings."""

from pathlib import Path


APP_NAME = "HyprWall"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
APP_ICON = DATA_DIR / "icon.ico"
LANGUAGES_FILE = DATA_DIR / "languages.json"

WALLPAPER_DIR = Path.home() / "Pictures" / "HyprlandWallpaper"
HYPRLAND_CONFIG = Path.home() / ".config" / "hypr" / "hyprland.conf"
STATE_FILE = Path.home() / ".local" / "state" / "desktop-live-linux" / "wallpaper.json"
MARKER_START = "# >>> DesktopLiveLinux mpvpaper >>>"
MARKER_END = "# <<< DesktopLiveLinux mpvpaper <<<"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

DEFAULT_ROTATION_MINUTES = 15
MIN_ROTATION_MINUTES = 1
