# CHANGELOG - Icho

All notable changes to this project will be documented in this file following the “Keep a Changelog” format. See https://keepachangelog.com for guidance.

## [1.4.1] – 2025-08-23

### Hotfix (Windows)

- Switched audio backend from QMediaPlayer to python-vlc for reliable Windows playback
- Fixed missing QtMultimedia backends on Windows
- Thoroughly cleaned up AudioPlayer class for cross-platform support
- Updated build and run scripts for Windows compatibility
- Version string updated to v1.4.1 everywhere

---

## [1.4.0] – 2025-08-23

**A portable Windows .exe will be available soon in the Releases tab!**

### Added

- Search box above Library for filtering songs by title or artist
- Songs in Library and Playlist show Title — Artist (from metadata or filename)
- After autotagging, song titles and artists update in the UI

### Fixed

- Metadata display and refresh after autotag
- Import errors for mutagen.id3 frames and error
- Autotag function import and usage

### Changed

- README updated for v1.4 features
- Version string updated to v1.4

## [1.3.0] – 2025-08-23

### Added

- Sidebar navigation for Library and Playlists
- Library folder selection and scanning
- Playlists menu with Load/Save actions (moved from File menu)
- Shuffle, Repeat, and Autoplay playback features
- Automatic track skipping when a song ends (autoplay)
- Robust Windows launcher script (`run.bat`) for venv and dependencies

### Fixed

- Play/Pause button now reliably toggles playback (no skipping)
- Next button respects Shuffle mode
- Autoplay logic now works for all supported formats
- Menu structure restored (File, Tools, Help, Playlists)
- All debug output removed from production code

### Changed

- Refactored signal/slot logic for PySide6 reliability
- Improved error handling and startup robustness
- Updated run.bat for better Windows compatibility

## [1.1.0] – 2025-08-18

### Added

- **Theme support**:
  - Tools → Dark Mode toggle
  - Remembers last theme (light/dark) across sessions via `QSettings`
- **Playlists menu**:
  - Save/Load playlists to `.json`
  - Automatic tracking of last 5 recent playlists
  - Ability to pin up to 10 playlists for quick access
- **Scripts for launching**:
  - `scripts/run.sh` for Linux/macOS
  - `scripts/run.bat` for Windows

### Fixed

- Now Playing text colors properly adapt to dark/light themes
- Cover image updates refresh reliably when changing tracks

---

## [1.0.0] – 2025-08-18

### Added

- Drag-and-drop support for files and folders
- Playback controls: Play/Pause, Stop, Next, Previous, Seek Slider, Volume Slider
- Playlist panel with double-click to play
- Now Playing metadata panel showing Title, Artist, Album
- Automatic metadata tagging:
  - Filename parsing (`Artist – Title`)
  - MusicBrainz lookup for correct metadata
  - Cover Art Archive integration for album art
  - Metadata + artwork embedding using `mutagen`
  - Actions accessible via Tools menu
- Cover art display in UI, reading embedded images dynamically
- VS Code setup:
  - `.vscode/settings.json` to suppress PySide6 stub warnings
  - `launch.json` for F5 debug
  - `tasks.json` for virtualenv & dependency setup

### Fixed

- Resolved PySide6 signal issues by forwarding via `@Slot(int)`
- Improved reliability of Next/Prev navigation and now-playing updates

### Known Issues

- Gtk warning `"Failed to load module 'xapp-gtk3-module'"` — harmless on some Linux distros
- Occasional FFmpeg timestamp warnings during MP3 decoding — benign
- Cover updates only reflect embedded artwork; external fetch not displayed until tagged

---

_Icho v1.0 released._
