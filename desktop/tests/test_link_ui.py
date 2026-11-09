"""Actual native phone-parity link widgets, with explicit offline provider fixtures."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from dkord_desktop.qt import QApplication, QPushButton, BINDING
if BINDING == 'PyQt5':
    from PyQt5.QtTest import QTest
else:
    from PyQt6.QtTest import QTest
from dkord_desktop.models import Track
from dkord_desktop.store import Store
from dkord_desktop.ui import MainWindow
from test_core import tone
from test_ui import FixtureProvider


class NativeLinkWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([]); cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.provider = FixtureProvider(); self.provider.link_calls = []
        def link_source(link, cancel):
            self.provider.link_calls.append(link.url)
            return Track(link.video_id, 'Rare upload — audio flip (offline fixture)', 'Original uploader', durationSec=19)
        self.provider.open_youtube_link = link_source
        self.window = MainWindow(Store(Path(self.temp.name) / 'data'), self.provider, autoload=False)
        self.window.show(); self.app.processEvents()

    def tearDown(self):
        self.window.close()
        for pool in (self.window.pool, self.window.home_pool, self.window.download_pool, self.window.artwork_cache.pool):
            pool.waitForDone(10000)
        self.app.processEvents(); self.temp.cleanup()

    def wait(self, condition):
        end = time.monotonic() + 5
        while not condition() and time.monotonic() < end:
            self.app.processEvents(); QTest.qWait(10)
        self.assertTrue(condition())

    def test_separate_link_entry_is_discoverable_without_a_new_tab_or_clipboard_autoplay(self):
        self.window.navigate('Search'); self.app.processEvents()
        entry = self.window.findChild(QPushButton, 'open-youtube-link')
        self.assertTrue(entry.isVisible()); self.assertEqual(self.window.tr('youtube_link_open'), entry.text())
        self.app.clipboard().setText('https://youtu.be/AbCdEf012_-'); entry.click(); self.app.processEvents()
        panel = self.window.youtube_link_panel
        self.assertEqual('YouTube link', self.window.page); self.assertTrue(self.window.back_button.isVisible())
        self.assertEqual('', panel.input.text()); self.assertEqual([], self.provider.link_calls)
        self.assertEqual(['Home', 'Search', 'Listen Again', 'Library', 'Downloads'], list(self.window.nav_buttons))
        self.assertTrue(self.window.player.source().isEmpty()); self.assertFalse(panel.preview.isVisible())

    def test_link_paste_preview_and_play_are_distinct_and_reuse_exact_track_and_standard_menu(self):
        self.window.youtube_link_button.click(); self.app.processEvents(); panel = self.window.youtube_link_panel
        self.app.clipboard().setText('https://music.youtube.com/watch?v=AbCdEf012_-&list=PL_playlist&si=share')
        panel.paste_button.click(); self.app.processEvents()
        self.assertEqual([], self.provider.link_calls); self.assertFalse(panel.preview.isVisible())
        panel.resolve_button.click(); self.wait(lambda: panel.track is not None)
        self.assertEqual(['https://www.youtube.com/watch?v=AbCdEf012_-'], self.provider.link_calls)
        self.assertEqual(self.provider.link_calls[0], panel.canonical.text()); self.assertIn('offline fixture', panel.title.text())
        self.assertTrue(self.window.player.source().isEmpty()); self.assertEqual([], self.provider.calls)
        with patch.object(self.window, 'play_track') as play, patch.object(self.window, 'track_menu') as menu:
            panel.more_button.click(); menu.assert_called_once(); self.assertEqual(panel.track, menu.call_args.args[0]); play.assert_not_called()
            panel.play_button.click(); play.assert_called_once_with(panel.track, related=False)

    def test_link_invalid_and_playlist_only_errors_do_not_fetch_arbitrary_hosts_or_touch_playback(self):
        self.window.navigate('YouTube link'); panel = self.window.youtube_link_panel
        for value, key in [('https://untrusted.test/watch?v=AbCdEf012_-', 'youtube_link_invalid'),
                           ('https://youtube.com/playlist?list=PL_playlist', 'youtube_link_playlist_only')]:
            panel.input.setText(value); panel.resolve_button.click(); self.app.processEvents()
            self.assertEqual(self.window.tr(key), panel.error.text()); self.assertTrue(panel.error.isVisible())
            self.assertIsNone(panel.track); self.assertFalse(panel.preview.isVisible()); self.assertEqual([], self.provider.link_calls)
        self.assertTrue(self.window.player.source().isEmpty()); self.assertEqual([], self.provider.calls)

    def test_link_preview_never_writes_library_history_settings_downloads_studio_or_source_files(self):
        old = Track('online00001', 'Keep this song', 'Artist'); store = self.window.store
        store.like(old, True); store.history(old, 1234); store.save_playlist('Keep playlist', [old]); store.set_setting('quality', 'medium')
        original = Path(self.temp.name) / 'untouched-original.wav'; tone(original); original_bytes = original.read_bytes()
        project = store.create_project('Keep Studio project'); store.queue_download(old, 'app')
        self.window.queue = [old]; self.window.index = 0; self.window.timer.stop()
        with store.connect() as db:
            before = list(db.iterdump())
        self.window.navigate('YouTube link'); panel = self.window.youtube_link_panel
        panel.input.setText('https://youtu.be/AbCdEf012_-'); panel.resolve_button.click(); self.wait(lambda: panel.track is not None)
        panel.input.setText('not a link'); panel.resolve_button.click(); self.app.processEvents()
        with store.connect() as db:
            self.assertEqual(before, list(db.iterdump()))
        self.assertEqual([old], self.window.queue); self.assertEqual(original_bytes, original.read_bytes())
        self.assertIsNotNone(store.project(project)); self.assertTrue(self.window.player.source().isEmpty())

    def test_return_from_link_restores_search_rows_query_scope_cursor_and_saved_queries_without_research(self):
        self.window.query.setText('Keep results'); self.window.scope.setCurrentText('Music videos'); self.window.search()
        self.wait(lambda: self.window.table is not None)
        before = (list(self.provider.calls), self.window.store.queries(), list(self.window.entries), self.window.search_cursor)
        self.window.search_link_button.click(); self.app.processEvents(); self.window.go_back(); self.app.processEvents()
        self.assertEqual('Search', self.window.page); self.assertEqual('Keep results', self.window.query.text())
        self.assertEqual('Music videos', self.window.scope.currentText()); self.assertIsNotNone(self.window.table)
        self.assertEqual(before, (self.provider.calls, self.window.store.queries(), self.window.entries, self.window.search_cursor))
        self.assertEqual([], self.provider.link_calls); self.assertTrue(self.window.player.source().isEmpty())

    def test_link_edit_and_navigation_ignore_an_uncancellable_late_lookup(self):
        started = threading.Event(); release = threading.Event()
        def load(link, cancel):
            self.provider.link_calls.append(link.url)
            if link.video_id == 'AbCdEf012_-':
                started.set(); release.wait(5)
            return Track(link.video_id, 'Exact fixture upload', 'Uploader')
        self.provider.open_youtube_link = load; self.window.navigate('YouTube link'); panel = self.window.youtube_link_panel
        try:
            panel.input.setText('https://youtu.be/AbCdEf012_-'); panel.resolve_button.click(); self.wait(started.is_set)
            panel.resolve(); self.assertEqual(1, len(self.provider.link_calls))
            panel.input.setText('https://youtube.com/shorts/ZyXwVu987_-'); panel.resolve_button.click()
            self.wait(lambda: panel.track is not None); self.assertEqual('ZyXwVu987_-', panel.track.id)
            release.set(); self.window.pool.waitForDone(3000); self.app.processEvents()
            self.assertEqual('ZyXwVu987_-', panel.track.id); self.assertFalse(panel.error.isVisible())
            panel.input.setText('https://youtu.be/AbCdEf012_-'); self.assertIsNone(panel.track); self.assertFalse(panel.preview.isVisible())
            self.window.navigate('Library'); self.app.processEvents(); self.assertFalse(panel.work['active'])
        finally:
            release.set()
        self.assertTrue(self.window.player.source().isEmpty()); self.assertEqual([], self.provider.calls)

    def test_link_cancel_button_clears_busy_state_and_queued_callbacks_cannot_show_a_late_result(self):
        callbacks = []
        class Work:
            def __init__(self):
                self.cancel = threading.Event()
        def queue(call, done=None, failed=None, **kwargs):
            task = Work(); callbacks.append((done, failed, task)); return task
        self.window.navigate('YouTube link'); panel = self.window.youtube_link_panel
        with patch.object(self.window, 'run', side_effect=queue):
            panel.input.setText('https://youtu.be/AbCdEf012_-'); panel.resolve_button.click(); self.app.processEvents()
            self.assertTrue(panel.busy.isVisible()); self.assertFalse(panel.resolve_button.isEnabled())
            panel.cancel_button.click(); self.app.processEvents(); self.assertFalse(panel.loading)
            self.assertTrue(callbacks[0][2].cancel.is_set()); self.assertTrue(panel.resolve_button.isEnabled())
            callbacks[0][0]((Track('AbCdEf012_-', 'Stale success', 'Uploader'), None)); callbacks[0][1]('stale failure')
            self.assertIsNone(panel.track); self.assertFalse(panel.preview.isVisible()); self.assertFalse(panel.error.isVisible())
            panel.resolve_button.click(); self.window.navigate('Home', fetch=False); self.app.processEvents()
            callbacks[1][0]((Track('AbCdEf012_-', 'Stale route', 'Uploader'), None)); self.assertEqual('Home', self.window.page)
        self.assertTrue(self.window.player.source().isEmpty())

    def test_link_provider_failure_and_wrong_identity_have_no_fake_success_and_retry_stays_exact(self):
        from dkord_desktop.youtube_links import YouTubeLinkError
        def fail(link, cancel):
            raise YouTubeLinkError('private')
        self.provider.open_youtube_link = fail; self.window.navigate('YouTube link'); panel = self.window.youtube_link_panel
        panel.input.setText('https://youtu.be/AbCdEf012_-'); panel.resolve_button.click(); self.wait(lambda: not panel.loading)
        self.assertEqual(self.window.tr('err_private'), panel.error.text()); self.assertFalse(panel.preview.isVisible())
        self.provider.open_youtube_link = lambda link, cancel: Track('ZyXwVu987_-', 'Wrong video', 'Uploader')
        panel.resolve_button.click(); self.wait(lambda: not panel.loading); self.assertIsNone(panel.track)
        self.assertEqual(self.window.tr('err_unavailable'), panel.error.text())
        self.provider.open_youtube_link = lambda link, cancel: Track(link.video_id, 'Exact upload', 'Uploader')
        panel.resolve_button.click(); self.wait(lambda: panel.track is not None)
        self.assertEqual('AbCdEf012_-', panel.track.id); self.assertFalse(panel.error.isVisible()); self.assertTrue(self.window.player.source().isEmpty())

    def test_hindi_link_page_has_readable_compact_controls_and_the_same_preview_actions(self):
        self.window.change_language('hi'); self.window.resize(420, 720); self.window.youtube_link_button.click(); self.app.processEvents()
        panel = self.window.youtube_link_panel
        self.assertEqual(self.window.tr('youtube_link_open'), self.window.heading.text())
        self.assertEqual('लिंक पेस्ट करें', panel.paste_button.text()); self.assertEqual('वीडियो दिखाएँ', panel.resolve_button.text())
        panel.input.setText('https://youtu.be/AbCdEf012_-'); panel.resolve_button.click(); self.wait(lambda: panel.track is not None)
        self.assertEqual('चलाएँ', panel.play_button.text()); self.assertTrue(panel.more_button.isVisible())
        for widget in (panel.input, panel.paste_button, panel.resolve_button, panel.more_button, panel.play_button):
            rect = widget.rect().translated(widget.mapTo(panel, self.window.rect().topLeft()))
            self.assertTrue(panel.rect().contains(rect), (widget.objectName(), rect, panel.rect()))
        self.assertTrue(self.window.player.source().isEmpty()); self.assertEqual([], self.provider.calls)


if __name__ == '__main__':
    unittest.main()
