"""Isolated store/byte checks; actual installers execute separately on native CI."""
from pathlib import Path
import tempfile
import unittest
from dkord_desktop.upgrade_fixture import seed,verify,MARKER

class UpgradeFixtureTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'library';self.device=self.base/'accessible-device'
    def tearDown(self):self.temp.cleanup()
    def test_all_persisted_categories_and_original_audio_bytes_can_be_verified_after_reopen(self):
        seed(self.root,self.device);result=verify(self.root,decode=True)
        self.assertTrue(all(result[key] is True for key in ('library','likes','playlists','history','settings','queue','privateDownload','deviceDownload','studioSources','studioClips','audioDecoded')))
        self.assertTrue((self.root/MARKER).is_file())
    def test_qa_seed_cannot_overwrite_a_library_or_existing_device_folder(self):
        self.root.mkdir();source=self.root/'valuable-original';source.write_bytes(b'never reset')
        with self.assertRaises(ValueError):seed(self.root,self.device)
        with self.assertRaises(ValueError):verify(self.root)
        self.assertEqual(b'never reset',source.read_bytes());self.assertFalse((self.root/'library.sqlite3').exists())
    def test_lost_download_or_studio_bytes_are_not_reported_as_a_successful_upgrade(self):
        value=seed(self.root,self.device);file=self.root/next(iter(value['files']));before=file.read_bytes();file.write_bytes(b'changed')
        with self.assertRaises(ValueError):verify(self.root)
        file.write_bytes(before);next((self.root/'studio/sources').iterdir()).unlink()
        with self.assertRaises(FileNotFoundError):verify(self.root)
