"""Requested real native screenshots, never an AI/browser reconstruction.

All content is isolated, explicitly labelled OFFLINE DEMO. Generated tones are
real local WAV files. Search/link metadata is a fixture, not live provider proof.
Normal launch never imports or runs this opt-in QA command.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import sys
import tempfile
import threading
import time
from uuid import uuid4

from . import __version__
from .capture import NoNetwork, tone
from .catalogue import Page, Shelf, Chip
from .media import MediaLibrary
from .models import Track
from .platforms import platform_key
from .provider import Entry, SearchPage
from .qt import QApplication, BINDING, QDialog, QLineEdit, QTimer, QtCore, QtWidgets
from .store import Store
from .ui import MainWindow

DEMO = 'OFFLINE DEMO · generated tones / sample metadata · no live provider'
# Stable screen IDs make a partial or missing gallery a validation failure.
from .gallery_contract import SCREENS


class GalleryProvider(NoNetwork):
    """Explicit screenshot fixtures. They must never be mistaken for live results."""
    def __init__(self, tracks):
        self.tracks = tuple(tracks)
        self.entries = tuple(Entry('song', t.id, t.title, t.artist, t) for t in tracks)
        self.link_calls = 0

    def search(self, query, scope='Songs', limit=20):
        return list(self.entries)

    def search_page(self, query, scope='Songs', exact=False):
        return SearchPage(self.entries)

    def suggestions(self, query):
        return []

    def open_youtube_link(self, link, cancel=None):
        self.link_calls += 1
        return Track(link.video_id, 'Sample upload · OFFLINE metadata fixture',
                     'Demo uploader · not a live YouTube result', durationSec=12)


def capture_gallery(app, output: Path):
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError('Gallery output must be new/empty; never overwrite a library or previous capture')
    output.mkdir(parents=True, exist_ok=True)
    records = []
    old_language = app.property('dkord-language')
    with tempfile.TemporaryDirectory(prefix='dkord-native-gallery-') as temporary:
        root = Path(temporary)
        store = Store(root / 'isolated-data')
        media = MediaLibrary(store, NoNetwork())
        tracks, files = [], []
        for title, frequency in (('Warm glow', 220), ('Midnight pulse', 440), ('First light', 880), ('Quiet horizon', 330)):
            path = media.offline / (title + '.wav')
            tone(path, frequency)
            track = Track('studio:' + str(uuid4()), title + ' · generated tone',
                          'Dkord offline demo', 'Generated audio samples', 12)
            store.put_track(track)
            store.queue_download(track, 'app')
            store.update_download(track.id, state='DONE', path=str(path), bytes=path.stat().st_size, total=path.stat().st_size)
            store.like(track, True); store.history(track, 3200)
            tracks.append(track); files.append(path)
        playlist = store.save_playlist('Offline demo · generated tones', tracks)
        store.remember_query('Generated tones · offline demo', 'Songs')
        store.set_setting('session', {'version': 1, 'queue': [t.json() for t in tracks], 'index': 0, 'position': 3200})
        project = store.create_project('Offline demo · two-source mix')
        for file in files[:2]:
            media.import_source(project, file, threading.Event())
        def edit(data):
            data['clips'][0]['startMs'] = 1000; data['clips'][0]['endMs'] = 5500
            data['clips'][1]['startMs'] = 2000; data['clips'][1]['endMs'] = 9000
        store.change_project(project, edit)
        provider = GalleryProvider(tracks)
        window = MainWindow(store, provider, autoload=False)
        window.resize(1440, 960)
        window.show()
        window.timer.stop()  # Keep the paused demo position deterministic; never claim heard audio.
        window.studio_id = project
        from types import SimpleNamespace
        window.lyrics_repository = SimpleNamespace(load=lambda track, cancel: None)

        def settle(seconds=.22):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                app.processEvents()
                QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
                time.sleep(.01)

        def wait(condition):
            deadline = time.monotonic() + 8
            while not condition() and time.monotonic() < deadline:
                settle(.02)
            if not condition():
                raise ValueError('Actual gallery UI did not finish its isolated fixture operation')

        def shot(name, title, widget=None):
            if name not in SCREENS or name in {r['id'] for r in records}:
                raise ValueError('Unexpected or repeated gallery screen')
            widget = widget or window
            window.notify(DEMO)
            settle()
            if not widget.isVisible():
                raise ValueError('Cannot capture a hidden or fabricated widget')
            image = widget.grab()
            path = output / (name + '.png')
            if image.isNull() or not image.save(str(path), 'PNG'):
                raise ValueError('Actual native widget capture failed')
            data = path.read_bytes()
            records.append(dict(id=name, title=title, name=path.name, bytes=len(data),
                                sha256=hashlib.sha256(data).hexdigest(), width=image.width(), height=image.height(),
                                page=window.page, widget=type(widget).__name__,
                                language=store.setting('language', 'en'), theme=window.effective_theme(),
                                data='OFFLINE DEMO; generated tones and explicitly labelled metadata fixtures'))

        def page(target, name, title):
            window.navigate(target, fetch=False)
            window.content_scroll.verticalScrollBar().setValue(0)
            shot(name, title)

        def modal(name, title, invoke, setup=None):
            failures = []
            captured = []
            def ready():
                dialog = QApplication.activeModalWidget()
                try:
                    if not isinstance(dialog, QDialog):
                        raise ValueError('Expected the real production modal dialog')
                    if setup:
                        setup(dialog)
                    shot(name, title, dialog)
                    captured.append(True)
                except Exception as error:
                    failures.append(error)
                finally:
                    if isinstance(dialog, QDialog):
                        dialog.reject()  # Cancel: never download/export or modify project via screenshots.
            QTimer.singleShot(100, ready)
            invoke()
            if failures:
                raise failures[0]
            if not captured:
                raise ValueError('No actual modal was captured')

        try:
            home = Page(title='Offline demo', chips=(Chip('Instrumental demo', 'demo-chip'),), shelves=(
                Shelf('Generated tones · offline demo', provider.entries),
                Shelf('Local audio showcase · not a live catalogue', tuple(reversed(provider.entries))),
            ))
            window.home_data = home
            page('Home', '01-home', 'Home · actual native shelves and navigation')
            window.content_scroll.verticalScrollBar().setValue(window.content_scroll.verticalScrollBar().maximum())
            shot('02-home-discovery', 'Home · discovery shelves (offline fixtures)')
            page('Search', '03-search-history', 'Search · saved queries and separate link entry')
            window.query.setText('Generated tones · OFFLINE demo')
            window.search(); wait(lambda: window.table is not None)
            shot('04-search-songs', 'Search · Songs results (explicit offline fixtures)')
            window.scope.setCurrentText('All YouTube'); window.search(); wait(lambda: window.table is not None)
            shot('05-search-all-youtube', 'Search · broader filter (explicit offline fixtures)')
            page('YouTube link', '06-link-empty', 'Open YouTube link · empty input')
            panel = window.youtube_link_panel
            panel.input.setText('https://youtu.be/AbCdEf012_-')
            shot('07-link-pasted', 'Open YouTube link · entered sample URL, not submitted')
            panel.resolve(); wait(lambda: panel.track is not None)
            shot('08-link-preview', 'Exact link preview · OFFLINE sample metadata, not live playback proof')
            panel.input.setText('https://example.invalid/not-youtube'); panel.resolve()
            shot('09-link-invalid', 'Open YouTube link · invalid-link feedback')
            panel.input.setText('https://www.youtube.com/playlist?list=PL_demo'); panel.resolve()
            shot('10-link-playlist-only', 'Open YouTube link · individual-video guidance')
            page('Library', '11-library', 'Library · playlists, Studio and Listen Together')
            page('Liked songs', '12-liked-songs', 'Liked songs · real local generated audio')
            page('Listen Again', '13-listen-again', 'Listen Again · isolated local history')
            window.browse_result('Offline demo playlist', tracks)
            shot('14-playlist', 'Playlist · generated local tracks')
            page('Downloads', '15-downloads', 'Downloads · actual generated WAV files')
            modal('16-download-destinations', 'Download destination chooser · cancelled without enqueueing', lambda: window.choose_download([tracks[0]]))
            page('Mashup Studio', '17-studio', 'Mashup Studio · real generated sources and precise clip ranges')
            source = store.project(project)['sources'][0]
            modal('18-studio-clip-editor', 'Studio clip editor · actual millisecond controls', lambda: window.edit_clip(source))
            modal('19-studio-online-picker', 'Studio online-song picker · no provider request', window.online_picker)
            page('Listen Together', '20-listen-together', 'Listen Together · create/join hub, no room started')
            window.show_full_player(0); settle()
            shot('21-player', 'Full player · paused generated tone', window.full_player)
            window.full_player.tabs.setCurrentIndex(2)
            shot('22-player-queue', 'Full player · queue of generated tones', window.full_player)
            window.full_player.tabs.setCurrentIndex(1); settle()
            shot('23-player-lyrics', 'Full player · honest unavailable lyrics for generated tones', window.full_player)
            window.full_player.hide()
            modal('24-sleep-timer', 'Sleep timer · actual controls, cancelled', window.sleep_timer)
            page('Settings', '25-settings', 'Settings · language, theme, quality, local diagnostics and updates')
            modal('26-about', 'About · actual concise © 2026 dKORD dialog', window.about)
            window.apply_theme('light'); window.navigate('Library', fetch=False)
            shot('27-light-theme', 'Light theme · Library')
            window.apply_theme('amoled'); window.navigate('Library', fetch=False)
            shot('28-amoled-theme', 'AMOLED theme · Library')
            window.apply_theme('dark'); window.change_language('hi'); window.navigate('YouTube link', fetch=False)
            window.youtube_link_panel.input.setText('https://youtu.be/AbCdEf012_-')
            window.youtube_link_panel.resolve(); wait(lambda: window.youtube_link_panel.track is not None)
            shot('29-hindi-link', 'Hindi · native exact-link page, offline sample metadata')
            window.change_language('en'); window.resize(760, 900); window.navigate('Library', fetch=False)
            shot('30-compact-layout', 'Compact PC window · responsive Library and bottom navigation')
            if {r['id'] for r in records} != set(SCREENS) or provider.link_calls != 2:
                raise ValueError('Incomplete gallery or unexpected fixture extraction')
        finally:
            window.close()
            for pool in (window.pool, window.download_pool, window.home_pool, window.artwork_cache.pool):
                pool.waitForDone()
            settle(.05)
            app.setProperty('dkord-language', old_language)
    proof = dict(format=1, application='Dkord', version=__version__, source=os.environ.get('DKORD_SOURCE_SHA', 'local'),
                 platform=platform_key(), os=platform.system(), python_bits=struct.calcsize('P') * 8,
                 qt_binding=BINDING, qt_version=QtCore.QT_VERSION_STR, frozen=bool(getattr(sys, 'frozen', False)),
                 capture='actual QWidget.grab from production native Qt pages and dialogs; no compositing or AI',
                 data=DEMO, liveProviderTested=False, heardAudioTested=False, userDataAccessed=False, images=records)
    (output / 'gallery-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    return 0
