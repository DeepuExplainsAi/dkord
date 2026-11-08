"""Port of the PHONE MusicParser, including shelves, chips, moods and continuations.

The pinned ytmusicapi client supplies anonymous WEB_REMIX HTTP/context, not a
replacement flattened chart catalogue. Song/playlist IDs and provider order stay
intact. No account/cookies are imported from a browser or Android installation.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import re

from .models import Track, VIDEO_ID
from .provider import Entry


@dataclass(frozen=True)
class Chip:
    title: str
    browse_id: str
    params: str | None = None


@dataclass(frozen=True)
class Shelf:
    title: str
    items: tuple[Entry, ...]
    radio_hint: str = ''


@dataclass(frozen=True)
class Page:
    title: str = ''
    subtitle: str = ''
    thumbnail: str | None = None
    chips: tuple[Chip, ...] = ()
    shelves: tuple[Shelf, ...] = ()
    tracks: tuple[Track, ...] = ()
    continuation: str | None = None


def at(value, *keys):
    for key in keys:
        if isinstance(key, int):
            value = value[key] if isinstance(value, list) and 0 <= key < len(value) else None
        else:
            value = value.get(key) if isinstance(value, dict) else None
        if value is None:
            return None
    return value


def array(value):
    return value if isinstance(value, list) else []


def find(value, key):
    stack = [value]
    budget = 100_000
    while stack and budget:
        budget -= 1; value = stack.pop()
        if isinstance(value, dict):
            if key in value:
                return value[key]
            stack.extend(reversed(list(value.values())))
        elif isinstance(value, list):
            stack.extend(reversed(value))
    return None


def runs(value):
    return array(at(value, 'runs'))


def runs_text(value):
    return ''.join(run.get('text', '') for run in runs(value) if isinstance(run, dict) and isinstance(run.get('text', ''), str))


def thumbnail(value):
    images = array(find(value, 'thumbnails'))
    url = at(images, len(images)-1, 'url')
    if not isinstance(url, str):
        return None
    return 'https:' + url if url.startswith('//') else url


def duration(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,2}(?::\d{2}){1,2}', value.strip()):
        return 0
    total = 0
    for part in value.strip().split(':'):
        total = total * 60 + int(part)
    return total


def page_type(endpoint):
    return at(endpoint, 'browseEndpointContextSupportedConfigs', 'browseEndpointContextMusicConfig', 'pageType')


def _browse_entry(endpoint, title, subtitle, image):
    kind = {'MUSIC_PAGE_TYPE_ALBUM': 'album', 'MUSIC_PAGE_TYPE_ARTIST': 'artist',
            'MUSIC_PAGE_TYPE_USER_CHANNEL': 'artist', 'MUSIC_PAGE_TYPE_PLAYLIST': 'playlist'}.get(page_type(endpoint))
    id = at(endpoint, 'browseId')
    if not kind or not isinstance(id, str):
        return None
    return Entry(kind, id, title, subtitle, thumbnail=image, params=at(endpoint, 'params'))


def list_item(row):
    if not isinstance(row, dict):
        return None
    cols = [at(col, 'musicResponsiveListItemFlexColumnRenderer', 'text') for col in array(row.get('flexColumns'))]
    title = runs_text(at(cols, 0))
    video_id = at(row, 'playlistItemData', 'videoId') or at(find(find(row, 'playNavigationEndpoint'), 'watchEndpoint'), 'videoId')
    if not video_id:
        video_id = next((at(run, 'navigationEndpoint', 'watchEndpoint', 'videoId') for run in runs(at(cols, 0))
                         if at(run, 'navigationEndpoint', 'watchEndpoint', 'videoId')), None)
    image = thumbnail(row.get('thumbnail'))
    if not video_id:
        return _browse_entry(at(row, 'navigationEndpoint', 'browseEndpoint'), title, runs_text(at(cols, 1)), image)
    if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id) or not title.strip():
        return None
    meta = runs(at(cols, 1))
    artists = [run.get('text', '') for run in meta if page_type(at(run, 'navigationEndpoint', 'browseEndpoint')) == 'MUSIC_PAGE_TYPE_ARTIST']
    album = next((run.get('text') for run in meta if page_type(at(run, 'navigationEndpoint', 'browseEndpoint')) == 'MUSIC_PAGE_TYPE_ALBUM'), None)
    artist = ', '.join(artists) or next((run.get('text', '') for run in meta if run.get('text', '').strip() not in ('•', '·', '')), '')
    dur = runs_text(at(row, 'fixedColumns', 0, 'musicResponsiveListItemFixedColumnRenderer', 'text'))
    if not dur:
        dur = next((run.get('text') for run in reversed(meta) if duration(run.get('text'))), '')
    track = Track(video_id, title, artist, album, duration(dur), image)
    return Entry('song', video_id, title, artist, track, image)


def carousel_item(value):
    row = at(value, 'musicTwoRowItemRenderer')
    if isinstance(row, dict):
        title, subtitle = runs_text(row.get('title')), runs_text(row.get('subtitle'))
        image = thumbnail(row.get('thumbnailRenderer'))
        watch = at(row, 'navigationEndpoint', 'watchEndpoint')
        if isinstance(watch, dict):
            id = watch.get('videoId')
            if isinstance(id, str) and VIDEO_ID.fullmatch(id) and title.strip():
                return Entry('song', id, title, subtitle, Track(id, title, subtitle.split(' • ')[0], thumbnail=image), image)
            return None
        return _browse_entry(at(row, 'navigationEndpoint', 'browseEndpoint'), title, subtitle, image)
    row = at(value, 'musicNavigationButtonRenderer')
    if isinstance(row, dict):
        endpoint = at(row, 'clickCommand', 'browseEndpoint')
        if at(endpoint, 'browseId'):
            return Entry('mood', endpoint['browseId'], runs_text(row.get('buttonText')), params=endpoint.get('params'))
    return list_item(at(value, 'musicResponsiveListItemRenderer'))


def continuation(root):
    return at(find(root, 'continuationItemRenderer'), 'continuationEndpoint', 'continuationCommand', 'token') or at(find(root, 'nextContinuationData'), 'continuation')


def _sections(root):
    contents = at(root, 'contents')
    return (array(at(contents, 'singleColumnBrowseResultsRenderer', 'tabs', 0, 'tabRenderer', 'content', 'sectionListRenderer', 'contents'))
            or array(at(contents, 'twoColumnBrowseResultsRenderer', 'secondaryContents', 'sectionListRenderer', 'contents'))
            or array(at(contents, 'sectionListRenderer', 'contents')))


def _build(sections, root, album_page=False):
    shelves, tracks = [], []
    for section in sections:
        if not isinstance(section, dict) or not section:
            continue
        name, body = next(iter(section.items()))
        if name in ('musicPlaylistShelfRenderer', 'musicShelfRenderer'):
            entries = tuple(entry for row in array(at(body, 'contents')) if (entry := list_item(at(row, 'musicResponsiveListItemRenderer'))))
            title = runs_text(at(body, 'title'))
            if name == 'musicPlaylistShelfRenderer' or not title:
                tracks.extend(entry.track for entry in entries if entry.track)
            else:
                shelves.append(Shelf(title, entries, title))
        elif name in ('musicCarouselShelfRenderer', 'gridRenderer'):
            title = runs_text(at(body, 'header', 'musicCarouselShelfBasicHeaderRenderer' if name == 'musicCarouselShelfRenderer' else 'gridHeaderRenderer', 'title'))
            entries = tuple(entry for row in array(at(body, 'contents' if name == 'musicCarouselShelfRenderer' else 'items')) if (entry := carousel_item(row)))
            if entries:
                shelves.append(Shelf(title, entries, title))
    headers = ('musicResponsiveHeaderRenderer', 'musicImmersiveHeaderRenderer', 'musicVisualHeaderRenderer',
               'musicDetailHeaderRenderer', 'musicHeaderRenderer', 'musicEditablePlaylistDetailHeaderRenderer')
    header = next((item for key in headers if (item := find(root, key))), None)
    title = runs_text(at(header, 'title'))
    strapline = runs_text(at(header, 'straplineTextOne'))
    subtitle = ' · '.join(value for value in (runs_text(at(header, 'subtitle')), strapline) if value.strip())
    image = thumbnail(at(header, 'thumbnail')) or thumbnail(at(header, 'foregroundThumbnail'))
    tracks = [replace(track, artist=track.artist or strapline or title, thumbnail=track.thumbnail or image,
                      album=track.album or (title if album_page and title.strip() else None)) for track in tracks]
    chips = []
    for item in array(at(find(root, 'chipCloudRenderer'), 'chips')):
        row = at(item, 'chipCloudChipRenderer')
        endpoint = at(row, 'navigationEndpoint', 'browseEndpoint')
        if at(endpoint, 'browseId'):
            label = runs_text(at(row, 'text')) or (at(row, 'text') if isinstance(at(row, 'text'), str) else '')
            chips.append(Chip(label, endpoint['browseId'], endpoint.get('params')))
    return Page(title, subtitle, image, tuple(chips), tuple(shelves), tuple(tracks), continuation(root))


def parse_page(root, album_page=False):
    return _build(_sections(root), root, album_page)


def parse_continuation(root):
    bare = array(at(find(root, 'musicPlaylistShelfContinuation'), 'contents')) or array(at(find(root, 'musicShelfContinuation'), 'contents'))
    if bare:
        tracks = tuple(entry.track for row in bare if (entry := list_item(at(row, 'musicResponsiveListItemRenderer'))) and entry.track)
        return Page(tracks=tracks, continuation=continuation(root))
    sections = array(at(find(root, 'sectionListContinuation'), 'contents'))
    if not sections:
        sections = next((array(find(action, 'continuationItems')) for action in array(find(root, 'onResponseReceivedActions')) if find(action, 'continuationItems')), [])
    return _build(sections, root)


def watch_next(root):
    tracks = []
    for row in array(at(find(root, 'playlistPanelRenderer'), 'contents')):
        item = at(row, 'playlistPanelVideoRenderer') or at(row, 'playlistPanelVideoWrapperRenderer', 'primaryRenderer', 'playlistPanelVideoRenderer')
        if not isinstance(item, dict) or 'unplayableText' in item or item.get('isPlayable') is False:
            continue
        classification = at(item, 'navigationEndpoint', 'watchEndpoint', 'watchEndpointMusicSupportedConfigs', 'watchEndpointMusicConfig', 'musicVideoType')
        if classification not in ('MUSIC_VIDEO_TYPE_ATV', 'MUSIC_VIDEO_TYPE_OMV'):
            continue
        id = item.get('videoId')
        title = runs_text(item.get('title')) or at(item, 'title', 'simpleText')
        if not isinstance(id, str) or not VIDEO_ID.fullmatch(id) or not isinstance(title, str) or not title.strip():
            continue
        artist = next((r.get('text', '') for r in runs(item.get('longBylineText')) if r.get('text', '').strip() not in ('•','·','')), '')
        dur = runs_text(item.get('lengthText')) or at(item, 'lengthText', 'simpleText')
        tracks.append(Track(id, title, artist, durationSec=duration(dur), thumbnail=thumbnail(item.get('thumbnail'))))
    return tracks
