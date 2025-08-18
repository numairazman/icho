# Icho --- Local Music Player (v1.0)

Icho is a lightweight, free and offline-capable local music player built
with Python and PySide6. It offers drag-and-drop playlists, keyboard
shortcuts, metadata tagging, and album art support.

------------------------------------------------------------------------

## Features (v1.0)

-   **Simple playlist creation**: Drag files or folders directly into
    the window, or use **File → Open Files/Folder**
-   **Playback controls**: Play/Pause, Next, Previous, Stop, Seek bar,
    Volume control
-   **Now Playing panel**: Displays Title, Artist, Album
-   **Automatic tagging**:
    -   Guess from filename (e.g., `Artist – Title`)
    -   Query MusicBrainz API for correct metadata
    -   Download cover art from Cover Art Archive
    -   Embed metadata and cover into the file using `mutagen`
    -   Accessible via **Tools → Auto-tag Current / Auto-tag All**
-   **Cover art rendering**: Reads embedded art and displays it in the
    UI
-   Tested formats: `.mp3`, `.flac`, `.m4a`

------------------------------------------------------------------------

## Installation & Setup

``` bash
git clone https://github.com/numairazman/icho-.git
cd icho
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

------------------------------------------------------------------------

## Usage Tips

-   Add files via drag-and-drop or menu (Ctrl+O for files, Ctrl+Shift+O
    for folders).
-   Double-click an item to play immediately.
-   Use **Tools → Auto-tag Current** to tag the currently playing track.
-   Use **Tools → Auto-tag All** to tag your entire playlist in batch.
-   Invalid or missing metadata falls back to filename styling ("Title
    -- Artist").
-   If embedded album art exists, it will display; otherwise it will
    show a placeholder.

------------------------------------------------------------------------

## Development

-   Signals from `AudioPlayer` are routed via Slots to avoid PySide6
    direct-Signal pitfalls.
-   Metadata logic resides in `icho/metadata.py` --- easy to extend
    (e.g. fetch lyrics, more formats, etc.).
-   Future plans:
    -   Add playlist saving and file export
    -   Display synchronized lyrics
    -   Build installers (AppImage, macOS `.app`, Windows `.exe`)

------------------------------------------------------------------------

## License

Icho is released under the MIT License. See [LICENSE](LICENSE) for
details.

------------------------------------------------------------------------

Made with passion by Numair Azman.