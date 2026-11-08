"""Phone LyricsRepository/LrcParser behavior, including timed line selection."""
from __future__ import annotations
from bisect import bisect_right
from collections import OrderedDict
from dataclasses import dataclass
import json
import re
import threading

import requests

from .models import Track

STAMP = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]')
NOISE = re.compile(r'\s*[(\[][^)\]]*(official|video|audio|lyric|lyrics|visualizer|hd|4k|remaster)[^)\]]*[)\]]', re.I)


@dataclass(frozen=True)
class LyricLine:
    time_ms: int
    text: str


@dataclass(frozen=True)
class Lyrics:
    synced: tuple[LyricLine, ...] = ()
    plain: str | None = None


def parse_lrc(value: str) -> tuple[LyricLine, ...]:
    result = []
    for line in value.splitlines():
        matches = list(STAMP.finditer(line))
        text = STAMP.sub('', line).strip()
        for match in matches:
            minutes, seconds, fraction = match.groups()
            ms = int((fraction or '').ljust(3, '0') or '0')
            result.append(LyricLine(int(minutes) * 60_000 + int(seconds) * 1000 + ms, text))
    return tuple(sorted(result, key=lambda item: item.time_ms))


def index_at(lines, position_ms: int) -> int:
    # Same rightmost-at-or-before rule as Android, including duplicate timestamps.
    return bisect_right([line.time_ms for line in lines], position_ms) - 1


def clean_title(value: str) -> str:
    return NOISE.sub('', value).strip()


class LyricsRepository:
    def __init__(self, get=None):
        self._get = get or requests.get
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _parse(value) -> Lyrics | None:
        if not isinstance(value, dict):
            return None
        lrc, plain = value.get('syncedLyrics'), value.get('plainLyrics')
        synced = parse_lrc(lrc) if isinstance(lrc, str) else ()
        plain = plain if isinstance(plain, str) and plain.strip() else None
        return Lyrics(synced, plain) if synced or plain else None

    def _request(self, path, params, cancel):
        if cancel.is_set():
            return None
        with self._get('https://lrclib.net/api/' + path, params={k: v for k, v in params.items() if v},
                       headers={'User-Agent': 'Dkord (https://github.com/DeepuExplainsAi/dkord)'}, timeout=15, stream=True) as response:
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(16_384):
                if cancel.is_set():
                    return None
                data.extend(chunk)
                if len(data) > 1_048_576:
                    raise ValueError('Lyrics response is too large')
            return json.loads(data)

    def load(self, track: Track, cancel=None) -> Lyrics | None:
        cancel = cancel or threading.Event()
        if track.local:
            return None
        with self._lock:
            if track.id in self._cache:
                self._cache.move_to_end(track.id)
                return self._cache[track.id]
        title, artist = clean_title(track.title), track.artist.removesuffix(' - Topic')
        result = self._parse(self._request('get', dict(track_name=title, artist_name=artist,
                                                     album_name=track.album, duration=track.durationSec or None), cancel))
        if result is None and not cancel.is_set():
            rows = self._request('search', dict(track_name=title, artist_name=artist), cancel)
            if isinstance(rows, list):
                result = next((item for row in rows if (item := self._parse(row)) and item.synced), None)
        if result and not cancel.is_set():
            with self._lock:
                self._cache[track.id] = result
                self._cache.move_to_end(track.id)
                while len(self._cache) > 128:
                    self._cache.popitem(last=False)
        return result
