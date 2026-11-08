"""Real native Qt widgets/events, not browser rendering. OS-level IME/live-provider acceptance is separate."""
import tempfile
import time
import unittest
import sys
from unittest.mock import patch
from pathlib import Path
from dkord_desktop.qt import Qt,QTimer,QLockFile,QApplication,QDialog,QLineEdit,QPushButton,BINDING
if BINDING == "PyQt5":
    from PyQt5.QtTest import QTest
else:
    from PyQt6.QtTest import QTest
from dkord_desktop.ui import MainWindow
from dkord_desktop.models import Track
from dkord_desktop.provider import Entry
from dkord_desktop.store import Store
from test_core import tone

class FixtureProvider:
    def __init__(self):self.calls=[]
    def search(self,query,scope='Songs',limit=20):
        self.calls.append((query,scope,limit));track=Track('online00001','संगवारी — Choliwood','Fixture artist');return [Entry('song',track.id,track.title,track.artist,track)]
    def resolve(self,track):raise AssertionError('Typing/search must not start network playback')

class NativeWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.provider=FixtureProvider();self.window=MainWindow(Store(Path(self.temp.name)/'data'),self.provider,autoload=False);self.window.show();self.app.processEvents()
    def tearDown(self):
        self.window.close();self.window.pool.waitForDone(10000);self.app.processEvents();self.temp.cleanup()
    def wait(self,condition):
        end=time.monotonic()+5
        while not condition() and time.monotonic()<end:self.app.processEvents();QTest.qWait(10)
        self.assertTrue(condition())
    def test_typing_spaces_does_not_search_or_start_audio(self):
        self.window.query.setFocus();QTest.keyClicks(self.window.query,'Choliwood instrumental covers')
        self.assertEqual('Choliwood instrumental covers',self.window.query.text());self.assertEqual([],self.provider.calls);self.assertTrue(self.window.player.source().isEmpty())
    def test_explicit_unicode_search_keeps_real_provider_identity_and_song_scope(self):
        self.window.query.setText('संगवारी Choliwood');QTest.keyClick(self.window.query,Qt.Key.Key_Return)
        self.wait(lambda:self.window.table is not None)
        self.assertEqual([('संगवारी Choliwood','Songs',20)],self.provider.calls)
        self.assertIn('संगवारी',self.window.table.item(0,0).text());self.assertTrue(self.window.player.source().isEmpty())
    def test_cancel_download_chooser_writes_no_download_or_false_destination(self):
        track=Track('online00001','Song','Artist')
        def cancel():
            dialog=self.app.activeModalWidget();self.assertIsInstance(dialog,QDialog)
            for button in dialog.findChildren(QPushButton):
                if button.text()=='Cancel':button.click();return
            self.fail('Visible Cancel action is required')
        QTimer.singleShot(50,cancel);self.window.choose_download([track]);self.assertIsNone(self.window.store.download(track.id))
    def test_clip_editor_rejects_bad_range_then_saves_millisecond_range_without_replacing_source(self):
        file=Path(self.temp.name)/'original.wav';tone(file);project=self.window.store.create_project('Precise mix')
        import threading
        source=self.window.library.import_source(project,file,threading.Event());self.window.studio_id=project;self.window.navigate('Mashup Studio')
        def edit():
            dialog=self.app.activeModalWidget();start=dialog.findChild(QLineEdit,'studio-start');end=dialog.findChild(QLineEdit,'studio-end')
            save=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Save clip')
            start.setText('1.0');end.setText('0.0');save.click();self.assertTrue(dialog.isVisible())
            start.setText('0.123');end.setText('1.234');save.click()
        QTimer.singleShot(50,edit);self.window.edit_clip(source)
        clip=self.window.store.project(project)['clips'][-1];self.assertEqual((123,1234),(clip['startMs'],clip['endMs']));self.assertTrue(file.is_file())

    def test_update_restart_drains_workers_and_releases_real_data_lock_before_relaunch(self):
        from dkord_desktop.__main__ import main
        root=Path(self.temp.name)/'entry-library';store=Store(root);store.set_setting('retained','existing playlists and offline data')
        observations=[];spawned=[]
        def create_window(actual_store):
            window=MainWindow(actual_store,self.provider,autoload=False);spawned.append(window)
            def cleanup(cancel,progress):
                cancel.wait(5);time.sleep(.75);actual_store.set_setting('drained','cleanup committed')
            window.run(cleanup)
            def restarted():
                next_lock=QLockFile(str(root/'application.lock'));acquired=next_lock.tryLock(0)
                observations.append((acquired,actual_store.setting('drained'),window.pool.activeThreadCount(),actual_store.setting('retained')))
                if acquired:next_lock.unlock()
            window.restart_after_close=restarted
            def quit():
                window.close();self.app.quit()
            QTimer.singleShot(0,quit)
            return window
        with patch.object(sys,'argv',['dkord','--data-dir',str(root)]),patch('dkord_desktop.qt.QApplication',return_value=self.app),patch('dkord_desktop.qt.QMessageBox.critical') as error,patch('dkord_desktop.ui.MainWindow',side_effect=create_window):
            code=main()
        self.assertEqual(0,code,str(error.call_args));error.assert_not_called()
        self.assertEqual([(True,'cleanup committed',0,'existing playlists and offline data')],observations)
        self.assertEqual([],self.provider.calls)

    def test_real_capture_uses_isolated_store_and_actual_widget_pixels_without_network_or_overwrite(self):
        from dkord_desktop.capture import capture
        from dkord_desktop.qt import QImage
        from dkord_desktop.platforms import platform_key
        import hashlib,json,platform
        canary=Path(self.temp.name)/'original-user-file';canary.write_bytes(b'KEEP existing original music and library')
        output=Path(self.temp.name)/'isolated-capture'
        self.assertEqual(0,capture(self.app,output))
        proof=json.loads((output/'windows-x86-screenshot-proof.json').read_text(encoding='utf-8'))
        self.assertEqual(platform_key(),proof['platform']);self.assertEqual(platform.system(),proof['os']);self.assertIs(False,proof['frozen'])
        self.assertEqual({'Liked songs','Mashup Studio'},{x['page'] for x in proof['images']})
        for item in proof['images']:
            path=output/item['name'];image=QImage(str(path))
            self.assertFalse(image.isNull());self.assertGreaterEqual(image.width(),1360);self.assertGreaterEqual(image.height(),850)
            self.assertEqual(item['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        before={p.name:p.read_bytes() for p in output.iterdir()}
        with self.assertRaises(ValueError):capture(self.app,output)
        self.assertEqual(before,{p.name:p.read_bytes() for p in output.iterdir()})
        self.assertEqual(b'KEEP existing original music and library',canary.read_bytes());self.assertEqual([],self.provider.calls)

    def test_theme_choice_persists_without_changing_likes_or_original_audio(self):
        track=Track('online00001','संगवारी','Artist');self.window.store.like(track,True)
        file=Path(self.temp.name)/'theme-original.wav';tone(file);before=file.read_bytes()
        self.window.apply_theme('light');self.app.processEvents()
        reopened=Store(self.window.store.root)
        self.assertEqual('light',reopened.setting('theme'));self.assertEqual([track],reopened.library('liked'))
        self.assertEqual(before,file.read_bytes());self.assertTrue(self.window.player.source().isEmpty())

    def test_real_player_output_bridge_retains_volume_and_empty_source_semantics(self):
        from dkord_desktop.qt import QtCore,QWidget
        self.window.resize(1024,768);self.app.processEvents()
        player=self.window.findChild(QWidget,'player')
        for control in (self.window.now,self.window.now_artist,self.window.previous_button,self.window.play_button,self.window.next_button):
            rect=control.rect().translated(control.mapTo(player,QtCore.QPoint(0,0)))
            self.assertTrue(player.rect().contains(rect),(control.objectName(),rect,player.rect()))
        # Phone secondary controls moved to the FULL player, not removed or squeezed
        # into the mini-player. Test their actual new native container and bounds.
        self.window.queue=[Track('online00001','Long title for the native full player','Artist')]
        self.window.show_full_player();self.app.processEvents();full=self.window.full_player
        for control in (self.window.repeat,self.window.speed,self.window.shuffle,self.window.seek,full.play_toggle):
            rect=control.rect().translated(control.mapTo(full,QtCore.QPoint(0,0)))
            self.assertTrue(full.rect().contains(rect),(control.objectName(),rect,full.rect()))
        self.assertFalse(self.window.now.wordWrap());self.assertFalse(self.window.now_artist.wordWrap())
        self.assertGreaterEqual(self.window.repeat.width(),116);self.assertEqual(92,self.window.speed.width())
        self.window.audio.setVolume(.42)
        self.assertAlmostEqual(.42,self.window.audio.volume(),places=3)
        self.assertIs(self.window.audio,self.window.player.audioOutput())
        self.assertTrue(self.window.player.source().isEmpty())
        if BINDING=='PyQt5':self.assertEqual(42,self.window.player.volume())
        self.assertEqual(self.window.player.PlaybackState.StoppedState,self.window.player.playbackState())

    def test_same_five_phone_destinations_switch_between_pc_rail_and_compact_bottom_nav(self):
        self.assertEqual(['Home','Search','Listen Again','Library','Downloads'],list(self.window.nav_buttons))
        self.window.resize(1024,768);self.app.processEvents()
        self.assertTrue(self.window.sidebar.isVisible());self.assertFalse(self.window.bottom_nav.isVisible())
        self.window.resize(640,720);self.app.processEvents()
        self.assertFalse(self.window.sidebar.isVisible());self.assertTrue(self.window.bottom_nav.isVisible())
        self.assertEqual(5,len(self.window.bottom_buttons));self.assertTrue(all(b.isVisible() for b in self.window.bottom_buttons.values()))
        self.assertEqual([],self.provider.calls);self.assertTrue(self.window.player.source().isEmpty())

    def test_library_opens_a_global_room_hub_without_a_song_or_implicit_relay_connection(self):
        self.window.navigate('Library');self.app.processEvents()
        entry=self.window.findChild(QPushButton,'library-listen-together');self.assertIsNotNone(entry);entry.click();self.app.processEvents()
        self.assertEqual('Listen Together',self.window.page);self.assertIsNone(self.window.rooms.session)
        self.assertTrue(self.window.findChild(QPushButton,'room-create').isVisible())
        self.assertTrue(self.window.findChild(QPushButton,'room-join').isVisible());self.assertTrue(self.window.player.source().isEmpty())

    def test_professional_about_has_copyright_without_repository_links_or_technical_paragraphs(self):
        from dkord_desktop.qt import QLabel
        def inspect():
            dialog=self.app.activeModalWidget();self.assertIsInstance(dialog,QDialog)
            content=' '.join(label.text() for label in dialog.findChildren(QLabel))
            self.assertIn('© 2026 dKORD',content);self.assertNotIn('GitHub',content);self.assertNotIn('https://',content)
            self.assertNotIn('notarization',content);dialog.accept()
        QTimer.singleShot(50,inspect);self.window.about()

    def test_full_player_has_artwork_lyrics_queue_and_timestamp_free_clickable_synced_lines(self):
        from dkord_desktop.lyrics import Lyrics,parse_lrc
        class Repository:
            def load(self,track,cancel):return Lyrics(parse_lrc('[00:01.23]पहली पंक्ति\n[00:02.4]Second line'),'पहली पंक्ति\nSecond line')
        self.window.lyrics_repository=Repository();self.window.queue=[Track('online00001','Song','Artist')]
        self.window.show_full_player(1);full=self.window.full_player
        self.wait(lambda:full.lyrics_view.count()==2)
        self.assertEqual(3,full.tabs.count());self.assertEqual('पहली पंक्ति',full.lyrics_view.item(0).text())
        full.seek_lyric(full.lyrics_view.item(0));self.assertEqual(1230,self.window.pending_seek)
        self.assertTrue(self.window.player.source().isEmpty());self.assertFalse(self.window.desired_playing)

    def test_selecting_a_song_in_any_collection_keeps_its_whole_playlist_and_selected_index(self):
        tracks=[Track('abcdefghijk','One','Artist'),Track('lmnopqrstuv','Two','Artist')]
        self.window.browse_result('Any playlist',tracks)
        with patch.object(self.window,'play_index') as start:
            self.window.open_entry(self.window.entries[1],1)
        self.assertEqual(tracks,self.window.queue);self.assertEqual(1,self.window.index)
        start.assert_called_once_with(1,user=True);self.assertTrue(self.window.player.source().isEmpty())

    def test_queued_cancelled_background_work_does_not_call_a_provider(self):
        from dkord_desktop.tasks import Task
        called=[];task=Task(lambda cancel,progress:called.append(True));task.cancel.set();task.run()
        self.assertEqual([],called)

    def test_diagnostic_copy_is_local_private_and_contains_no_repository_or_song_metadata(self):
        self.window.queue=[Track('online00001','Private song title','Private artist')]
        self.window.diagnostics.record('playback','prepare_failed');self.window.copy_diagnostics()
        report=self.app.clipboard().text()
        self.assertIn('Dkord playback diagnostics',report);self.assertIn('playback: prepare_failed',report)
        for value in ('Private song title','Private artist','https://','github','online00001'):
            self.assertNotIn(value,report)
        self.assertEqual([],self.provider.calls);self.assertIsNone(self.window.rooms.session)

    def test_inline_new_releases_uses_the_actual_selected_window_and_choliwood_category(self):
        class Repository:
            def __init__(self):self.calls=[]
            def songs(self,window,category,refresh,cancel):
                self.calls.append((window,category,refresh));return [Track('online00001','Dated release','Artist')]
        repository=Repository();self.window.releases_repository=repository;self.window.new_releases_page()
        self.wait(lambda:self.window.release_tracks is not None)
        self.assertEqual([('LAST_7_DAYS','ALL',False)],repository.calls)
        self.window.select_release('CHOLIWOOD',True);self.wait(lambda:self.window.release_tracks is not None)
        self.window.select_release('LAST_24_HOURS');self.wait(lambda:self.window.release_tracks is not None)
        self.assertEqual(('LAST_24_HOURS','CHOLIWOOD',False),repository.calls[-1])
        buttons=self.window.findChildren(QPushButton,'release-choliwood');self.assertTrue(any(b.isVisible() and b.isChecked() for b in buttons))
        self.assertEqual('Home',self.window.page);self.assertEqual([],self.provider.calls)
        self.window.new_releases_page();self.assertFalse(self.window.release_expanded)

    def test_optional_video_has_a_separate_native_player_and_never_auto_resumes_music_on_close(self):
        from dkord_desktop.video_view import VideoPlayer
        video=VideoPlayer(self.window,Track('online00001','Video','Artist'),autoload=False)
        self.assertIsNot(video.player,self.window.player);video.show();self.app.processEvents();video.close()
        self.assertTrue(video.closing);self.assertFalse(self.window.desired_playing)
        self.assertTrue(self.window.player.source().isEmpty());self.assertEqual([],self.provider.calls)

    def test_stale_cover_result_cannot_replace_new_song_and_capacity_rejection_is_retryable(self):
        from dkord_desktop.artwork import Cover
        from dkord_desktop.qt import QPixmap,QColor
        cache=self.window.artwork_cache;cache.timer.stop()
        old='https://i.ytimg.com/vi/abcdefghijk/a.jpg';new='https://i.ytimg.com/vi/lmnopqrstuv/b.jpg'
        cover=Cover(cache,old);cover.set_url(new);image=QPixmap(8,8);image.fill(QColor('#ff2d2d'))
        cover.loaded(image,old);self.assertIsNone(cover.pixmap_data)
        cover.loaded(image,new);self.assertIsNotNone(cover.pixmap_data)
        cache.pending={f'https://i.ytimg.com/{index}.jpg':[] for index in range(64)}
        self.assertIs(False,cache.request('https://i.ytimg.com/retry.jpg',lambda _:None))
        self.assertIs(True,cache.request('http://untrusted.test/image.jpg',lambda _:None))
        self.assertEqual(0,cache.pool.activeThreadCount());cover.deleteLater()

    def test_failed_preparation_keeps_the_queue_but_clears_play_intent_and_records_only_an_event_code(self):
        def fail(track):raise RuntimeError('Fixture unavailable https://private.test/?token=not-for-ui')
        self.provider.resolve=fail;self.window.play_queue([Track('online00001','Keep this song','Artist')])
        self.wait(lambda:not self.window.desired_playing)
        self.assertEqual('online00001',self.window.current().id);self.assertEqual('play',self.window.play_button.accessibleName().lower())
        self.assertTrue(any(kind=='playback' and code=='prepare_failed' for _,kind,code in self.window.diagnostics.events))
        self.assertNotIn('https://',self.window.statusBar().currentMessage())

    def test_music_search_loads_a_real_cursor_page_once_without_researching_or_dropping_existing_rows(self):
        from dkord_desktop.provider import SearchPage,SearchCursor
        one=Track('abcdefghijk','First','Artist');two=Track('lmnopqrstuv','Second','Artist');calls=[]
        cursor=SearchCursor('Original','Songs','opaque_cursor','params')
        def first(query,scope,exact):calls.append(('first',query,scope,exact));return SearchPage((Entry('song',one.id,one.title,one.artist,one),),cursor,'Corrected',True)
        def more(actual):calls.append(('more',actual));return SearchPage((Entry('song',two.id,two.title,two.artist,two),))
        self.provider.search_page=first;self.provider.search_more=more
        self.window.query.setText('Original');self.window.search();self.wait(lambda:self.window.table is not None)
        self.assertTrue(self.window.search_result.corrected);self.assertEqual('Corrected',self.window.search_result.suggested_query)
        self.window.more('Original','Songs');self.window.more('Original','Songs')
        self.wait(lambda:self.window.more_task is None)
        self.assertEqual([one.id,two.id],[entry.id for entry in self.window.entries]);self.assertIsNone(self.window.search_cursor)
        self.assertEqual([('first','Original','Songs',False),('more',cursor)],calls);self.assertTrue(self.window.player.source().isEmpty())

    def test_only_deliberate_player_intents_reach_room_controls_not_remote_seek_or_auto_queue(self):
        self.window.queue=[Track('online00001','One','Artist'),Track('online00002','Two','Artist')]
        with patch.object(self.window.rooms,'user_intent') as intent,patch.object(self.window,'run'):
            self.window.play_index(0,user=False);self.window.user_seek(1234,user=False);self.window.next_track(1,user=False)
            intent.assert_not_called()
            self.window.user_seek(4321);intent.assert_called_once()
            self.window.play_index(0,user=True);self.assertEqual(2,intent.call_count)

    def test_phone_sleep_timer_fades_last_eight_seconds_restores_volume_and_never_autoplays(self):
        self.window.audio.setVolume(.8)
        with patch('dkord_desktop.ui.time.monotonic',return_value=100):self.window.start_sleep(1)
        self.window.desired_playing=True
        with patch('dkord_desktop.ui.time.monotonic',return_value=156):self.window.tick()
        self.assertAlmostEqual(.4,self.window.audio.volume(),places=5);self.assertTrue(self.window.desired_playing)
        with patch('dkord_desktop.ui.time.monotonic',return_value=160):self.window.tick()
        self.assertAlmostEqual(.8,self.window.audio.volume(),places=5);self.assertFalse(self.window.desired_playing)
        self.assertIsNone(self.window.sleep_at);self.assertTrue(self.window.player.source().isEmpty());self.assertEqual([],self.provider.calls)

    def test_sleep_at_end_of_track_preempts_repeat_and_queue_advance(self):
        from dkord_desktop.qt import QMediaPlayer
        self.window.queue=[Track('online00001','Song','Artist')];self.window.desired_playing=True
        self.window.loaded_epoch=self.window.epoch;self.window.repeat.setCurrentIndex(1);self.window.start_sleep(end=True)
        with patch.object(self.window,'play_index') as advance:
            self.window.media_status(QMediaPlayer.MediaStatus.EndOfMedia)
        advance.assert_not_called();self.assertFalse(self.window.desired_playing);self.assertFalse(self.window.sleep_end_of_track)
        self.assertEqual([],self.provider.calls)

if __name__=='__main__':unittest.main()
