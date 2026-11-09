"""Explicit video-link identity, independent of music search and radio policy.

Only a canonical YouTube watch URL reaches the provider. Never fetch a pasted
host, playlist, redirect, title search or signed stream URL. Android runs the same
URL vectors from app/src/test/resources/youtube-links.json.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from urllib.parse import parse_qsl, urlsplit

from .models import Track, VIDEO_ID

MAX_LINK_LENGTH = 4096
VIDEO_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}
SHORT_HOSTS = {'youtu.be', 'www.youtu.be'}
EMBED_HOSTS = {'youtube-nocookie.com', 'www.youtube-nocookie.com'}
PROBLEM_KEYS = {
    'invalid_link': 'youtube_link_invalid', 'playlist_only': 'youtube_link_playlist_only',
    'network': 'err_network', 'private': 'err_private', 'age_restricted': 'err_age_restricted',
    'geo': 'err_geo', 'bot_check': 'err_bot_check', 'no_audio': 'err_no_audio',
    'unavailable': 'err_unavailable',
}


class YouTubeLinkError(Exception):
    def __init__(self, problem='unavailable'):
        self.problem = problem if problem in PROBLEM_KEYS else 'unavailable'
        super().__init__(self.problem)


@dataclass(frozen=True)
class YouTubeVideoLink:
    video_id: str

    def __post_init__(self):
        if not isinstance(self.video_id, str) or not VIDEO_ID.fullmatch(self.video_id):
            raise YouTubeLinkError('invalid_link')

    @property
    def url(self):
        return 'https://www.youtube.com/watch?v=' + self.video_id


def parse_youtube_link(value: str) -> YouTubeVideoLink:
    if not isinstance(value, str):
        raise YouTubeLinkError('invalid_link')
    text = value.strip()
    if (not text or len(text) > MAX_LINK_LENGTH or
            any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == '\\' for c in text)):
        raise YouTubeLinkError('invalid_link')
    try:
        url = urlsplit('https:' + text if text.startswith('//') else text if '://' in text else 'https://' + text)
        host = (url.hostname or '').lower()
        port = 443 if url.scheme == 'https' else 80
        if (url.scheme not in {'http', 'https'} or host not in VIDEO_HOSTS | SHORT_HOSTS | EMBED_HOSTS
                or url.netloc.lower() not in {host, f'{host}:{port}'}):
            raise ValueError('Unsupported authority')
        # urlsplit tolerates malformed escapes; URI on Android deliberately does not.
        if re.search(r'%(?![0-9a-fA-F]{2})', text):
            raise ValueError('Malformed escape')
        query = parse_qsl(url.query, keep_blank_values=True, errors='replace')
        path = url.path.removesuffix('/')
        ids = [v for k, v in query if k == 'v']
        if host in VIDEO_HOSTS and (path == '/playlist' or (
                path in {'', '/watch'} and not ids and any(k == 'list' and v for k, v in query))):
            raise YouTubeLinkError('playlist_only')
        if host in SHORT_HOSTS:
            video_id = path.removeprefix('/')
        elif host in VIDEO_HOSTS and path == '/watch':
            video_id = ids[0] if len(ids) == 1 else ''
        else:
            pattern = r'/(?:shorts|live|embed|v)/([A-Za-z0-9_-]{11})' if host in VIDEO_HOSTS else r'/embed/([A-Za-z0-9_-]{11})'
            match = re.fullmatch(pattern, path)
            video_id = match[1] if match else ''
        return YouTubeVideoLink(video_id)
    except YouTubeLinkError:
        raise
    except (ValueError, UnicodeError):
        raise YouTubeLinkError('invalid_link') from None


def link_track(link: YouTubeVideoLink, info: dict) -> Track:
    """Provider metadata must describe the chosen ID, never a replacement/search hit."""
    if (not isinstance(info, dict) or info.get('id') != link.video_id or
            info.get('_type', 'video') not in {'video', None}):
        raise YouTubeLinkError()
    availability = info.get('availability')
    if availability == 'private':
        raise YouTubeLinkError('private')
    if availability in {'premium_only', 'subscriber_only', 'needs_auth'} or info.get('live_status') == 'is_upcoming':
        raise YouTubeLinkError()
    duration = info.get('duration') or 0
    if (not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0
            or duration > 9223372036854775807 or not math.isfinite(duration)):
        raise YouTubeLinkError()
    try:
        return Track(link.video_id, info.get('title'), info.get('uploader') or info.get('channel') or '',
                     durationSec=int(duration), thumbnail=info.get('thumbnail')).validate()
    except (ValueError, TypeError, OverflowError):
        raise YouTubeLinkError() from None


def extraction_problem(error: Exception) -> str:
    """Classify yt-dlp failures without exposing/logging provider URLs or raw responses."""
    if isinstance(error, YouTubeLinkError):
        return error.problem
    message = str(error).lower()
    if any(x in message for x in ('not a bot', 'too many requests', 'http error 429')):
        return 'bot_check'
    if any(x in message for x in ('confirm your age', 'age-restricted', 'age restricted')):
        return 'age_restricted'
    if any(x in message for x in ('private video', 'video is private')):
        return 'private'
    if any(x in message for x in ('your country', 'geographic restriction', 'geo restricted', 'geo-restricted')):
        return 'geo'
    if any(x in message for x in ('no audio', 'no video formats', 'requested format is not available')):
        return 'no_audio'
    if isinstance(error, (OSError, TimeoutError, ConnectionError)) or any(x in message for x in (
            'timed out', 'connection', 'network', 'unable to download', 'name resolution', 'resolve host', 'temporary failure')):
        return 'network'
    return 'unavailable'
