"""Real native Qt widgets/events, not browser rendering. OS-level IME/live-provider acceptance is separate."""
import tempfile
import time
import unittest
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QDialog,QLineEdit,QPushButton
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

if __name__=='__main__':unittest.main()
