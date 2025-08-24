# Icho --- Local Music Player (v1.5)

**v1.5:** New Albums sidebar view, Play Next priority queue, manual Edit Tags / Cover dialog, improved auto-tag fixes. See CHANGELOG for details.

**A portable Windows .exe is now available in the [Releases tab](https://github.com/numairazman/icho/releases)!**

Icho is a lightweight, free and offline-capable local music player built
with Python and PySide6. It offers drag-and-drop playlists, keyboard
shortcuts, metadata tagging, album art support, theming, playlist management,
a library system, shuffle/repeat/autoplay, robust cross-platform launchers, and more.

---

## Features (v1.5)

### 1. Library & Albums

- **Library folder scanning**: Point Icho at a root folder; it recursively indexes supported audio files (`.mp3`, `.flac`, `.m4a`, `.wav`, `.ogg`).
- **Albums view (NEW)**: Sidebar now has an Albums section. Browse a deduplicated list of album names (fallback: "Unknown Album"). Double‑click an album to drill in; double‑click a track to play that album only.
- **Album‑scoped playback**: Starting a song from an album view builds a temporary playlist containing only that album's tracks; the Upcoming queue reflects just that scope unless you manually add overrides.
- **Search box**: Live filtering in Library by title or artist (case‑insensitive, metadata aware).
- **Metadata-based display**: Track items show `Title — Artist` when tags exist; otherwise fall back to filename.

### 2. Playlists & Queueing

- **Ad‑hoc playlist building**: Drag files/folders in or use File → Open Files / Open Folder. Duplicate suppression while preserving order.
- **Persistent playlist management**: Save / Load JSON playlists; automatic recent list (last 5) and pinnable favorites (up to 10) via the Playlists menu.
- **Automatic Upcoming queue**: After you start playback, Icho auto‑generates an "upcoming" sequence from the current playlist or album (shuffle aware) — no manual seeding required.
- **Play Next priority (NEW)**: Right‑click (context menu in track list) → Play Next instantly injects selected tracks at the front of the pending order without disturbing the underlying playlist order.
- **Manual overrides list**: Maintains a short-term priority buffer consumed before auto upcoming items; cleared automatically as entries play or when you clear the playlist.
- **Up Next label**: Always shows the real next track considering manual Play Next overrides and shuffle mode.
- **Upcoming dialog**: Tools → View Upcoming to inspect and prune forthcoming tracks (remove individual entries or clear auto-generated list; manual overrides are reflected first).

### 3. Playback Engine

- **Transport controls**: Play/Pause, Next, Previous, Stop, Seek bar, Position + Duration time display, Volume slider with percentage.
- **Shuffle**: Randomizes future order while preserving a playback history so Previous works intuitively even in shuffle mode.
- **Repeat**: Optional repeat toggle for continuous playback.
- **Autoplay**: Automatically advances at track end; logic integrates with shuffle/history and manual Play Next.
- **Accurate Previous in Shuffle**: History stack ensures you traverse actual played sequence, not just list index math.

### 4. Tagging & Metadata

- **Auto-tag (Current / All)**: MusicBrainz lookup + Cover Art Archive retrieval + filename heuristic (`Artist – Title`) fallback.
- **Fix Auto-tag (Current)**: Re-run tagging pipeline quickly if earlier lookup was low quality.
- **Manual Edit Tags / Cover (NEW)**: Full in-app dialog to adjust Title, Artist, Album, and replace embedded artwork (MP3 ID3v2, FLAC pictures, M4A atoms) with immediate UI refresh.
- **Embedded cover handling**: Reads existing artwork on each track change; scales with aspect preservation.
- **Graceful fallbacks**: Missing fields display as `-`; cover placeholder text if no art.
- **User agent identification**: Custom `Icho/x.y` user agent for polite API use.

### 5. UI & UX

- **Sidebar navigation**: Library / Albums / Current Playlist.
- **Context menus**: Track list action for Play Next.
- **Theme toggle**: Dark/Light (persisted via QSettings).
- **Responsive metadata panel**: Immediate updates on track change, tag edits, autotag completion, and Play Next insertions.
- **Non-blocking updates**: Signals decouple backend events (duration/position/track changes) from UI updates.

### 6. Cross-Platform & Tooling

- **PySide6 + python-vlc**: Cross-platform playback backend; avoids multimedia plugin issues on Windows.
- **Launcher scripts**: `scripts/run.sh` (Linux/macOS) and `scripts/run.bat` (Windows) set up virtualenv and dependencies.
- **(Planned)** Portable Windows executable and future packaging (AppImage / macOS bundle).

### 7. Reliability & Data Integrity

- **History aware shuffle** preventing repeat collisions in short sessions.
- **De-duplication** when adding paths while preserving first-seen order.
- **Safe tag writing** with exception handling per format; UI only updates on success.

### 8. Extensibility Targets (Roadmap)

- Lyrics (embedded / synced), no promises on this one
- Additional formats (AAC/Opus containers, cue sheet parsing)
- Smart playlists (rules: recently added, most played)

---

## Installation & Setup

```bash
git clone https://github.com/numairazman/icho.git
cd icho
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Or use the provided helper scripts:

- **Linux/macOS**: `./scripts/run.sh`
- **Windows**: `scripts\run.bat`

**A portable Windows .exe will be available soon in the [Releases tab](https://github.com/numairazman/icho/releases)!**

---

## Usage Tips

- Add files via drag-and-drop or menu (Ctrl+O for files, Ctrl+Shift+O
  for folders).
- Double-click an item to play immediately.
- Use **Tools → Auto-tag Current** to tag the currently playing track.
- Use **Tools → Auto-tag All** to tag your entire playlist in batch.
- Save and load playlists in JSON format, and manage them via the **Playlists** menu.
- Use the sidebar to switch between your library and playlists.
- Use the search box above the library to quickly find songs by title or artist.
- Shuffle, repeat, and autoplay options are available for seamless listening.
- Toggle Dark/Light mode from the Tools menu; your preference is remembered on next launch.
- Invalid or missing metadata falls back to filename styling ("Title -- Artist").

---

## Development

- Signals from `AudioPlayer` are routed via Slots to avoid PySide6
  direct-Signal pitfalls.
- Metadata logic resides in `icho/metadata.py` --- easy to extend
  (e.g. fetch lyrics, more formats, etc.).
- Future plans:
  - Display synchronized lyrics
  - Build installers (AppImage, macOS `.app`, Windows `.exe`)

---

## License

Icho is released under the MIT License. See [LICENSE](LICENSE) for
details.

---

Made with passion by Numair Azman.
