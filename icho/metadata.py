# icho/metadata.py
# Free automatic tagging and album art for Icho.
# - Guess from filename (Artist - Title)
# - Query MusicBrainz for canonical metadata
# - Fetch cover art from Cover Art Archive
# - Embed tags + artwork with mutagen

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
import re
import requests
import mutagen
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TALB, TPE1
from mutagen.id3._util import error as ID3Error
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

USER_AGENT = "Icho/1.0 (https://example.local)"  # be a good netizen

@dataclass
class TagInfo:
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    release_mbid: Optional[str] = None  # MusicBrainz release id (for cover art)

# -------------------- Local heuristics --------------------
def guess_from_filename(path: str) -> TagInfo:
    """
    Try to parse 'Artist - Title' from filename.
    e.g., 'Mazzy Star - Fade Into You (Lyrics).mp3'
    """
    name = Path(path).stem
    # Prefer "artist - title" but keep it forgiving
    m = re.match(r"^\s*(?P<artist>.+?)\s*-\s*(?P<title>.+?)\s*$", name)
    if m:
        artist = cleanup(m.group("artist"))
        title = cleanup(m.group("title"))
        return TagInfo(title=title, artist=artist)
    # Otherwise, just treat the stem as the title
    return TagInfo(title=cleanup(name))

def cleanup(s: str) -> str:
    # Strip common noise from titles
    s = re.sub(r"\s*\(lyrics?\)|\[.*?]\s*|\(official.*?\)", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -\u2013\u2014")
    return s

# -------------------- MusicBrainz lookup --------------------
def search_musicbrainz(artist: Optional[str], title: Optional[str]) -> TagInfo:
    """
    Use MusicBrainz recording search to find best match and return canonical tags.
    We keep it very conservative: only return when both artist and title match well.
    """
    if not title:
        return TagInfo()
    q_parts = []
    if artist:
        q_parts.append(f'artist:"{artist}"')
    q_parts.append(f'recording:"{title}"')
    q = " AND ".join(q_parts)

    url = "https://musicbrainz.org/ws/2/recording"
    params = {"query": q, "fmt": "json", "limit": 1}
    try:
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return TagInfo()

    recs = data.get("recordings") or []
    if not recs:
        return TagInfo()

    rec = recs[0]
    # Prefer first “release” entry for album/MBID
    releases = rec.get("releases") or []
    album = releases[0]["title"] if releases else None
    release_mbid = releases[0]["id"] if releases else None

    # Prefer credited artist name
    artist_credit = rec.get("artist-credit") or []
    if artist_credit and isinstance(artist_credit[0], dict):
        a = artist_credit[0].get("name") or artist_credit[0].get("artist", {}).get("name")
    else:
        a = artist
    # Recording title
    t = rec.get("title") or title

    return TagInfo(title=t, artist=a, album=album, release_mbid=release_mbid)

# -------------------- Cover Art Archive --------------------
def fetch_cover_art(release_mbid: str, prefer_size: int = 500) -> Optional[bytes]:
    """
    Try to fetch a front cover for a release from the Cover Art Archive.
    We try a direct sized jpg first, then fall back to the JSON index.
    """
    # 1) direct sized JPEG endpoint (fast path)
    sized = f"https://coverartarchive.org/release/{release_mbid}/front-{prefer_size}.jpg"
    try:
        r = requests.get(sized, headers={"User-Agent": USER_AGENT}, timeout=10)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:
        pass

    # 2) JSON index -> first “front” image
    index_url = f"https://coverartarchive.org/release/{release_mbid}"
    try:
        j = requests.get(index_url, headers={"User-Agent": USER_AGENT}, timeout=10).json()
        images = j.get("images") or []
        for img in images:
            if img.get("front"):
                # Try the best sized thumbnail or original
                thumbs = img.get("thumbnails") or {}
                for key in (str(prefer_size), "large", "small"):
                    u = thumbs.get(key)
                    if u:
                        rr = requests.get(u, headers={"User-Agent": USER_AGENT}, timeout=10)
                        if rr.status_code == 200 and rr.content:
                            return rr.content
                # original
                u = img.get("image")
                if u:
                    rr = requests.get(u, headers={"User-Agent": USER_AGENT}, timeout=10)
                    if rr.status_code == 200 and rr.content:
                        return rr.content
    except Exception:
        pass

    return None

# -------------------- Write tags + embed art --------------------
def write_tags(path: str, tags: TagInfo, cover_jpeg: Optional[bytes] = None) -> bool:
    """
    Write title/artist/album and optionally embed cover art into the file.
    Supports mp3, flac, m4a.
    Returns True if something was written.
    """
    ext = Path(path).suffix.lower()
    wrote = False

    if ext == ".mp3":
        wrote = _write_mp3(path, tags, cover_jpeg)
    elif ext == ".flac":
        wrote = _write_flac(path, tags, cover_jpeg)
    elif ext == ".m4a":
        wrote = _write_m4a(path, tags, cover_jpeg)
    return wrote

def _write_mp3(path: str, tags: TagInfo, cover: Optional[bytes]) -> bool:
    try:
        try:
            id3 = ID3(path)
        except ID3Error:
            id3 = ID3()  # create new tag if missing

        if tags.title:  id3.setall("TIT2", [TIT2(encoding=3, text=tags.title)])
        if tags.artist: id3.setall("TPE1", [TPE1(encoding=3, text=tags.artist)])
        if tags.album:  id3.setall("TALB", [TALB(encoding=3, text=tags.album)])
        if cover:
            id3.delall("APIC")
            id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Front cover", data=cover))
        id3.save(path)
        return True
    except Exception:
        return False

def _write_flac(path: str, tags: TagInfo, cover: Optional[bytes]) -> bool:
    try:
        flac = FLAC(path)
        if tags.title:  flac["title"] = [tags.title]
        if tags.artist: flac["artist"] = [tags.artist]
        if tags.album:  flac["album"] = [tags.album]
        if cover:
            pic = Picture()
            pic.type = 3  # front cover
            pic.mime = "image/jpeg"
            pic.desc = "Front cover"
            pic.data = cover
            flac.clear_pictures()
            flac.add_picture(pic)
        flac.save()
        return True
    except Exception:
        return False

def _write_m4a(path: str, tags: TagInfo, cover: Optional[bytes]) -> bool:
    try:
        mp4 = MP4(path)
        if tags.title:  mp4["\xa9nam"] = [tags.title]
        if tags.artist: mp4["\xa9ART"] = [tags.artist]
        if tags.album:  mp4["\xa9alb"] = [tags.album]
        if cover:
            mp4["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
        mp4.save()
        return True
    except Exception:
        return False

# -------------------- Orchestrator --------------------
def autotag(path: str) -> Dict[str, Any]:
    """
    End-to-end:
      1) Guess from filename
      2) Query MusicBrainz (refine tags)
      3) Fetch cover art (if we know a release)
      4) Write tags + embed art
    Returns a dict with what happened for UI messages.
    """
    guess = guess_from_filename(path)
    online = search_musicbrainz(guess.artist, guess.title)
    # Merge: prefer online when available, fallback to guess
    merged = TagInfo(
        title = online.title or guess.title,
        artist = online.artist or guess.artist,
        album = online.album,
        release_mbid = online.release_mbid
    )
    cover = fetch_cover_art(merged.release_mbid) if merged.release_mbid else None
    ok = write_tags(path, merged, cover)
    return {
        "ok": ok,
        "tags": merged,
        "had_cover": cover is not None,
    }
