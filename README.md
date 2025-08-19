# Icho --- Local Music Player (v1.1)

Icho is a lightweight, free and offline-capable local music player built
with Python and PySide6. It offers drag-and-drop playlists, keyboard
shortcuts, metadata tagging, album art support, theming, and playlist management.

------------------------------------------------------------------------

## Features (v1.1)

-   **Simple playlist creation**: Drag files or folders directly into
    the window, or use **File → Open Files/Folder**
-   **Playback controls**: Play/Pause, Next, Previous, Stop, Seek bar,
    Volume control
-   **Now Playing panel**: Displays Title, Artist, Album, and Cover Art
-   **Automatic tagging**:
    -   Guess from filename (e.g., `Artist – Title`)
    -   Query MusicBrainz API for correct metadata
    -   Download cover art from Cover Art Archive
    -   Embed metadata and cover into the file using `mutagen`
    -   Accessible via **Tools → Auto-tag Current / Auto-tag All**
-   **Cover art rendering**: Reads embedded art and displays it in the
    UI
-   **Playlists menu**:
    -   Save and load playlists to/from `.json`
    -   Remembers last 5 recent playlists
    -   Pin up to 10 favorite playlists for quick access
-   **Themes**:
    -   Dark Mode and Light Mode toggle (via **Tools → Dark Mode**)
    -   Persists your last choice across sessions
-   Tested formats: `.mp3`, `.flac`, `.m4a`

------------------------------------------------------------------------

## Installation & Setup

``` bash
git clone https://github.com/numairazman/icho.git
cd icho
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Or use the provided helper scripts:

-   **Linux/macOS**: `./scripts/run.sh`
-   **Windows**: `scripts\run.bat`

------------------------------------------------------------------------

## Usage Tips

-   Add files via drag-and-drop or menu (Ctrl+O for files, Ctrl+Shift+O
    for folders).
-   Double-click an item to play immediately.
-   Use **Tools → Auto-tag Current** to tag the currently playing track.
-   Use **Tools → Auto-tag All** to tag your entire playlist in batch.
-   Save and load playlists in JSON format, and manage them via the **Playlists** menu.
-   Toggle Dark/Light mode from the Tools menu; your preference is remembered on next launch.
-   Invalid or missing metadata falls back to filename styling ("Title
    -- Artist").

------------------------------------------------------------------------

## Development

-   Signals from `AudioPlayer` are routed via Slots to avoid PySide6
    direct-Signal pitfalls.
-   Metadata logic resides in `icho/metadata.py` --- easy to extend
    (e.g. fetch lyrics, more formats, etc.).
-   Future plans:
    -   Display synchronized lyrics
    -   Build installers (AppImage, macOS `.app`, Windows `.exe`)

------------------------------------------------------------------------

## License

Icho is released under the MIT License. See [LICENSE](LICENSE) for
details.

------------------------------------------------------------------------

Made with passion by Numair Azman.
