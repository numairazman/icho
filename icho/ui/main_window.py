# icho/ui/main_window.py
# Main window for Icho with:
# - Open Files / Open Folder
# - Drag-and-drop of files/folders
# - Now Playing metadata panel (Title/Artist/Album) via mutagen
# - Seek + Volume + Prev/Next/Play/Pause/Stop
#
# NOTE: For album art we’ll do it in v1.2 (needs cover extraction/fetch).

from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QFileDialog, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QMessageBox, QFrame
)

from icho.player import AudioPlayer

# 3rd-party lib for audio tags (already in requirements.txt)
import mutagen
from icho import metadata

# Accept common audio extensions (lowercase)
AUDIO_EXTS = {".flac", ".mp3", ".wav", ".ogg", ".m4a"}


def ms_to_mmss(ms: int) -> str:
    """Convert milliseconds -> 'MM:SS'."""
    s = max(0, int(ms // 1000))
    m, s = divmod(s, 60)
    return f"{m:02d}:{s:02d}"


# ---------- Drag-and-drop list ----------
class DropList(QListWidget):
    """QListWidget subclass that accepts file/folder drag-and-drop."""
    def __init__(self, on_paths_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_paths = on_paths_callback
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.is_dir():
                    # Recursively add audio files from folders
                    for sub in p.rglob("*"):
                        if sub.suffix.lower() in AUDIO_EXTS:
                            paths.append(str(sub))
                else:
                    if p.suffix.lower() in AUDIO_EXTS:
                        paths.append(str(p))
            self._on_paths(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class MainWindow(QMainWindow):
    """Top-level window for Icho with metadata panel + folder import."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Icho — Local Music Player")
        self.resize(1000, 600)

        # Backend: single AudioPlayer instance
        self.player = AudioPlayer(self)

        # ------- Left: track list (drag & drop) -------
        self.list_widget = DropList(self._add_paths)
        self.list_widget.itemDoubleClicked.connect(self._play_selected_item)

        # ------- Right: controls + metadata -------
        self.play_btn = QPushButton("Play/Pause")
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        self.stop_btn = QPushButton("Stop")

        # Seek bar and time labels
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)  # Range updated when duration known
        self.time_label = QLabel("00:00 / 00:00")

        # Volume slider + label
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_value = QLabel("70%")

        # ------- Metadata panel (Now Playing) -------
        # Simple labels for now — album art will be added in v1.2
        self.now_playing_title = QLabel("—")
        self.now_playing_artist = QLabel("—")
        self.now_playing_album = QLabel("—")

        # Cover image label (fixed box; image will scale to fit)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150,150)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid #444; background: #1e1e1e;")
        self.cover_label.setText("No cover")

        # Slight style to separate the panel visually
        meta_box = QVBoxLayout()
        meta_header = QLabel("Now Playing")
        meta_header.setStyleSheet("font-weight: 600;")

        # grid of text rows
        grid = QVBoxLayout()
        row1 = QHBoxLayout(); row1.addWidget(QLabel("Title:"));  row1.addWidget(self.now_playing_title, 1)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("Artist:")); row2.addWidget(self.now_playing_artist, 1)
        row3 = QHBoxLayout(); row3.addWidget(QLabel("Album:"));  row3.addWidget(self.now_playing_album, 1)
        grid.addLayout(row1); grid.addLayout(row2); grid.addLayout(row3)

        # NEW: art + text side by side
        art_and_text = QHBoxLayout()
        art_and_text.addWidget(self.cover_label)
        art_and_text.addLayout(grid, 1)

        meta_box.addWidget(meta_header)
        meta_box.addLayout(art_and_text)

        # Thin separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)

        # ------- Assemble right side -------
        right = QVBoxLayout()

        # Controls row
        row_controls = QHBoxLayout()
        for b in (self.prev_btn, self.play_btn, self.next_btn, self.stop_btn):
            row_controls.addWidget(b)
        right.addLayout(row_controls)

        # Seek row
        row_seek = QHBoxLayout()
        row_seek.addWidget(self.position_slider, 1)
        row_seek.addWidget(self.time_label)
        right.addLayout(row_seek)

        # Volume row
        row_vol = QHBoxLayout()
        row_vol.addWidget(QLabel("Volume"))
        row_vol.addWidget(self.volume_slider, 1)
        row_vol.addWidget(self.volume_value)
        right.addLayout(row_vol)

        # Separator + metadata panel
        right.addWidget(sep)
        right.addLayout(meta_box)

        # Spacer
        right.addStretch(1)

        # ------- Main horizontal split (list on left, controls on right) -------
        main = QHBoxLayout()
        main.addWidget(self.list_widget, 1)
        right_box = QWidget(); right_box.setLayout(right)
        main.addWidget(right_box, 1)

        container = QWidget(); container.setLayout(main)
        self.setCentralWidget(container)

        # Build menubar + shortcuts
        self._build_menu()

        # ------- Wire UI events to backend -------
        self.play_btn.clicked.connect(self.player.toggle_play)
        self.prev_btn.clicked.connect(self.player.previous)
        self.next_btn.clicked.connect(self.player.next)
        self.stop_btn.clicked.connect(self.player.stop)

        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.position_slider.sliderMoved.connect(self.player.seek)

        # ------- Backend -> UI updates -------
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.trackChanged.connect(self._on_track_changed)  # update list + metadata
        self.player.errorOccurred.connect(self._on_error)

        # Initial volume apply
        self._on_volume_changed(self.volume_slider.value())

    # -------------------- Menus & actions --------------------
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        act_open_files = QAction("Open &Files...", self)
        act_open_files.setShortcut(QKeySequence("Ctrl+O"))
        act_open_files.triggered.connect(self._open_files_dialog)

        act_open_folder = QAction("Open &Folder...", self)
        act_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_folder.triggered.connect(self._open_folder_dialog)

        act_clear = QAction("&Clear Playlist", self)
        act_clear.triggered.connect(self._clear_playlist)

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        file_menu.addActions([act_open_files, act_open_folder, act_clear, act_quit])

        # -------- NEW: Tools menu --------
        tools = self.menuBar().addMenu("&Tools")

        act_tag_current = QAction("Auto-tag Current (title/artist/album + cover)", self)
        act_tag_current.triggered.connect(self._auto_tag_current)

        act_tag_all = QAction("Auto-tag All in Playlist", self)
        act_tag_all.triggered.connect(self._auto_tag_all)

        tools.addActions([act_tag_current, act_tag_all])

        help_menu = self.menuBar().addMenu("&Help")
        act_about = QAction("&About", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    # -------------------- File dialogs --------------------
    def _open_files_dialog(self) -> None:
        """Allow the user to pick multiple audio files at once."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open audio files",
            str(Path.home()),
            "Audio Files (*.flac *.mp3 *.wav *.ogg *.m4a);;All Files (*)",
        )
        self._add_paths(paths)

    def _open_folder_dialog(self) -> None:
        """Select a folder and import all supported audio files (recursive)."""
        folder = QFileDialog.getExistingDirectory(self, "Open folder", str(Path.home()))
        if not folder:
            return
        p = Path(folder)
        paths = [str(sub) for sub in p.rglob("*") if sub.suffix.lower() in AUDIO_EXTS]
        self._add_paths(paths)

    # -------------------- Playlist handling --------------------
    def _add_paths(self, paths: Iterable[str]) -> None:
        """Add given paths to the playlist and visually list them on the left."""
        if not paths:
            return
        paths = list(dict.fromkeys(paths))  # de-duplicate, preserve order
        self.player.add_files(paths)

        # Avoid duplicates in the visible list while preserving order
        known = {self.list_widget.item(i).data(Qt.UserRole) for i in range(self.list_widget.count())}
        for p in paths:
            if p not in known:
                item = QListWidgetItem(Path(p).name)
                item.setToolTip(p)           # Full path on hover
                item.setData(Qt.UserRole, p) # Store the path with the item
                self.list_widget.addItem(item)

    def _clear_playlist(self) -> None:
        self.player.clear()
        self.list_widget.clear()
        self.position_slider.setRange(0, 0)
        self.time_label.setText("00:00 / 00:00")
        self._set_metadata("-", "-", "-")
        self._set_cover(None)

    # -------------------- UI updates --------------------
    def _on_volume_changed(self, value: int) -> None:
        self.player.set_volume(value)
        self.volume_value.setText(f"{value}%")

    def _on_position_changed(self, pos_ms: int) -> None:
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(pos_ms)
        self.position_slider.blockSignals(False)
        self._update_time_label(pos_ms, self.player.duration())

    def _on_duration_changed(self, dur_ms: int) -> None:
        self.position_slider.setRange(0, max(0, int(dur_ms)))
        self._update_time_label(self.player.position(), dur_ms)

    def _on_track_changed(self, path: str) -> None:
        # highlight current item
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.UserRole) == path:
                self.list_widget.setCurrentRow(i)
                break

        # refresh text metadata
        title, artist, album = self._read_tags(path)
        self._set_metadata(title, artist, album)

        # ✅ refresh cover image on every track change
        cover = self._read_cover_bytes(path)
        self._set_cover(cover)

    def _update_time_label(self, pos_ms: int, dur_ms: int) -> None:
        self.time_label.setText(f"{ms_to_mmss(pos_ms)} / {ms_to_mmss(dur_ms)}")

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Playback Error", msg or "Unknown error")

    # -------------------- Interactions --------------------
    def _play_selected_item(self, item: QListWidgetItem) -> None:
        """
        When user double-clicks a track:
        - Find that path in the internal playlist
        - Rotate playlist so that item becomes current
        - Start playing
        """
        target_path = item.data(Qt.UserRole)
        playlist = self.player.playlist()
        if target_path in playlist:
            idx = playlist.index(target_path)
            rotated = playlist[idx:] + playlist[:idx]  # bring target to front
            self.player.clear()
            self.player.add_files(rotated)
            self.player.play()

    def _about(self) -> None:
        QMessageBox.information(
            self, "About Icho",
            "Icho v1.0 — a lightweight, local music player.\n"
            "Now with Open Folder, drag-and-drop, and a Now Playing metadata panel."
        )

    # -------------------- Metadata helpers --------------------
    def _read_tags(self, path: str) -> tuple[str, str, str]:
        """
        Read (title, artist, album) from file tags using mutagen.
        Falls back to filename if tags are missing.
        """
        title = Path(path).stem
        artist = "-"
        album = "-"

        try:
            m = mutagen.File(path, easy=True)  # easy=True returns a dict-like
            if m:
                # Each tag returns a list; take the first value when present
                title = (m.get("title", [title]) or [title])[0]
                artist = (m.get("artist", ["-"]) or ["-"])[0]
                album = (m.get("album", ["-"]) or ["-"])[0]
        except Exception:
            # If mutagen fails, keep fallbacks
            pass

        # Guarantee strings (mutagen can return bytes sometimes)
        return str(title), str(artist), str(album)

    def _set_metadata(self, title: str, artist: str, album: str) -> None:
        """Update labels in the Now Playing panel (safe for None/empty)."""
        self.now_playing_title.setText(title or "-")
        self.now_playing_artist.setText(artist or "-")
        self.now_playing_album.setText(album or "-")

    def _current_path(self) -> Optional[str]:
        """Return filesystem path of currently-selected/playing item, or None."""
        item = self.list_widget.currentItem()
        return None if item is None else item.data(Qt.UserRole)
    
    def _run_autotag_single(self, path: str) -> None:
        """
        Run the autotag pipeline for a single file, then refresh the UI.
        - Calls icho.metadata.autotag(path)
        - Updates the Now Playing panel with the new tags and cover
        """
        try:
            res = metadata.autotag(path)
        except Exception as e:
            QMessageBox.warning(self, "Auto-tag", f"Failed: {e}")
            return

        # Refresh visible metadata and cover for the current item
        t, ar, al = self._read_tags(path)
        self._set_metadata(t, ar, al)
        self._set_cover(self._read_cover_bytes(path))

        # Optional: tell the user what happened
        if res.get("ok"):
            msg = "Updated tags"
            if res.get("had_cover"):
                msg += " + embedded cover"
            QMessageBox.information(self, "Auto-tag", msg + ".")
        else:
            QMessageBox.information(self, "Auto-tag", "No changes made.")

    def _auto_tag_current(self) -> None:
        path = self._current_path()
        if not path:
            QMessageBox.information(self, "Auto-tag", "Select a track first.")
            return
        self._run_autotag_single(path)

    def _auto_tag_all(self) -> None:
        if self.list_widget.count() == 0:
            QMessageBox.information(self, "Auto-tag", "Playlist is empty.")
            return
        changed = 0
        for i in range(self.list_widget.count()):
            p = self.list_widget.item(i).data(Qt.UserRole)
            res = metadata.autotag(p)
            changed += 1 if res.get("ok") else 0
        # Refresh current item's panel
        cur = self._current_path()
        if cur:
            t, ar, al = self._read_tags(cur)
            self._set_metadata(t, ar, al)
            self._set_cover(self._read_cover_bytes(cur))  # ✅
        QMessageBox.information(self, "Auto-tag", f"Finished. Updated {changed} file(s).")
        


    def _read_cover_bytes(self, path: str) -> bytes | None:
        """
        Return embedded cover image bytes from path (mp3/flac/m4a) or None.
        """
        try:
            ext = Path(path).suffix.lower()
            if ext == ".mp3":
                from mutagen.id3 import ID3, APIC
                id3 = ID3(path)
                # choose the first APIC (front cover usually type=3)
                for frame in id3.getall("APIC"):
                    if isinstance(frame, APIC):
                        return bytes(frame.data)
                return None
            elif ext == ".flac":
                from mutagen.flac import FLAC
                f = FLAC(path)
                if f.pictures:
                    # pick first picture (front cover typically type=3)
                    return bytes(f.pictures[0].data)
                return None
            elif ext == ".m4a":
                from mutagen.mp4 import MP4, MP4Cover
                mp4 = MP4(path)
                covr = mp4.tags.get("covr") if mp4.tags else None
                if covr:
                    # MP4 stores a list of MP4Cover objects
                    return bytes(covr[0])
                return None
        except Exception:
            return None

    def _set_cover(self, img_bytes: bytes | None) -> None:
        """Display the image bytes in the cover label; fall back to placeholder."""
        if img_bytes:
            pix = QPixmap()
            if pix.loadFromData(img_bytes):
                # scale to the label box, preserve aspect
                scaled = pix.scaled(
                    self.cover_label.width(),
                    self.cover_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.cover_label.setPixmap(scaled)
                self.cover_label.setText("")  # clear placeholder text
                return
        # no image or failed to load
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("No cover")
