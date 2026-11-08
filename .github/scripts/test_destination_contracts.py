"""Additive destination/source safety contracts. Real DB/media/Compose tests remain mandatory in Actions."""
from pathlib import Path
import re
import sqlite3
import unittest
ROOT = Path(__file__).resolve().parents[2]
def read(path):
    return (ROOT / path).read_text()
BASE = 'app/src/main/java/app/dkord/'
class DestinationContractsTest(unittest.TestCase):
    def test_download_migration_only_adds_columns_and_preserves_old_rows_byte_for_byte(self):
        source = read(BASE + 'data/db/AppDatabase.kt')
        sql = re.findall(r'db.execSQL\("([^"]+)"\)', source)
        self.assertEqual(3, len(sql))
        self.assertTrue(all(q.startswith('ALTER TABLE downloads ADD COLUMN ') for q in sql))
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE downloads(trackId TEXT PRIMARY KEY, state TEXT, bytes INTEGER, localUri TEXT)')
        before = [('a', 'DONE', 42, 'content://media/external/audio/media/42'), ('b', 'PAUSED', 19, None)]
        db.executemany('INSERT INTO downloads VALUES (?,?,?,?)', before)
        for q in sql: db.execute(q)
        self.assertEqual(before, db.execute('SELECT trackId,state,bytes,localUri FROM downloads ORDER BY trackId').fetchall())
        self.assertEqual([('LEGACY', None, None)] * 2, db.execute('SELECT location,deviceUri,deviceTree FROM downloads').fetchall())
        self.assertNotIn('fallbackToDestructiveMigration', source)
    def test_private_publish_never_uses_public_media_or_fallback_device_save(self):
        storage = read(BASE + 'data/download/DownloadStorage.kt')
        private = storage.split('fun publishPrivate(', 1)[1].split('fun stageCopy(', 1)[0]
        for bad in ('MediaStore', 'publishToTree', 'getExternalFilesDir'): self.assertNotIn(bad, private)
        self.assertIn('File(context.filesDir, "offline")', storage)
        strict = storage.split('fun publishToDevice(', 1)[1].split('/** Legacy', 1)[0]
        self.assertIn('throw IOException', strict)
        self.assertNotIn('runCatching', strict)
        self.assertNotIn('publishPrivate', strict)
    def test_online_studio_does_not_enqueue_or_persist_provider_streams(self):
        vm = read(BASE + 'ui/studio/StudioViewModel.kt')
        importer = read(BASE + 'data/studio/StudioOnlineImporter.kt')
        self.assertNotIn('downloads.enqueue', vm)
        self.assertIn('online.import(id, track)', vm)
        self.assertIn('importPreparedAudio', importer)
        self.assertIn('downloader.fetch', importer)
        self.assertNotIn('DownloadManager', importer)
        repo = read(BASE + 'data/studio/StudioRepository.kt')
        self.assertIn('pendingImports.add(file.name)', repo)
        self.assertIn('finally { file.delete(); pendingImports.remove(file.name) }', repo)
        self.assertIn('setOf("import", "online")', repo)
    def test_destination_snapshot_existing_audio_and_public_copies_survive(self):
        manager = read(BASE + 'data/download/DownloadManager.kt')
        worker = read(BASE + 'data/download/DownloadWorker.kt')
        host = read(BASE + 'ui/common/DownloadDestination.kt')
        self.assertIn('deviceTree: String? = null', manager)
        self.assertIn('row.deviceTree', worker)
        self.assertIn('item.download.localUri?.takeIf(storage::exists)', worker)
        self.assertIn('dao.staged(id, uri, size, res.mime)', worker)
        self.assertNotIn('storage.delete(d.deviceUri', manager)
        self.assertNotIn('rememberSaveable { mutableStateOf<List<Track>', host)
        self.assertIn('selections.save(pending.tracks)', host)
        self.assertIn('settings.saveDownloadTree(tree.toString())', host)
        self.assertIn('enqueue(tracks, DownloadLocation.DEVICE, tree.toString())', host)
    def test_local_copies_do_not_require_network_or_reset_sibling_ownership(self):
        dao = read(BASE + 'data/db/Daos.kt')
        manager = read(BASE + 'data/download/DownloadManager.kt')
        worker = read(BASE + 'data/download/DownloadWorker.kt')
        self.assertIn('workDataOf(LOCAL_ONLY to true)', manager)
        self.assertIn('"$WORK_NAME-local-copies"', manager)
        self.assertIn('trackId NOT IN (:activeIds)', dao)
        self.assertIn('(:localOnly = 0 OR localUri IS NOT NULL)', dao)
        self.assertIn('dao.resetRunning(System.currentTimeMillis(), manager.active.keys.toList())', worker)
        self.assertIn('if (localOnly) throw java.io.FileNotFoundException', worker)
        self.assertIn('manager.active.remove(id, job)', worker)
    def test_old_and_new_native_classes_cannot_be_silently_skipped(self):
        flow = read('.github/workflows/validate-pr.yml')
        for c in ('SearchKeyboardViewportTest','StudioAudioExportTest','StudioClipEditorTest','StudioExportPublicationTest',
                  'ListenAgainTest','RelatedPlaybackRoutingTest','OnlineStudioAndStorageTest','DownloadDestinationTest','StudioSongPickerTest'):
            self.assertIn('--required-class app.dkord.' + c, flow)
        self.assertNotIn('continue-on-error', flow)
        self.assertNotIn('fallbackToDestructiveMigration', read(BASE + 'data/db/AppDatabase.kt'))
if __name__ == '__main__': unittest.main()
