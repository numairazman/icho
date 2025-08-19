# icho/player.py
# Full-featured AudioPlayer for Icho (PySide6)
# - Restores previous()/next()/seek(), playlist, and signals
# - Pylance-friendly: no "qlonglong" in @Slot, safe enum -> int conversion

from typing import List
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


def _enum_to_int(e) -> int:
    """Robustly convert Qt/Python enums to int (handles .value)."""
    try:
        return int(e)
    except (TypeError, ValueError):
        return int(getattr(e, "value", 0))

# Cache the "playing" state as an int (Pylance-safe, with fallback)
try:
    _PLAYING_INT = _enum_to_int(QMediaPlayer.PlaybackState.PlayingState)  # type: ignore[attr-defined]
except Exception:
    _PLAYING_INT = 1  # Qt currently uses 1 for PlayingState


class AudioPlayer(QObject):
    """
    Thin wrapper over QMediaPlayer with a simple in-memory playlist.

    Signals:
        trackChanged(str)     - path of the current track
        positionChanged(int)  - ms
        durationChanged(int)  - ms
        stateChanged(int)     - QMediaPlayer.PlaybackState as int
        errorOccurred(str)    - human-readable error message
    """
    trackChanged = Signal(str)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    stateChanged = Signal(int)
    errorOccurred = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Backend objects
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)

        # In-memory playlist
        self._playlist: List[str] = []
        self._index: int = -1  # -1 => nothing selected

        # Forward Qt signals via small slots (avoid Signal->Signal direct connect)
        self._player.positionChanged.connect(self._forward_position)
        self._player.durationChanged.connect(self._forward_duration)
        self._player.playbackStateChanged.connect(self._forward_state)
        self._player.errorOccurred.connect(self._forward_error)

    # ---------------- Playlist management ----------------
    def clear(self) -> None:
        """Stop playback and empty the playlist."""
        self.stop()
        self._playlist.clear()
        self._index = -1

    def add_files(self, paths: List[str]) -> None:
        """
        Add one or more files to the playlist.
        If nothing is selected yet, auto-select the first so the UI can play.
        """
        self._playlist.extend(paths)
        if self._index == -1 and self._playlist:
            self._index = 0
            self._load_current()

    def playlist(self) -> List[str]:
        """Return a shallow copy of the playlist."""
        return list(self._playlist)

    # ---------------- Volume ----------------
    def set_volume(self, percent: int) -> None:
        """Set output volume (0..100)."""
        percent = max(0, min(100, int(percent)))
        self._audio.setVolume(percent / 100.0)

    # ---------------- Core controls ----------------
    def _load_current(self) -> None:
        """Load current index into QMediaPlayer and emit trackChanged."""
        if 0 <= self._index < len(self._playlist):
            path = self._playlist[self._index]
            self._player.setSource(QUrl.fromLocalFile(path))
            self.trackChanged.emit(path)

    def play(self) -> None:
        """Start or resume playback. Auto-load first track if needed."""
        if self._player.source().isEmpty() and self._playlist:
            self._load_current()
        self._player.play()

    def pause(self) -> None:
        """Pause playback."""
        self._player.pause()

    def toggle_play(self) -> None:
        """Toggle play/pause without relying on enum names (Pylance-safe)."""
        if _enum_to_int(self._player.playbackState()) == _PLAYING_INT:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        """Stop playback and reset position to 0."""
        self._player.stop()

    def seek(self, ms: int) -> None:
        """Seek to absolute position in ms."""
        self._player.setPosition(max(0, int(ms)))

    def next(self) -> None:
        """Advance to next track (wrap-around)."""
        if self._playlist:
            self._index = (self._index + 1) % len(self._playlist)
            self._load_current()
            self.play()

    def previous(self) -> None:
        """Go to previous track (wrap-around)."""
        if self._playlist:
            self._index = (self._index - 1) % len(self._playlist)
            self._load_current()
            self.play()

    # ---------------- Info ----------------
    def duration(self) -> int:
        """Current track duration (ms)."""
        try:
            return int(self._player.duration() or 0)
        except TypeError:
            return 0

    def position(self) -> int:
        """Current playback position (ms)."""
        try:
            return int(self._player.position() or 0)
        except TypeError:
            return 0

    # ---------------- Qt -> our signals (forwarders) ----------------
    @Slot(int)  # accept int; Qt converts qint64 -> int for Python
    def _forward_position(self, pos_ms: int) -> None:
        self.positionChanged.emit(int(pos_ms))

    @Slot(int)
    def _forward_duration(self, dur_ms: int) -> None:
        self.durationChanged.emit(int(dur_ms))

    @Slot(object)
    def _forward_state(self, state_obj) -> None:
        self.stateChanged.emit(_enum_to_int(state_obj))

    @Slot(object)
    def _forward_error(self, *args) -> None:
        """Normalize error payloads to a single friendly string."""
        if len(args) == 2:
            _, err_str = args
            self.errorOccurred.emit(str(err_str))
        elif len(args) == 1:
            self.errorOccurred.emit(f"Playback error: {args[0]}")
        else:
            self.errorOccurred.emit("Unknown playback error.")
    # --- NEW: expose current index / track ---------------------------------
    def current_index(self) -> int:
        """Return the 0-based index of the current track, or -1 if none selected."""
        return int(self._index)

    def current_track(self) -> str | None:
        """Return the current track path or None if nothing is selected."""
        if 0 <= self._index < len(self._playlist):
            return self._playlist[self._index]
        return None

    # --- NEW: set the entire playlist (for Load Playlist) -------------------
    def set_playlist(self, paths: list[str], start_index: int = 0) -> None:
        """
        Replace the entire playlist and optionally set a starting index.
        The player will load (but not auto-play) the selected track.
        """
        self.stop()
        self._playlist = list(paths)
        if not self._playlist:
            self._index = -1
            # Clear any loaded source to avoid showing stale metadata
            self._player.setSource(QUrl())  # type: ignore[arg-type]
            return

        # Clamp index into valid range
        self._index = max(0, min(int(start_index), len(self._playlist) - 1))
        self._load_current()  # emits trackChanged

