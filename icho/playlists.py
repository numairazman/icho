# icho/playlists.py
# Small persistence layer for "Recent" and "Pinned" playlists.
# - Stores a JSON file in a per-user config dir (no extra deps).
# - API is tiny: add_recent, pin, unpin, get_recent, get_pinned, set_current.
# - Patched to:
#     * enforce lowercase "icho" app dir
#     * migrate legacy "iCho" -> "icho" silently
#     * normalize paths for stable dedupe (absolute/resolve)
#     * atomic saves to avoid corrupted JSON on crash

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import os
import platform
import shutil
import tempfile

# ---------- Path helpers ----------

def _platform_config_root() -> Path:
    """
    Platform base for per-user app config:
      - Windows: %APPDATA% (fallback to ~/AppData/Roaming)
      - macOS:   ~/Library/Application Support
      - Linux:   $XDG_CONFIG_HOME or ~/.config
    """
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    elif system == "Darwin":
        return home / "Library" / "Application Support"
    else:
        return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))

def _app_config_dir() -> Path:
    """
    Preferred (lowercase) app directory: .../icho
    """
    return _platform_config_root() / "icho"

def _legacy_app_config_dir() -> Path:
    """
    Legacy mixed-case directory retained by older builds: .../iCho
    """
    return _platform_config_root() / "iCho"

def _ensure_app_dir() -> Path:
    """
    Ensure icho/ exists. If legacy iCho/ exists and icho/ does not,
    move the legacy directory to icho/ (silent best-effort).
    """
    new_dir = _app_config_dir()
    legacy_dir = _legacy_app_config_dir()
    try:
        if legacy_dir.is_dir() and not new_dir.exists():
            # Parent exists by definition; still ensure defensive create
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_dir), str(new_dir))
    except Exception:
        # Non-fatal; just fall back to creating new_dir below
        pass

    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir

def _normalize_path(p: str | Path) -> str:
    """
    Normalize user-provided playlist paths so dedupe works reliably:
      - Expand user (~)
      - Make absolute
      - Resolve symlinks when possible (non-strict to avoid exceptions)
    """
    try:
        return str(Path(p).expanduser().absolute().resolve(strict=False))
    except Exception:
        # As a last resort, return the original string
        return str(p)

# ---------- Data model ----------

@dataclass
class _State:
    # Keep absolute/normalized paths only; UI should validate existence on use.
    recent: List[str]
    pinned: List[str]
    last_loaded: Optional[str] = None  # path of current/last loaded playlist

    @staticmethod
    def empty() -> "_State":
        return _State(recent=[], pinned=[], last_loaded=None)

# ---------- Manager ----------

class PlaylistManager:
    """
    Manages persistence for recent and pinned playlists.
    Limits:
      - recent: max 5 (MRU)
      - pinned: max 10 (user chosen)
    Public API intentionally small and unchanged.
    """

    def __init__(self, path: Optional[Path] = None, max_recent: int = 5, max_pinned: int = 10) -> None:
        self._max_recent = int(max_recent)
        self._max_pinned = int(max_pinned)

        config_dir = _ensure_app_dir()
        self._path = path or (config_dir / "playlists.json")

        self._state = self._load()

    # ---------- Public API (unchanged signatures) ----------

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
        self._state.last_loaded = _normalize_path(playlist_json_path)
        self._save()

    def add_recent(self, playlist_json_path: str) -> None:
        """
        Insert path at front of MRU list, dedupe, clamp size.
        """
        p = _normalize_path(playlist_json_path)
        items = [x for x in self._state.recent if x != p]
        items.insert(0, p)
        self._state.recent = items[: self._max_recent]
        self._save()

    def pin(self, playlist_json_path: str) -> None:
        """
        Add to pinned (front), dedupe, clamp size.
        """
        p = _normalize_path(playlist_json_path)
        items = [x for x in self._state.pinned if x != p]
        items.insert(0, p)
        self._state.pinned = items[: self._max_pinned]
        self._save()

    def unpin(self, playlist_json_path: str) -> None:
        p = _normalize_path(playlist_json_path)
        self._state.pinned = [x for x in self._state.pinned if x != p]
        self._save()

    # ---------- Storage ----------

    def _load(self) -> _State:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)

                # Normalize & lightly sanitize. We do not error if paths are gone.
                recent = [_normalize_path(p) for p in data.get("recent", []) if isinstance(p, str)]
                pinned = [_normalize_path(p) for p in data.get("pinned", []) if isinstance(p, str)]
                last_loaded = data.get("last_loaded") or None
                last_loaded = _normalize_path(last_loaded) if isinstance(last_loaded, str) else None

                # Optional light cleanup: drop obvious empties
                recent = [p for p in recent if p]
                pinned = [p for p in pinned if p]

                return _State(recent=recent, pinned=pinned, last_loaded=last_loaded)
        except Exception:
            # Corrupt or unreadable file → start fresh
            pass
        return _State.empty()

    def _save(self) -> None:
        data = {
            "recent": self._state.recent,
            "pinned": self._state.pinned,
            "last_loaded": self._state.last_loaded,
        }
        # Atomic write: write to temp file then replace
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", delete=False, dir=self._path.parent, encoding="utf-8") as tf:
                json.dump(data, tf, indent=2)
                tmp_name = tf.name
            os.replace(tmp_name, self._path)
        except Exception:
            # Not fatal for the app; we just skip persistence if it fails.
            try:
                # Best-effort cleanup of temp if replace failed
                if "tmp_name" in locals():
                    Path(tmp_name).unlink(missing_ok=True)  # type: ignore[attr-defined]
            except Exception:
                pass