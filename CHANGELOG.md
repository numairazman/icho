# Changelog

All notable changes to this project will be documented in this file following the “Keep a Changelog” format. See https://keepachangelog.com for guidance.

## [1.0.0] – 2025‑08‑18
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

*Icho v1.0 released. Let me know if you’d like non‑English support, command-line control, or theme options!*