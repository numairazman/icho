# core/settings.py
# JSON-backed settings with platform-correct config paths.
# We standardized the app directory name to "icho" (lowercase).
# This module also migrates any legacy "iCho" directory to "icho" automatically.

import json
import os
import sys
import shutil
from dataclasses import dataclass, asdict
from typing import Optional

# -----------------------------
# Internal path helpers
# -----------------------------
def _platform_config_root() -> str:
    """
    Return the base directory for per-user app config, platform-aware.
    - Windows: %APPDATA%
    - Linux/macOS: ~/.config
    """
    if sys.platform.startswith("win"):
        return os.getenv("APPDATA", os.path.expanduser("~"))  # Fallback to HOME
    else:
        return os.path.join(os.path.expanduser("~"), ".config")

def _app_dir() -> str:
    """
    Final app directory (lowercase) for icho.
    Examples:
      - Windows: %APPDATA%\\icho
      - Linux/macOS: ~/.config/icho
    """
    return os.path.join(_platform_config_root(), "icho")

def _legacy_app_dir() -> str:
    """
    Legacy directory that used to be spelled "iCho".
    We migrate from here if found.
    """
    return os.path.join(_platform_config_root(), "iCho")

def _config_path() -> str:
    return os.path.join(_app_dir(), "config.json")

def _migrate_legacy_dir_if_needed() -> None:
    """
    If the old 'iCho' directory exists and the new 'icho' does not,
    move its contents to the new folder. Non-destructive if both exist.
    """
    legacy = _legacy_app_dir()
    new = _app_dir()

    if os.path.isdir(legacy) and not os.path.exists(new):
        try:
            os.makedirs(os.path.dirname(new), exist_ok=True)
            shutil.move(legacy, new)  # moves the entire folder
        except Exception:
            # Fail silently to avoid blocking the app. (Optional: log to a debug file.)
            pass


# -----------------------------
# App version
# -----------------------------
VERSION = "1.4.2"

# -----------------------------
# Settings model
# -----------------------------
@dataclass
class Settings:
    # UI theme: "light" or "dark"
    theme: str = "dark"
    # Library directory for scanning music. If None, app can use a default (e.g., ~/Music).
    libraryPath: Optional[str] = None
    # Toggle internet metadata/artwork lookups.
    scrapingEnabled: bool = True
    # Persist main window geometry/position between runs.
    rememberWindowPos: bool = True
    # Remember last opened/saved playlist path.
    lastPlaylistPath: Optional[str] = None

# -----------------------------
# Public API
# -----------------------------
def load_settings() -> Settings:
    """
    Load settings from disk, migrating legacy directory spelling if needed.
    Creates defaults on first run.
    """
    _migrate_legacy_dir_if_needed()
    os.makedirs(_app_dir(), exist_ok=True)
    cfg_path = _config_path()

    if not os.path.exists(cfg_path):
        s = Settings()
        save_settings(s)
        return s

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Merge loaded settings with defaults to survive future fields being added.
    defaults = Settings()
    merged = {**asdict(defaults), **data}
    return Settings(**merged)

def save_settings(settings: Settings) -> None:
    """
    Persist settings to disk (pretty-printed JSON).
    """
    os.makedirs(_app_dir(), exist_ok=True)
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=2)