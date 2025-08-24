
# icho/player.py
# Full-featured AudioPlayer for Icho (PySide6)
# Version: 1.5 (Albums view, Play Next queue, manual tag editing)
# - Restores previous()/next()/seek(), playlist, and signals
# - Pylance-friendly: no "qlonglong" in @Slot, safe enum -> int conversion


from PySide6.QtCore import QObject, Signal, QTimer
import vlc
import random

class AudioPlayer(QObject):
    """
    VLC-based audio player for Icho. Handles playlist, playback, and emits signals for UI updates.
    """
    trackChanged = Signal(str)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    stateChanged = Signal(int)
    errorOccurred = Signal(str)
    playbackEnded = Signal()
    upcomingChanged = Signal()  # emitted whenever upcoming order changes

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._player = None
        self._playlist = []
        self._index = -1
        self._poll_timer = None
        self._history = []  # stack of previous indices for shuffle mode
        self._upcoming_indices = []  # indices (into _playlist) representing upcoming play order
        self._last_shuffle = False   # last shuffle state used to build upcoming
        self._manual_next = []  # list of indices manually queued to play next (in order)


    # -------------------- Upcoming (Auto-Queue) Management --------------------
    def rebuild_upcoming(self, shuffle: bool) -> None:
        """Rebuild the upcoming track index list based on current playlist/index and shuffle state."""
        self._last_shuffle = shuffle
        if not self._playlist or not (0 <= self._index < len(self._playlist)):
            self._upcoming_indices = []
            self.upcomingChanged.emit()
            return
        remaining = [i for i in range(len(self._playlist)) if i != self._index]
        if shuffle:
            random.shuffle(remaining)
        else:
            # Keep only tracks AFTER the current one (no wrap) for linear order
            remaining = [i for i in range(self._index + 1, len(self._playlist))]
        self._upcoming_indices = remaining
        self.upcomingChanged.emit()

    def upcoming_tracks(self) -> list:
        return [self._playlist[i] for i in self._upcoming_indices]

    def remove_upcoming(self, position: int) -> None:
        if 0 <= position < len(self._upcoming_indices):
            self._upcoming_indices.pop(position)
            self.upcomingChanged.emit()

    def clear_upcoming(self) -> None:
        self._upcoming_indices.clear()
        self.upcomingChanged.emit()

    def add_to_upcoming(self, paths: list[str]) -> None:
        """Append given track paths to the upcoming order.
        If a path is not yet in the playlist, append it to the playlist first.
        Current track is never duplicated; duplicates in upcoming are avoided preserving first occurrence order."""
        changed = False
        for p in paths:
            if p == self.current_track():
                continue
            if p in self._playlist:
                idx = self._playlist.index(p)
            else:
                # Append new track to playlist
                self._playlist.append(p)
                idx = len(self._playlist) - 1
                changed = True
            # Avoid duplicate scheduling
            if idx == self._index:
                continue
            if idx not in self._upcoming_indices:
                self._upcoming_indices.append(idx)
                changed = True
        if changed:
            self.upcomingChanged.emit()

    def peek_next(self, shuffle: bool = False) -> str | None:
        """Return the path that would play if next() were called now.
        For shuffle: returns first upcoming (building if empty). For linear: next index with wrap.
        Returns None if no valid next track (playlist empty or single-track edge where wrap would repeat)."""
        if not self._playlist:
            return None
        # Manual overrides take priority
        if self._manual_next:
            idx = self._manual_next[0]
            if 0 <= idx < len(self._playlist):
                return self._playlist[idx]
        if shuffle:
            # Ensure upcoming list exists (mirrors logic that next() will use)
            if not self._upcoming_indices:
                self.rebuild_upcoming(True)
            if self._upcoming_indices:
                return self._playlist[self._upcoming_indices[0]]
            return None
        # linear
        if len(self._playlist) <= 1:
            return None
        nxt_idx = self._index + 1 if self._index + 1 < len(self._playlist) else 0
        return self._playlist[nxt_idx]
    
    def set_volume(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        if self._player:
            self._player.audio_set_volume(percent)

    def _load_current(self) -> None:
        if 0 <= self._index < len(self._playlist):
            path = self._playlist[self._index]
            self._player = vlc.MediaPlayer(path)
            self.trackChanged.emit(path)

    def play(self) -> None:
        if self._player is None and self._playlist and 0 <= self._index < len(self._playlist):
            self._load_current()
        if self._player:
            self._player.play()
            self._start_polling()

    def pause(self) -> None:
        if self._player:
            self._player.pause()
            self._stop_polling()

    def toggle_play(self) -> None:
        if self._player and self._player.is_playing():
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        if self._player:
            self._player.stop()
            self._stop_polling()

    def seek(self, ms: int) -> None:
        if self._player:
            self._player.set_time(max(0, int(ms)))

    def next(self, shuffle=False) -> None:
        if not self._playlist:
            return
        self.stop()
        # Manual play-next overrides
        if self._manual_next:
            idx = self._manual_next.pop(0)
            if 0 <= idx < len(self._playlist):
                self._index = idx
                self._load_current()
                # Only rebuild upcoming if shuffle AND upcoming empty (to avoid losing manual list order for subsequent items)
                if shuffle and not self._manual_next and not self._upcoming_indices:
                    self.rebuild_upcoming(True)
                self.play()
                self.upcomingChanged.emit()
                return
        if shuffle:
            # If upcoming list exhausted, rebuild a new shuffle cycle (excluding current)
            if not self._upcoming_indices:
                self.rebuild_upcoming(True)
            if self._upcoming_indices:
                if 0 <= self._index < len(self._playlist):
                    self._history.append(self._index)
                self._index = self._upcoming_indices.pop(0)
        else:
            if self._index < len(self._playlist) - 1:
                self._index += 1
            else:
                self._index = 0
        self._load_current()
        # Rebuild upcoming (use current shuffle mode) excluding new current
        self.rebuild_upcoming(shuffle)
        self.play()

    def previous(self, shuffle=False) -> None:
        if not self._playlist:
            return
        self.stop()
        if shuffle and self._history:
            self._index = self._history.pop()
        else:
            self._index = (self._index - 1) % len(self._playlist)
        self._load_current()
        self.rebuild_upcoming(shuffle)
        self.play()

    def duration(self) -> int:
        try:
            if self._player:
                return int(self._player.get_length() or 0)
        except Exception:
            pass
        return 0

    def position(self) -> int:
        try:
            if self._player:
                return int(self._player.get_time() or 0)
        except Exception:
            pass
        return 0

    def playlist(self) -> list:
        return list(self._playlist)

    def clear(self) -> None:
        self.stop()
        self._playlist.clear()
        self._index = -1
        self._history.clear()
        self._upcoming_indices.clear()
        self._manual_next.clear()
        self.upcomingChanged.emit()

    def add_files(self, paths: list) -> None:
        self._playlist.extend(paths)
        if self._index == -1 and self._playlist:
            self._index = 0
            self._load_current()

    def current_index(self) -> int:
        return int(self._index)

    def current_track(self) -> str | None:
        if 0 <= self._index < len(self._playlist):
            return self._playlist[self._index]
        return None

    def set_playlist(self, paths: list, start_index: int = 0) -> None:
        self.stop()
        self._playlist = list(paths)
        if not self._playlist:
            self._index = -1
            return
        self._index = max(0, min(int(start_index), len(self._playlist) - 1))
        self._load_current()
        # Rebuild upcoming with last known shuffle mode
        self.rebuild_upcoming(self._last_shuffle)

    # -------------------- Manual Play Next --------------------
    def add_play_next(self, paths: list[str]) -> None:
        """Insert given track paths so they will play next (in provided order).
        Tracks are added to playlist if missing. Duplicates in the manual list are removed, preserving first occurrence.
        Current track is never inserted."""
        inserted_any = False
        new_indices = []
        for p in paths:
            if p == self.current_track():
                continue
            if p in self._playlist:
                idx = self._playlist.index(p)
            else:
                self._playlist.append(p)
                idx = len(self._playlist) - 1
            if idx == self._index:
                continue
            if idx not in new_indices and idx not in self._manual_next:
                new_indices.append(idx)
        if new_indices:
            # Prepend in order so first path ends up first to play
            self._manual_next = new_indices + self._manual_next
            inserted_any = True
        if inserted_any:
            self.upcomingChanged.emit()

    def manual_next_tracks(self) -> list[str]:
        return [self._playlist[i] for i in self._manual_next if 0 <= i < len(self._playlist)]

    def _start_polling(self):
        if self._poll_timer is not None:
            return
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_vlc)
        self._poll_timer.start(200)

    def _stop_polling(self):
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def _poll_vlc(self):
        pos = self.position()
        dur = self.duration()
        self.positionChanged.emit(pos)
        self.durationChanged.emit(dur)
        if dur > 0 and pos >= dur:
            self.playbackEnded.emit()
