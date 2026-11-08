from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import threading

from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL

from .models import Track, VIDEO_ID


@dataclass(frozen=True)
class Entry:
    kind: str
    id: str
    title: str
    subtitle: str = ""
    track: Track | None = None
    thumbnail: str | None = None
    params: str | None = None


def provider_track(row: dict, album: str | None = None) -> Track | None:
    if not isinstance(row, dict):
        return None
    id = row.get("videoId") or row.get("id")
    if not isinstance(id, str) or not VIDEO_ID.fullmatch(id):
        return None
    artists = row.get("artists") or []
    artist = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict)) or row.get("artist") or row.get("uploader") or row.get("author") or ""
    if isinstance(artist, dict):
        artist = artist.get("name", "")
    if not isinstance(artist, str) or not isinstance(row.get("title"), str) or not row["title"].strip():
        return None
    record = row.get("album")
    if isinstance(record, dict):
        record = record.get("name")
    duration = row.get("duration_seconds") or row.get("duration") or row.get("length") or 0
    if isinstance(duration, str):
        result = 0
        for n in duration.split(":"):
            if not n.isdigit():
                result = 0
                break
            result = result * 60 + int(n)
        duration = result
    images = row.get("thumbnails") or row.get("thumbnail") or []
    thumbnail = images[-1].get("url") if isinstance(images, list) and images else (images if isinstance(images, str) else None)
    return Track(id, row.get("title") or "", artist, album or record, int(duration or 0), thumbnail).validate()


def runtime_node() -> str | None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    for location in (root / "runtime" / "node.exe", root / "runtime" / "node", root / ".runtime" / "node"):
        if location.is_file():
            return str(location)
    return shutil.which("node")


class QuietLogger:
    # Never log cookies, signed provider URLs, full user queries or credentials.
    def debug(self, message):
        pass
    def warning(self, message):
        pass
    def error(self, message):
        pass


class Provider:
    """Anonymous public music/search/streams. No account/password/cookie capture or restriction bypass."""
    scopes = ("Songs", "Albums", "Artists", "Playlists", "Music videos", "Videos", "All YouTube")

    @staticmethod
    def music() -> YTMusic:
        return YTMusic(language="en", location="IN", requests_session=True)

    @staticmethod
    def options(**extra) -> dict:
        node = runtime_node()
        return {"quiet": True, "no_warnings": True, "logger": QuietLogger(), "noplaylist": True,
                "socket_timeout": 15, "retries": 2, "fragment_retries": 2,
                "js_runtimes": {"node": {"path": node}} if node else {}, "remote_components": [], **extra}

    def search(self, query: str, scope: str = "Songs", limit: int = 20) -> list[Entry]:
        query = " ".join(query.split())[:500]
        if not query or scope not in self.scopes or limit < 1 or limit > 200:
            raise ValueError("Enter a query and a supported search scope")
        if scope in {"Videos", "All YouTube"}:
            with YoutubeDL(self.options(extract_flat=True, skip_download=True)) as ydl:
                response = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                rows = (response or {}).get("entries", [])
        else:
            filter = {"Songs": "songs", "Albums": "albums", "Artists": "artists", "Playlists": "playlists", "Music videos": "videos"}[scope]
            rows = self.music().search(query, filter=filter, limit=limit, ignore_spelling=True)
        entries, seen = [], set()
        for row in rows:
            track = provider_track(row)
            kind = row.get("resultType") or ("song" if track else "")
            id = (track.id if track else row.get("browseId")) or ""
            if not id or id in seen:
                continue
            seen.add(id)
            artist = ", ".join(a.get("name", "") for a in row.get("artists", []) if isinstance(a, dict))
            entries.append(Entry(kind, id, row.get("title") or row.get("artist") or "", artist or row.get("author") or "", track))
        return entries

    def home_page(self, chip=None):
        from .catalogue import parse_page
        body = {"browseId": chip.browse_id if chip else "FEmusic_home"}
        if chip and chip.params:
            body["params"] = chip.params
        return parse_page(self.music()._send_request("browse", body))

    def catalogue_page(self, entry=None, continuation=None, browse_id=None):
        from .catalogue import parse_page, parse_continuation
        body = {}
        if continuation:
            if not isinstance(continuation, str) or len(continuation) > 8192:
                raise ValueError("Unsupported catalogue continuation")
            body["continuation"] = continuation
        else:
            id = browse_id or (entry.id if entry else "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", id):
                raise ValueError("Unsupported catalogue reference")
            body["browseId"] = id
            if entry and entry.params:
                body["params"] = entry.params
        response = self.music()._send_request("browse", body)
        return parse_continuation(response) if continuation else parse_page(response, bool(entry and entry.kind in {"album", "albums"}))

    def suggestions(self, query):
        query = " ".join(query.split())[:500]
        return self.music().get_search_suggestions(query)[:12] if query else []

    def resolve_video(self, track):
        track.validate()
        if track.local:
            raise ValueError("Local audio has no online video")
        with YoutubeDL(self.options(format="best[protocol=https][ext=mp4]/best[protocol=https]", skip_download=True)) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=" + track.id, download=False)
            if not info or not info.get("url") or info.get("vcodec") in {None, "none"}:
                raise ValueError("No accessible combined video/audio stream was returned")
            return info["url"], info.get("http_headers") or {}

    def home(self) -> list[Entry]:
        response = self.music().get_charts(country="IN")
        rows = []
        for section in response.values():
            if isinstance(section, dict):
                rows.extend(section.get("items") or [])
        result, seen = [], set()
        for row in rows:
            track = provider_track(row)
            if track and track.id not in seen:
                seen.add(track.id)
                result.append(Entry("song", track.id, track.title, track.artist, track))
        return result

    def browse(self, entry: Entry) -> tuple[str, list[Track]]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", entry.id):
            raise ValueError("Unsupported catalogue reference")
        music = self.music()
        if entry.kind in {"album", "albums"}:
            data = music.get_album(entry.id)
            rows = (data.get("tracks") or [])
        elif entry.kind in {"artist", "artists"}:
            data = music.get_artist(entry.id)
            rows = (data.get("songs") or {}).get("results", [])
        else:
            data = music.get_playlist(entry.id, limit=500)
            rows = (data.get("tracks") or [])
        return data.get("title") or data.get("name") or entry.title, [t for row in rows if (t := provider_track(row))]

    def related(self, track: Track, existing: list[Track]) -> list[Track]:
        if track.local:
            return []
        data = self.music().get_watch_playlist(videoId=track.id, radio=True, limit=30)
        # Music-only provider radio, not the unrelated web-video recommendations endpoint.
        seen = {t.id for t in existing}
        def base(title):
            return re.sub(r"\W+", "", re.sub(r"(?i)\b(official|video|audio|lyrics|remix|slowed|reverb|sped|up|lofi|8d|song|full|mix)\b", "", title)).casefold()
        seed_title = base(track.title)
        result = []
        for row in (data.get("tracks") or []):
            song = provider_track(row)
            if not song or song.id in seen or base(song.title) == seed_title:
                continue
            seen.add(song.id)
            if song.durationSec and (song.durationSec < 45 or song.durationSec > 15 * 60):
                continue
            result.append(song)
        return result[:15]

    def resolve(self, track: Track) -> tuple[str, dict]:
        track.validate()
        if track.local:
            raise ValueError("Local audio must never enter the network resolver")
        with YoutubeDL(self.options(format="bestaudio[protocol=https][ext=m4a]/bestaudio[protocol=https]", skip_download=True)) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=" + track.id, download=False)
            if not info or not info.get("url"):
                raise ValueError("No accessible progressive audio stream. Provider restrictions were not bypassed.")
            return info["url"], info.get("http_headers") or {}
