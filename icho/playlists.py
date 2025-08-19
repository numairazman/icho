# icho/playlists.py
# Small persistence layer for "Recent" and "Pinned" playlists.
# - Stores a JSON file in a per-user config dir (no extra deps).
# - API is tiny: add_recent, pin, unpin, get_recent, get_pinned, set_current.

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import os
import platform


# ---------- Where do we store the small config JSON? ----------
def _app_config_dir() -> Path:
    """
    Pick a per-user config directory depending on platform.
    Linux:  ~/.config/icho
    macOS:  ~/Library/Application Support/icho
    Windows:%APPDATA%\\icho
    """
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return base / "icho"
    elif system == "Darwin":
        return home / "Library" / "Application Support" / "icho"
    else:
        return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "icho"


@dataclass
class _State:
    # Keep absolute paths only; UI should ensure they exist when using them.
    recent: List[str]
    pinned: List[str]
    last_loaded: Optional[str] = None  # path of current/last loaded playlist

    @staticmethod
    def empty() -> "_State":
        return _State(recent=[], pinned=[], last_loaded=None)


class PlaylistManager:
    """
    Manages persistence for recent and pinned playlists.
    Limits:
      - recent: max 5 (MRU)
      - pinned: max 10 (user chosen)
    """

    def __init__(self, path: Optional[Path] = None, max_recent: int = 5, max_pinned: int = 10) -> None:
        self._max_recent = int(max_recent)
        self._max_pinned = int(max_pinned)

        config_dir = _app_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        self._path = path or (config_dir / "playlists.json")

        self._state = self._load()

    # ---------- Public API ----------

    def get_recent(self) -> List[str]:
        return list(self._state.recent)

    def get_pinned(self) -> List[str]:
        return list(self._state.pinned)

    def last_loaded(self) -> Optional[str]:
        return self._state.last_loaded

    def set_current(self, playlist_json_path: str) -> None:
        """
        Remember the last loaded/saved playlist path so the UI can
        offer quick Pin/Unpin actions for the 'current' playlist.
        """
        self._state.last_loaded = str(playlist_json_path)
        self._save()

    def add_recent(self, playlist_json_path: str) -> None:
        """
        Insert path at front of MRU list, dedupe, clamp size.
        """
        p = str(playlist_json_path)
        items = [x for x in self._state.recent if x != p]
        items.insert(0, p)
        self._state.recent = items[: self._max_recent]
        self._save()

    def pin(self, playlist_json_path: str) -> None:
        """
        Add to pinned (front), dedupe, clamp size.
        """
        p = str(playlist_json_path)
        items = [x for x in self._state.pinned if x != p]
        items.insert(0, p)
        self._state.pinned = items[: self._max_pinned]
        self._save()

    def unpin(self, playlist_json_path: str) -> None:
        p = str(playlist_json_path)
        self._state.pinned = [x for x in self._state.pinned if x != p]
        self._save()

    # ---------- Storage ----------

    def _load(self) -> _State:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                return _State(
                    recent=[str(p) for p in data.get("recent", [])],
                    pinned=[str(p) for p in data.get("pinned", [])],
                    last_loaded=(data.get("last_loaded") or None),
                )
        except Exception:
            pass
        return _State.empty()

    def _save(self) -> None:
        data = {
            "recent": self._state.recent,
            "pinned": self._state.pinned,
            "last_loaded": self._state.last_loaded,
        }
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # Not fatal for the app; we just skip persistence if it fails.
            pass