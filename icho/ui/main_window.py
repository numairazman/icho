# icho/ui/main_window.py
# Main window for Icho with:

import json
import os
from pathlib import Path
from typing import Iterable, Optional, Dict

from PySide6.QtCore import Qt, QSettings, Slot
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QPalette, QColor
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QFileDialog, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QMessageBox, QFrame, QApplication, QLineEdit
)

from icho.player import AudioPlayer
from icho.playlists import PlaylistManager
from icho.metadata import autotag

# 3rd-party lib for audio tags (already in requirements.txt)
import mutagen

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
    """Top-level window for Icho with metadata panel, library, playlists, and playback controls."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Icho")
        self.resize(1200, 700)

        # Shuffle and repeat controls
        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.setCheckable(True)
        self.repeat_btn = QPushButton("Repeat")
        self.repeat_btn.setCheckable(True)
        self.shuffle_enabled = False
        self.repeat_enabled = False

        # Backend: single AudioPlayer instance
        self.player = AudioPlayer(self)

        # Persistent playlist manager (recent + pinned) MUST exist before menus
        self.playlist_mgr = PlaylistManager()

        # --- THEME: settings + palettes (do NOT apply yet; cover_label/meta_header not created) ---
        self._settings = QSettings("Icho", "Icho")
        self._init_palettes()
        saved_theme = str(self._settings.value("theme", "dark"))

        # Library system state
        raw_folder = self._settings.value("library_folder", None)
        self.library_folder = str(raw_folder) if raw_folder else None
        self.library_tracks: list[str] = []
        self.album_index: Dict[str, list[str]] = {}
        self.current_album: Optional[str] = None
        if self.library_folder:
            folder = Path(self.library_folder)
            if folder.exists():
                self.library_tracks = [str(sub) for sub in folder.rglob("*") if sub.suffix.lower() in AUDIO_EXTS]
                self._build_album_index()

        # We'll rebuild this "Playlists" menu dynamically; keep a handle to it.
        self.menu_playlists = None  # type: ignore

        # ------- Sidebar: Library, Albums & Playlists -------
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(220)
        self.sidebar.addItem(QListWidgetItem("Library"))
        self.sidebar.addItem(QListWidgetItem("Albums"))
        self.sidebar.addItem(QListWidgetItem("Current Playlist"))
        self.sidebar.setCurrentRow(1)  # Default to playlist view
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)

        # ------- Library search box -------
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search by title or artist...")
        self.library_search.textChanged.connect(self._on_library_search)

        # ------- Track list (drag & drop) -------
        self.list_widget = DropList(self._add_paths)
        self.list_widget.itemDoubleClicked.connect(self._play_selected_item)

        # ------- Right: controls + metadata -------
        self.play_btn = QPushButton("Play/Pause")
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        self.stop_btn = QPushButton("Stop")

        # Seek bar and time labels
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)  # Range updated when duration known
        self.time_label = QLabel("00:00 / 00:00")

        # Volume slider + label
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_value = QLabel("70%")

        # ------- Metadata panel (Now Playing) -------
        self.now_playing_title = QLabel("—")
        self.now_playing_artist = QLabel("—")
        self.now_playing_album = QLabel("—")

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150, 150)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setText("No cover")

        self.meta_header = QLabel("Now Playing")
        self.meta_header.setStyleSheet("font-weight: 600;")

        self._apply_theme(saved_theme)

        meta_box = QVBoxLayout()
        meta_box.addWidget(self.meta_header)

        grid = QVBoxLayout()
        row1 = QHBoxLayout(); row1.addWidget(QLabel("Title:"));  row1.addWidget(self.now_playing_title, 1)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("Artist:")); row2.addWidget(self.now_playing_artist, 1)
        row3 = QHBoxLayout(); row3.addWidget(QLabel("Album:"));  row3.addWidget(self.now_playing_album, 1)
        grid.addLayout(row1); grid.addLayout(row2); grid.addLayout(row3)

        art_and_text = QHBoxLayout()
        art_and_text.addWidget(self.cover_label)
        art_and_text.addLayout(grid, 1)

        meta_box.addLayout(art_and_text)
        # Up Next label
        self.up_next_label = QLabel("Up Next: —")
        _f = self.up_next_label.font(); _f.setItalic(True); self.up_next_label.setFont(_f)
        meta_box.addWidget(self.up_next_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        right = QVBoxLayout()
        row_controls = QHBoxLayout()
        for b in (self.prev_btn, self.play_btn, self.next_btn, self.stop_btn, self.shuffle_btn, self.repeat_btn):
            row_controls.addWidget(b)
        right.addLayout(row_controls)

        row_seek = QHBoxLayout()
        row_seek.addWidget(self.position_slider, 1)
        row_seek.addWidget(self.time_label)
        right.addLayout(row_seek)

        row_vol = QHBoxLayout()
        row_vol.addWidget(QLabel("Volume"))
        row_vol.addWidget(self.volume_slider, 1)
        row_vol.addWidget(self.volume_value)
        right.addLayout(row_vol)

        right.addWidget(sep)
        right.addLayout(meta_box)
        right.addStretch(1)

        # ------- Main horizontal split (sidebar, list, controls) -------
        library_box = QVBoxLayout()
        library_box.addWidget(self.library_search)
        library_box.addWidget(self.list_widget, 1)
        library_widget = QWidget(); library_widget.setLayout(library_box)

        main = QHBoxLayout()
        main.addWidget(self.sidebar)
        main.addWidget(library_widget, 1)
        right_box = QWidget(); right_box.setLayout(right)
        main.addWidget(right_box, 1)

        container = QWidget(); container.setLayout(main)
        self.setCentralWidget(container)

        self._build_menu()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        act_play_next = QAction("Play Next", self)
        act_play_next.triggered.connect(self._add_to_queue_selected)
        self.list_widget.addAction(act_play_next)

        # Connect signals
        self.play_btn.clicked.connect(self.player.toggle_play)
        self.prev_btn.clicked.connect(self._on_prev_clicked)
        self.next_btn.clicked.connect(self._on_next_clicked)
        self.stop_btn.clicked.connect(self.player.stop)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.position_slider.sliderMoved.connect(self.player.seek)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.errorOccurred.connect(self._on_error)
        self.shuffle_btn.toggled.connect(self._on_shuffle_toggled)
        self.repeat_btn.toggled.connect(self._on_repeat_toggled)
        self.player.stateChanged.connect(self._on_player_state_changed)
        self.player.playbackEnded.connect(self._on_playback_ended)
        if hasattr(self.player, 'upcomingChanged'):
            self.player.upcomingChanged.connect(self._update_up_next)
        if hasattr(self, '_update_up_next'):
            self._update_up_next()
        if self.library_folder:
            self.sidebar.setCurrentRow(0)
            self._show_library()
        else:
            self.sidebar.setCurrentRow(1)

    def _show_queue_dialog(self):
        """Show a dialog listing the upcoming tracks (auto-queue)."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Upcoming")
        layout = QVBoxLayout()
        queue_list = QListWidget()
        # Populate list from player's upcoming_tracks
        for p in getattr(self.player, 'upcoming_tracks', lambda: [])():
            title, artist, _ = self._read_tags(p)
            display = f"{title} — {artist}" if title else p
            it = QListWidgetItem(display)
            it.setData(Qt.ItemDataRole.UserRole, p)
            queue_list.addItem(it)
        layout.addWidget(queue_list)
        btns = QHBoxLayout()
        btn_remove = QPushButton("Remove Selected")
        btn_clear = QPushButton("Clear Upcoming")
        btn_close = QPushButton("Close")
        btns.addWidget(btn_remove)
        btns.addWidget(btn_clear)
        btns.addWidget(btn_close)
        layout.addLayout(btns)
        dlg.setLayout(layout)
        def remove_selected():
            idx = queue_list.currentRow()
            if idx >= 0:
                # Remove upcoming; adapt if method exists
                if hasattr(self.player, 'remove_upcoming'):
                    self.player.remove_upcoming(idx)
                queue_list.takeItem(idx)
        def clear_queue():
            if hasattr(self.player, 'clear_upcoming'):
                self.player.clear_upcoming()
            queue_list.clear()
        # Double-click an item to remove it immediately
        def on_item_double_clicked(item: QListWidgetItem):  # type: ignore[name-defined]
            row = queue_list.row(item)
            if row >= 0:
                if hasattr(self.player, 'remove_upcoming'):
                    self.player.remove_upcoming(row)
                queue_list.takeItem(row)
        btn_remove.clicked.connect(remove_selected)
        btn_clear.clicked.connect(clear_queue)
        btn_close.clicked.connect(dlg.accept)
        queue_list.itemDoubleClicked.connect(on_item_double_clicked)
        dlg.exec()
    def _on_library_search(self, text: str):
        self._render_library_list(text)

    def _select_library_folder(self):
        """Prompt user to select a folder as the music library."""
        folder = QFileDialog.getExistingDirectory(self, "Select Library Folder", str(Path.home()))
        if not folder:
            return
        self.library_folder = folder
        self.library_tracks = [str(sub) for sub in Path(folder).rglob("*") if sub.suffix.lower() in AUDIO_EXTS]
        self._build_album_index()
        self._settings.setValue("library_folder", folder)
        self.sidebar.setCurrentRow(0)
        self._show_library()
    def _on_sidebar_clicked(self, item):
        """Switch between Library, Albums, and Playlist views."""
        txt = item.text()
        if txt == "Library":
            self.current_album = None
            self._show_library()
        elif txt == "Albums":
            self._show_albums()
        else:  # Current Playlist
            self.current_album = None
            self._show_playlist()

    def _show_library(self):
        self._render_library_list()
        self.current_album = None
        try:
            self.list_widget.itemDoubleClicked.disconnect()
        except Exception:
            pass
        self.list_widget.itemDoubleClicked.connect(self._play_selected_library_item)

    def _build_album_index(self) -> None:
        """Build mapping album -> list of track paths from library_tracks."""
        idx: Dict[str, list[str]] = {}
        for p in self.library_tracks:
            title, artist, album = self._read_tags(p)
            album_key = album if album and album != '-' else 'Unknown Album'
            idx.setdefault(album_key, []).append(p)
        # Keep track order stable (already in filesystem discovery order)
        self.album_index = idx

    def _show_albums(self):
        self.list_widget.clear()
        self.current_album = None
        # Show all album names
        albums = sorted(self.album_index.keys(), key=str.lower)
        for name in albums:
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, ('album', name))
            self.list_widget.addItem(it)
        # Wire double click
        try:
            self.list_widget.itemDoubleClicked.disconnect()
        except Exception:
            pass
        self.list_widget.itemDoubleClicked.connect(self._on_album_item_double_clicked)

    def _show_album_tracks(self, album: str):
        self.list_widget.clear()
        self.current_album = album
        back_item = QListWidgetItem("[All Albums]")
        self.list_widget.addItem(back_item)
        for p in self.album_index.get(album, []):
            title, artist, _ = self._read_tags(p)
            display = f"{title} — {artist}" if title else Path(p).name
            it = QListWidgetItem(display)
            it.setToolTip(p)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(it)
        try:
            self.list_widget.itemDoubleClicked.disconnect()
        except Exception:
            pass
        self.list_widget.itemDoubleClicked.connect(self._on_album_item_double_clicked)

    def _on_album_item_double_clicked(self, item: QListWidgetItem) -> None:  # type: ignore[name-defined]
        if self.current_album is None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple) and data and data[0] == 'album':
                self._show_album_tracks(data[1])
            return
        # In album tracks view
        if item.text() == "[All Albums]":
            self._show_albums()
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        # Set playlist to album-only tracks
        tracks = self.album_index.get(self.current_album, [])
        if not tracks:
            return
        if path in tracks:
            start_idx = tracks.index(path)
        else:
            start_idx = 0
        self.player.set_playlist(tracks, start_idx)
        self.player.play()
        if hasattr(self.player, 'rebuild_upcoming'):
            self.player.rebuild_upcoming(self.shuffle_enabled)
    def _render_library_list(self, filter_text: str = ""):
        self.list_widget.clear()
        filter_text = filter_text.strip().lower()
        for p in self.library_tracks:
            title, artist, _ = self._read_tags(p)
            display = f"{title} — {artist}" if title else Path(p).name
            if filter_text:
                if filter_text not in display.lower():
                    continue
            item = QListWidgetItem(display)
            item.setToolTip(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(item)

    def _play_selected_library_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            # Set playlist to all library tracks and start from selected track
            idx = self.library_tracks.index(path)
            self.player.set_playlist(self.library_tracks, idx)
            self.player.play()
            if hasattr(self.player, 'rebuild_upcoming'):
                self.player.rebuild_upcoming(self.shuffle_enabled)

    def _show_playlist(self):
        self.list_widget.clear()
        for p in self.player.playlist():
            title, artist, _ = self._read_tags(p)
            display = f"{title} — {artist}" if title else Path(p).name
            item = QListWidgetItem(display)
            item.setToolTip(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(item)
        # Ensure double-click plays from current playlist order
        try:
            self.list_widget.itemDoubleClicked.disconnect()
        except Exception:
            pass
        self.list_widget.itemDoubleClicked.connect(self._play_selected_item)

    def _on_shuffle_toggled(self, checked):
        self.shuffle_enabled = checked
        if hasattr(self.player, 'rebuild_upcoming'):
            self.player.rebuild_upcoming(self.shuffle_enabled)

    def _on_repeat_toggled(self, checked):
        self.repeat_enabled = checked

    def _on_player_state_changed(self, state):
        # Only update UI or handle errors here. Autoplay is handled by playbackEnded.
        pass

    def _play_random_track(self):
        # Use AudioPlayer's shuffle logic and history
        self.player.next()

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")

        act_open_files = QAction("Open &Files...", self)
        act_open_files.setShortcut(QKeySequence("Ctrl+O"))
        act_open_files.triggered.connect(self._open_files_dialog)

        act_open_folder = QAction("Open &Folder...", self)
        act_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_folder.triggered.connect(self._open_folder_dialog)

        act_save_pl = QAction("&Save Playlist (JSON)...", self)
        act_save_pl.setShortcut(QKeySequence("Ctrl+S"))
        act_save_pl.triggered.connect(self._save_playlist_json)

        act_load_pl = QAction("&Load Playlist (JSON)...", self)
        act_load_pl.setShortcut(QKeySequence("Ctrl+L"))
        act_load_pl.triggered.connect(self._load_playlist_json)

        # Playlists menu (move this up)
        self.menu_playlists = self.menuBar().addMenu("&Playlists")
        self.menu_playlists.addAction(act_save_pl)
        self.menu_playlists.addAction(act_load_pl)

        # Now create the Tools menu
        tools = self.menuBar().addMenu("&Tools")

        act_tag_current = QAction("Auto-tag Current (title/artist/album + cover)", self)
        act_tag_current.triggered.connect(self._auto_tag_current)

        act_tag_all = QAction("Auto-tag All in Playlist", self)
        act_tag_all.triggered.connect(self._auto_tag_all)

        act_fix_tag = QAction("Fix Auto-tag for Current", self)
        act_fix_tag.setToolTip("Re-run auto-tag on the current track and refresh its metadata/cover")
        act_fix_tag.triggered.connect(self._fix_auto_tag_current)

        act_edit_tags = QAction("Edit Tags / Cover...", self)
        act_edit_tags.setToolTip("Manually edit title/artist/album and replace cover art for the current track")
        act_edit_tags.triggered.connect(self._edit_tags_current)

        act_select_library = QAction("Select Library Folder...", self)
        act_select_library.triggered.connect(self._select_library_folder)

        act_view_queue = QAction("View Upcoming", self)
        act_view_queue.triggered.connect(self._show_queue_dialog)

        tools.addActions([
            act_tag_current,
            act_tag_all,
            act_fix_tag,
            act_edit_tags,
            act_select_library,
            act_view_queue,
        ])

        self.act_dark_mode = QAction("Dark Mode", self, checkable=True)
        self.act_dark_mode.setChecked(str(self._settings.value("theme", "dark")) == "dark")
        self.act_dark_mode.toggled.connect(
            lambda checked: self._apply_theme("dark" if checked else "light")
        )
        tools.addAction(self.act_dark_mode)

        # Add Help menu at the end
        help_menu = self.menuBar().addMenu("&Help")
        act_about = QAction("&About", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    def _add_to_queue_selected(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        paths = [it.data(Qt.ItemDataRole.UserRole) for it in selected if it.data(Qt.ItemDataRole.UserRole)]
        if hasattr(self.player, 'add_play_next'):
            self.player.add_play_next(paths)

    # Playlists menu (do not recreate or add actions here)


    def _rebuild_playlists_menu(self):
        # ...existing code for rebuilding playlists menu (placeholder)...
        pass

    def _on_prev_clicked(self):
        if self.shuffle_enabled:
            self.player.previous(shuffle=True)
        else:
            self.player.previous()

    def _on_next_clicked(self):
        if self.shuffle_enabled:
            self.player.next(shuffle=True)
        else:
            self.player.next()

    @Slot()
    def _on_playback_ended(self):
        self.player.stop()
        if self.repeat_enabled:
            self.player.next()
            self.player.play()
        elif self.shuffle_enabled:
            self._play_random_track()
        else:
            self.player.next()
            self.player.play()
    # ...existing code...

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
        known = {self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())}
        for p in paths:
            if p not in known:
                item = QListWidgetItem(Path(p).name)
                item.setToolTip(p)           # Full path on hover
                item.setData(Qt.ItemDataRole.UserRole, p) # Store the path with the item
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
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == path:
                self.list_widget.setCurrentRow(i)
                break

        # refresh text metadata
        title, artist, album = self._read_tags(path)
        self._set_metadata(title, artist, album)

        # refresh cover image on every track change
        cover = self._read_cover_bytes(path)
        self._set_cover(cover)
        if hasattr(self, '_update_up_next'):
            self._update_up_next()

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
        target_path = item.data(Qt.ItemDataRole.UserRole)
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
            "Icho v1.5 — a lightweight, local music player.\n"
            "Shuffle previous/history bug fixed: Previous now works correctly in shuffle mode.\n"
            "Now with Open Folder, drag-and-drop, Now Playing metadata panel, sidebar, library, playlists, search box, metadata display, autotag refresh, shuffle/repeat/autoplay, and more.\n\n"
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
            m = mutagen.File(path, easy=True)  # pyright: ignore[reportPrivateImportUsage] # easy=True returns a dict-like
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
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    # -------------------- Autotagging --------------------
    def _run_autotag_single(self, path: str) -> None:
        """
        Run the autotag pipeline for a single file, then refresh the UI.
        - Calls icho.metadata.autotag(path)
        - Updates the Now Playing panel with the new tags and cover
        """
        try:
            res = autotag(path)
        except Exception as e:
            QMessageBox.warning(self, "Auto-tag", f"Failed: {e}")
            return

        # Refresh visible metadata and cover for the current item
        t, ar, al = self._read_tags(path)
        self._set_metadata(t, ar, al)
        self._set_cover(self._read_cover_bytes(path))

        # Refresh visible list for this item
        self._refresh_list_item(path)

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

    def _fix_auto_tag_current(self) -> None:
        """Force re-run autotag on the current track and refresh its list/metadata display."""
        path = self._current_path()
        if not path:
            QMessageBox.information(self, "Auto-tag", "Select a track first.")
            return
        try:
            res = autotag(path)
        except Exception as e:
            QMessageBox.warning(self, "Auto-tag", f"Failed: {e}")
            return
        # Always refresh regardless of res.ok to "fix" display
        t, ar, al = self._read_tags(path)
        self._set_metadata(t, ar, al)
        self._set_cover(self._read_cover_bytes(path))
        self._refresh_list_item(path)
        if res.get("ok"):
            QMessageBox.information(self, "Auto-tag", "Re-applied tags.")
        else:
            QMessageBox.information(self, "Auto-tag", "No changes (already up to date).")

    def _edit_tags_current(self) -> None:
        """Open a dialog to manually edit title/artist/album and choose new cover for current track."""
        path = self._current_path()
        if not path:
            QMessageBox.information(self, "Edit Tags", "Select a track first.")
            return
        # Read current tags
        cur_title, cur_artist, cur_album = self._read_tags(path)
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton, QDialogButtonBox, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Tags / Cover")
        title_edit = QLineEdit(cur_title)
        artist_edit = QLineEdit(cur_artist)
        album_edit = QLineEdit(cur_album)
        cover_label = QLabel("(keep existing cover)")
        cover_label.setWordWrap(True)
        new_cover_bytes: bytes | None = None

        def choose_cover():
            nonlocal new_cover_bytes
            file, _ = QFileDialog.getOpenFileName(dlg, "Choose Image", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
            if not file:
                return
            try:
                with open(file, 'rb') as f:
                    new_cover_bytes = f.read()
                cover_label.setText(Path(file).name)
            except Exception as e:
                QMessageBox.warning(dlg, "Cover", f"Failed: {e}")

        cover_btn = QPushButton("Change Cover…")
        cover_btn.clicked.connect(choose_cover)

        form = QFormLayout()
        form.addRow("Title", title_edit)
        form.addRow("Artist", artist_edit)
        form.addRow("Album", album_edit)
        form.addRow("Cover", cover_btn)
        form.addRow("Selected", cover_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        dlg.setLayout(layout)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Write tags using mutagen
        try:
            ext = Path(path).suffix.lower()
            if ext == '.mp3':
                from mutagen.id3 import ID3  # type: ignore
                from mutagen.id3 import TIT2, TPE1, TALB, APIC  # type: ignore
                id3 = ID3(path)
                id3.delall('TIT2'); id3.add(TIT2(encoding=3, text=title_edit.text()))
                id3.delall('TPE1'); id3.add(TPE1(encoding=3, text=artist_edit.text()))
                id3.delall('TALB'); id3.add(TALB(encoding=3, text=album_edit.text()))
                if new_cover_bytes:
                    id3.delall('APIC')
                    id3.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=new_cover_bytes))
                id3.save()
            elif ext == '.flac':
                from mutagen.flac import FLAC, Picture
                f = FLAC(path)
                f['title'] = title_edit.text()
                f['artist'] = artist_edit.text()
                f['album'] = album_edit.text()
                if new_cover_bytes:
                    f.clear_pictures()
                    pic = Picture()
                    pic.type = 3
                    pic.mime = 'image/jpeg'
                    pic.desc = 'Cover'
                    pic.data = new_cover_bytes
                    f.add_picture(pic)
                f.save()
            elif ext == '.m4a':
                from mutagen.mp4 import MP4, MP4Cover  # type: ignore
                mp4 = MP4(path)
                if title_edit.text():
                    mp4['\xa9nam'] = [title_edit.text()]
                else:
                    mp4.pop('\xa9nam', None)
                if artist_edit.text():
                    mp4['\xa9ART'] = [artist_edit.text()]
                else:
                    mp4.pop('\xa9ART', None)
                if album_edit.text():
                    mp4['\xa9alb'] = [album_edit.text()]
                else:
                    mp4.pop('\xa9alb', None)
                if new_cover_bytes:
                    mp4['covr'] = [MP4Cover(new_cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                mp4.save()
            else:
                # Generic simple tags for other formats if supported
                audio = mutagen.File(path)  # type: ignore[attr-defined]
                if audio is not None:
                    audio['title'] = title_edit.text()
                    audio['artist'] = artist_edit.text()
                    audio['album'] = album_edit.text()
                    audio.save()
        except Exception as e:
            QMessageBox.warning(self, "Edit Tags", f"Failed to write tags: {e}")
            return

        # Refresh UI with new values
        self._set_metadata(title_edit.text(), artist_edit.text(), album_edit.text())
        if new_cover_bytes:
            self._set_cover(new_cover_bytes)
        else:
            self._set_cover(self._read_cover_bytes(path))
        self._refresh_list_item(path)
        QMessageBox.information(self, "Edit Tags", "Updated tags successfully.")

    def _auto_tag_all(self) -> None:
        if self.list_widget.count() == 0:
            QMessageBox.information(self, "Auto-tag", "Playlist is empty.")
            return
        changed = 0
        for i in range(self.list_widget.count()):
            p = self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            res = autotag(p)
            changed += 1 if res.get("ok") else 0
            self._refresh_list_item(p)
        # Refresh current item's panel
        cur = self._current_path()
        if cur:
            t, ar, al = self._read_tags(cur)
            self._set_metadata(t, ar, al)
            self._set_cover(self._read_cover_bytes(cur))
        QMessageBox.information(self, "Auto-tag", f"Finished. Updated {changed} file(s).")

    def _refresh_list_item(self, path: str) -> None:
        # Update the display text for the item matching path
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                title, artist, _ = self._read_tags(path)
                display = f"{title} — {artist}" if title else Path(path).name
                item.setText(display)
                break

    # -------------------- Cover helpers --------------------
    def _read_cover_bytes(self, path: str) -> bytes | None:
        """
        Return embedded cover image bytes from path (mp3/flac/m4a) or None.
        """
        try:
            ext = Path(path).suffix.lower()
            if ext == ".mp3":
                from mutagen.id3 import ID3, APIC # type: ignore
                id3 = ID3(path)
                # choose the first APIC (front cover usually type=3)
                for frame in id3.getall("APIC"):
                    if isinstance(frame, APIC):
                        return bytes(frame.data) # type: ignore
                return None
            elif ext == ".flac":
                from mutagen.flac import FLAC
                f = FLAC(path)
                if f.pictures:
                    # pick first picture (front cover typically type=3)
                    return bytes(f.pictures[0].data)
                return None
            elif ext == ".m4a":
                from mutagen.mp4 import MP4
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
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.cover_label.setPixmap(scaled)
                self.cover_label.setText("")  # clear placeholder text
                return
        # no image or failed to load
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("No cover")
    def _update_up_next(self) -> None:
        # Prefer a direct peek API if available
        nxt = None
        if hasattr(self.player, 'peek_next'):
            try:
                nxt = self.player.peek_next(self.shuffle_enabled)
            except Exception:
                nxt = None
        if not nxt and hasattr(self.player, 'upcoming_tracks'):
            up = self.player.upcoming_tracks()
            if up:
                nxt = up[0]
        if nxt:
            title, artist, _ = self._read_tags(nxt)
            disp = f"{title} — {artist}" if title else Path(nxt).name
            self.up_next_label.setText(f"Up Next: {disp}")
        else:
            self.up_next_label.setText("Up Next: —")

    # -------------------- Playlist Save/Load (JSON) --------------------
    def _save_playlist_json(self) -> None:
        """
        Save the current playlist to a JSON file:
        {
            "tracks": ["/abs/path1", "/abs/path2", ...],
            "current_index": 0
        }
        """
        # Collect current playlist + index from the backend
        tracks = self.player.playlist()
        idx = self.player.current_index()  # requires player.set of step #1

        if not tracks:
            QMessageBox.information(self, "Save Playlist", "Playlist is empty.")
            return

        # Choose where to save
        path, _ = QFileDialog.getSaveFileName(
            self, "Save playlist (JSON)", str(Path.home() / "playlist.json"),
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        # Ensure .json extension (nice to have)
        if not path.lower().endswith(".json"):
            path += ".json"

        # Build data and write
        data = {"tracks": tracks, "current_index": int(idx)}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Save Playlist", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Save Playlist", f"Failed to save:\n{e}")
            return

        # after successful save:
        self.playlist_mgr.add_recent(path)
        self.playlist_mgr.set_current(path)
        self._rebuild_playlists_menu()

    def _load_playlist_json(self) -> None:
        """
        Load a playlist from a JSON file. Missing files are skipped.
        Rebuild the UI list and select the saved current track.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Load playlist (JSON)", str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Load Playlist", f"Failed to read file:\n{e}")
            return

        # Validate schema
        tracks = data.get("tracks")
        start_index = int(data.get("current_index", 0))
        if not isinstance(tracks, list):
            QMessageBox.warning(self, "Load Playlist", "Invalid JSON: 'tracks' must be a list.")
            return

        # Filter out non-existent files to avoid errors when loading
        tracks = [str(t) for t in tracks if isinstance(t, str) and os.path.exists(t)]
        if not tracks:
            QMessageBox.information(self, "Load Playlist", "No valid files found in this playlist.")
            return

        # Replace backend playlist & set starting index (does not auto-play)
        self.player.set_playlist(tracks, start_index)

        # Rebuild the visible list on the left
        self.list_widget.clear()
        for p in tracks:
            item = QListWidgetItem(Path(p).name)
            item.setToolTip(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(item)

        # Highlight the current item (player emitted trackChanged already)
        current = self.player.current_track()
        if current:
            # refresh metadata + cover
            t, ar, al = self._read_tags(current)
            self._set_metadata(t, ar, al)
            self._set_cover(self._read_cover_bytes(current))

        QMessageBox.information(self, "Load Playlist", "Playlist loaded.")
        self.playlist_mgr.add_recent(path)
        self.playlist_mgr.set_current(path)
        self._rebuild_playlists_menu()

    # -------------------- Playlists menu actions --------------------
    def _pin_current_playlist(self) -> None:
        """
        Pins the last loaded/saved playlist (if any).
        """
        path = self.playlist_mgr.last_loaded()
        if not path:
            QMessageBox.information(self, "Pin Playlist", "Load or save a playlist first.")
            return
        self.playlist_mgr.pin(path)
        self._rebuild_playlists_menu()
        QMessageBox.information(self, "Pin Playlist", f"Pinned:\n{path}")

    def _unpin_current_playlist(self) -> None:
        """
        Unpins the last loaded/saved playlist (if present in pinned).
        """
        path = self.playlist_mgr.last_loaded()
        if not path:
            QMessageBox.information(self, "Unpin Playlist", "No current playlist to unpin.")
            return
        self.playlist_mgr.unpin(path)
        self._rebuild_playlists_menu()
        QMessageBox.information(self, "Unpin Playlist", f"Unpinned:\n{path}")

    def _load_playlist_path(self, json_path: str) -> None:
        """
        Load a playlist from a specific JSON path (used by Playlists menu items).
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Load Playlist", f"Failed to read file:\n{e}")
            return

        tracks = data.get("tracks")
        start_index = int(data.get("current_index", 0))
        if not isinstance(tracks, list):
            QMessageBox.warning(self, "Load Playlist", "Invalid JSON: 'tracks' must be a list.")
            return

        # Filter non-existent files
        tracks = [str(t) for t in tracks if isinstance(t, str) and os.path.exists(t)]
        if not tracks:
            QMessageBox.information(self, "Load Playlist", "No valid files found in this playlist.")
            return

        # Apply to backend
        self.player.set_playlist(tracks, start_index)

        # Rebuild visible list
        self.list_widget.clear()
        for p in tracks:
            item = QListWidgetItem(Path(p).name)
            item.setToolTip(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(item)

        # Update metadata + cover
        current = self.player.current_track()
        if current:
            t, ar, al = self._read_tags(current)
            self._set_metadata(t, ar, al)
            self._set_cover(self._read_cover_bytes(current))

        # Update MRU & "current"
        self.playlist_mgr.add_recent(json_path)
        self.playlist_mgr.set_current(json_path)
        self._rebuild_playlists_menu()

        QMessageBox.information(self, "Load Playlist", f"Loaded:\n{json_path}")

    # -------------------- Theme helpers --------------------
    def _init_palettes(self) -> None:
        """Prepare light and dark QPalettes once."""

        # --- Light palette (explicit white/black) ---
        light = QPalette()
        light.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.white)
        light.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        light.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        light.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
        light.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        light.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        light.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        light.setColor(QPalette.ColorRole.Button, QColor(245, 245, 245))
        light.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        light.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        light.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))     # nice blue
        light.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

        # --- Dark palette ---
        dark = QPalette()
        dark.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        dark.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        dark.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        self._palette_light = light
        self._palette_dark = dark

    def _apply_cover_style(self, dark: bool) -> None:
        """Give the cover box a theme‑appropriate background/border."""
        if dark:
            self.cover_label.setStyleSheet("border: 1px solid #444; background: #1e1e1e;")
        else:
            self.cover_label.setStyleSheet("border: 1px solid #aaa; background: #ffffff;")

    def _apply_header_style(self, dark: bool) -> None:
        """Make the 'Now Playing' header readable in both themes."""
        color = "#ffffff" if dark else "#000000"
        self.meta_header.setStyleSheet(f"font-weight: 600; color: {color};")

    def _apply_theme(self, mode: str) -> None:
        """
        Apply 'dark' or 'light' theme to the whole app and persist it.
        """
        app = QApplication.instance()
        if not app:
            return

        # Use Fusion for consistent cross‑DE rendering
        app.setStyle("Fusion") # type: ignore

        is_dark = str(mode).lower() == "dark"
        if is_dark:
            app.setPalette(self._palette_dark) # type: ignore
        else:
            app.setPalette(self._palette_light) # pyright: ignore[reportAttributeAccessIssue]

        # Match widgets that use stylesheets to the theme
        if hasattr(self, "cover_label"):
            self._apply_cover_style(is_dark)
        if hasattr(self, "meta_header"):
            self._apply_header_style(is_dark)

        # Persist last choice
        self._settings.setValue("theme", "dark" if is_dark else "light")

        # Keep the toggle's check state in sync (without feedback loop)
        if hasattr(self, "act_dark_mode"):
            self.act_dark_mode.blockSignals(True)
            self.act_dark_mode.setChecked(is_dark)
            self.act_dark_mode.blockSignals(False)