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

if __name__=='__main__':unittest.main()
